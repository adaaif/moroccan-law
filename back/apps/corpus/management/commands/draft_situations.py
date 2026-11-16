"""Claude Haiku drafts the twelve situations' words from the site's own articles (row 4 of the reader-experience review), for an
editor to approve (call C2). Writes apps/corpus/data/situations_drafts.json; costs a few cents on the shared budget."""
from django.core.management.base import BaseCommand

from apps.corpus.services.situations import draft
from apps.sources.services.ocr import allow_spending


class Command(BaseCommand):
    help = "Draft the situations' words with Claude Haiku, for an editor's review."

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('slugs', nargs='*', help='only these situations')

    def handle(self, *args, slugs, **options):
        allow_spending(options['write'], log=self.stdout.write)
        done = draft(slugs or None, log=self.stdout.write)
        self.stdout.write(f'{len(done)} situations drafted; {sum(len(s["articles"]) for s in done)} articles chosen')
