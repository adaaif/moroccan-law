"""The index read: BM25 over the search entries (ParadeDB), every word or any, with what lifts an entry (the shelf's
texts, the words in a row, the topics a question names and the articles they cite) and what weighs one less (the
Bulletin before 1956), the quoted phrases required; and the rows a page of answers reads back (the texts' title rows,
the articles under a heading that holds the words)."""
from functools import lru_cache

import ma_law
from django.conf import settings
from django.db import connection

from apps.corpus.services.addresses import article_path, text_path
from apps.corpus.services.codes import SHELF, texts_of
from apps.search.models import SearchEntry
from apps.search.services.search.quotes import _exactly, _loose, _needs_reading, _phrase_forms
from apps.topics.services import kit

LIMIT = 600            # entries read per search, enough for many pages of texts

# The Bulletin before 1956 (its 1913–1955 issues read in Nov 2026) weighs less unless the question names a year or asks a
# span of years (HM8 of the hard-moment review: a worker's long message found a 1928 wireless-telegraph dahir first,
# «garde des enfants» a 1923 reprint of the French Republic's Journal officiel).
OLD_ERA = 0.5
SHELF_BOOST = 1.3      # the shelf's twenty texts, the ones readers look for most, over a text that uses the word as often
PHRASE_BOOST = 1.5     # an article that holds the words as typed, in a row («التعويض عن الفصل»), over one that has them apart
TOPIC_BOOST = 2.0      # a text that a topic the question names rests on (its journeys' and pages' articles), over others
CITED_BOOST = 3.0      # and the articles that topic cites, over the text's other articles (R6 of the road plan)


def _exact_hits(terms: list[str], phrases: list[str], **filters) -> tuple[list[tuple], bool]:
    """The entries that hold every quoted phrase as typed, best first, and whether LIMIT entries were read. When the
    phrase's stems fill LIMIT entries («"النفقة"»: its stem is «نفقات»'s too, 9,250 articles), they are read again among
    those whose words match _loose, so the exact ones are not left past the LIMIT (45 → 262 articles for «"النفقة"»)."""
    hits = _bm25(terms, all_words=True, exact=phrases, **filters)
    if len(hits) >= LIMIT and any(_needs_reading(p) for p in phrases):
        hits = _bm25(terms, all_words=True, exact=phrases, loose=True, **filters)
    return _exactly(hits, phrases), len(hits) >= LIMIT


def _bm25(terms: list[str], *, all_words: bool, types: list[str], years: tuple, repealed: bool,
          phrase: str = '', lift: tuple = ((), ()), within: str = '', exact: list[str] | None = None,
          loose: bool = False) -> list[tuple]:
    """(entry id, kind, text address, address, text type, score) best first; `phrase`, the words as typed (folded and
    stemmed as the index has them), lifts the articles that hold them in a row; `lift`, the addresses of the texts and
    articles of the topics the question names (_topic_lift); `within`, one text's address, its articles alone;
    `exact`, the quoted phrases (folded), each required in a row, in an article's words or a text's title (by their
    stems here: _exactly reads them again as typed); `loose`, the entries whose words match each phrase's _loose too."""
    if not terms and not exact:
        return []
    query = ' '.join(terms)
    op = '&&&' if all_words else '|||'
    where = [f'(e.terms {op} %(q)s OR e.title_terms {op} %(q)s)'] if terms else []
    params: dict = {'q': query}
    if settings.SEARCH_LEMMAS and terms:
        # B4: the words as their lemmas too, so «عقد» finds «العقود».
        from apps.search.services.lemmas import lemmas
        where = [f'(e.terms {op} %(q)s OR e.lemma_terms {op} %(lq)s OR e.title_terms {op} %(q)s)']
        params['lq'] = ' '.join(lemmas(terms))
    boost = f' * CASE WHEN e.text_path = ANY(%(shelf)s) THEN {SHELF_BOOST} ELSE 1 END'
    params['shelf'] = _shelf_paths()
    if not years[0] and not years[1] and not any(t.isdigit() and len(t) == 4 for t in terms):
        boost += f' * CASE WHEN e.year < 1956 THEN {OLD_ERA} ELSE 1 END'

    if lift[0]:
        boost += (f' * CASE WHEN e.text_path = ANY(%(lt)s) THEN {TOPIC_BOOST} ELSE 1 END'
                  f" * CASE WHEN e.kind = 'article' AND e.path = ANY(%(la)s) THEN {CITED_BOOST} ELSE 1 END")
        params['lt'], params['la'] = list(lift[0]), list(lift[1])
    if phrase.count(' '):
        # The index says which articles hold the words in a row (one set, hashed once). position() over e.terms had read
        # every found article whole out of TOAST (annexes run to 1.2 million characters): «عقد العمل» 312 → 22 ms on the
        # PC, the same articles in the same order on the 2,636 phrases of the gold sets (2 Nov 2026).
        boost += f' * CASE WHEN e.id IN (SELECT id FROM search_entry WHERE terms ### %(p)s) THEN {PHRASE_BOOST} ELSE 1 END'  # noqa: S608 — fixed clauses and constants; the values go as parameters
        params['p'] = phrase
    for i, p in enumerate(exact or []):
        # ParadeDB's phrase: the stems side by side, in order, in any of the first word's fronts. An article is found by
        # its own words here, never by its text's title as the words are: the quote is shown in what it is found in.
        forms = _phrase_forms(p)
        params.update({f'x{i}_{j}': f for j, f in enumerate(forms)})
        article = ' OR '.join(f'e.terms ### %(x{i}_{j})s' for j in range(len(forms)))
        title = ' OR '.join(f'e.title_terms ### %(x{i}_{j})s' for j in range(len(forms)))
        if loose and _needs_reading(p):
            params[f'l{i}'] = _loose(p)
            article = f"({article}) AND (e.label || ' ' || e.body) ~* %(l{i})s"
            title = f'({title}) AND e.title_folded ~* %(l{i})s'
        where.append(f"((e.kind = 'article' AND ({article})) OR (e.kind = 'text' AND ({title})))")
    if within:
        where.append("e.text_path = %(within)s AND e.kind = 'article'")
        params['within'] = within
    if types:
        where.append('e.text_type = ANY(%(types)s)')
        params['types'] = types
    if years[0]:
        where.append('e.year >= %(y0)s')
        params['y0'] = years[0]
    if years[1]:
        where.append('e.year <= %(y1)s')
        params['y1'] = years[1]
    if not repealed:
        where.append('e.in_force')
    # Ties keep the order the index was built in: texts as they came into the corpus, articles in their text's order.
    sql = (f'SELECT e.id, e.kind, e.text_path, e.path, e.text_type, pdb.score(e.id) * e.weight{boost} AS s '  # noqa: S608 — fixed clauses and constants; the values go as parameters
           f'FROM search_entry e WHERE {" AND ".join(where)} ORDER BY s DESC, e.id LIMIT {LIMIT}')
    with connection.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _topic_lift(q: str) -> tuple[frozenset, frozenset]:
    """The addresses of the texts and articles that the topics a question names rest on: a topic is named by one of its
    doors' or tools' words, its everyday words or its keywords («permis de conduire», «الرادار», «السياقة»), and rests on
    what its journeys and pages cite. They rank higher; nothing is found that the words alone would not find."""
    from apps.topics.services import topics

    grams = topics.question_grams(q)
    texts, arts = set(), set()
    for t in topics.load():
        data = kit.load(t['slug'])
        if data is None:
            continue
        hub = data['hub']
        words = [*t.get('everyday', []), *t['keywords'],
                 *(w for d in [*(hub.get('events') or []), *(hub.get('tools') or [])] for w in d.get('words') or [])]
        if any(topics.names(w, grams) for w in words):
            tt, aa = _rests_on(t['slug'], kit.stamp(t['slug']))
            texts |= tt
            arts |= aa
    return frozenset(texts), frozenset(arts)


@lru_cache(maxsize=16)
def _rests_on(slug: str, stamp: tuple) -> tuple[frozenset, frozenset]:
    """(text addresses, article addresses) a topic's items cite: read from its folder, no corpus read (B24)."""
    from apps.corpus.services.addresses import split_path

    data = kit.load(slug)
    paths = kit.cited({k: v for k, v in data.items() if k != 'hub'})
    texts, arts = set(), set()
    for p in paths:
        uri, eid = split_path(p)
        texts.add(text_path(uri))
        if eid:
            arts.add(article_path(uri, eid))
    return frozenset(texts), frozenset(arts)


@lru_cache(maxsize=1)
def _shelf_paths() -> list[str]:
    return [text_path(t.akn_uri) for t in texts_of(key for key, _ in SHELF).values() if t is not None]


@lru_cache(maxsize=4096)
def _heading_terms(heading: str) -> str:
    """A heading's words as the index has them, spaced at both ends; the same headings stand over many articles."""
    return f" {' '.join(ma_law.index_terms(heading))} "


def _under_heading(entry_ids: list[int], phrase: str) -> dict[int, int]:
    """{entry id: its article's order} for the articles under a heading that holds the words as typed."""
    if not phrase or not entry_ids:
        return {}
    out = {}
    for pk, order, path in SearchEntry.objects.filter(pk__in=entry_ids).values_list('pk', 'order', 'heading_path'):
        if any(f' {phrase} ' in _heading_terms(h) for h in path or []):
            out[pk] = order
    return out


def _brief(row: SearchEntry) -> dict:
    """What an answer says of a text, from its title row (as citations.text_brief, without the corpus row's id)."""
    return {'path': row.text_path, 'type': row.text_type, 'title': row.title, 'name': row.name,
            'number_as_printed': row.number_as_printed, 'status': row.status, 'in_corpus': row.in_corpus}


def _texts(paths) -> dict[str, SearchEntry]:
    """{text address: its title row}, one query."""
    return {r.text_path: r for r in SearchEntry.objects.filter(kind=SearchEntry.Kind.TEXT, text_path__in=list(paths))}
