"""The explanations' API (R8, R9, R13 of the for-everyone review). Views read the request, call a service and answer;
refusals come back in the one error shape."""
import re
from datetime import date

from django.http import FileResponse
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView, require_types
from apps.accounts.services.refusals import Refused
from apps.corpus.services import generation, reading
from apps.explain.services import cards, concepts, explanations, week
from apps.opendata.throttles import OPEN
from config import drawing


def _path(request, source='query') -> str:
    data = request.query_params if source == 'query' else request.data
    return str(data.get('path') or '').strip()


class TextBundle(RefusingView):
    """GET ?path=/ma/loi/67-12: the text's explanation and each article's, as its page shows them."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        path = _path(request)
        # Its explanations, the articles' words they are compared with and the discussion's stand-ins (S14).
        return generation.answer(['explain-text', path], lambda: explanations.bundle(path),
                                 scopes=('corpus', 'talk', 'explain'))


class At(RefusingView):
    """GET ?path=…: an address's explanation page, every register, its history, what the viewer may do."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        return Response(explanations.detail(_path(request), request.user))


class Save(RefusingView):
    """POST {path, register, body, headline?, sources?, note?, consent?}: write or improve an explanation."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'contribute'

    def post(self, request):
        d = request.data
        require_types(d, lists=('sources',))
        sources = d.get('sources') or []
        explanations.save(request.user, _path(request, 'body'), str(d.get('register') or 'ar'), str(d.get('body') or ''),
                          headline=str(d.get('headline') or ''), sources=sources if isinstance(sources, list) else [],
                          note=str(d.get('note') or ''), consent=d.get('consent') in (True, 'true', '1'))
        return Response(explanations.detail(_path(request, 'body'), request.user), status=201)


class Check(RefusingView):
    """POST {path, register}: a reviewer of the text says the edit that waits is right as it stands."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'account'

    def post(self, request):
        explanations.check(request.user, _path(request, 'body'), str(request.data.get('register') or 'ar'))
        return Response(explanations.detail(_path(request, 'body'), request.user))


class Report(RefusingView):
    """POST {revision, reason, details?}: a reader reports a state of an explanation readers see."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'flags'

    def post(self, request):
        d = request.data
        require_types(d, ids=('revision',))
        explanations.report(request.user, d.get('revision'), reason=str(d.get('reason') or ''),
                            details=str(d.get('details') or ''))
        return Response({'ok': True}, status=201)


class Act(RefusingView):
    """POST {revision, act: remove|keep, rule?, note?}: a reviewer of the text removes a state or keeps a reported one."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'account'

    def post(self, request):
        d = request.data
        require_types(d, ids=('revision',))
        act = d.get('act')
        if act == 'remove':
            e = explanations.remove(request.user, d.get('revision'), str(d.get('rule') or ''), str(d.get('note') or ''))
        elif act == 'keep':
            e = explanations.keep(request.user, d.get('revision'), str(d.get('note') or ''))
        else:
            raise Refused('act', 'invalid')
        return Response(explanations.detail(e.path, request.user))


class Waiting(RefusingView):
    """GET: for a reviewer, the explanations with an edit to check or a state reported, in their area."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'account'

    def get(self, request):
        return Response({'items': explanations.waiting(request.user)})


class Helpful(RefusingView):
    """POST / DELETE {path, register}: «مفيد»."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'useful'

    def post(self, request):
        e = explanations.helpful(request.user, _path(request, 'body'), str(request.data.get('register') or 'ar'), True)
        return Response({'helpful': e.helpful_count, 'voted': True})

    def delete(self, request):
        e = explanations.helpful(request.user, _path(request, 'body'), str(request.data.get('register') or 'ar'), False)
        return Response({'helpful': e.helpful_count, 'voted': False})


class New(RefusingView):
    """GET: «جديد يهمك», the recent texts someone explained under a plain headline a reviewer checked."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        return generation.answer(['explain-new'], lambda: {'items': explanations.new_items()}, scopes=('corpus', 'explain'))


class Words(RefusingView):
    """GET: the words that open the law, each with whether its meaning has been written and checked, and that meaning
    (`means`, by register) so the list reads as a glossary."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        meanings = explanations.word_meanings()
        return Response({'concepts': [{**c, 'written': c['slug'] in meanings, 'means': meanings.get(c['slug'])}
                                      for c in concepts.load()]})


class Word(RefusingView):
    """GET /words/<slug>/: a word's page: its term, its meaning as people wrote it (checked), its topic."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request, slug):
        concept = concepts.find(slug)
        if concept is None:
            return Response({'errors': [{'field': 'slug', 'code': 'not_found'}]}, status=404)
        return Response({'concept': concept, **explanations.bundle_word(slug)})


class Week(RefusingView):
    """GET ?day=YYYY-MM-DD: the Bulletin's week holding that day, else its newest week (R13)."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        try:
            day = date.fromisoformat(request.query_params['day']) if request.query_params.get('day') else None
        except ValueError:
            raise Refused('day', 'invalid') from None
        return generation.answer(['week', day], lambda: week.week(day), scopes=('corpus', 'explain'))


class Card(RefusingView):
    """GET ?path=…|?answer=<id>, &shape=post|story, &register=: the picture to forward (R14): an article with its
    checked «باختصار», a text under its headline, or a question and its answer."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        q = request.query_params
        answer = str(q.get('answer') or '')
        shape = str(q.get('shape') or 'post')
        if shape not in cards.SHAPES:
            raise Refused('shape', 'invalid')
        c = cards.content(path=str(q.get('path') or ''), register=str(q.get('register') or 'ar'),
                          answer=int(answer) if re.fullmatch(r'[0-9]{1,12}', answer) else None)
        article = c['kind'] == 'article'

        def picture():
            try:
                found = cards.picture(shape, c, request)
            except drawing.Busy:
                return drawing.busy()
            response = FileResponse(open(found, 'rb'), content_type='image/png')
            # An article's card carries the article: counted, and kept by the reader's browser alone.
            response['Cache-Control'] = 'private, max-age=3600' if article else 'public, max-age=3600'
            return response
        # The article's words count against the day of reading, as on its text's page; a text's card or an answer's
        # holds people's words and a title.
        return reading.metered(request, picture, 1) if article else picture()
