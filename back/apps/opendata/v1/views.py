"""The versioned API's reads, /api/v1/: the law for outside programs, small and stable, over the services the
assistants' server answers with (apps/mcp/services/law), so one fix serves both doors. Only the Bulletin's texts and
articles, their versions and standing, each with its Bulletin page and its link: never a draft, never the discussion.

Every read but the OpenAPI file needs a key (X-Api-Key) whose access includes the API:
- no key: 401 (`key`, `required`); a key that opens nothing: 401 (`key`, `invalid` | `ended` | `expired`);
- while the database and the keyed API are closed (services/gate.py): 403 (`access`, `closed`); an access without
  the API: 403 (`access`, `no_api`);
- then one call is counted on the access's minute and day before the work, and the articles it gave after it
  (services/usage.py); past a limit, 429 (`key`, `minute` | `calls` | `articles`) with Retry-After.
What the services refuse (`law.Problem`, by its code; `Refused`) is a 400, or a 404 for what is not there. Every answer
to a key that opens something carries RateLimit-Policy and RateLimit and is private. No JWT is read and no CORS header
is sent: a key belongs on a server, never in a web page."""
from functools import cache
from pathlib import Path

from django.http import HttpResponse
from django.views.decorators.http import require_safe
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.services.refusals import Refused
from apps.mcp.services import law
from apps.opendata.middleware import refusal
from apps.opendata.services import changes, gate, keys, usage
from apps.opendata.v1 import deprecated
from config.malformed import JSONParser

OPENAPI = Path(__file__).with_name('openapi.yaml')
# The longest a program may send of each, as the assistants' tools take them.
QUERY_MOST, ID_MOST, START_MOST, ISSUE_MOST, REFERENCE_MOST = 300, 300, 20, 40, 200
YES, NO = ('1', 'true', 'yes'), ('', '0', 'false', 'no')


def _most(field: str, value: str, most: int) -> str:
    if len(value) > most:
        raise Refused(field, 'too_long')
    return value


def _problem(problem: law.Problem):
    field, _, code = (problem.code or 'request.invalid').partition('.')
    return refusal(field, code, 404 if code == 'not_found' else 400)


class Read(APIView):
    """A read a key opens. `read(request, **kwargs)` gives (the answer's data, the law's articles it holds)."""
    authentication_classes = []        # a key, never the site's sign-in
    permission_classes = [AllowAny]    # the key is read in `answer`, where its refusals keep the one shape
    throttle_classes = []              # the access's own limits count each call instead
    parser_classes = [JSONParser]
    door = ''

    def read(self, request, **kwargs) -> tuple[dict, int]:
        raise NotImplementedError

    def answer(self, request, **kwargs):
        """The read's answer, and on every one of them, refusals included, whether the read is going."""
        route = request.resolver_match.url_name if request.resolver_match else None
        return deprecated.mark(route, self._keyed(request, kwargs))

    def _keyed(self, request, kwargs):
        try:
            holder = keys.holder(request)
        except keys.Refused as refused:
            return refusal('key', refused.code, 401)
        if holder is None:
            return refusal('key', 'required', 401)
        if gate.position() == gate.CLOSED:
            return refusal('access', 'closed', 403)
        if not holder.api:
            return refusal('access', 'no_api', 403)
        try:
            usage.charge(holder, self.door)
        except usage.Limit as limit:
            response = refusal('key', limit.code, 429, limit.retry)
        else:
            response = self._worked(request, holder, kwargs)
        for name, value in usage.headers(holder).items():
            response[name] = value
        return response

    def _worked(self, request, holder, kwargs):
        try:
            data, served = self.read(request, **kwargs)
        except Refused as refused:
            return refusal(refused.field, refused.code, refused.status)
        except law.Problem as problem:
            return _problem(problem)
        usage.spend(holder, served)
        response = Response(data)
        response['Cache-Control'] = 'private'
        return response


class Get(Read):
    def get(self, request, **kwargs):
        return self.answer(request, **kwargs)


class Search(Get):
    """GET /api/v1/search?q=: the site's search, the best ten articles and texts."""
    door = 'v1.search'

    def read(self, request):
        return law.search(_most('q', request.query_params.get('q', ''), QUERY_MOST), via='v1', log=False), 0


class Texts(Get):
    """GET /api/v1/texts/<path>: an article whole, a text with its outline, or a Bulletin issue."""
    door = 'v1.text'

    def read(self, request, path):
        return law.fetch(_most('id', path, ID_MOST))


class Articles(Get):
    """GET /api/v1/articles/<path>?start=&count=&on=&french=: a run of a text's articles, as they read on a day."""
    door = 'v1.articles'

    def read(self, request, path):
        given = request.query_params
        count = given.get('count', '')
        if count and not (count.isascii() and count.isdigit() and 1 <= int(count) <= law.MAX_RUN):
            raise Refused('count', 'invalid')
        french = given.get('french', '').strip().lower()
        if french not in YES + NO:
            raise Refused('french', 'invalid')
        return law.articles(_most('id', path, ID_MOST), start=_most('start', given.get('start', ''), START_MOST),
                            count=int(count or 10), on=given.get('on', ''), french=french in YES)


class References(Read):
    """POST /api/v1/references {"references": […], "since"}: each reference resolved, with its standing."""
    door = 'v1.references'

    def post(self, request):
        return self.answer(request)

    def read(self, request):
        try:
            body = request.data
        except UnsupportedMediaType:
            raise Refused('body', 'unsupported_media_type', 415) from None
        except ParseError:
            raise Refused('body', 'invalid') from None
        references, since = body.get('references', []), body.get('since', '')
        if not isinstance(references, list) or not all(isinstance(r, str) for r in references):
            raise Refused('references', 'invalid')
        if any(len(r) > REFERENCE_MOST for r in references):
            raise Refused('references', 'too_long')
        if not isinstance(since, str):
            raise Refused('since', 'invalid')
        return law.check_references(references, since)[1], 0


class Bulletin(Get):
    """GET /api/v1/bulletin/ (the latest week's issues) and /api/v1/bulletin/<issue>."""
    door = 'v1.bulletin'

    def read(self, request, issue=''):
        return law.bulletin(_most('issue', issue, ISSUE_MOST)), 0


class Changes(Get):
    """GET /api/v1/changes?since=YYYY-MM-DD&cursor=: what the Bulletin published and changed since a day."""
    door = 'v1.changes'

    def read(self, request):
        given = request.query_params
        return changes.since(given.get('since', ''), given.get('cursor', '')), 0


@cache
def _openapi() -> bytes:
    return OPENAPI.read_bytes()


@require_safe
def openapi(request):
    """GET /api/v1/openapi.yaml: the contract, as written, to anyone."""
    response = HttpResponse(_openapi(), content_type='application/yaml; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    return response
