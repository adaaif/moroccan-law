"""The explanatory memoranda read from the fetched bills (row 11): each bill's first pages read by Haiku in one
batch (half price, within the budget the BO run shares), the memorandum cut from them and kept beside its law.
A memorandum that runs past the pages read gets two more.

    read_memoranda              # every fetched bill not read yet
    read_memoranda --pages 3
"""
from django.core.management.base import BaseCommand

from apps.parliament.models import Explanation
from apps.parliament.services.memoranda import memorandum, names_bill
from apps.sources.models import Document, Source
from apps.sources.services.ocr import allow_spending, ocr_claude_batch

MODEL = 'claude-haiku-5-5'


def page_texts(doc: Document, upto: int) -> list[str]:
    out = []
    for page in doc.pages.order_by('index')[:upto]:
        run = page.ocr_runs.filter(engine=MODEL).order_by('-id').first()
        out.append(run.text if run else '')
    return out


class Command(BaseCommand):
    help = 'Read the explanatory memoranda from the fetched bills.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('--pages', type=int, default=3)

    def handle(self, *args, pages, **opts):
        allow_spending(opts['write'], log=self.stdout.write)
        docs = [d for d in Document.objects.filter(source=Source.PARLIAMENT).exclude(meta__text_uri=None)
                if d.meta.get('text_uri') and not Explanation.objects.filter(text_uri=d.meta['text_uri']).exists()]
        upto = {d.pk: pages for d in docs}
        for attempt in range(2):
            todo = [p for d in docs for p in d.pages.order_by('index')[:upto[d.pk]]
                    if not p.ocr_runs.filter(engine=MODEL).exists()]
            if todo:
                self.stdout.write(f'reading {len(todo)} pages of {len(docs)} bills')
                ocr_claude_batch(todo, MODEL, max_tokens=6000, log=lambda m: self.stdout.write(str(m)))
            unfinished = []
            for d in docs:
                pages_read = page_texts(d, upto[d.pk])
                if not names_bill(pages_read, d.meta.get('bill', '')):
                    self.stderr.write(f"{d.meta.get('bill')}: the file read is another bill's ({d.url})")
                    continue
                text, ended = memorandum(pages_read)
                if text and (ended or attempt == 1 or upto[d.pk] >= (d.page_count or 0)):
                    Explanation.objects.update_or_create(
                        text_uri=d.meta['text_uri'], kind=Explanation.Kind.MEMORANDUM,
                        defaults={'body': text, 'source_url': d.url, 'document_sha': d.sha256, 'pages': f'1-{upto[d.pk]}'})
                elif text and not ended:
                    unfinished.append(d)
                    upto[d.pk] += 2
            docs = unfinished
            if not docs:
                break
        self.stdout.write(f'{Explanation.objects.count()} memoranda kept')
