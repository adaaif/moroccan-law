"""The finder's answers (PL19–PL22): a place's profile, its articles a page at a time with their filters, what a reader
types, search's door, a followed place's news; each in a fixed number of queries."""
from datetime import date

import pytest

from apps.corpus.models import Article
from apps.corpus.tests.test_perf import law
from apps.places.models import Mention, Place, PlaceYear, Year
from apps.places.services import finder
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    """France named in six laws' first article, from 2015 to 2020; Senegal beside it in two; the years' totals."""
    france = Place.objects.create(slug='france', kind='country', name_ar='فرنسا', name_fr='France', name_en='France', code='FRA',
                                  forms=['فرنسا', 'الجمهوريه الفرنسيه'], latin=['france'], lat=46.7, lon=2.5)
    senegal = Place.objects.create(slug='senegal', kind='country', name_ar='السنغال', name_fr='Sénégal', forms=['السنغال', 'السينغال'],
                                   latin=['senegal'])
    for i, year in enumerate(range(2015, 2021)):
        text = law(f'{i + 1}-{year % 100}', articles=2, title=f'قانون رقم {i + 1}')
        Article.objects.filter(version__text=text, eid='art_1').update(body='اتفاق مع فرنسا في شأن الشغل')
        Mention.objects.create(place=france, uri=text.akn_uri, eid='art_1', order=1, date=date(year, 3, 1), issue=str(6000 + i),
                               edition=Edition.GENERAL_AR, page=100 + i, text_type='law', kind='treaty' if i % 2 else 'other',
                               form='فرنسا', at=9)
        if i < 2:
            Mention.objects.create(place=senegal, uri=text.akn_uri, eid='art_1', order=1, date=date(year, 3, 1), issue=str(6000 + i),
                                   edition=Edition.GENERAL_AR, page=100 + i, text_type='law', kind='treaty', form='السنغال', at=0)
        PlaceYear.objects.create(place=france, year=year, texts=1, kinds={'treaty': 1})
        Year.objects.create(year=year, texts=100, foreign=10)
    france.texts, senegal.texts = 6, 2
    france.first = {'date': '2015-03-01', 'uri': '/akn/ma/act/loi/1-15', 'eid': 'art_1', 'order': 1, 'issue': '6000',
                    'edition': Edition.GENERAL_AR, 'page': 100, 'form': 'فرنسا', 'at': 9, 'title': 'قانون رقم 1'}
    france.save()
    senegal.save()
    return france


def test_a_profile_in_a_few_queries(api, world, django_assert_max_num_queries):
    with django_assert_max_num_queries(8):
        d = api.get('/api/places/france/').json()
    assert d['place']['texts'] == 6 and d['place']['first']['path'] == '/ma/loi/1-15/art_1'
    assert [y['texts'] for y in d['years']] == [1] * 6 and d['years'][0]['total'] == 100
    assert d['kinds'] == {'treaty': 6} and d['types'] == {'law': 6}


def test_the_articles_a_page_at_a_time_newest_first(api, world, django_assert_max_num_queries, monkeypatch):
    monkeypatch.setattr(finder, 'PAGE', 4)
    with django_assert_max_num_queries(9):
        first = api.get('/api/places/france/mentions/').json()
    assert [r['date'][:4] for r in first['rows']] == ['2020', '2019', '2018', '2017']
    assert first['rows'][0]['snippet']['hit'] == 'فرنسا' and first['rows'][0]['label'] == 'المادة 1'
    rest = api.get('/api/places/france/mentions/', {'after': first['next']}).json()
    assert [r['date'][:4] for r in rest['rows']] == ['2016', '2015'] and rest['next'] is None


@pytest.mark.parametrize('params, years', [
    ({'from': '2016', 'to': '2017'}, ['2017', '2016']),
    ({'kind': 'treaty'}, ['2020', '2018', '2016']),
    ({'with': 'senegal'}, ['2016', '2015']),
    ({'title': '1'}, []),
])
def test_the_filters(api, world, params, years):
    assert [r['date'][:4] for r in api.get('/api/places/france/mentions/', params).json()['rows']] == years


def test_a_filter_out_of_shape_is_refused(api, world):
    r = api.get('/api/places/france/mentions/', {'from': '19x6'})
    assert r.status_code == 400 and r.json() == {'errors': [{'field': 'from', 'code': 'invalid'}]}


def test_a_place_not_held(api, world):
    assert api.get('/api/places/atlantis/').status_code == 404


def test_what_a_reader_types_and_the_search_door(world):
    assert [p['slug'] for p in finder.typed('فرن')['places']] == ['france']
    assert [p['slug'] for p in finder.typed('السينغال')['places']] == ['senegal']
    assert finder.door('France')['slug'] == 'france'
    assert finder.door('فرنسا')['path'] == '/places/france'
    assert finder.door('فرنسا الجميلة') is None


def test_a_followed_place_has_its_newest_texts_as_news(world):
    from apps.follows.services import news
    assert news.kind_of('/places/france') == 'where' and news.kind_of('/places/رباط الخير') == 'place'
    assert news.describe('/places/france')['name'] == {'ar': 'فرنسا', 'fr': 'France'}
    items = news.items(news.describe('/places/france'))
    assert [i['text']['path'] for i in items][:2] == ['/ma/loi/6-20', '/ma/loi/5-19']
    assert items[0]['key'] == 'where:/ma/loi/6-20' and items[0]['kind'] == 'new_text'


def test_the_issue_page_link(world):
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=6000, date=date(2015, 3, 1))
    assert finder._stamp(Edition.GENERAL_AR, '6000', 100, {})['to'] is None
    assert issue.key == '6000'
