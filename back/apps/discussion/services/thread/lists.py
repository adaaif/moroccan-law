"""The lists of posts, each sorted and cut by the database: a topic's feed (or every topic's, or what a reader
follows), the hub's places with their latest posts, a topic's block on its page, the questions waiting and those
answered, an article's posts and the counts in a text's margin, and a person's page."""
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.db.models import Count, F, Max, Q, Window
from django.db.models.functions import Coalesce, RowNumber
from django.utils import timezone

from apps.discussion.models import Cite, Contribution, Discussion, Follow, Kind
from apps.discussion.services import anchors, counters, gates, holds, places, points
from apps.discussion.services.thread.cards import Context, _labels, _with_media, card, cites_of, post_card, where

PAGE = 20


SORTS = ('active', 'new', 'top', 'open')
#: «الأنفع» over the last days of a period, or since the start (31 Oct 2026).
PERIODS = {'week': 7, 'month': 30, 'year': 365, 'all': None}
#: «النشيط»: a post's last sign of life, else its own date (as its card says it), the newest first; indexed as such.
LIFE = (Coalesce('active_at', 'created_at').desc(), F('created_at').desc())


def _real() -> Q:
    """By a real person: everything while developing, the development's people left out where the public reads."""
    return Q() if settings.SHOW_DEMO_PEOPLE else ~counters.demo()


def _shown(viewer, reviewing: bool) -> Q:
    """What a list shows: what readers may see; the viewer's own words whatever their state, short of gone; and to a
    moderator of the place, what waits or was hidden."""
    standing = Q(removed_at=None, deleted_at=None, erased_at=None)
    shown = counters.published()
    if viewer is not None and viewer.is_authenticated:
        shown |= standing & Q(author=viewer)
    if reviewing:
        shown |= standing & _real()
    return shown


def _waiting():
    """Questions nobody else answered yet (counters.replies keeps when someone did)."""
    return Contribution.objects.filter(counters.published(), parent=None, kind=Kind.QUESTION, duplicate_of=None,
                                       answered_at=None)


def _page(qs, page: int, size: int = PAGE) -> tuple[list, int | None]:
    """A page of a list and the next page's number, from one row more than the page: no list counts itself (the load
    test of 30 Oct 2026: counting a million posts for «next» took seconds)."""
    start = (max(1, page) - 1) * size
    rows = list(qs[start:start + size + 1])
    return rows[:size], page + 1 if len(rows) > size else None


def _reviewing(viewer, path: str) -> bool:
    from apps.discussion.services import review

    return bool(viewer is not None and viewer.is_authenticated and review.is_reviewer(viewer)
                and review.covers(viewer, path))


def moderators(place_paths: list[str]) -> dict[str, list[dict]]:
    """Each place's moderators by name (the topic's page names them), in two queries."""
    from apps.discussion.models import Reviewer

    rows = [r for r in Reviewer.objects.filter(ended_at=None).select_related('user')
            if not r.user.deleted_at and r.user.is_active and not counters.is_demo(r.user)]
    karma = points.karma({r.user_id for r in rows})
    out: dict[str, list[dict]] = {p: [] for p in place_paths}
    for r in rows:
        for p in place_paths:
            if p in (r.text_paths or []):
                out[p].append({'username': r.user.username, 'name': holds.shown_name(r.user), 'karma': karma.get(r.user_id, 0)})
    return out


def place_payload(place: places.Place, d: Discussion | None, viewer) -> dict:
    following = bool(viewer is not None and viewer.is_authenticated
                     and Follow.objects.filter(user=viewer, path=place.path).exists())
    return {'path': place.path, 'slug': place.slug, 'name': place.name, 'count': d.count if d else 0,
            'open_questions': d.open_questions if d else 0, 'locked': bool(d and d.locked_at), 'following': following,
            'moderators': moderators([place.path])[place.path]}


#: The conversation's own feeds besides a topic's (30 Oct 2026): every topic at once, and what the reader follows.
ALL, FOLLOWING = '', 'following'


def _followed(viewer) -> Q:
    """What a reader follows: the topics they follow, and the posts they follow (writing in one follows it)."""
    paths = list(Follow.objects.filter(user=viewer, path__startswith=places.PREFIX).values_list('path', flat=True))
    topics = [p for p in paths if places.is_place(p)]
    posts = [pk for _, pk in map(places.split_post, paths) if pk]
    return Q(discussion__path__in=topics) | Q(pk__in=posts)


def feed(viewer, path: str, sort: str = 'active', page: int = 1, period: str = 'month') -> dict:
    """A topic's posts, a page at a time, sorted in the database; or every topic's (`ALL`), or what the reader follows
    (`FOLLOWING`), where a moderator sees only what readers see. «الأنفع» reads its `period`."""
    scope = path if path in (ALL, FOLLOWING) else None
    place = None if scope is not None else places.find(path)
    d = Discussion.objects.filter(path=place.path).first() if place else None
    reviewing = _reviewing(viewer, place.path) if place else False
    sort = sort if sort in SORTS else 'active'
    period = period if period in PERIODS else 'month'
    rows, following = [], None
    signed = viewer is not None and viewer.is_authenticated
    if d is not None or scope == ALL or (scope == FOLLOWING and signed):
        qs = Contribution.objects.filter(_shown(viewer, reviewing), parent=None)
        if d is not None:
            qs = qs.filter(discussion=d)
        else:
            qs = qs.filter(discussion__path__startswith=places.PREFIX)
            if scope == FOLLOWING:
                qs = qs.filter(_followed(viewer))
        if sort == 'new':
            qs = qs.order_by('-created_at')
        elif sort == 'top':
            if PERIODS[period]:
                qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=PERIODS[period]))
            qs = qs.order_by('-useful_count', '-reply_count', '-created_at')
        elif sort == 'open':
            qs = qs.filter(counters.published(), kind=Kind.QUESTION, duplicate_of=None,
                           answered_at=None).order_by('-created_at')
        else:
            qs = qs.order_by(*LIFE)
        rows, following = _page(_with_media(qs.select_related('discussion')), page)
    ctx, cites = Context(viewer, rows), cites_of(rows)
    return {'place': place_payload(place, d, viewer) if place else None,
            'scope': 'place' if scope is None else 'following' if scope == FOLLOWING else 'all', 'sort': sort,
            'period': period,
            'writing': gates.standing(viewer),
            'review': {'can': reviewing, 'staff': bool(viewer is not None and viewer.is_authenticated and viewer.is_staff)},
            'posts': [post_card(c, ctx, cites, 'full', reviewing) for c in rows], 'next_page': following}


def article_payload(anchor: anchors.Anchor) -> dict:
    """The article as the text page shows it (its stamp, its page), and its text's name."""
    from apps.corpus.api.views import issue_ref, text_payload, text_ref

    eids = list(anchor.version.articles.values_list('eid', flat=True))
    i = eids.index(anchor.article.eid)
    article = text_payload(anchor.text, span=(i, i + 1))['articles'][0]
    issue = anchor.text.first_published_in
    return {'article': {k: article[k] for k in ('label', 'number', 'body', 'eid', 'path', 'page', 'document_id',
                                                'page_index', 'marks', 'heading_path', 'citation')},
            'text': {**text_ref(anchor.text), 'issue': issue_ref(issue) if issue else None},
            'version': {'valid_from': anchor.version.valid_from, 'consolidation': anchor.version.consolidation}}


def cited(viewer, path: str, page: int = 1) -> dict:
    """An article and the posts that cite it or started from it (C3 of 29 Oct 2026): a comment that cites it brings
    its post. Where a question about it may go: its text's topics."""
    anchor = anchors.find(path)
    ids = Cite.objects.filter(path=anchor.path).values_list('contribution_id', flat=True)
    tops = set(Contribution.objects.filter(counters.published(), pk__in=ids)
               .values_list(Coalesce('parent_id', 'id'), flat=True))
    qs = (Contribution.objects.filter(counters.published(), pk__in=tops, parent=None)
          .order_by(*LIFE))
    total = qs.count()
    start = (max(1, page) - 1) * PAGE
    rows = list(_with_media(qs.select_related('discussion'))[start:start + PAGE])
    ctx, cites = Context(viewer, rows), cites_of(rows)
    names = _labels({c.discussion.path for c in rows})
    return {**article_payload(anchor),
            'posts': [{**post_card(c, ctx, cites), 'label': names[c.discussion.path]} for c in rows],
            'total': total, 'next_page': page + 1 if start + PAGE < total else None,
            'places': [{'path': p.path, 'slug': p.slug, 'name': p.name} for p in places.of_text(anchor.text_path)],
            'writing': gates.standing(viewer)}


def counts(text_path: str) -> dict:
    """Each article's number of published posts and comments that cite it, for the margin of a text's page."""
    rows = (Cite.objects.filter(text_path=text_path).filter(_cited_live()).values('path')
            .annotate(n=Count('contribution_id', distinct=True)))
    return {r['path'].rsplit('/', 1)[-1]: {'count': r['n']} for r in rows}


def _cited_live() -> Q:
    live = Q(contribution__held_at=None, contribution__hidden_at=None, contribution__removed_at=None,
             contribution__deleted_at=None, contribution__erased_at=None)
    return live if settings.SHOW_DEMO_PEOPLE else live & ~counters.demo('contribution__author__')


def _latest(ds: list[Discussion], latest: int) -> list[int]:
    """Each place's `latest` liveliest posts, in one query: on PostgreSQL a union of one short read of its own index a
    place (ranking a million posts to keep a few was too slow), elsewhere a rank over them."""
    posts = (Contribution.objects.filter(counters.published(), parent=None)
             .order_by(*LIFE))
    if not ds:
        return []
    if connection.features.supports_slicing_ordering_in_compound:
        parts = [posts.filter(discussion=d).values_list('pk', flat=True)[:latest] for d in ds]
        return list(parts[0].union(*parts[1:], all=True))
    return list(posts.filter(discussion__in=ds).annotate(
        rank=Window(RowNumber(), partition_by=[F('discussion_id')],
                    order_by=list(LIFE)))
        .filter(rank__lte=latest).values_list('pk', flat=True))


def overview(latest: int = 3) -> dict:
    """The places as the conversation's hub shows them: each with its counts and its latest posts, in three queries."""
    listed = places.all_places()
    ds = {d.path: d for d in Discussion.objects.filter(path__in=[p.path for p in listed])}
    rows = list(_with_media(Contribution.objects.filter(pk__in=_latest(list(ds.values()), latest))
                            .select_related('discussion'))
                .order_by('discussion_id', *LIFE))
    ctx = Context(None, rows)
    by_place: dict[str, list[dict]] = {}
    for c in rows:
        by_place.setdefault(c.discussion.path, []).append(post_card(c, ctx, {}))
    return {'places': [{'path': p.path, 'slug': p.slug, 'name': p.name, 'short': p.short,
                        'count': ds[p.path].count if p.path in ds else 0,
                        'open_questions': ds[p.path].open_questions if p.path in ds else 0,
                        'last_at': ds[p.path].last_at if p.path in ds else None,
                        'posts': by_place.get(p.path, [])} for p in listed]}


def topic_talk(slug: str, most: int = 3, waiting: int = 2) -> dict:
    """A topic's conversation on its page: its place's liveliest posts and the questions waiting longest."""
    place = places.find(f'{places.PREFIX}{slug}')
    live = Contribution.objects.filter(counters.published(), parent=None, discussion__path=place.path)
    rows = list(_with_media(live.select_related('discussion'))
                .order_by(*LIFE)[:most])
    questions = list(_with_media(_waiting().filter(discussion__path=place.path).select_related('discussion'))
                     .order_by('created_at')[:waiting])
    ctx = Context(None, rows + questions)
    return {'place': place.path, 'posts': [post_card(c, ctx, {}) for c in rows],
            'questions': [post_card(c, ctx, {}) for c in questions],
            'moderators': moderators([place.path])[place.path]}


def open_questions(place: str = '', page: int = 1) -> dict:
    """Questions nobody else answered yet, oldest waiting first; across the places or in one."""
    qs = _waiting().filter(discussion__path__startswith=places.PREFIX)
    if place:
        qs = qs.filter(discussion__path=place)
    rows, following = _page(_with_media(qs.select_related('discussion')).order_by('created_at'), page)
    ctx = Context(None, rows)
    labels = _labels(c.discussion.path for c in rows)
    return {'questions': [{**post_card(c, ctx, {}), 'label': labels[c.discussion.path]} for c in rows],
            'next_page': following,
            'places': list(Discussion.objects.filter(path__startswith=places.PREFIX).exclude(open_questions=0)
                           .values_list('path', flat=True))}


def answered_questions(page: int = 1) -> dict:
    """Questions someone answered (R12 of the for-everyone review), the latest answered first, each with its answer: the
    one the asker marked «أفادني», else the most useful, else the first; both kept on the question (counters.replies),
    read in two queries (computed for every question, it timed out over ten million comments)."""
    qs = (Contribution.objects.filter(counters.published(), parent=None, kind=Kind.QUESTION, duplicate_of=None,
                                      answered_at__isnull=False, discussion__path__startswith=places.PREFIX)
          .order_by('-answered_at'))
    rows, following = _page(_with_media(qs.select_related('discussion')), page)
    answers = {a.parent_id: a for a in _with_media(Contribution.objects.filter(
        counters.published(), pk__in=[q.answer_id for q in rows if q.answer_id]))}
    ctx = Context(None, rows + list(answers.values()))
    labels = _labels(q.discussion.path for q in rows)
    return {'questions': [{**post_card(q, ctx, {}), 'label': labels[q.discussion.path],
                           'answer': card(answers[q.pk], ctx) if answers.get(q.pk) else None} for q in rows],
            'next_page': following}


def _moderates(user) -> list[dict]:
    """The topics a person moderates, by name."""
    from apps.discussion.models import Reviewer

    r = Reviewer.objects.filter(user=user, ended_at=None).first()
    by_path = {p.path: p for p in places.all_places()}
    return [{'path': p, 'name': by_path[p].name} for p in (r.text_paths if r else []) if p in by_path]


def person(viewer, username: str, page: int = 1, kind: str = '') -> dict | None:
    """A person's page: what they wrote under their name (never their «بدون اسم»), their posts or their answers
    (`kind`), their karma, the topics they moderate, and where they write most (30 Oct 2026)."""
    from apps.accounts.models import User

    user = User.objects.filter(username__iexact=username, deleted_at=None, is_active=True).exclude(counters.demo('')).first()
    if user is None:
        return None
    theirs = Contribution.objects.filter(counters.published(), author=user, anonymous=False)
    # Where and what they write, in one query: a row per place and kind.
    spread = list(theirs.order_by().values('discussion__path', 'kind').annotate(n=Count('pk'), last=Max('created_at')))
    qs = theirs
    if kind == 'posts':
        qs = qs.filter(parent=None)
    elif kind == 'answers':
        qs = qs.exclude(parent=None)
    qs = _with_media(qs.select_related('discussion', 'parent')).order_by('-created_at')
    total = qs.count()
    start = (max(1, page) - 1) * PAGE
    rows = list(qs[start:start + PAGE])
    ctx = Context(viewer, rows)
    labels = _labels(c.discussion.path for c in rows)
    by_place: dict[str, int] = {}
    for r in spread:
        if places.is_place(r['discussion__path']):
            by_place[r['discussion__path']] = by_place.get(r['discussion__path'], 0) + r['n']
    names = {p.path: p for p in places.all_places()}
    return {
        'person': {'username': user.username, 'name': holds.shown_name(user), 'form': user.address_form,
                   'joined': user.date_joined, 'karma': points.total(user),
                   'contributions': sum(r['n'] for r in spread),
                   'posts': sum(r['n'] for r in spread if r['kind'] != Kind.COMMENT),
                   'answers': sum(r['n'] for r in spread if r['kind'] == Kind.COMMENT),
                   'last_at': max((r['last'] for r in spread), default=None),
                   'places': [{'path': path, 'slug': names[path].slug, 'name': names[path].name, 'count': n}
                              for path, n in sorted(by_place.items(), key=lambda x: -x[1]) if path in names],
                   'moderates': _moderates(user),
                   'accepted': theirs.exclude(accepted_at=None).count()},
        'contributions': [{**card(c, ctx), **where(c, viewer), 'label': labels[c.discussion.path]} for c in rows],
        'total': total,
        'next_page': page + 1 if start + PAGE < total else None,
    }
