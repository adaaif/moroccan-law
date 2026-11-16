"""The price of a pack of Marquise order by order, for «ماركيز، قرارا بعد قرار» (the blog's fourteenth post, S1 of
the first-principles review, 6 Nov 2026). The prices are the meta's, each the soft pack's row read in its order; what is counted
here ties each order (and the texts the post quotes: the renaming, the approval, the delegation, the levy for the
Palestinian people) to its issue, its printed page and its address; takes the minimum wage an hour from the sixth post's
checked steps; and lists every order on tobacco prices since 1956 by the verb of its title. Five queries."""
import re

from apps.blog.services import clock, posts
from apps.corpus.models import Text
from apps.sources.models import Edition

# An order on tobacco prices, by its title; the verb tells who decides: «تحديد/تغيير» the State sets, «المصادقة» it approves.
TOBACCO = r'(التبغ|السجائر|السكائر)'
PRICE = r'(ثمن|اثمان|أثمان|أسعار|اسعار|سعر)'


def _refs(meta: dict) -> list[dict]:
    one = lambda key, r: {'key': key, 'edition': Edition.GENERAL_AR, 'issue': r['issue'], 'bis': r.get('bis', False),
                          'page': r['page'], 'akn': r.get('akn')}
    refs = [one(f"p{p['date']}", p) for p in meta['prices']]
    refs += [one(k, meta[k]) for k in ('renamed', 'approve', 'delegate')]
    lev = meta['palestine']
    refs += [one('levy', lev['dahir']), one('applied', lev['applied'])]
    refs += [one(f"changed{c['date']}", c) for c in lev['changed']]
    return refs


def wage() -> list[dict]:
    """The minimum wage an hour outside agriculture, step by step, from the sixth post (its meta read in each decree)."""
    m, f = posts.meta('minimum-wage'), posts.figures('minimum-wage')['decrees']
    out = []
    for s in m['steps']:
        if 'hourly' not in s:
            continue
        d = f.get(s['decree'], {})
        day = d.get('published') if s.get('from_published') else s['from'].isoformat()
        out.append({'from': day, 'hourly': s['hourly'], 'decree': s['decree'], 'issue': d.get('issue'), 'path': d.get('path')})
    return sorted(out, key=lambda x: x['from'])


def count(meta: dict) -> dict:
    orders = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, title_ar__regex=TOBACCO,
                                  first_published_in__date__year__gte=1956, type__in=('order', 'decision'))
              .filter(title_ar__regex=PRICE).values_list('first_published_in__date', 'title_ar').order_by('first_published_in__date'))
    rows = [[day.isoformat(), 'approve' if 'المصادقة' in title else 'set'] for day, title in orders
            if not re.search(r'(المنطقة السابقة|طنجة|يمد)', title)]
    return {'texts': clock.tie(_refs(meta)), 'wage': wage(), 'orders': rows}
