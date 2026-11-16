"""Writing an explanation: a state checked for its lengths and addresses, passed through the discussion's guards
(the fixed patterns, then the check), kept as a revision, and shown at once when a reviewer of its text wrote it and
nothing held it; anyone else's waits for a reviewer."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.corpus.models import Text
from apps.corpus.services.addresses import split_path
from apps.corpus.services.codes import display_name
from apps.discussion.services import anchors, gates, holds, review
from apps.discussion.services import check as talk_check
from apps.explain.models import BODY_MAX, HEADLINE_MAX, NOTE_MAX, SOURCES_MAX, Explanation, Register, Revision
from apps.explain.services.explanations.reading import _hold_all, _holds, kind_of, text_of


def _clean(user, path: str, register: str, body: str, headline: str, sources, note: str) -> tuple:
    if register not in Register.values:
        raise Refused('register', 'invalid')
    body, headline, note = (body or '').strip(), (headline or '').strip(), (note or '').strip()
    if not body:
        raise Refused('body', 'required')
    if len(body) > BODY_MAX:
        raise Refused('body', 'too_long')
    if len(headline) > HEADLINE_MAX:
        raise Refused('headline', 'too_long')
    if len(note) > NOTE_MAX:
        raise Refused('note', 'too_long')
    if not _holds(path):
        raise Refused('path', 'not_found', 404)
    sources = [s for s in dict.fromkeys(sources or []) if isinstance(s, str) and s.strip()]
    if len(sources) > SOURCES_MAX:
        raise Refused('sources', 'too_many')
    if any(kind_of(s) not in ('article', 'text') for s in sources) or not _hold_all(sources):
        raise Refused('sources', 'not_found')
    return body, headline, sources, note


def _topic(path: str) -> dict:
    """What the check is told it reads: the «باختصار» of which article, text or word."""
    kind = kind_of(path)
    if kind == 'article':
        a = anchors.find(path)
        return {'ar': f'«باختصار»: شرح {a.article.label} من {display_name(a.text)["ar"]}', 'fr': ''}
    if kind == 'text':
        text = Text.objects.filter(akn_uri=split_path(path)[0]).first()
        return {'ar': f'«باختصار»: شرح {display_name(text)["ar"] if text else path}', 'fr': ''}
    from apps.explain.services.concepts import find
    term = ((find(path.removeprefix('/words/')) or {}).get('term') or {}).get('ar', '')
    return {'ar': f'«باختصار»: معنى كلمة «{term}» في القانون', 'fr': ''}


def _guarded(user, path: str, headline: str, body: str, note: str) -> tuple[list[str], list[list]]:
    """The discussion's guards over a state: the fixed patterns on the headline, the words and the note (the spans
    point into the words), then the check when they hold nothing. A return names a rule as a hold does: a reviewer
    reads every state before readers anyway."""
    reasons, spans = holds.scan(body)
    reasons = sorted(set(reasons) | set(holds.scan(headline)[0]) | set(holds.scan(note)[0]))
    if not reasons:
        v = talk_check.verdict(user, place=_topic(path), title=headline, body='\n\n'.join(x for x in (body, note) if x))
        if v.outcome != 'publish':
            reasons = v.reasons
    return reasons, spans


def _shows(e: Explanation, r: Revision, user, now) -> None:
    """`r` becomes the words readers see (e is saved by the caller)."""
    e.headline, e.body, e.sources = r.headline, r.body, r.sources
    if kind_of(e.path) == 'article':
        anchor = anchors.find(e.path)
        e.version_on, e.article_digest = anchor.version.valid_from, anchors.digest(anchor.article.body)
    e.reviewed_at, e.reviewed_by, e.pending = now, user, None
    r.checked_at, r.checked_by = now, user
    r.save(update_fields=['checked_at', 'checked_by'])


def _latest(e: Explanation) -> tuple[str, str, list]:
    """The words an edit is compared with: the one waiting, else those readers see."""
    r = e.pending
    return (r.body, r.headline, r.sources) if r is not None else (e.body, e.headline, e.sources)


def save(user, path: str, register: str, body: str, *, headline: str = '', sources=None, note: str = '',
         consent: bool = False) -> Explanation:
    """Write or improve the explanation of `path` in `register`. A reviewer of its text who writes it checks it at the
    same time when no guard held it; anyone else's change waits for a reviewer, and readers keep the checked words."""
    gates.writer(user)
    body, headline, sources, note = _clean(user, path, register, body, headline, sources, note)
    e = Explanation.objects.filter(path=path, register=register).select_related('pending').first()
    if e is not None and _latest(e) == (body, headline, sources):
        return e
    gates.day_limit(user)
    gates.consent(user, consent)
    reasons, spans = _guarded(user, path, headline, body, note)
    checks = (review.covers(user, text_of(path)) or user.is_staff) and not reasons
    now = timezone.now()
    with transaction.atomic():
        e, _created = Explanation.objects.select_for_update().get_or_create(
            path=path, register=register, defaults={'body': body, 'headline': headline, 'sources': sources})
        r = Revision.objects.create(explanation=e, author=user, headline=headline, body=body, sources=sources,
                                    note=note, held_reasons=reasons, held_spans=spans)
        if checks:
            _shows(e, r, user, now)
        else:
            e.pending = r
        e.save()
    return e
