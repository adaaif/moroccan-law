"""«مفيد», the one vote (D2), and «أفادني», the asker's mark on one answer. There is no downvote. A vote from an
account without a proven email or under three days old is kept and ranks nothing. No one votes for themself."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Contribution, Kind, Notice, Point, Useful
from apps.discussion.services import counters, gates, places, points


def _published(pk) -> Contribution:
    c = Contribution.objects.filter(pk=pk).select_related('discussion', 'parent').first()
    if c is None or not c.published:
        raise Refused('contribution', 'not_found', 404)
    return c


def useful(user, pk) -> Contribution:
    gates.voter(user)
    c = _published(pk)
    if c.author_id == user.id:
        raise Refused('useful', 'own')
    counted = gates.vote_counts(user)
    with transaction.atomic():
        try:
            with transaction.atomic():
                row = Useful.objects.create(user=user, contribution=c, counted=counted)
        except IntegrityError:  # a double tap raced its twin
            return c
        if counted:
            points.award(c.author, Point.Source.USEFUL, str(row.pk), points.USEFUL)
        counters.useful(c)
    return c


def not_useful(user, pk) -> Contribution:
    gates.voter(user)
    c = Contribution.objects.filter(pk=pk).first()
    if c is None:
        raise Refused('contribution', 'not_found', 404)
    with transaction.atomic():
        for row in Useful.objects.filter(user=user, contribution=c):
            points.void(Point.Source.USEFUL, str(row.pk))
            row.delete()
        counters.useful(c)
    return c


def accept(user, pk) -> Contribution:
    """The person who asked marks the answer that helped; one answer a question, and marking another moves it."""
    from apps.discussion.services import notices

    gates.voter(user)
    answer = _published(pk)
    question = answer.parent
    if question is None or question.kind != Kind.QUESTION or question.author_id != user.id \
            or answer.author_id == user.id:
        raise Refused('accept', 'not_asker', 403)
    with transaction.atomic():
        for other in question.replies.exclude(pk=answer.pk).exclude(accepted_at=None):
            other.accepted_at = None
            other.save(update_fields=['accepted_at'])
            points.void(Point.Source.ACCEPTED, str(other.pk))
        if answer.accepted_at is None:
            answer.accepted_at = timezone.now()
            answer.save(update_fields=['accepted_at'])
            points.award(answer.author, Point.Source.ACCEPTED, str(answer.pk), points.ACCEPTED)
            notices.notify(answer.author, Notice.Kind.ACCEPTED, contribution=answer, path=places.notice_path(answer))
        counters.replies(question)
    return answer


def unaccept(user, pk) -> Contribution:
    gates.voter(user)
    answer = _published(pk)
    if answer.parent is None or answer.parent.author_id != user.id:
        raise Refused('accept', 'not_asker', 403)
    with transaction.atomic():
        answer.accepted_at = None
        answer.save(update_fields=['accepted_at'])
        points.void(Point.Source.ACCEPTED, str(answer.pk))
        counters.replies(answer.parent)
    return answer


def void_all(c: Contribution) -> None:
    """A removal or a deletion takes back every point the contribution earned."""
    for pk in c.votes.filter(counted=True).values_list('pk', flat=True):
        points.void(Point.Source.USEFUL, str(pk))
    points.void(Point.Source.ACCEPTED, str(c.pk))


def restore_all(c: Contribution) -> None:
    """A restore gives them back."""
    for row in c.votes.filter(counted=True):
        points.award(c.author, Point.Source.USEFUL, str(row.pk), points.USEFUL)
    if c.accepted_at:
        points.award(c.author, Point.Source.ACCEPTED, str(c.pk), points.ACCEPTED)
