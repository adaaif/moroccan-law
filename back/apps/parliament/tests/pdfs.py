"""Small born-digital PDFs for the commands' tests: real files whose text layer pdfium reads back as it reads the
government's and the Chamber's, written with the repository's own Arabic font."""
import ctypes
import io
import re
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

FONT = Path(__file__).resolve().parents[2] / 'corpus' / 'fonts' / 'MarkaziText.ttf'

# A finance bill's running heads, on every page of its Arabic and French files.
HEAD_AR = ['مشروع قانون المالية رقم 60.26', 'للسنة المالية 2027']
HEAD_FR = ['PROJET DE LOI DE FINANCES N° 60-26', 'POUR L’ANNEE BUDGETAIRE 2027']


def plain_ar(first: int, last: int) -> list[str]:
    """Articles `first` to `last` of a bill, each a heading and one line."""
    return [line for n in range(first, last + 1) for line in (f'المادة {n}', 'نص هذه المادة.')]


def plain_fr(first: int, last: int) -> list[str]:
    return [line for n in range(first, last + 1) for line in (f'Article {n}', 'Texte de cet article.')]


def _visual(line: str) -> str:
    """An Arabic line as a right-to-left file draws it, left to right: its letters reversed, each number's digits kept
    in their order. The layer reads it back in reading order, with the quirks the real files have (mirrored
    guillemets, an amount's groups in visual order)."""
    return re.sub(r'[0-9][0-9.,]*[0-9]|[0-9]', lambda m: m.group(0)[::-1], line[::-1])


def pdf_bytes(pages: list[list[str]], *, rtl: bool = False) -> bytes:
    """A PDF of these pages, each line a text object of its own, one under the other."""
    pdf = pdfium.PdfDocument.new()
    font = None
    if any(pages):
        data = FONT.read_bytes()
        buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
        font = pdfium_c.FPDFText_LoadFont(pdf.raw, buffer, len(data), pdfium_c.FPDF_FONT_TRUETYPE, True)
    for lines in pages:
        page = pdf.new_page(595, 842)
        for k, line in enumerate(lines):
            obj = pdfium_c.FPDFPageObj_CreateTextObj(pdf.raw, font, 9)
            wide = ((_visual(line) if rtl else line) + '\0').encode('utf-16-le')
            pdfium_c.FPDFText_SetText(obj, ctypes.cast(ctypes.c_char_p(wide), pdfium_c.FPDF_WIDESTRING))
            pdfium_c.FPDFPageObj_Transform(obj, 1, 0, 0, 1, 20, 810 - 12 * k)
            pdfium_c.FPDFPage_InsertObject(page.raw, obj)
        page.gen_content()
    out = io.BytesIO()
    pdf.save(out)
    pdf.close()
    return out.getvalue()


def write_pdf(path: Path, pages: list[list[str]], *, rtl: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes(pages, rtl=rtl))
    return path
