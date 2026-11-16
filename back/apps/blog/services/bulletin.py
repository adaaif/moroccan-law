"""The Bulletin counted year by year, for the blog's first post (B1 of the blog-first-post review, 31 Oct 2026; from
1956 as «سبعون سنة», from No. 1 since BH8 of the posts-from-No.-1 review, 6 Nov 2026): every issue of the Arabic general
edition between two years with its pages and the texts it first published, the words of those texts as published,
the texts with a title and no words, the days it came out, and the issues that carry an institution's report rather
than a text; beside them, apart, the French edition's issues and the texts only it printed (1912–1925, translated into
Arabic by AI: never inside the Arabic counts, BH6). A handful of queries whatever the years.

Pages are the pages of the issue's file. The Bulletin numbers its pages on through each year, so the last page of a
year's last issue says how many it printed: where the two agree, the files are whole (they do for the 1980s, whose
thin years are the Bulletin's own: 1984 ends on page 1207, its files hold 1162 pages; 31 Oct 2026). A last first page
misread by a digit (3607 read as page 2437) disagrees, and that year's printed count is left out rather than guessed."""
import re
from collections import Counter, defaultdict

from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Sum, Value
from django.db.models.functions import ExtractYear, Length, Replace

from apps.corpus.models import Article, Consolidation, Text
from apps.sources.models import Edition, Issue, Page

# A text's kind as the post groups them; anything else (circulars, conventions, constitutions…) is «other».
KINDS = {'dahir': ['dahir'], 'law': ['law', 'organic_law'], 'decree': ['decree', 'decree_law'], 'order': ['order'],
         'decision': ['decision']}
# An institution's report as its first pages present it: addressed to the King, or titled as the yearly report.
REPORT = re.compile(r'مرفوع إلى (?:حضرة )?صاحب الجلالة|التقرير السنوي|تقرير حول أنشطة|تقرير السنة المالية')
YEAR_FIELDS = ['year', 'issues', 'bis', 'pages', 'texts', 'words', *KINDS, 'other', 'report_issues', 'report_pages',
               'printed']


def count(first: int, last: int, reports_read: list[str]) -> dict:
    """Every issue from January of `first` to December of `last`. `reports_read` names the report issues whose pages
    have no text to match (their file was never read), each looked at by a person."""
    by_kind = {k: Count('texts_first_published', filter=Q(texts_first_published__type__in=v)) for k, v in KINDS.items()}
    # An issue whose file online is another issue's (a copy, folded since the mended-Bulletin review: 83 of 1914–1955) holds
    # none of its own pages: counted apart (`copies`), never as a second set of the other's pages.
    issues = list(Issue.objects.filter(edition=Edition.GENERAL_AR, date__year__gte=first, date__year__lte=last,
                                       copy_of__isnull=True)
                  .annotate(texts=Count('texts_first_published'), **by_kind)
                  .values('id', 'number', 'suffix', 'date', 'first_page_number', 'document__page_count', 'texts', *KINDS)
                  .order_by('date', 'number', 'suffix'))
    reports = _reports([i for i in issues if not i['texts']], set(reports_read))
    copies = list(Issue.objects.filter(edition=Edition.GENERAL_AR, date__year__gte=first, date__year__lte=last,
                                       copy_of__isnull=False).values_list('date__year', flat=True))
    out = tabulate(first, last, issues, reports, _words(first, last), _french(first, last), _bare(first, last))
    return {**out, 'copies': dict(sorted(Counter(copies).items()))}


def tabulate(first: int, last: int, issues: list[dict], reports: set[int], words: dict[int, int],
             french: dict[int, list[int]] | None = None, bare: dict[int, int] | None = None) -> dict:
    """The figures from the issues (each as `count` reads it, in the order they came out), the ids of those that carry
    a report, and the words of each year. Apart from the queries, so the same arithmetic serves rows read elsewhere."""
    years: dict[int, dict] = defaultdict(lambda: dict.fromkeys(YEAR_FIELDS, 0))
    weekdays: dict[int, Counter] = defaultdict(Counter)
    rows = []
    for i in issues:
        y, pages, report = i['date'].year, i['document__page_count'] or 0, i['id'] in reports
        row = years[y]
        row['year'] = y
        row['issues'] += 1
        row['bis'] += bool(i['suffix'])
        row['pages'] += pages
        row['texts'] += i['texts']
        for k in KINDS:
            row[k] += i[k]
        row['other'] += i['texts'] - sum(i[k] for k in KINDS)
        row['report_issues'] += report
        row['report_pages'] += pages if report else 0
        if not i['suffix']:
            weekdays[y][i['date'].isoweekday()] += 1
        rows.append([i['number'], int(bool(i['suffix'])), i['date'].month * 100 + i['date'].day, pages, i['texts'],
                     int(report)])
    for y, printed in _printed(issues).items():
        years[y]['printed'] = printed
    for y, n in words.items():
        if y in years:
            years[y]['words'] = n

    table = [[years[y][f] for f in YEAR_FIELDS] for y in sorted(years)]
    thickest = sorted(issues, key=lambda i: -(i['document__page_count'] or 0))[:10]
    return {
        'span': [first, last],
        'year_fields': YEAR_FIELDS,
        'years': table,
        # Monday … Sunday, the regular issues only (a «bis» comes out on any day).
        'weekdays': {y: [weekdays[y][d] for d in range(1, 8)] for y in sorted(weekdays)},
        'issue_fields': ['number', 'bis', 'monthday', 'pages', 'texts', 'report'],
        'issues': {y: [r for r, i in zip(rows, issues) if i['date'].year == y] for y in sorted(years)},
        'thickest': [{'key': _key(i), 'date': i['date'].isoformat(), 'pages': i['document__page_count'],
                      'texts': i['texts'], 'report': i['id'] in reports} for i in thickest],
        'totals': {f: sum(years[y][f] for y in years) for f in YEAR_FIELDS if f not in ('year', 'printed')},
        # The French edition apart: [issues, texts only it printed], a year at a time.
        'french': dict(sorted((french or {}).items())),
        # The Arabic texts with a title and no words on the site, a year at a time (a third of 1913–1919's).
        'bare': {y: n for y, n in sorted((bare or {}).items()) if n},
    }


def _key(issue: dict) -> str:
    return f"{issue['number']}-{issue['suffix']}" if issue['suffix'] else str(issue['number'])


def _reports(textless: list[dict], read: set[str]) -> set[int]:
    """The issues without a text whose first four pages present a report, and those a person read as one."""
    ids = {i['id'] for i in textless}
    heads: dict[int, list[str]] = defaultdict(list)
    for p in Page.objects.filter(document__issue__in=ids, index__lt=4).values('document__issue', 'text'):
        heads[p['document__issue']].append(p['text'])
    return {i['id'] for i in textless if _key(i) in read or REPORT.search(' '.join(heads[i['id']]))}


def _printed(issues: list[dict]) -> dict[int, int]:
    """The year's last printed page: its last issue's first page plus that issue's pages, kept where it agrees with the
    pages of the year's files within a tenth (a first page misread by a digit does not)."""
    last: dict[int, dict] = {}
    pages: Counter = Counter()
    for i in issues:
        last[i['date'].year] = i
        pages[i['date'].year] += i['document__page_count'] or 0
    out = {}
    for y, i in last.items():
        if i['first_page_number'] and i['document__page_count']:
            end = i['first_page_number'] + i['document__page_count'] - 1
            if abs(end - pages[y]) <= pages[y] / 10:
                out[y] = end
    return out


def _french(first: int, last: int) -> dict[int, list[int]]:
    """The French edition's issues a year, and the texts only it printed (their Arabic an AI translation, BO 7410's way)."""
    out: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for row in (Issue.objects.filter(edition=Edition.TRANSLATION_FR, copy_of__isnull=True, date__year__gte=first - 1,
                                     date__year__lte=last)
                .annotate(y=ExtractYear('date'), texts=Count('texts_first_published')).values('y', 'texts')):
        out[row['y']][0] += 1
        out[row['y']][1] += row['texts']
    return dict(out)


def _bare(first: int, last: int) -> dict[int, int]:
    """The Arabic edition's texts with no article holding a word, by the year of their issue."""
    worded = Article.objects.filter(version__text=OuterRef('pk'), version__language='ar',
                                    version__consolidation=Consolidation.AS_PUBLISHED).exclude(body='')
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, first_published_in__copy_of__isnull=True,
                                first_published_in__date__year__gte=first, first_published_in__date__year__lte=last)
            .filter(~Exists(worded)).annotate(y=ExtractYear('first_published_in__date')).values('y').annotate(n=Count('id')))
    return {r['y']: r['n'] for r in rows}


def _words(first: int, last: int) -> dict[int, int]:
    """The words of each text as first published (its Arabic version as published), by the year of its issue: the
    spaces in its articles, plus one an article."""
    year = 'version__text__first_published_in__date'
    spaces = Length('body') - Length(Replace('body', Value(' '), Value('')))
    rows = (Article.objects.filter(version__language='ar', version__consolidation=Consolidation.AS_PUBLISHED,
                                   version__text__first_published_in__edition=Edition.GENERAL_AR,
                                   **{f'{year}__year__gte': first, f'{year}__year__lte': last})
            .annotate(y=ExtractYear(year)).values('y')
            .annotate(words=Sum(spaces + Value(1), output_field=IntegerField())))
    return {r['y']: r['words'] for r in rows}
