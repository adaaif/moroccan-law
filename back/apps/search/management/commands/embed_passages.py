"""B7 of the search plan: every article of the index read once by the meaning model into SearchPassage rows (its
pieces when long, its official French apart), in the process, on the CPU. Starts where it stopped: an article whose
version and model are already there is skipped. `--scope core` takes the laws, codes, dahirs and the shelf first.
`--max-chars` reads only an article's first characters (cut between words): annexes and tables run to 2 million, and
BM25 still has every word (25 Oct 2026: decrees and orders at 8,000). B9 (services/surrogates.py):
`--context` puts an article's context under each passage's header, `--searches` adds each of its searches as a passage
of its own (lang `q`), for the articles Haiku has read.

    manage.py embed_passages --scope core --threads 6
    manage.py embed_passages --scope all --threads 3 --max-chars 8000

Elsewhere (another machine, a rented GPU): `--out DIR` writes the passages to embed as files, a chunk each (the model only
counts tokens); `embed_files DIR` there writes each chunk's vectors beside it; `--load DIR` here writes the rows."""
import json
import time
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.consolidation.services.instructions import label_key
from apps.corpus.services.addresses import split_path
from apps.search.models import SearchEntry, SearchPassage
from apps.search.services import surrogates
from apps.search.services.meaning import Encoder, header, pieces
from apps.translations.models import FrenchArticle

CORE = ('law', 'organic_law', 'dahir', 'decree_law', 'code', 'constitution', 'other')
CHUNK = 256


class Command(BaseCommand):
    help = 'Embed the index\'s articles with the local meaning model (B7).'

    def add_arguments(self, parser):
        parser.add_argument('--scope', choices=['core', 'all', 'shelf'], default='core')
        parser.add_argument('--threads', type=int, default=6)
        parser.add_argument('--limit', type=int, default=0, help='articles at most (a trial)')
        parser.add_argument('--max-chars', type=int, default=0, help='an article\'s first characters only (0: all)')
        parser.add_argument('--out', help='write the passages to embed into this folder, a chunk a file, and stop')
        parser.add_argument('--load', help='write the rows from this folder\'s chunks and their vectors (embed_files)')
        parser.add_argument('--context', action='store_true', help='B9\'s context under each passage\'s header')
        parser.add_argument('--searches', action='store_true', help='B9\'s searches, each a passage of its own')

    def handle(self, *args, scope, threads, limit, max_chars, out, load, context, searches, **opts):
        model = settings.SEARCH_MODEL
        if load:
            return self._load(Path(load), model)
        rows = SearchEntry.objects.filter(kind=SearchEntry.Kind.ARTICLE)
        if scope != 'all':
            from apps.search.services.search.bm25 import _shelf_paths
            from django.db.models import Q
            rows = rows.filter(Q(text_type__in=CORE) | Q(text_path__in=_shelf_paths()) if scope == 'core'
                               else Q(text_path__in=_shelf_paths()))
        read = surrogates.load() if context or searches else {}
        done = set(SearchPassage.objects.filter(model=model, part=0, lang='ar').values_list('path', 'version_from'))
        names = {r.text_path: r.name.get('ar') or r.title[:120]
                 for r in SearchEntry.objects.filter(kind=SearchEntry.Kind.TEXT).only('text_path', 'name', 'title')}
        todo = [r for r in rows.order_by('id').only('path', 'text_path', 'label', 'heading_path', 'body', 'version_from',
                                                     'in_force', 'text_type', 'year')
                if (r.path, r.version_from) not in done]
        if limit:
            todo = todo[:limit]
        self.stdout.write(f'{len(todo)} articles to embed ({len(done)} already), model {model}, scope {scope}')
        enc = Encoder(threads=threads)
        if out:
            Path(out).mkdir(parents=True, exist_ok=True)
        started, written, tokens = time.time(), 0, 0
        for i in range(0, len(todo), CHUNK):
            chunk = todo[i:i + CHUNK]
            uris = {split_path(r.path)[0] for r in chunk}
            french = {(u, n): b for u, n, b in FrenchArticle.objects.filter(text_uri__in=uris).values_list('text_uri', 'number', 'body')}
            texts, meta = [], []
            for r in chunk:
                head = header(names.get(r.text_path, ''), r.heading_path, r.label)
                b9 = read.get(surrogates.key(r.path, r.version_from.isoformat() if r.version_from else ''))
                ar_head = f'{head}\n{b9["context_ar"]}' if context and b9 else head
                for part, piece in enumerate(pieces(ar_head, _first(r.body, max_chars), enc.count)):
                    texts.append(piece)
                    meta.append((r, part, 'ar'))
                uri, _ = split_path(r.path)
                fr = french.get((uri, label_key(r.label) or r.path.rsplit('_', 1)[-1]))
                if fr:
                    texts.append(f'{head}\n{b9["context_fr"]}\n{fr}' if context and b9 else f'{head}\n{fr}')
                    meta.append((r, 0, 'fr'))
                for part, search in enumerate(b9['searches'] if searches and b9 else []):
                    texts.append(search['q'])          # alone, as a question is read: a search meets its like
                    meta.append((r, part, 'q'))
            if out:
                _write_chunk(Path(out) / f'{i // CHUNK:05d}.jsonl', texts, meta)
                written += len(chunk)
                continue
            vectors = enc.encode(texts)
            tokens += sum(min(enc.count(t), 512) for t in texts)
            _save(model, [r.path for r in chunk], [(_row(r), part, lang) for r, part, lang in meta], vectors)
            written += len(chunk)
            spent = time.time() - started
            self.stdout.write(f'{written} of {len(todo)} articles, {len(texts)} passages this chunk; '
                              f'{written / spent:.1f} articles/s, {tokens / spent:.0f} tokens/s', ending='\n')
        self.stdout.write(f'done: {written} articles in {time.time() - started:.0f}s' + (f', into {out}' if out else ''))

    def _load(self, folder: Path, model: str):
        import numpy as np

        files = sorted(folder.glob('*.jsonl'))
        ready = [f for f in files if f.with_suffix('.npy').exists()]
        loaded = 0
        for f in ready:
            lines = [json.loads(line) for line in f.read_text().splitlines()]
            vectors = np.load(f.with_suffix('.npy'))
            assert len(vectors) == len(lines), f'{f.name}: {len(lines)} passages, {len(vectors)} vectors'  # noqa: S101 — a check on the command's own files
            rows = [({**x, 'version_from': date.fromisoformat(x['version_from']) if x['version_from'] else None},
                     x['part'], x['lang']) for x in lines]
            _save(model, list(dict.fromkeys(x['path'] for x in lines)), rows, vectors)
            loaded += len(lines)
        self.stdout.write(f'{loaded} passages from {len(ready)} of {len(files)} chunks written, model {model}')


def _first(body: str, chars: int) -> str:
    """The body's first `chars` characters, cut at the last space before them; all of it when `chars` is 0."""
    if not chars or len(body) <= chars:
        return body
    cut = body.rfind(' ', 0, chars)
    return body[:cut if cut > chars // 2 else chars]


def _row(r) -> dict:
    return {'path': r.path, 'text_path': r.text_path, 'version_from': r.version_from, 'in_force': r.in_force,
            'text_type': r.text_type, 'year': r.year}


def _save(model: str, paths: list[str], meta: list[tuple[dict, int, str]], vectors) -> None:
    """One chunk's passages, put in place of what its articles had under this model."""
    SearchPassage.objects.filter(path__in=paths, model=model).delete()
    SearchPassage.objects.bulk_create([
        SearchPassage(path=r['path'], text_path=r['text_path'], part=part, lang=lang, model=model,
                      version_from=r['version_from'], in_force=r['in_force'], text_type=r['text_type'], year=r['year'],
                      vector=vectors[k].tolist())
        for k, (r, part, lang) in enumerate(meta)])


def _write_chunk(path: Path, texts: list[str], meta: list) -> None:
    lines = [json.dumps({**_row(r), 'version_from': r.version_from.isoformat() if r.version_from else None,
                         'part': part, 'lang': lang, 'text': text}, ensure_ascii=False)
             for text, (r, part, lang) in zip(texts, meta)]
    path.write_text('\n'.join(lines) + '\n')
