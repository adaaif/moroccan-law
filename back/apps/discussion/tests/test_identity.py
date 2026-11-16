"""The proven email, a person's page, taking one's data and leaving."""
import pytest
from django.core import mail

from apps.accounts.models import EmailCode, User
from apps.discussion.models import Contribution
from apps.discussion.tests.conftest import PATH, make_user, settle, signed_in
from apps.media.models import Clip
from apps.media.services import store

pytestmark = pytest.mark.django_db


def test_a_six_digit_code_proves_the_address(api):
    user = make_user('new', proven=False)
    api = signed_in(api, user)
    assert api.post('/api/auth/email/code/').status_code == 204
    code = mail.outbox[0].subject.strip('\u202b\u202c').rsplit(' ', 1)[-1]
    assert len(code) == 6 and code.isdigit() and code in mail.outbox[0].body
    assert EmailCode.objects.get().code_digest != code
    wrong = '000000' if code != '000000' else '111111'
    assert api.post('/api/auth/email/prove/', {'code': wrong}, format='json').json()['errors'] == [
        {'field': 'code', 'code': 'invalid'}]
    r = api.post('/api/auth/email/prove/', {'code': code}, format='json')
    assert r.status_code == 200 and r.json()['email_proven'] is True


def test_a_code_burns_after_five_wrong_tries(api):
    api = signed_in(api, make_user('new', proven=False))
    api.post('/api/auth/email/code/')
    code = mail.outbox[0].subject.strip('\u202b\u202c').rsplit(' ', 1)[-1]
    wrong = '000000' if code != '000000' else '111111'
    for _ in range(5):
        api.post('/api/auth/email/prove/', {'code': wrong}, format='json')
    assert api.post('/api/auth/email/prove/', {'code': code}, format='json').status_code == 400


def test_five_letters_an_hour(api):
    api = signed_in(api, make_user('new', proven=False))
    for _ in range(5):
        assert api.post('/api/auth/email/code/').status_code == 204
    r = api.post('/api/auth/email/code/')
    assert r.status_code == 429 and r.json()['errors'] == [{'field': 'email', 'code': 'too_many_codes'}]


def test_a_persons_page_shows_their_named_words_never_their_anonymous_ones(api, writer):
    signed_in(api, writer)
    api.post('/api/discussion/contributions/', {'path': PATH, 'kind': 'post', 'title': 'عنوان', 'body': 'باسمي'}, format='json')
    api.post('/api/discussion/contributions/', {'path': PATH, 'kind': 'question', 'title': 'سؤال', 'body': 'بدون اسم',
                                                'anonymous': True}, format='json')
    page = api.get('/api/discussion/people/NADIA/').json()
    bodies = [c['body'] for c in page['contributions']]
    assert bodies[0] == 'باسمي' and 'بدون اسم' not in bodies
    assert api.get('/api/discussion/people/nobody/').status_code == 404


def test_a_persons_page_says_where_they_write_and_shows_their_posts_or_their_answers(api, writer):
    signed_in(api, writer)
    count = lambda p: (p['contributions'], p['posts'], p['answers'], {x['path']: x['count'] for x in p['places']}.get(PATH, 0))
    before = count(api.get('/api/discussion/people/NADIA/').json()['person'])
    post = api.post('/api/discussion/contributions/', {'path': PATH, 'kind': 'question', 'title': 'سؤال ديالي',
                                                       'body': 'سؤال'}, format='json').json()
    api.post('/api/discussion/contributions/', {'parent': post['id'], 'body': 'جواب ديالي'}, format='json')
    p = api.get('/api/discussion/people/NADIA/').json()['person']
    assert [a - b for a, b in zip(count(p), before)] == [2, 1, 1, 2] and p['last_at']
    posts = api.get('/api/discussion/people/NADIA/?kind=posts').json()['contributions']
    answers = api.get('/api/discussion/people/NADIA/?kind=answers').json()['contributions']
    assert posts[0]['body'] == 'سؤال' and all(c['kind'] != 'comment' for c in posts)
    assert answers[0]['body'] == 'جواب ديالي' and all(c['kind'] == 'comment' for c in answers)


def test_the_header_menu_knows_the_readers_karma_and_whether_they_moderate(api, writer):
    signed_in(api, writer)
    d = api.get('/api/discussion/me/unseen/').json()
    assert d['karma'] == 0 and d['reviewer'] is False


def test_the_account_takes_its_data_away(api, writer):
    signed_in(api, writer).post('/api/discussion/contributions/', {'path': PATH, 'kind': 'question', 'title': 'سؤال', 'body': 'سؤال'},
                                format='json')
    r = api.get('/api/auth/me/export/')
    assert r.status_code == 200 and 'attachment' in r['Content-Disposition']
    assert [c['body'] for c in r.json()['contributions']][-1] == 'سؤال'
    assert set(r.json()) >= {'checks', 'following_discussions', 'following_laws_and_topics', 'explanations_written'}


def test_deleting_an_account_keeps_its_words_as_a_deleted_account_and_erases_its_voices(api, writer, reader):
    signed_in(api, writer).post('/api/discussion/contributions/', {'path': PATH, 'kind': 'question', 'title': 'سؤال', 'body': 'سؤال'},
                                format='json')
    clip = Clip.objects.create(owner=writer, duration_ms=1, size=1, file_name=store.write('voices', b'x', 'm4a'))
    Contribution.objects.filter(author=writer, body='سؤال').update(clip=clip)
    assert api.post('/api/auth/me/delete/', {'password': 'wrong'}, format='json').status_code == 400
    assert api.post('/api/auth/me/delete/', {'password': 'a long secret 2026'}, format='json').status_code == 204
    gone = User.objects.get(pk=writer.pk)
    assert gone.deleted_at and not gone.is_active and gone.email.endswith('.invalid')
    clip.refresh_from_db()
    assert clip.state == 'erased'
    c = signed_in(api, reader).get('/api/discussion/feed/', {'place': PATH}).json()['posts'][0]
    assert c['body'] == 'سؤال' and c['author'] == {'deleted': True}


def test_leaving_takes_its_votes_and_the_points_they_gave_and_its_follows(api, writer, reader):
    from apps.discussion.services import points
    from apps.follows.models import Follow as Followed

    q = signed_in(api, writer).post('/api/discussion/contributions/', {'path': PATH, 'kind': 'question', 'title': 'سؤال',
                                                                      'body': 'سؤال'}, format='json').json()
    leaver = settle(make_user('leaver'), None)
    signed_in(api, leaver).post(f'/api/discussion/contributions/{q["id"]}/useful/')
    Followed.objects.create(user=leaver, path='/topics/housing')
    assert points.total(writer) == 1
    assert api.post('/api/auth/me/delete/', {'password': 'a long secret 2026'}, format='json').status_code == 204
    assert Contribution.objects.get(pk=q['id']).useful_count == 0 and points.total(writer) == 0
    assert not Followed.objects.filter(user=leaver).exists()
