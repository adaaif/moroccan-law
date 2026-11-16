"""Check each drafted meaning against the corpus: how many articles hold all its words (BM25 on the index).
A meaning the corpus never uses is flagged for the reviewer, not dropped: the corpus is still growing."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

import ma_law


def articles_with(words: list[str]) -> int:
    if not words:
        return 0
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM search_entry e WHERE e.kind = 'article' AND e.terms &&& %s",
                    [' '.join(words)])
        return cur.fetchone()[0]


class Command(BaseCommand):
    help = 'Count the articles that use each drafted meaning.'

    def handle(self, *args, **opts):
        path = Path(settings.CORPUS_DIR) / 'reports' / 'vocab' / 'drafts.json'
        data = json.loads(path.read_text())
        for d in data['drafts']:
            d['found'] = [articles_with(ma_law.search_terms(m)) for m in d['means']]
            d['typed_found'] = articles_with(ma_law.search_terms(d['typed']))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        grounded = sum(1 for d in data['drafts'] if any(d['found']))
        self.stdout.write(f"{grounded} of {len(data['drafts'])} drafts have a meaning the corpus uses")
