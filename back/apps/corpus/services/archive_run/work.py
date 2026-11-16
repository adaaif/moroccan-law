"""`archive work <phase>`: the issues a phase takes, claimed a chunk at a time by the workers that share them, each
chunk's outcome marked and its errors set aside (`archive retry` offers them again); the pages a reading by kind
takes (Z18) and the order of the decisions."""
import json
import os
import re
import time
import traceback
from pathlib import Path

from django.conf import settings

from apps.corpus.services.archive_run.common import issue_of, plan, workdir
from apps.sources.models import Issue, Page
from apps.sources.services import archive, witness
from apps.sources.services import issue as issue_service
from apps.sources.services.archive import KINDS, kind_of
from apps.sources.services.ocr import OutOfCredit, OverBudget, SpendingNotAllowed, spent


# Z18: the decisions that change another text are read first.
_CHANGES = re.compile(r'بتغيير|بتتميم|بنسخ|بتعديل|بإلغاء')


class Work:
    """The work loop over a phase's issues, and the pages each issue gives it."""

    def keys_for(self, phase: str, opts) -> list[str]:
        if opts['keys']:
            return opts['keys'].split(',')
        p = plan()
        if phase == 'pilot':
            return p['pilot']
        order = archive.root() / 'order.json'
        if phase in ('read', 'texts') and order.exists():
            return json.loads(order.read_text())
        return [i['key'] for i in p['issues']]

    def work(self, phase: str, opts) -> None:
        keys, taken = self.keys_for(phase, opts), 0
        self.general, self.only, self.code = opts['general'], opts['only'], opts['code']
        step = {'pilot': self.pilot, 'catalog': self.catalog, 'read': self.read, 'texts': self.texts,
                'fix': self.fix}[phase]
        size = opts['chunk'] or {'pilot': 1, 'catalog': 30, 'read': 6, 'texts': 12, 'fix': 6}[phase]
        base, phase = phase, f'{phase}-{self.only}' if self.only and phase in ('read', 'texts') else phase
        if base == 'read' and self.only == 'decisions' and not opts['keys']:
            keys = self.decisions_first(keys)
        while True:
            if why := archive.stopped():
                self.log(f'stopped: {why}')
                return
            chunk, waiting = [], False
            for k in keys:
                if archive.done(phase, k) or (archive._state(phase) / f'{k}.error').exists():
                    continue
                issue = issue_of(k)
                if issue is None:
                    continue
                if base == 'read' and not archive.done('catalog', k):
                    continue
                if base == 'read' and archive.done('read', k):
                    continue          # read whole before Z18: nothing left to read by kind
                if base == 'texts' and not self.read_for(k):
                    continue
                if base == 'fix' and not archive.done('read', k):
                    continue
                if base in ('read', 'pilot', 'fix') and not witness.has(issue.document):
                    waiting = True       # Tesseract has not reached it: take the next one it has read
                    continue
                if archive.claim(phase, k):
                    chunk.append(issue)
                    if len(chunk) >= size:
                        break
            if not chunk:
                if waiting and base == 'read':
                    self.log(f'waiting {opts["wait"]} s for Tesseract')
                    time.sleep(opts['wait'])
                    continue
                self.log(f'{phase}: nothing left for this worker')
                return
            started, before = time.monotonic(), spent()
            self.failed = {}
            try:
                summaries = step(chunk)
                cost = str(spent() - before)
                for issue in chunk:
                    if issue.key not in summaries:
                        archive.mark(phase, issue.key, 'error', self.failed.get(issue.key, 'no result'))
                        continue
                    summary = {**summaries[issue.key], 'chunk': len(chunk), 'chunk_cost': cost,
                               'seconds': round(time.monotonic() - started)}
                    archive.mark(phase, issue.key, 'done', json.dumps(summary, ensure_ascii=False))
                self.log(f'{phase} {",".join(i.key for i in chunk)}: ${cost} in {round(time.monotonic() - started)} s')
            except OutOfCredit as exc:     # this worker's key is spent: it stops alone, the chunk left for another
                name = os.environ.get('ARCHIVE_KEY_NAME', 'key')
                (archive.root() / f'NO_CREDIT-{name}').write_text(f'{time.strftime("%F %T")} {exc}')
                self.log(f'out of credit ({name}): {exc}')
                return
            except OverBudget as exc:
                (archive.root() / 'STOP_BUDGET').write_text(f'{time.strftime("%F %T")} {exc}')
                self.log(f'budget reached: {exc}')
                return
            except SpendingNotAllowed:      # run without --write: the worker stops, no chunk is marked
                raise
            except Exception:     # noqa: BLE001 — the chunk is set aside with its traceback (`archive retry`); the worker goes on
                for issue in chunk:
                    archive.mark(phase, issue.key, 'error', traceback.format_exc())
                self.log(f'{phase} {",".join(i.key for i in chunk)}: error, see state/{phase}/<key>.error')
            finally:
                for issue in chunk:
                    archive.release(phase, issue.key)
            taken += len(chunk)
            if opts['limit'] and taken >= opts['limit']:
                return

    def pages(self, issue: Issue) -> list[Page]:
        return list(issue.document.pages.order_by('index').select_related('document').prefetch_related('ocr_runs'))

    def pages_for(self, issue: Issue) -> list[Page]:
        """Every page, or with --only the pages its contents give to that kind and the kinds before it (Z18): from a
        text's page to the next text's and one more, in case it runs on; the cover and contents too. The whole issue
        when its contents or its folios cannot place the texts."""
        pages = self.pages(issue)
        if not self.only:
            return pages
        contents = self.contents(issue.key)
        toc = sorted((e for e in contents or [] if isinstance(e.get('page'), int)), key=lambda e: e['page'])
        offset = issue_service.number_pages(issue, contents) or issue.first_page_number
        if not toc or offset is None:
            return pages
        n, level = len(pages), KINDS.index(self.only)
        starts = [(min(max(e['page'] - offset, 0), n - 1), kind_of(e)) for e in toc]
        # Before 1956 the contents often leave out the non-official part: its heading, as Tesseract reads it, ends the
        # official texts' pages (the pilot of the Bulletin-from-No.-1 review: two pages in three are notices).
        if issue.date.year < 1956 and (cut := witness.unofficial_from(issue.document)) is not None:
            starts = sorted([*starts, (cut, 3)])
        chosen = set(range(starts[0][0]))
        for k, (start, kind) in enumerate(starts):
            end = starts[k + 1][0] if k + 1 < len(starts) else n - 1
            if kind <= level:
                chosen.update(range(start, min(max(start, end) + 2, n)))
        return [p for p in pages if p.index in chosen]

    def contents(self, key: str) -> list[dict] | None:
        """The issue's contents as the catalog read them (toc.json), or None before the catalog."""
        path = workdir(key) / 'toc.json'
        return json.loads(path.read_text()) if path.exists() else None

    def read_for(self, key: str) -> bool:
        """The issue is read as far as this texts step describes: whole, or by kind up to its kind."""
        if archive.done('read', key):
            return True
        level = KINDS.index(self.only) if self.only else len(KINDS) - 1
        return any(archive.done(f'read-{k}', key) for k in KINDS[level:])

    def decisions_first(self, keys: list[str]) -> list[str]:
        """Z18: the issues whose decisions change another text first, then the newest (they cost the least a page and
        are the likeliest in force)."""
        dates = {i['key']: i['date'] for i in plan()['issues']}

        def rank(key):
            path = workdir(key) / 'toc.json'
            toc = json.loads(path.read_text()) if path.exists() else []
            changes = any(kind_of(e) == 2 and _CHANGES.search(e.get('title') or '') for e in toc)
            return not changes, [-ord(c) for c in dates.get(key, '')]
        return sorted(keys, key=rank)

    def forget_renders(self, issue: Issue) -> None:
        """An issue read: its page images go (tens of GB over the run), as the 2019 run's column cuts did."""
        folder = Path(settings.CORPUS_DIR) / 'renders' / issue.document.sha256[:16]
        for image in folder.glob('*.png'):
            image.unlink()

    def retry(self, phase: str | None) -> None:
        """The issues a phase set aside with an error, offered again."""
        folder = archive.root() / 'state' / (phase or '')
        gone = 0
        for path in folder.glob('**/*.error'):
            path.unlink()
            gone += 1
        self.log(f'{gone} issues offered again')
