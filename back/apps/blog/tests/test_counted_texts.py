"""The posts whose figures are counted from the texts, their articles and the Bulletin's pages (posts 13 to 27 of
the first-principles review, and the words): each service's count over a small corpus with a row on each side of every rule it
applies, the whole figure asserted."""
from datetime import date

import pytest

from apps.blog.services import posts  # noqa: F401  first, as the site loads them: marquise reads the posts, which name it
from apps.blog.services import (absent, ages, clock, constitutions, deadlines, death, drinks, emergency, errata, expropriation,
                                marquise, ministry, speed, staples, strike, words)
from apps.corpus.models import Consolidation, Status, TextType
from apps.sources.models import Edition

from .rows import article, issue, page, text, version

pytestmark = pytest.mark.django_db
DECADES = list(range(1910, 2030, 10))


def decades(**n):
    """A count per decade from 1910, the decades named `d1980=2`."""
    return [n.get(f'd{d}', 0) for d in DECADES]


def test_a_word_counts_the_texts_of_law_that_carry_it_and_a_network_the_pages_that_print_it():
    """«القانون يعرف البرقية، ولا يعرف واتساب»: a machine's texts are the texts of law whose Arabic carries it (a model's
    translation, a French version and a circular do not count), the standing ones those not repealed; a network named in
    a text of law the meta does not set aside is a check, and so is a first page that is not the meta's."""
    old, mid = issue(2000, date(1985, 3, 6)), issue(6344, date(2015, 3, 19))
    new = issue(7218, date(2023, 8, 3), suffix='bis')
    french = issue(6344, date(2015, 3, 19), edition=Edition.TRANSLATION_FR)
    page(old, 0, 12, 'واتساب')                     # set aside by the meta: the 2015 page stays the first
    page(mid, 3, 457, 'والواتساب وتيك توك')
    page(mid, 4, 458, 'واتساب')
    page(new, 1, 9, 'واتساب')
    page(new, 2, 10, 'تيك توك')
    page(french, 3, 457, 'واتساب')
    version(text('/akn/ma/act/decret/2-85-1', TextType.DECREE, old), 'يرسل بالفاكس', 'عبر واتساب')
    # The newest names it in two articles: its address is the first of them.
    version(text('/akn/ma/act/arrete/10-15', TextType.ORDER, mid, status=Status.REPEALED), ('art_2', 'رقم الفاكس'), ('art_1', 'والفاكس'))
    version(text('/akn/ma/act/arrete/394-19', TextType.ORDER, mid), 'صفحة واتساب')       # a report the order swallowed
    version(text('/akn/ma/act/circulaire/1-23', TextType.CIRCULAR, new), 'الفاكس')
    translated = text('/akn/ma/act/decret/2-23-5', TextType.DECREE, new)
    version(translated, 'الفاكس', consolidation=Consolidation.TRANSLATION)
    version(translated, 'فاكس', language='fr', valid_from=date(2023, 9, 1))
    version(text('/akn/ma/act/loi/1-00', TextType.LAW), 'الفاكس')                         # Adala's, no issue: no decade
    organic = text('/akn/ma/act/loi-organique/1-00', TextType.ORGANIC_LAW, old)
    version(organic, 'يحدد بقانون«تنظيمي» ويحدد وبقانون\nتنظيمي آخر', 'لا شيء')
    version(organic, 'بقانون تنظيمي', consolidation=Consolidation.MACHINE)
    meta = {
        'rules': ['dahir', 'law', 'organic_law', 'decree_law', 'decree', 'order'],
        'machines': [{'key': 'fax', 're': 'فاكس', 'example': {'issue': 2000, 'page': 12, 'akn': '/akn/ma/act/decret/2-85-1', 'art': '1'}}],
        'generics': [{'key': 'internet', 're': 'الانترنت'}],
        'apps': [{'key': 'whatsapp', 're': 'واتساب', 'first': {'issue': 6344, 'page': 457, 'date': '2015-03-19'}},
                 {'key': 'tiktok', 're': 'تيك توك', 'first': {'issue': 7218, 'page': 1, 'date': '2023-08-03'}},
                 {'key': 'snapchat', 're': 'سناب شات', 'first': {'issue': 9999, 'page': 1, 'date': '2024-01-01'}}],
        'not_law': [{'akn': '/akn/ma/act/arrete/394-19', 'words': ['whatsapp']}],
        'not_pages': [{'word': 'whatsapp', 'issue': 2000, 'page': 12}, {'word': 'tiktok', 'issue': 6344, 'page': 457}],
        'clippings': [], 'mediator': {'reports': []},
        'naming': {'formula': {'issue': 2000, 'page': 12, 'akn': '/akn/ma/act/loi-organique/1-00', 'art': '7', 'phrase': 'بقانون تنظيمي'},
                   'law': {'issue': 6344, 'page': 458}},
        'cese': {'issue': 7218, 'bis': True, 'page': 10, 'title_page': 9},
        'telegraph': {'issue': 6344, 'page': 458},
    }
    at = lambda i, idx: f'/pages/{i.document_id}/{idx}'
    printed = lambda i, p, idx, number, day: {'issue': number, 'edition': 'general_ar', 'published': day, 'page': p,
                                              'viewer': at(i, idx) if idx is not None else None}
    assert absent.count(meta) == {
        'texts': {'m-fax': {**printed(old, 12, 0, '2000', '1985-03-06'), 'path': '/ma/decret/2-85-1'},
                  'a-whatsapp': {**printed(mid, 457, 3, '6344', '2015-03-19'), 'path': None},
                  'a-tiktok': {'path': None}, 'a-snapchat': {'path': None},
                  'n-formula': {**printed(old, 12, 0, '2000', '1985-03-06'), 'path': '/ma/loi-organique/1-00'},
                  'n-law': {**printed(mid, 458, 4, '6344', '2015-03-19'), 'path': None},
                  'cese': {**printed(new, 10, 2, '7218 bis', '2023-08-03'), 'path': None}, 'cese-title': {'path': None},
                  'telegraph': {**printed(mid, 458, 4, '6344', '2015-03-19'), 'path': None}},
        'articles': {'m-fax': '/ma/decret/2-85-1/art_1'},
        'decades': DECADES,
        'read': decades(d1980=2, d2010=2, d2020=1),
        'machines': [{'key': 'fax', 'texts': 3, 'standing': 2, 'newest': {'date': '2015-03-19', 'path': '/ma/arrete/10-15/art_1'},
                      'decades': decades(d1980=1, d2010=1)}],
        'generics': [{'key': 'internet', 'texts': 0, 'standing': 0, 'newest': None, 'decades': decades()}],
        'apps': [{'key': 'whatsapp', 'texts': 1, 'pages': 3, 'issues': 2, 'years': {2015: 2, 2023: 1},
                  'first': {'issue': '6344', 'page': 457, 'date': '2015-03-19'}},
                 {'key': 'tiktok', 'texts': 0, 'pages': 1, 'issues': 1, 'years': {2023: 1},
                  'first': {'issue': '7218 bis', 'page': 10, 'date': '2023-08-03'}},
                 {'key': 'snapchat', 'texts': 0, 'pages': 0, 'issues': 0, 'years': {}, 'first': None}],
        'formula': 2,
        'checks': [{'word': 'whatsapp', 'text': '/akn/ma/act/decret/2-85-1', 'eids': ['art_2']},
                   {'word': 'tiktok', 'first': {'issue': '7218 bis', 'page': 10, 'date': '2023-08-03'}}],
    }


def test_the_penal_code_is_drawn_article_by_article_and_a_death_the_meta_does_not_list_is_a_check():
    """«الإعدام في القانون المغربي»: Adala's Arabic copy of the code in its order, each article in the part its group starts;
    the clause naming the death penalty is its sentence, cut around the words when long; an article that names it and is not
    the meta's, or the meta's that no longer names it, is a check."""
    code = '/akn/ma/act/dahir/1-59-413'
    printing = issue(2640, date(1963, 6, 5), suffix='bis')
    page(printing, 3, 1254)
    penal = text(code, TextType.DAHIR, printing)
    adala = version(penal, consolidation=Consolidation.ADALA, valid_from=date(2024, 1, 1))
    # A sentence of 421 letters is cut around the words (260 before, 140 after), one of 420 is whole, one that starts with
    # them is cut from its start. Created before the articles they follow: the code's order counts.
    article(adala, 3, 'art_267', 'أ' * 300 + ' بالاعدام ' + 'ب' * 111)
    article(adala, 5, 'art_301', 'الإعدام ' + 'ج' * 412)
    article(adala, 6, 'art_310', 'بالاعدام ' + 'د' * 420)
    article(adala, 1, 'art_1', 'لا يسوغ مؤاخذة أحد')
    article(adala, 4, 'art_300', 'يعاقب بالحبس')
    article(adala, 2, 'art_16', 'العقوبات الجنائية الأصلية هي. الإعدام؛ السجن المؤبد.')
    # Only Adala's Arabic copy of this code is drawn: not the code as published, a French copy, or another text's copy.
    version(penal, ('art_20', 'الإعدام'))
    version(penal, ('art_20', 'la peine de mort, الإعدام'), consolidation=Consolidation.ADALA, language='fr', valid_from=date(2024, 1, 1))
    version(text('/akn/ma/act/dahir/1-58-100', TextType.DAHIR), ('art_20', 'الإعدام'), consolidation=Consolidation.ADALA)
    version(text('/akn/ma/act/dahir/1-56-270', TextType.DAHIR), 'الجيش')
    version(text('/akn/ma/act/dahir/1-59-380', TextType.DAHIR), ('art_2', 'المواد الغذائية'))
    version(text('/akn/ma/act/loi/22-01', TextType.LAW), ('art_606', 'ينفذ'))
    meta = {
        'code': {'akn': code, 'issue': 2640, 'bis': True},
        'groups': [{'from': 'art_1', 'key': 'general'}, {'from': 'art_267', 'key': 'state'}],
        'articles': [{'n': '16', 'page': 1254}, {'n': '392', 'page': 1300, 'issue': 5112, 'akn': '/akn/ma/act/loi/03-03'}],
        'others': {'military': {'issue': 2400, 'akn': '/akn/ma/act/dahir/1-56-270', 'arts': [{'n': '1', 'page': 5}]},
                   'railway': {'issue': 2400, 'page': 6, 'akn': '/akn/ma/act/dahir/1-61-100', 'art': '2'},
                   'food': {'issue': 2400, 'page': 7, 'akn': '/akn/ma/act/dahir/1-59-380'},
                   'victims': {'issue': 2400, 'page': 8}},
        'steps': [{'key': 'press', 'issue': 2400, 'page': 9, 'akn': '/akn/ma/act/loi/22-01', 'art': '606',
                   'was': {'issue': 2640, 'bis': True, 'page': 1500}}],
        'cndh': {'years': [{'year': 2020, 'issue': 2400, 'page': 10}], 'halt': {'issue': 2400, 'page': 11},
                 'pardons': {'issue': 2400, 'page': 12}, 'vote': {'issue': 2400, 'page': 13}},
    }
    in_1963 = {'issue': '2640 bis', 'edition': 'general_ar', 'published': '1963-06-05', 'path': '/ma/dahir/1-59-413'}
    assert death.count(meta) == {
        'texts': {'p-16': {**in_1963, 'page': 1254, 'viewer': f'/pages/{printing.document_id}/3'},
                  'p-392': {'path': None}, 'm-1': {'path': '/ma/dahir/1-56-270'}, 'railway': {'path': None},
                  'food': {'path': '/ma/dahir/1-59-380'}, 'victims': {'path': None}, 's-press': {'path': '/ma/loi/22-01'},
                  'w-press': {**in_1963, 'page': 1500, 'viewer': None},
                  'c-2020': {'path': None}, 'c-halt': {'path': None}, 'c-pardons': {'path': None}, 'c-vote': {'path': None}},
        'cells': [{'n': '1', 'g': 'general'}, {'n': '16', 'g': 'general', 'clause': 'الإعدام؛'},
                  {'n': '267', 'g': 'state', 'clause': '… ' + 'أ' * 258 + ' بالاعدام ' + 'ب' * 111 + ' …'},
                  {'n': '300', 'g': 'state'}, {'n': '301', 'g': 'state', 'clause': 'الإعدام ' + 'ج' * 412},
                  {'n': '310', 'g': 'state', 'clause': '… بالاعدام ' + 'د' * 132 + ' …'}],
        # The military code's art. 1 and the procedure's art. 606 are on the site; the food dahir's art. 1 is not (its art. 2
        # is), nor the railway dahir.
        'articles': {'m-1': '/ma/dahir/1-56-270/art_1', 's-press': '/ma/loi/22-01/art_606'},
        'checks': [{'article': '267', 'why': 'names the death penalty, not in the meta'},
                   {'article': '301', 'why': 'names the death penalty, not in the meta'},
                   {'article': '310', 'why': 'names the death penalty, not in the meta'},
                   {'article': '392', 'why': 'in the meta, but its words no longer name the death penalty'}],
    }


def test_expropriations_are_counted_by_year_and_purpose_and_each_purposes_last_since_2020_is_its_example():
    """«نزع الملكية»: a title that declares the public good and takes land, in the Arabic general edition and the post's
    span; its purpose read after «تقضي ب…»; the example the last declaration of each purpose since 2020 with a page."""
    before, start = issue(6700, date(2018, 8, 2)), issue(6800, date(2019, 8, 1))
    y21, y22, y24 = issue(6950, date(2021, 1, 7)), issue(7100, date(2022, 6, 2)), issue(7300, date(2024, 5, 2))
    y23 = issue(7218, date(2023, 8, 3), suffix='bis')
    page(y23, 1, 20)
    good = 'مرسوم بإعلان أن المنفعة العامة تقضي '
    # The last water declaration is created first: the last is the Bulletin's, not the rows'.
    text('/akn/ma/act/decret/2-23-5', TextType.DECREE, y23, title=good + 'ببناء سد واد  اخفمان وبنزع ملكية القطع', page=20)
    text('/akn/ma/act/decret/2-21-4', TextType.DECREE, y21, title=good + 'ببناء سد تامري وبنزع ملكية', page=10)
    text('/akn/ma/act/decret/2-19-1', TextType.DECREE, start, title=good + 'بتوسيع ميناء طنجة وبنزع ملكية', page=5)
    # 2020 is the examples' first year: the airport's of January is its example, not its later one of 2020 with no page.
    january, november = issue(6850, date(2020, 1, 30)), issue(6930, date(2020, 11, 5))
    page(january, 0, 7)
    text('/akn/ma/act/decret/2-20-1', TextType.DECREE, january, title=good + 'بتوسيع مطار فاس وبنزع ملكية', page=7)
    text('/akn/ma/act/decret/2-20-2', TextType.DECREE, november, title=good + 'بتوسيع مطار وجدة وبنزع ملكية')
    text('/akn/ma/act/decret/2-21-2', TextType.DECREE, y21, title=good + 'بتهيئة الطريق الجهوية رقم 315 وبنزع ملكية', page=55)
    text('/akn/ma/act/decret/2-22-3', TextType.DECREE, y22, title=good + 'بتوسيع الطريق وبنزع ملكية')     # no page: no example
    # A dam named after the land taken is not the purpose: a school is «other».
    text('/akn/ma/act/decret/2-22-6', TextType.DECREE, y22, title=good + 'بإحداث ثانوية وبنزع ملكية القطع قرب السد', page=30)
    # Not counted: before and after the span, no taking, no public good, the French edition.
    text('/akn/ma/act/decret/2-18-1', TextType.DECREE, before, title=good + 'ببناء سد وبنزع ملكية', page=1)
    text('/akn/ma/act/decret/2-24-1', TextType.DECREE, y24, title=good + 'بتهيئة الطريق وبنزع ملكية', page=1)
    text('/akn/ma/act/decret/2-21-7', TextType.DECREE, y21, title=good + 'ببناء سد', page=1)
    text('/akn/ma/act/decret/2-21-8', TextType.DECREE, y21, title='مرسوم بنزع ملكية قطعة أرضية لبناء سد', page=1)
    text('/akn/ma/act/decret/2-21-9', TextType.DECREE, issue(6950, date(2021, 1, 7), edition=Edition.TRANSLATION_FR),
         title=good + 'ببناء سد وبنزع ملكية', page=1)
    meta = {'span': [2019, 2023], 'title_re': 'المنفعة العامة', 'taking_re': 'نزع',
            'purposes': [{'key': 'water', 're': 'سد'}, {'key': 'road', 're': 'الطريق'}, {'key': 'port', 're': 'ميناء'},
                         {'key': 'airport', 're': 'مطار'}],
            'law': {'issue': 3685, 'page': 980, 'akn': '/akn/ma/act/loi/7-81'},
            'constitution': {'issue': 5964, 'bis': True, 'page': 3607, 'akn': '/akn/ma/act/dahir/1-11-91'}}
    in_21 = {'issue': '6950', 'edition': 'general_ar', 'published': '2021-01-07', 'viewer': None}
    assert expropriation.count(meta) == {
        'years': [{'year': 2019, 'water': 0, 'road': 0, 'port': 1, 'airport': 0, 'other': 0},
                  {'year': 2020, 'water': 0, 'road': 0, 'port': 0, 'airport': 2, 'other': 0},
                  {'year': 2021, 'water': 1, 'road': 1, 'port': 0, 'airport': 0, 'other': 0},
                  {'year': 2022, 'water': 0, 'road': 1, 'port': 0, 'airport': 0, 'other': 1},
                  {'year': 2023, 'water': 1, 'road': 0, 'port': 0, 'airport': 0, 'other': 0}],
        # The port's only declaration is of 2019: no example.
        'examples': {'water': {'title': good + 'ببناء سد واد اخفمان وبنزع ملكية القطع', 'akn': '/akn/ma/act/decret/2-23-5'},
                     'road': {'title': good + 'بتهيئة الطريق الجهوية رقم 315 وبنزع ملكية', 'akn': '/akn/ma/act/decret/2-21-2'},
                     'airport': {'title': good + 'بتوسيع مطار فاس وبنزع ملكية', 'akn': '/akn/ma/act/decret/2-20-1'},
                     'other': {'title': good + 'بإحداث ثانوية وبنزع ملكية القطع قرب السد', 'akn': '/akn/ma/act/decret/2-22-6'}},
        'texts': {'e-water': {'issue': '7218 bis', 'edition': 'general_ar', 'published': '2023-08-03', 'page': 20,
                              'viewer': f'/pages/{y23.document_id}/1', 'path': '/ma/decret/2-23-5'},
                  'e-road': {**in_21, 'page': 55, 'path': '/ma/decret/2-21-2'},
                  'e-other': {'issue': '7100', 'edition': 'general_ar', 'published': '2022-06-02', 'page': 30, 'viewer': None,
                              'path': '/ma/decret/2-22-6'},
                  'e-airport': {'issue': '6850', 'edition': 'general_ar', 'published': '2020-01-30', 'page': 7,
                                'viewer': f'/pages/{january.document_id}/0', 'path': '/ma/decret/2-20-1'},
                  'law': {'path': None}, 'constitution': {'path': None}},
    }


def test_each_extension_of_the_emergency_is_a_term_to_the_day_its_first_article_as_published_names():
    """«حالة الطوارئ الصحية»: the decrees since 2020 whose title extends the emergency, in the order they were printed; a
    decree that only changes the 2021 decree says so; with no first article as published the day is unknown (year 1)."""
    declared = issue(6867, date(2020, 3, 24), suffix='bis')
    page(declared, 0, 1783)
    version(text('/akn/ma/act/decret/2-20-293', TextType.DECREE, declared, title='مرسوم بإعلان حالة الطوارئ الصحية'),
            'يعلن عن حالة الطوارئ الصحية إلى غاية يوم الاثنين 20 أبريل 2020 في الساعة السادسة مساء')
    extend = 'مرسوم بتمديد مدة سريان مفعول حالة الطوارئ الصحية'
    # Created out of order: the terms run in the order the Bulletin printed them.
    last = text('/akn/ma/act/decret/2-21-1086', TextType.DECREE, issue(7051, date(2021, 12, 30), suffix='bis'), number='2-21-1086',
                title=extend + ' بتغيير المرسوم رقم 2.21.507', page=2400)
    version(last, 'تمدد … إلى غاية يوم الاثنين «31 يناير 2022 في الساعة السادسة مساء')
    april = issue(6877, date(2020, 4, 19))
    page(april, 0, 2008)
    version(text('/akn/ma/act/decret/2-20-330', TextType.DECREE, april, number='2-20-330', title=extend, page=2008),
            'تمدد … إلى غاية يوم الأربعاء 20 ماي 2020 في الساعة السادسة مساء')
    change = text('/akn/ma/act/decret/2-21-712', TextType.DECREE, issue(7026, date(2021, 9, 29)), number='2-21-712',
                  title='مرسوم بتغيير المرسوم رقم 2.21.507 الصادر في 28 يونيو 2021')
    version(change, 'إلى غاية يوم 10 أكتوبر 2021', consolidation=Consolidation.MACHINE)
    # Not terms: before 2020, and the French edition.
    text('/akn/ma/act/decret/2-19-1', TextType.DECREE, issue(6800, date(2019, 8, 1)), number='2-19-1', title=extend)
    text('/akn/ma/act/decret/2-20-9', TextType.DECREE, issue(6877, date(2020, 4, 19), edition=Edition.TRANSLATION_FR),
         number='2-20-9', title=extend)
    meta = {'extends_re': 'بتمديد مدة سريان مفعول حالة الطوارئ الصحية|بتغيير المرسوم رقم 2\\.21\\.507',
            'declaration': {'akn': '/akn/ma/act/decret/2-20-293', 'issue': 6867, 'bis': True, 'page': 1783},
            'decree_law': {'akn': '/akn/ma/act/decret-loi/2-20-292', 'issue': 6867, 'bis': True, 'page': 1782},
            'settlement': {'akn': '/akn/ma/act/decret-loi/2-20-503', 'issue': 6906, 'bis': True, 'page': 4306},
            'on_the_spot': {'akn': '/akn/ma/act/decret/2-20-572', 'issue': 6908, 'page': 4379},
            'ratified': {'akn': '/akn/ma/act/loi/23-20', 'issue': 6887, 'page': 3336}}
    in_6867 = {'issue': '6867 bis', 'edition': 'general_ar', 'published': '2020-03-24'}
    assert emergency.count(meta) == {
        'declared_until': '2020-04-20',
        'terms': [{'key': 't-0', 'number': '2.20.330', 'until': '2020-05-20', 'printed': '2020-04-19'},
                  {'key': 't-1', 'number': '2.21.712', 'until': '0001-01-01', 'printed': '2021-09-29', 'changes': True},
                  {'key': 't-2', 'number': '2.21.1086', 'until': '2022-01-31', 'printed': '2021-12-30'}],
        'texts': {'t-0': {'issue': '6877', 'edition': 'general_ar', 'published': '2020-04-19', 'page': 2008,
                          'viewer': f'/pages/{april.document_id}/0', 'path': '/ma/decret/2-20-330'},
                  't-1': {'issue': '7026', 'edition': 'general_ar', 'published': '2021-09-29', 'page': None, 'viewer': None,
                          'path': '/ma/decret/2-21-712'},
                  't-2': {'issue': '7051 bis', 'edition': 'general_ar', 'published': '2021-12-30', 'page': 2400, 'viewer': None,
                          'path': '/ma/decret/2-21-1086'},
                  'declaration': {**in_6867, 'page': 1783, 'viewer': f'/pages/{declared.document_id}/0', 'path': '/ma/decret/2-20-293'},
                  'decree_law': {**in_6867, 'page': 1782, 'viewer': None, 'path': None},
                  'settlement': {'path': None}, 'on_the_spot': {'path': None}, 'ratified': {'path': None}},
    }
    # A declaration the site does not hold says no day.
    assert emergency.count({**meta, 'declaration': {**meta['declaration'], 'akn': '/akn/ma/act/decret/2-20-0'}})['declared_until'] is None


def test_the_education_portfolios_are_read_from_the_authorities_and_kept_from_their_minimum_of_texts():
    """«وزارة التعليم»: since the meta's year, the Arabic edition's texts whose authority names an education minister; one
    portfolio across its spellings, shown as most printed, from its first year to its last; a delegate, an office «المكلف»
    and another ministry are no portfolio; a portfolio with fewer texts than the meta's minimum is left out."""
    # Neither the texts nor the issues' numbers run in the Bulletin's order: a portfolio's first year is its earliest.
    years = {y: issue(4000 - y, date(y, 5, 2)) for y in (1970, 1961, 1959, 1956, 1965, 1958, 1962, 1960, 1955)}
    # The most printed spelling is neither the first nor the last read.
    rows = [(1956, 'وزير التربية الوطنيـة'), (1960, 'وزير التربية الوطنية'), (1962, 'وزير التربية الوطنية (فلان)'),
            (1965, 'وزير التربية الوطنيه'),
            (1959, 'وزير التعليم الابتدائي بالنيابة'), (1958, 'وزير التعليم الابتدائي'), (1959, 'وزير التعليم الابتدائي'),
            (1961, 'وزير التهذيب الوطني'), (1958, 'وزير التهذيب الوطني'),
            (1970, 'وزير المالية ووزير التعليم الابتدائي ووزير التعليم العالي'), (1970, 'مدير التعليم الابتدائي'), (1970, 'وزير الدولة المكلف بالتعليم'),
            (1955, 'وزير التربية الوطنية')]
    for k, (year, authority) in enumerate(rows):
        text(f'/akn/ma/act/arrete/{k}-{year}', TextType.ORDER, years[year], authority=authority)
    text('/akn/ma/act/arrete/fr-1960', TextType.ORDER, issue(3960, date(1960, 5, 2), edition=Edition.TRANSLATION_FR),
         authority='وزير التربية الوطنية')
    assert ministry.count({'since': 1956, 'min_texts': 2}) == {
        'names': [{'name': 'التربية الوطنية', 'texts': 4, 'from': 1956, 'to': 1965},
                  {'name': 'التعليم الابتدائي', 'texts': 4, 'from': 1958, 'to': 1970},
                  {'name': 'التهذيب الوطني', 'texts': 2, 'from': 1958, 'to': 1961}],
        # The texts that name a portfolio, the one under the minimum among them.
        'texts': 10,
        'longest': 'التعليم الابتدائي',
    }


def test_a_section_order_is_one_dot_at_the_first_speed_its_articles_fix_between_10_and_130():
    """«السرعة في الجريدة الرسمية»: the ministers' orders of the Arabic edition in the meta's years whose article names
    kilometres, each once, by its first article (in the order's order) that fixes a speed within the bounds."""
    y61, y63, y70 = issue(2530, date(1961, 5, 5)), issue(2650, date(1963, 8, 1)), issue(3000, date(1970, 1, 2))
    code = issue(5878, date(2010, 9, 16))
    page(code, 4, 2350)
    fr24 = issue(615, date(1924, 7, 8), edition=Edition.TRANSLATION_FR)
    page(fr24, 0, 1219)
    o61 = version(text('/akn/ma/act/arrete/61-1', TextType.ORDER, y61))
    article(o61, 2, 'art_2', 'تحدد السرعة القصوى في أربعين (40) كيلومترا')
    article(o61, 1, 'art_1', 'تحدد السرعة القصوى للسيارات في ستين كيلومترا في الساعة')
    version(text('/akn/ma/act/arrete/63-1', TextType.ORDER, y63), 'يمنع المرور على مسافة 5 كيلومترات',
            'تحدد السرعة القصوى في 09 كلم', 'تحدد السرعة القصوى في 131 كلم', 'تحدد السرعة القصوى في 130 كلم')
    # «ستين كيلو» names no kilometre the query looks for: the order's dot is its next article's.
    version(text('/akn/ma/act/arrete/70-1', TextType.ORDER, y70), 'تحدد السرعة القصوى في ستين كيلو', 'تحدد السرعة في 10 كلم')
    # Not read: a decree, an order before or after the years, the French edition's, an order's French version.
    version(text('/akn/ma/act/decret/2-10-420', TextType.DECREE, code), 'تحدد السرعة في 50 كلم')
    version(text('/akn/ma/act/arrete/55-1', TextType.ORDER, issue(2250, date(1955, 12, 1))), 'تحدد السرعة في 50 كلم')
    version(text('/akn/ma/act/arrete/10-1', TextType.ORDER, code), 'تحدد السرعة في 50 كلم')
    version(text('/akn/ma/act/arrete/61-2', TextType.ORDER, issue(2530, date(1961, 5, 5), edition=Edition.TRANSLATION_FR)),
            'تحدد السرعة في 50 كلم')
    version(text('/akn/ma/act/arrete/63-2', TextType.ORDER, y63), 'تحدد السرعة في 50 كلم', language='fr')
    meta = {'orders': {'from': 1956, 'to': 2009},
            'eras': [{'key': 'e1924', 'edition': 'fr', 'issue': 615, 'page': 1219}, {'key': 'e1961', 'issue': 2530, 'page': 100}],
            'first_rule': {'issue': 76, 'page': 436},
            'code': {'akn': '/akn/ma/act/decret/2-10-420', 'issue': 5878}, 'today': [{'key': 'city', 'page': 2350}]}
    assert speed.count(meta) == {
        'texts': {'e1924': {'issue': '615', 'edition': 'translation_fr', 'published': '1924-07-08', 'page': 1219,
                            'viewer': f'/pages/{fr24.document_id}/0', 'path': None},
                  'e1961': {'issue': '2530', 'edition': 'general_ar', 'published': '1961-05-05', 'page': 100, 'viewer': None, 'path': None},
                  'first': {'path': None},
                  't-city': {'issue': '5878', 'edition': 'general_ar', 'published': '2010-09-16', 'page': 2350,
                             'viewer': f'/pages/{code.document_id}/4', 'path': '/ma/decret/2-10-420'}},
        'orders': [{'year': 1961, 'kmh': 60}, {'year': 1963, 'kmh': 130}, {'year': 1970, 'kmh': 10}],
    }


def test_an_age_opens_the_article_of_the_text_it_is_read_in_when_the_corpus_holds_it():
    """«حياتك بأعمار القانون»: an age, or a step of an age that moved, opens its article in the text the reader finds it
    in (`article_in`, else its reference's text), any version; no article, no address."""
    constitution, family = '/akn/ma/act/dahir/1-11-91', '/akn/ma/act/loi/65-99'
    printing = issue(5964, date(2011, 7, 30), suffix='bis')
    page(printing, 2, 3600)
    version(text(constitution, TextType.DAHIR, printing), ('art_5', 'سن الرشد'))
    version(text(family, TextType.LAW), ('art_9', 'الزواج'), ('art_143', 'الشغل'), consolidation=Consolidation.ADALA)
    meta = {'ages': [{'key': 'vote', 'ref': {'issue': 5964, 'bis': True, 'page': 3600, 'akn': constitution}, 'art': '5'},
                     {'key': 'work', 'ref': {'issue': 5167, 'page': 10, 'akn': '/akn/ma/act/loi/116-14'}, 'article_in': family, 'art': '143'},
                     {'key': 'none', 'ref': {'issue': 1, 'page': 1}},
                     {'key': 'miss', 'ref': {'issue': 1, 'page': 1, 'akn': constitution}, 'art': '9'}],
            'moves': [{'key': 'marry', 'steps': [{'ref': {'issue': 2, 'page': 2, 'akn': family}, 'art': '9'}, {'ref': {'issue': 3, 'page': 3}}]}],
            'equal': {'ref': {'issue': 5964, 'bis': True, 'page': 3601}}, 'retire': {'unknown_day': {'ref': {'issue': 4, 'page': 4}}}}
    in_5964 = {'issue': '5964 bis', 'edition': 'general_ar', 'published': '2011-07-30'}
    assert ages.count(meta) == {
        'texts': {'a-vote': {**in_5964, 'page': 3600, 'viewer': f'/pages/{printing.document_id}/2', 'path': '/ma/dahir/1-11-91'},
                  'a-work': {'path': None}, 'a-none': {'path': None}, 'a-miss': {'path': '/ma/dahir/1-11-91'},
                  'm-marry-0': {'path': '/ma/loi/65-99'}, 'm-marry-1': {'path': None},
                  'equal': {**in_5964, 'page': 3601, 'viewer': None, 'path': None}, 'unknown-day': {'path': None}},
        # The constitution has no art. 9 (the family code has).
        'articles': {'a-vote': '/ma/dahir/1-11-91/art_5', 'a-work': '/ma/loi/65-99/art_143', 'm-marry-0': '/ma/loi/65-99/art_9'},
    }


def test_the_orders_articles_open_their_address_and_a_fine_is_said_in_the_sixth_posts_wage():
    """«الفصل 28»: article 28, the articles named and those with a fine open their address in the order when the site holds
    them, in their numbers' order; the wage an hour is the sixth post's checked series."""
    order = '/akn/ma/act/arrete/3-177-66'
    printing = issue(2856, date(1967, 7, 19))
    page(printing, 3, 1661)
    version(text(order, TextType.ORDER, printing), ('art_3', 'الرخصة'), ('art_28', 'يعاقب'))
    version(text('/akn/ma/act/arrete/3-289-70', TextType.ORDER), ('art_40', 'غرامة'))
    meta = {'order': {'issue': 2856, 'page': 1658, 'akn': order}, 'art28': {'page': 1661}, 'articles': [{'n': 3, 'page': 1658}],
            'chain': [{'key': 'delegation', 'text': {'issue': 2782, 'page': 5, 'akn': '/akn/ma/act/decret/76-66'}}],
            'first': {'issue': 8, 'page': 56, 'akn': '/akn/ma/act/dahir/1913-8'}, 'pairs': [{'p1913': 57}],
            'drunk': {'text': {'issue': 2873, 'page': 3, 'akn': '/akn/ma/act/decret/724-66'}}, 'fines': [{'art': 40}]}
    in_2856 = {'issue': '2856', 'edition': 'general_ar', 'published': '1967-07-19', 'path': '/ma/arrete/3-177-66'}
    out = drinks.count(meta)
    assert out == {
        'texts': {'order': {**in_2856, 'page': 1658, 'viewer': None},
                  'art28': {**in_2856, 'page': 1661, 'viewer': f'/pages/{printing.document_id}/3'},
                  'o-3': {**in_2856, 'page': 1658, 'viewer': None}, 'c-delegation': {'path': None},
                  'f-56': {'path': None}, 'f-57': {'path': None}, 'drunk': {'path': None}},
        'articles': {'3': '/ma/arrete/3-177-66/art_3', '28': '/ma/arrete/3-177-66/art_28'},
        'wage': marquise.wage(),
    }
    assert list(out['articles']) == ['3', '28'] and out['wage'][0]['hourly'] == 0.808


def test_the_strike_laws_articles_open_their_address_in_their_numbers_order():
    law = '/akn/ma/act/loi-organique/97-15'
    printing = issue(7389, date(2025, 3, 24))
    version(text(law, TextType.ORGANIC_LAW, printing), ('art_21', 'الإضراب'), ('art_7', 'الإخطار'), ('art_1', 'تعريف'), ('art_30', 'أخرى'))
    version(text('/akn/ma/act/loi/12-25', TextType.LAW), ('art_5', 'خمسة'))
    meta = {'law': {'issue': 7389, 'page': 1, 'akn': law}, 'numbers': [{'key': 'notice', 'art': '7', 'page': 2}],
            'constitutions': [{'year': 2011, 'issue': 5964, 'bis': True, 'page': 3606, 'akn': '/akn/ma/act/dahir/1-11-91'}],
            'deadline': {'issue': 5964, 'bis': True, 'page': 3616}, 'decision': {'issue': 7389, 'page': 9},
            'opinion': {'issue': 1, 'page': 1}, 'organic': [{'number': '97.15', 'issue': 7389, 'page': 1, 'akn': law}],
            'election': {'issue': 6501, 'page': 6724}}
    in_7389 = {'issue': '7389', 'edition': 'general_ar', 'published': '2025-03-24', 'viewer': None}
    out = strike.count(meta)
    assert out == {
        'texts': {'c-2011': {'path': None}, 'deadline': {'path': None},
                  'law': {**in_7389, 'page': 1, 'path': '/ma/loi-organique/97-15'}, 'decision': {**in_7389, 'page': 9, 'path': None},
                  'opinion': {'path': None}, 'n-notice': {**in_7389, 'page': 2, 'path': '/ma/loi-organique/97-15'},
                  'ol-97.15': {**in_7389, 'page': 1, 'path': '/ma/loi-organique/97-15'}, 'election': {'path': None}},
        'articles': {'1': '/ma/loi-organique/97-15/art_1', '7': '/ma/loi-organique/97-15/art_7', '21': '/ma/loi-organique/97-15/art_21'},
    }
    assert list(out['articles']) == ['1', '7', '21']


def test_the_staples_orders_open_their_pages_and_the_wage_is_the_sixth_posts():
    printing = issue(3570, date(1981, 6, 7))
    page(printing, 1, 631)
    meta = {'basket': [{'key': 'bread', 'orders': [{'issue': 3570, 'page': 631, 'akn': '/akn/ma/act/arrete/3-263-81'}]}],
            'bread_1975': {'issue': 3270, 'page': 1}, 'gasoil': [{'from': '1984-01-01', 'issue': 3570, 'page': 632}],
            'last': {'issue': 9, 'page': 9}, 'away': [{'key': 'gasoil', 'text': {'issue': 9, 'page': 9}}]}
    in_3570 = {'issue': '3570', 'edition': 'general_ar', 'published': '1981-06-07', 'path': None}
    assert staples.count(meta) == {
        'texts': {'b-bread-0': {**in_3570, 'page': 631, 'viewer': f'/pages/{printing.document_id}/1'}, 'bread-1975': {'path': None},
                  'g1984-01-01': {**in_3570, 'page': 632, 'viewer': None}, 'last': {'path': None}, 'away-gasoil': {'path': None}},
        'wage': marquise.wage(),
    }


def test_a_hijri_month_is_read_from_a_day_of_thirty_at_most_and_a_masthead_without_a_day_says_nothing():
    """«من غرينيتش إلى غرينيتش»: «30 رمضان» puts the month's first day 29 days before; «31 شوال» is a misreading and «شوال»
    without its day dates nothing."""
    issue(6000, date(2011, 8, 30), hijri='30 رمضان 1432')
    issue(6001, date(2011, 8, 31), hijri='31 شوال 1432')
    issue(6002, date(2011, 9, 1), hijri='شوال 1432')
    assert clock.count({'texts': []}) == {'texts': {}, 'hijri': {'ramadan': {'2011': '2011-08-01'}, 'shawwal': {}}}


def test_a_constitution_counts_its_titles_article_by_article_and_one_without_its_facts_or_arabic_is_left_out():
    first = text('/akn/ma/act/dahir/constitution-1962', TextType.CONSTITUTION, signed_on=date(1962, 12, 14))
    v = version(first, consolidation=Consolidation.ADALA, valid_from=date(1962, 12, 19))
    for k, (number, title, body) in enumerate((('1', 'الباب الأول', 'المغرب مملكة'), ('2', 'الباب الأول', 'الإسلام دين الدولة'),
                                               ('3', 'الباب الثاني', 'الملك أمير المؤمنين')), 1):
        a = article(v, k, f'art_{number}', body)
        a.heading_path = [title]
        a.save()
    # 1970's text with only its French; a constitution the corpus's facts do not know.
    version(text('/akn/ma/act/dahir/1-70-177', TextType.CONSTITUTION, signed_on=date(1970, 7, 31)), 'Le Maroc', language='fr',
            consolidation=Consolidation.ADALA)
    version(text('/akn/ma/act/dahir/constitution-x', TextType.CONSTITUTION, signed_on=date(1980, 1, 1)), 'نص',
            consolidation=Consolidation.ADALA)
    meta = {'themes': [{'key': 'general', 'match': 'الأول'}, {'key': 'monarchy', 'match': 'الثاني'}], 'terms': []}
    (only,) = constitutions.count(meta)['constitutions']
    assert only['year'] == 1962 and (only['articles'], only['words']) == (3, 8)
    assert only['titles'] == [{'name': 'الباب الأول', 'theme': 'general', 'articles': 2, 'words': 5},
                              {'name': 'الباب الثاني', 'theme': 'monarchy', 'articles': 1, 'words': 3}]
    assert only['squares'] == [['1', 0, 0], ['2', 0, 0], ['3', 1, 0]]


def test_a_words_first_counted_text_before_its_first_stop_is_a_check_and_a_stop_reads_the_article_as_published():
    """«كلمات دخلت القانون»: a stop in a text opens the article as first published when the corpus has it, whichever of its
    versions came first, with that article's printed page; a first counted before the first mention the meta names is a
    check for a person to read; a word the meta leaves open keeps what it says."""
    oldest = issue(4798, date(2000, 5, 25))
    version(text('/akn/ma/act/loi/05-00', TextType.LAW, oldest, page=1184), 'تدريس الأمازيغية')
    ircam = text('/akn/ma/act/dahir/1-01-299', TextType.DAHIR, issue(4948, date(2001, 11, 1)), title='ظهير بإحداث المعهد', page=3677)
    published = version(ircam)
    article(published, 1, 'art_1', 'يحدث المعهد الملكي للثقافة الأمازيغية', printed_page=3678)
    version(ircam, 'نص آخر', consolidation=Consolidation.ADALA, valid_from=date(2011, 1, 1))
    constitution = text('/akn/ma/act/dahir/1-11-91', TextType.DAHIR, issue(5964, date(2011, 7, 30), suffix='bis'), page=3600)
    # Adala's copy came first in time; the article as published is still the one the stop reads.
    version(constitution, ('art_5', 'الأمازيغية لغة رسمية'), consolidation=Consolidation.ADALA, valid_from=date(2011, 7, 29))
    as_printed = version(constitution, consolidation=Consolidation.AS_PUBLISHED, valid_from=date(2011, 7, 31))
    article(as_printed, 5, 'art_5', 'تعد الأمازيغية أيضا لغة رسمية للدولة', printed_page=3606)
    first = {'date': date(2001, 11, 1), 'kind': 'first', 'text': '/akn/ma/act/dahir/1-01-299', 'art': 1, 'ar': 'المعهد', 'fr': 'IRCAM'}
    step = {'date': date(2011, 7, 30), 'kind': 'step', 'text': '/akn/ma/act/dahir/1-11-91', 'art': 5, 'ar': 'الدستور', 'fr': 'Constitution'}
    meta = {'span': [2000, 2011], 'groups': [{'words': [
        {'key': 'amazigh', 'forms': ['الأمازيغية'], 'open': {'ar': 'مفتوح', 'fr': 'ouvert'}, 'stops': [step, first]},
        {'key': 'institute', 'forms': ['المعهد'], 'stops': [first]}]}]}
    f = words.count(meta)
    stop_first = {'date': '2001-11-01', 'kind': 'first', 'ar': 'المعهد', 'fr': 'IRCAM', 'title': 'ظهير بإحداث المعهد', 'issue': '4948',
                  'page': 3678, 'path': '/ma/dahir/1-01-299/art_1'}
    stop_step = {'date': '2011-07-30', 'kind': 'step', 'ar': 'الدستور', 'fr': 'Constitution', 'title': '', 'issue': '5964-bis',
                 'page': 3606, 'path': '/ma/dahir/1-11-91/art_5'}
    years = lambda **n: [n.get(f'y{y}', 0) for y in range(2000, 2012)]
    assert f == {
        'span': [2000, 2011], 'texts': years(y2000=1, y2001=1, y2011=1),
        'words': [{'key': 'amazigh', 'years': years(y2000=1, y2001=1, y2011=1),
                   'first': {'date': '2000-05-25', 'title': '', 'issue': '4798', 'page': 1184, 'path': '/ma/loi/05-00/art_1'},
                   'open': {'ar': 'مفتوح', 'fr': 'ouvert'}, 'stops': [stop_first, stop_step]},
                  {'key': 'institute', 'years': years(y2001=1),
                   'first': {'date': '2001-11-01', 'title': 'ظهير بإحداث المعهد', 'issue': '4948', 'page': 3677, 'path': '/ma/dahir/1-01-299/art_1'},
                   'stops': [stop_first]}],
        'checks': [{'key': 'amazigh', 'counted': '2000-05-25', 'stop': '2001-11-01', 'path': '/ma/loi/05-00/art_1'}],
    }


@pytest.mark.parametrize('stop, refusal', [
    ({'text': '/akn/ma/act/loi/99-99'}, 'no text /akn/ma/act/loi/99-99'),
    ({'text': '/akn/ma/act/dahir/1-58-1'}, 'has no issue; name it in meta.yaml'),
    ({'text': '/akn/ma/act/dahir/1-58-1', 'issue': '1', 'art': 9}, 'no article 9 in /akn/ma/act/dahir/1-58-1'),
    ({'issue': '2373', 'title': 'ظهير'}, 'a text not cut yet needs its issue, page and title as printed'),
])
def test_a_stop_that_is_not_what_the_meta_says_stops_the_count(stop, refusal):
    """A stop in a text the corpus lacks, in a text with no issue when the meta names none, in an article the text lacks,
    or not cut and without its page: the count stops and says which."""
    version(text('/akn/ma/act/dahir/1-58-1', TextType.DAHIR), 'الحريات العامة')        # Adala's, no issue
    word = {'key': 'liberty', 'forms': ['الحريات'], 'stops': [{'date': date(1958, 11, 15), 'kind': 'step', 'ar': 'ع', 'fr': 'l', **stop}]}
    with pytest.raises(ValueError, match=refusal):
        words.resolve_stops([word], {'liberty': ['الحريات']})


def test_a_correction_naming_an_issue_the_bulletin_never_printed_is_left_out_and_the_texts_count_inside_the_span():
    """«استدراك»: a notice naming an issue the site does not hold is left out and said; the issues and the texts a decade
    are the span's."""
    corrected = issue(4628, date(1998, 10, 8))
    late = issue(7271, date(2024, 2, 5))
    page(late, 0, body='استدراك خطإ وقع بالجريدة الرسمية عدد 4628 بتاريخ 8 أكتوبر 1998، الصفحة 2877\n\nمرسوم رقم 2.98.661\n\n'
                       'استدراك خطإ وقع بالجريدة الرسمية عدد 4000 بتاريخ 1996\n\nقرار لوزير الفلاحة')
    issue(2373, date(1958, 4, 18))
    for k, at in enumerate((corrected, late, late, issue(2400, date(1958, 10, 1)))):
        text(f'/akn/ma/act/decret/2-{k}', TextType.DECREE, at)
    f = errata.count({'span': [1990, 2025]})
    assert (f['notices'], f['timed'], f['left_out']) == (1, 1, {'no_issue': 1})
    assert f['decades'] == [1990, 2000, 2010, 2020]
    assert f['per_decade'] == {'notices': [0, 0, 0, 1], 'texts': [1, 0, 0, 2], 'issues': [1, 0, 0, 1],
                               'law': [0, 0, 0, 0], 'decree': [0, 0, 0, 1], 'order': [0, 0, 0, 0], 'names': [0, 0, 0, 0],
                               'index': [0, 0, 0, 0], 'other': [0, 0, 0, 0]}
    assert f['longest'] == [{'printed': '2024-02-05', 'printed_issue': '7271', 'corrected': '1998-10-08', 'corrected_issue': '4628',
                             'days': 9251, 'kind': 'decree'}]
    # Rows exported with psql may hold any year: only the span's texts count.
    assert errata.tabulate({'span': [1990, 2025]}, [], [], [(1985, 4), (1995, 2)])['per_decade']['texts'] == [2, 0, 0, 0]


@pytest.mark.parametrize('words_, value', [('خمسة عشر', 15), ('الخمسة عشر', 15), ('ثلاث وعشرين', 23), ('الثلاث والعشرين', 23),
                                           ('ثلاثين', 30), ('مائة', None)])
def test_a_number_in_words_is_its_units_and_its_tens(words_, value):
    assert deadlines.words_value(words_) == value
