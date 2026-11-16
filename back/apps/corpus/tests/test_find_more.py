"""More of what a reader writes to name a text (W1, W3–W6 of the library-search review): the newest issue, a bill no one
filed, a day several texts share, a kind and a year, a name a text had, a citation of a text the site does not hold; each
answer sure only when nothing else could be meant, and a note saying what was not found."""
from datetime import date

import pytest

from apps.corpus.services.find import find
from apps.corpus.tests.test_find import corpus, first, paths, text  # noqa: F401  (corpus: the texts every test reads)

pytestmark = pytest.mark.django_db


def notes(q: str, **kw) -> list[dict]:
    return [a for a in find(q, **kw)['answers'] if a['kind'] == 'note']


def test_the_newest_issue_is_left_to_the_browser_and_a_bill_no_one_filed_is_said():
    assert find('آخر عدد') == {'query': 'آخر عدد', 'understood': {'newest': True}, 'answers': []}
    assert notes('مشروع قانون المالية 2031') == [{'kind': 'note', 'code': 'no_bill', 'year': 2031}]
    assert notes('قانون المالية 2031') == [{'kind': 'note', 'code': 'no_finance_law', 'year': 2031}]
    # A settlement law and an amending finance law are never the year's finance law.
    text('loi/11-23', 'law', '11-23', 'قانون التصفية رقم 11.23 المتعلق بتنفيذ قانون المالية للسنة المالية 2021')
    text('loi/35-20', 'law', '35-20', 'قانون المالية رقم 35.20 للسنة المالية 2020 المعدل')
    assert notes('قانون المالية 2021') == [{'kind': 'note', 'code': 'no_finance_law', 'year': 2021}]
    assert notes('قانون المالية 2020') == [{'kind': 'note', 'code': 'no_finance_law', 'year': 2020}]


def test_a_day_several_texts_share_is_narrowed_by_the_words_and_says_how_many_more():
    assert paths('ظهير 2 أكتوبر 1984 بتفويض السلطة') == [(True, '/ma/dahir/1-83-351')]      # the one left: sure
    for i in range(8):
        text(f'dahir/1-99-{i}', 'dahir', f'1-99-{i}', f'ظهير شريف رقم 1.99.{i} بتعيين عضو', signed=date(1999, 6, 1))
    r = find('ظهير 1 يونيو 1999')
    assert len([a for a in r['answers'] if a['kind'] == 'text']) == 6
    assert r['answers'][-1] == {'kind': 'note', 'code': 'more_that_day', 'n': 2}


def test_a_kind_a_year_and_words_offer_the_texts_that_year_or_say_there_is_none():
    # A name a text had, that year: the 1957 dahir on personal status, offered.
    r = find('ظهير 1957 الاحوال الشخصية')
    assert [(a['sure'], a['path'], a['why']) for a in r['answers']] == [(True, '/ma/dahir/1-57-343', 'year')]
    # The words in no title together: the first one alone.
    assert paths('ظهير 1958 الجمعيات العمالية') == [(True, '/ma/dahir/1-58-376')]
    assert notes('ظهير 1958 الطيران') == [{'kind': 'note', 'code': 'no_text_that_year', 'year': 1958}]
    # Two of that kind and year hold the word: neither is sure.
    text('dahir/1-58-377', 'dahir', '1-58-377', 'ظهير شريف رقم 1.58.377 بتنظيم الجمعيات الرياضية', signed=date(1958, 11, 15))
    assert [sure for sure, _ in paths('ظهير 1958 الجمعيات')] == [False, False]


def test_the_suggestions_ask_for_a_name_a_text_had():
    r = find('مدونة الاحوال الشخصية', beyond=True)
    assert next((a['path'], a['why'], a.get('former')) for a in r['answers']) == ('/ma/dahir/1-57-343', 'former', 'replaced')


def test_an_article_of_a_text_the_corpus_does_not_hold_is_said_and_a_dahir_too():
    assert notes('المادة 5 من القانون رقم 99.98') == [{'kind': 'note', 'code': 'not_held', 'number': '99.98', 'type': 'law'}]
    assert notes('ظهير شريف رقم 1.99.501') == [{'kind': 'note', 'code': 'not_held', 'number': '1.99.501', 'type': 'dahir'}]
    # A finance law's number before the Bulletin prints the law: the bill.
    assert first('القانون رقم 60.26')['path'] == '/ma/projet-loi/60-26'


def test_words_that_name_nothing_answer_nothing():
    assert find('في من على') == {'query': 'في من على', 'understood': {}, 'answers': []}
