"""Forget the answers kept in Redis (S14 of the performance audit): after writing the corpus outside manage.py, a
script on django.setup() for instance. Every manage.py command that may write does it on its own."""
from django.core.management.base import BaseCommand

from apps.corpus.services import generation


class Command(BaseCommand):
    help = 'Bump every generation: no answer kept so far is served again.'

    def add_arguments(self, parser):
        parser.add_argument('scopes', nargs='*', choices=[*generation.SCOPES, []], help='corpus, talk, explain (all)')

    def handle(self, *args, **opts):
        generation.bump(*opts['scopes'])
        self.stdout.write(f"forgotten: {', '.join(opts['scopes'] or generation.SCOPES)}")
