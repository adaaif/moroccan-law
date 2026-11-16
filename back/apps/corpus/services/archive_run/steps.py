"""Each phase's step on a chunk of issues, one batch a step for the whole chunk: the contents (`tocs`), the catalog,
the reading, the fix, the texts, and the pilot."""
import json
import traceback
from collections import Counter

from apps.corpus.services.archive_run.common import MODEL, looks_like_contents, workdir
from apps.sources.models import Issue, OcrRun
from apps.sources.services import archive, witness
from apps.sources.services import issue as issue_service
from apps.sources.services.archive import KINDS, general_or_law, kind_of
from apps.sources.services.ocr import OCR_WIDTH, ocr_columns_batch, ocr_readings_batch


class Steps:
    """The phases' steps, each on a chunk of issues."""

    def tocs(self, issues: list[Issue]) -> dict[str, list]:
        """The contents step for several issues in one batch. An issue whose answer was cut is read again alone, in
        halves, then quarters and eighths of its printed pages (BO 6695's contents ran past 48,000 characters in each
        half); one that still fails is set aside alone (self.failed), the chunk's other issues kept."""
        from apps.corpus.services.issue_structure import TOC_PAGES, TOC_SCHEMA, toc_system
        from apps.corpus.services.llm import request, run_batch

        def content(issue):
            pages = issue.document.pages.order_by('index')[:TOC_PAGES]
            return '\n\n'.join(f'=== الصفحة {p.printed_number or p.index + 1} ===\n{p.text}' for p in pages if p.text)

        for issue in issues:
            if not content(issue):          # nothing read on its first pages: never sent (the API refuses it)
                self.failed[issue.key] = 'no text on the contents pages'
        issues = [i for i in issues if i.key not in self.failed]
        if not issues:
            return {}
        reqs = [request(f'toc-{i.key}', model=MODEL, system=toc_system(i), content=content(i), schema=TOC_SCHEMA,
                        max_tokens=32000) for i in issues]
        results = run_batch(f'toc:{issues[0].key}+{len(issues) - 1}', reqs, log=self.log)
        out = {}
        for issue in issues:
            r = results.get(f'toc-{issue.key}') or {'data': None, 'stop': 'missing', 'error': 'missing'}
            entries = r['data']['entries'] if r['data'] else None
            for parts in (2, 4, 8):
                if entries is not None:
                    break
                first = issue.document.pages.order_by('index').first().printed_number or 1
                last = first + (issue.document.page_count or 1)
                bounds = [first + (last - first) * k // parts for k in range(parts + 1)]
                part_reqs = [request(f'toc-{issue.key}-{parts}-{k}', model=MODEL, content=content(issue),
                                     schema=TOC_SCHEMA, max_tokens=32000,
                                     system=f'{toc_system(issue)} Return only the entries whose page is from {bounds[k]} '
                                            f'to {bounds[k + 1] - 1}.') for k in range(parts)]
                answers = run_batch(f'toc:{issue.key}/{parts}', part_reqs, log=self.log)
                got = [answers.get(r['custom_id']) for r in part_reqs]
                if all(g and g['data'] for g in got):
                    entries = [e for k, g in enumerate(got) for e in g['data']['entries']
                               if bounds[k] <= e['page'] < bounds[k + 1] or (k == parts - 1 and e['page'] >= bounds[k])]
            if entries is None:
                self.failed[issue.key] = f'contents not read, even in eighths ({r["stop"] or r["error"]})'
                continue
            out[issue.key] = entries
            (workdir(issue.key) / 'toc.json').write_text(json.dumps(entries, ensure_ascii=False, indent=1))
        return out

    def catalog(self, issues: list[Issue]) -> dict[str, dict]:
        """Z5: each issue's cover and contents pages read once, two more while the last still reads as contents,
        then the contents step; all the chunk's issues in one batch a step."""
        from apps.corpus.services.issue_structure import TOC_PAGES

        pages = {i.key: self.pages(i) for i in issues}
        n = {i.key: min(witness.contents_pages(i.document), len(pages[i.key])) for i in issues}
        todo = list(issues)
        while todo:
            archive.read([p for i in todo for p in archive.unread(pages[i.key][:n[i.key]], MODEL)], MODEL,
                         log=self.log, upright=True)
            more = []
            for issue in todo:
                pages[issue.key] = self.pages(issue)
                kept = pages[issue.key][:n[issue.key]]
                if not kept:
                    continue
                archive.keep(kept, MODEL, witness.median_ratio([]))
                cap = min(TOC_PAGES, len(pages[issue.key]))
                if n[issue.key] < cap and looks_like_contents(kept[-1].text):
                    n[issue.key] = min(n[issue.key] + 2, cap)
                    more.append(issue)
            todo = more
        tocs = self.tocs(issues)
        return {i.key: {'pages_read': n[i.key], 'texts': len(tocs[i.key]),
                        'kinds': dict(Counter(e['type'] for e in tocs[i.key])),
                        'general': sum(1 for e in tocs[i.key] if e['section'] == 'general')} for i in issues
                if i.key in tocs}

    def read(self, issues: list[Issue]) -> dict[str, dict]:
        """Every page once (or with --only the pages of a kind, Z18), the witness's second readings, page numbers;
        one batch a step for the whole chunk. The texts step waits for its own phase: the pilot found the old issues'
        texts in their pages too seldom (1956: 16 of 44, 1971: 4 of 31) for it to be paid yet."""
        todo = {i.key: archive.unread(self.pages_for(i), MODEL) for i in issues}
        archive.read([p for pages in todo.values() for p in pages], MODEL, log=self.log)
        left = {p.pk for p in archive.unread([p for pages in todo.values() for p in pages], MODEL)}
        for issue in issues:     # their batch cancelled twice (BATCH_WAIT_S): set aside, never done with pages unread
            if n := sum(1 for p in todo[issue.key] if p.pk in left):
                self.failed[issue.key] = f'{n} pages left unread: their batch was cancelled twice'
        issues = [i for i in issues if i.key not in self.failed]
        medians, pending = {}, ([], [], [], {})
        for issue in issues:
            pages = self.pages(issue)
            medians[issue.key] = archive.issue_ratio(pages, MODEL)
            whole, split, strips, why = archive.second_plan(pages, MODEL, medians[issue.key])
            pending[0].extend(whole), pending[1].extend(split), pending[2].extend(strips), pending[3].update(why)
        archive.send_second(*pending, MODEL, log=self.log)
        out = {}
        for issue in issues:     # the readings are kept: an issue that fails here is set aside alone, its retry unpaid
            try:
                pages = self.pages(issue)
                doubts = archive.keep(pages, MODEL, medians[issue.key])
                archive.write_doubts(issue, medians[issue.key], doubts)
                offset = issue_service.number_pages(issue, self.contents(issue.key))
            except Exception:  # noqa: BLE001 — the issue is set aside with its traceback; the run goes on
                self.failed[issue.key] = traceback.format_exc()
                continue
            out[issue.key] = {'pages': sum(1 for p in pages if p.text), 'doubts': len(doubts), 'first_page': offset,
                              'median': round(medians[issue.key], 3), 'second': sum(1 for p in pages if p.pk in pending[3])}
            self.forget_renders(issue)
        return out

    def fix(self, issues: list[Issue]) -> dict[str, dict]:
        """Z16 of the second-archive-run review: an issue read before the line test (Z15), its pages whose readings all
        lack the witness's lines (or were cut) read again in strips, a table read in columns read whole; the best
        reading kept and the doubts written again. Its texts are cut again by `work texts --only … --code` (Z17)."""
        medians, pending = {}, ([], [], [], {})
        for issue in issues:
            pages = self.pages(issue)
            medians[issue.key] = archive.issue_ratio(pages, MODEL)
            whole, split, strips, why = archive.second_plan(pages, MODEL, medians[issue.key])
            pending[0].extend(whole), pending[1].extend(split), pending[2].extend(strips), pending[3].update(why)
        archive.send_second(*pending, MODEL, log=self.log)
        out = {}
        for issue in issues:
            try:
                pages = self.pages(issue)
                doubts = archive.keep(pages, MODEL, medians[issue.key])
                archive.write_doubts(issue, medians[issue.key], doubts)
            except Exception:  # noqa: BLE001 — the issue is set aside with its traceback; the run goes on
                self.failed[issue.key] = traceback.format_exc()
                continue
            out[issue.key] = {'sent': sum(1 for p in pages if p.pk in pending[3]), 'doubts': len(doubts),
                              'lines': sum(1 for d in doubts if d['reason'] == 'lines')}
            self.forget_renders(issue)
        return out

    def texts(self, issues: list[Issue]) -> dict[str, dict]:
        """The texts step for issues already read: the contents again when the catalog's stopped short of an issue's
        last pages, then each text described; one batch a step for the whole chunk."""
        from apps.corpus.services.issue_structure import texts_answered, texts_requests
        from apps.corpus.services.llm import run_batch

        short, tocs, before = [], {}, {}
        for issue in issues:
            tocs[issue.key] = json.loads((workdir(issue.key) / 'toc.json').read_text())
            # The texts are cut by the printed pages: numbered again by the contents' own (Z27).
            offset = issue_service.number_pages(issue, tocs[issue.key]) or issue.first_page_number or 1
            pages = issue.document.page_count or 1
            done = workdir(issue.key) / 'texts.json'
            before[issue.key] = json.loads(done.read_text()) if done.exists() else None
            # Read again once: an issue whose texts step ran before already had its contents read again.
            if before[issue.key] is None and (not tocs[issue.key]
                                              or max(e['page'] for e in tocs[issue.key]) < offset + 0.6 * (pages - 1)):
                short.append(issue)
        if short:
            tocs.update(self.tocs(short))
        issues = [i for i in issues if i.key not in self.failed]
        requests, waiting = [], {}
        if self.only:
            level = KINDS.index(self.only)
            only = lambda e: kind_of(e) <= min(level, 2) and (kind_of(e) == 0 or not self.code)
            by_code = (lambda e: 0 < kind_of(e) <= min(level, 2)) if self.code else None
        else:
            only, by_code = (general_or_law if self.general else None), None
        for issue in issues:
            reqs, items = texts_requests(issue, tocs[issue.key], MODEL, log=self.log, prefix=f'{issue.key}-',
                                         only=only, by_code=by_code, before=before[issue.key])
            requests += reqs
            waiting[issue.key] = items
        results = run_batch(f'texts:{issues[0].key}+{len(issues) - 1}', requests, log=self.log) if requests else {}
        out = {}
        for issue in issues:
            texts = texts_answered(waiting[issue.key], results)
            (workdir(issue.key) / 'texts.json').write_text(json.dumps(texts, ensure_ascii=False, indent=1))
            out[issue.key] = {'texts': len(texts), 'found': sum(1 for t in texts if t.get('data')),
                              'by_code': sum(1 for t in texts if t.get('stop') == 'code'),
                              'sent': sum(1 for r in requests if r['custom_id'].startswith(f'{issue.key}-')),
                              'contents_again': issue in short}
        return out

    def pilot(self, issues: list[Issue]) -> dict[str, dict]:
        return {i.key: self.pilot_one(i) for i in issues}

    def pilot_one(self, issue: Issue) -> dict:
        """Z4 and Z13: every page read whole and by columns at 3192 px (the 2019 way, so each era's readings can be
        compared) and at 1596 px (half the image tokens); the archive's choice kept; numbered, contents, texts."""
        from apps.corpus.services.issue_structure import extract_texts, read_toc

        pages = [p for p in self.pages(issue) if p.kind != 'blank']
        fresh = archive.unread(pages, MODEL)
        turned = [p for p in fresh if issue_service.is_sideways(p)]
        split = [p for p in fresh if p not in turned and issue_service.render_columns(p)]
        ocr_readings_batch([p for p in fresh if p not in turned], turned, split, MODEL, log=self.log)
        if split and not OcrRun.objects.filter(page__in=split, variant=f'columns-{OCR_WIDTH}').exists():
            ocr_columns_batch(split, MODEL, width=OCR_WIDTH, log=self.log)
        pages = self.pages(issue)
        median = archive.issue_ratio(pages, MODEL)
        doubts = archive.keep(pages, MODEL, median)
        offset = issue_service.number_pages(issue)
        toc = read_toc(issue, MODEL, log=self.log)
        work = workdir(issue.key)
        (work / 'toc.json').write_text(json.dumps(toc, ensure_ascii=False, indent=1))
        texts = extract_texts(issue, toc, MODEL, log=self.log)
        (work / 'texts.json').write_text(json.dumps(texts, ensure_ascii=False, indent=1))
        return {'pages': len(pages), 'split': len(split), 'turned': len(turned), 'median': round(median, 3),
                'doubts': len(doubts), 'first_page': offset, 'texts': len(texts),
                'found': sum(1 for t in texts if t.get('data'))}
