"""Read the trial pages with several engines; an engine never pays twice for a page it has read."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sources.models import OcrRun, Page
from apps.sources.services import ocr

ENGINES = {'haiku': 'claude-haiku-5-5', 'sonnet': 'claude-sonnet-5-5', 'opus': 'claude-opus-5-5'}


class Command(BaseCommand):
    help = 'OCR the pages listed in samples/ocr_selection.json.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('--engines', default='tesseract', help='tesseract,haiku,sonnet,opus')
        parser.add_argument('--now', action='store_true', help='One standard-price request per page.')
        parser.add_argument('--limit', type=int, default=0, help='Only the first N pages of the selection.')

    def pages(self, limit: int) -> list[Page]:
        selection = json.loads((Path(settings.CORPUS_DIR) / 'samples' / 'ocr_selection.json').read_text())
        if limit:
            selection = selection[:limit]
        pages = []
        for item in selection:
            page = Page.objects.select_related('document').filter(
                document__path=item['path'], index=item['index']).first()
            if page is None:
                raise CommandError(f'No page {item["index"]} in {item["path"]}: run ingest_samples first.')
            pages.append(page)
        return pages

    def handle(self, *args, **options):
        ocr.allow_spending(options['write'], log=self.stdout.write)
        pages = self.pages(options['limit'])
        for name in options['engines'].split(','):
            if name == 'tesseract':
                for page in pages:
                    if not OcrRun.objects.filter(page=page, engine='tesseract-5').exists():
                        run = ocr.ocr_tesseract(page)
                        self.stdout.write(f'tesseract {page}: {len(run.text)} chars, {run.seconds} s')
                continue
            model = ENGINES[name]
            todo = [p for p in pages if not OcrRun.objects.filter(
                page=p, engine=model, prompt_version=ocr.PROMPT_VERSION).exists()]
            if not todo:
                continue
            if options['now']:
                for page in todo:
                    run = ocr.ocr_claude_now(page, model)
                    self.stdout.write(f'{name} {page}: {run.output_tokens} tokens out, ${run.cost_usd}, {run.seconds} s')
            else:
                runs = ocr.ocr_claude_batch(todo, model, log=self.stdout.write)
                cost = sum(r.cost_usd for r in runs)
                self.stdout.write(f'{name}: {len(runs)} pages, ${cost:.4f}')
        self.stdout.write(f'spent so far: ${ocr.spent():.4f} of ${settings.OCR_BUDGET_USD:.2f}')
