"""Pauses on writing (3, 7 or 28 days, or for good with a second eye; never shortened) and the one written appeal
against a removal or a pause, decided by someone other than who acted."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import APPEAL_MAX, Action, Appeal, Ban, Contribution, Notice, Rule
from apps.discussion.services import notices, places
from apps.discussion.services.review.acts import restore
from apps.discussion.services.review.reviewers import _contribution, _ledger, _may_decide_appeal, covers

BAN_DAYS = (3, 7, 28)


def _days(days) -> int | None:
    """3, 7 or 28, or None for good ('permanent'). Missing is refused: it read as «for good»."""
    if days == 'permanent':
        return None
    if days is None or days == '':
        raise Refused('days', 'required')
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise Refused('days', 'invalid') from None
    if days not in BAN_DAYS:
        raise Refused('days', 'invalid')
    return days


def pause(user, pk, *, days, rule: str, note: str = '') -> Ban:
    """Through one of their contributions: the reviewer never needs the author's name. Staff pause for good at
    once; a reviewer's «for good» runs 28 days until a second reviewer or staff confirms. A pause never shortens one
    that runs: one that ends later, a permanent one, or one asked for good, stands (a three-day pause replaced a
    permanent one); a second reviewer confirms what was asked for good."""
    c = _contribution(user, pk)
    if rule not in Rule.values:
        raise Refused('rule', 'required')
    days = _days(days)
    permanent = days is None
    now = timezone.now()
    until = None if permanent and user.is_staff else now + timedelta(days=28 if permanent else days)
    with transaction.atomic():
        running = list(Ban.objects.select_for_update().filter(user=c.author, ended_at=None)
                       .filter(Q(until=None) | Q(until__gt=now)))
        if any(b.until is None or b.permanent_asked_by_id or (until is not None and b.until >= until) for b in running):
            raise Refused('pause', 'longer_running', 409)
        Ban.objects.filter(user=c.author, ended_at=None).update(ended_at=now)
        if permanent and not user.is_staff:
            ban = Ban.objects.create(user=c.author, until=now + timedelta(days=28), permanent_asked_by=user,
                                     rule=rule, note=note, by=user, via=c)
            _ledger(Action.Verb.BAN_ASK, user, c=c, rule=rule, note=note)
        else:
            ban = Ban.objects.create(user=c.author, until=None if permanent else now + timedelta(days=days),
                                     rule=rule, note=note, by=user, via=c)
            _ledger(Action.Verb.BAN, user, c=c, rule=rule, note=note)
        notices.notify(c.author, Notice.Kind.BANNED, contribution=c, path=places.notice_path(c), detail=rule)
    return ban


def _ban(user, pk) -> Ban:
    ban = Ban.objects.filter(pk=pk, ended_at=None).select_related('via__discussion', 'by').first()
    if ban is None:
        raise Refused('pause', 'not_found', 404)
    if not (user.is_staff or (ban.via and covers(user, ban.via.discussion.text_path))):
        raise Refused('review', 'not_reviewer', 403)
    # Nobody decides about their own pause: a paused moderator read its number on their account page and lifted it.
    if ban.user_id == user.id:
        raise Refused('review', 'own', 403)
    return ban


def confirm_permanent(user, pk, note: str = '') -> Ban:
    ban = _ban(user, pk)
    if ban.permanent_asked_by_id is None:
        raise Refused('review', 'nothing_waiting', 409)
    if ban.permanent_asked_by_id == user.id:
        raise Refused('review', 'second_eye', 409)
    with transaction.atomic():
        ban.until, ban.permanent_asked_by = None, None
        ban.save(update_fields=['until', 'permanent_asked_by'])
        _ledger(Action.Verb.BAN_CONFIRM, user, c=ban.via, target=ban.user, rule=ban.rule, note=note)
    return ban


def lift(user, pk, note: str = '', *, by_appeal: bool = False) -> Ban:
    """Lift a pause. What staff set, and a pause confirmed for good (two people), only staff lift: one moderator undid
    what took two. An appeal is decided as appeals are, by someone other than who acted."""
    ban = Ban.objects.get(pk=pk) if by_appeal else _ban(user, pk)
    if not by_appeal and not user.is_staff and (ban.until is None or (ban.by is not None and ban.by.is_staff)):
        raise Refused('review', 'staff_only', 403)
    with transaction.atomic():
        ban.ended_at = timezone.now()
        ban.save(update_fields=['ended_at'])
        _ledger(Action.Verb.UNBAN, user, c=ban.via, target=ban.user, rule=ban.rule, note=note)
    return ban


# ── appeals ────────────────────────────────────────────────────────────────

def appeal(user, *, contribution_id=None, ban_id=None, text: str) -> Appeal:
    text = (text or '').strip()
    if not text:
        raise Refused('text', 'required')
    if len(text) > APPEAL_MAX:
        raise Refused('text', 'too_long')
    target = {}
    if contribution_id:
        c = Contribution.objects.filter(pk=contribution_id, author=user).exclude(removed_at=None).first()
        if c is None or c.erased_at:
            raise Refused('contribution', 'not_found', 404)
        target['contribution'] = c
    else:
        ban = Ban.objects.filter(pk=ban_id, user=user, ended_at=None).first()
        if ban is None:
            raise Refused('pause', 'not_found', 404)
        target['ban'] = ban
    try:
        with transaction.atomic():
            return Appeal.objects.create(user=user, text=text, **target)
    except IntegrityError:
        raise Refused('appeal', 'used', 409) from None


def decide_appeal(user, pk, outcome: str, note: str = '') -> Appeal:
    a = Appeal.objects.filter(pk=pk, decided_at=None).select_related('contribution__discussion', 'ban__via').first()
    if a is None:
        raise Refused('appeal', 'not_found', 404)
    if not _may_decide_appeal(user, a):
        raise Refused('review', 'second_eye', 403)
    if outcome not in Appeal.Outcome.values:
        raise Refused('outcome', 'invalid')
    with transaction.atomic():
        a.outcome, a.decided_at, a.decided_by = outcome, timezone.now(), user
        a.save(update_fields=['outcome', 'decided_at', 'decided_by'])
        lifted = outcome == Appeal.Outcome.LIFTED
        if lifted and a.contribution_id:
            restore(user, a.contribution_id, note, by_appeal=True)
        elif lifted and a.ban_id and a.ban.ended_at is None:
            lift(user, a.ban_id, note, by_appeal=True)
        via = a.contribution or a.ban.via
        _ledger(Action.Verb.APPEAL_LIFT if lifted else Action.Verb.APPEAL_KEEP, user, c=via, target=a.user,
                note=note)
        notices.notify(a.user, Notice.Kind.APPEAL, contribution=a.contribution,
                       path=via.discussion.path if via else '', detail=outcome)
    return a
