"""Places (PL19–PL21 of the places review): GET /api/places/ the list, ?q= what a reader types; GET
/api/places/<slug>/ a place's profile; GET /api/places/<slug>/mentions/ the articles that name it, newest first, a page
at a time. Public, no session; kept by the generation."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.corpus.services import generation
from apps.opendata.throttles import PublicRate
from apps.places.services import finder


class PublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicRate]


class Places(PublicView):
    def get(self, request):
        q = request.query_params.get('q', '')[:80].strip()
        if q:
            return Response(generation.kept(['places-q', q], lambda: finder.typed(q)))
        return generation.answer(['places'], finder.listing)


class PlaceView(PublicView):
    def get(self, request, slug):
        found = generation.kept(['place', slug], lambda: finder.profile(slug))
        if found is None:
            return Response({'errors': [{'field': 'slug', 'code': 'not_found'}]}, status=404)
        return Response(found)


class Mentions(PublicView):
    def get(self, request, slug):
        p = request.query_params
        try:
            ask = finder.Ask.read(p)
        except ValueError as exc:
            return Response({'errors': [{'field': str(exc), 'code': 'invalid'}]}, status=400)
        found = generation.kept(['place-mentions', slug, *ask.key()], lambda: finder.mentions(slug, ask))
        if found is None:
            return Response({'errors': [{'field': 'slug', 'code': 'not_found'}]}, status=404)
        return Response(found)
