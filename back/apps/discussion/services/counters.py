"""Every counter changes here, by counting, after each create, edit, delete, removal and restore, so none can
drift (a counter that is only ever added to never comes down when a comment goes)."""
import time

from django.conf import settings
from django.db.models import Count, F, Max, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, Greatest

from apps.discussion.models import Contribution, Discussion, Kind, Useful

LIVE = Q(held_at=None, hidden_at=None, removed_at=None, deleted_at=None, erased_at=None)


def demo(prefix: str = 'author__') -> Q:
    """The development's people: the seeded demo accounts («demo-…»), the end-to-end tests' (…@demo.law.invalid) and
    any account made before the public site's database was copied from the development's (DEMO_UNTIL), a test account
    deleted since included. Off the public site unless SHOW_DEMO_PEOPLE (N1 of the read-and-trusted review, 27 Oct 2026:
    1,096 demo contributions stood on the family code's art. 49). An empty Q when they are shown; `prefix` '' asks it of
    users themselves. Through a relation it is a list of accounts the database reads once a query, not a join to every
    row (the load test of 30 Oct 2026: counting a topic of 900,000 rows that way took seconds)."""
    if settings.SHOW_DEMO_PEOPLE:
        return Q()
    if not prefix:
        return _people()
    return Q(**{f'{prefix}id__in': _demo_ids()})


def _people() -> Q:
    return (Q(username__startswith='demo-') | Q(email__endswith='@demo.law.invalid')
            | Q(date_joined__lt=settings.DEMO_UNTIL))


_kept_ids: tuple[float, list[int]] = (0.0, [])


def _demo_ids() -> list[int]:
    """The development's accounts by key, read again each DEMO_IDS_KEPT seconds in a process (every query read the
    100,000 accounts of the load test to find them, 100 ms; tests read them each time)."""
    global _kept_ids
    from apps.accounts.models import User

    at, ids = _kept_ids
    if time.monotonic() - at >= settings.DEMO_IDS_KEPT:
        ids = list(User.objects.filter(_people()).values_list('id', flat=True))
        _kept_ids = (time.monotonic(), ids)
    return ids


def is_demo(user) -> bool:
    """`demo()` asked of one account already read: the same three marks, in Python."""
    if settings.SHOW_DEMO_PEOPLE or user is None:
        return False
    return (user.username.startswith('demo-') or user.email.endswith('@demo.law.invalid')
            or user.date_joined < settings.DEMO_UNTIL)


def published() -> Q:
    """What a reader may see counted and listed: live, and by a real person."""
    return LIVE if settings.SHOW_DEMO_PEOPLE else LIVE & ~demo()


# How many published posts make the conversation a place of its own on a phone's bar, and how long the answer is kept.
ALIVE = 100
ALIVE_KEPT = 600


def alive() -> bool:
    """Whether the conversation holds its first hundred published posts. Until then a phone's bar gives its fifth place
    to «محفوظاتي», which works today, and the conversation is reached from the header, the home, a law and the footer
    (C2 of the readers review, 10 Nov 2026: «النقاش» held a place and no post in any topic). Kept ten minutes:
    one query that stops at the hundredth post, never a count of every post."""
    from django.core.cache import cache

    known = cache.get('talk:alive')
    if known is None:
        posts = Contribution.objects.filter(published(), parent=None).values_list('pk', flat=True)[:ALIVE]
        known = len(posts) >= ALIVE
        cache.set('talk:alive', known, ALIVE_KEPT)
    return known


def _posts_counted():
    """A place's counts read from its posts, which carry their own: its published posts and every published comment
    (each post's reply_count, whatever the post's state), the questions nobody else answered, its last sign of life."""
    live = published()
    return dict(
        posts=Count('pk', filter=live), comments=Coalesce(Sum('reply_count'), 0),
        waiting=Count('pk', filter=live & Q(kind=Kind.QUESTION, duplicate_of=None, answered_at=None)),
        last=Max('active_at', filter=live | Q(reply_count__gt=0)))


def discussion(d: Discussion) -> None:
    """A place counted again from its posts: one query over its posts, never over its comments."""
    n = Contribution.objects.filter(discussion=d, parent=None).aggregate(**_posts_counted())
    d.count, d.open_questions, d.last_at = n['posts'] + n['comments'], n['waiting'], n['last']
    d.save(update_fields=['count', 'open_questions', 'last_at'])


def _answer_order():
    return F('accepted_at').desc(nulls_last=True), '-useful_count', 'created_at', 'pk'


def replies(parent: Contribution | None) -> None:
    """A post's comments counted again; its last sign of life (itself or its latest published comment); when someone
    other than its author last answered it, and its answer (the marked one, else the most useful, else the first)."""
    if parent is None:
        return
    live = Contribution.objects.filter(published(), parent=parent).order_by()
    n = live.aggregate(n=Count('pk'), last=Max('created_at'),
                       answered=Max('created_at', filter=~Q(author_id=parent.author_id)),
                       first=Count('pk', filter=Q(reply_to=None)), people=Count('author', distinct=True))
    parent.reply_count, parent.conversation_count, parent.people_count = n['n'], n['first'], n['people']
    parent.active_at = max(parent.created_at, n['last']) if n['last'] else parent.created_at
    parent.answered_at = n['answered']
    parent.answer_id = (live.exclude(author_id=parent.author_id).order_by(*_answer_order())
                        .values_list('pk', flat=True).first()) if n['answered'] else None
    parent.save(update_fields=['reply_count', 'active_at', 'answered_at', 'answer', 'conversation_count',
                               'people_count'])


def useful(c: Contribution) -> None:
    c.useful_count = Useful.objects.filter(contribution=c, counted=True).count()
    c.save(update_fields=['useful_count'])
    replies(c.parent)


def around(c: Contribution) -> None:
    """After a contribution changed: its parent's counts, then its discussion's, which reads them."""
    replies(c.parent)
    discussion(c.discussion)


def every_post(only=None) -> int:
    """Posts counted again in one statement whatever their number (all of them, or those `only` names): after
    SHOW_DEMO_PEOPLE changes, and once for the answers' columns (30 Oct 2026)."""
    live = Contribution.objects.filter(published(), parent=OuterRef('pk')).order_by()
    others = live.exclude(author=OuterRef('author'))
    at = live.values('parent').annotate(m=Max('created_at')).values('m')
    posts = Contribution.objects.filter(parent=None)
    if only is not None:
        posts = posts.filter(only)
    return posts.update(
        reply_count=Coalesce(Subquery(live.values('parent').annotate(n=Count('pk')).values('n')), 0),
        conversation_count=Coalesce(Subquery(live.filter(reply_to=None).values('parent').annotate(n=Count('pk'))
                                             .values('n')), 0),
        people_count=Coalesce(Subquery(live.values('parent').annotate(n=Count('author', distinct=True)).values('n')), 0),
        active_at=Greatest(F('created_at'), Coalesce(Subquery(at), F('created_at'))),
        answered_at=Subquery(others.values('parent').annotate(m=Max('created_at')).values('m')),
        answer=Subquery(others.order_by(*_answer_order()).values('pk')[:1]))


def every_discussion() -> int:
    """Every discussion's counts again from their posts, in two queries whatever their number (after SHOW_DEMO_PEOPLE
    changes)."""
    counted = {r['discussion_id']: r for r in Contribution.objects.filter(parent=None).order_by()
               .values('discussion_id').annotate(**_posts_counted())}
    rows = list(Discussion.objects.only('pk', 'count', 'open_questions', 'last_at'))
    for d in rows:
        n = counted.get(d.pk)
        d.count = n['posts'] + n['comments'] if n else 0
        d.open_questions, d.last_at = (n['waiting'], n['last']) if n else (0, None)
    Discussion.objects.bulk_update(rows, ['count', 'open_questions', 'last_at'], batch_size=500)
    return len(rows)
