"""What writing and reviewing an explanation refuse, each in the one error shape: a field past its column, too many
sources, an address that is none of an article, a text or a word, a check with nothing waiting, a state that is not
there, one's own, one already removed, a keep with no report, a report's unknown reason; the same words twice write
nothing; who sees what waits; and the reviewers' and readers' doors that answer with the page."""
import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Action, Notice
from apps.discussion.services import review
from apps.discussion.tests.conftest import ARTICLE as PATH, lease, make_user, signed_in, uploads  # noqa: F401  (fixtures)
from apps.explain.models import BODY_MAX, HEADLINE_MAX, NOTE_MAX, Explanation, Report, Revision
from apps.explain.services import explanations

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'
FIRST = 'لا تتجاوز الزيادة 8% للسكن.'


@pytest.fixture
def people(lease):
    staff = make_user('staff', staff=True)
    reviewer = make_user('salma')
    review.appoint(staff, reviewer, [TEXT])
    return {'staff': staff, 'reviewer': reviewer, 'writer': make_user('nadia'), 'reader': make_user('hamid')}


@pytest.fixture
def checked(people):
    explanations.save(people['writer'], PATH, 'ar', FIRST)
    explanations.check(people['reviewer'], PATH, 'ar')
    return Revision.objects.get()


def refused(call) -> tuple:
    with pytest.raises(Refused) as no:
        call()
    return no.value.field, no.value.code, no.value.status


@pytest.mark.parametrize('field, most', [('body', BODY_MAX), ('headline', HEADLINE_MAX), ('note', NOTE_MAX)])
def test_a_field_is_taken_to_its_column_and_refused_one_letter_past_it(people, field, most):
    def write(n):
        words = {'body': FIRST, field: 'ب' * n}
        return explanations.save(people['writer'], TEXT, 'ar', words.pop('body'), **words)
    write(most)
    assert getattr(Revision.objects.get(), field) == 'ب' * most
    assert refused(lambda: write(most + 1)) == (field, 'too_long', 400)
    assert Revision.objects.count() == 1


def test_thirteen_sources_are_too_many_and_an_address_or_a_word_of_nothing_is_not_found(people):
    many = [f'{TEXT}/art_{n}' for n in range(13)]
    assert refused(lambda: explanations.save(people['writer'], PATH, 'ar', FIRST, sources=many)) == \
        ('sources', 'too_many', 400)
    for nothing in ('/elsewhere', '/words/nothing'):
        assert refused(lambda: explanations.save(people['writer'], nothing, 'ar', FIRST)) == ('path', 'not_found', 404)  # noqa: B023
    assert not Explanation.objects.exists()
    explanations.save(people['writer'], '/words/rent', 'ar', 'مبلغ الكراء.')
    assert list(Explanation.objects.values_list('path', flat=True)) == ['/words/rent']


def test_only_the_same_words_headline_and_sources_again_write_no_state(people, checked):
    e = explanations.save(people['writer'], PATH, 'ar', f'  {FIRST} ')
    assert e.pending is None and Revision.objects.count() == 1
    # The same words under another headline, then with other sources, are new states; each again is none.
    for headline, sources, states in (('', [], 1), ('الزيادة', [], 2), ('الزيادة', [], 2),
                                      ('الزيادة', [f'{TEXT}/art_33'], 3), ('الزيادة', [f'{TEXT}/art_33'], 3)):
        explanations.save(people['writer'], PATH, 'ar', FIRST, headline=headline, sources=sources)
        assert Revision.objects.count() == states, (headline, sources)
    assert (Explanation.objects.get().pending.headline, Explanation.objects.get().pending.sources) == \
        ('الزيادة', [f'{TEXT}/art_33'])
    explanations.save(people['writer'], PATH, 'ar', 'صيغة ثانية.')
    explanations.save(people['writer'], PATH, 'ar', 'صيغة ثانية.')
    assert Revision.objects.count() == 4 and Explanation.objects.get().pending.body == 'صيغة ثانية.'


def test_a_check_with_nothing_waiting_is_a_conflict(people, checked):
    assert refused(lambda: explanations.check(people['staff'], PATH, 'ar')) == ('review', 'nothing_waiting', 409)


def test_a_reviewer_acts_only_on_a_state_that_is_there_and_not_their_own(people, checked):
    for pk in ('x', None, checked.pk + 99):
        assert refused(lambda: explanations.remove(people['reviewer'], pk, 'privacy')) == ('revision', 'not_found', 404)  # noqa: B023
        assert refused(lambda: explanations.keep(people['reviewer'], pk)) == ('revision', 'not_found', 404)  # noqa: B023
    assert refused(lambda: explanations.remove(people['writer'], checked.pk, 'privacy')) == \
        ('review', 'not_reviewer', 403)
    explanations.save(people['reviewer'], PATH, 'ar', 'صيغة المراجعة.')
    own = Revision.objects.get(author=people['reviewer'])
    assert refused(lambda: explanations.remove(people['reviewer'], own.pk, 'privacy')) == ('review', 'own', 403)
    explanations.remove(people['staff'], own.pk, 'privacy')
    assert refused(lambda: explanations.remove(people['staff'], own.pk, 'respect')) == ('review', 'nothing_waiting', 409)
    assert Revision.objects.get(pk=own.pk).removed_rule == 'privacy'
    # A state nobody reported is not kept: there is nothing to decide.
    assert refused(lambda: explanations.keep(people['reviewer'], checked.pk)) == ('review', 'nothing_waiting', 409)
    assert not Action.objects.filter(verb=Action.Verb.KEEP).exists()


def test_a_report_names_one_of_the_discussions_reasons(people, checked):
    assert refused(lambda: explanations.report(people['reader'], checked.pk, reason='boring')) == \
        ('reason', 'invalid', 400)
    assert not Report.objects.exists()


@pytest.mark.parametrize('gone', ['deleted', 'erased'])
def test_an_author_whose_account_is_gone_is_told_nothing(people, gone):
    explanations.save(people['writer'], PATH, 'ar', FIRST)
    if gone == 'deleted':
        type(people['writer']).objects.filter(pk=people['writer'].pk).update(deleted_at=timezone.now())
    else:
        people['writer'].delete()
    explanations.check(people['reviewer'], PATH, 'ar')
    assert Explanation.objects.get().reviewed_by == people['reviewer']
    assert not Notice.objects.exists()


@pytest.mark.parametrize('who', [None, 'anonymous', 'reader'])
def test_what_waits_is_nobodys_but_a_reviewers(people, who):
    explanations.save(people['writer'], PATH, 'ar', FIRST)
    user = {None: None, 'anonymous': AnonymousUser(), 'reader': people['reader']}[who]
    assert explanations.waiting_count(user) == 0
    assert refused(lambda: explanations.waiting(user)) == ('review', 'not_reviewer', 403)


def test_a_reviewer_of_everything_sees_what_waits_on_every_text(api, people):
    everywhere = make_user('omar')
    review.appoint(people['staff'], everywhere, everywhere=True)
    explanations.save(people['writer'], PATH, 'ar', FIRST)
    items = signed_in(api, everywhere).get('/api/explain/waiting/').json()['items']
    assert [(i['path'], i['pending'], i['kind']) for i in items] == [(PATH, True, 'article')]
    assert explanations.waiting_count(everywhere) == 1


def test_the_check_keep_remove_and_helpful_doors_act_on_what_they_are_sent(api, people, checked):
    # The Darija register, not the doors' default: each door reads the register it is sent.
    explanations.save(people['writer'], PATH, 'darija', 'الزيادة ما تفوتش 8%.')
    page = signed_in(api, people['reviewer']).post('/api/explain/check/', {'path': PATH, 'register': 'darija'},
                                                    format='json').json()
    assert (page['registers']['darija']['body'], page['registers']['darija']['pending']) == ('الزيادة ما تفوتش 8%.', None)
    shown = Revision.objects.get(body='الزيادة ما تفوتش 8%.')
    explanations.report(people['reader'], shown.pk, reason='off_topic')
    kept = api.post('/api/explain/act/', {'revision': shown.pk, 'act': 'keep', 'note': 'قرأته، لا خطأ فيه'}, format='json')
    assert kept.status_code == 200 and kept.json()['registers']['darija']['history'][0]['reports'] == 0
    assert Report.objects.get().status == 'reviewed'
    assert list(Action.objects.filter(verb=Action.Verb.KEEP).values_list('note', flat=True)) == ['قرأته، لا خطأ فيه']
    # Its only report is decided: keeping it again has nothing to decide, and writes no second act.
    assert refused(lambda: explanations.keep(people['reviewer'], shown.pk)) == ('review', 'nothing_waiting', 409)
    assert Action.objects.filter(verb=Action.Verb.KEEP).count() == 1
    reader = signed_in(api, people['reader'])
    assert reader.post('/api/explain/helpful/', {'path': PATH, 'register': 'darija'}, format='json').json() == \
        {'helpful': 1, 'voted': True}
    assert dict(Explanation.objects.values_list('register', 'helpful_count')) == {'ar': 0, 'darija': 1}
    assert reader.delete('/api/explain/helpful/', {'path': PATH, 'register': 'darija'}, format='json').json() == \
        {'helpful': 0, 'voted': False}
    assert Explanation.objects.get(register='darija').helpful_count == 0
    removed = signed_in(api, people['reviewer']).post('/api/explain/act/', {
        'revision': shown.pk, 'act': 'remove', 'rule': 'respect', 'note': 'كلمة جارحة'}, format='json')
    assert removed.status_code == 200 and sorted(removed.json()['registers']) == ['ar']     # the Darija one is off the page
    assert Revision.objects.get(pk=shown.pk).removed_rule == 'respect'
    assert list(Action.objects.filter(verb=Action.Verb.REMOVE).values_list('rule', 'note')) == [('respect', 'كلمة جارحة')]
