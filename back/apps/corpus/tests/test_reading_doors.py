"""A day of reading's other doors (OP16–OP18 of the open-source audit): Cloudflare's Turnstile asked over the network
for a pass (a refusal or a network that does not answer gives none), and a key's day, its access's own articles."""
import io
import json
import urllib.parse
import urllib.request

import pytest
from django.test import override_settings

from apps.corpus.services import reading
from apps.corpus.tests.test_reading_budget import READER, code, fresh  # noqa: F401  (fixtures)
from apps.opendata.models import ApiKey
from apps.opendata.services import keys
from apps.opendata.tests.helpers import keyed

pytestmark = pytest.mark.django_db


@pytest.fixture
def cloudflare(monkeypatch):
    """Turnstile's siteverify endpoint: what it is sent, and its answer (or the network failing)."""
    asked, answer = [], {'success': True}

    def urlopen(request, timeout):
        asked.append((request.full_url, urllib.parse.parse_qs(request.data.decode()), timeout))
        if answer.get('down'):
            raise OSError('Network is unreachable')
        return io.BytesIO(json.dumps(answer).encode())
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    return asked, answer


@override_settings(READING_BUDGET=80, TURNSTILE_SITE_KEY='site', TURNSTILE_SECRET_KEY='secret')
def test_a_pass_is_cloudflares_word_and_none_when_it_cannot_be_asked(api, code, cloudflare):
    asked, answer = cloudflare
    api.get('/api/corpus/at/ma/loi/70-03/', **READER)
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER).status_code == 429
    answer.update(success=False)
    assert api.post('/api/corpus/reading/', {'token': 'tok'}, format='json', **READER).status_code == 400
    answer.update(down=True)
    assert api.post('/api/corpus/reading/', {'token': 'tok'}, format='json', **READER).status_code == 400
    answer.update(success=True, down=False)
    assert api.post('/api/corpus/reading/', {'token': 'tok'}, format='json', **READER).status_code == 204
    url, form, timeout = asked[-1]
    assert url == reading.VERIFY and timeout == 10
    assert form == {'secret': ['secret'], 'response': ['tok'], 'remoteip': ['105.155.1.2']}
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=40', **READER).status_code == 200


@override_settings(READING_BUDGET=80, OPEN_DATA='request')
def test_a_key_reads_its_accesss_articles_and_a_key_no_longer_active_nothing(api, code):
    from apps.opendata.services import usage
    access, live = keyed(size='partner', articles=150)
    gone, ended = ApiKey.issue(access, 'gone')
    keys.end(gone)
    key = {**READER, 'HTTP_X_API_KEY': live}
    # The access's 150 articles, not the browser's 80: two windows, then its day is spent.
    for _ in range(2):
        assert api.get('/api/corpus/at/ma/loi/70-03/?window=80', **key).status_code == 200
    r = api.get('/api/corpus/at/ma/loi/70-03/?window=80', **key)
    assert r.status_code == 429 and r.json() == {'errors': [{'field': 'key', 'code': 'articles'}]}
    assert int(r['Retry-After']) >= 60 and r.has_header('RateLimit')
    assert usage.today(access.pk) == {'calls': 3, 'articles': 160}
    # What the key read is its access's, not its address's: the browsers behind that address read on.
    assert api.get('/api/corpus/at/ma/loi/70-03/?window=80', **READER).status_code == 200
    # A key no longer active opens nothing: refused, never read at the address's day.
    r = api.get('/api/corpus/at/ma/loi/70-03/?window=80', **{**READER, 'HTTP_X_API_KEY': ended})
    assert r.status_code == 401 and r.json() == {'errors': [{'field': 'key', 'code': 'ended'}]}


@override_settings(READING_BUDGET=2)
def test_where_no_door_refused_it_a_key_that_opens_nothing_reads_as_no_key(rf):
    request = rf.get('/', HTTP_X_API_KEY='law_wrong', HTTP_CF_CONNECTING_IP='105.155.1.9')
    reading.spend(request, 2)
    assert reading.reached(request)                   # the address's day for requests without the cookie
    assert reading.refused(rf.get('/', HTTP_CF_CONNECTING_IP='105.155.1.9')) is not None
