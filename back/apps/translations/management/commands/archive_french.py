"""The texts only the French Bulletin printed, before 1926, given Arabic by AI translation (A of
the Bulletin-from-No.-1 review, 1 Nov 2026), each marked for readers as a machine translation from the official French.
The Arabic edition began on 1 Feb 1913, three months after the French, and printed a third to a half of it until
1924 (1913: 250 Arabic pages for 701 French). Run on the archive's folder, Haiku 5.5 only:

    archive_french register --pdfs DIR     the French issues of CORPUS_DIR/archive/plan_fr.json, edition translation_fr
    archive_french work read               every page once (columns when the image splits), the second readings
    archive_french work toc                each issue's contents («SOMMAIRE»)
    archive_french work match              each official entry paired by Haiku with the Arabic issues of its weeks
    archive_french work texts              the entries no Arabic text answers cut from the pages and translated
                                           (`translate_french`), to CORPUS_DIR/archive/translated/bo_<key>_fr.json
    archive_french status

Each file is then loaded anywhere with `load_translated`: the official French beside an Arabic that says it is an AI
translation of it. Workers share the issues by claim files (state/fr-<phase>/) and stop on STOP or STOP_BUDGET."""
import json
import time
import traceback
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.corpus.services import french
from apps.corpus.services.issue_structure import TOC_SCHEMA
from apps.corpus.services.llm import request, run_batch
from apps.sources.models import Edition, Issue
from apps.sources.services import archive, render
from apps.sources.services import issue as issue_service
from apps.sources.services.archive import kind_of
from apps.sources.services.ocr import OutOfCredit, OverBudget, SpendingNotAllowed, allow_spending, spent

MODEL = 'claude-haiku-5-5'
# The Arabic edition printed a text from three weeks before the French to four months after it (1913–1925).
BEFORE, AFTER = timedelta(days=21), timedelta(days=120)
ARABIC_NOTE = 'not printed in the Arabic edition (the French Bulletin alone holds it)'
# The codes of 1913 the site holds in Arabic from Adala (the DOC, the land registration dahir): never given a second,
# translated text, whatever the Arabic edition printed.
HELD = ('obligations et des contrats', 'immatriculation des immeubles')

MATCH_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['pairs'],
    'properties': {'pairs': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['fr', 'ar'],
        'properties': {'fr': {'type': 'integer'},
                       'ar': {'type': 'string', 'description': "the Arabic entry's id, or empty when none is that text"}}}}},
}
MATCH_SYSTEM = (
    'You compare the tables of contents of the Moroccan Bulletin officiel before 1926: the entries of one issue of the '
    'French edition, and the entries of the Arabic edition\'s issues of the same weeks. For each French entry, give the '
    'id of the Arabic entry that is the same text (the same dahir or order: the same subject, and the same day when '
    'both print one), or an empty string when no Arabic entry is that text. Never pair two different texts; when a '
    'French entry may be an Arabic one, pair them.'
)


def plan() -> dict:
    path = archive.root() / 'plan_fr.json'
    if not path.exists():
        raise CommandError(f'{path} is missing')
    return json.loads(path.read_text())


def issue_of(key: str) -> Issue | None:
    number, suffix = Issue.parse_key(key)
    return (Issue.objects.select_related('document')
            .filter(edition=Edition.TRANSLATION_FR, number=number, suffix=suffix).first())


def workdir(key: str) -> Path:
    path = Path(settings.CORPUS_DIR) / 'reports' / 'issues' / f'fr-{key}'
    path.mkdir(parents=True, exist_ok=True)
    return path


def official(toc: list[dict]) -> list[int]:
    """The entries of the official part (dahirs, orders, decisions): the notices are not translated."""
    return [i for i, e in enumerate(toc) if kind_of(e) < 3]


class Command(BaseCommand):
    help = 'The texts only the French Bulletin printed before 1926, read and translated into Arabic.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('action', choices=['register', 'work', 'status'])
        parser.add_argument('phase', nargs='?', choices=['read', 'toc', 'match', 'texts'])
        parser.add_argument('--pdfs', help='the folder holding the French PDFs (register)')
        parser.add_argument('--keys', help='only these issues, comma-separated')
        parser.add_argument('--chunk', type=int, default=0)
        parser.add_argument('--limit', type=int, default=0)

    def handle(self, *args, action, phase, **opts):
        allow_spending(opts['write'], log=self.stdout.write)
        self.log = lambda s: self.stdout.write(f'{time.strftime("%F %T")} {s}')
        # The French pages are printed upright: their orientation is never asked of Tesseract, which the machine that
        # runs this may not have (the Arabic archive takes it from Tesseract's files, read elsewhere).
        render._osd_rotation = lambda image: 0
        if action == 'register':
            return self.register(opts['pdfs'])
        if action == 'status':
            return self.status()
        if not phase:
            raise CommandError('work needs a phase: read, toc, match or texts')
        return self.work(phase, opts)

    # ── register ────────────────────────────────────────────────────────────────────────────────────────────────
    def register(self, pdfs: str | None) -> None:
        if not pdfs:
            raise CommandError('--pdfs is needed')
        links = Path(settings.CORPUS_DIR) / 'issues' / 'bo_fr'
        links.mkdir(parents=True, exist_ok=True)
        made = 0
        for item in plan()['issues']:
            if issue_of(item['key']) is not None:
                continue
            number, suffix = Issue.parse_key(item['key'])
            link = links / f'BO_{item["key"]}_fr.pdf'
            if not link.exists():
                link.symlink_to(Path(pdfs) / item['path'])
            issue = issue_service.register(link, edition=Edition.TRANSLATION_FR, number=number, suffix=suffix,
                                           day=date.fromisoformat(item['date']), url=item['url'])
            issue.document.meta = {**issue.document.meta, 'archive': item['path']}
            issue.document.save(update_fields=['meta'])
            made += 1
        self.log(f'registered {made}; {Issue.objects.filter(edition=Edition.TRANSLATION_FR).count()} French issues')

    # ── work ────────────────────────────────────────────────────────────────────────────────────────────────────
    def work(self, phase: str, opts) -> None:
        keys = opts['keys'].split(',') if opts['keys'] else [i['key'] for i in plan()['issues']]
        step = {'read': self.read, 'toc': self.toc, 'match': self.match, 'texts': self.texts}[phase]
        before = {'read': None, 'toc': 'fr-read', 'match': 'fr-toc', 'texts': 'fr-match'}[phase]
        size = opts['chunk'] or {'read': 6, 'toc': 20, 'match': 20, 'texts': 4}[phase]
        state, taken = f'fr-{phase}', 0
        while True:
            if why := archive.stopped():
                self.log(f'stopped: {why}')
                return
            chunk = []
            for k in keys:
                if archive.done(state, k) or (archive._state(state) / f'{k}.error').exists():
                    continue
                if before and not archive.done(before, k):
                    continue
                issue = issue_of(k)
                if issue is not None and archive.claim(state, k):
                    chunk.append(issue)
                    if len(chunk) >= size:
                        break
            if not chunk:
                self.log(f'{state}: nothing left for this worker')
                return
            started, cost = time.monotonic(), spent()
            self.failed = {}
            try:
                out = step(chunk)
                for issue in chunk:
                    if issue.key in out:
                        archive.mark(state, issue.key, 'done', json.dumps(out[issue.key], ensure_ascii=False))
                    else:
                        archive.mark(state, issue.key, 'error', self.failed.get(issue.key, 'no result'))
                self.log(f'{state} {",".join(i.key for i in chunk)}: ${spent() - cost} in {round(time.monotonic() - started)} s')
            except OutOfCredit as exc:
                self.log(f'out of credit: {exc}')
                return
            except OverBudget as exc:
                (archive.root() / 'STOP_BUDGET').write_text(f'{time.strftime("%F %T")} {exc}')
                self.log(f'budget reached: {exc}')
                return
            except SpendingNotAllowed:      # run without --write: the worker stops, no chunk is marked
                raise
            except Exception:  # noqa: BLE001 — the chunk is set aside with its traceback; the worker goes on
                for issue in chunk:
                    archive.mark(state, issue.key, 'error', traceback.format_exc())
                self.log(f'{state} {",".join(i.key for i in chunk)}: error, see state/{state}/<key>.error')
            finally:
                for issue in chunk:
                    archive.release(state, issue.key)
            taken += len(chunk)
            if opts['limit'] and taken >= opts['limit']:
                return

    def pages(self, issue):
        return list(issue.document.pages.order_by('index').select_related('document').prefetch_related('ocr_runs'))

    def read(self, issues: list[Issue]) -> dict:
        """Every page once, upright, by columns when its image splits; the second readings of a page cut or a table
        read in columns; the folios from the running heads."""
        todo = {i.key: archive.unread(self.pages(i), MODEL) for i in issues}
        archive.read([p for pages in todo.values() for p in pages], MODEL, log=self.log, upright=True)
        left = {p.pk for p in archive.unread([p for pages in todo.values() for p in pages], MODEL)}
        out, medians, pending = {}, {}, ([], [], [], {})
        for issue in issues:
            if n := sum(1 for p in todo[issue.key] if p.pk in left):
                self.failed[issue.key] = f'{n} pages left unread'
                continue
            pages = self.pages(issue)
            medians[issue.key] = archive.issue_ratio(pages, MODEL)
            whole, split, strips, why = archive.second_plan(pages, MODEL, medians[issue.key])
            pending[0].extend(whole), pending[1].extend(split), pending[2].extend(strips), pending[3].update(why)
        archive.send_second(*pending, MODEL, log=self.log)
        for issue in issues:
            if issue.key in self.failed:
                continue
            pages = self.pages(issue)
            doubts = archive.keep(pages, MODEL, medians[issue.key])
            path = archive.root() / 'doubts-fr' / f'{issue.key}.json'     # the Arabic issue of the same number has its own
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'median': medians[issue.key], 'pages': doubts}, ensure_ascii=False))
            out[issue.key] = {'pages': len(pages), 'doubts': len(doubts),
                              'first_page': issue_service.number_pages(issue)}
            folder = Path(settings.CORPUS_DIR) / 'renders' / issue.document.sha256[:16]
            for image in folder.glob('*.png'):
                image.unlink()
        return out

    def toc(self, issues: list[Issue]) -> dict:
        reqs = []
        for issue in issues:
            pages = issue.document.pages.order_by('index')[:french.TOC_PAGES]
            content = '\n\n'.join(f'=== Page {p.printed_number or p.index + 1} ===\n{french.clean(p.text)}'
                                  for p in pages if p.text)
            if not content:
                self.failed[issue.key] = 'no text on the contents pages'
                continue
            reqs.append(request(f'toc-fr-{issue.key}', model=MODEL, system=french.toc_system(issue), content=content,
                                schema=TOC_SCHEMA, max_tokens=32000))
        results = run_batch(f'toc-fr:{issues[0].key}+{len(issues) - 1}', reqs, log=self.log) if reqs else {}
        out = {}
        for issue in issues:
            r = results.get(f'toc-fr-{issue.key}')
            if not r or not r['data']:
                self.failed.setdefault(issue.key, f'contents not read: {(r or {}).get("stop") or (r or {}).get("error")}')
                continue
            entries = r['data']['entries']
            (workdir(issue.key) / 'toc.json').write_text(json.dumps(entries, ensure_ascii=False, indent=1))
            out[issue.key] = {'entries': len(entries), 'official': len(official(entries)),
                              'kinds': dict(Counter(e['type'] for e in entries))}
        return out

    def arabic_entries(self, day: date) -> list[dict]:
        """The official entries of the Arabic issues printed from three weeks before `day` to four months after it."""
        from apps.corpus.management.commands.archive import plan as arabic_plan
        root = Path(settings.CORPUS_DIR) / 'reports' / 'issues'
        out = []
        for item in arabic_plan()['issues']:
            if not day - BEFORE <= date.fromisoformat(item['date']) <= day + AFTER:
                continue
            path = root / item['key'] / 'toc.json'
            for j, e in enumerate(json.loads(path.read_text()) if path.exists() else []):
                if kind_of(e) < 3:
                    out.append({'id': f'{item["key"]}:{j}', 'date': item['date'], 'type': e['type'],
                                'signed': e.get('signed_on_gregorian') or '', 'title': e['title'][:160]})
        return out

    def match(self, issues: list[Issue]) -> dict:
        reqs, toc = [], {}
        for issue in issues:
            toc[issue.key] = json.loads((workdir(issue.key) / 'toc.json').read_text())
            entries = [{'fr': i, 'type': toc[issue.key][i]['type'], 'signed': toc[issue.key][i]['signed_on_gregorian'],
                        'title': toc[issue.key][i]['title'][:300]} for i in official(toc[issue.key])]
            if not entries:
                continue
            content = json.dumps({'french_issue': {'number': issue.key, 'date': issue.date.isoformat(), 'entries': entries},
                                  'arabic_entries': self.arabic_entries(issue.date)}, ensure_ascii=False)
            reqs.append(request(f'match-fr-{issue.key}', model=MODEL, system=MATCH_SYSTEM, content=content,
                                schema=MATCH_SCHEMA, max_tokens=8000))
        results = run_batch(f'match-fr:{issues[0].key}+{len(issues) - 1}', reqs, log=self.log) if reqs else {}
        out = {}
        for issue in issues:
            wanted = official(toc[issue.key])
            r = results.get(f'match-fr-{issue.key}')
            if wanted and (not r or not r['data']):
                self.failed[issue.key] = f'not matched: {(r or {}).get("stop") or (r or {}).get("error")}'
                continue
            pairs = {p['fr']: p['ar'] for p in (r['data']['pairs'] if r else [])}
            # An entry the answer left out is paired (never translated twice): only an empty «ar» says «no Arabic».
            alone = [i for i in wanted if i in pairs and not pairs[i]]
            (workdir(issue.key) / 'match.json').write_text(json.dumps(
                {'pairs': {str(i): pairs.get(i, '?') for i in wanted}, 'alone': alone}, ensure_ascii=False, indent=1))
            out[issue.key] = {'official': len(wanted), 'alone': len(alone)}
        return out

    def texts(self, issues: list[Issue]) -> dict:
        out = {}
        folder = archive.root() / 'translated'
        for issue in issues:
            toc = json.loads((workdir(issue.key) / 'toc.json').read_text())
            alone = {i for i in json.loads((workdir(issue.key) / 'match.json').read_text())['alone']
                     if not any(name in french._plain(toc[i]['title']) for name in HELD)}
            counts = french.load(issue, toc, only=alone)
            if counts['texts']:
                call_command('translate_french', issue.key, out=str(folder), arabic=ARABIC_NOTE,
                             stdout=open('/dev/null', 'w'))
            out[issue.key] = {**counts, 'alone': len(alone)}
        return out

    def status(self) -> None:
        keys = [i['key'] for i in plan()['issues']]
        state = archive.root() / 'state'
        for phase in ('read', 'toc', 'match', 'texts'):
            folder = state / f'fr-{phase}'
            names = {f.name for f in folder.iterdir()} if folder.exists() else set()
            self.stdout.write(f'fr-{phase}: {sum(1 for k in keys if f"{k}.done" in names)} of {len(keys)} done, '
                              f'{sum(1 for k in keys if f"{k}.error" in names)} errors')
        self.stdout.write(f'spent: {spent()}')
