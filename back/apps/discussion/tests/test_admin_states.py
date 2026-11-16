"""The admin's list of contributions: each one's state as readers meet it, the strongest first, and where it is read on
the site (a post in its topic, an article thread of before under /discussion)."""
import re

import pytest
from django.utils import timezone

from apps.discussion.models import Contribution, Discussion
from apps.discussion.tests.conftest import ARTICLE, PATH, make_user

pytestmark = pytest.mark.django_db


def test_each_contribution_shows_its_strongest_state_and_its_page_on_the_site(admin_client, settings):
    settings.SITE_URL = 'https://site.example.org'
    now = timezone.now()
    topic = Discussion.objects.create(path=PATH, text_path=PATH)
    old = Discussion.objects.create(path=ARTICLE, text_path='/ma/loi/2013/67-12')
    author = make_user('salma')
    rows = {
        'live': Contribution.objects.create(discussion=topic, author=author, kind='post', title='حي', body='.'),
        'held': Contribution.objects.create(discussion=topic, author=author, kind='post', title='منتظر', body='.',
                                            held_at=now),
        'removed over held': Contribution.objects.create(discussion=old, author=author, kind='question', body='محيد',
                                                         held_at=now, removed_at=now),
        'deleted over hidden': Contribution.objects.create(discussion=topic, author=author, kind='post', title='ممسوح',
                                                           body='.', hidden_at=now, deleted_at=now),
    }
    page = admin_client.get('/admin/discussion/contribution/').content.decode()
    states = dict(re.findall(r'/admin/discussion/contribution/(\d+)/change/.*?<td class="field-state">([^<]+)</td>',
                             page))
    assert {name: states[str(c.pk)] for name, c in rows.items()} == {
        'live': 'published', 'held': 'held for a moderator', 'removed over held': 'removed',
        'deleted over hidden': 'deleted by its author'}
    assert f'href="https://site.example.org/discussion{ARTICLE}"' in page
    assert f'href="https://site.example.org{PATH}/{rows["live"].pk}"' in page
