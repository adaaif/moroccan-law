"""The files themselves. A voice only by its signed link; a picture openly once live, by its signed link before
(its author's preview, a reviewer's queue). Nothing here decides who may have a link."""
from django.http import FileResponse, Http404
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.media.models import Clip, Picture, State
from apps.media.services import links, ranged, store
from apps.opendata.throttles import OpenRate


class ClipAudio(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OpenRate]

    def get(self, request, pk):
        if not links.clip_valid(request.query_params.get('t', ''), pk):
            raise Http404
        clip = Clip.objects.filter(pk=pk).exclude(state=State.ERASED).first()
        if clip is None or not clip.file_name:
            raise Http404
        try:
            return ranged.respond(request, store.path_of('voices', clip.file_name), 'audio/mp4')
        except (OSError, ValueError):
            raise Http404 from None


class PictureFile(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OpenRate]

    def get(self, request, pk, size):
        picture = Picture.objects.filter(pk=pk).exclude(state=State.ERASED).first()
        if picture is None or size not in ('full', 'thumb'):
            raise Http404
        live = picture.state == State.LIVE
        if not live and not links.picture_valid(request.query_params.get('t', ''), pk):
            raise Http404
        try:
            fh = store.path_of('pictures', picture.full_name if size == 'full' else picture.thumb_name).open('rb')
        except (OSError, ValueError):
            raise Http404 from None
        response = FileResponse(fh, content_type='image/webp')
        # A live picture may be cached a little; it can still be removed, so never for long.
        response['Cache-Control'] = 'public, max-age=600' if live else 'private, no-store, max-age=0'
        return response
