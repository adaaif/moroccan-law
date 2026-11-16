"""The speeds the Bulletin wrote, for «السرعة في الجريدة الرسمية» (the blog's twenty-second post, S22 of
the first-principles review, 7 Nov 2026). The eras are the meta's, each read on its page (the 1913 news, the 1923 vizirial order, the 1924
order of the French edition, the 1939 order, the ministers' orders of 1961, 1963 and 1983, the 2010 decree); what is counted
here ties each to its issue (its day) and page (clock.tie), and reads the ministers' orders that set a limit on a road
section, one dot an order: its year and the first speed its articles fix (one query)."""
import re

from apps.blog.services import clock
from apps.corpus.models import Article, TextType
from apps.sources.models import Edition

# «تحدد السرعة … في ستين كيلومترا في الساعة», «(60 كلم)», «بمائة وعشرين كيلومترا».
FIX = re.compile(r'(تحدد|تقدر|يحدد|تحديد)[^.]{0,80}(السرعة|سرعة)')
DIGITS = re.compile(r'(\d{2,3})\s*\)?\s*(?:كيلو ?مترا?|كيلومترات|كلم)')
WORDS = [('مائة وعشرين', 120), ('مائة وعشرون', 120), ('ثمانين', 80), ('سبعين', 70), ('ستين', 60), ('خمسين', 50), ('أربعين', 40),
         ('اربعين', 40), ('ثلاثين', 30), ('عشرين', 20), ('خمسة عشر', 15), ('مائة', 100), ('مائه', 100)]


def kmh(body: str) -> int | None:
    """The first speed an article fixes, in digits or in words."""
    m = FIX.search(body)
    if not m:
        return None
    rest = body[m.start():m.start() + 260]
    d = DIGITS.search(rest)
    hits = [(d.start(), int(d.group(1)))] if d else []
    hits += [(rest.find(w), v) for w, v in WORDS if rest.find(w) >= 0 and re.search(re.escape(w) + r'\s*\)?\s*(?:\(\S+\)\s*)?(?:كيلو|كلم)', rest)]
    return min(hits)[1] if hits else None


def _orders(meta: dict) -> list[dict]:
    lo, hi = meta['orders']['from'], meta['orders']['to']
    rows = (Article.objects.filter(version__text__type=TextType.ORDER, version__language='ar',
                                   version__text__first_published_in__edition=Edition.GENERAL_AR,
                                   version__text__first_published_in__date__year__gte=lo,
                                   version__text__first_published_in__date__year__lte=hi, body__regex=r'(كيلو ?متر|كلم)')
            .order_by('version__text__first_published_in__date', 'order')
            .values_list('version__text_id', 'version__text__first_published_in__date', 'body'))
    seen, out = set(), []
    for text_id, day, body in rows:
        if text_id in seen:
            continue
        v = kmh(body or '')
        if v and 10 <= v <= 130:
            seen.add(text_id)
            out.append({'year': day.year, 'kmh': v})
    return out


def _refs(meta: dict) -> list[dict]:
    def one(key, r, edition=Edition.GENERAL_AR, akn=None):
        return {'key': key, 'edition': edition, 'issue': r['issue'], 'bis': r.get('bis', False), 'page': r['page'], 'akn': r.get('akn', akn)}
    refs = [one(e['key'], e, Edition.TRANSLATION_FR if e.get('edition') == 'fr' else Edition.GENERAL_AR) for e in meta['eras']]
    refs.append(one('first', meta['first_rule']))
    refs += [one(f"t-{t['key']}", {'issue': meta['code']['issue'], 'page': t['page']}, akn=meta['code']['akn']) for t in meta['today']]
    return refs


def count(meta: dict) -> dict:
    return {'texts': clock.tie(_refs(meta)), 'orders': _orders(meta)}
