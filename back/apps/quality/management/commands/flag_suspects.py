"""Words a reading may have wrong, flagged for a person (FX9 of the mended-Bulletin review).

    flag_suspects                              what each signal finds on the Arabic pages of 1913–1955
    flag_suspects --write                      keeps them for review (/admin/quality/suspect/)
    flag_suspects --signals rare,glued --from 1956 --to 2026
    flag_suspects --tesseract 200 --write      also reads 200 pages with Tesseract (slow: a night per thousands)
"""
from collections import Counter

from django.core.management.base import BaseCommand

from apps.quality.models import Suspect
from apps.quality.services import suspects
from apps.sources.models import Page


class Command(BaseCommand):
    help = 'Flag words a reading may have wrong, for a person to confirm or set aside (a dry run unless --write).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--signals', default='rare,copies,glued')
        parser.add_argument('--from', dest='first', type=int, default=1913)
        parser.add_argument('--to', dest='last', type=int, default=1955)
        parser.add_argument('--tesseract', type=int, default=0, help='pages to read with Tesseract as well')

    def handle(self, *args, write: bool, signals: str, first: int, last: int, tesseract: int, **opts):
        wanted = {s.strip() for s in signals.split(',') if s.strip()}
        pages = Page.objects.filter(document__issue__edition='general_ar', document__issue__copy_of__isnull=True,
                                    document__issue__date__year__gte=first, document__issue__date__year__lte=last)
        found: list[Suspect] = []
        counts = None
        if 'rare' in wanted or tesseract:
            self.stdout.write('counting every word of the Bulletin…')
            counts = suspects.vocabulary()
        if 'rare' in wanted:
            common = suspects.neighbours(counts)
            found += suspects.rare(pages.only('pk', 'text').iterator(chunk_size=1000), counts, common)
        if 'glued' in wanted:
            found += suspects.glued(pages.only('pk', 'text').iterator(chunk_size=1000))
        if 'copies' in wanted:
            found += suspects.copies()
        if tesseract:
            busiest = pages.filter(text__regex=r'[ء-ي]{3}').order_by('?')[:tesseract]
            found += suspects.tesseract(busiest, counts)
        by = Counter(s.signal for s in found)
        self.stdout.write(f'{len(found)} words flagged: ' + ', '.join(f'{k} {n}' for k, n in by.most_common()))
        for signal in by:
            for s in [x for x in found if x.signal == signal][:5]:
                self.stdout.write(f'  {signal}: «{s.word}» → «{s.suggestion}»  …{s.context[:70]}…')
        if write:
            Suspect.objects.bulk_create(found, batch_size=2000, ignore_conflicts=True)
            self.stdout.write(f'{Suspect.objects.filter(status=Suspect.Status.OPEN).count()} open in the review queue')
