"""Rebuild the search index from the corpus (all texts, or the texts first published in the given issues)."""
from django.core.management.base import BaseCommand

from apps.corpus.models import Text
from apps.search.services.index import rebuild
from apps.sources.models import Issue


class Command(BaseCommand):
    help = 'Rebuild the search index.'

    def add_arguments(self, parser):
        parser.add_argument('issues', nargs='*', help='issue keys (7533, 7465-bis); none = every text')

    def handle(self, *args, issues, **opts):
        texts = None
        if issues:
            keys = [Issue.parse_key(k) for k in issues]
            texts = [t for n, s in keys for t in Text.objects.filter(first_published_in__number=n,
                                                                     first_published_in__suffix=s)]
        rebuild(texts, log=self.stdout.write)
