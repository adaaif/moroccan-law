"""`build_places` (PL2): every Arabic text of the general and conventions editions read once for the places of
places.json, its title and each article, in its words as published when held, else in its newest version; the mentions,
the years and each place's count, first mention and spellings swapped in at once. The swap is PostgreSQL's COPY, as on
the server: on SQLite these tests skip, and they run where TEST_DATABASE_URL names a PostgreSQL server."""
import io
import json
from datetime import date

import pytest
from django.core.management import call_command
from django.db import connection

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.places.models import Mention, Place, PlaceYear, Year
from apps.places.services import build
from apps.sources.models import Edition, Issue

pytestmark = [pytest.mark.django_db,
              pytest.mark.skipif(connection.vendor != 'postgresql', reason="the swap is PostgreSQL's COPY (TEST_DATABASE_URL)")]

TREATY = '/akn/ma/act/dahir/2015/1-15-1'
TREATY_TITLE = 'ظهير شريف رقم 1.15.1 بنشر الاتفاقية الموقعة بين المملكة المغربية والجمهورية  الفرنسية'   # two spaces, as read
PORT = '/akn/ma/act/arrete/1940/1-40-7'
TRADE = '/akn/ma/act/convention/1963/12'
TRADE_ARTICLE = 'تسري هذه الأحكام على الصادرات للسنغال انطلاقا من ميناء طَنجة'
CENTRE = '/akn/ma/act/decret/2015/2-15-5'
CENTRE_TITLE = 'مرسوم بإحداث مركز جهوي للاستثمار بمدينة طنجة'
PORT_ARTICLE = 'يطبق هذا القرار في دولة اسرائيل وبمدينة طنجة وفي ميناء بور\nليوطي والجمهورية\tالفرنسية'
LISTED = ('france', 'senegal', 'israel', 'tanger', 'kenitra', 'province-kenitra', 'czechoslovakia')


def text(uri, title, edition, day, *versions, number=1, suffix='', page=None, kind='dahir'):
    """A text first published in an issue, with its versions: (consolidation, language, valid_from, [article bodies])."""
    issue = Issue.objects.filter(edition=edition, number=number, suffix=suffix).first() or \
        Issue.objects.create(edition=edition, number=number, suffix=suffix, date=day)
    t = Text.objects.create(akn_uri=uri, type=kind, number=uri.rsplit('/', 1)[1], title_ar=title, first_published_in=issue,
                            first_published_page=page)
    for consolidation, language, valid_from, bodies in versions:
        v = Version.objects.create(text=t, language=language, valid_from=valid_from, consolidation=consolidation)
        Article.objects.bulk_create([Article(version=v, order=i, label=f'المادة {i}', number=str(i), eid=f'art_{i}', body=b)
                                     for i, b in enumerate(bodies, 1)])
    return t


def listed(tmp_path, monkeypatch, slugs=LISTED):
    """places.json as build_places reads it: these rows of the list, in a folder of the test's own."""
    path = tmp_path / 'places.json'
    path.write_text(json.dumps([r for r in build.gazetteer() if r['slug'] in slugs], ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(build, 'DATA', path)


def run() -> str:
    out = io.StringIO()
    call_command('build_places', stdout=out)
    return out.getvalue()


def named() -> list[tuple]:
    return sorted(Mention.objects.values_list('place__slug', 'uri', 'eid', 'printed'))


@pytest.fixture
def bulletin(tmp_path, monkeypatch):
    """Seven places of the list; a 2015 treaty with France read as published (Adala's later words not read), a decree
    of the same issue naming Tangier alone, a 1940 order held only in later versions, a 1963 agreement of the conventions
    edition; two reports, a French edition's text and a text with no Arabic words, none of them read. A place the list
    no longer holds, one whose names changed."""
    listed(tmp_path, monkeypatch)
    gone = Place.objects.create(slug='atlantis', kind='country', name_ar='أطلنتس')
    france = Place.objects.create(slug='france', kind='country', name_ar='فرنسا', name_fr='Fr.', texts=99)
    Mention.objects.create(place=gone, uri=TREATY, date=date(2015, 3, 1), issue='6340', edition=Edition.GENERAL_AR,
                           text_type='dahir', kind='other', form='أطلنتس')
    AP, ADALA, MACHINE = Consolidation.AS_PUBLISHED, Consolidation.ADALA, Consolidation.MACHINE
    text(TREATY, TREATY_TITLE, Edition.GENERAL_AR, date(2015, 3, 1),
         (AP, 'ar', date(2015, 3, 1), ['تطبق أحكام هذه الاتفاقية بمدينة طنجة وفي فرنسـا.', '']),
         (ADALA, 'ar', date(2020, 1, 1), ['نص آخر يذكر السنغال']), number=6340, page=1200)
    text(CENTRE, CENTRE_TITLE, Edition.GENERAL_AR, date(2015, 3, 1), (AP, 'ar', date(2015, 3, 1), ['يحدث مركز جهوي.']), number=6340,
         page=1210, kind='decree')
    text(PORT, 'قرار وزيري بتحديد المنطقة المحيطة بميناء بور ليوطي', Edition.GENERAL_AR, date(1940, 5, 10),
         (MACHINE, 'ar', date(1940, 5, 10), ['نص قديم']),
         (ADALA, 'ar', date(1990, 1, 1), [PORT_ARTICLE]), number=1440, suffix='bis', page=85, kind='arrete')
    text(TRADE, 'اتفاق تجاري بين المملكة المغربية وجمهورية السنغال', Edition.CONVENTIONS_AR, date(1963, 2, 1),
         (AP, 'ar', date(1963, 2, 1), [TRADE_ARTICLE]), number=12, page=3, kind='convention')
    text('/akn/ma/act/report/2015/1', 'تقرير حول التعاون مع فرنسا', Edition.GENERAL_AR, date(2015, 3, 1),
         (AP, 'ar', date(2015, 3, 1), ['التعاون مع فرنسا']), number=6340, kind='report')
    text('/akn/ma/act/report/2015/2', 'التقرير السنوي حول التعاون مع فرنسا', Edition.GENERAL_AR, date(2015, 3, 1),
         (AP, 'ar', date(2015, 3, 1), ['التعاون مع فرنسا']), number=6340, kind='report')
    text('/akn/ma/act/dahir/2015/1-15-2', 'ظهير شريف بنشر اتفاق مع فرنسا', Edition.TRANSLATION_FR, date(2015, 3, 2),
         (AP, 'ar', date(2015, 3, 2), ['اتفاق مع فرنسا']), number=6341)
    text('/akn/ma/act/decret/2016/2-16-1', 'مرسوم رقم 2.16.1', Edition.GENERAL_AR, date(2016, 1, 4),
         (AP, 'fr', date(2016, 1, 4), ['Décret relatif à la France']), number=6430, kind='decree')
    return france


def test_every_text_is_read_once_and_the_rows_swapped_in(bulletin):
    assert run() == ('5 texts, 4 read (3 as published)\n'
                     "{'texts': 4, 'articles': 4, 'mentions': 11, 'places': 4, 'years': 2}\n")
    rows = sorted(Mention.objects.values_list('place__slug', 'uri', 'eid', 'order', 'issue', 'edition', 'page', 'text_type',
                                              'form', 'at', 'printed', 'old'))
    assert rows == [
        # A tab or a line's end inside a name is a space in the row.
        ('france', PORT, 'art_1', 1, '1440-bis', Edition.GENERAL_AR, 85, 'arrete', 'والجمهورية الفرنسية', 65, False, False),
        ('france', TREATY, '', -1, '6340', Edition.GENERAL_AR, 1200, 'dahir', 'والجمهورية  الفرنسية', 65, True, False),
        ('france', TREATY, 'art_1', 1, '6340', Edition.GENERAL_AR, 1200, 'dahir', 'فرنسـا', 41, True, False),
        # Israel is not counted before the day it took its name (1948); the 1940 order is read in its newest words.
        ('kenitra', PORT, '', -1, '1440-bis', Edition.GENERAL_AR, 85, 'arrete', 'بور ليوطي', 41, False, True),
        ('kenitra', PORT, 'art_1', 1, '1440-bis', Edition.GENERAL_AR, 85, 'arrete', 'بور ليوطي', 55, False, True),
        ('senegal', TRADE, '', -1, '12', Edition.CONVENTIONS_AR, 3, 'convention', 'السنغال', 42, True, False),
        ('senegal', TRADE, 'art_1', 1, '12', Edition.CONVENTIONS_AR, 3, 'convention', 'للسنغال', 30, True, False),
        ('tanger', PORT, 'art_1', 1, '1440-bis', Edition.GENERAL_AR, 85, 'arrete', 'طنجة', 40, False, False),
        ('tanger', TRADE, 'art_1', 1, '12', Edition.CONVENTIONS_AR, 3, 'convention', 'طَنجة', TRADE_ARTICLE.index('طَنجة'), True,
         False),
        ('tanger', TREATY, 'art_1', 1, '6340', Edition.GENERAL_AR, 1200, 'dahir', 'طنجة', 32, True, False),
        ('tanger', CENTRE, '', -1, '6340', Edition.GENERAL_AR, 1210, 'decree', 'طنجة', CENTRE_TITLE.index('طنجة'), True, False)]
    # What a text is: by its title, as a state's text or as a Moroccan place's.
    assert set(Mention.objects.filter(uri=TREATY).values_list('place__slug', 'kind')) == {('france', 'treaty'), ('tanger', 'other')}
    # The years count the texts as printed, and those naming a state.
    assert list(Year.objects.order_by('year').values_list('year', 'texts', 'foreign')) == [(1963, 1, 1), (2015, 2, 1)]
    assert sorted(PlaceYear.objects.values_list('place__slug', 'year', 'texts', 'kinds')) == [
        ('france', 2015, 1, {'treaty': 1}), ('senegal', 1963, 1, {'treaty': 1}),
        ('tanger', 1963, 1, {'other': 1}), ('tanger', 2015, 2, {'other': 1, 'territory': 1})]


def test_each_place_its_count_first_mention_and_spellings(bulletin):
    run()
    places = {p.slug: p for p in Place.objects.all()}
    # The list is the list: a place it dropped is gone, one it kept is the same row with its names as listed.
    assert sorted(places) == sorted(LISTED) and places['france'].pk == bulletin.pk
    rows = {r['slug']: r for r in build.gazetteer() if r['slug'] in LISTED}
    assert {s: {'kind': p.kind, 'name_ar': p.name_ar, 'name_fr': p.name_fr, 'name_en': p.name_en, 'code': p.code,
                'region': p.region, 'parent': p.parent, 'town': p.town, 'successor': p.successor, 'lat': p.lat, 'lon': p.lon,
                'population': p.population, 'foreigners': p.foreigners, 'forms': p.forms, 'old': p.old, 'latin': p.latin}
            for s, p in places.items()} == {
        s: {'kind': r['kind'], 'name_ar': r['ar'], 'name_fr': r['fr'], 'name_en': r.get('en', ''), 'code': r['code'],
            'region': r.get('region', ''), 'parent': r.get('parent', ''), 'town': r.get('town', ''),
            'successor': r.get('successor', ''), 'lat': r.get('lat'), 'lon': r.get('lon'), 'population': r.get('pop'),
            'foreigners': r.get('foreign'), 'forms': r['forms'], 'old': r.get('old', []), 'latin': r['latin']}
        for s, r in rows.items()}
    # What the list leaves out is empty: no old name for a state, no population for a state or a gone state.
    assert (places['france'].old, places['france'].population, places['france'].parent) == ([], None, '')
    assert (places['czechoslovakia'].successor, places['province-kenitra'].town, places['tanger'].population) == (
        'czechia', 'kenitra', rows['tanger']['pop'])
    assert {s: p.texts for s, p in places.items()} == {'czechoslovakia': 0, 'france': 2, 'israel': 0, 'kenitra': 1,
                                                       'province-kenitra': 0, 'senegal': 1, 'tanger': 4}
    # The first mention as printed: the title before the article, the older text before the newer.
    assert places['france'].first == {
        'date': '2015-03-01', 'uri': TREATY, 'eid': '', 'order': -1, 'issue': '6340', 'edition': Edition.GENERAL_AR, 'page': 1200,
        'form': 'والجمهورية  الفرنسية', 'at': 65, 'title': TREATY_TITLE}
    assert (places['tanger'].first['uri'], places['tanger'].first['date']) == (TRADE, '1963-02-01')
    assert places['kenitra'].first is None and places['israel'].first is None
    # Spellings as printed, without the letter in front, the harakat, the elongation, a doubled space or «لل».
    assert places['france'].spellings == [{'form': 'الجمهورية الفرنسية', 'n': 1, 'from': 2015, 'to': 2015},
                                          {'form': 'فرنسا', 'n': 1, 'from': 2015, 'to': 2015}]
    assert places['senegal'].spellings == [{'form': 'السنغال', 'n': 2, 'from': 1963, 'to': 1963}]
    assert places['tanger'].spellings == [{'form': 'طنجة', 'n': 3, 'from': 1963, 'to': 2015}]


def test_a_second_build_replaces_the_first(bulletin):
    run()
    Text.objects.filter(akn_uri=TRADE).delete()
    assert run().endswith("{'texts': 3, 'articles': 3, 'mentions': 8, 'places': 3, 'years': 1}\n")
    assert Mention.objects.count() == 8 and list(Year.objects.values_list('year', flat=True)) == [2015]
    assert Place.objects.get(slug='senegal').texts == 0 and Place.objects.get(slug='senegal').spellings == []


def test_a_text_is_read_in_its_first_words_as_published_else_in_its_newest(tmp_path, monkeypatch):
    """Two printings of a treaty (the later one made first) and Adala's later words: the first printing is read. An order
    held only in later versions, made newest first: the newest is read."""
    listed(tmp_path, monkeypatch, ('france', 'senegal', 'tanger'))
    AP, ADALA, MACHINE = Consolidation.AS_PUBLISHED, Consolidation.ADALA, Consolidation.MACHINE
    text(TREATY, 'ظهير شريف رقم 1.15.1', Edition.GENERAL_AR, date(2015, 3, 1),
         (AP, 'ar', date(2015, 6, 1), ['تطبق في السنغال']), (AP, 'ar', date(2015, 3, 1), ['تطبق في فرنسا']),
         (ADALA, 'ar', date(2020, 1, 1), ['تطبق بمدينة طنجة']), number=6340, page=10)
    text(PORT, 'قرار وزيري رقم 7', Edition.GENERAL_AR, date(1940, 5, 10),
         (ADALA, 'ar', date(1990, 1, 1), ['يطبق بمدينة طنجة']), (MACHINE, 'ar', date(1950, 1, 1), ['يطبق في السنغال']),
         (MACHINE, 'ar', date(1945, 1, 1), ['يطبق في فرنسا']), number=1440, page=85, kind='arrete')
    assert run().startswith('2 texts, 2 read (1 as published)\n')
    assert named() == [('france', TREATY, 'art_1', True), ('tanger', PORT, 'art_1', False)]


def test_the_first_mention_is_the_earliest_day_then_issue_then_page_then_place_on_it(tmp_path, monkeypatch):
    """France on one day in three texts: a title on page 1200 of issue 6340, an article on its page 1190, an article on
    page 5 of 6340 bis; and a month later. The first is the article on page 1190; the year counts the four."""
    listed(tmp_path, monkeypatch, ('france',))
    AP = Consolidation.AS_PUBLISHED
    text(TREATY, 'ظهير شريف بنشر اتفاق مع فرنسا', Edition.GENERAL_AR, date(2015, 3, 1), (AP, 'ar', date(2015, 3, 1), ['نص']),
         number=6340, page=1200)
    text(CENTRE, 'مرسوم رقم 2.15.5', Edition.GENERAL_AR, date(2015, 3, 1), (AP, 'ar', date(2015, 3, 1), ['يطبق مع فرنسا']),
         number=6340, page=1190, kind='decree')
    text('/akn/ma/act/decret/2015/2-15-6', 'مرسوم رقم 2.15.6', Edition.GENERAL_AR, date(2015, 3, 1),
         (AP, 'ar', date(2015, 3, 1), ['يطبق مع فرنسا']), number=6340, suffix='bis', page=5, kind='decree')
    text('/akn/ma/act/dahir/2015/1-15-9', 'ظهير شريف بنشر اتفاق آخر مع فرنسا', Edition.GENERAL_AR, date(2015, 4, 1),
         (AP, 'ar', date(2015, 4, 1), ['نص']), number=6360, page=1)
    run()
    first = Place.objects.get(slug='france').first
    assert (first['uri'], first['issue'], first['page'], first['eid']) == (CENTRE, '6340', 1190, 'art_1')
    # The year's four texts, two of each kind.
    assert list(PlaceYear.objects.values_list('year', 'texts', 'kinds')) == [(2015, 4, {'treaty': 2, 'other': 2})]
    assert list(Year.objects.values_list('year', 'texts', 'foreign')) == [(2015, 4, 4)]


def test_a_place_keeps_its_eight_most_printed_spellings(tmp_path, monkeypatch):
    """France in ten articles, in nine spellings, «فرنسا» in two of them (and twice in the first)."""
    listed(tmp_path, monkeypatch, ('france',))
    once = ['الجمهورية الفرنسية', 'فرانسا', 'افرانسا', 'الجمهورية الفرنساوية', 'الدولة الفرنساوية', 'الجمهورية الفرنسوية',
            'الدولة الفرنسوية', 'الدولة الفرنسية']
    text(TREATY, 'ظهير شريف رقم 1.15.1', Edition.GENERAL_AR, date(2015, 3, 1),
         (Consolidation.AS_PUBLISHED, 'ar', date(2015, 3, 1),
          ['اتفاق مع فرنسا وتبادل مع فرنسا', *(f'اتفاق مع {x}' for x in ['فرنسا', *once])]), number=6340, page=1)
    run()
    # An article names a place once, where it first does.
    assert list(Mention.objects.filter(eid='art_1').values_list('at', flat=True)) == [9] and Mention.objects.count() == 10
    spellings = Place.objects.get(slug='france').spellings
    assert len(spellings) == 8 and spellings[0] == {'form': 'فرنسا', 'n': 2, 'from': 2015, 'to': 2015}
    assert {x['form'] for x in spellings[1:]} < set(once) and {x['n'] for x in spellings[1:]} == {1}
