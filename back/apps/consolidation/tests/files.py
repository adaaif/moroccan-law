"""Small real files for the loaders' tests: PDFs made as Word makes Adala's and the DGI's, each run of a line set at its
own size (the law in the main size, a footnote's mark small and raised beside its word, the footnotes a few points
under the body, the page number apart), Arabic drawn right to left as the files draw it, so pdfium's layer gives it
back in reading order with the files' own quirks (brackets mirrored, a mark printed before its line's words); and
Tesseract's answer for a page image, in the TSV it prints."""
import ctypes
import io
import json
import re
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from apps.parliament.tests.pdfs import FONT


def visual(line: str) -> str:
    """An Arabic line as a right-to-left file draws it, left to right: its letters reversed, each number's digits kept
    in their order."""
    return re.sub(r'[0-9][0-9.,]*[0-9]|[0-9]', lambda m: m.group(0)[::-1], line[::-1])


def word_pdf(path: Path, pages: list[list[list[tuple[str, float]]]], *, rtl: bool = True,
             size: tuple[int, int] = (595, 842)) -> Path:
    """A born-digital PDF: each page a list of lines, each line its runs (text, size) in reading order, set one after
    the other on one baseline; a run smaller than the line's largest is raised, as a footnote's mark is."""
    pdf = pdfium.PdfDocument.new()
    data = FONT.read_bytes()
    buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
    font = pdfium_c.FPDFText_LoadFont(pdf.raw, buffer, len(data), pdfium_c.FPDF_FONT_TRUETYPE, True)
    width, height = size
    for lines in pages:
        page = pdf.new_page(width, height)
        y = height - 30.0
        for runs in lines:
            line_size = max(s for _, s in runs)
            drawn = [(visual(t), s) for t, s in reversed(runs)] if rtl else runs
            x = 10.0
            for text, run_size in drawn:
                obj = pdfium_c.FPDFPageObj_CreateTextObj(pdf.raw, font, run_size)
                wide = (text + '\0').encode('utf-16-le')
                pdfium_c.FPDFText_SetText(obj, ctypes.cast(ctypes.c_char_p(wide), pdfium_c.FPDF_WIDESTRING))
                raised = 0 if run_size >= line_size else line_size * 0.1
                pdfium_c.FPDFPageObj_Transform(obj, 1, 0, 0, 1, x, y + raised)
                pdfium_c.FPDFPage_InsertObject(page.raw, obj)
                x += len(text) * run_size * 0.5
            y -= line_size * 1.6
        page.gen_content()
    out = io.BytesIO()
    pdf.save(out)
    pdf.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out.getvalue())
    return path


def lexicon(corpus: Path, lines: list[str], times: int = 20) -> dict[str, int]:
    """The corpus's words (derived/lexicon.json, as `build_lexicon` writes it from the BO's articles): each Arabic word
    of these lines, printed `times` times."""
    words: dict[str, int] = {}
    for line in lines:
        for w in re.findall(r'[ء-ي]+', line):
            words[w] = words.get(w, 0) + times
    (corpus / 'derived').mkdir(parents=True, exist_ok=True)
    (corpus / 'derived' / 'lexicon.json').write_text(json.dumps(words, ensure_ascii=False))
    return words


TSV_HEAD = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext'


def tsv(rows: list[tuple[int, int, str]]) -> str:
    """Tesseract's TSV for a page image read in lines: each (top, height, words) a line, then its words (level 5) in
    reading order, right to left on the page."""
    out = [TSV_HEAD]
    for k, (top, height, words) in enumerate(rows, 1):
        out.append(f'4\t1\t1\t1\t{k}\t0\t10\t{top}\t300\t{height}\t-1\t')
        for w, word in enumerate(words.split(), 1):
            out.append(f'5\t1\t1\t1\t{k}\t{w}\t{1000 - 20 * w}\t{top}\t18\t{height}\t91.5\t{word}')
    return '\n'.join(out)
