"""One Bulletin Officiel issue end to end, in resumable steps:

  ingest   register the PDF (CORPUS_DIR/issues/bo_ar/BO_<n>_ar.pdf; the French translation edition's
           issues/bo_fr/BO_<n>_fr.pdf, --edition translation_fr) and read its pages
  ocr      read every page with Claude (batches); a page left short of its text layer is read again column
           by column; each page keeps its most complete reading
  number   printed page numbers from the running headers
  toc      the table of contents: every text, its heading and first page
  texts    each text in full: articles cut by code; the model describes title, number, dates, preamble (its lists of
           citations and amendments stay in texts.json, a witness only)
  load     the texts into corpus: Text, Version, Article, each at the address its kind and number give
  links    what the issue's texts change and cite, read by code, weighed against their witnesses, and applied to
           every text they change (consolidation.services.engine, rows L3–L10)

A French issue reads its contents and cuts its texts by their «Article» headings (`texts` does nothing for it):
`load` keeps each beside the Arabic text it translates (apps.translations).
"""
import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sources.models import Edition, Issue
from apps.sources.services import issue as issue_service
from apps.sources.services.ocr import allow_spending

ENGINES = {'haiku': 'claude-haiku-5-5', 'sonnet': 'claude-sonnet-5-5', 'opus': 'claude-opus-5-5'}
STEPS = ['ingest', 'ocr', 'number', 'toc', 'texts', 'load', 'links']


class Command(BaseCommand):
    help = 'Process one BO issue end to end.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('issue', help='The issue key: «7533», «7465-bis».')
        parser.add_argument('--date', help='Issue date, YYYY-MM-DD (needed by ingest).')
        parser.add_argument('--url', default='')
        parser.add_argument('--edition', default=Edition.GENERAL_AR)
        parser.add_argument('--engine', default='haiku', choices=ENGINES)
        parser.add_argument('--steps', default=','.join(STEPS))
        parser.add_argument('--pages', type=int, default=None,
                            help='ocr: read only the first N pages (the cover and contents, for a sweep)')
        parser.add_argument('--toc-halves', action='store_true',
                            help='read the contents in two halves at once (it was cut read whole)')

    def workdir(self, key: str, french: bool = False, conventions: bool = False) -> Path:
        name = f'fr-{key}' if french else f'eci-{key}' if conventions else key
        path = Path(settings.CORPUS_DIR) / 'reports' / 'issues' / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def handle(self, *args, **opts):
        allow_spending(opts['write'], log=self.stdout.write)
        key, model = opts['issue'], ENGINES[opts['engine']]
        number, suffix = Issue.parse_key(key)
        steps = opts['steps'].split(',')
        log = self.stdout.write
        french = opts['edition'] == Edition.TRANSLATION_FR
        conventions = opts['edition'] == Edition.CONVENTIONS_AR
        if 'ingest' in steps:
            if not opts['date']:
                raise CommandError('--date is needed to register the issue.')
            folder, lang = ('bo_fr', 'fr') if french else ('bo_ar', 'ar')
            path = Path(settings.CORPUS_DIR) / 'issues' / folder / f'BO_{key}_{lang}.pdf'
            if conventions:     # the conventions edition (fetch_conventions): its own numbers, its own folder
                path = Path(settings.CORPUS_DIR) / 'issues' / 'eci_ar' / f'ECI_{key}_ar.pdf'
            issue = issue_service.register(path, edition=opts['edition'], number=number, suffix=suffix,
                                           day=date.fromisoformat(opts['date']), url=opts['url'])
            log(f'registered {issue}: {issue.document.page_count} pages')
        issue = Issue.objects.select_related('document').get(edition=opts['edition'], number=number, suffix=suffix)
        if 'ocr' in steps:
            issue_service.ocr_issue(issue, model, log=log, first=opts['pages'])
        if 'number' in steps:
            log(f'printed pages start at {issue_service.number_pages(issue)}')
        work = self.workdir(key, french, conventions)
        if french:
            from apps.corpus.services import french as fr
            if 'toc' in steps:
                toc = fr.read_toc(issue, model, log=log)
                (work / 'toc.json').write_text(json.dumps(toc, ensure_ascii=False, indent=1))
                log(f'table of contents: {len(toc)} texts')
            if 'load' in steps:
                log(f'loaded: {fr.load(issue, json.loads((work / "toc.json").read_text()))}')
            return
        if 'toc' in steps:
            from apps.corpus.services.issue_structure import read_toc
            toc = read_toc(issue, model, log=log, halves=opts['toc_halves'])
            (work / 'toc.json').write_text(json.dumps(toc, ensure_ascii=False, indent=1))
            log(f'table of contents: {len(toc)} texts')
        if 'texts' in steps:
            from apps.corpus.services.issue_structure import extract_texts
            toc = json.loads((work / 'toc.json').read_text())
            texts = extract_texts(issue, toc, model, log=log)
            (work / 'texts.json').write_text(json.dumps(texts, ensure_ascii=False, indent=1))
            log(f'texts read: {sum(1 for t in texts if t.get("data"))} of {len(texts)}')
        if 'load' in steps:
            from apps.corpus.services.issue_structure import load_texts
            texts = json.loads((work / 'texts.json').read_text())
            summary = load_texts(issue, texts)
            log(f'loaded: {summary}')
        if 'links' in steps and issue.edition == Edition.GENERAL_AR:
            from apps.consolidation.services import engine
            from apps.corpus.models import Text
            log(f'links: {engine.run(list(Text.objects.filter(first_published_in=issue)), log=log)}')
            from apps.sources.services import coverage
            coverage.refresh([issue.key])
