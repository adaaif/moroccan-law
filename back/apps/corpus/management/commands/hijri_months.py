"""The first day of each Hijri month, from the double dates the Bulletin prints on its texts and its issues
(`apps/corpus/services/hijri.py`). Reads only; `--write` renews `apps/corpus/data/hijri_months.json`, a file to commit.

    manage.py hijri_months            # what the corpus gives, beside the file
    manage.py hijri_months --write
    manage.py hijri_months --also pairs.tsv --write     # with the dates of issues the site holds and this corpus not yet
"""
import json

from django.core.management.base import BaseCommand

from apps.corpus.models import Text
from apps.corpus.services import hijri
from apps.sources.models import Edition, Issue


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='renew the file')
        parser.add_argument('--also', help='a TSV of more pairs (… <tab> 2026-10-26 <tab> 14 من جمادى الأولى 1448): '
                                            'the dates of issues another database holds and this one not yet')

    def handle(self, *args, write, also=None, **opts):
        def pairs():
            yield from Text.objects.exclude(signed_on=None).exclude(signed_on_hijri='').values_list('signed_on', 'signed_on_hijri').iterator()
            yield from Issue.objects.filter(edition=Edition.GENERAL_AR).exclude(hijri_date='').values_list('date', 'hijri_date').iterator()
            if also:
                from datetime import date as day
                for line in open(also, encoding='utf8'):
                    *_, on, printed = line.rstrip('\n').split('\t')
                    yield day.fromisoformat(on), printed
        table, counted = hijri.tabulate(pairs())
        try:
            kept = json.loads(hijri.FILE.read_text())
        except FileNotFoundError:
            kept = {}
        # A month the file holds far from the arithmetic calendar was a misprint's vote: it leaves the file.
        from datetime import date
        far = [k for k, v in kept.items()
               if abs((date.fromisoformat(v) - hijri.tabular(*map(int, k.split('-')))).days) > hijri.FAR]
        for k in far:
            self.stdout.write(f'  {k}: {kept.pop(k)} is not that month (the arithmetic calendar says about '
                              f'{hijri.tabular(*map(int, k.split("-")))}): dropped')
        new = [k for k in table if k not in kept]
        moved = [k for k in table if k in kept and kept[k] != table[k]]
        years = sorted({int(k.split('-')[0]) for k in table})
        self.stdout.write(f'{counted["pairs"]} dated pairs read; {counted["months"]} months fixed'
                          f'{f" ({years[0]}–{years[-1]})" if years else ""}, {counted["unsettled"]} unsettled, '
                          f'{counted["set_aside"]} pairs set aside as misprints; '
                          f'{len(new)} new, {len(moved)} moved beside the file ({len(kept)} months)')
        for k in moved[:20]:
            self.stdout.write(f'  {k}: {kept[k]} → {table[k]}')
        if write:
            # A month the file already fixes stays when today's corpus no longer settles it.
            merged = {**kept, **table}
            ordered = dict(sorted(merged.items(), key=lambda kv: tuple(map(int, kv[0].split('-')))))
            hijri.FILE.parent.mkdir(parents=True, exist_ok=True)
            hijri.FILE.write_text(json.dumps(ordered, separators=(',', ':')) + '\n')
            self.stdout.write(f'written: {len(ordered)} months')
