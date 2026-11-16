"""«أرضي فالجريدة الرسمية» (the land review, M8–M10): a land text read as a place's entry, its table as plots."""
from types import SimpleNamespace

import pytest

from apps.topics.services import places

# A topic is its folder's files and the checks a person recorded, which live in the database.
pytestmark = pytest.mark.django_db

TITLE = ('مرسوم رقم 2.99.900 بإعلان أن المنفعة العامة تقضي بإحداث إعدادية الأمل بجماعة واد المثال بإقليم النموذج '
         'وبنزع ملكية القطع الأرضية اللازمة لهذا الغرض')
TABLE = '''تنزع ملكية القطع الأرضية الكائنة بجماعة واد المثال بإقليم النموذج، المبينة في الجدول أسفله:
| رقم انقطعة بالتصميم | تعيين الملك ومرجعه العقاري | أسماء الملاك والملاك المفترضين وعناوينهم | المساحة بالمتر المربع | ملاحظات |
|---|---|---|---|---|
| 2 | قطعة أرضية تابعة للملك المسمى "الضيعة" ذي الرسم العقاري عدد F/12345 | - فلانة بنت فلان<br>- فلان بن فلان<br>الساكنون جميعا بباشوية واد المثال | 2766 | -تقييد احتياطي بمقتضى مقال |
| 4 | قطعة أرضية غير محفظة | فلان او فلان | 24 | |'''


def article(body, page=7588):
    return SimpleNamespace(body=body, printed_page=page)


def test_a_title_says_its_kind_by_its_own_formula():
    assert places.kind_of(TITLE) == 'expropriation'
    assert places.kind_of('مرسوم رقم 2.99.976 بتجديد إعلان المنفعة العامة التي تقضي ببناء سد واد المثال بإقليم النموذج') == 'renewal'
    assert places.kind_of('قرار لرئيس مجلس جماعة واد المثال بتخطيط حدود الطرق العامة … المراد نزع ملكيتهما') == 'road'
    assert places.kind_of('مرسوم رقم 2.99.953 بالمصادقة على عملية التحديد الإداري رقم 1365') == 'delimitation'
    # A temporary works unit for a dam («إعداد مؤقت») is not a temporary occupation of land.
    assert places.kind_of('قرار لوزير التجهيز والماء رقم 1112.23 بإحداث إعداد مؤقت لورش سد واد المثال بإقليم النموذج') is None


def test_a_text_names_its_commune_province_numbers_and_plots():
    entry = places.read(SimpleNamespace(title_ar=TITLE), [article('يعلن أن المنفعة العامة تقضي …'), article(TABLE)])
    assert entry['communes'] == ['واد المثال'] and entry['provinces'] == ['النموذج']
    assert entry['refs'] == ['f12345'] and entry['page'] == 7588
    first, second = entry['rows']
    assert (first['plot'], first['ref'], first['area'], first['owners_count']) == ('2', 'f12345', '2766', 2)
    assert 'تقييد احتياطي' in first['notes'] and second['property'] == 'قطعة أرضية غير محفظة'


def test_a_province_is_its_name_not_the_verb_after_it():
    assert places._province('النموذج يجدد') == 'النموذج'
    assert places._province('سيدي قاسم') == 'سيدي قاسم'
    assert places._province('الفحص - أنجرة') == 'الفحص - أنجرة'
    assert places.compact('F / 12345') == 'f12345'


def test_the_finder_answers_a_commune_a_number_or_a_name_in_a_fixed_number_of_queries(api, db, django_assert_max_num_queries):
    import datetime
    from apps.topics.models import Parcel, PlaceText
    for n in range(8):
        uri = f'/akn/ma/act/decret/2-99-{900 + n}'
        entry = places.read(SimpleNamespace(title_ar=TITLE), [article(TABLE)])
        PlaceText.objects.create(uri=uri, kind=entry['kind'], date=datetime.date(2026, 10, 1 + n), issue='7551', page=7588,
                                 title=TITLE, communes=entry['communes'], provinces=entry['provinces'], refs=entry['refs'],
                                 search=entry['search'], rows=len(entry['rows']))
        Parcel.objects.bulk_create([Parcel(uri=uri, row=i, **r) for i, r in enumerate(entry['rows'])])
    with django_assert_max_num_queries(4):
        out = api.get('/api/topics/land/places/', {'q': 'واد المثال'}).json()
    assert out['count'] == 8 and out['place'] == {'commune': 'واد المثال', 'since': 2026}
    assert out['texts'][0]['path'] == '/ma/decret/2-99-907'
    by_number = api.get('/api/topics/land/places/', {'q': 'F/12345'}).json()
    assert by_number['count'] == 8 and [r['ref'] for r in by_number['texts'][0]['rows']] == ['f12345']
    # C2 «names»: a name as printed in the table finds the row that holds it.
    by_name = api.get('/api/topics/land/places/', {'q': 'فلانة'}).json()
    assert by_name['count'] == 8 and by_name['texts'][0]['rows'][0]['owners_count'] == 2


def test_a_followed_commune_hears_of_its_land_texts(api, db):
    import datetime
    from apps.topics.models import PlaceText
    entry = places.read(SimpleNamespace(title_ar=TITLE), [article(TABLE)])
    PlaceText.objects.create(uri='/akn/ma/act/decret/2-99-900', kind='expropriation', date=datetime.date(2026, 10, 12),
                             issue='7551', title=TITLE, communes=entry['communes'], search=entry['search'])
    news = api.get('/api/follows/news/', {'path': '/places/واد المثال'}).json()['news'][0]
    assert news['kind'] == 'place' and [i['key'] for i in news['items']] == ['place:/ma/decret/2-99-900']
