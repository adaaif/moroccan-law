"""The reviewers' desk: the queue's tabs (held, reported, appeals, pauses) ordered and cut by the database, what a
card shows beside the words (the article, the post above, the author's recent words and record, the rule to
suggest), read once for a page (`Desk`), the ledger a reviewer may read, and the header's count."""
from functools import reduce
from operator import or_

from django.db.models import Case, IntegerField, Min, Prefetch, Q, Sum, When, prefetch_related_objects

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Action, Appeal, Ban, Contribution, Discussion, Report, Rule, Trust
from apps.discussion.services import anchors
from apps.discussion.services.review.reviewers import _area, decidable, is_reviewer, liftable, reviewer

# The rule a hold or a report points to (M2): the queue preselects the commonest.
RULE_OF = {'phone': Rule.SOLICITING, 'email': Rule.SOLICITING, 'link': Rule.SOLICITING, 'cin': Rule.PRIVACY,
           'rib': Rule.PRIVACY, 'case': Rule.PRIVACY, 'insult': Rule.RESPECT,
           Report.Reason.EXPOSING: Rule.PRIVACY, Report.Reason.ABUSE: Rule.RESPECT,
           Report.Reason.SOLICITING: Rule.SOLICITING, Report.Reason.FRAUD: Rule.LAWFUL,
           Report.Reason.SEXUAL: Rule.DECENT, Report.Reason.OFF_TOPIC: Rule.ON_TOPIC,
           # What the model's check held or returned under (29 Oct 2026).
           **{f'check_{rule}': rule for rule in Rule.values}}
# What harms most comes first in the reported tab (M7).
SEVERITY = {Report.Reason.EXPOSING: 3, Report.Reason.FRAUD: 3, Report.Reason.SEXUAL: 3, Report.Reason.ABUSE: 2,
            Report.Reason.SOLICITING: 1, Report.Reason.OFF_TOPIC: 1}


# What a card of the queue reads beside the contribution, brought by the queue's own query (S6 of the performance
# audit): its open reports, its earlier wordings, the answer it follows.
CARD_RELATED = ('discussion', 'author', 'clip', 'parent__author', 'reply_to__author')


def _card_prefetch() -> tuple:
    from apps.discussion.services.thread import pictures

    return (pictures(), 'revisions',
            Prefetch('reports', queryset=Report.objects.filter(status=Report.Status.OPEN).order_by('created_at'),
                     to_attr='open_reports'))


def open_reports(c: Contribution) -> list[Report]:
    """A contribution's open reports, oldest first: brought with it by the queue, else asked."""
    if hasattr(c, 'open_reports'):
        return c.open_reports
    return list(c.reports.filter(status=Report.Status.OPEN).order_by('created_at'))


def _reason(code: str) -> Q:
    """Held for this reason: `held_reasons` is a JSON list of codes, whose text holds each code in quotes, on
    PostgreSQL and SQLite alike."""
    return Q(held_reasons__icontains=f'"{code}"')


# What may expose someone comes first in the held tab, after what its author returned.
PRIVATE = ('cin', 'rib', 'case', 'check_privacy')


def _held(area):
    # Sent back: the author's to fix, not the queue's (M4).
    return (Contribution.objects.filter(area, held_at__isnull=False, removed_at=None, deleted_at=None, erased_at=None)
            .exclude(_reason('sent_back')))


def _reported(area):
    return Contribution.objects.filter(area, reports__status=Report.Status.OPEN)


def _reviewing(user):
    """Where `user` reviews, as a filter of contributions, and their reviewer's row (None for staff): read once for
    what a tab or the counts ask of it, never once a row."""
    r = None if user.is_staff else reviewer(user)
    return _area(user, r), r


def _appeals(user, r):
    return Appeal.objects.filter(decidable(user, r), decided_at=None)


def _pauses(user, r):
    return Ban.objects.filter(liftable(user, r), ended_at=None)


def counts(user) -> dict[str, int]:
    """How many wait in each tab, counted rather than loaded: anyone can fill the held and reported tabs, and the
    appeals and pauses."""
    area, r = _reviewing(user)
    return {'held': _held(area).count(), 'reported': _reported(area).distinct().count(),
            'appeals': _appeals(user, r).count(), 'pauses': _pauses(user, r).count()}


class Desk:
    """What a page of the queue shows beside each contribution, read once for the page: the articles, what each named
    author wrote lately, their record and whether they are trusted (about twelve queries a card before)."""

    def __init__(self, rows: list[Contribution], user=None):
        from django.db.models import Count, F, Window
        from django.db.models.functions import RowNumber

        rows = [c for c in rows if c is not None]
        # Where this reviewer may read what is not published (their area), read once for the page.
        r = reviewer(user) if user is not None and not user.is_staff else None
        self.everywhere = bool(user is not None and (user.is_staff or (r is not None and not r.text_paths)))
        self.area = set(r.text_paths) if r is not None else set()
        # The article each one is on: a post's starting article, or an article thread's own.
        self.anchors = anchors.find_many({c.about or c.discussion.path for c in rows})
        authors = {c.author_id for c in rows}
        named = {c.author_id for c in rows if not c.anonymous}
        self.records = {r['author_id']: r for r in Contribution.objects.filter(author_id__in=authors).values('author_id')
                        .annotate(n=Count('id'), removed=Count('id', filter=Q(removed_at__isnull=False)))}
        self.paused = dict(Ban.objects.filter(user_id__in=authors).values('user_id').annotate(n=Count('id'))
                           .values_list('user_id', 'n'))
        self.trusted = set(Trust.objects.filter(user_id__in=authors, ended_at=None).values_list('user_id', flat=True))
        self.recent: dict[int, list[Contribution]] = {}
        latest = (Contribution.objects.filter(author_id__in=named, anonymous=False)
                  .annotate(rank=Window(RowNumber(), partition_by=[F('author_id')], order_by=F('created_at').desc()))
                  .filter(rank__lte=6).select_related('discussion').order_by('author_id', '-created_at')) if named else []
        for o in latest:
            self.recent.setdefault(o.author_id, []).append(o)


def queue(user, tab: str, limit: int | None = None):
    """A tab's items in the order a reviewer takes them; the held and reported tabs ordered and cut by the database,
    `limit` at most, whatever waits behind them. An appeal comes with what its card shows of the contribution it is
    about (removed, or the one a pause came through), read for the whole tab."""
    area, r = _reviewing(user)
    if tab == 'held':
        # Returned by their author first (M4), then what may expose someone, then by age.
        first = Case(When(_reason('returned'), then=0), default=1, output_field=IntegerField())
        exposing = Case(When(reduce(or_, map(_reason, PRIVATE)), then=0), default=1, output_field=IntegerField())
        rows = (_held(area).annotate(by_return=first, by_privacy=exposing).order_by('by_return', 'by_privacy', 'held_at', 'pk')
                .select_related(*CARD_RELATED).prefetch_related(*_card_prefetch()))
        return list(rows[:limit] if limit else rows)
    if tab == 'reported':
        # The open reports' weight, heaviest first, then the oldest report: a takedown request outweighs everything,
        # then the reports' reasons, added up.
        weight = Case(When(reports__takedown=True, then=10),
                      *[When(reports__reason=reason, then=n) for reason, n in SEVERITY.items()],
                      default=1, output_field=IntegerField())
        rows = (_reported(area).annotate(weight=Sum(weight), first=Min('reports__created_at'))
                .order_by('-weight', 'first', 'pk').select_related(*CARD_RELATED).prefetch_related(*_card_prefetch()))
        return list(rows[:limit] if limit else rows)
    if tab == 'appeals':
        rows = list(_appeals(user, r).select_related(
            'user', *(f'contribution__{name}' for name in CARD_RELATED),
            *(f'ban__via__{name}' for name in CARD_RELATED)).order_by('created_at'))
        prefetch_related_objects([a.contribution or a.ban.via for a in rows if a.contribution or a.ban.via],
                                 *_card_prefetch())
        return rows
    if tab == 'pauses':
        return list(_pauses(user, r).select_related('via__discussion', 'user', 'by').order_by('-started_at'))
    raise Refused('tab', 'invalid')


def ledger(user, limit: int = 100):
    rows = Action.objects.select_related('actor', 'target', 'contribution__discussion').order_by('-created_at')
    if not user.is_staff:
        r = reviewer(user)
        if r is None:
            raise Refused('review', 'not_reviewer', 403)
        if r.text_paths:
            rows = rows.filter(Q(contribution__discussion__text_path__in=r.text_paths)
                               | Q(path__in=Discussion.objects.filter(text_path__in=r.text_paths).values('path')))
    return rows[:limit]


def suggest(c: Contribution) -> str | None:
    """The rule the hold's matches and the open reports point to most."""
    votes_for: dict[str, int] = {}
    for reason in c.held_reasons:
        if reason in RULE_OF:
            votes_for[RULE_OF[reason]] = votes_for.get(RULE_OF[reason], 0) + 1
    for r in open_reports(c):
        votes_for[RULE_OF[r.reason]] = votes_for.get(RULE_OF[r.reason], 0) + 2
    return max(votes_for, key=votes_for.get) if votes_for else None


def context(c: Contribution, desk: Desk | None = None) -> dict:
    """What a reviewer needs beside the words (M1): the article, the question an answer answers, and what a named
    author wrote lately with what came of it. Never an anonymous author's other words."""
    at = c.about or c.discussion.path
    if desk is not None:
        found = desk.anchors.get(at)
        article = found.article.body if found else ''
    else:
        try:
            article = anchors.find(at).article.body
        except Refused:
            article = ''
    parent = c.parent
    recent = []
    if not c.anonymous:
        lately = ([o for o in desk.recent.get(c.author_id, []) if o.pk != c.pk][:5] if desk is not None else
                  Contribution.objects.filter(author_id=c.author_id, anonymous=False).exclude(pk=c.pk)
                  .select_related('discussion').order_by('-created_at')[:5])
        for o in lately:
            # Words not published are a reviewer's to read where they review; elsewhere only what readers see.
            if not (o.published or (desk is not None and (desk.everywhere or o.discussion.text_path in desk.area))):
                continue
            recent.append({'id': o.pk, 'path': o.discussion.path, 'title': o.title, 'body': o.body[:160],
                           'created_at': o.created_at,
                           'state': 'removed' if o.removed_at else 'held' if o.held_at else
                           'deleted' if o.deleted_at else 'published', 'rule': o.removed_rule or None})
    return {'article': article,
            'parent': {'id': parent.pk, 'title': parent.title, 'body': parent.body[:600], 'kind': parent.kind,
                       'anonymous': parent.anonymous} if parent else None,
            'recent': recent, 'trusted': c.author_id in desk.trusted if desk is not None else
            Trust.objects.filter(user_id=c.author_id, ended_at=None).exists(),
            'suggested': suggest(c)}


def record(user, c: Contribution, desk: Desk | None = None) -> dict:
    """What a reviewer sees of an author: how much they wrote and what was removed. No name when anonymous."""
    if desk is not None:
        mine = desk.records.get(c.author_id, {})
        return {'contributions': mine.get('n', 0), 'removed': mine.get('removed', 0), 'paused': desk.paused.get(c.author_id, 0)}
    mine = Contribution.objects.filter(author_id=c.author_id)
    return {'contributions': mine.count(), 'removed': mine.exclude(removed_at=None).count(),
            'paused': Ban.objects.filter(user_id=c.author_id).count()}


def waiting_everywhere() -> list[tuple]:
    """What waits in the held and reported tabs of every area, as (its key, its text's address, held at, sent for
    review at): what the reviewers' digest counts for each reviewer, read once for all of them."""
    keys = ('pk', 'discussion__text_path', 'held_at', 'post_review_at')
    return [*_held(Q()).values_list(*keys), *_reported(Q()).values_list(*keys).distinct()]


def waiting_counts(user) -> int:
    """How many items wait in this reviewer's area: the header's count (M10), explanations to check included."""
    from apps.explain.services import explanations

    if not is_reviewer(user):
        return 0
    area = _area(user)
    return _held(area).count() + _reported(area).distinct().count() + explanations.waiting_count(user)
