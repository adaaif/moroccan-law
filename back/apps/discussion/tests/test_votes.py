"""«مفيد», «أفادني», points and titles."""
import pytest

from apps.discussion.models import Contribution, Point
from apps.discussion.services import points
from apps.discussion.tests.conftest import PATH, TITLE, feed, make_user, post_of, settle, signed_in

pytestmark = pytest.mark.django_db


def contribute(api, user, **data):
    sent = {'path': PATH, 'kind': 'question', **({} if data.get('parent') else {'title': TITLE}), **data}
    return signed_in(api, user).post('/api/discussion/contributions/', sent, format='json').json()


def test_useful_counts_from_a_proven_account_three_days_old(api, writer):
    c = contribute(api, writer, body='سؤال')
    voters = [make_user('old'), make_user('young', days=1), make_user('unproven', proven=False)]
    for v in voters:
        assert signed_in(api, v).post(f'/api/discussion/contributions/{c["id"]}/useful/').status_code == 200
    assert Contribution.objects.get(pk=c['id']).useful_count == 1
    assert points.total(writer) == 1


def test_no_one_votes_for_themself_and_a_vote_taken_back_takes_its_point(api, writer, reader):
    c = contribute(api, writer, body='سؤال')
    r = signed_in(api, writer).post(f'/api/discussion/contributions/{c["id"]}/useful/')
    assert r.status_code == 400 and r.json()['errors'] == [{'field': 'useful', 'code': 'own'}]
    signed_in(api, reader).post(f'/api/discussion/contributions/{c["id"]}/useful/')
    assert api.delete(f'/api/discussion/contributions/{c["id"]}/useful/').json() == {'useful': 0, 'voted': False}
    assert points.total(writer) == 0


def test_only_the_asker_marks_one_answer(api, writer):
    q = contribute(api, writer, body='سؤال')
    first = settle(make_user('amine'), None)
    second = settle(make_user('karim'), None)
    a1 = contribute(api, first, kind='explanation', body='جواب', parent=q['id'])
    a2 = contribute(api, second, kind='explanation', body='جواب آخر', parent=q['id'])
    r = signed_in(api, first).post(f'/api/discussion/contributions/{a2["id"]}/accept/')
    assert r.status_code == 403
    signed_in(api, writer).post(f'/api/discussion/contributions/{a1["id"]}/accept/')
    api.post(f'/api/discussion/contributions/{a2["id"]}/accept/')
    assert list(Contribution.objects.exclude(accepted_at=None).values_list('pk', flat=True)) == [a2['id']]
    assert (points.total(first), points.total(second)) == (0, 5)
    page = post_of(api, q['id'])['post']
    assert [r['id'] for r in page['replies']] == [a2['id'], a1['id']]


def test_karma_shows_beside_each_name_and_on_a_persons_page(api, writer, reader):
    for i in range(25):
        Point.objects.create(user=writer, source='useful', ref=f'x{i}', amount=1)
    Point.objects.create(user=writer, source='useful', ref='gone', amount=1, voided_at='2026-10-20T00:00:00Z')
    contribute(api, writer, body='سؤال')
    c = feed(signed_in(api, reader))['posts'][0]
    assert c['author'] == {'username': 'nadia', 'name': 'nadia', 'form': '', 'karma': 25}
    person = api.get('/api/discussion/people/nadia/').json()['person']
    assert person['karma'] == 25 and person['moderates'] == []


def test_staff_see_who_a_topic_found_useful_to_choose_its_moderators(api, writer, reader, staff):
    q = contribute(api, writer, body='سؤال')
    helper = settle(make_user('amine'), None)
    a = contribute(api, helper, body='جواب', parent=q['id'])
    signed_in(api, writer).post(f'/api/discussion/contributions/{a["id"]}/accept/')
    signed_in(api, reader).post(f'/api/discussion/contributions/{a["id"]}/useful/')
    signed_in(api, reader).post(f'/api/discussion/contributions/{q["id"]}/useful/')
    out = signed_in(api, staff).get('/api/discussion/review/reviewers/', {'place': PATH}).json()
    assert [(c['username'], c['karma_here']) for c in out['candidates']] == [('amine', 6), ('nadia', 1)]
    assert len(out['places']) == 13
    api.post('/api/discussion/review/reviewers/', {'username': 'amine', 'places': ['housing']}, format='json')
    out = api.get('/api/discussion/review/reviewers/', {'place': PATH}).json()
    assert [c['username'] for c in out['candidates']] == ['nadia']
    assert out['reviewers'][0]['text_paths'] == [PATH] and out['reviewers'][0]['karma'] == 6
    assert feed(api)['place']['moderators'] == [{'username': 'amine', 'name': 'amine', 'karma': 6}]
    assert api.get('/api/discussion/people/amine/').json()['person']['moderates'] == [
        {'path': PATH, 'name': {'ar': 'السكن والكراء', 'fr': 'Logement et location'}}]


def test_the_waiting_questions_are_counted_across_the_topics(api, writer, reader):
    contribute(api, writer, kind='post', body='منشور')
    question = contribute(api, writer, body='سؤال')
    contribute(api, writer, path='/talk/work', body='سؤال آخر')
    assert len(api.get('/api/discussion/questions/').json()['questions']) == 2
    only = api.get('/api/discussion/questions/', {'place': PATH}).json()
    assert [q['id'] for q in only['questions']] == [question['id']]
    assert only['questions'][0]['label']['place'] == 'housing'
