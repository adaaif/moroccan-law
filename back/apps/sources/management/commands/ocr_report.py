"""Score the OCR trial and write CORPUS_DIR/reports/ocr_trial.json.

Born-digital pages are scored against their own text layer (lam-alef blind for Arabic, since the
layers put those ligatures in the wrong order). Scans have no answer key: each engine is scored
against Opus, and a person reads samples.
"""
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.sources.models import OcrRun, Page
from apps.sources.services.compare import scores

ENGINES = ['tesseract-5', 'claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5']
LAYER_GROUPS = {'digital_ar', 'digital_fr', 'table'}
# Layers found too broken to be an answer key (read by eye): scored against Opus like a scan.
BROKEN_LAYERS = {
    ('samples/bo_ar/BO_6896_ar.pdf', 47): 'date line reversed, letters mangled',
    ('samples/bo_fr/BO_7544_fr.pdf', 40): 'Arabic table extracted as mojibake',
    ('samples/bo_ar/BO_7551_ar.pdf', 11): 'table cells extracted in another order',
}


class Command(BaseCommand):
    help = 'Score the OCR trial.'

    def handle(self, *args, **options):
        root = Path(settings.CORPUS_DIR)
        selection = json.loads((root / 'samples' / 'ocr_selection.json').read_text())
        pages_out, summary = [], defaultdict(lambda: defaultdict(list))
        for item in selection:
            page = Page.objects.select_related('document').get(document__path=item['path'], index=item['index'])
            runs = {}
            for run in OcrRun.objects.filter(page=page).order_by('created_at'):
                runs[run.engine] = run  # the latest run of each engine
            blind = page.document.language == 'ar'
            broken = BROKEN_LAYERS.get((item['path'], item['index']))
            if item['group'] in LAYER_GROUPS and not broken:
                reference, against = page.layer_text, 'text_layer'
            else:
                reference, against = (runs['claude-opus-5-5'].text if 'claude-opus-5-5' in runs else ''), 'opus'
            row = {**item, 'against': against, 'layer_broken': broken or '', 'engines': {}}
            for engine in ENGINES:
                run = runs.get(engine)
                if run is None:
                    continue
                entry = {'chars': len(run.text), 'input_tokens': run.input_tokens, 'output_tokens': run.output_tokens,
                         'cost_usd': float(run.cost_usd), 'seconds': run.seconds, 'stop': run.stop_reason}
                if reference and not (against == 'opus' and engine == 'claude-opus-5-5'):
                    entry.update(scores(reference, run.text, lam_alef_blind=blind))
                row['engines'][engine] = entry
                bucket = summary[item['group'] + ('_layer_broken' if broken else '')][engine]
                bucket.append(entry)
            pages_out.append(row)

        table = {}
        for group, engines in summary.items():
            table[group] = {}
            for engine, entries in engines.items():
                scored = [e for e in entries if 'word_f1' in e]
                table[group][engine] = {
                    'pages': len(entries),
                    'word_f1': round(mean(e['word_f1'] for e in scored), 4) if scored else None,
                    'cer': round(mean(e['cer'] for e in scored), 4) if scored else None,
                    'cost_per_page': round(mean(e['cost_usd'] for e in entries), 5),
                    'output_tokens_per_page': round(mean(e['output_tokens'] for e in entries)),
                }
        spent = round(sum(float(r.cost_usd) for r in OcrRun.objects.all()), 4)
        report = {'spent_usd': spent, 'budget_usd': settings.OCR_BUDGET_USD, 'summary': table, 'pages': pages_out}
        out = root / 'reports' / 'ocr_trial.json'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
        for group, engines in table.items():
            self.stdout.write(group)
            for engine, s in engines.items():
                self.stdout.write(f"  {engine:20} pages={s['pages']:>2} word_f1={s['word_f1']} cer={s['cer']} "
                                  f"${s['cost_per_page']}/page out={s['output_tokens_per_page']}")
        self.stdout.write(f'spent ${spent} of ${settings.OCR_BUDGET_USD}')
