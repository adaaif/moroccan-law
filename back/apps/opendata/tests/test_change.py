"""Changing an access: the holder's request to change it (POST /api/access/change/), accepted in place with its keys
working on at once under the new limits; the staff changing it, renewing it, ending one of its keys; and the letter
each answer would send, made by the same words as the one that goes."""
from datetime import timedelta

import pytest
from django.conf import settings as django_settings
from django.core import mail
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, ApiKey, Event, Request
from apps.opendata.services import access as accesses
from apps.opendata.services import keys, requests
from apps.opendata.tests.helpers import accepted, asked, keyed

pytestmark = pytest.mark.django_db

ACCESS, CHANGE = '/api/access/', '/api/access/change/'


@pytest.fixture(autouse=True)
def on_request(settings):
    settings.OPEN_DATA = 'request'
    settings.ACCESS_LETTER_TO = []
    settings.SITE_URL = 'https://example.org'


@pytest.fixture
def chief():
    chief = make_user('chief', staff=True)
    chief.is_superuser = True
    chief.save()
    return chief


@pytest.fixture
def holder(api):
    access, key = keyed(size='try')
    api.force_authenticate(access.user)
    return access, key


def errors(response) -> list[tuple]:
    return [(e['field'], e['code']) for e in response.json()['errors']]


def refused(fn, *args, **kwargs) -> tuple:
    with pytest.raises(Refused) as caught:
        fn(*args, **kwargs)
    return caught.value.field, caught.value.code


def test_a_holder_asks_to_change_its_access(api, holder, settings):
    settings.ACCESS_LETTER_TO = ['staff@example.org']
    access, _ = holder
    r = api.post(CHANGE, {'wants_api': True, 'wants_data': True, 'size': 'app', 'why': ' We need the database. '},
                 format='json')
    assert r.status_code == 201 and r.json() == api.get(ACCESS).json()
    shown = r.json()['request']
    assert (shown['change_of'], shown['wanted_size'], shown['state'], shown['purpose']) == (
        access.pk, 'app', 'waiting', 'We need the database.')
    assert shown['due_on'] == requests.working_days_after(timezone.localdate(), 5).isoformat()
    made = Request.objects.get(change_of=access)
    origin = access.request
    assert (made.name, made.kind, made.volume, made.terms) == (origin.name, origin.kind, origin.volume, origin.terms)
    received, told = mail.outbox
    assert 'وصل طلبك' in received.subject and 'الواجهة البرمجية (API) وقاعدة البيانات' in received.body
    assert told.subject.endswith('a request to change an access from A research group')
    assert 'Holds now: the API; size try' in told.body
    assert 'Asks to hold: the API and the database; size app' in told.body
    assert errors(api.post(CHANGE, {'wants_data': True, 'why': 'again'}, format='json')) == [('request', 'open')]


@pytest.mark.parametrize('body, refusal', [
    ({'wants_api': True, 'why': 'x'}, ('change', 'nothing')),
    ({'wants_api': True, 'size': 'try', 'why': 'x'}, ('change', 'nothing')),
    ({'wants_api': False, 'wants_data': False, 'why': 'x'}, ('wants', 'required')),
    ({'wants_api': 'yes', 'why': 'x'}, ('wants_api', 'invalid')),
    ({'wants_api': True, 'size': 'huge', 'why': 'x'}, ('size', 'invalid')),
    ({'wants_api': True, 'size': 'app'}, ('why', 'required')),
    ({'wants_api': True, 'size': 'app', 'why': 'x' * 601}, ('why', 'too_long')),
])
def test_what_a_change_request_must_say(api, holder, body, refusal):
    r = api.post(CHANGE, body, format='json')
    assert (r.status_code, errors(r)) == (400, [refusal])
    assert not Request.objects.filter(change_of__isnull=False).exists()


def test_a_partner_may_ask_for_the_partner_size_again(api):
    access, _ = keyed(size='partner', minute=100)
    api.force_authenticate(access.user)
    body = {'wants_api': True, 'size': 'partner', 'why': 'More calls a day.'}
    assert api.post(CHANGE, body, format='json').status_code == 201


def test_who_may_ask_for_a_change(api, settings):
    assert api.post(CHANGE, {}, format='json').status_code == 401
    person = make_user('salma')
    api.force_authenticate(person)
    r = api.post(CHANGE, {'wants_api': True, 'why': 'x'}, format='json')
    assert (r.status_code, errors(r)) == (403, [('access', 'none')])
    access = accepted(person, username='salma')
    settings.OPEN_DATA = 'closed'
    assert errors(api.post(CHANGE, {'wants_data': True, 'why': 'x'}, format='json')) == [('access', 'closed')]
    settings.OPEN_DATA = 'request'
    asked(person, change_of=access, state='declined', reason='later', decided_at=timezone.now())
    r = api.post(CHANGE, {'wants_data': True, 'why': 'x'}, format='json')
    again = timezone.localdate() + timedelta(days=django_settings.ACCESS_ASK_AGAIN_DAYS)
    assert r.status_code == 409 and r.json()['errors'] == [{'field': 'request', 'code': 'too_soon',
                                                            'on': again.isoformat()}]


def test_accepting_a_change_changes_the_access_in_place_and_its_key_works_on(api, chief, holder):
    access, key = holder
    ends = access.ends_on
    assert api.post(CHANGE, {'wants_api': True, 'wants_data': True, 'size': 'app', 'why': 'x'},
                    format='json').status_code == 201
    assert keys.read(key).calls == django_settings.ACCESS_SIZES['try']['calls']        # kept a minute
    r = Request.objects.get(change_of=access)
    mail.outbox.clear()
    preview = requests.letter_of(r, chief, 'accept', api=True, data=True, size='app')
    changed = requests.accept(r, chief, api=True, data=True, size='app')
    assert changed.pk == access.pk and Access.objects.count() == 1
    access.refresh_from_db()
    assert (access.api, access.data, access.size, access.ends_on) == (True, True, 'app', ends)
    assert keys.read(key).calls == django_settings.ACCESS_SIZES['app']['calls']        # at once
    assert ApiKey.objects.get().ended_at is None
    [letter] = mail.outbox
    assert (letter.subject, letter.body) == (f'‫{preview.subject}‬', preview.body)
    assert 'قُبل طلبك لتعديل وصولك' in letter.subject and 'مفاتيحك تبقى كما هي' in letter.body
    assert 'الطلبات في اليوم: 20000' in letter.body and f'{ends:%d/%m/%Y}' in letter.body
    assert 'https://example.org/data/access' in letter.body
    event = Event.objects.get(act='accepted')
    assert event.request == r and event.access == access
    assert event.details['before'] == {'api': True, 'data': False, 'size': 'try', 'minute': None, 'calls': None,
                                       'articles': None}
    body = api.get(ACCESS).json()
    assert body['request']['state'] == 'accepted' and body['access']['data'] is True


def test_a_change_accepted_with_an_end_date_moves_it(chief, holder):
    access, _ = holder
    r = asked(access.user, change_of=access, wants_api=True, wants_data=False, wanted_size='partner')
    later = timezone.localdate() + timedelta(days=500)
    requests.accept(r, chief, api=True, data=False, size='partner', ends_on=later, minute=600)
    access.refresh_from_db()
    assert (access.size, access.minute, access.ends_on) == ('partner', 600, later)


def test_a_change_of_an_ended_access_cannot_be_accepted(chief, holder):
    access, _ = holder
    r = asked(access.user, change_of=access, wants_data=True)
    accesses.end(access, Access.Ended.UNUSED, by=chief)
    assert refused(requests.accept, r, chief, api=True, data=True, size='app') == ('access', 'ended')
    r.refresh_from_db()
    assert r.state == 'waiting'
    requests.decline(r, chief, 'later')                  # declined as any request


def test_each_answer_s_letter_is_the_one_shown_before(chief):
    request = asked(wants_data=True)
    request.user.preferred_language = 'fr'
    request.user.save()
    for act, fields, do in (
            ('ask', {'line': 'Which school?'}, lambda: requests.ask(request, chief, 'Which school?')),
            ('accept', {'api': True, 'data': True, 'size': 'try'},
             lambda: requests.accept(request, chief, api=True, data=True, size='try'))):
        shown = requests.letter_of(request, chief, act, **fields)
        mail.outbox.clear()
        do()
        [letter] = mail.outbox
        assert (letter.subject, letter.body) == (shown.subject, shown.body) and shown.language == 'fr'
    other = asked(username='other')
    shown = requests.letter_of(other, chief, 'decline', reason='identity')
    requests.decline(other, chief, 'identity')
    assert (mail.outbox[-1].subject, mail.outbox[-1].body) == (f'‫{shown.subject}‬', shown.body)
    assert refused(requests.letter_of, other, chief, 'decline', reason='later') == ('request', 'decided')


def test_a_preview_is_refused_as_its_act_would_be(chief):
    request = asked()
    for act, fields, refusal in (('accept', {'api': False, 'data': False, 'size': 'try'}, ('wants', 'required')),
                                 ('accept', {'api': True, 'data': False, 'size': 'x'}, ('size', 'invalid')),
                                 ('ask', {'line': ''}, ('line', 'required')),
                                 ('decline', {'reason': 'rude'}, ('reason', 'invalid')),
                                 ('stamp', {}, ('act', 'invalid'))):
        assert refused(requests.letter_of, request, chief, act, **fields) == refusal
    assert refused(requests.letter_of, asked(chief, username='chief'), chief, 'ask', line='x') == ('by', 'own')
    assert mail.outbox == [] and not Event.objects.exists()


def test_the_staff_changes_an_access_and_its_keys_work_on(chief, holder):
    access, key = holder
    assert keys.read(key).articles == django_settings.ACCESS_SIZES['try']['articles']
    accesses.change(access, chief, data=True, size='partner', calls=50_000)
    access.refresh_from_db()
    assert (access.api, access.data, access.size, access.calls, access.minute) == (True, True, 'partner', 50_000, None)
    assert keys.read(key).calls == 50_000
    [letter] = mail.outbox
    assert 'تبدّل وصولك' in letter.subject and 'الطلبات في اليوم: 50000' in letter.body
    accesses.change(access, chief, minute=300)                   # a partner's numbers left out stay
    access.refresh_from_db()
    assert (access.minute, access.calls) == (300, 50_000)
    accesses.change(access, chief, size='app')                   # a named size carries the settings' numbers
    access.refresh_from_db()
    assert (access.minute, access.calls, access.articles) == (None, None, None)
    [first, *_] = Event.objects.filter(act='changed').order_by('pk')
    assert first.by == chief and first.details['before']['size'] == 'try' and first.details['after']['calls'] == 50_000


@pytest.mark.parametrize('given, refusal', [
    ({'api': False}, ('wants', 'required')),
    ({'size': 'try'}, ('change', 'nothing')),
    ({}, ('change', 'nothing')),
    ({'size': 'huge'}, ('size', 'invalid')),
    ({'api': 'yes'}, ('api', 'invalid')),
    ({'size': 'partner', 'calls': 0}, ('calls', 'invalid')),
    ({'size': 'partner', 'calls': 2**31}, ('calls', 'invalid')),
])
def test_what_a_change_must_say(chief, holder, given, refusal):
    access, _ = holder
    assert refused(accesses.change, access, chief, **given) == refusal
    assert not Event.objects.filter(act='changed').exists() and mail.outbox == []


def test_only_a_superuser_changes_and_only_a_live_access(chief, holder):
    access, _ = holder
    assert refused(accesses.change, access, make_user('staff', staff=True), data=True) == ('by', 'not_superuser')
    accesses.end(access, Access.Ended.TERMS, by=chief)
    assert refused(accesses.change, access, chief, data=True) == ('access', 'ended')
    assert refused(accesses.renew, access, chief) == ('access', 'ended')
    stale = accepted(username='stale', days=-1)
    assert refused(accesses.change, stale, chief, data=True) == ('access', 'ended')


def test_the_staff_ends_a_leaked_key_and_its_holder_is_told_which(chief, holder):
    access, key = holder
    row = ApiKey.objects.get()
    keys.end_by_staff(row, chief)
    with pytest.raises(keys.Refused) as stopped:
        keys.read(key)
    assert stopped.value.code == 'ended'
    access.refresh_from_db()
    assert access.state == 'live'
    [letter] = mail.outbox
    assert 'أوقفنا أحد مفاتيح' in letter.subject and f'«tests» الذي يبدأ بـ {row.prefix}…' in letter.body
    assert key not in letter.body
    assert Event.objects.get(act='key_ended').by == chief
    assert refused(keys.end_by_staff, row, chief) == ('key', 'ended')
    unnamed, _ = ApiKey.issue(access)
    assert refused(keys.end_by_staff, unnamed, make_user('staff', staff=True)) == ('by', 'not_superuser')
    keys.end_by_staff(unnamed, chief)
    assert '«بلا اسم»' in mail.outbox[-1].body


def test_the_staff_ends_an_access_for_its_own_reasons_only(chief, holder):
    access, _ = holder
    assert refused(accesses.end_by_staff, access, chief, 'expired') == ('reason', 'invalid')
    assert refused(accesses.end_by_staff, access, make_user('staff', staff=True), 'terms') == ('by', 'not_superuser')
    accesses.end_by_staff(access, chief, 'leaked')
    assert refused(accesses.end_by_staff, access, chief, 'terms') == ('access', 'ended')


def test_a_change_request_of_an_ended_access_loses_its_words_with_the_access_s_request(chief):
    access = accepted()
    change = asked(access.user, change_of=access, state='accepted', decided_at=timezone.now(), username='holder')
    Access.objects.filter(pk=access.pk).update(state='ended', ended_at=timezone.now() - timedelta(days=400))
    assert requests.forget_typed() == 2
    change.refresh_from_db()
    assert change.purpose == '' and change.state == 'accepted'


@pytest.mark.parametrize('sent, n, due', [
    ('2026-11-16', 5, '2026-11-23'),            # a Monday: the Monday after
    ('2026-11-20', 5, '2026-11-27'),            # a Friday
    ('2026-11-21', 5, '2026-11-27'),            # a Saturday: the Friday after
    ('2026-11-22', 1, '2026-11-23'),
])
def test_the_day_an_answer_is_due_counts_working_days(sent, n, due):
    from datetime import date
    assert requests.working_days_after(date.fromisoformat(sent), n) == date.fromisoformat(due)


@pytest.mark.parametrize('today, due, left', [
    ('2026-11-16', '2026-11-23', 5), ('2026-11-23', '2026-11-23', 0), ('2026-11-24', '2026-11-23', -1),
    ('2026-11-30', '2026-11-27', -1), ('2026-11-21', '2026-11-23', 1), ('2026-12-01', '2026-11-23', -6),
])
def test_the_working_days_left(today, due, left):
    from datetime import date
    assert requests.days_left(date.fromisoformat(due), date.fromisoformat(today)) == left
    assert requests.days_left(None) is None


def test_only_a_waiting_request_is_due():
    r = asked()
    assert requests.due_on(r) == requests.working_days_after(timezone.localdate(r.waiting_since), 5)
    r.state = 'more'
    assert requests.due_on(r) is None
