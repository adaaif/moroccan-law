"""A text taken from a file's layer, set against the Bulletin's own pages (RD1 of the readers review; services/
pages_witness.py). Prints how many articles the pages witness, how many agree word for word, and each small difference
to read on the page's image; keeps the whole list in CORPUS_DIR/reports/witness/. Read-only: a difference is a place to
look, and the fix goes through `apply_page_reading` once someone has read the page.

    witness_pages /akn/ma/act/dahir/1-11-91        # the Constitution against BO 5964 bis
    witness_pages --library                        # every book of the library held from a file
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.models import Text
from apps.quality.services.pages_witness import LAYERS, compare


class Command(BaseCommand):
    help = "Set a text held from a file's layer against the Bulletin's own pages, article by article."

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*', help='texts, e.g. /akn/ma/act/dahir/1-11-91')
        parser.add_argument('--library', action='store_true', help="every book of the library held from a file")
        parser.add_argument('--show', type=int, default=12, help='how many differences to print for each text')

    def handle(self, *args, uris, library, show, **opts):
        if library:
            from apps.corpus.services.addresses import split_path
            from apps.corpus.services.library import catalogue
            paths = [b['path'] for branch in catalogue()['branches'] for b in branch['books'] if b.get('path')]
            held = Text.objects.filter(akn_uri__in=[split_path(p)[0] for p in paths],
                                       versions__consolidation__in=LAYERS).distinct()
            uris = sorted(held.values_list('akn_uri', flat=True))
        if not uris:
            raise CommandError('name a text, or --library')
        out = Path(settings.CORPUS_DIR) / 'reports' / 'witness'
        out.mkdir(parents=True, exist_ok=True)
        total = {'witnessed': 0, 'agree': 0, 'slips': 0}
        for uri in uris:
            text = Text.objects.filter(akn_uri=uri).select_related('first_published_in').first()
            if text is None:
                raise CommandError(f'{uri}: not in the corpus')
            r = compare(text)
            (out / f'{uri.strip("/").replace("/", "_")}.pages.json').write_text(json.dumps(r, ensure_ascii=False, indent=1))
            if r.get('error'):
                self.stdout.write(f'{uri}: {r["error"]}')
                continue
            for key in total:
                total[key] += len(r[key]) if key == 'slips' else r[key]
            self.stdout.write(f'{uri}: {r["witnessed"]} of {r["articles"]} articles witnessed by the pages, '
                              f'{r["agree"]} agree word for word, {len(r["slips"])} small differences')
            for s in r['slips'][:show]:
                self.stdout.write(f'    {s["number"] or s["eid"]}: «{s["layer"]}» / the Bulletin «{s["bulletin"]}»   … {s["around"]}')
        if len(uris) > 1:
            self.stdout.write(f'{len(uris)} texts: {total["witnessed"]} articles witnessed, {total["agree"]} agree, '
                              f'{total["slips"]} small differences')
