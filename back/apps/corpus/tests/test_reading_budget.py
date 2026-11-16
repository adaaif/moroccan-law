"""A day of reading per reader (4 Nov 2026): no one client copies the whole corpus in a day."""
from datetime import date
from unittest import mock

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services import reading
from apps.opendata.throttles import bucket
from config.caching import counters

pytestmark = pytest.mark.django_db
READER = {'HTTP_CF_CONNECTING_IP': '105.155.1.2', 'HTTP_X_FORWARDED_FOR': '105.155.1.2, 127.0.0.1'}
NEIGHBOUR = {'HTTP_CF_CONNECTING_IP': '105.155.1.3', 'HTTP_X_FORWARDED_FOR': '105.155.1.3, 127.0.0.1'}


def counted(ip: str = '105.155.1.2') -> int:
    """What the day of reading has counted today for an address: every browser and every request without the cookie
    behind it together (its ceiling's count)."""
    return counters.get(reading._key(f'all:{bucket(ip, v6=reading.V6)}')) or 0


@pytest.fixture(autouse=True)
def fresh():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def code():
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='مدونة الأسرة')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2004, 2, 5), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.bulk_create([Article(version=v, order=k, label=f'المادة {k}', number=str(k), eid=f'art_{k}',
                                         body=f'نص المادة {k}') for k in range(1, 101)])
    return text


@override_settings(READING_BUDGET=100)
def test_a_reader_is_given_a_window_and_a_day_then_told_to_come_back(api, code):
    r = api.get('/api/corpus/at/ma/loi/70-03/', **READER)
    assert r.status_code == 200 and r.json()['range'] == [0, 80]      # never a long text whole
    assert api.get('/api/corpus/at/ma/loi/70-03/?from=80&count=40', **READER).json()['range'] == [80, 100]
    r = api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER)
    assert r.status_code == 429 and r.json() == {'errors': [{'field': 'reading', 'code': 'limit'}]}
    assert r['Cache-Control'] == 'no-store' and int(r['Retry-After']) >= 60
    assert api.get('/api/corpus/preview/?path=/ma/loi/70-03/art_1', **READER).status_code == 429
    # Another browser has its own day, behind the same address too (HM17: a mobile IPv4 holds many subscribers).
    from rest_framework.test import APIClient
    assert APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **NEIGHBOUR).status_code == 200
    assert APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **READER).status_code == 200


@override_settings(READING_BUDGET=10)
def test_what_counts_is_what_an_answer_gives(api, code):
    for k in range(1, 10):
        assert api.get(f'/api/corpus/preview/?path=/ma/loi/70-03/art_{k}', **READER).status_code == 200
    assert api.get('/api/corpus/preview/?path=/ma/loi/70-03', **READER).status_code == 200    # a text's: no article
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=1', **READER).status_code == 200
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=1', **READER).status_code == 429
    assert api.get(f'/api/corpus/texts/{code.pk}/', **READER).status_code == 429


@override_settings(READING_BUDGET=5)
def test_the_servers_own_requests_are_not_counted_and_read_a_text_whole(api, code):
    # The prerender through its tunnel, a job through nginx: the reader's address is the machine's.
    for _ in range(3):
        r = api.get('/api/corpus/at/ma/loi/70-03/', HTTP_X_FORWARDED_FOR='127.0.0.1')
        assert r.status_code == 200 and r.json()['range'] == [0, 100]
    assert api.get('/api/corpus/texts/').status_code == 200


def test_the_list_of_every_text_is_the_servers_own(api, code):
    r = api.get('/api/corpus/texts/', **READER)
    assert r.status_code == 403 and r.json() == {'errors': [{'field': 'texts', 'code': 'internal'}]}


def test_an_old_id_address_gives_the_texts_facts_not_the_text(api, code):
    r = api.get(f'/api/corpus/texts/{code.pk}/', **READER)
    assert r.status_code == 200 and r.json()['path'] == '/ma/loi/70-03' and len(r.json()['articles']) == 1


@override_settings(READING_BUDGET=80, TURNSTILE_SITE_KEY='site', TURNSTILE_SECRET_KEY='secret')
def test_past_the_day_a_person_passes_the_check_and_is_given_a_day_of_their_own(api, code):
    assert api.get('/api/corpus/at/ma/loi/70-03/', **READER).status_code == 200
    r = api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER)
    assert r.status_code == 429 and r.json()['errors'][0]['code'] == 'check'
    assert api.get('/api/corpus/reading/', **READER).json() == {'check': 'site', 'reached': True}
    from rest_framework.test import APIClient
    assert APIClient().get('/api/corpus/reading/', **NEIGHBOUR).json() == {'check': 'site', 'reached': False}
    with mock.patch.object(reading, 'verify', return_value=False):
        assert api.post('/api/corpus/reading/', {'token': 'x'}, format='json', **READER).status_code == 400
    with mock.patch.object(reading, 'verify', return_value=True):
        r = api.post('/api/corpus/reading/', {'token': 'x'}, format='json', **READER)
    assert r.status_code == 204 and r.cookies[reading.COOKIE]['httponly']
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER).status_code == 200      # the cookie's day
    api.cookies[reading.COOKIE] = 'forged'
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER).status_code == 429


@override_settings(READING_BUDGET=80, READING_PASSES=2, TURNSTILE_SITE_KEY='site', TURNSTILE_SECRET_KEY='secret')
def test_a_pass_is_given_only_past_the_day_and_a_few_an_address(code):
    """OP17: a pass went to anyone who solved a check, also before any limit, and was bound to nothing: 218 passes
    were the whole corpus."""
    from rest_framework.test import APIClient
    with mock.patch.object(reading, 'verify', return_value=True) as verify:
        r = APIClient().post('/api/corpus/reading/', {'token': 'x'}, format='json', **READER)
        assert r.status_code == 400 and r.json() == {'errors': [{'field': 'reading', 'code': 'not_reached'}]}
        assert not verify.called
        passed = []
        for _ in range(3):                  # three browsers behind one address, each past its own day
            browser = APIClient()
            assert browser.get('/api/corpus/at/ma/loi/70-03/', {'window': 80}, follow=True, **READER).status_code == 200
            assert browser.get('/api/corpus/at/ma/loi/70-03/', {'window': 1}, **READER).status_code == 429
            passed.append(browser.post('/api/corpus/reading/', {'token': 'x'}, format='json', **READER).status_code)
        assert passed == [204, 204, 429] and verify.call_count == 2
        assert browser.post('/api/corpus/reading/', ['x'], format='json', **READER).status_code == 400


def test_without_the_check_there_is_no_pass_to_get(api):
    assert api.get('/api/corpus/reading/').json() == {'check': '', 'reached': False}
    r = api.post('/api/corpus/reading/', {'token': 'x'}, format='json', **READER)
    assert r.status_code == 400 and r.json()['errors'][0]['code'] == 'limit'


@pytest.mark.parametrize('query, field', [
    ('window=-1', 'window'), ('window=0', 'window'), ('window=81', 'window'), ('window=²', 'window'),
    ('window=1_0', 'window'), ('from=-1', 'from'), ('from=0&count=0', 'count'), ('from=0&count=-1', 'count'),
    ('from=0&count=81', 'count'), ('count=-5', 'count'), ('on=yesterday', 'on')])
@override_settings(READING_BUDGET=1000)
def test_a_range_a_reader_may_not_ask_is_refused_and_counts_nothing(api, code, query, field):
    """OP5: a minus sign or a zero returned the text nearly whole (399 of 400 articles) and the counter, reading the
    range back from the JSON, found no number to count."""
    r = api.get(f'/api/corpus/at/ma/loi/70-03/?{query}', **READER)
    assert r.status_code == 400 and r.json() == {'errors': [{'field': field, 'code': 'invalid'}]}
    assert not any('reading:' in key for key in cache._cache)      # nothing spent, nothing counted


@pytest.mark.parametrize('query, given', [('window=1', 1), ('window=80', 80), ('from=0&count=80', 80),
                                          ('from=95', 5), ('from=99&count=1', 1), ('from=500', 0)])
@override_settings(READING_BUDGET=1000)
def test_what_is_counted_is_what_the_view_sent(api, code, query, given):
    r = api.get(f'/api/corpus/at/ma/loi/70-03/?{query}', **READER)
    assert r.status_code == 200 and len(r.json()['articles']) == given
    assert counted() == given


KEPT = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
        'answers': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'reading-answers'}}


@override_settings(READING_BUDGET=80, CACHES=KEPT)
def test_a_kept_answer_counts_the_articles_kept_beside_it(api, code):
    """The number of articles is kept with the answer's bytes: a kept window counts what it carries, never 0."""
    from django.core.cache import caches
    caches['answers'].clear()
    for k in range(1, 3):
        r = api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER)
        assert r.status_code == 200 and counted() == 40 * k
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER).status_code == 429
    caches['answers'].clear()


def test_a_constitutions_year_in_other_digits_is_no_error(api):
    assert api.get('/api/corpus/constitution/', {'year': '²', 'article': '١'}).status_code in (200, 404)


@override_settings(READING_BUDGET=50)
def test_browsers_behind_one_address_have_their_days_and_the_address_a_ceiling(api, code):
    """HM17 of the hard-moment review: the cookie gives a browser its day; a crawler that drops it is held by the
    address's ceiling, ten days' worth."""
    from rest_framework.test import APIClient
    r = api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER)
    assert r.status_code == 200 and reading.READER in r.cookies and r['Cache-Control'].startswith('private')
    again = api.get('/api/corpus/at/ma/loi/70-03/?window=10', **READER)
    assert again.status_code == 200 and reading.READER not in again.cookies      # one cookie, kept
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=10', **READER).status_code == 429   # its own day is spent
    # Browsers that keep their cookie, each its own day, stop together at the address's ceiling (500 here).
    given = 50
    for _ in range(20):
        if APIClient().get('/api/corpus/at/ma/loi/70-03/', {'window': 40}, follow=True, **READER).status_code == 429:
            break
        given += 40
    assert 500 <= given < 600
    assert APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **NEIGHBOUR).status_code == 200


@override_settings(READING_BUDGET=50)
def test_requests_without_the_cookie_share_one_day_of_their_address(code):
    """OP17: a request without the cookie was a new browser each time, so a client that sends none read ten days."""
    from rest_framework.test import APIClient
    for _ in range(2):
        assert APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **READER).status_code == 200
    # Past that day a request without the cookie is given one and asked again: a browser follows and reads its own day…
    r = APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **READER)
    assert r.status_code == 307 and r['Location'] == '/api/corpus/at/ma/loi/70-03/?window=40&reader=1'
    assert reading.READER in r.cookies and r['Cache-Control'] == 'no-store'
    browser = APIClient()
    r = browser.get('/api/corpus/at/ma/loi/70-03/', {'window': 40}, follow=True, **READER)
    assert r.status_code == 200 and len(r.json()['articles']) == 40
    assert browser.get('/api/corpus/at/ma/loi/70-03/?window=5', **READER).status_code == 200      # its cookie, its day
    # …a client that keeps no cookie comes back marked and without one, and is refused.
    r = APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40&reader=1', **READER)
    assert r.status_code == 429 and r.json() == {'errors': [{'field': 'reading', 'code': 'limit'}]}
    assert APIClient().get('/api/corpus/preview/?path=/ma/loi/70-03/art_1', **READER).status_code == 307
    # Another address's requests without the cookie have their own day.
    assert APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **NEIGHBOUR).status_code == 200


@override_settings(READING_BUDGET=100)
def test_a_client_without_cookies_cannot_spend_the_day_of_the_browsers_behind_its_address(api, code):
    """Finding 19: one client spent a mobile address's ceiling for everyone behind it; without the cookie it spends
    one day, a tenth of it, and the browsers read on."""
    from rest_framework.test import APIClient
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=10', **READER).status_code == 200          # a browser, kept
    codes = [APIClient().get('/api/corpus/at/ma/loi/70-03/?window=80', **READER).status_code for _ in range(10)]
    assert codes[:2] == [200, 200] and set(codes[2:]) == {307}
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=80', **READER).status_code == 200


def _v6(address: str) -> dict:
    return {'HTTP_CF_CONNECTING_IP': address, 'HTTP_X_FORWARDED_FOR': f'{address}, 127.0.0.1'}


@override_settings(READING_BUDGET=40)
def test_an_ipv6_line_is_one_address_for_the_day_of_reading(code):
    """OP16: a home line is given a /56 (256 /64s) or more; the browsers of one /56 share the address's ceiling."""
    from rest_framework.test import APIClient
    given = 0
    for k in range(1, 40):           # each a new browser in a new /64 of the same /56
        if APIClient().get('/api/corpus/at/ma/loi/70-03/', {'window': 40}, follow=True,
                           **_v6(f'2001:db8:0:{k:x}::1')).status_code == 429:
            break
        given += 40
    assert given == 400                                     # SHARED days for the whole /56
    assert APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **_v6('2001:db8:0:100::1')).status_code == 200


@override_settings(READING_BUDGET=1000, READING_OPERATOR_CEILING=100)
def test_an_operators_ceiling_holds_its_browsers_together_when_the_owner_sets_it(code):
    from rest_framework.test import APIClient
    with mock.patch.object(reading.operators, 'operator', return_value=36925) as looked_up:
        codes = [APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **_v6(f'2001:db8:{k:x}::1')).status_code
                 for k in range(1, 5)]
    assert codes == [200, 200, 200, 429] and looked_up.called
    with mock.patch.object(reading.operators, 'operator', return_value=6713):          # another operator
        assert APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **_v6('2001:db8:9::1')).status_code == 200


@override_settings(READING_BUDGET=1000)
def test_no_operator_ceiling_by_default_nor_any_look_up(code):
    """One mobile operator carries a large part of the honest readers: a ceiling per operator is for whoever runs the
    site to set."""
    from rest_framework.test import APIClient
    with mock.patch.object(reading.operators, 'operator', return_value=36925) as looked_up:
        for k in range(1, 6):
            assert APIClient().get('/api/corpus/at/ma/loi/70-03/?window=40', **_v6(f'2001:db8:{k:x}::1')).status_code == 200
    assert not looked_up.called


@override_settings(READING_BUDGET=100)
def test_an_outlines_first_words_count_one_article_for_every_ten(api, code):
    v = code.versions.get()
    r = api.get(f'/api/corpus/outline/{v.pk}/', **READER)
    assert r.status_code == 200 and len(r.json()['outline']) == 100 and counted() == 10
    assert api.get('/api/corpus/outline/999999/', **READER).status_code == 404
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=80', **READER).status_code == 200
    assert api.get('/api/corpus/at/ma/loi/70-03/?from=0&count=10', **READER).status_code == 200
    assert api.get(f'/api/corpus/outline/{v.pk}/', **READER).status_code == 429


@override_settings(READING_BUDGET=2)
def test_another_door_meters_with_one_call(rf):
    """`metered`, for the doors outside the corpus's own views (a link's picture, a page's image, a source file)."""
    from django.http import HttpResponse
    from django.http.response import Http404
    request = rf.get('/', HTTP_CF_CONNECTING_IP='105.155.1.2', HTTP_COOKIE='')
    assert reading.metered(request, lambda: HttpResponse(status=200), 2).status_code == 200
    with pytest.raises(Http404):
        reading.metered(rf.get('/', HTTP_CF_CONNECTING_IP='105.155.1.4'), lambda: (_ for _ in ()).throw(Http404()), 5)
    called = mock.Mock(return_value=HttpResponse())
    stop = reading.metered(rf.get('/?reader=1', HTTP_CF_CONNECTING_IP='105.155.1.2'), called, 1)
    assert stop.status_code == 429 and not called.called
    assert reading.metered(rf.get('/', HTTP_CF_CONNECTING_IP='105.155.1.4'), lambda: HttpResponse(status=404), 5).status_code == 404
    assert not reading.reached(rf.get('/', HTTP_CF_CONNECTING_IP='105.155.1.4'))           # a 404 counted nothing
