"""B10 of the search plan (25 Oct 2026): one thesaurus for the whole law, a concept a slug. Each concept holds the legal
term as Moroccan law writes it, the official French term, the words people use for it (Darija in Arabic and in Latin
letters, French, English), the concepts it goes with, and the articles that define it («يقصد ب») or are about it (B9's
concepts). It starts from what exists: the everyday-words list's meanings, the topics' doors, the explained concepts
(apps/explain) and B9's concepts used three times or more; Haiku drafts the other languages (`draft_thesaurus`),
`build_thesaurus` grounds each term in the index and writes apps/search/data/thesaurus.json (owner-provisional until
lawyers read it). Search reads its people's words as the everyday list's (vocab.entries) when SEARCH_THESAURUS is set,
until the measures say it helps."""
import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import ma_law

from apps.corpus.services.llm import request

MODEL = 'claude-haiku-5-5'
FILE = Path(__file__).resolve().parent.parent / 'data' / 'thesaurus.json'
DRAFTS = 'reports/thesaurus/drafts.json'
CONCEPTS = Path(__file__).resolve().parents[2] / 'explain' / 'data' / 'concepts.json'
B9_MIN = 3               # a B9 concept read in this many articles or more
PER_REQUEST = 40
RELATED = 4              # concepts it goes with, kept a concept
SYSTEM = (
    'You help a free search engine of Moroccan law find the law\'s own terms when people use their own words. For each '
    'numbered Arabic legal term, as Moroccan legislation writes it, give:\n'
    '- fr: the term the official French edition of Moroccan law uses (empty when none);\n'
    '- darija: up to three ways Moroccans say it in Darija, in Arabic letters, as typed on a phone (empty when people '
    'just use the legal term);\n'
    '- arabizi: up to two of those in Latin letters, digits for Arabic letters (3 for ع, 7 for ح, 9 for ق);\n'
    '- en: the English term;\n'
    '- sure: false when you are not confident.\n'
    'Only words that mean this term in a legal question, never a broader or vaguer word; never explain.')
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['terms'],
    'properties': {'terms': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['n', 'fr', 'darija', 'arabizi', 'en', 'sure'],
        'properties': {'n': {'type': 'integer'}, 'fr': {'type': 'string'},
                       'darija': {'type': 'array', 'items': {'type': 'string'}},
                       'arabizi': {'type': 'array', 'items': {'type': 'string'}},
                       'en': {'type': 'string'}, 'sure': {'type': 'boolean'}}}}},
}


def slug(term: str) -> str:
    return re.sub(r'\s+', '-', ma_law.fold(term).strip())


def candidates() -> dict[str, dict]:
    """{slug: {'ar': term, 'sources': [...]}} from the lists people approved and B9's concepts."""
    from apps.search.services import surrogates, vocab

    out: dict[str, dict] = {}

    def add(term: str, source: str):
        term = ' '.join(term.split())
        if not term or len(term) > 60:
            return
        entry = out.setdefault(slug(term), {'ar': term, 'sources': []})
        if source not in entry['sources']:
            entry['sources'].append(source)

    for e in json.loads(vocab.FILE.read_text())['entries']:
        for m in e['means']:
            add(m, 'everyday')
    for _, means in vocab.doors():
        add(means[0], 'door')
    if CONCEPTS.exists():
        for c in json.loads(CONCEPTS.read_text())['concepts']:
            add(c['term']['ar'], 'explained')
    counts = Counter(c for r in surrogates.load().values() for c in set(r['concepts']))
    for term, n in counts.items():
        if n >= B9_MIN:
            add(term, 'b9')
    return out


def requests(terms: list[str]) -> tuple[list[dict], dict[str, list[str]]]:
    reqs, meta = [], {}
    for i in range(0, len(terms), PER_REQUEST):
        chunk = terms[i:i + PER_REQUEST]
        cid = f'th{i // PER_REQUEST:04d}'
        reqs.append(request(cid, model=MODEL, system=SYSTEM, schema=SCHEMA, max_tokens=600 * len(chunk),
                            content='\n'.join(f'{n} {t}' for n, t in enumerate(chunk, 1))))
        meta[cid] = chunk
    return reqs, meta


def drafts_from(meta: dict[str, list[str]], results: dict) -> dict[str, dict]:
    out = {}
    for cid, chunk in meta.items():
        for item in ((results.get(cid) or {}).get('data') or {}).get('terms', []):
            n = item.get('n')
            if isinstance(n, int) and 1 <= n <= len(chunk):
                out[slug(chunk[n - 1])] = {k: item[k] for k in ('fr', 'darija', 'arabizi', 'en', 'sure')}
    return out


def grounded(term: str, counts: dict[str, int]) -> bool:
    """Every word of the term is a word the index holds (no query: the index's term counts)."""
    terms = ma_law.search_terms(term)
    return bool(terms) and all(counts.get(t, 0) for t in terms)


def build(cands: dict[str, dict], drafts: dict[str, dict], counts: dict[str, int], definitions: list[tuple[str, str]]) -> dict:
    """The thesaurus: grounded concepts with their people's words (a word two concepts claim is left to neither), the
    articles that define or are about each, and the concepts each goes with most (pointwise mutual information over the
    articles B9 read)."""
    from apps.search.services import surrogates

    read = list(surrogates.load().values())
    about: dict[str, list[str]] = {}
    pairs: Counter = Counter()
    single: Counter = Counter()
    for r in read:
        here = sorted({slug(c) for c in r['concepts']} & set(cands))
        for s in here:
            about.setdefault(s, []).append(r['path'])
            single[s] += 1
        for i, a in enumerate(here):
            for b in here[i + 1:]:
                pairs[a, b] += 1
    related: dict[str, list[tuple[float, str]]] = {}
    for (a, b), n in pairs.items():
        if n >= 2:
            pmi = math.log(n * len(read) / (single[a] * single[b]))
            related.setdefault(a, []).append((pmi, b))
            related.setdefault(b, []).append((pmi, a))
    concepts, claims = {}, Counter()
    for s, c in cands.items():
        if not grounded(c['ar'], counts):
            continue
        d = drafts.get(s, {})
        words = {'darija': d.get('darija', [])[:3], 'arabizi': d.get('arabizi', [])[:2],
                 'fr': [d['fr']] if d.get('fr') else [], 'en': [d['en']] if d.get('en') else []}
        folded_ar = ma_law.fold(c['ar'])
        words = {k: [w.strip() for w in v if w.strip() and len(w.strip()) > 2 and ma_law.fold(w) != folded_ar]
                 for k, v in words.items()}
        for v in words.values():
            claims.update({ma_law.fold(w) for w in v})
        folded = f' {folded_ar} '
        concepts[s] = {'ar': c['ar'], **words, 'sure': d.get('sure', True), 'sources': c['sources'],
                       'related': [b for _, b in sorted(related.get(s, []), reverse=True)[:RELATED]],
                       'defines': [p for p, body in definitions if folded in f' {ma_law.fold(body[:300])} '][:5],
                       'about': about.get(s, [])[:20]}
    for c in concepts.values():
        for k in ('darija', 'arabizi', 'fr', 'en'):
            c[k] = [w for w in c[k] if claims[ma_law.fold(w)] == 1]
        c['related'] = [r for r in c['related'] if r in concepts]
    return concepts


@lru_cache(maxsize=1)
def load() -> dict[str, dict]:
    return json.loads(FILE.read_text())['concepts'] if FILE.exists() else {}


LAW_WORD = 20            # an Arabic word the index holds this often is the law's own, searched as typed


def people_words() -> list[tuple[str, list[str]]]:
    """(folded word people use, [the legal term]) for every sure concept: read by vocab.entries under
    SEARCH_THESAURUS, after the approved lists (which win on a word both hold). A drafted word in Arabic letters that
    the law itself uses («الإيجار», «الضمان الاجتماعي») is left out: a query of it would be searched as another term
    (vocab.whole), where the typed words already find the law."""
    from apps.search.services.index import term_counts

    counts = term_counts()
    out = []
    for c in load().values():
        if not c.get('sure', True):
            continue
        for k in ('darija', 'arabizi', 'fr', 'en'):
            for w in c[k]:
                terms = ma_law.search_terms(w)
                arabic = any('\u0600' <= ch <= '\u06ff' for ch in w)
                if arabic and terms and all(counts.get(t, 0) >= LAW_WORD for t in terms):
                    continue
                out.append((ma_law.fold(w), [c['ar']]))
    return out
