"""Karma (29 Oct 2026, in place of D2's private sum and titles): a counted «مفيد» is a point, an answer the
asker marked «أفادني» five; the sum shows beside a person's name, to say how much what they write is appreciated.
A removal voids the points a contribution earned, a restore gives them back; the ledger keeps every one."""
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.corpus.services import generation
from apps.discussion.models import Point

USEFUL, ACCEPTED = 1, 5
# Pictures, once on (DISCUSSION_MEDIA), wait for a reviewer until their author has this much karma.
PICTURES_FREE = 25


def award(user, source: str, ref: str, amount: int) -> None:
    row = Point.objects.filter(source=source, ref=ref).first()
    if row is not None:
        if row.voided_at:
            row.voided_at = None
            row.save(update_fields=['voided_at'])
        return
    try:
        with transaction.atomic():
            Point.objects.create(user=user, source=source, ref=ref, amount=amount)
    except IntegrityError:
        pass


def void(source: str, ref: str) -> None:
    Point.objects.filter(source=source, ref=ref, voided_at=None).update(voided_at=timezone.now())
    generation.bump('talk')     # an update sends no signal: titles on the cards may change


def total(user) -> int:
    return Point.objects.filter(user=user, voided_at=None).aggregate(n=Sum('amount'))['n'] or 0


def karma(user_ids) -> dict:
    """Each person's karma: the sum of their points not voided, in one query."""
    rows = (Point.objects.filter(user_id__in=set(user_ids), voided_at=None).values('user_id')
            .annotate(n=Sum('amount')))
    return {r['user_id']: r['n'] or 0 for r in rows}


def in_place(place: str, limit: int = 10, leave_out=()) -> list[tuple[int, int]]:
    """The people whose words a topic found most useful: (user id, karma earned there), the most first. Two queries;
    staff read it to choose the topic's moderators."""
    from django.db.models import Count

    from apps.discussion.models import Contribution, Useful
    from apps.discussion.services import counters

    live = Contribution.objects.filter(counters.published(), discussion__path=place)
    earned: dict[int, int] = {}
    for row in (Useful.objects.filter(counted=True, contribution__in=live).values('contribution__author_id')
                .annotate(n=Count('id'))):
        earned[row['contribution__author_id']] = earned.get(row['contribution__author_id'], 0) + row['n'] * USEFUL
    for row in live.exclude(accepted_at=None).values('author_id').annotate(n=Count('id')):
        earned[row['author_id']] = earned.get(row['author_id'], 0) + row['n'] * ACCEPTED
    ranked = sorted(((u, n) for u, n in earned.items() if u not in set(leave_out)), key=lambda x: -x[1])
    return ranked[:limit]
