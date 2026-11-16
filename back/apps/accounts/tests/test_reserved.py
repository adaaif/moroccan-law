"""The names the code keeps for its own accounts (demo-, load-, deleted-): nobody may choose one, a deploy refuses a
server where one is switched on, and one command switches them off."""
from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.checks import run_checks
from django.core.exceptions import ValidationError
from django.core.management import call_command
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

from apps.accounts.services import accounts

pytestmark = pytest.mark.django_db
PASSWORD = 'daftar-maghribi-2026'


def codes(r):
    return {(e['field'], e['code']) for e in r.json()['errors']}


@pytest.mark.parametrize('name', ['demo-salma', 'Demo-Salma', 'load-001', 'deleted-12'])
def test_a_reserved_prefix_cannot_be_chosen_at_sign_up(api, name):
    r = api.post('/api/auth/register/', {'username': name, 'email': 'salma@example.org', 'password': PASSWORD},
                 format='json')
    assert r.status_code == 400 and codes(r) == {('username', 'reserved')}
    assert not get_user_model().objects.exists()
    # A name that only holds the word is a name like any other.
    assert api.post('/api/auth/register/', {'username': 'salma-demo', 'email': 'salma@example.org',
                                            'password': PASSWORD}, format='json').status_code == 201


def test_nor_with_google(settings):
    settings.GOOGLE_OAUTH_CLIENT_ID = 'web'
    settings.GOOGLE_OAUTH_CLIENT_IDS = ['web']
    claims = {'iss': 'https://accounts.google.com', 'aud': 'web', 'sub': '42', 'email': 'amina@example.org',
              'email_verified': True, 'nonce': 'n1'}
    with mock.patch('google.oauth2.id_token.verify_oauth2_token', return_value=claims):
        r = APIClient().post('/api/auth/google/', {'credential': 't', 'nonce': 'n1', 'username': 'demo-amina'},
                             format='json')
    assert r.status_code == 400 and codes(r) == {('username', 'reserved')}


def test_nor_at_a_rename_in_the_admin_but_an_account_keeps_its_own():
    user = accounts.register(username='salma', email='salma@example.org', password=PASSWORD)
    user.username = 'demo-salma'
    with pytest.raises(ValidationError) as refused:
        user.full_clean()
    assert refused.value.error_dict['username'][0].code == 'reserved'
    demo = get_user_model().objects.create_user(username='demo-karim', email='demo-karim@demo.law.invalid')
    demo.is_active = False
    demo.full_clean()                       # switching a demo account off in the admin still saves


def _deploy_errors():
    return [e for e in run_checks(include_deployment_checks=True) if e.id == 'accounts.E001']


def test_a_deploy_refuses_an_active_reserved_account():
    User = get_user_model()
    User.objects.create_user(username='salma', email='salma@example.org', password=PASSWORD)
    User.objects.create_user(username='deleted-3', email='deleted-3@deleted.invalid', is_active=False)
    assert _deploy_errors() == []
    tester = User.objects.create_user(username='e2e1', email='e2e1@demo.law.invalid', password=PASSWORD)
    assert len(_deploy_errors()) == 1
    tester.is_active = False
    tester.save()
    User.objects.create_user(username='demo-staff', email='demo-staff@demo.law.invalid', password=PASSWORD)
    [error] = _deploy_errors()
    assert error.level >= 40 and '1 active' in error.msg


def test_the_command_lists_then_switches_the_reserved_accounts_off():
    from apps.discussion.models import Reviewer
    from apps.oauth.models import Client, Grant

    User = get_user_model()
    owner = User.objects.create_user(username='salma', email='salma@example.org', password=PASSWORD, is_staff=True)
    staff = User.objects.create_user(username='demo-staff', email='demo-staff@demo.law.invalid', password=PASSWORD,
                                     is_staff=True, is_superuser=True)
    karim = User.objects.create_user(username='demo-karim', email='demo-karim@demo.law.invalid', password=PASSWORD)
    gone = User.objects.create_user(username='deleted-9', email='deleted-9@deleted.invalid', is_active=False)
    staff.groups.add(Group.objects.create(name='editors'))
    Reviewer.objects.create(user=karim, appointed_by=staff)
    accounts.tokens_for(karim)
    client = Client.objects.create(client_id='https://assistant.example/c', kind='cimd', redirect_uris=[])
    Grant.objects.create(user=karim, client=client, scope='law:read', resource='http://localhost:5190/mcp')

    out = StringIO()
    call_command('retire_reserved_accounts', stdout=out)
    assert 'demo-staff' in out.getvalue() and 'demo-karim' in out.getvalue() and 'deleted-9' not in out.getvalue()
    assert '2 of 3 reserved' in out.getvalue()
    staff.refresh_from_db()
    assert staff.is_active and staff.has_usable_password()        # a dry run changes nothing

    call_command('retire_reserved_accounts', '--write', stdout=StringIO())
    for user in (staff, karim):
        user.refresh_from_db()
        assert not user.is_active and not user.has_usable_password()
        assert not user.is_staff and not user.is_superuser and not user.groups.exists()
    assert not Reviewer.objects.filter(user=karim, ended_at=None).exists()
    assert hasattr(OutstandingToken.objects.get(user=karim), 'blacklistedtoken')
    assert Grant.objects.get(user=karim).revoked_at is not None
    owner.refresh_from_db()
    gone.refresh_from_db()
    assert owner.is_active and owner.is_staff and owner.check_password(PASSWORD)
    assert _deploy_errors() == []
    again = StringIO()
    call_command('retire_reserved_accounts', '--write', stdout=again)
    assert '0 of 3 reserved' in again.getvalue()


def test_the_demo_seed_writes_no_password_in_the_code_and_sets_the_one_it_prints():
    from django.contrib.auth.hashers import make_password

    from apps.discussion.management.commands import seed_demo_talk

    assert not hasattr(seed_demo_talk, 'PASSWORD')
    seed = seed_demo_talk.Command()
    seed.password = make_password('drawn-for-this-run')
    first = seed.person('tester', 'سارة', 'f', 'ar')
    seed.password = make_password('drawn-again')
    again = seed.person('tester', 'سارة', 'f', 'ar')
    assert first.pk == again.pk and again.check_password('drawn-again')


def test_the_older_development_addresses_move_to_the_plain_domains_in_one_update_each(django_assert_num_queries):
    """Migration 0006: each older domain's rows rewritten by one UPDATE, whatever the domain's letter case, the part
    before the @ kept; a person's address untouched; and back."""
    import importlib

    from django.apps import apps

    from apps.accounts.models import reserved_accounts

    move = importlib.import_module('apps.accounts.migrations.0006_reserved_domains_law')
    User = get_user_model()
    older = {'demo-karim': 'demo-karim@demo.matn.invalid', 'e2e1': 'e2e1@Demo.Matn.Invalid',
             'load-001': 'load-001@load.matn.invalid', 'salma': 'salma.matn.invalid@example.org'}
    for username, email in older.items():
        User.objects.create_user(username=username, email=email)
    with django_assert_num_queries(2):
        move.forward(apps, None)
    emails = dict(User.objects.values_list('username', 'email'))
    assert emails == {'demo-karim': 'demo-karim@demo.law.invalid', 'e2e1': 'e2e1@demo.law.invalid',
                      'load-001': 'load-001@load.law.invalid', 'salma': 'salma.matn.invalid@example.org'}
    assert set(User.objects.filter(reserved_accounts()).values_list('username', flat=True)) == {
        'demo-karim', 'e2e1', 'load-001'}
    with django_assert_num_queries(2):
        move.backward(apps, None)
    assert dict(User.objects.values_list('username', 'email')) == {**older, 'e2e1': 'e2e1@demo.matn.invalid'}
