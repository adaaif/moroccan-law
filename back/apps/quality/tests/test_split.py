"""Words a stray space cut in two in Adala's files (N3 of the read-and-trusted review): proposed joined, measured against
the BO as the OCR read it, applied by a person only."""
from collections import Counter
from datetime import date

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.models import Correction
from apps.quality.services import corrections, proofread

pytestmark = pytest.mark.django_db
ADALA = 'تطبق على الاستغ الالت الفلاحية الغابوية وتو ابعها، في أجل ثلاثين يوما.'


@pytest.fixture
def labour():
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', title_ar='مدونة الشغل')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 7, 16), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 66', number='66', eid='art_66', body=ADALA)
    return text


def printed() -> Counter:
    return Counter({'وتوابعها': 76, 'الاستغلالات': 8, 'في': 900, 'أجل': 400, 'ثلاثين': 50, 'يوما': 300})


def test_a_word_cut_in_two_is_found_joined_with_its_turned_lam_alef_put_back(labour):
    found = {(w, j) for _, w, _, _, j, _ in proofread.splits(printed())}
    assert found == {('وتو ابعها', 'وتوابعها'), ('الاستغ الالت', 'الاستغلالات')}


def test_two_words_the_bo_prints_are_never_joined(labour):
    # «في أجل» joins into nothing the BO prints, and both are words: left alone.
    assert all(w != 'في أجل' for _, w, *_ in proofread.splits(printed() + Counter({'فيأجل': 9})))


def test_split_proposes_and_a_person_applies(labour):
    assert proofread.split(printed()) == 2
    assert proofread.split(printed()) == 0                 # never proposed twice
    assert Article.objects.get(eid='art_66').body == ADALA
    c = Correction.objects.get(wrong='وتو ابعها')
    assert (c.source, c.status) == (Correction.Source.SPLIT, Correction.Status.SUGGESTED)
    assert 'الغابوية وتوابعها،' in corrections.put_right(ADALA, c)


def test_pieces_a_line_or_a_comma_keeps_apart_are_never_joined():
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/18-12', type='law', number='18-12', title_ar='قانون')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 7, 16), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body='وتو\nابعها، وتو، ابعها')
    assert list(proofread.splits(printed())) == []
