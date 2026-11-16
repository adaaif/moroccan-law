"""The check before publishing (29 Oct 2026): a model reads each post and comment and answers publish,
return or hold, in codes; when it cannot answer, a person decides. The model here is the `checking` fixture's."""
from decimal import Decimal

import pytest

from apps.discussion.models import Check, Contribution
from apps.discussion.services import check, numbers, review
from apps.discussion.tests.conftest import PATH, TITLE, feed, make_user, settle, signed_in

pytestmark = pytest.mark.django_db


def post(api, **data):
    sent = {'path': PATH, 'kind': 'question', 'consent': True,
            **({} if data.get('parent') else {'title': TITLE}), **data}
    return api.post('/api/discussion/contributions/', sent, format='json')


def codes(r):
    return [(e['field'], e['code']) for e in r.json()['errors']]


def test_a_newcomers_first_post_goes_out_at_once_once_the_model_read_it(api, lease, checking, reader):
    newcomer = make_user('salma')
    r = post(signed_in(api, newcomer), body='مول الدار طلب مني نزيد 15% في الكراء. واش عندو الحق؟')
    assert r.status_code == 201 and r.json()['held'] is False
    assert [p['id'] for p in feed(signed_in(api, reader))['posts']] == [r.json()['id']]
    row = Check.objects.get()
    assert (row.outcome, row.contribution_id, row.model, row.prompt_version) == (
        'publish', r.json()['id'], 'claude-haiku-5-5', check.PROMPT_VERSION)
    assert row.cost_usd == Decimal('0.000130')   # 1,200 tokens in and 20 out at $0.10 and $0.50 a million


def test_the_first_post_asks_for_the_agreement_that_a_model_reads_it(api, writer, checking):
    api = signed_in(api, writer)
    r = post(api, consent=False, body='سؤال')
    assert r.status_code == 403 and codes(r) == [('consent', 'required')] and checking.sent == []
    assert api.get('/api/discussion/feed/', {'place': PATH}).json()['writing']['consent'] is False
    assert post(api, body='سؤال').status_code == 201
    writer.refresh_from_db()
    assert writer.check_consent_at is not None
    assert post(api, consent=False, body='سؤال ثان').status_code == 201


def test_the_model_reads_the_topic_the_title_the_words_and_the_post_above_never_the_author(api, writer, checking):
    q = post(signed_in(api, writer), title='الزيادة', body='واش يقدر يزيد؟').json()
    post(signed_in(api, settle(make_user('amine'), None)), parent=q['id'], body='لا قبل ثلاث سنين')
    first, second = checking.sent
    assert '<topic>السكن والكراء / Logement et location</topic>' in first and '<title>الزيادة</title>' in first
    assert '<post_above>الزيادة\nواش يقدر يزيد؟</post_above>' in second and '<words>لا قبل ثلاث سنين</words>' in second
    assert 'nadia' not in first + second and 'amine' not in second


def test_a_returned_post_goes_back_to_its_author_who_may_send_it_as_it_is(api, writer, checking, staff):
    api = signed_in(api, writer)
    r = post(api, body='جاري أحمد بنعلي ما خلصش الكرا [return:privacy]')
    assert r.status_code == 422 and codes(r) == [('check', 'privacy')]
    assert not Contribution.objects.filter(discussion__path=PATH).exists() and Check.objects.get().outcome == 'return'
    r = post(api, body='جاري أحمد بنعلي ما خلصش الكرا [return:privacy]', insist=True)
    assert r.status_code == 201 and r.json()['held'] is True and r.json()['held_reasons'] == ['check_privacy']
    card = signed_in(api, staff).get('/api/discussion/review/', {'tab': 'held'}).json()['items'][0]
    assert card['context']['suggested'] == 'privacy'


def test_a_held_post_waits_for_the_topics_moderator(api, writer, checking, staff, reader):
    mod = make_user('mod')
    review.appoint(staff, mod, [PATH])
    r = post(signed_in(api, writer), body='تهديد [hold:respect]')
    assert r.json()['held'] is True and r.json()['held_reasons'] == ['check_respect']
    assert feed(signed_in(api, reader))['posts'] == []
    signed_in(api, mod).post(f'/api/discussion/review/contributions/{r.json()["id"]}/', {'act': 'approve'},
                             format='json')
    assert Contribution.objects.get(pk=r.json()['id']).published


@pytest.mark.parametrize('words, failure', [('[boom]', 'error'), ('[refuse]', 'refusal')])
def test_when_the_check_cannot_answer_a_person_decides(api, writer, checking, words, failure):
    r = post(signed_in(api, writer), body=f'سؤال {words}')
    assert r.json()['held'] is True and r.json()['held_reasons'] == ['check_unavailable']
    assert (Check.objects.get().outcome, Check.objects.get().failure) == ('unavailable', failure)


def test_no_key_or_a_spent_budget_holds_too(api, writer, checking, settings):
    settings.ANTHROPIC_API_KEY = ''
    assert post(signed_in(api, writer), body='سؤال').json()['held_reasons'] == ['check_unavailable']
    settings.ANTHROPIC_API_KEY, settings.CHECK_BUDGET_USD = 'sk-ant-test', 0.0001
    Check.objects.create(outcome='publish', cost_usd=Decimal('0.0002'))
    assert post(api, body='سؤال آخر').json()['held_reasons'] == ['check_unavailable']
    assert Check.objects.filter(failure='budget').count() == 1 and len(checking.sent) == 0


def test_a_pattern_holds_before_any_model_reads_it(api, writer, checking):
    r = post(signed_in(api, writer), body='اتصلوا بي 0600000000')
    assert r.json()['held_reasons'] == ['phone'] and checking.sent == []


def test_an_edit_is_read_again(api, writer, checking):
    api = signed_in(api, writer)
    c = post(api, body='سؤال').json()
    r = api.patch(f'/api/discussion/contributions/{c["id"]}/', {'body': 'سؤال وفيه إشهار [return:soliciting]'},
                  format='json')
    assert r.status_code == 422 and codes(r) == [('check', 'soliciting')]
    r = api.patch(f'/api/discussion/contributions/{c["id"]}/', {'body': 'سؤال [hold:respect]'}, format='json')
    assert r.json()['held'] is True
    r = api.patch(f'/api/discussion/contributions/{c["id"]}/', {'body': 'سؤال مهذب'}, format='json')
    assert r.json()['held'] is False and len(checking.sent) == 4


def test_the_months_numbers_say_what_the_check_did_and_what_people_overturned(api, writer, checking, staff):
    held = post(signed_in(api, writer), body='[hold:respect]').json()
    post(api, body='سؤال')
    signed_in(api, staff).post(f'/api/discussion/review/contributions/{held["id"]}/', {'act': 'approve'},
                               format='json')
    from django.utils import timezone

    today = timezone.localdate()
    month = numbers.month(today.year, today.month)
    assert month['checks'] == {'publish': 1, 'return': 0, 'hold': 1, 'unavailable': 0} and month['overturned'] == 1


def test_without_the_check_the_patterns_alone_decide(api, lease, settings):
    settings.DISCUSSION_CHECK = 'pass'
    r = post(signed_in(api, make_user('salma')), consent=False, body='سؤال')
    assert r.status_code == 201 and r.json()['held'] is False and Check.objects.count() == 0


def test_the_markers_stand_in_for_the_model_while_developing_only(api, writer, settings):
    settings.DISCUSSION_CHECK, settings.DEBUG = 'markers', True
    r = post(signed_in(api, writer), body='[hold:respect]')
    assert r.json()['held_reasons'] == ['check_respect'] and Check.objects.get().model == 'markers'
    settings.DEBUG = False
    assert post(api, body='سؤال').json()['held_reasons'] == ['check_unavailable']
