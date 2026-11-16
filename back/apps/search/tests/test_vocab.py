import pytest



def test_a_word_with_a_bare_lam_or_ba_also_carries_the_word_without_it(monkeypatch):
    # H5 of the housing plan: the aid decree writes «لدعم السكن»; a reader types «دعم السكن».
    from apps.search.services import index
    monkeypatch.setattr(index, 'term_counts', lambda: {'دعم': 900, 'لدعم': 40, 'طاق': 500, 'بطاق': 4000, 'اجاز': 700, 'باجاز': 3})
    assert index.with_bare(['لدعم', 'سكن']) == ['لدعم', 'سكن', 'دعم']
    assert index.with_bare(['باجاز']) == ['باجاز', 'اجاز']
    assert index.with_bare(['بطاق']) == ['بطاق']      # «بطاقة» stays apart from «طاقة»: both common


@pytest.mark.django_db
def test_the_question_is_said_again_with_the_laws_words_under_its_everyday_ones():
    # The search page's «بكلام القانون» (30 Oct 2026): a door's words and the everyday list, the longest form first.
    from apps.search.services.vocab import gloss
    # The door shown first lends its words (HM10 of the hard-moment review: never another door's).
    door = {'topic': 'housing', 'slug': 'housing-increase'}
    assert gloss('مول الدار بغا يزيد فالكرا', door) == [{'t': 'مول الدار '}, {'t': 'بغا يزيد فالكرا', 'law': 'الزيادة في الوجيبة الكرائية'}]
    assert gloss('واش الصابو قانوني؟', {'topic': 'road', 'slug': 'road-impound'}) == [{'t': 'واش '}, {'t': 'الصابو', 'law': 'توقيف المركبات'}, {'t': ' قانوني؟'}]
    assert gloss('الطلاق') == []
    # Another door's words are not the shown door's: no gloss of the medicine refund over a damages question.
    assert gloss('واش الصابو قانوني؟') == []
