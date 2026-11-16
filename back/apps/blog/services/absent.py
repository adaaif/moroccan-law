"""The words the law does not know, for «القانون يعرف البرقية، ولا يعرف واتساب» (the blog's nineteenth post, S16 of
the first-principles review, 7 Nov 2026).

For each machine the law still writes (the telegram, the typewriter, the fax, the telex) and each word it has for the new
means (the internet, email, «التواصل الاجتماعي»): the texts of law whose Arabic carries it (dahirs, laws, organic laws,
decree-laws, decrees, orders; any Arabic version but a model's translation from the French), how many stand, the newest,
and how many were first published each decade among all the texts of law of that decade. For each network: the texts of
law that name it (none, once the swallowed report pages and the misreadings meta.yaml lists are set aside: any other
lands in `checks` for a person to read), the Bulletin's Arabic pages that print it and the first of them (checked against
the first the meta names). And every quote's issue, page and text (clock.tie).

One regular-expression pass over the articles per word and one over the pages per network (minutes in all), so the
post is counted on a copy of the database, never on the live server."""
from collections import Counter, defaultdict

from apps.blog.services import clock
from apps.corpus.models import Article, Consolidation, Text
from apps.corpus.services.addresses import article_path
from apps.sources.models import Edition, Page

DECADES = list(range(1910, 2030, 10))
TEXT = 'version__text'


def _issue(number, suffix) -> str:
    return f"{number}{' bis' if suffix else ''}"


def _rules(meta: dict, pattern: str) -> dict[int, tuple]:
    """The texts of law whose Arabic carries the pattern: {text id: (status, day first published, akn, eids)}."""
    rows = (Article.objects.filter(version__language='ar', version__text__type__in=meta['rules'], body__regex=pattern)
            .exclude(version__consolidation=Consolidation.TRANSLATION).order_by()
            .values_list(TEXT, f'{TEXT}__status', f'{TEXT}__first_published_in__date', f'{TEXT}__akn_uri', 'eid'))
    out: dict[int, tuple] = {}
    for text_id, status, day, akn, eid in rows:
        eids = out[text_id][3] if text_id in out else set()
        eids.add(eid)
        out[text_id] = (status, day, akn, eids)
    return out


def _decades(found: dict[int, tuple]) -> list[int]:
    by = Counter((day.year // 10) * 10 for _, day, _, _ in found.values() if day)
    return [by.get(d, 0) for d in DECADES]


def _word(meta: dict, w: dict) -> dict:
    found = _rules(meta, w['re'])
    newest = max((v for v in found.values() if v[1]), key=lambda v: v[1], default=None)
    return {'key': w['key'], 'texts': len(found), 'standing': sum(v[0] != 'repealed' for v in found.values()),
            'newest': {'date': newest[1].isoformat(), 'path': article_path(newest[2], sorted(newest[3])[0])} if newest else None,
            'decades': _decades(found)}


def _pages(meta: dict, app: dict) -> dict:
    left = {(p['issue'], p['page']) for p in meta['not_pages'] if p['word'] == app['key']}
    rows = (Page.objects.filter(document__issue__edition=Edition.GENERAL_AR, text__regex=app['re']).order_by()
            .values_list('document__issue__number', 'document__issue__suffix', 'document__issue__date', 'printed_number'))
    kept = sorted((day, number, suffix, page) for number, suffix, day, page in rows if (number, page) not in left)
    years = Counter(day.year for day, *_ in kept)
    first = kept[0] if kept else None
    return {'pages': len(kept), 'issues': len({(n, s) for _, n, s, _ in kept}), 'years': dict(sorted(years.items())),
            'first': {'issue': _issue(first[1], first[2]), 'page': first[3], 'date': first[0].isoformat()} if first else None}


def _refs(meta: dict) -> list[dict]:
    def one(key: str, r: dict) -> dict:
        return {'key': key, 'edition': Edition.GENERAL_AR, 'issue': r['issue'], 'bis': r.get('bis', False),
                'page': r['page'], 'akn': r.get('akn')}
    refs = [one(f"m-{m['key']}", m['example']) for m in meta['machines']]
    refs += [one(f"a-{a['key']}", a['first']) for a in meta['apps']]
    refs += [one(f"c-{c['key']}", c) for c in meta['clippings']]
    refs += [one(f"t-{c['key']}", {'issue': c['issue'], 'page': c['title_page']}) for c in meta['clippings']]
    refs += [one(f"r-{r['year']}", r) for r in meta['mediator']['reports']]
    refs += [one(f'n-{k}', v) for k, v in meta['naming'].items()]
    refs += [one('cese', meta['cese']), one('cese-title', {'issue': meta['cese']['issue'], 'page': meta['cese']['title_page']}),
             one('telegraph', meta['telegraph'])]
    return refs


def _formula(meta: dict) -> int:
    """How many times the organic law writes its formula, in its Arabic as published (the amending text's quotation
    marks and line breaks set aside)."""
    f = meta['naming']['formula']
    bodies = Article.objects.filter(version__text__akn_uri=f['akn'], version__language='ar',
                                    version__consolidation=Consolidation.AS_PUBLISHED).values_list('body', flat=True)
    return sum(' '.join(b.replace('«', ' ').replace('»', ' ').split()).count(f['phrase']) for b in bodies)


def _articles(meta: dict) -> dict:
    """The articles the post quotes, by key: their addresses on the site (one query)."""
    quoted = {f"m-{m['key']}": m['example'] for m in meta['machines']} | {f'n-{k}': v for k, v in meta['naming'].items()}
    quoted = {k: v for k, v in quoted.items() if v.get('art')}
    have = set(Article.objects.filter(version__text__akn_uri__in={v['akn'] for v in quoted.values()},
                                      eid__in={f"art_{v['art']}" for v in quoted.values()})
               .values_list('version__text__akn_uri', 'eid'))
    return {k: article_path(v['akn'], f"art_{v['art']}") for k, v in quoted.items() if (v['akn'], f"art_{v['art']}") in have}


def count(meta: dict) -> dict:
    machines = [_word(meta, w) for w in meta['machines']]
    generics = [_word(meta, w) for w in meta['generics']]
    # Every text of law read, by the decade it was first published: what each machine's decades are shares of.
    days = Text.objects.filter(type__in=meta['rules'], first_published_in__isnull=False).values_list('first_published_in__date', flat=True)
    texts = Counter((d.year // 10) * 10 for d in days.iterator(chunk_size=20000))
    left = defaultdict(set)
    for n in meta['not_law']:
        for w in n['words']:
            left[w].add(n['akn'])
    apps, checks = [], []
    for a in meta['apps']:
        found = {k: v for k, v in _rules(meta, a['re']).items() if v[2] not in left[a['key']]}
        checks += [{'word': a['key'], 'text': v[2], 'eids': sorted(v[3])} for v in found.values()]
        pages = _pages(meta, a)
        if pages['first'] and (pages['first']['date'], pages['first']['page']) != (a['first']['date'], a['first']['page']):
            checks.append({'word': a['key'], 'first': pages['first']})
        apps.append({'key': a['key'], 'texts': len(found), **pages})
    return {'texts': clock.tie(_refs(meta)), 'articles': _articles(meta), 'decades': DECADES,
            'read': [texts.get(d, 0) for d in DECADES], 'machines': machines, 'generics': generics, 'apps': apps,
            'formula': _formula(meta), 'checks': checks}
