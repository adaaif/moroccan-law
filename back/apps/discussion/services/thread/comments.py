"""A post's page: the post as its reader may open it, and its comments as a tree grown on request (the load test of
30 Oct 2026): a page of first-level comments read from their own index, each with its first replies; a door under any
comment for the rest of the replies that answer it; and the line of a conversation down to the comment a link
names."""
from collections import namedtuple

from django.db import connection
from django.db.models import Count, F, Q, Window
from django.db.models.functions import RowNumber

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Contribution, Follow
from apps.discussion.services import anchors, counters, gates, places
from apps.discussion.services.thread.cards import Context, _with_media, card, cites_of, post_card, visible
from apps.discussion.services.thread.lists import _page, _reviewing, article_payload, place_payload

#: A post's comments as a tree grown on request (30 Oct 2026): its first-level comments
#: a page (the load test of 30 Oct 2026: a post of 23,428 comments answered 13 MB at once), each with the first replies
#: that answer it; under any comment, the rest of the replies that answer it a door at a time, one level per tap.
CONVERSATIONS = 30
REPLY_PREVIEW = 2
DOOR = 10
COMMENT_SORTS = ('best', 'new', 'old')


#: How a post's first-level comments are ordered: «best» the asker's marked answer, then the most useful, then the
#: first; «new», «old» by date.
_TOP_ORDER = {'best': (F('accepted_at').desc(nulls_last=True), '-useful_count', 'created_at', 'pk'),
              'new': ('-created_at', '-pk'), 'old': ('created_at', 'pk')}


_FIELDS = ('id', 'reply_to_id', 'author_id', 'accepted_at', 'useful_count', 'created_at', 'held_at', 'hidden_at',
           'removed_at', 'deleted_at', 'erased_at', 'reply_count')


class _Row(namedtuple('_Row', _FIELDS)):
    """A comment's few fields, as `visible` and the conversations read them: a tuple, not a model object (the load test
    of 30 Oct 2026: tens of thousands of model objects took seconds to build)."""
    __slots__ = ()

    @property
    def pk(self):
        return self.id

    @property
    def published(self) -> bool:
        return not (self.held_at or self.hidden_at or self.removed_at or self.deleted_at or self.erased_at)


def may_open(viewer, pk: int, place: str = '') -> bool:
    """Whether this reader may open post `pk` (in `place`, when one is named): the rule `post()` reads it by."""
    try:
        c, *_ = _opened(viewer, pk)
    except Refused:
        return False
    return not place or c.discussion.path == place


def _opened(viewer, pk: int):
    """A post as its reader may see it: (post, place, reviewing, how it is shown), or Refused."""
    c = (Contribution.objects.filter(pk=pk, parent=None).exclude(counters.demo()).select_related('discussion')
         .first())
    if c is None or not places.is_place(c.discussion.path):
        raise Refused('post', 'not_found', 404)
    place = places.find(c.discussion.path)
    reviewing = _reviewing(viewer, place.path)
    shown = visible(c, viewer, reviewing)
    if shown is None:
        raise Refused('post', 'not_found', 404)
    return c, place, reviewing, shown


def _comments(viewer, c: Contribution, reviewing: bool):
    """The post's comments its reader may see, as one query: what `visible` shows (the published; the held or hidden
    to their author and the place's moderators; a removed one with answers, as a marker), never the development's
    people. The page is read from it a slice at a time, never whole (a post of a hundred thousand comments read whole
    was too slow)."""
    standing = Q(removed_at=None, deleted_at=None, erased_at=None)
    waiting = standing & (Q(held_at__isnull=False) | Q(hidden_at__isnull=False))
    seen = counters.LIVE | (~standing & Q(reply_count__gt=0))
    if reviewing:
        seen |= waiting
    elif viewer is not None and viewer.is_authenticated:
        seen |= waiting & Q(author=viewer)
    return Contribution.objects.filter(seen, parent=c).exclude(counters.demo()).order_by(), seen


def _rows(qs) -> list:
    return [_Row._make(t) for t in qs.values_list(*_FIELDS)]


def _unseen(viewer, c: Contribution, reviewing: bool) -> list[int]:
    """The comments under a post its reader cannot see: of its few unpublished ones (their own index), those `visible`
    hides from this reader, and the development's people's. A reply to one of them stands as a conversation of its own."""
    ids = [r.pk for r in _rows(Contribution.objects.filter(parent=c).exclude(counters.LIVE))
           if visible(r, viewer, reviewing) is None]
    demo = counters.demo()
    if demo:
        ids += list(Contribution.objects.filter(demo, parent=c).values_list('pk', flat=True))
    return ids


def _conversations(tops, c: Contribution, sort: str, page: int) -> tuple[list, int | None]:
    """A page of the post's first-level comments in the reader's order, read from their own index a page at a time:
    «best» the one its asker marked (the answer its post keeps), then the most useful, then the first; «new», «old» by
    date (ordering all 109,535 comments of a post took seconds)."""
    start = (max(1, page) - 1) * CONVERSATIONS
    if sort != 'best':
        rows, following = _page(tops.order_by(*_TOP_ORDER[sort]).values_list(*_FIELDS), page, CONVERSATIONS)
        return [_Row._make(t) for t in rows], following
    marked = _rows(tops.filter(pk=c.answer_id, accepted_at__isnull=False)) if c.answer_id else []
    rows = marked[start:start + CONVERSATIONS + 1]
    more = CONVERSATIONS + 1 - len(rows)
    skip = max(0, start - len(marked))
    rows += _rows(tops.filter(accepted_at=None).order_by('-useful_count', 'created_at', 'pk')[skip:skip + more])
    return rows[:CONVERSATIONS], page + 1 if len(rows) > CONVERSATIONS else None


def _answers_to(shown, rows: list) -> dict[int, int]:
    """How many shown comments answer each of these, in one query."""
    return dict(shown.filter(reply_to__in=[r.pk for r in rows]).values_list('reply_to').annotate(n=Count('pk'))) \
        if rows else {}


def _cards(viewer, c: Contribution, rows: list, answers: dict, reviewing: bool) -> tuple:
    """The comments' cards, read in one query, each saying how many answer it (`answers`); the context and the full
    rows, for a page that shows more (the post)."""
    full = {x.pk: x for x in _with_media(Contribution.objects.filter(pk__in=[c.pk] + [r.pk for r in rows])
                                          .select_related('discussion'))}
    ctx, cites = Context(viewer, list(full.values())), cites_of(list(full.values()))
    cards = [{**card(full[r.pk], ctx, visible(r, viewer, reviewing), reviewing), 'cites': cites.get(r.pk, []),
              'answers': answers.get(r.pk, 0)} for r in rows]
    return cards, ctx, cites, full


def post_answers(viewer, pk: int, to: int, page: int = 1) -> dict:
    """A door: the replies that answer comment `to`, DOOR a page, oldest first (the first page holds the ones the post's
    page showed under it), each saying how many answer it; the page grows the tree one level where the reader asked."""
    c, _, reviewing, _ = _opened(viewer, pk)
    shown, _ = _comments(viewer, c, reviewing)
    if not shown.filter(pk=to).exists():
        raise Refused('to', 'not_found', 404)
    lane = shown.filter(reply_to=to)
    rows, following = _page(lane.order_by('created_at', 'pk').values_list(*_FIELDS), page, DOOR)
    rows = [_Row._make(t) for t in rows]
    cards, *_ = _cards(viewer, c, rows, _answers_to(shown, rows), reviewing)
    return {'replies': cards, 'answers': lane.count(), 'next_page': following}


def _line(post: int, to: int) -> list[int]:
    """Comment `to` and the comments it answers up to its first-level one, in one query however deep (200 at most)."""
    table = connection.ops.quote_name(Contribution._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f'WITH RECURSIVE line(id, reply_to_id, depth) AS ('  # noqa: S608 — the model's quoted table name; the ids go as parameters
            f'SELECT id, reply_to_id, 0 FROM {table} WHERE id = %s AND parent_id = %s '
            f'UNION ALL SELECT c.id, c.reply_to_id, line.depth + 1 FROM {table} c JOIN line ON c.id = line.reply_to_id '
            f'WHERE line.depth < 200) SELECT id FROM line', [to, post])
        return [r[0] for r in cursor.fetchall()]


def post_around(viewer, pk: int, to: int) -> dict:
    """Where a link to one comment lands (a shared comment, a notice, the answer under the question): the line of its
    conversation from the first-level comment down to it, and its first replies, so the page shows it in place however
    deep it is; every card says how many answer it, the rest a door away."""
    c, _, reviewing, _ = _opened(viewer, pk)
    shown, _ = _comments(viewer, c, reviewing)
    by_id = {r.pk: r for r in _rows(shown.filter(pk__in=_line(c.pk, to)))}
    if to not in by_id:
        raise Refused('c', 'not_found', 404)
    line, at = [], by_id[to]
    while at is not None and len(line) < 200:
        line.append(at)
        at = by_id.get(at.reply_to_id)
    line.reverse()
    rows = line + _rows(shown.filter(reply_to=to).order_by('created_at', 'pk')[:REPLY_PREVIEW])
    cards, *_ = _cards(viewer, c, rows, _answers_to(shown, rows), reviewing)
    return {'replies': cards, 'first': line[0].pk}


def post(viewer, pk: int, page: int = 1, sort: str = 'best') -> dict:
    """One post with a page of its comments, CONVERSATIONS first-level comments at a time (a comment whose own is not
    shown counts as one), each with its first REPLY_PREVIEW replies, and the article it started from when it did. Only
    the page's comments are read: each card says how many answer it (`answers`; post_answers is its door). How many
    conversations and people are what its post keeps (counters.replies). The answer its asker marked is no box of its
    own (31 Oct 2026): it is marked where it stands, first by «الأنفع»."""
    c, place, reviewing, shown_as = _opened(viewer, pk)
    shown, _ = _comments(viewer, c, reviewing)
    unseen = _unseen(viewer, c, reviewing)
    tops = shown.filter(Q(reply_to=None) | Q(reply_to__in=unseen) if unseen else Q(reply_to=None))
    picked, following = _conversations(tops, c, sort if sort in COMMENT_SORTS else 'best', page)
    first = (shown.filter(reply_to__in=[r.pk for r in picked])
             .annotate(rank=Window(RowNumber(), partition_by=[F('reply_to')], order_by=[F('created_at'), F('pk')]))
             .filter(rank__lte=REPLY_PREVIEW).order_by('created_at', 'pk')) if picked else None
    under: dict[int, list] = {}
    for r in (_rows(first) if first is not None else []):
        under.setdefault(r.reply_to_id, []).append(r)
    rows = [x for r in picked for x in [r, *under.get(r.pk, ())]]
    cards, ctx, cites, full = _cards(viewer, c, rows, _answers_to(shown, rows), reviewing)
    item = post_card(full[c.pk], ctx, cites, shown_as, reviewing)
    item['replies'] = cards
    article = None
    if c.about:
        try:
            article = article_payload(anchors.find(c.about))
        except Refused:
            article = None
    return {'place': place_payload(place, c.discussion, viewer), 'post': item, 'about': article,
            'conversations': c.conversation_count, 'people': c.people_count, 'next_page': following,
            'following': bool(viewer is not None and viewer.is_authenticated
                              and Follow.objects.filter(user=viewer, path=item['path']).exists()),
            'writing': gates.standing(viewer),
            'review': {'can': reviewing, 'staff': bool(viewer is not None and viewer.is_authenticated and viewer.is_staff)}}
