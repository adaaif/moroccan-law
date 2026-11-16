"""The health emergency, for «حالة الطوارئ الصحية» (the blog's twenty-seventh post, S10 of the first-principles review, 7
Nov 2026). The declaration and every decree that extended the emergency (meta.yaml's `extends_re` on its title), each with
the day and hour its first article, as printed, carries the emergency to («إلى غاية يوم … في الساعة السادسة مساء»); each
term starts where the one before ended. Two queries; every decree and the meta's texts are tied to their pages with
`clock.tie`."""
import re
from datetime import date

from apps.blog.services import clock
from apps.corpus.models import Article, Consolidation, Text
from apps.sources.models import Edition

MONTHS = {'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'ماي': 5, 'مايو': 5, 'يونيو': 6, 'يونيه': 6, 'يوليو': 7,
          'يوليوز': 7, 'غشت': 8, 'أغسطس': 8, 'شتنبر': 9, 'سبتمبر': 9, 'أكتوبر': 10, 'اكتوبر': 10, 'نونبر': 11, 'نوفمبر': 11,
          'دجنبر': 12, 'ديسمبر': 12}
UNTIL = re.compile(r'إلى غاية\s*يوم\s*(?:\S+\s+)?«?\s*(\d{1,2})\s+(' + '|'.join(MONTHS) + r')\s+(\d{4})')


def until(body: str) -> date | None:
    m = UNTIL.search(' '.join((body or '').split()))
    return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))) if m else None


def count(meta: dict) -> dict:
    texts = list(Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, title_ar__regex=meta['extends_re'],
                                     first_published_in__date__year__gte=2020)
                 .values('akn_uri', 'number', 'title_ar', 'first_published_in__number', 'first_published_in__suffix', 'first_published_in__date',
                         'first_published_page'))
    akns = [meta['declaration']['akn']] + [t['akn_uri'] for t in texts]
    bodies = dict(Article.objects.filter(version__text__akn_uri__in=akns, version__consolidation=Consolidation.AS_PUBLISHED, eid='art_1')
                  .values_list('version__text__akn_uri', 'body'))
    rows = sorted(texts, key=lambda t: (t['first_published_in__date'], t['number']))
    terms, refs = [], []
    for i, t in enumerate(rows):
        key = f't-{i}'
        terms.append({'key': key, 'number': t['number'].replace('-', '.'), 'until': (until(bodies.get(t['akn_uri'], '')) or date(1, 1, 1)).isoformat(),
                      'printed': t['first_published_in__date'].isoformat(), **({'changes': True} if t['title_ar'].lstrip().split(' بتغيير', 1)[0] != t['title_ar'].lstrip() and 'بتمديد' not in t['title_ar'].split('بتغيير')[0] else {})})
        refs.append({'key': key, 'edition': Edition.GENERAL_AR, 'issue': t['first_published_in__number'], 'bis': bool(t['first_published_in__suffix']),
                     'page': t['first_published_page'], 'akn': t['akn_uri']})
    for k in ('declaration', 'decree_law', 'settlement', 'on_the_spot', 'ratified'):
        r = meta[k]
        refs.append({'key': k, 'edition': Edition.GENERAL_AR, 'issue': r['issue'], 'bis': r.get('bis', False), 'page': r['page'], 'akn': r['akn']})
    declared = until(bodies.get(meta['declaration']['akn'], ''))
    return {'declared_until': declared.isoformat() if declared else None, 'terms': terms, 'texts': clock.tie(refs)}
