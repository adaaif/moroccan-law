import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db

PASSWORD = 'daftar-maghribi-2026'


def register(api, **overrides):
    body = {'username': 'salma', 'email': 'Salma@Example.org', 'password': PASSWORD}
    body.update(overrides)
    return api.post('/api/auth/register/', body, format='json')


def codes(response):
    return {(e['field'], e['code']) for e in response.json()['errors']}


def test_register_creates_the_account_and_signs_it_in(api):
    r = register(api, display_name=' سلمى ')
    assert r.status_code == 201
    body = r.json()
    assert body['access'] and body['refresh']
    assert body['user']['username'] == 'salma'
    assert body['user']['email'] == 'salma@example.org'
    assert body['user']['display_name'] == 'سلمى'
    assert body['user']['preferred_language'] == 'ar'


def test_register_refuses_while_sign_up_is_closed_and_says_so(api, settings):
    settings.REGISTRATION_OPEN = False
    settings.DISCUSSION_OPEN = False
    assert api.get('/api/auth/register/').json() == {'open': False, 'discussion': False, 'talk_alive': False, 'mcp_open': True, 'google': ''}
    r = register(api)
    assert r.status_code == 403
    assert codes(r) == {('registration', 'closed')}
    assert not get_user_model().objects.exists()


def test_register_says_when_sign_up_is_open(api):
    assert api.get('/api/auth/register/').json() == {'open': True, 'discussion': True, 'talk_alive': False, 'mcp_open': True, 'google': ''}


def test_asking_what_is_open_is_never_throttled(api, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {
        **settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}), 'auth': '1/min'}}
    assert all(api.get('/api/auth/register/').status_code == 200 for _ in range(3))


def test_register_accepts_an_arabic_username(api):
    r = register(api, username='سلمى_العلوي', email='s@example.org')
    assert r.status_code == 201


def test_register_refuses_a_taken_name_or_address_whatever_the_case(api):
    register(api)
    r = register(api, username='SALMA', email='salma@EXAMPLE.org')
    assert r.status_code == 400
    assert codes(r) == {('username', 'username_taken'), ('email', 'email_taken')}


@pytest.mark.parametrize('password, code', [
    ('short1', 'password_too_short'),
    ('2026202620262026', 'password_entirely_numeric'),
    ('password123', 'password_too_common'),
])
def test_register_names_the_first_password_rule_broken(api, password, code):
    r = register(api, password=password)
    assert r.status_code == 400
    assert codes(r) == {('password', code)}


def test_register_refuses_an_at_sign_in_the_username(api):
    r = register(api, username='salma@home')
    assert codes(r) == {('username', 'invalid')}


def test_register_reports_missing_fields_by_code(api):
    r = api.post('/api/auth/register/', {}, format='json')
    assert codes(r) == {('username', 'required'), ('email', 'required'),
                        ('password', 'required')}


def test_register_reports_empty_fields_as_blank(api):
    # The web form sends empty strings, not missing keys: the locales carry both codes.
    r = api.post('/api/auth/register/', {'username': '', 'email': '', 'password': ''},
                 format='json')
    assert codes(r) == {('username', 'blank'), ('email', 'blank'), ('password', 'blank')}


@pytest.mark.parametrize('login', ['salma', 'SALMA', 'salma@example.org', 'Salma@Example.ORG'])
def test_sign_in_takes_the_username_or_the_address(api, login):
    register(api)
    r = api.post('/api/auth/token/', {'username': login, 'password': PASSWORD}, format='json')
    assert r.status_code == 200
    assert r.json()['access']


def test_sign_in_with_a_wrong_password_is_refused(api):
    register(api)
    r = api.post('/api/auth/token/', {'username': 'salma', 'password': 'wrong-password'},
                 format='json')
    assert r.status_code == 401


def test_me_needs_a_session(api):
    assert api.get('/api/auth/me/').status_code == 401


def test_me_reads_and_updates_the_profile(api):
    access = register(api).json()['access']
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    assert api.get('/api/auth/me/').json()['username'] == 'salma'

    r = api.patch('/api/auth/me/', {'display_name': 'Salma A.', 'preferred_language': 'fr'},
                  format='json')
    assert r.status_code == 200
    assert r.json()['display_name'] == 'Salma A.'
    assert r.json()['preferred_language'] == 'fr'
    assert get_user_model().objects.get(username='salma').preferred_language == 'fr'


def test_me_refuses_an_unknown_language(api):
    access = register(api).json()['access']
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    r = api.patch('/api/auth/me/', {'preferred_language': 'en'}, format='json')
    assert codes(r) == {('preferred_language', 'invalid_choice')}


def test_refresh_rotates_and_the_old_token_dies(api):
    refresh = register(api).json()['refresh']
    r = api.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
    assert r.status_code == 200
    assert r.json()['refresh'] != refresh
    again = api.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
    assert again.status_code == 401


def test_a_deleted_accounts_token_is_refused_not_an_error(api):
    """RD17 of the readers review: the refresh of a token whose account is gone raised, and the phone got a 500."""
    refresh = register(api).json()['refresh']
    get_user_model().objects.all().delete()
    assert api.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json').status_code == 401


def test_logout_ends_the_session(api):
    refresh = register(api).json()['refresh']
    assert api.post('/api/auth/logout/', {'refresh': refresh}, format='json').status_code == 204
    r = api.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
    assert r.status_code == 401


def test_logout_with_a_bad_token_says_so(api):
    r = api.post('/api/auth/logout/', {'refresh': 'not-a-token'}, format='json')
    assert codes(r) == {('refresh', 'token_invalid')}


# ── What is too long is refused before anything reads it ─────────────────────


def test_a_login_or_an_address_longer_than_an_address_can_be_is_refused_first(api, django_assert_max_num_queries):
    from unittest import mock

    access = register(api).json()['access']
    long_address = 'a@' + 'x' * 300_000 + '.com'
    with mock.patch('apps.accounts.services.addresses._dl') as measured, django_assert_max_num_queries(0):
        signin = api.post('/api/auth/token/', {'username': long_address, 'password': 'x'}, format='json')
        reset = api.post('/api/auth/password/reset/', {'login': long_address}, format='json')
    assert signin.status_code == 400 and codes(signin) == {('login', 'max_length')}
    assert reset.status_code == 400 and codes(reset) == {('login', 'max_length')}
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    change = api.post('/api/auth/email/', {'email': long_address, 'password': PASSWORD}, format='json')
    assert change.status_code == 400 and codes(change) == {('email', 'max_length')}
    assert not measured.called
    # 254 characters is still an address: judged as before.
    edge = 'a@' + 'x' * 248 + '.com'
    assert len(edge) == 254
    assert api.post('/api/auth/token/', {'username': edge, 'password': 'x'}, format='json').status_code == 401


def test_the_typo_check_measures_only_names_near_a_providers():
    from unittest import mock

    from apps.accounts.services import addresses

    with mock.patch.object(addresses, '_dl', wraps=addresses._dl) as measured:
        assert addresses.typed_fix('reader@' + 'g' * 40 + '.com') is None
        assert not measured.called
        assert addresses.typed_fix('reader@gmial.com').split('@') == ['reader', 'gmail.com']
        assert measured.called
