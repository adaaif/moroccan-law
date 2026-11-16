"""What the counts say (the analytics review, 15 Nov 2026): every figure of the staff's page (/admin/analytics/) and of
the Monday letter (`analytics_letter`), read back from the day counts (DayCount), the search log, the assistants'
tallies and the topics' «did it help». Plain dicts: the page and the letter only show them.

A period is the last `days` complete days of Morocco, yesterday back, set against the `days` before them. A count is
{now, before, change}, the change in % of `before` when it is not 0. A share is {now, before, points}, in % of its
whole, and its change in points: a share that goes from 10 % to 15 % has moved 5 points, not 50 %.

Readers are counted, never described. In a breakdown of readers (their country, how they came, their language and
screen, how long since their phone last came) a group of 1 to 4 is said FEWER, never its number, and so are its share
and its change: a group that small is a person or two. A list of contents (addresses, tools, errors, machines) shows
its numbers.

A day's speeds are its 75th percentiles (services/fold.py); a period's is the median of its days' values, each value
counted as many times as its day had measures (`speed.n`), so a quiet day weighs less than a busy one.

The counts from before 16 Nov 2026 (`past.*`, written by `import_past_counts`) are summed whole, with their first and
last day: a reader there is a person seen in a day in one country, so one seen in two countries was counted twice.

Every figure is read in QUERIES queries whatever the counts hold: the counts of both periods summed by metric and key
(their keys are few: kinds, languages, countries, tools' steps, machines' families), the days' rows the tables by day
need (readers, visits, speeds), the most shown addresses and the missing ones (each its own LIMIT), and one each for the
assistants' tallies, the searches, what readers said of them, «did it help» and the counts from before."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from functools import reduce
from operator import or_

from django.db.models import BooleanField, Case, Count, Max, Min, Q, Sum, Value, When
from django.utils import timezone

from apps.analytics.models import DayCount
from apps.analytics.services import past
from apps.analytics.services.fold import start
from apps.mcp.models import Tally
from apps.search.models import SearchEvent, SearchLog
from apps.topics.models import Helped

DAYS = (7, 28)                  # the periods the page offers; the first is the default
FEW = 5                         # a group of readers under this is said FEWER
FEWER = 'fewer than 5'
TOP = 20                        # the longest list of addresses, tools or missing pages
COUNTRIES = 10
SCREENS = ('phone', 'desk')
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
SPEEDS = ('lcp', 'inp', 'cls', 'ttfb')
# web.dev's thresholds: good at or under the first, poor over the second (the Core Web Vitals, and TTFB's own guide).
THRESHOLDS = {'lcp': (2500, 4000), 'inp': (200, 500), 'cls': (0.1, 0.25), 'ttfb': (800, 1800)}
# page.shown's `back` for a phone that had opened the site before.
RETURNING = ('today', 'day', 'week', 'month', 'more')
SITE, ASSISTANTS = '', 'mcp'    # SearchLog.via
STEPS = ('opened', 'answered', 'result')
ERRORS = ('app.error', 'api.failed', 'page.missing')
BROWSER = 'browser'             # machine.requests' family for people's browsers
# The counts summed over a period by metric and key; DAILY's are also read day by day.
SUMMED = ('visits', 'visits.nostore', 'readers.day', 'page.shown', 'page.shown.lang', 'page.shown.screen',
          'page.shown.source', 'page.shown.back', 'visit.country', 'tool.step', *ERRORS, 'machine.requests')
DAILY = ('readers.day', 'visits')
QUERIES = 9


@dataclass(frozen=True)
class Period:
    first: date
    last: date
    days: int

    @property
    def before_first(self) -> date:
        return self.first - timedelta(self.days)

    @property
    def before_last(self) -> date:
        return self.first - timedelta(1)

    def said(self) -> dict:
        return {'days': self.days, 'first': self.first, 'last': self.last, 'before_first': self.before_first,
                'before_last': self.before_last}


def period(days: int = DAYS[0], today: date | None = None) -> Period:
    """The last `days` complete Moroccan days: yesterday and the days before it."""
    last = (today or timezone.localdate()) - timedelta(1)
    return Period(first=last - timedelta(days - 1), last=last, days=days)


def change(now: int, before: int) -> int | None:
    """The change in % of `before`; None when `before` is 0."""
    return round((now - before) * 100 / before) if before else None


def count(now: int, before: int) -> dict:
    return {'now': now, 'before': before, 'change': change(now, before)}


def percent(part, whole) -> float | None:
    return round(part * 100 / whole, 1) if whole else None


def share(part_now, whole_now, part_before, whole_before) -> dict:
    now, before = percent(part_now, whole_now), percent(part_before, whole_before)
    return {'now': now, 'before': before,
            'points': round(now - before, 1) if now is not None and before is not None else None}


def few(n) -> bool:
    """A group of readers too small to be shown by its number: 1 to 4 (none is no group)."""
    return isinstance(n, int) and 0 < n < FEW


def guarded(row: dict, now: int, before: int) -> dict:
    """A group of readers as it may be shown: a side under FEW said FEWER, its share too, and no change between them."""
    if few(now):
        row.update(now=FEWER, share=FEWER)
    if few(before):
        row.update(before=FEWER, share_before=FEWER)
    if few(now) or few(before):
        row['change'] = None
    return row


def groups(found: dict[str, tuple[int, int]], readers: bool, most: int | None = None) -> list[dict]:
    """A breakdown's rows, the largest first, each with its share of the breakdown's whole in both periods. With
    `readers`, each group is guarded, and the groups said FEWER come after the others by their key alone, so not even
    their order tells their sizes."""
    whole_now = sum(now for now, _ in found.values())
    whole_before = sum(before for _, before in found.values())

    def order(item):
        key, (now, _) = item
        return (1, 0, key) if readers and few(now) else (0, -now, key)

    rows = []
    for key, (now, before) in sorted(found.items(), key=order):
        row = {'key': key, **count(now, before), 'share': percent(now, whole_now),
               'share_before': percent(before, whole_before)}
        rows.append(guarded(row, now, before) if readers else row)
    return rows[:most] if most else rows


def weighted_median(pairs) -> float | None:
    """The median of the values, each counted `weight` times ((value, weight) pairs); None without any."""
    ordered = sorted((v, w) for v, w in pairs if w > 0)
    total = sum(w for _, w in ordered)
    if not total:
        return None
    low, high = (total - 1) // 2, total // 2        # the middle places of the values laid out one by one
    seen, lo = 0, None
    for value, weight in ordered:
        if lo is None and low < seen + weight:
            lo = value
        if high < seen + weight:
            break                                   # always reached: `high` is under `total`
        seen += weight
    return (lo + value) / 2


def _whole(value: float | None):
    """A median as it reads: 2 for 2.0, 1.5 as it is."""
    return int(value) if value is not None and value == int(value) else value


def band(metric: str, value) -> str | None:
    """'good', 'needs work' or 'poor' by web.dev's thresholds."""
    if value is None:
        return None
    good, poor = THRESHOLDS[metric]
    return 'good' if value <= good else 'poor' if value > poor else 'needs work'


def _span(p: Period) -> dict:
    return {'day__gte': p.before_first, 'day__lte': p.last}


def _both(p: Period) -> dict:
    """A count summed over each period: the one asked, and the one before it."""
    return {'now': Sum('count', filter=Q(day__gte=p.first), default=0),
            'before': Sum('count', filter=Q(day__lt=p.first), default=0)}


def _flag(field: str, edge) -> Case:
    """True for a row of the period asked, False for one of the period before (`edge`: the asked period's first hour)."""
    return Case(When(**{f'{field}__gte': edge}, then=Value(True)), default=Value(False), output_field=BooleanField())


def _side(now) -> str:
    return 'now' if now else 'before'


def _summed(p: Period) -> dict[str, dict[str, tuple[int, int]]]:
    found: dict = defaultdict(dict)
    rows = (DayCount.objects.filter(metric__in=SUMMED, **_span(p)).values('metric', 'key').annotate(**_both(p))
            .order_by())
    for r in rows:
        found[r['metric']][r['key']] = (r['now'], r['before'])
    return found


def _days(p: Period) -> dict[tuple, int]:
    """{(day, metric, key): count} for the tables by day: readers, visits, and the speeds of phones and desks."""
    speed = Q(metric__startswith='speed.') & reduce(or_, (Q(key__endswith=f':{s}') for s in SCREENS))
    rows = DayCount.objects.filter(Q(metric__in=DAILY) | speed, **_span(p)).values_list('day', 'metric', 'key', 'count')
    return {(day, metric, key): n for day, metric, key, n in rows}


def _top(metric: str, p: Period) -> list[dict]:
    """The TOP keys most counted in the period asked, each with its count before."""
    rows = (DayCount.objects.filter(metric=metric, **_span(p)).values('key').annotate(**_both(p)).filter(now__gt=0)
            .order_by('-now', 'key')[:TOP])
    return [{'key': r['key'], **count(r['now'], r['before'])} for r in rows]


def _calls(p: Period) -> dict[date, int]:
    """The assistants' calls by day (apps.mcp's tallies, every origin)."""
    return dict(Tally.objects.filter(**_span(p)).values('day').annotate(n=Sum('calls')).order_by()
                .values_list('day', 'n'))


def _by_day(p: Period, daily: dict, calls: dict) -> list[dict]:
    """Each day of the period beside the same weekday of the period before."""
    out = []
    for i in range(p.days):
        day = p.first + timedelta(i)
        was = day - timedelta(p.days)
        out.append({'day': day, 'was': was, 'weekday': WEEKDAYS[day.weekday()],
                    'readers': count(daily.get((day, 'readers.day', ''), 0), daily.get((was, 'readers.day', ''), 0)),
                    'visits': count(daily.get((day, 'visits', ''), 0), daily.get((was, 'visits', ''), 0)),
                    'calls': count(calls.get(day, 0), calls.get(was, 0))})
    return out


def _speeds(p: Period, daily: dict) -> dict[str, list[dict]]:
    """For phones and desks, each kind of page (the most measured first): its measures, and each speed (in SPEEDS'
    order) as the median of daily 75th percentiles in both periods, with its band."""
    pairs: defaultdict = defaultdict(list)
    measured: Counter = Counter()
    for (day, metric, key), n in daily.items():
        if not metric.startswith('speed.'):
            continue
        side = _side(day >= p.first)
        if metric == 'speed.n':
            measured[side, key] += n
            continue
        name = metric.split('.')[1]
        pairs[side, key, name].append((n / 1000 if name == 'cls' else n, daily.get((day, 'speed.n', key), 0)))
    out: dict = {screen: [] for screen in SCREENS}
    for key in sorted({key for _, key in measured}, key=lambda k: (-measured['now', k], k)):
        kind, _, screen = key.partition(':')
        speeds = []
        for name in SPEEDS:
            now, before = (weighted_median(pairs[side, key, name]) for side in ('now', 'before'))
            digits = 3 if name == 'cls' else None
            now, before = (None if v is None else round(v, digits) for v in (now, before))
            speeds.append({'name': name, 'now': now, 'before': before, 'band': band(name, now)})
        out[screen].append({'kind': kind, 'measures': count(measured['now', key], measured['before', key]),
                            'speeds': speeds})
    return out


def _tools(steps: dict[str, tuple[int, int]]) -> tuple[list[dict], dict]:
    """The TOP tools by openings, each with its openings that were answered and that reached a result; and all the
    tools' openings and results together."""
    by: defaultdict = defaultdict(dict)
    for key, pair in steps.items():
        if not key.startswith('kind='):
            path, _, step = key.rpartition(':')
            by[path][step] = pair
    rows = []
    for path, reached in by.items():
        opened, answered, result = (reached.get(step, (0, 0)) for step in STEPS)
        rows.append({'path': path, 'opened': count(*opened), 'answered': count(*answered), 'result': count(*result),
                     'finished': share(result[0], opened[0], result[1], opened[1])})
    rows.sort(key=lambda r: (-r['opened']['now'], r['path']))
    opened = [sum(r['opened'][side] for r in rows) for side in ('now', 'before')]
    result = [sum(r['result'][side] for r in rows) for side in ('now', 'before')]
    return rows[:TOP], {'opened': count(*opened), 'finished': share(result[0], opened[0], result[1], opened[1])}


def _searches(p: Period) -> dict:
    """The site's searches and the assistants' apart: how many, the share that found nothing, the share where an
    answer was opened, the median place of the first answer opened (0 is the citation's card, 1 the first text), and
    how often readers said they found it or not."""
    first, edge, end = start(p.before_first), start(p.first), start(p.last + timedelta(1))
    logs = (SearchLog.objects.filter(at__gte=first, at__lt=end, via__in=(SITE, ASSISTANTS))
            .annotate(now=_flag('at', edge)).values('now', 'via', 'opened')
            .annotate(n=Count('id'), empty=Count('id', filter=Q(results=0))).order_by())
    said = (SearchEvent.objects.filter(at__gte=first, at__lt=end, log__via__in=(SITE, ASSISTANTS),
                                       kind__in=(SearchEvent.Kind.FOUND, SearchEvent.Kind.NOT_FOUND))
            .annotate(now=_flag('at', edge)).values('now', 'log__via', 'kind').annotate(n=Count('id')).order_by())
    seen = {(side, via): {'n': 0, 'empty': 0, 'opened': 0, 'ranks': []}
            for side in ('now', 'before') for via in (SITE, ASSISTANTS)}
    for r in logs:
        s = seen[_side(r['now']), r['via']]
        s['n'] += r['n']
        s['empty'] += r['empty']
        if r['opened'] is not None:
            s['opened'] += r['n']
            s['ranks'].append((r['opened'], r['n']))
    heard: Counter = Counter()
    for r in said:
        heard[_side(r['now']), r['log__via'], r['kind']] += r['n']
    out = {}
    for via, name in ((SITE, 'site'), (ASSISTANTS, 'assistants')):
        a, b = seen['now', via], seen['before', via]
        out[name] = {'searches': count(a['n'], b['n']),
                     'empty': share(a['empty'], a['n'], b['empty'], b['n']),
                     'opened': share(a['opened'], a['n'], b['opened'], b['n']),
                     'rank': {'now': _whole(weighted_median(a['ranks'])), 'before': _whole(weighted_median(b['ranks']))},
                     'found': count(heard['now', via, 'found'], heard['before', via, 'found']),
                     'not_found': count(heard['now', via, 'not_found'], heard['before', via, 'not_found'])}
    return out


def _helped(p: Period) -> dict:
    """«هل ساعدك هذا؟»: the yes and the no the topics' pages were given."""
    edge = start(p.first)
    rows = (Helped.objects.filter(created_at__gte=start(p.before_first), created_at__lt=start(p.last + timedelta(1)))
            .annotate(now=_flag('created_at', edge)).values('now', 'helped').annotate(n=Count('id')).order_by())
    said: Counter = Counter()
    for r in rows:
        said[_side(r['now']), bool(r['helped'])] += r['n']
    return {'yes': count(said['now', True], said['before', True]), 'no': count(said['now', False], said['before', False])}


def _machines(found: dict[str, tuple[int, int]]) -> dict:
    """The requests by family (machine.requests, key `<family>:<kind>`), and the machines' share of them all: every
    family but the people's browsers."""
    families: defaultdict = defaultdict(lambda: [0, 0])
    for key, (now, before) in found.items():
        family = families[key.partition(':')[0]]
        family[0] += now
        family[1] += before
    whole = [sum(f[i] for f in families.values()) for i in (0, 1)]
    people = families.get(BROWSER, [0, 0])
    return {'families': groups({k: (v[0], v[1]) for k, v in families.items()}, readers=False),
            'share': share(whole[0] - people[0], whole[0], whole[1] - people[1], whole[1])}


def _past() -> dict | None:
    """The counts from before 16 Nov 2026, summed whole: None until `import_past_counts` has run."""
    # Bounded by day as well, so the read walks the days' index instead of every count.
    rows = (DayCount.objects.filter(day__lt=past.FIRST_DAY, metric__startswith=past.PREFIX).values('metric', 'key')
            .annotate(n=Sum('count'), first=Min('day'), last=Max('day')).order_by())
    sums: defaultdict = defaultdict(dict)
    first = last = None
    for r in rows:
        sums[r['metric']][r['key']] = r['n']
        first = r['first'] if first is None else min(first, r['first'])
        last = r['last'] if last is None else max(last, r['last'])
    if first is None:
        return None
    countries = sorted(sums['past.country'].items(), key=lambda kv: (1, 0, kv[0]) if few(kv[1]) else (0, -kv[1], kv[0]))
    assistants = sorted(sums['past.assistant'].items(), key=lambda kv: (-kv[1], kv[0]))
    requests = sums['past.requests']
    return {'first': first, 'last': last,
            'pages': sum(sums['past.pages'].values()), 'readers': sum(sums['past.readers'].values()),
            'people': requests.get('people', 0), 'machines': requests.get('machines', 0),
            'calls': sum(sums['past.assistant'].values()),
            'tools': sum(n for key, n in sums['past.tool'].items() if key.endswith(':open')),
            'countries': [{'key': k, 'n': FEWER if few(n) else n} for k, n in countries[:COUNTRIES]],
            'assistants': [{'key': k, 'n': n} for k, n in assistants[:COUNTRIES]]}


def build(days: int = DAYS[0], today: date | None = None) -> dict:
    """Every figure of the page, for the last `days` complete days beside the `days` before."""
    p = period(days, today)
    summed, daily, calls = _summed(p), _days(p), _calls(p)

    def one(metric: str, key: str = '') -> tuple[int, int]:
        return summed.get(metric, {}).get(key, (0, 0))

    def total(metric: str) -> tuple[int, int]:
        found = summed.get(metric, {}).values()
        return sum(n for n, _ in found), sum(b for _, b in found)

    def by(metric: str, readers: bool, most: int | None = None) -> list[dict]:
        return groups({k.removeprefix('kind='): v for k, v in summed.get(metric, {}).items()}, readers, most)

    visits = one('visits')
    back = summed.get('page.shown.back', {})
    returning = [sum(back.get(k, (0, 0))[i] for k in RETURNING) for i in (0, 1)]
    returning_share = share(returning[0], visits[0], returning[1], visits[1])
    for side, n in zip(('now', 'before'), returning):
        if few(n):
            returning_share.update({side: FEWER, 'points': None})
    tools, all_tools = _tools(summed.get('tool.step', {}))
    shown = by('page.shown', readers=False)
    pages = [sum(r[side] for r in shown) for side in ('now', 'before')]
    return {
        'period': p.said(),
        'come': {'days': _by_day(p, daily, calls), 'readers': count(*one('readers.day')), 'visits': count(*visits),
                 'returning': returning_share, 'nostore': count(*one('visits.nostore')),
                 'back': by('page.shown.back', readers=True), 'calls': count(*total_calls(calls, p))},
        'arrive': {'sources': by('page.shown.source', readers=True)},
        'read': {'pages': count(*pages), 'paths': _top('page.path', p), 'kinds': shown,
                 'langs': by('page.shown.lang', readers=True), 'screens': by('page.shown.screen', readers=True)},
        'where': {'countries': by('visit.country', readers=True, most=COUNTRIES)},
        'search': _searches(p),
        'tools': {'tools': tools, 'all': all_tools, 'helped': _helped(p)},
        'speed': _speeds(p, daily),
        'breaks': {'kinds': {metric.replace('.', '_'): by(metric, readers=False) for metric in ERRORS},
                   'totals': {metric.replace('.', '_'): count(*total(metric)) for metric in ERRORS},
                   'missing': _top('page.missing.path', p)},
        'machines': _machines(summed.get('machine.requests', {})),
        'past': _past(),
    }


def total_calls(calls: dict[date, int], p: Period) -> tuple[int, int]:
    """The assistants' calls of the period asked, and of the period before."""
    now = sum(n for day, n in calls.items() if day >= p.first)
    return now, sum(calls.values()) - now


def most_shown(days: int = 7, most: int = 200, today: date | None = None) -> list[str]:
    """The `most` addresses most shown in the last `days` complete days, the most shown first (one query)."""
    p = period(days, today)
    return list(DayCount.objects.filter(metric='page.path', day__gte=p.first, day__lte=p.last).values('key')
                .annotate(n=Sum('count')).order_by('-n', 'key').values_list('key', flat=True)[:most])


def shown_under(prefix: str, days: int = 28, today: date | None = None) -> dict[str, int]:
    """{address: times shown} in the last `days` complete days, for every address under `prefix` (one query)."""
    p = period(days, today)
    return dict(DayCount.objects.filter(metric='page.path', day__gte=p.first, day__lte=p.last, key__startswith=prefix)
                .values('key').annotate(n=Sum('count')).order_by().values_list('key', 'n'))
