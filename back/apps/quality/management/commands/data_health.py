"""Count every fault the mended-Bulletin review found (FX1): `manage.py data_health`. Only reads.

    data_health                          every check, a line each with examples
    data_health --only pages,texts       some of them (copies, pages, readings, articles, texts)
    data_health --json out.json          the counts and examples kept, to set beside a later run
    data_health --baseline base.json     fails (exit 1) when a count is above the baseline's: run it after a load
"""

import json as jsonlib
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.quality.services import health


class Command(BaseCommand):
    help = "Count the faults in the Bulletin's data that FX1 of the mended-Bulletin review listed (only reads)."

    def add_arguments(self, parser):
        parser.add_argument('--only', default='', help='copies, pages, readings, articles, texts (comma-separated)')
        parser.add_argument('--json', help='write the counts and examples to this file')
        parser.add_argument('--baseline', help='fail when a count is above this file\'s')

    def handle(self, *args, only, json: str | None = None, baseline: str | None = None, **opts):
        checks = health.run({o.strip() for o in only.split(',') if o.strip()} or None)
        for c in checks:
            self.stdout.write(f'{c.name:28s} {c.count:>8,}  {c.means}')
            for s in c.sample[:4]:
                self.stdout.write(f'{"":38s}{s}')
        if json:
            Path(json).write_text(jsonlib.dumps(
                {c.name: {'count': c.count, 'means': c.means, 'sample': c.sample} for c in checks},
                ensure_ascii=False, indent=1))
        if baseline:
            base = jsonlib.loads(Path(baseline).read_text())
            worse = [f'{c.name} {base[c.name]["count"]} → {c.count}' for c in checks
                     if c.name in base and c.count > base[c.name]['count']]
            if worse:
                self.stderr.write('Above the baseline: ' + '; '.join(worse))
                sys.exit(1)
            self.stdout.write('No count above the baseline.')
