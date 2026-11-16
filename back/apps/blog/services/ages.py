"""The ages the law writes, for «حياتك بأعمار القانون» (the blog's sixteenth post, S9 of the first-principles review, 7 Nov
2026). The ages are the meta's, each read in its article and found on the Bulletin's page that printed it; what is
counted here ties every reference to its issue, its page and its text (clock.tie, three queries) and gives each article
its own address on the site when the text holds it (one query)."""
from django.db.models import Q

from apps.blog.services import clock
from apps.corpus.models import Article
from apps.corpus.services.addresses import article_path
from apps.sources.models import Edition


def _refs(meta: dict) -> list[dict]:
    one = lambda key, r: {'key': key, 'edition': Edition.GENERAL_AR, 'issue': r['issue'], 'bis': r.get('bis', False),
                          'page': r['page'], 'akn': r.get('akn')}
    refs = [one(f"a-{a['key']}", a['ref']) for a in meta['ages']]
    refs += [one(f"m-{m['key']}-{i}", s['ref']) for m in meta['moves'] for i, s in enumerate(m['steps'])]
    refs += [one('equal', meta['equal']['ref']), one('unknown-day', meta['retire']['unknown_day']['ref'])]
    return refs


def _eid(art: str) -> str:
    return f'art_{art}'


def _articles(meta: dict) -> dict:
    """Each age's and each step's article, by its key: its address when the text the site holds has an article of that
    number (any version), else nothing."""
    wanted = {f"a-{a['key']}": (a.get('article_in') or a['ref'].get('akn'), a.get('art')) for a in meta['ages']}
    wanted |= {f"m-{m['key']}-{i}": (s['ref'].get('akn'), s.get('art')) for m in meta['moves'] for i, s in enumerate(m['steps'])}
    pairs = {(akn, _eid(art)) for akn, art in wanted.values() if akn and art}
    where = Q()
    for akn, eid in pairs:
        where |= Q(version__text__akn_uri=akn, eid=eid)
    found = set(Article.objects.filter(where).values_list('version__text__akn_uri', 'eid').distinct()) if pairs else set()
    return {key: article_path(akn, _eid(art)) for key, (akn, art) in wanted.items() if (akn, _eid(art or '')) in found}


def count(meta: dict) -> dict:
    return {'texts': clock.tie(_refs(meta)), 'articles': _articles(meta)}
