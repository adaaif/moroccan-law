"""The gate in front of the tools (MC19): what it reads of a request to count it against the caller's share. A tool
call is counted by its tool; anything else (a DELETE, a notification, a body that is no call, a batch led by anything
but a tool call, a body past the CAP bytes the gate reads) is counted by the gate. ChatGPT's `openai/subject` gives a
share of its own only from ChatGPT's ranges. An account past its minute, ChatGPT's hints in part, a body that arrives in
pieces; with an account required, each tool says so to ChatGPT."""
import json

import anyio
import httpx2
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from apps.mcp.models import Tally
from apps.mcp.server import CAP, asgi, build
from apps.mcp.tests.test_server import WAIT, rpc, server_url, the_clock_stands_still  # noqa: F401  (fixtures)
from apps.oauth.models import Client as OAuthClient, Grant
from apps.oauth.services import tokens

HEADERS = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-06-18',
           'User-Agent': 'python-httpx/0.28'}


def post(url, body: bytes, forwarded: str):
    return httpx2.post(url, timeout=WAIT, content=body, headers={**HEADERS, 'Content-Type': 'application/json',
                                                                 'X-Forwarded-For': forwarded})


def body(pad: int, meta: dict | None = None) -> bytes:
    """A call to get_bulletin, its `_meta` padded with `pad` bytes."""
    return json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                       'params': {'name': 'get_bulletin', 'arguments': {}, '_meta': {**(meta or {}), 'pad': 'x' * pad}}}).encode()


def sized(size: int, meta: dict | None = None) -> bytes:
    """That call, exactly `size` bytes long."""
    made = body(size - len(body(0, meta)), meta)
    assert len(made) == size
    return made


def answered(response) -> bool:
    """A tool's answer that is no error."""
    return response.status_code == 200 and not response.json()['result'].get('isError')


def chatgpt_address() -> str:
    import ipaddress

    from apps.mcp.services import origin
    data = json.loads(origin.BUNDLED.read_text())
    net = next(n for n in map(ipaddress.ip_network, data['chatgpt']['prefixes']) if n.version == 4 and n.num_addresses > 2)
    return str(net[1])


@pytest.fixture
def reader_token(labour):
    cache.clear()
    user = get_user_model().objects.create_user(username='reader', email='reader@example.org', password='daftar-2026-x',
                                                email_proven_at=timezone.now())
    client = OAuthClient.objects.create(client_id='https://claude.ai/oauth/x', kind='cimd', name='Claude',
                                        domain='claude.ai', redirect_uris=['https://claude.ai/api/mcp/auth_callback'])
    grant = Grant.objects.create(user=user, client=client, scope='law:read', resource='http://localhost:5190/mcp')
    return tokens._pair(grant)['access_token']


def test_each_request_is_counted_and_answered_whole(server_url, reader_token, settings):
    settings.MCP_ADDRESS_LIMITS = {'minute': 1, 'day': 1000, 'articles': 2000}
    settings.MCP_QUOTAS = {'minute': 1, 'day': 300, 'articles': 600}
    # A body longer than the gate reads (64 KB; nginx lets 256 KB through) is answered whole.
    padded = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {'_meta': {'pad': 'x' * 300_000}}}
    long = post(server_url, json.dumps(padded).encode(), '203.0.113.90')
    assert long.status_code == 200 and len(long.json()['result']['tools']) == 5
    # A request with no body counts too (a DELETE: no session to end here): the same address's next one is past its minute.
    ended = httpx2.delete(server_url, timeout=WAIT, headers={**HEADERS, 'X-Forwarded-For': '203.0.113.91'})
    past = rpc(server_url, 'tools/list', forwarded='203.0.113.91')
    assert ended.status_code == 405 and past.status_code == 429
    told = post(server_url, b'{"jsonrpc": "2.0", "method": "notifications/initialized"}', '203.0.113.93')
    assert told.status_code == 202 and told.content == b''
    # JSON that is no call is counted too, and the SDK refuses it.
    odd = post(server_url, b'"tools/call"', '203.0.113.95')
    assert odd.status_code == 400 and rpc(server_url, 'tools/list', forwarded='203.0.113.95').status_code == 429
    # An account past its minute: the 429 names it.
    first, second = (rpc(server_url, 'tools/list', token=reader_token, forwarded='203.0.113.94') for _ in range(2))
    assert first.status_code == 200 and second.status_code == 429
    assert 'This account reached its 1 calls a minute' in second.json()['error']['message']
    # ChatGPT's hints in part: a country that is no ISO code, no timezone, no user, no conversation; then a locale alone.
    chatgpt = chatgpt_address()
    for meta in ({'openai/userLocation': {'country': 'MAR', 'city': 'Fès', 'region': 'Fès-Meknès'}},
                 {'openai/locale': 'ar-MA'}):
        assert rpc(server_url, 'tools/call', {'name': 'get_bulletin', 'arguments': {}}, forwarded=chatgpt,
                   meta=meta).status_code == 200


def test_a_tool_call_past_what_the_gate_reads_is_counted_there_as_no_tool_call(server_url, labour, settings):
    cache.clear()
    settings.MCP_ADDRESS_LIMITS = {'minute': 2, 'day': 1000, 'articles': 2000}
    # CAP bytes, read: a tool call, counted once, by its tool; the address's next request is its second.
    assert answered(post(server_url, sized(CAP), '203.0.113.100'))
    assert rpc(server_url, 'tools/list', forwarded='203.0.113.100').status_code == 200
    # One byte more, not read: the gate counts it and so does its tool, and the minute's two are spent.
    assert answered(post(server_url, sized(CAP + 1), '203.0.113.101'))
    assert rpc(server_url, 'tools/list', forwarded='203.0.113.101').status_code == 429
    assert list(Tally.objects.values_list('origin', 'calls')) == [('direct:python-httpx', 2)]   # each served once


def test_chatgpts_user_in_a_body_past_what_the_gate_reads_has_no_share_of_its_own(server_url, labour, settings):
    cache.clear()
    settings.MCP_SUBJECT_LIMITS = {'minute': 20, 'hour': 1, 'articles': 300}
    settings.MCP_PLATFORM_LIMITS = {'minute': 600, 'hour': 100, 'articles': 10000}
    chatgpt, one = chatgpt_address(), {'openai/subject': 'v1/user-long'}
    assert answered(post(server_url, sized(CAP + 1, one), chatgpt))        # the platform's share alone
    assert answered(post(server_url, body(0, one), chatgpt))               # the user's first call of the hour
    past = post(server_url, body(0, one), chatgpt).json()['result']
    assert past['isError'] and 'This ChatGPT account reached its 1 calls this hour' in past['content'][0]['text']
    assert Tally.objects.get(origin='chatgpt').calls == 2


def test_a_batch_is_read_by_its_first_message(server_url, labour, settings):
    """A 2025-03 client sends batches; the SDK refuses them, but the gate counts them first by their first message."""
    cache.clear()
    settings.MCP_ADDRESS_LIMITS = {'minute': 1, 'day': 1000, 'articles': 2000}
    call = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'get_bulletin', 'arguments': {}}}
    listed = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
    # Led by a tool call: left to its tool, which the SDK never reaches, so the address's minute is whole.
    assert post(server_url, json.dumps([call, listed]).encode(), '203.0.113.110').status_code == 400
    assert rpc(server_url, 'tools/list', forwarded='203.0.113.110').status_code == 200
    # Led by anything else, or empty: counted by the gate, and the address's next request is past its minute.
    for address, batch in (('203.0.113.111', [listed, call]), ('203.0.113.112', [])):
        assert post(server_url, json.dumps(batch).encode(), address).status_code == 400
        assert rpc(server_url, 'tools/list', forwarded=address).status_code == 429
    assert not Tally.objects.exists()                                      # no tool served any of them


@pytest.mark.parametrize('params, status', [([1, 2], 400), ('words', 400), ({'_meta': 'words'}, 200), ({'_meta': [1]}, 200)])
def test_params_or_a_meta_that_are_no_object_are_refused_by_the_sdk_and_counted_by_the_gate(
        server_url, labour, settings, params, status):
    """The gate reads `_meta` only where `params` and it are objects: whatever else a client sends there reaches the
    SDK, which says «invalid parameters», and the request is counted like any other that is no tool call."""
    cache.clear()
    settings.MCP_ADDRESS_LIMITS = {'minute': 1, 'day': 1000, 'articles': 2000}
    odd = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': params}).encode()
    refused = post(server_url, odd, '203.0.113.120')
    assert (refused.status_code, refused.json()['error']['code']) == (status, -32602)
    assert post(server_url, odd, '203.0.113.120').status_code == 429
    # From ChatGPT's ranges, where the gate looks in `_meta` for the user: the same answer.
    assert post(server_url, odd, chatgpt_address()).status_code == status


def test_openai_subject_gives_a_share_only_from_chatgpts_ranges(server_url, labour, settings):
    cache.clear()
    settings.MCP_SUBJECT_LIMITS = {'minute': 20, 'hour': 1, 'articles': 300}
    settings.MCP_PLATFORM_LIMITS = {'minute': 600, 'hour': 100, 'articles': 10000}
    settings.MCP_ADDRESS_LIMITS = {'minute': 20, 'day': 1000, 'articles': 2000}
    one = {'openai/subject': 'v1/user-one'}
    # From Claude's range and from a direct address the same _meta is read as no user's: two calls each pass.
    for address in ('160.79.104.9', '203.0.113.120'):
        assert [answered(post(server_url, body(0, one), address)) for _ in range(2)] == [True, True], address
    assert dict(Tally.objects.values_list('origin', 'calls')) == {'claude': 2, 'direct:python-httpx': 2}
    # From ChatGPT's, the subject is a user with an hour of its own.
    chatgpt = chatgpt_address()
    assert [answered(post(server_url, body(0, one), chatgpt)) for _ in range(2)] == [True, False]
    assert Tally.objects.get(origin='chatgpt').calls == 1


def test_with_an_account_required_each_tool_asks_chatgpt_to_link_an_account(settings):
    settings.MCP_AUTH = 'required'
    tools = anyio.run(build().list_tools)
    assert [t.meta for t in tools] == [{'securitySchemes': [{'type': 'oauth2', 'scopes': ['law:read']}]}] * 5


async def served(app, scope: dict, parts: list[bytes]) -> list[dict]:
    """One request to the ASGI app as a server hands it over, its body in `parts` (a slow line delivers it in pieces),
    inside the app's lifespan; the messages the app sent back."""
    up, answered = anyio.Event(), anyio.Event()
    life = [{'type': 'lifespan.startup'}]

    async def life_receive():
        if life:
            return life.pop(0)
        await answered.wait()
        return {'type': 'lifespan.shutdown'}

    async def life_send(message):
        if message['type'] == 'lifespan.startup.complete':
            up.set()

    body = [{'type': 'http.request', 'body': p, 'more_body': k < len(parts) - 1} for k, p in enumerate(parts)]
    sent = []

    async def receive():
        if body:
            return body.pop(0)
        await answered.wait()
        return {'type': 'http.disconnect'}

    async def send(message):
        sent.append(message)
        if message['type'] == 'http.response.body' and not message.get('more_body'):
            answered.set()

    with anyio.fail_after(WAIT):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(app, {'type': 'lifespan', 'asgi': {'version': '3.0'}}, life_receive, life_send)
            await up.wait()
            await app(scope, receive, send)
    return sent


def test_a_body_that_arrives_in_pieces_is_read_whole_before_it_is_counted(transactional_db, labour, settings):
    """A tool call is counted by its tool, not by the gate: read in part, it looked like no tool call and was counted
    twice, so an address with one call a minute was refused its first."""
    cache.clear()
    settings.MCP_ADDRESS_LIMITS = {'minute': 1, 'day': 1000, 'articles': 2000}
    call = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                       'params': {'name': 'get_bulletin', 'arguments': {}}}).encode()
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'POST', 'scheme': 'http',
             'path': '/mcp', 'raw_path': b'/mcp', 'query_string': b'', 'root_path': '', 'client': ('203.0.113.99', 50000),
             'server': ('127.0.0.1', 8042), 'headers': [
                 (b'host', b'127.0.0.1:8042'), (b'content-type', b'application/json'),
                 (b'accept', b'application/json, text/event-stream'), (b'mcp-protocol-version', b'2025-06-18'),
                 (b'user-agent', b'python-httpx/0.28'), (b'content-length', str(len(call)).encode())]}
    sent = anyio.run(served, asgi(), scope, [call[:40], call[40:]])
    assert sent[0]['status'] == 200
    result = json.loads(b''.join(m.get('body', b'') for m in sent[1:]))['result']
    assert not result.get('isError') and 'Bulletin officiel 5167' in result['content'][0]['text']
    assert Tally.objects.get().calls == 1
