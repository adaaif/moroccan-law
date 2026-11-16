"""The night's fold (apps/analytics/services/fold.py, `fold_events`): a day's events made into counts that describe
nobody, in the same few queries whatever the day held, replaced when the day is folded again, and the events deleted
after ANALYTICS_DAYS."""
import re
from datetime import UTC, date, datetime, timedelta
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import manage
from apps.analytics.models import DayCount, Event
from apps.analytics.services import fold

pytestmark = pytest.mark.django_db

DAY = date(2026, 11, 14)
DEPLOY = settings.BASE_DIR.parent / 'deploy'


def at(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def made(hour: datetime, name='page.shown', kind='article', path='/ma/loi/65-99/art_53', props=None, flow=None,
         lang='ar', screen='phone', n=1) -> list[Event]:
    return [Event(hour=hour, name=name, kind=kind, path=path, props=props or {}, flow=flow, lang=lang, screen=screen,
                  build='abc1234') for _ in range(n)]


def day_of(events: list[Event]) -> None:
    Event.objects.bulk_create(events)


def counts(day=DAY) -> dict:
    return {(c.metric, c.key): c.count for c in DayCount.objects.filter(day=day)}


def a_day(day=DAY, scale=1) -> None:
    """A small day: three visits, pages read, a tool opened and finished, speeds, an error, a link that led nowhere.
    `scale` gives every group more events, and more groups (paths, kinds, tools, screens)."""
    h = lambda k: at(day, 8 + k % 12)
    events = []
    for k in range(scale):
        suffix = '' if k == 0 else f'-{k}'
        events += made(h(k), props={'entry': True, 'source': 'search', 'ref': 'www.google.com', 'back': 'first',
                                    'fresh': 'dwm', 'installed': False})
        events += made(h(k), props={'entry': True, 'source': 'direct', 'back': 'today', 'fresh': 'none'}, lang='fr',
                       screen='desk')
        events += made(h(k), props={'entry': True, 'source': 'social', 'back': 'week', 'fresh': 'dw'}, kind='topic',
                       path=f'/topics/road{suffix}')
        events += made(h(k), props={'entry': True, 'source': 'direct', 'back': 'unknown', 'fresh': 'x'}, kind='home', path='/')
        events += made(h(k), props={'entry': False}, n=2)
        events += made(h(k), kind='law', path=f'/ma/loi/65-99{suffix}')
        tool = f'/topics/road/tools/fine{suffix}'
        events += made(h(k), 'tool.step', 'tool', tool, {'step': 'opened'}, flow=1000 + k, n=3)   # one opening, said 3 times
        events += made(h(k), 'tool.step', 'tool', tool, {'step': 'opened'}, flow=2000 + k)
        events += made(h(k), 'tool.step', 'tool', tool, {'step': 'result'}, flow=1000 + k)
        events += made(h(k), 'tool.step', 'tool', tool, {'step': 'opened'}, n=2)                  # without a flow: one each
        for ms in (800, 1200, 2000, 4000):
            events += made(h(k), 'page.speed', props={'lcp': ms, 'ttfb': ms // 10, 'cls': ms / 10000, 'net': '4g'})
        events += made(h(k), 'page.speed', kind='topic', screen='desk', props={'lcp': 500, 'inp': 100, 'saver': True})
        events += made(h(k), 'app.error', props={'error': 'TypeError', 'at': '/assets/index.js:1:2'})
        events += made(h(k), 'page.missing', kind='other', path=f'/ma/loi/1-1{suffix}',
                       props={'source': 'site', 'ref': 'hespress.com', 'inside': False}, n=2)
        events += made(h(k), 'page.missing', kind='other', path=f'/ma/loi/1-1{suffix}', props={'inside': True})
        events += made(h(k), 'page.missing', kind='other', path=f'/texts/9{suffix}', props={'inside': True})
    day_of(events)


def test_a_days_counts(django_assert_max_num_queries):
    a_day()
    day_of(made(at(DAY - timedelta(1), 12)) + made(at(DAY + timedelta(1), 0)))    # the days beside are not this one's
    assert fold.fold(DAY) == len(counts())
    c = counts()
    # The events by name, kind, language and screen.
    assert c['page.shown', 'kind=article'] == 4 and c['page.shown', 'kind=topic'] == 1 and c['page.shown', 'kind=home'] == 1
    assert c['page.shown', 'kind=law'] == 1
    assert c['page.shown.lang', 'ar'] == 6 and c['page.shown.lang', 'fr'] == 1
    assert c['page.shown.screen', 'phone'] == 6 and c['page.shown.screen', 'desk'] == 1
    assert c['tool.step', 'kind=tool'] == 7 and c['page.speed', 'kind=article'] == 4 and c['app.error', 'kind=article'] == 1
    # The choices and yes-or-no properties.
    assert c['page.shown.entry', 'true'] == 4 and c['page.shown.entry', 'false'] == 2
    assert c['page.shown.source', 'search'] == 1 and c['page.shown.source', 'direct'] == 2
    assert c['page.shown.source', 'social'] == 1
    assert c['page.shown.back', 'first'] == 1 and c['page.shown.fresh', 'dwm'] == 1
    assert c['page.shown.installed', 'false'] == 1
    assert c['tool.step.step', 'opened'] == 6 and c['tool.step.step', 'result'] == 1
    assert c['page.speed.net', '4g'] == 4 and c['page.speed.saver', 'true'] == 1
    assert c['page.missing.source', 'site'] == 2
    assert c['page.missing.inside', 'true'] == 2 and c['page.missing.inside', 'false'] == 2
    # A pattern's or a number's values are never keys: a host, an error, a place in a file, a figure.
    assert not {m for m, _ in c} & {'page.shown.ref', 'page.speed.lcp', 'page.speed.cls', 'app.error.error',
                                     'app.error.at', 'api.failed.endpoint', 'api.failed.status', 'page.missing.ref'}
    # Visits and readers.
    assert c['visits', ''] == 4 and c['visits.nostore', ''] == 1
    assert c['readers.day', ''] == 2 and c['readers.week', ''] == 2 and c['readers.month', ''] == 1
    # The pages shown, by address.
    assert c['page.path', '/ma/loi/65-99/art_53'] == 4 and c['page.path', '/'] == 1 and c['page.path', '/topics/road'] == 1
    assert ('page.path', '/ma/loi/1-1') not in c
    # The addresses that led nowhere, by address.
    assert c['page.missing.path', '/ma/loi/1-1'] == 3 and c['page.missing.path', '/texts/9'] == 1
    assert ('page.missing.path', '/ma/loi/65-99/art_53') not in c
    # A tool's openings by step: one flow said three times is one, two without a flow are two.
    assert c['tool.step', '/topics/road/tools/fine:opened'] == 4
    assert c['tool.step', '/topics/road/tools/fine:result'] == 1
    # Speeds: the 75th percentile by nearest rank (800, 1200, 2000, 4000 → 2000), cls in thousandths.
    assert c['speed.lcp.p75', 'article:phone'] == 2000 and c['speed.ttfb.p75', 'article:phone'] == 200
    assert c['speed.cls.p75', 'article:phone'] == 200 and c['speed.n', 'article:phone'] == 4
    assert c['speed.lcp.p75', 'topic:desk'] == 500 and c['speed.inp.p75', 'topic:desk'] == 100
    assert ('speed.inp.p75', 'article:phone') not in c


def test_the_75th_percentile_is_the_nearest_rank():
    assert fold.p75([5]) == 5
    assert fold.p75([4, 1, 3, 2]) == 3
    assert fold.p75(list(range(1, 101))) == 75
    assert fold.p75([1, 2, 3, 4, 5]) == 4


def test_a_day_is_moroccos_day_by_the_zones_own_rules():
    """On 10 September 2026 Morocco was an hour ahead: 23:00 UTC on the 9th was its 10th. Since 20 September it is on
    Greenwich's time: 23:00 UTC on 14 November is still the 14th."""
    day_of(made(at(date(2026, 9, 9), 23)) + made(at(date(2026, 9, 10), 22)) + made(at(date(2026, 9, 10), 23)))
    fold.fold(date(2026, 9, 10))
    assert counts(date(2026, 9, 10))['page.shown', 'kind=article'] == 2
    day_of(made(at(DAY, 23)) + made(at(DAY + timedelta(1), 0)))
    fold.fold(DAY)
    assert counts()['page.shown', 'kind=article'] == 1


OTHERS = {('visit.country', 'MA'): 7, ('machine.requests', 'googlebot'): 120, ('past.pages', '/ma/loi/65-99'): 40,
          ('visitors', ''): 3, ('speedy', ''): 1}


def test_folding_a_day_again_replaces_its_own_counts_and_no_other_writers(api):
    """The door's countries, the night's machines, the old counts imported, and any metric outside the fold's names stay
    as their writers left them, however often the day is folded."""
    DayCount.objects.bulk_create(DayCount(day=DAY, metric=m, key=k, count=n) for (m, k), n in OTHERS.items())
    DayCount.objects.create(day=DAY, metric='page.path', key='/gone', count=99)       # a count the day no longer has
    DayCount.objects.create(day=DAY, metric='readers.year', key='', count=5)           # under a prefix the fold owns
    a_day()
    fold.fold(DAY)
    once = counts()
    fold.fold(DAY)
    assert counts() == once
    assert {k: once[k] for k in OTHERS} == OTHERS
    assert ('page.path', '/gone') not in once and ('readers.year', '') not in once
    Event.objects.filter(name='app.error').delete()
    fold.fold(DAY)
    assert ('app.error', 'kind=article') not in counts() and {k: counts()[k] for k in OTHERS} == OTHERS


def test_every_count_the_fold_writes_is_one_it_owns():
    """So folding a day again never meets a count it cannot replace, and never takes another writer's."""
    a_day()
    fold.fold(DAY)
    assert all(fold.owns(metric) for metric, _ in counts())
    for other in ('visit.country', 'machine.requests', 'past.pages', 'visitors', 'page.pathways'):
        assert not fold.owns(other), other


def test_an_event_the_registry_no_longer_names_is_not_folded():
    day_of(made(at(DAY, 9)) + made(at(DAY, 9), 'page.clicked'))
    fold.fold(DAY)
    assert counts()['page.shown', 'kind=article'] == 1
    assert not any(metric.startswith('page.clicked') for metric, _ in counts())


def test_the_most_met_addresses_alone_are_kept(monkeypatch):
    monkeypatch.setattr(fold, 'PATHS_KEPT', {'page.shown': 2, 'page.missing': 1})
    day_of(made(at(DAY, 9), path='/a', n=3) + made(at(DAY, 9), path='/b', n=1) + made(at(DAY, 9), path='/c', n=2)
           + made(at(DAY + timedelta(1), 9), path='/d')
           + made(at(DAY, 9), 'page.missing', 'other', '/x', n=2) + made(at(DAY, 9), 'page.missing', 'other', '/y', n=5))
    fold.fold(DAY, DAY + timedelta(1))
    paths = lambda day, metric: {k: v for (m, k), v in counts(day).items() if m == metric}
    assert paths(DAY, 'page.path') == {'/a': 3, '/c': 2}
    assert paths(DAY + timedelta(1), 'page.path') == {'/d': 1}
    assert paths(DAY, 'page.missing.path') == {'/y': 5}


def test_a_day_keeps_2000_pages_shown_and_200_addresses_that_led_nowhere():
    assert fold.PATHS_KEPT == {'page.shown': 2000, 'page.missing': 200}


def _queries(**kwargs) -> int:
    with CaptureQueriesContext(connection) as seen:
        fold.fold(**kwargs)
    return len(seen.captured_queries)


def test_a_fold_costs_the_same_queries_for_a_small_day_or_a_large_one():
    """Ten times the events and the groups (paths, kinds, tools, speeds' groups): not one query more."""
    a_day()
    small = _queries(first=DAY)
    Event.objects.all().delete()
    a_day(scale=10)
    large = _queries(first=DAY)
    assert small == large <= 12
    assert counts()['visits', ''] == 40


def test_folding_many_days_costs_what_one_day_does():
    a_day()
    one = _queries(first=DAY)
    for k in range(1, 4):
        a_day(DAY - timedelta(k))
    many = _queries(first=DAY - timedelta(3), last=DAY)
    assert many == one
    assert all(counts(DAY - timedelta(k))['visits', ''] == 4 for k in range(4))


def test_a_day_without_events_has_no_counts():
    assert fold.fold(DAY) == 0 and not DayCount.objects.exists()


def test_the_events_past_the_days_kept_are_deleted(settings):
    settings.ANALYTICS_DAYS = 90
    today = date(2026, 11, 15)
    kept = today - timedelta(90)
    day_of(made(at(kept - timedelta(1), 12)) + made(at(kept, 12)) + made(at(today, 9)))
    assert fold.forget(today) == 1
    assert sorted(Event.objects.values_list('hour', flat=True)) == [at(kept, 12), at(today, 9)]
    DayCount.objects.create(day=kept - timedelta(5), metric='visits', key='', count=3)
    assert fold.forget(today) == 0 and DayCount.objects.count() == 1      # the counts stay for good


def run(*args) -> str:
    out = StringIO()
    call_command('fold_events', *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def morning(monkeypatch):
    """15 November 2026, 03:30 in Morocco: the night's job."""
    monkeypatch.setattr(timezone, 'now', lambda: datetime(2026, 11, 15, 3, 30, tzinfo=UTC))


def test_the_night_folds_yesterday_and_deletes_the_old_events(morning, settings):
    settings.ANALYTICS_DAYS = 90
    a_day()
    day_of(made(at(date(2026, 8, 1), 9)) + made(at(date(2026, 11, 15), 1)))
    said = run()
    assert '2026-11-14:' in said and '1 events older than the days kept deleted' in said
    assert counts()['visits', ''] == 4
    assert not DayCount.objects.filter(day=date(2026, 11, 15)).exists()


def test_the_night_folds_a_day_asked_for(morning):
    a_day(date(2026, 11, 10))
    assert '2026-11-10:' in run('--day', '2026-11-10')
    assert counts(date(2026, 11, 10))['visits', ''] == 4


def test_all_the_days_held_are_folded_up_to_yesterday(morning):
    for day in (date(2026, 11, 12), date(2026, 11, 14), date(2026, 11, 15)):
        a_day(day)
    assert '2026-11-12 to 2026-11-14:' in run('--all')
    assert set(DayCount.objects.values_list('day', flat=True)) == {date(2026, 11, 12), date(2026, 11, 14)}


def test_with_nothing_held_there_is_no_day_to_fold(morning):
    assert 'no day to fold' in run('--all')
    day_of(made(at(date(2026, 11, 15), 1)))                 # today's alone: folded tomorrow night
    assert 'no day to fold' in run('--all')


def test_a_day_that_is_no_day_is_refused():
    with pytest.raises(CommandError, match='not a day'):
        run('--day', '2026-13-01')


def test_the_fold_never_empties_the_kept_answers():
    """It writes no row an answer reads: after any command not in READ_ONLY, manage.py empties every kept answer."""
    assert 'fold_events' in manage.READ_ONLY


@pytest.mark.skipif(not DEPLOY.is_dir(), reason='the repository is not beside the app')
def test_the_nights_dump_leaves_the_events_out_and_keeps_their_counts():
    night = (DEPLOY / 'nightly.sh').read_text(encoding='utf-8')
    dump = next(line for line in night.splitlines() if 'pg_dump' in line and not line.lstrip().startswith('#'))
    assert '--exclude-table-data=analytics_event ' in dump + ' '
    assert 'analytics_daycount' not in dump
    # A fold that fails is said, and the night (under set -e) goes on to its other jobs and the dump.
    assert re.search(r'^"\$ROOT/venv/bin/python" manage\.py fold_events \|\| echo .fold_events failed. >&2$', night, re.M)
    assert night.index('manage.py fold_events') < night.index('pg_dump') and 'set -euo pipefail' in night
