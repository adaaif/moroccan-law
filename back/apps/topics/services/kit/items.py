"""What an item of a topic's folder is made of and what is said of it: the article addresses it cites, at any depth
and in the order it names them; those articles, from each text's newest version, with a digest of their words; whether
a reader may see it, and its state since its check; the item with its articles in place of their addresses; the pages
it leads to."""
import hashlib
from functools import reduce
from operator import or_

from django.conf import settings
from django.db.models import Q

from apps.corpus.models import Article, Text
from apps.corpus.services.addresses import article_path, split_path


def digest(body: str) -> str:
    return hashlib.sha1(' '.join(body.split()).encode(), usedforsecurity=False).hexdigest()[:16]


def cited(obj) -> set[str]:
    """Every article address an item cites, at any depth."""
    found: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'cites' and isinstance(v, list):
                found.update(p for p in v if isinstance(p, str))
            else:
                found |= cited(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= cited(v)
    return found


def articles(paths: set[str]) -> dict[str, dict]:
    """{path: {label, path, text {ar, fr}, number, digest}} for the cited articles, from each text's newest version."""
    from apps.corpus.services.codes import display_name

    by_uri: dict[str, set[str]] = {}
    for p in paths:
        uri, eid = split_path(p.strip('/'))
        by_uri.setdefault(uri, set()).add(eid)
    # The texts with their versions, then every cited article of their newest versions, in one query each (a version
    # and an article query a cited text before: found by the repeated-queries log).
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=by_uri).prefetch_related('versions')}
    newest = {uri: v for uri, t in texts.items() if (v := t.latest_version()) is not None}
    wanted = reduce(or_, (Q(version=v, eid__in=by_uri[uri]) for uri, v in newest.items()), Q(pk__in=[]))
    of_version = {v.pk: uri for uri, v in newest.items()}
    out = {}
    for a in Article.objects.filter(wanted).order_by('version_id', 'order'):
        text = texts[of_version[a.version_id]]
        path = article_path(text.akn_uri, a.eid)
        out[path] = {'path': path, 'label': a.label, 'number': a.number, 'text': display_name(text),
                     'digest': digest(a.body), 'body': a.body}
    return out


def shown(item: dict) -> bool:
    return bool(item.get('checked') or item.get('open')) or settings.SHOW_DRAFTS     # `open`: before a check, saying so


def state(item: dict, arts: dict[str, dict]) -> str:
    """'draft' (never checked), 'stale' (an article it cites changed since its check), or 'checked'."""
    checked = item.get('checked')
    if not checked:
        return 'draft'
    for path, was in (checked.get('digests') or {}).items():
        now = arts.get(path)
        if now is None or now['digest'] != was:
            return 'stale'
    return 'checked'


def _resolve(obj, arts: dict[str, dict]):
    """The item with each cited address replaced by its article (label, text, address); a missing one is dropped."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == 'cites' and isinstance(v, list):
                out[k] = [{k2: arts[p][k2] for k2 in ('path', 'label', 'number', 'text')} for p in v if p in arts]
            elif k == 'checked':
                out[k] = None if not v else {'by': v.get('by'), 'on': v.get('on')}
            else:
                out[k] = _resolve(v, arts)
        return out
    if isinstance(obj, list):
        return [_resolve(v, arts) for v in obj]
    return obj


LINKS = ('to', 'next', 'papers', 'tool', 'more')


def links(obj) -> set[str]:
    """Every page an item leads to (`to`, `next`, `papers`, `tool`, `more`), at any depth: journeys/marry, tools/dates."""
    found: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in LINKS:
                # A tool's link may carry its case (PX3: «tools/deadline?k=crim-appeal»): the page it leads to is the tool.
                found.update(x.split('?')[0] for x in (v if isinstance(v, list) else [v]) if isinstance(x, str) and '/' in x)
            else:
                found |= links(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= links(v)
    return found


def cited_in_order(obj) -> list[str]:
    """`cited`, in the order the item names them: its first step's articles first."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'cites' and isinstance(v, list):
                found.extend(p for p in v if isinstance(p, str))
            else:
                found.extend(cited_in_order(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(cited_in_order(v))
    return list(dict.fromkeys(found))
