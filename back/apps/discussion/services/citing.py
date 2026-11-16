"""Citations in a contribution become links (the page's «citations become links»), read by the site's own citation
reader (`ma_law.parse_citations`, the one the search box uses). «المادة 32» alone is the article of the text the post
started from; with none, it names nothing."""
import ma_law

from apps.corpus.models import Text
from apps.corpus.services.addresses import article_path
from apps.corpus.services.citations import _find_article, resolve


def read(body: str, text: Text | None) -> list[dict]:
    links = []
    for c in ma_law.parse_citations(body) if body else []:
        start, end = c.get('start'), c.get('end')
        if start is None or end is None or body[start:end] != c.get('raw'):
            continue
        path = None
        if c.get('kind') == 'issue' and c.get('issue'):
            found = resolve(c)
            path = found['issue']['path'] if found.get('issue') else None
        elif c.get('article') and not (c.get('code') or c.get('text_number') or c.get('text_kind')):
            article = _find_article(text, c['article']) if text is not None else None
            path = article_path(text.akn_uri, article.eid) if article else None
        else:
            found = resolve(c)
            if found.get('article'):
                path = found['article']['path']
            elif found.get('text') and found['text'].get('in_corpus'):
                path = found['text']['path']
        if path:
            links.append({'start': start, 'end': end, 'path': path})
    return links


def articles(links: list[dict]) -> list[str]:
    """The articles among a contribution's links, in order, once each."""
    return list(dict.fromkeys(link['path'] for link in links if '/art_' in link['path']))


def text_for(c) -> Text | None:
    """The text a contribution's bare «المادة 32» belongs to: the article its post started from, or its old thread's."""
    from apps.accounts.services.refusals import Refused
    from apps.discussion.services import anchors

    for path in (c.about, (c.parent.about if c.parent_id else ''), c.discussion.path):
        if path and path.startswith('/ma/'):
            try:
                return anchors.find(path).text
            except Refused:
                continue
    return None
