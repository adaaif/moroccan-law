"""One issue for each printed cover (FX3 of the mended-Bulletin review): `manage.py fold_copies` lists the covers stored
under several numbers and what folding would do; `--write` folds them (services/copies.py), then puts the search index
right for the texts kept and takes out the rows of the texts folded away."""
from django.core.management.base import BaseCommand

from apps.sources.services import copies


class Command(BaseCommand):
    help = 'Fold the copies of an issue stored under its other numbers into the issue (a dry run unless --write).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--only', type=int, help='one cover, by its number')

    def handle(self, *args, write: bool, only: int | None = None, **opts):
        from apps.corpus.models import Text
        from apps.corpus.services import generation
        from apps.corpus.services.addresses import text_path
        from apps.search.models import SearchEntry, SearchPassage
        from apps.search.services.index import rebuild

        groups = [g for g in copies.groups(log=self.stdout.write) if only is None or g[0].number == only]
        self.stdout.write(f'{len(groups)} covers, {sum(len(c) for _, c in groups)} copies')
        kept, gone = [], []
        for cover, rest in groups:
            texts = {m.key: m.texts_first_published.count() for m in [cover, *rest]}
            line = f'  {cover.edition} {cover.key} ×{1 + len(rest)} ({cover.date}): texts {texts}'
            if not write:
                plan = copies.clusters(cover, rest)
                self.stdout.write(f'{line} → {len(plan)} printed texts')
                continue
            done = copies.fold(cover, rest, log=self.stdout.write)
            kept += done.pop('kept')
            gone += done.pop('gone')
            self.stdout.write(f'{line} → ' + ', '.join(f'{k} {v}' for k, v in done.items()))
        if write and groups:
            paths = [text_path(u) for u in gone]
            for i in range(0, len(paths), 2000):
                SearchEntry.objects.filter(text_path__in=paths[i:i + 2000]).delete()
                SearchPassage.objects.filter(text_path__in=paths[i:i + 2000]).delete()
            rebuild(list(Text.objects.filter(pk__in=kept)), log=self.stdout.write)
            generation.bump('corpus')
            self.stdout.write(f'{len(kept)} texts kept, {len(gone)} addresses now lead to them')
