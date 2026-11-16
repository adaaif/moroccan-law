"""Where a contribution sits: an article of a text's current version, by its address on the site."""
import hashlib
from dataclasses import dataclass

from apps.accounts.services.refusals import Refused
from apps.corpus.models import Article, Text, Version
from apps.corpus.services.addresses import article_path, split_path, text_path


@dataclass
class Anchor:
    path: str
    text_path: str
    text: Text
    version: Version
    article: Article


def find(path: str) -> Anchor:
    uri, eid = split_path(str(path or ''))
    text = Text.objects.filter(akn_uri=uri).first() if eid and str(path).startswith('/ma/') else None
    version = text.latest_version() if text else None
    article = version.articles.filter(eid=eid).first() if version else None
    if article is None:
        raise Refused('path', 'not_found', 404)
    return Anchor(article_path(uri, eid), text_path(uri), text, version, article)


def find_many(paths) -> dict[str, Anchor]:
    """`find` for many addresses: three queries for all of them. An address that is no article of a current version
    is left out (where `find` refuses it)."""
    from django.db.models import Q

    wanted = {}
    for path in dict.fromkeys(paths):
        uri, eid = split_path(str(path or ''))
        if eid and str(path).startswith('/ma/'):
            wanted[path] = (uri, eid)
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={uri for uri, _ in wanted.values()})
             .prefetch_related('versions')} if wanted else {}
    latest = {uri: t.latest_version() for uri, t in texts.items()}
    found = Q()
    for uri, eid in wanted.values():
        if latest.get(uri):
            found |= Q(version_id=latest[uri].pk, eid=eid)
    articles = {}
    for a in Article.objects.filter(found).order_by('version_id', 'order') if found else []:
        articles.setdefault((a.version_id, a.eid), a)
    out = {}
    for path, (uri, eid) in wanted.items():
        version = latest.get(uri)
        article = articles.get((version.pk, eid)) if version else None
        if article is not None:
            out[path] = Anchor(article_path(uri, eid), text_path(uri), texts[uri], version, article)
    return out


def plain(words: str) -> str:
    return ' '.join(words.split())


def digest(body: str) -> str:
    """The article's words, spacing aside: a contribution compares it with today's to know the article changed."""
    return hashlib.sha1(plain(body).encode(), usedforsecurity=False).hexdigest()
