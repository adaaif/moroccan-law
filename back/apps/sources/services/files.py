"""Which of the kept files the site hands out, and how.

Every fetched file is kept with its hash as evidence, but the site publishes only the law's own files: a Bulletin
issue, an official consolidation or text, a bill and its papers, each from the official site that printed it. These
are the files its pages link to (an issue's, a version's source, a French issue, a bill's). The rest stays on disk: a
court decision still carries the parties' names, and a web page, a table or a report from another site is kept to
prove a claim and is linked at its own address. A file that is not a PDF leaves as a download that the browser never
runs as this site: a page saved from another site carries that site's scripts."""
from pathlib import Path

from django.core.exceptions import SuspiciousFileOperation
from django.db.models import Q

from apps.sources.models import Document, DocumentKind, Source
from apps.sources.services.ingest import corpus_path

PDF = 'application/pdf'
PUBLIC_KINDS = (DocumentKind.BO_ISSUE, DocumentKind.CONSOLIDATED_TEXT, DocumentKind.TEXT, DocumentKind.PARLIAMENT)
PUBLIC_SOURCES = (Source.SGG_BO, Source.SGG_CONSOLIDATED, Source.ADALA, Source.DGI, Source.PARLIAMENT, Source.MEF)


def public(prefix: str = '') -> Q:
    """The documents the site publishes; `prefix` reads them through a relation ('document__' for pages)."""
    return Q(**{f'{prefix}kind__in': PUBLIC_KINDS, f'{prefix}source__in': PUBLIC_SOURCES})


def published(document_id: int) -> Document | None:
    return Document.objects.filter(public(), pk=document_id).first()


def on_disk(doc: Document) -> Path | None:
    """The document's file, while it is where its row says, inside the corpus folder."""
    try:
        path = corpus_path(doc)
    except SuspiciousFileOperation:
        return None
    return path if path.is_file() else None


def opens_in_browser(doc: Document) -> bool:
    """A PDF is shown by the browser's own viewer; anything else is a download."""
    return doc.mime == PDF
