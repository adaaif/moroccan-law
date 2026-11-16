"""The law's deadlines, for «15 يوما: الأجل المفضل في القانون المغربي» (the blog's twenty-third post, S17 of
the first-principles review, 7 Nov 2026).

One pass over the articles of every text of law the site has read no repeal for, in its latest Arabic version (a model's
translation left out): each number of hours, days, weeks, months or years that follows, within three words, a word that
makes it a limit (meta.yaml's `limit_words`: «أجل», «خلال», «داخل» …), in digits («15 يوما»), in words
(«خمسة عشر يوما», «ثلاثين يوما») or as a dual («شهرين»). Ages («سنه 40 سنة»), exam lengths («مدتها ثلاث ساعات») and terms
of office are left out by that word. Each deadline keeps one example: the first of the meta's laws, in their order, that
writes it (its article and the words around it). About half a minute on a copy of the database."""
import re
from collections import Counter

from apps.corpus.models import Article, Consolidation, Status, Version
from apps.corpus.services.addresses import article_path

UNITS = {'ساعة': 'h', 'ساعات': 'h', 'يوم': 'd', 'يوما': 'd', 'أيام': 'd', 'ايام': 'd', 'أسبوع': 'w', 'أسابيع': 'w', 'أسبوعا': 'w',
         'شهر': 'm', 'شهرا': 'm', 'أشهر': 'm', 'اشهر': 'm', 'شهور': 'm', 'سنة': 'y', 'سنوات': 'y', 'سنين': 'y', 'عاما': 'y', 'أعوام': 'y'}
ONES = {'واحد': 1, 'واحدة': 1, 'اثنين': 2, 'اثنتين': 2, 'اثنا': 2, 'اثني': 2, 'اثنتي': 2, 'إثنا': 2, 'إثني': 2, 'إثنتي': 2, 'ثلاثة': 3, 'ثلاث': 3, 'أربعة': 4, 'أربع': 4,
        'اربعة': 4, 'خمسة': 5, 'خمس': 5, 'ستة': 6, 'ست': 6, 'سبعة': 7, 'سبع': 7, 'ثمانية': 8, 'ثماني': 8, 'ثمان': 8, 'تسعة': 9, 'تسع': 9,
        'عشرة': 10, 'عشر': 10}
TENS = {'عشرين': 20, 'عشرون': 20, 'ثلاثين': 30, 'ثلاثون': 30, 'أربعين': 40, 'اربعين': 40, 'أربعون': 40, 'خمسين': 50, 'خمسون': 50,
        'ستين': 60, 'ستون': 60, 'سبعين': 70, 'ثمانين': 80, 'تسعين': 90}
DUALS = {'ساعتين': ('h', 2), 'يومين': ('d', 2), 'أسبوعين': ('w', 2), 'شهرين': ('m', 2), 'سنتين': ('y', 2), 'عامين': ('y', 2)}
DAYS = {'h': 1 / 24, 'd': 1, 'w': 7, 'm': 30.4375, 'y': 365.25}
_U = '|'.join(sorted(UNITS, key=len, reverse=True))
# A number in words, with or without its article («الخمسة عشر يوما» is 15, never 10).
_ONE = '(?:ال)?(?:{})'.format('|'.join(sorted(ONES, key=len, reverse=True)))
_TEN = '(?:ال)?(?:{})'.format('|'.join(sorted(TENS, key=len, reverse=True)))
_W = rf'(?:{_ONE} ?عشر[ةا]?|{_ONE}(?: و{_TEN})?|{_TEN})'


def _patterns(limit_words: str) -> tuple[re.Pattern, re.Pattern]:
    ctx = '(?:' + limit_words + ')'
    number = re.compile(ctx + r'(?:\s+\S+){0,3}?\s+(?:(\d{1,3})|(' + _W + r'))\s*\(?\d*\)?\s*(' + _U + r')(?![ء-ي])')
    dual = re.compile(ctx + r'(?:\s+\S+){0,3}?\s+(' + '|'.join(DUALS) + r')(?![ء-ي])')
    return number, dual


def words_value(w: str) -> int | None:
    """«خمسة عشر» 15, «الخمسة عشر» 15, «ثلاث وعشرين» 23, «ثلاثين» 30."""
    w = ' '.join(x.removeprefix('ال') if x.removeprefix('ال') in ONES or x.removeprefix('ال') in TENS else x
                 for x in w.strip().replace(' و', ' و ').split()).replace(' و ', ' و')
    m = re.match(r'(\S+) ?عشر[ةا]?$', w)
    if m and m.group(1) in ONES:
        return ONES[m.group(1)] + 10
    parts = w.split(' و')
    if len(parts) == 2 and parts[0] in ONES and parts[1] in TENS:
        return ONES[parts[0]] + TENS[parts[1]]
    return ONES.get(w) or TENS.get(w)


def deadlines(body: str, number: re.Pattern, dual: re.Pattern) -> list[tuple[str, int, int, int]]:
    """Each deadline in an article: (unit, number, start, end)."""
    b = ' '.join((body or '').split())
    out = []
    for m in number.finditer(b):
        n = int(m.group(1)) if m.group(1) else words_value(m.group(2))
        if n:
            out.append((UNITS[m.group(3)], n, m.start(), m.end()))
    for m in dual.finditer(b):
        u, n = DUALS[m.group(1)]
        out.append((u, n, m.start(), m.end()))
    return out


def count(meta: dict) -> dict:
    number, dual = _patterns(meta['limit_words'])
    preferred = {akn: i for i, akn in enumerate(meta['examples'])}
    counts: Counter = Counter()
    examples: dict[tuple, tuple] = {}
    latest = (Version.objects.filter(language='ar').exclude(consolidation=Consolidation.TRANSLATION)
              .order_by('text_id', '-valid_from', '-id').distinct('text_id').values('id'))
    rows = (Article.objects.filter(version__in=latest, version__text__type__in=meta['rules'],
                                   version__text__status__in=[Status.IN_FORCE, Status.PARTLY_REPEALED])
            .values_list('body', 'version__text__akn_uri', 'eid', 'order').iterator(chunk_size=20000))
    for body, akn, eid, order in rows:
        found = deadlines(body, number, dual)
        for u, n, a, b in found:
            counts[(u, n)] += 1
            rank = preferred.get(akn)
            if rank is not None and ((u, n) not in examples or (rank, order) < examples[(u, n)][:2]):
                words = ' '.join(body.split())
                start = max(0, words.rfind(' ', 0, max(0, a - 70)) + 1)
                end = words.find(' ', min(len(words), b + 50))
                examples[(u, n)] = (rank, order, akn, eid, ('… ' if start else '') + words[start:end if end > 0 else None].strip() + ' …')
    out = []
    for (u, n), k in counts.most_common():
        if k < 5:
            continue
        row = {'unit': u, 'n': n, 'count': k, 'days': round(n * DAYS[u], 4)}
        if (u, n) in examples:
            _, _, akn, eid, words = examples[(u, n)]
            row['example'] = {'path': article_path(akn, eid), 'akn': akn, 'eid': eid, 'words': words}
        out.append(row)
    return {'deadlines': out, 'total': sum(counts.values())}
