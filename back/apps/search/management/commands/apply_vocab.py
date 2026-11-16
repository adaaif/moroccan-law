"""Write the approved everyday words into apps/search/data/everyday.json, from a person's review: a JSON file
{"entries": [{id, typed, kind, means}], "decisions": {id: {verdict, keep, extra}}} exported from the review page.
An approved entry keeps the meanings ticked and the one added; a rejected or undecided entry stays out."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.search.services import vocab


class Command(BaseCommand):
    help = 'Write the approved everyday words from a review export.'

    def add_arguments(self, parser):
        parser.add_argument('review', help='the review export (entries + decisions)')

    def handle(self, *args, review, **opts):
        data = json.loads(Path(review).read_text())
        decisions = data['decisions']
        out = []
        for e in sorted(data['entries'], key=lambda e: e.get('order', 0)):
            d = decisions.get(e['id'])
            if not d or d.get('verdict') != 'approve':
                continue
            keep = d.get('keep') or [False] * len(e['means'])
            means = [m for m, k in zip(e['means'], keep) if k]
            extra = (d.get('extra') or '').strip()
            if extra and extra not in means:
                means.append(extra)
            if means:
                out.append({'typed': [e['typed']], 'kind': e['kind'], 'means': means})
        current = json.loads(vocab.FILE.read_text())
        current['entries'] = out
        vocab.FILE.write_text(json.dumps(current, ensure_ascii=False, indent=1) + '\n')
        vocab.entries.cache_clear()
        self.stdout.write(f'{len(out)} approved entries written to {vocab.FILE.name}')
