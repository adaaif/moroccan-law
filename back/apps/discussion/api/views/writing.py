"""Writing in the discussion: a post or a comment, its edit and its deletion, «مفيد» and «أفادني», a report and a
takedown request, following, what the form checks while it is typed (the holds' patterns, similar questions), and
the voices and pictures a contribution carries."""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView, require_types
from apps.accounts.services.refusals import Refused
from apps.discussion.models import Contribution, Follow
from apps.discussion.services import compose, gates, holds, notices, reports, review, thread, votes
from apps.media.models import Clip, Picture, State
from apps.media.services import files, links, pictures
from apps.opendata.throttles import OPEN


def _list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        return [v for v in value.split(',') if v]
    return []


class ContributionsView(RefusingView):
    throttle_scope = 'contribute'

    def post(self, request):
        d = request.data
        require_types(d, words=('path', 'kind', 'title', 'body', 'about', 'quote'), ids=('parent',),
                      uuids=('voice', 'pictures'))
        c = compose.contribute(request.user, path=d.get('path', ''), kind=d.get('kind', ''), title=d.get('title', ''),
                               body=d.get('body', ''), about=d.get('about', ''), quote=d.get('quote', ''),
                               parent_id=d.get('parent') or None,
                               anonymous=d.get('anonymous') in (True, 'true', '1'), clip_id=d.get('voice') or None,
                               picture_ids=_list(d.get('pictures')), consent=d.get('consent') in (True, 'true', '1'),
                               insist=d.get('insist') in (True, 'true', '1'))
        return Response(_written(request.user, c), status=status.HTTP_201_CREATED)


def _written(user, c: Contribution) -> dict:
    """A contribution just written or edited, as its author's list shows it."""
    c = (Contribution.objects.select_related('author', 'clip', 'discussion', 'parent').prefetch_related(thread.pictures())
         .get(pk=c.pk))
    ctx, cites = thread.Context(user, [c]), thread.cites_of([c])
    return {**thread.card(c, ctx), **thread.where(c, user), 'cites': cites.get(c.pk, []), 'replies': [],
            'active_at': c.active_at or c.created_at}


class ContributionView(RefusingView):
    throttle_scope = 'contribute'

    def patch(self, request, pk):
        require_types(request.data, words=('body',))
        title = request.data.get('title')
        c = compose.edit(request.user, pk, request.data.get('body', ''), title if isinstance(title, str) else None,
                         insist=request.data.get('insist') in (True, 'true', '1'))
        return Response(_written(request.user, c))

    def delete(self, request, pk):
        compose.delete(request.user, pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsefulView(RefusingView):
    throttle_scope = 'useful'

    def post(self, request, pk):
        c = votes.useful(request.user, pk)
        return Response({'useful': c.useful_count, 'voted': True})

    def delete(self, request, pk):
        c = votes.not_useful(request.user, pk)
        return Response({'useful': c.useful_count, 'voted': False})


class AcceptView(RefusingView):
    throttle_scope = 'useful'

    def post(self, request, pk):
        votes.accept(request.user, pk)
        return Response({'accepted': True})

    def delete(self, request, pk):
        votes.unaccept(request.user, pk)
        return Response({'accepted': False})


class ReportView(RefusingView):
    throttle_scope = 'flags'

    def post(self, request, pk):
        d = request.data
        require_types(d, words=('reason', 'details'))
        reports.file(request.user, pk, reason=d.get('reason', ''), details=d.get('details', ''),
                     moment_ms=d.get('moment_ms'))
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


class TakedownView(RefusingView):
    """POST {details, contact}: «هذه المساهمة تذكرني», with or without an account (M11)."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN
    throttle_scope = 'flags'

    def post(self, request, pk):
        user = request.user if request.user.is_authenticated else None
        require_types(request.data, words=('details', 'contact'))
        reports.takedown(user, pk, details=request.data.get('details', ''), contact=request.data.get('contact', ''))
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


class FollowView(RefusingView):
    throttle_scope = 'account'
    def post(self, request):
        """{path}: a topic's place (/talk/family) or a post (/talk/family/12) the caller may open."""
        notices.follow(request.user, str(request.data.get('path', '')))
        return Response({'following': True})

    def delete(self, request):
        Follow.objects.filter(user=request.user, path=request.data.get('path', '')).delete()
        return Response({'following': False})


class CheckView(RefusingView):
    """POST {body}: what would hold these words (W2), by the same patterns the server holds with."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN
    throttle_scope = 'checks'

    def post(self, request):
        reasons, spans = holds.scan(str(request.data.get('body', ''))[:3000])
        return Response({'reasons': reasons, 'spans': spans})


class SimilarView(RefusingView):
    """POST {path: /talk/family, q}: the place's questions that share these words (W3). The words of a question being
    typed go in the body: an address is written in the server's logs, a body never (/privacy)."""
    permission_classes = [AllowAny]
    throttle_classes = OPEN
    throttle_scope = 'checks'

    def post(self, request):
        return Response({'questions': thread.similar(str(request.data.get('path', ''))[:300],
                                                     str(request.data.get('q', ''))[:600])})


# ── voices and pictures ────────────────────────────────────────────────────

class VoicesView(RefusingView):
    """POST multipart {voice, peaks}: a recording, checked and converted; a draft until a contribution carries it."""
    throttle_scope = 'uploads'

    def post(self, request):
        gates.writer(request.user)
        gates.may_voice(request.user)
        clip = files.upload_clip(request.user, request.FILES.get('voice'), request.data.get('peaks', '[]'))
        return Response({'id': str(clip.pk), 'duration_ms': clip.duration_ms, 'peaks': clip.peaks,
                         **links.clip(clip)}, status=status.HTTP_201_CREATED)


class VoiceView(RefusingView):
    permission_classes = [AllowAny]
    throttle_classes = OPEN

    def get(self, request, pk):
        """A fresh link, for a player resuming after its link ran out."""
        clip = Clip.objects.filter(pk=pk).exclude(state=State.ERASED).select_related('contribution').first()
        user = request.user if request.user.is_authenticated else None
        allowed = clip is not None and (
            clip.state == State.LIVE
            or (user and clip.owner_id == user.pk)
            or (user and hasattr(clip, 'contribution') and review.is_reviewer(user)
                and review.covers(user, clip.contribution.discussion.text_path)))
        if not allowed:
            raise Refused('voice', 'not_found', 404)
        return Response(links.clip(clip))

    def delete(self, request, pk):
        if not request.user.is_authenticated:
            raise Refused('account', 'sign_in', 401)
        files.erase([files.draft_of(Clip, request.user, pk)])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PicturesView(RefusingView):
    """POST multipart {picture}: a picture (already blurred where its author chose), re-encoded without metadata."""
    throttle_scope = 'uploads'

    def post(self, request):
        gates.writer(request.user)
        gates.may_picture(request.user)
        picture = pictures.upload(request.user, request.FILES.get('picture'))
        return Response(links.picture(picture), status=status.HTTP_201_CREATED)


class PictureView(RefusingView):
    throttle_scope = 'account'
    def delete(self, request, pk):
        files.erase([files.draft_of(Picture, request.user, pk)])
        return Response(status=status.HTTP_204_NO_CONTENT)
