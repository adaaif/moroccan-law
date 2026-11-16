"""The staff's three answers to a request (services/requests.py): accept, ask for more, decline. Only a superuser decides,
never on their own request, and a request is decided once; each decision keeps who and when and sends its letter. And
the queue's figures, and the retention /privacy states."""
from datetime import date, timedelta

import pytest
from django.conf import settings as django_settings
from django.core import mail
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, Request
from apps.opendata.services import access as accesses
from apps.opendata.services import requests
from apps.opendata.tests.helpers import accepted, asked

pytestmark = pytest.mark.django_db


@pytest.fixture
def chief():
    chief = make_user('chief', staff=True)
    chief.is_superuser = True
    chief.save()
    return chief


def refused(fn, *args, **kwargs) -> tuple:
    with pytest.raises(Refused) as caught:
        fn(*args, **kwargs)
    return caught.value.field, caught.value.code


def test_only_a_superuser_decides_and_never_their_own_request(chief):
    request = asked()
    staff = make_user('staff', staff=True)
    for act, extra in ((requests.accept, {'api': True, 'data': False, 'size': 'try'}),
                       (requests.ask, {'line': 'Who?'}), (requests.decline, {'reason': 'later'})):
        assert refused(act, request, staff, **extra) == ('by', 'not_superuser')
        assert refused(act, asked(chief, username='x'), chief, **extra) == ('by', 'own')
        Request.objects.filter(user=chief).delete()
    request.refresh_from_db()
    assert request.state == Request.State.WAITING and mail.outbox == []


def test_accepting_makes_the_access_with_what_the_staff_grants(chief, settings):
    settings.SITE_URL = 'https://example.org'
    request = asked(wants_api=True, wants_data=True)
    made = requests.accept(request, chief, api=False, data=True, size='app')
    request.refresh_from_db()
    assert (request.state, request.decided_by, request.decided_at is not None) == ('accepted', chief, True)
    assert (made.user, made.request, made.api, made.data, made.size) == (request.user, request, False, True, 'app')
    assert made.ends_on == accesses.months_after(timezone.localdate(), django_settings.ACCESS_MONTHS)
    assert (made.minute, made.calls, made.articles) == (None, None, None)
    [letter] = mail.outbox
    assert 'قُبل طلبك' in letter.subject and 'الوصول إلى قاعدة البيانات حتى' in letter.body
    assert f'{made.ends_on:%d/%m/%Y}' in letter.body
    assert 'الطلبات في الدقيقة: 120\nالطلبات في اليوم: 20000\nالمواد في اليوم: 10000' in letter.body
    assert 'https://example.org/data/access' in letter.body
    assert refused(requests.accept, request, chief, api=True, data=False, size='app') == ('request', 'decided')


def test_a_partners_numbers_are_its_own_and_a_named_sizes_are_the_settings(chief):
    ends = timezone.localdate() + timedelta(days=90)
    partner = requests.accept(asked(username='p'), chief, api=True, data=False, size='partner', ends_on=ends,
                              minute=600, calls=None, articles=50_000)
    assert (partner.ends_on, partner.minute, partner.calls, partner.articles) == (ends, 600, None, 50_000)
    assert partner.limits() == {'minute': 600, 'calls': django_settings.ACCESS_SIZES['app']['calls'],
                                'articles': 50_000}
    tried = requests.accept(asked(username='t'), chief, api=True, data=False, size='try', minute=600)
    assert tried.minute is None and tried.limits() == django_settings.ACCESS_SIZES['try']
    assert 'الطلبات في الدقيقة: 600' in mail.outbox[0].body


@pytest.mark.parametrize('given, refusal', [
    ({'api': False, 'data': False, 'size': 'try'}, ('wants', 'required')),
    ({'api': True, 'data': False, 'size': 'huge'}, ('size', 'invalid')),
    ({'api': True, 'data': False, 'size': 'partner', 'minute': 0}, ('minute', 'invalid')),
    ({'api': True, 'data': False, 'size': 'partner', 'calls': True}, ('calls', 'invalid')),
    ({'api': True, 'data': False, 'size': 'partner', 'articles': '9'}, ('articles', 'invalid')),
    ({'api': True, 'data': False, 'size': 'try', 'ends_on': date(2020, 1, 1)}, ('ends_on', 'past')),
])
def test_what_an_acceptance_must_say(chief, given, refusal):
    request = asked()
    assert refused(requests.accept, request, chief, **given) == refusal
    assert not Access.objects.exists()


def test_an_account_holds_one_live_access(chief):
    holder = accepted()
    again = asked(holder.user, username='holder')
    assert refused(requests.accept, again, chief, api=True, data=False, size='try') == ('access', 'live')


def test_an_access_whose_date_passed_is_ended_before_the_new_one(chief):
    stale = accepted(days=-3)
    again = asked(stale.user, username='holder')
    made = requests.accept(again, chief, api=True, data=False, size='try')
    stale.refresh_from_db()
    assert (stale.state, stale.ended_reason) == ('ended', 'expired') and made.state == 'live'


def test_asking_for_more_sends_one_line(chief):
    request = asked(answer='an earlier answer')
    for line, code in (('', 'required'), ('x' * 301, 'too_long'), (3, 'invalid')):
        assert refused(requests.ask, request, chief, line) == ('line', code)
    requests.ask(request, chief, '  Which newsroom do you work for?  ')
    request.refresh_from_db()
    assert (request.state, request.asked, request.answer, request.decided_by) == (
        'more', 'Which newsroom do you work for?', '', chief)
    [letter] = mail.outbox
    assert '«Which newsroom do you work for?»' in letter.body
    requests.ask(request, chief, 'And its address?')            # asked again while the answer is awaited
    request.refresh_from_db()
    assert request.asked == 'And its address?'


def test_declining_says_the_reason_and_the_day_to_ask_again(chief):
    request = asked()
    request.user.preferred_language = 'fr'
    request.user.save()
    assert refused(requests.decline, request, chief, 'rude') == ('reason', 'invalid')
    requests.decline(request, chief, 'scope')
    request.refresh_from_db()
    assert (request.state, request.reason, request.decided_by) == ('declined', 'scope', chief)
    again = timezone.localdate() + timedelta(days=django_settings.ACCESS_ASK_AGAIN_DAYS)
    [letter] = mail.outbox
    assert letter.subject.startswith('La réponse à votre demande')
    assert 'vous demandez plus que l’usage décrit n’en a besoin.' in letter.body
    assert f'à partir du {again:%d/%m/%Y}' in letter.body
    assert requests.ask_again_on(request) == again
    assert refused(requests.decline, request, chief, 'later') == ('request', 'decided')


def test_every_reason_and_every_end_has_its_words_in_both_languages():
    for lang in ('ar', 'fr'):
        words = accesses.mail.ACCESS_WORDS[lang]
        assert set(words['declined']) == set(Request.Reason.values)
        assert set(words['ended']) == set(Access.Ended.values) - {'account'}
        assert set(words['granted']) == {'api', 'data', 'both'}


def test_the_queues_figures(django_assert_num_queries):
    now = timezone.now()
    asked(username='a')
    waiting = asked(username='b')
    six = now - timedelta(days=6)
    Request.objects.filter(pk=waiting.pk).update(created_at=six, waiting_since=six)
    for name, state, waited in (('c', 'accepted', 2), ('d', 'accepted', 4), ('e', 'declined', 9)):
        r = asked(username=name, state=state, decided_at=now)
        Request.objects.filter(pk=r.pk).update(created_at=now - timedelta(days=waited))
    old = asked(username='f', state='declined', decided_at=now - timedelta(days=40))
    Request.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=45))
    accepted(username='g', days=12)
    accepted(username='h', days=80)
    with django_assert_num_queries(requests.QUERIES):
        figures = requests.counted()
    # Received: every request but the one sent 45 days ago (the helper's accepted ones were sent today, undated).
    assert figures == {'received': 7, 'accepted': 2, 'declined': 1, 'waiting': 2, 'median_days': 4.0,
                       'oldest_days': 6, 'ending': 1}
    assert requests.lines(figures) == [
        'Access requests, the last 30 days: 7 received, 2 accepted, 1 declined; a median of 4 days to an answer.',
        'Waiting for an answer: 2, the oldest for 6 days. Accesses ending within 30 days: 1.']
    Access.objects.all().delete()
    Request.objects.all().delete()
    assert requests.lines(requests.counted()) == [
        'Access requests, the last 30 days: 0 received, 0 accepted, 0 declined; none answered.',
        'Waiting for an answer: none. Accesses ending within 30 days: 0.']


def test_old_requests_lose_their_typed_answers_as_privacy_says():
    today = timezone.localdate()
    now = timezone.now()
    typed = {'runs_at': 'https://example.org', 'asked': 'Who?', 'answer': 'Us.'}
    fresh = asked(username='a', state='declined', decided_at=now - timedelta(days=150), **typed)
    stale = asked(username='b', state='declined', decided_at=now - timedelta(days=200), **typed)
    ended_long_ago = accepted(username='c')
    ended_lately = accepted(username='d')
    live = accepted(username='e')
    Access.objects.filter(pk=ended_long_ago.pk).update(state='ended', ended_at=now - timedelta(days=400))
    Access.objects.filter(pk=ended_lately.pk).update(state='ended', ended_at=now - timedelta(days=300))
    assert requests.forget_typed(today) == 2
    emptied = {r.pk for r in Request.objects.filter(name='', purpose='', runs_at='', asked='', answer='')}
    assert emptied == {stale.pk, ended_long_ago.request_id}
    for kept in (fresh, ended_lately.request, live.request):
        kept.refresh_from_db()
        assert kept.name and kept.purpose
    stale.refresh_from_db()
    assert (stale.state, stale.kind, stale.decided_at is not None) == ('declined', 'school', True)
    assert requests.forget_typed(today) == 0                    # emptied once


@pytest.mark.parametrize('day, months, then', [
    (date(2026, 1, 31), 1, date(2026, 2, 28)), (date(2028, 1, 31), 1, date(2028, 2, 29)),
    (date(2026, 11, 16), 12, date(2027, 11, 16)), (date(2026, 11, 16), -6, date(2026, 5, 16)),
    (date(2026, 3, 31), -1, date(2026, 2, 28)), (date(2026, 12, 5), 1, date(2027, 1, 5)),
])
def test_months_after(day, months, then):
    assert accesses.months_after(day, months) == then
