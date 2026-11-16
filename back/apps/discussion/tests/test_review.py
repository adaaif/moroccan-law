"""The reviewers' powers: holds, reports, removals with a rule, pauses with a second eye, appeals, the ledger."""
from django.core import mail
from django.core.management import call_command
import pytest

from apps.discussion.models import Action, Ban, Contribution, Notice, Report
from apps.discussion.services import points, review
from apps.discussion.tests.conftest import PATH, TITLE, feed, make_user, settle, signed_in

pytestmark = pytest.mark.django_db


def contribute(api, user, **data):
    sent = {'path': PATH, 'kind': 'question', **({} if data.get('parent') else {'title': TITLE}), **data}
    return signed_in(api, user).post('/api/discussion/contributions/', sent, format='json').json()


def act(api, user, pk, **data):
    return signed_in(api, user).post(f'/api/discussion/review/contributions/{pk}/', data, format='json')


@pytest.fixture
def lawyer_reviewer(staff, lease):
    """A moderator of the housing topic, from its community."""
    user = make_user('rev')
    review.appoint(staff, user, [PATH])
    return user


def test_a_moderator_sees_only_their_topics_and_never_their_own_words(api, lease, staff):
    other = make_user('elsewhere')
    review.appoint(staff, other, ['/talk/work'])
    held = contribute(api, make_user('salma'), body='سؤال')
    assert signed_in(api, other).get('/api/discussion/review/', {'tab': 'held'}).json()['items'] == []
    assert act(api, other, held['id'], act='approve').status_code == 403
    assert signed_in(api, make_user('nobody')).get('/api/discussion/review/').status_code == 403


def test_publishing_a_held_contribution_tells_its_author_and_is_ledgered(api, lawyer_reviewer, reader):
    author = make_user('salma')
    held = contribute(api, author, body='سؤال 0600000000')
    queue = signed_in(api, lawyer_reviewer).get('/api/discussion/review/', {'tab': 'held'}).json()
    assert queue['counts']['held'] == 1
    assert queue['items'][0]['held_reasons'] == ['phone']
    assert act(api, lawyer_reviewer, held['id'], act='approve').status_code == 200
    assert Contribution.objects.get(pk=held['id']).published
    assert Notice.objects.filter(user=author, kind='approved').exists()
    assert list(Action.objects.values_list('verb', flat=True).order_by('pk')) == ['appoint', 'approve']


def test_a_removal_names_its_rule_takes_back_points_and_tells_the_author(api, writer, lawyer_reviewer, reader):
    c = contribute(api, writer, body='اتصلوا بالمكتب')
    signed_in(api, make_user('v1')).post(f'/api/discussion/contributions/{c["id"]}/useful/')
    signed_in(api, reader).post(f'/api/discussion/contributions/{c["id"]}/report/', {'reason': 'soliciting'},
                                format='json')
    assert points.total(writer) == 1
    assert act(api, lawyer_reviewer, c['id'], act='remove').json()['errors'] == [{'field': 'rule', 'code': 'required'}]
    assert act(api, lawyer_reviewer, c['id'], act='remove', rule='soliciting').status_code == 200
    call_command('send_notice_letters')
    row = Contribution.objects.get(pk=c['id'])
    assert row.removed_rule == 'soliciting' and points.total(writer) == 0
    assert Report.objects.get().status == 'acted'
    assert Notice.objects.filter(user=writer, kind='removed', detail='soliciting').exists()
    assert Notice.objects.filter(user=reader, kind='report', detail='acted').exists()
    assert any('القاعدة 3' in m.body for m in mail.outbox)
    assert feed(signed_in(api, reader))['posts'] == []


def test_a_restore_gives_the_points_back(api, writer, lawyer_reviewer):
    c = contribute(api, writer, body='شرح')
    signed_in(api, make_user('v1')).post(f'/api/discussion/contributions/{c["id"]}/useful/')
    act(api, lawyer_reviewer, c['id'], act='remove', rule='on_topic')
    act(api, lawyer_reviewer, c['id'], act='restore')
    assert Contribution.objects.get(pk=c['id']).published and points.total(writer) == 1


def test_a_pause_stops_writing_and_voting_but_not_reading(api, writer, lawyer_reviewer):
    c = contribute(api, writer, body='سؤال')
    assert act(api, lawyer_reviewer, c['id'], act='pause', days=7, rule='respect').status_code == 200
    r = signed_in(api, writer).post('/api/discussion/contributions/', {'path': PATH, 'kind': 'post', 'title': TITLE, 'body': 'x'},
                                    format='json')
    assert r.status_code == 403 and r.json()['errors'] == [{'field': 'account', 'code': 'paused'}]
    assert api.get('/api/discussion/feed/', {'place': PATH}).status_code == 200


def test_a_reviewers_pause_for_good_waits_for_a_second_eye(api, writer, lawyer_reviewer, staff):
    c = contribute(api, writer, body='سؤال')
    act(api, lawyer_reviewer, c['id'], act='pause', days='permanent', rule='respect')
    ban = Ban.objects.get()
    assert ban.until is not None and ban.permanent_asked_by == lawyer_reviewer
    r = signed_in(api, lawyer_reviewer).post(f'/api/discussion/review/pauses/{ban.pk}/', {'act': 'confirm'},
                                             format='json')
    assert r.json()['errors'] == [{'field': 'review', 'code': 'second_eye'}]
    signed_in(api, staff).post(f'/api/discussion/review/pauses/{ban.pk}/', {'act': 'confirm'}, format='json')
    ban.refresh_from_db()
    assert ban.until is None


def test_an_appeal_is_once_and_goes_to_someone_else(api, writer, lawyer_reviewer, staff):
    c = contribute(api, writer, body='شرح')
    act(api, lawyer_reviewer, c['id'], act='remove', rule='on_topic')
    api = signed_in(api, writer)
    assert api.post('/api/discussion/appeals/', {'contribution': c['id'], 'text': 'كان في الموضوع'},
                    format='json').status_code == 201
    assert api.post('/api/discussion/appeals/', {'contribution': c['id'], 'text': 'مرة أخرى'},
                    format='json').json()['errors'] == [{'field': 'appeal', 'code': 'used'}]
    mine = signed_in(api, lawyer_reviewer).get('/api/discussion/review/', {'tab': 'appeals'}).json()
    assert mine['items'] == []
    theirs = signed_in(api, staff).get('/api/discussion/review/', {'tab': 'appeals'}).json()['items']
    signed_in(api, staff).post(f'/api/discussion/review/appeals/{theirs[0]["id"]}/', {'outcome': 'lifted'},
                               format='json')
    assert Contribution.objects.get(pk=c['id']).published


def test_only_staff_reveal_an_anonymous_author_and_the_ledger_keeps_why(api, writer, lawyer_reviewer, staff):
    c = contribute(api, writer, body='سؤال', anonymous=True)
    queue_card = review.queue(lawyer_reviewer, 'held')
    assert not queue_card
    assert act(api, lawyer_reviewer, c['id'], act='reveal', note='x').status_code == 403
    assert act(api, staff, c['id'], act='reveal').json()['errors'] == [{'field': 'note', 'code': 'required'}]
    assert act(api, staff, c['id'], act='reveal', note='تهديد').json()['username'] == 'nadia'
    assert Action.objects.get(verb='reveal').note == 'تهديد'
    ledger = signed_in(api, lawyer_reviewer).get('/api/discussion/review/ledger/').json()['actions']
    assert ledger[0]['target'] is None


def test_the_monthly_numbers_count_without_names(api, writer, reader):
    c = contribute(api, writer, body='سؤال')
    signed_in(api, reader).post(f'/api/discussion/contributions/{c["id"]}/report/', {'reason': 'abuse'},
                                format='json')
    month = api.get('/api/discussion/numbers/').json()['months'][0]
    assert month['contributions'] == 4 and month['reports']['abuse'] == 1


def test_reporting_is_once_and_never_ones_own(api, writer, reader):
    c = contribute(api, writer, body='سؤال')
    assert signed_in(api, writer).post(f'/api/discussion/contributions/{c["id"]}/report/', {'reason': 'abuse'},
                                       format='json').status_code == 400
    api = signed_in(api, reader)
    assert api.post(f'/api/discussion/contributions/{c["id"]}/report/', {'reason': 'abuse'},
                    format='json').status_code == 201
    assert api.post(f'/api/discussion/contributions/{c["id"]}/report/', {'reason': 'abuse'},
                    format='json').json()['errors'] == [{'field': 'report', 'code': 'already'}]


def test_answers_and_followed_discussions_send_one_letter_at_a_time(api, writer):
    q = contribute(api, writer, body='سؤال')
    one, two = settle(make_user('amine'), None), settle(make_user('karim'), None)
    contribute(api, one, body='جواب', parent=q['id'])
    contribute(api, two, body='جواب ثان', parent=q['id'])
    call_command('send_notice_letters')
    to_writer = [m for m in mail.outbox if m.to == ['nadia@example.org']]
    assert len(to_writer) == 1
    assert Notice.objects.filter(user=writer).count() == 2
