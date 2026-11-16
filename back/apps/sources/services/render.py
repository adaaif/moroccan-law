"""Page images for OCR, cached under CORPUS_DIR/renders; and for reading (`for_reading`)."""
import os
import secrets
from functools import lru_cache
from pathlib import Path

import pypdfium2 as pdfium
from django.conf import settings

from apps.sources.models import Page
from apps.sources.services.ingest import corpus_path

# Claude bills an image by 28-pixel tiles and caps it at 4,784 tiles: 1,596 px wide keeps an A4 page
# (57 x 81 tiles) under the cap, so nothing is downscaled on the way in.
OCR_WIDTH = 1596


def _render(page: Page, width: int):
    pdf = pdfium.PdfDocument(str(corpus_path(page.document)))
    try:
        pdf_page = pdf[page.index]
        return pdf_page.render(scale=width / pdf_page.get_width(), grayscale=True).to_pil()
    finally:
        pdf.close()


def render_page(page: Page, width: int = OCR_WIDTH) -> Path:
    """The page as a grayscale PNG `width` pixels wide, kept under CORPUS_DIR/renders. PNGs are saved at zlib's
    default level: `optimize` made them 8 % smaller at five times the CPU, the issue runs' main cost."""
    out = Path(settings.CORPUS_DIR) / 'renders' / page.document.sha256[:16] / f'{page.index:04d}-{width}.png'
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    # Written whole, then renamed: a reader or a batch that asked for the same page while it was written read half a PNG.
    part = out.with_name(f'.{out.stem}.{secrets.token_hex(4)}.png')
    try:
        _render(page, width).save(part)
        part.replace(out)
    finally:
        part.unlink(missing_ok=True)
    return out


WEB_WIDTHS = ('900', '1600')


def web_image(page: Page, width: int) -> Path:
    """The page for reading (U16 of the Moroccan-design review): WebP, `width` wide, from the OCR render, kept beside
    it. Quality 60 keeps the print's small type sharp; 900 px is a phone, 1600 a desk or a zoom."""
    from PIL import Image

    out = Path(settings.CORPUS_DIR) / 'renders' / page.document.sha256[:16] / f'{page.index:04d}-{width}.webp'
    if out.exists():
        return out
    source = render_page(page)
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as im:
        # Its own name for each process: a deploy's draw_pages and a reader opening the same page wrote one file (29 Oct).
        tmp = out.with_name(f'{out.stem}.{os.getpid()}.tmp.webp')
        _for_web(im, width).save(tmp, 'WEBP', quality=60, method=4)
        tmp.replace(out)
    return out


def _for_web(image, width: int):
    """The page in grey, `width` wide at most."""
    from PIL import Image

    small = image.convert('L')
    if small.width > width:
        small = small.resize((width, round(small.height * width / small.width)), Image.Resampling.LANCZOS)
    return small


def for_reading(page: Page, width: int | None, request=None) -> Path:
    """The page as a reader asks for it: WebP `width` wide (900 or 1600), or the PNG at the OCR width. The file drawn
    ahead under CORPUS_DIR/renders when there is one (draw_pages, the pipeline's own); else one drawn now, under the
    drawing limits (config/drawing.py), into CORPUS_DIR/drawn, whose size is kept. Nothing more is written under
    renders for a reader: a reader's page had left its PNG there for good, two hundred kilobytes each. Raises Busy."""
    from PIL import Image

    from config import drawing

    name = f'{page.index:04d}-{width}.webp' if width else f'{page.index:04d}-{OCR_WIDTH}.png'
    folder = Path(settings.CORPUS_DIR) / 'renders' / page.document.sha256[:16]
    if (folder / name).exists():
        return folder / name

    def draw(part: Path) -> None:
        drawn = folder / f'{page.index:04d}-{OCR_WIDTH}.png'
        with (Image.open(drawn) if drawn.exists() else _render(page, OCR_WIDTH)) as image:
            if width:
                _for_web(image, width).save(part, 'WEBP', quality=60, method=4)
            else:
                image.save(part, 'PNG')
    return drawing.picture(Path(settings.CORPUS_DIR) / 'drawn' / f'{page.document.sha256[:16]}-{name}', draw, request)


def _ink(image, box, size):
    """Mean ink (0–1) of `box`, squeezed to `size`: one value per column (size=(w, 1)) or per row."""
    from PIL import Image

    strip = image.crop(box).point(lambda v: 255 if v < 128 else 0).resize(size, Image.Resampling.BOX)
    return [v / 255 for v in strip.get_flattened_data()]


def is_sideways(page: Page) -> bool:
    """A page printed turned a quarter (a landscape table). A born-digital page says so itself: most of its
    characters are set at a quarter turn. A scan is asked of Tesseract's orientation detection, which was right on
    every page tried; the ink texture used before mistook an upright table's dotted leaders for turned lines
    (15 errors in 275 pages, even smoothed)."""
    if page.layer_letters >= 200:
        return _turned_characters(page.document.sha256, str(corpus_path(page.document)), page.index)
    from apps.sources.services import witness   # the archive's scans: the worker already asked Tesseract, at night
    turned = witness.sideways(witness.of(page))
    if turned is not None:
        return turned
    return _osd_rotation(str(render_page(page))) in (90, 270)


@lru_cache(maxsize=8192)
def _osd_rotation(image: str) -> int:
    """Tesseract's «Rotate: N»: the clockwise turn that makes the page upright (0 when it is, or when unsure)."""
    import re
    import subprocess

    result = subprocess.run(['tesseract', image, '-', '--psm', '0'], capture_output=True, text=True)
    m = re.search(r'Rotate:\s*(\d+)', result.stdout + result.stderr)
    return int(m.group(1)) if m else 0


@lru_cache(maxsize=4096)
def _turned_characters(sha: str, path: str, index: int) -> bool:
    import math

    import pypdfium2.raw as pdfium_c

    pdf = pdfium.PdfDocument(path)
    try:
        textpage = pdf[index].get_textpage()
        turned = upright = 0
        for i in range(pdfium_c.FPDFText_CountChars(textpage.raw)):
            if pdfium_c.FPDFText_GetUnicode(textpage.raw, i) < 0x30:
                continue
            angle = pdfium_c.FPDFText_GetCharAngle(textpage.raw, i) % math.pi   # upside down counts as upright
            if min(angle, math.pi - angle) < 0.3:
                upright += 1
            else:
                turned += 1
        return turned > upright
    finally:
        pdf.close()


def render_turned(page: Page) -> Path:
    """A sideways page turned upright. A born-digital page is turned a quarter counter-clockwise (its top on the
    right, as the BO prints landscape tables); a scan the way Tesseract says."""
    from PIL import Image

    src = render_page(page)
    out = src.with_name(f'{page.index:04d}-{OCR_WIDTH}-turned.png')
    if not out.exists():
        angle = 90 if page.layer_letters >= 200 else (360 - _osd_rotation(str(src))) % 360 or 90
        Image.open(src).rotate(angle, expand=True).save(out)
    return out


def render_columns(page: Page, width: int = 2 * OCR_WIDTH, *, upright: bool = False) -> list[Path] | None:
    """The page body cut at its column rule, at twice the OCR width so each column keeps full detail;
    reading order first (right column first on an Arabic page). None when no clean split is found.
    The running header (above the first full-width rule) is left out: the whole-page run has it.
    `width`: the archive's pilot also cuts at the OCR width, half the image tokens (Z13 of
    the Bulletin-to-1956 review), to see whether a 200 dpi scan reads as well. `upright`: a page known not to be sideways (a cover, the
    contents) skips the orientation check, for a scan Tesseract has not read yet a Tesseract call of its own."""

    from apps.sources.models import Language

    folder = Path(settings.CORPUS_DIR) / 'renders' / page.document.sha256[:16]
    out = [folder / f'{page.index:04d}-{width}-col{i}.png' for i in (0, 1)]
    if all(p.exists() for p in out):
        return out
    if not upright and is_sideways(page):
        return None
    folder.mkdir(parents=True, exist_ok=True)
    image = _render(page, width).convert('L')      # cut in memory: the full 3192 px page is never needed again
    w, h = image.size
    rows = _ink(image, (0, 0, w, h), (1, h))
    top = 0
    for y in range(int(h * 0.15)):
        if rows[y] > 0.6:  # the rule under the running header
            top = y + 1
    inked = [y for y in range(top, h) if rows[y] > 0.002]
    if not inked:
        return None
    bottom = inked[-1] + 1
    lo, hi = int(w * 0.4), int(w * 0.6)
    cols = _ink(image, (lo, top, hi, bottom), (hi - lo, 1))
    rule = max(range(len(cols)), key=cols.__getitem__)
    if cols[rule] > 0.85:
        split = lo + rule
    else:
        window = 8
        sums = [sum(cols[i:i + window]) / window for i in range(len(cols) - window)]
        gap = min(range(len(sums)), key=sums.__getitem__)
        if sums[gap] > 0.01:
            return None
        split = lo + gap + window // 2
    right, left = image.crop((split, top, w, bottom)), image.crop((0, top, split, bottom))
    first, second = (right, left) if page.document.language == Language.ARABIC else (left, right)
    # zlib level 1: a scan's columns compress in half the time for 13 % more bytes (0.28 s against 0.51 s at
    # 3192 px on the machine that runs the archive, whose CPU sets the run's pace; the upload does not).
    first.save(out[0], compress_level=1)
    second.save(out[1], compress_level=1)
    return out


def _halves(image):
    """An image cut in two at the whitest band between its 40 % and 60 % of height, so no line is cut through."""
    w, h = image.size
    rows = _ink(image, (0, 0, w, h), (1, h))
    lo, hi, window = int(h * 0.4), int(h * 0.6), max(4, h // 300)
    sums = [sum(rows[y:y + window]) for y in range(lo, hi - window)]
    if not sums:
        return image.crop((0, 0, w, h // 2)), image.crop((0, h // 2, w, h))
    least = min(sums)
    y = min((lo + i + window // 2 for i, v in enumerate(sums) if v <= least + 1e-9), key=lambda y: abs(y - h // 2))
    return image.crop((0, 0, w, y)), image.crop((0, y, w, h))


def render_strips(page: Page, width: int, *, columns: bool) -> list[Path]:
    """The page in smaller pieces for a reading that lost lines (Z16 of the second-archive-run review): each column's
    upper and lower half in reading order, or, for a page read whole, its two halves. Haiku left fewer lines out of a
    column than of a page (5 % short against 23 % in the pilot); a half column holds half again."""
    from PIL import Image

    folder = Path(settings.CORPUS_DIR) / 'renders' / page.document.sha256[:16]
    kind = 'cs' if columns else 'ps'
    sources = (render_columns(page, width) or []) if columns else [render_page(page, width)]
    out = [folder / f'{page.index:04d}-{width}-{kind}{i}.png' for i in range(2 * len(sources))]
    if sources and all(p.exists() for p in out):
        return out
    for i, source in enumerate(sources):
        with Image.open(source) as image:
            for k, half in enumerate(_halves(image.convert('L'))):
                half.save(out[2 * i + k], compress_level=1)
    return out if sources else []
