"""The password in front of the whole site (25 Oct 2026): nothing without it, the cookie after it."""
import pytest
from django.core.cache import cache

from apps.gate.services import gate

FAKE = 'not-the-real-password'       # never the one a site used


@pytest.fixture
def locked(settings):
    settings.GATE_PASSWORD = FAKE
    cache.clear()


@pytest.mark.django_db
def test_no_password_set_means_no_gate(client):
    assert client.get('/gate/check/').status_code == 204
    assert 'X-Robots-Tag' not in client.get('/api/corpus/issues/')


@pytest.mark.django_db
def test_without_the_cookie_the_api_is_refused_in_the_one_error_shape_and_a_page_leads_to_the_gate(client, locked):
    r = client.get('/api/corpus/issues/')
    assert r.status_code == 401 and r.json() == {'errors': [{'field': 'gate', 'code': 'locked'}]}
    assert r['X-Robots-Tag'] == 'noindex, nofollow'
    r = client.get('/admin/?x=1')
    assert r.status_code == 302 and r['Location'] == '/gate/?next=%2Fadmin%2F%3Fx%3D1'
    assert client.get('/gate/check/').status_code == 401
    assert client.get('/gate/').status_code == 200


@pytest.mark.django_db
def test_the_password_gives_the_cookie_and_leads_back_where_the_reader_was_going(client, locked):
    r = client.post('/gate/', {'password': 'maroc2030', 'next': '/ma/loi/67-12'})
    assert r.status_code == 200 and 'كلمة السر غير صحيحة' in r.content.decode()
    r = client.post('/gate/', {'password': FAKE, 'next': '/ma/loi/67-12'})
    assert r.status_code == 302 and r['Location'] == '/ma/loi/67-12'
    assert r.cookies[gate.COOKIE]['httponly'] and r.cookies[gate.COOKIE]['max-age'] == 30 * 86400
    assert client.get('/gate/check/').status_code == 204
    assert client.get('/api/corpus/issues/').status_code == 200


@pytest.mark.django_db
def test_the_gate_never_leads_elsewhere_and_a_changed_password_voids_the_cookie(client, locked, settings):
    assert client.post('/gate/', {'password': FAKE, 'next': 'https://evil.example/'})['Location'] == '/'
    assert client.post('/gate/', {'password': FAKE, 'next': '//evil.example/'})['Location'] == '/'
    settings.GATE_PASSWORD = 'another one'
    assert client.get('/gate/check/').status_code == 401


@pytest.mark.django_db
def test_ten_wrong_passwords_make_an_address_wait(client, locked):
    for _ in range(gate.TRIES):
        client.post('/gate/', {'password': 'guess'})
    r = client.post('/gate/', {'password': FAKE})
    assert r.status_code == 429 and gate.COOKIE not in r.cookies


@pytest.mark.django_db
def test_the_cookie_says_nothing_of_the_password(client, locked, settings):
    import hashlib

    from django.core import signing

    r = client.post('/gate/', {'password': FAKE})
    value = r.cookies[gate.COOKIE].value
    assert value.split(':')[0] == gate.ADMITTED                     # a constant, signed
    assert hashlib.sha256(FAKE.encode()).hexdigest()[:16] not in value
    # The old ticket, the password's hash signed with SECRET_KEY alone, no longer opens the gate.
    old = signing.TimestampSigner(salt='law.gate').sign(hashlib.sha256(FAKE.encode()).hexdigest()[:16])
    client.cookies[gate.COOKIE] = old
    assert client.get('/gate/check/').status_code == 401
    # A cookie signed under another secret, the same password, opens nothing.
    client.cookies[gate.COOKIE] = value
    assert client.get('/gate/check/').status_code == 204
    settings.SECRET_KEY = 'another secret ' * 4
    assert client.get('/gate/check/').status_code == 401


@pytest.mark.django_db
def test_an_ipv6_visitor_is_counted_by_its_64(client, locked):
    for n in range(gate.TRIES):
        client.post('/gate/', {'password': 'guess'}, HTTP_X_FORWARDED_FOR=f'2001:db8:1:2::{n + 1:x}')
    assert client.post('/gate/', {'password': FAKE}, HTTP_X_FORWARDED_FOR='2001:db8:1:2:ffff::1').status_code == 429
    assert client.post('/gate/', {'password': FAKE}, HTTP_X_FORWARDED_FOR='2001:db8:1:3::1').status_code == 302
