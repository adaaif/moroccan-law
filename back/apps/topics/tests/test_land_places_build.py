"""`build_land_places` (the land review, M8–M9): the BO's land texts since 2019, each read from its newest Arabic
version into a place's entry and its table's rows, every earlier reading replaced; and the finder's words when the
phrase as typed is nowhere."""
import datetime

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document, Issue
from apps.sources.services.compare import fold
from apps.topics.models import Parcel, PlaceText

pytestmark = pytest.mark.django_db

EXPROPRIATION = ('مرسوم رقم 2.99.900 بإعلان أن المنفعة العامة تقضي بإحداث إعدادية الأمل بجماعة واد المثال بإقليم '
                 'النموذج وبنزع ملكية القطع الأرضية اللازمة لهذا الغرض')
TABLE = '''| رقم القطعة | تعيين الملك ومرجعه العقاري | أسماء الملاك وعناوينهم | المساحة بالمتر المربع | ملاحظات |
|---|---|---|---|---|
| 2 | الملك المدعو "الضيعة" ذي الرسم العقاري عدد F/12345 | - فلانة بنت فلان<br>- فلان بن فلان<br>الساكنون بواد المثال | 2766 | تقييد<br>احتياطي |
| المجموع | | | 2790 | |
| 4 | قطعة أرضية غير محفظة | فلان | 24 | |
| 6 | قطعة من الملك الغابوي | | 12 | |'''


def issue(number, day, suffix=''):
    scan = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{number}{suffix}'.ljust(64, '0'),
                                   path=f'bo/{number}{suffix}.pdf', mime='application/pdf', bytes=1, language='ar',
                                   fetched_at=timezone.now())
    return Issue.objects.create(edition='general_ar', number=number, suffix=suffix, date=day, document=scan)


def text(uri, title, published, type='decree', versions=()):
    t = Text.objects.create(akn_uri=uri, type=type, number=uri.rsplit('/', 1)[1], title_ar=title,
                            first_published_in=published)
    for language, valid_from, bodies in versions:
        v = Version.objects.create(text=t, language=language, valid_from=valid_from,
                                   consolidation=Consolidation.AS_PUBLISHED)
        # Created last to first: the articles are read in their order, not their rows'.
        Article.objects.bulk_create(Article(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                                            body=body, printed_page=page)
                                    for n, (body, page) in reversed(list(enumerate(bodies, 1))))
    return t


def test_the_land_texts_since_2019_are_read_again_into_places_and_plots(capsys):
    PlaceText.objects.create(uri='/akn/ma/act/decret/2-18-1', kind='road', date=datetime.date(2019, 2, 1), title='قديم')
    Parcel.objects.create(uri='/akn/ma/act/decret/2-18-1', row=0, owners='فلان')
    week, bis, old = (issue(7551, datetime.date(2026, 10, 12)), issue(7552, datetime.date(2026, 10, 15), 'bis'),
                      issue(6700, datetime.date(2018, 12, 27)))
    # The delimitation first: the kinds are said by their counts, not as they came.
    text('/akn/ma/act/decret/2-99-902', 'مرسوم رقم 2.99.902 بالمصادقة على عملية التحديد الإداري رقم 1365 بجماعة الوادي',
         week)
    text('/akn/ma/act/decret/2-99-900', EXPROPRIATION, week, versions=[
        ('ar', datetime.date(2026, 1, 1), [('نص قديم', 7000)]),
        ('ar', datetime.date(2026, 10, 12), [('يعلن أن المنفعة العامة تقضي بذلك.\n| الأجل | سنتان |', None),
                                             ('تنزع ملكية القطع المبينة في الجدول أسفله:\n' + TABLE, 7588),
                                             ('ينشر هذا المرسوم بالجريدة الرسمية.', 7589)]),
        ('fr', datetime.date(2026, 10, 13), [('Est déclarée d’utilité publique…', 9000)])])
    text('/akn/ma/act/arrete/1-99-901', 'قرار بنزع ملكية قطعة أرضية بجماعة واد المثال', bis, type='order')
    text('/akn/ma/act/decret/2-99-903', 'مرسوم رقم 2.99.903 بتعيين أعضاء المجلس', week)            # not land
    text('/akn/ma/act/decret/2-18-904', 'مرسوم بنزع ملكية قطعة أرضية بجماعة القديمة', old)       # before 2019
    text('/akn/ma/act/loi/99-05', 'قانون يتعلق بنزع الملكية لأجل المنفعة العامة', week, type='law')   # a law

    call_command('build_land_places')

    assert capsys.readouterr().out.splitlines() == ['3 texts, 3 rows', '  expropriation: 2', '  delimitation: 1']
    places = {p.uri: p for p in PlaceText.objects.all()}
    assert sorted(places) == ['/akn/ma/act/arrete/1-99-901', '/akn/ma/act/decret/2-99-900', '/akn/ma/act/decret/2-99-902']
    p = places['/akn/ma/act/decret/2-99-900']
    assert (p.kind, p.date, p.issue, p.page, p.title, p.rows) == (
        'expropriation', datetime.date(2026, 10, 12), '7551', 7588, EXPROPRIATION, 3)
    assert (p.communes, p.provinces, p.properties, p.refs) == (['واد المثال'], ['النموذج'], ['الضيعة'], ['f12345'])
    assert p.search.startswith(fold(EXPROPRIATION)) and fold('فلانة بنت فلان') in p.search and 'f12345' in p.search
    q = places['/akn/ma/act/arrete/1-99-901']
    assert (q.kind, q.issue, q.page, q.rows, q.communes) == ('expropriation', '7552-bis', None, 0, ['واد المثال'])
    assert places['/akn/ma/act/decret/2-99-902'].kind == 'delimitation'
    rows = [(r.uri, r.row, r.plot, r.property, r.ref, r.area, r.owners, r.owners_count, r.notes)
            for r in Parcel.objects.order_by('uri', 'row')]
    assert rows == [
        ('/akn/ma/act/decret/2-99-900', 0, '2', 'الملك المدعو "الضيعة" ذي الرسم العقاري عدد F/12345', 'f12345', '2766',
         'فلانة بنت فلان\nفلان بن فلان\nالساكنون بواد المثال', 2, 'تقييد\nاحتياطي'),
        ('/akn/ma/act/decret/2-99-900', 1, '4', 'قطعة أرضية غير محفظة', '', '24', 'فلان', 1, ''),
        ('/akn/ma/act/decret/2-99-900', 2, '6', 'قطعة من الملك الغابوي', '', '12', '', 0, ''),      # no owner named
    ]


def test_a_title_outside_the_lands_formulas_is_no_place():
    from types import SimpleNamespace

    from apps.topics.services import places
    assert places.read(SimpleNamespace(title_ar='مرسوم رقم 2.99.903 بتعيين أعضاء المجلس'), []) is None


def test_words_typed_apart_find_the_texts_that_hold_each_when_the_phrase_is_nowhere(api):
    for n, communes in enumerate((['واد المثال'], ['الوادي'])):
        PlaceText.objects.create(uri=f'/akn/ma/act/decret/2-99-{900 + n}', kind='expropriation',
                                 date=datetime.date(2026, 10, 1 + n), title=EXPROPRIATION, communes=communes,
                                 search=fold(EXPROPRIATION + ' ' + ' '.join(communes)))
    found = api.get('/api/topics/land/places/', {'q': 'المثال إعدادية'}).json()
    assert found['count'] == 2 and found['place'] is None
    one = api.get('/api/topics/land/places/', {'q': 'المثال الوادي'}).json()
    assert one['count'] == 1 and [t['path'] for t in one['texts']] == ['/ma/decret/2-99-901']
    assert api.get('/api/topics/land/places/', {'q': 'المثال طنجة'}).json()['count'] == 0


def test_the_phrase_as_typed_wins_over_its_words_apart(api):
    # «رباط الخير» is a commune; «الخير» near «الرباط» in another text is not it.
    for n, words in enumerate(('مرسوم بجماعة رباط الخير', 'مرسوم لفائدة الخير بعمالة الرباط')):
        PlaceText.objects.create(uri=f'/akn/ma/act/decret/2-99-{900 + n}', kind='expropriation',
                                 date=datetime.date(2026, 10, 1 + n), title=words, search=fold(words))
    found = api.get('/api/topics/land/places/', {'q': 'رباط الخير'}).json()
    assert found['count'] == 1 and [t['path'] for t in found['texts']] == ['/ma/decret/2-99-900']
