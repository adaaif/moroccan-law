"""Dates and twins that cannot be right (FX7 of the mended-Bulletin review).

    mend_records            what would change: texts dated after their issue, texts cut twice in one issue
    mend_records --write    gives each its signed day from its closing, folds each twin into the fuller cut
"""
from django.core.management.base import BaseCommand

from apps.corpus.services import records


class Command(BaseCommand):
    help = 'Put right dates after the issue and texts cut twice in one issue (a dry run unless --write).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write: bool, **opts):
        from apps.corpus.models import Text
        from apps.corpus.services import generation
        from apps.corpus.services.addresses import text_path
        from apps.search.models import SearchEntry, SearchPassage
        from apps.search.services.index import rebuild

        fixed, left = records.dates(write=write)
        self.stdout.write(f'{len(fixed)} texts dated after their issue take the day their closing signs; '
                          f'{len(left)} name none')
        for uri, was, day in fixed[:8]:
            self.stdout.write(f'  {uri}: {was} → {day}')
        for uri in left[:8]:
            self.stdout.write(f'  left: {uri}')
        twins = records.twins(write=write)
        self.stdout.write(f'{len(twins)} texts cut twice in one issue' + (' — folded' if write else ''))
        for gone, kept in twins[:8]:
            self.stdout.write(f'  {gone} → {kept}')
        if write and twins:
            paths = [text_path(g) for g, _ in twins]
            SearchEntry.objects.filter(text_path__in=paths).delete()
            SearchPassage.objects.filter(text_path__in=paths).delete()
            rebuild(list(Text.objects.filter(akn_uri__in=[k for _, k in twins])), log=self.stdout.write)
        if write:
            generation.bump('corpus')
