"""RD17 of the readers review: an amending article's link to the article it changes is looked up, never written from
the number (72 of the 2,758 article links a crawler followed on 9 Nov 2026 led nowhere)."""
from datetime import date

import pytest

from apps.corpus.models import Article, Text, Version
from apps.corpus.services.annotate import _eids, _mirror

pytestmark = pytest.mark.django_db


def test_an_added_articles_number_is_found_either_way_round():
    code = Text.objects.create(akn_uri='/akn/ma/act/loi/22-01', type='law', number='22-01', title_ar='قانون المسطرة الجنائية')
    v = Version.objects.create(text=code, language='ar', valid_from=date(2025, 9, 8), consolidation='adala')
    Article.objects.create(version=v, order=1, label='المادة 60', number='60', eid='art_60', body='…')
    Article.objects.create(version=v, order=2, label='المادة 595-1', number='595-1', eid='art_595-1', body='…')
    uri = code.akn_uri
    found = _eids({(uri, '1-595'), (uri, '60'), (uri, '999'), ('/akn/ma/act/loi/9-99', '3')})
    # «1-595» is article 595-1; article 60 as kept; an article the text does not hold, and a text not held, have none.
    assert found == {(uri, '1-595'): 'art_595-1', (uri, '60'): 'art_60'}
    assert _eids(set()) == {}


def test_only_a_number_in_two_parts_is_mirrored():
    assert (_mirror('1-595'), _mirror('595-1'), _mirror('40-bis'), _mirror('12'), _mirror('2-1-3')) == ('595-1', '1-595', '40-bis', '12', '2-1-3')
