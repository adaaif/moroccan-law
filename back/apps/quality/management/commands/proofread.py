"""Proposes fixes for the words Adala's and the SGG's ligatures turned round (R7 of the for-everyone review); a person
applies each (/corrections, or the admin). `--add PATH WRONG RIGHT` records what a person found reading. `--foreign`
fixes the words read with letters of another alphabet from each page's second reading, `--table-rows` gives back the table
rows the cut put over the next article (T3 of the work plan). `--split` proposes the words a stray space cut in two
(N3 of the read-and-trusted review)."""
from django.core.management.base import BaseCommand

from apps.quality.models import Correction
from apps.quality.services import proofread


class Command(BaseCommand):
    help = 'Propose corrections of ligature-reversed words in Adala and SGG texts, for a person to confirm.'

    def add_arguments(self, parser):
        parser.add_argument('--add', nargs=3, metavar=('PATH', 'WRONG', 'RIGHT'))
        parser.add_argument('--before', default='')
        parser.add_argument('--after', default='')
        parser.add_argument('--foreign', action='store_true')
        parser.add_argument('--table-rows', action='store_true')
        parser.add_argument('--split', action='store_true')

    def handle(self, *args, add=None, before='', after='', foreign=False, table_rows=False, split=False, **options):
        if split:
            self.stdout.write(f'{proofread.split()} words cut in two proposed joined')
            return
        if table_rows:
            from apps.quality.services import tables
            tables.give_back(log=self.stdout.write)
            return
        if foreign:
            from apps.quality.services import foreign as letters
            self.stdout.write(f'{letters.suggest()}; {letters.apply_witnessed()} articles changed')
            return
        if add:
            path, wrong, right = add
            c, made = Correction.objects.get_or_create(path=path, wrong=wrong, before=before, after=after,
                                                      defaults={'right': right, 'source': Correction.Source.REVIEW})
            self.stdout.write(f'{"proposed" if made else "already proposed"}: {c}')
            return
        self.stdout.write(f'{proofread.suggest()} corrections proposed')
