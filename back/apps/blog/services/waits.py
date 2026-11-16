"""The days between a text's signature and its issue, for «من التوقيع إلى الجريدة: كم ينتظر القانون؟» (the blog's eighth
post, B3 of the blog-first-post review, 31 Oct 2026): each law's wait, the medians of each kind of text a decade at a
time, laws and dahirs that concern an international agreement apart, and the laws that waited more than a year.

The signature is the date its title prints (for a law, its promulgation dahir's), read when it was cut. A text signed
after its issue is a misreading and is left out, as are errata reprinted under a law's title. One query, the arithmetic
apart (`tabulate`), so rows exported with psql count as the command does."""
import statistics
from collections import defaultdict

from apps.corpus.models import Text
from apps.corpus.services.addresses import text_path
from apps.sources.models import Edition

AGREEMENT = ('يوافق بموجبه', 'الموافقة', 'تصديق', 'بنشر الاتفاق', 'بنشر اتفاق', 'بنشر الاتفاقية', 'بنشر اتفاقية', 'بنشر البروتوكول')
ERRATUM = 'استدراك'
BANDS = [7, 30, 90, 365]


def count(meta: dict) -> dict:
    first, last = meta['span']
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, first_published_in__date__year__gte=first,
                                first_published_in__date__year__lte=last)
            .values_list('type', 'number', 'signed_on', 'first_published_in__date', 'first_published_in__number',
                         'first_published_in__suffix', 'first_published_page', 'akn_uri', 'title_ar'))
    return tabulate(meta, rows)


def kind(text_type: str, title: str) -> str:
    """The text's kind as the post compares them: laws and dahirs that concern an international agreement apart."""
    agreement = any(w in title for w in AGREEMENT)
    if text_type in ('law', 'organic_law'):
        return 'law_agreement' if agreement else 'law'
    if text_type == 'dahir':
        return 'dahir_agreement' if agreement else 'dahir'
    return {'decree': 'decree', 'decree_law': 'decree', 'order': 'order', 'decision': 'decision'}.get(text_type, '')


def band(days: int) -> int:
    return next((i for i, b in enumerate(BANDS) if days <= b), len(BANDS))


def tabulate(meta: dict, rows) -> dict:
    """`rows`: (type, number, signed, published, issue number, suffix, page, akn_uri, title), a text each."""
    first, last = meta['span']
    medians: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    laws, late, same, kept = [], [], [], 0
    left_out = {'no_date': 0, 'after': 0, 'erratum': 0}
    for text_type, number, signed, published, issue, suffix, page, uri, title in rows:
        if not signed:
            left_out['no_date'] += 1
            continue
        if signed > published:
            left_out['after'] += 1
            continue
        k = kind(text_type, title)
        if ERRATUM in title and k.startswith('law'):
            left_out['erratum'] += 1
            continue
        days = (published - signed).days
        kept += 1
        if k:
            medians[k][published.year // 10 * 10].append(days)
        if k.startswith('law'):
            key = f'{issue}-bis' if suffix else str(issue)
            laws.append([published.isoformat(), days, int(k == 'law_agreement'), number, key, text_path(uri)])
            if days > 365:
                late.append({'number': number, 'signed': signed.isoformat(), 'published': published.isoformat(), 'days': days,
                             'issue': key, 'page': page, 'path': text_path(uri), 'title': title, 'agreement': k == 'law_agreement'})
            if days == 0:
                same.append(published.isoformat())
    decades = list(range(first // 10 * 10, last + 1, 10))
    return {
        'span': [first, last], 'bands': BANDS, 'kept': kept, 'left_out': left_out,
        'law_fields': ['published', 'days', 'agreement', 'number', 'issue', 'path'],
        'laws': sorted(laws),
        'decades': decades,
        'medians': {k: [statistics.median(v[d]) if v.get(d) else None for d in decades] for k, v in sorted(medians.items())},
        'overall': {k: statistics.median([x for vs in v.values() for x in vs]) for k, v in sorted(medians.items())},
        'counts': {k: sum(len(vs) for vs in v.values()) for k, v in sorted(medians.items())},
        'late': sorted(late, key=lambda x: -x['days']),
        'same_day': len(same),
    }

