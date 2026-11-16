"""The posts whose arithmetic is apart (`tabulate`, so rows exported with psql count as the command does): each count reads
exactly the rows its post is about (the Arabic general edition, the post's years, the kinds it names) and hands them to
the same arithmetic. The arithmetic itself is tested in test_blog.py; here, which rows reach it."""
from datetime import date

import pytest

from apps.blog.services import posts  # noqa: F401  first, as the site loads them
from apps.blog.services import agreements, cities, countries, months, waits, writers
from apps.corpus.models import TextType
from apps.places.models import Mention, Place, PlaceYear, Year
from apps.sources.models import Edition

from .rows import issue, text

pytestmark = pytest.mark.django_db


def test_the_agreements_are_the_titles_that_name_one_of_the_seven_words_in_the_posts_years():
    meta = {'span': [1956, 2025]}
    titles = [(1958, TextType.ORDER, 'قرار في تخصيص سلف للصندوق الفلاحي'),
              (1960, TextType.DAHIR, 'ظهير شريف بنشر الاتفاق المبرم بين المغرب والبرتغال'),
              (1961, TextType.DAHIR, 'ظهير شريف بنشر المعاهدة الموقعة بلاهاي'),
              (1962, TextType.DAHIR, 'ظهير شريف بنشر البروتوكول الملحق بالميثاق'),
              (2011, TextType.DECREE, 'مرسوم بالموافقة على عقد الضمان المبرم مع الصندوق الكويتي للتنمية'),
              (2012, TextType.DECREE, 'مرسوم بالموافقة على عقد ضمان مع البنك الإفريقي للتنمية'),
              (2024, TextType.DECREE, 'مرسوم بالموافقة على القرض الممنوح من البنك الدولي للإنشاء والتعمير')]
    rows = []
    for k, (year, kind, title) in enumerate(titles):
        t = text(f'/akn/ma/act/{kind}/{k}-{year}', kind, issue(1000 + k, date(year, 3, 1)), title=title, number=f'{k}.{year}')
        rows.append((kind, t.number, date(year, 3, 1), t.akn_uri, title))
    # Not read: a title without the words, before and after the span, the French edition.
    text('/akn/ma/act/decree/x-2000', TextType.DECREE, issue(2000, date(2000, 3, 1)), title='مرسوم بتحديد الأجور')
    text('/akn/ma/act/dahir/x-1955', TextType.DAHIR, issue(1955, date(1955, 3, 1)), title='ظهير بنشر اتفاق')
    text('/akn/ma/act/dahir/x-2026', TextType.DAHIR, issue(2026, date(2026, 3, 1)), title='ظهير بنشر اتفاق')
    text('/akn/ma/act/dahir/x-fr', TextType.DAHIR, issue(1001, date(1960, 3, 1), edition=Edition.TRANSLATION_FR),
         title='ظهير بنشر اتفاق')
    out = agreements.count(meta)
    assert out == agreements.tabulate(meta, rows)
    assert out['texts'] == 7 and sum(out['sorted'].values()) == 7


def test_the_waits_read_each_text_of_the_posts_years_with_its_signature_issue_and_page():
    meta = {'span': [2019, 2021]}
    bis = issue(6860, date(2020, 3, 5), suffix='bis')
    law = text('/akn/ma/act/loi/25-19', TextType.LAW, bis, title='قانون رقم 25.19', number='25-19', page=400, signed_on=date(2019, 1, 10))
    feb = issue(6850, date(2020, 2, 14))
    order = text('/akn/ma/act/arrete/1-20', TextType.ORDER, feb, title='قرار', number='1-20', page=7, signed_on=date(2020, 1, 1))
    # A circular is kept but is no kind the post compares; a dahir without its signature's day is left out and said.
    circular = text('/akn/ma/act/circulaire/2-20', TextType.CIRCULAR, feb, title='دورية', number='2-20', page=8, signed_on=date(2020, 1, 1))
    dahir = text('/akn/ma/act/dahir/1-20-1', TextType.DAHIR, feb, title='ظهير', number='1-20-1', page=9)
    for k, (day, kind) in enumerate(((date(2018, 6, 1), TextType.LAW), (date(2022, 6, 1), TextType.LAW))):
        text(f'/akn/ma/act/loi/x-{k}', kind, issue(7000 + k, day), title='قانون', signed_on=date(2017, 1, 1))
    text('/akn/ma/act/loi/x-fr', TextType.LAW, issue(6860, date(2020, 3, 5), suffix='bis', edition=Edition.TRANSLATION_FR),
         title='قانون', signed_on=date(2019, 1, 1))
    rows = [(t.type, t.number, t.signed_on, t.first_published_in.date, t.first_published_in.number, t.first_published_in.suffix,
             t.first_published_page, t.akn_uri, t.title_ar) for t in (law, order, circular, dahir)]
    out = waits.count(meta)
    assert out == waits.tabulate(meta, rows)
    assert (out['kept'], out['left_out']['no_date']) == (3, 1) and out['counts'] == {'law': 1, 'order': 1}
    assert out['late'][0]['issue'] == '6860-bis' and out['late'][0]['page'] == 400 and out['late'][0]['days'] == 420


def test_who_writes_reads_each_texts_year_kind_authority_and_title_in_the_posts_years():
    meta = {'span': [1965, 2011],
            'authors': [{'key': 'king', 'types': ['dahir']}, {'key': 'ministers', 'types': ['order']}, {'key': 'others', 'types': []}],
            'ministries': [{'key': 'education', 'words': ['التعليم']}, {'key': 'finance', 'words': ['المالية']}],
            'subjects': [{'key': 'delegation', 'words': ['تفويض الإمضاء']}], 'laws': [{'key': 'agreement', 'words': ['يوافق بموجبه']}]}
    texts = [(1965, TextType.DAHIR, '', 'ظهير'), (2011, TextType.ORDER, 'وزير المالية', 'قرار بتفويض الإمضاء'),
             (2011, TextType.LAW, '', 'قانون يوافق بموجبه على اتفاق'), (1970, TextType.DECREE_LAW, '', 'مرسوم بمثابة قانون')]
    for k, (year, kind, authority, title) in enumerate(texts):
        text(f'/akn/ma/act/{kind}/{k}', kind, issue(100 + k, date(year, 6, 1)), authority=authority, title=title)
    # Outside the years: an order of 1964 (its decade is the post's) and a law of 2012 (so is its).
    text('/akn/ma/act/arrete/x-1964', TextType.ORDER, issue(90, date(1964, 6, 1)), authority='وزير المالية', title='قرار')
    text('/akn/ma/act/loi/x-2012', TextType.LAW, issue(91, date(2012, 6, 1)), title='قانون')
    text('/akn/ma/act/arrete/x-fr', TextType.ORDER, issue(101, date(2011, 6, 1), edition=Edition.TRANSLATION_FR), authority='وزير التعليم')
    out = writers.count(meta)
    assert out == writers.tabulate(meta, texts)
    assert out['ministries'] == {'finance': 1} and out['authors']['king'][0] == 1 and sum(out['authors']['king']) == 1


def test_the_months_read_each_issue_of_the_posts_years_with_its_pages_and_its_texts_by_kind():
    meta = {'span': [1996, 1996], 'hijri_since': 1996}
    march = issue(4363, date(1996, 3, 4), pages=20, hijri='14 شوال 1416')
    for k, kind in enumerate((TextType.LAW, TextType.DECREE, TextType.ORDER, TextType.CIRCULAR)):
        text(f'/akn/ma/act/{kind}/3-{k}', kind, march)
    december = issue(4444, date(1996, 12, 31), suffix='bis', pages=300, hijri='19 شعبان 1417')
    for k, kind in enumerate((TextType.ORGANIC_LAW, TextType.DECREE_LAW)):
        text(f'/akn/ma/act/{kind}/12-{k}', kind, december)
    issue(4340, date(1995, 12, 27), pages=10)
    issue(4445, date(1997, 1, 2), pages=10)
    issue(4363, date(1996, 3, 4), pages=99, edition=Edition.TRANSLATION_FR)
    out = months.count(meta)
    assert out == months.tabulate(meta, [(date(1996, 3, 4), '', '14 شوال 1416', 20, 4, 1, 1, 1),
                                         (date(1996, 12, 31), 'bis', '19 شعبان 1417', 300, 2, 1, 1, 0)])
    assert out['months'][0][2] == [1, 0, 20, 4] and out['months'][0][11] == [1, 1, 300, 2]
    assert out['kinds'] == {'laws': [0, 0, 1] + [0] * 8 + [1], 'decrees': [0, 0, 1] + [0] * 8 + [1], 'orders': [0, 0, 1] + [0] * 9}


def place(slug, kind, **fields):
    return Place.objects.create(slug=slug, kind=kind, name_ar=fields.pop('name_ar', slug), name_fr=fields.pop('name_fr', slug.title()),
                                **fields)


def mention(at, uri, day, *, kind='other', edition=Edition.GENERAL_AR, printed=True, old=False, form=''):
    return Mention.objects.create(place=at, uri=uri, date=day, issue='1', edition=edition, text_type='decree', kind=kind,
                                  form=form or at.name_ar, printed=printed, old=old)


def test_the_states_are_read_from_the_places_count_with_the_conventions_editions_texts_beside():
    """«العالم في الجريدة الرسمية»: the states and the gone ones (never a city), their years, the years' totals; a state's
    year with no text opens nothing; the conventions edition's texts as printed, each once."""
    meta = {'periods': [[1956, 1969], [2020, 2025]], 'moves': {'floor': 1, 'most': 3}}
    first = {'date': '1957-01-04', 'issue': '2306', 'edition': 'general_ar', 'page': 3, 'form': 'البرتغال', 'title': 'ظهير'}
    portugal = place('portugal', 'country', name_ar='البرتغال', name_en='Portugal', lat=39.5, lon=-8.0, region='Europe/Southern Europe',
                     texts=4, first=first, spellings=[{'form': 'البرتغال'}])
    france = place('france', 'country', name_ar='فرنسا', name_en='France', lat=46.7, lon=2.5, region='Europe', texts=5)
    soviet = place('soviet-union', 'gone', name_ar='الاتحاد السوفياتي', name_en='Soviet Union', successor='russia', texts=1)
    place('tuvalu', 'country', name_ar='توفالو', name_en='Tuvalu')
    taza = place('taza', 'city', name_ar='تازة', population=100)
    for at, year, n, kinds in ((portugal, 1960, 3, {'treaty': 3}), (portugal, 2021, 1, {'studies': 1}), (france, 1962, 5, {'treaty': 5}),
                               (france, 2021, 0, {}), (soviet, 1960, 1, {'treaty': 1}), (taza, 1960, 9, {'other': 9})):
        PlaceYear.objects.create(place=at, year=year, texts=n, kinds=kinds)
    for year, n, foreign in ((1960, 1000, 10), (1990, 50, 1), (2021, 2000, 20)):
        Year.objects.create(year=year, texts=n, foreign=foreign)
    for uri, edition, printed in (('/a', Edition.CONVENTIONS_AR, True), ('/a', Edition.CONVENTIONS_AR, True),
                                  ('/b', Edition.CONVENTIONS_AR, True), ('/c', Edition.CONVENTIONS_AR, False), ('/d', Edition.GENERAL_AR, True)):
        mention(portugal, uri, date(2021, 1, 1), edition=edition, printed=printed)
    fields = lambda p: {f: getattr(p, f) for f in countries.FIELDS}
    expected = countries.tabulate(meta, [fields(p) for p in (portugal, france, soviet, Place.objects.get(slug='tuvalu'))],
                                  [('portugal', 1960, 3, {'treaty': 3}), ('portugal', 2021, 1, {'studies': 1}),
                                   ('france', 1962, 5, {'treaty': 5}), ('france', 2021, 0, {}), ('soviet-union', 1960, 1, {'treaty': 1})],
                                  [(1960, 1000, 10), (1990, 50, 1), (2021, 2000, 20)])
    out = countries.count(meta)
    assert out == {**expected, 'totals': {**expected['totals'], 'conventions': 2}}
    by = {s['slug']: s for s in out['states']}
    # France's 2021 holds no text: its first year in the span is 1962, its last 2021.
    assert by['france']['c'] == [5, 0] and by['france']['last'] == 2021 and by['france']['first'] is None
    assert by['portugal']['first']['year'] == 1957 and out['climb']['counts'][1957 - 1956] == 1
    assert out['texts'] == [1000, 2000] and out['totals']['never'] == 1


def test_a_city_counts_with_its_province_and_shows_its_old_name_as_the_bulletin_printed_it_most():
    """«المغرب في الجريدة الرسمية»: a city's texts as printed with its province's (each once), a period at a time; its old
    name shown as most printed, a clinging «ب» dropped only when what is left is the old name; the French zone's titles
    before 1956."""
    meta = {'periods': [[1956, 1969], [2020, 2025]], 'moves': {'floor': 1, 'most': 3}, 'people_floor': 1}
    first = {'date': '1957-02-01', 'issue': '2310', 'page': 4, 'form': 'القنيطرة'}
    kenitra = place('kenitra', 'city', name_ar='القنيطرة', lat=34.2, lon=-6.6, population=20000, old=['بور ليوطي'], first=first)
    taza = place('taza', 'city', name_ar='تازة', population=100, old=['تازه العليا'])
    province = place('taza-province', 'province', name_ar='إقليم تازة', town='taza', population=50000)
    jadida = place('el-jadida', 'city', name_ar='الجديدة', population=10, old=['مازاغان'])
    # Its list holds «بتي جان» and, as printed once, «تي جان»: the «ب» of «بتي جان» is its own first letter all the same.
    kacem = place('sidi-kacem', 'city', name_ar='سيدي قاسم', population=10, old=['بتي جان', 'تي جان'])
    place('ifrane', 'city', name_ar='إفران', population=10)                               # never named
    loose = place('loose-province', 'province', name_ar='إقليم', town='', population=10)
    france = place('france', 'country', name_ar='فرنسا')
    # Printed joined twice, as listed once: the joined form is shown, whole (what follows its «ب» is no old name).
    mention(kenitra, '/c', date(1965, 1, 1), kind='other', old=True, form='بور ليوطي')
    mention(kenitra, '/a', date(1960, 1, 1), kind='land', old=True, form='بورليوطي')
    mention(kenitra, '/b', date(1962, 1, 1), kind='land', old=True, form='بورليوطي')
    mention(kenitra, '/d', date(2021, 1, 1), kind='courts')
    mention(kenitra, '/e', date(1990, 1, 1))                                               # between the periods
    mention(kenitra, '/f', date(2022, 1, 1), printed=False)                                # its newest version only
    mention(taza, '/g', date(1960, 1, 1), kind='land')
    mention(province, '/g', date(1960, 1, 1), kind='land')                                 # the same text, once
    mention(province, '/h', date(2021, 1, 1), kind='courts')
    mention(province, '/i', date(1961, 1, 1), old=True, form='تازة العليا')
    mention(jadida, '/j', date(1958, 1, 1), old=True, form='بمازاغان')
    mention(kacem, '/k', date(1957, 1, 1), old=True, form='بتي جان')
    mention(loose, '/l', date(1960, 1, 1))
    mention(france, '/m', date(1960, 1, 1))
    for y, n in ((1960, 1000), (1990, 500), (2021, 2000)):
        Year.objects.create(year=y, texts=n, foreign=0)
    zone = ('ظهير شريف في شأن الأسواق بالمنطقة الفرنسوية من الايالة الشريفة', 'قرار وزيري بالمنطقة الفرنسية')
    for k, (year, title, edition) in enumerate(((1950, zone[0], Edition.GENERAL_AR), (1951, zone[1], Edition.GENERAL_AR),
                                                (1960, zone[0], Edition.GENERAL_AR), (1950, zone[0], Edition.TRANSLATION_FR),
                                                (1950, 'ظهير شريف في شأن الأسواق', Edition.GENERAL_AR))):
        text(f'/akn/ma/act/dahir/z-{k}', TextType.DAHIR, issue(500 + k, date(year, 1, 1), edition=edition), title=title)
    city = lambda slug, ar, n, c, s, kinds, old, pop, lat=None, lon=None, first=None: {
        'slug': slug, 'ar': ar, 'fr': slug.title(), 'lat': lat, 'lon': lon, 'pop': pop, 'n': n, 'c': c, 's': s, 'kinds': kinds,
        'old': old, 'first': first}
    assert cities.count(meta) == {
        'periods': [[1956, 1969], [2020, 2025]], 'texts': [1000, 2000],
        'cities': [city('kenitra', 'القنيطرة', 4, [3, 1], [3.0, 0.5], {'land': 2, 'other': 1, 'courts': 1},
                        {'forms': ['بورليوطي', 'بور ليوطي'], 'c': [3, 0]}, 20000, 34.2, -6.6,
                        {'year': 1957, 'date': '1957-02-01', 'issue': '2310', 'page': 4, 'form': 'القنيطرة'}),
                   # Its old name was printed only under its province's: shown as the list holds it.
                   city('taza', 'تازة', 3, [2, 1], [2.0, 0.5], {'land': 1, 'courts': 1, 'other': 1},
                        {'forms': ['تازه العليا'], 'c': [1, 0]}, 50000),
                   city('el-jadida', 'الجديدة', 1, [1, 0], [1.0, 0], {'other': 1}, {'forms': ['مازاغان', 'مازاغان'], 'c': [1, 0]}, 10),
                   city('sidi-kacem', 'سيدي قاسم', 1, [1, 0], [1.0, 0], {'other': 1},
                        {'forms': ['بتي جان', 'بتي جان', 'تي جان'], 'c': [1, 0]}, 10)],
        'moves': {'rose': [], 'fell': []},
        'five': {'slugs': ['kenitra', 'taza', 'el-jadida', 'sidi-kacem'], 'top': [7.0, 1.0], 'rest': [0, 0]},
        'people': [{'slug': 'kenitra', 'v': 0.5}, {'slug': 'taza', 'v': 0.2}],
        'people_low': [{'slug': 'kenitra', 'v': 0.5}, {'slug': 'taza', 'v': 0.2}],
        'totals': {'cities': 4, 'texts': 3000, 'zone': 2},
    }


@pytest.mark.parametrize('title, sorted_as', [
    # Neither publishing nor approving, with a state named: abroad, but no treaty.
    ('مرسوم يتعلق بتطبيق الاتفاق المبرم بين المغرب والبرتغال', {'group': 'states', 'partner': 'portugal', 'what': 'other'}),
    # A loan approved with no lender named: the banks'.
    ('مرسوم بالموافقة على عقد القرض المبرم مع مقرض أجنبي',
     {'group': 'lenders', 'partner': 'banks', 'what': 'money', 'kind': 'loan', 'borrower': None}),
])
def test_an_agreement_is_sorted_by_what_its_title_does(title, sorted_as):
    assert agreements.sort(TextType.DECREE, title) == sorted_as
