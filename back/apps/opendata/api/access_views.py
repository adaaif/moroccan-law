"""/api/access/: an account's request for access and its access. Every door answers the same body as GET, made by
`requests.body` (services/requests.py), after it acts."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView
from apps.opendata.services import access, requests


class AccessView(RefusingView):
    """GET: where access on request stands (its position, the terms' version, the sizes, the days to an answer), and
    the account's newest request and access; both null for a visitor."""

    permission_classes = [AllowAny]
    throttle_scope = 'account'

    def get(self, request):
        return Response(requests.body(request.user))


class RequestView(RefusingView):
    """POST {name, kind, purpose, wants_api, wants_data, runs_at, volume, commercial, terms, consent}: the request."""

    throttle_scope = 'access_request'

    def post(self, request):
        requests.send(request.user, request.data)
        return Response(requests.body(request.user), status=status.HTTP_201_CREATED)


class AnswerView(RefusingView):
    """POST {answer}: the answer to the line the staff asked; the request waits for the staff again."""

    throttle_scope = 'access_request'

    def post(self, request):
        requests.answer(request.user, request.data.get('answer'))
        return Response(requests.body(request.user))


class ChangeView(RefusingView):
    """POST {wants_api, wants_data, size, why}: a holder asks to change the access it holds; it waits for the staff like
    any request."""

    throttle_scope = 'access_request'

    def post(self, request):
        requests.change(request.user, request.data)
        return Response(requests.body(request.user), status=status.HTTP_201_CREATED)


class EndView(RefusingView):
    """POST: the holder ends their own access, and its keys with it."""

    throttle_scope = 'access_request'

    def post(self, request):
        access.end_own(request.user)
        return Response(requests.body(request.user))
