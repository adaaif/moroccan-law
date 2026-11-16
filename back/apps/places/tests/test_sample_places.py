"""`sample_places` (PL3): mentions drawn at random for a person to read, half naming a state and half a Moroccan place,
each with its words around it and its address, written as JSON; the same seed draws the same sample; `--before` draws
from the old Bulletin only."""
import io
import json
from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.places.models import Mention, Place
from apps.sources.models import Edition

pytestmark = pytest.mark.django_db

LAW, DAHIR, PORT = '/akn/ma/act/loi/1-15', '/akn/ma/act/dahir/1955/1-55-100', '/akn/ma/act/dahir/1956/1-56-7'
LAW_BODY = 'اتفاق مع فرنسا في شأن الشغل بمدينة طنجة'
DAHIR_TITLE = 'ظهير شريف في شأن ميناء طنجة'


@pytest.fixture
def mentions():
    """A 2015 law naming France and Tangier in its first article (its French beside it); a 1955 dahir naming Tangier in
    its title and France in an article held only in Adala's version; a 1956 dahir naming Tangier in its title; France once
    more in a text read in its newest version (never drawn)."""
    france = Place.objects.create(slug='france', kind='country', name_ar='فرنسا', name_fr='France')
    tanger = Place.objects.create(slug='tanger', kind='city', name_ar='طنجة', name_fr='Tanger')
    law = Text.objects.create(akn_uri=LAW, type='law', number='1-15', title_ar='القانون رقم 1.15')
    for language, body in (('ar', LAW_BODY), ('fr', 'Accord avec la France sur le travail à Tanger')):
        v = Version.objects.create(text=law, language=language, valid_from=date(2015, 3, 1), consolidation=Consolidation.AS_PUBLISHED)
        Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body=body)
    dahir = Text.objects.create(akn_uri=DAHIR, type='dahir', number='1-55-100', title_ar=DAHIR_TITLE)
    v = Version.objects.create(text=dahir, language='ar', valid_from=date(1990, 1, 1), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='الفصل 1', number='1', eid='art_1', body='يطبق مع فرنسا')
    Text.objects.create(akn_uri=PORT, type='dahir', number='1-56-7', title_ar='ظهير شريف بتنظيم ميناء طنجة')

    def mention(place, uri, eid, day, issue, page, form, at, printed=True):
        Mention.objects.create(place=place, uri=uri, eid=eid, order=1 if eid else -1, date=day, issue=issue, page=page,
                               edition=Edition.GENERAL_AR, text_type='dahir', kind='other', form=form, at=at, printed=printed)
    mention(france, LAW, 'art_1', date(2015, 3, 1), '6340', 1200, 'فرنسا', LAW_BODY.index('فرنسا'))
    mention(tanger, LAW, 'art_1', date(2015, 3, 1), '6340', 1200, 'طنجة', LAW_BODY.index('طنجة'))
    mention(tanger, DAHIR, '', date(1955, 6, 2), '2225', 1561, 'طنجة', DAHIR_TITLE.index('طنجة'))
    mention(france, DAHIR, 'art_1', date(1955, 6, 2), '2225', 1561, 'فرنسا', 7)
    mention(tanger, PORT, '', date(1956, 3, 2), '2264', 410, 'طنجة', 22)
    mention(france, '/akn/ma/act/loi/2-16', 'art_2', date(2016, 1, 1), '6430', 30, 'فرنسا', 0, printed=False)


def draw(tmp_path, *args) -> tuple[list, str]:
    out, said = tmp_path / 'sample.json', io.StringIO()
    call_command('sample_places', '--out', str(out), *args, stdout=said)
    return json.loads(out.read_text(encoding='utf-8')), said.getvalue()


def test_half_states_half_moroccan_places_each_with_its_words(mentions, tmp_path):
    sample, said = draw(tmp_path, '--each', '5')
    assert said == '5 mentions drawn\n'
    assert [(m['n'], m['group']) for m in sample] == [(1, 'foreign'), (2, 'foreign'), (3, 'home'), (4, 'home'), (5, 'home')]
    by = {(m['place'], m['date']): m for m in sample}
    assert set(by) == {('france', '2015-03-01'), ('france', '1955-06-02'), ('tanger', '2015-03-01'), ('tanger', '1955-06-02'),
                       ('tanger', '1956-03-02')}
    # The article in its Arabic words as published, never its French.
    assert by['france', '2015-03-01'] == {
        'n': by['france', '2015-03-01']['n'], 'group': 'foreign', 'place': 'france', 'name': 'فرنسا', 'kind': 'country',
        'form': 'فرنسا', 'snippet': {'before': 'اتفاق مع', 'hit': 'فرنسا', 'after': 'في شأن الشغل بمدينة طنجة'},
        'date': '2015-03-01', 'issue': '6340', 'page': 1200, 'path': '/ma/loi/1-15/art_1'}
    # A title's mention reads the title and points to the text.
    assert by['tanger', '1955-06-02'] == {
        'n': by['tanger', '1955-06-02']['n'], 'group': 'home', 'place': 'tanger', 'name': 'طنجة', 'kind': 'city', 'form': 'طنجة',
        'snippet': {'before': 'ظهير شريف في شأن ميناء', 'hit': 'طنجة', 'after': ''}, 'date': '1955-06-02', 'issue': '2225',
        'page': 1561, 'path': '/ma/dahir/1955/1-55-100'}
    # An article whose words as published are not held has no snippet.
    assert by['france', '1955-06-02']['snippet'] is None


def test_each_group_is_drawn_up_to_its_number(mentions, tmp_path):
    sample, said = draw(tmp_path, '--each', '1')
    assert said == '2 mentions drawn\n' and [m['group'] for m in sample] == ['foreign', 'home']


def test_the_same_seed_draws_the_same_sample(mentions, tmp_path):
    def picked(seed):
        return [(m['place'], m['date']) for m in draw(tmp_path, '--each', '1', '--seed', str(seed))[0]]
    assert picked(7) == picked(7)
    assert len({tuple(picked(seed)) for seed in range(12)}) > 1


def test_before_a_year_draws_from_the_years_before_it_only(mentions, tmp_path):
    sample, _ = draw(tmp_path, '--before', '1956')
    assert sorted((m['place'], m['date']) for m in sample) == [('france', '1955-06-02'), ('tanger', '1955-06-02')]


def test_the_file_to_write_is_required():
    with pytest.raises(CommandError, match='--out'):
        call_command('sample_places')
