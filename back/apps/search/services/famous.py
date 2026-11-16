"""The articles people know by their number or by the public's name for them (9 Nov 2026, the famous-articles review F3–F9:
a reader who types 222 means that article). The list is `data/famous.json`, owner-provisional.

- A bare number («490») or an article cited without its code («الفصل 490», «المادة 20») shows the famous article of
  that number first, on a card, then «490 في نصوص أخرى»: the shelf's other codes that hold an article of that number
  (F3, F5; C2 «famous first»). The usual answers follow.
- A name the public gives it («العلاقات الرضائية», «وكالين رمضان») shows the same card (F6); a word the law uses
  that everyday speech reads otherwise («الفساد») only asks «did you mean» (`maybe`).
- The card holds the law's own words, «يُعرف في النقاش العام بـ…» (F8, C3), the article's changes as the Bulletin
  printed them, any bill that would change it as a proposal, and the articles that cite it, read from the law's words
  rather than chosen (F9: 493 cites 490).

A card costs a fixed number of queries whatever the list (the articles, their texts, their changes, the citing texts,
the citing articles' labels, the French): never one per card. The articles that cite inside the same code are read
once per corpus generation and kept in the cache.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import ma_law
from django.core.cache import cache
from django.db.models import F, Q

from apps.search.models import SearchEntry

FILE = Path(__file__).resolve().parent.parent / 'data' / 'famous.json'
BODY = 320              # characters of the law's words a card shows, cut at a word
CITERS = 6              # citing articles a card names; the rest are counted
SUGGESTED = 3           # famous articles offered while typing
CHOICES = 8             # codes «490 في نصوص أخرى» names

# Small words that do not make a name: «partage des biens» is one word long by this count, so it must be the whole
# question («partage des biens apres deces» is an inheritance).
_SMALL = {'de', 'des', 'du', 'la', 'le', 'les', 'l', 'd', 'a', 'au', 'aux', 'en', 'et', 'un', 'une', 'في', 'من', 'على',
          'بين', 'عن', 'و', 'ف', 'د', 'ديال'}
# Words around a name that do not change what is asked: «زواج القاصرات فالمغرب», «avortement au maroc».
_AROUND = {'فالمغرب', 'في', 'المغرب', 'بالمغرب', 'المغربي', 'المغربيه', 'القانون', 'قانون', 'au', 'maroc', 'le', 'la',
           'loi', 'droit', 'marocain', 'marocaine', 'en'}
_NUMBER = re.compile(r'^\d{1,4}$')


def _norm(s: str) -> str:
    return ' '.join(ma_law.fold(s).split())


@lru_cache(maxsize=1)
def table() -> dict:
    """The list as read once: its rows, the rows of each number, and each folded name's row."""
    rows = json.loads(FILE.read_text())['articles']
    numbers: dict[str, list[int]] = {}
    names: dict[str, int] = {}
    maybe: dict[str, int] = {}
    for i, row in enumerate(rows):
        numbers.setdefault(row['number'], []).append(i)
        for name in row['names']:
            names.setdefault(_norm(name), i)
        for name in row.get('maybe', []):
            maybe.setdefault(_norm(name), i)
    long = sorted(((n, i) for n, i in names.items() if len([w for w in n.split() if w not in _SMALL]) > 1),
                  key=lambda ni: -len(ni[0]))
    return {'rows': rows, 'numbers': numbers, 'names': names, 'maybe': maybe, 'long': long}


def _word(raw: str) -> str:
    """How an article was named: «الفصل» (fasl), «المادة» (madda), «article»; '' for a bare number."""
    head = _norm(raw).split()[0] if raw.strip() else ''
    if head in ('الفصل', 'فصل', 'ف', 'الفصول', 'الفصلين'):
        return 'fasl'
    if head in ('الماده', 'ماده', 'م', 'المواد', 'المادتين'):
        return 'madda'
    return 'art' if head.startswith('art') else ''


def read(plain: str, citations: list[dict]) -> dict | None:
    """What the question asks of the list, without the database: {'number', 'word', 'rows', 'maybe'}; None for nothing.
    `rows` are the famous articles to show (by number or by name), `maybe` those a «did you mean» line names."""
    t = table()
    folded = _norm(plain)
    number, word = None, ''
    if _NUMBER.match(folded):
        number = folded
    else:
        bare = next((c for c in citations if c.get('kind') == 'article' and c.get('article') and not c.get('code')
                     and not c.get('text_number') and not c.get('issue')), None)
        if bare and _NUMBER.match(bare['article']):
            number, word = bare['article'], _word(bare.get('raw') or '')
    if number is not None:
        rows = t['numbers'].get(number, [])
        # A bare number no famous article has is a year, an issue, an amount: searched as typed, no choice offered.
        return {'number': number, 'word': word, 'rows': rows, 'maybe': []} if rows or word else None
    words = [w for w in folded.split() if w not in _AROUND] or folded.split()
    whole = ' '.join(words)
    if whole in t['names'] or folded in t['names']:
        return {'number': None, 'word': '', 'rows': [t['names'].get(whole, t['names'].get(folded))], 'maybe': []}
    padded = f' {folded} '
    for name, i in t['long']:
        if f' {name} ' in padded:
            return {'number': None, 'word': '', 'rows': [i], 'maybe': []}
    if whole in t['maybe']:
        return {'number': None, 'word': '', 'rows': [], 'maybe': [t['maybe'][whole]]}
    return None


def suggested(typed: str) -> list[int]:
    """While typing (F7): the famous articles a number or the start of a name opens, «49» → art. 49 of the family code,
    then 490 and 491 of the penal code."""
    t = table()
    folded = _norm(typed)
    if not folded:
        return []
    digits = re.sub(r'^(?:الفصل|فصل|الماده|ماده|art|article)\s*', '', folded)
    if digits.isdigit() and len(digits) >= 2:
        exact = t['numbers'].get(digits, [])
        starting = [i for n, rows in sorted(t['numbers'].items(), key=lambda kv: (len(kv[0]), kv[0]))
                    if n != digits and n.startswith(digits) for i in rows]
        return (exact + starting)[:SUGGESTED]
    if len(folded) < 4:
        return []
    found = [i for name, i in t['names'].items() if name.startswith(folded) or f' {name} ' in f' {folded} ']
    return list(dict.fromkeys(found))[:SUGGESTED]


def of_text(path: str) -> dict[str, dict]:
    """{article number: its `known_as`} for a text's address: what its page and its head say of its famous articles
    (F10). No query once the shelf's addresses are kept."""
    from apps.corpus.services.addresses import text_path
    from apps.corpus.services.codes import CODE_TEXTS, CODE_URIS

    rows = [row for row in table()['rows'] if row['known_as']['ar'] or row['known_as']['fr']]
    # Only the list's codes can hold one: any other law is told so without a query (its page's ceiling, test_perf).
    tail = path.rstrip('/').rsplit('/', 1)[-1]
    rows = [row for row in rows if (row['code'] in CODE_URIS and text_path(CODE_URIS[row['code']]) == path)
            or CODE_TEXTS.get(row['code'], ('', ''))[1] == tail]
    if not rows:
        return {}
    paths = _paths()
    return {row['number']: row['known_as'] for row in rows if paths.get(row['code']) == path}


def _paths() -> dict[str, str]:
    from apps.search.services.search.suggestions import _shelf_map
    return _shelf_map()


def _cut(body: str) -> str:
    first = body.strip()
    if len(first) <= BODY:
        return first
    at = first.rfind(' ', 0, BODY)
    return first[:at if at > BODY // 2 else BODY].rstrip(' ،,؛;') + '…'


def _inner(paths: list[str]) -> dict[str, dict[str, list[str]]]:
    """{text address: {famous number: the eids of the same text's articles that cite it}}, read from the law's words
    (ma_cite: «الفصلين 490 و491» in art. 493). Kept for the corpus generation; on a miss one query reads the texts."""
    from apps.corpus.services import generation

    gen = generation.current('corpus') or 'none'
    keys = {p: f'famous:inner:{gen}:{p}' for p in paths}
    kept = cache.get_many(list(keys.values())) if gen != 'none' else {}
    out = {p: kept[k] for p, k in keys.items() if k in kept}
    missing = [p for p in paths if p not in out]
    if not missing:
        return out
    wanted = {row['number'] for row in table()['rows']}
    read: dict[str, dict[str, list[str]]] = {p: {} for p in missing}
    for path, eid, body in (SearchEntry.objects.filter(kind=SearchEntry.Kind.ARTICLE, text_path__in=missing)
                            .order_by('text_path', 'order').values_list('text_path', 'eid', 'body')):
        for c in ma_law.parse_citations(body or ''):
            n = c.get('article')
            if c.get('kind') == 'article' and n in wanted and not c.get('code') and not c.get('text_number') \
                    and eid != f'art_{n}':
                eids = read[path].setdefault(n, [])
                if eid not in eids:
                    eids.append(eid)
    if gen != 'none':
        cache.set_many({keys[p]: read[p] for p in missing}, timeout=7 * 24 * 3600)
    return {**out, **read}


def cards(rows: list[int], *, word: str = '', lang: str = 'ar') -> list[dict]:
    """The famous articles' cards, in a fixed number of queries. An article named as the question named it («الفصل»
    for a penal article, «المادة» for the family code's) comes first."""
    from apps.consolidation.models import Change
    from apps.corpus.models import Mention
    from apps.corpus.services.addresses import split_path, text_path
    from apps.search.services.search.bm25 import _brief, _texts

    t = table()
    paths = _paths()
    asked = [(t['rows'][i], paths.get(t['rows'][i]['code'])) for i in rows]
    asked = [(row, path) for row, path in asked if path]
    if not asked:
        return []
    wanted = Q()
    for row, path in asked:
        wanted |= Q(text_path=path, eid=f"art_{row['number']}")
    entries = {(e.text_path, e.eid): e for e in SearchEntry.objects.filter(wanted, kind=SearchEntry.Kind.ARTICLE)}
    asked = [(row, path) for row, path in asked if (path, f"art_{row['number']}") in entries]
    if not asked:
        return []
    uris = {path: split_path(path)[0] for _, path in asked}
    numbers = {row['number'] for row, _ in asked}
    # The changes the Bulletin printed (read or noted by Adala) and the bills that would make one (F9).
    # A reading shows once checked or confirmed (as citations.SHOWN); an official footnote (Adala's, the SGG's, the
    # DGI's) as it is; a model's reading never alone.
    shown_rows = (Q(source=Change.Source.READING, state__in=(Change.State.CHECKED, Change.State.CONFIRMED, Change.State.READ))
                  | Q(source__in=(Change.Source.ADALA, Change.Source.SGG, Change.Source.DGI))
                  | Q(source=Change.Source.BILL, state=Change.State.PROPOSED))
    changes = list(Change.objects.filter(shown_rows, text_uri__in=set(uris.values()), number__in=numbers)
                   .order_by(F('published_on').asc(nulls_last=True), 'issue')
                   .values('text_uri', 'number', 'verb', 'source', 'state', 'by_uri', 'issue', 'issue_bis', 'page',
                           'published_on'))
    # Other texts that cite the article (the links pipeline's mentions), and the same text's own articles that do.
    mentions = list(Mention.objects.filter(to_uri__in=set(uris.values()), to_number__in=numbers,
                                           kind__in=(Mention.Kind.CITES, Mention.Kind.APPLIES))
                    .exclude(from_uri=F('to_uri')).order_by('from_uri', 'from_eid')
                    .values_list('to_uri', 'to_number', 'from_uri', 'from_eid').distinct())
    inner = _inner(sorted({path for _, path in asked}))
    citing: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for row, path in asked:
        n = row['number']
        here = [(path, eid) for eid in inner.get(path, {}).get(n, [])]
        # A text that changed the article names it to change it: it is under «changes», not among those citing it.
        changers = {c['by_uri'] for c in changes if c['text_uri'] == uris[path] and c['number'] == n}
        there = [(text_path(f), e) for to, num, f, e in mentions if to == uris[path] and num == n and e and f not in changers]
        citing[(path, n)] = here + there
    shown = {pair for pairs in citing.values() for pair in pairs[:CITERS]}
    labels = {}
    if shown:
        named = Q()
        for p, e in shown:
            named |= Q(text_path=p, eid=e)
        labels = {(p, e): (label, at) for p, e, label, at in SearchEntry.objects.filter(named, kind=SearchEntry.Kind.ARTICLE)
                  .values_list('text_path', 'eid', 'label', 'path')}
    texts = _texts({path for _, path in asked} | {p for p, _ in shown} | {text_path(c['by_uri']) for c in changes if c['by_uri']})
    french = {}
    if lang == 'fr':
        from apps.translations.models import FrenchArticle
        from apps.translations.services import divisions
        french = {(fa.text_uri, fa.number): {'label': fa.label, 'body': _cut(divisions.trim(fa.body))}
                  for fa in FrenchArticle.objects.filter(text_uri__in=set(uris.values()), number__in=numbers)}
    out = []
    for row, path in asked:
        n = row['number']
        e = entries[(path, f'art_{n}')]
        text = texts.get(path)
        mine = [c for c in changes if c['text_uri'] == uris[path] and c['number'] == n]
        seen, made = set(), []
        for c in mine:
            if c['source'] == 'bill' or c['by_uri'] in seen:
                continue
            seen.add(c['by_uri'])
            by = texts.get(text_path(c['by_uri'])) if c['by_uri'] else None
            made.append({'verb': c['verb'], 'by': _brief(by) if by else None, 'published': c['published_on'],
                         'issue': f"{c['issue']}-bis" if c['issue_bis'] else (str(c['issue']) if c['issue'] else None),
                         'page': c['page']})
        bills = [{'by': _brief(texts[text_path(c['by_uri'])]) if text_path(c['by_uri']) in texts else None, 'verb': c['verb']}
                 for c in mine if c['source'] == 'bill']
        pairs = citing[(path, n)]
        cited = [{'label': labels[p][0], 'path': labels[p][1],
                  'text': _brief(texts[p[0]]) if p[0] != path and p[0] in texts else None}
                 for p in pairs[:CITERS] if p in labels]
        out.append({
            'path': e.path, 'label': e.label, 'number': n, 'code': row['code'], 'page': e.page,
            'heading_path': e.heading_path,
            'text': {**_brief(text), 'issue': text.issue or None, 'consolidation': text.consolidation or None} if text else None,
            'body': _cut(e.body),
            'french': french.get((uris[path], n)),
            'known_as': row['known_as'],
            'changes': made, 'proposed': bills,
            'cited_by': cited, 'cited_more': max(0, len(pairs) - len(cited)),
        })
    if word:
        lead = {'fasl': ('الفصل',), 'madda': ('المادة',), 'art': ()}.get(word, ())
        out.sort(key=lambda c: not any(c['label'].startswith(w) for w in lead))
    return out


def maybe(rows: list[int]) -> list[dict]:
    """«Did you mean» (F6): the article a word the law uses names, without its card; one query and its text's."""
    from apps.search.services.search.bm25 import _brief, _texts

    t = table()
    paths = _paths()
    asked = [(t['rows'][i], paths.get(t['rows'][i]['code'])) for i in rows]
    asked = [(row, path) for row, path in asked if path]
    if not asked:
        return []
    wanted = Q()
    for row, path in asked:
        wanted |= Q(text_path=path, eid=f"art_{row['number']}")
    entries = {(e.text_path, e.eid): e for e in SearchEntry.objects.filter(wanted, kind=SearchEntry.Kind.ARTICLE)
               .only('text_path', 'eid', 'label', 'path', 'body')}
    texts = _texts({path for _, path in asked})
    return [{'path': e.path, 'label': e.label, 'body': _cut(e.body), 'text': _brief(texts[path]) if path in texts else None,
             'known_as': row['known_as']}
            for row, path in asked if (e := entries.get((path, f"art_{row['number']}")))]


def choices(number: str, shown: list[str], word: str = '') -> dict:
    """«490 في نصوص أخرى» (F3): the shelf's codes that hold an article of this number, without the ones on a card, those
    that name their articles as the question did («الفصل 19»: the constitution's, the DOC's) first, then the shelf's
    order; CHOICES of them and how many more. One query and its texts'."""
    from apps.corpus.services.codes import SHELF
    from apps.search.services.search.bm25 import _brief, _texts

    paths = _paths()
    order = [paths[key] for key, _ in SHELF if paths.get(key)]
    rows = {p: (label, at) for p, label, at in SearchEntry.objects.filter(
        kind=SearchEntry.Kind.ARTICLE, text_path__in=order, eid=f'art_{number}').values_list('text_path', 'label', 'path')
        if at not in shown}
    texts = _texts(rows)
    lead = {'fasl': 'الفصل', 'madda': 'المادة'}.get(word)
    found = [{'label': rows[p][0], 'path': rows[p][1], 'text': _brief(texts[p])} for p in order if p in rows and p in texts]
    if lead:
        found.sort(key=lambda c: not c['label'].startswith(lead))
    return {'number': number, 'texts': found[:CHOICES], 'more': max(0, len(found) - CHOICES)}


def suggestions(typed: str) -> list[dict]:
    """The famous articles to offer as citations while typing, in the shape a resolved citation has (the box shows them
    with the citations); two queries, only when one is offered."""
    from apps.corpus.services.codes import CODES
    from apps.search.services.search.bm25 import _brief, _texts

    rows = suggested(typed)
    if not rows:
        return []
    t = table()
    paths = _paths()
    asked = [(t['rows'][i], paths.get(t['rows'][i]['code'])) for i in rows]
    asked = [(row, path) for row, path in asked if path]
    if not asked:
        return []
    wanted = Q()
    for row, path in asked:
        wanted |= Q(text_path=path, eid=f"art_{row['number']}")
    entries = {(p, e): (label, at) for p, e, label, at in SearchEntry.objects.filter(wanted, kind=SearchEntry.Kind.ARTICLE)
               .values_list('text_path', 'eid', 'label', 'path')}
    texts = _texts({path for _, path in asked})
    out = []
    for row, path in asked:
        found = entries.get((path, f"art_{row['number']}"))
        if not found or path not in texts:
            continue
        name = CODES.get(row['code'])
        out.append({'citation': {'kind': 'article', 'raw': typed, 'article': row['number'], 'text_number': None,
                                 'code': row['code'], 'issue': None},
                    'state': 'found', 'name': {'ar': name[0], 'fr': name[1]} if name else None,
                    'text': _brief(texts[path]), 'article': {'label': found[0], 'eid': f"art_{row['number']}", 'path': found[1]},
                    'issue': None, 'changes': [], 'known_as': row['known_as']})
    return out
