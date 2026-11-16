"""Follow what matters (R13 of the for-everyone review): a law, an article or a life topic; what changed it, from the links
pipeline, with the text that changed it and the BO page; a change not settled is said so; a letter tells an account
only what it had not been told."""
from datetime import date

import pytest
from django.core import mail as outbox

from apps.accounts.services.refusals import Refused
from apps.consolidation.models import Change
from apps.discussion.tests.conftest import ARTICLE as PATH, lease, make_user, signed_in, uploads  # noqa: F401  (fixtures)
from apps.follows.models import Follow
from apps.follows.services import following, news

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'


def change(lease, number, by='2-24', issue=7547, state='read', verb='modified', on=date(2026, 9, 28)):
    return Change.objects.create(text_uri=lease.akn_uri, number=number, verb=verb, source=Change.Source.READING,
                                 by_kind='law', by_number=by, issue=issue, page=7012, published_on=on, state=state)


def test_an_address_is_a_law_an_article_or_a_topic_the_site_holds(lease):
    assert news.describe(TEXT) == {'path': TEXT, 'kind': 'text', 'name': {'ar': 'قانون الكراء', 'fr': news.name(lease)['fr']}}
    assert news.describe(PATH)['article'] == 'المادة 34'
    assert news.describe('/topics/housing')['name']['ar'] == 'السكن والكراء'
    for missing in ('/ma/loi/2013/67-12/art_99', '/topics/nothing', '/elsewhere'):
        with pytest.raises(Refused):
            news.describe(missing)


def test_a_law_hears_of_each_text_that_changed_it_an_article_only_of_its_own(lease):
    change(lease, '34')
    change(lease, '33', state='unclear')
    change(lease, '32', by='10-26', issue=7551, on=date(2026, 10, 12))
    law = news.news([TEXT])[0]
    assert [(i['by']['number'], i['articles'], i['settled']) for i in law['items']] == \
        [('10-26', ['32'], True), ('2-24', ['34', '33'], False)]
    article = news.news([PATH])[0]
    assert [(i['key'], i['articles'], i['settled']) for i in article['items']] == [('law:2-24:7547', ['34'], True)]
    assert following.line(article, article['items'][0], 'ar') == \
        'قانون الكراء: القانون رقم 2.24 غيّر المادة 34 (الجريدة الرسمية عدد 7547، الصفحة 7012)'
    assert following.line(law, law['items'][1], 'ar').endswith('— لم نتحقق منه بعد')


def test_a_letter_tells_only_what_the_account_had_not_been_told(lease, django_capture_on_commit_callbacks):
    change(lease, '34')
    nadia, omar = make_user('nadia'), make_user('omar', proven=False)
    following.follow(nadia, PATH)
    following.follow(omar, PATH)
    assert following.send_letters() == 0  # what stood when she began to follow, she knew
    change(lease, '34', by='10-26', issue=7551, on=date(2026, 10, 12))
    with django_capture_on_commit_callbacks(execute=True):
        assert following.send_letters() == 1
    assert len(outbox.outbox) == 1
    assert 'القانون رقم 10.26 غيّر المادة 34' in outbox.outbox[0].body
    assert following.send_letters() == 0
    assert Follow.objects.get(user=nadia).told == ['law:2-24:7547', 'law:10-26:7551']


def test_anyone_reads_the_news_an_account_follows(api, lease):
    change(lease, '34')
    got = api.get('/api/follows/news/', {'path': [PATH, '/topics/housing', '/nowhere']}).json()['news']
    assert [n['path'] for n in got] == [PATH, '/topics/housing']
    assert api.post('/api/follows/', {'path': TEXT}, format='json').status_code == 401
    me = signed_in(api, make_user('nadia'))
    assert me.post('/api/follows/', {'path': TEXT}, format='json').status_code == 201
    assert me.post('/api/follows/', {'path': '/ma/loi/2013/99-99'}, format='json').json() == \
        {'errors': [{'field': 'path', 'code': 'not_found'}]}
    assert [f['path'] for f in me.get('/api/follows/').json()['following']] == [TEXT]
    me.delete('/api/follows/', {'path': TEXT}, format='json')
    assert me.get('/api/follows/').json()['following'] == []


def test_a_topics_reform_is_followed_by_its_dated_record(settings):
    """«تابع الإصلاح» (F12 of the family plan): each dated line of the record is news, newest first; a reform no person
    has checked is not followed outside development."""
    from apps.topics.services import kit
    kit.load.cache_clear()
    settings.SHOW_DRAFTS = True
    what = news.describe('/topics/family/reform')
    assert what['kind'] == 'reform' and what['name']['ar'] == 'إصلاح مدونة الأسرة'
    items = news.items(what)
    assert items[0]['key'] == 'reform:2026-10-16' and items[-1]['key'] == 'reform:2023-09-26'
    settings.SHOW_DRAFTS = False
    with pytest.raises(Refused):
        news.describe('/topics/family/reform')
    with pytest.raises(Refused):
        news.describe('/topics/family/nowhere')


def test_an_account_follows_at_most_its_cap(api, lease, monkeypatch):
    monkeypatch.setattr(following, 'FOLLOWS_MAX', 2)
    me = signed_in(api, make_user('nadia'))
    assert me.post('/api/follows/', {'path': TEXT}, format='json').status_code == 201
    assert me.post('/api/follows/', {'path': PATH}, format='json').status_code == 201
    assert me.post('/api/follows/', {'path': '/topics/housing'}, format='json').json() == \
        {'errors': [{'field': 'follows', 'code': 'too_many'}]}
    assert me.post('/api/follows/', {'path': TEXT}, format='json').status_code == 201     # one already followed
    # A commune is followed by its name as printed: never longer than the row holds.
    me.delete('/api/follows/', {'path': PATH}, format='json')
    assert me.post('/api/follows/', {'path': '/places/' + 'ب' * 400}, format='json').json() == \
        {'errors': [{'field': 'path', 'code': 'not_found'}]}


@pytest.mark.parametrize('paths', [
    [TEXT, PATH],
    [TEXT, PATH, f'{TEXT}/art_32', f'{TEXT}/art_33', f'{TEXT}/art_35', '/topics/housing', '/places/casablanca',
     '/places/rabat', '/places/سيدي بنور'],
])
def test_an_accounts_follows_are_listed_at_one_cost(api, lease, paths, django_assert_max_num_queries):
    from apps.places.models import Place
    Place.objects.bulk_create([Place(slug='casablanca', kind='city', name_ar='الدار البيضاء', name_fr='Casablanca'),
                               Place(slug='rabat', kind='city', name_ar='الرباط', name_fr='Rabat')])
    user = make_user('nadia')
    Follow.objects.bulk_create([Follow(user=user, path=p) for p in paths])
    me = signed_in(api, user)
    with django_assert_max_num_queries(8):
        listed = me.get('/api/follows/').json()['following']
    assert sorted(f['path'] for f in listed) == sorted(paths)
    assert {f['path']: f['name']['fr'] for f in listed}.get('/places/rabat', 'Rabat') == 'Rabat'


def test_two_lists_of_addresses_never_share_a_kept_answer(api, monkeypatch):
    from apps.follows.api import views
    asked = []
    monkeypatch.setattr(views.generation, 'answer', lambda parts, build, **kw: asked.append(parts) or
                        views.Response({'news': []}))
    api.get('/api/follows/news/', {'path': ['/ma/a:b']})
    api.get('/api/follows/news/', {'path': ['/ma/a', 'b']})
    # The kept answer's key joins its parts with «:» (apps/corpus/services/generation.py).
    assert ':'.join(map(str, asked[0])) != ':'.join(map(str, asked[1]))
