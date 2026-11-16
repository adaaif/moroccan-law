"""Chosen articles as a Word file, each with its reference as it is cited: for a lawyer's memo or a student's
revision. POST /api/corpus/export/ {"paths": ["/ma/loi/2025/60-24/art_8", …]}."""
import io
from functools import reduce
from operator import or_

from django.db.models import Prefetch, Q
from django.http import HttpResponse
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from rest_framework.response import Response

from apps.corpus.api.views import PublicView
from apps.corpus.models import Article, Text, Version
from apps.corpus.services import reading
from apps.corpus.services.addresses import split_path
from apps.corpus.services.citing import COMPILERS, citer
from apps.sources.models import Edition, Issue
from config.saved import file_name

MAX_ARTICLES = 200
ADDRESS_MOST = 300       # an article's address, as a report's path allows


def chosen(paths: list) -> list[tuple]:
    """(the text, its version, the article, how it is cited) for each address that leads to an article of a text's
    latest version, in the order asked, in four queries whatever their number: three a path before (OP15 of the
    open-source audit, 600 queries for the 200 allowed)."""
    asked = [split_path(str(p)[:ADDRESS_MOST]) for p in paths]
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={uri for uri, eid in asked if eid})
             .select_related('first_published_in')
             .prefetch_related(Prefetch('versions', queryset=Version.objects.select_related('source_document')))}
    latest = {uri: t.latest_version() for uri, t in texts.items()}
    pairs = {(latest[uri].pk, eid) for uri, eid in asked if eid and latest.get(uri) is not None}
    found: dict[tuple, Article] = {}
    if pairs:
        for a in Article.objects.filter(reduce(or_, (Q(version_id=v, eid=e) for v, e in pairs))).order_by('version_id', 'order'):
            found.setdefault((a.version_id, a.eid), a)
    # The issue a compiler's file names, for a text that holds none, read once for all of them (citing.citer).
    noted = {str(v.source_document.meta['first_issue']) for uri, v in latest.items()
             if v is not None and texts[uri].first_published_in_id is None and v.consolidation in COMPILERS
             and v.source_document_id and v.source_document.meta.get('first_issue')}
    issues: dict[str, Issue] = {}
    for i in Issue.objects.filter(edition=Edition.GENERAL_AR, number__in=noted).order_by('-suffix') if noted else []:
        issues[str(i.number)] = i          # the first by suffix wins, as citer's own query orders them
    cites = {}
    out = []
    for uri, eid in asked:
        version = latest.get(uri)
        article = found.get((version.pk, eid)) if version is not None and eid else None
        if article is None:
            continue
        if uri not in cites:
            cites[uri] = citer(texts[uri], version, issues)
        out.append((texts[uri], version, article, cites[uri]))
    return out


def _rtl(paragraph, size: int = 13, bold: bool = False):
    """A paragraph set right to left, its runs in Arabic script sizes (Word reads the complex-script size)."""
    paragraph._p.get_or_add_pPr().append(OxmlElement('w:bidi'))
    for run in paragraph.runs:
        rpr = run._r.get_or_add_rPr()
        rpr.append(OxmlElement('w:rtl'))
        cs = OxmlElement('w:szCs')
        cs.set(qn('w:val'), str(size * 2))
        rpr.append(cs)
        run.font.size = Pt(size)
        run.font.bold = bold
        if bold:
            rpr.append(OxmlElement('w:bCs'))
    return paragraph


class Export(PublicView):
    def post(self, request):
        paths = request.data.get('paths') if isinstance(request.data, dict) else None
        if not isinstance(paths, list) or not 0 < len(paths) <= MAX_ARTICLES:
            return Response({'errors': [{'field': 'paths', 'code': 'invalid'}]}, status=400)
        if (stop := reading.refused(request)) is not None:
            return stop
        found = chosen(paths)
        if not found:
            return Response({'errors': [{'field': 'paths', 'code': 'not_found'}]}, status=404)
        doc = Document()
        for _text, _version, article, cite in found:
            _rtl(doc.add_paragraph(article.label), size=15, bold=True)
            for line in article.body.splitlines():
                if line.strip():
                    _rtl(doc.add_paragraph(line.strip()))
            _rtl(doc.add_paragraph(cite(article)), size=11)
        reading.spend(request, len(found))
        buf = io.BytesIO()
        doc.save(buf)
        response = HttpResponse(buf.getvalue(),
                                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="{file_name("articles.docx")}"'
        return response
