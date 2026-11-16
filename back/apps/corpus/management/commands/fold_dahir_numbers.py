"""Rows filed as laws under a dahir's number (1.72.184) folded into the dahir's address (T2 of the work plan)."""
from django.core.management.base import BaseCommand

from apps.corpus.services import works


class Command(BaseCommand):
    help = "Fold rows filed as laws under a dahir's three-part number into the dahir's address."

    def handle(self, *args, **opts):
        self.stdout.write(str(works.fold_dahir_numbers(log=self.stdout.write)))
