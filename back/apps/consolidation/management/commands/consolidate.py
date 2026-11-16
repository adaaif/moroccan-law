"""The links pipeline over the whole corpus (rows L1–L10 of the links review; row 19 before it): every text at the
address its kind and number give, then every article read for what it changes and cites, each change weighed against
its witnesses, applied into dated versions, and every text's status. Run again after a load: it replaces its own
changes, mentions, versions and open doubts, and keeps a person's resolved ones. `process_issue` runs the same for
one issue's texts (its `links` step). It rewrites every text's links, so it runs only on the database named:

    consolidate --yes-on <database name>
"""
import json
from datetime import UTC, datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.consolidation.services import engine
from apps.sources.services import coverage
from config import confirm


class Command(BaseCommand):
    help = 'Address every text, then read, weigh and apply what the corpus changes and cites.'

    def add_arguments(self, parser):
        confirm.add_argument(parser)

    def handle(self, *args, yes_on='', **opts):
        confirm.confirm(yes_on, what='consolidate (every text\'s links)')
        stats = {**{f'address_{k}': v for k, v in engine.readdress().items()}, **engine.run(log=self.stdout.write)}
        led = dict(coverage.refresh().items())
        stats['coverage_issues'] = len(led)
        out = settings.CORPUS_DIR / 'reports' / 'consolidation.json'
        out.write_text(json.dumps({'at': datetime.now(UTC).isoformat(), **stats}, indent=1, default=str))
        for k, v in sorted(stats.items()):
            self.stdout.write(f'{k:>22}  {v}')
