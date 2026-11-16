"""The Bulletin's issues: the list of those holding texts, an issue with its pages and texts, how it was read, and
the compact map of every issue."""
from collections import defaultdict
from functools import reduce
from operator import or_

from django.db.models import Count, Exists, Max, OuterRef, Q, Subquery
from django.http import Http404

from apps.consolidation.models import Change
from apps.corpus.api.views.base import PublicView, issue_ref, text_ref
from apps.corpus.models import Text, Version
from apps.corpus.services import generation
from apps.corpus.services.addresses import text_path
from apps.quality.models import Report
from apps.sources.models import Issue
from apps.sources.services.quality import issue_quality


def last_numbers() -> dict[int, int]:
    """Each cover that bears several numbers, and the last of them (one query)."""
    return dict(Issue.objects.filter(copy_of__isnull=False).values('copy_of').annotate(last=Max('number'))
                .values_list('copy_of', 'last'))


class IssueList(PublicView):
    def get(self, request):
        return generation.answer(['issues'], self.issues)

    @staticmethod
    def issues() -> list[dict]:
        # Explicit order: a grouped query (the Count) drops the model's default ordering.
        issues = (Issue.objects.select_related('document').annotate(n_texts=Count('texts_first_published'))
                  .order_by('-date', '-number', '-suffix'))
        last = last_numbers()
        return [{**issue_ref(i, last.get(i.pk)), 'texts': i.n_texts} for i in issues if i.n_texts]


class IssueDetail(PublicView):
    def get(self, request, edition, key):
        return generation.answer(['issue', edition, key], lambda: self.issue(edition, key))

    @staticmethod
    def issue(edition: str, key: str) -> dict:
        try:
            number, suffix = Issue.parse_key(key)
        except ValueError:
            raise Http404 from None
        last = Subquery(Issue.objects.filter(copy_of=OuterRef('pk')).values('copy_of').annotate(m=Max('number'))
                        .values('m')[:1])
        found = Issue.objects.select_related('document').annotate(last=last)
        issue = found.filter(edition=edition, number=number, suffix=suffix).first()
        if issue is None:
            raise Http404
        asked_for = None
        if issue.copy_of_id:            # a number printed on another issue's cover leads to it (C1)
            asked_for, issue = issue.key, found.get(pk=issue.copy_of_id)
        texts = (Text.objects.filter(first_published_in=issue).order_by('first_published_page', 'id')
                 .annotate(n_articles=Count('versions__articles', distinct=True),
                           has_versions=Exists(Version.objects.filter(text=OuterRef('pk')))))
        amends = defaultdict(set)
        for by, target in Change.objects.filter(by_uri__in=[t.akn_uri for t in texts],
                                                source=Change.Source.READING).values_list('by_uri', 'text_uri'):
            amends[by].add(target)
        pages = issue.document.pages.order_by('index').values('index', 'printed_number', 'kind', 'text_source')
        texts = list(texts)
        printed = []
        if not texts:                   # kept by its pages alone: what its own contents table says it holds (W9)
            from apps.sources.services.contents import contents
            printed = contents(issue.document.pages.filter(index=0).values_list('text', flat=True).first() or '')
        return {**issue_ref(issue, issue.last), 'asked_for': asked_for, 'pages': list(pages), 'contents': printed, 'texts': [
            {**text_ref(t), 'rubric': t.rubric, 'section': t.bo_section, 'page': t.first_published_page,
             'authority': t.authority, 'signed_on': t.signed_on, 'articles': t.n_articles,
             'amends': len(amends[t.akn_uri])}
            for t in texts]}


class IssueQuality(PublicView):
    """How an issue was read, page by page, the texts its contents list that were not found, the open reports."""

    def get(self, request, edition, key):
        return generation.answer(['issue-quality', edition, key], lambda: self.quality(edition, key))

    @staticmethod
    def quality(edition: str, key: str) -> dict:
        try:
            number, suffix = Issue.parse_key(key)
        except ValueError:
            raise Http404 from None
        issue = Issue.objects.select_related('document').filter(edition=edition, number=number, suffix=suffix).first()
        if issue is None or not issue.document_id:
            raise Http404
        paths = [text_path(t.akn_uri) for t in Text.objects.filter(first_published_in=issue)]
        # The open reports on the issue's texts and their articles, read once (two counts a text before).
        anywhere = reduce(or_, (Q(path=p) | Q(path__startswith=p + '/') for p in paths), Q(pk__in=[]))
        reported = list(Report.objects.filter(anywhere, status=Report.Status.OPEN).values_list('path', flat=True))
        open_reports = sum(1 for p in paths for r in reported if r == p or r.startswith(p + '/'))
        return {**issue_ref(issue), **issue_quality(issue), 'texts': len(paths), 'open_reports': open_reports}


class IssueMap(PublicView):
    """Every issue held, compact (LB13, LB10): what the library's strata, /bo and the box read, 29 KB gzipped where the
    issue list is 188 KB."""

    def get(self, request):
        from apps.corpus.services.library import issue_map
        return generation.answer(['issue-map'], issue_map)
