"""How the discussion names where things are: an article thread of before by its article, an article gone from the
corpus by nothing, a place that no longer exists by its address; whose names a topic shows as its moderators; and the
lists that leave the development's people out."""
from types import SimpleNamespace

import pytest
from django.core import mail
from django.core.management import call_command

from apps.accounts.services import mail as letters
from apps.corpus.models import Text
from apps.discussion.models import Contribution, Discussion, Follow, Notice
from apps.discussion.services import counters, review, thread
from apps.discussion.tests.conftest import ARTICLE, PATH, make_user, signed_in

pytestmark = pytest.mark.django_db
GONE = '/ma/loi/2013/67-12/art_99'
UNREAD = '/ma/loi/2020/1-20/art_1'          # a text with no version read yet
NAMED = {'article': 'المادة 34', 'number': '34'}
NOTHING = {'article': '', 'text': '', 'name': None, 'number': ''}


@pytest.mark.parametrize('n', [1, 4])
def test_an_article_thread_of_before_is_named_by_its_article_and_a_gone_article_by_nothing(
        api, lease, staff, django_assert_max_num_queries, n):
    user = make_user('salma')
    old = Discussion.objects.create(path=ARTICLE, text_path='/ma/loi/2013/67-12')
    topic = Discussion.objects.create(path=PATH, text_path=PATH)
    for i in range(n):
        Contribution.objects.create(discussion=old, author=user, kind='question', body=f'سؤال قديم {i}')
    post = Contribution.objects.create(discussion=topic, author=user, kind='post', title='منشور', body='كلام')
    Text.objects.create(akn_uri='/akn/ma/act/loi/2020/1-20', type='law', number='1-20', title_ar='قانون')
    for path in (GONE, UNREAD):
        Follow.objects.create(user=user, path=path)
    with django_assert_max_num_queries(17):
        me = signed_in(api, user).get('/api/discussion/me/').json()
    olds = [c for c in me['contributions'] if c['path'] == ARTICLE]
    assert len(olds) == n and all(c['post_title'] == '' and NAMED.items() <= c['label'].items() for c in olds)
    assert olds[0]['label']['text'] and olds[0]['label']['name']['ar'] == olds[0]['label']['text']
    assert {f['path']: f['label'] for f in me['following']} == {GONE: NOTHING, UNREAD: NOTHING}
    # A person's page: where they wrote, the topics only; an old thread's card leads to the thread itself.
    with django_assert_max_num_queries(13):
        page = api.get('/api/discussion/people/salma/').json()
    assert page['person']['contributions'] == n + 1
    assert [(p['path'], p['count']) for p in page['person']['places']] == [(PATH, 1)]
    where = {c['id']: (c['path'], c['place']) for c in page['contributions']}
    assert where[post.pk] == (f'{PATH}/{post.pk}', PATH) and where[olds[0]['id']] == (ARTICLE, '')
    # Held in an old thread, it reaches the desk named by its article.
    Contribution.objects.filter(discussion=old).update(held_at=post.created_at, held_reasons=['phone'])
    cards = signed_in(api, staff).get('/api/discussion/review/', {'tab': 'held'}).json()['items']
    assert len(cards) == n and NAMED.items() <= cards[0]['label'].items() and cards[0]['path'] == ARTICLE


def test_a_stop_link_names_what_it_stops(api, lease, reader):
    def named(path):
        return api.get('/api/discussion/letters/stop/', {'t': letters.stop_token(reader, path)}).json()['label']

    article = named(ARTICLE)
    assert article.startswith('المادة 34 — ') and len(article) > len('المادة 34 — ')
    assert named(PATH) == 'السكن والكراء'
    for path in (GONE, '/talk/nowhere/5', '/ma/nowhere'):
        assert named(path) == path


def test_a_letter_about_a_place_that_is_gone_names_its_address_and_letters_go_paced(api, reader, settings, monkeypatch):
    from apps.discussion.services import notices

    slept = []
    monkeypatch.setattr(notices, 'time', SimpleNamespace(sleep=slept.append))
    settings.NOTICE_LETTER_PACE_S = 0.25
    for path in ('/talk/nowhere/5', '/talk/nowhere/6', '/talk/nowhere/7'):
        Notice.objects.create(user=reader, kind='approved', path=path, letter_due=True)
    call_command('send_notice_letters')
    assert len(mail.outbox) == 3 and slept == [0.25, 0.25]
    assert sorted(m.body.split(' ونشرها')[0].rsplit('حول ', 1)[1] for m in mail.outbox) == [
        '/talk/nowhere/5', '/talk/nowhere/6', '/talk/nowhere/7']       # named by their address
    assert not Notice.objects.filter(letter_due=True).exists()


def test_ones_notices_are_the_latest_forty(api, reader):
    Notice.objects.bulk_create([Notice(user=reader, kind='approved', path=f'{PATH}/{i}') for i in range(41)])
    notices = signed_in(api, reader).get('/api/discussion/me/').json()['notices']
    assert len(notices) == 40 and notices[0]['path'] == f'{PATH}/40' and notices[-1]['path'] == f'{PATH}/1'


def test_a_topic_names_its_own_moderators_never_the_developments_people(api, staff, settings):
    settings.SHOW_DEMO_PEOPLE = False
    # Real people joined after the development's database was copied (DEMO_UNTIL): a day ago.
    for name, paths in (('rev', [PATH]), ('worker', ['/talk/work']), ('demo-rev', [PATH])):
        review.appoint(staff, make_user(name, days=1), paths)
    place = api.get('/api/discussion/feed/', {'place': PATH}).json()['place']
    assert [m['username'] for m in place['moderators']] == ['rev']


def test_a_post_page_leaves_out_the_developments_people_and_an_article_gone(api, settings):
    settings.SHOW_DEMO_PEOPLE = False
    topic = Discussion.objects.create(path=PATH, text_path=PATH)
    post = Contribution.objects.create(discussion=topic, author=make_user('salma', days=1), kind='question',
                                       title='سؤال', body='سؤال', about=GONE)
    real = Contribution.objects.create(discussion=topic, parent=post, author=make_user('omar', days=1), kind='comment',
                                       body='جواب')
    demo = Contribution.objects.create(discussion=topic, parent=post, author=make_user('demo-x'), kind='comment',
                                       body='تجربة')
    # A real reader's answer to the demo's comment stands as a conversation of its own.
    answer = Contribution.objects.create(discussion=topic, parent=post, reply_to=demo, author=make_user('ali', days=1),
                                         kind='comment', body='رد')
    counters.around(real)
    page = api.get(f'/api/discussion/posts/{post.pk}/').json()
    assert [r['id'] for r in page['post']['replies']] == [real.pk, answer.pk] and page['about'] is None


def test_the_developments_accounts_are_read_again_after_their_minute(api, settings, monkeypatch):
    settings.SHOW_DEMO_PEOPLE, settings.DEMO_IDS_KEPT = False, 60
    monkeypatch.setattr(counters, '_kept_ids', counters._kept_ids)      # put back after the test
    clock = [10.0 ** 9]
    monkeypatch.setattr(counters, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    topic = Discussion.objects.create(path=PATH, text_path=PATH)

    def shown():
        return [p['title'] for p in api.get('/api/discussion/feed/', {'place': PATH}).json()['posts']]

    Contribution.objects.create(discussion=topic, author=make_user('salma', days=1), kind='post', title='حقيقي', body='.')
    Contribution.objects.create(discussion=topic, author=make_user('demo-a'), kind='post', title='تجربة', body='.')
    assert shown() == ['حقيقي']
    Contribution.objects.create(discussion=topic, author=make_user('demo-b'), kind='post', title='تجربة ثانية', body='.')
    clock[0] += 59.5
    assert 'تجربة ثانية' in shown()            # the accounts read less than a minute ago, kept
    clock[0] += 0.5
    assert shown() == ['حقيقي']


def test_a_question_of_one_word_has_asked_nothing_before(lease):
    topic = Discussion.objects.create(path=PATH, text_path=PATH)
    Contribution.objects.create(discussion=topic, author=make_user('salma'), kind='question',
                                title='مراجعة الوجيبة الكرائية', body='واش كتراجع الوجيبة كل ثلاث سنين؟')
    assert thread.asked_before(PATH, 'الوجيبة', []) == []
    assert [q['title'] for q in thread.asked_before(PATH, 'مراجعة الوجيبة', [])] == ['مراجعة الوجيبة الكرائية']


def test_a_months_numbers_are_asked_by_its_name(api):
    from datetime import UTC, datetime

    topic = Discussion.objects.create(path=PATH, text_path=PATH)
    c = Contribution.objects.create(discussion=topic, author=make_user('salma', days=1), kind='post', title='منشور',
                                    body='.', held_reasons=['phone'])
    Contribution.objects.filter(pk=c.pk).update(created_at=datetime(2026, 9, 15, 12, tzinfo=UTC))
    september = api.get('/api/discussion/numbers/', {'month': '2026-09'}).json()['months']
    assert [(m['month'], m['contributions'], m['held']) for m in september] == [('2026-09', 1, 1)]
    assert api.get('/api/discussion/numbers/', {'month': '2026-08'}).json()['months'][0]['contributions'] == 0
    r = api.get('/api/discussion/numbers/', {'month': '2026-13'})
    assert r.status_code == 400 and r.json()['errors'] == [{'field': 'month', 'code': 'invalid'}]
