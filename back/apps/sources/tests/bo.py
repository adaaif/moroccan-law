"""Bulletin issues for the commands' tests: small real PDFs whose text layer pdfium reads back as it reads the SGG's
(written with the repository's own Arabic font), registered the way the pipeline registers them."""
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

from apps.parliament.tests.pdfs import pdf_bytes
from apps.sources.models import Edition, Issue

# A page of a decree, enough Arabic letters (over 200) for its layer to count as text.
DECREE = ['مرسوم رقم 2.26.100 صادر في 2 نوفمبر 2026',
          'بتطبيق القانون رقم 31.08 القاضي بتحديد تدابير لحماية المستهلك',
          'رئيس الحكومة بناء على الدستور ولا سيما الفصل 90 منه',
          'المادة الأولى تحدد بقرار للسلطة الحكومية المكلفة بالتجارة',
          'كيفيات إعلام المستهلك بأسعار المنتوجات والسلع والخدمات',
          'المادة الثانية يسند تنفيذ هذا المرسوم إلى وزير الصناعة والتجارة']


class Reader:
    """The `anthropic` client a page reading meets: the corpus tests' stand-in for batches (claude.py: the API's own
    shapes, answered at once), and a single message whose text is the transcription as the model writes it."""

    def __init__(self, answer):
        from apps.corpus.tests.claude import Claude
        self.claude = Claude(answer)
        self.answer, self.sent = answer, []
        self.messages = NS(batches=self.claude.messages.batches, create=self.create)

    def create(self, **params):
        self.sent.append(params)
        return NS(model=params['model'], stop_reason='end_turn', usage=NS(input_tokens=2000, output_tokens=400),
                  content=[NS(type='thinking', thinking='…'), NS(type='text', text=self.answer('message', params))])

    def with_options(self, **kw):
        return self

    def requests(self) -> list[dict]:
        """Every request the batches carried, by custom id."""
        return self.messages.batches.requests()


def install(monkeypatch, settings, tmp_path, answer) -> Reader:
    """The model answers `answer(custom_id, params)`; the ledger and the budget's holds under tmp_path; the permission to
    spend is the test's own (claude.install)."""
    import anthropic

    from apps.corpus.tests import claude
    claude.install(monkeypatch, settings, tmp_path, answer)
    reader = Reader(answer)
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **kw: reader)
    return reader


def images(params: dict) -> list:
    """The pictures a request sends, decoded."""
    import base64
    import io

    from PIL import Image
    return [Image.open(io.BytesIO(base64.b64decode(block['source']['data'])))
            for block in params['messages'][0]['content'] if block['type'] == 'image']


def letters(lines: list[str]) -> int:
    return sum('ء' <= c <= 'ي' for c in ''.join(lines))


def write_pdf(path: Path, pages: list[list[str]], *, turned: bool = False) -> Path:
    """`turned`: each page's lines set a quarter turn, as the BO prints a landscape table on a portrait page."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_turned_bytes(pages) if turned else pdf_bytes(pages, rtl=True))
    return path


def _turned_bytes(pages: list[list[str]]) -> bytes:
    """Like `pdf_bytes`, each line turned 90° counter-clockwise, running up the page from its bottom left."""
    import ctypes
    import io

    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    from apps.parliament.tests.pdfs import FONT

    pdf = pdfium.PdfDocument.new()
    data = FONT.read_bytes()
    buffer = (ctypes.c_uint8 * len(data)).from_buffer_copy(data)
    font = pdfium_c.FPDFText_LoadFont(pdf.raw, buffer, len(data), pdfium_c.FPDF_FONT_TRUETYPE, True)
    for lines in pages:
        page = pdf.new_page(595, 842)
        for k, line in enumerate(lines):
            obj = pdfium_c.FPDFPageObj_CreateTextObj(pdf.raw, font, 9)
            # Drawn as a right-to-left file draws it: letters reversed, each number's digits kept in order.
            drawn = re.sub(r'[0-9][0-9.,]*[0-9]|[0-9]', lambda m: m.group(0)[::-1], line[::-1])
            wide = (drawn + '\0').encode('utf-16-le')
            pdfium_c.FPDFText_SetText(obj, ctypes.cast(ctypes.c_char_p(wide), pdfium_c.FPDF_WIDESTRING))
            pdfium_c.FPDFPageObj_Transform(obj, 0, 1, -1, 0, 40 + 12 * k, 40)
            pdfium_c.FPDFPage_InsertObject(page.raw, obj)
        page.gen_content()
    out = io.BytesIO()
    pdf.save(out)
    pdf.close()
    return out.getvalue()


def register(root: Path, number: int, pages: list[list[str]], *, day: date = date(2026, 11, 2), suffix: str = '') -> Issue:
    """An Arabic issue as `process_issue` registers it: its file under the corpus, a Document, its Issue, its pages."""
    from apps.sources.services.issue import register as register_issue
    key = f'{number}-{suffix}' if suffix else str(number)
    path = write_pdf(root / 'issues' / 'bo_ar' / f'BO_{key}_ar.pdf', pages)
    return register_issue(path, edition=Edition.GENERAL_AR, number=number, suffix=suffix, day=day)
