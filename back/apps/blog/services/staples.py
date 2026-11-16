"""The prices the Bulletin wrote for bread and gasoil, for «الخبز والغازوال، يوم كانت الجريدة الرسمية تكتب ثمنهما» (the
blog's fifteenth post, S2 and S3 of the first-principles review, 6 Nov 2026). The prices are the meta's, each read in
its order's article or on its printed page; what is counted here ties every order to its issue, its page and its address
(clock.tie, three queries) and takes the minimum wage an hour from the sixth post's checked steps (marquise.wage)."""
from apps.blog.services import clock, marquise
from apps.sources.models import Edition


def _refs(meta: dict) -> list[dict]:
    one = lambda key, r: {'key': key, 'edition': Edition.GENERAL_AR, 'issue': r['issue'], 'bis': r.get('bis', False),
                          'page': r['page'], 'akn': r.get('akn')}
    refs = [one(f"b-{item['key']}-{i}", o) for item in meta['basket'] for i, o in enumerate(item['orders'])]
    refs.append(one('bread-1975', meta['bread_1975']))
    refs += [one(f"g{g['from']}", g) for g in meta['gasoil']]
    refs.append(one('last', meta['last']))
    refs += [one(f"away-{a['key']}", a['text']) for a in meta['away']]
    return refs


def count(meta: dict) -> dict:
    return {'texts': clock.tie(_refs(meta)), 'wage': marquise.wage()}
