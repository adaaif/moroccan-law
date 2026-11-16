"""Files into Documents, Bulletin Officiel issues and Pages, with each page's text layer and kind."""
import hashlib
import mimetypes
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.db import transaction

from apps.sources.models import Document, Issue, Page, PageKind, TextSource

# A page with this many letters in its text layer is read from the layer; fewer, it needs OCR.
TEXT_LAYER_MIN_LETTERS = 200


ARABIC_LETTERS = [chr(c) for c in range(0x0621, 0x064B)]     # ء … ي, as the reading counts them


def letters(text: str, language: str) -> int:
    """An Arabic file counts Arabic letters only: old fonts give a layer of mojibake («E=: R±³PR&±»), which is no
    text to read or to check a reading against. A reading is counted the same way (its French words, a diploma's
    name, are not in the count either)."""
    if language == 'ar':
        return sum(map(text.count, ARABIC_LETTERS))
    return sum(ch.isalpha() for ch in text)


def classify(letters: int, has_image: bool) -> str:
    if letters >= TEXT_LAYER_MIN_LETTERS:
        return PageKind.TEXT_LAYER
    if has_image:
        return PageKind.SCAN if letters < 20 else PageKind.MIXED
    return PageKind.BLANK if letters < 20 else PageKind.TEXT_LAYER


def corpus_path(doc: Document) -> Path:
    """The document's file under CORPUS_DIR. Its path is relative and never climbs out: an absolute path would replace
    the folder, and a «..» leave it, handing out any file the server can read. The check reads the path's own parts
    rather than resolving links, because the corpus's folders may be links to another disk."""
    parts = PurePosixPath(doc.path)
    if not doc.path or '\x00' in doc.path or parts.is_absolute() or '..' in parts.parts:
        raise SuspiciousFileOperation(f'document {doc.pk}: its path leaves the corpus folder')
    return Path(settings.CORPUS_DIR) / parts


def read_pages(doc: Document) -> None:
    """One Page per PDF page: its text layer as extracted (defects kept) and its kind."""
    pdf = pdfium.PdfDocument(str(corpus_path(doc)))
    try:
        doc.page_count = len(pdf)
        doc.producer = (pdf.get_metadata_dict().get('Producer') or '').replace('\x00', '')[:200]
        doc.save(update_fields=['page_count', 'producer'])
        pages = []
        for index in range(len(pdf)):
            page = pdf[index]
            # Postgres refuses NUL; some scans' layers and producers carry it (28 Oct 2026).
            text = page.get_textpage().get_text_range().replace('\x00', '')
            count = letters(text, doc.language)
            has_image = next(page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]), None) is not None
            kind = classify(count, has_image)
            pages.append(Page(document=doc, index=index, kind=kind, layer_text=text, layer_letters=count,
                              text=text if kind == PageKind.TEXT_LAYER else '',
                              text_source=TextSource.LAYER if kind == PageKind.TEXT_LAYER else TextSource.NONE))
        Page.objects.bulk_create(pages)
    finally:
        pdf.close()


@transaction.atomic
def ingest_file(path: Path, *, source: str, kind: str, language: str, url: str = '', title: str = '',
                meta: dict | None = None, issue: dict | None = None) -> Document:
    """Register a file under CORPUS_DIR once (by its hash) and read its pages."""
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    doc, created = Document.objects.get_or_create(sha256=sha, defaults={
        'source': source,
        'kind': kind,
        'url': url,
        'path': str(path.relative_to(settings.CORPUS_DIR)),
        'mime': mimetypes.guess_type(path.name)[0] or 'application/octet-stream',
        'bytes': len(data),
        'language': language,
        'title': title,
        'fetched_at': datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        'meta': meta or {},
    })
    if created and doc.mime == 'application/pdf':
        read_pages(doc)
    if issue:
        Issue.objects.update_or_create(
            edition=issue['edition'], number=int(issue['number']), suffix=issue.get('suffix', ''),
            defaults={'date': date.fromisoformat(issue['date']), 'document': doc},
        )
    return doc
