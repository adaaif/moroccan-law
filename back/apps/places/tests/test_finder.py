"""The finder's answers beyond the profile's and the list's basics (PL19–PL21): an article's words cut on whole words and
read as published, a title's mention, the printed page a stamp opens, the filters a reader may send and those refused,
what a reader types."""
from datetime import date

import pytest
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.places.models import Mention, Place
from apps.places.services import finder
from apps.sources.models import Document, Edition, Issue, Page

pytestmark = pytest.mark.django_db

LAW, DECREE = '/akn/ma/act/loi/1-15', '/akn/ma/act/decret/2-16-10'
TITLE = 'ظهير شريف بنشر الاتفاقية الموقعة مع فرنسا'
BODY = 'أ' + ' بيت' * 40 + ' فرنسا' + ' دار' * 40       # the name far from both ends, the cut falling inside a word


@pytest.fixture
def france():
    """France named in a 2015 law's title and first article (its page held), and in a 2016 decree."""
    document = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='6340'.ljust(64, '0'), path='BO_6340_ar.pdf',
                                       mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now())
    Issue.objects.create(edition=Edition.GENERAL_AR, number=6340, date=date(2015, 3, 1), document=document)
    Page.objects.create(document=document, index=4, printed_number=1200, kind='scan')
    law = Text.objects.create(akn_uri=LAW, type='law', number='1-15', title_ar=TITLE)
    printed = Version.objects.create(text=law, language='ar', valid_from=date(2015, 3, 1), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=printed, order=1, label='المادة 1', number='1', eid='art_1', body=BODY)
    later = Version.objects.create(text=law, language='ar', valid_from=date(2020, 1, 1), consolidation=Consolidation.ADALA)
    Article.objects.create(version=later, order=1, label='المادة الأولى', number='1', eid='art_1', body='نص المادة كما غير')
    Text.objects.create(akn_uri=DECREE, type='decree', number='2-16-10', title_ar='مرسوم رقم 2.16.10')
    place = Place.objects.create(slug='france', kind='country', name_ar='فرنسا', name_fr='France', forms=['فرنسا'], texts=2,
                                 first={'date': '2015-03-01', 'uri': LAW, 'eid': 'art_1', 'order': 1, 'issue': '6340',
                                        'edition': Edition.GENERAL_AR, 'page': 1200, 'form': 'فرنسا', 'at': BODY.index('فرنسا'),
                                        'title': TITLE})
    common = dict(place=place, issue='6340', edition=Edition.GENERAL_AR, page=1200, kind='treaty', form='فرنسا')
    Mention.objects.create(uri=LAW, eid='art_1', order=1, date=date(2015, 3, 1), text_type='law', at=BODY.index('فرنسا'), **common)
    Mention.objects.create(uri=LAW, eid='', order=-1, date=date(2015, 3, 1), text_type='law', at=TITLE.index('فرنسا'), **common)
    Mention.objects.create(uri=DECREE, eid='art_3', order=3, date=date(2016, 5, 2), text_type='decree', at=0,
                           **{**common, 'issue': '6460', 'page': None})
    return document


def test_an_article_is_read_as_published_and_cut_on_whole_words(api, france):
    rows = api.get('/api/places/france/mentions/', {'type': 'law'}).json()['rows']
    (art,) = [r for r in rows if not r['in_title']]
    assert (art['path'], art['label'], art['type']) == ('/ma/loi/1-15/art_1', 'المادة 1', 'law')
    snippet = art['snippet']
    assert snippet['hit'] == 'فرنسا'
    assert snippet['before'].split()[0] == '…' and set(snippet['before'].split()[1:]) == {'بيت'}
    assert snippet['after'].split()[-1] == '…' and set(snippet['after'].split()[:-1]) == {'دار'}
    # The issue's page is held: its stamp opens the printed page.
    assert art['stamp'] == {'issue': '6340', 'edition': Edition.GENERAL_AR, 'page': 1200, 'to': f'/pages/{france.pk}/4'}


def test_a_title_names_the_place(api, france):
    rows = api.get('/api/places/france/mentions/', {'title': '1'}).json()['rows']
    assert [(r['path'], r['in_title'], r['label'], r['title']) for r in rows] == [('/ma/loi/1-15', True, '', TITLE)]
    assert rows[0]['snippet'] == {'before': 'ظهير شريف بنشر الاتفاقية الموقعة مع', 'hit': 'فرنسا', 'after': ''}


def test_the_texts_of_one_type(api, france):
    rows = api.get('/api/places/france/mentions/', {'type': 'decree'}).json()['rows']
    assert [(r['path'], r['type'], r['stamp']['to']) for r in rows] == [('/ma/decret/2-16-10/art_3', 'decree', None)]


@pytest.mark.parametrize('field, value', [('type', 'Law'), ('with', 'Senegal!'), ('after', '2024-01-31|/other/x|1')])
def test_a_filter_out_of_shape_is_refused(api, france, field, value):
    r = api.get('/api/places/france/mentions/', {field: value})
    assert (r.status_code, r.json()) == (400, {'errors': [{'field': field, 'code': 'invalid'}]})


def test_the_profile_opens_the_first_mention_on_its_page(api, france):
    first = api.get('/api/places/france/').json()['place']['first']
    assert first['path'] == '/ma/loi/1-15/art_1' and first['stamp']['to'] == f'/pages/{france.pk}/4'


def test_a_place_never_named_has_no_first_mention(api, france):
    Place.objects.create(slug='senegal', kind='country', name_ar='السنغال', name_fr='Sénégal', forms=['السنغال'])
    d = api.get('/api/places/senegal/').json()
    assert d['place']['first'] is None and d['place']['texts'] == 0 and d['kinds'] == {}


def test_what_a_reader_types_names_those_it_starts_first():
    Place.objects.create(slug='region-tanger-tetouan-al-hoceima', kind='region', name_ar='طنجة-تطوان-الحسيمة', texts=50,
                         forms=['طنجه تطوان الحسيمه'], latin=['tanger tetouan al hoceima'])
    Place.objects.create(slug='tetouan', kind='city', name_ar='تطوان', name_fr='Tétouan', texts=9, forms=['تطوان'],
                         latin=['tetouan'])
    assert [p['slug'] for p in finder.typed('تطوان')['places']] == ['tetouan', 'region-tanger-tetouan-al-hoceima']
    assert [p['slug'] for p in finder.typed('hoceima')['places']] == ['region-tanger-tetouan-al-hoceima']
