"""The dahir that promulgates each law held without one, from the Bulletin's own sentence
(`apps/corpus/services/promulgated.py`). A dry run unless `--write`.

    manage.py name_dahirs            # what the sentences settle, and how they stand against the dahirs already known
    manage.py name_dahirs --write
"""
from django.core.management.base import BaseCommand
from django.db import connection

from apps.corpus.models import Text
from apps.corpus.services import promulgated


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='fill promulgating_dahir where the sentences settle it')

    def handle(self, *args, write, **opts):
        def bodies():
            with connection.cursor() as cur:
                cur.execute('select body from corpus_article where body like %s', [promulgated.LIKE])
                for (body,) in cur:
                    yield body
        votes = promulgated.read(bodies())
        laws = list(Text.objects.filter(type__in=('law', 'organic_law')).values_list('id', 'number', 'promulgating_dahir'))
        agree, differ, fill = 0, [], []
        for pk, number, known in laws:
            dahir = promulgated.settled(number, votes.get(promulgated.key(number)))
            if dahir is None:
                continue
            if known:
                if promulgated.same(known, dahir):
                    agree += 1
                else:
                    differ.append((number, known, dahir))
            else:
                fill.append((pk, number, dahir))
        self.stdout.write(f'{len(votes)} laws named beside their dahir; the sentences settle {agree + len(differ) + len(fill)}: '
                          f'{agree} as already known, {len(differ)} differently, {len(fill)} held without one')
        for number, known, dahir in differ:
            self.stdout.write(f'  doubt: {number} is kept with {known}, the sentences say {dahir} (not changed)')
        for _, number, dahir in fill:
            self.stdout.write(f'  {number}: {dahir}')
        if not write:
            self.stdout.write('nothing written (run with --write)')
            return
        rows = [Text(pk=pk, promulgating_dahir=dahir) for pk, _, dahir in fill]
        Text.objects.bulk_update(rows, ['promulgating_dahir'], batch_size=500)
        self.stdout.write(f'written: {len(rows)} laws')
