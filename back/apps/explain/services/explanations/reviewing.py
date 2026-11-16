"""The reviewers' side of the explanations: their area, checking an edit that waits, removing a state under a rule
or keeping a reported one (each a row of the discussion's ledger, its author told), a reader's report, and what waits
for a reviewer."""
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Action, Notice, Report as TalkReport, Rule
from apps.discussion.services import gates, review
from apps.explain.models import Explanation, Report, Revision
from apps.explain.services.explanations.reading import _public, kind_of, text_of
from apps.explain.services.explanations.writing import _shows


def _area(user) -> Q | None:
    """The explanations a reviewer reviews, as a filter on their address (None: none)."""
    if user is None or not user.is_authenticated:
        return None
    if user.is_staff:
        return Q()
    r = review.reviewer(user)
    if r is None:
        return None
    if not r.text_paths:
        return Q()
    area = Q(pk__in=[])
    for p in r.text_paths:
        if p.startswith('/ma/'):
            area |= Q(path=p) | Q(path__startswith=f'{p}/')
    return area


def check(user, path: str, register: str) -> Explanation:
    """A reviewer of the text (or staff) says the edit that waits is right as it stands: readers see it from now. Never
    their own: another reviewer decides about it."""
    if not (user and user.is_authenticated and (user.is_staff or review.covers(user, text_of(path)))):
        raise Refused('review', 'not_reviewer', 403)
    e = Explanation.objects.filter(path=path, register=register).select_related('pending').first()
    if e is None:
        raise Refused('path', 'not_found', 404)
    r = e.pending
    if r is None:
        raise Refused('review', 'nothing_waiting', 409)
    if r.author_id == user.id:
        raise Refused('review', 'own', 403)
    with transaction.atomic():
        _shows(e, r, user, timezone.now())
        e.save()
        _ledger(Action.Verb.APPROVE, user, e, r)
        _tell(r, Notice.Kind.APPROVED)
    return e


def _tell(r: Revision, kind: str, rule: str = '') -> None:
    """Its author is told on their account page what came of their words (no letter: the discussion's letters speak of
    posts and of appeals, which an explanation has not)."""
    if r.author is not None and not r.author.deleted_at:
        Notice.objects.create(user=r.author, kind=kind, path=f'/explain{r.explanation.path}', detail=rule)


def _ledger(verb: str, user, e: Explanation, r: Revision, rule: str = '', note: str = '') -> Action:
    """The discussion's ledger: every act of power on an explanation is a row, by the explanation's page."""
    return Action.objects.create(verb=verb, actor=user, path=f'/explain{e.path}', target=r.author, rule=rule,
                                 note=(note or f'«باختصار» {e.register}').strip()[:500])


def _revision(user, pk) -> tuple[Revision, Explanation]:
    """A state a reviewer acts on: in their area, never their own."""
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        raise Refused('revision', 'not_found', 404) from None
    r = Revision.objects.filter(pk=pk).select_related('explanation', 'author').first()
    if r is None:
        raise Refused('revision', 'not_found', 404)
    e = r.explanation
    if not (user and user.is_authenticated and (user.is_staff or review.covers(user, text_of(e.path)))):
        raise Refused('review', 'not_reviewer', 403)
    if r.author_id == user.id:
        raise Refused('review', 'own', 403)
    return r, e


def _close_reports(r: Revision, status: str, user) -> None:
    r.reports.filter(status=TalkReport.Status.OPEN).update(status=status, decided_at=timezone.now(), decided_by=user)


def remove(user, pk, rule: str, note: str = '') -> Explanation:
    """A reviewer takes a state out under one of the rules: an edit that waits never shows; the words readers see go
    back to the state checked before them, or off the page when there is none. Its author is told which rule."""
    r, e = _revision(user, pk)
    if rule not in Rule.values:
        raise Refused('rule', 'required')
    if r.removed_at:
        raise Refused('review', 'nothing_waiting', 409)
    now = timezone.now()
    with transaction.atomic():
        e = Explanation.objects.select_for_update().get(pk=e.pk)
        shown = e.revisions.filter(checked_at__isnull=False, removed_at=None).first()
        r.removed_at, r.removed_by, r.removed_rule = now, user, rule
        r.save(update_fields=['removed_at', 'removed_by', 'removed_rule'])
        _close_reports(r, TalkReport.Status.ACTED, user)
        if e.pending_id == r.pk:
            # The next edit waiting, if one came after the words readers see.
            after = shown.created_at if shown is not None else None
            waiting = e.revisions.filter(checked_at=None, removed_at=None)
            e.pending = (waiting.filter(created_at__gt=after) if after else waiting).first()
        if shown is not None and shown.pk == r.pk:
            before = e.revisions.filter(checked_at__isnull=False, removed_at=None).first()
            if before is not None:
                e.headline, e.body, e.sources = before.headline, before.body, before.sources
                e.reviewed_at, e.reviewed_by = before.checked_at, before.checked_by
            else:
                e.headline, e.body, e.sources, e.reviewed_at, e.reviewed_by = '', '', [], None, None
        e.save()
        _ledger(Action.Verb.REMOVE, user, e, r, rule, note)
        _tell(r, Notice.Kind.REMOVED, rule)
    return e


def keep(user, pk, note: str = '') -> Explanation:
    """A reviewer reads a reported state and keeps it: its reports are closed."""
    r, e = _revision(user, pk)
    if not r.reports.filter(status=TalkReport.Status.OPEN).exists():
        raise Refused('review', 'nothing_waiting', 409)
    with transaction.atomic():
        _close_reports(r, TalkReport.Status.REVIEWED, user)
        _ledger(Action.Verb.KEEP, user, e, r, note=note)
    return e


def report(user, pk, *, reason: str, details: str = '') -> Report:
    """A reader's report of a state readers see, once a person, never of one's own words; the reporter is never
    shown."""
    gates.voter(user)
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        raise Refused('revision', 'not_found', 404) from None
    r = Revision.objects.filter(pk=pk).select_related('explanation', 'checked_by').first()
    if r is None or not _public(r.explanation, r):
        raise Refused('revision', 'not_found', 404)
    if r.author_id == user.id:
        raise Refused('report', 'own')
    if reason not in TalkReport.Reason.values:
        raise Refused('reason', 'invalid')
    try:
        with transaction.atomic():
            return Report.objects.create(reporter=user, revision=r, reason=reason,
                                         details=(details or '').strip()[:500])
    except IntegrityError:
        raise Refused('report', 'already', 409) from None


def _open_reports():
    return Report.objects.filter(revision__explanation=OuterRef('pk'), status=TalkReport.Status.OPEN)


def waiting(user, limit: int = 50) -> list[dict]:
    """What waits for this reviewer: explanations with an edit to check or a state reported, the oldest first."""
    area = _area(user)
    if area is None:
        raise Refused('review', 'not_reviewer', 403)
    rows = (Explanation.objects.filter(area).filter(Q(pending__isnull=False) | Exists(_open_reports()))
            .select_related('pending')
            .annotate(reports=Count('revisions__reports', filter=Q(revisions__reports__status=TalkReport.Status.OPEN)))
            .order_by('updated_at')[:limit])
    return [{'path': e.path, 'register': e.register, 'kind': kind_of(e.path), 'pending': e.pending_id is not None,
             'held_reasons': e.pending.held_reasons if e.pending is not None else [], 'reports': e.reports,
             'since': e.pending.created_at if e.pending is not None else e.updated_at} for e in rows]


def waiting_count(user) -> int:
    """How many explanations wait for this reviewer: the header's count beside the discussion's."""
    area = _area(user)
    if area is None:
        return 0
    return Explanation.objects.filter(area).filter(Q(pending__isnull=False) | Exists(_open_reports())).count()
