"""What a key opens (apps/opendata/services/keys.py, apps/opendata/middleware.py): one lookup a request, kept a minute;
a key that opens nothing refused on every door of the site; its access's limits and headers; its answers never
public."""
import re
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.opendata.models import Access, AccessDay, ApiKey, new_key, well_formed
from apps.opendata.services import keys, usage
from apps.opendata.tests.helpers import keyed

pytestmark = pytest.mark.django_db
READER = {'HTTP_X_FORWARDED_FOR': '41.92.1.2', 'HTTP_CF_CONNECTING_IP': '41.92.1.2'}


@pytest.fixture(autouse=True)
def fresh(settings):
    settings.OPEN_DATA = 'request'
    cache.clear()
    yield
    cache.clear()


def get(api, path, key, **extra):
    return api.get(path, HTTP_X_API_KEY=key, **READER, **extra)


def error(response) -> tuple:
    return response.status_code, response.json()['errors'][0]['field'], response.json()['errors'][0]['code']


# ── One lookup, kept a minute ────────────────────────────────────────────────────────────────────────────────────

def test_a_key_is_looked_up_once_and_kept_a_minute_refusals_too(django_assert_num_queries):
    access, key = keyed()
    with django_assert_num_queries(1):
        held = keys.read(key)
    with django_assert_num_queries(0):
        assert keys.read(key) == held
    assert (held.access, held.api, held.minute, held.calls, held.articles) == (access.pk, True, 120, 20000, 10000)
    # A wrong key with a key's shape is refused from what was kept: it cannot be used to hammer the database.
    wrong = new_key()
    for expected in (1, 0):
        with django_assert_num_queries(expected), pytest.raises(keys.Refused) as refused:
            keys.read(wrong)
        assert refused.value.code == 'invalid'
    # One without a key's shape or checksum never reaches the database.
    with django_assert_num_queries(0), pytest.raises(keys.Refused):
        keys.read(key[:-1] + ('A' if key[-1] != 'A' else 'B'))
    assert not well_formed('law_short')


def test_a_warm_keyed_request_asks_the_database_nothing_about_its_key(api):
    _, key = keyed()
    assert get(api, '/api/corpus/issues/', key).status_code == 200     # warm: kept, the day's first writes done
    with CaptureQueriesContext(connection) as asked:
        assert get(api, '/api/corpus/issues/', key).status_code == 200
    assert not [q['sql'] for q in asked.captured_queries if 'opendata_' in q['sql']]


def test_a_request_asks_its_key_once_whatever_asks_it(api, rf):
    _, key = keyed()
    request = rf.get('/', HTTP_X_API_KEY=key)
    held = keys.holder(request)
    cache.clear()
    assert keys.holder(request) is held               # the second door is answered from the request
    assert keys.holder(rf.get('/')) is None
    refused = rf.get('/', HTTP_X_API_KEY='law_wrong')
    for _ in range(2):
        with pytest.raises(keys.Refused):
            keys.holder(refused)
    # The key is read from the header only, never from the address.
    assert keys.holder(rf.get('/', {'key': key, 'X-Api-Key': key})) is None


def test_ending_a_key_or_its_access_stops_it_at_once(api):
    access, key = keyed()
    assert get(api, '/api/corpus/issues/', key).status_code == 200
    keys.end(ApiKey.objects.get())
    assert error(get(api, '/api/corpus/issues/', key)) == (401, 'key', 'ended')
    # An access ended: its state, then each of its keys ended (what the access's end does).
    other = ApiKey.issue(access, 'second')[1]
    assert get(api, '/api/corpus/issues/', other).status_code == 200
    Access.objects.filter(pk=access.pk).update(state=Access.State.ENDED)
    for row in access.keys.filter(ended_at__isnull=True):
        keys.end(row)
    assert error(get(api, '/api/corpus/issues/', other)) == (401, 'key', 'ended')


def test_an_access_past_its_end_date_is_refused_at_midnight_whatever_was_kept(api, monkeypatch):
    _, key = keyed(days=0)
    assert get(api, '/api/corpus/issues/', key).status_code == 200
    tomorrow = timezone.localdate() + timedelta(days=1)
    monkeypatch.setattr(timezone, 'localdate', lambda value=None, tz=None: tomorrow)
    assert error(get(api, '/api/corpus/issues/', key)) == (401, 'key', 'expired')
    monkeypatch.undo()
    _, late = keyed(username='late', days=-1)
    assert error(get(api, '/api/corpus/issues/', late)) == (401, 'key', 'expired')


# ── Refused on every door ────────────────────────────────────────────────────────────────────────────────────────

DOORS = ('/api/corpus/issues/', '/api/corpus/shelf/', '/api/corpus/at/ma/loi/12-26/', '/api/search/?q=شغل',
         '/api/topics/', '/api/budget/2026/', '/api/explain/?path=/ma/loi/12-26/art_1', '/api/sources/pages/1/',
         '/api/discussion/?path=/ma/loi/12-26/art_1', '/api/places/', '/api/blog/', '/ma/loi/12-26', '/bo/general_ar/1')


@pytest.mark.parametrize('path', DOORS)
def test_a_key_that_opens_nothing_is_refused_on_every_door_of_the_site(api, path):
    access = keyed()[0]
    ended = ApiKey.issue(access, 'old')
    keys.end(ended[0])
    for sent, code in ((new_key(), 'invalid'), ('not a key', 'invalid'), (ended[1], 'ended')):
        r = get(api, path, sent)
        assert (r.status_code, r.json()) == (401, {'errors': [{'field': 'key', 'code': code}]})
        assert r['Cache-Control'] == 'no-store' and 'X-Api-Key' in r['Vary']


def test_the_doors_with_rules_of_their_own_are_left_to_them(api):
    """The edition and the versioned API read their keys themselves (the account's own pages: test_keys_api.py)."""
    assert api.get('/api/open/about/', HTTP_X_API_KEY='law_wrong').status_code == 200
    assert api.get('/api/v1/', HTTP_X_API_KEY='law_wrong').status_code == 404


def test_while_closed_any_key_is_refused_and_a_key_without_the_api_too(api, settings):
    _, key = keyed()
    _, data_only = keyed(username='reader', api=False, data=True)
    assert error(get(api, '/api/corpus/issues/', data_only)) == (403, 'access', 'no_api')
    settings.OPEN_DATA = 'closed'
    assert error(get(api, '/api/corpus/issues/', key)) == (403, 'access', 'closed')


def test_without_a_key_nothing_changes(api):
    r = api.get('/api/corpus/issues/', **READER)
    assert r.status_code == 200 and r['Cache-Control'].startswith('public, ')
    assert not r.has_header('RateLimit') and 'X-Api-Key' not in r.get('Vary', '')
    assert not usage.today(1)['calls'] and not AccessDay.objects.exists()


# ── Its limits and headers; never public ─────────────────────────────────────────────────────────────────────────

def test_a_keyed_answer_says_its_limits_and_is_private_on_the_site_and_the_edition(api):
    access, key = keyed(size='try')
    r = get(api, '/api/corpus/issues/', key)
    assert r.status_code == 200
    assert r['Cache-Control'] == 'private, max-age=60, stale-while-revalidate=600'
    assert 'X-Api-Key' in r['Vary']
    assert r['RateLimit-Policy'] == '"minute";q=30;w=60, "day";q=1000;w=86400'
    assert re.fullmatch(r'"minute";r=29;t=\d+, "day";r=999;t=\d+', r['RateLimit'])
    # A view that says public itself is made private too; the edition's answers as well.
    picture = get(api, '/api/blog/', key)
    assert 'public' not in picture['Cache-Control'] and picture['Cache-Control'].startswith('private')
    opened = get(api, '/api/open/about/', key)
    assert opened.status_code == 200 and opened['Cache-Control'].startswith('private')
    assert 'X-Api-Key' in opened['Vary']
    assert usage.today(access.pk)['calls'] == 2         # the edition counts its own downloads


def test_a_keyed_call_is_counted_on_its_access_not_its_address(api, settings):
    settings.PUBLIC_API_RATES = {'anonymous': '1/min'}
    access, key = keyed(size='partner', minute=3, calls=4)
    second = ApiKey.issue(access, 'second')[1]
    assert [get(api, '/api/corpus/issues/', k).status_code for k in (key, second, key)] == [200] * 3
    past = get(api, '/api/corpus/issues/', second)
    assert error(past) == (429, 'key', 'minute') and 1 <= int(past['Retry-After']) <= 60
    assert past['RateLimit'].startswith('"minute";r=0;')
    # The address's own allowance was not spent by the key.
    assert api.get('/api/corpus/issues/', **READER).status_code == 200
    assert api.get('/api/corpus/issues/', **READER).status_code == 429


def test_past_its_calls_today_a_key_waits_until_midnight(api):
    access, key = keyed(size='partner', calls=1)
    assert get(api, '/api/corpus/issues/', key).status_code == 200
    past = get(api, '/api/corpus/issues/', key)
    assert error(past) == (429, 'key', 'calls') and int(past['Retry-After']) >= 1
    assert '"day";r=0;' in past['RateLimit']
    assert usage.today(access.pk)['calls'] == 1          # a call refused counts nothing


def test_a_keys_use_is_written_cheaply_and_holds_no_question_and_no_address(api):
    access, key = keyed()
    for _ in range(3):
        get(api, '/api/corpus/issues/', key)
    usage.fold(access.pk, [timezone.localdate()])
    row = AccessDay.objects.get()
    assert (row.calls, row.doors) == (3, {'site': 3})
    assert set(row.__dict__) - {'_state'} == {'id', 'access_id', 'day', 'calls', 'articles', 'doors', 'limits'}
    assert ApiKey.objects.get().last_used_on == timezone.localdate()
