"""Every act on a request or an access leaves one event (services/log.py), in the service that does it, whichever
door it came by: sent and answered by the account; asked, accepted, declined by a superuser; an access changed,
renewed, ended (by the staff, its holder, the night's job or the account's deletion); a key made and ended. The
details hold codes, numbers and dates, never a key nor what the account typed; the account's export holds the acts on
its own requests and accesses, without who decided."""
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, ApiKey, Event, Request
from apps.opendata.services import access as accesses
from apps.opendata.services import keys, log, requests
from apps.opendata.tests.helpers import accepted, asked, keyed

pytestmark = pytest.mark.django_db

SEND, ANSWER, END = '/api/access/request/', '/api/access/request/answer/', '/api/access/end/'


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


def acts(**where) -> list[tuple]:
    return [(e.act, e.by.username if e.by else None, e.details)
            for e in Event.objects.filter(**where).select_related('by').order_by('at', 'pk')]


def form(**fields) -> dict:
    return {'name': 'Une école', 'kind': 'school', 'purpose': 'Typed words: how the code changed.',
            'wants_api': True, 'wants_data': False, 'runs_at': 'https://example.org/lab', 'volume': 'medium',
            'commercial': False, 'terms': '2026-11-16', 'consent': True, **fields}


def test_a_request_s_life_is_its_events(api, chief, settings):
    settings.ACCESS_TERMS = '2026-11-16'
    person = make_user('salma')
    api.force_authenticate(person)
    assert api.post(SEND, form(), format='json').status_code == 201
    r = Request.objects.get()
    requests.ask(r, chief, 'Which school?')
    sent_at = r.waiting_since
    assert api.post(ANSWER, {'answer': 'The law faculty of Fes.'}, format='json').status_code == 200
    r.refresh_from_db()
    assert r.waiting_since > sent_at                    # it waits again from its answer
    made = requests.accept(r, chief, api=True, data=False, size='app')
    assert acts(request=r) == [
        ('sent', 'salma', {'api': True, 'data': False, 'volume': 'medium'}),
        ('asked', 'chief', {'line': 'Which school?'}),
        ('answered', 'salma', {}),
        ('accepted', 'chief', {'api': True, 'data': False, 'size': 'app', 'minute': None, 'calls': None,
                               'articles': None, 'ends_on': made.ends_on.isoformat()}),
    ]
    assert Event.objects.get(act='accepted').access == made
    text = str(list(Event.objects.values_list('details', flat=True)))
    assert 'Typed words' not in text and 'Fes' not in text and 'Une école' not in text


def test_a_decline_keeps_its_reason(chief):
    r = asked()
    requests.decline(r, chief, 'scope')
    assert acts(request=r) == [('declined', 'chief', {'reason': 'scope'})]


def test_an_access_s_ends_say_who_ended_it_and_why(api, chief):
    by_staff, by_holder, by_night, by_leaving = (accepted(username=n) for n in ('a', 'b', 'c', 'd'))
    accesses.end(by_staff, Access.Ended.TERMS, by=chief)
    api.force_authenticate(by_holder.user)
    assert api.post(END).status_code == 200
    Access.objects.filter(pk=by_night.pk).update(ends_on=timezone.localdate() - timedelta(days=1))
    accesses.expire()
    accesses.leave(by_leaving.user)
    assert acts(access=by_staff) == [('ended', 'chief', {'reason': 'terms'})]
    assert acts(access=by_holder) == [('ended', 'b', {'reason': 'asked'})]
    assert acts(access=by_night) == [('ended', None, {'reason': 'expired'})]
    assert acts(access=by_leaving) == [('ended', None, {'reason': 'account'})]


def test_a_renewal_keeps_the_date_before_and_after(chief):
    access = accepted(days=10)
    before = access.ends_on
    later = timezone.localdate() + timedelta(days=200)
    accesses.renew(access, chief, later)
    assert acts(access=access) == [('renewed', 'chief', {'ends_on': later.isoformat(), 'before': before.isoformat()})]
    [letter] = mail.outbox
    assert f'{later:%d/%m/%Y}' in letter.subject and 'مفاتيحك تبقى كما هي' in letter.body


def test_a_key_made_and_ended_by_its_holder_never_says_the_key(api):
    access = accepted()
    api.force_authenticate(access.user)
    made = api.post('/api/access/keys/', {'name': 'the lab server'}, format='json').json()
    assert api.delete(f'/api/access/keys/{made["id"]}/').status_code == 204
    assert acts(access=access) == [('key_made', 'holder', {'key': made['id']}),
                                   ('key_ended', 'holder', {'key': made['id']})]
    row = ApiKey.objects.get()
    text = str(list(Event.objects.values_list('details', flat=True)))
    assert made['key'] not in text and row.key_hash not in text and row.prefix not in text and 'lab' not in text


def test_a_key_ended_once_is_logged_once():
    access, _ = keyed()
    key = ApiKey.objects.get()
    keys.end(key)
    keys.end(key)
    assert [a for a, *_ in acts(access=access)] == ['key_ended']


def test_a_detail_s_day_is_kept_as_written():
    e = log.note('renewed', access=accepted(), ends_on=timezone.localdate(), before={'on': timezone.localdate()})
    e.refresh_from_db()
    today = timezone.localdate().isoformat()
    assert e.details == {'ends_on': today, 'before': {'on': today}} and e.by is None


def test_the_export_holds_the_acts_on_its_own_rows_not_who_decided(api, chief):
    access, _ = keyed()
    accesses.renew(access, chief, timezone.localdate() + timedelta(days=90))
    other = accepted(username='other')
    accesses.end(other, Access.Ended.UNUSED, by=chief)
    api.force_authenticate(access.user)
    events = api.get('/api/auth/me/export/').json()['access_events']
    assert [(e['act'], e['access']) for e in events] == [('renewed', access.pk)]
    assert set(events[0]) == {'act', 'day', 'request', 'access', 'details'}
    assert events[0]['day'] == timezone.localdate().isoformat() and 'chief' not in str(events)
