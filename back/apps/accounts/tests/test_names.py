"""A name stands beside everything its holder writes: when it is chosen, it passes the discussion's fixed patterns (a
phone number, an address, a link, an insult), and one that holds something is refused. An account that already holds
such a name keeps it."""
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.services import accounts

pytestmark = pytest.mark.django_db
PASSWORD = 'daftar-maghribi-2026'


def codes(r):
    return {(e['field'], e['code']) for e in r.json()['errors']}


def register(api, **overrides):
    body = {'username': 'salma', 'email': 'salma@example.org', 'password': PASSWORD, **overrides}
    return api.post('/api/auth/register/', body, format='json')


@pytest.mark.parametrize('field, name', [
    ('username', '0600000000'),
    ('username', 'PUTAIN'),
    ('display_name', 'اتصلوا 0600000000'),
    ('display_name', 'salma@example.org'),
    ('display_name', 'bit.ly/abc'),
    ('display_name', 'القحبة'),
])
def test_a_name_that_holds_something_is_refused_at_sign_up(api, field, name):
    r = register(api, **{field: name})
    assert r.status_code == 400 and codes(r) == {(field, 'held')}
    assert not get_user_model().objects.exists()


def test_a_clean_name_passes(api):
    assert register(api, username='salma_06', display_name='سلمى العلوي').status_code == 201


def test_a_new_display_name_is_judged_and_one_already_held_is_kept(api):
    user = accounts.register(username='salma', email='salma@example.org', password=PASSWORD)
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {accounts.tokens_for(user)["access"]}')
    r = api.patch('/api/auth/me/', {'display_name': 'رقمي 0600000000', 'preferred_language': 'fr'}, format='json')
    assert r.status_code == 400 and codes(r) == {('display_name', 'held')}
    user.refresh_from_db()
    assert user.display_name == '' and user.preferred_language == 'ar'      # nothing of the request was saved
    assert api.patch('/api/auth/me/', {'display_name': 'سلمى'}, format='json').status_code == 200
    # An account that held such a name before the rule keeps it, and can still save its other fields with it.
    get_user_model().objects.filter(pk=user.pk).update(display_name='اتصلوا 0600000000')
    kept = api.patch('/api/auth/me/', {'display_name': 'اتصلوا 0600000000', 'preferred_language': 'fr'}, format='json')
    assert kept.status_code == 200 and kept.json()['preferred_language'] == 'fr'


def test_google_sign_up_judges_the_chosen_username(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = 'web'
    settings.GOOGLE_OAUTH_CLIENT_IDS = ['web']
    claims = {'iss': 'https://accounts.google.com', 'aud': 'web', 'sub': '42', 'email': 'amina@example.org',
              'email_verified': True, 'nonce': 'n1'}
    with mock.patch('google.oauth2.id_token.verify_oauth2_token', return_value=claims):
        r = APIClient().post('/api/auth/google/', {'credential': 't', 'nonce': 'n1', 'username': '0600000009'},
                             format='json')
    assert r.status_code == 400 and codes(r) == {('username', 'held')}
    assert not get_user_model().objects.exists()
