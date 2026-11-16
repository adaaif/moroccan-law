"""Situations (row 4 of the reader-experience review): «وقعت لي حادثة سير», «طُردت من العمل» — the articles to read first,
each said in a plain sentence, and the texts it rests on, including those the site does not hold yet. The sentences
are drafted by Claude Haiku from the site's own articles (`draft`) and reach readers only once an editor has approved
them (call C2): data/situations_approved.json. A draft never gives advice; it says what an article says."""
import json
import re
from pathlib import Path

from django.conf import settings

from apps.corpus.models import Text
from apps.corpus.services.addresses import split_path, text_path
from apps.corpus.services.codes import SHELF, books_of, shelf
from apps.corpus.services.llm import request, run_batch
from apps.search.services.search import search

DATA = Path(__file__).resolve().parent.parent / 'data'
SITUATIONS = DATA / 'situations.json'
DRAFTS = DATA / 'situations_drafts.json'
APPROVED = DATA / 'situations_approved.json'
# Step-by-step guides (R10 of the for-everyone review): drafts until a lawyer reviewed them and an editor approved them
# (an approved situation carries its own `guide`).
GUIDES = DATA / 'situation_guides.json'
TOPICS = Path(__file__).resolve().parent.parent.parent / 'topics' / 'data' / 'topics.json'
MODEL = 'claude-haiku-5-5'
CANDIDATES = 24

SYSTEM = (
    'You help Moroccan readers find their way in the law. For a situation a person is in, you get candidate '
    'articles found in 3adala («قانون» in Arabic), a library of Moroccan law (each with its address, text and words). Choose the 3 to 6 '
    'articles a person in that situation should read first, most useful first, and say for each, in one plain '
    'sentence, what the article says — never what to do, never advice, nothing the article does not say. Then '
    'write a two-sentence introduction naming which texts govern the situation (only from the candidates and the '
    'texts listed as not yet in 3adala), plain and neutral. Write each sentence in Modern Standard Arabic and in '
    'French (the French reader uses «vous»). If no candidate fits, return no articles and say so in the '
    'introduction.'
)
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['intro', 'articles'],
    'properties': {
        'intro': {'type': 'object', 'additionalProperties': False, 'required': ['ar', 'fr'],
                  'properties': {'ar': {'type': 'string'}, 'fr': {'type': 'string'}}},
        'articles': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['path', 'says'],
            'properties': {'path': {'type': 'string'},
                           'says': {'type': 'object', 'additionalProperties': False, 'required': ['ar', 'fr'],
                                    'properties': {'ar': {'type': 'string'}, 'fr': {'type': 'string'}}}}}},
    },
}


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text())['situations'] if path.exists() else []


def candidates(situation: dict) -> list[dict]:
    """The articles the situation's searches find, best first, a few per text, at most CANDIDATES."""
    seen, out = set(), []
    for q in situation['searches']:
        for r in search(q, log=False)['results'][:6]:
            for a in r['articles'][:2]:
                if a['path'] not in seen:
                    seen.add(a['path'])
                    out.append({'path': a['path'], 'label': a['label'], 'text': r['text']['title'][:160]})
    out = out[:CANDIDATES]
    for c in out:
        c['body'] = (_body(c['path']) or '')[:1500]
    return [c for c in out if c['body']]


def _body(path: str) -> str | None:
    """An article's words by its address, in its text's latest version (anchors repeat across texts)."""
    uri, eid = split_path(path.lstrip('/'))
    text = Text.objects.filter(akn_uri=uri).first()
    version = text.latest_version() if text else None
    article = version.articles.filter(eid=eid).first() if version else None
    return article.body if article else None


def draft(slugs: list[str] | None = None, log=print) -> list[dict]:
    """Haiku's drafts for each situation (or those named), written to data/situations_drafts.json."""
    situations = [s for s in load(SITUATIONS) if not slugs or s['slug'] in slugs]
    missing = {x['key']: x['name']['ar'] for x in shelf() if x['state'] != 'in_corpus'}
    found, reqs = {}, []
    for s in situations:
        found[s['slug']] = candidates(s)
        lines = [f'Situation: {s["title"]["ar"]} / {s["title"]["fr"]}',
                 'Texts that govern it but are not in 3adala yet: '
                 + (', '.join(missing[k] for k in s['shelf'] if k in missing) or 'none'), '', 'Candidates:']
        lines += [f'--- {c["path"]} | {c["label"]} | {c["text"]}\n{c["body"]}' for c in found[s['slug']]]
        reqs.append(request(f'situation-{s["slug"]}', model=MODEL, system=SYSTEM, content='\n'.join(lines),
                            schema=SCHEMA, max_tokens=6000))
    results = run_batch('situations', reqs, log=log)
    drafts = {s['slug']: s for s in load(DRAFTS)}
    for s in situations:
        data = results[f'situation-{s["slug"]}']['data']
        if not data:
            log(f'{s["slug"]}: no draft ({results[f"situation-{s["slug"]}"]["error"]})')
            continue
        # The site's Arabic name as it is written (the model spells it «ماتن» or in Latin letters now and then).
        for part in [data['intro'], *(a['says'] for a in data['articles'])]:
            part['ar'] = re.sub(r'(?:ماتن|ماطن|3adala)\b', '«قانون»', part['ar'])
        allowed = {c['path'] for c in found[s['slug']]}
        # Only the candidates' addresses: a model cannot send a reader to an article it invented.
        data['articles'] = [a for a in data['articles'] if a['path'] in allowed]
        drafts[s['slug']] = {**s, **data, 'model': MODEL}
    DRAFTS.write_text(json.dumps({'about': 'Drafts by Claude Haiku from the site\'s articles, for an editor\'s review.',
                                  'situations': list(drafts.values())}, ensure_ascii=False, indent=1) + '\n')
    return list(drafts.values())


def shown() -> list[dict]:
    """The situations readers see, as written in situations.json (no database): the approved ones, and while
    developing the drafts too, as `published` has them. The search box's guides (P8 of the polish review)."""
    seen = {s['slug'] for s in load(APPROVED)} | ({s['slug'] for s in load(DRAFTS)} if settings.SHOW_DRAFTS else set())
    return [s for s in load(SITUATIONS) if s['slug'] in seen]


def published(include_drafts: bool = False, only: list[str] | None = None) -> list[dict]:
    """What readers see: the approved situations (or `only` these), each text it rests on as the shelf has it. While
    developing, the drafts too, marked as such."""
    approved = {s['slug']: s for s in load(APPROVED)}
    drafts = {s['slug']: {**s, 'draft': True} for s in load(DRAFTS)} if include_drafts else {}
    guides = json.loads(GUIDES.read_text())['guides'] if include_drafts and GUIDES.exists() else {}
    topic_of = {slug: t['slug'] for t in json.loads(TOPICS.read_text())['topics'] for slug in t['situations']}
    chosen = [(s, approved.get(s['slug']) or drafts.get(s['slug'])) for s in load(SITUATIONS)
              if only is None or s['slug'] in only]
    chosen = [(s, item) for s, item in chosen if item]
    books = {x['key']: x for x in books_of([(k, dict(SHELF)[k]) for k in
                                            dict.fromkeys(k for s, _ in chosen for k in s['shelf']) if k in dict(SHELF)])}
    where = _where([a['path'] for _, item in chosen for a in item['articles']])
    out = []
    for s, item in chosen:
        articles = [{**a, **where.get(a['path'], {})} for a in item['articles']]
        out.append({'slug': s['slug'], 'title': s['title'], 'intro': item['intro'], 'draft': item.get('draft', False),
                    'articles': [a for a in articles if a.get('label')],
                    'shelf': [books[k] for k in s['shelf'] if k in books],
                    'topic': topic_of.get(s['slug'], ''),
                    'guide': item.get('guide') or guides.get(s['slug'])})
    return out


def titles(only: list[str], include_drafts: bool = False) -> list[dict]:
    """The situations' names alone, in `only`'s order, from the files (no query): a topic's chips beside search's
    answers (U17 of the Moroccan-design review)."""
    approved = {s['slug'] for s in load(APPROVED)}
    shown = approved | ({s['slug'] for s in load(DRAFTS)} if include_drafts else set())
    names = {s['slug']: s['title'] for s in load(SITUATIONS)}
    return [{'slug': slug, 'title': names[slug], 'draft': slug not in approved} for slug in only if slug in shown and slug in names]


def _where(paths: list[str]) -> dict[str, dict]:
    """Each article's label and its text's title and address, for the situations' lists: three queries for all of
    them (S5 of the performance audit: three each before, 232 for the page)."""
    from django.db.models import Q

    from apps.corpus.models import Article

    wanted = {path: split_path(path.lstrip('/')) for path in dict.fromkeys(paths)}
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={uri for uri, _ in wanted.values()})
             .prefetch_related('versions')}
    latest = {uri: t.latest_version() for uri, t in texts.items()}
    found = Q()
    for uri, eid in wanted.values():
        if latest.get(uri):
            found |= Q(version_id=latest[uri].pk, eid=eid)
    articles = {}
    for a in Article.objects.filter(found).order_by('version_id', 'order').only('id', 'version_id', 'eid', 'label') if found else []:
        articles.setdefault((a.version_id, a.eid), a)
    out = {}
    for path, (uri, eid) in wanted.items():
        version = latest.get(uri)
        article = articles.get((version.pk, eid)) if version else None
        if article is None:
            continue
        text = texts[uri]
        out[path] = {'label': article.label, 'text': {'title': text.title_ar, 'path': text_path(text.akn_uri),
                                                      'number_as_printed': text.number_as_printed, 'type': text.type}}
    return out
