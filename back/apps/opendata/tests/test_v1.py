"""The versioned API (/api/v1/): its six reads over the assistants' services, the key every read asks for, its
limits and headers, the refusals in the one shape, and the reads that will go saying so."""
import json
from datetime import date, timedelta
from unittest import mock
from urllib.parse import quote

import pytest
import yaml
from django.utils import timezone

from apps.consolidation.models import Change
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.mcp.tests.conftest import ART_51_NOW, ART_51_THEN, labour  # noqa: F401  (a fixture)
from apps.opendata.models import Access, ApiKey, hash_key
from apps.opendata.services import keys, usage
from apps.opendata.tests.helpers import accepted, keyed
from apps.opendata.v1 import deprecated
from apps.opendata.v1.views import OPENAPI
from apps.sources.models import Document, Edition, Issue

pytestmark = pytest.mark.django_db
SITE = 'http://localhost:5190'
# The site's search as `law.search` reads it (BM25 needs ParadeDB; the suite runs on SQLite).
FOUND = {'jump': {'state': 'found', 'text': {'path': '/ma/loi/65-99', 'title': 'القانون رقم 65.99', 'status': 'in_force',
                                             'name': {'ar': 'مدونة الشغل'}},
                  'article': {'label': 'المادة 51', 'path': '/ma/loi/65-99/art_51'}},
         'results': [{'text': {'path': '/ma/loi/65-99', 'title': 'القانون رقم 65.99', 'status': 'in_force',
                               'name': {'ar': 'مدونة الشغل'}, 'type': 'law'}, 'title_match': False,
                      'articles': [{'label': 'المادة 52', 'path': '/ma/loi/65-99/art_52',
                                    'snippet': [{'t': 'أجل '}, {'t': 'الإخطار', 'hit': True}]}]}],
         'repaired': None}


@pytest.fixture(autouse=True)
def requests_open(settings):
    settings.OPEN_DATA = 'request'


def ago(days: int) -> date:
    return timezone.localdate() - timedelta(days=days)


def issue_of(number: int, day: date, edition=Edition.GENERAL_AR) -> Issue:
    scan = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{edition}{number}'.ljust(64, '0')[:64],
                                   path=f'bo/{number}.pdf', mime='application/pdf', bytes=1, language='ar',
                                   fetched_at=timezone.now())
    return Issue.objects.create(edition=edition, number=number, date=day, document=scan)


def law_of(number: str, issue: Issue, page: int = 1, articles: int = 2, **fields) -> Text:
    text = Text.objects.create(akn_uri=f'/akn/ma/act/loi/{number}', type=fields.pop('type', 'law'), number=number,
                               number_as_printed=number.replace('-', '.'), title_ar=f'القانون رقم {number}',
                               status='in_force', first_published_in=issue, first_published_page=page, **fields)
    version = Version.objects.create(text=text, language='ar', valid_from=issue.date,
                                     consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.bulk_create(Article(version=version, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                                        body=f'نص المادة {n} من القانون {number}.') for n in range(1, articles + 1))
    return text


def change_of(by: Text, *, number='51', day=None, text_uri='/akn/ma/act/loi/65-99', **fields) -> Change:
    issue = by.first_published_in
    given = {'verb': 'modified', 'source': Change.Source.READING, 'state': Change.State.READ, 'by_kind': 'law',
             'by_number': by.number_as_printed, 'by_uri': by.akn_uri, 'by_article': 'المادة 2', 'issue': issue.number,
             'page': (by.first_published_page or 0) + 1, 'published_on': day or issue.date,
             'effective_on': (day or issue.date) + timedelta(days=30)}
    return Change.objects.create(text_uri=text_uri, number=number, **{**given, **fields})


@pytest.fixture
def made(labour):
    """The labour code of the assistants' tests (BO 5167, 2003), and a law of twenty days ago (BO 7533) that changes
    its article 51."""
    recent = issue_of(7533, ago(20))
    amending = law_of('12-26', recent, page=100)
    change_of(amending)
    return {'labour': labour, 'recent': recent, 'amending': amending}


def get(api, path, key=None, **extra):
    return api.get(path, **({'HTTP_X_API_KEY': key} if key else {}), **extra)


def post(api, path, body, key=None, **extra):
    return api.post(path, json.dumps(body) if not isinstance(body, str) else body, content_type='application/json',
                    **({'HTTP_X_API_KEY': key} if key else {}), **extra)


def error(response) -> tuple:
    return response.status_code, response.json()['errors'][0]['field'], response.json()['errors'][0]['code']


# ── The reads ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_an_article_is_given_whole_with_its_source_and_standing(api, made):
    access, key = keyed()
    r = get(api, '/api/v1/texts/ma/loi/65-99/art_51', key)
    assert r.status_code == 200
    item = r.json()
    assert item['id'] == '/ma/loi/65-99/art_51' and item['text'] == ART_51_NOW and item['url'] == f'{SITE}/ma/loi/65-99/art_51'
    meta = item['metadata']
    assert meta['published_in'] == {'bo': '5167', 'date': '2003-12-08', 'page': 3969, 'url': f'{SITE}/bo/general_ar/5167'}
    assert meta['version']['official'] is False and 'Bulletin officiel prevails' in meta['version']['note']
    assert meta['french']['text'].startswith('Toute rupture')
    assert usage.today(access.pk) == {'calls': 1, 'articles': 1}


def test_a_text_gives_its_outline_and_an_issue_its_texts(api, made):
    _, key = keyed()
    text = get(api, '/api/v1/texts/ma/loi/65-99', key).json()
    assert text['metadata']['kind'] == 'text' and text['metadata']['articles'] == 6
    assert 'المادة 51 (/ma/loi/65-99/art_51)' in text['text']
    issue = get(api, '/api/v1/texts/bo/7533', key).json()
    assert issue['metadata'] == {'kind': 'bulletin_issue', 'edition': 'general_ar', 'date': str(ago(20)), 'texts': 1}


def test_a_run_of_articles_holds_their_words_and_says_where_to_read_on(api, made):
    access, key = keyed()
    run = get(api, '/api/v1/articles/ma/loi/65-99?start=50&count=3', key).json()
    assert [a['label'] for a in run['articles']] == ['المادة 50', 'المادة 51', 'المادة 52']
    assert run['articles'][1]['text'] == ART_51_NOW and 'french' not in run['articles'][1]
    assert run['range'] == [2, 4] and run['total'] == 6 and run['next'] == '/ma/loi/65-99/art_53'
    assert usage.today(access.pk) == {'calls': 1, 'articles': 3}
    then = get(api, '/api/v1/articles/ma/loi/65-99/art_51?count=1&on=2010-01-01&french=true', key).json()
    assert then['articles'][0]['text'] == ART_51_THEN and then['on'] == '2010-01-01'
    assert then['articles'][0]['french']['text'].startswith('Toute rupture')
    assert get(api, '/api/v1/articles/ma/loi/65-99/art_49?count=1&french=1', key).json()['articles'][0]['french'] is None


def test_the_assistants_tools_answer_as_they_did(made):
    """The words are given to the versioned API alone: an assistant reads them in read_articles' text."""
    from apps.mcp.services import law
    text, data, served = law.read_articles('/ma/loi/65-99', start='51', count=1)
    assert ART_51_NOW in text and served == 1
    assert set(data) == {'law', 'version', 'on', 'published_in', 'note', 'articles', 'range', 'total', 'next'}
    assert set(data['articles'][0]) == {'id', 'label', 'url', 'status', 'changes'}


def test_search_gives_the_sites_results_and_keeps_nothing_of_what_was_asked(api, made):
    _, key = keyed()
    with mock.patch('apps.search.services.search.search', return_value=FOUND) as asked:
        r = get(api, '/api/v1/search?q=المادة 51 من مدونة الشغل', key)
    assert asked.call_args.kwargs == {'via': 'v1', 'log': False}
    assert [x['id'] for x in r.json()['results']] == ['/ma/loi/65-99/art_51', '/ma/loi/65-99', '/ma/loi/65-99/art_52']


def test_references_are_resolved_with_their_changes_since_a_day(api, made):
    _, key = keyed()
    r = post(api, '/api/v1/references', {'references': ['المادة 51 من القانون رقم 65.99', 'شكرا'],
                                         'since': str(ago(60))}, key)
    assert r.status_code == 200
    first, second = r.json()['references']
    assert first['found'][0]['id'] == '/ma/loi/65-99/art_51' and first['found'][0]['state'] == 'found'
    assert [c['bo'] for c in first['found'][0]['changed_since']] == ['7533']
    assert second == {'reference': 'شكرا', 'found': []}


def test_the_bulletin_gives_the_latest_week_and_one_issue(api, made):
    _, key = keyed()
    latest = get(api, '/api/v1/bulletin/', key).json()['issues']
    assert [i['key'] for i in latest] == ['7533'] and latest[0]['texts'][0]['id'] == '/ma/loi/12-26'
    one = get(api, '/api/v1/bulletin/5167', key).json()['issues'][0]
    assert one['texts'][0] == {'id': '/ma/loi/65-99', 'kind': 'Law', 'title': 'القانون رقم 65.99 المتعلق بمدونة الشغل',
                               'page': 3969}


def test_changes_give_what_the_bulletin_published_and_changed(api, made):
    _, key = keyed()
    page = get(api, f'/api/v1/changes?since={ago(30)}', key).json()
    assert [t['id'] for t in page['published']] == ['/ma/loi/12-26']
    assert [(c['id'], c['article_id']) for c in page['amended']] == [('/ma/loi/65-99', '/ma/loi/65-99/art_51')]
    assert page['next'] is None


# ── What a read refuses ───────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('path, expected', [
    ('/api/v1/texts/ma/loi/1-01', (404, 'id', 'not_found')),
    ('/api/v1/texts/ma/loi/65-99/art_700', (404, 'id', 'not_found')),
    ('/api/v1/texts/the%20labour%20code', (400, 'id', 'invalid')),
    ('/api/v1/texts/ma/' + 'x' * 300, (400, 'id', 'too_long')),
    ('/api/v1/texts/bo/9999', (404, 'issue', 'not_found')),
    ('/api/v1/articles/ma/loi/65-99?on=last%20year', (400, 'on', 'invalid')),
    ('/api/v1/articles/ma/loi/65-99?on=1990-01-01', (200, None, None)),
    ('/api/v1/articles/ma/loi/65-99?start=700', (404, 'start', 'not_found')),
    ('/api/v1/articles/ma/loi/65-99?start=' + '1' * 21, (400, 'start', 'too_long')),
    ('/api/v1/articles/ma/loi/65-99?count=21', (400, 'count', 'invalid')),
    ('/api/v1/articles/ma/loi/65-99?count=0', (400, 'count', 'invalid')),
    ('/api/v1/articles/ma/loi/65-99?count=%C2%B2', (400, 'count', 'invalid')),
    ('/api/v1/articles/ma/loi/65-99?french=maybe', (400, 'french', 'invalid')),
    ('/api/v1/articles/ma/loi/12-26?on=2000-01-01', (200, None, None)),
    ('/api/v1/search?q=', (400, 'q', 'required')),
    ('/api/v1/search?q=' + 'x' * 301, (400, 'q', 'too_long')),
    ('/api/v1/bulletin/the-last', (400, 'issue', 'invalid')),
    ('/api/v1/bulletin/' + '1' * 41, (400, 'issue', 'too_long')),
    ('/api/v1/bulletin/9999', (404, 'issue', 'not_found')),
    ('/api/v1/changes', (400, 'since', 'required')),
    ('/api/v1/changes?since=yesterday', (400, 'since', 'invalid')),
    ('/api/v1/changes?since=2001-01-01', (400, 'since', 'too_far')),
])
def test_a_read_refuses_what_it_cannot_read_by_a_code(api, made, path, expected):
    _, key = keyed()
    r = get(api, path, key)
    if expected[0] == 200:
        assert r.status_code == 200
        return
    assert error(r) == expected
    assert r['Cache-Control'] == 'no-store' and r.has_header('RateLimit')


def test_a_site_that_holds_no_issue_yet_has_no_latest_week(api):
    _, key = keyed()
    assert error(get(api, '/api/v1/bulletin/', key)) == (404, 'issue', 'not_found')


def test_a_broken_link_is_a_wrong_address_on_both_doors():
    from apps.mcp.services import law
    with pytest.raises(law.Problem) as problem:
        law.fetch('https://[')
    assert problem.value.code == 'id.invalid' and 'not a link to read' in str(problem.value)


def test_a_text_held_by_no_version_on_a_day_is_not_found(api, made):
    _, key = keyed()
    Text.objects.create(akn_uri='/akn/ma/act/decret/2-96-1', type='decree', title_ar='مرسوم بلا نص')
    assert error(get(api, '/api/v1/articles/ma/decret/2-96-1', key)) == (404, 'id', 'not_found')
    assert error(get(api, '/api/v1/articles/ma/decret/2-96-1?on=2020-01-01', key)) == (404, 'on', 'not_found')


@pytest.mark.parametrize('body, expected', [
    ({}, (400, 'references', 'required')),
    ({'references': []}, (400, 'references', 'required')),
    ({'references': 'المادة 51'}, (400, 'references', 'invalid')),
    ({'references': [51]}, (400, 'references', 'invalid')),
    ({'references': ['x' * 201]}, (400, 'references', 'too_long')),
    ({'references': ['x'] * 51}, (400, 'references', 'too_many')),
    ({'references': ['x'], 'since': 2020}, (400, 'since', 'invalid')),
    ({'references': ['x'], 'since': 'last year'}, (400, 'since', 'invalid')),
    ('{"references": ', (400, 'body', 'invalid')),
    ('["x"]', (400, 'body', 'invalid')),
])
def test_references_refuse_what_they_cannot_read(api, made, body, expected):
    _, key = keyed()
    assert error(post(api, '/api/v1/references', body, key)) == expected


def test_references_read_json_alone(api, made):
    _, key = keyed()
    r = api.post('/api/v1/references', {'references': 'x'}, HTTP_X_API_KEY=key)       # a form
    assert error(r) == (415, 'body', 'unsupported_media_type')
    assert get(api, '/api/v1/references', key).status_code == 405


# ── The key ───────────────────────────────────────────────────────────────────────────────────────────────────────

READS = ['/api/v1/search?q=x', '/api/v1/texts/ma/loi/65-99', '/api/v1/articles/ma/loi/65-99', '/api/v1/bulletin/',
         '/api/v1/bulletin/5167', '/api/v1/changes?since={today}']


@pytest.mark.parametrize('path', READS + ['references'])
def test_every_read_asks_for_a_key_and_reads_no_sign_in(api, made, path):
    def send(key=None, **extra):
        if path == 'references':
            return post(api, '/api/v1/references', {'references': ['x']}, key, **extra)
        return get(api, path.format(today=ago(0)), key, **extra)

    r = send()
    assert error(r) == (401, 'key', 'required') and r['Cache-Control'] == 'no-store'
    assert not r.has_header('RateLimit')
    access, key = keyed()
    ended = ApiKey.issue(access, 'old')
    keys.end(ended[0])
    assert error(send('law_wrong')) == (401, 'key', 'invalid')
    assert error(send(ended[1])) == (401, 'key', 'ended')
    # The site's sign-in is not read here, not even to refuse a token that no longer holds.
    with mock.patch('apps.search.services.search.search', return_value=FOUND):
        assert send(key, HTTP_AUTHORIZATION='Bearer not-a-token').status_code == 200


def test_a_key_past_its_access_date_has_expired(api, made):
    access, key = keyed()
    Access.objects.filter(pk=access.pk).update(ends_on=ago(1))
    keys.forget(hash_key(key))
    assert error(get(api, READS[1], key)) == (401, 'key', 'expired')


def test_the_access_must_include_the_api_and_the_api_be_open(api, made, settings):
    _, data_only = keyed(api=False, data=True)
    r = get(api, READS[1], data_only)
    assert error(r) == (403, 'access', 'no_api') and r['Cache-Control'] == 'no-store'
    _, key = keyed(username='other')
    settings.OPEN_DATA = 'closed'
    assert error(get(api, READS[1], key)) == (403, 'access', 'closed')
    settings.OPEN_DATA = 'open'
    assert get(api, READS[1], key).status_code == 200


def test_an_answer_carries_its_limits_is_private_and_sends_no_cors_header(api, made):
    _, key = keyed()
    r = get(api, READS[1], key, HTTP_ORIGIN='https://elsewhere.example')
    assert r.status_code == 200
    assert r['RateLimit-Policy'] == '"minute";q=120;w=60, "day";q=20000;w=86400'
    assert r['RateLimit'].startswith('"minute";r=119;t=') and '"day";r=19999;' in r['RateLimit']
    assert r['Cache-Control'] == 'private' and 'X-Api-Key' in r['Vary']
    assert not [h for h in r.headers if h.lower().startswith('access-control-')]
    assert not r.has_header('Deprecation') and not r.has_header('Sunset')


def test_past_a_limit_a_read_waits_and_nothing_is_counted(api, made):
    access, key = keyed(accepted(size=Access.Size.PARTNER, minute=2, calls=100, articles=100))
    assert get(api, READS[1], key).status_code == 200
    assert get(api, '/api/v1/bulletin/', key).status_code == 200
    r = get(api, READS[1], key)
    assert error(r) == (429, 'key', 'minute') and 1 <= int(r['Retry-After']) <= 60
    assert r['RateLimit'].startswith('"minute";r=0;')
    assert usage.today(access.pk)['calls'] == 2


def test_once_the_days_articles_are_spent_the_words_wait_and_the_rest_answers(api, made):
    access, key = keyed(accepted(size=Access.Size.PARTNER, minute=100, calls=100, articles=3))
    assert get(api, '/api/v1/articles/ma/loi/65-99?count=3', key).status_code == 200      # reaches the limit, served
    assert usage.today(access.pk) == {'calls': 1, 'articles': 3}
    for path in ('/api/v1/articles/ma/loi/65-99?count=1', '/api/v1/texts/ma/loi/65-99/art_51'):
        assert error(get(api, path, key)) == (429, 'key', 'articles')
    assert get(api, '/api/v1/bulletin/', key).status_code == 200
    assert get(api, f'/api/v1/changes?since={ago(0)}', key).status_code == 200


def test_a_refused_read_is_counted_as_a_call_and_gives_no_article(api, made):
    access, key = keyed()
    assert get(api, '/api/v1/texts/ma/loi/1-01', key).status_code == 404
    assert usage.today(access.pk) == {'calls': 1, 'articles': 0}


# ── v1 only grows ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_read_that_will_go_says_when_on_each_answer(api, made, monkeypatch):
    monkeypatch.setitem(deprecated.ROUTES, 'v1-bulletin', (date(2027, 1, 1), date(2027, 6, 1)))
    _, key = keyed()
    going = get(api, '/api/v1/bulletin/5167', key)
    assert going['Deprecation'] == '@1798761600' and going['Sunset'] == 'Tue, 01 Jun 2027 00:00:00 GMT'
    assert get(api, '/api/v1/bulletin/9999', key)['Sunset'] == 'Tue, 01 Jun 2027 00:00:00 GMT'
    assert get(api, '/api/v1/bulletin/5167')['Deprecation'] == '@1798761600'          # said before the key too
    staying = get(api, '/api/v1/bulletin/', key)
    assert not staying.has_header('Deprecation') and not staying.has_header('Sunset')


def test_no_read_is_going_today():
    assert deprecated.ROUTES == {}


def test_the_contract_is_served_as_written_to_anyone(api):
    r = api.get('/api/v1/openapi.yaml')
    assert r.status_code == 200 and r['Content-Type'].startswith('application/yaml')
    assert r.content == OPENAPI.read_bytes() and r['Cache-Control'] == 'public, max-age=3600'
    assert yaml.safe_load(r.content)['openapi'] == '3.1.0'
    assert api.post('/api/v1/openapi.yaml').status_code == 405


# ── Malformed requests with a key ─────────────────────────────────────────────────────────────────────────────────

ODD = ['\x00', '²', '2024-99-99', '9' * 40, 'x' * 3000, 'https://[', '-1', '[]', '{}']


@pytest.mark.parametrize('odd', ODD)
def test_no_odd_value_a_key_sends_answers_500(api, made, odd):
    _, key = keyed(accepted(size=Access.Size.PARTNER, minute=10_000, calls=10_000, articles=10_000))
    q = quote(odd, safe='')
    paths = [f'/api/v1/search?q={q}', f'/api/v1/texts/{q}', f'/api/v1/texts/ma/loi/{q}', f'/api/v1/articles/{q}',
             f'/api/v1/articles/ma/loi/65-99?start={q}&count={q}&on={q}&french={q}', f'/api/v1/bulletin/{q}',
             f'/api/v1/changes?since={q}', f'/api/v1/changes?since={ago(0)}&cursor={q}']
    with mock.patch('apps.search.services.search.search', return_value=FOUND):
        for path in paths:
            r = get(api, path, key)
            assert r.status_code < 500, (path, r.status_code)
        for body in ({'references': [odd], 'since': odd}, {'references': odd}, {'references': [[odd]]}):
            assert post(api, '/api/v1/references', body, key).status_code < 500
