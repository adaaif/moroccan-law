"""Who reviews where: a reviewer and their area, who may decide an appeal, staff appointing and ending moderators;
and what every act shares: its row in the ledger, the contribution it acts on (never one's own), its reports
closed."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import NOTE_MAX, Action, Appeal, Contribution, Report, Reviewer


def reviewer(user) -> Reviewer | None:
    if user is None or not user.is_authenticated:
        return None
    return Reviewer.objects.filter(user=user, ended_at=None).first()


def is_reviewer(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or reviewer(user)))


def covers(user, text_path: str) -> bool:
    if user.is_staff:
        return True
    r = reviewer(user)
    return r is not None and (not r.text_paths or text_path in r.text_paths)


def _area(user, r: Reviewer | None = None):
    """The contributions a reviewer reviews, as a filter. `r`: their row, when the caller has read it."""
    if user.is_staff:
        return Q()
    r = r or reviewer(user)
    if r is None:
        raise Refused('review', 'not_reviewer', 403)
    return Q(discussion__text_path__in=r.text_paths) if r.text_paths else Q()


def _acted_by(a: Appeal):
    if a.contribution_id:
        return a.contribution.removed_by_id
    return a.ban.by_id


def _may_decide_appeal(user, a: Appeal) -> bool:
    if _acted_by(a) == user.id or a.user_id == user.id:
        return False
    if user.is_staff:
        return True
    via = a.contribution if a.contribution_id else a.ban.via
    return via is not None and covers(user, via.discussion.text_path)


def decidable(user, r: Reviewer | None) -> Q:
    """The appeals `_may_decide_appeal` lets through, as a filter the database applies to all of them at once: not
    one's own, not against one's own act, and for a reviewer (`r`, their row) one on a contribution of their area or a
    pause made through one."""
    mine = (Q(user_id=user.id) | Q(contribution__isnull=False, contribution__removed_by_id=user.id)
            | Q(contribution__isnull=True, ban__by_id=user.id))
    if user.is_staff:
        return ~mine
    on_removal, on_pause = Q(contribution__isnull=False), Q(contribution__isnull=True, ban__via__isnull=False)
    if r is not None and r.text_paths:
        on_removal &= Q(contribution__discussion__text_path__in=r.text_paths)
        on_pause &= Q(ban__via__discussion__text_path__in=r.text_paths)
    return ~mine & (on_removal | on_pause) if r is not None else Q(pk__in=[])


def liftable(user, r: Reviewer | None) -> Q:
    """The pauses `covers` lets a reviewer see (`r`, their row), as a filter: those made through a contribution of
    their area; all of them for staff."""
    if user.is_staff:
        return Q()
    if r is None:
        return Q(pk__in=[])
    return Q(via__discussion__text_path__in=r.text_paths) if r.text_paths else Q(via__isnull=False)


def _ledger(verb, actor, *, c: Contribution | None = None, path='', target=None, rule='', note='') -> Action:
    hidden = bool(c and c.anonymous)
    return Action.objects.create(verb=verb, actor=actor, contribution=c, path=path or (c.discussion.path if c else ''),
                                 target=target or (c.author if c else None), target_hidden=hidden, rule=rule,
                                 note=(note or '').strip()[:NOTE_MAX])


def _contribution(user, pk) -> Contribution:
    c = Contribution.objects.filter(pk=pk).select_related('discussion', 'parent', 'author', 'clip').first()
    if c is None or c.erased_at:
        raise Refused('contribution', 'not_found', 404)
    if not covers(user, c.discussion.text_path):
        raise Refused('review', 'not_reviewer', 403)
    if c.author_id == user.id:
        raise Refused('review', 'own', 403)
    return c


def _close_reports(c: Contribution, status: str, user) -> None:
    c.reports.filter(status=Report.Status.OPEN).update(status=status, decided_at=timezone.now(), decided_by=user)


def appoint(staff, user, text_paths=(), *, everywhere: bool = False) -> Reviewer:
    """A moderator of these places (or texts); of everything only when asked so in as many words (`everywhere`): no
    place chosen made a moderator of everything, explanations included."""
    if not staff.is_staff:
        raise Refused('review', 'staff_only', 403)
    text_paths = [p for p in dict.fromkeys(text_paths or []) if isinstance(p, str) and p.strip()]
    if not text_paths and not everywhere:
        raise Refused('places', 'required')
    if everywhere:
        text_paths = []
    with transaction.atomic():
        Reviewer.objects.filter(user=user, ended_at=None).update(ended_at=timezone.now())
        r = Reviewer.objects.create(user=user, text_paths=list(text_paths), appointed_by=staff)
        _ledger(Action.Verb.APPOINT, staff, target=user, note=', '.join(text_paths))
    return r


def dismiss(staff, user) -> None:
    if not staff.is_staff:
        raise Refused('review', 'staff_only', 403)
    with transaction.atomic():
        Reviewer.objects.filter(user=user, ended_at=None).update(ended_at=timezone.now())
        _ledger(Action.Verb.DISMISS, staff, target=user)
