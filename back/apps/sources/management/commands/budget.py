"""Where the API budget stands: spent (OCR runs and the structuring ledger), held by batches out now (every
process's), the cap (OCR_BUDGET_USD) and what is left. `--left` prints only what is left, for the queue runner.

    budget
    budget --left
"""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.sources.services.ocr import in_flight, spent


class Command(BaseCommand):
    help = 'Spent, in flight, cap and left.'

    def add_arguments(self, parser):
        parser.add_argument('--left', action='store_true')

    def handle(self, *args, left, **opts):
        total, out, cap = spent(), in_flight(), Decimal(str(settings.OCR_BUDGET_USD))
        rest = cap - total - out
        self.stdout.write(f'{rest:.4f}' if left else
                          f'spent ${total:.4f}, in flight ${out:.4f}, cap ${cap:.2f}, left ${rest:.4f}')
