"""A contribution as every list shows it: what a page's cards need read once (`Context`), who may see one and how,
its card, its pictures in order, the articles it cites, where it is read; and an address said in words (an article
by the name people know its text by, a place by its topic, a post by its title while readers may read it)."""
from django.db.models import Q

from apps.discussion.models import Cite, Contribution, Kind, Useful
from apps.discussion.services import anchors, counters, holds, places, points
from apps.media.models import State
from apps.media.services import links


class Context:
    """What every card on a page needs, fetched once: the viewer's votes, the authors' karma, today's article."""

    def __init__(self, viewer, rows: list[Contribution], digest: str | None = None):
        self.viewer = viewer if viewer is not None and viewer.is_authenticated else None
        ids = [c.pk for c in rows]
        self.voted = set(Useful.objects.filter(user=self.viewer, contribution_id__in=ids)
                         .values_list('contribution_id', flat=True)) if self.viewer else set()
        authors = {c.author_id for c in rows}
        self.karma = points.karma(authors)
        self.digest = digest
        # A question's answer comes first when its asker marked one (counters.replies), so its mark says it.
        self._answers = {c.answer_id: c.pk for c in rows
                         if c.parent_id is None and c.kind == Kind.QUESTION and c.answer_id}
        self._solved = None

    @property
    def solved(self) -> set[int]:
        """The questions whose asker marked an answer «أفادني»: one query by key, the first time a list asks."""
        if self._solved is None:
            self._solved = {self._answers[pk] for pk in Contribution.objects.filter(
                pk__in=list(self._answers), accepted_at__isnull=False).values_list('pk', flat=True)} \
                if self._answers else set()
        return self._solved

    def outdated(self, c: Contribution) -> bool:
        return bool(self.digest and c.article_digest and c.article_digest != self.digest)


def author(c: Contribution, ctx: Context) -> dict | None:
    if c.anonymous:
        return None
    a = c.author
    if a.deleted_at:
        return {'deleted': True}
    # The name the patterns find nothing in (holds.shown_name): a phone number as a name broke the rules on every card.
    return {'username': a.username, 'name': holds.shown_name(a), 'form': a.address_form,
            'karma': ctx.karma.get(a.pk, 0)}


def visible(c: Contribution, viewer, reviewing: bool = False) -> str | None:
    """'full', 'marker' (a removed or deleted contribution with answers) or None. A held or hidden contribution is
    its author's to see, and a reviewer's where they review (M5)."""
    if c.published:
        return 'full'
    mine = viewer is not None and viewer.is_authenticated and c.author_id == viewer.pk
    if (c.held_at or c.hidden_at) and not (c.removed_at or c.deleted_at or c.erased_at):
        return 'full' if mine or reviewing else None
    return 'marker' if c.reply_count else None


def replied(c: Contribution) -> dict | None:
    """«ردا على نادية» (W7): the answer this one follows, and its author unless they wrote without a name, or the answer
    can no longer be read (held, hidden, removed, deleted): a reply never names the author of words readers cannot see."""
    r = c.reply_to
    if r is None:
        return None
    named = not r.anonymous and not r.author.deleted_at and r.published
    return {'id': r.pk, 'name': holds.shown_name(r.author) if named else None, 'anonymous': r.anonymous}


def card(c: Contribution, ctx: Context, shown: str = 'full', reviewing: bool = False) -> dict:
    base = {'id': c.pk, 'parent': c.parent_id, 'created_at': c.created_at, 'reply_count': c.reply_count}
    if shown == 'marker':
        return {**base, 'marker': 'removed' if c.removed_at else 'deleted', 'rule': c.removed_rule or None}
    viewer = ctx.viewer
    mine = viewer is not None and c.author_id == viewer.pk
    clip = c.clip if c.clip and c.clip.state != State.ERASED else None
    pictures = [p for p in c.pictures.all() if p.state not in (State.ERASED,) and not p.replaced_by_id]
    extra = {}
    if mine or reviewing:
        # Why it waits, for its author to fix (W2) or its reviewer to decide (M5).
        extra.update(held_reasons=c.held_reasons if c.held_at else [], hidden=bool(c.hidden_at))
    if mine and c.review_note:
        extra['review_note'] = c.review_note
    if reviewing:
        from apps.discussion.services import review
        extra.update(suggested=review.suggest(c) if c.held_at else None)
    return {**extra,
        **base, 'kind': c.kind, 'title': c.title, 'body': c.body, 'links': c.links, 'quote': c.quote, 'about': c.about,
        'anonymous': c.anonymous,
        'author': author(c, ctx), 'mine': mine, 'edited_at': c.edited_at,
        'held': bool(c.held_at), 'useful': c.useful_count, 'voted': c.pk in ctx.voted,
        'accepted': bool(c.accepted_at), 'outdated': ctx.outdated(c), 'version_on': c.version_on,
        'voice': {**links.clip(clip), 'id': str(clip.pk), 'duration_ms': clip.duration_ms, 'peaks': clip.peaks}
        if clip else None,
        'pictures': [links.picture(p) for p in pictures],
        'reply_to': replied(c), 'duplicate_of': c.duplicate_of_id,
    }


def pictures():
    """A contribution's pictures in the order they were attached, whatever rows the query reads (it was the
    database's order, which changed with how many contributions a page read)."""
    from django.db.models import Prefetch
    from django.db.models.expressions import RawSQL

    from apps.media.models import Picture

    through = Contribution.pictures.through._meta.db_table
    return Prefetch('pictures', queryset=Picture.objects.order_by(RawSQL(f'"{through}"."id"', [])))  # noqa: S611 — the model's own table name, no input


def _with_media(qs):
    return qs.select_related('author', 'clip', 'reply_to__author').prefetch_related(pictures())


def cites_of(rows: list[Contribution]) -> dict[int, list[dict]]:
    """Each contribution's cited articles, labelled, and whether each changed since it was cited (D14): three queries
    for a page of cards, whatever it cites."""
    found = list(Cite.objects.filter(contribution_id__in=[c.pk for c in rows]).order_by('pk'))
    if not found:
        return {}
    articles = anchors.find_many({f.path for f in found})
    labels = {f.path: label_of(articles.get(f.path)) for f in found}
    today = {path: anchors.digest(a.article.body) for path, a in articles.items()}
    out: dict[int, list[dict]] = {}
    for f in found:
        out.setdefault(f.contribution_id, []).append(
            {'path': f.path, 'label': labels[f.path], 'changed': bool(f.digest and today.get(f.path)
                                                                     and today[f.path] != f.digest)})
    return out


def post_card(c: Contribution, ctx: Context, cites: dict, shown: str = 'full', reviewing: bool = False) -> dict:
    """A post as a list shows it: its card, its address, how many comments, its last sign of life, what it cites."""
    return {**card(c, ctx, shown, reviewing), 'path': f'{c.discussion.path}/{c.pk}', 'place': c.discussion.path,
            'active_at': c.active_at or c.created_at, 'cites': cites.get(c.pk, []), 'solved': c.pk in ctx.solved}


def where(c: Contribution, viewer=None, reviewing: bool = False) -> dict:
    """Where a contribution is read: its post's page (with the post's title, for a comment), or an article's thread.
    The title only while this reader may read the post: a comment's card on its writer's page carried the title of a
    post removed for naming someone."""
    if places.is_place(c.discussion.path):
        top = c.parent or c
        title = top.title if visible(top, viewer, reviewing) == 'full' else ''
        return {'path': f'{c.discussion.path}/{top.pk}', 'place': c.discussion.path, 'post_title': title}
    return {'path': c.discussion.path, 'place': '', 'post_title': ''}


def _label(path: str) -> dict:
    return _labels([path])[path]


def _labels(paths, viewer=None) -> dict[str, dict]:
    """Each address said in words: an article and the name people know its text by (P6 of the polish review), with the
    article's number for a French label, in three queries for a page of cards (S6 of the performance audit); a place
    by its topic's name, and a post by its title too, in one query for all of them. An article gone from the corpus
    still lists its question, with an empty label. A post's title is said only when readers may read the post, or it
    is `viewer`'s own."""
    from apps.corpus.services import generation

    paths = list(dict.fromkeys(paths))
    talk = [p for p in paths if p.startswith(places.PREFIX)]
    out = _place_labels(talk, viewer) if talk else {}

    def made(missing):
        found = anchors.find_many(missing)
        return {path: label_of(found.get(path)) for path in missing}
    rest = [p for p in paths if p not in out]
    return {**out, **(generation.kept_many(rest, made) if rest else {})}


def readable_titles(pks, viewer=None) -> dict[int, str]:
    """The titles of these posts that this reader may read: published ones, and the viewer's own whatever their state.
    A title is often what held a post (a name, a phone number): every list that names a post by its title reads it
    here, in one query."""
    pks = [pk for pk in pks if pk]
    if not pks:
        return {}
    shown = counters.published()
    if viewer is not None and getattr(viewer, 'is_authenticated', False):
        shown |= Q(author=viewer)
    return dict(Contribution.objects.filter(shown, pk__in=pks, parent=None).values_list('pk', 'title'))


def _place_labels(paths: list[str], viewer=None) -> dict[str, dict]:
    by_slug = {p.slug: p for p in places.all_places()}
    split = {path: places.split_post(path) for path in paths}
    titles = readable_titles([pk for _, pk in split.values()], viewer)
    out = {}
    for path, (place, pk) in split.items():
        found = by_slug.get(place.removeprefix(places.PREFIX))
        out[path] = {'place': found.slug if found else '', 'name': found.name if found else None,
                     'title': titles.get(pk, '') if pk else '', 'article': '', 'text': ''}
    return out


def label_of(a: anchors.Anchor | None) -> dict:
    from apps.corpus.services.codes import display_name

    if a is None:
        return {'article': '', 'text': '', 'name': None, 'number': ''}
    return {'article': a.article.label, 'text': display_name(a.text)['ar'], 'name': display_name(a.text),
            'number': a.article.number}
