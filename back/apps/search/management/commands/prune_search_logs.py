"""B3 of the search plan: the words of searches older than 90 days are blanked; what they found and what readers did
with the answers stay as counts (the line on /privacy). Run daily."""
from django.core.management.base import BaseCommand

from apps.search.services.events import KEEP_DAYS, prune


class Command(BaseCommand):
    help = 'Blank the words of searches older than 90 days.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=KEEP_DAYS)

    def handle(self, *args, days, **opts):
        self.stdout.write(f'{prune(days)} searches older than {days} days kept as counts only')
