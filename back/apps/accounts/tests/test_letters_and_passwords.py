"""Sign-up opened with real letters (3 Nov 2026): Resend, the address check, the brake on wrong passwords, the reset
link, a new password and a new address."""
import json
import re
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.services import addresses
from apps.accounts.services import mail as letters

pytestmark = pytest.mark.django_db

PASSWORD = 'daftar-maghribi-2026'
NEW = 'jdida-maghribia-2026'
STRIP = '‫‬'


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


def errors(response):
    return response.json()['errors']


def register(api, **overrides):
    body = {'username': 'salma', 'email': 'salma@example.org', 'password': PASSWORD}
    body.update(overrides)
    return api.post('/api/auth/register/', body, format='json')


def at(domain, local='reader'):
    """An address at a real provider, where the provider is what the test is about (a misspelt one, Gmail's dots).
    Every other address in these tests is at a reserved example domain."""
    return f'{local}@{domain}'


def signed_in(api, response):
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {response.json()["access"]}')
    return api


def sign_in(api, login, password, ip='203.0.113.7'):
    return api.post('/api/auth/token/', {'username': login, 'password': password}, format='json', REMOTE_ADDR=ip)


def code_of(message):
    return re.search(r'\b(\d{6})\b', message.body).group(1)


# ── Resend ───────────────────────────────────────────────────────────────────


class FakeResend:
    """requests.Session.request for anymail's Resend backend: keeps what was posted, answers `status`."""

    def __init__(self, status=200):
        self.status, self.posted = status, []

    def __call__(self, method, url, **kwargs):
        self.posted.append((method, url, json.loads(kwargs['data']), kwargs.get('headers', {})))
        response = mock.Mock(status_code=self.status, headers={}, text='{}', content=b'{}', reason='')
        response.json.return_value = {'id': 'f00d'} if self.status == 200 else {'message': 'nope'}
        return response


RESEND = {'EMAIL_BACKEND': 'anymail.backends.resend.EmailBackend',
          'ANYMAIL': {'RESEND_API_KEY': 're_test_key'},
          'DEFAULT_FROM_EMAIL': '3adala <noreply@mail.example.org>', 'SITE_URL': 'https://3adala.com'}


@override_settings(**RESEND)
def test_the_code_goes_through_resend_from_the_site_in_both_bodies(api):
    fake = FakeResend()
    with mock.patch('requests.Session.request', fake):
        r = register(api, email='Salma@Example.org')
    assert r.status_code == 201 and r.json()['code_sent'] is True
    [(method, url, payload, headers)] = fake.posted
    assert (method, url) == ('POST', 'https://api.resend.com/emails')
    assert headers['Authorization'] == 'Bearer re_test_key'
    assert payload['from'] == 'قانون المغرب <noreply@mail.example.org>'
    assert payload['to'] == ['salma@example.org']
    assert payload['subject'].startswith('‫') and payload['subject'].strip(STRIP).startswith('رمز تأكيد بريدك')
    code = re.search(r'\d{6}', payload['subject']).group(0)
    assert code in payload['text'] and 'salma' in payload['text']
    assert 'dir="rtl"' in payload['html'] and code in payload['html']
    # The account's own letters are not a list: no unsubscribe header, nothing tracked.
    assert 'List-Unsubscribe' not in (payload.get('headers') or {})
    assert '<img' not in payload['html']
    # Signed with the name and the address people type (8 Nov 2026), in both bodies.
    assert payload['text'].endswith('قانون المغرب · 3adala.com') and '>3adala.com</a>' in payload['html']


@override_settings(**RESEND)
def test_a_french_reader_gets_the_latin_name_and_a_left_to_right_letter(api):
    fake = FakeResend()
    with mock.patch('requests.Session.request', fake):
        register(api, preferred_language='fr')
    payload = fake.posted[0][2]
    assert payload['from'] == '3adala <noreply@mail.example.org>'
    assert payload['subject'].startswith('Votre code 3adala')
    # Signed with the address alone: in French the site's name is the address's own word.
    assert 'dir="ltr"' in payload['html'] and payload['text'].endswith('\n\n3adala.com')
    assert '>3adala.com</a></p>' in payload['html'] and '3adala · ' not in payload['html']


@override_settings(**RESEND)
def test_when_resend_refuses_the_sign_up_still_succeeds_and_says_the_code_did_not_go(api):
    with mock.patch('requests.Session.request', FakeResend(status=500)):
        r = register(api)
        assert r.status_code == 201 and r.json()['code_sent'] is False
        # Asking again says so; the next letter is not counted against the hour.
        asked = signed_in(api, r).post('/api/auth/email/code/')
    assert asked.status_code == 503 and errors(asked) == [{'field': 'email', 'code': 'not_sent'}]


def test_a_letter_that_cannot_go_never_fails_its_request(api, settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    settings.EMAIL_HOST, settings.EMAIL_PORT = '127.0.0.1', 9   # nothing listens there
    r = register(api)
    assert r.status_code == 201 and r.json()['code_sent'] is False
    user = get_user_model().objects.get()
    assert letters.send(user, 'password_changed') is False


def test_the_backend_is_resend_once_a_key_is_set(monkeypatch):
    import importlib

    import config.settings.base as base

    monkeypatch.setenv('RESEND_API_KEY', 're_x')
    monkeypatch.delenv('EMAIL_BACKEND', raising=False)
    try:
        assert importlib.reload(base).EMAIL_BACKEND == 'anymail.backends.resend.EmailBackend'
        monkeypatch.setenv('RESEND_API_KEY', '')
        assert importlib.reload(base).EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend'
    finally:
        monkeypatch.undo()
        importlib.reload(base)


# ── The address ──────────────────────────────────────────────────────────────


def test_a_misspelt_provider_is_answered_with_its_fix_until_the_person_keeps_theirs(api):
    r = register(api, email=at('gamil.com'))
    assert r.status_code == 400
    assert errors(r) == [{'field': 'email', 'code': 'typo', 'suggestion': at('gmail.com')}]
    kept = register(api, email=at('gamil.com'), email_confirmed=True)
    # Kept as typed, the account is made, but no code goes to a squatter's inbox.
    assert kept.status_code == 201 and kept.json()['code_sent'] is False
    assert mail.outbox == []
    asked = signed_in(api, kept).post('/api/auth/email/code/')
    assert errors(asked) == [{'field': 'email', 'code': 'unreachable'}]


def test_a_throwaway_inbox_is_refused_and_what_a_keyboard_slips_in_is_cleaned(api):
    assert errors(register(api, email='salma@yopmail.com')) == [{'field': 'email', 'code': 'disposable'}]
    assert errors(register(api, email='salma@x.test')) == [{'field': 'email', 'code': 'invalid'}]
    r = register(api, email='‏ Salma＠Example,org ')
    assert r.status_code == 201 and r.json()['user']['email'] == 'salma@example.org'


@pytest.mark.parametrize('typed, fix', [
    ('gamil.com', 'gmail.com'), ('gmail.con', 'gmail.com'), ('gmail.fr', 'gmail.com'), ('hotmial.fr', 'hotmail.fr'),
    ('gmailcom', 'gmail.com'), ('menara.com', 'menara.ma'), ('yahooo.fr', 'yahoo.fr'),
    ('hotmail.be', None), ('ymail.com', None), ('um5.ac.ma', None), ('menara.ma', None), ('outlook.sa', None),
])
def test_the_suggestions(typed, fix):
    assert addresses._misspelt(typed) == fix


# ── Signing in ───────────────────────────────────────────────────────────────


def test_a_wrong_password_and_a_misspelt_address_at_sign_in(api):
    register(api, email='salma@example.org')
    wrong = sign_in(api, 'salma', 'wrong-password')
    assert wrong.status_code == 401 and errors(wrong) == [{'field': 'login', 'code': 'wrong'}]
    typo = sign_in(api, at('gmial.com'), PASSWORD)
    assert typo.status_code == 401
    assert errors(typo) == [{'field': 'login', 'code': 'typo', 'suggestion': at('gmail.com')}]
    assert sign_in(api, 'SALMA@example.org', PASSWORD).status_code == 200


def test_ten_wrong_passwords_from_one_address_brake_that_address_alone(api, settings):
    register(api)
    for _ in range(settings.LOGIN_BRAKE_FAILURES - 1):
        assert sign_in(api, 'salma', 'wrong-password').status_code == 401
    locked = sign_in(api, 'salma', 'wrong-password')
    assert locked.status_code == 429 and errors(locked) == [{'field': 'login', 'code': 'locked', 'minutes': 15}]
    # Not even the right password from there; its holder elsewhere gets in.
    assert sign_in(api, 'salma', PASSWORD).status_code == 429
    assert sign_in(api, 'salma', PASSWORD, ip='198.51.100.9').status_code == 200


def test_the_password_asked_again_counts_with_the_brake(api, settings):
    me = signed_in(api, register(api))
    for _ in range(settings.LOGIN_BRAKE_FAILURES - 1):
        r = me.post('/api/auth/password/', {'password': 'nope-nope-1', 'new_password': NEW}, format='json')
        assert errors(r) == [{'field': 'password', 'code': 'invalid'}]
    r = me.post('/api/auth/password/', {'password': 'nope-nope-1', 'new_password': NEW}, format='json')
    assert r.status_code == 429 and errors(r)[0]['code'] == 'locked'
    assert me.post('/api/auth/me/delete/', {'password': PASSWORD}, format='json').status_code == 429


# ── The reset link ───────────────────────────────────────────────────────────


def _link(message):
    return dict(p.split('=', 1) for p in re.search(r'/reset#(\S+)', message.body).group(1).split('&'))


def test_a_forgotten_password_by_username_or_address_ends_in_a_new_one_and_a_session(api):
    first = register(api, email='salma@example.org').json()
    mail.outbox.clear()
    r = api.post('/api/auth/password/reset/', {'login': 'Salma'}, format='json')
    assert r.status_code == 200 and r.json() == {}
    [letter] = mail.outbox
    assert letter.to == ['salma@example.org'] and letter.subject.strip(STRIP) == 'كلمة سر جديدة لحسابك في «قانون المغرب»'
    assert 'http://localhost:5190/reset#u=' in letter.body and '3 ساعات' in letter.body
    link = _link(letter)
    assert api.post('/api/auth/password/reset/check/', {'uid': link['u'], 'token': link['t']},
                    format='json').json() == {'username': 'salma'}

    weak = api.post('/api/auth/password/reset/confirm/', {'uid': link['u'], 'token': link['t'], 'password': '123'},
                    format='json')
    assert errors(weak) == [{'field': 'password', 'code': 'password_too_short'}]
    done = api.post('/api/auth/password/reset/confirm/', {'uid': link['u'], 'token': link['t'], 'password': NEW},
                    format='json')
    assert done.status_code == 200 and done.json()['access'] and done.json()['user']['email_proven'] is True
    # The device that signed up is signed out; the link works once; the new password signs in.
    assert api.post('/api/auth/token/refresh/', {'refresh': first['refresh']}, format='json').status_code == 401
    again = api.post('/api/auth/password/reset/check/', {'uid': link['u'], 'token': link['t']}, format='json')
    assert errors(again) == [{'field': 'link', 'code': 'dead'}]
    assert sign_in(api, 'salma', NEW).status_code == 200
    assert mail.outbox[-1].subject.strip(STRIP) == 'تبدّلت كلمة سر حسابك في «قانون المغرب»'


def test_a_reset_says_plainly_what_it_cannot_do(api):
    register(api, email='salma@example.org')
    no_email = api.post('/api/auth/password/reset/', {'login': 'nobody@example.org'}, format='json')
    assert no_email.status_code == 404 and errors(no_email) == [{'field': 'login', 'code': 'no_email'}]
    no_name = api.post('/api/auth/password/reset/', {'login': 'nobody'}, format='json')
    assert errors(no_name) == [{'field': 'login', 'code': 'no_username'}]
    typo = api.post('/api/auth/password/reset/', {'login': at('gmal.com')}, format='json')
    assert errors(typo) == [{'field': 'login', 'code': 'typo', 'suggestion': at('gmail.com')}]
    bad = api.post('/api/auth/password/reset/check/', {'uid': 'MQ', 'token': 'abc-def'}, format='json')
    assert errors(bad) == [{'field': 'link', 'code': 'dead'}]


def test_reset_letters_wait_a_minute_and_stop_at_five_a_day_answered_as_sent(api, settings):
    register(api)
    mail.outbox.clear()
    for _ in range(3):
        assert api.post('/api/auth/password/reset/', {'login': 'salma'}, format='json').status_code == 200
    assert len(mail.outbox) == 1


def test_a_deleted_account_cannot_be_reset(api):
    me = signed_in(api, register(api))
    assert me.post('/api/auth/me/delete/', {'password': PASSWORD}, format='json').status_code == 204
    api.credentials()
    gone = get_user_model().objects.get()
    for login in (gone.username, gone.email, 'salma'):
        assert api.post('/api/auth/password/reset/', {'login': login}, format='json').status_code == 404


# ── A new password, a new address ────────────────────────────────────────────


def test_a_new_password_signs_the_other_devices_out_and_keeps_this_one(api):
    first = register(api).json()
    other = sign_in(api, 'salma', PASSWORD).json()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {first["access"]}')
    me = api
    weak = me.post('/api/auth/password/', {'password': PASSWORD, 'new_password': 'salma2026'}, format='json')
    assert errors(weak) == [{'field': 'new_password', 'code': 'password_too_similar'}]
    r = me.post('/api/auth/password/', {'password': PASSWORD, 'new_password': NEW}, format='json')
    assert r.status_code == 200 and r.json()['access'] and r.json()['refresh']
    refresh = lambda token: api.post('/api/auth/token/refresh/', {'refresh': token}, format='json').status_code
    assert refresh(other['refresh']) == 401 and refresh(first['refresh']) == 401
    assert refresh(r.json()['refresh']) == 200
    assert sign_in(api, 'salma', NEW).status_code == 200


def test_a_new_address_asks_the_password_waits_for_its_code_and_tells_the_old_one(api):
    me = signed_in(api, register(api, email='salma@example.org'))
    assert me.post('/api/auth/email/prove/', {'code': code_of(mail.outbox[0])}, format='json').status_code == 200
    mail.outbox.clear()
    register(api, username='karim', email='karim@example.org')
    mail.outbox.clear()

    def change(**body):
        return me.post('/api/auth/email/', body, format='json')

    assert errors(change(email=at('hotmial.com'), password=PASSWORD)) == [
        {'field': 'email', 'code': 'typo', 'suggestion': at('hotmail.com')}]
    assert errors(change(email='Karim@example.org', password=PASSWORD)) == [{'field': 'email', 'code': 'email_taken'}]
    assert errors(change(email='salma@example.net', password='nope')) == [{'field': 'password', 'code': 'invalid'}]
    assert mail.outbox == []

    r = change(email='Salma@Example.net', password=PASSWORD)
    assert r.status_code == 200 and r.json()['code_sent'] is True
    assert r.json()['user']['email'] == 'salma@example.net' and r.json()['user']['email_proven'] is False
    told, code = mail.outbox
    assert told.to == ['salma@example.org'] and 'salma@example.net' in told.body
    assert code.to == ['salma@example.net']
    proved = me.post('/api/auth/email/prove/', {'code': code_of(code)}, format='json')
    assert proved.json()['email_proven'] is True
    assert sign_in(api, 'salma@example.net', PASSWORD).status_code == 200
    assert sign_in(api, 'salma@example.org', PASSWORD).status_code == 401


def test_a_pending_reset_link_dies_with_the_address_it_went_to(api):
    me = signed_in(api, register(api))
    api.post('/api/auth/password/reset/', {'login': 'salma'}, format='json')
    link = _link(mail.outbox[-1])
    me.post('/api/auth/email/', {'email': 'salma2@example.org', 'password': PASSWORD}, format='json')
    r = api.post('/api/auth/password/reset/confirm/', {'uid': link['u'], 'token': link['t'], 'password': NEW},
                 format='json')
    assert errors(r) == [{'field': 'link', 'code': 'dead'}]


# ── Every password door shares the brake ─────────────────────────────────────


def _admin_sign_in(client, password, ip='203.0.113.7'):
    return client.post('/admin/login/', {'username': 'boss', 'password': password, 'next': '/admin/'}, REMOTE_ADDR=ip)


def _boss():
    return get_user_model().objects.create_user(username='boss', email='boss@example.org', password=PASSWORD,
                                                is_staff=True)


def test_the_admins_form_counts_wrong_passwords_and_holds_like_the_api(client, settings):
    _boss()
    refused = _admin_sign_in(client, 'wrong-password')
    words = refused.context['form'].non_field_errors()
    assert refused.status_code == 200 and words
    for _ in range(settings.LOGIN_BRAKE_FAILURES - 1):
        _admin_sign_in(client, 'wrong-password')
    # Held: the right password is refused too, with Django's own words, and no hash is spent on it.
    with mock.patch.object(get_user_model(), 'check_password') as checked:
        held = _admin_sign_in(client, PASSWORD)
    assert held.status_code == 200 and not checked.called
    assert held.context['form'].non_field_errors() == words
    # Elsewhere, the right password opens the admin.
    assert _admin_sign_in(client, PASSWORD, ip='198.51.100.9').status_code == 302


def test_the_api_and_the_admin_count_the_same_tries(api, client, settings):
    _boss()
    half = settings.LOGIN_BRAKE_FAILURES // 2
    for _ in range(half):
        _admin_sign_in(client, 'wrong-password')
    for _ in range(settings.LOGIN_BRAKE_FAILURES - half - 1):
        assert sign_in(api, 'boss', 'wrong-password').status_code == 401
    locked = sign_in(api, 'boss', 'wrong-password')
    assert locked.status_code == 429 and errors(locked) == [{'field': 'login', 'code': 'locked', 'minutes': 15}]
    assert _admin_sign_in(client, PASSWORD).status_code == 200


def test_a_staff_account_gets_no_reset_link(api):
    _boss()
    mail.outbox.clear()
    for login in ('boss', 'boss@example.org'):
        r = api.post('/api/auth/password/reset/', {'login': login}, format='json')
        assert r.status_code == 403 and errors(r) == [{'field': 'login', 'code': 'staff'}]
    assert mail.outbox == []


# ── Proving an address, while a new one lands ────────────────────────────────
# Each test reads the account, lets "another request" save a new address, then goes on with the copy it read: the
# order two requests sent half a second apart can take.


def test_a_code_proves_only_the_address_the_account_holds_now(api):
    from apps.accounts.services import codes
    from apps.accounts.services.refusals import Refused

    register(api)
    code = code_of(mail.outbox[0])
    stale = get_user_model().objects.get()
    get_user_model().objects.filter(pk=stale.pk).update(email='victim@example.org')   # another request's new address
    with pytest.raises(Refused):
        codes.prove(stale, code)
    fresh = get_user_model().objects.get()
    assert fresh.email == 'victim@example.org' and fresh.email_proven_at is None


def test_guesses_sent_together_each_spend_a_try(api):
    from apps.accounts.models import EmailCode
    from apps.accounts.services import codes
    from apps.accounts.services.refusals import Refused

    register(api)
    right = code_of(mail.outbox[0])
    wrong = '000000' if right != '000000' else '111111'
    user = get_user_model().objects.get()
    real, inside = codes.hmac.compare_digest, []

    def alongside(a, b):
        # While this guess is being compared, a second one arrives and is judged in full.
        if not inside:
            inside.append(1)
            with pytest.raises(Refused):
                codes.prove(get_user_model().objects.get(), wrong)
        return real(a, b)

    with mock.patch.object(codes.hmac, 'compare_digest', side_effect=alongside), pytest.raises(Refused):
        codes.prove(user, wrong)
    assert EmailCode.objects.get().tries == 2


def test_a_new_address_ends_every_live_code(api):
    from apps.accounts.services import accounts, codes
    from apps.accounts.services.refusals import Refused

    register(api)
    old_code = code_of(mail.outbox[0])
    user = get_user_model().objects.get()
    accounts.change_email(user, email='salma2@example.org')
    with pytest.raises(Refused):
        codes.prove(user, old_code)
    codes.prove(user, code_of(mail.outbox[-1]))
    assert get_user_model().objects.get().email_proven_at is not None


def test_a_reset_link_never_lands_on_an_address_the_account_moved_to(api):
    from django.contrib.auth.tokens import default_token_generator

    register(api)
    api.post('/api/auth/password/reset/', {'login': 'salma'}, format='json')
    link = _link(mail.outbox[-1])
    real = default_token_generator.check_token

    def moved_meanwhile(user, token):
        good = real(user, token)
        get_user_model().objects.filter(pk=user.pk).update(email='victim@example.org')
        return good

    with mock.patch.object(default_token_generator, 'check_token', side_effect=moved_meanwhile):
        r = api.post('/api/auth/password/reset/confirm/', {'uid': link['u'], 'token': link['t'], 'password': NEW},
                     format='json')
    assert errors(r) == [{'field': 'link', 'code': 'dead'}]
    fresh = get_user_model().objects.get()
    assert fresh.email_proven_at is None and fresh.check_password(PASSWORD)


# ── Sessions die with the password ───────────────────────────────────────────


def test_a_new_password_ends_the_old_access_tokens_at_once(api):
    old = register(api).json()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {old["access"]}')
    new = api.post('/api/auth/password/', {'password': PASSWORD, 'new_password': NEW}, format='json').json()
    assert api.get('/api/auth/me/').status_code == 401
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {new["access"]}')
    assert api.get('/api/auth/me/').status_code == 200


def test_a_refresh_token_made_under_another_password_is_refused(api):
    session = register(api).json()
    user = get_user_model().objects.get()
    user.set_password(NEW)          # as the admin's form sets one: no session is ended by it
    user.save()
    r = api.post('/api/auth/token/refresh/', {'refresh': session['refresh']}, format='json')
    assert r.status_code == 401


def test_asked_by_username_the_reset_names_no_address_asked_by_address_it_shows_it_back_masked(api):
    # Usernames are public; an address's domain (an employer's, a firm's) can name the person behind one.
    register(api, email='karima@cabinet-x.example.org', username='karima')
    by_name = api.post('/api/auth/password/reset/', {'login': 'karima'}, format='json')
    assert by_name.status_code == 200 and by_name.json() == {} and 'cabinet' not in by_name.content.decode()
    cache.clear()
    by_address = api.post('/api/auth/password/reset/', {'login': 'Karima@cabinet-x.example.org'}, format='json')
    assert by_address.json() == {'to': 'ka•••@cabinet-x.example.org'}
    user = get_user_model().objects.get()
    get_user_model().objects.filter(pk=user.pk).update(email='karima@gamil.com')   # a misspelt provider
    unreachable = api.post('/api/auth/password/reset/', {'login': 'karima'}, format='json')
    assert unreachable.status_code == 409 and errors(unreachable) == [{'field': 'login', 'code': 'unreachable'}]


# ── The mailer and the lock, turned on other people ──────────────────────────


def test_an_inbox_gets_three_codes_a_day_whichever_account_asks(api, settings):
    settings.ACCOUNT_MAIL_PER_ADDRESS = 3
    me = signed_in(api, register(api, email=at('gmail.com', 'victim')))
    assert me.post('/api/auth/email/code/').status_code == 204
    assert me.post('/api/auth/email/code/').status_code == 204
    fourth = me.post('/api/auth/email/code/')
    assert fourth.status_code == 429 and errors(fourth) == [{'field': 'email', 'code': 'too_many_today'}]
    # Another account on the same inbox, by Gmail's dots and a «+tag», is no way around it.
    other = register(APIClient(), username='other', email=at('gmail.com', 'v.ictim+news'))
    assert other.status_code == 201 and other.json()['code_sent'] is False
    assert len(mail.outbox) == 3 and {m.to[0] for m in mail.outbox} == {at('gmail.com', 'victim')}


def test_an_inbox_gets_three_reset_letters_a_day_answered_as_sent_past_them(api, settings):
    settings.ACCOUNT_MAIL_PER_ADDRESS = 3
    for n in range(4):
        register(APIClient(), username=f'salma{n}', email=f'salma+{n}@example.org')
    mail.outbox.clear()
    for n in range(4):
        r = api.post('/api/auth/password/reset/', {'login': f'salma{n}'}, format='json')
        assert r.status_code == 200
    assert len(mail.outbox) == 3


TURNSTILE = {'TURNSTILE_SITE_KEY': 'site-key', 'TURNSTILE_SECRET_KEY': 'secret-key'}


def _lock(api, settings, login='salma'):
    for n in range(settings.LOGIN_BRAKE_ACCOUNT_FAILURES):
        sign_in(api, login, 'wrong-password', ip=f'203.0.113.{n % 250}')


def test_past_the_threshold_turnstile_lets_the_right_password_in(api, settings):
    settings.LOGIN_BRAKE_FAILURES = 1000          # only the account's level, from everywhere
    register(api)
    _lock(api, settings)
    with override_settings(**TURNSTILE), mock.patch('apps.corpus.services.reading.verify', return_value=True) as cf:
        asked = sign_in(api, 'salma', PASSWORD)
        assert asked.status_code == 429
        assert errors(asked) == [{'field': 'login', 'code': 'check', 'minutes': 15, 'sitekey': 'site-key'}]
        assert not cf.called                      # no token, no question to Cloudflare
        wrong = api.post('/api/auth/token/', {'username': 'salma', 'password': 'wrong-password', 'check': 'tok'},
                         format='json', REMOTE_ADDR='198.51.100.9')
        assert wrong.status_code == 401 and errors(wrong) == [{'field': 'login', 'code': 'wrong'}]
        right = api.post('/api/auth/token/', {'username': 'salma', 'password': PASSWORD, 'check': 'tok'},
                         format='json', REMOTE_ADDR='198.51.100.9')
        assert right.status_code == 200 and right.json()['access']
        assert cf.call_count == 2
    with override_settings(**TURNSTILE), mock.patch('apps.corpus.services.reading.verify', return_value=False):
        failed = api.post('/api/auth/token/', {'username': 'salma', 'password': PASSWORD, 'check': 'bad'},
                          format='json')
        assert failed.status_code == 429 and errors(failed)[0]['code'] == 'check'


def test_without_turnstile_the_lock_refuses_as_before(api, settings):
    settings.LOGIN_BRAKE_FAILURES = 1000
    register(api)
    _lock(api, settings)
    r = api.post('/api/auth/token/', {'username': 'salma', 'password': PASSWORD, 'check': 'tok'}, format='json')
    assert r.status_code == 429 and errors(r) == [{'field': 'login', 'code': 'locked', 'minutes': 15}]


def test_the_open_doors_read_json_only(api):
    register(api)
    mail.outbox.clear()
    for url, body in (('/api/auth/token/', {'username': 'salma', 'password': PASSWORD}),
                      ('/api/auth/register/', {'username': 'karim', 'email': 'karim@example.org', 'password': PASSWORD}),
                      ('/api/auth/password/reset/', {'login': 'salma'}),
                      ('/api/auth/token/refresh/', {'refresh': 'x'}),
                      ('/api/auth/logout/', {'refresh': 'x'})):
        # What a form on another site sends: form-encoded, or the browser's multipart.
        for sent in (api.post(url, body), api.post(url, body, content_type='application/x-www-form-urlencoded')):
            assert sent.status_code == 415, url
            assert errors(sent) == [{'field': 'body', 'code': 'unsupported_media_type'}]
    assert get_user_model().objects.count() == 1 and mail.outbox == []


# ── A refresh is not a sign-in ───────────────────────────────────────────────


def test_a_refresh_has_its_own_bucket_counted_by_account(api):
    from rest_framework.throttling import SimpleRateThrottle

    salma = register(api).json()
    karim = register(APIClient(), username='karim', email='karim@example.org').json()
    refresh = lambda client, token: client.post('/api/auth/token/refresh/', {'refresh': token},
                                                format='json', REMOTE_ADDR='203.0.113.7')
    with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'auth': '2/min', 'refresh': '1/min'}):
        # Behind one address, someone spends the sign-in's bucket with wrong passwords…
        for _ in range(3):
            sign_in(api, 'nobody', 'wrong-password')
        assert sign_in(api, 'nobody', 'wrong-password').status_code == 429
        # …and the readers there still refresh, each in their own account's bucket.
        assert refresh(APIClient(), salma['refresh']).status_code == 200
        assert refresh(APIClient(), karim['refresh']).status_code == 200
        again = refresh(APIClient(), karim['refresh'])
        assert again.status_code == 429


@pytest.mark.parametrize('sender, refused', [
    ('3adala <noreply@localhost>', True),           # the default: a copy of the code that never set its own
    ('noreply@LOCALHOST', True),
    ('nobody', True),
    ('example <noreply@mail.example.org>', False),
])
def test_a_deploy_refuses_letters_from_no_real_address(settings, sender, refused):
    from django.core.checks import run_checks
    settings.DEFAULT_FROM_EMAIL = sender
    errors = [e for e in run_checks(include_deployment_checks=True) if e.id == 'accounts.E002']
    assert bool(errors) == refused
    assert all(e.level >= 40 and 'DEFAULT_FROM_EMAIL' in e.msg for e in errors)
