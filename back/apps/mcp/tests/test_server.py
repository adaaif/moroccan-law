"""The MCP server over HTTP, as an assistant meets it (MC9, MC17, MC19): a real uvicorn on a free port, the SDK's own
client, in the 2025 handshake and the 2026 stateless protocol; open to everyone (MCP_AUTH 'open', since
3 Nov 2026), with a token from the site's sign-in, and with an account required."""
import json
import socket
import threading
import time
from datetime import timedelta

import anyio
import httpx2
import pytest
import uvicorn
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from apps.mcp.server import asgi, instructions
from apps.mcp.models import Tally
from apps.oauth.models import Client as OAuthClient, Day, Grant
from apps.oauth.services import tokens

pytestmark = pytest.mark.django_db(transaction=True)


WAIT = 30         # seconds, for the server to start and to stop, and for an answer: a loaded machine is slow, not wrong


@pytest.fixture
def server_url(transactional_db):
    """A test's own server, gone before its database is emptied. The server answers from a thread of its own, and the
    SDK's client may leave a request on its way as it closes: with one server for the whole file, a loaded machine
    emptied the database while such a request still read or wrote it (a deadlock on PostgreSQL). Stopping waits for
    every request the server took. Set up after the database, this is torn down before it."""
    # A free port, bound here and handed to the server, so no other process takes it in between (the server closes it).
    listening = socket.socket()
    listening.bind(('127.0.0.1', 0))
    port = listening.getsockname()[1]
    # As in production behind nginx: the caller's address from X-Forwarded-For, trusted from 127.0.0.1 only.
    server = uvicorn.Server(uvicorn.Config(asgi(), log_level='warning', lifespan='on',
                                           proxy_headers=True, forwarded_allow_ips='127.0.0.1'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listening]}, daemon=True)
    thread.start()
    until = time.monotonic() + WAIT
    while not server.started and thread.is_alive() and time.monotonic() < until:
        time.sleep(0.01)
    assert server.started, 'the MCP server did not start'
    yield f'http://127.0.0.1:{port}/mcp'
    server.should_exit = True
    thread.join(WAIT)
    assert not thread.is_alive(), 'the MCP server did not stop'


@pytest.fixture(autouse=True)
def the_clock_stands_still(monkeypatch):
    """The shares are counted by the clock's minute, hour and day (quotas._window). For the counts the clock stands
    still during a test: when the minute turned between a test's calls, the third call of a share of two passed."""
    moment, real = timezone.localtime(), timezone.localtime
    monkeypatch.setattr(timezone, 'localtime', lambda value=None, tz=None: moment if value is None else real(value, tz))


@pytest.fixture
def token(labour):
    cache.clear()
    user = get_user_model().objects.create_user(username='salma', email='salma@example.org', password='daftar-2026-x',
                                                email_proven_at=timezone.now())
    client = OAuthClient.objects.create(client_id='https://claude.ai/oauth/x', kind='cimd', name='Claude',
                                        domain='claude.ai', redirect_uris=['https://claude.ai/api/mcp/auth_callback'])
    grant = Grant.objects.create(user=user, client=client, scope='law:read', resource='http://localhost:5190/mcp')
    return tokens._pair(grant)['access_token']


def call(url, token, steps, mode='auto', forwarded='', extra=None):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    if forwarded:
        headers['X-Forwarded-For'] = forwarded
    headers.update(extra or {})

    async def go():
        async with httpx2.AsyncClient(headers=headers, timeout=WAIT) as http:
            async with Client(streamable_http_client(url, http_client=http), mode=mode) as client:
                return await steps(client)
    return anyio.run(go)


@pytest.mark.parametrize('mode', ['legacy', 'auto'])
def test_an_assistant_lists_the_tools_and_reads_an_article(server_url, token, mode):
    async def steps(client):
        listed = await client.list_tools()
        fetched = await client.call_tool('fetch', {'id': '/ma/loi/65-99/art_51'})
        run = await client.call_tool('read_articles', {'id': '/ma/loi/65-99', 'start': '50', 'count': 2})
        return client.server_instructions if hasattr(client, 'server_instructions') else None, listed, fetched, run
    _, listed, fetched, run = call(server_url, token, steps, mode)
    assert [t.name for t in listed.tools] == ['search', 'fetch', 'read_articles', 'check_references', 'get_bulletin']
    assert all(t.annotations.read_only_hint and not t.annotations.open_world_hint for t in listed.tools)
    item = json.loads(fetched.content[0].text)
    assert not fetched.is_error and item['id'] == '/ma/loi/65-99/art_51' and item['metadata']['status'] == 'in force'
    assert not run.is_error and run.structured_content['range'] == [2, 3]
    assert 'المادة 50' in run.content[0].text
    day = Day.objects.get()
    assert day.calls == 2 and day.articles == 3 and day.tools == {'fetch': 1, 'read_articles': 1}
    assert Tally.objects.get().origin == 'accounts'
    assert Grant.objects.get().used_at is not None


@pytest.mark.parametrize('mode', ['legacy', 'auto'])
def test_the_server_says_what_its_data_is(server_url, token, mode):
    async def steps(client):
        return client.instructions, client.server_info, client.protocol_version
    said, info, version = call(server_url, token, steps, mode)
    assert said == instructions() and len(said) <= 512 and said.startswith('3adala (قانون) serves Moroccan law')
    assert info.name == '3adala' and info.title == 'قانون المغرب · 3adala'
    assert [i.sizes for i in info.icons] == [['48x48'], ['192x192'], ['512x512']]
    assert all(i.src.startswith(info.website_url + '/icons/') and i.mime_type == 'image/png' for i in info.icons)
    assert version == ('2026-07-28' if mode == 'auto' else version)


def test_without_an_account_anyone_reads_the_law(server_url, labour):
    cache.clear()

    async def steps(client):
        listed = await client.list_tools()
        return listed, await client.call_tool('fetch', {'id': '/ma/loi/65-99/art_51'})
    listed, fetched = call(server_url, None, steps)
    assert all(t.meta['securitySchemes'] == [{'type': 'noauth'}] for t in listed.tools)
    assert not fetched.is_error and json.loads(fetched.content[0].text)['id'] == '/ma/loi/65-99/art_51'
    tally = Tally.objects.get()
    assert tally.origin.startswith('direct:') and tally.calls == 1 and tally.articles == 1
    assert not Day.objects.exists()                       # no connection, nothing about a person


def test_claude_and_chatgpt_users_share_their_platforms_count(server_url, labour):
    cache.clear()

    async def steps(client):
        return await client.call_tool('get_bulletin', {})
    for address in ('160.79.104.9', '160.79.111.250'):                 # Anthropic's published range
        assert not call(server_url, None, steps, forwarded=address).is_error
    assert Tally.objects.get(origin='claude').calls == 2


def rpc(url, method, params=None, *, forwarded='', token=None, meta=None, agent='python-httpx/0.28'):
    """One JSON-RPC request as a stateless client sends it, with no handshake: the share counts each one."""
    params = dict(params or {})
    if meta:
        params['_meta'] = meta
    headers = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-06-18', 'User-Agent': agent}
    if forwarded:
        headers['X-Forwarded-For'] = forwarded
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return httpx2.post(url, timeout=WAIT, headers=headers,
                       json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})


def tool(url, name, arguments=None, **kw):
    """A tool's answer: (is it an error, its first text)."""
    result = rpc(url, 'tools/call', {'name': name, 'arguments': arguments or {}}, **kw).json()['result']
    return bool(result.get('isError')), result['content'][0]['text']


def test_past_an_addresss_share_the_tool_says_to_wait(server_url, labour, settings):
    cache.clear()
    settings.MCP_ADDRESS_LIMITS = {'minute': 2, 'day': 1000, 'articles': 2000}
    results = [tool(server_url, 'get_bulletin', forwarded='203.0.113.40') for _ in range(3)]
    assert [error for error, _ in results] == [False, False, True]
    assert 'This address reached its 2 calls a minute' in results[2][1]
    # Another address, or a platform's users, are not held by it.
    assert not tool(server_url, 'get_bulletin', forwarded='203.0.113.41')[0]


def test_every_request_counts_not_only_tool_calls(server_url, labour, settings):
    """A flood of tools/list was free: now it spends the share, and past it the answer is a 429 that says when."""
    cache.clear()
    settings.MCP_ADDRESS_LIMITS = {'minute': 3, 'day': 1000, 'articles': 2000}
    assert [rpc(server_url, 'tools/list', forwarded='203.0.113.60').status_code for _ in range(3)] == [200, 200, 200]
    past = rpc(server_url, 'tools/list', forwarded='203.0.113.60')
    assert past.status_code == 429 and 1 <= int(past.headers['retry-after']) <= 60
    assert 'This address reached its 3 calls a minute' in past.json()['error']['message']
    error, text = tool(server_url, 'get_bulletin', forwarded='203.0.113.60')      # a tool says it in its answer
    assert error and 'reached its 3 calls a minute' in text


def test_a_request_that_reads_no_law_goes_on_when_the_counts_store_is_down(server_url, labour, monkeypatch):
    """The handshake and the tools' list never fail because a count could not be written."""
    from apps.mcp.services import quotas

    def down(*args, **kwargs):
        raise ConnectionError('the counts store does not answer')
    monkeypatch.setattr(quotas, 'charge', down)
    assert rpc(server_url, 'tools/list', forwarded='203.0.113.61').status_code == 200


def test_a_chatgpt_user_has_a_share_of_its_own_inside_the_platforms(server_url, labour, settings):
    """One ChatGPT user is held by its own share an hour; what it was refused spends nothing of everyone's."""
    import ipaddress
    from apps.mcp.services import origin
    cache.clear()
    settings.MCP_SUBJECT_LIMITS = {'minute': 20, 'hour': 2, 'articles': 300}
    settings.MCP_PLATFORM_LIMITS = {'minute': 600, 'hour': 4, 'articles': 10000}
    data = json.loads(origin.BUNDLED.read_text())
    chatgpt = str(next(n for n in map(ipaddress.ip_network, data['chatgpt']['prefixes'])
                       if n.version == 4 and n.num_addresses > 2)[1])
    one, other = {'openai/subject': 'v1/user-one'}, {'openai/subject': 'v1/user-two'}
    results = [tool(server_url, 'get_bulletin', forwarded=chatgpt, meta=one) for _ in range(3)]
    assert [error for error, _ in results] == [False, False, True]
    assert 'This ChatGPT account reached its 2 calls this hour' in results[2][1] and 'on the hour' in results[2][1]
    assert not tool(server_url, 'get_bulletin', forwarded=chatgpt, meta=other)[0]           # the platform's 3rd
    assert rpc(server_url, 'tools/list', forwarded=chatgpt).status_code == 200              # its 4th
    past = rpc(server_url, 'tools/list', forwarded=chatgpt)
    assert past.status_code == 429 and 'Everyone on this assistant reached its 4 calls this hour' in past.text


def test_a_token_that_no_longer_verifies_is_set_aside_not_a_dead_end(server_url, token):
    Grant.objects.update(revoked_at=timezone.now())

    async def steps(client):
        return await client.call_tool('get_bulletin', {})
    assert not call(server_url, token, steps).is_error
    assert Tally.objects.filter(origin__startswith='direct:').exists()


def test_with_an_account_required_no_token_is_a_401_pointing_at_the_metadata(server_url, token, settings):
    settings.MCP_AUTH = 'required'
    body = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}
    for header in ({}, {'Authorization': 'Bearer wrong'}):
        r = httpx2.post(server_url, timeout=WAIT, json=body, headers={'Accept': 'application/json, text/event-stream', **header})
        assert r.status_code == 401
        challenge = r.headers['www-authenticate']
        assert 'resource_metadata="http://localhost:5190/.well-known/oauth-protected-resource/mcp"' in challenge
        assert 'scope="law:read"' in challenge
    assert 'error="invalid_token"' in challenge
    preflight = httpx2.options(server_url, timeout=WAIT, headers={'Origin': 'http://localhost:6274', 'Access-Control-Request-Method': 'POST',
                                                    'Access-Control-Request-Headers': 'authorization'})
    assert preflight.status_code == 200 and preflight.headers['access-control-allow-origin'] == '*'
    Grant.objects.update(revoked_at=timezone.now())                    # a revoked connection stops at once
    r = httpx2.post(server_url, timeout=WAIT, json=body, headers={'Authorization': f'Bearer {token}',
                                                    'Accept': 'application/json, text/event-stream'})
    assert r.status_code == 401


def test_a_problem_is_an_answer_the_model_can_act_on(server_url, token):
    async def steps(client):
        return await client.call_tool('fetch', {'id': '/ma/loi/65-99/art_700'})
    result = call(server_url, token, steps)
    assert result.is_error and 'has no article 700' in result.content[0].text


def test_past_the_minutes_share_the_tool_says_to_wait(server_url, token, settings):
    settings.MCP_QUOTAS = {'minute': 2, 'day': 300, 'articles': 600}
    results = [tool(server_url, 'get_bulletin', token=token) for _ in range(3)]
    assert [error for error, _ in results] == [False, False, True]
    assert 'This account reached its 2 calls a minute' in results[2][1]


def test_past_the_days_articles_search_still_answers(server_url, token, settings):
    settings.MCP_QUOTAS = {'minute': 20, 'day': 300, 'articles': 1}

    async def steps(client):
        return [await client.call_tool('fetch', {'id': '/ma/loi/65-99/art_51'}),
                await client.call_tool('fetch', {'id': '/ma/loi/65-99/art_52'}),
                await client.call_tool('check_references', {'references': ['المادة 51 من القانون رقم 65.99']})]
    first, second, third = call(server_url, token, steps)
    assert not first.is_error and second.is_error and 'This account was given 1 articles today' in second.content[0].text
    assert not third.is_error


def test_with_an_account_required_an_expired_token_is_refused(server_url, token, settings):
    from apps.oauth.models import Token
    settings.MCP_AUTH = 'required'
    Token.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    r = httpx2.post(server_url, timeout=WAIT, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                    headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json, text/event-stream'})
    assert r.status_code == 401


def test_a_call_that_fails_still_spends_a_call_of_the_share(server_url, labour, settings):
    cache.clear()
    settings.MCP_ADDRESS_LIMITS = {'minute': 2, 'day': 1000, 'articles': 2000}
    wrong = tool(server_url, 'fetch', {'id': '/ma/loi/65-99/art_700'}, forwarded='203.0.113.50')
    fine = tool(server_url, 'get_bulletin', forwarded='203.0.113.50')
    limited = tool(server_url, 'get_bulletin', forwarded='203.0.113.50')
    assert [wrong[0], fine[0], limited[0]] == [True, False, True]
    assert 'no article' in wrong[1].lower() and 'reached its 2 calls a minute' in limited[1]
