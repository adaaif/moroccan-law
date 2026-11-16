"""Every limit counts by one address (OP16 of the open-source audit): an IPv4 address whole, an IPv6 one by its /64.
A line or a phone holds a whole /64; counting each of its 2^64 addresses apart gave each a fresh allowance."""
import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from apps.accounts.services import brake
from apps.opendata.throttles import ByNetwork, address, bucket, ident

pytestmark = pytest.mark.django_db
BEHIND_NGINX = {**settings.REST_FRAMEWORK, 'NUM_PROXIES': 1}


def test_an_ipv6_address_counts_by_its_64_and_an_ipv4_one_whole():
    assert bucket('2001:db8:1:2:3:4:5:6') == '2001:db8:1:2::/64'
    assert bucket('2001:db8:1:2:3:4:5:6', v6=56) == '2001:db8:1::/56'
    assert bucket('105.155.1.2') == '105.155.1.2'
    assert bucket('::ffff:105.155.1.2') == '105.155.1.2'      # an IPv4 address written as IPv6 is that address
    assert bucket('') == '-' and bucket('not an address') == 'not an address'


@override_settings(REST_FRAMEWORK=BEHIND_NGINX)
def test_the_address_counted_is_the_one_nginx_appended_folded():
    request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='9.9.9.9, 2001:db8:1:2:aaaa::1', REMOTE_ADDR='127.0.0.1')
    assert ident(request) == '2001:db8:1:2::/64'           # never the address a client wrote first
    assert brake.address(request) == '2001:db8:1:2::/64'    # the sign-in brake counts the same


def test_the_readers_address_is_cloudflares_else_the_last_one_nginx_appended():
    """What the day of reading and the crawlers' check read: Cloudflare's view of the reader, else the last address of
    X-Forwarded-For, else the connection's own; as sent, so a malformed one reaches the lookups that refuse it."""
    rf = RequestFactory()
    assert address(rf.get('/', HTTP_CF_CONNECTING_IP=' 105.155.1.2 ', HTTP_X_FORWARDED_FOR='9.9.9.9, 127.0.0.1')) == '105.155.1.2'
    assert address(rf.get('/', HTTP_X_FORWARDED_FOR='9.9.9.9, 105.155.1.3 ')) == '105.155.1.3'
    assert address(rf.get('/', REMOTE_ADDR='105.155.1.4')) == '105.155.1.4'
    assert address(rf.get('/', HTTP_CF_CONNECTING_IP='not an address')) == 'not an address'


@override_settings(REST_FRAMEWORK=BEHIND_NGINX)
def test_changing_the_last_64_bits_gives_no_new_allowance(api, settings):
    settings.PUBLIC_API_RATES = {'anonymous': '2/min'}
    cache.clear()
    asked = [api.get('/api/corpus/shelf/', HTTP_X_FORWARDED_FOR=f'2001:db8:1:2:{k:x}::1').status_code for k in range(3)]
    assert asked == [200, 200, 429]
    assert api.get('/api/corpus/shelf/', HTTP_X_FORWARDED_FOR='2001:db8:1:3::1').status_code == 200   # the next line
    cache.clear()


@override_settings(REST_FRAMEWORK=BEHIND_NGINX)
def test_the_reports_limit_counts_a_line_not_an_address(api):
    from apps.quality.api.views import ReportCreate
    throttle = ReportCreate().get_throttles()[0]
    one = RequestFactory().post('/', HTTP_X_FORWARDED_FOR='2001:db8:1:2::1')
    other = RequestFactory().post('/', HTTP_X_FORWARDED_FOR='2001:db8:1:2:ffff:ffff:ffff:ffff')
    assert throttle.get_ident(one) == throttle.get_ident(other) == '2001:db8:1:2::/64'


def _views(patterns):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _views(p.url_patterns)
        elif isinstance(p, URLPattern) and isinstance(getattr(p.callback, 'cls', None), type) \
                and issubclass(p.callback.cls, APIView):
            yield p.callback.cls


def test_every_limit_of_the_api_counts_by_the_same_address():
    """A new throttle that counts an address whole would undo the rest: each one is ByNetwork."""
    seen = 0
    for view in _views(get_resolver().url_patterns):
        for throttle in view.throttle_classes:
            seen += 1
            assert not issubclass(throttle, BaseThrottle) or issubclass(throttle, ByNetwork), (view, throttle)
    assert seen > 20


APART = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'apart-default'},
         'answers': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'apart-answers'},
         'counters': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'apart-counters'}}


@pytest.fixture
def apart():
    from django.core.cache import caches
    with override_settings(CACHES=APART):
        for name in APART:
            caches[name].clear()
        yield caches
        for name in APART:
            caches[name].clear()


def test_the_counts_live_apart_from_the_answers_and_never_go_with_them(api, apart, settings):
    """OP18: the counts shared one evicting store with the kept answers; an evicted count started again from zero."""
    from apps.corpus.services import reading
    from apps.corpus.tests.test_perf import law
    law('31-08', articles=50)
    settings.READING_BUDGET = 40
    settings.PUBLIC_API_RATES = {'anonymous': '3/min'}
    reader = {'HTTP_CF_CONNECTING_IP': '105.155.1.2', 'HTTP_X_FORWARDED_FOR': '105.155.1.2'}
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'window': 40}, **reader).status_code == 200
    counted = set(apart['counters']._cache)
    assert any('reading:' in k for k in counted) and any('throttle_public_' in k for k in counted)
    assert not any('reading:' in k or 'throttle_' in k for k in apart['default']._cache)
    # The answers' store and the default one emptied (a flood of large answers): the counts stand.
    apart['answers'].clear()
    apart['default'].clear()
    assert api.get('/api/corpus/at/ma/loi/31-08/', {'window': 1}, **reader).status_code == 429
    assert reading.reached(RequestFactory().get('/', HTTP_CF_CONNECTING_IP='105.155.1.2'))


def test_the_brake_the_shares_and_the_gate_count_apart_too(apart):
    from apps.gate.services import gate
    from apps.mcp.services import quotas
    brake.cache.set('brake:probe', 1)
    quotas.cache.set('mcp:probe', 1)
    gate.cache.set('gate:probe', 1)
    assert {k.rsplit(':', 1)[-1] for k in apart['counters']._cache} >= {'probe'} and len(apart['counters']._cache) == 3
    assert not apart['default']._cache


def test_without_a_store_of_their_own_the_counts_are_the_default_caches(settings):
    from config.caching import counters
    from config.settings.base import redis_caches
    from django.core.cache import caches
    assert 'counters' not in settings.CACHES
    counters.set('probe', 1)
    assert caches['default'].get('probe') == 1
    caches['default'].delete('probe')
    assert set(redis_caches('redis://r:6381/0', 'law')) == {'default', 'answers'}
    both = redis_caches('redis://r:6381/0', 'law', 'redis://r:6382/0')
    assert both['counters']['LOCATION'] == 'redis://r:6382/0' and both['counters']['KEY_PREFIX'] == 'law:counters'
    assert both['default']['LOCATION'] == both['answers']['LOCATION'] == 'redis://r:6381/0'
