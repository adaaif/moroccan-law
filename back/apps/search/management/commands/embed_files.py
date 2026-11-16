"""Embed the passages `embed_passages --out` wrote, on whatever machine has the cores: each chunk's vectors (float16)
beside it, written whole or not at all, so a run stopped starts again where it was. No database.

    manage.py embed_files /path/to/chunks --threads 3
    (then, where the database is: embed_passages --load /path/to/chunks)"""
import json
import os
import time
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.search.services.meaning import Encoder


class Command(BaseCommand):
    help = 'Write the vectors of the passages embed_passages --out wrote (B7).'

    def add_arguments(self, parser):
        parser.add_argument('folder')
        parser.add_argument('--threads', type=int, default=6)
        parser.add_argument('--model-dir', help='the model\'s folder (default SEARCH_MODEL_DIR)')

    def handle(self, *args, folder, threads, model_dir, **opts):
        import numpy as np

        todo = [f for f in sorted(Path(folder).glob('*.jsonl')) if not f.with_suffix('.npy').exists()]
        self.stdout.write(f'{len(todo)} chunks to embed')
        enc = Encoder(model_dir, threads=threads)
        started, passages = time.time(), 0
        for n, f in enumerate(todo, 1):
            texts = [json.loads(line)['text'] for line in f.read_text().splitlines()]
            vectors = enc.encode(texts).astype(np.float16)
            tmp = f.with_suffix('.npy.tmp')
            with open(tmp, 'wb') as out:
                np.save(out, vectors)
            os.replace(tmp, f.with_suffix('.npy'))
            passages += len(texts)
            self.stdout.write(f'{n} of {len(todo)} chunks, {passages} passages, '
                              f'{passages / (time.time() - started):.2f} passages/s')
