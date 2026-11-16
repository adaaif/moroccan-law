"""The assistants' sign-in (MC5–MC8 of the MCP review): discovery, who asks, the person's answer, codes, tokens."""
import base64
import hashlib
import json
import socket
import threading
import time
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.services.refusals import Refused
from apps.oauth.models import Client, Grant, Token
from apps.oauth.services import clients, tokens

pytestmark = pytest.mark.django_db

RESOURCE = 'http://localhost:5190/mcp'
CLAUDE = 'https://claude.ai/oauth/mcp-oauth-client-metadata'
CLAUDE_DOC = {'client_id': CLAUDE, 'client_name': 'Claude', 'redirect_uris': ['https://claude.ai/api/mcp/auth_callback'],
              'token_endpoint_auth_method': 'none', 'grant_types': ['authorization_code', 'refresh_token']}
VERIFIER = 'v' * 20 + 'Sample-verifier-of-pkce-1234567890'


def challenge(verifier=VERIFIER):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()


@pytest.fixture(autouse=True)
def _fresh():
    cache.clear()


@pytest.fixture
def salma():
    user = get_user_model().objects.create_user(username='salma', email='salma@example.org', password='daftar-2026-x')
    user.email_proven_at = timezone.now()
    user.save()
    return user


def signed(api, user):
    from apps.accounts.services.accounts import tokens_for
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens_for(user)["access"]}')
    return api


def fragment(location):
    return parse_qs(urlsplit(location).fragment)


def query(location):
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}


def authorize(api, **over):
    params = {'response_type': 'code', 'client_id': CLAUDE, 'redirect_uri': CLAUDE_DOC['redirect_uris'][0],
              'code_challenge': challenge(), 'code_challenge_method': 'S256', 'state': 'st-1', 'resource': RESOURCE,
              'scope': 'law:read'}
    params.update(over)
    with mock.patch('apps.oauth.services.clients.fetch_document', return_value=dict(CLAUDE_DOC)):
        return api.get('/oauth/authorize', {k: v for k, v in params.items() if v is not None})


def connect(api, user, **over):
    """The whole dance up to the code: {code, state, iss}."""
    r = authorize(api, **over)
    raw = fragment(r['Location'])['r'][0]
    approved = signed(api, user).post('/api/oauth/approve/', {'r': raw}, format='json')
    api.credentials()
    return query(approved.json()['redirect'])


def exchange(api, code, **over):
    body = {'grant_type': 'authorization_code', 'code': code, 'client_id': CLAUDE, 'code_verifier': VERIFIER,
            'redirect_uri': CLAUDE_DOC['redirect_uris'][0], 'resource': RESOURCE}
    body.update(over)
    return api.post('/oauth/token', body)          # form-encoded, as RFC 6749 says


# ── Discovery ────────────────────────────────────────────────────────────────

def test_the_metadata_says_what_claude_and_chatgpt_look_for(api):
    server = api.get('/.well-known/oauth-authorization-server').json()
    assert server['issuer'] == 'http://localhost:5190'
    assert server['client_id_metadata_document_supported'] is True
    assert server['token_endpoint_auth_methods_supported'] == ['none']      # Claude uses CIMD only with both
    assert server['code_challenge_methods_supported'] == ['S256']
    assert server['authorization_response_iss_parameter_supported'] is True
    assert server['registration_endpoint'].endswith('/oauth/register')
    for path in ('/.well-known/oauth-protected-resource', '/.well-known/oauth-protected-resource/mcp'):
        r = api.get(path)
        assert r['Access-Control-Allow-Origin'] == '*'
        assert r.json()['resource'] == RESOURCE and r.json()['authorization_servers'] == ['http://localhost:5190']
        assert 'offline_access' not in r.json()['scopes_supported']


# ── Who asks ─────────────────────────────────────────────────────────────────

def test_a_metadata_document_is_read_once_a_day_and_must_name_itself(api):
    with mock.patch('apps.oauth.services.clients.fetch_document', return_value=dict(CLAUDE_DOC)) as fetched:
        c = clients.find(CLAUDE)
        clients.find(CLAUDE)
    assert fetched.call_count == 1 and c.name == 'Claude' and c.domain == 'claude.ai'
    with mock.patch('apps.oauth.services.clients.fetch_document', return_value={**CLAUDE_DOC, 'client_id': 'https://x.y/z'}):
        with pytest.raises(Refused):
            clients.find('https://evil.example/client')


def test_a_metadata_document_on_a_private_address_is_never_fetched():
    with mock.patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('192.168.1.1', 443))]):
        with pytest.raises(clients.FetchError, match='private_address'):
            clients.fetch_document('https://claude.ai/client.json')
    with mock.patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('169.254.169.254', 443))]):
        with pytest.raises(clients.FetchError):
            clients.fetch_document('https://chatgpt.com/latest')
    with pytest.raises(clients.FetchError, match='scheme'):
        clients.fetch_document('http://claude.ai/client.json')


def test_registration_takes_https_and_loopback_redirects_only(api):
    ok = api.post('/oauth/register', {'client_name': 'MCP Inspector', 'redirect_uris': ['http://localhost:6274/oauth/callback']},
                  format='json')
    assert ok.status_code == 201 and ok.json()['client_id'].startswith('qc_')
    assert ok.json()['token_endpoint_auth_method'] == 'none'
    bad = api.post('/oauth/register', {'redirect_uris': ['http://evil.example/cb']}, format='json')
    assert bad.status_code == 400 and bad.json()['error'] == 'invalid_redirect_uri'
    secret = api.post('/oauth/register', {'redirect_uris': ['https://a.example/cb'],
                                          'token_endpoint_auth_method': 'client_secret_basic'}, format='json')
    assert secret.json()['error'] == 'invalid_client_metadata'


def test_a_loopback_redirect_matches_on_any_port():
    c = Client(redirect_uris=['http://localhost/callback', 'http://127.0.0.1/callback'])
    assert clients.redirect_allowed(c, 'http://localhost:3118/callback')
    assert clients.redirect_allowed(c, 'http://127.0.0.1:50211/callback')
    assert not clients.redirect_allowed(c, 'http://localhost:3118/other')
    assert not clients.redirect_allowed(Client(redirect_uris=['https://a.example/cb']), 'https://a.example/cb2')


# ── The request and the answer ───────────────────────────────────────────────

def test_a_bad_redirect_is_shown_here_never_sent_there(api):
    r = authorize(api, redirect_uri='https://evil.example/cb')
    assert r.status_code == 302 and r['Location'] == '/connect#error=redirect'


def test_after_a_good_redirect_refusals_go_back_with_state_and_iss(api):
    r = authorize(api, code_challenge_method='plain')
    q = query(r['Location'])
    assert r['Location'].startswith('https://claude.ai/api/mcp/auth_callback?')
    assert q == {'error': 'invalid_request', 'error_description': 'PKCE with S256 is required.', 'state': 'st-1',
                 'iss': 'http://localhost:5190'}
    assert query(authorize(api, resource='https://other.example/mcp')['Location'])['error'] == 'invalid_target'


def test_connect_shows_who_asks_and_needs_a_proven_email(api, salma):
    raw = fragment(authorize(api)['Location'])['r'][0]
    seen = api.post('/api/oauth/request/', {'r': raw}, format='json').json()
    assert seen['client'] == {'name': 'Claude', 'known': True, 'domain': 'claude.ai', 'self_named': False}
    assert seen['redirect_host'] == 'claude.ai' and seen['loopback'] is False
    assert api.post('/api/oauth/approve/', {'r': raw}, format='json').status_code == 401     # signed in first
    salma.email_proven_at = None
    salma.save()
    refused = signed(api, salma).post('/api/oauth/approve/', {'r': raw}, format='json')
    assert refused.status_code == 403 and refused.json()['errors'] == [{'field': 'email', 'code': 'not_proven'}]


def test_no_says_access_denied_and_a_request_is_answered_once(api, salma):
    raw = fragment(authorize(api)['Location'])['r'][0]
    no = api.post('/api/oauth/deny/', {'r': raw}, format='json').json()['redirect']
    assert query(no) == {'error': 'access_denied', 'state': 'st-1', 'iss': 'http://localhost:5190'}
    again = signed(api, salma).post('/api/oauth/approve/', {'r': raw}, format='json')
    assert again.status_code == 410 and again.json()['errors'][0]['code'] == 'expired'


# ── Codes and tokens ─────────────────────────────────────────────────────────

def test_the_code_with_its_verifier_gives_a_pair_once(api, salma):
    back = connect(api, salma)
    assert back['state'] == 'st-1' and back['iss'] == 'http://localhost:5190'
    r = exchange(api, back['code'])
    assert r.status_code == 200 and r['Cache-Control'] == 'no-store'
    pair = r.json()
    assert pair['token_type'] == 'Bearer' and pair['expires_in'] == 3600 and pair['scope'] == 'law:read'
    assert tokens.verify(pair['access_token']).grant.user == salma
    assert exchange(api, back['code']).json()['error'] == 'invalid_grant'          # once


def test_a_wrong_verifier_burns_the_code(api, salma):
    back = connect(api, salma)
    assert exchange(api, back['code'], code_verifier='w' * 50).json()['error'] == 'invalid_grant'
    assert exchange(api, back['code']).json()['error'] == 'invalid_grant'          # the right one is too late


def test_a_code_for_another_resource_or_redirect_is_refused(api, salma):
    assert exchange(api, connect(api, salma)['code'], resource='https://other.example/mcp').json()['error'] == 'invalid_target'
    assert exchange(api, connect(api, salma)['code'], redirect_uri='https://claude.ai/x').json()['error'] == 'invalid_grant'


def test_refresh_rotates_and_a_stolen_refresh_token_ends_the_connection(api, salma):
    pair = exchange(api, connect(api, salma)['code']).json()
    body = {'grant_type': 'refresh_token', 'refresh_token': pair['refresh_token'], 'client_id': CLAUDE}
    new = api.post('/oauth/token', body).json()
    assert new['refresh_token'] != pair['refresh_token'] and tokens.verify(new['access_token'])
    # A lost answer replayed soon after gets the same pair, not a disconnection.
    assert api.post('/oauth/token', body).json() == new
    cache.clear()                                         # later: whoever holds the old token is not the client
    stolen = api.post('/oauth/token', body)
    assert stolen.status_code == 400 and stolen.json()['error'] == 'invalid_grant'
    assert tokens.verify(new['access_token']) is None
    assert Grant.objects.get().revoked_at is not None


def test_an_expired_access_token_and_a_deleted_registration_say_so(api, salma):
    pair = exchange(api, connect(api, salma)['code']).json()
    Token.objects.filter(kind='access').update(expires_at=timezone.now() - timedelta(seconds=1))
    assert tokens.verify(pair['access_token']) is None
    gone = api.post('/oauth/token', {'grant_type': 'refresh_token', 'refresh_token': 'x', 'client_id': 'qc_gone'})
    assert gone.status_code == 401 and gone.json()['error'] == 'invalid_client'


def test_revoking_any_token_ends_the_connection(api, salma):
    pair = exchange(api, connect(api, salma)['code']).json()
    assert api.post('/oauth/revoke', {'token': pair['refresh_token']}).status_code == 200
    assert tokens.verify(pair['access_token']) is None
    assert api.post('/oauth/revoke', {'token': 'unknown'}).status_code == 200


# ── Connections ──────────────────────────────────────────────────────────────

def test_one_connection_per_assistant_listed_and_ended_from_the_account(api, salma):
    first = exchange(api, connect(api, salma)['code']).json()
    exchange(api, connect(api, salma)['code'])
    listed = signed(api, salma).get('/api/oauth/connections/').json()
    assert len(listed) == 1 and listed[0]['name'] == 'Claude' and listed[0]['domain'] == 'claude.ai'
    assert listed[0]['calls_this_month'] == 0
    assert api.delete(f'/api/oauth/connections/{listed[0]["id"]}/').status_code == 204
    assert tokens.verify(first['access_token']) is None
    assert api.get('/api/oauth/connections/').json() == []


def test_a_new_password_or_deleting_the_account_ends_every_connection(api, salma):
    pair = exchange(api, connect(api, salma)['code']).json()
    signed(api, salma).post('/api/auth/password/', {'password': 'daftar-2026-x', 'new_password': 'jdida-maghribia-2026'},
                            format='json')
    assert tokens.verify(pair['access_token']) is None
    salma.refresh_from_db()         # a session is made under the password the account holds now
    pair = exchange(api, connect(api, salma)['code']).json()
    signed(api, salma).post('/api/auth/me/delete/', {'password': 'jdida-maghribia-2026'}, format='json')
    assert tokens.verify(pair['access_token']) is None


# ── What the server fetches, and how often (OP23) ────────────────────────────

PUBLIC = [(2, 1, 6, '', ('160.79.104.10', 443))]


def answering(chunks, pause=0.0):
    """Our end of a socket pair whose other end reads the request and answers `chunks`, `pause` seconds apart: a host
    without the network."""
    ours, theirs = socket.socketpair()

    def run():
        try:
            theirs.recv(4096)
            for chunk in chunks:
                theirs.sendall(chunk)
                time.sleep(pause)
        except OSError:
            pass
        finally:
            theirs.close()
    threading.Thread(target=run, daemon=True).start()
    return ours


def test_a_metadata_document_is_fetched_only_from_the_assistants_hosts(api):
    """Every fetch leaves from the server's own connection: any other client registers, which fetches nothing."""
    with mock.patch('apps.oauth.services.clients.fetch_document') as fetched:
        r = authorize(api, client_id='https://x.attacker.example/client')
        assert r['Location'] == '/connect#error=client_unlisted'
    assert not fetched.called
    with mock.patch('socket.getaddrinfo') as resolved:
        with pytest.raises(clients.FetchError, match='unlisted'):
            clients.fetch_document('https://claude.ai.attacker.example/client')
    assert not resolved.called


def test_a_whole_fetch_ends_on_time_however_slowly_the_host_answers(settings):
    """A byte every 0.3 s never trips a timeout per read; the deadline ends the whole exchange."""
    settings.OAUTH_METADATA_SECONDS = 1
    ours = answering([bytes([b]) for b in b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n'], pause=0.3)
    started = time.monotonic()
    with mock.patch('socket.getaddrinfo', return_value=PUBLIC), \
            mock.patch('apps.oauth.services.clients._connect', return_value=ours):
        with pytest.raises(clients.FetchError, match='timeout'):
            clients.fetch_document(CLAUDE)
    assert time.monotonic() - started < 2
    ours.close()


def test_a_document_sent_in_chunks_is_read_whole():
    body = json.dumps(CLAUDE_DOC).encode()
    head = b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n'
    chunked = b''.join(b'%x\r\n%s\r\n' % (len(part), part) for part in (body[:40], body[40:])) + b'0\r\n\r\n'
    ours = answering([head, chunked])
    with mock.patch('socket.getaddrinfo', return_value=PUBLIC), \
            mock.patch('apps.oauth.services.clients._connect', return_value=ours):
        assert clients.fetch_document(CLAUDE) == CLAUDE_DOC
    big = answering([b'HTTP/1.1 200 OK\r\nContent-Length: 999999\r\n\r\n'])
    with mock.patch('socket.getaddrinfo', return_value=PUBLIC), \
            mock.patch('apps.oauth.services.clients._connect', return_value=big):
        with pytest.raises(clients.FetchError, match='too_large'):
            clients.fetch_document(CLAUDE)


def test_a_refusal_is_kept_a_few_minutes_not_asked_for_again_each_time():
    with mock.patch('apps.oauth.services.clients.fetch_document', side_effect=clients.FetchError('timeout')) as fetched:
        for _ in range(3):
            with pytest.raises(Refused) as refused:
                clients.find(CLAUDE)
            assert refused.value.code == 'unreachable'
    assert fetched.call_count == 1
    wrong = {**CLAUDE_DOC, 'client_secret': 'x'}
    cache.clear()                                         # the minutes have passed
    with mock.patch('apps.oauth.services.clients.fetch_document', return_value=wrong) as fetched:
        for _ in range(2):
            with pytest.raises(Refused) as refused:
                clients.find(CLAUDE)
            assert refused.value.code == 'invalid'
    assert fetched.call_count == 1
    cache.clear()
    with mock.patch('apps.oauth.services.clients.fetch_document', return_value=dict(CLAUDE_DOC)):
        kept = clients.find(CLAUDE)
    # Their host down a day later: yesterday's copy, and one fetch for the minutes it stays down.
    Client.objects.filter(pk=kept.pk).update(fetched_at=timezone.now() - timedelta(days=2))
    with mock.patch('apps.oauth.services.clients.fetch_document', side_effect=clients.FetchError('network')) as fetched:
        assert clients.find(CLAUDE).pk == kept.pk and clients.find(CLAUDE).pk == kept.pk
    assert fetched.call_count == 1


def test_the_assistants_link_has_a_limit_and_connect_says_to_wait(api):
    with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'oauth_authorize': '2/min'}):
        assert [authorize(api)['Location'][:11] for _ in range(2)] == ['/connect#r='] * 2
        assert authorize(api)['Location'] == '/connect#error=busy'
    with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'oauth_metadata': '1/min'}):
        assert api.get('/.well-known/oauth-authorization-server').status_code == 200
        assert api.get('/.well-known/oauth-protected-resource').status_code == 429


def test_a_client_the_site_does_not_know_is_never_sent_its_refusals(api):
    """Its refusals are shown on /connect: no person is sent from the site to a page the client chose without answering."""
    registered = api.post('/oauth/register', {'redirect_uris': ['https://evil.example/landing']}, format='json').json()
    base = {'client_id': registered['client_id'], 'redirect_uri': 'https://evil.example/landing', 'response_type': 'code',
            'code_challenge': challenge(), 'code_challenge_method': 'S256', 'resource': RESOURCE}
    for over, shown in (({'response_type': 'x'}, 'response_type'), ({'code_challenge_method': 'plain'}, 'pkce'),
                        ({'resource': 'https://other.example/mcp'}, 'resource'), ({'scope': 'admin'}, 'scope')):
        r = api.get('/oauth/authorize', {**base, **over})
        assert r.status_code == 302 and r['Location'] == f'/connect#error={shown}'


def test_a_malformed_address_is_a_refusal_not_an_error(api):
    for client_id in ('https://[', 'https://claude.ai:99999/client', 'https://claude.ai:x/client'):
        assert authorize(api, client_id=client_id)['Location'] == '/connect#error=client_invalid'
    assert authorize(api, redirect_uri='http://[')['Location'] == '/connect#error=redirect'


# ── Who the consent page names (OP22) ────────────────────────────────────────

def registered(api, *redirects, name=''):
    r = api.post('/oauth/register', {'client_name': name, 'redirect_uris': list(redirects)}, format='json')
    assert r.status_code == 201, r.json()
    return r.json()['client_id']


def shown(api, client_id, redirect_uri):
    r = api.get('/oauth/authorize', {'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect_uri,
                                     'code_challenge': challenge(), 'code_challenge_method': 'S256'})
    return api.post('/api/oauth/request/', {'r': fragment(r['Location'])['r'][0]}, format='json').json()


def test_a_registration_is_named_as_an_assistant_only_when_every_redirect_goes_to_it(api, salma):
    mixed = registered(api, 'https://claude.ai/x', 'https://zz.attacker.example/cb', name='Claude')
    for redirect, host in (('https://zz.attacker.example/cb', 'zz.attacker.example'), ('https://claude.ai/x', 'claude.ai')):
        seen = shown(api, mixed, redirect)
        assert seen['client'] == {'name': 'Claude', 'known': False, 'domain': 'claude.ai, zz.attacker.example',
                                  'self_named': True}
        assert seen['redirect_host'] == host                 # the page's headline: where the answer goes
    own = registered(api, 'https://claude.ai/api/mcp/auth_callback', 'https://claude.com/api/mcp/auth_callback')
    assert shown(api, own, 'https://claude.ai/api/mcp/auth_callback')['client']['known'] is True
    # The account page names a connection the same way.
    from apps.oauth.services import flow
    raw = fragment(api.get('/oauth/authorize', {'response_type': 'code', 'client_id': mixed,
                                                'redirect_uri': 'https://zz.attacker.example/cb',
                                                'code_challenge': challenge(),
                                                'code_challenge_method': 'S256'})['Location'])['r'][0]
    flow.approve(raw, salma)
    listed = signed(api, salma).get('/api/oauth/connections/').json()
    assert [(c['name'], c['known'], c['domain']) for c in listed] == [('Claude', False, 'claude.ai, zz.attacker.example')]


def test_an_assistant_is_known_by_its_exact_host():
    assert clients.known_name('claude.ai') == 'Claude' and clients.known_name('CHATGPT.COM') == 'ChatGPT'
    assert clients.known_name('evil.claude.ai') == '' and clients.known_name('claude.ai.evil.example') == ''


# Each read by Node's URL (the WHATWG parser browsers use) on 12 Nov 2026: what a browser opens. Python's urlsplit
# names another host for each of the first ones, or none.
READ_APART = [
    'https://claude.ai\\@evil.example/cb',        # browser: claude.ai; Python: evil.example
    'https://evil.example\\@claude.ai/cb',        # browser: evil.example; Python: claude.ai
    'https://evil.example\\claude.ai/cb',         # browser: evil.example
    'https://claude.ai%2Eevil.example/cb',        # browser: claude.ai.evil.example
    'https://claude%2Eai/cb',                     # browser: claude.ai
    'https://сlaude.ai/cb',                       # a Cyrillic «с»; browser: xn--laude-0ye.ai
    'https://claude.ai。evil.example/cb',     # an ideographic full stop; browser: claude.ai.evil.example
    'https://0x7f000001/cb',                      # browser: 127.0.0.1
    'https://127.1/cb',                           # browser: 127.0.0.1
    'https://claude.ai\u0000.evil/cb',
    'https:/claude.ai/cb', 'https:claude.ai/cb',  # browser: claude.ai; Python: no host
    # The same reading, refused all the same: «@», spaces and controls, a backslash anywhere.
    'https://claude.ai@evil.example/cb', 'http://evil.example@localhost/cb', ' https://claude.ai/cb',
    'https://claude.ai/cb\n', 'https://cla\tude.ai/cb', 'https://a.example/c\\b', 'https://claude.ai:/cb',
    'https://claude.ai./cb', 'https://claude.ai:99999/cb', 'http://evil.example/cb', 'https://claude.ai/cb#x',
]
READ_ALIKE = {
    'https://claude.ai/api/mcp/auth_callback': 'claude.ai', 'https://CLAUDE.AI/cb': 'claude.ai',
    'https://claude.ai:443/cb': 'claude.ai', 'https://xn--laude-3we.ai/cb': 'xn--laude-3we.ai',
    'https://chatgpt.com/connector_platform_oauth_redirect?x=1': 'chatgpt.com',
    'http://localhost:3118/callback': 'localhost', 'http://127.0.0.1/callback': '127.0.0.1',
    'http://[::1]:5000/cb': '[::1]',
}


def test_a_redirect_a_browser_could_read_apart_is_refused(api):
    for uri in READ_APART:
        assert clients.redirect_host(uri) == '', uri
        r = api.post('/oauth/register', {'redirect_uris': [uri]}, format='json')
        # A NUL is refused with the body that holds it, before any redirect is read (config/malformed.py).
        refusal = 'invalid_request' if '\x00' in uri else 'invalid_redirect_uri'
        assert r.status_code == 400 and r.json()['error'] == refusal, uri
    for uri, host in READ_ALIKE.items():
        assert clients.redirect_host(uri) == host, uri


def test_a_redirect_kept_from_before_the_check_or_asked_with_an_at_sign_is_never_used(api):
    old = Client.objects.create(client_id='qc_old', kind='dcr', redirect_uris=['https://claude.ai\\@evil.example/cb'],
                                domain='claude.ai')
    r = api.get('/oauth/authorize', {'response_type': 'code', 'client_id': old.client_id,
                                     'code_challenge': challenge(), 'code_challenge_method': 'S256'})
    assert r['Location'] == '/connect#error=redirect'
    code = registered(api, 'http://localhost/callback')
    r = api.get('/oauth/authorize', {'response_type': 'code', 'client_id': code,
                                     'redirect_uri': 'http://evil.example@localhost:3118/callback',
                                     'code_challenge': challenge(), 'code_challenge_method': 'S256'})
    assert r['Location'] == '/connect#error=redirect'
