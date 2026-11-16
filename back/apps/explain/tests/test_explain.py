"""The people's words beside the law (R8 of the for-everyone review): one shared explanation an address and a register,
every change kept, readers see it once a reviewer checked it, an article's says when the article changed, its sources
are addresses the site holds, and until an article has one, the discussion's most useful «شرح» stands in."""
import datetime

import pytest
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.corpus.models import Article, Text
from apps.discussion.models import Contribution, Discussion
from apps.discussion.services import review
from apps.discussion.tests.conftest import ARTICLE as PATH, lease, make_user, signed_in, uploads  # noqa: F401  (fixtures)
from apps.explain.models import Explanation
from apps.explain.services import explanations
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'


@pytest.fixture
def people(lease):
    staff = make_user('staff', staff=True)
    reviewer = make_user('salma')
    review.appoint(staff, reviewer, [TEXT])
    return {'staff': staff, 'reviewer': reviewer, 'writer': make_user('nadia'), 'new': make_user('karim', days=1)}


def test_readers_see_an_explanation_once_a_reviewer_checked_it(people):
    explanations.save(people['writer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن.', sources=[f'{TEXT}/art_33'])
    assert explanations.bundle(TEXT)['articles'] == {}
    explanations.check(people['reviewer'], PATH, 'ar')
    shown = explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']
    assert shown['body'] == 'لا تتجاوز الزيادة 8% للسكن.' and shown['checked_on'] == timezone.localdate()
    # Someone else's change waits for a reviewer, and readers keep the checked words meanwhile; every state is kept.
    explanations.save(people['writer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن و10% للمحل المهني.')
    assert explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']['body'] == 'لا تتجاوز الزيادة 8% للسكن.'
    assert Explanation.objects.get(path=PATH).revisions.count() == 2
    # A reviewer of the text who writes checks at once.
    explanations.save(people['reviewer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن و10% للمحل المهني (المادة 34).')
    shown = explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']
    assert shown['body'].endswith('(المادة 34).') and shown['editors'] == 2


def test_only_a_reviewer_of_the_text_or_staff_checks(people):
    explanations.save(people['writer'], PATH, 'darija', 'الزيادة ما تفوتش 8%.')
    with pytest.raises(Refused) as no:
        explanations.check(people['writer'], PATH, 'darija')
    assert (no.value.field, no.value.code) == ('review', 'not_reviewer')
    explanations.check(people['staff'], PATH, 'darija')


def test_writing_needs_the_discussion_open_and_a_proven_email(people, settings):
    with pytest.raises(Refused) as unproven:
        explanations.save(make_user('omar', proven=False), PATH, 'ar', 'شرح')
    assert unproven.value.code == 'not_proven'
    settings.DISCUSSION_OPEN = False
    with pytest.raises(Refused) as closed:
        explanations.save(people['writer'], PATH, 'ar', 'شرح')
    assert closed.value.code == 'closed'


def test_sources_are_addresses_the_corpus_holds(people):
    with pytest.raises(Refused) as no:
        explanations.save(people['writer'], PATH, 'ar', 'شرح', sources=['/ma/loi/2013/67-12/art_99'])
    assert (no.value.field, no.value.code) == ('sources', 'not_found')
    with pytest.raises(Refused):
        explanations.save(people['writer'], '/ma/loi/2013/67-12/art_99', 'ar', 'شرح')


def test_an_articles_explanation_says_when_the_article_changed(people):
    explanations.save(people['reviewer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن.')
    assert explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']['outdated'] is False
    Article.objects.filter(eid='art_34').update(body='تحدد نسبة الزيادة في الوجيبة الكرائية في 5%.')
    assert explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']['outdated'] is True


def test_helpful_counts_only_from_proven_accounts_three_days_old(people):
    explanations.save(people['reviewer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن.')
    explanations.helpful(people['writer'], PATH, 'ar', True)
    explanations.helpful(people['new'], PATH, 'ar', True)
    assert Explanation.objects.get(path=PATH).helpful_count == 1
    explanations.helpful(people['writer'], PATH, 'ar', False)
    assert Explanation.objects.get(path=PATH).helpful_count == 0


def test_new_for_you_lists_recent_texts_explained_under_a_headline(people):
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7523, date=timezone.localdate() - datetime.timedelta(days=10))
    Text.objects.create(akn_uri='/akn/ma/act/loi/41-26', type='law', number='41-26', title_ar='قانون رقم 41.26',
                        first_published_in=issue, first_published_page=4200)
    explanations.save(people['staff'], '/ma/loi/41-26', 'ar', 'منحة استثنائية لمدة 12 شهرا.', headline='منحة استثنائية')
    assert [(i['path'], i['headline'], i['text']['page']) for i in explanations.new_items()] == \
        [('/ma/loi/41-26', 'منحة استثنائية', 4200)]
    # Its French beside it, one item a text (U11 of the Moroccan-design review).
    explanations.save(people['staff'], '/ma/loi/41-26', 'fr', 'Une aide exceptionnelle de 12 mois.', headline='Aide exceptionnelle')
    [item] = explanations.new_items()
    assert item['headline'] == 'منحة استثنائية' and item['registers']['fr']['headline'] == 'Aide exceptionnelle'


def test_the_api_reads_for_anyone_and_writes_for_a_signed_in_writer(api, people):
    assert api.get('/api/explain/text/', {'path': TEXT}).json() == {'text': {}, 'articles': {}}
    assert api.post('/api/explain/save/', {'path': PATH, 'register': 'ar', 'body': 'شرح'}, format='json').status_code == 401
    out = signed_in(api, people['reviewer']).post('/api/explain/save/', {'path': PATH, 'register': 'ar', 'body': 'شرح واضح'},
                                                  format='json')
    assert out.status_code == 201 and out.json()['registers']['ar']['waiting'] is False
    assert api.get('/api/explain/words/').json()['concepts'][0]['slug'] == 'nafaqa'
    assert api.get('/api/explain/words/rent/').json()['concept']['term']['ar'] == 'الوجيبة الكرائية'


def test_a_word_of_the_law_is_dotted_once_its_meaning_is_checked_and_carries_it(people, api):
    # HM35 of the hard-moment review: 58 words were dotted and none had a meaning; a tap left the article.
    from apps.corpus.models import Consolidation, Version
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/67-12', type='law', number='67-12', title_ar='قانون رقم 67.12')
    v = Version.objects.create(text=text, language='ar', valid_from=datetime.date(2013, 11, 28),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة 3', number='3', eid='art_3', body='بيان مبلغ الوجيبة الكرائية.')
    words = lambda: [m for m in api.get('/api/corpus/at/ma/loi/67-12/').json()['articles'][0]['marks'] if m['kind'] == 'word']
    assert words() == []
    explanations.save(people['staff'], '/words/rent', 'ar', 'مبلغ الكراء الذي يؤديه المكتري.')
    [word] = words()
    assert (word['slug'], word['means']) == ('rent', {'ar': 'مبلغ الكراء الذي يؤديه المكتري.'})


def test_the_week_puts_first_what_an_editor_told_and_lists_the_rest(people, api):
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7551, date=datetime.date(2026, 10, 12))
    for n, title in (('41-26', 'قانون رقم 41.26 بتغيير قانون الدعم الاجتماعي المباشر'), ('50-26', 'قانون رقم 50.26')):
        Text.objects.create(akn_uri=f'/akn/ma/act/loi/{n}', type='law', number=n, title_ar=title, first_published_in=issue,
                            first_published_page=7576)
    Text.objects.create(akn_uri='/akn/ma/act/annonce/1', type='other', title_ar='إعلان', first_published_in=issue,
                        bo_section='special')
    explanations.save(people['staff'], '/ma/loi/41-26', 'ar', 'منحة استثنائية لمدة 12 شهرا.', headline='منحة استثنائية')
    w = api.get('/api/explain/week/', {'day': '2026-10-14'}).json()
    assert (w['from'], w['to'], w['issues'][0]['special']) == ('2026-10-12', '2026-10-18', 1)
    assert [(x['path'], x['topic']['slug'], x['told']['ar']['headline']) for x in w['people']] == \
        [('/ma/loi/41-26', 'health', 'منحة استثنائية')]
    assert [x['path'] for x in w['rest']] == ['/ma/loi/50-26']
    assert api.get('/api/explain/week/', {'day': 'soon'}).json() == {'errors': [{'field': 'day', 'code': 'invalid'}]}


@pytest.mark.needs('fribidi')
def test_a_card_names_its_text_and_source_and_keeps_the_peoples_words_apart(people, api, settings, tmp_path):
    from io import BytesIO

    from PIL import Image

    from apps.explain.services import cards
    settings.CORPUS_DIR = tmp_path
    explanations.save(people['reviewer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن.')
    c = cards.content(path=PATH)
    assert (c['label'], c['name'], c['explained']['body']) == ('المادة 34', 'قانون الكراء', 'لا تتجاوز الزيادة 8% للسكن.')
    assert c['source'] == {'consolidated': False, 'words': 'الجريدة الرسمية 6208 · الصفحة 12'}
    got = api.get('/api/explain/card/', {'path': PATH, 'shape': 'story'})
    assert got['Content-Type'] == 'image/png' and Image.open(BytesIO(b''.join(got.streaming_content))).size == (1080, 1920)
    # The article changed since it was explained: the card shows the law alone, paragraph by paragraph, a number's
    # groups held together (HM14: art. 53's four tiers ran into one paragraph; «40 000» was drawn «000 40»).
    Article.objects.filter(eid='art_34').update(body='تحدد نسبة الزيادة كما يلي:\n- 5% إلى غاية 40 000 درهم؛\n- 8% ما زاد على ذلك.')
    c = cards.content(path=PATH)
    assert c['explained'] is None and c['body'] == 'تحدد نسبة الزيادة كما يلي:\n- 5% إلى غاية 40\u00a0000 درهم؛\n- 8% ما زاد على ذلك.'
    _img, pen, _ = cards._frame('post')
    assert pen.wrap(c['body'], cards._font('MarkaziText.ttf', 48, 500), 9) == [
        'تحدد نسبة الزيادة كما يلي:', '- 5% إلى غاية 40\u00a0000 درهم؛', '- 8% ما زاد على ذلك.']
    d = Discussion.objects.create(path=PATH, text_path=TEXT)
    q = Contribution.objects.create(discussion=d, author=people['new'], kind='question', body='واش يقدر يزيد 15%؟')
    a = Contribution.objects.create(discussion=d, author=people['writer'], kind='explanation', parent=q, body='لا.')
    assert (cards.content(answer=a.pk)['question'], cards.content(answer=a.pk)['link']) == ('واش يقدر يزيد 15%؟', f'/discussion{PATH}')
    assert api.get('/api/explain/card/', {'answer': q.pk}).status_code == 404
    assert api.get('/api/explain/card/', {'path': PATH, 'shape': 'square'}).json() == \
        {'errors': [{'field': 'shape', 'code': 'invalid'}]}


@pytest.mark.needs('fribidi')
def test_a_card_waits_while_the_site_draws_others_and_reads_what_it_can_hold(people, api, settings, tmp_path,
                                                                          monkeypatch):
    # OP15 of the open-source audit: drawn under the drawing limits (config/drawing.py), and a long article is no longer
    # wrapped whole at six sizes before it is cut.
    from apps.explain.services import cards
    from config.caching import counters
    settings.CORPUS_DIR = tmp_path
    settings.DRAWING_AT_ONCE = 1
    counters.add('drawing:place:0', 1, timeout=60)
    try:
        r = api.get('/api/explain/card/', {'path': PATH})
        assert r.status_code == 503 and r.json() == {'errors': [{'field': 'picture', 'code': 'busy'}]}
    finally:
        counters.delete('drawing:place:0')
    Article.objects.filter(eid='art_34').update(body='تحدد نسبة الزيادة ' * 200_000)
    wrapped = []
    wrap = cards.Pen.wrap
    monkeypatch.setattr(cards.Pen, 'wrap', lambda pen, text, *a, **k: wrapped.append(len(text)) or wrap(pen, text, *a, **k))
    r = api.get('/api/explain/card/', {'path': PATH, 'shape': 'story'})
    assert r.status_code == 200 and max(wrapped) <= cards.FIT_MOST
    assert api.get('/api/explain/card/', {'answer': '²'}).status_code == 404     # not a 500


def test_the_bundle_costs_the_same_whatever_the_articles(people, lease, django_assert_max_num_queries):
    # S4 of the performance audit: the DOC, 1,314 articles with no explanation, cost 1,320 queries.
    version = lease.latest_version()
    for i in range(100, 160):
        Article.objects.create(version=version, order=i, label=f'المادة {i}', number=str(i), eid=f'art_{i}',
                               body=f'نص المادة {i}.')
    with django_assert_max_num_queries(3):
        assert explanations.bundle(TEXT) == {'text': {}, 'articles': {}}
    explanations.save(people['reviewer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن.')
    explanations.save(people['writer'], f'{TEXT}/art_33', 'ar', 'كل ثلاث سنوات.')
    explanations.check(people['reviewer'], f'{TEXT}/art_33', 'ar')
    with django_assert_max_num_queries(7):
        shown = explanations.bundle(TEXT)['articles']
    assert sorted(shown) == ['art_33', 'art_34'] and not shown['art_34']['registers']['ar']['outdated']


def test_a_deleted_editor_still_counts_once(people):
    explanations.save(people['writer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن.')
    explanations.check(people['reviewer'], PATH, 'ar')
    explanations.save(people['reviewer'], PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن (المادة 34).')
    Explanation.objects.get(path=PATH).revisions.filter(author=people['writer']).update(author=None)
    assert explanations.bundle(TEXT)['articles']['art_34']['registers']['ar']['editors'] == 2
