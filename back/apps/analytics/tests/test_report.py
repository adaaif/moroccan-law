"""The counts read back (apps/analytics/services/report.py): each figure beside the period before, a group of readers
under 5 never shown by its number, and every figure read in the same few queries whatever the counts hold."""
from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.analytics.models import DayCount
from apps.analytics.services import report
from apps.mcp.models import Tally
from apps.search.models import SearchEvent, SearchLog
from apps.topics.models import Helped

pytestmark = pytest.mark.django_db

TODAY = date(2026, 11, 15)
NOW = [TODAY - timedelta(k) for k in range(1, 8)]          # 8 to 14 Nov: the period asked
BEFORE = [day - timedelta(7) for day in NOW]                 # 1 to 7 Nov: the period before


def counts(day: date, metric: str, **keys) -> None:
    DayCount.objects.bulk_create(DayCount(day=day, metric=metric, key=key, count=n) for key, n in keys.items())


def put(day: date, metric: str, key: str, n: int) -> None:
    DayCount.objects.create(day=day, metric=metric, key=key, count=n)


def at(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def a_fortnight(scale: int = 1) -> None:
    """Two weeks of counts: the week asked, and the week before with less. `scale` gives every group more rows (more
    pages, tools, countries, kinds of page) and the same figures for the groups the tests read."""
    for day in NOW + BEFORE:
        was = day in BEFORE
        for metric, n in (('readers.day', 6 if was else 10), ('visits', 15 if was else 20), ('visits.nostore', 1)):
            put(day, metric, '', n)
        counts(day, 'page.shown.back', first=10 if was else 12, today=2 if was else 4, week=1 if was else 3,
               unknown=2 if was else 1)
        counts(day, 'page.shown.source', search=10, direct=3 if was else 9, social=1 if was else 0)
        counts(day, 'page.shown', **{'kind=article': 30, 'kind=law': 10 if was else 20})
        counts(day, 'page.shown.lang', ar=38 if was else 49, fr=2 if was else 1)
        counts(day, 'page.shown.screen', phone=40 if was else 50)
        counts(day, 'visit.country', MA=12 if was else 18)
        put(day, 'page.path', '/ma/loi/65-99/art_53', 9 if was else 12)
        put(day, 'page.path', '/topics/road', 3)
        counts(day, 'tool.step', **{'kind=tool': 9, '/topics/road/tools/fine:opened': 4, '/topics/road/tools/fine:answered': 3,
                                    '/topics/road/tools/fine:result': 1 if was else 2, '/topics/work/tools/end:opened': 1})
        counts(day, 'app.error', **{'kind=article': 1})
        counts(day, 'page.missing', **{'kind=other': 2})
        counts(day, 'machine.requests', **{'browser:page': 60, 'googlebot:page': 20 if was else 40, 'gptbot:api': 10})
        Tally.objects.create(day=day, origin='claude', calls=30 if was else 40)
        Tally.objects.create(day=day, origin='chatgpt', calls=5)
        for k in range(scale - 1):
            put(day, 'page.path', f'/ma/loi/1-{k}', 1)
            put(day, 'visit.country', f'Z{k % 10}', 6)
            put(day, 'page.shown', f'kind=k{k}', 1)
            put(day, 'tool.step', f'/topics/x/tools/t{k}:opened', 1)
            put(day, 'page.missing.path', f'/gone/{k}', 1)
            put(day, 'machine.requests', f'bot{k}:page', 1)
    put(NOW[0], 'visit.country', 'FR', 3)                     # a few readers: never their number
    put(BEFORE[0], 'visit.country', 'FR', 7)
    put(NOW[0], 'page.missing.path', '/ma/loi/9-99', 5)
    # Speeds: the article on a phone, two days of the period, the second busier.
    for day, lcp, n in ((NOW[0], 3000, 10), (NOW[1], 2000, 30), (BEFORE[0], 4500, 5)):
        counts(day, 'speed.lcp.p75', **{'article:phone': lcp})
        counts(day, 'speed.cls.p75', **{'article:phone': 120})
        counts(day, 'speed.n', **{'article:phone': n})
    counts(NOW[0], 'speed.inp.p75', **{'topic:desk': 600})
    counts(NOW[0], 'speed.n', **{'topic:desk': 4, 'topic:tablet': 9})
    counts(NOW[0], 'speed.lcp.p75', **{'topic:tablet': 900})
    # Searches: the site's and an assistant's, and what readers said.
    site = [SearchLog(query='q', folded='q', results=0 if k < 2 else 5, opened=None if k < 5 else (k % 3) + 1)
            for k in range(10)]
    site += [SearchLog(query='q', folded='q', results=5, opened=1) for _ in range(4)]
    site += [SearchLog(query='q', folded='q', results=0, via='mcp') for _ in range(3)]
    logs = SearchLog.objects.bulk_create(site)
    # auto_now_add writes the moment: the days are set after.
    for part, day in ((logs[:10], NOW[2]), (logs[10:14], BEFORE[2]), (logs[14:], NOW[3])):
        SearchLog.objects.filter(pk__in=[log.pk for log in part]).update(at=at(day))
    SearchEvent.objects.bulk_create([SearchEvent(log=logs[5], kind='found'), SearchEvent(log=logs[6], kind='not_found')])
    SearchEvent.objects.filter(log=logs[5]).update(at=at(NOW[2]))
    SearchEvent.objects.filter(log=logs[6]).update(at=at(NOW[2]))
    helped = Helped.objects.bulk_create([Helped(path='/topics/road/journeys/radar#1', helped=k < 3) for k in range(4)])
    Helped.objects.filter(pk__in=[h.pk for h in helped]).update(created_at=at(NOW[4]))
    # Out of both periods: today's and older counts are left out.
    put(TODAY, 'visits', '', 1000)
    put(BEFORE[-1] - timedelta(1), 'visits', '', 1000)


def test_a_period_is_the_last_complete_days_beside_as_many_before():
    p = report.period(7, TODAY)
    assert (p.first, p.last, p.before_first, p.before_last) == (date(2026, 11, 8), date(2026, 11, 14),
                                                                date(2026, 11, 1), date(2026, 11, 7))
    p = report.period(28, TODAY)
    assert (p.first, p.before_first, p.before_last) == (date(2026, 10, 18), date(2026, 9, 20), date(2026, 10, 17))


def test_a_change_is_in_percent_of_the_period_before_and_a_shares_in_points():
    assert report.count(120, 100) == {'now': 120, 'before': 100, 'change': 20}
    assert report.count(5, 0)['change'] is None and report.count(0, 4)['change'] == -100
    assert report.share(15, 100, 10, 100) == {'now': 15.0, 'before': 10.0, 'points': 5.0}
    assert report.share(1, 0, 1, 3) == {'now': None, 'before': 33.3, 'points': None}


def test_the_weighted_median_is_the_median_of_each_value_laid_out_weight_times():
    assert report.weighted_median([]) is None and report.weighted_median([(5, 0)]) is None
    assert report.weighted_median([(3000, 10), (2000, 30)]) == 2000
    assert report.weighted_median([(1, 1), (3, 1)]) == 2
    assert report.weighted_median([(4, 2), (1, 1), (9, 1)]) == 4          # 1 4 4 9
    assert report.weighted_median([(1, 1), (2, 1), (10, 1)]) == 2


def test_the_bands_are_web_devs():
    assert [report.band('lcp', v) for v in (2500, 2501, 4000, 4001)] == ['good', 'needs work', 'needs work', 'poor']
    assert [report.band('inp', v) for v in (200, 500, 501)] == ['good', 'needs work', 'poor']
    assert [report.band('cls', v) for v in (0.1, 0.25, 0.26)] == ['good', 'needs work', 'poor']
    assert report.band('ttfb', 800) == 'good' and report.band('lcp', None) is None


def test_a_group_of_readers_under_5_is_never_shown_by_its_number():
    rows = report.groups({'MA': (40, 30), 'FR': (3, 7), 'BE': (0, 2), 'US': (5, 4), 'DE': (1, 0)}, readers=True)
    by = {r['key']: r for r in rows}
    assert by['MA'] == {'key': 'MA', 'now': 40, 'before': 30, 'change': 33, 'share': 81.6, 'share_before': 69.8}
    assert (by['FR']['now'], by['FR']['share'], by['FR']['before'], by['FR']['change']) == (report.FEWER, report.FEWER, 7, None)
    assert (by['US']['now'], by['US']['before'], by['US']['share_before'], by['US']['change']) == (5, report.FEWER, report.FEWER, None)
    assert (by['BE']['now'], by['BE']['before']) == (0, report.FEWER)    # none is no group: 0 is said
    # The groups said FEWER come after the others, by their key alone.
    assert [r['key'] for r in rows] == ['MA', 'US', 'BE', 'DE', 'FR']
    assert not any(isinstance(v, int) and 0 < v < 5 for r in rows for k, v in r.items() if k in ('now', 'before'))
    # A list of contents shows its numbers.
    shown = report.groups({'/a': (3, 1)}, readers=False)
    assert shown == [{'key': '/a', 'now': 3, 'before': 1, 'change': 200, 'share': 100.0, 'share_before': 100.0}]


def test_the_figures_of_a_fortnight():
    a_fortnight()
    r = report.build(7, TODAY)
    assert r['period']['first'] == NOW[-1] and r['period']['last'] == NOW[0]
    come = r['come']
    assert come['readers'] == {'now': 70, 'before': 42, 'change': 67}
    assert come['visits'] == {'now': 140, 'before': 105, 'change': 33}
    # Returning: today and week, of the visits (unknown and first are not).
    assert come['returning'] == {'now': 35.0, 'before': 20.0, 'points': 15.0}
    assert come['nostore'] == {'now': 7, 'before': 7, 'change': 0}
    assert come['calls'] == {'now': 315, 'before': 245, 'change': 29}
    assert [d['day'] for d in come['days']] == sorted(NOW) and come['days'][0]['was'] == BEFORE[-1]
    assert come['days'][0]['weekday'] == 'Sun' and come['days'][0]['readers'] == {'now': 10, 'before': 6, 'change': 67}
    assert come['days'][0]['calls'] == {'now': 45, 'before': 35, 'change': 29}
    assert {g['key']: g['now'] for g in come['back']} == {'first': 84, 'today': 28, 'week': 21, 'unknown': 7}
    sources = {g['key']: g for g in r['arrive']['sources']}
    assert sources['search']['now'] == 70 and sources['search']['share'] == 52.6 and sources['direct']['now'] == 63
    assert sources['social']['now'] == 0 and sources['social']['before'] == 7
    read = r['read']
    assert read['pages'] == {'now': 350, 'before': 280, 'change': 25}
    assert read['paths'][0] == {'key': '/ma/loi/65-99/art_53', 'now': 84, 'before': 63, 'change': 33}
    assert [g['key'] for g in read['kinds']] == ['article', 'law'] and read['kinds'][1]['share'] == 40.0
    assert {g['key']: g['now'] for g in read['langs']} == {'ar': 343, 'fr': 7}
    assert {g['key']: g['now'] for g in read['screens']} == {'phone': 350}
    countries = r['where']['countries']
    assert [(g['key'], g['now'], g['before']) for g in countries] == [('MA', 126, 84), ('FR', report.FEWER, 7)]
    site, assistants = r['search']['site'], r['search']['assistants']
    assert site['searches'] == {'now': 10, 'before': 4, 'change': 150}
    assert site['empty'] == {'now': 20.0, 'before': 0.0, 'points': 20.0}
    assert site['opened'] == {'now': 50.0, 'before': 100.0, 'points': -50.0}
    assert site['rank'] == {'now': 2, 'before': 1}                        # places 3 1 2 3 1 → 2
    assert site['found']['now'] == 1 and site['not_found']['now'] == 1
    assert assistants['searches']['now'] == 3 and assistants['empty']['now'] == 100.0 and assistants['rank']['now'] is None
    tools = r['tools']
    fine = tools['tools'][0]
    assert fine['path'] == '/topics/road/tools/fine' and fine['opened'] == {'now': 28, 'before': 28, 'change': 0}
    assert fine['answered']['now'] == 21 and fine['result']['now'] == 14 and fine['finished'] == {'now': 50.0, 'before': 25.0, 'points': 25.0}
    assert [t['path'] for t in tools['tools']] == ['/topics/road/tools/fine', '/topics/work/tools/end']
    assert tools['all']['opened']['now'] == 35 and tools['all']['finished']['now'] == 40.0
    assert tools['helped'] == {'yes': {'now': 3, 'before': 0, 'change': None}, 'no': {'now': 1, 'before': 0, 'change': None}}
    phone = r['speed']['phone']
    assert [g['kind'] for g in phone] == ['article'] and phone[0]['measures'] == {'now': 40, 'before': 5, 'change': 700}
    lcp, inp, cls, ttfb = phone[0]['speeds']
    assert lcp == {'name': 'lcp', 'now': 2000, 'before': 4500, 'band': 'good'}
    assert cls == {'name': 'cls', 'now': 0.12, 'before': 0.12, 'band': 'needs work'}
    assert inp['now'] is None and ttfb['now'] is None
    desk = r['speed']['desk']
    assert desk[0]['kind'] == 'topic' and desk[0]['speeds'][1] == {'name': 'inp', 'now': 600, 'before': None, 'band': 'poor'}
    breaks = r['breaks']
    assert breaks['totals']['app_error'] == {'now': 7, 'before': 7, 'change': 0}
    assert breaks['kinds']['page_missing'][0]['key'] == 'other' and breaks['totals']['api_failed']['now'] == 0
    assert breaks['missing'] == [{'key': '/ma/loi/9-99', 'now': 5, 'before': 0, 'change': None}]
    machines = r['machines']
    assert machines['share'] == {'now': 45.5, 'before': 33.3, 'points': 12.2}
    assert [g['key'] for g in machines['families']] == ['browser', 'googlebot', 'gptbot']
    assert r['past'] is None


def test_the_counts_from_before_are_summed_whole():
    for day, n in ((date(2026, 10, 25), 3), (date(2026, 11, 15), 4)):
        put(day, 'past.pages', '', 10 * n)
        put(day, 'past.readers', '', n)
        counts(day, 'past.requests', people=20 * n, machines=50 * n)
        counts(day, 'past.country', MA=n, BE=1)
        counts(day, 'past.assistant', Claude=2 * n, curl=1)
        counts(day, 'past.tool', **{'/topics/road/tools/fine:open': n, '/topics/road/tools/fine:share': 9})
    past = report.build(7, TODAY)['past']
    assert (past['first'], past['last']) == (date(2026, 10, 25), date(2026, 11, 15))
    assert (past['pages'], past['readers'], past['people'], past['machines'], past['calls'], past['tools']) == (
        70, 7, 140, 350, 16, 7)
    assert past['countries'] == [{'key': 'MA', 'n': 7}, {'key': 'BE', 'n': report.FEWER}]
    assert past['assistants'] == [{'key': 'Claude', 'n': 14}, {'key': 'curl', 'n': 2}]


def test_the_returning_share_of_a_few_readers_is_not_said():
    for day in NOW:
        put(day, 'visits', '', 50)
    counts(NOW[0], 'page.shown.back', today=3)
    returning = report.build(7, TODAY)['come']['returning']
    assert returning['now'] == report.FEWER and returning['points'] is None


def _queries(**kwargs) -> int:
    with CaptureQueriesContext(connection) as seen:
        report.build(**kwargs)
    return len(seen.captured_queries)


def test_every_figure_costs_the_same_queries_for_a_small_fortnight_or_a_large_one():
    """Ten times the groups (pages, countries, kinds, tools, missing addresses, machines): not one query more."""
    assert _queries(days=7, today=TODAY) == report.QUERIES
    a_fortnight()
    small = _queries(days=7, today=TODAY)
    for model in (DayCount, Tally, SearchLog, Helped):
        model.objects.all().delete()
    a_fortnight(scale=10)
    assert _queries(days=7, today=TODAY) == small == report.QUERIES
    assert _queries(days=28, today=TODAY) == report.QUERIES
    r = report.build(7, TODAY)
    assert len(r['read']['paths']) == 11 and len(r['where']['countries']) == report.COUNTRIES
    assert len(r['tools']['tools']) == 11 and len(r['breaks']['missing']) == 10


def test_the_pages_most_shown_and_a_topics_pages_are_one_query_each(django_assert_num_queries):
    for day, n in ((NOW[0], 5), (NOW[6], 2), (BEFORE[0], 50), (TODAY, 70)):
        counts(day, 'page.path', **{'/a': n, '/topics/road/journeys/radar': 2 * n, '/topics/roadside': 1})
    with django_assert_num_queries(1):
        assert report.most_shown(days=7, most=2, today=TODAY) == ['/topics/road/journeys/radar', '/a']
    with django_assert_num_queries(1):
        assert report.shown_under('/topics/road/', days=7, today=TODAY) == {'/topics/road/journeys/radar': 14}
    assert report.shown_under('/topics/road/', days=28, today=TODAY) == {'/topics/road/journeys/radar': 114}
