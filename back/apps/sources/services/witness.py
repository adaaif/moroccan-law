"""Tesseract's reading of a scan, the witness of Haiku's (Z3 and Z9 of the Bulletin-to-1956 review, 27 Oct 2026).

A scan has no text layer to say whether a reading is whole, as 2019+ pages had. A Tesseract worker outside the app
reads every page at 150 dpi and writes CORPUS_DIR/tess/<file stem>.json.gz: each page's size and its lines, each
[left, top, right, bottom, text, confidence]. Its words are too loose to show (word F1 0.74–0.96 on 1956–2018
scans), but it rarely misses a whole line: its letters say how much a page holds, its line boxes whether the page
is in two columns, its first lines the running head with the folio.
"""
import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings

# Arabic letters only: no diacritics, no tatweel, no digits. Haiku writes the hamza forms Tesseract often drops,
# so the two counts differ by a factor the issue's own pages set (`median_ratio`), never by a fixed one.
_LETTER = re.compile(r'[ء-غف-ي]')
HEAD = 0.07              # the running head sits in the top 7 % of a page
CROSS = 0.03             # a line crosses the middle when it reaches 3 % of the width past it on both sides
# A contents line ends on the page it points to («… 1341»), or runs dots up to it.
_REF = re.compile(r'(?:\.{3,}|…{2,}|(?<![\d.])\d{1,5}\s*$|^\s*\d{1,5}(?![\d.]))')


def letters(text: str) -> int:
    return len(_LETTER.findall(text or ''))


def _file(document) -> Path | None:
    folder = Path(settings.CORPUS_DIR) / 'tess'
    stems = [Path(document.meta.get('archive', '')).stem, Path(document.path).stem]
    for stem in filter(None, stems):
        for name in (stem, stem[:-3] + '_Ar' if stem.lower().endswith('_ar') else stem):
            path = folder / f'{name}.json.gz'
            if path.exists():
                return path
    return None


@lru_cache(maxsize=48)
def _load(path: str, mtime: float) -> dict[int, dict]:
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return {p['i']: p for p in json.load(f)['pages']}


def of(page) -> dict | None:
    """The page as Tesseract read it ({'w', 'h', 'lines'}), or None when it has not been read."""
    path = _file(page.document)
    if path is None:
        return None
    return _load(str(path), path.stat().st_mtime).get(page.index)


def has(document) -> bool:
    return _file(document) is not None


def body(seen: dict) -> list[list]:
    return [line for line in seen['lines'] if line[1] >= HEAD * seen['h']]


def head_lines(seen: dict) -> list[str]:
    """The lines of the running head: the folio, the issue's number and its dates."""
    return [line[4] for line in seen['lines'] if line[1] <= 0.06 * seen['h']]


def page_letters(seen: dict) -> int:
    return sum(letters(line[4]) for line in body(seen))


def empty(seen: dict | None) -> bool:
    """Tesseract saw (almost) no letter on the page: a blank, a picture. False when it has not read the page."""
    return seen is not None and sum(letters(line[4]) for line in seen['lines']) < 20


def sideways(seen: dict | None) -> bool | None:
    """Whether the page is printed a quarter turn, from the orientation the worker asked of Tesseract when the page
    read badly upright (None: unknown, or Tesseract could not say)."""
    if seen is None or seen.get('rot') is None:
        return None
    return seen['rot'] in (90, 270)


def crossing_share(seen: dict, split: float = 0.5) -> float | None:
    """The share of the body's lines that run across the page's middle: near 0 on a page in two columns, high on a
    full-width one. None with too few lines to tell."""
    lines = [line for line in body(seen) if letters(line[4]) >= 6]
    if len(lines) < 8:
        return None
    w = seen['w'] or 1
    across = sum(1 for left, _, right, *_ in lines if left / w < split - CROSS and right / w > split + CROSS)
    return across / len(lines)


def two_columns(seen: dict | None) -> bool | None:
    """True when the page's lines keep to two columns, False when they run full width (K10's half-lines: BO 6286
    pp. 6544 and 6551, full-width pages cut as columns), None when Tesseract cannot tell."""
    if seen is None:
        return None
    share = crossing_share(seen)
    return None if share is None else share < 0.2


def looks_like_contents(seen: dict) -> bool:
    lines = [line for line in body(seen) if letters(line[4]) >= 8]
    return bool(lines) and sum(1 for line in lines if _REF.search(line[4])) / len(lines) >= 0.3


def contents_pages(document, cap: int = 8, default: int = 3) -> int:
    """How many first pages hold the cover and the contents: the cover, then each page that reads like contents
    (lines ending on the page they point to), up to `cap`. `default` when Tesseract has not read the issue."""
    pages = list(document.pages.order_by('index')[:cap])
    if not pages or not has(document):
        return min(default, len(pages))
    n = 1
    for page in pages[1:]:
        seen = of(page)
        if seen is None or not looks_like_contents(seen):
            break
        n += 1
    return max(n, min(2, len(pages)))      # the contents often run on to the second page's top


def _unofficial(line: str) -> bool:
    """«القسم الغير الرسمي» as Tesseract reads an old scan's heading: «الفسم الغير الرسمى», «القسم الفير الرسمي»,
    «القسم التي الرسبي»; never «القسم الرسمي», which has no word between."""
    words = re.findall(r'[\u0621-\u064a]+', line)
    if len(words) > 7:
        return False
    return any(w.endswith('سم') and 4 <= len(w) <= 6 and 3 <= len(x) <= 6 and 'رس' not in x and 'رس' in y
               for w, x, y in zip(words, words[1:], words[2:]))


def unofficial_from(document) -> int | None:
    """The page index where an issue before 1956 starts its non-official part («القسم الغير الرسمي»: land registration
    requests, companies, announcements), from Tesseract's lines: the last page that prints the heading, past the cover
    and contents (which name it too). None when Tesseract does not see it, or sees it only there."""
    if not has(document):
        return None
    last = None
    for page in document.pages.order_by('index'):
        seen = of(page)
        if seen and any(_unofficial(line[4]) for line in seen.get('lines', [])):
            last = page.index
    return last if last is not None and last >= contents_pages(document) else None


def ratio(page, text: str) -> float | None:
    """Letters Haiku read on the page over the letters Tesseract saw; None when the page holds too little text to
    compare (a cover, a picture, a blank)."""
    seen = of(page)
    if seen is None:
        return None
    expected = page_letters(seen)
    if expected < 150:
        return None
    return letters(text) / expected


def median_ratio(values: list[float], fallback: float = 1.15) -> float:
    """The issue's own ratio: its pages share a typeface and a scan, so most of them agree."""
    values = sorted(v for v in values if v)
    if len(values) < 5:
        return fallback
    return values[len(values) // 2]


# The line test (Z15 of the second-archive-run review, 29 Oct 2026). Tesseract's words are loose on old scans: it
# misspells half of them («المماك ة المغربي ة») and turns a French table into Arabic letters, so a test by words found
# 71 % of the pages it checked lacking 3 lines in a row where Haiku had read every one. A line counts here only when
# Tesseract is sure of it (confidence 60 or more, 12 letters or more), and it is in the reading when 60 % of its letter
# triplets are: 3 % of the readings kept then lack 3 lines in a row. It is a witness, never a reason to pay: with half
# a reading taken away it still saw only 54 % of the pages, legal Arabic repeating its words from line to line.
LOST = 3
_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي'})
_MARKS = re.compile(r'[\u064B-\u0652\u0670\u0640]')
SURE = 60


def folded(text: str) -> str:
    """The Arabic letters of a text in a row: hamzas, alif maqsura and ta marbuta folded, marks, tatweel and spaces gone."""
    return ''.join(_LETTER.findall(_MARKS.sub('', text or '').translate(_FOLD)))


def _triplets(letters_in_a_row: str) -> set[str]:
    return {letters_in_a_row[i:i + 3] for i in range(len(letters_in_a_row) - 2)}


def lost(seen: dict | None, text: str) -> dict | None:
    """The witness's sure lines the reading lacks: {'run': the most in a row, 'at': [top, bottom] of that run as
    shares of the page's height, 'lines': lines compared}. None without a witness or with fewer than five sure lines."""
    if seen is None:
        return None
    have = set()
    for line in (text or '').splitlines():
        have |= _triplets(folded(line))
    lines = [line for line in body(seen) if (line[5] or 0) >= SURE and len(folded(line[4])) >= 12]
    if len(lines) < 5:
        return None
    run, worst, start, at = 0, 0, 0, None
    h = seen['h'] or 1
    for n, line in enumerate(lines):
        t = _triplets(folded(line[4]))
        if len(t & have) >= 0.6 * len(t):
            run = 0
            continue
        run += 1
        if run == 1:
            start = n
        if run > worst:
            worst, at = run, [round(lines[start][1] / h, 3), round(line[3] / h, 3)]
    return {'run': worst, 'at': at, 'lines': len(lines)}
