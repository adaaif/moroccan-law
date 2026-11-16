"""The access desk's doors (/api/access/desk/): every door for an active superuser alone (401 to nobody signed in,
403 (`desk`, `forbidden`) to a reader, a reviewer and a staff account that is not a superuser), never kept by a cache;
nobody decides their own request; accepting, changing and ending ask to be confirmed; each acting door answers the
sheet it acted on."""
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.discussion.models import Reviewer
from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, ApiKey, Event, Request
from apps.opendata.tests.helpers import asked, keyed

pytestmark = pytest.mark.django_db

DESK = '/api/access/desk/'


@pytest.fixture(autouse=True)
def on_request(settings):
    settings.OPEN_DATA = 'request'
    settings.ACCESS_LETTER_TO = []


@pytest.fixture
def chief():
    chief = make_user('chief', staff=True)
    chief.is_superuser = True
    chief.save()
    return chief


@pytest.fixture
def rows():
    """Three requests waiting, an access with a key: a row for every door."""
    first, second, third = (asked(username=n) for n in ('first', 'second', 'third'))
    access, _ = keyed()
    return {'r1': first.pk, 'r2': second.pk, 'r3': third.pk, 'a': access.pk, 'k': ApiKey.objects.get().pk}


def doors(ids: dict) -> list[tuple]:
    """Every door, with a body a superuser's call succeeds with, in an order where each still can."""
    later = (timezone.localdate() + timedelta(days=200)).isoformat()
    r1, r2, r3, a, k = (ids[n] for n in ('r1', 'r2', 'r3', 'a', 'k'))
    return [
        ('get', '', None), ('get', 'requests/', None), ('get', f'requests/{r1}/', None),
        ('post', f'requests/{r1}/preview/', {'act': 'accept', 'api': True, 'size': 'try'}),
        ('post', f'requests/{r1}/accept/', {'api': True, 'size': 'try', 'confirm': True}),
        ('post', f'requests/{r2}/ask/', {'line': 'Which school?'}),
        ('post', f'requests/{r3}/decline/', {'reason': 'later'}),
        ('get', 'accesses/', None), ('get', f'accesses/{a}/', None),
        ('post', f'accesses/{a}/change/', {'data': True, 'confirm': True}),
        ('post', f'accesses/{a}/renew/', {'ends_on': later}),
        ('post', f'keys/{k}/end/', None),
        ('post', f'accesses/{a}/end/', {'reason': 'terms', 'confirm': True}),
        ('get', 'use/', None), ('get', 'editions/', None), ('get', 'log/', None),
    ]


def call(api, method, door, body=None):
    if method == 'get':
        return api.get(DESK + door)
    return api.post(DESK + door, body or {}, format='json')


def errors(r) -> list[tuple]:
    return [(e['field'], e['code']) for e in r.json()['errors']]


def test_nobody_signed_in_is_asked_to_sign_in(api, rows):
    for method, door, body in doors(rows):
        r = call(api, method, door, body)
        assert r.status_code == 401 and r['Cache-Control'] == 'no-store', door


@pytest.mark.parametrize('who', ['reader', 'reviewer', 'staff'])
def test_only_a_superuser_opens_the_desk(api, rows, who):
    user = make_user(who, staff=who == 'staff')
    if who == 'reviewer':
        Reviewer.objects.create(user=user)
    api.force_authenticate(user)
    for method, door, body in doors(rows):
        r = call(api, method, door, body)
        assert (r.status_code, errors(r), r['Cache-Control']) == (403, [('desk', 'forbidden')], 'no-store'), door
    assert Request.objects.filter(state='waiting').count() == 3 and not Event.objects.exists()
    assert mail.outbox == []


def test_an_inactive_superuser_is_refused_too(api, rows, chief):
    chief.is_active = False
    chief.save()
    api.force_authenticate(chief)
    assert errors(api.get(DESK)) == [('desk', 'forbidden')]


def test_a_superuser_opens_every_door_and_each_act_answers_its_sheet(api, rows, chief):
    api.force_authenticate(chief)
    for method, door, body in doors(rows):
        r = call(api, method, door, body)
        assert (r.status_code, r['Cache-Control']) == (200, 'no-store'), (door, r.content)
        if '/accept/' in door or '/ask/' in door or '/decline/' in door:
            assert set(r.json()) >= {'request', 'account', 'history', 'may_decide'}, door
        elif door.endswith(('/change/', '/renew/', '/end/')):
            assert set(r.json()) >= {'access', 'keys', 'days', 'history'}, door
    states = dict(Request.objects.values_list('pk', 'state'))
    assert [states[rows[n]] for n in ('r1', 'r2', 'r3')] == ['accepted', 'more', 'declined']
    access = Access.objects.get(pk=rows['a'])
    assert (access.data, access.state, access.ended_by) == (True, 'ended', chief)
    acts = list(Event.objects.order_by('pk').values_list('act', flat=True))
    assert acts == ['accepted', 'asked', 'declined', 'changed', 'renewed', 'key_ended', 'ended']


def test_nobody_decides_their_own_request(api, chief):
    mine = asked(chief, username='chief')
    api.force_authenticate(chief)
    for door, body in (('accept', {'api': True, 'size': 'try', 'confirm': True}), ('ask', {'line': 'x'}),
                       ('decline', {'reason': 'later'}), ('preview', {'act': 'ask', 'line': 'x'})):
        r = api.post(f'{DESK}requests/{mine.pk}/{door}/', body, format='json')
        assert (r.status_code, errors(r)) == (403, [('by', 'own')]), door
    assert api.get(f'{DESK}requests/{mine.pk}/').json()['may_decide'] is False
    mine.refresh_from_db()
    assert mine.state == 'waiting'


def test_accepting_changing_and_ending_ask_to_be_confirmed(api, rows, chief):
    api.force_authenticate(chief)
    for door, body in ((f'requests/{rows["r1"]}/accept/', {'api': True, 'size': 'try'}),
                       (f'accesses/{rows["a"]}/change/', {'data': True, 'confirm': 'yes'}),
                       (f'accesses/{rows["a"]}/end/', {'reason': 'terms', 'confirm': 1})):
        r = api.post(DESK + door, body, format='json')
        assert (r.status_code, errors(r)) == (400, [('confirm', 'required')]), door
    assert not Event.objects.exists() and not Access.objects.filter(data=True).exists()


def test_the_acts_refuse_as_their_services_do(api, rows, chief):
    api.force_authenticate(chief)
    accept = f'{DESK}requests/{rows["r1"]}/accept/'
    for body, refusal in (({'api': True, 'size': 'huge', 'confirm': True}, ('size', 'invalid')),
                          ({'size': 'try', 'confirm': True}, ('wants', 'required')),
                          ({'api': True, 'size': 'try', 'ends_on': '2020-01-01', 'confirm': True}, ('ends_on', 'past')),
                          ({'api': True, 'size': 'try', 'ends_on': '1 Nov', 'confirm': True}, ('ends_on', 'invalid')),
                          ({'api': 'yes', 'size': 'try', 'confirm': True}, ('api', 'invalid')),
                          ({'api': True, 'size': 'partner', 'minute': '9', 'confirm': True}, ('minute', 'invalid'))):
        assert errors(api.post(accept, body, format='json')) == [refusal], body
    assert errors(api.post(f'{DESK}requests/{rows["r2"]}/ask/', {'line': ''}, format='json')) == [('line', 'required')]
    assert errors(api.post(f'{DESK}requests/{rows["r2"]}/ask/', {'line': 'x' * 301}, format='json')) == [
        ('line', 'too_long')]
    assert errors(api.post(f'{DESK}requests/{rows["r3"]}/decline/', {'reason': 'rude'}, format='json')) == [
        ('reason', 'invalid')]
    assert errors(api.post(f'{DESK}requests/{rows["r1"]}/preview/', {'act': 'stamp'}, format='json')) == [
        ('act', 'invalid')]
    assert errors(api.post(f'{DESK}accesses/{rows["a"]}/end/', {'reason': 'expired', 'confirm': True},
                           format='json')) == [('reason', 'invalid')]
    assert errors(api.post(f'{DESK}accesses/{rows["a"]}/renew/', {'ends_on': 7}, format='json')) == [
        ('ends_on', 'invalid')]
    assert api.post(accept, {'api': True, 'size': 'try', 'confirm': True}, format='json').status_code == 200
    r = api.post(accept, {'api': True, 'size': 'try', 'confirm': True}, format='json')
    assert (r.status_code, errors(r)) == (409, [('request', 'decided')])
    for door in ('requests/999999/', 'accesses/999999/', 'keys/999999/end/'):
        r = call(api, 'post' if door.endswith('end/') else 'get', door)
        assert r.status_code == 404, door


def test_the_preview_is_the_letter_and_nothing_is_written(api, rows, chief, settings):
    settings.SITE_URL = 'https://example.org'
    api.force_authenticate(chief)
    r = api.post(f'{DESK}requests/{rows["r1"]}/preview/', {'act': 'decline', 'reason': 'identity'}, format='json')
    letter = r.json()
    assert letter['language'] == 'ar' and 'لم نستطع أن نعرف من يطلب.' in letter['body']
    assert letter['body'].endswith('\n\nقانون المغرب · example.org') and 'https://example.org/data/access' in letter['body']
    assert mail.outbox == [] and not Event.objects.exists()
    api.post(f'{DESK}requests/{rows["r1"]}/decline/', {'reason': 'identity'}, format='json')
    [sent] = mail.outbox
    assert sent.body == letter['body'] and sent.subject == f'‫{letter["subject"]}‬'


def test_the_account_s_own_answer_says_what_waits_for_a_superuser(api, rows, chief, django_assert_max_num_queries):
    asked(username='more', state='more')
    api.force_authenticate(chief)
    with django_assert_max_num_queries(4):          # the account, its newest request and access, the count
        assert api.get('/api/access/').json()['desk'] == {'waiting': 3}
    api.force_authenticate(make_user('staff', staff=True))
    assert api.get('/api/access/').json()['desk'] is None


def test_the_desk_s_limit_counts_each_account_apart(api, chief, monkeypatch):
    from django.core.cache import cache

    from apps.opendata.throttles import ScopedRate
    monkeypatch.setattr(ScopedRate, 'THROTTLE_RATES', {**ScopedRate.THROTTLE_RATES, 'access_desk': '2/min'})
    cache.clear()
    api.force_authenticate(chief)
    assert [api.get(DESK + 'log/').status_code for _ in range(3)] == [200, 200, 429]
    second = make_user('second', staff=True)
    second.is_superuser = True
    second.save()
    api.force_authenticate(second)                   # the same address, another account
    assert api.get(DESK + 'log/').status_code == 200
    cache.clear()
