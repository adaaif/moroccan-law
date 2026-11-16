"""What the box offers as a reader types: what a citation would open and the articles people know by their number,
the topics, guides and words of the law the letters open, the shelf's codes by their everyday names and the texts whose
title holds the words; and `warm`, what a suggestion and a search read on first use, read before a worker answers
anyone."""
import ma_law

from apps.corpus.services.addresses import text_path
from apps.corpus.services.citations import resolve
from apps.corpus.services.codes import SHELF, texts_of
from apps.search.models import SearchEntry
from apps.search.services.search.bm25 import _brief, _texts
from apps.search.services.search.query import TYPED_MOST, search
from apps.search.services.search.titles import SUGGEST_FROM, _titles
from apps.topics.services import kit
from config.timing import laps

SUGGEST_MOST = 6


def suggest(query: str) -> dict:
    """As you type: what a citation would open; then the topics and guides the words name, the texts whose title holds
    every word typed (the last one as a prefix; laws before decrees, the newest first) and the word of the law they
    open. Six at most besides the citations (P8 of the polish review: «كراء» used to offer four formal titles that
    filled the screen, and not the renting guide). Nothing but citations and famous articles before SUGGEST_FROM
    letters."""
    q = query.strip()[:TYPED_MOST]
    out = {'query': q, 'citations': [], 'topics': [], 'guides': [], 'texts': [], 'words': [], 'repaired': None, 'finds': []}
    if not q:
        return out
    lap = laps()
    # What the library's reader finds that the suggestions never read (W3 of the library-search review: one reader for both
    # boxes): a text by its day in either calendar, a short form, a finance law's year, a name a text had.
    from apps.corpus.services.find import find
    out['finds'] = [{'path': a['path'], 'name': a['name'], 'type': a['type'], 'number': a['number'], 'why': a['why']}
                    for a in find(q, beyond=True)['answers'] if a['kind'] == 'text'][:4]
    lap('finds')
    # Darija in Latin letters suggests what it would search («kra» → «الكراء»: the renting guide, not two orders whose
    # title holds «KRA»; UX7 of the phone-test review).
    from apps.search.services.spelling import arabizi
    latin = arabizi(q)
    if latin:
        q = out['repaired'] = latin
    typed = [_bare(w) for w in ma_law.tokens(q)]
    enough = sum(map(len, typed)) >= SUGGEST_FROM
    if enough:
        out['topics'] = _topics(q, typed)[:1]
        out['guides'] = (kit.matching(q) + _guides(typed))[:2]
        out['words'] = _words(typed)[:1]
    lap('topics')
    limit = SUGGEST_MOST - len(out['topics']) - len(out['guides']) - len(out['words'])
    from apps.corpus.services.find import spelled
    for citation in ma_law.parse_query(spelled(q)):
        found = resolve(citation)
        if found['state'] != 'unknown':
            out['citations'].append(found)
    out['citations'] += _completions(q, out['citations'])
    # A text a citation opens already is not offered twice.
    cited = {c['text']['path'] for c in out['citations'] if c.get('text')}
    out['finds'] = [f for f in out['finds'] if f['path'] not in cited]
    # The articles people know by their number or a name (F7 of the famous-articles review): «222» offers the penal code's,
    # «زواج القا» the family code's art. 20; after a citation that opens one already.
    from apps.search.services import famous
    opened = {c['article']['path'] for c in out['citations'] if c.get('article')}
    out['citations'] += [c for c in famous.suggestions(q) if c['article']['path'] not in opened]
    lap('cite')
    words = ma_law.tokens(q)
    rows = _titles(words, limit)
    if not rows:
        for _, candidate in ma_law.layout_candidates(q):
            rows = _titles(ma_law.tokens(candidate), limit)
            if rows:
                out['repaired'] = candidate
                break
    lap('titles')
    codes = _codes(typed) if enough else []
    # The laws of the topic the words name, before any title that merely holds them (RD9 of the readers review:
    # «الطلا» offered three protectorate dahirs on French divorce law and no family code; 13 of 33 beginnings filled
    # with texts of 1915 to 1960).
    # Four letters typed at least: «عقد» opens a word of five topics, and names none. Counted as typed, «ال» included:
    # «الطلا», «الطرد» and «الشيك» are stems of three letters (the first rule counted the stems, and offered nothing).
    own = _topic_codes(out['topics'][0]['slug']) if out['topics'] and len(q.replace(' ', '')) >= 4 else []
    known = {f['path'] for f in out['finds']}
    found = [p for p in dict.fromkeys(codes + own + [r[0] for r in rows]) if p not in known][:max(limit, 2)]
    texts = _texts(found)
    out['texts'] = [_brief(texts[p]) for p in found if p in texts]
    lap('texts')
    return out


def warm() -> None:
    """What a suggestion reads on first use (the titles, the topics', guides' and words' matchers, the citation reader),
    read before a worker answers anyone (N12 of the read-and-trusted review): with several workers and few readers,
    nearly every suggestion met a cold one, which read the titles and built its matchers first."""
    for q in ('مدونة الشغل', 'البيرمي بالنقط', 'الفصل 418 من ق.ل.ع'):
        suggest(q)
    # And the French words a Latin-letter question is weighed against, slow to build on first use (RD10).
    from apps.search.services.spelling import french_words
    french_words()
    # And what a search's words read on first use: the corpus's term counts (450,000, about a second to read) and the
    # spelling's and thesaurus's tables: a cold worker's «words» stage is many times slower than a warm one's (UX10 of
    # the phone-test review). Not logged as a search.
    from django.db import connection
    if connection.vendor == 'postgresql':      # the index is ParadeDB's: SQLite has none to warm
        search('الطرد', log=False)


COMPLETIONS = 4       # a text's articles offered as their number is typed


def _completions(q: str, citations: list[dict]) -> list[dict]:
    """A citation typed up to its number («مدونة السير 8») offers the text's other articles that start with it (80, 81…),
    in the text's order (B17 of the search plan): one query for every citation."""
    from django.db.models import Q

    typed = [c for c in citations if c.get('text') and c['text'].get('in_corpus') and (c['citation'].get('article') or '').isdigit()
             and q.rstrip().endswith(c['citation']['article'])]
    if not typed:
        return []
    wanted = Q()
    for c in typed:
        wanted |= Q(text_path=c['text']['path'], eid__startswith=f"art_{c['citation']['article']}")
    rows: dict[str, list] = {}
    for path, text, label, eid in (SearchEntry.objects.filter(wanted, kind=SearchEntry.Kind.ARTICLE)
                                   .order_by('text_path', 'order').values_list('path', 'text_path', 'label', 'eid')):
        rows.setdefault(text, []).append((path, label, eid))
    out = []
    for c in typed:
        exact = (c.get('article') or {}).get('path')
        more = [r for r in rows.get(c['text']['path'], []) if r[0] != exact][:COMPLETIONS]
        out += [{**c, 'state': 'found', 'article': {'label': label, 'eid': eid, 'path': path}, 'changes': []}
                for path, label, eid in more]
    return out


def _topic_codes(slug: str, most: int = 1) -> list[str]:
    """The address of a topic's first law that stands on the shelf (its code): no query, the shelf's map is kept in the
    process."""
    from apps.topics.services import topics
    topic = topics.find(slug)
    paths = _shelf_map()
    return [paths[key] for key in (topic or {}).get('codes', []) if paths.get(key)][:most]


def _codes(typed: list[str]) -> list[str]:
    """The addresses of the shelf's texts whose everyday name the typed words open: «مدونة» → the family code, the
    labour code…"""
    from apps.corpus.services.codes import CODES, NAMES, SHELF

    keys = [key for key, numbered in SHELF
            if _opens(typed, *(CODES[key] if numbered is None else numbered[2:]), *NAMES.get(key, []))]
    paths = _shelf_map()
    return [paths[key] for key in keys if paths.get(key)]


_SHELF: dict = {'generation': None, 'paths': {}}


def _shelf_map() -> dict[str, str]:
    """{shelf key: its text's address}, kept in the process while the corpus generation holds: a suggestion asks no
    query for the codes (59 ms on every keystroke before)."""
    from apps.corpus.services import generation

    gen = generation.current('corpus')
    if gen is None or gen != _SHELF['generation']:
        texts = texts_of(key for key, _ in SHELF)
        paths = {key: text_path(t.akn_uri) for key, t in texts.items() if t is not None}
        if gen is None:
            return paths
        _SHELF.update(generation=gen, paths=paths)
    return _SHELF['paths']


def _bare(word: str) -> str:
    return word[2:] if word.startswith('ال') and len(word) > 4 else word


def _opens(typed: list[str], *handles: str) -> bool:
    """Every typed word opens a word of one of the handles, «ال» set aside: «كرا» opens «الكراء»."""
    for handle in handles:
        words = [_bare(w) for w in ma_law.tokens(handle or '')]
        if words and all(any(w.startswith(t) for w in words) for t in typed):
            return True
    return False


def _topics(q: str, typed: list[str]) -> list[dict]:
    from apps.topics.services import topics

    found = topics.matching(q)
    # Then the topics a word of theirs opens, the one whose word is nearest what was typed first (RD9 of
    # the readers review: «الضريب» named the housing, by «ضريبة السكن», before the taxes, by «الضريبة»: the list's order decided).
    opened = []
    for t in topics.load():
        if t['slug'] in {x['slug'] for x in found}:
            continue
        handles = [h for h in (*t['name'].values(), *t['everyday'], *t['keywords']) if _opens(typed, h)]
        if handles:
            opened.append((min((len(ma_law.tokens(h)), len(h)) for h in handles), {'slug': t['slug'], 'name': t['name']}))
    found += [t for _, t in sorted(opened, key=lambda x: x[0])]
    return [{**t, 'path': f'/topics/{t["slug"]}'} for t in found]


def _guides(typed: list[str]) -> list[dict]:
    from apps.corpus.services.situations import shown

    return [{'slug': s['slug'], 'title': s['title'], 'path': f'/situations/{s["slug"]}'}
            for s in shown() if _opens(typed, *s['title'].values(), *s['searches'])]


def _words(typed: list[str]) -> list[dict]:
    from apps.explain.services import concepts

    return [{'slug': c['slug'], 'term': c['term'], 'path': f'/words/{c["slug"]}'}
            for c in concepts.load() if _opens(typed, *c['term'].values(), c['search'])]
