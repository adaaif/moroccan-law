"""`archive status` (where the run stands) and `archive report` (the pilot's measures, issue by issue and variant
by variant)."""
import json
import time
from decimal import Decimal
from pathlib import Path

from django.conf import settings

from apps.corpus.services.archive_run.common import MODEL, issue_of, plan
from apps.sources.models import Edition, Issue, OcrRun
from apps.sources.services import archive, witness
from apps.sources.services.compare import word_f1
from apps.sources.services.issue import clean_reading
from apps.sources.services.ocr import OCR_WIDTH, in_flight, spent


class Measures:
    """Where the run stands, and what its pilot measured."""

    def status(self, as_json: bool) -> None:
        p = plan()
        state = archive.root() / 'state'
        phases = {}
        for phase in ('pilot', 'catalog', 'read', 'texts'):
            folder = state / phase
            names = [f.name for f in folder.iterdir()] if folder.exists() else []
            phases[phase] = {what: sum(1 for n in names if n.endswith(f'.{what}')) for what in ('done', 'claim', 'error')}
        tess = Path(settings.CORPUS_DIR) / 'tess'
        runs = OcrRun.objects.filter(engine=MODEL)
        out = {
            'at': time.strftime('%F %T'),
            'issues': len(p['issues']),
            'registered': Issue.objects.filter(edition=Edition.GENERAL_AR).count(),
            'tesseract_issues': len(list(tess.glob('*.json.gz'))) if tess.exists() else 0,
            'phases': phases,
            'pages_read': runs.values('page').distinct().count(),
            'readings': runs.count(),
            'spent': str(spent()), 'in_flight': str(in_flight()),
            'budget': settings.OCR_BUDGET_USD,
            'stopped': archive.stopped(),
            'doubtful_pages': sum(len(json.loads(f.read_text())['pages'])
                                  for f in (archive.root() / 'doubts').glob('*.json')) if (archive.root() / 'doubts').exists() else 0,
        }
        errors = sorted((state / 'read').glob('*.error'))[-3:] + sorted((state / 'catalog').glob('*.error'))[-3:] \
            if state.exists() else []
        out['last_errors'] = [f'{e.parent.name}/{e.stem}: {e.read_text().strip().splitlines()[-1][:160]}' for e in errors]
        if as_json:
            self.stdout.write(json.dumps(out, ensure_ascii=False))
            return
        for k, v in out.items():
            self.stdout.write(f'{k:>18}: {v}')

    def report(self) -> None:
        """The pilot's measures per issue and variant: pages, cost, tokens, witness agreement, word F1 against the
        3192 px columns; texts found from the contents."""
        rows = []
        for key in (self.keys.split(',') if self.keys else plan()['pilot']):
            issue = issue_of(key)
            if issue is None or not archive.done('pilot', key):
                continue
            pages = self.pages(issue)
            by_variant: dict[str, dict] = {}
            ratios: dict[str, list] = {}
            f1: dict[str, list] = {}
            for page in pages:
                runs = {r.variant: r for r in page.ocr_runs.all() if r.engine == MODEL}
                ref = runs.get(f'columns-{2 * OCR_WIDTH}')
                for variant, run in runs.items():
                    v = by_variant.setdefault(variant, {'pages': 0, 'cost': Decimal('0'), 'in': 0, 'out': 0})
                    v['pages'] += 1
                    v['cost'] += run.cost_usd
                    v['in'] += run.input_tokens
                    v['out'] += run.output_tokens
                    if (share := witness.ratio(page, clean_reading(run.text))) is not None:
                        ratios.setdefault(variant, []).append(share)
                    if ref and run is not ref:
                        f1.setdefault(variant, []).append(word_f1(clean_reading(ref.text), clean_reading(run.text)))
            summary = json.loads((archive._state('pilot') / f'{key}.done').read_text())
            rows.append({'key': key, 'year': issue.date.year, **summary, 'variants': {
                v: {**{k: (str(x) if isinstance(x, Decimal) else x) for k, x in d.items()},
                    'ratio_median': round(witness.median_ratio(ratios.get(v, [])), 3),
                    'f1_vs_columns_3192': round(sum(f1[v]) / len(f1[v]), 4) if f1.get(v) else None}
                for v, d in by_variant.items()}})
        (archive.root() / ('pilot_1913.json' if self.keys else 'pilot.json')).write_text(
            json.dumps(rows, ensure_ascii=False, indent=1))
        for r in rows:
            self.stdout.write(f'{r["year"]} {r["key"]}: {r["found"]}/{r["texts"]} texts found, {r["doubts"]} doubts, '
                              + ', '.join(f'{v} ${d["cost"]} F1 {d["f1_vs_columns_3192"]}' for v, d in r['variants'].items()))
