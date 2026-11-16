"""POST /api/quality/reports/ — a reader reports an error in an article. Public, throttled, nothing about the
reader kept. /api/quality/words/ — the doubtful words a visitor settles on «ساهم» (services/words.py)."""
from django.http import FileResponse, Http404
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.corpus.models import Text
from apps.corpus.services.addresses import split_path
from apps.accounts.api.errors import MOST_ID, JsonOnly, RefusingView
from apps.accounts.services.refusals import Refused
from apps.quality.models import PageTiming, Report, Suspect
from apps.opendata.throttles import OPEN, OpenRate
from apps.quality.services import corrections, words


class ReportCreate(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'reports'

    def post(self, request):
        data = request.data
        path = str(data.get('path', ''))[:300]
        kind = data.get('kind')
        quote = str(data.get('quote', ''))[:1000].strip()
        message = str(data.get('message', ''))[:2000].strip()
        errors = []
        uri, _eid = split_path(path)
        if not path.startswith('/ma/') or not Text.objects.filter(akn_uri=uri).exists():
            errors.append({'field': 'path', 'code': 'not_found'})
        if kind not in Report.Kind.values:
            errors.append({'field': 'kind', 'code': 'invalid'})
        if not (quote or message):
            errors.append({'field': 'message', 'code': 'required'})
        if errors:
            return Response({'errors': errors}, status=400)
        Report.objects.create(path=path, kind=kind, quote=quote, message=message)
        return Response({'ok': True}, status=201)


class TimingCreate(APIView):
    """POST /api/quality/timing/ {kind, ms}: one page load's time to its main content (row 20). Anonymous."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'timings'

    def post(self, request):
        kind, ms = request.data.get('kind'), request.data.get('ms')
        if kind not in PageTiming.Kind.values or not isinstance(ms, int) or not 0 < ms < 120_000:
            return Response({'errors': [{'field': 'ms', 'code': 'invalid'}]}, status=400)
        PageTiming.objects.create(kind=kind, ms=ms)
        return Response(status=204)



class Corrections(RefusingView):
    """GET /api/quality/corrections/: what was put right (R7), and for staff what waits for a person."""
    permission_classes = [AllowAny]
    throttle_classes = [OpenRate]

    def get(self, request):
        return Response(corrections.listed(request.user))


class MayDecide(BasePermission):
    def has_permission(self, request, view):
        return corrections.may_decide(request.user)


class Decide(RefusingView):
    """POST /api/quality/corrections/<id>/apply/ or …/reject/: one correction at a time, by staff given the right to
    change corrections (corrections.may_decide)."""
    permission_classes = [MayDecide]

    def post(self, request, pk, verb):
        if verb not in ('apply', 'reject'):
            raise Refused('verb', 'invalid', 404)
        (corrections.apply if verb == 'apply' else corrections.reject)(request.user, pk)
        return Response(corrections.listed(request.user))


class Words(RefusingView):
    """GET /api/quality/words/: how many words there are to settle, may be asked now, were answered enough, and the
    answers ever and today. Public; a minute in any cache."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OpenRate]

    def get(self, request):
        response = Response(words.figures())
        response['Cache-Control'] = 'public, max-age=60'
        return response


class NextWord(RefusingView):
    """GET /api/quality/words/next/?not=3,9,12: one word to settle, or {"word": null}. Never kept: each visitor is
    given a word of their own."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = OPEN
    throttle_scope = 'words_read'

    def get(self, request):
        response = Response({'word': words.one(words.skipped(request.query_params.get('not', '')))})
        response['Cache-Control'] = 'no-store'
        return response


class WordAnswer(JsonOnly, RefusingView):
    """POST /api/quality/words/<id>/ {"says": "word" | "suggestion" | "neither" | "unclear"}: one person's answer.
    Nothing about the person is kept. JSON only: a form on another site cannot answer in its visitors' names."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = OPEN
    throttle_scope = 'words'

    def post(self, request, pk):
        says = request.data.get('says') if isinstance(request.data, dict) else None
        words.say(pk if pk <= MOST_ID else 0, says if isinstance(says, str) else '')
        return Response({'ok': True}, status=201)


class Strip(RefusingView):
    """GET /api/quality/words/<id>/strip/: the printed line around the word, as WebP. Not counted in a reader's day of
    reading: it is a line, not a page."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OpenRate]

    def get(self, request, pk):
        suspect = Suspect.objects.select_related('page__document').filter(pk=pk if pk <= MOST_ID else 0).first()
        path = words.strip(suspect) if suspect else None
        if path is None:
            raise Http404
        response = FileResponse(open(path, 'rb'), content_type='image/webp')
        response['Cache-Control'] = 'public, max-age=86400'
        return response

