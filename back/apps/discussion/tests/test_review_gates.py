"""Powers that a few accounts or one moderator could turn: hiding by reports counts only reporters whose vote would
count; a pause never shortens one that runs; nobody acts on their own pause; what staff set, or two people confirmed,
staff lift; a review act never defaults to its widest power (a missing length, «false», no place)."""
import pytest
from django.utils import timezone

from apps.discussion.models import Ban, Contribution, Discussion, Reviewer
from apps.discussion.services import review
from apps.discussion.tests.conftest import PATH, make_user, signed_in

pytestmark = pytest.mark.django_db


def act(api, user, pk, **data):
    return signed_in(api, user).post(f'/api/discussion/review/contributions/{pk}/', data, format='json')


def lift(api, user, ban, what='lift'):
    return signed_in(api, user).post(f'/api/discussion/review/pauses/{ban.pk}/', {'act': what}, format='json')


@pytest.fixture
def place(lease):
    return Discussion.objects.create(path=PATH, text_path=PATH)


@pytest.fixture
def moderator(staff, lease):
    user = make_user('rev')
    review.appoint(staff, user, [PATH])
    return user


def post(place, author, title='منشور عادي') -> Contribution:
    return Contribution.objects.create(discussion=place, author=author, kind='post', title=title, body='كلام')


def report(api, user, c):
    return signed_in(api, user).post(f'/api/discussion/contributions/{c.pk}/report/', {'reason': 'exposing'},
                                     format='json')


def test_three_accounts_made_today_cannot_hide_a_post(api, place):
    c = post(place, make_user('salma'))
    for name in ('n1', 'n2', 'n3'):
        assert report(api, make_user(name, days=0), c).status_code == 201
    assert Contribution.objects.get(pk=c.pk).hidden_at is None
    # Unproven ones neither; three whose vote counts do.
    for name in ('u1', 'u2', 'u3'):
        report(api, make_user(name, proven=False), c)
    assert Contribution.objects.get(pk=c.pk).hidden_at is None
    for name in ('o1', 'o2'):
        report(api, make_user(name, days=4), c)
    assert Contribution.objects.get(pk=c.pk).hidden_at is None
    report(api, make_user('o3', days=4), c)
    assert Contribution.objects.get(pk=c.pk).hidden_at is not None


def test_a_pause_never_shortens_one_that_runs(api, place, moderator, staff):
    author = make_user('salma')
    first, second = post(place, author), post(place, author, 'منشور ثان')
    assert act(api, staff, first.pk, act='pause', days='permanent', rule='respect').status_code == 200
    shorter = act(api, moderator, second.pk, act='pause', days=3, rule='respect')
    assert shorter.status_code == 409 and shorter.json()['errors'] == [{'field': 'pause', 'code': 'longer_running'}]
    ban = Ban.objects.get(user=author, ended_at=None)
    assert ban.until is None
    # A longer one replaces a shorter one; an equal or shorter one is refused.
    other = make_user('omar')
    third, fourth = post(place, other), post(place, other, 'منشور رابع')
    assert act(api, moderator, third.pk, act='pause', days=3, rule='respect').status_code == 200
    assert act(api, moderator, fourth.pk, act='pause', days=28, rule='respect').status_code == 200
    assert act(api, moderator, fourth.pk, act='pause', days=7, rule='respect').status_code == 409
    [running] = Ban.objects.filter(user=other, ended_at=None)
    assert (running.until - timezone.now()).days >= 27
    # A pause asked for good is confirmed by a second eye, never replaced by another pause.
    asker = make_user('rev2')
    review.appoint(staff, asker, [PATH])
    third_one = make_user('karim')
    fifth, sixth = post(place, third_one), post(place, third_one, 'منشور سادس')
    assert act(api, asker, fifth.pk, act='pause', days='permanent', rule='respect').status_code == 200
    assert act(api, moderator, sixth.pk, act='pause', days='permanent', rule='respect').status_code == 409
    assert Ban.objects.get(user=third_one, ended_at=None).permanent_asked_by == asker


def test_a_paused_moderator_cannot_lift_or_confirm_their_own_pause(api, place, moderator, staff):
    other = make_user('rev2')
    review.appoint(staff, other, [PATH])
    c = post(place, moderator)
    assert act(api, other, c.pk, act='pause', days='permanent', rule='respect').status_code == 200
    ban = Ban.objects.get(user=moderator, ended_at=None)
    assert lift(api, moderator, ban).json()['errors'] == [{'field': 'review', 'code': 'own'}]
    assert lift(api, moderator, ban, 'confirm').json()['errors'] == [{'field': 'review', 'code': 'own'}]
    assert Ban.objects.get(pk=ban.pk).ended_at is None


def test_what_staff_set_or_two_people_confirmed_only_staff_lift(api, place, moderator, staff):
    author = make_user('salma')
    c = post(place, author)
    act(api, staff, c.pk, act='pause', days=7, rule='respect')
    ban = Ban.objects.get(user=author, ended_at=None)
    assert lift(api, moderator, ban).json()['errors'] == [{'field': 'review', 'code': 'staff_only'}]
    other = make_user('omar')
    asker = make_user('rev2')
    review.appoint(staff, asker, [PATH])
    d = post(place, other)
    act(api, asker, d.pk, act='pause', days='permanent', rule='respect')
    asked = Ban.objects.get(user=other, ended_at=None)
    assert lift(api, moderator, asked, 'confirm').status_code == 200
    assert lift(api, moderator, Ban.objects.get(pk=asked.pk)).json()['errors'] == [{'field': 'review', 'code': 'staff_only'}]
    assert lift(api, staff, ban).status_code == 200 and lift(api, staff, asked).status_code == 200
    # A moderator still lifts what a moderator set for a few days.
    e = post(place, make_user('karim'))
    act(api, asker, e.pk, act='pause', days=3, rule='respect')
    assert lift(api, moderator, Ban.objects.get(user__username='karim', ended_at=None)).status_code == 200


def test_a_pause_without_a_length_is_refused_not_made_permanent(api, place, moderator):
    c = post(place, make_user('salma'))
    assert act(api, moderator, c.pk, act='pause', rule='respect').json()['errors'] == [{'field': 'days', 'code': 'required'}]
    assert act(api, moderator, c.pk, act='pause', days='soon', rule='respect').json()['errors'] == \
        [{'field': 'days', 'code': 'invalid'}]
    assert act(api, moderator, c.pk, act='pause', days=5, rule='respect').status_code == 400
    assert not Ban.objects.exists()


def test_false_does_not_lock_a_topic(api, place, moderator):
    out = signed_in(api, moderator).post('/api/discussion/review/lock/', {'path': PATH, 'locked': 'false'}, format='json')
    assert out.json() == {'locked': False} and Discussion.objects.get(pk=place.pk).locked_at is None
    assert signed_in(api, moderator).post('/api/discussion/review/lock/', {'path': PATH, 'locked': True},
                                          format='json').json() == {'locked': True}


def test_a_moderator_of_everything_is_asked_for_in_as_many_words(api, staff):
    target = make_user('salma')
    out = signed_in(api, staff).post('/api/discussion/review/reviewers/', {'username': 'salma'}, format='json')
    assert out.json() == {'errors': [{'field': 'places', 'code': 'required'}]} and not Reviewer.objects.exists()
    assert signed_in(api, staff).post('/api/discussion/review/reviewers/', {'username': 'salma', 'places': ['family']},
                                      format='json').status_code == 201
    assert Reviewer.objects.get(user=target, ended_at=None).text_paths == ['/talk/family']
    signed_in(api, staff).post('/api/discussion/review/reviewers/', {'username': 'salma', 'everywhere': True},
                               format='json')
    assert Reviewer.objects.get(user=target, ended_at=None).text_paths == []
