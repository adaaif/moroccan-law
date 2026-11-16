"""Search by meaning (B7 and B25 of the search plan, 24 Oct 2026): a local model, never an API, reads every article
once into a vector (SearchPassage) and each question at search time; the articles nearest the question are fused with
what BM25 found. The model runs in one process beside Django (`serve_models`): a question is embedded there, kept in the
cache, and search goes on with BM25 alone when the server does not answer in time.

The model is bge-m3 (BAAI, MIT licence) as an int8 ONNX export, run by ONNX Runtime on the CPU; its folder holds
SOURCE.txt with its origin and hash. Until the test set says it helps every kind of question, search uses it only when
SEARCH_MEANING is set."""
import hashlib
import json
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection

MAX_TOKENS = 512          # what the model reads at most
PIECE_TOKENS = 380        # a long article is cut into pieces of about this many tokens
NEAREST = 200             # passages read from the index a question
TIMEOUT = 1.5             # seconds the model server has to embed a question
KEEP = 7 * 24 * 3600      # a question's vector kept a week (the model does not change under it)
RRF_K = 60


class Encoder:
    """The model, loaded once in a process: texts in, normalized vectors out (numpy float32)."""

    def __init__(self, folder: str | None = None, threads: int = 4):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        folder = Path(folder or settings.SEARCH_MODEL_DIR)
        self.tokenizer = Tokenizer.from_file(str(folder / 'tokenizer.json'))
        self.tokenizer.enable_truncation(MAX_TOKENS)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(folder / 'model.onnx'), opts, providers=['CPUExecutionProvider'])
        self.outputs = [o.name for o in self.session.get_outputs()]

    def count(self, text: str) -> int:
        """All of a text's tokens (past MAX_TOKENS, with the few each piece the tokenizer kept apart opens with): it gives
        MAX_TOKENS at most and keeps the rest apart, and a long article measured by those alone was never cut."""
        encoding = self.tokenizer.encode(text)
        return len(encoding.ids) + sum(len(o.ids) for o in encoding.overflowing)

    def encode(self, texts: list[str], batch: int = 1):
        """One text at a time by default: padded in a batch, a text's int8 vector moves (cosine 0.977–0.983 with the
        same text alone, as a question is embedded; 25 Oct 2026), and the padding costs time (69 s for 128 passages in
        sixteens, 49 s one by one)."""
        import numpy as np

        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        out = [None] * len(texts)
        for k in range(0, len(order), batch):
            idx = order[k:k + batch]
            enc = self.tokenizer.encode_batch([texts[i] for i in idx])
            width = max(len(e.ids) for e in enc)
            ids = np.zeros((len(idx), width), dtype=np.int64)
            mask = np.zeros_like(ids)
            for r, e in enumerate(enc):
                ids[r, :len(e.ids)] = e.ids
                mask[r, :len(e.ids)] = 1
            got = dict(zip(self.outputs, self.session.run(None, {'input_ids': ids, 'attention_mask': mask})))
            vectors = got['sentence_embedding'] if 'sentence_embedding' in got else got[self.outputs[0]][:, 0]
            vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
            for r, i in enumerate(idx):
                out[i] = vectors[r].astype(np.float32)
        return np.stack(out) if out else np.zeros((0, 1024), dtype=np.float32)


_SENTENCE = re.compile(r'(?<=[.؛;:!؟?\n])\s+')


def pieces(header: str, body: str, count) -> list[str]:
    """The article as the model reads it: its header and words whole when they fit, else pieces of about PIECE_TOKENS
    tokens cut between sentences, each opened by the header (`count`: a text's tokens)."""
    whole = f'{header}\n{body}'
    if count(whole) <= MAX_TOKENS:
        return [whole]
    out, current = [], ''
    for sentence in _SENTENCE.split(body):
        candidate = f'{current} {sentence}'.strip()
        if current and count(candidate) > PIECE_TOKENS:
            out.append(f'{header}\n{current}')
            current = sentence
        else:
            current = candidate
    if current:
        out.append(f'{header}\n{current}')
    return out


def header(text_name: str, headings: list[str], label: str) -> str:
    return ' › '.join([text_name, *(headings or []), label])


def embed_query(q: str) -> list[float] | None:
    """The question's vector from the model server, kept a week; None when the server does not answer in time."""
    key = f'qvec:{settings.SEARCH_MODEL}:{hashlib.sha1(q.encode(), usedforsecurity=False).hexdigest()}'
    try:
        kept = cache.get(key)
    except Exception:       # noqa: BLE001 — the cache down is no reason to fail a search
        kept = None
    if kept is not None:
        return kept
    body = json.dumps({'texts': [q]}).encode()
    request = urllib.request.Request(f'{settings.SEARCH_MODEL_URL}/embed', data=body,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:
            vector = json.loads(answer.read())['vectors'][0]
    except Exception:  # noqa: BLE001 — the model server down or slow: the words alone answer
        return None
    try:
        cache.set(key, vector, KEEP)
    except Exception:  # noqa: BLE001 — the cache down: the vector is used, not kept
        pass
    return vector


def nearest(vector: list[float], *, types: list[str], years: tuple, repealed: bool, limit: int = NEAREST,
            within: str = '') -> list[tuple]:
    """(article address, text address, similarity) of the passages nearest the vector, an article once (its best
    passage), best first, with search's own filters; `within`, one text's address, its passages alone."""
    where = ['p.model = %(model)s']
    params: dict = {'v': '[' + ','.join(f'{x:.6f}' for x in vector) + ']', 'model': settings.SEARCH_MODEL, 'n': limit}
    if within:
        # One text's few hundred passages, by the address's index and measured exactly, never by the graph's walk.
        where.append('p.path LIKE %(within)s')
        params['within'] = within.replace('%', r'\%').replace('_', r'\_') + '/%'
    if types:
        where.append('p.text_type = ANY(%(types)s)')
        params['types'] = types
    if years[0]:
        where.append('p.year >= %(y0)s')
        params['y0'] = years[0]
    if years[1]:
        where.append('p.year <= %(y1)s')
        params['y1'] = years[1]
    if not repealed:
        where.append('p.in_force')
    with connection.cursor() as cur:
        # The graph's walk goes on past rows a filter leaves out (pgvector 0.8's iterative scans).
        cur.execute('SET hnsw.iterative_scan = relaxed_order')
        source = f'(SELECT * FROM search_passage p WHERE {" AND ".join(where)} OFFSET 0) p' if within else 'search_passage p'  # noqa: S608 — fixed clauses; the values go as parameters
        cur.execute(f'SELECT p.path, p.text_path, 1 - (p.vector <=> %(v)s::halfvec) AS sim FROM {source} '  # noqa: S608 — fixed clauses; the values go as parameters
                    f'{"" if within else "WHERE " + " AND ".join(where)} ORDER BY p.vector <=> %(v)s::halfvec LIMIT %(n)s',
                    params)
        rows = cur.fetchall()
    best: dict[str, tuple] = {}
    for path, text_path, sim in rows:
        if path not in best or sim > best[path][2]:
            best[path] = (path, text_path, sim)
    return sorted(best.values(), key=lambda r: -r[2])


def _scaled(values: list[float]) -> list[float]:
    """Min-max to [0, 1]; all ones when they are all the same."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    return [(v - lo) / (hi - lo) if hi > lo else 1.0 for v in values]


def fuse(words: list[tuple], meaning: list[tuple], entries: dict[str, tuple], weight: float | None = None) -> list[tuple]:
    """BM25's hits and the nearest articles in one list, in the hits' own shape (entry id, kind, text address,
    address, text type, score). `weight` is BM25's share of a weighted sum of both scores scaled to [0, 1] (B8: tuned on
    the dev questions; the pilot chose 0.2); None fuses by reciprocal rank (k=60). `entries`: {article address: (entry
    id, text address, text type)} for the nearest ones."""
    scores: dict[int, float] = {}
    rows: dict[int, tuple] = {}
    if weight is None:
        for rank, hit in enumerate(words):
            scores[hit[0]] = scores.get(hit[0], 0.0) + 1 / (RRF_K + rank + 1)
            rows[hit[0]] = hit
    else:
        for hit, scaled in zip(words, _scaled([h[5] for h in words])):
            scores[hit[0]] = scores.get(hit[0], 0.0) + weight * scaled
            rows[hit[0]] = hit
    scaled_near = _scaled([n[2] for n in meaning])
    for rank, (path, _, _) in enumerate(meaning):
        found = entries.get(path)
        if not found:
            continue
        entry_id, text_path, text_type = found
        part = 1 / (RRF_K + rank + 1) if weight is None else (1 - weight) * scaled_near[rank]
        scores[entry_id] = scores.get(entry_id, 0.0) + part
        rows.setdefault(entry_id, (entry_id, 'article', text_path, path, text_type, 0.0))
    return [(*rows[i][:5], s) for i, s in sorted(scores.items(), key=lambda kv: -kv[1])]


@lru_cache(maxsize=1)
def encoder() -> Encoder:
    return Encoder()
