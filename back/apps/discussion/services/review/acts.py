"""A reviewer's acts on a contribution and a discussion: approve, keep after reports, remove under a rule, restore
within 90 days, reveal an anonymous author (staff, with a reason), lock; and the polish's: redact words or part of a
picture, send back to the author, trust an author, mark a repeated question."""
from datetime import timedelta
from itertools import pairwise

from django.db import transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import NOTE_MAX, Action, Contribution, Discussion, Kind, Notice, Report, Rule, Trust
from apps.discussion.services import citing, counters, holds, notices, places, votes
from apps.discussion.services.review.desk import suggest
from apps.discussion.services.review.reviewers import _close_reports, _contribution, _ledger, covers
from apps.media.models import State
from apps.media.services import files, pictures

KEPT = timedelta(days=90)
REDACTED = '[حُذف]'


def approve(user, pk, note: str = '') -> Contribution:
    c = _contribution(user, pk)
    if not c.held_at or c.removed_at or c.deleted_at:
        raise Refused('review', 'nothing_waiting', 409)
    with transaction.atomic():
        c.held_at, c.held_reasons, c.review_note, c.post_review_at = None, [], '', None
        c.save(update_fields=['held_at', 'held_reasons', 'review_note', 'post_review_at'])
        files.set_state([c.clip, *c.pictures.all()], State.LIVE)
        _ledger(Action.Verb.APPROVE, user, c=c, note=note)
        counters.around(c)
        notices.notify(c.author, Notice.Kind.APPROVED, contribution=c, path=places.notice_path(c))
        notices.on_published(c)
    return c


def keep(user, pk, note: str = '') -> Contribution:
    c = _contribution(user, pk)
    if not c.reports.filter(status=Report.Status.OPEN).exists() and not c.hidden_at:
        raise Refused('review', 'nothing_waiting', 409)
    with transaction.atomic():
        _close_reports(c, Report.Status.REVIEWED, user)
        if c.hidden_at:
            c.hidden_at = None
            c.save(update_fields=['hidden_at'])
            # Its files back with its words, unless something else keeps them from readers.
            if not (c.held_at or c.removed_at or c.deleted_at):
                files.set_state([c.clip, *c.pictures.all()], State.LIVE)
            counters.around(c)
        _ledger(Action.Verb.KEEP, user, c=c, note=note)
        _thank_reporters(c)
    return c


def remove(user, pk, rule: str, note: str = '') -> Contribution:
    c = _contribution(user, pk)
    if rule not in Rule.values:
        raise Refused('rule', 'required')
    if c.removed_at:
        raise Refused('review', 'nothing_waiting', 409)
    with transaction.atomic():
        c.removed_at, c.removed_by, c.removed_rule = timezone.now(), user, rule
        c.hidden_at = c.post_review_at = None
        c.save(update_fields=['removed_at', 'removed_by', 'removed_rule', 'hidden_at', 'post_review_at'])
        files.set_state([c.clip, *c.pictures.all()], State.EVIDENCE)
        votes.void_all(c)
        _close_reports(c, Report.Status.ACTED, user)
        _ledger(Action.Verb.REMOVE, user, c=c, rule=rule, note=note)
        # A removal ends a trust (M8).
        if Trust.objects.filter(user=c.author, ended_at=None).update(ended_at=timezone.now()):
            _ledger(Action.Verb.UNTRUST, user, c=c, note='ended by a removal')
        counters.around(c)
        if not c.deleted_at:
            notices.notify(c.author, Notice.Kind.REMOVED, contribution=c, path=places.notice_path(c), detail=rule)
        _thank_reporters(c)
    return c


def restore(user, pk, note: str = '', *, by_appeal: bool = False) -> Contribution:
    c = _contribution(user, pk) if not by_appeal else Contribution.objects.get(pk=pk)
    if not c.removed_at or c.erased_at or c.removed_at < timezone.now() - KEPT:
        raise Refused('review', 'nothing_waiting', 409)
    with transaction.atomic():
        c.removed_at, c.removed_by, c.removed_rule = None, None, ''
        c.save(update_fields=['removed_at', 'removed_by', 'removed_rule'])
        if not c.deleted_at:
            files.set_state([c.clip, *c.pictures.all()], State.EVIDENCE if c.held_at else State.LIVE)
            votes.restore_all(c)
        _ledger(Action.Verb.RESTORE, user, c=c, note=note)
        counters.around(c)
        notices.notify(c.author, Notice.Kind.RESTORED, contribution=c, path=places.notice_path(c))
    return c


def _thank_reporters(c: Contribution) -> None:
    """Each reporter of `c` whose report is closed is told what came of it, once: who was told already read in one
    query, the others' notices written in one insert (one person reports a contribution once)."""
    reports = list(c.reports.exclude(reporter=None).exclude(status=Report.Status.OPEN).select_related('reporter'))
    told = set(Notice.objects.filter(user_id__in=[r.reporter_id for r in reports], kind=Notice.Kind.REPORT,
                                     contribution=c).values_list('user_id', flat=True)) if reports else set()
    fresh = [r for r in reports if r.reporter_id not in told]
    notices._tell_many([r.reporter for r in fresh], Notice.Kind.REPORT, c, places.notice_path(c) if fresh else '',
                       details={r.reporter_id: r.status for r in fresh})


def reveal(user, pk, note: str) -> dict:
    """Staff only, with a reason: who wrote an anonymous contribution."""
    if not user.is_staff:
        raise Refused('review', 'staff_only', 403)
    if not (note or '').strip():
        raise Refused('note', 'required')
    c = Contribution.objects.select_related('author', 'discussion').filter(pk=pk, anonymous=True).first()
    if c is None:
        raise Refused('contribution', 'not_found', 404)
    _ledger(Action.Verb.REVEAL, user, c=c, note=note)
    return {'username': c.author.username, 'display_name': c.author.display_name, 'email': c.author.email}


# ── a discussion ───────────────────────────────────────────────────────────

def lock(user, path: str, locked: bool, note: str = '') -> Discussion:
    d = Discussion.objects.filter(path=path).first()
    if d is None:
        raise Refused('path', 'not_found', 404)
    if not covers(user, d.text_path):
        raise Refused('review', 'not_reviewer', 403)
    with transaction.atomic():
        d.locked_at, d.locked_by = (timezone.now(), user) if locked else (None, None)
        d.save(update_fields=['locked_at', 'locked_by'])
        _ledger(Action.Verb.LOCK if locked else Action.Verb.UNLOCK, user, path=path, note=note)
    return d


# ── the polish (19 Oct 2026): redact, send back, trust, repeats ──────────────

def redact(user, pk, spans, note: str = '', publish: bool = True) -> Contribution:
    """Remove words, keep the contribution (M3): each span becomes «[حُذف]»; the earlier wording stays for the
    reviewers (a revision, 90 days). Held, it is then published if nothing else holds it."""
    from apps.discussion.models import Revision

    c = _contribution(user, pk)
    try:
        spans = sorted({(int(s), int(e)) for s, e in spans})
    except (TypeError, ValueError):
        raise Refused('spans', 'invalid') from None
    if not spans or any(not 0 <= s < e <= len(c.body) for s, e in spans) or any(
            a[1] > b[0] for a, b in pairwise(spans)):
        raise Refused('spans', 'invalid')
    body, at = '', 0
    for s, e in spans:
        body += c.body[at:s] + REDACTED
        at = e
    body += c.body[at:]
    with transaction.atomic():
        Revision.objects.create(contribution=c, body=c.body)
        reasons, matched = holds.scan(body)
        c.body, c.links, c.held_spans = body, citing.read(body, citing.text_for(c)), matched
        c.held_reasons = sorted(set([r for r in c.held_reasons if r == 'pictures'] + reasons))
        c.save(update_fields=['body', 'links', 'held_spans', 'held_reasons'])
        _ledger(Action.Verb.REDACT, user, c=c, rule=suggest(c) or '', note=note)
        notices.notify(c.author, Notice.Kind.REDACTED, contribution=c, path=places.notice_path(c))
        _close_reports(c, Report.Status.ACTED, user)
    if publish and c.held_at:
        c = approve(user, pk, note)
    return c


def redact_picture(user, pk, picture_id, file, note: str = '') -> Contribution:
    """Cover part of a picture (M3): the covered copy takes the old one's place; the old one is kept 90 days."""
    c = _contribution(user, pk)
    old = c.pictures.filter(pk=picture_id).first()
    if old is None:
        raise Refused('picture', 'not_found', 404)
    with transaction.atomic():
        new = pictures.upload(c.author, file)
        files.set_state([new], State.LIVE if c.published else State.EVIDENCE)
        old.replaced_by = new
        old.save(update_fields=['replaced_by'])
        files.set_state([old], State.EVIDENCE)
        c.pictures.remove(old)
        c.pictures.add(new)
        _ledger(Action.Verb.REDACT, user, c=c, note=note or 'picture')
        notices.notify(c.author, Notice.Kind.REDACTED, contribution=c, path=places.notice_path(c), detail='picture')
    return c


def send_back(user, pk, note: str) -> Contribution:
    """Ask the author to fix it (M4): it waits, out of readers' sight, until they edit it; then it returns to the
    top of the queue."""
    c = _contribution(user, pk)
    note = (note or '').strip()
    if not note:
        raise Refused('note', 'required')
    if c.removed_at or c.deleted_at:
        raise Refused('review', 'nothing_waiting', 409)
    with transaction.atomic():
        c.held_at = c.held_at or timezone.now()
        c.held_reasons = sorted(set([r for r in c.held_reasons if r != 'returned'] + ['sent_back']))
        c.review_note, c.post_review_at = note[:NOTE_MAX], None
        c.save(update_fields=['held_at', 'held_reasons', 'review_note', 'post_review_at'])
        files.set_state([c.clip, *c.pictures.all()], State.EVIDENCE)
        _close_reports(c, Report.Status.ACTED, user)
        _ledger(Action.Verb.SEND_BACK, user, c=c, rule=suggest(c) or '', note=note)
        counters.around(c)
        notices.notify(c.author, Notice.Kind.SENT_BACK, contribution=c, path=places.notice_path(c), detail=note[:40])
    return c


def trust(user, pk, trusted: bool, note: str = '') -> None:
    """Trust a contribution's author (M8), never learning an anonymous one's name."""
    c = _contribution(user, pk)
    with transaction.atomic():
        live = Trust.objects.filter(user=c.author, ended_at=None)
        if trusted and not live.exists():
            Trust.objects.create(user=c.author, by=user)
            _ledger(Action.Verb.TRUST, user, c=c, note=note)
        elif not trusted and live.update(ended_at=timezone.now()):
            _ledger(Action.Verb.UNTRUST, user, c=c, note=note)


def duplicate(user, pk, of_pk, note: str = '') -> Contribution:
    """A question asked before (M9): linked to the first one, its asker told where the answers are."""
    c = _contribution(user, pk)
    original = Contribution.objects.filter(pk=of_pk, discussion=c.discussion, parent=None, kind=Kind.QUESTION).first()
    if c.parent_id or c.kind != Kind.QUESTION or original is None or original.pk == c.pk or not original.published:
        raise Refused('duplicate', 'invalid')
    with transaction.atomic():
        c.duplicate_of = original
        c.save(update_fields=['duplicate_of'])
        _close_reports(c, Report.Status.ACTED, user)
        _ledger(Action.Verb.DUPLICATE, user, c=c, rule=Rule.ON_TOPIC, note=note)
        counters.around(c)
        notices.notify(c.author, Notice.Kind.DUPLICATE, contribution=original, path=places.notice_path(c))
    return c
