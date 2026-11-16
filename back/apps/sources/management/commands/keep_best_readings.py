"""Each page of the given issues keeps its best reading again, after a change to how readings are chosen.

Free (no model call). `--recount` first recounts every page's layer letters the way ingest now does. Prints the
issues whose pages changed: their texts need `process_issue <key> --steps texts,load` again. With no issue named it
rewrites every page's reading (and --recount every page's count), so it runs only on the database named:

    keep_best_readings 7520 7465-bis
    keep_best_readings --yes-on <database name>
"""
from django.core.management.base import BaseCommand

from apps.sources.models import Edition, Issue, Page
from apps.sources.services.ingest import letters
from apps.sources.services.issue import keep_best
from config import confirm

MODEL = 'claude-haiku-5-5'


class Command(BaseCommand):
    help = 'Choose each page\'s best reading again.'

    def add_arguments(self, parser):
        parser.add_argument('keys', nargs='*', help='issue keys (7520, 7465-bis); none = every issue read by the model')
        parser.add_argument('--recount', action='store_true', help='recount every page\'s layer letters first')
        parser.add_argument('--edition', default=Edition.GENERAL_AR)
        confirm.add_argument(parser)

    def handle(self, *args, keys, recount, edition, yes_on='', **opts):
        if recount or not keys:         # every page of the database, not the issues named
            confirm.confirm(yes_on, what='keep_best_readings ' + ('--recount' if recount else 'with no issue named'))
        if recount:
            stale = []
            for page in Page.objects.select_related('document').only(
                    'layer_text', 'layer_letters', 'document__language').iterator(chunk_size=500):
                if (count := letters(page.layer_text, page.document.language)) != page.layer_letters:
                    page.layer_letters = count
                    stale.append(page)
            Page.objects.bulk_update(stale, ['layer_letters'], batch_size=500)
            self.stdout.write(f'layer letters recounted on {len(stale)} pages')
        issues = ([Issue.objects.get(edition=edition, number=n, suffix=s) for n, s in map(Issue.parse_key, keys)] if keys else
                  Issue.objects.filter(edition=edition, document__pages__ocr_runs__engine=MODEL).distinct()
                  .order_by('number', 'suffix'))
        for issue in issues:
            pages = list(issue.document.pages.order_by('index'))
            if changed := keep_best(pages, MODEL):
                self.stdout.write(f'{issue.key}: {len(changed)} pages changed: '
                                  + ', '.join(str(p.index) for p in changed))
