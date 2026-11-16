"""The polish of 19 Oct 2026 (its 6 fixes and 27 recommendations, all «Yes»): fewer
waits for writers, fewer clicks for reviewers, nothing lost for readers."""
import io
from datetime import timedelta

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

from apps.accounts.services import mail as letters
from apps.discussion.models import Action, Contribution, Follow, Notice, Report, Revision, Trust
from apps.discussion.services import review, thread
from apps.discussion.tests.conftest import ARTICLE, PATH, TITLE, feed, make_user, post_of, settle, signed_in
from apps.media.models import Picture
from apps.topics.services import kit

pytestmark = pytest.mark.django_db


def contribute(api, user, **data):
    sent = {'path': PATH, 'kind': 'question', **({} if data.get('parent') else {'title': TITLE}), **data}
    r = signed_in(api, user).post('/api/discussion/contributions/', sent, format='json')
    assert r.status_code == 201, r.content
    return r.json()


def act(api, user, pk, **data):
    return signed_in(api, user).post(f'/api/discussion/review/contributions/{pk}/', data, format='json')


@pytest.fixture
def rev(staff, lease):
    user = make_user('rev')
    review.appoint(staff, user, [PATH])
    return user


def picture_file():
    buf = io.BytesIO()
    Image.new('RGB', (640, 480), (90, 120, 160)).save(buf, 'JPEG')
    return SimpleUploadedFile('p.jpg', buf.getvalue(), content_type='image/jpeg')


# ── writers ───────────────────────────────────────────────────────────────

def test_a_held_contribution_goes_live_once_its_author_takes_the_number_out(api, writer):
    c = contribute(api, writer, body='اتصلوا بي 0600000000')
    assert c['held'] is True and c['held_reasons'] == ['phone']
    r = api.patch(f'/api/discussion/contributions/{c["id"]}/', {'body': 'سؤال بلا رقم'}, format='json')
    assert r.json()['held'] is False
    assert Contribution.objects.get(pk=c['id']).published


def test_a_reply_under_an_answer_says_whom_it_answers(api, writer):
    q = contribute(api, writer, body='سؤال')
    nadia = settle(make_user('nadia2'), None)
    a = contribute(api, nadia, kind='explanation', body='جواب', parent=q['id'])
    b = contribute(api, writer, kind='remark', body='شكرا', parent=a['id'])
    assert b['parent'] == q['id'] and b['reply_to'] == {'id': a['id'], 'name': 'nadia2', 'anonymous': False}


def test_the_form_learns_what_would_hold_it_before_sending(api, lease):
    r = api.post('/api/discussion/check/', {'body': 'راسلني على me@example.org أو 0600000000'}, format='json')
    assert r.json()['reasons'] == ['email', 'phone']
    body = 'راسلني على me@example.org أو 0600000000'
    assert [body[s:e] for s, e, _ in r.json()['spans']] == ['me@example.org', '0600000000']


def test_similar_questions_in_the_same_topic(api, writer):
    contribute(api, writer, body='واش مول الدار عندو الحق يطلب زيادة 15% في الكراء قبل ثلاث سنين؟')
    found = api.post('/api/discussion/similar/', {'path': PATH, 'q': 'المكري طلب زيادة في الكراء قبل ثلاث سنين'},
                     format='json').json()
    assert len(found['questions']) == 1
    assert api.post('/api/discussion/similar/', {'path': PATH, 'q': 'سؤال عن الإرث'},
                    format='json').json()['questions'] == []
    # The words being typed go in the body, never in the address: the logs write addresses.
    assert api.get('/api/discussion/similar/', {'path': PATH, 'q': 'سؤال عن الإرث'}).status_code == 405



def test_search_answers_with_the_questions_people_asked_already_and_their_best_answer(api, writer, reader, lease):
    # The search page's «سولو قبلك» (30 Oct 2026): the same door's words find the question though the words differ
    # («طلع ليا الكرا» and «بغا يزيد فالكرا»); its best answer is someone else's, a direct answer before a thank-you.
    q = contribute(api, writer, title='مول الدار بغا يزيد فالكرا', body='طلب 15% وما زال ما كملناش عامين من العقد.')
    other = contribute(api, writer, title='الضمانة ما بغاش يردها', body='خرجت من الدار وما رد ليا الضمانة.')
    settle(reader, lease)
    a = contribute(api, reader, kind='explanation', body='المادة 32: لا زيادة قبل ثلاث سنوات.', parent=q['id'])
    contribute(api, writer, kind='remark', body='شكرا بزاف', parent=a['id'])
    people = thread.asked_before(PATH, 'طلع ليا الكرا', kit.door_words('housing-increase'))
    assert [p['id'] for p in people] == [q['id']] and other['id'] not in [p['id'] for p in people]
    assert people[0]['answers'] == 2 and people[0]['answer']['body'].startswith('المادة 32')
    assert thread.asked_before(PATH, 'الطلاق والنفقة ديال الولاد', []) == []
    # Asked beside the search's own answer (PX10 of the where-it-trips review), by the same words: the search no longer
    # waits for them.
    r = api.get('/api/search/people/', {'q': 'مول الدار بغا يزيد فالكرا'})
    assert r.status_code == 200 and r.data['topic'] == 'housing' and [p['id'] for p in r.data['people']] == [q['id']]
    assert api.get('/api/search/people/', {'q': 'zzz'}).data == {'topic': None, 'people': []}

def test_signing_up_sends_the_code_at_once(api, lease):
    r = api.post('/api/auth/register/', {'username': 'newone', 'email': 'new@example.org',
                                         'password': 'a long secret 2026', 'preferred_language': 'ar'}, format='json')
    assert r.status_code == 201
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ['new@example.org']
    signed_in(api, make_user('unproven', proven=False))
    writing = feed(api)['writing']
    assert writing['why'] == 'email.not_proven' and writing['email_hint'] == 'u•••@example.org'


# ── reviewers ─────────────────────────────────────────────────────────────

def test_the_card_carries_its_context_and_its_suggested_rule(api, writer, rev):
    q = contribute(api, writer, body='سؤال', about=ARTICLE)
    held = contribute(api, make_user('salma'), body='عيطو ليا 0600000000', parent=q['id'])
    card = signed_in(api, rev).get('/api/discussion/review/', {'tab': 'held'}).json()['items'][0]
    assert card['id'] == held['id'] and card['context']['suggested'] == 'soliciting'
    assert card['context']['parent']['id'] == q['id'] and card['context']['parent']['title'] == TITLE
    assert card['path'] == f"{PATH}/{q['id']}" and card['post_title'] == TITLE


def test_redacting_keeps_the_words_and_drops_the_number(api, writer, rev):
    c = contribute(api, writer, body='مفيد جدا، اتصلوا 0600000000 للمزيد')
    start, end, _ = Contribution.objects.get(pk=c['id']).held_spans[0]
    assert act(api, rev, c['id'], act='redact', spans=[[start, end]]).status_code == 200
    call_command('send_notice_letters')
    row = Contribution.objects.get(pk=c['id'])
    assert row.body == 'مفيد جدا، اتصلوا [حُذف] للمزيد' and row.published
    assert Revision.objects.get(contribution=row).body.endswith('0600000000 للمزيد')
    assert {m.subject.strip('\u202b\u202c') for m in mail.outbox} >= {'حذفنا جزءا من مساهمتك', 'نُشرت مساهمتك في «قانون المغرب»'}


def test_sending_back_hides_it_until_the_author_edits_then_it_returns_first(api, writer, rev, reader):
    older = contribute(api, make_user('other'), body='سؤال قديم 0600000001')
    c = contribute(api, writer, body='قصة فيها تفاصيل كثيرة')
    act(api, rev, c['id'], act='send_back', note='احذف اسم المكري')
    assert feed(signed_in(api, reader))['posts'] == []
    mine = feed(signed_in(api, writer))['posts'][0]
    assert mine['review_note'] == 'احذف اسم المكري' and mine['held'] is True
    api.patch(f'/api/discussion/contributions/{c["id"]}/', {'body': 'قصة بلا أسماء'}, format='json')
    queue = signed_in(api, rev).get('/api/discussion/review/', {'tab': 'held'}).json()['items']
    assert [i['id'] for i in queue][:2] == [c['id'], older['id']]


def test_a_trusted_author_waits_for_nothing_until_a_removal(api, rev, lease):
    salma = make_user('salma')
    first = contribute(api, salma, body='سؤال')
    act(api, rev, first['id'], act='trust')
    second = contribute(api, salma, body='سؤال ثان')
    assert second['held'] is False and Contribution.objects.get(pk=second['id']).post_review_at is None
    act(api, rev, second['id'], act='remove', rule='on_topic')
    assert not Trust.objects.filter(user=salma, ended_at=None).exists()
    assert list(Action.objects.filter(verb__in=['trust', 'untrust']).values_list('verb', flat=True)) == [
        'trust', 'untrust']


def test_a_repeated_question_points_to_the_first(api, writer, rev):
    first = contribute(api, writer, body='واش نقدر نزيد؟')
    again = contribute(api, settle(make_user('karim'), None), body='واش نقدر نزيد فالكرا؟')
    assert act(api, rev, again['id'], act='duplicate', of=first['id']).status_code == 200
    assert Contribution.objects.get(pk=again['id']).duplicate_of_id == first['id']
    assert len(api.get('/api/discussion/questions/').json()['questions']) == 1
    assert Notice.objects.filter(kind='duplicate', contribution_id=first['id']).exists()


def test_the_worst_comes_first_and_a_takedown_needs_no_account(api, writer, rev):
    mild = contribute(api, writer, body='ملاحظة أولى')
    worst = contribute(api, writer, kind='post', body='تجربة')
    for name in ('r1', 'r2'):
        signed_in(api, make_user(name)).post(f'/api/discussion/contributions/{mild["id"]}/report/',
                                             {'reason': 'off_topic'}, format='json')
    api.force_authenticate(None)
    r = api.post(f'/api/discussion/contributions/{worst["id"]}/takedown/',
                 {'details': 'هذه قصتي وفيها ما يعرّف بي', 'contact': 'tel: 06…'}, format='json')
    assert r.status_code == 201 and Report.objects.get(takedown=True).reporter is None
    queue = signed_in(api, rev).get('/api/discussion/review/', {'tab': 'reported'}).json()['items']
    assert [i['id'] for i in queue] == [worst['id'], mild['id']]
    assert queue[0]['reports']['takedowns'][0]['contact'] == 'tel: 06…'


def test_three_proven_reports_of_exposing_hide_it_until_a_reviewer_decides(api, writer, rev, reader):
    c = contribute(api, writer, kind='post', body='تجربة')
    for name in ('p1', 'p2', 'p3'):
        signed_in(api, make_user(name)).post(f'/api/discussion/contributions/{c["id"]}/report/',
                                             {'reason': 'exposing'}, format='json')
    assert Contribution.objects.get(pk=c['id']).hidden_at is not None
    assert feed(signed_in(api, reader))['posts'] == []
    seen = feed(signed_in(api, rev))['posts'][0]
    assert seen['hidden'] is True
    act(api, rev, c['id'], act='keep')
    assert Contribution.objects.get(pk=c['id']).published


def test_a_reviewer_sees_held_ones_in_place_with_the_suggested_rule(api, writer, rev, reader):
    q = contribute(api, writer, body='سؤال')
    contribute(api, make_user('salma'), body='عيطو 0600000000', parent=q['id'])
    as_reviewer = post_of(signed_in(api, rev), q['id'])
    assert as_reviewer['review']['can'] is True
    held = as_reviewer['post']['replies'][0]
    assert held['held'] is True and held['suggested'] == 'soliciting'
    as_reader = post_of(signed_in(api, reader), q['id'])
    assert as_reader['review']['can'] is False and as_reader['post']['replies'] == []


def test_staff_appoint_a_topics_moderators_from_the_review_page(api, staff, writer, reader):
    api.post('/api/discussion/review/reviewers/', {'username': 'hamid', 'places': 'housing,work'}, format='json')
    signed_in(api, staff)
    assert api.post('/api/discussion/review/reviewers/', {'username': 'hamid', 'places': 'housing,work'},
                    format='json').status_code == 201
    assert api.post('/api/discussion/review/reviewers/', {'username': 'hamid', 'places': 'nowhere'},
                    format='json').status_code == 404
    listed = api.get('/api/discussion/review/reviewers/').json()['reviewers']
    assert [(r['username'], r['text_paths']) for r in listed] == [('hamid', ['/talk/housing', '/talk/work'])]
    assert signed_in(api, writer).get('/api/discussion/review/reviewers/').status_code == 403


def test_reviewers_hear_once_a_day_about_what_waited_twelve_hours(api, rev, lease):
    c = contribute(api, make_user('salma'), body='سؤال')
    Contribution.objects.filter(pk=c['id']).update(held_at=timezone.now() - timedelta(hours=13))
    call_command('review_digest', stdout=io.StringIO())
    call_command('review_digest', stdout=io.StringIO())
    to_rev = [m for m in mail.outbox if m.to == ['rev@example.org']]
    assert len(to_rev) == 1 and to_rev[0].subject.strip('\u202b\u202c') == 'مساهمات تنتظر مراجعتك في «قانون المغرب»'
    assert signed_in(api, rev).get('/api/discussion/me/unseen/').json()['review'] == 1


# ── readers ───────────────────────────────────────────────────────────────

def test_unanswered_questions_wait_above_the_list(api, writer):
    contribute(api, writer, kind='post', body='شرح')
    q = contribute(api, writer, body='سؤال لم يجب عنه أحد')
    answered = contribute(api, writer, body='سؤال مجاب')
    contribute(api, settle(make_user('nadia2'), None), kind='explanation', body='جواب', parent=answered['id'])
    waiting = feed(api, 'open')['posts']
    assert [w['id'] for w in waiting] == [q['id']]


def test_a_topics_new_posts_come_as_one_line(api, writer, reader):
    contribute(api, writer, body='سؤال')
    Follow.objects.create(user=reader, path=PATH)
    for name in ('a1', 'a2', 'a3'):
        contribute(api, settle(make_user(name), None), kind='post', body=f'ملاحظة من {name}')
    mine = signed_in(api, reader).get('/api/discussion/me/').json()['notices']
    assert [(n['kind'], n['count']) for n in mine] == [('new', 3)]
    assert api.get('/api/discussion/me/unseen/').json()['unseen'] == 3


def test_every_letter_can_be_stopped_without_signing_in(api, writer):
    q = contribute(api, writer, body='سؤال')
    contribute(api, settle(make_user('nadia2'), None), kind='explanation', body='جواب', parent=q['id'])
    call_command('send_notice_letters')
    letter = next(m for m in mail.outbox if m.to == ['nadia@example.org'])
    assert letter.extra_headers['List-Unsubscribe-Post'] == 'List-Unsubscribe=One-Click'
    at = f"{PATH}/{q['id']}"
    token = letters.stop_token(writer, at)
    api.force_authenticate(None)
    assert api.get('/api/discussion/letters/stop/', {'t': token}).json()['path'] == at
    api.post('/api/discussion/letters/stop/', {'t': token, 'scope': 'path'}, format='json')
    assert not Follow.objects.filter(user=writer, path=at).exists()
    api.post(f'/api/discussion/letters/stop/?t={token}&scope=all', 'List-Unsubscribe=One-Click',
             content_type='application/x-www-form-urlencoded')
    writer.refresh_from_db()
    assert writer.email_notices is False
    assert api.post('/api/discussion/letters/stop/', {'t': 'forged', 'scope': 'all'}, format='json').status_code == 400


def test_a_writer_hears_when_held_words_go_live(api, rev, lease):
    c = contribute(api, make_user('salma'), body='سؤال، رقمي 0600000000')
    act(api, rev, c['id'], act='approve')
    call_command('send_notice_letters')
    assert [m.subject.strip('\u202b\u202c') for m in mail.outbox if m.to == ['salma@example.org']] == ['نُشرت مساهمتك في «قانون المغرب»']


def test_a_reviewer_covers_part_of_a_picture(api, rev, lease):
    author = settle(make_user('khadija'), lease)
    pic = signed_in(api, author).post('/api/discussion/pictures/', {'picture': picture_file()}, format='multipart')
    c = contribute(api, author, kind='post', body='عقد', pictures=[pic.json()['id']])
    r = signed_in(api, rev).post(f'/api/discussion/review/contributions/{c["id"]}/pictures/{pic.json()["id"]}/',
                                 {'picture': picture_file()}, format='multipart')
    assert r.status_code == 200
    row = Contribution.objects.get(pk=c['id'])
    assert row.pictures.count() == 1 and row.pictures.get().pk != pic.json()['id']
    assert Picture.objects.get(pk=pic.json()['id']).replaced_by_id == row.pictures.get().pk
