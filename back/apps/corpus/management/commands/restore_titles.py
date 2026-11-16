"""Put the BO's heading back on the titles the model shortened («بتحديد…» → «مرسوم رقم … صادر في … بتحديد…»)."""
from django.core.management.base import BaseCommand

from apps.corpus.services.titles import restore


class Command(BaseCommand):
    help = "Restore the BO heading on titles stored without it (a dry run unless --write)."

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write=False, **opts):
        self.stdout.write(str(restore(log=self.stdout.write, write=write)))
