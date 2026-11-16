"""The Bulletin's year, month by month, for «دجنبر، شهر الأعداد المكررة، ومارس، شهر القوانين» (the blog's fifth post, B4 of
the blog-first-post review, 31 Oct 2026): each year's months with their issues, «bis» issues, pages and texts; the laws, decrees and orders
each month; and the regular issues of the Hijri months, read from the date each masthead prints («12 رجب 1375»).

One query (the issues with their counts) and the arithmetic apart (`tabulate`), so the live rows exported with psql
count as the command does."""

from django.db.models import Count, Q

from apps.sources.models import Edition, Issue

HIJRI = ['محرم', 'صفر', 'ربيع الأول', 'ربيع الآخر', 'جمادى الأولى', 'جمادى الآخرة', 'رجب', 'شعبان', 'رمضان', 'شوال',
         'ذو القعدة', 'ذو الحجة']
# The mastheads' spellings, brought to one: «الاول», «الثاني», «ذي الحجة», «فاتح».
SPELLINGS = [('الاولى', 'الأولى'), ('الاول', 'الأول'), ('الاخرة', 'الآخرة'), ('الثانية', 'الآخرة'), ('الاخر', 'الآخر'),
             ('الثاني', 'الآخر'), ('ذي ', 'ذو ')]
KINDS = {'laws': ['law', 'organic_law'], 'decrees': ['decree', 'decree_law'], 'orders': ['order']}


def hijri_month(printed: str) -> int | None:
    """The Hijri month a masthead's date names, 0 for Muharram, None when it names none."""
    for a, b in SPELLINGS:
        printed = printed.replace(a, b)
    # «جمادى الأولى» before «جمادى»: the longer names are tried first.
    for i in sorted(range(12), key=lambda k: -len(HIJRI[k])):
        if HIJRI[i] in printed:
            return i
    return None


def count(meta: dict) -> dict:
    first, last = meta['span']
    by_kind = {k: Count('texts_first_published', filter=Q(texts_first_published__type__in=v)) for k, v in KINDS.items()}
    rows = (Issue.objects.filter(edition=Edition.GENERAL_AR, date__year__gte=first, date__year__lte=last)
            .annotate(texts=Count('texts_first_published'), **by_kind)
            .values_list('date', 'suffix', 'hijri_date', 'document__page_count', 'texts', *KINDS))
    return tabulate(meta, rows)


def tabulate(meta: dict, rows) -> dict:
    """`rows`: (date, suffix, hijri date as printed, pages, texts, laws, decrees, orders), an issue each."""
    first, last = meta['span']
    since = meta['hijri_since']
    years = list(range(first, last + 1))
    cells = {y: [[0, 0, 0, 0] for _ in range(12)] for y in years}         # issues, bis, pages, texts
    kinds = {k: [0] * 12 for k in KINDS}
    hijri = [[0, 0, 0] for _ in range(12)]                                    # regular issues, texts, pages
    for day, suffix, printed, pages, texts, *counts in rows:
        cell = cells[day.year][day.month - 1]
        cell[0] += 1
        cell[1] += bool(suffix)
        cell[2] += pages or 0
        cell[3] += texts
        for k, v in zip(KINDS, counts):
            kinds[k][day.month - 1] += v
        month = hijri_month(printed or '')
        if month is not None and not suffix and day.year >= since:
            hijri[month][0] += 1
            hijri[month][1] += texts
            hijri[month][2] += pages or 0
    return {'span': [first, last], 'cell_fields': ['issues', 'bis', 'pages', 'texts'],
            'months': [cells[y] for y in years], 'kinds': kinds, 'hijri_since': since, 'hijri': hijri}
