"""The order of 17 July 1967 on the trade in alcoholic drinks, for «الفصل 28، كما طبعته الجريدة الرسمية سنة 1967» (the blog's
seventeenth post, S13 of the first-principles review, 7 Nov 2026). The words are the meta's, each read on its printed
page; what is counted here ties every reference to its issue, its page and its text (clock.tie, three queries), gives
the order's articles their addresses on the site (one query), and takes the minimum wage an hour from the sixth post's
checked steps (marquise.wage), to say a fine in hours of work."""
from apps.blog.services import clock, marquise
from apps.corpus.models import Article
from apps.corpus.services.addresses import article_path
from apps.sources.models import Edition


def _refs(meta: dict) -> list[dict]:
    one = lambda key, issue, page, akn=None, bis=False: {'key': key, 'edition': Edition.GENERAL_AR, 'issue': issue, 'bis': bis,
                                                         'page': page, 'akn': akn}
    order = meta['order']
    refs = [one('order', order['issue'], order['page'], order['akn']), one('art28', order['issue'], meta['art28']['page'], order['akn'])]
    refs += [one(f"o-{a['n']}", order['issue'], a['page'], order['akn']) for a in meta['articles']]
    refs += [one(f"c-{c['key']}", c['text']['issue'], c['text']['page'], c['text'].get('akn')) for c in meta['chain']]
    first = meta['first']
    refs += [one(f"f-{page}", first['issue'], page, first['akn']) for page in sorted({first['page'], *(p['p1913'] for p in meta['pairs'])})]
    refs.append(one('drunk', meta['drunk']['text']['issue'], meta['drunk']['text']['page'], meta['drunk']['text']['akn']))
    return refs


def _articles(meta: dict) -> dict:
    """The order's articles the post names, by number: their addresses when the site holds them (one query)."""
    akn = meta['order']['akn']
    wanted = {28, *(a['n'] for a in meta['articles']), *(f['art'] for f in meta['fines'])}
    found = set(Article.objects.filter(version__text__akn_uri=akn, eid__in=[f'art_{n}' for n in wanted]).values_list('eid', flat=True))
    return {str(n): article_path(akn, f'art_{n}') for n in sorted(wanted) if f'art_{n}' in found}


def count(meta: dict) -> dict:
    return {'texts': clock.tie(_refs(meta)), 'articles': _articles(meta), 'wage': marquise.wage()}
