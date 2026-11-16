"""The right to strike, for «حق الإضراب مضمون» (the blog's eighteenth post, S7 of the first-principles review, 7 Nov 2026).
The words are the meta's, each read on its printed page: the six constitutions' articles, the 2011 Constitution's
deadline for its organic laws (art. 86), organic law 97.15 and the Constitutional Court's decision on it. What is counted
here ties every reference to its issue, its page and its text (clock.tie, three queries), gives the law's articles their
addresses (one query), and lists the organic laws the 2011 Constitution called for with the day the Bulletin printed
each (the meta's, found on their pages)."""
from apps.blog.services import clock
from apps.corpus.models import Article
from apps.corpus.services.addresses import article_path
from apps.sources.models import Edition


def _refs(meta: dict) -> list[dict]:
    one = lambda key, r: {'key': key, 'edition': Edition.GENERAL_AR, 'issue': r['issue'], 'bis': r.get('bis', False),
                          'page': r['page'], 'akn': r.get('akn')}
    refs = [one(f"c-{c['year']}", c) for c in meta['constitutions']]
    refs.append(one('deadline', {**meta['deadline'], 'akn': meta['constitutions'][-1]['akn']}))
    refs += [one(k, meta[k]) for k in ('law', 'decision', 'opinion')]
    refs += [one(f"n-{n['key']}", {'issue': meta['law']['issue'], 'page': n['page'], 'akn': meta['law']['akn']}) for n in meta['numbers']]
    refs += [one(f"ol-{o['number']}", o) for o in meta['organic']]
    refs.append(one('election', meta['election']))
    return refs


def _articles(meta: dict) -> dict:
    """The law's articles the post names, by number: their addresses on the site (one query)."""
    akn = meta['law']['akn']
    wanted = {*(n['art'] for n in meta['numbers']), '19', '21', '22', '1', '5', '12'}
    found = set(Article.objects.filter(version__text__akn_uri=akn, eid__in=[f'art_{n}' for n in wanted]).values_list('eid', flat=True))
    return {n: article_path(akn, f'art_{n}') for n in sorted(wanted, key=int) if f'art_{n}' in found}


def count(meta: dict) -> dict:
    return {'texts': clock.tie(_refs(meta)), 'articles': _articles(meta)}
