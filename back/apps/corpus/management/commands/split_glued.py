"""Cut apart two articles read as one, where the body holds the next article's heading line (58.25's arts 466–467)."""
from django.core.management.base import BaseCommand

from apps.corpus.services import glued


class Command(BaseCommand):
    help = "Cut apart articles that hold the next article's heading (a dry run unless --write)."

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write=False, **opts):
        self.stdout.write(f'{glued.repair(log=self.stdout.write, write=write)} articles')
