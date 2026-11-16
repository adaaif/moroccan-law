"""The Arabic Bulletin before 2019 from its scans (the Bulletin-to-1956 review, 27 Oct 2026; from No. 1 of 1913 since
the Bulletin-from-No.-1 review, 1 Nov 2026), run on a machine of its own, then imported into the main database.

    archive register                every issue of CORPUS_DIR/archive/plan.json: its PDF linked, registered
    archive work pilot              Z4: the 13 pilot issues read whole and by columns at 3192 and 1596 px
    archive work catalog            Z5: each issue's cover and contents read, then its contents step
    archive order [--cited-dates F] Z7: the reading order from the catalog (CORPUS_DIR/archive/order.json); before
                                    1956, the issues printing a date the site cites a text by first (H4)
    archive work read               each issue in that order: every page once, the witness's second readings,
                                    page numbers
    archive work texts              later (the old issues' texts are not yet found well in their pages): the
                                    contents again if the catalog's fell short, then the texts step
    archive work fix                Z16 of the second-archive-run review: an issue read before the line test, its pages
                                    that lack the witness's lines read again in strips
    archive work read --only KIND   Z18: only the pages the contents give to KIND and the kinds before it (general:
                                    laws, general texts, the Constitutional Council; rules: special decrees and orders;
                                    decisions; notices), its state under read-KIND
    archive work texts --only KIND --code
                                    the texts step on what is read: KIND and the kinds before it described, the general
                                    ones by Haiku, the special ones by code (Z19), a description already paid kept
    archive queue                   every issue of the plan from its `coverage_from` (1956 by default) as
                                    reports/runs/queue_1956_2018.txt, for the coverage line (Z23): an old text's «no
                                    change found» is said of the issues read
    archive status [--json]         where the run stands
    archive report [--keys K]       the pilot's measures (CORPUS_DIR/archive/pilot.json; with --keys, the 1913–1955
                                    pilot's issues, pilot_1913.json)
    archive export --out DIR        where it ran: each issue a phase has done, as DIR/<key>.json.gz (pages, readings,
                                    contents, texts, doubts)
    archive import --folder DIR --pdfs P
                                    here: those issues registered from the same PDFs, their readings put back;
                                    then `process_issue <key> --steps load,links`, oldest first

Several `archive work <phase>` processes share the issues by claim files (archive.services); each stops on
CORPUS_DIR/archive/STOP, and all stop on STOP_BUDGET when a batch would pass OCR_BUDGET_USD. Paid steps use Haiku
5.5 only (LLM_MODELS_ALLOWED). What it writes stays in this database and folder: `load` and `links` run where the
corpus is, after the readings are copied back.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from apps.corpus.services.archive_run.exchange import Exchange
from apps.corpus.services.archive_run.issues import Issues
from apps.corpus.services.archive_run.measures import Measures
from apps.corpus.services.archive_run.steps import Steps
from apps.corpus.services.archive_run.work import Work
from apps.sources.models import Edition
from apps.sources.services.archive import KINDS
from apps.sources.services.ocr import allow_spending
# The names this module held before its parts moved to apps.corpus.services.archive_run, importable from it as before.
from apps.corpus.services.archive_run.common import MODEL, issue_of, looks_like_contents, plan, workdir  # noqa: F401
from apps.corpus.services.archive_run.issues import _NUMBER  # noqa: F401
from apps.corpus.services.archive_run.work import _CHANGES  # noqa: F401
from apps.sources.services.archive import LEGISLATION, general_or_law, kind_of  # noqa: F401


class Command(Exchange, Issues, Work, Steps, Measures, BaseCommand):
    help = 'The Arabic Bulletin before 2019 read from its scans, phase by phase.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('action', choices=['register', 'work', 'order', 'status', 'report', 'retry', 'export',
                                               'import', 'queue'])
        parser.add_argument('phase', nargs='?', choices=['pilot', 'catalog', 'read', 'texts', 'fix'])
        parser.add_argument('--pdfs', help='the folder holding <year>/BO_<n>_Ar.pdf (register)')
        parser.add_argument('--keys', help='only these issues, comma-separated')
        parser.add_argument('--limit', type=int, default=0, help='issues this worker takes at most')
        parser.add_argument('--missing', help='JSON {address: citations} of the texts the site cites and lacks (order)')
        parser.add_argument('--cited-dates', dest='cited_dates',
                            help='JSON {"dahir:YYYY-MM-DD": citations} of the texts before 1956 the site cites by date (order)')
        parser.add_argument('--json', action='store_true')
        parser.add_argument('--out', help='export: the folder the issues go to')
        parser.add_argument('--folder', help='import: the folder of exported issues')
        parser.add_argument('--french', action='store_true',
                            help='export: the French issues of A (archive_french, edition translation_fr) given by --keys, '
                                 'their pages and readings, so a translated text opens its French page anywhere')
        parser.add_argument('--wait', type=int, default=600, help='seconds to wait for Tesseract, read phase')
        parser.add_argument('--general', action='store_true',
                            help='texts phase: describe the general texts and the laws and dahirs only, the others later')
        parser.add_argument('--only', choices=KINDS,
                            help='read and texts phases: the pages and texts of this kind and the kinds before it')
        parser.add_argument('--code', action='store_true',
                            help='texts phase: the special texts described by code, not by Haiku')
        parser.add_argument('--chunk', type=int, default=0,
                            help='issues taken together, one batch a step (default: pilot 1, catalog 30, read 6)')

    def handle(self, *args, action, phase, **opts):
        allow_spending(opts['write'], log=self.stdout.write)
        self.log = lambda s: self.stdout.write(f'{time.strftime("%F %T")} {s}')
        if action == 'register':
            return self.register(opts['pdfs'])
        if action == 'work':
            if not phase:
                raise CommandError('work needs a phase: pilot, catalog, read, texts or fix')
            return self.work(phase, opts)
        if action == 'order':
            return self.order(opts['missing'], opts['cited_dates'])
        if action == 'status':
            return self.status(opts['json'])
        if action == 'retry':
            return self.retry(phase)
        if action == 'export':           # with --only, the issues a phase did by kind (`texts --only decisions`)
            if opts['french']:
                return self.export('fr-read', opts['out'], opts['keys'], Edition.TRANSLATION_FR)
            return self.export(f'{phase or "read"}-{opts["only"]}' if opts['only'] else phase or 'read', opts['out'],
                               opts['keys'])
        if action == 'import':
            return self.import_(opts['folder'], opts['pdfs'])
        if action == 'queue':
            return self.queue()
        self.keys = opts['keys']
        return self.report()
