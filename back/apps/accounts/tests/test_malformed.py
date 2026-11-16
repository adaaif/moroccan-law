"""No malformed request answers 500 at any address of apps.accounts (OP53 of the open-source audit): a list where an
object is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and
the walk over every route are `knock` and `malformed` in back/conftest.py.

Here too, what every view stands on: the API's parsers and the NUL middleware (config/malformed.py), and DRF's own
refusals in the one error shape (apps/accounts/api/errors.py `exception_handler`)."""
import pytest
from django.core.cache import cache

pytestmark = pytest.mark.django_db


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('accounts', malformed) == []


def _codes(r):
    return [(e['field'], e['code']) for e in r.json()['errors']]


def test_drfs_own_refusals_answer_a_code_and_keep_their_headers(api, monkeypatch):
    # 405 with its Allow, 404 from Http404, 401 with WWW-Authenticate: once an English sentence under «detail».
    r = api.put('/api/topics/')
    assert (r.status_code, _codes(r)) == (405, [('request', 'method_not_allowed')]) and 'GET' in r['Allow']
    r = api.get('/api/topics/no-such-topic/')
    assert (r.status_code, r.json()) == (404, {'errors': [{'field': 'request', 'code': 'not_found'}]})
    r = api.get('/api/auth/me/')
    assert (r.status_code, _codes(r)) == (401, [('request', 'not_authenticated')]) and r['WWW-Authenticate']
    r = api.get('/api/auth/me/', HTTP_AUTHORIZATION='Bearer not-a-token')
    assert (r.status_code, _codes(r)) == (401, [('request', 'token_not_valid')]) and r['WWW-Authenticate']
    # 415 for a body no parser reads, 400 for JSON that does not parse.
    r = api.post('/api/quality/reports/', 'x', content_type='text/plain')
    assert (r.status_code, _codes(r)) == (415, [('request', 'unsupported_media_type')])
    r = api.post('/api/quality/reports/', '{"path": 1', content_type='application/json')
    assert (r.status_code, _codes(r)) == (400, [('request', 'parse_error')])
    # A limit's 429 keeps Retry-After.
    from apps.topics.api.views import UseRate
    monkeypatch.setattr(UseRate, 'rate', '1/min')
    cache.clear()
    body = {'path': '/topics/housing', 'event': 'open'}
    assert api.post('/api/topics/use/', body, format='json').status_code == 204
    r = api.post('/api/topics/use/', body, format='json')
    assert (r.status_code, _codes(r)) == (429, [('request', 'throttled')]) and int(r['Retry-After']) > 0
    assert 'detail' not in r.content.decode()


def test_the_house_refusals_and_the_assistants_doors_are_as_they_were(api):
    # A view's own refusal is untouched; a JSON-only door says 415 of the body, as before.
    r = api.post('/api/quality/reports/', {'path': '/ma/x', 'kind': 'reading', 'message': 'x'}, format='json')
    assert r.json() == {'errors': [{'field': 'path', 'code': 'not_found'}]}
    r = api.post('/api/auth/token/', {'username': 'x', 'password': 'y'})
    assert (r.status_code, _codes(r)) == (415, [('body', 'unsupported_media_type')])
    # OAuth's doors answer as RFC 6749 says, never in the site's shape: DRF's own words for its refusals, and a body that
    # cannot be read is `invalid_request`.
    r = api.put('/oauth/token')
    assert r.status_code == 405 and 'detail' in r.json()
    r = api.post('/oauth/register', '[]', content_type='application/json')
    assert (r.status_code, r.json()['error']) == (400, 'invalid_request')


@pytest.mark.parametrize('body', ['[]', '[{"path": "/ma/x"}]', '"x"', '5', 'null', '[' * 5000,
                                  '{"message": "a\\u0000b"}', '{"a\\u0000": 1}', '{"message": "\\ud800"}',
                                  '{"x": [[{"y": "\\u0000"}]]}'])
def test_a_json_body_that_is_not_one_object_of_storable_words_is_refused(api, body):
    """Each was a 500: `request.data.get` on a list, Python's reader out of depth, a NUL or half a UTF-16 pair that
    Postgres cannot hold."""
    r = api.post('/api/quality/reports/', body, content_type='application/json')
    assert r.status_code == 400
    assert _codes(r)[0][0] == 'request'


def test_a_form_holding_a_nul_is_refused():
    from rest_framework.test import APIClient
    r = APIClient().post('/api/quality/reports/', {'path': '/ma/x', 'kind': 'reading', 'message': 'a\x00b'})
    assert (r.status_code, _codes(r)) == (400, [('request', 'null_characters_not_allowed')])
    r = APIClient().post('/api/quality/reports/', 'path=%2Fma%2Fx&message=a%00b',
                         content_type='application/x-www-form-urlencoded')
    assert (r.status_code, _codes(r)) == (400, [('request', 'null_characters_not_allowed')])


def test_an_address_or_query_holding_a_nul_is_refused_before_any_view(api):
    for url in ('/api/search/suggest/?q=a%00b', '/api/discussion/feed/?place=%00', '/api/corpus/at/ma/a%00b/',
                '/ma/loi/a%00b', '/api/topics/?x=1&%00=2'):
        r = api.get(url)
        assert (r.status_code, r.json()) == (400, {'errors': [{'field': 'request', 'code': 'null_characters_not_allowed'}]}), url
    # «%2500» is a percent sign and two zeros, not a NUL.
    assert api.get('/api/topics/?x=%2500').status_code == 200
