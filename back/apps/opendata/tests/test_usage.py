"""What an access uses (apps/opendata/services/usage.py): three limits per access and Morocco's day, shared by its keys
and its doors; counted in the counters store and copied into AccessDay at most once a minute."""
from datetime import date, datetime, timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.opendata.models import AccessDay, ApiKey
from apps.opendata.services import keys, usage
from apps.opendata.tests.helpers import keyed

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def clock(monkeypatch):
    """Morocco's time standing at 10:00:30 on 16 Nov 2026 until a test moves it (`clock['at'] = …`)."""
    now = {'at': datetime(2026, 11, 16, 10, 0, 30, tzinfo=timezone.get_current_timezone())}
    real = timezone.localtime
    monkeypatch.setattr(timezone, 'localtime', lambda value=None, tz=None: now['at'] if value is None else real(value, tz))
    return now


def held(**limits):
    """A partner's access with its own numbers, and the holder its key opens."""
    access, key = keyed(size='partner', **limits)
    return access, keys.read(key)


def test_the_minute_holds_the_access_and_a_refusal_counts_nothing(clock):
    access, holder = held(minute=2)
    usage.charge(holder, 'v1.search')
    usage.charge(holder, 'site')
    with pytest.raises(usage.Limit) as past:
        usage.charge(holder, 'mcp')
    assert (past.value.code, past.value.retry) == ('minute', 30)
    assert usage.today(access.pk) == {'calls': 2, 'articles': 0}
    clock['at'] += timedelta(minutes=1)
    usage.charge(holder, 'mcp')
    assert usage.today(access.pk)['calls'] == 3


def test_the_days_calls_hold_until_moroccos_midnight(clock):
    access, holder = held(calls=2)
    for _ in range(2):
        usage.charge(holder, 'site')
        clock['at'] += timedelta(minutes=1)
    with pytest.raises(usage.Limit) as past:
        usage.charge(holder, 'v1.changes')
    assert past.value.code == 'calls' and past.value.retry == 24 * 3600 - (10 * 3600 + 2 * 60 + 30)   # to midnight
    clock['at'] = datetime(2026, 11, 17, 0, 0, 1, tzinfo=clock['at'].tzinfo)
    usage.charge(holder, 'v1.changes')
    assert usage.today(access.pk)['calls'] == 1


def test_once_the_days_articles_are_spent_only_the_doors_that_give_the_law_are_refused(clock):
    access, holder = held(articles=5)
    usage.charge(holder, 'v1.articles', 3)        # counted when the call knows it before
    usage.charge(holder, 'v1.text')
    usage.spend(holder, 2)                        # or after
    assert usage.reached(holder) and usage.today(access.pk) == {'calls': 2, 'articles': 5}
    for door in ('v1.text', 'v1.articles'):
        with pytest.raises(usage.Limit) as past:
            usage.charge(holder, door)
        assert past.value.code == 'articles'
    with pytest.raises(usage.Limit):
        usage.charge(holder, 'mcp', bodies=True)      # the assistants' server says per tool
    for door in ('v1.search', 'v1.references', 'v1.bulletin', 'site', 'mcp'):
        usage.charge(holder, door)                    # a search, a list, the references still answer
    usage.spend(holder, 0)
    assert usage.today(access.pk) == {'calls': 7, 'articles': 5}


def test_two_keys_of_one_access_share_its_limits(clock):
    access, first = held(minute=3)
    second = keys.read(ApiKey.issue(access, 'the new server')[1])
    assert second.key != first.key and second.access == first.access
    usage.charge(first, 'site')
    usage.charge(second, 'v1.search')
    usage.charge(first, 'mcp')
    with pytest.raises(usage.Limit):
        usage.charge(second, 'site')
    # Another access is not held by it.
    _, other = keyed(username='other', size='partner', minute=3)
    usage.charge(keys.read(other), 'site')


def test_a_door_is_one_of_the_named_ones(clock):
    _, holder = held()
    with pytest.raises(ValueError, match='no such door'):
        usage.charge(holder, 'v1.texts')


def test_the_headers_say_the_policy_and_what_is_left(clock):
    _, holder = held(minute=120, calls=20000)
    for _ in range(3):
        usage.charge(holder, 'site')
    said = usage.headers(holder)
    assert said['RateLimit-Policy'] == '"minute";q=120;w=60, "day";q=20000;w=86400'
    assert said['RateLimit'] == f'"minute";r=117;t=30, "day";r=19997;t={14 * 3600 - 30}'


def test_a_busy_access_writes_its_day_once_a_minute_and_its_keys_day_once_a_day(clock, django_assert_num_queries):
    access, holder = held()
    usage.charge(holder, 'site')
    row = AccessDay.objects.get()
    assert (row.day, row.calls, row.doors) == (date(2026, 11, 16), 1, {'site': 1})
    assert ApiKey.objects.get().last_used_on == date(2026, 11, 16)
    with django_assert_num_queries(0):            # the same minute: counted, nothing written
        usage.charge(holder, 'v1.articles', 4)
        usage.charge(holder, 'mcp')
        usage.spend(holder, 2)
    clock['at'] += timedelta(minutes=1)
    with django_assert_num_queries(1):            # the next minute: the day's totals, one upsert
        usage.charge(holder, 'site')
    row.refresh_from_db()
    assert (row.calls, row.articles, row.doors) == (4, 6, {'site': 2, 'v1.articles': 1, 'mcp': 1})
    usage.fold(access.pk, [date(2026, 11, 16)])   # said twice, changes nothing
    row.refresh_from_db()
    assert row.calls == 4 and AccessDay.objects.count() == 1


def test_a_days_last_minute_is_copied_on_the_next_days_first_call(clock):
    _, holder = held()
    clock['at'] = clock['at'].replace(hour=23, minute=59, second=10)
    usage.charge(holder, 'site')
    usage.charge(holder, 'site')                  # the same minute: not copied yet
    usage.spend(holder, 7)
    assert AccessDay.objects.get().calls == 1
    clock['at'] = datetime(2026, 11, 17, 0, 0, 5, tzinfo=clock['at'].tzinfo)
    usage.charge(holder, 'mcp')
    days = {r.day: (r.calls, r.articles, r.doors) for r in AccessDay.objects.all()}
    assert days == {date(2026, 11, 16): (2, 7, {'site': 2}), date(2026, 11, 17): (1, 0, {'mcp': 1})}
    assert ApiKey.objects.get().last_used_on == date(2026, 11, 17)


def test_the_last_thirty_days_oldest_first_today_as_counted_now(clock, django_assert_num_queries):
    access, holder = held()
    today = date(2026, 11, 16)
    AccessDay.objects.bulk_create([
        AccessDay(access=access, day=today - timedelta(days=40), calls=9, articles=9),    # past the window
        AccessDay(access=access, day=today - timedelta(days=12), calls=5, articles=1),
        AccessDay(access=access, day=today - timedelta(days=3), calls=0, articles=0),     # no use: left out
        AccessDay(access=access, day=today - timedelta(days=1), calls=2, articles=0),
    ])
    usage.charge(holder, 'site')
    usage.spend(holder, 3)                        # after the copy: not in AccessDay yet
    with django_assert_num_queries(1):
        days = usage.days(access.pk)
    assert days == [{'day': '2026-11-04', 'calls': 5, 'articles': 1}, {'day': '2026-11-15', 'calls': 2, 'articles': 0},
                    {'day': '2026-11-16', 'calls': 1, 'articles': 3}]
    assert usage.days(access.pk, n=1) == [{'day': '2026-11-16', 'calls': 1, 'articles': 3}]


def test_a_call_is_not_failed_when_its_accesss_row_is_gone_while_its_key_is_remembered(clock, monkeypatch):
    # An account removed outright takes its access's rows with it, while a key of it is still remembered for a minute.
    # The database then refuses the day's row (it names an access that is no more): the call is not failed for it.
    from django.db import IntegrityError

    _, key = keyed()
    held = keys.read(key)
    usage.charge(held, 'v1.search')

    def gone(*args, **kwargs):
        raise IntegrityError('insert or update on table "opendata_access_day" violates foreign key constraint')
    monkeypatch.setattr(AccessDay.objects, 'bulk_create', gone)
    clock['at'] += timedelta(minutes=1)
    usage.charge(held, 'v1.search')                 # the minute's copy is refused: nothing is raised
    assert usage.today(held.access)['calls'] == 2


def test_a_call_refused_for_a_limit_is_counted_by_limit_and_copied_into_the_day(clock):
    access, holder = held(minute=1, articles=2)
    usage.charge(holder, 'v1.articles', 2)
    for door in ('site', 'mcp'):
        with pytest.raises(usage.Limit):
            usage.charge(holder, door)                # past its minute: refused, counted
    clock['at'] += timedelta(minutes=1)
    with pytest.raises(usage.Limit) as past:
        usage.charge(holder, 'v1.text')               # past its articles
    assert past.value.code == 'articles'
    row = AccessDay.objects.get()
    assert (row.calls, row.limits) == (1, {'minute': 2, 'articles': 1})      # copied on the refusal's minute
    assert usage.today(access.pk) == {'calls': 1, 'articles': 2}               # a refusal is no call
    assert usage.limited([access.pk]) == {access.pk: {'minute': 2, 'calls': 0, 'articles': 1}}


def test_limited_today_is_read_in_one_call_for_every_access(clock, monkeypatch):
    first, one = held(minute=1)
    second, _ = keyed(username='other', size='partner')
    usage.charge(one, 'site')
    with pytest.raises(usage.Limit):
        usage.charge(one, 'site')
    from config.caching import counters
    calls = []
    real = counters.get_many
    monkeypatch.setattr(type(counters), 'get_many', lambda self, keys: calls.append(keys) or real(keys), raising=False)
    assert usage.limited([first.pk, second.pk]) == {first.pk: {'minute': 1, 'calls': 0, 'articles': 0}}
    assert len(calls) == 1
    clock['at'] = datetime(2026, 11, 17, 9, 0, tzinfo=clock['at'].tzinfo)
    assert usage.limited([first.pk]) == {}                    # a new day, nothing refused yet


def test_the_day_of_reading_counts_a_key_it_refuses_for_its_articles(clock, rf):
    from apps.corpus.services import reading

    access, key = keyed(size='partner', articles=1)
    holder = keys.read(key)
    usage.charge(holder, 'site', 1)
    request = rf.get('/api/corpus/at/ma/loi/70-03/', HTTP_X_API_KEY=key)
    answer = reading.refused(request)
    assert answer.status_code == 429
    assert usage.limited([access.pk]) == {access.pk: {'minute': 0, 'calls': 0, 'articles': 1}}
    with pytest.raises(ValueError, match='no such limit'):
        usage.refuse(holder, 'hours')


def test_the_assistants_server_counts_a_key_it_refuses(clock):
    from apps.mcp.services import quotas

    access, holder = held(calls=1)
    caller = quotas.Caller('key', str(access.pk), 'keys', holder=holder)
    quotas.charge(caller)
    with pytest.raises(quotas.Limit):
        quotas.charge(caller)
    assert usage.limited([access.pk])[access.pk]['calls'] == 1


def test_the_live_counts_of_an_access(clock):
    access, holder = held()
    usage.charge(holder, 'v1.search')
    assert usage.live(access.pk, [date(2026, 11, 16), date(2026, 11, 15)]) == {
        date(2026, 11, 16): {'calls': 1, 'articles': 0, 'doors': {'v1.search': 1}, 'limits': {}}}
