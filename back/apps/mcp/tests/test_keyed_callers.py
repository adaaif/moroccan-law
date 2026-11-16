"""A direct caller with a key (X-Api-Key) on the assistants' server: counted on its access's limits and day (door
`mcp`) in place of its address's share; a key that opens nothing is a 401, one while the keyed API is closed or whose
access has no API a 403. The platforms' users and the callers without a key are untouched."""
import re

import httpx2
import pytest
from django.core.cache import cache

from apps.mcp.models import Tally
from apps.mcp.tests.test_server import WAIT, server_url, the_clock_stands_still, token  # noqa: F401  (fixtures)
from apps.opendata.models import ApiKey
from apps.opendata.services import usage
from apps.opendata.tests.helpers import keyed

pytestmark = pytest.mark.django_db(transaction=True)
HEADERS = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-06-18',
           'User-Agent': 'python-httpx/0.28'}


def post(url, method, params=None, *, key='', forwarded='203.0.113.70', token=''):
    headers = {**HEADERS, 'X-Forwarded-For': forwarded}
    if key:
        headers['X-Api-Key'] = key
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return httpx2.post(url, timeout=WAIT, headers=headers,
                       json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})


def tool(url, name, arguments=None, **kw):
    response = post(url, 'tools/call', {'name': name, 'arguments': arguments or {}}, **kw)
    result = response.json()['result']
    return response, bool(result.get('isError')), result['content'][0]['text']


@pytest.fixture(autouse=True)
def fresh(settings):
    settings.OPEN_DATA = 'request'
    cache.clear()
    yield
    cache.clear()


def test_a_key_is_counted_on_its_access_not_its_address(server_url, labour, settings):
    settings.MCP_ADDRESS_LIMITS = {'minute': 1, 'day': 1000, 'articles': 2000}
    access, key = keyed(size='partner', minute=3)
    second = ApiKey.issue(access, 'second')[1]
    answered, error, _ = tool(server_url, 'fetch', {'id': '/ma/loi/65-99/art_51'}, key=key)
    assert not error
    assert answered.headers['ratelimit-policy'] == '"minute";q=3;w=60, "day";q=20000;w=86400'
    assert re.fullmatch(r'"minute";r=2;t=\d+, "day";r=19999;t=\d+', answered.headers['ratelimit'])
    assert post(server_url, 'tools/list', key=second).status_code == 200      # a request that is no tool call counts too
    assert not tool(server_url, 'get_bulletin', key=key)[1]
    _, error, said = tool(server_url, 'get_bulletin', key=second)
    assert error and "This key's access reached its 3 calls a minute" in said
    past = post(server_url, 'tools/list', key=key)
    assert past.status_code == 429 and 1 <= int(past.headers['retry-after']) <= 60 and 'ratelimit' in past.headers
    assert usage.today(access.pk) == {'calls': 3, 'articles': 1}
    assert Tally.objects.get(origin='keys').calls == 2
    # The address's own share is untouched by the key's calls.
    assert not tool(server_url, 'get_bulletin')[1]
    assert tool(server_url, 'get_bulletin')[1]


def test_a_key_past_its_articles_still_searches(server_url, labour):
    _, key = keyed(size='partner', articles=1)
    assert not tool(server_url, 'fetch', {'id': '/ma/loi/65-99/art_51'}, key=key)[1]
    _, error, said = tool(server_url, 'read_articles', {'id': '/ma/loi/65-99', 'count': 2}, key=key)
    assert error and "This key's access was given 1 articles today" in said
    assert not tool(server_url, 'get_bulletin', key=key)[1]


def test_a_key_that_opens_nothing_is_refused(server_url, labour, settings):
    access, key = keyed()
    _, data_only = keyed(username='reader', api=False, data=True)
    for sent, expected in (('law_wrong', (401, 'key', 'invalid')), (data_only, (403, 'access', 'no_api'))):
        r = post(server_url, 'tools/list', key=sent)
        assert (r.status_code, r.json()['errors'][0]['field'], r.json()['errors'][0]['code']) == expected
        assert 'www-authenticate' not in r.headers          # never an invitation to the assistants' sign-in
    settings.OPEN_DATA = 'closed'
    r = post(server_url, 'tools/call', {'name': 'get_bulletin', 'arguments': {}}, key=key)
    assert (r.status_code, r.json()) == (403, {'errors': [{'field': 'access', 'code': 'closed'}]})
    assert not usage.today(access.pk)['calls']


def test_past_its_calls_today_a_key_is_told_when_its_day_starts_again():
    from apps.mcp.services import quotas
    from apps.opendata.services import keys
    access, key = keyed(size='partner', calls=1)
    caller = quotas.Caller('key', str(access.pk), 'keys', holder=keys.read(key))
    quotas.charge(caller)
    with pytest.raises(quotas.Limit) as past:
        quotas.charge(caller, bodies=True)
    assert "This key's access reached its 1 calls today" in str(past.value) and 'midnight, Morocco time' in str(past.value)
    assert past.value.retry >= 1


def test_the_platforms_users_and_the_accounts_are_untouched_by_a_key(server_url, token):
    for sent in ('law_wrong', keyed(username='holder2')[1]):
        assert not tool(server_url, 'get_bulletin', key=sent, forwarded='160.79.104.9')[1]     # Anthropic's range
        assert not tool(server_url, 'get_bulletin', key=sent, token=token)[1]
    assert Tally.objects.get(origin='claude').calls == 2 and Tally.objects.get(origin='accounts').calls == 2
    assert not Tally.objects.filter(origin='keys').exists()
