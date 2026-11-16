"""How often an old reading is wrong (FX8 of the mended-Bulletin review): `manage.py reading_rates [--json FILE]`.
Only reads. Three measures by period: readings beside the vote of many (BO 610's 28), half the disagreement of two
readings of one page, and passages read against their printed pages (reading_gold.yaml)."""
import json as jsonlib
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.quality.services import rates


class Command(BaseCommand):
    help = 'Measure how often a reading of the Bulletin is wrong, period by period (only reads).'

    def add_arguments(self, parser):
        parser.add_argument('--json', help='write the measures to this file')

    def handle(self, *args, json: str | None = None, **opts):
        out = {}
        for name, measure in (('vote of many', rates.votes), ('two readings', rates.pairs), ('pages read', rates.gold)):
            found = measure()
            out[name] = {k: {'errors': e, 'words': w, 'rate': round(100 * e / w, 1) if w else None,
                             'median_page': round(100 * m, 1) if m is not None else None}
                         for k, (e, w, m) in sorted(found.items())}
            for k, v in out[name].items():
                self.stdout.write(f'{name:14s} {k:10s} {v["words"]:>9,} words  {v["errors"]:>7,} wrong  {v["rate"]} %'
                                  + (f'  (median page {v["median_page"]} %)' if v['median_page'] is not None else ''))
        if json:
            Path(json).write_text(jsonlib.dumps(out, ensure_ascii=False, indent=1))
