from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.api.errors import JsonOnly, RefusingView
from apps.accounts.services.refusals import Refused
from apps.analytics import registry
from apps.analytics.services import record


class MeasureView(JsonOnly, RefusingView):
    """POST /api/measure/: a batch of measures from a page of the app (services/record.py), 204 with no body; a batch
    the registry refuses is 400 in the one error shape, and nothing of it is written. GET: what /privacy says of the
    measures (registry.public).

    No authentication at all: the door cannot know who is signed in, so a signed-in reader's batch is written as
    anyone's. It reads JSON alone (JsonOnly) and counts by network (the `measure` scope)."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'measure'

    def get(self, request):
        return Response(registry.public())

    def post(self, request):
        facts = record.facts_of(request)
        if record.ignored(facts):
            return Response(status=204)
        if len(request.body) > registry.MOST_BYTES:
            raise Refused('body', 'too_large')
        record.record(request.data, facts)
        return Response(status=204)
