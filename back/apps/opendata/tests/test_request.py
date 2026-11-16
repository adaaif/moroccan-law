"""The request for access, as an account sends it (/api/access/): where it stands, the six answers and the terms, one
open request an account, none while it holds an access, a decline's wait, the answer to what was asked, the holder's
own end; one body for every door; the letters to the person and to the staff."""
from datetime import timedelta

import pytest
from django.conf import settings as django_settings
from django.core import mail
from django.utils import timezone

from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, ApiKey, Request
from apps.opendata.tests.helpers import accepted, asked, keyed

pytestmark = pytest.mark.django_db

ACCESS, SEND, ANSWER, END = '/api/access/', '/api/access/request/', '/api/access/request/answer/', '/api/access/end/'


def form(**fields) -> dict:
    """The six answers, the terms and the box, as the web sends them."""
    return {'name': 'Faculté des sciences juridiques', 'kind': 'school', 'purpose': 'How the labour code changed.',
            'wants_api': True, 'wants_data': False, 'runs_at': 'https://example.org/lab', 'volume': 'small',
            'commercial': False, 'terms': django_settings.ACCESS_TERMS, 'consent': True, **fields}


def errors(response) -> list[tuple]:
    return [(e['field'], e['code']) for e in response.json()['errors']]


@pytest.fixture(autouse=True)
def on_request(settings):
    settings.OPEN_DATA = 'request'
    settings.ACCESS_LETTER_TO = []
    settings.SITE_URL = 'https://example.org'


@pytest.fixture
def person(api):
    user = make_user('salma')
    api.force_authenticate(user)
    return user


def test_a_visitor_reads_where_it_stands_and_nothing_of_anyone(api, django_assert_max_num_queries):
    asked()
    with django_assert_max_num_queries(0):
        body = api.get(ACCESS).json()
    assert body == {'position': 'request', 'terms': django_settings.ACCESS_TERMS,
                    'answer_days': django_settings.ACCESS_ANSWER_DAYS, 'sizes': django_settings.ACCESS_SIZES,
                    'request': None, 'access': None, 'desk': None}


@pytest.mark.parametrize('value, position', [('closed', 'closed'), (True, 'open'), ('open', 'open')])
def test_the_position_is_the_settings(api, settings, value, position):
    settings.OPEN_DATA = value
    assert api.get(ACCESS).json()['position'] == position


def test_sending_a_request_answers_the_body_and_writes_to_the_person(api, person):
    r = api.post(SEND, form(), format='json')
    assert r.status_code == 201
    body = r.json()
    assert body == {**api.get(ACCESS).json()}
    shown = body['request']
    assert {k: shown[k] for k in ('state', 'name', 'kind', 'wants_api', 'wants_data', 'volume', 'commercial',
                                  'terms', 'asked', 'answer', 'reason', 'decided_at', 'ask_again_on')} == {
        'state': 'waiting', 'name': 'Faculté des sciences juridiques', 'kind': 'school', 'wants_api': True,
        'wants_data': False, 'volume': 'small', 'commercial': False, 'terms': django_settings.ACCESS_TERMS,
        'asked': '', 'answer': '', 'reason': '', 'decided_at': None, 'ask_again_on': None}
    assert body['access'] is None
    [letter] = mail.outbox
    assert letter.to == [person.email] and 'وصل طلبك' in letter.subject
    assert 'الواجهة البرمجية (API)' in letter.body and '5 أيام عمل' in letter.body
    assert 'https://example.org/data/access' in letter.body
    assert 'List-Unsubscribe' not in letter.extra_headers         # the account's own letter: no stop link


def test_the_letter_is_in_the_accounts_language(api, person):
    person.preferred_language = 'fr'
    person.save()
    api.post(SEND, form(wants_data=True), format='json')
    [letter] = mail.outbox
    assert letter.subject.startswith('Votre demande d’accès') and 'l’API et la base de données' in letter.body


def test_the_staff_is_written_to_in_plain_english(api, person, settings):
    settings.ACCESS_LETTER_TO = ['staff@example.org']
    api.post(SEND, form(commercial=True), format='json')
    _, told = mail.outbox
    made = Request.objects.get()
    assert told.to == ['staff@example.org'] and not getattr(told, 'alternatives', None)
    assert told.subject.endswith('a request for access from Faculté des sciences juridiques')
    for line in ('Who: Faculté des sciences juridiques, a university or a school; account salma, 30 days old, '
                 'address proven', 'What for: How the labour code changed.',
                 'Asks for: the API; volume small; commercial', 'Runs at: https://example.org/lab',
                 'Answer it on the desk: https://example.org/data/desk',
                 f'Or here: https://example.org/admin/opendata/request/{made.pk}/change/'):
        assert line in told.body, line


def test_a_letter_that_cannot_go_never_fails_the_request(api, person, settings):
    settings.ACCESS_LETTER_TO = ['staff@example.org']
    settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    settings.EMAIL_HOST, settings.EMAIL_PORT = '127.0.0.1', 9      # nothing listens there
    assert api.post(SEND, form(), format='json').status_code == 201
    assert Request.objects.filter(user=person).exists()


def test_a_request_needs_the_position_an_account_and_a_proven_address(api, settings):
    assert api.post(SEND, form(), format='json').status_code == 401
    api.force_authenticate(make_user('unproven', proven=False))
    r = api.post(SEND, form(), format='json')
    assert (r.status_code, errors(r)) == (403, [('email', 'unproven')])
    api.force_authenticate(make_user('salma'))
    settings.OPEN_DATA = 'closed'
    r = api.post(SEND, form(), format='json')
    assert (r.status_code, errors(r)) == (403, [('access', 'closed')])
    assert not Request.objects.exists() and mail.outbox == []
    # While the files are open to anyone, a key for the API is still asked for.
    settings.OPEN_DATA = 'open'
    assert api.post(SEND, form(), format='json').status_code == 201


@pytest.mark.parametrize('fields, refused', [
    ({'name': ''}, [('name', 'required')]),
    ({'name': '   '}, [('name', 'required')]),
    ({'name': 'x' * 121}, [('name', 'too_long')]),
    ({'name': ['a']}, [('name', 'invalid')]),
    ({'purpose': None}, [('purpose', 'required')]),
    ({'purpose': 'x' * 601}, [('purpose', 'too_long')]),
    ({'runs_at': 'x' * 201}, [('runs_at', 'too_long')]),
    ({'runs_at': 3}, [('runs_at', 'invalid')]),
    ({'kind': ''}, [('kind', 'required')]),
    ({'kind': 'spy'}, [('kind', 'invalid')]),
    ({'kind': {'a': 1}}, [('kind', 'invalid')]),
    ({'volume': 'huge'}, [('volume', 'invalid')]),
    ({'wants_api': False}, [('wants', 'required')]),
    ({'wants_api': 'yes'}, [('wants_api', 'invalid')]),
    ({'wants_data': 1}, [('wants_data', 'invalid')]),
    ({'commercial': None}, [('commercial', 'required')]),
    ({'commercial': 'no'}, [('commercial', 'invalid')]),
    ({'terms': '2020-01-01'}, [('terms', 'stale')]),
    ({'terms': ''}, [('terms', 'required')]),
    ({'terms': 20261116}, [('terms', 'invalid')]),
    ({'consent': False}, [('consent', 'required')]),
    ({'consent': 'true'}, [('consent', 'required')]),
    ({'consent': None}, [('consent', 'required')]),
    ({'name': '', 'kind': 'spy', 'consent': False}, [('name', 'required'), ('kind', 'invalid'),
                                                    ('consent', 'required')]),
])
def test_each_answer_is_checked_and_every_refusal_said_at_once(api, person, fields, refused):
    r = api.post(SEND, form(**fields), format='json')
    assert (r.status_code, errors(r)) == (400, refused)
    assert not Request.objects.exists()


def test_the_answers_are_kept_trimmed_a_name_on_one_line_and_runs_at_may_be_empty(api, person):
    api.post(SEND, form(name='  Une\nrédaction  ', purpose=' Two\nlines. ', runs_at=None, wants_data=None),
             format='json')
    made = Request.objects.get()
    assert (made.name, made.purpose, made.runs_at, made.wants_data) == ('Une rédaction', 'Two\nlines.', '', False)


def test_one_open_request_an_account_and_none_while_it_holds_an_access(api, person):
    assert api.post(SEND, form(), format='json').status_code == 201
    r = api.post(SEND, form(), format='json')
    assert (r.status_code, errors(r)) == (409, [('request', 'open')])
    Request.objects.update(state=Request.State.MORE)
    assert errors(api.post(SEND, form(), format='json')) == [('request', 'open')]
    holder = accepted(username='holder')
    api.force_authenticate(holder.user)
    r = api.post(SEND, form(), format='json')
    assert (r.status_code, errors(r)) == (409, [('access', 'live')])


def test_two_requests_sent_at_once_leave_one_open(api, person, monkeypatch):
    from apps.opendata.services import requests
    assert api.post(SEND, form(), format='json').status_code == 201
    monkeypatch.setattr(requests, '_newest', lambda user: None)        # the second read before the first was written
    r = api.post(SEND, form(), format='json')
    assert (r.status_code, errors(r)) == (409, [('request', 'open')])
    assert Request.objects.count() == 1


def test_an_access_whose_end_date_passed_lets_its_account_ask_again(api):
    holder = accepted(days=-1)
    api.force_authenticate(holder.user)
    assert api.get(ACCESS).json()['access']['state'] == 'ended'
    assert api.get(ACCESS).json()['access']['ended_reason'] == 'expired'
    assert api.post(SEND, form(), format='json').status_code == 201


def test_a_declined_account_asks_again_after_its_days(api, person):
    declined = asked(person, state=Request.State.DECLINED, reason=Request.Reason.UNCLEAR,
                     decided_at=timezone.now() - timedelta(days=10))
    on = (timezone.localdate(declined.decided_at) + timedelta(days=django_settings.ACCESS_ASK_AGAIN_DAYS)).isoformat()
    assert api.get(ACCESS).json()['request']['ask_again_on'] == on
    r = api.post(SEND, form(), format='json')
    assert (r.status_code, r.json()['errors']) == (409, [{'field': 'request', 'code': 'too_soon', 'on': on}])
    Request.objects.update(decided_at=timezone.now() - timedelta(days=django_settings.ACCESS_ASK_AGAIN_DAYS))
    assert api.get(ACCESS).json()['request']['ask_again_on'] is None
    assert api.post(SEND, form(), format='json').status_code == 201
    assert api.get(ACCESS).json()['request']['state'] == 'waiting'


def test_the_body_reads_the_newest_request_and_access_in_two_queries(api, person, django_assert_max_num_queries):
    older = accepted(person, data=True)
    Access.objects.filter(pk=older.pk).update(state=Access.State.ENDED, ended_reason=Access.Ended.ASKED)
    for _ in range(5):
        asked(person, state=Request.State.DECLINED, reason=Request.Reason.LATER,
              decided_at=timezone.now() - timedelta(days=60))
    newest = asked(person)
    with django_assert_max_num_queries(3):          # the account, its newest request, its newest access
        body = api.get(ACCESS).json()
    assert body['request']['id'] == newest.pk
    assert body['access'] == {
        'id': older.pk, 'api': True, 'data': True, 'size': 'app', 'limits': django_settings.ACCESS_SIZES['app'],
        'ends_on': older.ends_on.isoformat(), 'state': 'ended', 'ended_reason': 'asked',
        'created_at': body['access']['created_at']}


def test_the_answer_to_what_was_asked_sends_the_request_back_to_the_staff(api, person, settings):
    settings.ACCESS_LETTER_TO = ['staff@example.org']
    r = api.post(ANSWER, {'answer': 'x'}, format='json')
    assert (r.status_code, errors(r)) == (409, [('request', 'none')])
    asked(person, state=Request.State.MORE, asked='Which newsroom?')
    for text, code in (('', 'required'), ('x' * 601, 'too_long'), (['a'], 'invalid')):
        assert errors(api.post(ANSWER, {'answer': text}, format='json')) == [('answer', code)]
    r = api.post(ANSWER, {'answer': '  The weekly paper of Fes.  '}, format='json')
    assert r.status_code == 200 and r.json() == api.get(ACCESS).json()
    assert r.json()['request']['state'] == 'waiting' and r.json()['request']['answer'] == 'The weekly paper of Fes.'
    [told] = mail.outbox
    assert told.subject.endswith('answered your question')
    assert 'You asked: Which newsroom?\nThe answer: The weekly paper of Fes.' in told.body
    assert errors(api.post(ANSWER, {'answer': 'again'}, format='json')) == [('request', 'none')]


def test_the_holder_ends_their_own_access_and_its_keys(api):
    access, _ = keyed()
    api.force_authenticate(access.user)
    r = api.post(END)
    assert r.status_code == 200 and r.json() == api.get(ACCESS).json()
    assert r.json()['access']['state'] == 'ended' and r.json()['access']['ended_reason'] == 'asked'
    access.refresh_from_db()
    assert access.ended_by == access.user and access.ended_at
    assert not ApiKey.objects.filter(access=access, ended_at=None).exists()
    [letter] = mail.outbox
    assert 'انتهى وصولك' in letter.subject and 'أُنهي بطلب منك.' in letter.body
    r = api.post(END)
    assert (r.status_code, errors(r)) == (403, [('access', 'none')])


def test_the_doors_need_an_account(api):
    for door in (SEND, ANSWER, END):
        assert api.post(door, {}, format='json').status_code == 401


def test_no_malformed_body_answers_500_while_requests_are_open(knock, malformed):
    """The shapes of back/conftest.py at every address of the app, with the doors reading their fields (the app's own
    malformed test knocks while the position is closed, where they refuse before reading)."""
    assert knock('opendata', malformed) == []
