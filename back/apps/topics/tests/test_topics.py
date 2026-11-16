"""Life topics (R2 of the for-everyone review): each names real codes and situations, and a topic's recent changes are its
rule-making texts of the last half year whose title holds one of its words, the special section left out."""
import datetime
import json
from pathlib import Path

import pytest

from apps.corpus.models import Text
from apps.topics.services import topics
from apps.corpus.services.codes import MORE, SHELF
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db
DATA = Path(topics.__file__).resolve().parent.parent / 'data'
SITUATIONS = DATA.parent.parent / 'corpus' / 'data' / 'situations.json'


def test_every_topic_names_codes_and_situations_that_exist():
    every = topics.load()
    assert len(every) == 12 and len({t['slug'] for t in every}) == 12
    shelf = {key for key, _ in SHELF + MORE}       # a topic may list the named texts beside the shelf's (H17)
    situations = {s['slug'] for s in json.loads(SITUATIONS.read_text())['situations']}
    for t in every:
        assert set(t['codes']) <= shelf, t['slug']
        assert set(t['situations']) <= situations, t['slug']
        assert t['name']['ar'] and t['name']['fr'] and t['keywords']


def _text(uri, title, day, *, section='general', kind='decree'):
    issue, _ = Issue.objects.get_or_create(edition=Edition.GENERAL_AR, number=7000 + day.toordinal() % 500, suffix='',
                                           defaults={'date': day})
    return Text.objects.create(akn_uri=uri, type=kind, number=uri.rsplit('/', 1)[-1], title_ar=title,
                               first_published_in=issue, bo_section=section)


def test_a_topics_recent_changes_are_its_rule_making_texts_of_the_half_year():
    today = datetime.date(2026, 10, 19)
    housing = topics.find('housing')
    _text('/akn/ma/act/decret/2-26-578', 'مرسوم رقم 2.26.578 بتحديد أشكال دعم السكن', datetime.date(2026, 9, 1))
    _text('/akn/ma/act/decret/2-20-1', 'مرسوم رقم 2.20.1 يتعلق بالكراء', datetime.date(2020, 1, 1))
    _text('/akn/ma/act/decision/2026/1-26', 'مقرر يتعلق بالسكنى', datetime.date(2026, 9, 2), section='special')
    _text('/akn/ma/act/decret/2-26-9', 'مرسوم رقم 2.26.9 يتعلق بالصيد البحري', datetime.date(2026, 9, 3))
    assert [r['path'] for r in topics.recent(housing, today)] == ['/ma/decret/2-26-578']


def test_the_api_lists_the_topics_and_answers_one(api):
    listed = api.get('/api/topics/').json()
    assert [t['slug'] for t in listed][:3] == ['family', 'work', 'housing']
    one = api.get('/api/topics/housing/').json()
    assert one['name']['ar'] == 'السكن والكراء' and set(one) >= {'situations', 'codes', 'recent', 'words', 'talk'}
    # Its words by their terms (P16 of the polish review), and its conversation, empty here.
    assert one['words'][0] == {'slug': 'rent', 'term': {'ar': 'الوجيبة الكرائية', 'fr': one['words'][0]['term']['fr']}}
    assert one['talk'] == {'place': '/talk/housing', 'posts': [], 'questions': [], 'moderators': []}
    assert api.get('/api/topics/nowhere/').status_code == 404


def test_a_question_in_everyday_words_names_its_topic():
    assert [t['slug'] for t in topics.matching('مول الدار بغا يخرجني')] == ['housing']
    assert [t['slug'] for t in topics.matching('بغا يزيد فالكرا')] == ['housing']     # «فالكرا» holds «الكرا»
    assert [t['slug'] for t in topics.matching('طردوني من الخدمة')] == ['work']
    assert topics.matching('الفصل 418 من ق.ل.ع') == []


def test_search_answers_with_the_topics_a_question_names(api, monkeypatch):
    # BM25 needs ParadeDB; the answer's topics do not.
    monkeypatch.setattr('apps.search.api.views.search', lambda q, **kw: {'query': q, 'results': []})
    monkeypatch.setattr('apps.search.api.views.topic_words', lambda slug: [{'slug': 'eviction', 'article': None}])
    out = api.get('/api/search/', {'q': 'مول الدار بغا يخرجني'}).json()
    assert out['words'] == [{'slug': 'eviction', 'article': None}]
    assert [t['slug'] for t in out['topics']] == ['housing']


def test_a_topics_recent_changes_take_four_queries_whatever_the_texts(django_assert_max_num_queries):
    # S9 of the performance audit: the half year's issues first, then their texts' titles; since M7 of
    # the land review also the topic's own texts (one query) and which of the found texts change them (one query).
    today = datetime.date(2026, 10, 19)
    for n in range(12):
        _text(f'/akn/ma/act/decret/2-26-{600 + n}', f'مرسوم رقم 2.26.{600 + n} يتعلق بالكراء', datetime.date(2026, 9, 1 + n))
    with django_assert_max_num_queries(4):
        found = topics.recent(topics.find('housing'), today)
    assert [r['path'] for r in found][:2] == ['/ma/decret/2-26-611', '/ma/decret/2-26-610']


def test_a_name_that_borrows_a_topics_word_is_not_a_change_of_its_law():
    # M7 of the land review: the World Bank's Arabic name holds «التعمير»; its loans are not urbanism.
    today = datetime.date(2026, 10, 19)
    _text('/akn/ma/act/decret/2-26-759', 'مرسوم رقم 2.26.759 بالموافقة على اتفاقية قرض مع البنك الدولي للإنشاء والتعمير', datetime.date(2026, 10, 1))
    _text('/akn/ma/act/decret/2-26-760', 'مرسوم رقم 2.26.760 بتطبيق القانون المتعلق بالتعمير', datetime.date(2026, 10, 2))
    land = {**topics.find('land'), 'keywords': ['التعمير']}
    assert [r['path'] for r in topics.recent(land, today)] == ['/ma/decret/2-26-760']


def test_a_topic_without_words_has_no_recent_texts_and_asks_nothing(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert topics.recent({**topics.find('family'), 'keywords': []}) == []
