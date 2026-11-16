"""Who may write, vote and report (D3, D4, D5, and the choices of 29 Oct 2026).

- Writing needs the discussion open (D12), a proven email and no running pause. The first seven days allow five a
  day. What a newcomer writes no longer waits for a reviewer: a model reads every post first (check.py).
- Voices and pictures are off at launch (DISCUSSION_MEDIA, C1); once on, they open after three days and a first
  published contribution, and pictures wait for a reviewer until their author has 25 karma or is trusted (M8).
- A vote ranks only from a proven account three days old.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Action, Ban, Contribution, Trust
from apps.discussion.services import points

NEWCOMER_DAYS = 7
NEWCOMER_PER_DAY = 5
MEDIA_AFTER_DAYS = 3
VOTE_AFTER_DAYS = 3


def running_ban(user) -> Ban | None:
    now = timezone.now()
    return (Ban.objects.filter(user=user, ended_at=None).filter(Q(until=None) | Q(until__gt=now))
            .order_by('-started_at').first())


def _active(user) -> None:
    if not settings.DISCUSSION_OPEN:
        raise Refused('discussion', 'closed', 403)
    if user is None or not user.is_authenticated or user.deleted_at or not user.is_active:
        raise Refused('account', 'sign_in', 401)
    if running_ban(user):
        raise Refused('account', 'paused', 403)


def writer(user) -> None:
    _active(user)
    if not user.email_proven_at:
        raise Refused('email', 'not_proven', 403)


def voter(user) -> None:
    _active(user)


def published_count(user) -> int:
    """Contributions a reader saw: published once, whatever happened since apart from a removal."""
    return Contribution.objects.filter(author=user, held_at=None, removed_at=None).count()


def trusted(user) -> bool:
    return Trust.objects.filter(user=user, ended_at=None).exists()


def day_limit(user) -> None:
    """A newcomer's five a day: posts, comments and the explanations they write together."""
    from apps.explain.models import Revision

    now = timezone.now()
    if user.date_joined > now - timedelta(days=NEWCOMER_DAYS):
        since = now - timedelta(days=1)
        today = (Contribution.objects.filter(author=user, created_at__gte=since).count()
                 + Revision.objects.filter(author=user, created_at__gte=since).count())
        if today >= NEWCOMER_PER_DAY:
            raise Refused('account', 'day_limit', 429)


def consent(user, given: bool) -> None:
    """A model reads what is written before it is published, abroad: the first time asks for the account's agreement
    (law 09-08, art. 44), kept with its date. Posts, comments and explanations alike."""
    if settings.DISCUSSION_CHECK not in ('model', 'markers') or user.check_consent_at:
        return
    if not given:
        raise Refused('consent', 'required', 403)
    user.check_consent_at = timezone.now()
    user.save(update_fields=['check_consent_at'])


def media_open(user) -> bool:
    return (settings.DISCUSSION_MEDIA and user.date_joined <= timezone.now() - timedelta(days=MEDIA_AFTER_DAYS)
            and published_count(user) >= 1)


def may_voice(user) -> None:
    if not media_open(user):
        raise Refused('voice', 'not_yet', 403)


def may_picture(user) -> None:
    if not media_open(user):
        raise Refused('pictures', 'not_yet', 403)


def pictures_held(user) -> bool:
    return not trusted(user) and points.total(user) < points.PICTURES_FREE


def review_hours() -> float | None:
    """How long a held contribution waited before a reviewer published it, the median over the last week (W6)."""
    since = timezone.now() - timedelta(days=7)
    waits = sorted((a.created_at - a.contribution.created_at).total_seconds() / 3600
                   for a in Action.objects.filter(verb=Action.Verb.APPROVE, created_at__gte=since)
                   .exclude(contribution=None).select_related('contribution'))
    if not waits:
        return None
    middle = len(waits) // 2
    return round(waits[middle] if len(waits) % 2 else (waits[middle - 1] + waits[middle]) / 2, 1)


def vote_counts(user) -> bool:
    return bool(user.email_proven_at) and user.date_joined <= timezone.now() - timedelta(days=VOTE_AFTER_DAYS)


def standing(user) -> dict:
    """What the form needs to know before anyone types: may this person write, record, add a picture."""
    if not settings.DISCUSSION_OPEN:
        return {'can': False, 'why': 'discussion.closed', 'voice': False, 'pictures': False}
    if user is None or not user.is_authenticated:
        return {'can': False, 'why': 'account.sign_in', 'voice': False, 'pictures': False}
    try:
        writer(user)
    except Refused as exc:
        why = f'{exc.field}.{exc.code}'
        out = {'can': False, 'why': why, 'voice': False, 'pictures': False}
        if why == 'email.not_proven':
            # The form asks for the code in place (W1): where it was sent, half hidden.
            name, _, domain = user.email.partition('@')
            out['email_hint'] = f'{name[:1]}•••@{domain}'
        return out
    media = media_open(user)
    return {'can': True, 'why': None, 'voice': media, 'pictures': media, 'review_hours': review_hours(),
            # The first post asks for the agreement that a model reads it before it is published (law 09-08).
            'consent': settings.DISCUSSION_CHECK not in ('model', 'markers') or bool(user.check_consent_at)}
