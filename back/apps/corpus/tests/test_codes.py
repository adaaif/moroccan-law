"""Codes by the names people give them, and the shelf of the texts people look for most."""
from datetime import date

import pytest

from apps.corpus.models import Consolidation, Text, Version
from apps.corpus.services.codes import code_named, shelf
from apps.search.services.search import asked_words


def test_code_named():
    assert code_named('قانون السير') == ('road', 'قانون السير')
    assert code_named('شنو كيقول القانون الجنائي على السرقة')[0] == 'penal'
    assert code_named('Code de la famille')[0] == 'family'
    assert code_named('مدونة السير على الطرق') == ('road', 'مدونة السير على الطرق')
    assert code_named('constitution') == ('constitution', 'constitution')
    assert code_named("constitution d'une société anonyme") is None
    assert code_named('الكراء') is None
    # The home's lease law (67.12) by what people type: the whole query, or words only it uses.
    assert code_named('عقد الكراء') == ('housing_lease', 'عقد الكراء')
    assert code_named('عقد الكراء التجاري') is None
    assert code_named('واجبات كراء المحلات المعدة للسكنى')[0] == 'housing_lease'


def test_asked_words():
    assert asked_words('واش خاصني رخصة السياقة باش نسوق موطور') == 'رخصة السياقة نسوق موطور'
    assert asked_words('est-ce que je peux conduire une moto') == 'conduire moto'
    assert asked_words('شنو هي العقوبة ديال السرقة') == 'العقوبة السرقة'
    assert asked_words('واش') == 'واش'


@pytest.mark.django_db
def test_shelf_says_where_each_text_stands():
    road = Text.objects.create(akn_uri='/akn/ma/act/loi/52-05', type='law', number='52-05', number_as_printed='52.05',
                               title_ar='القانون رقم 52.05 المتعلق بمدونة السير على الطرق')
    Version.objects.create(text=road, language='ar', valid_from=date(2010, 3, 11), consolidation=Consolidation.AS_PUBLISHED)
    rows = {r['key']: r for r in shelf()}
    assert len(rows) == 20
    assert rows['road']['state'] == 'in_corpus' and rows['road']['path'] == '/ma/loi/52-05' and rows['road']['official'] is None
    assert rows['family']['state'] == 'not_in_corpus' and 'adala.justice.gov.ma' in rows['family']['official']
