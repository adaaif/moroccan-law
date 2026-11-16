"""Load a finance law's figures from the corpus and run its checks:

    load_finance_law 50.25 --year 2026 [--kind law]

The law must be in the corpus first (process_issue on its BO issue). Prints every check; a table is shown on the
site only when all its checks pass.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.budget.models import Kind
from apps.budget.services.load import load_finance_law
from apps.corpus.models import Text
from apps.corpus.services.issue_structure import normalize_number


class Command(BaseCommand):
    help = "Load a finance law's figures and check them."

    def add_arguments(self, parser):
        parser.add_argument('number', help='As printed: «50.25».')
        parser.add_argument('--year', type=int, required=True)
        parser.add_argument('--kind', default=Kind.LAW, choices=Kind.values)

    def handle(self, *args, **opts):
        # A bill is at its own address (/projet-loi/60-26), never the law of that number.
        texts = Text.objects.filter(number=normalize_number(opts['number']), versions__isnull=False)
        text = (texts.filter(type='bill') if opts['kind'] == Kind.BILL else texts.exclude(type='bill')).first()
        if text is None:
            raise CommandError(f'No text {opts["number"]} in the corpus: run process_issue on its BO issue first.')
        law = load_finance_law(text, year=opts['year'], kind=opts['kind'], number=opts['number'])
        counts = {t: law.lines.filter(table=t).count() for t in ('balance', 'posts', 'A', 'B', 'C', 'D', 'E', 'F', 'G')}
        self.stdout.write(f'{law}: ' + ', '.join(f'{t} {n}' for t, n in counts.items()))
        for check in law.checks:
            mark = 'ok  ' if check['ok'] else 'FAIL'
            self.stdout.write(f'  {mark} {check["name"]}: expected {check["expected"]}, found {check["found"]}'
                              + (f' ({check["source"]})' if check['source'] else ''))
        self.stdout.write(f'shown: {sorted(law.tables_checked())}')
