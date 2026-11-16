"""The Arabic Bulletin before 2019, read from its scans (the Bulletin-to-1956 review, 27 Oct 2026: Z1, Z3–Z5, Z7–Z14
«Yes», Z2 and Z6 «No»: the readers at half load on the machines that run them, every page read, the next month's
allowance taking over where this one ends).

A scan has no text layer, so the 2019 way (every page whole, then by columns, the layer confirming) is replaced by:
- one reading a page (Z8): by columns when Tesseract sees two columns and the image splits cleanly, whole
  otherwise, turned upright when sideways;
- Tesseract as the witness (Z9): a reading whose letters stray more than 15 % from what the issue's own pages
  show, a cut answer or a table cut in two is read once more the other way; a page still in doubt keeps its
  closest reading and is listed for /corrections, never guessed.

Several workers share the issues through claim files under CORPUS_DIR/archive/state/<phase>/.
"""
import json
import os
import re
import socket
import time
from pathlib import Path

from django.conf import settings

from apps.sources.models import OcrRun, Page, PageKind, TextSource
from apps.sources.services import witness
from apps.sources.services.issue import clean_reading, mostly_table
from apps.sources.services.ocr import OCR_WIDTH, PROMPT_VERSION, ocr_readings_batch, ocr_strips_batch
from apps.sources.services.render import is_sideways, render_columns

BAND = 0.15
# The columns' image width: 3192 px as since 2019, or 1596 if the pilot shows a 200 dpi scan reads as well at half
# the image tokens (Z13).
COLUMN_WIDTH = int(os.environ.get('ARCHIVE_COLUMN_WIDTH', 2 * OCR_WIDTH))


def _width(run: OcrRun) -> int:
    tail = run.variant.rsplit('-', 1)[-1]
    return int(tail) if tail.isdigit() else 0


def root() -> Path:
    path = Path(settings.CORPUS_DIR) / 'archive'
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── what a page holds, by its issue's contents ──────────────────────────────────────────────────────────────────

# 28 Oct 2026: describing these is left to a later allowance; until then the special texts wait.
LEGISLATION = {'law', 'organic_law', 'dahir', 'decree_law'}


def general_or_law(entry: dict) -> bool:
    return entry.get('section') == 'general' or entry.get('type') in LEGISLATION


# Z18 and Z21 of the second-archive-run review (29 Oct 2026): what a page holds, by its contents, read in this order.
KINDS = ('general', 'rules', 'decisions', 'notices')
_COUNCIL = re.compile(r'المجلس الدستوري|المحكمة الدستورية')


def council(entry: dict) -> bool:
    return bool(_COUNCIL.search(f'{entry.get("rubric") or ""} {entry.get("title") or ""}'))


def kind_of(entry: dict) -> int:
    """0 a law, a general text or the Constitutional Council's; 1 a special decree, order or convention; 2 another
    special text (decisions, mostly); 3 a notice."""
    if general_or_law(entry) or council(entry):
        return 0
    if entry.get('section') == 'special':
        return 1 if entry.get('type') in ('decree', 'order', 'convention') else 2
    return 3


# ── which reading a page gets ───────────────────────────────────────────────────────────────────────────────────

def unread(pages: list[Page], model: str) -> list[Page]:
    """The pages not yet read, a blank one left out only when Tesseract saw almost nothing on it. Registration calls
    a page blank when pdfium finds no image on it, and 12,417 scanned pages in 372 issues keep their image inside a
    form object it does not look into (Neevia PDFcompress, Distiller: BO 6300, 6447 bis; 28 Oct 2026)."""
    read = set(OcrRun.objects.filter(page__in=pages, engine=model, prompt_version=PROMPT_VERSION)
               .values_list('page_id', flat=True))
    return [p for p in pages if p.pk not in read and not (p.kind == PageKind.BLANK and witness.empty(witness.of(p)))]


def plan(pages: list[Page], upright: bool = False) -> tuple[list[Page], list[Page], list[Page]]:
    """(whole, turned, split): each page's one reading. `upright`: covers and contents, never printed sideways, skip
    the orientation check (for a page Tesseract has not read yet, a Tesseract call here)."""
    whole, turned, split = [], [], []
    for page in pages:
        if not upright and is_sideways(page):   # for a scan the worker's orientation check, when it has read it
            turned.append(page)
        elif witness.two_columns(witness.of(page)) is False or not render_columns(page, COLUMN_WIDTH, upright=upright):
            whole.append(page)
        else:
            split.append(page)
    return whole, turned, split


def read(pages: list[Page], model: str, log=print, upright: bool = False) -> None:
    whole, turned, split = plan(pages, upright)
    log(f'{len(split)} pages by columns, {len(whole)} whole, {len(turned)} turned')
    ocr_readings_batch(whole, turned, split, model, width=COLUMN_WIDTH, log=log)


# ── what the witness doubts ─────────────────────────────────────────────────────────────────────────────────────

def _runs(page: Page, model: str) -> list[OcrRun]:
    return [r for r in page.ocr_runs.all() if r.engine == model and r.text]


def issue_ratio(pages: list[Page], model: str) -> float:
    return witness.median_ratio([witness.ratio(p, clean_reading(runs[0].text))
                                 for p in pages if (runs := _runs(p, model))])


def gap(page: Page, run: OcrRun) -> dict | None:
    """The witness's sure lines this reading lacks (`witness.lost`), or None when it cannot judge the page."""
    return witness.lost(witness.of(page), clean_reading(run.text))


# A table cell Haiku left as «...»: 61 of 96,161 pages read, names it could not make out on old scans (BO 3549).
_ELIDED = re.compile(r'\|\s*(?:\.{3}|…)\s*(?=\|)')
# The doubts a reader is told of (Z23): the page may lack lines.
SHORT = ('cut', 'letters', 'elided')


def doubt(page: Page, run: OcrRun | None, median: float) -> str:
    """Why a reading cannot stand as it is, or '' when it can. Since the second-archive-run review (29 Oct 2026) a
    reading with more letters than the witness stands (those held their lines), and one with fewer is in doubt only
    when the witness's sure lines agree it lacks some, where it has enough of them to tell."""
    if run is None:
        return 'unread'
    if 'max_tokens' in (run.stop_reason or ''):
        return 'cut'
    if run.variant.startswith('columns') and mostly_table(run.text):
        return 'table'                     # a table cut in two parts its labels from its amounts
    if _ELIDED.search(run.text):
        return 'elided'
    share = witness.ratio(page, clean_reading(run.text))
    if share is not None and share / median < 1 - BAND:
        lost = gap(page, run)
        if lost is None or lost['run'] >= witness.LOST:
            return 'letters'
    return ''


def second_readings(pages: list[Page], model: str, median: float, log=print) -> dict[int, str]:
    """Read once more each page whose readings are all in doubt. {page id: reason} of the pages that were sent."""
    whole, split, strips, why = second_plan(pages, model, median)
    send_second(whole, split, strips, why, model, log=log)
    return why


def send_second(whole: list[Page], split: list[Page], strips: list[tuple[Page, bool]], why: dict[int, str],
                model: str, log=print) -> None:
    if whole or split:
        log(f'second readings: {len(whole)} whole, {len(split)} by columns')
        ocr_readings_batch(whole, [], split, model, width=COLUMN_WIDTH, log=log)
    if strips:
        log(f'second readings: {len(strips)} in strips (cut at the token limit)')
        ocr_strips_batch(strips, model, width=COLUMN_WIDTH, log=log)


def second_plan(pages: list[Page], model: str, median: float
                ) -> tuple[list[Page], list[Page], list[tuple[Page, bool]], dict[int, str]]:
    """(whole, split, strips, {page id: reason}): the pages whose only reading is in doubt, and the other way to
    read each: by columns read whole, read whole now by columns; a reading cut at the token limit in strips, its
    columns' halves or its own, which write less each (Z16). A page whose reading left table cells out is not sent:
    neither another way nor strips gave them back on BO 3549. Strips did not give back what the letters missed
    either: on 200 pages of the first $100 they left 87 % of them as short of the witness as before."""
    whole, split, strips, why = [], [], [], {}
    for page in pages:
        runs = _runs(page, model)
        if not runs or any(r.variant.startswith('strips') for r in runs):
            continue
        reason = doubt(page, runs[0], median) if len(runs) == 1 else ''
        if reason == 'cut' and not runs[0].variant.startswith('turned'):
            columns = runs[0].variant.startswith('columns')
            strips.append((page, columns))
        elif reason in ('letters', 'table'):
            if not runs[0].variant.startswith('page'):
                whole.append(page)         # read by columns or turned: now whole
            elif render_columns(page, COLUMN_WIDTH) and witness.two_columns(witness.of(page)) is not False:
                split.append(page)         # read whole: now column by column, half the answer each
            else:
                continue                   # whole, and no clean split: nothing else to try
        else:
            continue
        why[page.pk] = reason
    return whole, split, strips, why


_PREFERRED = ('columns', 'strips', 'page', 'turned')


def choose(page: Page, runs: list[OcrRun], median: float) -> OcrRun:
    """The reading a page keeps: one that stands before one in doubt; among those standing, columns (the widest
    first), strips, the whole page; among those in doubt, the nearest to the issue's own share of letters."""
    def letters_off(r):
        share = witness.ratio(page, clean_reading(r.text))
        return abs(share / median - 1) if share is not None else 1.0

    def rank(r):
        if doubt(page, r, median):
            return (1, 0, 0, letters_off(r))
        kind = next((k for k, v in enumerate(_PREFERRED) if r.variant.startswith(v)), len(_PREFERRED))
        return (0, kind, -_width(r), 0)
    return min(runs, key=rank)


def keep(pages: list[Page], model: str, median: float) -> list[dict]:
    """Each page's text from the reading it keeps (`choose`); the pages still in doubt, for /corrections. A page whose
    reading may lack lines is measured `short` (Z23): the article on it says so and opens the page as printed."""
    from apps.sources.services.quality import measure, store

    doubts, changed, short = [], [], []
    for page in pages:
        runs = _runs(page, model)
        if not runs:
            continue
        best = choose(page, runs, median)
        if reason := doubt(page, best, median):
            doubts.append({'page': page.index, 'reason': reason, 'run': best.pk})
        text = clean_reading(best.text)
        if text != page.text:
            page.text, page.text_source = text, TextSource.OCR
            page.save(update_fields=['text', 'text_source'])
            changed.append(page)
        if reason in SHORT:
            short.append((page, reason))
        elif text == page.text and (page.quality or {}).get('reading') == 'short':
            changed.append(page)           # marked before by rules since lifted: measured again
    store(changed)
    for page, reason in short:
        page.quality = {**measure(page), 'reading': 'short', 'doubt': reason}
    Page.objects.bulk_update([p for p, _ in short], ['quality'], batch_size=500)
    return doubts


def read_issue_pages(issue, pages: list[Page], model: str, log=print) -> list[dict]:
    """The archive's whole reading of some of an issue's pages: one reading each, the witness's second readings,
    the best kept. Returns the pages still in doubt."""
    todo = unread(pages, model)
    if todo:
        read(todo, model, log=log)
    pages = list(Page.objects.filter(pk__in=[p.pk for p in pages]).select_related('document')
                 .prefetch_related('ocr_runs'))
    median = issue_ratio(list(issue.document.pages.prefetch_related('ocr_runs')), model)
    if second_readings(pages, model, median, log=log):
        pages = list(Page.objects.filter(pk__in=[p.pk for p in pages]).select_related('document')
                     .prefetch_related('ocr_runs'))
    doubts = keep(pages, model, median)
    write_doubts(issue, median, doubts)
    return doubts


def write_doubts(issue, median: float, doubts: list[dict]) -> None:
    path = root() / 'doubts' / f'{issue.key}.json'
    if doubts:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'median': median, 'pages': doubts}, ensure_ascii=False))
    elif path.exists():
        path.unlink()                      # read again since, and nothing left in doubt


# ── claims: several workers, one issue each at a time ──────────────────────────────────────────────────────────

def _state(phase: str) -> Path:
    path = root() / 'state' / phase
    path.mkdir(parents=True, exist_ok=True)
    return path


def done(phase: str, key: str) -> bool:
    return (_state(phase) / f'{key}.done').exists()


def mark(phase: str, key: str, what: str, body: str = '') -> None:
    (_state(phase) / f'{key}.{what}').write_text(body or time.strftime('%F %T'))


def _alive(claim: Path) -> bool:
    try:
        host, pid = claim.read_text().split()[:2]
    except (OSError, ValueError):
        return False
    if host != socket.gethostname():
        return True
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def claim(phase: str, key: str) -> bool:
    """Take an issue for this process; a claim left by a dead process is taken over."""
    path = _state(phase) / f'{key}.claim'
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _alive(path):
                return False
            path.unlink(missing_ok=True)
            continue
        with os.fdopen(fd, 'w') as f:
            f.write(f'{socket.gethostname()} {os.getpid()} {time.strftime("%F %T")}')
        return True
    return False


def release(phase: str, key: str) -> None:
    (_state(phase) / f'{key}.claim').unlink(missing_ok=True)


def stopped() -> str:
    """Why the run is to stop ('' when it goes on): a STOP file a person wrote, or the budget's."""
    for name in ('STOP', 'STOP_BUDGET'):
        path = root() / name
        if path.exists():
            return f'{name}: {path.read_text().strip()}'
    return ''
