"""Morocco's constitutions since 1962 (data/constitutions.json, loaded by load_constitutions): what the files do not
say (the referendum, the dahir's date, the BO issue and page), the name people cite («الفصل 19 من الدستور», «… من دستور
1996»), and the address a year and an article lead to (/constitution/1996/19, C1 of the constitution review)."""
import json
from datetime import date
from functools import lru_cache
from itertools import pairwise
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'data' / 'constitutions.json'
HISTORY = Path(__file__).resolve().parent.parent / 'data' / 'constitution_history.json'


@lru_cache(maxsize=1)
def by_uri() -> dict[str, dict]:
    return {c['uri']: c for c in json.loads(DATA.read_text())['constitutions']}


def facts(text) -> dict | None:
    """What the page's opening says of a constitution: its year, referendum, dahir and where it was printed."""
    c = by_uri().get(text.akn_uri)
    if c is None:
        return None
    from apps.corpus.services.codes import CODES

    ar, fr = CODES['constitution']
    return {'name': {'ar': ar, 'fr': fr}, 'year': c['year'], 'referendum': c['referendum'], 'signed': c['signed'],
            'published': c['published'],
            'issue': c['issue'], 'page': c['page'], 'dahir': text.number_as_printed, 'cited_as': c['cited_as'],
            'story': history()['chapters'].get(str(c['year'])), 'checked': history()['checked']}


@lru_cache(maxsize=1)
def history() -> dict:
    """The short history (C4): {checked, chapters: {year: {ar, fr}}}, links written [words](art_N) to that text."""
    return json.loads(HISTORY.read_text())


def chapters() -> dict:
    """/constitution/history: each constitution with its facts, address and chapter, oldest first; two queries."""
    from apps.corpus.models import Text
    from apps.corpus.services.addresses import text_path

    held = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=by_uri())}
    return {'checked': history()['checked'],
            'chapters': [{**facts(held[uri]), 'path': text_path(uri), 'current': held[uri].status == 'in_force'}
                         for uri in by_uri() if uri in held]}


def cited_as(text) -> str | None:
    c = by_uri().get(text.akn_uri)
    return c['cited_as'] if c else None


def path_for(year: int | None, article: str | None) -> str | None:
    """The address of the constitution of `year` (today's when None), or of its article: the constitution in force that
    year, as a citation on that date reads it (codes.CODE_BEFORE)."""
    from apps.corpus.models import Text
    from apps.corpus.services.addresses import article_path, text_path
    from apps.corpus.services.works import code_target, follow

    if year and year < min(c['year'] for c in by_uri().values()):
        return None                                         # no constitution yet
    uri = follow(code_target('constitution', date(year, 12, 31) if year else None)[0])
    if not Text.objects.filter(akn_uri=uri).exists():
        return None
    return article_path(uri, f'art_{article}') if article else text_path(uri)



LINEAGE = Path(__file__).resolve().parent.parent / 'data' / 'constitution_lineage.json'
LIKE, MUTUAL, UNLIKE = 0.80, 0.70, 0.66     # meaning: the same article, each other's nearest, nothing near


def _plain(text: str) -> str:
    """Words as compared across constitutions: folded, hamza's seats and lam-alef set aside (Adala's files print «الى»
    and «إلى», «المومنين» and «المؤمنين», and turn «للأمة» into «لالمة»), so only a changed word counts."""
    from apps.sources.services.compare import fold

    return fold(text.replace('ؤ', 'و').replace('ئ', 'ي').replace('ء', ''), lam_alef_blind=True)


def changed_words(old: str, new: str) -> list[list[str]]:
    """The word diff of two articles, words whose spelling alone changed («ماعدا اذا», «ما عدا إذا») kept as they now read."""
    from apps.consolidation.services.history import word_diff

    out: list[list[str]] = []
    for op, words in word_diff(old, new):
        if op == '+' and out and out[-1][0] == '-' and _plain(out[-1][1]).replace(' ', '') == _plain(words).replace(' ', ''):
            op = '='
            out.pop()
        if out and out[-1][0] == op == '=':
            out[-1][1] += ' ' + words
        else:
            out.append([op, words])
    return out


def _articles(uris, eids=None) -> dict[tuple[str, str], object]:
    """The articles of these texts' standing versions, by (address, eid); two queries."""
    from apps.corpus.models import Article, Version, latest_ids

    newest = latest_ids(Version.objects.filter(text__akn_uri__in=uris).order_by()
                        .values_list('id', 'text_id', 'valid_from', 'consolidation'))
    rows = Article.objects.filter(version_id__in=newest.values()).select_related('version__text').order_by('order')
    if eids is not None:
        rows = rows.filter(eid__in=eids)
    return {(a.version.text.akn_uri, a.eid): a for a in rows}


def trace(model: str = 'bge-m3') -> dict:
    """Each constitution's articles against the one before (C5): the nearest by meaning (the mean of an article's
    passages under `model`, already in SearchPassage) and how alike their words are, word by word (by letters, two
    unrelated articles of a length are half alike): `same` (the same words, spelling aside), `changed` (meaning ≥ 0.80, or each the
    other's nearest at 0.70, or half the words alike), `none` (nothing near: meaning under 0.66 and a tenth of the
    words), else `unsure`, kept for a person and never shown. Three queries; no model is called."""
    import numpy as np
    from rapidfuzz.fuzz import ratio

    from apps.corpus.services.addresses import text_path
    from apps.search.models import SearchPassage

    cons = sorted(by_uri().values(), key=lambda c: c['year'])
    year_of = {text_path(c['uri']): c['year'] for c in cons}
    words: dict[int, dict[str, str]] = {c['year']: {} for c in cons}
    for (uri, eid), a in _articles([c['uri'] for c in cons]).items():
        words[by_uri()[uri]['year']][eid] = _plain(a.body)
    sums: dict[int, dict[str, list]] = {c['year']: {} for c in cons}
    for at, path, v in SearchPassage.objects.filter(text_path__in=year_of, lang='ar', model=model) \
                                            .values_list('text_path', 'path', 'vector'):
        sums[year_of[at]].setdefault(path.rsplit('/', 1)[1], []).append(np.asarray(list(v), dtype=np.float32))
    vectors = {y: {e: (m := np.mean(vs, 0)) / np.linalg.norm(m) for e, vs in s.items()} for y, s in sums.items()}
    pairs = {}
    for old, new in pairwise(cons):
        before, after = vectors[old['year']], vectors[new['year']]
        eids, news = list(before), [e for e in words[new['year']] if e in after]
        near = np.stack([before[e] for e in eids]) @ np.stack([after[e] for e in news]).T
        back = near.argmax(1)                                # each old article's nearest new one
        links = {}
        for j, eid in enumerate(news):
            i = int(near[:, j].argmax())
            best, body, was = eids[i], words[new['year']][eid], words[old['year']].get(eids[i], '')
            meaning, alike = float(near[i, j]), ratio(was.split(), body.split()) / 100
            share = len(set(was.split()) & set(body.split())) / max(1, len(set(body.split())))
            mutual = back[i] == j and meaning >= MUTUAL
            state = ('same' if was == body else 'changed' if meaning >= LIKE or mutual or alike >= 0.5
                     else 'none' if meaning < UNLIKE and share < 0.1 else 'unsure')
            links[eid] = [best if state != 'none' else '', state, round(meaning, 3), round(alike, 3)]
        pairs[str(new['year'])] = {'from': old['year'], 'links': links}
    return {'model': model, 'checked': '', 'pairs': pairs}


@lru_cache(maxsize=1)
def _lineage() -> dict:
    return json.loads(LINEAGE.read_text()) if LINEAGE.exists() else {'pairs': {}, 'checked': ''}


def lineage(path: str) -> dict | None:
    """An article of a constitution in the others (C5): each year with its counterpart and how its words stand against
    the year before's (`same`, `changed` with the words that changed, `none`: nothing near). Followed back from the
    article and forward to today's; a pair the machine is unsure of ends the chain there, unsaid; `before` says what
    stood before the first (nothing near, or a pair a person is to check). Two queries."""
    from apps.corpus.services.addresses import article_path, text_path

    at, _, eid = path.rpartition('/')
    here = next((c for c in by_uri().values() if text_path(c['uri']) == at), None)
    if here is None:
        return None
    pairs = _lineage()['pairs']
    uri_of = {c['year']: c['uri'] for c in by_uri().values()}
    shown = ('same', 'changed')
    chain = {here['year']: eid}                              # year → eid; '' when the next one has none we name
    year, e = here['year'], eid
    while (p := pairs.get(str(year))) and (link := p['links'].get(e)) and link[1] in shown:
        year, e = p['from'], link[0]
        chain[year] = e
    later = {p['from']: int(y) for y, p in pairs.items()}
    year, e = here['year'], eid
    while year in later:
        y = later[year]
        took = [(row[2], n) for n, row in pairs[str(y)]['links'].items() if row[0] == e and row[1] in shown]
        if not took:
            if any(row[0] == e and row[1] == 'unsure' for row in pairs[str(y)]['links'].values()):
                break                                        # a person is to say
            chain[y] = ''
            break
        year, e = y, max(took)[1]
        chain[year] = e
    found = _articles([uri_of[y] for y in chain], [e for e in chain.values() if e])
    rows = []
    for y in sorted(chain):
        a = found.get((uri_of[y], chain[y]))
        link = pairs.get(str(y), {}).get('links', {}).get(chain[y]) if a else None
        was = found.get((uri_of[pairs[str(y)]['from']], link[0])) if link and link[1] == 'changed' and rows else None
        rows.append({'year': y, 'label': a.label if a else '', 'path': article_path(uri_of[y], chain[y]) if a else '',
                     'here': y == here['year'], 'state': (link[1] if link and rows else '') if a else 'none',
                     'diff': changed_words(was.body, a.body) if was else None})
    first = min(chain)
    link = pairs.get(str(first), {}).get('links', {}).get(chain[first])
    before = {'year': pairs[str(first)]['from'], 'state': link[1]} if link and link[1] in ('none', 'unsure') else None
    return {'rows': rows, 'before': before, 'checked': _lineage()['checked']}
