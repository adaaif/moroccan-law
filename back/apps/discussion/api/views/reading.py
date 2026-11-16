"""What anyone reads of the discussion: a topic's feed, a post and its replies, an article's posts, the places, the
margin's counts, the questions waiting and answered, a person's page, the month's numbers. A reader with no account
gets the answer kept by generation."""
from datetime import date

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView
from apps.accounts.services.refusals import Refused
from apps.corpus.services import generation, reading
from apps.discussion.services import numbers, thread
from apps.opendata.throttles import OPEN

# A page or a comment asked for in the address, within what the database counts: «?page=10**40» overflowed the query's
# offset, and a comment's number past a row's id overflowed its lookup (each a 500).
MOST_PAGE = 10_000
MOST_ID = 2**31 - 1


def _int(value, default=1) -> int:
    try:
        return min(max(1, int(value)), MOST_PAGE)
    except (TypeError, ValueError):
        return default


def _offset(value) -> int:
    """A comment's number, 0 or more."""
    try:
        return min(max(0, int(value)), MOST_ID)
    except (TypeError, ValueError):
        return 0


# How long a reader's answer is kept at most: its voices' links are signed for 30 minutes (S14 of the performance audit).
TALK_KEPT = 60
#: The month's counts on the rules page: kept ten minutes, the law's generation aside (each comment would end them).
NUMBERS_KEPT = 600


class FeedView(RefusingView):
    """GET ?place=/talk/family&sort=active|new|top|open&period=week|month|year|all&page=1: a topic's posts, the form's
    standing; `period` for «الأنفع» only."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        q = request.query_params
        place, sort, page = q.get('place', ''), q.get('sort', 'active'), _int(q.get('page'))
        period = q.get('period') if sort == 'top' and q.get('period') in thread.PERIODS else 'month'
        if request.user.is_authenticated:
            return Response(thread.feed(request.user, place, sort, page, period))
        return generation.answer(['feed', place, sort, page, period],
                                 lambda: thread.feed(None, place, sort, page, period),
                                 scopes=('corpus', 'talk'), timeout=TALK_KEPT)


class PostView(RefusingView):
    """GET ?page=&sort=best|new|old: one post with a page of its comments' conversations."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request, pk):
        page, sort = _int(request.query_params.get('page')), request.query_params.get('sort', 'best')
        if request.user.is_authenticated:
            return Response(thread.post(request.user, pk, page, sort))
        return generation.answer(['post', pk, page, sort], lambda: thread.post(None, pk, page, sort),
                                 scopes=('corpus', 'talk'), timeout=TALK_KEPT)


class PostAnswersView(RefusingView):
    """GET ?to=<a comment>&page=: a door, the replies that answer that comment a page at a time; or ?around=<a comment>:
    the line of its conversation down to it, where a link to it lands."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request, pk):
        if 'around' in request.query_params:
            to = _offset(request.query_params.get('around'))
            if request.user.is_authenticated:
                return Response(thread.post_around(request.user, pk, to))
            return generation.answer(['around', pk, to], lambda: thread.post_around(None, pk, to),
                                     scopes=('corpus', 'talk'), timeout=TALK_KEPT)
        to, page = _offset(request.query_params.get('to')), _int(request.query_params.get('page'))
        if request.user.is_authenticated:
            return Response(thread.post_answers(request.user, pk, to, page))
        return generation.answer(['door', pk, to, page], lambda: thread.post_answers(None, pk, to, page),
                                 scopes=('corpus', 'talk'), timeout=TALK_KEPT)


class CitedView(RefusingView):
    """GET ?path=/ma/…/art_34&page=: the article, the posts that cite it, the places a question about it may go. The
    article's words count against the day of reading, as on its text's page."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        path, page = request.query_params.get('path', ''), _int(request.query_params.get('page'))
        if request.user.is_authenticated:
            return reading.metered(request, lambda: Response(thread.cited(request.user, path, page)))
        return reading.metered(request, lambda: generation.answer(['cited', path, page], lambda: thread.cited(None, path, page),
                                                                  scopes=('corpus', 'talk'), timeout=TALK_KEPT))


class PlacesView(RefusingView):
    """GET: the places, each with its counts and latest posts (the conversation's hub)."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = OPEN

    def get(self, request):
        return generation.answer(['places'], thread.overview, scopes=('corpus', 'talk'), timeout=TALK_KEPT)


class CountsView(RefusingView):
    """GET ?text=/ma/loi/2013/67-12: how many posts and comments cite each article, for the text's margin."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = OPEN

    def get(self, request):
        from django.conf import settings

        text = request.query_params.get('text', '')
        response = generation.answer(['counts', text, settings.DISCUSSION_OPEN], lambda: {
            'open': settings.DISCUSSION_OPEN, 'articles': thread.counts(text)}, scopes=('talk',), timeout=TALK_KEPT)
        response['Cache-Control'] = 'public, max-age=60'
        return response


class QuestionsView(RefusingView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = OPEN

    def get(self, request):
        place, page = request.query_params.get('place', ''), _int(request.query_params.get('page'))
        return generation.answer(['questions', place, page], lambda: thread.open_questions(place, page),
                                 scopes=('corpus', 'talk'), timeout=TALK_KEPT)


class AnsweredView(RefusingView):
    """GET ?page=: questions someone answered, the latest first, each with its answer (R12 of the for-everyone review)."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = OPEN

    def get(self, request):
        page = _int(request.query_params.get('page'))
        return generation.answer(['answered', page], lambda: thread.answered_questions(page), scopes=('corpus', 'talk'),
                                 timeout=TALK_KEPT)


class PersonView(RefusingView):
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request, username):
        page = _int(request.query_params.get('page'))
        kind = request.query_params.get('kind', '')
        kind = kind if kind in ('posts', 'answers') else ''

        def build(viewer=None):
            found = thread.person(viewer, username, page, kind)
            if found is None:
                raise Refused('person', 'not_found', 404)
            return found
        if request.user.is_authenticated:
            return Response(build(request.user))
        return generation.answer(['person', username.lower(), page, kind], build, scopes=('corpus', 'talk'),
                                 timeout=TALK_KEPT)


class NumbersView(RefusingView):
    """GET ?month=2026-10: the month's counts; without, this month and the one before."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = OPEN

    def get(self, request):
        asked = request.query_params.get('month', '')
        try:
            if asked:
                year, month = (int(x) for x in asked.split('-'))
                date(year, month, 1)
                return generation.answer(['numbers', year, month], lambda: {'months': [numbers.month(year, month)]},
                                         timeout=NUMBERS_KEPT)
        except ValueError:
            raise Refused('month', 'invalid') from None
        today = timezone.localdate()
        before = (today.year - (today.month == 1), (today.month - 2) % 12 + 1)
        return generation.answer(['numbers', today.year, today.month],
                                 lambda: {'months': [numbers.month(today.year, today.month), numbers.month(*before)]},
                                 timeout=NUMBERS_KEPT)
