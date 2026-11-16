"""The work topic, counted (the work-counted review, 26 Oct 2026)."""
import pytest

from apps.topics.services import kit

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db


def _drafts(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()


def test_the_dismissal_band_says_the_answers_of_its_journey_steps_and_counts_from_its_day(settings):
    # E5: the band's three acts are the dismissal journey's answers (the decision, the receipt, the papers after); its
    # day is the journey's, which counts the 90 days from the decision.
    _drafts(settings)
    band = kit.hub('work')['urgent']
    steps = kit.load('work')['journeys']['dismissed']['steps']
    assert band['tone'] == 'ink' and band['to'] == 'journeys/dismissed' and band['tool'] == 'tools/end'
    assert band['acts'] == [steps[i]['answer'] for i in (2, 3, 7)]
    assert [s['delay']['days'] for s in steps if s.get('delay', {}).get('on_day')] == [90]


def test_every_work_step_is_answered_and_every_door_has_a_number_or_a_paper(settings):
    # E1, E10: forty answers in both languages; a door led by its number, or by the paper that decides it.
    _drafts(settings)
    content = kit.load('work')
    steps = [s for j in content['journeys'].values() for s in j['steps']]
    assert len(steps) == 40 and all(s['answer']['ar'] and s['answer']['fr'] for s in steps)
    doors = kit.hub('work')['events']
    assert all(d.get('mark') or d.get('icon') for d in doors)
    unpaid = next(d for d in doors if d['key'] == 'unpaid')
    assert unpaid['mark']['value'] == '17,92' and unpaid['mark']['by']['farm']['value'] == '97,44'


def test_the_last_change_is_the_newest_passed_entry_of_a_change_in_force(settings):
    # E9: with nothing dated ahead, the card says the last change in words; a bill or an announcement never counts.
    _drafts(settings)
    content = kit.load('work')
    last = kit.latest(content, today='2026-10-26')
    assert last['date'] <= '2026-10-26' and content['reform'][last['change']]['stage'] == 'in_force'
    assert kit.latest(content, today='2000-01-01') is None


def test_a_door_whose_words_say_more_of_the_question_comes_first(settings):
    # E16: «ما صرحش بيا فالضمان» opens the work's CNSS door before the consumer's warranty («الضمان»); «كونجي الولادة»
    # the work's maternity before the family's birth.
    _drafts(settings)
    assert kit.matching('المشغل ما صرحش بيا فالضمان')[0]['ref'] == 'journeys/not-declared'
    assert kit.matching('كونجي الولادة شحال')[0]['ref'] == 'journeys/maternity'
    assert kit.matching('licenciement abusif indemnité')[0]['ref'] == 'journeys/dismissed'
