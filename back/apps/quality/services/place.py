"""Where a doubtful word stands on its printed page, so a visitor can be shown the printed line and asked which of two
readings it prints («ساهم», /open-source).

The page's reading is a language model's, and Tesseract's word boxes read the same print badly: the two texts differ.
The words around the doubtful one (its context, as the reading has it) are looked for among the page's lines loosely:
letters folded, dots set aside, a letter or two of difference, a word Tesseract cut in two joined again; in order, over
one line or two consecutive lines of one column. A word found on many lines of the page (the «الساكن», «زنقة» and «محل
اقامته» of every notice) weighs less than one found on one or two. The best window is kept only when it holds enough of
the context and clearly more weight than any window elsewhere on the page: a formula printed again down the page must
not be placed on the wrong line. Anything less is «not found», and the word is simply not asked.

Then the strip a visitor sees: the line whole in height with the lines of print above and below, and in width about
seven words around the doubtful one, never the whole column, so its dots stay readable on a phone. When Tesseract read
the word itself (as one reading or the other, loosely) in a box of its own, its place in the strip is kept as the mark;
when only its line was found (and then two thirds of its context, not half), the strip is centred where the word should
stand by its rank, and has no mark.

A placement is kept as shares of the page: {'box': [left, top, right, bottom], 'line': [top, bottom] of the word's
own line, 'mark': [left, right] | None,
'size': [width, height] of the render the boxes were read on, 'found': context words found, 'of': words looked for,
'ahead': {'words', 'weight'} beyond the best window elsewhere}. `{}` is «looked for, not found»."""
import math
from itertools import pairwise
import re
from dataclasses import dataclass, field

from django.db.models import Count, Q
from rapidfuzz.distance import Levenshtein

from apps.quality.services.suspects import fold, shape

# A word's letters and digits only, the Persian forms Tesseract sometimes writes for Arabic ones folded back.
_KEEP = re.compile(r'[^ء-ي0-9A-Za-z]')
_TESSERACT = str.maketrans({'ی': 'ي', 'ک': 'ك', 'ہ': 'ه', 'ۃ': 'ه', 'ے': 'ي', 'ٹ': 'ت', 'ڈ': 'د'})
_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')

STRIP_WORDS = 3            # words kept on each side of the doubtful one
STRIP_MOST = 560           # the strip's width at most, in the render's pixels (1596 a page)
STRIP_LEAST = 320          # and at least: a short word alone gives the reader nothing to find it by
NEED = 0.5                 # the share of the context's words a window must hold
NEED_LEAST = 3             # and never fewer than this many
AHEAD_WORDS = 2            # words a window must hold beyond the best window elsewhere on the page,
AHEAD = 1.5                # or weight
COMMON = 2                 # a word found on more lines of the page than this weighs that many lines' share
DOUBTFUL = 1.5             # the doubtful word's own weight, found as either reading
UNMARKED = 2 / 3           # the share of the context a window must hold when the word's own reading is not in it


def norm(text: str) -> str:
    """A word as compared: marks and letter forms folded, digits Western, anything but letters and digits dropped."""
    return _KEEP.sub('', fold(text.translate(_TESSERACT).translate(_DIGITS)))


def alike(a: str, b: str, shape_a: str | None = None, shape_b: str | None = None) -> bool:
    """Two folded words that may be one word read twice: equal; of three or four letters, the same shape (the letters
    without their dots); from five letters, shapes a letter apart, two from eight letters. Never a word of letters and
    one with digits in it (a date's day Tesseract ran into its month). Their shapes may be given."""
    if a == b:
        return True
    if min(len(a), len(b)) < 3 or abs(len(a) - len(b)) > 2 or a.isalpha() != b.isalpha():
        return False
    longest = max(len(a), len(b))
    allowed = 0 if longest <= 4 else 1 if longest <= 7 else 2
    return Levenshtein.distance(shape_a or shape(a), shape_b or shape(b), score_cutoff=allowed) <= allowed


@dataclass
class Word:
    text: str
    left: int
    top: int
    right: int
    bottom: int


@dataclass
class Row:
    """A line of print in one column, its words in reading order."""
    words: list[Word]
    normed: list[str] = field(default_factory=list)

    @property
    def left(self) -> int:
        return min(w.left for w in self.words)

    @property
    def right(self) -> int:
        return max(w.right for w in self.words)

    @property
    def top(self) -> int:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> int:
        return max(w.bottom for w in self.words)


@dataclass
class Sheet:
    """A page's rows as Tesseract read them, read once for all the page's doubtful words."""
    rows: list[Row]
    size: tuple[int, int]
    below: list[int | None]
    line: int                  # the page's usual word height, in pixels
    _shapes: dict[str, str] | None = None

    def shapes(self) -> dict[str, str]:
        """Every token of the page and every two tokens side by side run together, with their shapes: worked out once
        for all the page's words."""
        if self._shapes is None:
            seen = {t for r in self.rows for t in r.normed if t}
            seen |= {a + b for r in self.rows for a, b in pairwise(r.normed)}
            self._shapes = {t: shape(t) for t in seen}
        return self._shapes


def page_size(tsv: str) -> tuple[int, int] | None:
    """The image's size, from the TSV's page row (level 1)."""
    for row in tsv.splitlines()[1:]:
        cells = row.split('\t')
        if len(cells) >= 10 and cells[0] == '1':
            return int(cells[8]), int(cells[9])
    return None


def sheet_of(tsv: str, rtl: bool = True) -> Sheet | None:
    """The page's rows: Tesseract's lines, one column each (a line it ran across a column's gutter is cut there, at a
    gap wider than three times the page's usual word height), top to bottom. None for a page without words."""
    from apps.sources.services.regions import word_rows

    size = page_size(tsv)
    lines: dict[tuple, list[Word]] = {}
    for key, left, top, width, height, text in word_rows(tsv):
        lines.setdefault(key, []).append(Word(text, left, top, left + width, top + height))
    if not lines or not size:
        return None
    heights = sorted(w.bottom - w.top for ws in lines.values() for w in ws)
    line = heights[len(heights) // 2]
    rows = []
    for ws in lines.values():
        ws.sort(key=lambda w: -w.right if rtl else w.left)
        run = [ws[0]]
        for prev, cur in pairwise(ws):
            if (prev.left - cur.right if rtl else cur.left - prev.right) > 3 * line:
                rows.append(Row(run))
                run = []
            run.append(cur)
        rows.append(Row(run))
    rows.sort(key=lambda r: (r.top, -r.right if rtl else r.left))
    for r in rows:
        r.normed = [norm(w.text) for w in r.words]
    return Sheet(rows, size, _below(rows), line)


def _below(rows: list[Row]) -> list[int | None]:
    """For each row, the next row down in its column (most of the narrower one's width shared), or None."""
    out: list[int | None] = []
    for i, r in enumerate(rows):
        nxt = None
        for j in range(i + 1, len(rows)):
            s = rows[j]
            if s.top <= r.top:
                continue
            shared = min(r.right, s.right) - max(r.left, s.left)
            if shared > 0.5 * min(r.right - r.left, s.right - s.left):
                nxt = j
                break
        out.append(nxt)
    return out


def _align(weights: list[float], matches: list[set[str]], merged: list[set[str]], normed: list[str],
           end: int | None = None):
    """The context words found in order among a window's tokens, the most weight first: a word on one token, a word
    Tesseract cut in two on two tokens side by side (never the last of one line and the first of the next: `end` is
    the first line's last token), two words it ran together on one (`merged[j]`: what words j and j+1 may be as one
    token). Gives (weight, how many words, {context word: its tokens})."""
    n, m = len(weights), len(normed)
    pairs = ['' if i == end else normed[i] + normed[i + 1] for i in range(m - 1)]
    best = [[0.0] * (m + 1) for _ in range(n + 2)]

    def steps(j: int, i: int):
        """The ways context word j may stand at token i: (weight, words taken, tokens taken)."""
        if normed[i] in matches[j]:
            yield weights[j], 1, 1
        if i + 1 < m and pairs[i] in matches[j]:
            yield weights[j], 1, 2
        if j + 1 < n and normed[i] in merged[j]:
            yield weights[j] + weights[j + 1], 2, 1

    for j in range(n - 1, -1, -1):
        for i in range(m - 1, -1, -1):
            best[j][i] = max([best[j + 1][i], best[j][i + 1],
                              *(w + best[j + dj][i + di] for w, dj, di in steps(j, i))])
    found: dict[int, list[int]] = {}
    j = i = 0
    while j < n and i < m:
        step = next(((dj, di) for w, dj, di in steps(j, i) if best[j][i] == w + best[j + dj][i + di]), None)
        if step:
            for jj in range(j, j + step[0]):
                found[jj] = list(range(i, i + step[1]))
            j, i = j + step[0], i + step[1]
        elif best[j][i] == best[j + 1][i]:
            j += 1
        else:
            i += 1
    return best[0][0], len(found), found


def where(context: str, word: str) -> int | None:
    """The doubtful word's place among its context's words (the context is four words, the word, four words; the one
    nearest the middle when it stands there twice), or None."""
    raw = context.split()
    at = [i for i, t in enumerate(raw) if t.strip('«»"\'.,،:;()') == word] or \
         [i for i, t in enumerate(raw) if norm(t) and norm(t) == norm(word)]
    return min(at, key=lambda i: abs(i - len(raw) / 2)) if at else None


def find(sheet: Sheet, context: str, word: str, suggestion: str) -> dict:
    """The word's placement on the page (see the module's docstring), or {} when it is not clearly found."""
    k = where(context, word)
    if k is None or not sheet.rows:
        return {}
    ctx = [norm(t) for t in context.split()]
    readings = [r for r in (norm(word), norm(suggestion)) if r]
    rows = sheet.rows

    # Which of the page's tokens (and pairs of tokens side by side) each context word may be, and on how many rows.
    seen = sheet.shapes()

    def like(wanted: list[str]) -> set[str]:
        return {t for w in wanted for t in seen if alike(w, t, shape(w), seen[t])}

    matches = [like(readings if j == k else [c] if len(c) >= 2 else []) for j, c in enumerate(ctx)]
    merged = [like([c + ctx[j + 1]] if j + 1 < len(ctx) and k not in (j, j + 1) and min(len(c), len(ctx[j + 1])) >= 2
                   else []) for j, c in enumerate(ctx)]
    lines_with = [{x for x, r in enumerate(rows) if any(t in matches[j] for t in r.normed)
                   or any(a + b in matches[j] for a, b in pairwise(r.normed))} for j in range(len(ctx))]
    weights = [min(1.0, COMMON / max(1, len(on))) * (DOUBTFUL if j == k else 1) for j, on in enumerate(lines_with)]
    looked = sum(1 for j, c in enumerate(ctx) if j == k or len(c) >= 2)
    need = max(NEED_LEAST, math.ceil(NEED * looked))

    hit = set().union(*lines_with) | {x for x, r in enumerate(rows) if any(t in m for m in merged for t in r.normed)}
    scored = []          # (weight, how many, rows in the window, alignment)
    for r in sorted(hit | {x for x, b in enumerate(sheet.below) if b in hit}):
        for window in ((r,), (r, sheet.below[r])):
            if window[-1] is None or not hit & set(window):
                continue
            normed = [t for x in window for t in rows[x].normed]
            weight, count, found = _align(weights, matches, merged, normed, len(rows[r].normed) - 1)
            if count:
                scored.append((weight, count, window, found))
    if not scored:
        return {}
    # The most weight; between equals, the most words, then one row rather than two. It must hold enough of the
    # context, and clearly more of it than any window elsewhere: two words more, or the weight of a word and a half.
    weight, count, window, found = max(scored, key=lambda s: (s[0], s[1], -len(s[2])))
    others = [s for s in scored if not set(s[2]) & set(window)]
    ahead = count - max((s[1] for s in others), default=0)
    heavier = weight - max((s[0] for s in others), default=0)
    if count < need or (ahead < AHEAD_WORDS and heavier < AHEAD - 1e-6):
        return {}

    tokens = [w for x in window for w in rows[x].words]
    # A line where the word's own reading was not recognised holds more of its context: the page's formula with
    # another number in it (a surface, a date) is otherwise found in its place.
    if k not in found and count < math.ceil(UNMARKED * looked):
        return {}
    # The mark only where Tesseract read the doubtful word on its own (whole, or cut in two), in a box of its own.
    if k in found and not (found.get(k - 1) == found[k] or found.get(k + 1) == found[k]):
        at_token, marked = found[k][0], [tokens[i] for i in found[k]]
    else:
        at_token, marked = (found[k][0] if k in found else _by_rank(found, k, len(tokens))), None
    if at_token is None:             # by its rank the word stands before or after the window: its line is not known
        return {}
    row = next(x for x in window if tokens[at_token] in rows[x].words)
    if marked and _overlaps(marked, rows[row].words):
        marked = None
    box, line = _strip(sheet, row, rows[row].words.index(tokens[at_token]), marked)
    width, height = sheet.size
    place = {'box': [round(box[0] / width, 5), round(box[1] / height, 5), round(box[2] / width, 5),
                     round(box[3] / height, 5)],
             'line': [round(line[0] / height, 5), round(line[1] / height, 5)],
             'mark': None, 'size': [width, height], 'found': count, 'of': looked,
             'ahead': {'words': ahead, 'weight': round(heavier, 2)}}
    if marked:
        place['mark'] = [round(min(w.left for w in marked) / width, 5), round(max(w.right for w in marked) / width, 5)]
    return place


def _overlaps(marked: list[Word], words: list[Word]) -> bool:
    """Whether Tesseract's box for the word runs over a neighbour's (a third of the narrower one or more): a box that
    covers other words marks them too."""
    for w in marked:
        for o in words:
            if o not in marked and min(w.right, o.right) - max(w.left, o.left) > min(w.right - w.left,
                                                                                   o.right - o.left) / 3:
                return True
    return False


def _by_rank(found: dict[int, list[int]], k: int, m: int) -> int | None:
    """Where the word should stand among the window's `m` tokens when Tesseract's reading of it was not recognised: as
    many tokens past the context word found before it, or before the one found after it. None when that falls outside
    the window: the word then stands on a line the window does not hold."""
    p = max((j for j in found if j < k), default=None)
    q = min((j for j in found if j > k), default=None)
    if p is None:
        guess = found[q][0] - (q - k)
    else:
        guess = found[p][-1] + (k - p)
        if q is not None and guess >= found[q][0]:     # fewer tokens between the two than words: the nearer one
            guess = found[p][-1] if k - p <= q - k else found[q][0]
    return guess if 0 <= guess < m else None


def _strip(sheet: Sheet, r: int, i: int, marked: list[Word] | None) -> tuple[tuple[int, int, int, int], tuple[int, int]]:
    """The strip around word `i` of row `r`, in pixels: about seven words wide, centred on the word, slid inside its
    column where it can be; the line whole in height with the lines above and below it in its column. With it, the
    top and bottom of the word's own line: a strip holds three lines, and the reader is shown which."""
    rows, (width, height) = sheet.rows, sheet.size
    row = rows[r]
    near = row.words[max(0, i - STRIP_WORDS):i + STRIP_WORDS + 1]
    target = marked or [row.words[i]]
    left, right = min(w.left for w in target), max(w.right for w in target)
    centre = (left + right) / 2
    half = max(centre - min(w.left for w in near), max(w.right for w in near) - centre) + 8
    half = min(max(half, STRIP_LEAST / 2), STRIP_MOST / 2)
    half = max(half, (right - left) / 2 + 24)
    above = next((j for j, b in enumerate(sheet.below) if b == r), None)
    under = sheet.below[r]
    column = [rows[j] for j in (above, r, under) if j is not None]
    col_left, col_right = min(c.left for c in column) - 12, max(c.right for c in column) + 12
    x0, x1 = centre - half, centre + half
    if x1 - x0 <= col_right - col_left:            # slid inside the column, the word kept inside the strip
        shift = max(0, col_left - x0) - max(0, x1 - col_right)
        shift = max(min(shift, left - 16 - x0), right + 16 - x1)
        x0, x1 = x0 + shift, x1 + shift
    x0, x1 = max(0, round(x0)), min(width, round(x1))
    # In height: the line as the words near the word stand (a line Tesseract merged with the next is taller than one),
    # and the lines of print above and below it, a line and a half of the page's usual height at most.
    top, bottom = min(w.top for w in near), max(w.bottom for w in near)
    if bottom - top > 2 * sheet.line:              # Tesseract ran two lines of print into one: the word's own height
        top, bottom = min(w.top for w in target), max(w.bottom for w in target)
    reach = round(1.6 * sheet.line)
    up = top - min(reach, max(8, top - rows[above].top)) if above is not None and rows[above].bottom < top + 8 \
        else top - reach
    down = bottom + min(reach, max(8, rows[under].bottom - bottom)) if under is not None and rows[under].top > bottom - 8 \
        else bottom + reach
    return (x0, max(0, up), x1, min(height, down)), (top, bottom)


# ── The pages ───────────────────────────────────────────────────────────────────────────────────────────────────────

SECOND_READING = ('reread', 'copies')       # signals of two real readings of the page, asked before the rare words


def place_page(page) -> int:
    """Looks for every askable word of `page` not looked for yet, when the page's word boxes are read (its document
    selected with it): one query to read them, one to write their places. Gives how many were placed."""
    from apps.quality.models import Suspect
    from apps.quality.services.words import askable
    from apps.sources.services import regions

    path = regions.boxes_path(page)
    if not path.exists():
        return 0
    suspects = list(askable().filter(page=page, place__isnull=True).only('pk', 'word', 'suggestion', 'context'))
    if not suspects:
        return 0
    sheet = sheet_of(path.read_text(), rtl=page.document.language != 'fr')
    for s in suspects:
        s.place = find(sheet, s.context, s.word, s.suggestion) if sheet else {}
    Suspect.objects.bulk_update(suspects, ['place'])
    return sum(1 for s in suspects if s.place)


def waiting(signal: str | None = None) -> list:
    """The pages holding askable words not looked for yet, their documents with them: those whose boxes are read
    first (no Tesseract: fast), then the others, the pages of a second reading before the rare words', the most words
    first. Two queries, and the pages by chunks."""
    from apps.quality.services.words import askable
    from apps.sources.models import Page
    from apps.sources.services import regions

    rows = askable().filter(place__isnull=True)
    if signal:
        rows = rows.filter(signal=signal)
    counts = {r['page']: r for r in rows.values('page').annotate(
        n=Count('pk'), second=Count('pk', filter=Q(signal__in=SECOND_READING))).order_by()}
    ids = sorted(counts)
    # Without their texts: what rendering, reading and placing a page need.
    pages = [p for i in range(0, len(ids), 5000)
             for p in Page.objects.select_related('document').filter(pk__in=ids[i:i + 5000])
             .only('index', 'document__sha256', 'document__path', 'document__language')]
    return sorted(pages, key=lambda p: (not regions.read_yet(p), not counts[p.pk]['second'], -counts[p.pk]['n'], p.pk))


def run(stop: float, limit: int | None = None, signal: str | None = None) -> dict:
    """Places the waiting pages' words until `stop` (time.monotonic()): a page read already at once, another read
    first (`regions.lines_of`: the page rendered and Tesseract run once, one page at a time), at most `limit` of those.
    A page whose file is not on this machine is passed over. Gives {'read', 'pages', 'missing', 'placed'}: pages read
    with Tesseract, pages whose words were looked for, pages passed over, words placed."""
    import time

    from django.core.exceptions import SuspiciousFileOperation

    from apps.sources.services import regions
    from apps.sources.services.ingest import corpus_path

    done = {'read': 0, 'pages': 0, 'missing': 0, 'placed': 0}
    for page in waiting(signal):
        if time.monotonic() > stop:
            break
        if not regions.read_yet(page):
            if limit is not None and done['read'] >= limit:
                break
            try:
                here = corpus_path(page.document).exists()
            except SuspiciousFileOperation:      # a path that leaves the corpus folder: not here either
                here = False
            if not here:
                done['missing'] += 1
                continue
            regions.lines_of(page)
            if not regions.read_yet(page):        # Tesseract missing, or a page it could not finish: asked again later
                continue
            done['read'] += 1
        done['placed'] += place_page(page)
        done['pages'] += 1
    return done
