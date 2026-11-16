"""Grades for search answers (B2 of the search plan, 24 Oct 2026): for each question, every article a variant under test
shows on its first page (today's search: up to twenty) and the articles the set expects, graded by Haiku 5.5 from 0 to 3
against a written rubric. Grades are kept by the question's folded words, the article's address and its version
(CORPUS_DIR/derived/search_grades.jsonl), so a reload keeps them and a new variant only adds the pairs it brings.

Haiku grades and local models rank: the judge never grades its own choices. Until lawyers grade 300 pairs to calibrate
it, it is checked against the gold sets' expected answers (they should come out 2 or 3) and against random articles
(they should come out 0): a provisional check by the editors (24 Oct 2026)."""
import json
import math
import random
from datetime import datetime
from pathlib import Path

import ma_law
from django.conf import settings

MODEL = 'claude-haiku-5-5'
PROMPT = 'g1'
FILE = 'derived/search_grades.jsonl'
BODY_MAX = 1200
PER_REQUEST = 24
SYSTEM = (
    'You judge the answers of a free search engine of Moroccan law. You get a search as a person typed it (in Arabic, '
    'Darija, French or English) and numbered articles of Moroccan legal texts. Grade every article on its own:\n'
    '3 = it answers the search: what the person wants to know or find is in this article.\n'
    '2 = it is needed for the answer with another article, or answers part of the search.\n'
    '1 = it is on the same subject but does not answer the search.\n'
    '0 = it has nothing to do with the search.\n'
    'Judge by meaning, whatever the language of the search; a search naming a text is answered by that text\'s '
    'articles about the subject. Ignore the order of the articles. why: at most 12 words, in English.')
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['grades'],
    'properties': {'grades': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['n', 'grade', 'why'],
        'properties': {'n': {'type': 'integer'}, 'grade': {'type': 'integer', 'enum': [0, 1, 2, 3]},
                       'why': {'type': 'string'}}}}},
}


def _file() -> Path:
    return Path(settings.CORPUS_DIR) / FILE


def key(q: str, path: str, version: str) -> tuple:
    return ma_law.fold(q), path, version


def load() -> dict[tuple, dict]:
    """{(folded question, address, version): grade row}; a later row for the same pair wins."""
    path = _file()
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                out[key(row['q'], row['path'], row['version'])] = row
    return out


def save(rows: list[dict]) -> None:
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def anchors(paths) -> dict:
    """{address: Anchor} for the current version of every article named, a few queries a chunk of 400."""
    from apps.discussion.services.anchors import find_many

    paths = list(dict.fromkeys(paths))
    out = {}
    for i in range(0, len(paths), 400):
        out.update(find_many(paths[i:i + 400]))
    return out


def version_of(anchor) -> str:
    return f'{anchor.version.valid_from.isoformat()}:{anchor.version.consolidation}'


def pools(rows: list[dict], extra: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    """{question: addresses to grade}: what today's search showed (`rows[i]['shown']`), the expected articles, and what
    other variants showed (`extra`, by question)."""
    out: dict[str, list[str]] = {}
    for r in rows:
        expect = r['expect'] if isinstance(r['expect'], list) else [r['expect']]
        wanted = [e for e in expect if not e.startswith('missing:') and '/art' in e]
        out.setdefault(r['q'], [])
        out[r['q']] = list(dict.fromkeys(out[r['q']] + r.get('shown', []) + wanted + (extra or {}).get(r['q'], [])))
    return out


def requests(pool: dict[str, list[str]], known: dict[tuple, dict]):
    """The batch requests for the pairs not graded yet, and {custom_id: (question, [(address, version)])}."""
    from apps.corpus.services.codes import display_name
    from apps.corpus.services.llm import request

    found = anchors(p for paths in pool.values() for p in paths)
    reqs, meta = [], {}
    for qi, (q, paths) in enumerate(pool.items()):
        todo = [(p, found[p]) for p in paths if p in found and key(q, p, version_of(found[p])) not in known]
        for part in range(0, len(todo), PER_REQUEST):
            chunk = todo[part:part + PER_REQUEST]
            cid = f'g{qi:05d}-{part // PER_REQUEST}'
            blocks = [f'[{n}] {display_name(a.text)["ar"]} › {" › ".join(a.article.heading_path or [])} › {a.article.label}\n'
                      f'{a.article.body[:BODY_MAX]}' for n, (_, a) in enumerate(chunk, 1)]
            reqs.append(request(cid, model=MODEL, system=SYSTEM, schema=SCHEMA, max_tokens=3000,
                                content=f'Search: {q}\n\n' + '\n\n'.join(blocks)))
            meta[cid] = (q, [(p, version_of(a)) for p, a in chunk])
    return reqs, meta


def collect(results: dict, meta: dict) -> list[dict]:
    """Grade rows from a batch's answers; a pair the judge skipped stays ungraded."""
    now = datetime.now().isoformat(timespec='seconds')
    rows = []
    for cid, (q, pairs) in meta.items():
        got = (results.get(cid) or {}).get('data') or {}
        for g in got.get('grades', []):
            n = g.get('n')
            if isinstance(n, int) and 1 <= n <= len(pairs) and g.get('grade') in (0, 1, 2, 3):
                path, version = pairs[n - 1]
                rows.append({'q': q, 'path': path, 'version': version, 'grade': g['grade'], 'why': g.get('why', ''),
                             'judge': MODEL, 'prompt': PROMPT, 'at': now})
    return rows


def by_question(known: dict[tuple, dict]) -> dict[str, dict[str, int]]:
    """{folded question: {address: grade}}, whatever the version (the newest grade wins)."""
    out: dict[str, dict[str, int]] = {}
    for (kq, path, _), row in known.items():
        out.setdefault(kq, {})[path] = row['grade']
    return out


def _dcg(gains: list[int]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def measure(rows: list[dict], known: dict[tuple, dict]) -> dict:
    """nDCG@10 over the articles shown in order, MRR of the first article graded 2 or more, and recall@20 of the
    articles graded 2 or more that the grades know of; questions without any grade are left out."""
    by_q = by_question(known)
    totals = {'questions': 0, 'ndcg10': 0.0, 'mrr': 0.0, 'recall20': 0.0}
    for r in rows:
        grades = by_q.get(ma_law.fold(r['q']))
        if not grades:
            continue
        shown = r.get('shown', [])
        gains = [grades.get(p, 0) for p in shown[:10]]
        ideal = _dcg(sorted(grades.values(), reverse=True)[:10])
        relevant = {p for p, g in grades.items() if g >= 2}
        totals['questions'] += 1
        totals['ndcg10'] += _dcg(gains) / ideal if ideal else 0.0
        first = next((i for i, p in enumerate(shown) if grades.get(p, 0) >= 2), None)
        totals['mrr'] += 1 / (first + 1) if first is not None else 0.0
        totals['recall20'] += len(relevant & set(shown[:20])) / len(relevant) if relevant else 0.0
    n = totals['questions'] or 1
    return {'questions': totals['questions'], 'ndcg10': round(totals['ndcg10'] / n, 3),
            'mrr': round(totals['mrr'] / n, 3), 'recall20': round(totals['recall20'] / n, 3)}


NEGATIVES = 'derived/search_grade_negatives.json'


def checks(rows: list[dict], known: dict[tuple, dict]) -> dict:
    """The judge against what is known without a lawyer: the gold sets' expected articles should come out 2 or 3, and
    the unrelated articles slipped into some pools (`negatives`) 0."""
    by_q = by_question(known)
    expected = graded = 0
    for r in rows:
        grades = by_q.get(ma_law.fold(r['q']), {})
        for e in (r['expect'] if isinstance(r['expect'], list) else [r['expect']]):
            if e in grades:
                graded += 1
                expected += grades[e] >= 2
    planted = Path(settings.CORPUS_DIR) / NEGATIVES
    plants = json.loads(planted.read_text()) if planted.exists() else {}
    zero = low = seen = 0
    for q, paths in plants.items():
        grades = by_q.get(ma_law.fold(q), {})
        for p in paths:
            if p in grades:
                seen += 1
                zero += grades[p] == 0
                low += grades[p] <= 1
    return {'expected_graded': graded, 'expected_2_or_3': expected, 'expected_share': round(expected / graded, 3) if graded else None,
            'unrelated_graded': seen, 'unrelated_0': zero, 'unrelated_0_or_1': low}


def negatives(rows: list[dict], n: int, seed: int = 7) -> dict[str, list[str]]:
    """For `n` questions, two articles another set's questions led to (texts this question has nothing to do with),
    kept in CORPUS_DIR/derived/search_grade_negatives.json: the judge should grade them 0."""
    rng = random.Random(seed)
    picked = rng.sample(rows, min(n, len(rows)))
    out = {}
    for r in picked:
        others = [x for x in rows if x.get('set') != r.get('set') and x.get('shown')]
        if len(others) >= 2:
            out[r['q']] = [rng.choice(o['shown']) for o in rng.sample(others, 2)]
    path = Path(settings.CORPUS_DIR) / NEGATIVES
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = json.loads(path.read_text()) if path.exists() else {}
    kept.update(out)
    path.write_text(json.dumps(kept, ensure_ascii=False, indent=1))
    return out
