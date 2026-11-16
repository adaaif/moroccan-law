"""What the discussion's lists cost in queries (S6, S7 and S20 of the performance audit, 24 Oct 2026; the topics' pages
of 29 Oct 2026): the same for 3 cards as for 12. A card's labels and cited articles are read for the whole page."""
import pytest
from django.utils import timezone

from apps.corpus.models import Article
from apps.discussion.models import Cite, Contribution, Discussion, Report
from apps.discussion.services import anchors, counters, review
from apps.discussion.tests.conftest import lease, make_user, signed_in, uploads  # noqa: F401  (fixtures)

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'
PLACE = '/talk/housing'


def questions(lease, n: int):
    """`n` questions in the housing topic, each started from its own article, each answered by someone else; every
    third one reported."""
    version = lease.latest_version()
    asker, helper, reporter = make_user('asker'), make_user('helper'), make_user('reporter')
    d = Discussion.objects.create(path=PLACE, text_path=PLACE, count=2 * n, open_questions=0)
    for i in range(n):
        eid = f'art_{100 + i}'
        body = f'نص المادة {100 + i}.'
        Article.objects.create(version=version, order=100 + i, label=f'المادة {100 + i}', number=str(100 + i), eid=eid,
                               body=body)
        q = Contribution.objects.create(discussion=d, author=asker, kind='question', title=f'سؤال {i}',
                                        body=f'سؤال عن الكراء رقم {i}؟', about=f'{TEXT}/{eid}', active_at=timezone.now())
        Cite.objects.create(contribution=q, path=f'{TEXT}/{eid}', text_path=TEXT, digest=anchors.digest(body))
        Contribution.objects.create(discussion=d, author=helper, kind='comment', parent=q, body=f'جواب {i}.',
                                    accepted_at=timezone.now() if i % 2 else None)
        if i % 3 == 0:
            Report.objects.create(contribution=q, reporter=reporter, reason='insult')
    counters.every_post()       # written here without the services, which keep each post's counts


@pytest.mark.parametrize('n', [3, 12])
def test_the_discussions_lists_cost_the_same_whatever_their_length(api, lease, django_assert_max_num_queries, n):
    questions(lease, n)
    with django_assert_max_num_queries(12):
        d = api.get('/api/discussion/answered/').json()
    assert len(d['questions']) == n and all(q['answer'] and q['label']['place'] == 'housing' for q in d['questions'])
    with django_assert_max_num_queries(12):
        assert len(api.get('/api/discussion/people/asker/').json()['contributions']) == n
    with django_assert_max_num_queries(16):
        feed = api.get('/api/discussion/feed/', {'place': PLACE}).json()
    assert len(feed['posts']) == n and all(p['cites'][0]['label']['article'] for p in feed['posts'])
    with django_assert_max_num_queries(10):
        hub = api.get('/api/discussion/places/').json()
    assert sum(len(p['posts']) for p in hub['places']) == min(n, 3)


@pytest.mark.parametrize('n', [3, 12])
def test_an_articles_page_and_a_post_cost_the_same_whatever_their_length(api, lease, django_assert_max_num_queries, n):
    questions(lease, n)
    d = Discussion.objects.get(path=PLACE)
    q = Contribution.objects.filter(parent=None).first()
    people = [make_user(f'p{i}') for i in range(4)]
    for i in range(n):
        c = Contribution.objects.create(discussion=d, author=people[i % 4], kind='comment', parent=q, body=f'تعليق {i}')
        Cite.objects.create(contribution=c, path=f'{TEXT}/art_34', text_path=TEXT)
    # The article the post started from is drawn as the text page draws it: about a dozen queries of its own. (Here
    # the development's accounts are read for each question asked of them: DEMO_IDS_KEPT is 0 in tests.) 29 since HM37 of
    # the hard-moment review: a compiled text's reference reads its file's note of the Bulletin issue, once a page.
    with django_assert_max_num_queries(29):
        page = api.get(f'/api/discussion/posts/{q.pk}/').json()
    assert len(page['post']['replies']) == n + 1
    with django_assert_max_num_queries(26):
        cited = api.get('/api/discussion/cited/', {'path': f'{TEXT}/art_34'}).json()
    assert [p['id'] for p in cited['posts']] == [q.pk]


@pytest.mark.parametrize('n', [3, 12])
def test_a_page_of_the_review_queue_costs_the_same_whatever_its_length(api, lease, django_assert_max_num_queries, n):
    questions(lease, n)
    staff = make_user('staff', staff=True)
    review.appoint(staff, staff, [PLACE])
    signed_in(api, staff)
    with django_assert_max_num_queries(30):
        d = api.get('/api/discussion/review/', {'tab': 'reported'}).json()
    assert d['counts']['reported'] == len(range(0, n, 3)) == len(d['items'])
    first = d['items'][0]
    assert first['reports']['reasons'] == {'insult': 1} and first['context']['article'].startswith('نص المادة')
    assert first['record'] == {'contributions': 2 * n - n, 'removed': 0, 'paused': 0}
    assert first['label']['place'] == 'housing' and first['path'].startswith(f'{PLACE}/')


@pytest.mark.parametrize('n', [25, 100])
def test_a_topic_reads_only_the_page_it_shows(api, lease, django_assert_max_num_queries, n):
    # S12 of the performance audit: the thread read every contribution with its media to show twenty.
    d = Discussion.objects.create(path=PLACE, text_path=PLACE, count=n)
    people = [make_user(f'p{i}') for i in range(5)]
    for i in range(n):
        q = Contribution.objects.create(discussion=d, author=people[i % 5], kind='question', title=f'سؤال {i}',
                                        body=f'سؤال {i}؟', useful_count=i % 7, active_at=timezone.now())
        if i % 4 == 0:
            Contribution.objects.create(discussion=d, author=people[(i + 1) % 5], kind='comment', parent=q,
                                        body=f'جواب {i}')
    with django_assert_max_num_queries(16):
        r = api.get('/api/discussion/feed/', {'place': PLACE, 'sort': 'top'}).json()
    assert len(r['posts']) == 20 and r['next_page'] == 2
    useful = [c['useful'] for c in r['posts']]
    assert useful == sorted(useful, reverse=True)
