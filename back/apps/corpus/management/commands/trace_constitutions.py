"""Each constitution's articles against the one before (C5 of the constitution review, 25 Oct 2026), from the meaning
vectors search already holds and the articles' words: writes data/constitution_lineage.json. Free: no model is called.
Run after load_constitutions and embed_passages over them; a person checks the `unsure` pairs.

    trace_constitutions [--model bge-m3]"""
import json
from collections import Counter

from django.core.management.base import BaseCommand

from apps.corpus.services import constitutions


class Command(BaseCommand):
    help = "Trace each constitution's articles to the one before."

    def add_arguments(self, parser):
        parser.add_argument('--model', default='bge-m3')

    def handle(self, *args, **opts):
        data = constitutions.trace(opts['model'])
        constitutions.LINEAGE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
        for year, p in data['pairs'].items():
            counts = Counter(row[1] for row in p['links'].values())
            self.stdout.write(f"{p['from']} → {year}: " + ', '.join(f'{k} {n}' for k, n in sorted(counts.items())))
