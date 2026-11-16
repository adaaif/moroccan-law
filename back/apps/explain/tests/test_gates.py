"""«باختصار» behind the discussion's own gates: its fixed patterns and its check on the headline, the words and the
note; a waiting edit and every state nobody checked for its author and the reviewers only; the last checked words kept
on the law's page while an edit waits; reports, and a reviewer's removal under a rule; nobody decides about their own
words."""
import json

import pytest

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Action, Check, Notice
from apps.discussion.services import review
from apps.discussion.tests.conftest import ARTICLE as PATH, checking, lease, make_user, signed_in, uploads  # noqa: F401
from apps.explain.models import Explanation, Report, Revision
from apps.explain.services import explanations

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'
FIRST = 'لا تتجاوز الزيادة 8% للسكن.'
ADVERT = 'للاستشارة اتصلوا بالأستاذ على 0600000000'


@pytest.fixture
def people(lease):
    staff = make_user('staff', staff=True)
    reviewer, second = make_user('salma'), make_user('yassine')
    review.appoint(staff, reviewer, [TEXT])
    review.appoint(staff, second, [TEXT])
    return {'staff': staff, 'reviewer': reviewer, 'second': second, 'writer': make_user('nadia'),
            'reader': make_user('hamid'), 'new': make_user('karim', days=1)}


@pytest.fixture
def checked(people):
    explanations.save(people['writer'], PATH, 'ar', FIRST)
    explanations.check(people['reviewer'], PATH, 'ar')
    return Explanation.objects.get(path=PATH)


def page(api, user=None) -> dict:
    api.force_authenticate(user)
    return api.get('/api/explain/at/', {'path': PATH}).json()


def test_a_phone_number_in_the_note_waits_and_never_reaches_readers(api, people, checked):
    explanations.save(people['writer'], PATH, 'ar', f'{FIRST} وللمحل المهني 10%.', note=ADVERT)
    r = Revision.objects.get(explanation=checked, note=ADVERT)
    assert r.held_reasons == ['phone'] and Explanation.objects.get(pk=checked.pk).pending_id == r.pk
    # The law's page keeps the checked words; nobody but its author and the reviewers reads the waiting one.
    assert explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']['body'] == FIRST
    for who in (None, people['reader']):
        shown = page(api, who)
        assert ADVERT not in json.dumps(shown, ensure_ascii=False)
        assert shown['registers']['ar']['body'] == FIRST and shown['registers']['ar']['pending'] is None
        assert [h['state'] for h in shown['registers']['ar']['history']] == ['checked']
    mine = page(api, people['writer'])['registers']['ar']
    assert mine['pending']['note'] == ADVERT and mine['pending']['held_reasons'] == ['phone']
    desk = page(api, people['reviewer'])
    assert desk['can_review'] and desk['registers']['ar']['pending']['held_reasons'] == ['phone']
    assert [h['state'] for h in desk['registers']['ar']['history']] == ['waiting', 'checked']


def test_the_headline_is_read_by_the_patterns_too(people):
    explanations.save(people['writer'], TEXT, 'ar', 'يحدد هذا القانون علاقة المكري بالمكتري.', headline=ADVERT)
    e = Explanation.objects.get(path=TEXT)
    assert e.reviewed_at is None and e.pending.held_reasons == ['phone']
    assert explanations.bundle(TEXT)['text'] == {}


def test_the_check_reads_what_no_pattern_held_and_says_what_it_found(people, checked, checking):
    explanations.save(people['writer'], PATH, 'ar', 'شرح عادي [hold:respect]', note='صيغة أوضح', consent=True)
    assert Explanation.objects.get(pk=checked.pk).pending.held_reasons == ['check_respect']
    [sent] = checking.sent
    assert 'صيغة أوضح' in sent and '«باختصار»' in sent and 'nadia' not in sent
    assert Check.objects.filter(user=people['writer']).count() == 1
    # A pattern holds first: no call.
    explanations.save(people['writer'], PATH, 'ar', f'شرح آخر {ADVERT}')
    assert len(checking.sent) == 1


def test_the_first_state_asks_for_the_agreement_to_the_check(people, checking):
    with pytest.raises(Refused) as no:
        explanations.save(people['writer'], PATH, 'ar', FIRST)
    assert (no.value.field, no.value.code) == ('consent', 'required')
    explanations.save(people['writer'], PATH, 'ar', FIRST, consent=True)
    people['writer'].refresh_from_db()
    assert people['writer'].check_consent_at is not None


def test_a_reviewer_whose_words_were_held_waits_for_another_reviewer(people, checked):
    explanations.save(people['reviewer'], PATH, 'ar', f'{FIRST} {ADVERT}')
    e = Explanation.objects.get(pk=checked.pk)
    assert e.body == FIRST and e.pending is not None
    with pytest.raises(Refused) as own:
        explanations.check(people['reviewer'], PATH, 'ar')
    assert (own.value.field, own.value.code) == ('review', 'own')
    explanations.check(people['second'], PATH, 'ar')
    assert Explanation.objects.get(pk=checked.pk).body == f'{FIRST} {ADVERT}'


def test_a_reader_reports_what_readers_see_and_a_reviewer_removes_it(api, people, checked):
    explanations.save(people['writer'], PATH, 'ar', 'صيغة ثانية بلا خطأ.')
    explanations.check(people['second'], PATH, 'ar')
    second = Revision.objects.get(explanation=checked, body='صيغة ثانية بلا خطأ.')
    shown = page(api, people['reader'])['registers']['ar']
    assert shown['shown_id'] == second.pk and page(api, people['reader'])['can_report']
    out = signed_in(api, people['reader']).post('/api/explain/report/', {'revision': second.pk, 'reason': 'exposing'},
                                                 format='json')
    assert out.status_code == 201
    again = api.post('/api/explain/report/', {'revision': second.pk, 'reason': 'exposing'}, format='json')
    assert again.json() == {'errors': [{'field': 'report', 'code': 'already'}]}
    own = signed_in(api, people['writer']).post('/api/explain/report/', {'revision': second.pk, 'reason': 'abuse'},
                                                format='json')
    assert own.json() == {'errors': [{'field': 'report', 'code': 'own'}]}
    # A state nobody checked cannot be reported: readers never saw it.
    explanations.save(people['writer'], PATH, 'ar', 'صيغة ثالثة تنتظر.')
    waiting = Explanation.objects.get(pk=checked.pk).pending
    assert signed_in(api, people['reader']).post('/api/explain/report/', {'revision': waiting.pk, 'reason': 'abuse'},
                                                 format='json').status_code == 404
    # The reviewers see it waiting, with its report.
    assert [(i['path'], i['pending'], i['reports']) for i in explanations.waiting(people['reviewer'])] == [(PATH, True, 1)]
    assert signed_in(api, people['reviewer']).get('/api/discussion/me/unseen/').json()['review'] == 1
    # The author cannot decide about their own words; a reviewer removes the reported state under a rule.
    with pytest.raises(Refused):
        explanations.remove(people['writer'], second.pk, 'privacy')
    with pytest.raises(Refused) as no_rule:
        explanations.remove(people['reviewer'], second.pk, '')
    assert no_rule.value.field == 'rule'
    removed = signed_in(api, people['reviewer']).post('/api/explain/act/', {'revision': second.pk, 'act': 'remove',
                                                                            'rule': 'privacy'}, format='json')
    assert removed.status_code == 200
    # Readers go back to the state checked before it; its author is told; the ledger keeps the act; the report is closed.
    assert explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']['body'] == FIRST
    assert 'صيغة ثانية' not in json.dumps(page(api, people['reader']), ensure_ascii=False)
    assert Notice.objects.filter(user=people['writer'], kind=Notice.Kind.REMOVED, detail='privacy').exists()
    assert Action.objects.filter(verb=Action.Verb.REMOVE, path=f'/explain{PATH}', rule='privacy').exists()
    assert Report.objects.get().status == 'acted'
    # The edit that waits is removed too, and nothing waits any more.
    explanations.remove(people['reviewer'], waiting.pk, 'on_topic')
    assert Explanation.objects.get(pk=checked.pk).pending is None and explanations.waiting(people['reviewer']) == []


def test_removing_the_only_checked_state_takes_it_off_the_page(people, checked):
    first = Revision.objects.get(explanation=checked)
    explanations.remove(people['second'], first.pk, 'soliciting')
    assert explanations.bundle(TEXT)['articles'] == {} and Explanation.objects.get(pk=checked.pk).body == ''


def test_a_kept_report_is_closed(people, checked):
    first = Revision.objects.get(explanation=checked)
    explanations.report(people['reader'], first.pk, reason='off_topic')
    explanations.keep(people['second'], first.pk)
    assert Report.objects.get().status == 'reviewed' and explanations.waiting(people['second']) == []


def test_only_the_texts_reviewers_and_staff_see_what_waits(api, people, checked):
    other = make_user('omar')
    review.appoint(people['staff'], other, ['/talk/family'])
    with pytest.raises(Refused):
        explanations.waiting(people['reader'])
    assert explanations.waiting(other) == [] and explanations.waiting_count(other) == 0
    explanations.save(people['writer'], PATH, 'ar', 'صيغة تنتظر.')
    assert len(explanations.waiting(people['staff'])) == 1 and explanations.waiting_count(people['reviewer']) == 1
    assert signed_in(api, people['reader']).get('/api/explain/waiting/').status_code == 403
    assert 'صيغة تنتظر' not in json.dumps(page(api, other), ensure_ascii=False)


def test_a_newcomers_five_a_day_count_explanations_too(people):
    for i in range(5):
        explanations.save(people['new'], PATH, 'ar', f'صيغة {i}')
    with pytest.raises(Refused) as limit:
        explanations.save(people['new'], PATH, 'ar', 'صيغة سادسة')
    assert (limit.value.field, limit.value.code) == ('account', 'day_limit')


def test_the_page_costs_the_same_whatever_its_history(api, people, checked, django_assert_max_num_queries):
    for i in range(30):
        explanations.save(people['writer'], PATH, 'ar', f'صيغة {i}')
    api.force_authenticate(people['reviewer'])
    with django_assert_max_num_queries(16):
        assert api.get('/api/explain/at/', {'path': PATH}).status_code == 200


def test_a_removed_states_words_are_erased_after_ninety_days(people, checked):
    import io
    from datetime import timedelta

    from django.core.management import call_command
    from django.utils import timezone

    explanations.save(people['writer'], PATH, 'ar', f'صيغة {ADVERT}', note='ملاحظة')
    r = Explanation.objects.get(pk=checked.pk).pending
    explanations.remove(people['reviewer'], r.pk, 'soliciting')
    call_command('keep_promises', stdout=io.StringIO())
    r.refresh_from_db()
    assert r.body.startswith('صيغة')                         # kept for the reviewers
    Revision.objects.filter(pk=r.pk).update(removed_at=timezone.now() - timedelta(days=91))
    call_command('keep_promises', stdout=io.StringIO())
    r.refresh_from_db()
    assert (r.body, r.note, r.removed_rule) == ('', '', 'soliciting')


def test_the_explanations_already_written_are_read_in_the_new_shape(people):
    """The migration: a checked explanation shows the newest state with its words; an unchecked one waits on its newest."""
    import importlib

    from django.apps import apps
    from django.utils import timezone

    shown = Explanation.objects.create(path=PATH, register='ar', body=FIRST, reviewed_at=timezone.now(),
                                       reviewed_by=people['staff'])
    old = Revision.objects.create(explanation=shown, author=people['writer'], body='صيغة أقدم')
    same = Revision.objects.create(explanation=shown, author=people['writer'], body=FIRST)
    waiting = Explanation.objects.create(path=TEXT, register='ar', body='ينتظر')
    _first, last = (Revision.objects.create(explanation=waiting, author=people['writer'], body=b) for b in ('أ', 'ينتظر'))
    importlib.import_module('apps.explain.migrations.0003_checked_states').forward(apps, None)
    same.refresh_from_db(), old.refresh_from_db()
    assert same.checked_by == people['staff'] and same.checked_at == shown.reviewed_at and old.checked_at is None
    assert Explanation.objects.get(pk=waiting.pk).pending_id == last.pk
    assert Explanation.objects.get(pk=shown.pk).pending_id is None
