"""Writing in a topic (29 Oct 2026): who may, what waits for a reviewer, what a reader sees; the article a post starts
from and the articles it cites."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.corpus.models import Article
from apps.discussion.models import Cite, Contribution, Discussion, Follow, Report, Revision
from apps.discussion.services import holds
from apps.discussion.tests.conftest import (ART_34, ARTICLE, PATH, TITLE, feed, make_user, post_of, settle,
                                            signed_in)

pytestmark = pytest.mark.django_db


def post(api, **data):
    sent = {'path': PATH, 'kind': 'question', 'title': TITLE, **data}
    if data.get('parent'):
        sent.pop('title')
    return api.post('/api/discussion/contributions/', sent, format='json')


def codes(r):
    return [(e['field'], e['code']) for e in r.json()['errors']]


def test_writing_needs_a_proven_email(api, lease):
    r = post(signed_in(api, make_user('new', proven=False)), body='سؤال')
    assert r.status_code == 403 and codes(r) == [('email', 'not_proven')]


def test_writing_stays_closed_until_the_owner_opens_it(api, writer, settings):
    settings.DISCUSSION_OPEN = False
    r = post(signed_in(api, writer), body='سؤال')
    assert r.status_code == 403 and codes(r) == [('discussion', 'closed')]


def test_a_post_goes_to_a_topic_with_a_title(api, writer):
    api = signed_in(api, writer)
    assert codes(post(api, path='/talk/nowhere', body='؟')) == [('path', 'not_found')]
    assert codes(post(api, path=ARTICLE, body='؟')) == [('path', 'not_found')]
    assert codes(post(api, title='', body='؟')) == [('title', 'required')]
    assert codes(post(api, title='x' * 141, body='؟')) == [('title', 'too_long')]
    assert codes(post(api, kind='explanation', body='؟')) == [('kind', 'invalid')]
    r = post(api, kind='post', title='  تجربتي   مع الكراء ', body='')
    assert r.status_code == 201 and (r.json()['kind'], r.json()['title']) == ('post', 'تجربتي مع الكراء')
    assert r.json()['path'] == f'{PATH}/{r.json()["id"]}'


def test_an_article_thread_of_before_is_read_never_written_in(api, writer):
    old = Discussion.objects.create(path=ARTICLE, text_path='/ma/loi/2013/67-12')
    q = Contribution.objects.create(discussion=old, author=writer, kind='question', body='سؤال قديم')
    r = post(signed_in(api, make_user('amine')), body='جواب', parent=q.pk)
    assert codes(r) == [('path', 'not_a_place')]


def test_an_established_writer_is_published_at_once_and_follows_the_post(api, writer):
    r = post(signed_in(api, writer), body='سؤال واضح')
    assert r.status_code == 201 and r.json()['held'] is False
    assert Discussion.objects.get(path=PATH).count == 1
    assert Follow.objects.filter(user=writer, path=f'{PATH}/{r.json()["id"]}').exists()
    assert not Follow.objects.filter(user=writer, path=PATH).exists()


def test_a_post_starts_from_an_article_and_quotes_its_own_words(api, writer):
    api = signed_in(api, writer)
    assert codes(post(api, body='؟', quote='نسبة الزيادة')) == [('quote', 'not_in_article')]
    assert codes(post(api, body='؟', about=ARTICLE, quote='نسبة الزيادة 20%')) == [('quote', 'not_in_article')]
    assert codes(post(api, body='؟', about='/ma/loi/2013/67-12/art_99')) == [('about', 'not_found')]
    r = post(api, body='؟', about=ARTICLE, quote='%8 بالنسبة للمحلات   المعدة للسكنى')
    assert r.status_code == 201 and r.json()['quote'] == '%8 بالنسبة للمحلات المعدة للسكنى'
    assert r.json()['about'] == ARTICLE
    assert [x['path'] for x in r.json()['cites']] == [ARTICLE]


def test_citations_become_links_and_are_kept_for_the_articles_page(api, writer):
    body = 'حسب المادة 32 لا يجوز الرفع قبل ثلاث سنوات، والمادة 35 للمحكمة.'
    # «المادة 32» alone names the article of the text the post started from.
    made = post(signed_in(api, writer), about=ARTICLE, body=body).json()
    assert [(body[x['start']:x['end']], x['path']) for x in made['links']] == [
        ('المادة 32', '/ma/loi/2013/67-12/art_32'), ('والمادة 35', '/ma/loi/2013/67-12/art_35')]
    assert set(Cite.objects.values_list('path', flat=True)) == {
        ARTICLE, '/ma/loi/2013/67-12/art_32', '/ma/loi/2013/67-12/art_35'}
    # With no article to start from, a bare «المادة 32» names nothing.
    lone = post(api, body='المادة 32 واضحة').json()
    assert lone['links'] == [] and lone['cites'] == []


def test_the_articles_page_lists_the_posts_that_cite_it_and_where_to_ask(api, writer, reader):
    from apps.corpus.models import Alias

    # The fixture's text keeps its address of before 19 Oct 2026; the citation reader finds it by kind and number.
    Alias.objects.create(alias='/akn/ma/act/loi/67-12', uri='/akn/ma/act/loi/2013/67-12', reason='moved')
    cites = post(signed_in(api, writer), about=ARTICLE, body='؟').json()
    other = post(api, body='بلا مادة').json()
    under = post(api, body='سؤال آخر').json()
    post(signed_in(api, settle(make_user('amine'), None)), parent=under['id'], body='شوف المادة 34 من القانون 67.12')
    page = signed_in(api, reader).get('/api/discussion/cited/', {'path': ARTICLE}).json()
    assert page['article']['label'] == 'المادة 34'
    assert {p['id'] for p in page['posts']} == {cites['id'], under['id']} and other['id'] not in page['posts']
    assert page['places'] and page['places'][0]['path'].startswith('/talk/')


@pytest.mark.parametrize('words, reason', [
    ('اتصلوا بي على 06 00 00 00 00', 'phone'),
    ('+212 6 00 00 00 00', 'phone'),
    ('راسلني: me@example.org', 'email'),
    ('بطاقتي BE123456', 'cin'),
    ('الملف عدد 1234/1201/2024', 'case'),
    ('www.mon-avocat.com', 'link'),
    ('MA64 0110 0000 0000 0000 0000 0000', 'rib'),
    ('يا ولد القحبة', 'insult'),
])
def test_patterns_hold_for_a_reviewer(words, reason):
    assert holds.scan(words)[0] == [reason]


@pytest.mark.parametrize('words', [
    'الفصل 418 من ق.ل.ع', 'BO 7533', 'de 50000 dirhams', 'https://adala.justice.gov.ma/ar', '%8 و%10',
    'الحمار ملك لصاحبه', 'القانون 67.12',
])
def test_the_laws_own_words_hold_nothing(words):
    assert holds.scan(words) == ([], [])


def test_a_phone_number_holds_even_an_established_writer(api, writer):
    r = post(signed_in(api, writer), body='نعرف محامي يربح ليكم الملف، اتصلوا 0600000000')
    c = Contribution.objects.get(pk=r.json()['id'])
    assert c.held_at and c.held_reasons == ['phone']
    start, end, _ = c.held_spans[0]
    assert c.body[start:end] == '0600000000'


def test_a_phone_number_in_the_title_holds_too(api, writer):
    r = post(signed_in(api, writer), title='عيطو 0600000000', body='')
    assert Contribution.objects.get(pk=r.json()['id']).held_reasons == ['phone']


def test_comments_stay_two_levels_deep_and_the_post_comes_alive(api, writer, reader):
    q = post(signed_in(api, writer), body='سؤال').json()
    a = post(signed_in(api, settle(make_user('amine'), None)), body='جواب', parent=q['id']).json()
    b = post(signed_in(api, writer), body='شكرا', parent=a['id']).json()
    assert b['parent'] == q['id'] and (a['kind'], b['kind']) == ('comment', 'comment')
    page = post_of(api, q['id'])
    assert [r['id'] for r in page['post']['replies']] == [a['id'], b['id']]
    assert page['post']['reply_count'] == 2
    row = Contribution.objects.get(pk=q['id'])
    assert row.active_at == Contribution.objects.get(pk=b['id']).created_at


def test_an_edit_keeps_the_earlier_words_for_reviewers_and_a_phone_number_holds_it(api, writer):
    api = signed_in(api, writer)
    c = post(api, body='سؤال أول').json()
    r = api.patch(f'/api/discussion/contributions/{c["id"]}/', {'body': 'سؤال ثان 0600000000'}, format='json')
    assert r.status_code == 200 and r.json()['held'] is True and r.json()['edited_at']
    assert list(Revision.objects.values_list('body', flat=True)) == [f'{TITLE}\n\nسؤال أول']
    r = api.patch(f'/api/discussion/contributions/{c["id"]}/', {'body': 'سؤال ثان', 'title': 'عنوان جديد'},
                  format='json')
    assert r.json()['title'] == 'عنوان جديد'


def test_deleting_erases_and_leaves_a_marker_only_above_answers(api, writer):
    asker = signed_in(api, writer)
    lone = post(asker, body='سؤال وحيد').json()
    asked = post(asker, body='سؤال مجاب').json()
    other = settle(make_user('amine'), None)
    post(signed_in(api, other), body='جواب', parent=asked['id'])
    signed_in(api, writer)
    assert api.delete(f'/api/discussion/contributions/{lone["id"]}/').status_code == 204
    assert api.delete(f'/api/discussion/contributions/{asked["id"]}/').status_code == 204
    gone = Contribution.objects.get(pk=lone['id'])
    assert gone.erased_at and gone.body == '' and gone.title == ''
    assert feed(api)['posts'] == []
    page = post_of(api, asked['id'])
    assert page['post'].get('marker') == 'deleted' and len(page['post']['replies']) == 1
    assert api.get(f'/api/discussion/posts/{lone["id"]}/').status_code == 404


def test_deleting_under_a_report_freezes_it_for_the_reviewers(api, writer, reader):
    c = post(signed_in(api, writer), body='سؤال').json()
    signed_in(api, reader).post(f'/api/discussion/contributions/{c["id"]}/report/', {'reason': 'abuse'},
                                format='json')
    signed_in(api, writer).delete(f'/api/discussion/contributions/{c["id"]}/')
    row = Contribution.objects.get(pk=c['id'])
    assert row.deleted_at and row.frozen_until and row.erased_at is None and row.body == 'سؤال'
    assert Report.objects.get().status == 'open'


def test_a_locked_topic_takes_nothing_new(api, writer):
    post(signed_in(api, writer), body='سؤال')
    Discussion.objects.filter(path=PATH).update(locked_at='2026-10-19T00:00:00Z')
    assert codes(post(api, body='آخر')) == [('discussion', 'locked')]


def test_a_newcomer_writes_five_a_day_in_the_first_week(api, lease):
    api = signed_in(api, make_user('fresh', days=2))
    for _ in range(5):
        assert post(api, body='سؤال').status_code == 201
    r = post(api, body='سؤال')
    assert r.status_code == 429 and codes(r) == [('account', 'day_limit')]


def test_a_post_says_when_an_article_it_cites_changed_after_it(api, writer):
    old = post(signed_in(api, writer), about=ARTICLE, body='النسبة 8%').json()
    assert [x['changed'] for x in old['cites']] == [False]
    Article.objects.filter(eid='art_34').update(body=ART_34.replace('%8', '%9'))
    fresh = post(api, about=ARTICLE, body='النسبة 9%').json()
    posts = {p['id']: p for p in feed(api, 'new')['posts']}
    assert [x['changed'] for x in posts[old['id']]['cites']] == [True]
    assert [x['changed'] for x in posts[fresh['id']]['cites']] == [False]


def test_a_voice_is_never_anonymous(api, writer):
    r = post(signed_in(api, writer), body='', anonymous=True, voice='7d5c0b0e-0000-0000-0000-000000000000')
    assert r.status_code == 404  # no such draft: the voice is checked before anything else about it


def test_anonymous_hides_the_name_from_readers(api, writer, reader):
    post(signed_in(api, writer), body='سؤال', anonymous=True)
    c = feed(signed_in(api, reader))['posts'][0]
    assert c['anonymous'] is True and c['author'] is None


def test_the_feed_sorts_by_life_newness_use_and_waiting(api, writer, reader):
    api = signed_in(api, writer)
    first = post(api, body='الأول').json()
    second = post(api, kind='post', body='الثاني').json()
    third = post(api, body='الثالث').json()
    amine = settle(make_user('amine'), None)
    post(signed_in(api, amine), parent=first['id'], body='جواب')
    assert [p['id'] for p in feed(api, 'active')['posts']] == [first['id'], third['id'], second['id']]
    assert [p['id'] for p in feed(api, 'new')['posts']] == [third['id'], second['id'], first['id']]
    assert [p['id'] for p in feed(api, 'open')['posts']] == [third['id']]
    signed_in(api, reader).post(f'/api/discussion/contributions/{second["id"]}/useful/')
    assert feed(api, 'top')['posts'][0]['id'] == second['id']


def test_the_most_useful_reads_a_period(api):
    # 31 Oct 2026: «الأنفع» over a week, a month (the default), a year or since the start.
    d = Discussion.objects.create(path=PATH, text_path=PATH)
    author = make_user('author')
    made = {}
    for days, useful in ((3, 1), (20, 5), (200, 9), (500, 20)):
        c = Contribution.objects.create(discussion=d, author=author, kind='question', title=f'سؤال {days}',
                                        body='؟', useful_count=useful)
        Contribution.objects.filter(pk=c.pk).update(created_at=timezone.now() - timedelta(days=days))
        made[c.pk] = days

    def top(**period):
        r = api.get('/api/discussion/feed/', {'place': PATH, 'sort': 'top', **period}).json()
        return r['period'], [made[p['id']] for p in r['posts']]

    assert top(period='week') == ('week', [3])
    assert top(period='month') == top() == top(period='decade') == ('month', [20, 3])
    assert top(period='year') == ('year', [200, 20, 3])
    assert top(period='all') == ('all', [500, 200, 20, 3])
    # Another order has no period.
    r = api.get('/api/discussion/feed/', {'place': PATH, 'sort': 'new', 'period': 'week'}).json()
    assert r['period'] == 'month' and len(r['posts']) == 4


def test_the_hub_reads_every_topic_at_once_and_a_reader_what_they_follow(api, writer, reader):
    here = post(signed_in(api, writer), body='سؤال هنا').json()
    there = post(api, path='/talk/family', body='سؤال هناك').json()
    everything = [p['id'] for p in feed(api, 'new', place='')['posts']]
    assert everything.index(there['id']) < everything.index(here['id'])
    assert feed(api, place='')['place'] is None and feed(api, place='')['scope'] == 'all'
    reader_api = signed_in(api, reader)
    assert feed(reader_api, place='following')['posts'] == []
    reader_api.post('/api/discussion/follow/', {'path': '/talk/family'}, format='json')
    assert [p['id'] for p in feed(reader_api, place='following')['posts']] == [there['id']]
    # The writer follows their own post by writing it.
    assert here['id'] in [p['id'] for p in feed(signed_in(api, writer), place='following')['posts']]


def test_the_margin_counts_what_cites_each_article(api, writer):
    post(signed_in(api, writer), about=ARTICLE, body='سؤال')
    r = api.get('/api/discussion/counts/', {'text': '/ma/loi/2013/67-12'})
    assert r.json() == {'open': True, 'articles': {'art_34': {'count': 1}}}


def test_the_hub_lists_every_place_with_its_latest_posts(api, writer):
    made = post(signed_in(api, writer), body='سؤال').json()
    hub = api.get('/api/discussion/places/').json()['places']
    assert len(hub) == 13 and hub[-1]['slug'] == 'general'
    housing = next(p for p in hub if p['path'] == PATH)
    assert housing['count'] == 1 and [p['id'] for p in housing['posts']] == [made['id']]
