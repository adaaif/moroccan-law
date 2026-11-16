"""An account's own keys (/api/access/keys/): made by the holder of a usable access, shown once, at most ACCESS_KEYS
live, ended at once; their use shown to the holder in a fixed number of queries."""
from datetime import date, timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.discussion.tests.conftest import make_user, signed_in
from apps.opendata.models import AccessDay, ApiKey, well_formed
from apps.opendata.tests.helpers import accepted, keyed
from apps.opendata.tests.test_keys import READER, error, get

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh(settings):
    settings.OPEN_DATA = 'request'
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def holder(api):
    access = accepted()
    return signed_in(api, access.user), access


def test_the_keys_pages_read_the_accounts_sign_in_not_a_key(holder):
    api, _ = holder
    assert api.get('/api/access/keys/', HTTP_X_API_KEY='law_wrong').status_code == 200


def test_no_access_no_keys(api):
    assert api.get('/api/access/keys/').status_code == 401
    signed_in(api, make_user('nobody'))
    for r in (api.get('/api/access/keys/'), api.post('/api/access/keys/', {'name': 'x'}, format='json')):
        assert error(r) == (403, 'access', 'none')
    ended = accepted(username='was', days=-1)
    signed_in(api, ended.user)
    assert error(api.get('/api/access/keys/')) == (403, 'access', 'none')


def test_a_key_is_shown_once_and_its_holder_sees_its_use(holder, caplog):
    api, _ = holder
    caplog.set_level('DEBUG')
    made = api.post('/api/access/keys/', {'name': '  the server  '}, format='json')
    assert made.status_code == 201 and made['Cache-Control'] == 'no-store'
    body = made.json()
    key = body['key']
    assert well_formed(key) and body['name'] == 'the server' and body['prefix'] == key[:12]
    assert key not in caplog.text
    # Used once from a server.
    assert api.get('/api/corpus/issues/', HTTP_X_API_KEY=key, **READER).status_code == 200
    shown = api.get('/api/access/keys/')
    assert shown.status_code == 200 and key not in shown.content.decode()
    data = shown.json()
    assert data['keys'] == [{'id': body['id'], 'name': 'the server', 'prefix': key[:12],
                             'created_at': data['keys'][0]['created_at'], 'last_used_on': str(timezone.localdate())}]
    assert data['limits'] == {'minute': 120, 'calls': 20000, 'articles': 10000}
    assert data['today'] == {'calls': 1, 'articles': 0}
    assert data['days'] == [{'day': str(timezone.localdate()), 'calls': 1, 'articles': 0}]


def test_at_most_two_live_keys_and_ending_one_frees_its_place(holder):
    api, _ = holder
    made = [api.post('/api/access/keys/', {}, format='json') for _ in range(2)]
    assert [r.status_code for r in made] == [201, 201]
    assert error(api.post('/api/access/keys/', {'name': 'third'}, format='json')) == (409, 'keys', 'full')
    first = made[0].json()
    assert api.delete(f'/api/access/keys/{first["id"]}/').status_code == 204
    assert error(get(api, '/api/corpus/issues/', first['key'])) == (401, 'key', 'ended')
    assert [k['id'] for k in api.get('/api/access/keys/').json()['keys']] == [made[1].json()['id']]
    assert api.post('/api/access/keys/', {'name': 'third'}, format='json').status_code == 201
    # A key ended, someone else's, or none at all: not found.
    other = keyed(username='other')[0].keys.get()
    for pk in (first['id'], other.pk, 999999, 2**70):
        assert error(api.delete(f'/api/access/keys/{pk}/')) == (404, 'key', 'not_found')


def test_a_keys_name_is_words_of_sixty_at_most(holder):
    api, _ = holder
    assert error(api.post('/api/access/keys/', {'name': 'x' * 61}, format='json')) == (400, 'name', 'too_long')
    assert error(api.post('/api/access/keys/', {'name': ['x']}, format='json')) == (400, 'name', 'invalid')
    assert api.post('/api/access/keys/', {'name': 'x' * 60}, format='json').status_code == 201


def test_the_keys_page_asks_a_fixed_number_of_queries(holder, django_assert_max_num_queries):
    api, access = holder
    with django_assert_max_num_queries(4):
        assert api.get('/api/access/keys/').status_code == 200
    ApiKey.issue(access, 'one')
    ApiKey.issue(access, 'two')
    today = timezone.localdate()
    AccessDay.objects.bulk_create([AccessDay(access=access, day=today - timedelta(days=k), calls=k + 1)
                                   for k in range(30)])
    with django_assert_max_num_queries(4):
        data = api.get('/api/access/keys/').json()
    assert len(data['keys']) == 2 and len(data['days']) == 30 and data['days'][0]['day'] < data['days'][-1]['day']
    assert date.fromisoformat(data['days'][-1]['day']) == today
