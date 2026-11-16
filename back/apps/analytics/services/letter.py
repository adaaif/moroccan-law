"""The Monday letter (`analytics_letter`, the analytics review, 15 Nov 2026): ten figures of the last 7 complete days,
each beside the 7 before, in plain English for the people who run the site (ANALYTICS_LETTER_TO). Its figures are the
staff page's (services/report.py), read the same way: the letter says nothing the page does not. Below them, two lines
on the requests for access, as the admin's lists of them say, and the week's decisions on access, one line each
(apps/opendata/services/requests.py)."""
from datetime import date

from django.conf import settings

from apps.analytics.services import report
from apps.opendata.services import requests as access_requests

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
MOST_READ = 3


def day(d: date) -> str:
    return f'{d.day} {MONTHS[d.month - 1]} {d.year}'


def number(value) -> str:
    """A figure as the letter writes it: 1,234, or «none»."""
    return 'none' if value is None else f'{value:,}'


def counted(f: dict) -> str:
    """«120 (before 100, +20%)»."""
    out = f'{number(f["now"])} (before {number(f["before"])}'
    return out + (f', {f["change"]:+d}%)' if f.get('change') is not None else ')')


def shared(f: dict) -> str:
    """«35.0% (before 30.0%, +5.0 points)»."""
    pct = lambda v: v if isinstance(v, str) else 'none' if v is None else f'{v}%'
    out = f'{pct(f["now"])} (before {pct(f["before"])}'
    return out + (f', {f["points"]:+} points)' if f.get('points') is not None else ')')


def decided(first: date, last: date) -> list[str]:
    """The staff's decisions on access in the week, one line each, under a line that says so."""
    rows = access_requests.decisions(first, last)
    return ['The staff\'s decisions on access this week:', *rows] if rows else [
        'The staff\'s decisions on access this week: none.']


def write(r: dict) -> tuple[str, str]:
    """The letter's subject and body, from report.build(7)."""
    p = r['period']
    span = f'{day(p["first"])} to {day(p["last"])}'
    read = ', '.join(f'{x["key"]} ({number(x["now"])})' for x in r['read']['paths'][:MOST_READ]) or 'none'
    site = r['search']['site']
    tools = r['tools']['all']
    article = next((row for row in r['speed']['phone'] if row['kind'] == 'article'), None)
    lcp = next((m for m in article['speeds'] if m['name'] == 'lcp'), None) if article else None
    if lcp and lcp['now'] is not None:
        was = f'{number(lcp["before"])} ms' if lcp['before'] is not None else 'none'
        speed = f'{number(lcp["now"])} ms, {lcp["band"]} (before {was})'
    else:
        speed = 'no measure'
    errors = r['breaks']['totals']
    said = lambda key: number(errors[key]['now'])
    was = lambda key: number(errors[key]['before'])
    lines = [
        f'The week of {span}, beside {day(p["before_first"])} to {day(p["before_last"])}.',
        '',
        f' 1. Readers: {counted(r["come"]["readers"])}',
        f' 2. Visits: {counted(r["come"]["visits"])}',
        f' 3. Returning visits: {shared(r["come"]["returning"])}',
        f' 4. Pages shown: {counted(r["read"]["pages"])}',
        f' 5. Most read: {read}',
        f' 6. Searches on the site: {counted(site["searches"])}; with no result: {shared(site["empty"])}',
        f' 7. Assistants\' calls: {counted(r["come"]["calls"])}',
        f' 8. Tools opened: {counted(tools["opened"])}; reaching a result: {shared(tools["finished"])}',
        f' 9. Articles on phones, LCP (median of the daily 75th percentiles): {speed}',
        f'10. Errors: {said("app_error")} in the app, {said("api_failed")} failed API calls, '
        f'{said("page_missing")} missing pages (before {was("app_error")}, {was("api_failed")}, {was("page_missing")})',
        '',
        # Access on request: the queue and the accesses ending (apps/opendata/services/requests.py, as its admin lists),
        # and the week's decisions, so that one nobody remembers making is seen.
        *access_requests.lines(access_requests.counted()),
        *decided(p['first'], p['last']),
        '',
        'Readers: each day\'s phones on their first visit of that day, added up over the days. Nothing here describes '
        'a person.',
        f'The whole report: {settings.SITE_URL.rstrip("/")}/admin/analytics/',
    ]
    return f'{settings.SITE_NAME}: the week of {span}', '\n'.join(lines) + '\n'


def letter(today: date | None = None) -> tuple[str, str]:
    """The subject and body for the last 7 complete days."""
    return write(report.build(7, today))
