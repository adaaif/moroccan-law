"""Turn the OCR text of a few trial pages into texts and articles, and keep what it cost. Each request is held against
the shared budget and written to its ledger by `structure.extract`."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.corpus.services.structure import extract
from apps.sources.models import OcrRun
from apps.sources.services.ocr import allow_spending

# (selection label, group): the pages read for structure.
PAGES = [('1938', 'scan_ar'), ('1970', 'scan_ar'), ('SGG consolidated', 'digital_ar'), ('2026', 'digital_fr')]


class Command(BaseCommand):
    help = 'Structure test on OCR output.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('--engine', default='claude-sonnet-5-5', help='Whose OCR text to read.')

    def handle(self, *args, **options):
        allow_spending(options['write'], log=self.stdout.write)
        root = Path(settings.CORPUS_DIR)
        selection = json.loads((root / 'samples' / 'ocr_selection.json').read_text())
        results = []
        for label, group in PAGES:
            item = next(i for i in selection if i['label'] == label and i['group'] == group)
            run = OcrRun.objects.filter(page__document__path=item['path'], page__index=item['index'],
                                        engine=options['engine']).latest('created_at')
            data, usage = extract(run.text)
            results.append({**item, 'ocr_engine': options['engine'], 'usage': usage, 'structure': data})
            self.stdout.write(f"{label}: {len(data['texts'])} texts, ${usage['cost_usd']}")
        (root / 'reports' / 'structure_trial.json').write_text(json.dumps(results, ensure_ascii=False, indent=1))
