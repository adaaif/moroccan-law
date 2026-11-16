"""What readers are given of the explanations: a text's own summary on its page, an article's kept while its text has no
version, an address's page for a text, a register nobody checked shown to its author alone, fifty states of history a
register, «جديد يهمك» over its last 183 days, «مفيد» once a person, and the reading page's built-in words."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.corpus.models import Text, Version
from apps.discussion.services import review
from apps.discussion.tests.conftest import ARTICLE as PATH, lease, make_user, uploads  # noqa: F401  (fixtures)
from apps.explain.models import Explanation, Helpful, Revision
from apps.explain.services import explanations
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'
FIRST = 'لا تتجاوز الزيادة 8% للسكن.'


@pytest.fixture
def people(lease):
    staff = make_user('staff', staff=True)
    reviewer = make_user('salma')
    review.appoint(staff, reviewer, [TEXT])
    return {'staff': staff, 'reviewer': reviewer, 'writer': make_user('nadia'), 'reader': make_user('hamid')}


def test_a_texts_own_summary_is_on_its_page_and_its_explanation_page(people):
    explanations.save(people['reviewer'], TEXT, 'ar', 'ينظم كراء السكن.', headline='كراء السكن')
    today = timezone.localdate()
    assert explanations.bundle(TEXT) == {'articles': {}, 'text': {'ar': {
        'register': 'ar', 'headline': 'كراء السكن', 'body': 'ينظم كراء السكن.', 'sources': [], 'checked_on': today,
        'helpful': 0, 'outdated': False, 'editors': 1}}}
    page = explanations.detail(TEXT, people['reader'])
    assert (page['kind'], page['text_path'], page['registers']['ar']['body']) == ('text', TEXT, 'ينظم كراء السكن.')


def test_an_articles_explanation_stays_while_its_text_has_no_version(people, lease, django_assert_num_queries):
    # A reload deletes a text's versions and makes them again: the explanation, keyed by its address, waits there.
    explanations.save(people['reviewer'], PATH, 'ar', FIRST)
    Version.objects.filter(text=lease).delete()
    with django_assert_num_queries(4):        # the explanations, their editors, the text, its versions: no articles
        shown = explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']
    assert (shown['body'], shown['outdated']) == (FIRST, False)


def test_a_register_nobody_checked_is_its_authors_alone(people):
    explanations.save(people['writer'], PATH, 'ar', FIRST)
    for who in (None, people['reader']):
        assert explanations.detail(PATH, who)['registers'] == {}
    mine = explanations.detail(PATH, people['writer'])['registers']['ar']
    assert (mine['waiting'], mine['body'], mine['checked_on'], mine['shown_id']) == (True, FIRST, None, None)


def test_a_registers_history_is_its_fifty_newest_states(people):
    explanations.save(people['writer'], PATH, 'ar', FIRST)
    e = Explanation.objects.get()
    Revision.objects.bulk_create([Revision(explanation=e, author=people['writer'], body=f'صيغة {n}') for n in range(50)])
    newest = list(Revision.objects.filter(explanation=e).values_list('pk', flat=True)[:50])
    history = explanations.detail(PATH, people['reviewer'])['registers']['ar']['history']
    assert [h['id'] for h in history] == newest and len(newest) == 50
    assert Revision.objects.filter(explanation=e).count() == 51


def test_new_for_you_keeps_the_texts_of_its_last_183_days(people):
    today = timezone.localdate()
    for n, issue in (('1-26', today - timedelta(days=183)), ('2-26', today - timedelta(days=184)), ('3-26', None)):
        if issue:
            issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7000 + int(n[0]), date=issue)
        Text.objects.create(akn_uri=f'/akn/ma/act/loi/{n}', type='law', number=n, title_ar=f'قانون رقم {n}',
                            first_published_in=issue)
        explanations.save(people['staff'], f'/ma/loi/{n}', 'ar', 'شرح القانون.', headline=f'عنوان {n}')
    assert [(i['path'], i['headline'], i['text']['date']) for i in explanations.new_items()] == \
        [('/ma/loi/1-26', 'عنوان 1-26', today - timedelta(days=183))]


def test_helpful_twice_is_one_vote(people):
    explanations.save(people['reviewer'], PATH, 'ar', FIRST)
    for _ in range(2):
        assert explanations.helpful(people['reader'], PATH, 'ar', True).helpful_count == 1
    assert Helpful.objects.count() == 1


def test_a_built_in_word_of_the_reading_page_has_its_page_and_no_meaning_yet(api):
    assert api.get('/api/explain/words/bo/').json() == {
        'concept': {'slug': 'bo', 'term': None, 'search': '', 'topic': '', 'built_in': True}, 'registers': {}}
