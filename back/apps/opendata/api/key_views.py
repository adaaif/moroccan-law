"""An access's keys and their use, for the signed-in account that holds it.

GET /api/access/keys/: the live keys (never a key itself), the limits, today's use and the last 30 days.
POST /api/access/keys/ {"name"}: a new key, given in this answer and never again. DELETE /api/access/keys/<id>/: end
one. 403 (`access`, `none`) without a usable access; 409 (`keys`, `full`) with ACCESS_KEYS live keys."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView
from apps.opendata.services import keys


class AccountKeys(RefusingView):
    permission_classes = [IsAuthenticated]
    throttle_scope = 'access_keys'


class Keys(AccountKeys):
    def get(self, request):
        return Response(keys.shown(request.user))

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        response = Response(keys.make(request.user, data.get('name') or ''), status=status.HTTP_201_CREATED)
        # The key is in this answer alone: no cache may keep it.
        response['Cache-Control'] = 'no-store'
        return response


class Key(AccountKeys):
    def delete(self, request, pk):
        keys.drop(request.user, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
