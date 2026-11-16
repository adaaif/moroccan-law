from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.models import Count, F

from apps.accounts.models import User
from apps.discussion.models import Contribution, Discussion, Useful

pytestmark = pytest.mark.django_db


def here() -> str:
    return connection.settings_dict['NAME']


def test_the_load_test_writes_nothing_unless_it_is_told_which_database_it_writes_to():
    with pytest.raises(CommandError, match='--yes-on'):
        call_command('seed_load_test', users=5, posts=3, comments=50)
    with pytest.raises(CommandError, match='--yes-on'):
        call_command('seed_load_test', users=5, posts=3, comments=50, yes_on='another_database')
    with pytest.raises(CommandError, match='--yes-on'):
        call_command('seed_load_test', remove=True)
    assert not User.objects.exists() and not Contribution.objects.exists()


def test_the_load_test_writes_its_people_posts_and_comments_counted_and_takes_them_away():
    call_command('seed_load_test', users=5, posts=3, comments=50, yes_on=here())
    people = User.objects.filter(username__startswith='load-')
    assert people.count() == 5 and not people.first().has_usable_password()
    heads = Contribution.objects.filter(author__in=people, parent=None)
    assert heads.count() == 3
    assert Contribution.objects.filter(author__in=people, parent__isnull=False).count() == 50
    assert sum(h.reply_count for h in heads) == 50        # counted as the services count
    assert all(h.active_at >= h.created_at for h in heads)
    assert sum(d.count for d in Discussion.objects.all()) == 53
    with pytest.raises(CommandError):
        call_command('seed_load_test', users=5, posts=3, comments=50, yes_on=here())
    call_command('seed_load_test', remove=True, yes_on=here())
    assert not User.objects.filter(username__startswith='load-').exists()
    assert not Contribution.objects.exists()
    assert sum(d.count for d in Discussion.objects.all()) == 0


@pytest.mark.skipif(connection.vendor != 'postgresql', reason='the SQL path is PostgreSQL\'s (TEST_DATABASE_URL)')
def test_on_postgres_the_database_makes_the_rows_right_and_takes_them_away_whole():
    call_command('seed_load_test', users=40, posts=300, comments=3000, days=30, viral=200, yes_on=here())
    people = User.objects.filter(username__startswith='load-')
    assert people.count() == 40 and not people.first().has_usable_password()
    posts = Contribution.objects.filter(parent=None)
    assert posts.count() == 300 and Contribution.objects.filter(parent__isnull=False).count() == 3000
    counted = dict(Contribution.objects.filter(parent__isnull=False).values_list('parent').annotate(n=Count('pk')))
    assert all(p.reply_count == counted.get(p.pk, 0) and p.active_at >= p.created_at for p in posts)
    answers = Contribution.objects.filter(reply_to__isnull=False)
    assert not answers.exclude(parent=F('reply_to__parent')).exists()               # in its own post
    assert not answers.filter(created_at__lt=F('reply_to__created_at')).exists()     # after what it answers
    assert sum(d.count for d in Discussion.objects.all()) == 3300
    # A real reader's comment under a test post and a «مفيد» on a test comment: those threads go through Django.
    reader = User.objects.create_user('reader', 'reader@example.org', 'a-long-pass-phrase')
    touched = posts.first()
    Contribution.objects.create(discussion=touched.discussion, parent=touched, author=reader, kind='comment', body='؟')
    Useful.objects.create(contribution=Contribution.objects.filter(parent__isnull=False).last(), user=reader)
    call_command('seed_load_test', remove=True, yes_on=here())
    assert not people.exists() and not Contribution.objects.exists() and not Useful.objects.exists()
    assert User.objects.filter(username='reader').exists()
    assert sum(d.count for d in Discussion.objects.all()) == 0


def test_the_load_test_wants_three_comments_a_post_at_least():
    with pytest.raises(CommandError, match='at least three a post'):
        call_command('seed_load_test', users=2, posts=4, comments=11, yes_on=here())
    assert not User.objects.exists()


@pytest.mark.skipif(connection.vendor == 'postgresql', reason='the rows written one by one are the other databases\' path')
def test_a_viral_conversation_hangs_on_the_busiest_posts_first_comment():
    call_command('seed_load_test', users=3, posts=2, comments=12, viral=3, yes_on=here())
    busiest = max(Contribution.objects.filter(parent=None), key=lambda p: p.reply_count)
    under = list(busiest.replies.order_by('created_at', 'pk'))
    first = under[0]
    assert busiest.reply_count == len(under) == 9 and first.reply_to is None
    assert first.created_at == busiest.created_at + timedelta(microseconds=1)       # the oldest, so it leads the post
    # The conversation it draws, in the order written: the first reply answers it, the others it or one another
    # (the default seed draws the second and third under the first reply).
    drawn = sorted((c for c in under if c.reply_to_id), key=lambda c: c.pk)
    assert [c.reply_to_id for c in drawn] == [first.pk, drawn[0].pk, drawn[0].pk]
    assert all(c.created_at >= c.reply_to.created_at for c in drawn)
    other = Contribution.objects.filter(parent=None).exclude(pk=busiest.pk).get()
    assert other.reply_count == 3 and other.replies.filter(reply_to__isnull=False).count() == 1
