"""Finds where the doubtful words stand on their printed pages, so «ساهم» (/open-source) can show each one's line: first
the pages whose word boxes are read already (no Tesseract: fast), then, one page at a time, the others, read first
(the page rendered and Tesseract run once, its boxes kept beside the render). The pages of a second reading
(`reread`, `copies`) before the rare words'. A page whose file is not on this machine is passed over. The night's
`read_regions` does the same for a share of its time; this is the same work on demand.

    nice -n 19 manage.py place_words --minutes 60 [--limit 200] [--signal reread]
"""
import time

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from apps.quality.services import place
from apps.quality.services.words import PLACED, SIGNALS, askable


def tally() -> dict[str, tuple[int, int]]:
    """{signal: (placed, not found)} among the askable words. One query."""
    rows = askable().values('signal').annotate(placed=Count('pk', filter=PLACED),
                                                missed=Count('pk', filter=Q(place={}))).order_by()
    return {r['signal']: (r['placed'], r['missed']) for r in rows}


class Command(BaseCommand):
    help = 'Find where the doubtful words stand on their printed pages (Tesseract, one page at a time).'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=float, default=60)
        parser.add_argument('--limit', type=int, default=None, help='Pages read with Tesseract, at most.')
        parser.add_argument('--signal', choices=[str(s) for s in SIGNALS], default=None)

    def handle(self, *args, minutes, limit, signal, **options):
        started = time.monotonic()
        before = tally()
        done = place.run(started + minutes * 60, limit=limit, signal=signal)
        after = tally()
        spent = (time.monotonic() - started) / 60
        placed = sum(after.get(s, (0, 0))[0] - before.get(s, (0, 0))[0] for s in after)
        missed = sum(after.get(s, (0, 0))[1] - before.get(s, (0, 0))[1] for s in after)
        self.stdout.write(f"{done['read']} pages read, {done['pages']} pages looked at, {done['missing']} passed over "
                          f"(no file here), in {spent:.1f} minutes; {placed} words placed, {missed} not found")
        for s in SIGNALS:
            p = after.get(s, (0, 0))[0] - before.get(s, (0, 0))[0]
            m = after.get(s, (0, 0))[1] - before.get(s, (0, 0))[1]
            if p or m:
                self.stdout.write(f'  {s}: {p} placed, {m} not found ({round(100 * p / (p + m))}% placed)')
        left = askable().filter(place__isnull=True).count()
        self.stdout.write(f'{left} askable words not looked for yet')
