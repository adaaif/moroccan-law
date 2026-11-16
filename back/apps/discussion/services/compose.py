"""Writing, editing and deleting a post or a comment.

A post lives in a topic's place (/talk/family), with a title, as a question or a post (C4 of 29 Oct 2026); a comment
sits under a post, and a comment on a comment joins the post's comments and says whom it answers (W7). A post may
start from an article («اسأل على هاد المادة»): its quote must be the article's own words. Citations become links, and
every article a contribution cites is kept with a digest of its words (Cite), for the article's page and D14.

It is published at once once a model has read it (check.py: the choice of 29 Oct 2026, which replaced the newcomer's
wait), unless something holds it: a pattern in the words (holds.py, before any model: what the patterns
hold a person decides), the model's hold, the check unable to run, a picture before its author is trusted. The model
may also return it to its author with a rule; the author can send it to a moderator as it is. A voice is never
anonymous and never edited; a picture is never edited; the text is, with its earlier versions kept for the
reviewers."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import (BODY_MAX, PICTURES_MAX, POST_KINDS, QUOTE_MAX, TITLE_MAX, Cite, Contribution,
                                    Discussion, Follow, Kind, Report, Revision)
from apps.discussion.services import anchors, check, citing, counters, gates, holds, notices, places, votes
from apps.media.models import Clip, Picture, State
from apps.media.services import files

FREEZE = timedelta(days=30)
TITLE_MIN = 3


def _media_state(c: Contribution, state: str) -> None:
    files.set_state([c.clip, *c.pictures.all()], state)


def _cite(c: Contribution) -> None:
    """What the contribution cites, again: the article it started from and every article its words name."""
    paths = list(dict.fromkeys(([c.about] if c.about else []) + citing.articles(c.links)))
    found = anchors.find_many(paths)
    Cite.objects.filter(contribution=c).delete()
    Cite.objects.bulk_create([Cite(contribution=c, path=path, text_path=found[path].text_path,
                                   digest=anchors.digest(found[path].article.body)) for path in paths if path in found])


def _checked(user, discussion: Discussion, title: str, body: str, parent, insist: bool) -> check.Verdict | None:
    """The model's verdict on words no pattern held. Returned to its author unless they send it as it is."""
    v = check.verdict(user, place=places.find(discussion.path).name, title=title, body=body, parent=parent)
    if v.outcome == 'return' and not insist:
        raise Refused('check', v.rule, 422)
    return v


def _scan(title: str, body: str) -> tuple[list[str], list[list]]:
    """The holds' patterns over the title and the words; the spans point into the words."""
    reasons, spans = holds.scan(body)
    return sorted(set(reasons) | set(holds.scan(title)[0])), spans


def contribute(user, *, path: str = '', kind: str = '', title: str = '', body: str = '', about: str = '',
               quote: str = '', parent_id=None, anonymous: bool = False, clip_id=None, picture_ids=(),
               consent: bool = False, insist: bool = False) -> Contribution:
    gates.writer(user)
    parent = reply_to = None
    if parent_id:
        target = Contribution.objects.filter(pk=parent_id).select_related('parent', 'discussion').first()
        # Two levels: an answer to an answer joins the first one's answers, and says whom it answers (W7).
        parent = target.parent if target and target.parent_id else target
        reply_to = target if target and target.parent_id else None
        if parent is None or not parent.published or (reply_to and not reply_to.published):
            raise Refused('parent', 'not_found', 404)
        discussion = parent.discussion
    else:
        place = places.find(path)
        discussion, _ = Discussion.objects.get_or_create(path=place.path, defaults={'text_path': place.path})
    # The article threads of before 29 Oct 2026 stay in the database, never written in: a question goes to a topic.
    if not places.is_place(discussion.path):
        raise Refused('path', 'not_a_place')
    if discussion.locked_at:
        raise Refused('discussion', 'locked', 403)
    title, body = ' '.join((title or '').split()), (body or '').strip()
    if parent is None:
        if kind not in POST_KINDS:
            raise Refused('kind', 'invalid')
        if len(title) < TITLE_MIN:
            raise Refused('title', 'required')
        if len(title) > TITLE_MAX:
            raise Refused('title', 'too_long')
    else:
        kind, title, about, quote = Kind.COMMENT, '', '', ''
    if len(body) > BODY_MAX:
        raise Refused('body', 'too_long')
    anchor = None
    if about:
        try:
            anchor = anchors.find(about)
        except Refused:
            raise Refused('about', 'not_found', 404) from None
    quote = anchors.plain(quote or '')
    if len(quote) > QUOTE_MAX:
        raise Refused('quote', 'too_long')
    if quote and (anchor is None or quote not in anchors.plain(anchor.article.body)):
        raise Refused('quote', 'not_in_article')
    clip = files.draft_of(Clip, user, clip_id) if clip_id else None
    picture_ids = list(dict.fromkeys(picture_ids or []))
    if len(picture_ids) > PICTURES_MAX:
        raise Refused('pictures', 'too_many')
    pictures = [files.draft_of(Picture, user, pk) for pk in picture_ids]
    if parent is not None and not (body or clip or pictures):
        raise Refused('body', 'required')
    if anonymous and clip:
        raise Refused('anonymous', 'voice')
    if clip:
        gates.may_voice(user)
    if pictures:
        gates.may_picture(user)
    gates.day_limit(user)

    gates.consent(user, consent)
    reasons, spans = _scan(title, body)
    looked = None
    if not reasons:
        looked = _checked(user, discussion, title, body, parent, insist)
        if looked.outcome != 'publish':
            reasons += looked.reasons
    if pictures and gates.pictures_held(user):
        reasons.append('pictures')
    reasons.sort()
    now = timezone.now()
    with transaction.atomic():
        c = Contribution.objects.create(
            discussion=discussion, parent=parent, reply_to=reply_to, author=user, kind=kind, title=title, body=body,
            about=anchor.path if anchor else '', quote=quote,
            links=citing.read(body, anchor.text if anchor else None), anonymous=bool(anonymous), clip=clip,
            version_on=anchor.version.valid_from if anchor else None,
            article_digest=anchors.digest(anchor.article.body) if anchor else '',
            held_at=now if reasons else None, held_reasons=reasons, held_spans=spans,
            active_at=now if parent is None else None)
        if looked is not None and looked.record is not None:
            looked.record.contribution = c
            looked.record.save(update_fields=['contribution'])
        c.pictures.set(pictures)
        _cite(c)
        # Held: its files are for the reviewers and its author only, until a reviewer publishes it.
        _media_state(c, State.EVIDENCE if reasons else State.LIVE)
        # Writing follows the post: its comments are told, not the whole topic's.
        Follow.objects.get_or_create(user=user, path=places.post_path(c))
        counters.around(c)
        if not reasons:
            notices.on_published(c)
    return c


def mine(user, pk) -> Contribution:
    c = Contribution.objects.filter(pk=pk, author=user).select_related('discussion', 'parent', 'clip').first()
    if c is None or c.deleted_at or c.erased_at:
        raise Refused('contribution', 'not_found', 404)
    return c


def edit(user, pk, body: str, title: str | None = None, insist: bool = False) -> Contribution:
    gates.writer(user)
    c = mine(user, pk)
    if c.removed_at:
        raise Refused('contribution', 'removed', 409)
    body = (body or '').strip()
    if len(body) > BODY_MAX:
        raise Refused('body', 'too_long')
    title = c.title if title is None or c.parent_id else ' '.join(title.split())
    if c.parent_id is None and places.is_place(c.discussion.path) and not TITLE_MIN <= len(title) <= TITLE_MAX:
        raise Refused('title', 'required' if len(title) < TITLE_MIN else 'too_long')
    if c.parent_id is not None and not (body or c.clip_id or c.pictures.exists()):
        raise Refused('body', 'required')
    if body == c.body and title == c.title:
        return c
    anchor = None
    if c.about:
        try:
            anchor = anchors.find(c.about)
        except Refused:
            anchor = None
    reasons, spans = _scan(title, body)
    looked = None
    if not reasons:
        looked = _checked(user, c.discussion, title, body, c.parent, insist) if places.is_place(c.discussion.path) \
            else None
        if looked is not None and looked.outcome != 'publish':
            reasons += looked.reasons
    with transaction.atomic():
        if looked is not None and looked.record is not None:
            looked.record.contribution = c
            looked.record.save(update_fields=['contribution'])
        Revision.objects.create(contribution=c, body=c.body if not c.title else f'{c.title}\n\n{c.body}')
        c.title, c.body, c.links, c.edited_at = title, body, citing.read(body, anchor.text if anchor else None), timezone.now()
        fields = ['title', 'body', 'links', 'edited_at']
        released = False
        # An edit that brings a phone number in waits for a reviewer like a new contribution would.
        if reasons and not c.held_at:
            c.held_at, c.held_reasons, c.held_spans = timezone.now(), reasons, spans
            fields += ['held_at', 'held_reasons', 'held_spans']
            _media_state(c, State.EVIDENCE)
        elif c.held_at:
            kept = [r for r in c.held_reasons if r in ('pictures', 'returned')]
            # Sent back by a reviewer (M4): edited, it returns to the top of the queue.
            if 'sent_back' in c.held_reasons:
                kept.append('returned')
            c.held_reasons, c.held_spans = sorted(set(kept + reasons)), spans
            fields += ['held_reasons', 'held_spans']
            # Held only for what the author has now taken out (F1): published, as if it had been written so.
            if not c.held_reasons:
                c.held_at, released = None, True
                fields.append('held_at')
                _media_state(c, State.LIVE)
        c.save(update_fields=fields)
        _cite(c)
        counters.around(c)
        if released:
            notices.on_published(c)
    return c


def erase(c: Contribution) -> None:
    """The words and files go; the row stays while answers hang under it."""
    erase_many([c])


def erase_many(rows: list[Contribution]) -> None:
    """`erase` for many contributions at once, in a fixed number of queries (six a contribution before): their voices
    and pictures read together, their words emptied in one update, their earlier wordings and citations deleted in one
    statement each, and the discussion's kept answers renewed once, as each save renewed them."""
    from django.db.models import prefetch_related_objects

    from apps.corpus.services import generation

    if not rows:
        return
    prefetch_related_objects(rows, 'clip', 'pictures')
    files.erase([f for c in rows for f in (c.clip, *c.pictures.all())])
    now = timezone.now()
    for c in rows:
        c.title, c.body, c.quote, c.links, c.held_spans, c.erased_at = '', '', '', [], [], now
    Contribution.objects.bulk_update(rows, ['title', 'body', 'quote', 'links', 'held_spans', 'erased_at'])
    generation.bump('talk')
    Revision.objects.filter(contribution__in=rows).delete()
    Cite.objects.filter(contribution__in=rows).delete()


def delete(user, pk) -> None:
    """Deleting erases at once. Under an open report the contribution stays for the reviewers until they decide,
    30 days at most (frozen); readers never see it again either way."""
    c = mine(user, pk)
    with transaction.atomic():
        c.deleted_at = timezone.now()
        votes.void_all(c)
        if c.reports.filter(status=Report.Status.OPEN).exists():
            c.frozen_until = timezone.now() + FREEZE
            c.save(update_fields=['deleted_at', 'frozen_until'])
            _media_state(c, State.EVIDENCE)
        else:
            c.save(update_fields=['deleted_at'])
            erase(c)
        counters.around(c)
