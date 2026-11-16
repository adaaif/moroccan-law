"""The counts' report in the admin (/admin/analytics/): staff with the view right on the day counts alone, listed on the
index for them, every question answered, and the same queries whatever the counts hold."""
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.analytics.models import DayCount
from apps.analytics.services import report
from apps.analytics.tests.test_report import TODAY, a_fortnight
from apps.mcp.models import Tally
from apps.search.models import SearchLog
from apps.topics.models import Helped

pytestmark = pytest.mark.django_db

URL = '/admin/analytics/'
QUESTIONS = ('Do people come, and do they come back?', 'How do they arrive?', 'What do they read?', 'From where?',
             'Does search answer?', 'Are tools finished?', 'Is it fast on a phone?', 'What breaks?', 'Who else reads?',
             'Before 16 Nov 2026')


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(timezone, 'localdate', lambda *a: TODAY)


def person(n: int, **rights) -> Client:
    user = get_user_model().objects.create_user(username=f'p{n}', email=f'p{n}@example.org', password='a long pass 12',
                                                **rights)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def reader():
    """Staff with the view right on the day counts, and nothing else."""
    client = person(1, is_staff=True)
    user = get_user_model().objects.get(username='p1')
    user.user_permissions.add(Permission.objects.get(codename='view_daycount'))
    return client


def test_the_page_is_for_staff_with_the_right_alone(reader):
    anonymous = Client().get(URL)
    assert anonymous.status_code == 302 and anonymous['Location'].startswith(reverse('admin:login'))
    not_staff = person(2).get(URL)
    assert not_staff.status_code == 302 and not_staff['Location'].startswith(reverse('admin:login'))
    assert person(3, is_staff=True).get(URL).status_code == 403
    assert reader.get(URL).status_code == 200
    assert person(4, is_staff=True, is_superuser=True).get(URL).status_code == 200


def test_the_index_lists_the_page_for_those_who_may_open_it(reader):
    page = reader.get(reverse('admin:index'))
    assert page.status_code == 200 and f'href="{URL}"' in page.content.decode()
    assert 'analytics' in [a['app_label'] for a in page.context['app_list']]
    other = person(5, is_staff=True).get(reverse('admin:index'))
    assert f'href="{URL}"' not in other.content.decode()


def test_every_question_is_answered_and_a_few_readers_are_never_counted_aloud(reader):
    a_fortnight()
    page = reader.get(URL)
    text = page.content.decode()
    assert all(q in text for q in QUESTIONS)
    assert page.context['r']['period']['days'] == 7 and '2026-11-08 to 2026-11-14' in text
    assert '/ma/loi/65-99/art_53' in text and '/topics/road/tools/fine' in text
    # FR's three visitors: «fewer than 5», never 3.
    assert '<td>FR</td><td class="r-n">fewer than 5</td>' in text
    assert 'width:52.6%' in text                                    # a share's bar, written with a point
    assert reader.get(URL, {'days': '28'}).context['r']['period']['days'] == 28
    assert reader.get(URL, {'days': '5'}).context['r']['period']['days'] == 7


def _queries(client) -> int:
    with CaptureQueriesContext(connection) as seen:
        assert client.get(URL).status_code == 200
    return len(seen.captured_queries)


def test_the_page_costs_the_same_queries_whatever_the_counts_hold(reader):
    """The session, the account and its rights, then the report's own (report.QUERIES): not one more for ten times
    the groups."""
    empty = _queries(reader)
    a_fortnight()
    small = _queries(reader)
    for model in (DayCount, Tally, SearchLog, Helped):
        model.objects.all().delete()
    a_fortnight(scale=10)
    assert empty == small == _queries(reader) == report.QUERIES + 4


def test_the_counts_from_before_are_shown_once_brought_in(reader):
    assert 'Not brought in yet' in reader.get(URL).content.decode()
    DayCount.objects.create(day=date(2026, 11, 1), metric='past.pages', key='', count=321)
    text = reader.get(URL).content.decode()
    assert 'Pages people were shown</td><td class="r-n">321</td>' in text and 'counted twice' in text
