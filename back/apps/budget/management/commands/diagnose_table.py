"""Where a table goes wrong: every block whose lines do not add up to its own «مجموع» row, with its pages.

    diagnose_table 2024 F [--kind law]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.budget.models import FinanceLaw
from apps.budget.services.extract import parse_coded_table
from apps.budget.services.load import _columns, table_chunks


class Command(BaseCommand):
    help = "List a table's blocks that do not add up to their subtotal."

    def add_arguments(self, parser):
        parser.add_argument('year', type=int)
        parser.add_argument('table')
        parser.add_argument('--kind', default='law')

    def handle(self, *args, **opts):
        law = FinanceLaw.objects.get(year=opts['year'], kind=opts['kind'])
        rows = parse_coded_table(table_chunks(law.text).get(opts['table'], []))
        paid = Decimal(0)
        pages = set()
        for row in rows:
            amount = _columns(row['amounts'])[0] if opts['table'] in 'CF' else row['amounts'][0]
            if row['is_total']:
                mark = 'ok  ' if amount == paid else 'DIFF'
                if mark == 'DIFF' or opts['verbosity'] > 1:
                    self.stdout.write(f'{mark} p{sorted(pages)} {row["label"][:80]}: total {amount}, lines {paid}, '
                                      f'missing {amount - paid}')
                paid, pages = Decimal(0), set()
            else:
                paid += amount
                pages.add(row['page'])
        self.stdout.write(f'{len(rows)} rows; after the last total: {paid}')
