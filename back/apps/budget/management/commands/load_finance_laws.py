"""Every finance law in the corpus into budget data, with its checks:

    load_finance_laws

A finance law is a text titled «قانون المالية رقم N للسنة المالية YYYY» (an amending one «قانون المالية المعدل
رقم N للسنة المالية YYYY»). Prints one line a law: its tables and how many checks pass.
"""
import re

from django.core.management.base import BaseCommand

from apps.budget.models import Kind
from apps.budget.services.load import load_finance_law
from apps.corpus.models import Text

_TITLE = re.compile(r'قانون\s+المالية\s+(المعدل\s+)?(?:لسنة\s+\d{4}\s+)?رقم\s+([\d.]+\d).*?(?:(?:لل|ال)سنة\s+المالية|لسنة)\s+(\d{4})')  # «السنة»: an OCR dropping «لل»


def finance_laws():
    # The title starts with the law's name: a Constitutional Court decision on a finance law names it too.
    for text in Text.objects.filter(versions__isnull=False, title_ar__startswith='قانون المالية').distinct():
        m = _TITLE.match(text.title_ar)
        if m:
            yield text, int(m.group(3)), Kind.AMENDING if m.group(1) else Kind.LAW, m.group(2)


class Command(BaseCommand):
    help = 'Load every finance law in the corpus and check its figures.'

    def handle(self, *args, **opts):
        for text, year, kind, number in sorted(finance_laws(), key=lambda x: (-x[1], x[2])):
            try:
                law = load_finance_law(text, year=year, kind=kind, number=number)
            except Exception as exc:  # noqa: BLE001 — one law's surprise must not stop the others
                self.stdout.write(f'{year} {kind} {number}: FAILED {type(exc).__name__}: {exc}')
                continue
            passed = sum(c['ok'] for c in law.checks)
            failed = [c['name'] for c in law.checks if not c['ok']]
            self.stdout.write(f'{year} {kind} {number}: {passed}/{len(law.checks)} checks, shown '
                              f'{sorted(law.tables_checked())}' + (f'; failing: {failed[:6]}' if failed else ''))
