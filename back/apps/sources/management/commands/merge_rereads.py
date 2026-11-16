"""FX10 of the mended-Bulletin review: each page read again weighed against its reading (services/rereads.py): a fuller
reading replaces it, glued and rare words give way word by word, the articles printed on the page follow, two
plausible words go to a person (suspects, signal «reread»). A dry run unless --write; safe to run again.

    merge_rereads [--write]
"""
from collections import Counter

from django.core.management.base import BaseCommand

from apps.quality.services import suspects
from apps.sources.models import Page
from apps.sources.services import rereads


class Command(BaseCommand):
    help = 'Weigh each page read again against its reading (a dry run unless --write).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write: bool, **opts):
        from apps.corpus.models import Text
        from apps.corpus.services import generation
        from apps.search.services.index import rebuild

        self.stdout.write('counting every word of the Bulletin…')
        counts = suspects.vocabulary()
        total = Counter()
        issues = set()
        pages = Page.objects.filter(ocr_runs__variant__startswith='reread').distinct().select_related('document__issue')
        for page in pages:
            done = rereads.merge(page, counts, write=write)
            total.update(done)
            total['pages'] += 1
            if done.get('articles') or done.get('fuller'):
                issues.add(page.document.issue.pk)
        self.stdout.write(', '.join(f'{k} {v}' for k, v in sorted(total.items())))
        if write:
            self.stdout.write(f'{suspects.prune()} suspects whose word is gone from its page taken out of the queue')
            rebuild(list(Text.objects.filter(first_published_in__in=issues)), log=self.stdout.write)
            generation.bump('corpus')
