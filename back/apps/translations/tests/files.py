"""Small real files for the commands' tests: a scanned French Bulletin's pages (image-only PDFs, drawn as the BO sets
its pages: two columns, a masthead across over them, a table across the page) with Tesseract's reading of each part
it is given; and Word-made PDFs whose text layer sets each run at its own size (Adala's French files: the body, a
footnote mark set small beside its word, footnotes a point under the body)."""
import ctypes
import io
import subprocess
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image, ImageDraw

from apps.parliament.tests.pdfs import FONT

# A page of 400 × 560 px at 300 dpi: pdfium renders it back at that size for the French reader (300 dpi), so the
# tests' images stay small.
W, H, DPI = 400, 560, 300


def _lines(draw, left: int, right: int, top: int, bottom: int) -> None:
    for y in range(top, bottom, 12):
        draw.rectangle((left, y, right, y + 4), fill=0)


def page_image(layout: str) -> Image.Image:
    """`columns`: two columns and the white gutter between them; `front`: the masthead and contents across, a rule,
    then the two columns; `across`: lines the whole width down the page (a table)."""
    image = Image.new('L', (W, H), 255)
    draw = ImageDraw.Draw(image)
    if layout == 'columns':
        _lines(draw, 20, 190, 20, 540)
        _lines(draw, 210, 380, 20, 540)
    elif layout == 'front':
        _lines(draw, 20, 380, 20, 60)
        draw.rectangle((10, 75, 390, 77), fill=0)
        _lines(draw, 20, 190, 90, 540)
        _lines(draw, 210, 380, 90, 540)
    else:
        _lines(draw, 20, 380, 20, 540)
    return image


def scan_pdf(path: Path, layouts: list[str]) -> Path:
    """An image-only PDF, one scanned page a layout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    first, *rest = [page_image(layout) for layout in layouts]
    first.save(path, 'PDF', resolution=DPI, save_all=True, append_images=rest)
    return path


class Tesseract:
    """Tesseract as the French reader runs it: each call answers the next reading, in the order the pages and their
    parts are read, as Tesseract prints it to stdout. `calls`: each call's arguments, its image's place left out (a
    temporary file), with the image's format and size, and the options it was run with."""

    def __init__(self, readings: list[str]):
        self.readings, self.calls = list(readings), []
        self.run = subprocess.run

    @property
    def sizes(self) -> list[tuple[int, int]]:
        return [call['size'] for call in self.calls]

    def __call__(self, args, **kw):
        if args[0] != 'tesseract':
            return self.run(args, **kw)
        with Image.open(args[1]) as image:
            self.calls.append({'args': [args[0], *args[2:]], 'image': (Path(args[1]).suffix, image.format),
                               'size': image.size, 'options': kw})
        return subprocess.CompletedProcess(args, 0, stdout=self.readings.pop(0) + '\n', stderr='')


def layer_pdf(path: Path, pages: list[list[list[tuple[str, float]]]]) -> Path:
    """A born-digital PDF: each page a list of lines, each line its runs (text, size) set one after the other on one
    baseline, a smaller run raised as a footnote's mark is."""
    pdf = pdfium.PdfDocument.new()
    data = FONT.read_bytes()
    buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
    font = pdfium_c.FPDFText_LoadFont(pdf.raw, buffer, len(data), pdfium_c.FPDF_FONT_TRUETYPE, True)
    for lines in pages:
        page = pdf.new_page(595, 842)
        y = 800.0
        for runs in lines:
            x, size = 40.0, runs[0][1]
            for text, run_size in runs:
                obj = pdfium_c.FPDFPageObj_CreateTextObj(pdf.raw, font, run_size)
                wide = (text + '\0').encode('utf-16-le')
                pdfium_c.FPDFText_SetText(obj, ctypes.cast(ctypes.c_char_p(wide), pdfium_c.FPDF_WIDESTRING))
                pdfium_c.FPDFPageObj_Transform(obj, 1, 0, 0, 1, x, y + (0 if run_size >= size else size * 0.4))
                pdfium_c.FPDFPage_InsertObject(page.raw, obj)
                x += len(text) * run_size * 0.5
            y -= size * 1.6
        page.gen_content()
    out = io.BytesIO()
    pdf.save(out)
    pdf.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out.getvalue())
    return path
