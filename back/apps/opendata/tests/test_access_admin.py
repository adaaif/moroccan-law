"""Access on request in the admin: the requests open on the waiting ones, oldest first, with the queue's figures; a
request's page shows the six answers and the account around them, and decides through three small forms; an access's
page ends or renews it; the accesses' list says each one's use of the last 30 days in its own query; only a superuser
decides, never on their own request."""
from datetime import timedelta

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.core import mail
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, AccessDay, ApiKey, Request
from apps.opendata.services import access as accesses
from apps.opendata.tests.helpers import accepted, asked, keyed

pytestmark = pytest.mark.django_db

REQUESTS = reverse('admin:opendata_request_changelist')
ACCESSES = reverse('admin:opendata_access_changelist')


def page_of(model, pk, act=None) -> str:
    name = model._meta.model_name
    return reverse(f'admin:opendata_{name}_{act}' if act else f'admin:opendata_{name}_change', args=[pk])


def test_the_requests_open_on_the_waiting_ones_oldest_first_with_the_queues_figures(admin_client):
    now = timezone.now()
    newer, older = asked(username='newer'), asked(username='older')
    four = now - timedelta(days=4)
    Request.objects.filter(pk=older.pk).update(created_at=four, waiting_since=four)
    decided = asked(username='decided', state='declined', reason='later', decided_at=now)
    page = admin_client.get(REQUESTS)
    assert list(page.context['cl'].result_list) == [older, newer]
    text = page.content.decode()
    assert 'Access requests, the last 30 days: 3 received, 0 accepted, 1 declined' in text
    assert 'Waiting for an answer: 2, the oldest for 4 days.' in text
    every = admin_client.get(REQUESTS, {'state': 'all'}).context['cl'].result_list
    assert list(every) == [decided, newer, older]                   # every state: the newest first
    assert list(admin_client.get(REQUESTS, {'state': 'declined'}).context['cl'].result_list) == [decided]
    found = admin_client.get(REQUESTS, {'q': 'older@example', 'state': 'all'}).context['cl'].result_list
    assert list(found) == [older]


def test_a_requests_page_shows_the_answers_the_account_and_what_came_before(admin_client):
    request = asked(purpose='A study of the family code.', runs_at='https://lab.example.org')
    earlier = asked(request.user, state='declined', reason='unclear', decided_at=timezone.now() - timedelta(days=40))
    holder = accepted(username='holder')
    text = admin_client.get(page_of(Request, request.pk)).content.decode()
    for words in ('A study of the family code.', 'https://lab.example.org', '30 days, since',
                  'asker@example.org: proven on', 'The use is not clear: say more',
                  page_of(Request, earlier.pk), page_of(Request, request.pk, 'accept'),
                  page_of(Request, request.pk, 'ask'), page_of(Request, request.pk, 'decline')):
        assert words in text, words
    text = admin_client.get(page_of(Request, holder.request_id)).content.decode()
    assert page_of(Access, holder.pk) in text and 'Decided.' in text and page_of(Request, holder.request_id,
                                                                               'accept') not in text


def test_accepting_in_the_admin_makes_the_access_and_writes_to_the_person(admin_client):
    request = asked(wants_data=True)
    page = admin_client.get(page_of(Request, request.pk, 'accept'))
    assert 'How a code changed over time. Asks for API + database; volume small' in page.content.decode()
    form = page.context['form']
    assert form.initial['api'] and form.initial['data'] and form.initial['size'] == 'try'
    assert form.initial['ends_on'] == accesses.default_end()
    ends = timezone.localdate() + timedelta(days=200)
    r = admin_client.post(page_of(Request, request.pk, 'accept'),
                          {'api': 'on', 'size': 'partner', 'minute': '300', 'calls': '', 'articles': '90000',
                           'ends_on': ends.isoformat()})
    assert r.status_code == 302 and r.url == page_of(Request, request.pk)
    made = Access.objects.get(request=request)
    assert (made.api, made.data, made.size, made.minute, made.calls, made.articles, made.ends_on) == (
        True, False, 'partner', 300, None, 90000, ends)
    request.refresh_from_db()
    assert request.state == 'accepted' and request.decided_by.username == 'admin'
    assert len(mail.outbox) == 1 and LogEntry.objects.filter(object_id=str(request.pk)).exists()


def test_asking_and_declining_in_the_admin(admin_client):
    request = asked()
    assert admin_client.post(page_of(Request, request.pk, 'ask'), {'line': 'Which school?'}).status_code == 302
    request.refresh_from_db()
    assert (request.state, request.asked) == ('more', 'Which school?')
    assert admin_client.post(page_of(Request, request.pk, 'decline'), {'reason': 'identity'}).status_code == 302
    request.refresh_from_db()
    assert (request.state, request.reason) == ('declined', 'identity')
    assert len(mail.outbox) == 2


def test_a_refusal_is_said_on_the_form(admin_client):
    request = asked()
    r = admin_client.post(page_of(Request, request.pk, 'accept'),
                          {'size': 'try', 'ends_on': accesses.default_end().isoformat()})
    assert r.status_code == 200 and 'Grant the API, the database or both.' in r.content.decode()
    mine = asked(User.objects.get(username='admin'), username='admin')
    text = admin_client.get(page_of(Request, mine.pk)).content.decode()
    assert 'Only a superuser decides, never on their own request.' in text
    r = admin_client.post(page_of(Request, mine.pk, 'decline'), {'reason': 'later'})
    assert 'Nobody decides their own request.' in r.content.decode()
    assert not Access.objects.exists() and Request.objects.filter(state='waiting').count() == 2


def test_only_a_superuser_opens_the_forms(client):
    request = asked()
    staff = make_user('staff', staff=True)
    staff.user_permissions.add(*Permission.objects.filter(codename__in=('view_request', 'view_access')))
    client.force_login(staff)
    assert client.get(REQUESTS).status_code == 200
    text = client.get(page_of(Request, request.pk)).content.decode()
    assert page_of(Request, request.pk, 'accept') not in text
    for act in ('accept', 'ask', 'decline'):
        assert client.get(page_of(Request, request.pk, act)).status_code == 403
        assert client.post(page_of(Request, request.pk, act), {'reason': 'later', 'line': 'x'}).status_code == 403
    holder = accepted()
    assert client.post(page_of(Access, holder.pk, 'end'), {'reason': 'terms'}).status_code == 403
    request.refresh_from_db()
    holder.refresh_from_db()
    assert request.state == 'waiting' and holder.state == 'live'


def test_the_accesses_say_their_use_of_the_last_30_days(admin_client):
    access = accepted(days=20)
    today = timezone.localdate()
    for back, calls in ((0, 5), (29, 7), (30, 1000)):            # the 31st day back is not counted
        AccessDay.objects.create(access=access, day=today - timedelta(days=back), calls=calls, articles=calls * 2)
    page = admin_client.get(ACCESSES)
    [row] = page.context['cl'].result_list
    assert (row.calls_30, row.articles_30) == (12, 24)
    assert 'Accesses ending within 30 days: 1.' in page.content.decode()
    assert list(admin_client.get(ACCESSES, {'ends': 'soon'}).context['cl'].result_list) == [access]
    assert list(admin_client.get(ACCESSES, {'ends': 'passed'}).context['cl'].result_list) == []
    text = admin_client.get(page_of(Access, access.pk)).content.decode()
    assert '12 calls, 24 articles' in text and page_of(Access, access.pk, 'end') in text


def test_the_accesses_list_costs_the_same_whatever_their_days(admin_client):
    def cost() -> int:
        with CaptureQueriesContext(connection) as queries:
            admin_client.get(ACCESSES)
        return len(queries)
    made = [accepted(username=f'h{i}') for i in range(3)]
    admin_client.get(ACCESSES)
    few = cost()
    for a in made:
        for back in range(25):
            AccessDay.objects.create(access=a, day=timezone.localdate() - timedelta(days=back), calls=1)
    assert cost() == few


def test_ending_and_renewing_in_the_admin(admin_client):
    access, _ = keyed()
    page = admin_client.get(page_of(Access, access.pk, 'renew'))
    assert '120 a minute, 20,000 calls and 10,000 articles a day, until' in page.content.decode()
    form = page.context['form']
    assert form.initial['ends_on'] == accesses.default_end()
    later = timezone.localdate() + timedelta(days=500)
    assert admin_client.post(page_of(Access, access.pk, 'renew'), {'ends_on': later.isoformat()}).status_code == 302
    access.refresh_from_db()
    assert access.ends_on == later and access.renewed_at
    r = admin_client.post(page_of(Access, access.pk, 'end'), {'reason': 'expired'})
    assert r.status_code == 200 and 'reason' in r.context['form'].errors          # the staff's three reasons only
    assert admin_client.post(page_of(Access, access.pk, 'end'), {'reason': 'unused'}).status_code == 302
    access.refresh_from_db()
    assert (access.state, access.ended_reason, access.ended_by.username) == ('ended', 'unused', 'admin')
    assert not ApiKey.objects.filter(access=access, ended_at=None).exists()
    renewed, ended = mail.outbox
    assert f'{later:%d/%m/%Y}' in renewed.subject and 'لم يُستعمل منذ مدة.' in ended.body
    r = admin_client.post(page_of(Access, access.pk, 'end'), {'reason': 'terms'})
    assert 'This access is ended.' in r.content.decode()
    assert '—' in admin_client.get(page_of(Access, access.pk)).content.decode()


def test_the_index_counts_the_requests_waiting(admin_client):
    asked(username='a')
    asked(username='b', state='more')
    text = admin_client.get(reverse('admin:index')).content.decode()
    assert f'{REQUESTS}?state=waiting' in text and '1 requests for access' in text
    assert 'Access requests' in text


def test_decisions_in_the_admin_leave_events_shown_on_each_page_and_in_the_log(admin_client):
    request = asked()
    admin_client.post(page_of(Request, request.pk, 'ask'), {'line': 'Which school?'})
    text = admin_client.get(page_of(Request, request.pk)).content.decode()
    assert 'The staff asked for more' in text and 'line Which school?' in text
    access, _ = keyed()
    later = timezone.localdate() + timedelta(days=300)
    admin_client.post(page_of(Access, access.pk, 'renew'), {'ends_on': later.isoformat()})
    text = admin_client.get(page_of(Access, access.pk)).content.decode()
    assert 'An access was given a new end date' in text and f'ends_on {later.isoformat()}' in text
    assert f'{reverse("admin:opendata_event_changelist")}?access={access.pk}' in text
    log = admin_client.get(reverse('admin:opendata_event_changelist'))
    assert [e.act for e in log.context['cl'].result_list] == ['renewed', 'asked']
    assert [e.act for e in admin_client.get(reverse('admin:opendata_event_changelist'),
                                            {'access': access.pk}).context['cl'].result_list] == ['renewed']


def test_a_change_request_s_page_names_its_access(admin_client):
    access = accepted()
    change = asked(access.user, change_of=access, wants_data=True, wanted_size='app')
    text = admin_client.get(page_of(Request, change.pk)).content.decode()
    assert page_of(Access, access.pk) in text and 'App, API' in text


def test_accepting_a_change_in_the_admin_starts_from_its_access(admin_client):
    access = accepted(size='app', days=90)
    change = asked(access.user, change_of=access, wants_data=True, wanted_size='partner')
    form = admin_client.get(page_of(Request, change.pk, 'accept')).context['form']
    assert (form.initial['size'], form.initial['ends_on'], form.initial['data']) == ('partner', access.ends_on, True)
    r = admin_client.post(page_of(Request, change.pk, 'accept'),
                          {'api': 'on', 'data': 'on', 'size': 'partner', 'calls': '40000',
                           'ends_on': access.ends_on.isoformat()})
    assert r.status_code == 302
    access.refresh_from_db()
    assert (access.data, access.size, access.calls, Access.objects.count()) == (True, 'partner', 40000, 1)


def test_the_queue_counts_from_the_last_time_a_request_began_to_wait(admin_client):
    now = timezone.now()
    answered, waiting = asked(username='answered'), asked(username='waiting')
    Request.objects.filter(pk=answered.pk).update(created_at=now - timedelta(days=9), waiting_since=now)
    Request.objects.filter(pk=waiting.pk).update(created_at=now - timedelta(days=3),
                                                 waiting_since=now - timedelta(days=3))
    page = admin_client.get(REQUESTS)
    assert list(page.context['cl'].result_list) == [waiting, answered]
    assert 'Waiting for an answer: 2, the oldest for 3 days.' in page.content.decode()
