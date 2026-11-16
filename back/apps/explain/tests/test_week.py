"""/new drawn again from the newest issues (1 Nov 2026): a week brings every text, the special section's too; a series of
texts of one form is folded by its title alone; a text that makes rules opens on its first article as printed; the
weeks around it come for stepping by sight; and the answer costs the same whatever the week holds."""
import datetime

import pytest

from apps.corpus.models import Article, Consolidation, Mention, Text, Version
from apps.explain.services import series
from apps.explain.services.week import week
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db

# BO 7555 (26 Oct 2026) and 7555 bis, as printed.
POWERS = ['مرسوم رقم 2.26.814 يتعلق باختصاصات وزير الداخلية',
          'مرسوم رقم 2.26.816 صادر في 14 من جمادى الأولى 1448 (26 أكتوبر 2026) يتعلق باختصاصات وزير العدل',
          'مرسوم رقم 2.26.818 يتعلق باختصاصات الأمين العام للحكومة',
          'مرسوم رقم 2.26.828 صادر في 14 من جمادى الأولى 1448 (26 أكتوبر 2026) يتعلق باختصاصات وزيرة الطاقة والمعادن والتنمية المستدامة',
          'مرسوم يتعلق باختصاصات وزير التعليم العالي والبحث العلمي والابتكار']
ALONE = 'مرسوم رقم 2.26.834 بتفويض بعض الاختصاصات والسلط إلى الوزيرة المنتدبة لدى رئيسة الحكومة'


def rows(titles, numbers=None):
    return [{'title': t, 'number': (numbers or [''] * len(titles))[i]} for i, t in enumerate(titles)]


def test_a_series_is_its_shared_words_and_each_member_what_differs():
    r = rows(POWERS + [ALONE])
    found = series.fold(r, general=True)
    assert list(found.values()) == [{'head': 'مرسوم يتعلق باختصاصات', 'size': 5, 'issuers': []}]
    assert [x.get('part', '') for x in r] == ['وزير الداخلية', 'وزير العدل', 'الأمين العام للحكومة',
                                      'وزيرة الطاقة والمعادن والتنمية المستدامة',
                                      'وزير التعليم العالي والبحث العلمي والابتكار', '']
    assert r[-1].get('series') is None


def test_the_general_section_folds_only_a_long_series_or_one_that_shares_its_act():
    # Three decrees «بتغيير المرسوم» on three subjects keep their own rows; three orders creating collective
    # land-registration zones, issuer printed once, fold.
    changes = ['مرسوم رقم 2.26.1 بتغيير المرسوم رقم 2.04.89 بتحديد اختصاص المؤسسات الجامعية',
               'مرسوم رقم 2.26.2 بتغيير المرسوم رقم 2.17.362 يتعلق بالجائزة الوطنية',
               'مرسوم رقم 2.26.3 بتغيير المرسوم رقم 2.22.431 يتعلق بالصفقات العمومية']
    assert series.fold(rows(changes), general=True) == {}
    zones = ['قرار لوزير الفلاحة والصيد البحري يقضي بإحداث وتحديد منطقة للتحفيظ الجماعي بجماعة تديلي مسفيوة',
             'قرار لوزير الفلاحة والصيد البحري يقضي بإحداث وتحديد منطقة للتحفيظ الجماعي بجماعة انشادن',
             'قرار يقضي بإحداث وتحديد منطقة للتحفيظ الجماعي بجماعة آيت سعيد']
    r = rows(zones)
    assert [s['head'] for s in series.fold(r, general=True).values()] == \
        ['قرار وزير الفلاحة والصيد البحري يقضي بإحداث وتحديد منطقة للتحفيظ الجماعي بجماعة']
    assert [x['part'] for x in r] == ['تديلي مسفيوة', 'انشادن', 'آيت سعيد']


def test_the_special_section_folds_across_the_hands_that_signed():
    titles = ['قرار لرئيسة الحكومة رقم 2049.26 بتفويض الإمضاء'] * 3 + \
             ['قرار للأمين العام للحكومة رقم 2100.26 بتفويض الإمضاء', 'قرار للمدير العام للأمن الوطني بتفويض الإمضاء',
              # «عدد … /ق/2026» and «لمجلس» are the same Council's
              'قرار لمجلس المنافسة المتعلق بتولي شركة «Covestro AG» المراقبة الحصرية',
              'قرار مجلس المنافسة عدد 144/ق/2026 المتعلق بتولي شركة «GDI Simulation» المراقبة الحصرية',
              'قرار لمجلس المنافسة المتعلق بتولي المراقبة المشتركة لشركة «Portnet SA»',
              # «للسيدة» licenses as «للسيد» does
              'مقرر يرخص للسيدة سلمى الادريسي بحمل صفة مهندس معماري', 'مقرر يرخص للسيد محمد فواسي بحمل صفة مهندس معماري',
              'مقرر يرخص للسيدة نهيلة وشاك بحمل صفة مهندس معماري']
    found = series.fold(rows(titles), general=False)
    assert [(s['head'], s['size'], [(i['name'], i['count']) for i in s['issuers']]) for s in found.values()] == [
        ('قرار بتفويض الإمضاء', 5, [('رئيسة الحكومة', 3), ('الأمين العام للحكومة', 1), ('المدير العام للأمن الوطني', 1)]),
        ('قرار مجلس المنافسة المتعلق بتولي', 3, []),
        ('مقرر يرخص للسيد', 3, []),
    ]


@pytest.fixture
def bulletin():
    """A week of two issues: five decrees of a series, a decree applying a law, a dahir naming a government (its first
    article a table), the special section's delegations; and an issue a week before."""
    Issue.objects.create(edition=Edition.GENERAL_AR, number=7553, date=datetime.date(2026, 10, 19))
    i1 = Issue.objects.create(edition=Edition.GENERAL_AR, number=7555, date=datetime.date(2026, 10, 26),
                              hijri_date='14 جمادى الأولى 1448', first_page_number=7867)
    i2 = Issue.objects.create(edition=Edition.GENERAL_AR, number=7555, suffix='bis', date=datetime.date(2026, 10, 27),
                              first_page_number=7889)
    law = Text.objects.create(akn_uri='/akn/ma/act/loi/59-24', type='law', number='59-24',
                              title_ar='قانون رقم 59.24 يتعلق بالتعليم العالي والبحث العلمي')
    for k, title in enumerate(POWERS):
        Text.objects.create(akn_uri=f'/akn/ma/act/decret/2-26-{814 + k}', type='decree', title_ar=title,
                            number_as_printed=f'2.26.{814 + k}', first_published_in=i1, first_published_page=7869 + k)
    applying = Text.objects.create(akn_uri='/akn/ma/act/decret/2-26-326', type='decree', first_published_in=i2,
                                   title_ar='مرسوم رقم 2.26.326 بتطبيق أحكام المواد 30 و42 من القانون رقم 59.24',
                                   first_published_page=7892)
    Mention.objects.create(from_uri=applying.akn_uri, words='القانون رقم 59.24', kind=Mention.Kind.APPLIES,
                           to_uri=law.akn_uri, state=Mention.State.RESOLVED)
    dahir = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-26-91', type='dahir', first_published_in=i1,
                                title_ar='ظهير شريف رقم 1.26.91 بتعيين أعضاء الحكومة', first_published_page=7868)
    for t, body in ((applying, 'تطبيقا لأحكام المواد 30 و42 من القانون المشار إليه أعلاه رقم 59.24، يحدد هذا المرسوم ما يلي'),
                    (dahir, 'يعين ابتداء من 4 جمادى الأولى 1448 (16 أكتوبر 2026) :\n| السيد عبد الوافي لفتيت | وزيرا للداخلية ؛ |')):
        v = Version.objects.create(text=t, language='ar', valid_from=t.first_published_in.date, consolidation=Consolidation.AS_PUBLISHED)
        Article.objects.create(version=v, order=2, label='المادة الثانية', number='2', eid='art_2', body='ينشر في الجريدة الرسمية.')
        Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body=body)
    for k in range(3):
        Text.objects.create(akn_uri=f'/akn/ma/act/arrete/{2049 + k}-26', type='decision', bo_section='special',
                            title_ar=f'قرار لرئيسة الحكومة رقم {2049 + k}.26 بتفويض الإمضاء', first_published_in=i2,
                            first_published_page=7950 + k)
    return {'i1': i1, 'i2': i2}


def test_the_week_brings_every_text_its_series_and_the_first_words_of_what_makes_rules(bulletin, api):
    w = api.get('/api/explain/week/').json()
    assert (w['from'], w['to'], w['prev'], w['next']) == ('2026-10-26', '2026-11-01', '2026-10-19', None)
    assert [(i['key'], i['hijri'], i['first_page'], i['special']) for i in w['issues']] == \
        [('7555-bis', '', 7889, 3), ('7555', '14 جمادى الأولى 1448', 7867, 0)]
    # The Bulletin's order: by day, then by page.
    assert [x['number'] or x['path'] for x in w['rest']][:2] == ['/ma/dahir/1-26-91', '2.26.814']
    by = {x['path']: x for x in w['rest']}
    assert by['/ma/dahir/1-26-91']['first'] == {
        'label': 'المادة الأولى', 'body': 'يعين ابتداء من 4 جمادى الأولى 1448 (16 أكتوبر 2026) :\n| السيد عبد الوافي لفتيت | وزيرا للداخلية ؛ |'}
    assert by['/ma/decret/2-26-326']['applies'] == [{'path': '/ma/loi/59-24', 'name': {
        'ar': 'قانون رقم 59.24 يتعلق بالتعليم العالي والبحث العلمي', 'fr': 'قانون رقم 59.24 يتعلق بالتعليم العالي والبحث العلمي'}}]
    # A member of a series is named in it, never opened on its words.
    powers = [x for x in w['rest'] if x['series']]
    assert len(powers) == 5 and {x['first'] for x in powers} == {None}
    assert w['series'][powers[0]['series']]['head'] == 'مرسوم يتعلق باختصاصات'
    assert [x['part'] for x in w['special_texts']] == [''] * 3 and w['special_texts'][0]['series']
    # The weeks around it, oldest first, the last this one.
    assert len(w['weeks']) == 13 and w['weeks'][-1] == {'from': '2026-10-26', 'issues': 2, 'pages': 0}
    assert w['weeks'][-2]['issues'] == 1


def test_the_week_costs_the_same_whatever_it_holds(bulletin, django_assert_max_num_queries):
    with django_assert_max_num_queries(14):
        few = week(datetime.date(2026, 10, 26))
    for k in range(40):
        Text.objects.create(akn_uri=f'/akn/ma/act/decret/2-26-{900 + k}', type='decree', first_published_in=bulletin['i2'],
                            title_ar=f'مرسوم رقم 2.26.{900 + k} بالموافقة على اتفاق القرض رقم {k}', first_published_page=7990 + k)
    with django_assert_max_num_queries(14):
        many = week(datetime.date(2026, 10, 26))
    assert len(many['rest']) == len(few['rest']) + 40


@pytest.mark.parametrize('title', ['إعلان عن مباراة لتوظيف متصرفين من الدرجة الثانية',   # no word opens an act
                                   'قرار لوزير الفلاحة رقم 2.26 بالموافقة'])              # the act is one word
def test_titles_with_no_act_of_two_words_are_no_series(title):
    r = rows([title] * 5)
    assert series.fold(r, general=True) == {} and [x.get('series') for x in r] == [None] * 5


def test_a_text_that_cites_itself_is_not_said_to_apply_itself(bulletin, api):
    applying = Text.objects.get(akn_uri='/akn/ma/act/decret/2-26-326')
    Mention.objects.create(from_uri=applying.akn_uri, words='هذا المرسوم', kind=Mention.Kind.APPLIES,
                           to_uri=applying.akn_uri, state=Mention.State.RESOLVED)
    by = {x['path']: x for x in api.get('/api/explain/week/').json()['rest']}
    assert [a['path'] for a in by['/ma/decret/2-26-326']['applies']] == ['/ma/loi/59-24']
