"""What the access desk reads (services/desk.py), through its doors: the overview, the request rows and a request's
sheet (with the account's standing in the discussion), the access rows and an access's sheet, the use across accesses,
the editions and who took them, the log. Each answers the contract's shape, pages by a cursor, and costs the same
number of queries for a few rows as for many."""
import json
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.models import Ban, Contribution, Discussion
from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, AccessDay, ApiKey, Download, Event, Request
from apps.opendata.services import access as accesses
from apps.opendata.services import desk, dump, editions, keys, log, requests, usage
from apps.opendata.tests.helpers import accepted, asked, keyed
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db

DESK = '/api/access/desk/'
REQUEST_ROW = {'id', 'name', 'kind', 'username', 'wants_api', 'wants_data', 'volume', 'commercial', 'state',
               'created_at', 'waiting_since', 'due_on', 'days_left', 'answered', 'change_of', 'wanted_size', 'reason'}
ACCESS_ROW = {'id', 'name', 'kind', 'username', 'api', 'data', 'size', 'limits', 'ends_on', 'state', 'ended_reason',
              'last_used_on', 'keys', 'calls_30', 'articles_30', 'spark'}
EVENT = {'at', 'by', 'act', 'request', 'access', 'name', 'details'}
ACCOUNT = {'id', 'username', 'display_name', 'email', 'email_proven', 'joined', 'days', 'posts', 'removed', 'paused'}


@pytest.fixture(autouse=True)
def on_request(settings):
    settings.OPEN_DATA = 'request'
    settings.ACCESS_LETTER_TO = ['staff@example.org']


@pytest.fixture
def chief(api):
    chief = make_user('chief', staff=True)
    chief.is_superuser = True
    chief.save()
    api.force_authenticate(chief)
    return chief


def get(api, door, **query):
    r = api.get(DESK + door, query)
    assert r.status_code == 200, r.content
    return r.json()


def cost(api, door, **query) -> int:
    with CaptureQueriesContext(connection) as seen:
        assert api.get(DESK + door, query).status_code == 200
    return len(seen.captured_queries)


def waiting_for(r: Request, days: int) -> None:
    Request.objects.filter(pk=r.pk).update(waiting_since=timezone.now() - timedelta(days=days),
                                           created_at=timezone.now() - timedelta(days=days))


def test_the_overview_opens_on_what_waits(api, chief, settings):
    settings.ACCESS_LETTER_TO = ['a@example.org']
    old, new = asked(username='old'), asked(username='new')
    waiting_for(old, 10)
    answered = asked(username='answered', answer='We are a newsroom.')
    more = asked(username='more', state='more', asked='Who?', decided_at=timezone.now())
    ending = accepted(username='ending', days=12)
    accepted(username='later', days=100)
    keyed(ending)
    body = get(api, '')
    assert set(body) == {'state', 'waiting', 'asked', 'ending', 'figures'}
    assert body['state'] == {'position': 'request', 'letter_to': ['a@example.org'], 'terms': settings.ACCESS_TERMS,
                             'answer_days': 5, 'sizes': settings.ACCESS_SIZES, 'edition': None,
                             'next_edition_on': body['state']['next_edition_on']}
    assert [r['id'] for r in body['waiting']] == [old.pk, new.pk, answered.pk]
    assert set(body['waiting'][0]) == REQUEST_ROW
    assert body['waiting'][0]['days_left'] < 0 and body['waiting'][1]['days_left'] >= 4
    assert [r['answered'] for r in body['waiting']] == [False, False, True]
    assert [r['id'] for r in body['asked']] == [more.pk] and body['asked'][0]['due_on'] is None
    assert [a['id'] for a in body['ending']] == [ending.pk] and set(body['ending'][0]) == ACCESS_ROW
    assert body['ending'][0]['keys'] == 1
    figures = body['figures']
    assert set(figures) == {'received', 'accepted', 'declined', 'median_days', 'waiting', 'oldest_days', 'ending',
                            'live', 'keys'}
    assert (figures['waiting'], figures['oldest_days'], figures['live'], figures['keys'], figures['ending']) == (
        3, 10, 2, 1, 1)


def test_the_next_edition_is_the_first_of_the_month():
    assert desk.next_edition_on(date(2026, 11, 16), None) == date(2026, 12, 1)
    assert desk.next_edition_on(date(2026, 12, 31), None) == date(2027, 1, 1)
    assert desk.next_edition_on(date(2026, 12, 1), None) == date(2026, 12, 1)       # not written yet today


def test_the_overview_costs_the_same_whatever_waits(api, chief):
    asked(username='a')
    accepted(username='b', days=10)
    few = cost(api, '')
    for i in range(8):
        asked(username=f'w{i}')
        asked(username=f'm{i}', state='more', decided_at=timezone.now())
        keyed(accepted(username=f'e{i}', days=5 + i))
    assert cost(api, '') == few


def test_the_requests_page_by_state_by_words_and_by_cursor(api, chief, monkeypatch):
    monkeypatch.setattr(desk, 'PAGE', 2)
    made = [asked(username=f'p{i}') for i in range(5)]
    for i, r in enumerate(made):
        waiting_for(r, 10 - i)
    asked(username='gone', state='declined', reason='later', decided_at=timezone.now())
    asked(username='took', state='accepted', decided_at=timezone.now(), name='Le Matin')
    first = get(api, 'requests/')
    assert first['counts'] == {'waiting': 5, 'more': 0, 'accepted': 1, 'declined': 1}
    assert [r['id'] for r in first['results']] == [made[0].pk, made[1].pk] and first['next']
    second = get(api, 'requests/', cursor=first['next'])
    third = get(api, 'requests/', cursor=second['next'])
    assert [r['id'] for r in second['results'] + third['results']] == [r.pk for r in made[2:]]
    assert third['next'] is None
    assert [r['username'] for r in get(api, 'requests/', state='all')['results']] == ['took', 'gone']
    found = get(api, 'requests/', state='all', q='matin')
    assert [r['username'] for r in found['results']] == ['took'] and found['counts']['waiting'] == 0
    assert [r['username'] for r in get(api, 'requests/', state='all', q='p3@example')['results']] == ['p3']
    for query, refusal in (({'state': 'lost'}, 'state'), ({'cursor': 'not-a-cursor'}, 'cursor'),
                           ({'cursor': 'MjAyNnwx'}, 'cursor')):
        r = api.get(DESK + 'requests/', query)
        assert r.status_code == 400 and r.json()['errors'][0]['field'] == refusal


def test_the_requests_page_costs_the_same_whatever_its_rows(api, chief):
    asked(username='a')
    few = cost(api, 'requests/', state='all')
    for i in range(12):
        asked(username=f'r{i}', change_of=accepted(username=f'h{i}'))
    assert cost(api, 'requests/', state='all') == few


def test_a_request_s_sheet_holds_what_deciding_needs(api, chief):
    r = asked(volume='large', runs_at='https://lab.example.org', purpose='A study.')
    person = r.user
    place = Discussion.objects.create(path='/talk/work', text_path='/talk/work')
    for kind in ('post', 'comment', 'question'):
        Contribution.objects.create(discussion=place, author=person, kind=kind, body='x')
    Contribution.objects.create(discussion=place, author=person, kind='post', body='x', removed_at=timezone.now(),
                                removed_rule='spam')
    Contribution.objects.create(discussion=place, author=person, kind='post', body='x', held_at=timezone.now())
    Ban.objects.create(user=person, rule='spam', until=timezone.now() + timedelta(days=3))
    earlier = asked(person, state='declined', reason='unclear', decided_at=timezone.now() - timedelta(days=40))
    other = asked(username='other')
    for line in ('Which lab?', 'Who funds it?', 'Which lab?', 'Its address?', 'A fourth one?'):
        log.note(Event.Act.ASKED, by=chief, request=other, line=line)
    log.note(Event.Act.ASKED, by=make_user('second', staff=True), request=other, line='Not mine.')
    sheet = get(api, f'requests/{r.pk}/')
    assert set(sheet) == {'request', 'account', 'earlier', 'access', 'proposed', 'questions', 'history', 'may_decide'}
    assert set(sheet['request']) == REQUEST_ROW | {'purpose', 'runs_at', 'terms', 'asked', 'answer', 'decided_at',
                                                   'decided_by', 'holds'}
    assert sheet['request']['runs_at'] == 'https://lab.example.org' and sheet['request']['holds'] is None
    account = sheet['account']
    assert set(account) == ACCOUNT
    assert (account['email'], account['email_proven'], account['posts'], account['removed'], account['paused']) == (
        'asker@example.org', True, 3, 1, True)
    assert [e['id'] for e in sheet['earlier']] == [earlier.pk] and sheet['earlier'][0]['reason'] == 'unclear'
    assert sheet['access'] is None
    assert sheet['proposed'] == {'api': True, 'data': False, 'size': 'partner',
                                 'ends_on': accesses.default_end().isoformat()}
    assert sheet['questions'] == ['A fourth one?', 'Its address?', 'Which lab?']
    assert sheet['may_decide'] is True and sheet['history'] == []
    api.post(f'{DESK}requests/{r.pk}/ask/', {'line': 'Which lab?'}, format='json')
    [event] = get(api, f'requests/{r.pk}/')['history']
    assert set(event) == EVENT and (event['by'], event['act'], event['name'], event['details']) == (
        'chief', 'asked', 'A research group', {'line': 'Which lab?'})


def test_a_change_request_s_sheet_says_what_is_held_now(api, chief):
    access = accepted(size='try', days=60)
    change = asked(access.user, change_of=access, wants_api=True, wants_data=True)
    sheet = get(api, f'requests/{change.pk}/')
    assert sheet['request']['holds'] == {'api': True, 'data': False, 'size': 'try'}
    assert sheet['request']['change_of'] == access.pk
    assert sheet['proposed'] == {'api': True, 'data': True, 'size': 'try', 'ends_on': access.ends_on.isoformat()}
    assert sheet['access']['id'] == access.pk
    Request.objects.filter(pk=change.pk).update(wanted_size='app')
    assert get(api, f'requests/{change.pk}/')['proposed']['size'] == 'app'
    body = {'api': True, 'data': True, 'size': 'app', 'confirm': True}
    done = api.post(f'{DESK}requests/{change.pk}/accept/', body, format='json').json()
    assert done['request']['state'] == 'accepted' and done['access']['data'] is True
    assert done['access']['ends_on'] == access.ends_on.isoformat()


def test_a_request_s_sheet_costs_the_same_whatever_surrounds_it(api, chief):
    r = asked()
    few = cost(api, f'requests/{r.pk}/')
    place = Discussion.objects.create(path='/talk/work', text_path='/talk/work')
    for i in range(6):
        Contribution.objects.create(discussion=place, author=r.user, kind='post', body='x')
        asked(r.user, state='declined', reason='later', decided_at=timezone.now())
        log.note(Event.Act.ASKED, by=chief, request=r, line=f'Line {i}')
    a = accepted(username='x')
    Access.objects.filter(pk=a.pk).update(user=r.user, state='ended')
    keyed(Access.objects.get(pk=a.pk))
    assert cost(api, f'requests/{r.pk}/') == few + 1            # its newest access's 30 days, once there is one
    for i in range(6):
        AccessDay.objects.create(access=a, day=timezone.localdate() - timedelta(days=i), calls=i)
    assert cost(api, f'requests/{r.pk}/') == few + 1


def test_the_accesses_by_state_with_their_thirty_days(api, chief):
    today = timezone.localdate()
    used, _ = keyed(accepted(username='used'))
    AccessDay.objects.create(access=used, day=today, calls=7, articles=20)
    AccessDay.objects.create(access=used, day=today - timedelta(days=29), calls=3, articles=1)
    AccessDay.objects.create(access=used, day=today - timedelta(days=30), calls=100, articles=100)
    ApiKey.objects.filter(access=used).update(last_used_on=today)
    unused = accepted(username='unused', days=200)
    ending = accepted(username='ending', days=10)
    AccessDay.objects.create(access=ending, day=today, calls=1)
    ended = accepted(username='ended')
    accesses.end(ended, Access.Ended.TERMS, by=chief)
    stale = accepted(username='stale', days=-2)
    page = get(api, 'accesses/')
    assert page['counts'] == {'live': 3, 'ending': 1, 'ended': 2, 'unused': 1}
    assert [a['id'] for a in page['results']] == [ending.pk, unused.pk, used.pk]
    row = next(a for a in page['results'] if a['id'] == used.pk)
    assert (row['calls_30'], row['articles_30'], row['keys'], row['last_used_on']) == (10, 21, 1, today.isoformat())
    assert len(row['spark']) == 30 and row['spark'][0] == 3 and row['spark'][-1] == 7 and sum(row['spark']) == 10
    assert [a['id'] for a in get(api, 'accesses/', state='unused')['results']] == [unused.pk]
    assert [a['id'] for a in get(api, 'accesses/', state='ending')['results']] == [ending.pk]
    gone = get(api, 'accesses/', state='ended')['results']
    assert {a['id']: a['ended_reason'] for a in gone} == {ended.pk: 'terms', stale.pk: 'expired'}
    assert len(get(api, 'accesses/', state='all')['results']) == 5
    assert [a['id'] for a in get(api, 'accesses/', state='all', q='stale@')['results']] == [stale.pk]


def test_the_accesses_page_costs_the_same_whatever_its_rows(api, chief):
    keyed(accepted(username='a'))
    few = cost(api, 'accesses/', state='all')
    for i in range(10):
        a, _ = keyed(accepted(username=f'h{i}'))
        ApiKey.issue(a, 'second')
        for back in range(5):
            AccessDay.objects.create(access=a, day=timezone.localdate() - timedelta(days=back), calls=back)
    assert cost(api, 'accesses/', state='all') == few


def test_an_access_s_sheet(api, chief, monkeypatch):
    access, key = keyed(accepted(size='partner', minute=1))
    old, _ = ApiKey.issue(access, 'old')
    keys.end(old, by=access.user)
    today = timezone.localdate()
    AccessDay.objects.create(access=access, day=today - timedelta(days=3), calls=5, articles=9,
                             doors={'v1.search': 4, 'mcp': 1}, limits={'minute': 2})
    holder = keys.read(key)
    usage.charge(holder, 'v1.search')
    with pytest.raises(usage.Limit):
        usage.charge(holder, 'site')
    Download.objects.create(access=access, edition='2026-11-01', file='akn.zip', by='key')
    change = asked(access.user, change_of=access, wants_data=True, username='holder')
    requests.decline(change, chief, 'later')
    sheet = get(api, f'accesses/{access.pk}/')
    assert set(sheet) == {'access', 'request', 'account', 'keys', 'days', 'doors', 'downloads', 'history'}
    assert set(sheet['access']) == ACCESS_ROW | {'created_at', 'renewed_at', 'ended_at', 'ended_by'}
    assert sheet['request']['name'] == 'A research group' and set(sheet['account']) == ACCOUNT
    assert [k['name'] for k in sheet['keys']] == ['tests', 'old'] and sheet['keys'][1]['ended_at']
    assert sheet['access']['keys'] == 1
    assert sheet['days'] == [
        {'day': (today - timedelta(days=3)).isoformat(), 'calls': 5, 'articles': 9,
         'doors': {'v1.search': 4, 'mcp': 1}, 'limits': {'minute': 2}},
        {'day': today.isoformat(), 'calls': 1, 'articles': 0, 'doors': {'v1.search': 1}, 'limits': {'minute': 1}}]
    assert sheet['doors'] == {'v1.search': 5, 'mcp': 1}
    assert sheet['downloads'] == [{'edition': '2026-11-01', 'file': 'akn.zip', 'by': 'key',
                                   'at': sheet['downloads'][0]['at']}]
    assert [(e['act'], e['by']) for e in sheet['history']] == [('key_ended', 'holder'), ('declined', 'chief')]
    assert key not in json.dumps(sheet) and ApiKey.objects.get(name='tests').key_hash not in json.dumps(sheet)


def test_an_access_s_sheet_costs_the_same_whatever_it_holds(api, chief):
    access, _ = keyed()
    few = cost(api, f'accesses/{access.pk}/')
    for i in range(8):
        ApiKey.issue(access, f'k{i}')
        AccessDay.objects.create(access=access, day=timezone.localdate() - timedelta(days=i + 1), calls=i)
        Download.objects.create(access=access, edition='2026-11-01', file='akn.zip', by='key')
        log.note(Event.Act.RENEWED, by=chief, access=access, ends_on=timezone.localdate())
    assert cost(api, f'accesses/{access.pk}/') == few


def test_the_use_across_every_access(api, chief):
    today = timezone.localdate()
    names = {}
    for i, calls in enumerate((50, 5, 30, 1, 2, 9)):
        a = accepted(username=f'u{i}')
        names[a.pk] = a.request.name
        AccessDay.objects.create(access=a, day=today, calls=calls, articles=calls * 2, doors={'v1.search': calls})
        AccessDay.objects.create(access=a, day=today - timedelta(days=40), calls=1000)       # past the window
    limited, key = keyed(accepted(username='limited', size='partner', minute=1))
    holder = keys.read(key)
    usage.charge(holder, 'mcp')
    with pytest.raises(usage.Limit):
        usage.charge(holder, 'mcp')
    body = get(api, 'use/')
    assert set(body) == {'days', 'doors', 'busiest', 'limited_today', 'totals'}
    assert body['days'] == [{'day': today.isoformat(), 'calls': 98, 'articles': 194}]
    assert body['doors'] == {'v1.search': 97, 'mcp': 1}
    assert [b['calls'] for b in body['busiest']] == [50, 30, 9, 5, 2]
    assert body['limited_today'] == [{'access': limited.pk, 'name': 'A research group',
                                      'limits': {'minute': 1, 'calls': 0, 'articles': 0}}]
    assert body['totals'] == {'calls': 98, 'articles': 194, 'accesses': 7}
    assert len(get(api, 'use/', days=60)['days']) == 2
    for days in ('0', '400', 'x'):
        assert api.get(DESK + 'use/', {'days': days}).json()['errors'] == [{'field': 'days', 'code': 'invalid'}]


def test_the_use_costs_the_same_whatever_its_rows(api, chief):
    accepted(username='a')
    few = cost(api, 'use/')
    for i in range(10):
        a = accepted(username=f'u{i}')
        for back in range(4):
            AccessDay.objects.create(access=a, day=timezone.localdate() - timedelta(days=back), calls=i + back)
    assert cost(api, 'use/') == few


@pytest.fixture
def written(settings, tmp_path):
    """An edition written on disk, and an older one only the record remembers."""
    settings.OPEN_DATA_DIR = tmp_path / 'open'
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26', number_as_printed='12.26',
                               title_ar='قانون رقم 12.26', first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 8, 10),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body='نص.')
    edition = editions.read(dump.write_dump(log=lambda m: None))
    with open(editions.root() / editions.LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'date': '2026-10-01', 'sha256': 'b' * 64, 'texts': 9, 'articles': 90, 'versions': 10})
                + '\n')
    return edition


def test_the_editions_and_who_took_them(api, chief, written, monkeypatch):
    monkeypatch.setattr(desk, 'EDITION_DOWNLOADS', 2)
    a = accepted(data=True, username='taker')
    for file in ('akn.zip', 'texts.jsonl.gz', 'akn.zip'):
        Download.objects.create(access=a, edition=written.date, file=file, by='account')
    Download.objects.create(access=a, edition='2026-10-01', file='akn.zip', by='key')
    body = get(api, 'editions/')
    assert set(body) == {'editions', 'next_on'}
    newest, older = body['editions'][0], body['editions'][-1]
    assert (newest['date'], newest['sha256'], newest['on_disk'], newest['texts'], newest['articles']) == (
        written.date, written.sha256, True, 1, 1)
    assert newest['bytes'] == sum(f['bytes'] for f in written.manifest['files'].values())
    taken = {f['name']: f['taken'] for f in newest['files']}
    assert set(taken) == set(written.manifest['files'])
    assert {name: n for name, n in taken.items() if n} == {'akn.zip': 2, 'texts.jsonl.gz': 1}
    assert len(newest['downloads']) == 2 and newest['downloads'][0]['name'] == 'A research group'
    assert set(newest['downloads'][0]) == {'access', 'name', 'file', 'by', 'at'}
    assert (older['date'], older['on_disk'], older['bytes'], older['files'], older['texts']) == (
        '2026-10-01', False, None, [], 9)
    assert [d['by'] for d in older['downloads']] == ['key']
    few = cost(api, 'editions/')
    for i in range(6):
        Download.objects.create(access=accepted(data=True, username=f't{i}'), edition=written.date,
                                file='akn.zip', by='key')
    assert cost(api, 'editions/') == few


def test_the_log_newest_first_a_page_at_a_time(api, chief, monkeypatch):
    monkeypatch.setattr(desk, 'PAGE', 3)
    r = asked()
    for i in range(5):
        log.note(Event.Act.ASKED, by=chief, request=r, line=f'Line {i}')
    a = accepted(username='h')
    log.note(Event.Act.RENEWED, access=a, ends_on=timezone.localdate())
    first = get(api, 'log/')
    assert [e['act'] for e in first['results']] == ['renewed', 'asked', 'asked'] and first['next']
    assert first['results'][0]['name'] == 'A research group' and first['results'][0]['by'] is None
    rest = get(api, 'log/', cursor=first['next'])
    assert [e['details']['line'] for e in rest['results']] == ['Line 2', 'Line 1', 'Line 0'] and rest['next'] is None
    few = cost(api, 'log/')
    for i in range(6):
        log.note(Event.Act.RENEWED, by=make_user(f'x{i}', staff=True), access=accepted(username=f'y{i}'))
    assert cost(api, 'log/') == few
