"""B10 of the search plan: Haiku drafts the French term, the Darija words (both scripts) and the English term of each
candidate concept (services/thesaurus.py) into CORPUS_DIR/reports/thesaurus/drafts.json; `build_thesaurus` grounds
and writes them. Without --write, the candidates and the worst case only.

    manage.py draft_thesaurus --write"""
import json
from collections import Counter
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.corpus.services.llm import _worst_case, run_batch
from apps.search.services import thesaurus
from apps.sources.services.ocr import allow_spending


class Command(BaseCommand):
    help = 'Draft the thesaurus\'s people\'s words with Haiku (B10).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write, **opts):
        cands = thesaurus.candidates()
        path = Path(settings.CORPUS_DIR) / thesaurus.DRAFTS
        kept = json.loads(path.read_text())['drafts'] if path.exists() else {}
        todo = [c['ar'] for s, c in cands.items() if s not in kept]
        reqs, meta = thesaurus.requests(todo)
        sources = Counter(s for c in cands.values() for s in c['sources'])
        self.stdout.write(f'{len(cands)} candidate concepts ({", ".join(f"{k} {v}" for k, v in sources.items())}); '
                          f'{len(todo)} to draft in {len(reqs)} requests; worst case ${_worst_case(reqs) if reqs else 0}')
        if not write or not reqs:
            return
        allow_spending(log=self.stdout.write)
        results = run_batch('search-thesaurus', reqs, log=self.stdout.write)
        kept.update(thesaurus.drafts_from(meta, results))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'date': date.today().isoformat(), 'model': thesaurus.MODEL, 'drafts': kept},
                                   ensure_ascii=False, indent=1))
        self.stdout.write(f'{len(kept)} drafts kept in {path}')
