"""Follows' API (R13 of the for-everyone review): anyone reads what changed in a list of addresses (a device's follows);
an account follows for letters."""
import json

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView
from apps.corpus.services import generation
from apps.follows.services import following, news
from apps.opendata.throttles import OPEN


class News(RefusingView):
    """GET ?path=…&path=…: each address the site holds, what changed it, newest first."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request):
        paths = request.query_params.getlist('path')
        # The list as one part of the key: joined with «:», «a:b» and «a», «b» were one key, and one answer.
        return generation.answer(['news', json.dumps(paths, ensure_ascii=False)], lambda: {'news': news.news(paths)})


class Follows(RefusingView):
    """GET: what the account follows. POST / DELETE {path}: follow, stop following."""
    permission_classes = [IsAuthenticated]
    throttle_scope = 'account'

    def get(self, request):
        return Response({'following': following.listed(request.user)})

    def post(self, request):
        return Response(following.follow(request.user, request.data.get('path', '')), status=201)

    def delete(self, request):
        following.unfollow(request.user, request.data.get('path', ''))
        return Response({'following': False})
