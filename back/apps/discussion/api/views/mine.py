"""A person's own: what their account page shows of the discussion, their notices seen, their appeals, the header's
dot, and a letter's stop link."""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView, require_types
from apps.accounts.services.refusals import Refused
from apps.discussion.models import Appeal, Contribution, Follow, Notice
from apps.discussion.services import gates, notices, points, reports, review, thread
from apps.opendata.throttles import OPEN


class MineView(RefusingView):
    """GET: what the account page shows of the discussion: notices, contributions (held and removed ones too, with
    the rule), reports and what came of them, a running pause, the karma, what is followed."""
    throttle_scope = 'account'

    def get(self, request):
        user = request.user
        rows = list(Contribution.objects.filter(author=user, erased_at=None, deleted_at=None)
                    .select_related('discussion', 'parent', 'author', 'clip', 'appeal').prefetch_related(thread.pictures())
                    .order_by('-created_at')[:50])
        ctx = thread.Context(user, rows)
        ban = gates.running_ban(user)
        total = points.total(user)
        following = list(Follow.objects.filter(user=user).order_by('-created_at').values_list('path', flat=True)[:50])
        labels = thread._labels([c.discussion.path for c in rows] + following, user)

        return Response({
            'standing': {**gates.standing(user), 'karma': total,
                         'reviewer': review.is_reviewer(user), 'staff': user.is_staff},
            'notices': notices.grouped(user),
            'unseen': Notice.objects.filter(user=user, seen_at=None).count(),
            'contributions': [{**thread.card(c, ctx), 'path': c.discussion.path, 'label': labels[c.discussion.path],
                               'post_title': thread.where(c, user)['post_title'],
                               'removed': bool(c.removed_at),
                               'rule': c.removed_rule or None,
                               'appeal': _appeal(c.appeal) if hasattr(c, 'appeal') else None}
                              for c in rows],
            'reports': [{'reason': r.reason, 'status': r.status, 'created_at': r.created_at,
                         'path': r.contribution.discussion.path} for r in reports.mine(user)[:20]],
            'pause': {'id': ban.pk, 'until': ban.until, 'rule': ban.rule,
                      'appeal': _appeal(ban.appeal) if hasattr(ban, 'appeal') else None} if ban else None,
            'following': [{'path': p, 'label': labels[p]} for p in following],
        })


def _appeal(a: Appeal) -> dict:
    return {'created_at': a.created_at, 'decided': bool(a.decided_at), 'outcome': a.outcome or None}


class NoticesSeenView(RefusingView):
    throttle_scope = 'account'
    def post(self, request):
        Notice.objects.filter(user=request.user, seen_at=None).update(seen_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)


class AppealsView(RefusingView):
    throttle_scope = 'flags'

    def post(self, request):
        d = request.data
        require_types(d, words=('text',), ids=('contribution', 'pause'))
        review.appeal(request.user, contribution_id=d.get('contribution') or None, ban_id=d.get('pause') or None,
                      text=d.get('text', ''))
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


class UnseenView(RefusingView):
    """GET: the header's dot (R2) and, for a reviewer, what waits for them (M10)."""
    throttle_scope = 'account'

    def get(self, request):
        # The header's menu (30 Oct 2026) names the reader's karma and, for a moderator, their desk.
        return Response({'unseen': Notice.objects.filter(user=request.user, seen_at=None).count(),
                         'review': review.waiting_counts(request.user),
                         'reviewer': review.is_reviewer(request.user),
                         'karma': points.total(request.user)})


class LettersStopView(RefusingView):
    """A letter's stop link (R3). GET reads what it would stop; POST {t, scope} stops it. A mail provider's
    one-click POST (RFC 8058) carries t and scope=all in the address."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = OPEN
    throttle_scope = 'flags'

    def get(self, request):
        from apps.accounts.services import mail

        found = mail.read_stop(request.query_params.get('t', ''))
        if found is None:
            raise Refused('token', 'invalid')
        return Response({'path': found[1], 'label': notices.label(found[1], found[0]) if found[1] else ''})

    def post(self, request):
        require_types(request.data, words=('t', 'scope'))
        token = request.data.get('t') or request.query_params.get('t', '')
        scope = request.data.get('scope') or request.query_params.get('scope', 'path')
        return Response(notices.stop(token, scope))
