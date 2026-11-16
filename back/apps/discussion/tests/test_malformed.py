"""No malformed request answers 500 at any address of apps.discussion (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""
import pytest


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('discussion', malformed) == []

from apps.discussion.models import Contribution, Discussion  # noqa: E402
from apps.discussion.tests.conftest import PATH, TITLE, make_user, signed_in  # noqa: E402


def _codes(r):
    return [(e['field'], e['code']) for e in r.json()['errors']]


@pytest.fixture
def post(writer):
    place, _ = Discussion.objects.get_or_create(path=PATH, defaults={'text_path': PATH})
    return Contribution.objects.create(discussion=place, author=writer, kind='question', title=TITLE, body='نص')


@pytest.mark.django_db
@pytest.mark.parametrize('field, value', [('title', 5), ('body', ['نص']), ('about', True), ('quote', {'a': 1}),
                                          ('path', ['/talk/housing']), ('parent', '²'), ('parent', [1]),
                                          ('parent', 10**40), ('voice', 'not-a-voice'), ('pictures', [{}]),
                                          ('pictures', 'a,b')])
def test_a_contributions_field_of_another_kind_is_refused(api, writer, field, value):
    """A list read as words (`.strip()`), a word read as a row's number, a voice that is no id: each answered 500."""
    sent = {'path': PATH, 'kind': 'question', 'title': TITLE, 'body': 'نص', field: value}
    r = signed_in(api, writer).post('/api/discussion/contributions/', sent, format='json')
    assert (r.status_code, _codes(r)) == (400, [(field, 'invalid')])


@pytest.mark.django_db
def test_the_review_and_the_letters_refuse_words_of_another_kind(api, writer, staff, post):
    staff.is_superuser = True
    staff.save()
    desk = signed_in(api, staff)
    for url, body, field in [(f'/api/discussion/review/contributions/{post.pk}/', {'act': 'send_back', 'note': 5}, 'note'),
                             (f'/api/discussion/review/contributions/{post.pk}/', {'act': 'duplicate', 'of': ['1']}, 'of'),
                             ('/api/discussion/review/lock/', {'path': PATH, 'locked': True, 'note': []}, 'note'),
                             ('/api/discussion/review/reviewers/', {'username': 'nadia', 'text_paths': 5}, 'text_paths'),
                             ('/api/discussion/appeals/', {'pause': [1], 'text': 'ظلمت'}, 'pause'),
                             ('/api/discussion/appeals/', {'contribution': post.pk, 'text': 5}, 'text'),
                             (f'/api/discussion/contributions/{post.pk}/report/', {'reason': 'spam', 'details': [1]},
                              'details'),
                             (f'/api/discussion/contributions/{post.pk}/takedown/', {'details': 'x', 'contact': 5},
                              'contact'),
                             ('/api/discussion/letters/stop/', {'t': 5, 'scope': 'all'}, 't')]:
        r = desk.post(url, body, format='json')
        assert (r.status_code, _codes(r)) == (400, [(field, 'invalid')]), url
    # An appeal or a duplicate whose id is '' is one with no id, as a missing one is.
    r = desk.post('/api/discussion/appeals/', {'pause': '', 'text': 'ظلمت'}, format='json')
    assert (r.status_code, _codes(r)) == (404, [('pause', 'not_found')])


@pytest.mark.django_db
def test_a_page_or_a_comment_past_the_database_is_an_empty_page(api, post):
    """«?page=10**40» overflowed the query's offset; a comment's number past any id, its lookup."""
    huge = '9' * 40
    for url in (f'/api/discussion/feed/?place={PATH}&page={huge}', f'/api/discussion/posts/{post.pk}/?page={huge}',
                f'/api/discussion/posts/{post.pk}/replies/?around={huge}', f'/api/discussion/questions/?page={huge}',
                f'/api/discussion/answered/?page={huge}', f'/api/discussion/people/nadia/?page={huge}'):
        assert api.get(url).status_code < 500, url


@pytest.mark.django_db
def test_a_broken_link_is_a_link_that_holds_never_an_error(api):
    """`urlparse('https://[')` raises: the words a reader checks, writes or explains answered 500."""
    r = api.post('/api/discussion/check/', {'body': 'انظر https://[ هنا'}, format='json')
    assert r.status_code == 200 and 'link' in r.json()['reasons']


@pytest.mark.django_db
def test_following_a_post_whose_number_is_no_number_is_refused(api, writer):
    r = signed_in(api, writer).post('/api/discussion/follow/', {'path': f'{PATH}/²'}, format='json')
    assert 400 <= r.status_code < 500


@pytest.mark.django_db
def test_a_moderators_address_takes_delete_alone(api, staff):
    """One view for both addresses called its methods with an argument they do not take: a GET or POST on
    /reviewers/<id>/, or a DELETE on /reviewers/, answered 500."""
    staff.is_superuser = True
    staff.save()
    desk = signed_in(api, staff)
    other = make_user('mod')
    assert desk.get(f'/api/discussion/review/reviewers/{other.pk}/').status_code == 405
    assert desk.post(f'/api/discussion/review/reviewers/{other.pk}/', {}, format='json').status_code == 405
    assert desk.delete('/api/discussion/review/reviewers/').status_code == 405
    assert desk.get('/api/discussion/review/reviewers/').status_code == 200
