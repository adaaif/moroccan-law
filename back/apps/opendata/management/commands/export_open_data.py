"""Write today's edition of the database (services/dump.py), record its manifest's hash and keep the newest three.
Run on the first day of each month by deploy/law-edition.timer."""
from django.core.management.base import BaseCommand

from apps.opendata.services.dump import write_dump


class Command(BaseCommand):
    help = "Write today's edition of the database."

    def handle(self, *args, **opts):
        write_dump(log=self.stdout.write)
