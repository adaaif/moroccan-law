"""Work that belongs in a job, not in a writer's request: the followers told in one insert and their letters sent by
`send_notice_letters`; the check asked once and briefly; the desk's count counted, not loaded."""
import sys
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.discussion.models import Contribution, Discussion, Follow, Notice
from apps.discussion.services import check, review
from apps.discussion.tests.conftest import PATH, TITLE, make_user, signed_in

pytestmark = pytest.mark.django_db


def post(api, user, body='سؤال جديد'):
    r = signed_in(api, user).post('/api/discussion/contributions/', {'path': PATH, 'kind': 'question', 'title': TITLE,
                                                                     'body': body}, format='json')
    assert r.status_code == 201, r.content
    return r.json()


def followers(n: int, **kwargs) -> list:
    people = [make_user(f'f{i}', **kwargs) for i in range(n)]
    Follow.objects.bulk_create([Follow(user=u, path=PATH) for u in people])
    return people


# What one publication costs its writer, whatever the followers: 25 with 3 or with 30 (one insert tells them all).
PUBLISH_QUERIES = 25


@pytest.mark.parametrize('n', [3, 30])
def test_publishing_tells_every_follower_at_one_cost_and_no_letter_leaves_in_the_request(
        api, writer, n, django_assert_max_num_queries, django_capture_on_commit_callbacks):
    followers(n)
    with django_capture_on_commit_callbacks(execute=True), django_assert_max_num_queries(PUBLISH_QUERIES):
        post(api, writer)
    assert Notice.objects.filter(kind=Notice.Kind.NEW, path=PATH).count() == n
    assert mail.outbox == []                       # no call to the mail provider inside a writer's request
    call_command('send_notice_letters')
    assert sorted(m.to[0] for m in mail.outbox) == sorted(f'f{i}@example.org' for i in range(n))
    call_command('send_notice_letters')
    assert len(mail.outbox) == n                   # each letter once


def test_the_job_sends_a_letter_only_to_whoever_takes_them(api, writer):
    takes = followers(2)
    unproven = make_user('unproven', proven=False)
    quiet = make_user('quiet')
    quiet.email_notices = False
    quiet.save()
    Follow.objects.bulk_create([Follow(user=unproven, path=PATH), Follow(user=quiet, path=PATH)])
    post(api, writer)
    assert Notice.objects.filter(kind=Notice.Kind.NEW).count() == 4
    call_command('send_notice_letters')
    assert sorted(m.to[0] for m in mail.outbox) == sorted(u.email for u in takes)


def test_a_discussion_sends_one_letter_in_six_hours_even_queued(api, writer):
    followers(1)
    post(api, writer, 'سؤال أول')
    post(api, writer, 'سؤال ثان')
    assert Notice.objects.filter(user__username='f0').count() == 2
    call_command('send_notice_letters')
    assert [m.to for m in mail.outbox] == [['f0@example.org']]


def test_a_letter_a_day_late_is_not_sent(api, writer):
    followers(1)
    post(api, writer)
    Notice.objects.update(created_at=timezone.now() - timedelta(days=2))
    call_command('send_notice_letters')
    assert mail.outbox == [] and not Notice.objects.filter(letter_due=True).exists()


def test_the_check_waits_a_few_seconds_and_asks_once(monkeypatch, settings):
    # A failure already sends the post to a person: a retry only held a worker twice as long.
    made = {}

    class Client:
        def __init__(self, **kwargs):
            made.update(kwargs)
            self.messages = SimpleNamespace(create=lambda **kw: 'answered')

    monkeypatch.setitem(sys.modules, 'anthropic', SimpleNamespace(Anthropic=Client))
    assert check._call('words') == 'answered'
    assert made['max_retries'] == 0 and made['timeout'] == settings.CHECK_TIMEOUT_S <= 6


def test_the_desks_count_is_counted_and_its_page_read_alone(api, staff, lease):
    d = Discussion.objects.create(path=PATH, text_path=PATH)
    author = make_user('author')
    now = timezone.now()
    Contribution.objects.bulk_create(
        [Contribution(discussion=d, author=author, kind='question', title=f'سؤال {i}', body=f'رقمي {i}',
                      held_at=now - timedelta(minutes=i), held_reasons=['phone']) for i in range(55)]
        + [Contribution(discussion=d, author=author, kind='question', title='رجع', body='مرجوع', held_at=now,
                        held_reasons=['returned']),
           Contribution(discussion=d, author=author, kind='question', title='للكاتب', body='للتعديل', held_at=now,
                        held_reasons=['sent_back'])])
    signed_in(api, staff)
    with CaptureQueriesContext(connection) as asked:
        assert api.get('/api/discussion/me/unseen/').json()['review'] == 56
    read = [q['sql'] for q in asked.captured_queries if 'FROM "discussion_contribution"' in q['sql']]
    assert read and all('COUNT(' in sql for sql in read), read
    page = api.get('/api/discussion/review/', {'tab': 'held'}).json()
    assert page['counts']['held'] == 56 and len(page['items']) == 50
    # Returned by its author first, then by age; the one sent back is the author's to fix, not the queue's.
    assert page['items'][0]['body'] == 'مرجوع' and page['items'][1]['body'] == 'رقمي 54'
    assert 'للتعديل' not in [i['body'] for i in page['items']]
    assert [c.body for c in review.queue(staff, 'held', limit=2)] == ['مرجوع', 'رقمي 54']
