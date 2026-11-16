"""Reporting a contribution, once per person, with a reason and a moment inside a voice. The author never learns
who reported. The reporter is told: waiting, acted on, or reviewed.

Two more for what harms most (M11): anyone named in a contribution can ask for it to go, with or without an account
(law 09-08's right to object), and three reports of exposing someone or of sexual content hide the contribution
until a reviewer decides. Only reporters whose vote would count are counted there (a proven address, three days old):
three accounts made the same day could hide any post."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import NOTE_MAX, Action, Contribution, Report
from apps.discussion.services import counters, gates
from apps.media.models import State
from apps.media.services import files

SERIOUS = {Report.Reason.EXPOSING, Report.Reason.SEXUAL}
HIDE_AFTER = 3


def file(user, pk, *, reason: str, details: str = '', moment_ms=None) -> Report:
    gates.voter(user)
    c = Contribution.objects.filter(pk=pk).select_related('clip').first()
    if c is None or not c.published:
        raise Refused('contribution', 'not_found', 404)
    if c.author_id == user.id:
        raise Refused('report', 'own')
    if reason not in Report.Reason.values:
        raise Refused('reason', 'invalid')
    if moment_ms is not None:
        try:
            moment_ms = int(moment_ms)
        except (TypeError, ValueError):
            raise Refused('moment_ms', 'invalid') from None
        if c.clip is None or not 0 <= moment_ms <= c.clip.duration_ms:
            raise Refused('moment_ms', 'invalid')
    try:
        with transaction.atomic():
            report = Report.objects.create(reporter=user, contribution=c, reason=reason,
                                           details=(details or '').strip()[:NOTE_MAX], moment_ms=moment_ms)
    except IntegrityError:
        raise Refused('report', 'already', 409) from None
    if reason in SERIOUS:
        hide_if_serious(c)
    return report


def hide_if_serious(c: Contribution) -> None:
    standing = timezone.now() - timedelta(days=gates.VOTE_AFTER_DAYS)
    serious = (c.reports.filter(status=Report.Status.OPEN, reason__in=SERIOUS, reporter__email_proven_at__isnull=False,
                                reporter__date_joined__lte=standing, reporter__deleted_at=None)
               .values('reporter').distinct().count())
    if serious >= HIDE_AFTER and not c.hidden_at:
        with transaction.atomic():
            c.hidden_at = timezone.now()
            c.save(update_fields=['hidden_at'])
            # Its voice and pictures leave readers' sight with its words: a live picture answered at its address, and
            # anyone was given a voice's link.
            files.set_state([c.clip, *c.pictures.all()], State.EVIDENCE)
            Action.objects.create(verb=Action.Verb.HIDE, actor=None, contribution=c, path=c.discussion.path,
                                  target=c.author, target_hidden=c.anonymous,
                                  note=f'{serious} reports of exposing or sexual content')
            counters.around(c)


def takedown(user, pk, *, details: str = '', contact: str = '') -> Report:
    """«هذه المساهمة تذكرني»: a person asks for a contribution about them to go. No account needed; it goes to the
    top of the reviewers' queue."""
    c = Contribution.objects.filter(pk=pk).first()
    if c is None or c.erased_at or c.removed_at or (c.held_at and not c.hidden_at):
        raise Refused('contribution', 'not_found', 404)
    details = (details or '').strip()[:NOTE_MAX]
    if not details:
        raise Refused('details', 'required')
    signed_in = user is not None and user.is_authenticated
    if signed_in and Report.objects.filter(reporter=user, contribution=c).exists():
        raise Refused('report', 'already', 409)
    return Report.objects.create(reporter=user if signed_in else None, contribution=c,
                                 reason=Report.Reason.EXPOSING, takedown=True, details=details,
                                 contact=(contact or '').strip()[:200])


def mine(user):
    return Report.objects.filter(reporter=user).select_related('contribution__discussion').order_by('-created_at')
