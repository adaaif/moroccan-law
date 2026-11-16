"""The tools that hand over the law's texts: `search` (the site's search, its results as ChatGPT's deep research
expects them), `fetch` (an article, a text with its outline, or a Bulletin issue) and `read_articles` (a run of a text's
articles in order, as they read on a day). `articles` is the same run as data with each article's words, for the
versioned API (an assistant reads the words in read_articles' text)."""
from datetime import date

from django.conf import settings

from apps.consolidation.services import history
from apps.corpus.models import Text, TextType
from apps.corpus.services import generation
from apps.corpus.services.addresses import text_path
from apps.mcp.services.law.common import (ISSUE_ID, STATUS, Problem, _article_item, _eids, _head, _json, _law,
                                          _published, _run, _text_or_problem, _version, address, site)
from apps.mcp.services.law.issues import bulletin

MAX_RESULTS = 10
CITED = 'The article the citation names.'

MAX_RUN = 20                  # articles read_articles gives at once

OUTLINE_SHOWN = 150           # a text's outline lines fetch gives; read_articles reads on


# ── search ───────────────────────────────────────────────────────────────────

def search(query: str, via: str = 'mcp', log: bool = True) -> dict:
    """`via` says which door the words came by in the search's log. The versioned API passes `log=False`: a key names
    its holder, and what a holder asked is never kept."""
    from apps.search.services.search import search as find

    query = (query or '').strip()
    if not query:
        raise Problem('Give words to search: a question, a citation such as «المادة 53 من مدونة الشغل», or a law\'s name.',
                      code='q.required')
    out = find(query, via=via, log=log)
    results, seen = [], set()

    def add(item):
        if item['id'] not in seen and len(results) < MAX_RESULTS:
            seen.add(item['id'])
            results.append(item)

    jump = out.get('jump') or {}
    if jump.get('text') and jump.get('state') in ('found', 'repealed', 'text_only'):
        t = jump['text']
        status = STATUS.get(t.get('status'), t.get('status'))
        if jump.get('article'):
            a = jump['article']
            add({'id': a['path'], 'title': f"{a['label']} — {(t.get('name') or {}).get('ar') or t['title']}",
                 'url': site(a['path']), 'text': CITED, 'status': status, 'kind': 'article'})
        add({'id': t['path'], 'title': (t.get('name') or {}).get('ar') or t['title'], 'url': site(t['path']),
             'text': t['title'], 'status': status, 'kind': 'text'})
    for r in out.get('results') or []:
        t = r['text']
        name = (t.get('name') or {}).get('ar') or t['title']
        status = STATUS.get(t.get('status'), t.get('status'))
        if t.get('type') == TextType.BILL:
            status = 'a bill: not law'
        if r.get('title_match') and not r['articles']:
            add({'id': t['path'], 'title': name, 'url': site(t['path']), 'text': t['title'], 'status': status,
                 'kind': 'text'})
        for a in r['articles']:
            words = ''.join(s.get('t', '') for s in a.get('snippet') or []).strip()
            add({'id': a['path'], 'title': f"{a['label']} — {name}", 'url': site(a['path']), 'text': words,
                 'status': status, 'kind': 'article'})
    _first_words(results)
    answer = {'results': results}
    if out.get('repaired'):
        answer['searched_as'] = out['repaired']
    if not results:
        answer['note'] = ('Nothing found. Try the law\'s own words in Arabic or French, the text\'s number '
                          '(«القانون 65.99»), or fewer words.')
    return answer


def _first_words(results: list[dict]) -> None:
    """A cited article has no snippet: its first words instead, from the search index (one query)."""
    from apps.search.models import SearchEntry

    bare = [r for r in results if r['kind'] == 'article' and r['text'] == CITED]
    if not bare:
        return
    bodies = dict(SearchEntry.objects.filter(kind=SearchEntry.Kind.ARTICLE, path__in=[r['id'] for r in bare])
                  .values_list('path', 'body'))
    for r in bare:
        words = ' '.join((bodies.get(r['id']) or '').split()[:40])
        r['text'] = words + (' …' if words and len((bodies.get(r['id']) or '').split()) > 40 else '') or r['text']


# ── fetch ────────────────────────────────────────────────────────────────────

def fetch(raw_id: str) -> tuple[dict, int]:
    """(the item, the article bodies it gives)."""
    path = address(raw_id)
    if ISSUE_ID.match(path):
        issue = bulletin(path)['issues'][0]
        lines = [f"• {t['kind']}: {t['title']} (p. {t['page']}) — {t['id']}" for t in issue['texts']]
        return {'id': f"bo/{issue['key']}", 'title': f"الجريدة الرسمية عدد {issue['key']} ({issue['date']})",
                'text': '\n'.join(lines) or f'This issue published no text {settings.SITE_NAME} holds.', 'url': issue['url'],
                'metadata': {'kind': 'bulletin_issue', 'edition': issue['edition'], 'date': issue['date'],
                             'texts': len(issue['texts'])}}, 0
    text, uri, eid = _text_or_problem(path)
    head = _head(text, uri)
    law = _law(head)
    if eid:
        eids = _eids(text)
        if eid not in eids:
            raise Problem(f"{law['name_ar'] or law['title']} has no {eid.replace('art_', 'article ')} in its current "
                          f'version ({len(eids)} articles). Use read_articles on {law["id"]} to read them in order.',
                          code='id.not_found')
        at = eids.index(eid)
        article = _run(text, uri, at, at + 1)['articles'][0]
        item = _article_item(article, head, law)
        meta = {'kind': 'article', 'law': law, 'status': item['status'], 'heading': item['heading'],
                'citation': item['citation'], 'published_in': _published(head), 'version': _version(head),
                'changes': item['changes'], 'french': item['french'], 'position': f'{at + 1} of {len(eids)}'}
        if item.get('cut'):
            meta['cut'] = item['cut']
        return {'id': item['id'], 'title': item['title'], 'text': item['text'], 'url': item['url'], 'metadata': meta}, 1
    eids = _eids(text)
    lines = _outline(text, head, eids)
    meta = {'kind': 'text', 'law': law, 'published_in': _published(head), 'version': _version(head),
            'articles': len(eids), 'signed_on': head.get('signed_on'), 'authority': head.get('authority') or '',
            'french_title': (head.get('french') or {}).get('title'),
            'amended_by': [{'id': c['by']['path'], 'title': c['by']['title'], 'published': c.get('published_on')}
                           for c in (head.get('amended_by') or [])[-10:] if c.get('by')]}
    if text.type == TextType.BILL:
        meta['note'] = 'A bill (projet de loi) as filed or voted in a chamber: it is not law.'
    return {'id': law['id'], 'title': law['title'], 'text': '\n'.join(lines), 'url': law['url'], 'metadata': meta}, 0


def _outline(text: Text, head: dict, eids: list[str]) -> list[str]:
    from apps.corpus.api.views import outline
    from apps.corpus.models import Article

    version = (head.get('version') or {})
    if not eids:
        return [f"{settings.SITE_NAME} holds this text's title and publication, not its articles."]
    picked, _ = history.pick_version(text, None)

    def build():
        rows = list(Article.objects.filter(version=picked).order_by('order')
                    .only('id', 'version_id', 'eid', 'label', 'number', 'body', 'heading_path'))
        return {'version': picked.pk, 'outline': outline(rows)}
    entries = _json(generation.answer(['outline', picked.pk], build))['outline']
    lines = [f"{len(eids)} articles; version in force since {version.get('valid_from', '?')}."]
    for e in entries[:OUTLINE_SHOWN]:
        if e.get('h'):
            lines.append('§ ' + ' › '.join(e['h']))
        lines.append(f"  {e['label']} ({text_path(text.akn_uri)}/{e['eid']}): {e['w']}")
    if len(entries) > OUTLINE_SHOWN:
        lines.append(f'… {len(entries) - OUTLINE_SHOWN} more articles: read them with read_articles.')
    return lines


# ── read_articles ────────────────────────────────────────────────────────────

def _read(raw_id: str, start: str, count: int, on: str, french: bool) -> dict:
    """What read_articles and articles share: the text's facts, the run of its articles as items, and where they stand
    in it."""
    path = address(raw_id)
    text, uri, eid = _text_or_problem(path)
    day = None
    if on:
        try:
            day = date.fromisoformat(on)
        except ValueError:
            raise Problem(f'«{on}» is not a date: give it as YYYY-MM-DD, e.g. 2022-03-01.', code='on.invalid') from None
    head = _head(text, uri, day)
    law = _law(head)
    eids = _eids(text, day)
    if not eids:
        when = f' on {day}' if day else ''
        raise Problem(f"{settings.SITE_NAME} holds no version of {law['name_ar'] or law['title']}{when}"
                      + (' (it may not have existed yet).' if day else '.'),
                      code='on.not_found' if day else 'id.not_found')
    first = eid
    if start:
        wanted = start.strip().removeprefix('art_')
        first = f'art_{wanted}'
        if first not in eids:
            first = next((e for e in eids if e.split('_', 1)[-1].split('-')[0] == wanted.split('-')[0]), '')
            if not first:
                raise Problem(f'No article {start} in this version of {law["name_ar"] or law["title"]} '
                              f'({len(eids)} articles).', code='start.not_found')
    at = eids.index(first) if first in eids else 0
    count = max(1, min(int(count or 10), MAX_RUN))
    rows = _run(text, uri, at, at + count, day)['articles']
    items = [_article_item(a, head, law, french=french) for a in rows]
    version = _version(head)
    early = ''
    if day and version and version['in_force_since'] > str(day):
        published = (head.get('issue') or {}).get('date')
        if published and published > str(day):
            early = (f'This text was published in the Bulletin officiel on {published}, after {day}: it did not exist '
                     f"yet. Below is its text from {version['in_force_since']}.")
        else:
            early = (f"{settings.SITE_NAME} holds this text only as it reads from {version['in_force_since']}: on {day} it may have "
                     'read otherwise. Each article below says whether it changed after that day, and when.')
    end = at + len(rows)
    return {'law': law, 'version': version, 'day': day, 'head': head, 'early': early, 'items': items, 'at': at,
            'end': end, 'eids': eids, 'next': f"{law['id']}/{eids[end]}" if end < len(eids) else None}


def _data(run: dict, articles: list[dict]) -> dict:
    day = run['day']
    return {'law': run['law'], 'version': run['version'], 'on': str(day) if day else None,
            'published_in': _published(run['head']), 'note': run['early'] or None, 'articles': articles,
            'range': [run['at'] + 1, run['end']], 'total': len(run['eids']), 'next': run['next']}


def read_articles(raw_id: str, start: str = '', count: int = 10, on: str = '', french: bool = False) -> tuple[str, dict, int]:
    """(text, data, article bodies served)."""
    run = _read(raw_id, start, count, on, french)
    law, version, day, early, items, eids, end = (run[k] for k in ('law', 'version', 'day', 'early', 'items', 'eids',
                                                                   'end'))
    lines = [f"{law['title']} — {law['status']}", early,
             f"Version: {version['source'] if version else 'unknown'}"
             + (f", in force since {version['in_force_since']}" if version else '')
             + (f' (as it stood on {day})' if day else ''),
             version.get('note', '') if version else '', '']
    for it in items:
        lines.append(f"{it['label']} — {it['url']}")
        if it['heading']:
            lines.append(f"[{it['heading']}]")
        lines.append(it['text'])
        if it.get('cut'):
            lines.append(it['cut'])
        if it['status'] == 'repealed':
            lines.append('(This article is repealed.)')
        if early and day:
            after = sorted({str(c['on']) for c in it['changes'] if c.get('on') and str(c['on']) > str(day)})
            lines.append(f"(Changed after {day}: on {', '.join(after)}; it then read otherwise.)" if after
                         else f'(No change to this article after {day} is recorded.)')
        if french and it.get('french'):
            lines.append(f"{it['french']['label']} — {it['french']['text']}")
        lines.append('')
    if run['next']:
        lines.append(f'Next: read_articles from {eids[end].removeprefix("art_")} ({len(eids) - end} more articles).')
    data = _data(run, [{'id': it['id'], 'label': it['label'], 'url': it['url'], 'status': it['status'],
                        'changes': it['changes']} for it in items])
    return '\n'.join(line for line in lines if line is not None).strip(), data, len(items)


def articles(raw_id: str, start: str = '', count: int = 10, on: str = '', french: bool = False) -> tuple[dict, int]:
    """read_articles' run as data alone, each article whole: its words, heading and citation, its changes, its
    standing, and its official French when `french` asks (null where the BO printed none). (data, article bodies
    served)."""
    run = _read(raw_id, start, count, on, french)
    return _data(run, run['items']), len(run['items'])
