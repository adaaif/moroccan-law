"""The ways to a text: the shelf, the library and a book's card, the box that reads what a reader wrote, a year's
laws, the situations, and the constitutions by year and article."""
from pathlib import Path

from django.conf import settings
from django.http import Http404
from rest_framework.response import Response

from apps.corpus.api.views.answer import _WHOLE
from apps.corpus.api.views.base import PublicView
from apps.corpus.services import constitutions, generation
from apps.corpus.services.addresses import split_path
from apps.corpus.services.codes import shelf
from apps.corpus.services.situations import APPROVED, DRAFTS, GUIDES, SITUATIONS, TOPICS, published
from apps.corpus.services.works import text_at


class Shelf(PublicView):
    """The twenty texts readers look for most, and where each stands on the site (row 3 of the reader-experience review)."""

    def get(self, request):
        return generation.answer(['shelf'], shelf)


class Library(PublicView):
    """The library's codes and core laws in their nine piles, each book's currency (LB3–LB7 of the every-code review)."""

    def get(self, request):
        from apps.corpus.services.library import catalogue
        # The nightly fetch's own note of when it asked the SGG is part of the answer: kept until that file changes.
        asked = generation.files(Path(settings.CORPUS_DIR) / 'reports' / 'fetch_new_issues.json')
        return generation.answer(['library', asked], catalogue)


class LibraryCard(PublicView):
    """GET /api/corpus/library/card/?path=/ma/loi/15-95: a book's card (LB6): how to cite it, where it was printed, its
    parts, its newest change and its French. No law's words: it spends no reading."""

    def get(self, request):
        from apps.corpus.services.library import card
        path = request.query_params.get('path', '')
        if not path.startswith('/ma/'):
            return Response({'errors': [{'field': 'path', 'code': 'invalid'}]}, status=400)
        uri, _ = split_path(path)
        text, now = text_at(uri)
        if text is None:
            raise Http404
        return generation.answer(['library-card', now], lambda: card(text))


class Find(PublicView):
    """GET /api/corpus/find/?q=…: what a reader wrote to name a text, read into the texts it names, each sure or not
    (W1, W3–W6 of the library-search review). The library's box and the header's box both ask here. No law's words: it
    spends no reading."""

    def get(self, request):
        from apps.corpus.services.find import find
        return Response(find(request.query_params.get('q', '')))


class Year(PublicView):
    """GET /api/corpus/years/1958/: the laws and dahirs signed that year, the most cited first named (W8 of
    the library-search review). Titles and addresses only: it spends no reading."""

    def get(self, request, year):
        from apps.corpus.services import years

        def build():
            found = years.year(year)
            if found is None:
                raise Http404
            return found
        return generation.answer(['year', year], build)


class Situations(PublicView):
    """Situations readers meet, each with the articles to read first (row 4): the approved ones; while
    developing, Haiku's drafts too, marked as drafts."""

    def get(self, request):
        files = generation.files(SITUATIONS, DRAFTS, APPROVED, GUIDES, TOPICS)
        return generation.answer(['situations', settings.SHOW_DRAFTS, files], lambda: published(include_drafts=settings.SHOW_DRAFTS))


class ConstitutionAt(PublicView):
    """GET /api/corpus/constitution/?year=1996&article=19: the address of a constitution, or its article, by year (C1 of
    the constitution review: /constitution/1996/19); today's without a year."""

    def get(self, request):
        p = request.query_params
        # Western digits only: «²» passes isdigit() and int() refuses it.
        year = int(p['year']) if _WHOLE.fullmatch(p.get('year', '')) else None
        article = p.get('article') if _WHOLE.fullmatch(p.get('article', '')) else None
        path = constitutions.path_for(year, article)
        if path is None:
            return Response({'errors': [{'field': 'year', 'code': 'not_found'}]}, status=404)
        return Response({'path': path})


class ConstitutionLineage(PublicView):
    """GET /api/corpus/constitution/lineage/?path=/ma/dahir/1-11-91/art_19: the article in the other constitutions
    (C5), each with how its words stood against the one before."""

    def get(self, request):
        found = constitutions.lineage(request.query_params.get('path', ''))
        if found is None:
            return Response({'errors': [{'field': 'path', 'code': 'not_found'}]}, status=404)
        return Response(found)


class ConstitutionHistory(PublicView):
    """GET /api/corpus/constitution/history/: the six constitutions' short history (C4), with each one's facts."""

    def get(self, request):
        return Response(constitutions.chapters())
