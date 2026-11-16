"""Search the corpus. A query is read, in order, as:

1. a citation («ف 418 ق.ل.ع», «مدونة الأسرة 53», «ج.ر 7533», «2.22.729») or a code by any of its names («قانون
   السير», «code pénal»): the answer jumps to it, or says it is not held here yet and where to read it;
2. words, the words that only ask («واش», «كيفاش», «est-ce que») set aside: BM25 over the folded, stemmed index, every word required, in an article or in a text's title;
3. if nothing is found, the query as the law says it, from the approved everyday-words list («AMO» →
   «التأمين الإجباري الأساسي عن المرض»);
4. then, the query in Latin letters, as typed on an Arabic keyboard («hgtzg» → «الفصل»);
5. if still nothing, any of the words.

Words between quotes («"القوة القاهرة"», «"العقد"») are searched as typed: each word whole and unstemmed, in that order,
side by side (folded as everywhere: harakat, hamzas, letter case and the punctuation between words do not count), the
first word with or without the letters Arabic writes on its front («بالقوة القاهرة», «والعقد»), with no repair, no
everyday word and no meaning search.

Results come grouped by text (a text's best articles under it), texts known to be repealed left out unless
asked for. Every search is logged with its count and no trace of who searched.
"""
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import ma_law
from django.conf import settings
from django.db import close_old_connections

from apps.corpus.services.citations import resolve
from apps.corpus.services.codes import ALONE, code_named
from apps.search.models import SearchEntry, SearchLog
from apps.search.services import vocab
from apps.search.services.search.asking import _constitution_of_year, _flipped, asked_words
from apps.search.services.search.bm25 import LIMIT, _bm25, _brief, _exact_hits, _texts, _topic_lift, _under_heading
from apps.search.services.search.quotes import _exact_terms, _phrase, quoted
from apps.search.services.search.snippets import SNIPPET, snippet
from apps.topics.services import kit
from config.timing import laps

# The longest question read, in characters: a search's and the questions people asked (QUERY_MOST), what the box
# suggests from and «ابحث في هذا النص» (TYPED_MOST). The views cut what they are sent to these before anything reads it.
QUERY_MOST = 300
TYPED_MOST = 200
_EMBED: ThreadPoolExecutor


def _new_pool() -> None:
    """This process's threads for the question's vector. gunicorn --preload forks its workers from a master that ran a
    search (config/wsgi.py warms it): a pool made there told each worker it had an idle thread it never had, so no vector
    came and every search waited for its timeout (31 Oct 2026). A fork makes its own."""
    global _EMBED
    _EMBED = ThreadPoolExecutor(max_workers=4, thread_name_prefix='search-embed')


_new_pool()
os.register_at_fork(after_in_child=_new_pool)


def _vector(early, q: str):
    """The question's vector, asked early (`early`) or now; None when it does not come in the model server's time and a
    second: the words answer alone, as when the server is down."""
    from apps.search.services import meaning
    if early is None:
        return meaning.embed_query(q)
    try:
        return early.result(timeout=meaning.TIMEOUT + 1)
    except Exception:  # noqa: BLE001 — no meaning in time: the words alone answer
        return None


def _embed(q: str):
    from apps.search.services import meaning
    try:
        return meaning.embed_query(q)
    finally:
        close_old_connections()   # a thread's own database connection, if the cache ever opened one
PER_TEXT = 2           # articles shown under a text, then «و N مواد أخرى» (P9 of the polish review)

PAGE = 10              # texts a page
AFTER_KINDS = {'decree', 'order', 'decision', 'circular'}   # N11: what SEARCH_MEANING_AFTER='rules' moves after
TITLE_BOOST = 2.0      # a law or decree whose title (or popular name) holds every searched word, over texts that mention them

# The kinds a title boost lifts: the texts that make the rules. A court's decision or an opinion names the law it is
# about in its title, and is not where a reader starts.
RULE_KINDS = {'constitution', 'organic_law', 'law', 'dahir', 'decree_law', 'decree', 'code'}
JUMP_STATES = {'found', 'text_only', 'issue', 'repealed'}


def search(query: str, *, types: list[str] | None = None, years: tuple = (None, None), repealed: bool = False,
           page: int = 1, log: bool = True, via: str = '', lang: str = 'ar') -> dict:
    q = query.strip()[:QUERY_MOST]
    out = {'query': q, 'jump': None, 'understood_as': 'words', 'repaired': None, 'partial': False, 'texts': 0, 'articles': 0,
           'page': page, 'pages': 0, 'results': [], 'asked': None, 'exact': []}
    if not q:
        return out
    lap = laps()        # each stage's time, in the answer's Server-Timing header (B27)
    # Words between quotes are searched as typed (31 Oct 2026); a citation or a code's name is read in the
    # words outside them.
    phrases, out['exact'], plain = quoted(q)
    if not phrases:
        plain = q
    folded = ma_law.fold(plain)
    # «constitution» is the Constitution alone, never inside «constitution d'une société».
    # «ق 31.08» and «المادة 225 المكررة» are read as the library's box reads them (W3 of the library-search review); when one
    # of them names what is opened, the words searched beside it are cut from the same spelling.
    from apps.corpus.services.find import spelled
    read = spelled(plain)
    citations = [c for c in ma_law.parse_query(read)
                 if not (c.get('code') in ALONE and not c.get('article') and folded not in
                         {ma_law.fold(n) for n in ALONE[c['code']]})]
    if plain and not any(c.get('code') for c in citations) and (named := code_named(plain)):
        citations.append({'kind': 'text', 'code': named[0], 'raw': named[1]})
    on = None
    if dated := _constitution_of_year(plain):
        citations, on = dated
    for citation in citations:
        found = resolve(citation, on=on)
        if on and found.get('text'):
            found['name'] = found['text']['name']        # «دستور المملكة المغربية لسنة 1996», not the code's own name
        flipped = _flipped(citation) if found['state'] not in JUMP_STATES else None
        if flipped:
            # A law's number typed the wrong way round («12.67» for 67.12), found the right way: said, then opened.
            again = resolve(flipped)
            if again['state'] in JUMP_STATES:
                found = again
                out['repaired'] = flipped['text_number'].replace('-', '.')
        if found['state'] in JUMP_STATES or (out['jump'] is None and found['state'] == 'not_in_corpus'):
            out['jump'] = found
            if found['state'] in JUMP_STATES:
                break
    if out['jump']:
        out['understood_as'] = 'citation'
    # The articles people know by their number or a name (famous.py, F3–F6 of the famous-articles review, 9 Nov 2026): read here,
    # shown on the first page above the answers.
    from apps.search.services import famous
    known = famous.read(plain, citations) if plain and not phrases and not out['jump'] and page == 1 else None
    lap('cite')
    # Darija in Latin letters (B6): searched in Arabic letters as the law spells its words, and said.
    from apps.search.services.spelling import arabizi
    latin = arabizi(q) if not out['jump'] and not phrases else None
    if latin:
        # Its words too are the Arabic reading's from here on (RD10 of the readers review: the words searched were
        # still the Latin letters', and «bghit ntala9 mn rajli» led with a wali's decision that holds «Mn,»).
        q = plain = out['arabizi'] = out['repaired'] = latin
    # The question's vector asked from the model server now, while the words are searched (PX10 of
    # the where-it-trips review: the two waited one after the other, up to a second each). Read where meaning is used; unused, it is kept a
    # week in the cache anyway.
    early = _EMBED.submit(_embed, q) if settings.SEARCH_MEANING and not phrases else None
    filters = {'types': types or [], 'years': years, 'repealed': repealed, 'lift': _topic_lift(q)}
    jump = out['jump']
    words = asked_words(read if jump and read != plain and not latin else plain) if plain else ''
    if words != q and not phrases and not (jump and read != plain):
        out['asked'] = words
    cited = jump if jump and jump['state'] == 'found' and jump.get('article') else None
    if cited:
        # A found article is the answer (B8: a citation keeps its exact path): the words around the citation are
        # searched, not its own letters and numbers («ف 418 ق.ل.ع» found three annexes holding «ف», «ق» and «418»).
        words = ma_law.fold(words).replace(ma_law.fold(cited['citation'].get('raw') or ''), ' ').strip()
    terms, said = ma_law.search_terms(words), words
    plain_terms = terms         # the words outside the quotes, which a snippet marks by their stems
    full = False                # the index's LIMIT entries read before the quotes were read again as typed
    if phrases:
        # Found as typed or not at all: no everyday word, no repair, no spelling, no meaning, never some of the words.
        if jump and jump['citation'].get('code') and not jump['citation'].get('article'):
            # «مدونة الأسرة "النفقة"»: the code is said above, and its name is not asked of the texts' words.
            plain_terms = ma_law.search_terms(ma_law.fold(words).replace(ma_law.fold(jump['citation']['raw'] or ''), ' '))
        terms = plain_terms + [t for t in _exact_terms(phrases) if t not in plain_terms]
        hits, full = _exact_hits(terms, phrases, **filters)
        everyday = ''
    else:
        # A door's words may hold an asking word («مول الدار ما بغاش يصلح»): the query as typed is one of them too.
        everyday = q if vocab.whole(q) else words
        hits = [] if vocab.whole(everyday) else _bm25(terms, all_words=True, phrase=_phrase(words), **filters)
    if not hits and not phrases:
        # The everyday-words list: «AMO» searched as «التأمين الإجباري الأساسي عن المرض».
        # The forms as typed first, then without the asking words (HM10 of the hard-moment review: «garde à vue»
        # lost its «à» and was searched as «garde», a child's custody).
        typed = [asked_words(r) for r in vocab.rewrites(q)] if q != everyday else []
        for rewrite in dict.fromkeys([*typed, *vocab.rewrites(everyday)]):
            again = ma_law.search_terms(rewrite)
            hits = _bm25(again, all_words=True, phrase=_phrase(rewrite), **filters)
            if hits:
                terms, said, out['repaired'], out['understood_as'] = again, rewrite, rewrite, 'everyday'
                break
        if not hits and vocab.whole(everyday):
            hits = _bm25(terms, all_words=True, phrase=_phrase(words), **filters)
        # Still nothing: what the question's everyday words mean, alone («واش الصابو قانوني؟» → «توقيف المركبات»), before
        # any of its words (R6 of the road plan: a Darija question's other words are seldom the law's).
        if not hits and (meant := (q != everyday and vocab.meanings(q)) or vocab.meanings(everyday)):
            again = ma_law.search_terms(meant)
            hits = _bm25(again, all_words=True, phrase=_phrase(meant), **filters)
            if hits:
                terms, said, out['repaired'], out['understood_as'] = again, meant, meant, 'everyday'
    if not hits and words and not phrases:
        for _, candidate in ma_law.layout_candidates(q):
            again = ma_law.search_terms(candidate)
            hits = _bm25(again, all_words=True, **filters)
            if hits:
                terms, said, out['repaired'], out['understood_as'] = again, candidate, candidate, 'repaired'
                break
    if not hits and not out['jump'] and not phrases:
        # A word one letter away from the law's (B6): «الطلاف» searched as «الطلاق», and said.
        from apps.search.services.spelling import corrected
        fix = corrected(words)
        if fix:
            again = ma_law.search_terms(fix)
            hits = _bm25(again, all_words=True, phrase=_phrase(fix), **filters)
            if hits:
                terms, said, out['repaired'], out['understood_as'] = again, fix, fix, 'spelling'
    jump = out['jump']
    named_code = jump and jump['citation'].get('code') and not jump['citation'].get('article')
    if not hits and named_code and not phrases:
        # «حقوق المرأة في الدستور»: the code is said above, the rest of the words are searched here.
        rest = ma_law.fold(words).replace(ma_law.fold(jump['citation']['raw'] or ''), ' ')
        again = ma_law.search_terms(rest)
        if again and again != terms:
            hits = _bm25(again, all_words=True, **filters)
            terms = again if hits else terms
    # A code asked for by name: texts holding one of its words («code», «مدونة») are other codes, not answers.
    if not hits and len(terms) > 1 and not named_code and not phrases:
        hits = _bm25(terms, all_words=False, **filters)
        out['partial'] = bool(hits)
        if hits and out['understood_as'] == 'words':
            out['understood_as'] = 'some_words'
    lap('words')

    # Meaning (B7, behind SEARCH_MEANING until the test set says it helps): the articles nearest the question, fused
    # with what the words found; with nothing found by the words, the nearest alone.
    by_words, by_meaning = {h[0] for h in hits}, set()      # each result says how it was found (B15)
    # A question inside a named code (C12 of the constitution review): «ما هي اللغات الرسمية في الدستور» is searched in
    # that code first, by its words and by meaning, and the code's articles lead; the other texts follow as found.
    inside = ''
    if settings.SEARCH_INSIDE and named_code and jump['state'] in ('found', 'repealed') and jump.get('text'):
        rest = ma_law.search_terms(ma_law.fold(words).replace(ma_law.fold(jump['citation']['raw'] or ''), ' '))
        if rest or phrases:
            inside = jump['text']['path']
            scope = {'types': [], 'years': (None, None), 'repealed': True, 'within': inside}
            if phrases:
                mine = _exact_hits(rest + [t for t in _exact_terms(phrases) if t not in rest], phrases, **scope)[0]
            else:
                mine = _bm25(rest, all_words=True, **scope) or _bm25(rest, all_words=False, **scope)
            by_words |= {h[0] for h in mine}
            if settings.SEARCH_MEANING and not phrases:
                from apps.search.services import meaning
                vector = _vector(early, q)
                if near := meaning.nearest(vector, types=[], years=(None, None), repealed=True, within=inside,
                                           limit=20) if vector else []:
                    entries = {path: (i, tp, tt) for i, path, tp, tt in SearchEntry.objects.filter(
                        kind=SearchEntry.Kind.ARTICLE, path__in=[n[0] for n in near]).values_list(
                        'id', 'path', 'text_path', 'text_type')}
                    by_meaning |= {entries[n[0]][0] for n in near if n[0] in entries}
                    mine = meaning.fuse(mine, near, entries, settings.SEARCH_FUSION_WEIGHT)
            hits = mine + [h for h in hits if h[2] != inside]
            lap('inside')
    if phrases and out['understood_as'] == 'words':
        out['understood_as'] = 'exact'
    # A text opened by its number («12.67», «67.12») stands alone too: no decree found by meaning under it (HM44 of
    # the hard-moment review: three unrelated decrees came «by meaning» under the lease law).
    numbered = jump and jump['state'] in JUMP_STATES and jump['citation'].get('text_number') and not jump['citation'].get('article')
    if settings.SEARCH_MEANING and not named_code and not cited and not numbered and not phrases:
        from apps.search.services import meaning
        vector = _vector(early, q)
        if vector:
            near = meaning.nearest(vector, types=filters['types'], years=years, repealed=repealed)
            entries = {path: (i, tp, tt) for i, path, tp, tt in SearchEntry.objects.filter(
                kind=SearchEntry.Kind.ARTICLE, path__in=[n[0] for n in near]).values_list('id', 'path', 'text_path', 'text_type')}
            if near and not hits:
                out['understood_as'], out['partial'] = 'meaning', False
            by_meaning = {entries[n[0]][0] for n in near if n[0] in entries}
            hits = meaning.fuse(hits, near, entries, settings.SEARCH_FUSION_WEIGHT)
            # An article found by meaning alone, beside what the words found, needs SEARCH_MEANING_FLOOR of likeness
            # (N11 of the read-and-trusted review: the hospitals' internal rules came second for an eviction).
            if by_words and settings.SEARCH_MEANING_FLOOR:
                likeness = {entries[p][0]: sim for p, _, sim in near if p in entries}
                hits = [h for h in hits if h[0] in by_words or likeness.get(h[0], 1.0) >= settings.SEARCH_MEANING_FLOOR]
        lap('meaning')
    groups: dict[str, dict] = {}
    for entry_id, kind, where, _, text_type, score in hits:
        g = groups.setdefault(where, {'score': score, 'title_match': False, 'articles': [], 'found': 0, 'type': text_type})
        if kind == SearchEntry.Kind.TEXT:
            g['title_match'] = True
        else:
            g['found'] += 1
            g['articles'].append(entry_id)
    if not out['partial'] and groups:
        # Every word was required, so a title entry among the hits holds them all.
        groups = dict(sorted(groups.items(), key=lambda kv: -kv[1]['score'] * (
            TITLE_BOOST if kv[1]['title_match'] and kv[1]['type'] in RULE_KINDS else 1)))
    if settings.SEARCH_MEANING_AFTER and by_words and groups:
        # Found by meaning alone, after the texts the words found, each in its order (N11): every such text ('all'), or
        # only the decrees, orders and decisions ('rules': the hospitals' rules came second for an eviction, while a
        # code found by meaning is often a Darija question's answer).
        worded = {k for k, g in groups.items() if g['title_match'] or any(a in by_words for a in g['articles'])}
        moved = {k for k, g in groups.items() if k not in worded
                 and (settings.SEARCH_MEANING_AFTER == 'all' or g['type'] in AFTER_KINDS)}
        groups = dict(sorted(groups.items(), key=lambda kv: kv[0] in moved))
    if inside in groups:
        groups = {inside: groups.pop(inside), **groups}
    out['texts'] = len(groups)
    # How many texts of each kind were found, for the filters' row (B15). Counted in the entries read: when the words
    # filled all LIMIT of them, a filter reads LIMIT of its own kind and finds more (PX17), so the row shows no number.
    out['kinds'] = dict(Counter(g['type'] for g in groups.values()))
    out['capped'] = len(by_words) >= LIMIT or full
    out['articles'] = sum(1 for h in hits if h[1] == SearchEntry.Kind.ARTICLE)
    out['pages'] = (len(groups) + PAGE - 1) // PAGE
    shown = list(groups.items())[(page - 1) * PAGE: page * PAGE]
    # Under a text, the articles a heading names the words over come first, in the text's order: «التعويض عن الفصل»
    # opens the section of that name at its first article, not the article that says the words most. Read for the
    # page's texts only (B27: the headings of 600 hits were stemmed for ten texts).
    led = _under_heading([a for _, g in shown for a in g['articles']], _phrase(phrases[0] if phrases else said))
    for _, g in shown:
        first = sorted((a for a in g['articles'] if a in led), key=led.get)
        g['articles'] = (first + [a for a in g['articles'] if a not in led])[:PER_TEXT]
    # A page of answers reads its texts' rows and its articles' rows: two queries, no corpus table (B24).
    texts = _texts(where for where, _ in shown)
    articles = SearchEntry.objects.in_bulk([a for _, g in shown for a in g['articles']])
    lap('page')
    for where, g in shown:
        text = texts.get(where)
        if text is None:
            continue
        # Where the words come from, for the result's stamp: the BO issue and page, or a consolidation.
        out['results'].append({
            'text': {**_brief(text), 'year': text.signed_year, 'issue': text.issue or None,
                     'consolidation': text.consolidation or None},
            'title_match': g['title_match'],
            'articles': [{'label': articles[a].label, 'eid': articles[a].eid, 'path': articles[a].path,
                          'heading_path': articles[a].heading_path, 'page': articles[a].page,
                          'changes': articles[a].changes, 'found_by': _found_by(a, by_words, by_meaning),
                          'snippet': snippet(articles[a].body, plain_terms if phrases else terms, *SNIPPET, exact=phrases)}
                         for a in g['articles'] if a in articles],
            # The other articles that hold the words, found inside the text («ابحث في هذا النص»).
            'more': max(0, g['found'] - PER_TEXT),
        })
    out['answer'] = _answer(out, q, terms, articles) if page == 1 and settings.SEARCH_ANSWER and not phrases else None
    lap('snippets')
    if known:
        # The famous article first (C2), then «490 في نصوص أخرى» for a number, or «did you mean» for a word the law
        # uses that everyday speech reads otherwise («الفساد»).
        out['famous'] = famous.cards(known['rows'], word=known['word'], lang=lang) if known['rows'] else []
        out['maybe'] = famous.maybe(known['maybe']) if known['maybe'] else []
        if known['number']:
            out['choices'] = famous.choices(known['number'], [c['path'] for c in out['famous']], known['word'])
        lap('famous')
    if out.get('arabizi') and out['understood_as'] in ('words', 'some_words'):
        out['understood_as'] = 'arabizi'      # «كتبت بالحروف اللاتينية، بحثنا عن …» (B6)
    out['log'] = None
    # Words about violence are counted, never kept as typed (F14 of the family plan).
    out['private'] = kit.private(q)
    if log:
        hidden = out['private']
        typed = out['query']        # what the reader typed, not its Arabic spelling (B6)
        out['log'] = SearchLog.objects.create(query='' if hidden else typed, folded='' if hidden else ma_law.fold(typed)[:300],
                                              results=out['texts'] + bool(out['jump']),
                                              understood_as='private' if hidden else out['understood_as'],
                                              shown=[] if hidden else shown_paths(out), via=via).pk
        lap('log')
    return out


def _found_by(entry: int, words: set, near: set) -> str:
    return 'both' if entry in words and entry in near else 'words' if entry in words else 'meaning'


def _answer(out: dict, q: str, terms: list[str], articles: dict) -> dict | None:
    """The box that answers first (B15): for a question, the first article's sentence that answers it best, in the law's
    words; for «شحال» and its kind, the number in bold. Not for a citation, a name, a few words, or words found apart."""
    from apps.search.services import answer, surrogates

    if out['jump'] or out['partial'] or not out['results'] or not out['results'][0]['articles'] or not answer.asks(out['query']):
        return None
    first = out['results'][0]['articles'][0]
    if first['found_by'] != 'both':
        return None         # words and meaning agree on it, or no box (the tuning sets: 71% right so, 40% on words alone)
    row = next((r for r in articles.values() if r.path == first['path']), None)
    if row is None:
        return None
    amount = answer.asks_amount(out['query']) or answer.asks_amount(q)
    sentence = answer.best_sentence(row.body, terms, amount=amount, facts=surrogates.facts(row.path) if amount else [])
    if not sentence:
        return None
    return {'path': row.path, 'label': row.label, 'text': out['results'][0]['text'], 'page': row.page,
            'found_by': first['found_by'], 'sentence': sentence, 'amount': amount and any(s['num'] for s in sentence)}


def shown_paths(answer: dict) -> list[str]:
    """The articles a page of answers shows, in order, the citation card's first (B3): what the log keeps and what a
    judge grades."""
    jump = answer.get('jump') or {}
    out = [jump['article']['path']] if jump.get('article') else []
    out += [c['path'] for c in answer.get('famous') or [] if c['path'] not in out]
    for r in answer['results']:
        out.extend(a['path'] for a in r['articles'] if a['path'] not in out)
    return out
