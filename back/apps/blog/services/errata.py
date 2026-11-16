"""The Bulletin's corrections of itself, for «حين تصحح الجريدة الرسمية نفسها» (the blog's ninth post, B9 of
the blog-first-post review, 31 Oct 2026): every correction notice («استدراك خطإ وقع بالجريدة الرسمية عدد …») the Arabic edition printed
from 1956 to 2025, read on its pages, since most are a few lines that no reading cut as a text of their own.

A notice counts once for the issue that prints it and the issue it names: the index and the page that both carry it
count one, and two corrections of one issue in the same issue count one. Its wait is the days between the two issues.
A notice whose corrected issue's year, printed beside its number, is not that issue's is a misreading: counted, never
timed. What it corrects is read in the lines after its heading (names in a list, a dahir or law, a decree, an order); a
notice found only in an issue's index is said so. One query each for the pages, the issues and the texts; the
arithmetic apart (`tabulate`), so rows exported with psql count as the command does."""
import re
import statistics
from collections import Counter, defaultdict

from django.db.models import Count, Q

from apps.corpus.models import Text
from apps.sources.models import Edition, Issue, Page

DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
# The heading names the issue it corrects: «استدراك خطإ وقع بالجريدة الرسمية عدد 4628», «استدراك في الجريدة الرسمية
# العربية عدد 2682», «استدراك : (ج. ر عدد 3150», «… للجريدة الرسمية عدد 2.373» (1958's dotted thousands). No figure or
# table rule between the word and the issue: a pension list's row «استدراك | تحويل المعاش رقم … المنشور بالجريدة …» is not one.
# A text citing a notice is not one: «… وكذا الاستدراك المنشور بالجريدة الرسمية عدد 803 الصادرة في 13 مارس 1928» in the
# references of a code the Bulletin printed in 1963 (BO 2629) had been timed as a 35-year correction once 1928 was read.
# Before 1956 the heading is «اصلاح غلط» (871 pages of 1913–1955 against 98 with «استدراك»; BH5 of
# the posts-from-No.-1 review, 6 Nov 2026): «اصلاح غلط واقع في الجريدة الرسمية العربية عدد 1744 بصحيفة عدد 223» (1946). A page named before
# the issue («استدراك لاصلاح غلط في الصحيفة 6542 من عدد الجريدة الرسمية العربية رقم 2089», 1952) is read past (PAGE).
HEADING = re.compile(r'(?:(?<!ال)استدراك|[اإ]صلاح\s+(?:ال)?(?:غلط|خط[أإا]))[^\d|]{0,60}?(?:جريدة\s*(?:ال)?رسم(?:ية|ة)|ج\s*\.\s*ر)'
                     r'[^\d\n]{0,40}?(?:عدد|رقم)\s*:?\s*(\d\.\d{3}|\d{1,4})\s*(مكرر|bis)?')
PAGE = re.compile(r'(?:(?:ب|في|من)\s*)?(?:ال)?(?:صحيفة|صفحة)\s*(?:عدد|رقم)?\s*\d+')
YEAR = re.compile(r'\b(19[1-9]\d|20[0-2]\d)\b')
OPENERS = ('استدراك', 'صلاح غلط', 'صلاح الغلط', 'صلاح خطأ', 'صلاح خطإ')
LEADERS = re.compile(r'\.{6,}|…{2,}')
# The first of these after the heading says what the notice puts right; a list of names (an exam's results, a pension)
# before any text's title.
WHAT = re.compile(r'(ظهير|قانون|مرسوم|قرار|مقرر|الناجحين|نتائج|مباراة|[لق]ائحة ب[أا]سماء|قائمة ب[أا]سماء|المعاش|معاش)')
KINDS = ('names', 'law', 'decree', 'order', 'other', 'index')
BANDS = [7, 30, 90, 365, 3650]


def count(meta: dict) -> dict:
    first, last = meta['span']
    pages = (Page.objects.filter(document__issue__edition=Edition.GENERAL_AR, document__issue__date__year__gte=first,
                                 document__issue__date__year__lte=last)
             .filter(Q(*[Q(text__contains=w) for w in OPENERS], _connector=Q.OR))
             .values_list('document__issue__date', 'document__issue__number', 'document__issue__suffix', 'text'))
    issues = Issue.objects.filter(edition=Edition.GENERAL_AR).values_list('number', 'suffix', 'date')
    texts = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, first_published_in__date__year__gte=first,
                                 first_published_in__date__year__lte=last)
             .values_list('first_published_in__date__year').annotate(n=Count('id')))
    return tabulate(meta, pages, issues, texts)


def key(number: int, bis: bool) -> str:
    return f'{number}-bis' if bis else str(number)


def kind(after: str) -> str:
    """What a notice corrects, from the lines after its heading."""
    m = WHAT.search(after[:700])
    if not m:
        return 'other'
    word = m.group(1)
    if word in ('ظهير', 'قانون'):
        return 'law'
    if word == 'مرسوم':
        return 'decree'
    if word in ('قرار', 'مقرر'):
        return 'order'
    return 'names'


def notices(pages) -> dict:
    """{(printing issue, corrected issue): {date, index, page, years, kind}} from (date, number, suffix, text) pages."""
    out: dict = {}
    for date, number, suffix, text in pages:
        text = PAGE.sub(' ', text.translate(DIGITS).replace('ـ', ''))
        for m in HEADING.finditer(text):
            corrected = (int(m.group(1).replace('.', '')), bool(m.group(2)))
            after = text[m.end():m.end() + 900]
            first = re.split(r'\n\s*\n', after, maxsplit=1)[0]
            index = bool(LEADERS.search(first[:250]))
            n = out.setdefault(((number, bool(suffix)), corrected), {'date': date, 'index': False, 'page': False,
                                                                    'years': set(), 'kind': None})
            n['index' if index else 'page'] = True
            n['years'].update(int(y) for y in YEAR.findall(re.split(r'\.{4,}|…|\n\s*\n', after[:120])[0]))
            if not index and n['kind'] is None:
                n['kind'] = kind(after)
    return out


def tabulate(meta: dict, pages, issues, texts) -> dict:
    """`pages`: (date, number, suffix, text) for each page that holds «استدراك»; `issues`: (number, suffix, date) for
    every Arabic issue; `texts`: (year, count) of the texts first published each year."""
    first, last = meta['span']
    dates = {(number, bool(suffix)): date for number, suffix, date in issues}
    decades = list(range(first // 10 * 10, last + 1, 10))
    at = {d: i for i, d in enumerate(decades)}
    per = {k: [0] * len(decades) for k in ('notices', 'texts', 'issues', *KINDS)}
    years = [0] * (last - first + 1)
    waits: dict[int, list[int]] = defaultdict(list)
    left_out = Counter()
    arcs, timed = [], []
    for (printed, corrected), n in notices(pages).items():
        then = dates.get(corrected) or dates.get((corrected[0], False))
        if then is None:
            left_out['no_issue'] += 1
            continue
        if then > n['date']:
            left_out['after'] += 1
            continue
        k = n['kind'] or 'index'
        d = at[n['date'].year // 10 * 10]
        per['notices'][d] += 1
        per[k][d] += 1
        years[n['date'].year - first] += 1
        if n['years'] and not n['years'] & {then.year - 1, then.year, then.year + 1}:
            left_out['misread'] += 1
            continue
        days = (n['date'] - then).days
        waits[d].append(days)
        row = {'printed': n['date'].isoformat(), 'printed_issue': key(*printed), 'corrected': then.isoformat(),
               'corrected_issue': key(*corrected), 'days': days, 'kind': k}
        timed.append(row)
        arcs.append([row['corrected'], row['printed'], row['corrected_issue'], row['printed_issue'], KINDS.index(k)])
    for _number, _suffix, date in issues:
        if first <= date.year <= last:
            per['issues'][at[date.year // 10 * 10]] += 1
    for year, n in texts:
        if first <= year <= last:
            per['texts'][at[year // 10 * 10]] += n
    days = [r['days'] for r in timed]
    bands = Counter(next((i for i, b in enumerate(BANDS) if x <= b), len(BANDS)) for x in days)
    times = Counter(r['corrected_issue'] for r in timed)
    corrected_on = {r['corrected_issue']: r['corrected'] for r in timed}
    return {
        'span': [first, last], 'notices': sum(per['notices']), 'timed': len(timed), 'left_out': dict(left_out),
        'decades': decades, 'kinds': list(KINDS), 'per_decade': per, 'years': years,
        'median_days': statistics.median(days) if days else None,
        'decade_median_days': [statistics.median(waits[i]) if waits[i] else None for i in range(len(decades))],
        'bands': BANDS, 'band_counts': [bands[i] for i in range(len(BANDS) + 1)],
        'arc_fields': ['corrected', 'printed', 'corrected_issue', 'printed_issue', 'kind'],
        'arcs': sorted(arcs),
        'longest': sorted(timed, key=lambda r: -r['days'])[:10],
        'most_corrected': [{'issue': i, 'date': corrected_on[i], 'times': c} for i, c in times.most_common(5)],
    }
