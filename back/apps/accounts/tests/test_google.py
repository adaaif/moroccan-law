"""«المتابعة بحساب Google» (9 Nov 2026, services/google.py): Google's signed token for an account, found by its `sub`
or its verified address, a new one with the username the person chose; never a stranger's token, an unverified
address, or another app's audience."""
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.services import accounts

pytestmark = pytest.mark.django_db
WEB = 'web-client.apps.googleusercontent.com'
URL = '/api/auth/google/'


@pytest.fixture
def on(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = WEB
    settings.GOOGLE_OAUTH_CLIENT_IDS = [WEB]
    settings.REGISTRATION_OPEN = True


def signed(**claims):
    """Google's verification answering these claims (the signature check itself is google-auth's)."""
    full = {'iss': 'https://accounts.google.com', 'aud': WEB, 'sub': '1234567890', 'email': 'Amina@Example.org',
            'email_verified': True, 'nonce': 'n1', **claims}
    return mock.patch('google.oauth2.id_token.verify_oauth2_token', return_value=full)


def post(**body):
    return APIClient().post(URL, {'credential': 'token', 'nonce': 'n1', **body}, format='json')


def codes(r):
    return [(e['field'], e['code']) for e in r.json()['errors']]


def test_off_without_a_client_id(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_IDS = '', []
    assert APIClient().get(URL).json() == {'client_id': ''}
    assert APIClient().get('/api/auth/register/').json()['google'] == ''
    r = post()
    assert r.status_code == 503 and codes(r) == [('google', 'off')]


def test_a_newcomer_chooses_a_username_and_is_in(on):
    assert APIClient().get(URL).json() == {'client_id': WEB}
    with signed():
        first = post()
        assert first.status_code == 200 and first.json() == {'code': 'google_signup', 'email': 'amina@example.org'}
        assert not get_user_model().objects.exists()                    # no account before the username
        made = post(username='amina_k', preferred_language='fr')
    assert made.status_code == 201 and made.json()['created'] is True and made.json()['access']
    user = get_user_model().objects.get(username='amina_k')
    assert user.google_sub == '1234567890' and user.email == 'amina@example.org' and user.email_proven_at
    assert not user.has_usable_password() and user.preferred_language == 'fr'
    assert made.json()['user']['google'] is True and made.json()['user']['has_password'] is False
    with signed():                                                     # next time: straight in, by `sub`
        again = post()
    assert again.status_code == 200 and again.json()['created'] is False and again.json()['user']['username'] == 'amina_k'


def test_a_taken_username_is_said(on):
    accounts.register(username='amina_k', email='other@example.com', password='a-long-pass-123')
    with signed():
        r = post(username='Amina_K')
    assert r.status_code == 400 and codes(r) == [('username', 'username_taken')]


def test_sign_up_closed_lets_accounts_in_but_makes_none(on, settings):
    settings.REGISTRATION_OPEN = False
    with signed():
        r = post(username='amina_k')
    assert r.status_code == 403 and codes(r) == [('registration', 'closed')]
    accounts.register(username='amina', email='amina@example.org', password='a-long-pass-123')
    with signed():
        assert post().status_code == 200


def test_an_account_with_that_proven_address_is_bound_and_keeps_its_password(on):
    user = accounts.register(username='amina', email='amina@example.org', password='a-long-pass-123')
    user.email_proven_at = timezone.now()
    user.save()
    with signed():
        r = post()
    user.refresh_from_db()
    assert r.status_code == 200 and user.google_sub == '1234567890' and user.check_password('a-long-pass-123')


def test_an_unproven_address_goes_to_its_owner_alone(on):
    # An account opened with someone else's address, waiting for them: Google proves who owns the inbox, the password
    # whoever opened it set is voided, and its sessions end.
    user = accounts.register(username='squatter', email='amina@example.org', password='a-long-pass-123')
    accounts.tokens_for(user)
    with signed():
        r = post()
    user.refresh_from_db()
    assert r.status_code == 200 and user.email_proven_at and not user.has_usable_password()
    first = OutstandingToken.objects.filter(user=user).order_by('created_at').first()
    assert hasattr(first, 'blacklistedtoken')


@pytest.mark.parametrize('claims, code, status', [
    ({'aud': 'someone-elses-app.apps.googleusercontent.com'}, ('google', 'invalid'), 401),
    ({'nonce': 'another'}, ('google', 'invalid'), 401),
    ({'iss': 'https://evil.example'}, ('google', 'invalid'), 401),
    ({'email_verified': False}, ('google', 'email_unverified'), 400),
    ({'email': ''}, ('google', 'no_email'), 400),
])
def test_refused_tokens(on, claims, code, status):
    with signed(**claims):
        r = post(username='amina_k')
    assert r.status_code == status and codes(r) == [code] and not get_user_model().objects.exists()


def test_a_forged_token_is_refused(on):
    with mock.patch('google.oauth2.id_token.verify_oauth2_token', side_effect=ValueError('bad signature')):
        r = post()
    assert r.status_code == 401 and codes(r) == [('google', 'invalid')]


def test_an_address_bound_to_another_google_account_stays_with_it(on):
    user = accounts.register(username='amina', email='amina@example.org', password='a-long-pass-123')
    user.google_sub = 'another-sub'
    user.save()
    with signed():
        r = post()
    assert r.status_code == 409 and codes(r) == [('google', 'other')]


def test_a_new_address_unbinds_google_and_ends_the_assistants_connections(on):
    # Someone signs up with their own Google account, sets a password, then moves the account to another person's
    # address. That person may later take the account over («email in use», then a reset): the first Google identity
    # must not still open it.
    from apps.oauth.models import Client, Grant

    with signed():
        assert post(username='amina_k').status_code == 201
    user = get_user_model().objects.get(username='amina_k')
    user.set_password('a-long-pass-123')
    user.save()
    client = Client.objects.create(client_id='https://assistant.example/client', kind='cimd',
                                   redirect_uris=['https://assistant.example/cb'])
    grant = Grant.objects.create(user=user, client=client, scope='law:read', resource='http://localhost:5190/mcp')

    assert accounts.change_email(user, email='victim@example.com') in (True, False)
    user.refresh_from_db()
    grant.refresh_from_db()
    assert user.email == 'victim@example.com' and user.google_sub is None and grant.revoked_at is not None
    with signed():
        r = post()
    # The old identity finds no account any more: it is offered a new one of its own.
    assert r.status_code == 200 and r.json() == {'code': 'google_signup', 'email': 'amina@example.org'}


def test_a_disabled_account_is_not_opened(on):
    user = accounts.register(username='amina', email='amina@example.org', password='a-long-pass-123')
    user.is_active = False
    user.save()
    with signed():
        r = post()
    assert r.status_code == 401 and codes(r) == [('login', 'disabled')]


def test_a_deleted_account_lets_go_of_its_google(on):
    from apps.discussion.services import leaving
    with signed():
        post(username='amina_k')
    user = get_user_model().objects.get(username='amina_k')
    user.set_password('a-long-pass-123')
    user.save()
    leaving.delete_account(user, 'a-long-pass-123')
    user.refresh_from_db()
    assert user.google_sub is None
    with signed():                                                     # the same Google account is a newcomer again
        assert post().json() == {'code': 'google_signup', 'email': 'amina@example.org'}


def test_google_never_opens_a_staff_account(on):
    user = accounts.register(username='boss', email='amina@example.org', password='a-long-pass-123')
    user.is_staff = True
    user.save()
    with signed():
        r = post()
    user.refresh_from_db()
    assert r.status_code == 403 and codes(r) == [('login', 'staff')]
    assert user.google_sub is None and user.check_password('a-long-pass-123')


def test_when_google_gives_an_account_to_its_owner_the_squatters_tokens_and_connections_end(on):
    from apps.oauth.models import Client, Grant

    squatter = accounts.register(username='squatter', email='amina@example.org', password='a-long-pass-123')
    access = accounts.tokens_for(squatter)['access']
    client = Client.objects.create(client_id='https://assistant.example/client', kind='cimd', redirect_uris=[])
    grant = Grant.objects.create(user=squatter, client=client, scope='law:read', resource='http://localhost:5190/mcp')
    with signed():
        owner = post()
    assert owner.status_code == 200
    me = APIClient()
    me.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    assert me.get('/api/auth/me/').status_code == 401
    me.credentials(HTTP_AUTHORIZATION=f'Bearer {owner.json()["access"]}')
    assert me.get('/api/auth/me/').status_code == 200
    grant.refresh_from_db()
    assert grant.revoked_at is not None


def test_an_account_whose_address_moved_meanwhile_is_not_bound(on):
    from apps.accounts.services import google
    from apps.accounts.services.refusals import Refused

    found = accounts.register(username='amina', email='amina@example.org', password='a-long-pass-123')
    get_user_model().objects.filter(pk=found.pk).update(email='elsewhere@example.com')
    claims = {'sub': '1234567890', 'email': 'amina@example.org'}
    with pytest.raises(Refused) as refused:
        google.link(found, claims)
    assert refused.value.code == 'invalid'
    assert get_user_model().objects.get().google_sub is None


def test_an_address_changed_in_the_admin_unbinds_google_too(on, admin_client):
    # The same move made by staff on the account's admin page: the binding must not outlive the address there either.
    from apps.oauth.models import Client, Grant

    with signed():
        assert post(username='amina_k').status_code == 201
    user = get_user_model().objects.get(username='amina_k')
    assert user.google_sub
    client = Client.objects.create(client_id='https://assistant.example/client', kind='cimd',
                                   redirect_uris=['https://assistant.example/cb'])
    grant = Grant.objects.create(user=user, client=client, scope='law:read', resource='http://localhost:5190/mcp')
    page = admin_client.get(f'/admin/accounts/user/{user.pk}/change/')
    form = page.context['adminform'].form
    data = {name: form.initial.get(name) for name in form.fields if form.initial.get(name) not in (None, '')}
    data.update({'email': 'someone-else@example.com', 'groups': [], 'user_permissions': []})
    saved = admin_client.post(f'/admin/accounts/user/{user.pk}/change/', {k: v for k, v in data.items() if v is not False})
    assert saved.status_code == 302, saved.context and saved.context['adminform'].form.errors
    user.refresh_from_db()
    grant.refresh_from_db()
    assert user.email == 'someone-else@example.com' and user.google_sub is None and grant.revoked_at is not None
