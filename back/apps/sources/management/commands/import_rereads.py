"""FX10 of the mended-Bulletin review: the pages read again on another machine (a JSON file of their readings), kept here as
runs of their pages (variant «reread …»), found by issue and place in the file. Running it again adds nothing twice.

    import_rereads FILE.json
"""
import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.sources.models import OcrRun, Page


class Command(BaseCommand):
    help = 'Keep the pages read again elsewhere as runs of their pages here.'

    def add_arguments(self, parser):
        parser.add_argument('file')

    def handle(self, *args, file: str, **opts):
        if not Path(file).is_file():
            raise CommandError(f'{file}: no such file. It is written by a run script of the private repository; the '
                               'pages it holds come with the data release.')
        rows = json.loads(Path(file).read_text())
        pages = {(p.document.issue.edition, p.document.issue.number, p.document.issue.suffix, p.index): p
                 for p in Page.objects.filter(document__issue__copy_of__isnull=True,
                                              document__issue__number__in={r['number'] for r in rows})
                 .select_related('document__issue')}
        have = {(page_id, batch, text[:200]) for page_id, batch, text in OcrRun.objects.filter(
            variant__startswith='reread', page__in=[p.pk for p in pages.values()]).values_list('page_id', 'batch_id', 'text')}
        new, missing, cost = [], 0, Decimal('0')
        for r in rows:
            page = pages.get((r['edition'], r['number'], r['suffix'], r['index']))
            if page is None:
                missing += 1
                continue
            if (page.pk, r['batch_id'], r['text'][:200]) in have:
                continue
            cost += Decimal(r['cost_usd'])
            new.append(OcrRun(page=page, engine=r['engine'], variant=f'reread: {r["variant"]}'[:40], text=r['text'],
                              prompt_version=r['prompt_version'], image_px=r['image_px'], input_tokens=r['input_tokens'],
                              output_tokens=r['output_tokens'], cost_usd=Decimal(r['cost_usd']), batch_id=r['batch_id'],
                              stop_reason=r['stop_reason']))
        OcrRun.objects.bulk_create(new, batch_size=500)
        self.stdout.write(f'{len(new)} readings kept (${cost:.2f}), {missing} pages not found here')
