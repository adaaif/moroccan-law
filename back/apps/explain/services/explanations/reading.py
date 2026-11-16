"""What readers see of the explanations: which addresses one may be of, the ones a reader may see (checked by a
real reviewer), «مفيد», a text's page bundle, an address's page with its history, the new texts explained, and the
words' meanings."""
from collections import Counter
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.corpus.models import Article, Text
from apps.corpus.services.addresses import split_path, text_path
from apps.corpus.services.codes import display_name
from apps.discussion.models import Report as TalkReport
from apps.discussion.services import anchors, counters, gates, holds, review
from apps.explain.models import Explanation, Helpful, Report, Revision

NEW_DAYS = 183


def checked():
    """The explanations a reader may see: checked by a reviewer, and not by one of the development's people (the public
    site showed the seeds' thirteen, «checked» by demo-staff, until 29 Oct 2026)."""
    from django.conf import settings

    rows = Explanation.objects.filter(reviewed_at__isnull=False)
    return rows if settings.SHOW_DEMO_PEOPLE else rows.exclude(counters.demo('reviewed_by__'))


def kind_of(path: str) -> str:
    """'article', 'text' or 'word'; '' for an address that is none of them."""
    if path.startswith('/words/'):
        return 'word'
    if not path.startswith('/ma/'):
        return ''
    return 'article' if split_path(path)[1] else 'text'


def text_of(path: str) -> str:
    """The text an address belongs to: the text itself for a text, '' for a word."""
    return text_path(split_path(path)[0]) if path.startswith('/ma/') else ''


def _hold_all(paths: list[str]) -> bool:
    """`_holds` for every one of these articles and texts, in three queries for the articles and one for the texts (a
    state's sources, twelve at most: three queries each before)."""
    articles = [p for p in paths if kind_of(p) == 'article']
    uris = {split_path(p)[0] for p in paths if kind_of(p) == 'text'}
    if articles and len(anchors.find_many(articles)) < len(set(articles)):
        return False
    return not uris or Text.objects.filter(akn_uri__in=uris).count() == len(uris)


def _holds(path: str) -> bool:
    kind = kind_of(path)
    if kind == 'article':
        try:
            anchors.find(path)
        except Refused:
            return False
        return True
    if kind == 'text':
        return Text.objects.filter(akn_uri=split_path(path)[0]).exists()
    if kind == 'word':
        from apps.explain.services.concepts import find
        return find(path.removeprefix('/words/')) is not None
    return False


def _public(e: Explanation, r: Revision) -> bool:
    """A state readers may read: checked by a real reviewer, never removed."""
    return bool(r.checked_at and not r.removed_at and not counters.is_demo(r.checked_by))


def helpful(user, path: str, register: str, on: bool) -> Explanation:
    """«مفيد», once a person; counted from a proven account three days old (the discussion's rule)."""
    gates.voter(user)
    e = checked().filter(path=path, register=register).first()
    if e is None:
        raise Refused('path', 'not_found', 404)
    with transaction.atomic():
        if on:
            try:
                with transaction.atomic():
                    Helpful.objects.create(user=user, explanation=e, counted=gates.vote_counts(user))
            except IntegrityError:
                pass
        else:
            Helpful.objects.filter(user=user, explanation=e).delete()
        e.helpful_count = e.votes.filter(counted=True).count()
        e.save(update_fields=['helpful_count'])
    return e


def _digests(text_path_: str, eids: set[str]) -> dict[str, str]:
    """These articles' words today, as digests, by anchor: what their explanations are compared with. Read as pairs:
    `version.articles.only(…)` deferred the version's key and Django read it back once an article (S4 of the
    performance audit: 1,320 queries for the DOC, whose articles have no explanation)."""
    if not eids:
        return {}
    text = Text.objects.filter(akn_uri=split_path(text_path_)[0]).first()
    version = text.latest_version() if text else None
    if version is None:
        return {}
    return {eid: anchors.digest(body) for eid, body in
            Article.objects.filter(version=version, eid__in=eids).values_list('eid', 'body')}


def short(e: Explanation, digest: str = '') -> dict:
    return {'register': e.register, 'headline': e.headline, 'body': e.body, 'sources': e.sources,
            'checked_on': timezone.localdate(e.reviewed_at) if e.reviewed_at else None, 'helpful': e.helpful_count,
            'outdated': bool(digest and e.article_digest and e.article_digest != digest),
            'editors': e.editors if hasattr(e, 'editors') else e.revisions.values('author').distinct().count()}


def _with_editors(rows) -> list[Explanation]:
    """Explanations with how many people wrote the states readers can read (a deleted account counts once, as before),
    in one query for all."""
    rows = list(rows)
    pairs = set(Revision.objects.filter(explanation__in=rows, checked_at__isnull=False, removed_at=None)
                .values_list('explanation_id', 'author_id')) if rows else set()
    count = Counter(e for e, _ in pairs)
    for e in rows:
        e.editors = count.get(e.pk, 0)
    return rows


def bundle(text_path_: str) -> dict:
    """What a text's page shows beside the law, in one request: the text's own explanation and each article's, in
    every register a reviewer checked."""
    shown = _with_editors(checked().filter(Q(path=text_path_) | Q(path__startswith=f'{text_path_}/')))
    digests = _digests(text_path_, {eid for e in shown if (eid := split_path(e.path)[1])})
    text: dict = {}
    articles: dict[str, dict] = {}
    for e in shown:
        eid = split_path(e.path)[1]
        if not eid:
            text[e.register] = short(e)
        else:
            articles.setdefault(eid, {'registers': {}})['registers'][e.register] = short(e, digests.get(eid, ''))
    return {'text': text, 'articles': articles}


def _state(e: Explanation, r: Revision) -> str:
    if r.removed_at:
        return 'removed'
    if r.checked_at:
        return 'checked'
    return 'waiting' if e.pending_id == r.pk else 'unchecked'


def _name(user) -> str | None:
    return holds.shown_name(user) if user is not None and not user.deleted_at else None


def _history(e: Explanation, revisions: list[Revision], viewer, reviewing: bool, reports: dict[int, int]) -> list[dict]:
    """The states this viewer may read, newest first: the checked ones for everyone; their own too for an author; all of
    them, with what held them and their reports, for a reviewer of the text."""
    out = []
    for r in revisions:
        mine = viewer is not None and r.author_id == viewer.pk
        if not (reviewing or _public(e, r) or (mine and not r.removed_at)):
            continue
        item = {'id': r.pk, 'body': r.body, 'headline': r.headline, 'sources': r.sources, 'note': r.note,
                'created_at': r.created_at, 'author': _name(r.author), 'state': _state(e, r)}
        if reviewing or mine:
            item.update(held_reasons=r.held_reasons, rule=r.removed_rule or None)
        if reviewing:
            item.update(held_spans=r.held_spans, reports=reports.get(r.pk, 0))
        out.append(item)
    return out


def _waiting_item(r: Revision, viewer, reviewing: bool) -> dict:
    return {'id': r.pk, 'headline': r.headline, 'body': r.body, 'sources': r.sources, 'note': r.note,
            'created_at': r.created_at, 'author': _name(r.author), 'mine': viewer is not None and r.author_id == viewer.pk,
            'held_reasons': r.held_reasons, **({'held_spans': r.held_spans} if reviewing else {})}


def detail(path: str, viewer) -> dict:
    """An address's explanation page: in each register the words readers see, their history, what the viewer may do.
    An edit that waits, and a register nobody checked yet, are shown to their author and the text's reviewers only."""
    kind = kind_of(path)
    if not kind or not _holds(path):
        raise Refused('path', 'not_found', 404)
    digest = ''
    if kind == 'article':
        digest = anchors.digest(anchors.find(path).article.body)
    signed = viewer is not None and viewer.is_authenticated
    viewer = viewer if signed else None
    reviewing = bool(signed and (viewer.is_staff or review.covers(viewer, text_of(path))))
    rows = _with_editors(Explanation.objects.filter(path=path).select_related('reviewed_by', 'pending__author'))
    voted = set(Helpful.objects.filter(user=viewer).values_list('explanation_id', flat=True)) if signed else set()
    # Every state of the address's registers (three at most), 50 a register, in one query.
    states: dict[int, list[Revision]] = {}
    for r in Revision.objects.filter(explanation__in=rows).select_related('author', 'checked_by'):
        if len(states.setdefault(r.explanation_id, [])) < 50:
            states[r.explanation_id].append(r)
    reports = dict(Report.objects.filter(revision__explanation__in=rows, status=TalkReport.Status.OPEN)
                   .values_list('revision').annotate(n=Count('pk'))) if reviewing and rows else {}
    registers = {}
    for e in rows:
        shown = e.reviewed_at is not None and not counters.is_demo(e.reviewed_by)
        pending = e.pending if e.pending is not None and not e.pending.removed_at else None
        sees_pending = pending is not None and (reviewing or (signed and pending.author_id == viewer.pk))
        if not shown and not sees_pending:
            continue
        revisions = states.get(e.pk, [])
        if shown:
            base = short(e, digest)
            showing = next((r for r in revisions if _public(e, r)), None)
        else:
            base = {**short(e, digest), 'headline': pending.headline, 'body': pending.body, 'sources': pending.sources,
                    'checked_on': None, 'outdated': False}
            showing = None
        registers[e.register] = {**base, 'waiting': not shown, 'voted': e.pk in voted,
                                 'shown_id': showing.pk if showing else None,
                                 'pending': _waiting_item(pending, viewer, reviewing) if sees_pending else None,
                                 'history': _history(e, revisions, viewer, reviewing, reports)}
    try:
        gates.writer(viewer)
        can_edit = True
    except Refused:
        can_edit = False
    return {'path': path, 'kind': kind, 'text_path': text_of(path), 'registers': registers, 'can_edit': can_edit,
            'can_review': reviewing, 'can_report': signed,
            # The first state asks for the agreement that a model reads it before a reviewer does (law 09-08).
            'consent': gates.standing(viewer).get('consent', True) if can_edit else True}


def new_items(days: int = NEW_DAYS) -> list[dict]:
    """«جديد يهمك»: texts of the last months that someone explained under a plain headline a reviewer checked, newest
    first."""
    since = timezone.localdate() - timedelta(days=days)
    rows = [e for e in checked().filter(path__startswith='/ma/').exclude(headline='')
            if kind_of(e.path) == 'text']
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={split_path(e.path)[0] for e in rows})
             .select_related('first_published_in')}
    # One item a text, in plain Arabic first; its other registers beside it (U11 of the Moroccan-design review: a
    # French reader reads the French headline where someone wrote one).
    order = {'ar': 0, 'darija': 1, 'fr': 2}
    rows.sort(key=lambda e: order.get(e.register, 9))
    out, seen = [], {}
    for e in rows:
        if e.path in seen:
            seen[e.path]['registers'][e.register] = {'headline': e.headline, 'summary': e.body}
            continue
        text = texts.get(split_path(e.path)[0])
        issue = text.first_published_in if text else None
        if not issue or issue.date < since:
            continue
        item = {'path': e.path, 'register': e.register, 'headline': e.headline, 'summary': e.body, 'reviewed': True,
                'checked_on': timezone.localdate(e.reviewed_at),
                'registers': {e.register: {'headline': e.headline, 'summary': e.body}},
                'text': {'title': text.title_ar, 'name': display_name(text), 'path': e.path, 'issue': {'number': issue.number, 'suffix': issue.suffix},
                         'page': text.first_published_page, 'date': issue.date}}
        seen[e.path] = item
        out.append(item)
    out.sort(key=lambda x: x['text']['date'], reverse=True)
    return out


def word_meanings() -> dict[str, dict[str, str]]:
    """Each checked word's meaning by register, in one query (the words' page shows them beside the terms): {slug: {ar,
    fr, darija: body}}."""
    out: dict[str, dict[str, str]] = {}
    for path, register, body in checked().filter(path__startswith='/words/') \
            .values_list('path', 'register', 'body'):
        out.setdefault(path.removeprefix('/words/'), {})[register] = body
    return out


def bundle_word(slug: str) -> dict:
    """A word's meaning in every register a reviewer checked."""
    return {'registers': {e.register: short(e) for e in
                          _with_editors(checked().filter(path=f'/words/{slug}'))}}
