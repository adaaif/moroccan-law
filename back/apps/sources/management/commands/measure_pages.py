"""Measures each page's reading and keeps it with the page (S11 of the performance audit): how it was read and what its
layer confirms, which an issue's quality page and a text's pages read. Run once after sources 0002, and with --all after
a change to how a reading is checked; the OCR step keeps the measure of every reading it chooses."""
from django.core.management.base import BaseCommand

from apps.sources.models import Page
from apps.sources.services.quality import fingerprint, store

CHUNK = 500


class Command(BaseCommand):
    help = "Measure every page's reading (or only those whose kept measure is not of their present reading)."

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='measure again pages already measured')

    def handle(self, *args, **opts):
        measured = kept = 0
        batch: list[Page] = []
        for page in Page.objects.select_related('document').order_by('pk').iterator(chunk_size=CHUNK):
            if not opts['all'] and page.quality and page.quality.get('of') == fingerprint(page):
                kept += 1
                continue
            batch.append(page)
            if len(batch) == CHUNK:
                measured += store(batch)
                batch = []
        measured += store(batch)
        self.stdout.write(f'pages measured: {measured}, already measured: {kept}')
