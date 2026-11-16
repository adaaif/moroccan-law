"""No malformed request answers 500 at any address of apps.oauth (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""
import pytest


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('oauth', malformed) == []

from apps.oauth.models import Client  # noqa: E402
from apps.oauth.services import clients  # noqa: E402


@pytest.mark.django_db
@pytest.mark.parametrize('client_id', ['https://[', 'https://claude.ai:99999/oauth/x', 'https://a.example/' + 'x' * 600,
                                       'https://' + 'a' * 300 + '.example/x'])
def test_a_client_id_no_url_reader_takes_is_shown_as_invalid(api, client_id, monkeypatch):
    """`urlsplit('https://[')` and a port past 65535 raised ValueError; an id or a host past its column, DataError.
    None of them is fetched."""
    monkeypatch.setattr(clients, 'fetch_document', lambda url: pytest.fail(f'fetched {url[:40]}'))
    r = api.get('/oauth/authorize', {'client_id': client_id, 'redirect_uri': 'https://claude.ai/cb', 'response_type': 'code',
                                     'code_challenge': 'x' * 43, 'code_challenge_method': 'S256'})
    assert (r.status_code, r['Location']) == (302, '/connect#error=client_invalid')


def test_a_loopback_redirect_with_a_user_name_or_past_its_column_is_not_the_registered_one():
    c = Client(redirect_uris=['http://localhost/callback'])
    assert clients.redirect_allowed(c, 'http://localhost:3118/callback')
    assert not clients.redirect_allowed(c, 'http://someone@localhost:3118/callback')
    assert not clients.redirect_allowed(c, 'http://' + 'u' * 2000 + '@localhost/callback')
    assert not clients.redirect_allowed(c, 'http://localhost:99999/callback')
    assert not clients.redirect_allowed(c, 'http://[/callback')


@pytest.mark.django_db
def test_the_assistants_doors_refuse_parameters_of_another_kind_as_oauth_says(api):
    r = api.post('/oauth/token', {'grant_type': 'refresh_token', 'client_id': 5, 'refresh_token': 'r'}, format='json')
    assert (r.status_code, r.json()['error']) == (400, 'invalid_request')
    r = api.post('/oauth/token', {'grant_type': 'refresh_token', 'client_id': 'qc_x', 'refresh_token': ['r']}, format='json')
    assert (r.status_code, r.json()['error']) == (400, 'invalid_request')
    assert api.post('/oauth/revoke', {'token': 5}, format='json').status_code == 200
    r = api.post('/oauth/register', {'redirect_uris': ['https://a.example/cb'], 'grant_types': [{}]}, format='json')
    assert (r.status_code, r.json()['error']) == (400, 'invalid_client_metadata')
    r = api.post('/oauth/register', {'redirect_uris': ['https://[/cb']}, format='json')
    assert (r.status_code, r.json()['error']) == (400, 'invalid_redirect_uri')
    # The app's own call answers in the site's shape: a request's id that is a number is no request.
    r = api.post('/api/oauth/request/', {'r': 5}, format='json')
    assert (r.status_code, r.json()) == (410, {'errors': [{'field': 'request', 'code': 'expired'}]})
