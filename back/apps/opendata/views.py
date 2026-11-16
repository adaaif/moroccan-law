"""The database's door, under /api/open/:

- GET /api/open/: the newest edition's manifest, with its own SHA-256 and every edition's dated hash;
- GET /api/open/latest/<file> and /api/open/<date>/<file>: a file of an edition;
- GET /api/open/<date>/RECEIPT.txt: the holder's receipt for their copy;
- POST /api/open/ticket/: a signed link to one file, good for ten minutes, for the browser to follow;
- GET /api/open/about/: the figures «عن «قانون»» shows, whatever the position.

The position (services/gate.py) decides: `closed`, everything but the figures answers 403 `open_data.closed`; `open`,
every file goes to anyone; `request`, the files that describe an edition go to anyone and the data files only to an
access that includes the database (services/downloads.py). Django decides; with OPEN_DATA_ACCEL set, nginx sends the
file (X-Accel-Redirect to its internal location, resumable), and without it Django streams it."""
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.accounts.api.errors import errors_response
from apps.opendata.services import downloads, editions, gate, keys
from apps.opendata.services.about import figures
from apps.opendata.throttles import PublicRate, ScopedRate
from config.saved import file_name


class OpenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicRate]


def closed():
    if gate.position() == gate.CLOSED:
        return errors_response([('open_data', 'closed')], status.HTTP_403_FORBIDDEN)
    return None


def refused(refusal: downloads.Refusal) -> Response:
    """A refusal that depends on who asked: never kept for anyone else."""
    response = errors_response([(refusal.field, refusal.code)], refusal.status)
    if refusal.retry:
        response['Retry-After'] = str(refusal.retry)
    response['Cache-Control'] = 'private'
    return response


def _attachment(edition, name: str) -> str:
    return f'{edition.date}-{name}'


def _send(edition, name: str) -> HttpResponse:
    """A data file: nginx sends it when OPEN_DATA_ACCEL names its internal location, else Django streams it. Never kept
    by a browser or a proxy."""
    accel = settings.OPEN_DATA_ACCEL.rstrip('/')
    if accel:
        response = HttpResponse(content_type=editions.DATA[name])
        response['X-Accel-Redirect'] = f'{accel}/{edition.date}/{name}'
        response['Content-Disposition'] = f'attachment; filename="{file_name(_attachment(edition, name))}"'
    else:
        response = FileResponse(open(edition.folder / name, 'rb'), content_type=editions.DATA[name],
                                as_attachment=True, filename=file_name(_attachment(edition, name)))
    response['Cache-Control'] = 'no-store'
    return response


def _describe(edition, name: str) -> HttpResponse:
    """A file that describes an edition: small, the same for everyone."""
    try:
        data = (edition.folder / name).read_bytes()
    except OSError:
        raise Http404 from None
    return HttpResponse(data, content_type=editions.DESCRIBE[name])


class Manifest(OpenView):
    def get(self, request):
        if answer := closed():
            return answer
        edition = editions.latest()
        if edition is None:
            raise Http404
        return Response({**edition.manifest, 'sha256': edition.sha256, 'editions': editions.history()})


class EditionFile(OpenView):
    # The account is read only when a data file or the receipt asks who is calling (services/downloads.py), not before
    # the view as DRF does: a token that no longer holds never stands between anyone and a file that describes an
    # edition. When it is read, such a token is the 401 of every signed-in door.
    authentication_classes = [JWTAuthentication]

    def perform_authentication(self, request):
        pass

    def get(self, request, edition, name):
        if answer := closed():
            return answer
        found = editions.find(edition)
        if found is None or (name not in editions.DESCRIBE and name not in editions.DATA and name != downloads.RECEIPT):
            raise Http404
        if name in editions.DESCRIBE:
            return _describe(found, name)
        try:
            if name in editions.DATA and gate.position() == gate.OPEN:
                keys.holder(request)            # a key that opens nothing is refused here too
                return _send(found, name)
            taker = downloads.taker(request, request.query_params.get('t', ''), found, name)
            if name == downloads.RECEIPT:
                response = HttpResponse(downloads.receipt(taker, found), content_type='text/plain; charset=utf-8')
                response['Content-Disposition'] = f'inline; filename="{file_name(_attachment(found, name))}"'
                response['Cache-Control'] = 'private'
                return response
            if request.method != 'HEAD':       # a look at the file's size takes nothing
                downloads.give(taker, found, name)
        except keys.Refused as e:
            return refused(downloads.Refusal(status.HTTP_401_UNAUTHORIZED, 'key', e.code))
        except downloads.Refusal as e:
            return refused(e)
        return _send(found, name)


class Ticket(APIView):
    """POST {"file", "edition": "latest"} → {"url"}: a link to one file for the signed-in account's access."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRate]
    throttle_scope = 'open_ticket'

    def post(self, request):
        if answer := closed():
            return answer
        try:
            url = downloads.ticket(request.user, request.data.get('edition', 'latest'), request.data.get('file'))
        except downloads.Refusal as e:
            return refused(e)
        return Response({'url': url})


class About(OpenView):
    def get(self, request):
        return Response(figures())
