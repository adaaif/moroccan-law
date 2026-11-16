"""The night's fold (the analytics review, 15 Nov 2026): a day's events made into counts kept for good (DayCount),
before the rows go after ANALYTICS_DAYS. Each count is a metric and a key, and describes nobody:

- `<name>`, key `kind=<kind>`: the events of a name on a kind of page; `<name>.lang` and `<name>.screen`, by value;
- `<name>.<prop>`, key the value, for each Choice or Bool property the registry gives the name (a Bool as true/false);
- `page.path`, key the address: the pages shown, the day's 2,000 most shown; `page.missing.path`, the addresses that led
  nowhere, the day's 200 most met (PATHS_KEPT);
- `tool.step`, key `<path>:<step>`: the tool's openings that reached the step (distinct flows; an event without a flow
  is one opening);
- `visits` (every visit's first page), `visits.nostore` (a phone that keeps nothing), and `readers.day`, `readers.week`,
  `readers.month` (the visits that were their phone's first of that period: `fresh` holds d, w, m), key '';
- `speed.<lcp|inp|cls|ttfb>.p75`, key `<kind>:<screen>`, the 75th percentile as the count (cls times 1000), and
  `speed.n` with how many page.speed events the group had.

Every number is read in the same few queries whatever the days hold, the groups made by the database (GROUP BY), and
written in one delete and one insert. The 75th percentile is worked out here: SQLite has no percentile function and
PostgreSQL's percentile_cont would make the two databases count differently. One query returns the speed values (a
day's page.speed events, four numbers each), and each group's 75th percentile is its nearest rank: the value at
ceil(0.75 n) of the sorted values.

The days are Morocco's (TIME_ZONE): their first hours are worked out here from the pinned zone rules and the rows chosen
by them, never by the database's own time zones (config/settings/base.py).

The fold owns the metrics it writes (`owns`), and folding a day again replaces those alone: the registry's names and
every `<name>.…`, `page.path`, `visits`, `visits.nostore`, `readers.…` and `speed.…`. DayCount's other writers keep
theirs (models.DayCount says who writes which). Only the registry's names are folded, so a measure removed from it
leaves its events to go with their days and writes nothing the fold would not own."""
import math
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Case, Count, DateField, Q, Value, When
from django.db.models.fields.json import KT
from django.utils import timezone

from apps.analytics import registry
from apps.analytics.models import DayCount, Event

# The addresses kept a day, the most met first, by the event that met them.
PATHS_KEPT = {'page.shown': 2000, 'page.missing': 200}
PATH_METRICS = {'page.shown': 'page.path', 'page.missing': 'page.missing.path'}
# The metrics the fold writes, and so replaces: these names whole, and those under these prefixes.
OWNED = (*registry.MEASURES, 'page.path', 'visits', 'visits.nostore')
OWNED_UNDER = (*(f'{name}.' for name in registry.MEASURES), 'readers.', 'speed.')
SPEEDS = ('lcp', 'inp', 'cls', 'ttfb')
# The Choice and Bool properties, by name: what `<name>.<prop>` counts.
COUNTED = {name: {prop: rule for prop, rule in m.props.items() if isinstance(rule, (registry.Choice, registry.Bool))}
           for name, m in registry.MEASURES.items()}
_GROUPED = sorted({prop for props in COUNTED.values() for prop in props})
ENTRY = registry.MEASURES['page.shown'].props['entry']


def start(day: date) -> datetime:
    """The first hour of a Moroccan day."""
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_default_timezone())


def owns(metric: str) -> bool:
    """Whether the fold writes this metric, and so replaces it when it folds a day again."""
    return metric in OWNED or metric.startswith(OWNED_UNDER)


def _owned() -> Q:
    q = Q(metric__in=OWNED)
    for prefix in OWNED_UNDER:
        q |= Q(metric__startswith=prefix)
    return q


def _days(first: date, last: date):
    """The registered events of the days from `first` to `last`, each given its day."""
    days = [first + timedelta(n) for n in range((last - first).days + 1)]
    edges = [start(d) for d in days] + [start(last + timedelta(1))]
    day = Case(*(When(hour__gte=edges[i], hour__lt=edges[i + 1], then=Value(d)) for i, d in enumerate(days)),
               output_field=DateField())
    rows = Event.objects.filter(hour__gte=edges[0], hour__lt=edges[-1], name__in=list(registry.MEASURES))
    return days, rows.annotate(day=day).order_by()


def _word(value, rule) -> str:
    """A property's value as a key: a Bool as 'true' or 'false' whichever way the database gave it back."""
    if isinstance(rule, registry.Bool):
        return 'true' if value in (True, 1, '1', 'true') else 'false'
    return str(value)


def p75(values: list) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.75 * len(ordered)) - 1]


def fold(first: date, last: date | None = None) -> int:
    """The counts of the days from `first` to `last` (one day when `last` is None) written again; how many rows."""
    last = last or first
    days, rows = _days(first, last)
    counts: Counter = Counter()

    # The events by name, kind, language and screen.
    for g in rows.values('day', 'name', 'kind', 'lang', 'screen').annotate(n=Count('id')):
        day, name, n = g['day'], g['name'], g['n']
        counts[day, name, f'kind={g["kind"]}'] += n
        counts[day, f'{name}.lang', g['lang']] += n
        counts[day, f'{name}.screen', g['screen']] += n

    # The Choice and Bool properties, all in one grouping (their values are few, so the groups are too).
    grouped = rows.annotate(**{f'p_{p}': KT(f'props__{p}') for p in _GROUPED})
    for g in grouped.values('day', 'name', *(f'p_{p}' for p in _GROUPED)).annotate(n=Count('id')):
        day, name, n = g['day'], g['name'], g['n']
        for prop, rule in COUNTED.get(name, {}).items():
            if (value := g[f'p_{prop}']) is not None:
                counts[day, f'{name}.{prop}', _word(value, rule)] += n
        if name == 'page.shown' and g['p_entry'] is not None and _word(g['p_entry'], ENTRY) == 'true':
            fresh = g['p_fresh'] or ''
            counts[day, 'visits', ''] += n
            for letter, metric in (('d', 'readers.day'), ('w', 'readers.week'), ('m', 'readers.month'),
                                   ('x', 'visits.nostore')):
                if letter in fresh:
                    counts[day, metric, ''] += n

    # The pages shown and the addresses that led nowhere, the most met first: PATHS_KEPT of each a day.
    kept: Counter = Counter()
    met = rows.filter(name__in=list(PATHS_KEPT)).values('day', 'name', 'path').annotate(n=Count('id')).order_by(
        'day', 'name', '-n', 'path')
    for g in met.iterator():
        day, name = g['day'], g['name']
        if kept[day, name] < PATHS_KEPT[name]:
            kept[day, name] += 1
            counts[day, PATH_METRICS[name], g['path']] = g['n']

    # A tool's openings that reached each step.
    steps = rows.filter(name='tool.step').annotate(step=KT('props__step')).values('day', 'path', 'step').annotate(
        flows=Count('flow', distinct=True), loose=Count('id', filter=Q(flow__isnull=True)))
    for g in steps:
        if g['step'] is not None:
            counts[g['day'], 'tool.step', f'{g["path"]}:{g["step"]}'] = g['flows'] + g['loose']

    # Speeds: each group's 75th percentile.
    values: defaultdict = defaultdict(lambda: defaultdict(list))
    sampled: Counter = Counter()
    speed = rows.filter(name='page.speed').annotate(**{f's_{m}': KT(f'props__{m}') for m in SPEEDS})
    for day, kind, screen, *found in speed.values_list('day', 'kind', 'screen', *(f's_{m}' for m in SPEEDS)).iterator():
        group = (day, f'{kind}:{screen}')
        sampled[group] += 1
        for metric, value in zip(SPEEDS, found):
            if value is not None:
                values[group][metric].append(float(value))
    for (day, key), n in sampled.items():
        counts[day, 'speed.n', key] = n
        for metric, found in values[day, key].items():
            figure = p75(found) * (1000 if metric == 'cls' else 1)
            counts[day, f'speed.{metric}.p75', key] = round(figure)

    with transaction.atomic():
        DayCount.objects.filter(_owned(), day__in=days).delete()
        DayCount.objects.bulk_create(DayCount(day=day, metric=metric, key=key, count=n)
                                     for (day, metric, key), n in counts.items())
    return len(counts)


def first_day() -> date | None:
    """The Moroccan day of the oldest event held."""
    oldest = Event.objects.order_by('hour').values_list('hour', flat=True).first()
    return timezone.localdate(oldest) if oldest else None


def forget(today: date | None = None) -> int:
    """The events older than ANALYTICS_DAYS days deleted; how many."""
    today = today or timezone.localdate()
    return Event.objects.filter(hour__lt=start(today - timedelta(days=settings.ANALYTICS_DAYS))).delete()[0]
