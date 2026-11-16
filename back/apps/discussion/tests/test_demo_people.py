"""N1 of the read-and-trusted review: the development's demo people never reach a reader where SHOW_DEMO_PEOPLE is off."""
from datetime import UTC, datetime

import pytest

from apps.accounts.models import User
from apps.discussion.models import Contribution, Discussion, Kind
from apps.discussion.services import counters, thread


@pytest.fixture
def heated(db):
    d = Discussion.objects.create(path='/talk/family', text_path='/talk/family')
    demo = User.objects.create(username='demo-amina', email='amina@demo.law.invalid')
    e2e = User.objects.create(username='e2emvfgm7xw', email='e2emvfgm7xw@demo.law.invalid')
    early = User.objects.create(username='deleted-359', email='deleted-359@deleted.invalid')
    User.objects.filter(pk=early.pk).update(date_joined=datetime(2026, 10, 19, tzinfo=UTC))
    real = User.objects.create(username='salma', email='salma@example.com')
    for u, n in ((demo, 3), (e2e, 1), (early, 1), (real, 1)):
        for i in range(n):
            Contribution.objects.create(discussion=d, author=u, kind=Kind.QUESTION, title=f'سؤال {i}',
                                        body=f'سؤال {u.username} {i}')
    counters.discussion(d)
    return d


def test_demo_people_are_counted_while_developing(heated):
    heated.refresh_from_db()
    assert heated.count == 6


def test_the_developments_people_leave_the_counts_and_the_lists(heated, settings):
    # The seeded demo, the end-to-end tests' accounts and one made before the public site's database was copied.
    settings.SHOW_DEMO_PEOPLE = False
    assert counters.every_discussion() == 1
    heated.refresh_from_db()
    assert (heated.count, heated.open_questions) == (1, 1)
    assert thread.open_questions('/talk/family')['questions'][0]['author']['username'] == 'salma'
    assert [p['author']['username'] for p in thread.feed(None, '/talk/family')['posts']] == ['salma']
    assert thread.person(None, 'demo-amina') is None
    assert thread.person(None, 'salma') is not None


def test_the_months_numbers_leave_the_developments_moderation_out(heated, settings):
    """The public site counted the demo's 25 reports and 9 approvals of October 2026 against 0 contributions."""
    from django.utils import timezone

    from apps.discussion.models import Action, Report
    from apps.discussion.services import numbers

    demo, real = User.objects.get(username='demo-amina'), User.objects.get(username='salma')
    staff = User.objects.create(username='demo-staff', email='staff@demo.law.invalid', is_staff=True)
    on_demo = Contribution.objects.filter(author=demo).first()
    on_real = Contribution.objects.get(author=real)
    Report.objects.create(reporter=real, contribution=on_demo, reason=Report.Reason.ABUSE)
    Report.objects.create(reporter=demo, contribution=on_real, reason=Report.Reason.ABUSE)
    Action.objects.create(verb=Action.Verb.APPROVE, actor=staff, contribution=on_demo, target=demo)
    Action.objects.create(verb=Action.Verb.REMOVE, actor=staff, contribution=on_real, target=real)
    today = timezone.localdate()
    month = numbers.month(today.year, today.month)
    assert month['reports']['abuse'] == 2 and month['acts']['approve'] == 1
    settings.SHOW_DEMO_PEOPLE = False
    month = numbers.month(today.year, today.month)
    assert (month['contributions'], month['reports']['abuse'], month['acts']['approve'], month['acts']['remove']) \
        == (1, 0, 0, 0)


def test_an_explanation_a_demo_account_checked_waits_like_an_unchecked_one(db, settings):
    from django.utils import timezone

    from apps.explain.models import Explanation
    from apps.explain.services import explanations

    demo = User.objects.create(username='demo-staff', email='staff@demo.law.invalid', is_staff=True)
    real = User.objects.create(username='reviewer-1', email='r@example.com', is_staff=True)
    Explanation.objects.create(path='/words/rent', body='الوجيبة الكرائية: الكراء.', reviewed_at=timezone.now(),
                               reviewed_by=demo)
    Explanation.objects.create(path='/words/eviction', body='الإفراغ: الخروج من المحل.', reviewed_at=timezone.now(),
                               reviewed_by=real)
    assert set(explanations.word_meanings()) == {'rent', 'eviction'}
    settings.SHOW_DEMO_PEOPLE = False
    assert set(explanations.word_meanings()) == {'eviction'}
    assert explanations.bundle_word('rent') == {'registers': {}}


def test_the_conversation_lives_from_its_hundredth_published_post(heated, settings, monkeypatch, django_assert_num_queries):
    """C2 of the readers review: a phone's bar gives «النقاش» its place only then; comments and the development's
    people do not count, and the answer is kept, so a page's flags cost no query."""
    from django.core.cache import cache

    settings.SHOW_DEMO_PEOPLE = False
    monkeypatch.setattr(counters, 'ALIVE', 3)
    cache.delete('talk:alive')
    assert counters.alive() is False                      # one real post among six
    real = User.objects.get(username='salma')
    first = Contribution.objects.get(author=real)
    Contribution.objects.create(discussion=heated, author=real, parent=first, kind=Kind.COMMENT, body='جواب')
    Contribution.objects.create(discussion=heated, author=real, kind=Kind.QUESTION, title='ثان', body='سؤال ثان')
    cache.delete('talk:alive')
    assert counters.alive() is False                      # two posts and a comment
    Contribution.objects.create(discussion=heated, author=real, kind=Kind.QUESTION, title='ثالث', body='سؤال ثالث')
    cache.delete('talk:alive')
    with django_assert_num_queries(2):                    # the development's accounts, then the posts up to the bar
        assert counters.alive() is True
    with django_assert_num_queries(0):
        assert counters.alive() is True
