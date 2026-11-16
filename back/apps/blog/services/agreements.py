"""Morocco's agreements with states, lenders and organisations, for «المغرب والعالم في الجريدة الرسمية» (the blog's tenth
post, B8 of the blog-first-post review, 31 Oct 2026). Every Arabic text since 1956 whose title holds «اتفاق», «معاهدة»,
«بروتوكول», «قرض» or «عقد الضمان», sorted by rules a person reads in the post's `words.yaml`: what the text does (a decree
approves a loan or a guarantee, a dahir publishes a treaty, a law approves one), whether its partner is abroad (a
lender, an organisation, a state, or a convention between many) or at home (a petroleum agreement, a concession, an
aquaculture licence), who the partner is, the public body a guaranteed loan goes to, and how old a treaty was when the
Bulletin published it.

Since 2019 the dahirs that publish treaties appear in the Bulletin's conventions edition (decree 2.18.576), which the site
has not read: here the publications stop in 2018, while the laws and the loan decrees go on in the general edition. One
query; the sorting apart (`tabulate`), so rows exported with psql count as the command does."""
import re
import statistics
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

import yaml
from django.db.models import Q

from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path
from apps.sources.models import Edition

WORDS = Path(__file__).resolve().parent.parent / 'posts' / 'agreements' / 'words.yaml'
MOROCCO = re.compile(r'(?:حكومة )?(?:المملكة المغربية|الدولة المغربية|المغرب)')
# Before 1956 a loan is «سلف» (263 titles of 1913–1955 against 147 with «قرض»; BH5 of the posts-from-No.-1 review, 6 Nov
# 2026): nearly all credit at home (the agricultural and land credit funds, veterans' loans), so they sort as domestic or
# other; a word whole, never «السلفي» or «سلفا».
SALAF = r'(?<![ء-ي])(?:ب|ل|و|وب)?(?:ال)?سلف(?:ه|ة|ات)?(?![ء-ي])'
LOAN = re.compile(r'قرض|القرض|قروض|اقتراض|' + SALAF)
# A lender's financing that is not called a loan: Islamic finance's sale on terms, lease and manufacture, or «تمويل».
FINANCE = re.compile(r'التمويل|تمويل|البيع لاجل|بيع لاجل|الاجارة|اجارة|الاستصناع|المرابحة')
GRANT = re.compile(r'(?<!\w)(?:هبة|الهبة|منحة|المنحة|هبات)(?!\w)')
PUBLISH = re.compile(r'(?<!\w)و?بنشر')
# Matched on the folded title, where «على» is «علي».
APPROVE = re.compile(r'(?:الموافقة|المصادقة) علي|بالموافقة|بالمصادقة|في الموافقة')
KINDS = ('loan', 'guarantee', 'grant')
YEAR = r'(1[89]\d\d|20[0-2]\d)'
REGIONS = ('africa', 'arab', 'europe', 'asia', 'americas_oceania')


def fold(text: str) -> str:
    text = re.sub('[أإآ]', 'ا', text.replace('ـ', '')).replace('ى', 'ي')
    return re.sub(r'\s+', ' ', text)


def matcher(words: list[str]) -> re.Pattern:
    """Any of `words`, whole, alone or after و ب ل; a word in «ال» also as «لل»."""
    def one(w):
        w = fold(w)
        return '(?:ال|لل)' + re.escape(w[2:]) if w.startswith('ال') else re.escape(w)
    return re.compile(r'(?:(?<!\w)|(?<=(?<!\w)[وبل]))(?:' + '|'.join(one(w) for w in words) + r')(?!\w)', re.I)


@cache
def rules() -> dict:
    w = yaml.safe_load(WORDS.read_text(encoding='utf-8'))
    first = lambda items: [(i, matcher(i['words'])) for i in items]
    return {
        'partners': [(group, i, r) for group in ('lenders', 'organisations', 'states') for i, r in first(w[group])],
        'domestic': matcher(w['domestic']), 'multilateral': matcher(w['multilateral']), 'law': matcher(w['approve_law']),
        'signed': re.compile(r'(?:' + '|'.join(w['signed']) + r')[^0-9]{0,80}?(?:\d{1,2} )?[^0-9()]{0,20}?' + YEAR),
        'not_aged': matcher(w['not_aged']), 'topics': first(w['topics']), 'borrowers': first(w['borrowers']),
        'names': {i['key']: {k: i[k] for k in ('ar', 'fr', 'short_ar', 'short_fr') if k in i}
                  for g in ('lenders', 'organisations', 'states', 'borrowers') for i in w[g]},
        'region': {i['key']: i['region'] for i in w['states']},
    }


def count(meta: dict) -> dict:
    first, last = meta['span']
    words = Q()
    for w in ('اتفاق', 'معاهدة', 'بروتوكول', 'قرض', 'سلف', 'عقد الضمان', 'عقد ضمان'):
        words |= Q(title_ar__contains=w)
    rows = (Text.objects.filter(words, first_published_in__edition=Edition.GENERAL_AR, first_published_in__date__year__gte=first,
                                first_published_in__date__year__lte=last)
            .values_list('type', 'number', 'first_published_in__date', 'akn_uri', 'title_ar'))
    return tabulate(meta, rows)


def first_of(pairs, text: str):
    hits = [(m.start(), i) for i, r in pairs if (m := r.search(text))]
    return min(hits, key=lambda h: h[0])[1] if hits else None


def partner(title: str):
    """(group, key) of the partner the title names after its «بين», Morocco's own names taken out."""
    at = title.find('بين ')
    part = MOROCCO.sub(' ', title[at + 4:at + 260] if at >= 0 else title)
    hits = [(group, m.start(), i['key']) for group, i, r in rules()['partners'] if (m := r.search(part))]
    if not hits:
        return None
    order = ('lenders', 'organisations', 'states')
    group, _, key = min(hits, key=lambda h: (order.index(h[0]), h[1]))
    return group, key


def sort(text_type: str, title: str) -> dict:
    """What a text is: `what` (money, treaty, law, domestic or other), its partner, and for money its kind."""
    R = rules()
    t = fold(title)
    found = partner(t)
    if text_type in ('law', 'organic_law') or R['law'].search(t):
        role = 'law'
    elif text_type in ('order', 'decision'):
        role = 'order'
    elif PUBLISH.search(t):
        role = 'publish'
    elif APPROVE.search(t):
        role = 'approve'
    else:
        role = 'other'
    plain = t.replace('الضمان الاجتماعي', '')
    money = ('guarantee' if 'ضمان' in plain else 'loan') if LOAN.search(plain) else None
    if not money and found and found[0] == 'lenders' and role == 'approve':
        money = 'grant' if GRANT.search(plain) else ('guarantee' if 'ضمان' in plain else 'loan') if FINANCE.search(plain) else None
    abroad = bool(found) or (not R['domestic'].search(t) and (role in ('publish', 'law') or bool(R['multilateral'].search(t))))
    if role == 'approve' and money and not found and not R['domestic'].search(t):
        abroad, found = True, ('lenders', 'banks')
    if not abroad or (role == 'order' and not found):
        return {'what': 'domestic' if R['domestic'].search(t) or role == 'order' else 'other'}
    group, key = found or ('multilateral', 'multilateral')
    out = {'group': group, 'partner': key}
    if role in ('publish', 'approve') and money:
        return {**out, 'what': 'money', 'kind': money, 'borrower': first_of(R['borrowers'], t)['key'] if money == 'guarantee' and first_of(R['borrowers'], t) else None}
    if role in ('publish', 'approve'):
        return {**out, 'what': 'treaty', 'published': role == 'publish', 'topic': (first_of(R['topics'], t) or {'key': 'other'})['key'],
                'signed': None if R['not_aged'].search(t) else next((int(m.group(1)) for m in [R['signed'].search(t)] if m), None)}
    if role == 'law':
        return {**out, 'what': 'law'}
    return {**out, 'what': 'other'}


def region(found: dict) -> str:
    return rules()['region'].get(found['partner'], found['group'])


def tabulate(meta: dict, rows) -> dict:
    """`rows`: (type, number, published, akn_uri, title), a text each."""
    first, last = meta['span']
    decades = list(range(first // 10 * 10, last + 1, 10))
    at = {d: i for i, d in enumerate(decades)}
    zero = lambda: [0] * len(decades)
    sorted_ = Counter()
    money, lenders, borrowers = [], defaultdict(list), Counter()
    per_money = {k: zero() for k in KINDS}
    treaties, laws = zero(), zero()
    treaty_regions, law_regions = defaultdict(zero), defaultdict(zero)
    treaty_partners, law_partners, topics = Counter(), Counter(), Counter()
    ages, oldest, last_publication = defaultdict(list), [], None
    for text_type, number, published, uri, title in rows:
        s = sort(text_type, title)
        sorted_[s['what']] += 1
        d = at[published.year // 10 * 10]
        if s['what'] == 'money':
            money.append([published.isoformat(), KINDS.index(s['kind']), s['partner'], text_path(uri), number or ''])
            per_money[s['kind']][d] += 1
            lenders[s['partner']].append(published.isoformat())
            if s['kind'] == 'guarantee':
                borrowers[s['borrower'] or 'other'] += 1
        elif s['what'] == 'treaty':
            treaties[d] += 1
            treaty_regions[region(s)][d] += 1
            treaty_partners[s['partner']] += 1
            if s['group'] == 'states':
                topics[s['topic']] += 1
            if s['published']:
                last_publication = max(last_publication or published, published)
                if s['signed'] and s['signed'] <= published.year:
                    ages[d].append(published.year - s['signed'])
                    oldest.append({'published': published.isoformat(), 'signed': s['signed'], 'years': published.year - s['signed'],
                                   'title': title, 'path': text_path(uri)})
        elif s['what'] == 'law':
            laws[d] += 1
            law_regions[region(s)][d] += 1
            law_partners[s['partner']] += 1
    names = rules()['names']
    since = lambda dates, y: sum(1 for x in dates if x >= f'{y}')
    shown = set(lenders) | set(borrowers) | {k for k, _ in treaty_partners.most_common(15)} | {k for k, _ in law_partners.most_common(15)}
    return {
        'span': [first, last], 'texts': sum(sorted_.values()), 'sorted': dict(sorted_), 'decades': decades,
        'names': {k: names[k] for k in sorted(shown) if k in names},
        'kinds': list(KINDS), 'money_fields': ['date', 'kind', 'lender', 'path', 'number'],
        'money': sorted(money),
        'money_per_decade': per_money,
        'lenders': sorted(({'key': k, 'n': len(v), 'since_2000': since(v, 2000), 'first': min(v), 'last': max(v)} for k, v in lenders.items()),
                          key=lambda x: -x['n']),
        'borrowers': [{'key': k, 'n': n} for k, n in borrowers.most_common()],
        'treaties_per_decade': treaties,
        'treaty_regions': dict(treaty_regions),
        'treaty_partners': [{'key': k, 'n': n} for k, n in treaty_partners.most_common(15)],
        'topics': [{'key': k, 'n': n} for k, n in topics.most_common()],
        'last_publication': last_publication.isoformat() if last_publication else None,
        'ages': {'aged': [len(ages[i]) for i in range(len(decades))],
                 'median': [statistics.median(ages[i]) if ages[i] else None for i in range(len(decades))],
                 'over_10': [sum(a > 10 for a in ages[i]) for i in range(len(decades))],
                 'over_20': [sum(a > 20 for a in ages[i]) for i in range(len(decades))]},
        'oldest': sorted(oldest, key=lambda x: -x['years'])[:8],
        'laws_per_decade': laws,
        'law_regions': dict(law_regions),
        'law_partners': [{'key': k, 'n': n} for k, n in law_partners.most_common(15)],
    }
