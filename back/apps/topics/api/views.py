"""Topics (R2 of the for-everyone review, F16 of the family plan): GET /api/topics/ the list; GET /api/topics/<slug>/ one
topic with what its folder adds; GET /api/topics/<slug>/<kind>/<key>/ a journey, checklist, page, the reform or a
series; POST /api/topics/helped/ «هل ساعدك هذا؟». Public, no session."""
import re
from datetime import date

from django.conf import settings
from django.db.models import F
from django.http import FileResponse, Http404
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.corpus.services import generation
from apps.opendata.throttles import ByNetwork, PublicRate
from apps.topics.models import Helped, ToolUse
from apps.topics.services import kit, topics


class PublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicRate]


class Topics(PublicView):
    """The life topics, in the order the home shows them."""

    def get(self, request):
        return Response([topics.summary(t) for t in topics.load()])


class Calendar(PublicView):
    """GET /api/topics/calendar/: the law's calendar around today across the topics (the home, 30 Oct 2026): the next
    dated changes and the latest. Kept by the topics' files, the drafts' setting and the day."""

    def get(self, request):
        from django.utils import timezone

        today = timezone.localdate().isoformat()
        files = tuple(kit.stamp(t['slug']) for t in topics.load())
        return Response(generation.kept(['topics-calendar', today, settings.SHOW_DRAFTS, files], lambda: kit.calendar(today)))


class Moments(PublicView):
    """GET /api/topics/moments/: each topic's moments in people's words with the line that answers them, how many, its
    next change (the topics page, 30 Oct 2026). Kept by the topics' files, the drafts' setting and the day."""

    def get(self, request):
        from django.utils import timezone

        today = timezone.localdate().isoformat()
        files = tuple(kit.stamp(t['slug']) for t in topics.load())
        return Response(generation.kept(['topics-moments', today, settings.SHOW_DRAFTS, files], lambda: kit.moments(today)))


class Cites(PublicView):
    """GET /api/topics/cites/?text=/ma/loi/65-99: for each article of a text, the topic items that cite it (HM20 of
    the hard-moment review): «يجيب عنها: الشغل · شنو كيتسالني؟ · …» under the article. Keyed by the article's
    address; the map is built once a process from the folders, then kept by the folders' files and the drafts' setting."""

    def get(self, request):
        text = request.query_params.get('text') or ''
        if not re.fullmatch(r'/ma(?:/[\w.-]+){2,3}', text):
            return Response({'errors': [{'field': 'text', 'code': 'invalid'}]}, status=400)
        files = tuple(kit.stamp(t['slug']) for t in topics.load())
        return Response(generation.kept(['topic-cites', text, settings.SHOW_DRAFTS, files], lambda: kit.cites_of(text)))


class Topic(PublicView):
    """One life topic: its situations, codes, words, talk and recent changes, and what its own folder adds."""

    def get(self, request, slug):
        topic = topics.find(slug)
        if not topic:
            raise Http404
        # The law's part kept by the corpus and the topic's files; its conversation by the discussion, a minute at most
        # (its voices' links are signed); the folder's hub too, by the corpus, its files and the day (S14 of the
        # performance audit). The hub was read in each worker's memory alone: each worker read the folder's YAML
        # once, about a second, and a reader opening a topic met a worker that had not yet.
        files = (kit.stamp(slug), generation.files(topics.DATA))
        page = generation.kept(['topic', slug, settings.SHOW_DRAFTS, files], lambda: topics.detail(topic, talk=False))
        talk = generation.kept(['topic-talk', slug, files], lambda: topics.talk_of(slug), scopes=('corpus', 'talk'),
                               timeout=60)
        module = generation.kept(['topic-hub', slug, settings.SHOW_DRAFTS, files[0]], lambda: kit.hub(slug))
        return Response({**{k: v for k, v in page.items() if k != 'recent'}, 'talk': talk, 'recent': page['recent'],
                         'module': module})


class Places(PublicView):
    """«أرضي فالجريدة الرسمية» (the land review, M8): GET /api/topics/land/places/?q= the BO's land texts that name
    a commune, a property, a title or requisition number or a name as printed, newest first, with their rows. Kept by
    the corpus's generation and the words typed."""

    def get(self, request):
        from apps.topics.services import places
        q = str(request.query_params.get('q', ''))[:80]
        return Response(generation.kept(['land-places', q], lambda: places.find(q)))


class Card(PublicView):
    """The picture a link to a topic's page shows (U15 of the Moroccan-design review)."""

    def get(self, request, slug):
        from apps.topics.services.cards import card_path
        item = request.query_params.get('item', '')
        if item and not re.fullmatch(r'[a-z]+/[a-z0-9-]+', item):
            raise Http404
        path = card_path(slug, item)
        if path is None:
            raise Http404
        response = FileResponse(open(path, 'rb'), content_type='image/png')
        response['Cache-Control'] = 'public, max-age=86400'
        return response


class TopicPage(PublicView):
    def get(self, request, slug, kind, key):
        if kind not in kit.KINDS or not topics.find(slug):
            raise Http404

        def build():
            found = kit.page(slug, kind, key)
            if found is None:
                raise Http404
            return found
        return generation.answer(['topic-item', slug, kind, key, settings.SHOW_DRAFTS, kit.stamp(slug)], build)


class HelpedRate(ByNetwork, AnonRateThrottle):
    rate = '60/hour'


class HelpedView(PublicView):
    throttle_classes = [HelpedRate]

    def post(self, request):
        d = request.data
        path = str(d.get('path', ''))[:300]
        reason = str(d.get('reason', ''))
        if not path.startswith('/topics/') or not isinstance(d.get('helped'), bool):
            return Response({'errors': [{'field': 'path', 'code': 'invalid'}]}, status=400)
        if reason not in Helped.Reason.values:
            return Response({'errors': [{'field': 'reason', 'code': 'invalid'}]}, status=400)
        Helped.objects.create(path=path, helped=d['helped'], reason=reason)
        return Response(status=201)


class MayReview(BasePermission):
    """Staff given the review desk's right (topics.review_topic); a superuser has every right."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff and user.has_perm('topics.review_topic'))


REVIEW_REFS_MAX = 100


class Review(APIView):
    """GET /api/topics/<slug>/review/: everything a reviewer reads, drafts included (R1 of the road tools review);
    POST {refs}: record that the signed-in reviewer checked them, under their account's name, as `manage.py
    approve_topic` does. Only items the topic has. Reviewers only."""
    permission_classes = [MayReview]

    def get(self, request, slug):
        found = kit.review(slug) if topics.find(slug) else None
        if found is None:
            raise Http404
        return Response(found)

    def post(self, request, slug):
        refs = request.data.get('refs')
        if not topics.find(slug) or kit.load(slug) is None:
            raise Http404
        if (not isinstance(refs, list) or not 0 < len(refs) <= REVIEW_REFS_MAX
                or not all(isinstance(r, str) and '/' in r and len(r) <= 120 for r in refs)):
            return Response({'errors': [{'field': 'refs', 'code': 'invalid'}]}, status=400)
        try:
            written = kit.record_checks(slug, refs, request.user.shown_name, date.today().isoformat(), user=request.user)
        except KeyError:
            return Response({'errors': [{'field': 'refs', 'code': 'not_found'}]}, status=400)
        return Response({'checked': written})


class UseRate(ByNetwork, AnonRateThrottle):
    rate = '240/hour'


class UseView(PublicView):
    """POST /api/topics/use/ {path, event}: one count more for that page and event today (M1). The path is a topic's
    page without its query; anything else is refused, so no input ever reaches the server."""
    throttle_classes = [UseRate]

    def post(self, request):
        path, event = str(request.data.get('path', ''))[:120], str(request.data.get('event', ''))
        if not re.fullmatch(r'/topics/[a-z-]+(/[a-z-]+){0,2}/?|/search', path) or event not in ToolUse.Event.values:
            return Response({'errors': [{'field': 'path', 'code': 'invalid'}]}, status=400)
        row, _ = ToolUse.objects.get_or_create(on=date.today(), path=path.rstrip('/') or '/', event=event)
        ToolUse.objects.filter(pk=row.pk).update(count=F('count') + 1)
        return Response(status=204)
