"""Read again the pages of every finance-law table that fails its checks, with a prompt for tables, and keep the
new readings only where they make the table add up:

    repair_tables [--year 2019]

One batch for all pages. A reading that does not help is deleted, so the page keeps its reading as it was.
"""
from django.core.management.base import BaseCommand

from apps.budget.models import FinanceLaw
from apps.budget.services.load import load_finance_law, table_chunks
from apps.sources.models import Page, TextSource
from apps.sources.services.quality import store
from apps.sources.services.issue import clean_reading
from apps.sources.services.ocr import allow_spending, ocr_claude_batch

MODEL = 'claude-haiku-5-5'
ASK = ('This page holds part of a budget table of the Moroccan finance law. Transcribe the whole page. Write the '
       'table as a Markdown table with every row in the order printed and its cells in the printed order, right '
       'to left: code, label, then the amounts. Copy every amount digit for digit, as printed, with its groups in '
       'order (3 000 000). Keep rows with «-» or «للتذكرة». Do not skip any row.')


class Command(BaseCommand):
    help = 'Re-read the pages of failing finance-law tables and keep the readings that make them add up.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('--year', type=int)

    def handle(self, *args, **opts):
        allow_spending(opts['write'], log=self.stdout.write)
        laws = FinanceLaw.objects.filter(text__isnull=False)
        if opts['year']:
            laws = laws.filter(year=opts['year'])
        todo = {}
        for law in laws:
            failing = {t for c in law.checks if not c['ok'] for t in c['tables']} - {'A'}
            chunks = table_chunks(law.text)
            pages = {page for table in failing for page, _ in chunks.get(table, [])}
            # The balance and the posts are articles: their first page and the next.
            articles = {a.number: a for a in law.text.versions.order_by('-valid_from').first().articles.all()}
            for table in failing & {'balance', 'posts'}:
                article = articles.get(law.sources.get(table, ''))
                if article and article.printed_page:
                    pages |= {article.printed_page, article.printed_page + 1}
            if pages:
                todo[law] = (failing, sorted(pages))
                self.stdout.write(f'{law.year} {law.kind}: tables {sorted(failing)}, {len(pages)} pages')
        if not todo:
            self.stdout.write('nothing to repair')
            return
        page_objs = {(law.document_id, n): Page.objects.get(document_id=law.document_id, printed_number=n)
                     for law, (_, pages) in todo.items() for n in pages}
        runs = ocr_claude_batch(list(page_objs.values()), MODEL, variant='table-1596', ask=ASK, log=self.stdout.write)
        by_page = {r.page_id: r for r in runs}
        for law, (failing, pages) in todo.items():
            old = {n: page_objs[(law.document_id, n)].text for n in pages}
            for n in pages:
                page = page_objs[(law.document_id, n)]
                if page.pk in by_page:
                    page.text, page.text_source = clean_reading(by_page[page.pk].text), TextSource.OCR
                    page.save(update_fields=['text', 'text_source'])
            law = load_finance_law(law.text, year=law.year, kind=law.kind, number=law.number)
            fixed = failing & law.tables_checked()
            self.stdout.write(f'{law.year} {law.kind}: fixed {sorted(fixed)}, still failing {sorted(failing - fixed)}')
            if failing - fixed:
                # Page by page: keep a new reading only where the old one comes back without harm.
                for n in pages:
                    page = page_objs[(law.document_id, n)]
                    if page.pk not in by_page:
                        continue
                    new = page.text
                    page.text = old[n]
                    page.save(update_fields=['text'])
                    law = load_finance_law(law.text, year=law.year, kind=law.kind, number=law.number)
                    if not (failing & law.tables_checked()) >= fixed:   # the old reading broke something: keep the new
                        page.text = new
                        page.save(update_fields=['text'])
                        law = load_finance_law(law.text, year=law.year, kind=law.kind, number=law.number)
                    else:
                        by_page.pop(page.pk).delete()
                self.stdout.write(f'  after page by page: shown {sorted(law.tables_checked())}')
        # Each page's measure is of its reading as left here.
        store(page_objs.values())
