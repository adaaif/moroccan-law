"""The measures' door (POST /api/measure/, apps/analytics/services/record.py): what it writes, what it refuses whole, what
it drops without a word, and that it never knows who sent a batch."""
import json
import logging

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User
from apps.accounts.services import accounts
from apps.analytics import registry
from apps.analytics.api.views import MeasureView
from apps.analytics.models import DayCount, Event
from apps.analytics.services import record
from apps.analytics.tests.beacon import BROWSER, URL, batch, event, post
from apps.opendata.throttles import ScopedRate

pytestmark = pytest.mark.django_db

COLUMNS = ('hour', 'name', 'kind', 'path', 'flow', 'props', 'lang', 'screen', 'build')


def rows():
    return list(Event.objects.order_by('id').values(*COLUMNS))


def countries():
    return {r.key: r.count for r in DayCount.objects.filter(metric='visit.country')}


def nothing_written():
    return not Event.objects.exists() and not DayCount.objects.exists()


def test_a_batch_is_written_whole_at_its_hour_and_answered_204_with_no_body(api, still):
    sent = batch(event(props={'entry': True, 'fresh': 'dwm'}), event('tool.step', 'tool', '/topics/road/tools/fine',
                                                                       flow=9, props={'step': 'opened'}))
    r = post(api, sent, HTTP_CF_IPCOUNTRY='MA')
    assert r.status_code == 204 and r.content == b''
    written = rows()
    assert [w['name'] for w in written] == ['page.shown', 'tool.step']
    assert {w['hour'] for w in written} == {still.replace(minute=0, second=0, microsecond=0)}
    assert written[0]['props'] == {'entry': True, 'fresh': 'dwm', 'source': 'direct'}
    assert written[1] == {'hour': written[1]['hour'], 'name': 'tool.step', 'kind': 'tool', 'path': '/topics/road/tools/fine',
                          'flow': 9, 'props': {'step': 'opened'}, 'lang': 'ar', 'screen': 'phone', 'build': 'abc1234'}


def test_the_query_and_fragment_are_cut_before_the_address_is_read_and_never_kept(api):
    sent = batch(event(path='/ma/loi/65-99/art_53?q=طلاق+سري&from=1#art_53'), event(path='/search?q=x y%20z'))
    assert post(api, sent).status_code == 204
    assert [w['path'] for w in rows()] == ['/ma/loi/65-99/art_53', '/search']
    stored = json.dumps(rows(), default=str, ensure_ascii=False)
    assert 'طلاق' not in stored and 'q=' not in stored and '#' not in stored


def test_numbers_are_kept_in_their_bands_and_a_host_lowercased(api):
    sent = batch(event('page.speed', props={'lcp': 1234, 'inp': 87.4, 'ttfb': 26, 'cls': 0.1234, 'net': '4g',
                                            'saver': False}),
                 event('api.failed', props={'endpoint': '/api/corpus/at/', 'status': 503.0}),
                 event(props={'entry': True, 'ref': 'WWW.Google.CO.MA'}))
    assert post(api, sent).status_code == 204
    speed, failed, shown = (w['props'] for w in rows())
    assert speed == {'lcp': 1250, 'inp': 100, 'ttfb': 50, 'cls': 0.12, 'net': '4g', 'saver': False}
    assert failed == {'endpoint': '/api/corpus/at/', 'status': 503}
    assert shown == {'entry': True, 'ref': 'www.google.co.ma', 'source': 'search'}


@pytest.mark.parametrize('props, source', [
    ({'entry': True}, 'direct'),
    ({'entry': True, 'ref': 'chatgpt.com'}, 'assistant'),
    ({'entry': True, 'ref': 'l.facebook.com'}, 'social'),
    ({'entry': True, 'ref': 'hespress.com'}, 'site'),
    ({'entry': True, 'ref': 'www.google.com', 'source': 'social'}, 'social'),   # the browser's own word is kept
])
def test_a_first_pages_source_is_the_browsers_else_read_from_its_host(api, props, source):
    assert post(api, batch(event(props=props))).status_code == 204
    assert rows()[0]['props']['source'] == source


@pytest.mark.parametrize('props, stored', [
    ({'inside': True}, {'inside': True}),                                     # a link of the site's own: no source
    ({'inside': True, 'ref': 'hespress.com'}, {'inside': True, 'ref': 'hespress.com'}),
    ({}, {'source': 'direct'}),
    ({'inside': False, 'ref': 'www.google.com'}, {'inside': False, 'ref': 'www.google.com', 'source': 'search'}),
    ({'ref': 'L.Facebook.com'}, {'ref': 'l.facebook.com', 'source': 'social'}),
    ({'source': 'assistant', 'ref': 'hespress.com'}, {'source': 'assistant', 'ref': 'hespress.com'}),
])
def test_an_address_that_led_nowhere_says_whether_the_site_or_another_sent_the_reader(api, props, stored):
    """Its source is read from its host as a first page's is, but only when the dead link was not the site's own; it
    needs no first page."""
    assert post(api, batch(event('page.missing', 'other', '/texts/9', props=props))).status_code == 204
    assert rows()[0]['props'] == stored


def test_a_page_that_is_not_a_first_page_gets_no_source(api):
    assert post(api, batch(event(props={'entry': False}), event(props={}))).status_code == 204
    assert [w['props'] for w in rows()] == [{'entry': False}, {}]


def test_a_missing_or_null_property_is_left_out(api):
    assert post(api, batch(event('page.speed', props={'lcp': None, 'cls': 0}), event(props=None))).status_code == 204
    assert [w['props'] for w in rows()] == [{'cls': 0}, {}]


REFUSALS = [
    # (what is wrong, the body, the field, the code)
    ('a list for the batch', [], 'request', 'parse_error'),
    ('a field the door does not read', batch(user='nadia'), 'body', 'unexpected'),
    ('no language', {k: v for k, v in batch().items() if k != 'lang'}, 'lang', 'required'),
    ('another language', batch(lang='en'), 'lang', 'invalid'),
    ('a language as a number', batch(lang=1), 'lang', 'invalid'),
    ('another screen', batch(screen='tv'), 'screen', 'invalid'),
    ('no screen', {k: v for k, v in batch().items() if k != 'screen'}, 'screen', 'required'),
    ('a build with words', batch(build='abc 1234'), 'build', 'invalid'),
    ('a build too long', batch(build='abcdef123'), 'build', 'invalid'),
    ('no build', {k: v for k, v in batch().items() if k != 'build'}, 'build', 'required'),
    ('no events', {k: v for k, v in batch().items() if k != 'events'}, 'events', 'required'),
    ('events not a list', batch(events={'name': 'page.shown'}), 'events', 'invalid'),
    ('too many events', batch(*[event()] * 41), 'events', 'too_many'),
    ('an event not an object', batch('page.shown'), 'events.0', 'invalid'),
    ('a field an event does not have', batch(event(user='nadia')), 'events.0', 'unexpected'),
    ('an address in an event', batch(event(ip='196.200.1.1')), 'events.0', 'unexpected'),
    ('no name', batch({'kind': 'home', 'path': '/'}), 'events.0.name', 'required'),
    ('a name not in the registry', batch(event('page.clicked')), 'events.0.name', 'unknown'),
    ('a name as a list', batch(event(['page.shown'])), 'events.0.name', 'unknown'),
    ('no kind', batch({'name': 'page.shown', 'path': '/'}), 'events.0.kind', 'required'),
    ('a kind not listed', batch(event(kind='admin')), 'events.0.kind', 'invalid'),
    ('no address', batch({'name': 'page.shown', 'kind': 'home'}), 'events.0.path', 'required'),
    ('an address as a number', batch(event(path=7)), 'events.0.path', 'invalid'),
    ('an address with Arabic letters', batch(event(path='/words/طلاق')), 'events.0.path', 'invalid'),
    ('an address from another site', batch(event(path='https://example.org/x')), 'events.0.path', 'invalid'),
    ('an address too long', batch(event(path='/' + 'x' * 200)), 'events.0.path', 'invalid'),
    ('a flow of 0', batch(event(flow=0)), 'events.0.flow', 'invalid'),
    ('a flow past what JavaScript holds', batch(event(flow=2**53 + 1)), 'events.0.flow', 'invalid'),
    ('a flow with a fraction', batch(event(flow=1.5)), 'events.0.flow', 'invalid'),
    ('a flow as words', batch(event(flow='12')), 'events.0.flow', 'invalid'),
    ('a flow as true', batch(event(flow=True)), 'events.0.flow', 'invalid'),
    ('properties not an object', batch(event(props=['entry'])), 'events.0.props', 'invalid'),
    ('a property not listed for the name', batch(event(props={'q': 'طلاق'})), 'events.0.props', 'unexpected'),
    ("another name's property", batch(event(props={'step': 'opened'})), 'events.0.props', 'unexpected'),
    ('a word outside a choice', batch(event(props={'fresh': 'often'})), 'events.0.props.fresh', 'invalid'),
    ('a yes as 1', batch(event(props={'entry': 1})), 'events.0.props.entry', 'invalid'),
    ('a number past its range', batch(event('page.speed', props={'lcp': 60001})), 'events.0.props.lcp', 'invalid'),
    ('a negative number', batch(event('page.speed', props={'cls': -0.1})), 'events.0.props.cls', 'invalid'),
    ('a number as words', batch(event('api.failed', props={'status': '404'})), 'events.0.props.status', 'invalid'),
    ("an error's message", batch(event('app.error', props={'error': 'TypeError: x of null'})), 'events.0.props.error',
     'invalid'),
    ('a referring page, not its host', batch(event(props={'entry': True, 'ref': 'google.com/search?q=x'})),
     'events.0.props.ref', 'invalid'),
    ('a source on a page that is not a first page', batch(event(props={'source': 'search'})), 'events.0.props.source',
     'entry_only'),
    ('a return on a page that is not a first page', batch(event(props={'entry': False, 'back': 'week'})),
     'events.0.props.back', 'entry_only'),
    ('a good event before a bad one', batch(event(), event(kind='nowhere')), 'events.1.kind', 'invalid'),
]


@pytest.mark.parametrize('why, body, field, code', REFUSALS, ids=[r[0] for r in REFUSALS])
def test_a_batch_the_registry_refuses_is_400_and_nothing_of_it_is_written(api, why, body, field, code):
    r = post(api, body, HTTP_CF_IPCOUNTRY='MA')
    assert r.status_code == 400, why
    assert r.json() == {'errors': [{'field': field, 'code': code}]}
    assert nothing_written()


def test_a_batch_that_is_not_an_object_is_refused_by_the_door_too():
    """The API's parser already refuses one (request.parse_error); the door does not count on it."""
    with pytest.raises(record.Refused) as refused:
        record.read([batch()], hour=None)
    assert (refused.value.field, refused.value.code) == ('body', 'invalid')


def test_a_body_over_16_kb_is_refused_before_it_is_read(api):
    body = json.dumps(batch()) + ' ' * registry.MOST_BYTES
    r = post(api, body)
    assert r.status_code == 400 and r.json() == {'errors': [{'field': 'body', 'code': 'too_large'}]}
    assert nothing_written()


def test_forty_events_are_taken(api):
    assert post(api, batch(*[event()] * registry.MOST_EVENTS)).status_code == 204
    assert Event.objects.count() == 40


def test_a_form_is_refused_the_door_reads_json_alone(api):
    r = api.post(URL, {'lang': 'ar'}, HTTP_USER_AGENT=BROWSER)
    assert r.status_code == 415 and r.json() == {'errors': [{'field': 'body', 'code': 'unsupported_media_type'}]}


DROPPED = [
    ('a search engine by its name', {'HTTP_USER_AGENT': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}),
    ('a headless browser', {'HTTP_USER_AGENT': BROWSER.replace('Chrome/', 'HeadlessChrome/')}),
    ('a script', {'HTTP_USER_AGENT': 'python-httpx/0.28.1'}),
    ('a page measured by Lighthouse', {'HTTP_USER_AGENT': BROWSER + ' Chrome-Lighthouse'}),
    ('no User-Agent at all', {'HTTP_USER_AGENT': ''}),
    ('a search engine by its published address', {'HTTP_CF_CONNECTING_IP': '157.55.39.5'}),
    ('a browser asking not to be counted (Global Privacy Control)', {'HTTP_SEC_GPC': '1'}),
]


@pytest.mark.parametrize('why, headers', DROPPED, ids=[d[0] for d in DROPPED])
def test_a_machine_or_a_reader_who_asked_not_to_be_counted_is_answered_204_and_nothing_is_written(api, why, headers):
    assert post(api, batch(event(props={'entry': True})), HTTP_CF_IPCOUNTRY='MA', **headers).status_code == 204
    assert nothing_written(), why


@pytest.mark.parametrize('why, headers', DROPPED[:3] + DROPPED[-1:], ids=[d[0] for d in DROPPED[:3] + DROPPED[-1:]])
def test_a_dropped_request_learns_nothing_about_the_rules(api, why, headers):
    """A machine that sends a wrong batch is answered as one that sends a right one."""
    assert post(api, batch(event('page.clicked')), **headers).status_code == 204
    assert post(api, ' ' * (registry.MOST_BYTES + 1), **headers).status_code == 204
    assert nothing_written()


@pytest.mark.parametrize('agent', [
    BROWSER + ' WhatsApp/2.24.25.78',
    BROWSER.replace('Mobile Safari/537.36', 'Mobile Safari/537.36 Telegram-Android/11.4.2'),
    BROWSER + ' [FB_IAB/FB4A;FBAV/489.0.0.53.81;]',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
])
def test_the_browsers_inside_messengers_are_readers(api, agent):
    """The request log's machine list named WhatsApp and Telegram: their link previews run no script, so they send
    nothing here, and the browsers inside the apps that carry their names are people reading."""
    assert post(api, batch(), HTTP_USER_AGENT=agent).status_code == 204
    assert Event.objects.count() == 1


def test_while_closed_the_door_answers_204_and_writes_nothing(api, settings):
    settings.ANALYTICS_OPEN = False
    assert post(api, batch(event(props={'entry': True}))).status_code == 204
    assert post(api, batch(event('page.clicked'))).status_code == 204
    assert nothing_written()


def test_a_signed_in_reader_writes_the_same_rows_as_anyone(api, client, still):
    """The door cannot see who is signed in: the same batch sent with a valid token and a session cookie, and with
    neither, writes the same rows and the same counts."""
    user = User.objects.create_user(username='nadia', email='nadia@example.org', password='a long secret 2026')
    client.force_login(user)                             # a session cookie, as the admin gives one
    access = accounts.tokens_for(user)['access']
    sent = batch(event(props={'entry': True, 'ref': 'claude.ai', 'fresh': 'd'}), event('tool.step', 'tool',
                                                                                         '/topics/family/tools/inheritance', flow=5, props={'step': 'result'}))
    assert post(client, sent, HTTP_AUTHORIZATION=f'Bearer {access}', HTTP_CF_IPCOUNTRY='MA').status_code == 204
    signed_in = rows()
    Event.objects.all().delete()
    assert post(api, sent, HTTP_CF_IPCOUNTRY='MA').status_code == 204
    assert rows() == signed_in
    assert countries() == {'MA': 2}
    assert 'nadia' not in json.dumps(signed_in, default=str)


def test_a_token_that_does_not_verify_is_never_read(api):
    """Any view that authenticates refuses a broken token (401); this one never looks at it."""
    assert post(api, batch(), HTTP_AUTHORIZATION='Bearer not-a-token').status_code == 204
    assert Event.objects.count() == 1


def test_the_view_has_no_authentication():
    assert MeasureView.authentication_classes == []


class Headers(dict):
    """A request's META that notes each header read."""

    def __init__(self, *args):
        super().__init__(*args)
        self.read = set()

    def get(self, key, default=None):
        self.read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.read.add(key)
        return super().__getitem__(key)


class Request:
    """A request whose cookies, account, token and body may not be touched."""

    def __init__(self, meta):
        self.META = meta

    def __getattr__(self, name):
        raise AssertionError(f'the door read request.{name}')


def test_the_door_reads_the_named_headers_and_nothing_else_of_the_request():
    meta = Headers({'HTTP_USER_AGENT': BROWSER, 'HTTP_COOKIE': 'sessionid=x', 'HTTP_AUTHORIZATION': 'Bearer x',
                    'HTTP_CF_IPCOUNTRY': 'ma', 'HTTP_CF_CONNECTING_IP': '196.200.1.1', 'HTTP_REFERER': 'https://x.org/',
                    'HTTP_ACCEPT_LANGUAGE': 'ar-MA', 'HTTP_SEC_GPC': '0', 'REMOTE_ADDR': '127.0.0.1'})
    facts = record.facts_of(Request(meta))
    assert facts == record.Facts(agent=BROWSER, address='196.200.1.1', gpc=False, country='MA')
    assert meta.read <= {'HTTP_USER_AGENT', 'HTTP_SEC_GPC', 'HTTP_CF_IPCOUNTRY', 'HTTP_CF_CONNECTING_IP',
                         'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR'}


@pytest.mark.parametrize('header, country', [('MA', 'MA'), ('fr', 'FR'), (' ES ', 'ES'), ('XX', 'XX'), ('T1', 'XX'),
                                              ('', 'XX'), ('MAR', 'XX'), ('م', 'XX')])
def test_a_visits_country_is_counted_alone_and_never_on_a_row(api, header, country):
    assert post(api, batch(event(props={'entry': True})), HTTP_CF_IPCOUNTRY=header).status_code == 204
    assert countries() == {country: 1}
    assert 'country' not in {f.name for f in Event._meta.get_fields()}
    assert country not in json.dumps(rows(), default=str)


def test_only_a_visits_first_page_counts_its_country_once_a_page(api, still):
    post(api, batch(event(props={'entry': True}), event(props={'entry': False}), event(), event('page.speed')),
         HTTP_CF_IPCOUNTRY='MA')
    post(api, batch(event(props={'entry': True})), HTTP_CF_IPCOUNTRY='MA')
    post(api, batch(event(props={'entry': True})), HTTP_CF_IPCOUNTRY='FR')
    post(api, batch(event(props={'entry': False})), HTTP_CF_IPCOUNTRY='DE')
    assert countries() == {'MA': 2, 'FR': 1}
    assert set(DayCount.objects.values_list('day', flat=True)) == {still.date()}


def _queries(api, events) -> list[str]:
    with CaptureQueriesContext(connection) as seen:
        assert post(api, batch(*events), HTTP_CF_IPCOUNTRY='MA').status_code == 204
    return [q['sql'] for q in seen.captured_queries]


def test_a_batch_costs_the_same_queries_for_one_event_or_forty(api, django_assert_max_num_queries):
    """One INSERT for the events and one upsert for the countries, whatever the batch holds."""
    one = _queries(api, [event(props={'entry': True})])
    many = _queries(api, [event(props={'entry': True})] * 10 + [event('page.speed', props={'lcp': 900})] * 15
                    + [event('tool.step', 'tool', '/topics/road/tools/fine', flow=k + 1, props={'step': 'opened'})
                       for k in range(15)])
    assert len(one) == len(many) <= 4
    assert sum(q.startswith('INSERT INTO "analytics_event"') for q in many) == 1
    assert countries() == {'MA': 11}
    with django_assert_max_num_queries(4):
        post(api, batch(*[event()] * 40))


def test_a_failure_while_writing_is_logged_and_never_reaches_the_reader(api, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError('the database went away')
    monkeypatch.setattr(Event.objects, 'bulk_create', broken)
    with caplog.at_level(logging.ERROR, logger='apps.analytics.services.record'):
        assert post(api, batch(event(props={'entry': True})), HTTP_CF_IPCOUNTRY='MA').status_code == 204
    assert 'was not written' in caplog.text and nothing_written()


def test_a_fault_while_reading_a_batch_is_logged_and_answered_204(api, monkeypatch, caplog):
    monkeypatch.setattr(record, '_props', lambda *args: 1 / 0)
    with caplog.at_level(logging.ERROR, logger='apps.analytics.services.record'):
        assert post(api, batch()).status_code == 204
    assert 'could not be read' in caplog.text and nothing_written()


def test_nothing_about_the_reader_is_logged(api, monkeypatch, caplog):
    """A failure's log line names the batch, never its sender's address or browser."""
    monkeypatch.setattr(Event.objects, 'bulk_create', lambda *a, **k: 1 / 0)
    with caplog.at_level(logging.DEBUG):
        post(api, batch(), HTTP_CF_CONNECTING_IP='196.200.1.1')
    assert '196.200.1.1' not in caplog.text and 'Android' not in caplog.text


def test_an_empty_batch_writes_nothing(api, django_assert_num_queries):
    with django_assert_num_queries(0):
        assert post(api, batch(events=[])).status_code == 204


def test_the_door_counts_by_network(api, monkeypatch):
    monkeypatch.setitem(ScopedRate.THROTTLE_RATES, 'measure', '2/min')
    answers = [post(api, batch(), REMOTE_ADDR=f'2001:db8:1:2::{k}').status_code for k in range(1, 4)]
    assert answers == [204, 204, 429]
    assert post(api, batch(), REMOTE_ADDR='2001:db8:1:3::1').status_code == 204


def test_the_list_for_privacy_is_public_and_kept_a_minute(api, settings):
    settings.ANALYTICS_DAYS = 90
    r = api.get(URL)
    assert r.status_code == 200 and r.json() == registry.public()
    assert r['Cache-Control'].startswith('public, max-age=60')
    assert all('question' not in m for m in r.json()['measures'])
