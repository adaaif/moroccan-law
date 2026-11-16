"""Where an article stands on its printed page (U14 of the Moroccan-design review): its heading's line («المادة 49»,
«الفصل 618-3», «Article 12») found among Tesseract's word boxes of the page as rendered, down to the next heading in
the same column (an article, or a part: «الباب الثاني»), or the column's last line. The viewer opens on that place with
a band around it. Free (a second of Tesseract a page, its boxes kept beside the page's image); a heading not found gives
nothing, and the page shows whole as before.

Tesseract never runs inside a request (N13 of the read-and-trusted review, 27 Oct 2026: a page can take most of a
minute, holding a worker all along): the endpoint answers from the boxes already read, or says «not yet»
and puts the page on the list `read_regions` reads at night, one page at a time, nice 19."""
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from apps.sources.models import Page
from apps.sources.services.render import OCR_WIDTH, render_page

ARTICLE_WORDS = {'الماده', 'ماده', 'الفصل', 'فصل', 'article', 'art'}
PART_WORDS = {'الباب', 'القسم', 'الفرع', 'الكتاب', 'الجزء', 'titre', 'chapitre', 'section', 'livre'}
ORDINALS = {'الاولي': '1', 'الاول': '1', 'الثانيه': '2', 'الثاني': '2', 'الثالثه': '3', 'الثالث': '3', 'الرابعه': '4',
            'الرابع': '4', 'الخامسه': '5', 'الخامس': '5', 'السادسه': '6', 'السادس': '6', 'السابعه': '7', 'السابع': '7',
            'الثامنه': '8', 'الثامن': '8', 'التاسعه': '9', 'التاسع': '9', 'العاشره': '10', 'العاشر': '10',
            'فريده': 'unique', 'premier': '1', 'unique': 'unique'}
INDIC = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')


def fold(word: str) -> str:
    w = re.sub(r'[ً-ْـ]', '', word.translate(INDIC)).lower().strip('.:-–—()«»"\'،,')
    return w.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه').replace('ى', 'ي').replace('er', '')


def number_of(label: str) -> str:
    """«المادة 49» → «49»; «الفصل 618-3» → «618-3»; «المادة الأولى» → «1»; «مادة فريدة» → «unique»."""
    words = [fold(w) for w in label.split()]
    digits = [w for w in words if re.fullmatch(r'\d+(?:-\d+)?', w)]
    if digits:
        return digits[0]
    return next((ORDINALS[w] for w in words if w in ORDINALS), '')


@dataclass
class Line:
    words: list[str]
    left: int
    top: int
    right: int
    bottom: int

    @property
    def centre(self) -> float:
        return (self.left + self.right) / 2


def boxes_path(page: Page) -> Path:
    """Where the page's word boxes are kept: beside its render, whether or not either exists yet."""
    return Path(settings.CORPUS_DIR) / 'renders' / page.document.sha256[:16] / f'{page.index:04d}-{OCR_WIDTH}.tsv'


def read_yet(page: Page) -> bool:
    return boxes_path(page).exists()


def wanted_path() -> Path:
    return Path(settings.CORPUS_DIR) / 'reports' / 'regions-wanted.txt'


def want(page: Page) -> None:
    """The page asked for and not read yet, for tonight's `read_regions` (one line a request; appends are atomic)."""
    path = wanted_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        f.write(f'{page.document_id} {page.index}\n')


def lines_of(page: Page) -> tuple[list[Line], tuple[int, int]]:
    """The page's lines with their boxes, and the image's size; Tesseract's TSV is kept beside the image."""
    image = render_page(page)
    tsv = image.with_suffix('.tsv')
    if not tsv.exists():
        lang = 'fra' if page.document.language == 'fr' else 'ara'
        try:
            out = subprocess.run(['tesseract', str(image), 'stdout', '-l', lang, '--psm', '3', 'tsv'], capture_output=True,
                                 text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):     # no Tesseract here, or a page it cannot finish: no band
            return [], _size(image)
        tmp = tsv.with_suffix('.tsv.tmp')
        tmp.write_text(out.stdout)
        tmp.replace(tsv)
    return parse(tsv.read_text()), _size(image)


def _size(image: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(image) as im:
        return im.size


def word_rows(tsv: str):
    """Tesseract's words, its level-5 rows, in its order: (line key, left, top, width, height, text), empty ones left
    out. The line key is (block, paragraph, line)."""
    for row in tsv.splitlines()[1:]:
        cells = row.split('\t')
        if len(cells) < 12 or cells[0] != '5' or not cells[11].strip():
            continue
        left, top, width, height = (int(c) for c in cells[6:10])
        yield (cells[2], cells[3], cells[4]), left, top, width, height, cells[11]


def parse(tsv: str) -> list[Line]:
    by_line: dict[tuple, Line] = {}
    for key, left, top, width, height, text in word_rows(tsv):
        ln = by_line.get(key)
        if ln is None:
            by_line[key] = Line([text], left, top, left + width, top + height)
        else:
            ln.words.append(text)
            ln.left, ln.top = min(ln.left, left), min(ln.top, top)
            ln.right, ln.bottom = max(ln.right, left + width), max(ln.bottom, top + height)
    return sorted(by_line.values(), key=lambda ln: ln.top)


def heading(line: Line) -> str | None:
    """'article' for a line that is an article's heading, 'part' for a division's, else None."""
    words = [fold(w) for w in line.words]
    if len(words) <= 5 and any(w in ARTICLE_WORDS for w in words):
        return 'article'
    if len(words) <= 7 and words and (words[0] in PART_WORDS or words[-1] in PART_WORDS):
        return 'part'
    return None


def region(page: Page, label: str) -> dict | None:
    """{top, bottom, left, right} as shares of the page for the article `label` that starts on it, or None."""
    if not number_of(label):
        return None
    lines, size = lines_of(page)
    return locate(lines, size, label)


def guess(page: Page, label: str) -> dict | None:
    """Until tonight's read (HM39 of the hard-moment review): the article's place from the witness, Tesseract's lines
    of the archive's scans at 150 dpi (services/witness.py), read already and kept beside the issue. Its words are loose
    but its line boxes are sound: the heading found among them frames the article's column, as the boxes would. None for a
    page the witness never read (the 2019+ issues), or a heading it misread."""
    from apps.sources.services import witness

    seen = witness.of(page) if number_of(label) else None
    if not seen:
        return None
    lines = [Line(str(text).split(), int(left), int(top), int(right), int(bottom))
             for left, top, right, bottom, text, *_ in seen['lines'] if str(text).strip()]
    return locate(sorted(lines, key=lambda ln: ln.top), (seen['w'], seen['h']), label)


def locate(lines: list[Line], size: tuple[int, int], label: str) -> dict | None:
    """The article `label`'s place among a page's lines (`size` the page's, in the lines' pixels)."""
    wanted = number_of(label)
    if not wanted or not lines:
        return None
    width, height = size
    body_left, body_right = min(ln.left for ln in lines), max(ln.right for ln in lines)
    mid = (body_left + body_right) / 2
    # Two columns when most lines stop short of the middle (the BO's general section).
    columns = sum(1 for ln in lines if ln.right < mid + 20 or ln.left > mid - 20) > 0.6 * len(lines)
    heads = [ln for ln in lines if heading(ln) == 'article']
    start = next((ln for ln in heads if wanted in _numbers(ln)), None)
    if start is None:
        start = _misread(heads, wanted, mid if columns else None)
    if start is None:
        return None
    side = (lambda ln: (ln.centre > mid) == (start.centre > mid)) if columns else (lambda ln: True)
    column = [ln for ln in lines if side(ln)]
    after = [ln for ln in column if ln.top > start.bottom]
    end = next((ln for ln in after if heading(ln)), None)
    inside = [ln for ln in after if end is None or ln.top < end.top]
    bottom = max([start.bottom, *(ln.bottom for ln in inside)])
    left = min([start.left, *(ln.left for ln in inside)]) if columns else body_left
    right = max([start.right, *(ln.right for ln in inside)]) if columns else body_right
    pad = 12
    return {'top': round(max(0, start.top - pad) / height, 4), 'bottom': round(min(height, bottom + pad) / height, 4),
            'left': round(max(0, left - pad) / width, 4), 'right': round(min(width, right + pad) / width, 4)}


def _numbers(line: Line) -> set[str]:
    """The number a heading line names, as a set of one; none when it names two (the witness's «1 الفصل. 23.», a stray
    «1» on the line of «الفصل 13», framed art. 13 for «الفصل الأول»)."""
    words = [fold(w) for w in line.words]
    found = [w for w in words if re.fullmatch(r'\d+(?:-\d+)?', w)] + [ORDINALS[w] for w in words if w in ORDINALS]
    return set(found) if len(found) == 1 else set()


def _misread(heads: list[Line], wanted: str, mid: float | None) -> Line | None:
    """A heading whose number was misread («الفصل <.» for «الفصل 1» in the witness of BO 2622 p. 176): the one right
    above the next article's heading in its column, or right below the one before's; None when neither is read."""
    if not wanted.isdigit():
        return None
    same = (lambda a, b: (a.centre > mid) == (b.centre > mid)) if mid is not None else (lambda a, b: True)
    unread = [ln for ln in heads if not any(w.isdigit() or w in ORDINALS for w in map(fold, ln.words))]
    for near, above in ((str(int(wanted) + 1), True), (str(int(wanted) - 1), False)):
        anchor = next((ln for ln in heads if near in _numbers(ln)), None)
        if anchor is None:
            continue
        side = [ln for ln in heads if same(ln, anchor) and (ln.top < anchor.top if above else ln.top > anchor.top)]
        closest = max(side, key=lambda ln: ln.top) if above and side else min(side, key=lambda ln: ln.top) if side else None
        if closest is not None and closest in unread:
            return closest
    return None
