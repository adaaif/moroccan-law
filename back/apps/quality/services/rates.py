"""How often an old reading is wrong (FX8 of the mended-Bulletin review, 2 Nov 2026), measured three ways, none paid:

- `votes`: a cover read three times or more (BO 610's 28 copies, BO 304's 6): each reading set beside what most of them
  read (the vote, a run of its own since FX3). The vote is near the page; a reading's distance from it is its error.
- `pairs`: a cover read twice (1914–1925): the two readings set side by side. Two readings that each err on p words
  in a hundred disagree on about 2p: half the disagreement is one reading's error.
- `gold`: passages read word for word against their printed pages (the Bulletin stories, reading_gold.yaml), each set
  beside the page's reading as the model gave it.

Words are folded as search folds them (hamza, ى, ة, marks): an error is a word search would not find. Each measure
gives (errors, words) by period."""
import difflib
import re
from collections import defaultdict
from pathlib import Path

import yaml

from apps.sources.models import OcrRun, Page

_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي'})
_WORD = re.compile(r'[0-9ء-ي]+')
GOLD = Path(__file__).resolve().parent.parent / 'data' / 'reading_gold.yaml'


def words(text: str) -> list[str]:
    return _WORD.findall(re.sub(r'[ً-ْـ]', '', text or '').translate(_FOLD))


def errors(ref: list[str], hyp: list[str], edges: bool = True) -> int:
    """Words to change, add or drop to make `hyp` read `ref` (a word-level edit distance, as the diff counts it).
    `edges=False`: words `hyp` has before the passage begins or after it ends are not counted (a window cut wide)."""
    out = 0
    ops = difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_opcodes()
    for k, (op, a1, a2, b1, b2) in enumerate(ops):
        if op == 'equal':
            continue
        if not edges and op == 'insert' and ((k == 0 and a1 == 0) or (k == len(ops) - 1 and a1 == len(ref))):
            continue
        out += max(a2 - a1, b2 - b1)
    return out


def period(year: int) -> str:
    return '1913–1925' if year <= 1925 else '1926–1955' if year <= 1955 else '1956–1999' if year <= 1999 else '2000–2026'


def _runs(page: Page) -> tuple[OcrRun | None, list[OcrRun]]:
    """The page's vote and its readings, each as readers see it (the model's remarks out: a run keeps them)."""
    from apps.sources.services.issue import clean_reading
    runs = list(page.ocr_runs.exclude(text=''))
    for r in runs:
        r.text = clean_reading(r.text)
    vote = next((r for r in runs if r.engine == 'vote'), None)
    return vote, [r for r in runs if r.engine != 'vote' and not r.engine.startswith('tesseract')]


def median(values: list[float]) -> float | None:
    values = sorted(values)
    return values[len(values) // 2] if values else None


def votes() -> dict[str, tuple[int, int, float | None]]:
    """Each reading of a page read three times or more, beside the vote: (errors, words, the median page's rate).
    A page read in another order (a column first) counts many words wrong: the median page leaves it aside."""
    out = defaultdict(lambda: [0, 0, []])
    pages = Page.objects.filter(ocr_runs__engine='vote', ocr_runs__variant__startswith='vote of').distinct()
    for page in pages.select_related('document__issue'):
        vote, others = _runs(page)
        ref = words(vote.text)
        got = out[period(page.document.issue.date.year)]
        for run in others:
            e = errors(ref, words(run.text))
            got[0] += e
            got[1] += len(ref)
            if ref:
                got[2].append(e / len(ref))
    return {k: (v[0], v[1], median(v[2])) for k, v in out.items()}


def pairs() -> dict[str, tuple[int, int, float | None]]:
    """Half the disagreement of the two readings of a page read twice (one reading's share): (errors, words, the
    median page's rate)."""
    out = defaultdict(lambda: [0, 0, []])
    pages = Page.objects.filter(ocr_runs__engine='vote', ocr_runs__variant='kept of 2 readings').distinct()
    for page in pages.select_related('document__issue'):
        _, others = _runs(page)
        if len(others) < 2:
            continue
        a, b = words(others[0].text), words(others[1].text)
        got = out[period(page.document.issue.date.year)]
        e = errors(a, b) / 2
        got[0] += e
        got[1] += len(a)
        if a:
            got[2].append(e / len(a))
    return {k: (round(v[0]), v[1], median(v[2])) for k, v in out.items()}


def _window(page_words: list[str], passage: list[str]) -> list[str]:
    """The stretch of the page's words that reads most like the passage."""
    if not page_words or not passage:
        return []
    best, at = 0, 0
    span, wanted = len(passage), set(passage)
    for start in range(max(1, len(page_words) - span + 1)):
        hits = sum(1 for w in page_words[start:start + span] if w in wanted)
        if hits > best:
            best, at = hits, start
    return page_words[max(0, at - 2):at + span + 2]


def gold(path: Path = GOLD) -> dict[str, tuple[int, int]]:
    """Each passage read against its printed page, beside the page's reading as the model gave it (its own run, not
    the page as corrected since)."""
    from apps.sources.models import Issue
    out = defaultdict(lambda: [0, 0])
    for p in yaml.safe_load(path.read_text(encoding='utf-8'))['passages']:
        issue = Issue.objects.filter(edition='general_ar', number=p['issue'], suffix='', copy_of__isnull=True).first()
        page = issue and Page.objects.filter(document=issue.document_id, printed_number=p['page']).first()
        if not page:
            continue
        _, runs = _runs(page)
        own = [r for r in runs if not r.variant.startswith('copy ')] or runs
        reading = own[-1].text if own else page.text
        ref = words(p['words'])
        got = out[period(issue.date.year)]
        got[0] += errors(ref, _window(words(reading), ref), edges=False)
        got[1] += len(ref)
    return {k: (v[0], v[1], None) for k, v in out.items()}
