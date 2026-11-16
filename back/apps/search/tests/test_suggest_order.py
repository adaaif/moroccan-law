"""RD9 of the readers review: what the box offers while a reader types. «الطلا» offered three protectorate
dahirs on French divorce law and no family code; 13 of 33 beginnings filled with texts of 1915 to 1960."""
from datetime import date

import ma_law
import pytest

from apps.corpus.models import Text, Version
from apps.search.services import index
from apps.search.services.search.suggestions import _bare, _topics

pytestmark = pytest.mark.django_db


def _text(uri, kind, number, title, day):
    t = Text.objects.create(akn_uri=uri, type=kind, number=number, number_as_printed=number.replace('-', '.'),
                            title_ar=title, signed_on=day)
    Version.objects.create(text=t, language='ar', valid_from=day, consolidation='as_published')
    return t


def test_the_kingdoms_base_texts_come_before_the_archive_and_the_laws_that_amend(api):
    _text('/akn/ma/act/dahir/1915-12-08/bo137-2', 'dahir', '', 'ظهير شريف في كراء المحلات بالمدن', date(1915, 12, 8))
    _text('/akn/ma/act/loi/40-27', 'law', '40-27', 'قانون رقم 40.27 يقضي بتغيير القانون رقم 12.26 المتعلق بكراء المحلات التجارية',
          date(2027, 3, 1))
    _text('/akn/ma/act/loi/12-26', 'law', '12-26', 'قانون رقم 12.26 يتعلق بكراء المحلات التجارية', date(2026, 8, 10))
    index.rebuild(log=lambda *_: None)
    paths = [t['path'] for t in api.get('/api/search/suggest/', {'q': 'كراء المحلات'}).json()['texts']]
    assert paths == ['/ma/loi/12-26', '/ma/loi/40-27', '/ma/dahir/1915-12-08/bo137-2']


def test_a_typed_beginning_names_the_topic_whose_word_is_nearest():
    # «الضريب» opens the taxes' «الضريبة» and the housing's «ضريبة السكن»: the list's order decided, for the housing.
    assert _topics('الضريب', [_bare(w) for w in ma_law.tokens('الضريب')])[0]['slug'] == 'tax'


def test_darija_in_latin_letters_is_read_as_people_write_it():
    """RD10 of the readers review: «tla9» was read «تلق», «ntala9» «نتالاق». A question that mixes in a French
    word is still left to its French (UX7's measure stands: read in Arabic letters it lost texts)."""
    from apps.search.services.spelling import arabizi
    assert arabizi('bghit ntala9 mn rajli') == 'بغيت نطلق من راجلي'
    assert arabizi('chrit mn internet w bghit nrje3 sel3a').split()[0] == 'شريت'
    assert arabizi('vignette tomobil chhal') is None
    assert arabizi('code du travail licenciement') is None


def test_the_named_topics_law_is_offered_from_four_typed_letters(api, monkeypatch):
    """«الطلا» is a stem of three letters: the rule counted stems, and the live box still offered two decrees."""
    from apps.search.services.search import suggestions
    monkeypatch.setattr(suggestions, '_topic_codes', lambda slug, most=1: [f'/ma/code-of/{slug}'])
    seen = {}
    monkeypatch.setattr(suggestions, '_texts', lambda found: seen.setdefault('found', list(found)) and {})
    api.get('/api/search/suggest/', {'q': 'الطلا'})
    assert seen['found'][:1] == ['/ma/code-of/family']
    seen.clear()
    api.get('/api/search/suggest/', {'q': 'عقد'})
    assert not any(p.startswith('/ma/code-of/') for p in seen.get('found', []))
