"""The evidence behind every text: a page's image, its OCR text, the PDF itself. Public, read-only."""
from django.http import FileResponse, Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.consolidation.services.layer import page_text
from apps.corpus.models import Text, Version
from apps.corpus.services import reading
from apps.corpus.services.addresses import text_path
from apps.opendata.throttles import PublicRate
from apps.sources.models import OcrRun, Page, TextSource
from apps.sources.services import files
from apps.sources.services.issue import clean_reading, reading_check
from apps.sources.services.render import WEB_WIDTHS, for_reading
from config import drawing


class PublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicRate]


# An answer the day of reading counts is the reader's browser's to keep, never a shared cache's: one in between would
# hand it on uncounted.
METERED = 'private, max-age=86400'


def engine(run: OcrRun) -> str:
    """Who read a page, as a reader is told: «tesseract», or «ai» for any model and a vote between its readings. The
    model's name and the run's price stay in the pipeline's rows."""
    return 'tesseract' if run.engine.startswith('tesseract') else 'ai'


def _page(document_id: int, index: int) -> Page:
    page = (Page.objects.select_related('document__issue')
            .filter(files.public('document__'), document_id=document_id, index=index).first())
    if page is None:
        raise Http404
    return page


class PageDetail(PublicView):
    def get(self, request, document_id, index):
        page = _page(document_id, index)
        if (stop := reading.refused(request)) is not None:
            return stop
        reading.spend(request, 1)            # a printed page's reading counts as an article
        doc = page.document
        issue = getattr(doc, 'issue', None)
        texts = []
        if issue and page.printed_number:
            # Each text's printed pages, from its first version as the model orders them, read for all of them at once
            # (found by the repeated-queries log: one query a text of the issue).
            spans: dict[int, str] = {}
            for text_id, pages in (Version.objects.filter(text__first_published_in=issue)
                                   .order_by('text_id', 'language', '-valid_from').values_list('text_id', 'source_pages')):
                spans.setdefault(text_id, pages)
            for t in Text.objects.filter(first_published_in=issue).order_by('first_published_page'):
                span = spans.get(t.pk) or ''
                lo, _, hi = span.partition('-')
                if lo.isdigit() and int(lo) <= page.printed_number <= int(hi or lo):
                    texts.append({'id': t.pk, 'path': text_path(t.akn_uri), 'title': t.title_ar,
                                  'number_as_printed': t.number_as_printed,
                                  'type_label': t.get_type_display()})
        runs = list(page.ocr_runs.order_by('-created_at'))
        shown = next((r for r in runs if clean_reading(r.text) == page.text), None) \
            if page.text_source == TextSource.OCR else None
        text, repaired = page_text(page)
        return Response({
            'document_id': doc.pk, 'index': page.index, 'printed_number': page.printed_number, 'source': doc.source,
            'page_count': doc.page_count, 'kind': page.kind, 'language': doc.language, 'text': text, 'text_source': page.text_source,
            'repaired': repaired,
            'layer_letters': page.layer_letters,
            'read_by': None if shown is None else {'engine': engine(shown), 'variant': shown.variant.split('-')[0]},
            'check': reading_check(page, page.text) if shown else None,
            'ocr_runs': [{'engine': engine(r), 'variant': r.variant, 'chars': len(r.text)} for r in runs],
            'issue': None if issue is None else {'edition': issue.edition, 'number': issue.number,
                                                 'suffix': issue.suffix, 'key': issue.key, 'date': issue.date},
            'texts': texts,
        })


class PageImage(PublicView):
    """The page as rendered for OCR (PNG, 1596 px), or with ?w=900|1600 as WebP for reading (U16 of
    the Moroccan-design review: a page's PNG weighed 210–240 KB; at a phone's 900 px the WebP is about a third)."""

    def get(self, request, document_id, index):
        page = _page(document_id, index)
        width = request.query_params.get('w')
        width = int(width) if width in WEB_WIDTHS else None
        # The printed page holds the law's words: it counts as an article of the day of reading, as its reading does.
        return reading.metered(request, lambda: self.image(request, page, width), 1)

    @staticmethod
    def image(request, page, width):
        try:
            path = for_reading(page, width, request)
        except drawing.Busy:
            return drawing.busy()
        except FileNotFoundError:          # the page's file is not on this machine (the sample, a copy without files)
            raise Http404 from None
        response = FileResponse(open(path, 'rb'), content_type='image/webp' if width else 'image/png')
        response['Cache-Control'] = METERED
        return response


class PageRegion(PublicView):
    """GET ?label=المادة 49: where that article stands on the page, as shares of it (U14 of
    the Moroccan-design review), or null; `waiting` while its words were not read yet (N13 of the read-and-trusted review)."""

    def get(self, request, document_id, index):
        from apps.sources.services import regions
        label = (request.query_params.get('label') or '')[:60]
        if not label:
            return Response({'region': None})
        page = _page(document_id, index)
        if not regions.read_yet(page):
            # Never Tesseract in a request (N13): «not yet», the page put on tonight's list, asked again tomorrow; meanwhile
            # the witness's lines of an archive scan frame the article's column (HM39).
            regions.want(page)
            response = Response({'region': regions.guess(page, label), 'waiting': True})
            response['Cache-Control'] = 'public, max-age=300'
            return response
        return Response({'region': regions.region(page, label)})


class DocumentFile(PublicView):
    """A published document's file as fetched (services/files.py says which): a PDF opens in the browser; any other
    file is a download, sandboxed, so a page saved from another site never runs its scripts here."""

    def get(self, request, document_id):
        doc = files.published(document_id)
        path = files.on_disk(doc) if doc else None
        if path is None:
            raise Http404
        # A whole file is all its pages: each counts as an article of the day of reading.
        return reading.metered(request, lambda: self.file(doc, path), doc.page_count or 1)

    @staticmethod
    def file(doc, path):
        if files.opens_in_browser(doc):
            response = FileResponse(open(path, 'rb'), content_type=files.PDF)
        else:
            response = FileResponse(open(path, 'rb'), content_type=doc.mime or 'application/octet-stream',
                                    as_attachment=True, filename=path.name)
            response['Content-Security-Policy'] = 'sandbox'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Cache-Control'] = METERED
        return response
