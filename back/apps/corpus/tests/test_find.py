"""What a reader writes to name a text, read into the texts it names (W1, W3–W6 of the library-search review): each answer
sure or not, and the queries it costs whatever the corpus holds."""
from datetime import date

import pytest

from apps.corpus.models import Article, Consolidation, Mention, Text, Version
from apps.corpus.services import find as finder
from apps.corpus.services.find import find

pytestmark = pytest.mark.django_db


def text(uri: str, kind: str, number: str, title: str, *, signed=None, hijri='', articles: int = 0, status='in_force', dahir='') -> Text:
    t = Text.objects.create(akn_uri=f'/akn/ma/act/{uri}', type=kind, number=number, number_as_printed=number.replace('-', '.'),
                            title_ar=title, signed_on=signed, signed_on_hijri=hijri, status=status, promulgating_dahir=dahir)
    if articles:
        v = Version.objects.create(text=t, language='ar', valid_from=signed or date(2020, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
        Article.objects.bulk_create([Article(version=v, order=i, label=f'المادة {i}', number=str(i), eid=f'art_{i}', body=f'نص {i}.')
                                     for i in range(1, articles + 1)])
    return t


@pytest.fixture(autouse=True)
def corpus():
    finder._KEPT.clear()
    text('loi/70-03', 'law', '70-03', 'القانون رقم 70.03 بمثابة مدونة الأسرة', signed=date(2004, 2, 3), articles=20)
    text('loi/65-99', 'law', '65-99', 'القانون رقم 65.99 المتعلق بمدونة الشغل', signed=date(2003, 9, 11), articles=5, dahir='1.03.194')
    text('loi/58-25', 'law', '58-25', 'القانون رقم 58.25 يتعلق بالمسطرة المدنية', signed=date(2026, 2, 11), articles=3)
    text('loi/43-20', 'law', '43-20', 'قانون رقم 43.20 يتعلق بخدمات الثقة بشأن المعاملات الإلكترونية', signed=date(2020, 12, 31), articles=2)
    text('loi/95-17', 'law', '95-17', 'قانون رقم 95.17 يتعلق بالتحكيم والوساطة الاتفاقية', signed=date(2022, 5, 24), articles=2)
    text('loi/60-24', 'law', '60-24', 'قانون المالية رقم 60.24 للسنة المالية 2025', signed=date(2024, 12, 13), articles=2)
    text('loi/50-25', 'law', '50-25', 'قانون المالية رقم 50.25 للسنة المالية 2026', signed=date(2025, 12, 10), articles=2)
    text('projet-loi/60-26', 'bill', '60-26', 'مشروع قانون المالية رقم 60.26 للسنة المالية 2027')
    text('loi/41-90', 'law', '41-90', 'قانون رقم 41.90 تحدث بموجبه محاكم إدارية', signed=date(1993, 9, 10), articles=2, status='repealed')
    text('loi/38-15', 'law', '38-15', 'قانون رقم 38.15 يتعلق بالتنظيم القضائي', signed=date(2022, 6, 30), articles=2)
    text('dahir/1-57-343', 'dahir', '1-57-343', 'ظهير شريف رقم 1.57.343 تطبق بموجبه مقتضيات مدونة الاحوال الشخصية', signed=date(1957, 11, 22), articles=2)
    text('dahir/1-84-177', 'dahir', '1-84-177', 'ظهير شريف رقم 1.84.177 يتعلق بتعويض المصابين في حوادث تسببت فيها مركبات برية ذات محرك',
         signed=date(1984, 10, 2), hijri='6 محرم 1405', articles=2)
    text('dahir/1-83-351', 'dahir', '1-83-351', 'ظهير شريف رقم 1.83.351 بتفويض السلطة فيما يتعلق بإدارة الدفاع الوطني', signed=date(1984, 10, 2), articles=1)
    text('dahir/1-58-376', 'dahir', '1-58-376', 'الظهير الشريف رقم 1.58.376 بتنظيم حق تأسيس الجمعيات', signed=date(1958, 11, 15), hijri='3 جمادى الأولى 1378', articles=2)
    text('dahir/1-58-250', 'dahir', '1-58-250', 'ظهير شريف رقم 1.58.250 بسن قانون الجنسية المغربية', signed=date(1958, 9, 6), articles=2)
    text('dahir/1-96-157', 'constitution', '1-96-157', 'ظهير شريف رقم 1.96.157 بتنفيذ نص الدستور المراجع', signed=date(1996, 10, 7), articles=2)
    text('dahir/1-11-91', 'constitution', '1-11-91', 'ظهير شريف رقم 1.11.91 بتنفيذ نص الدستور', signed=date(2011, 7, 29), articles=20)
    for i in range(25):                                    # the compensation dahir is the one other texts cite
        Mention.objects.create(from_uri=f'/akn/ma/act/decret/2-90-{i}', words='الظهير', kind='cites', to_uri='/akn/ma/act/dahir/1-84-177', state='resolved')
    Mention.objects.create(from_uri='/akn/ma/act/decret/2-90-99', words='الظهير', kind='cites', to_uri='/akn/ma/act/dahir/1-83-351', state='resolved')


def first(q: str) -> dict:
    answers = [a for a in find(q)['answers'] if a['kind'] != 'note']
    return answers[0] if answers else {}


def paths(q: str) -> list[tuple[bool, str]]:
    return [(a['sure'], a['path']) for a in find(q)['answers'] if a['kind'] != 'note']


def test_a_number_opens_its_text_whatever_its_kind_and_wherever_it_stands():
    assert paths('43.20') == [(True, '/ma/loi/43-20')]
    assert paths('القانون رقم 43.20') == [(True, '/ma/loi/43-20')]
    assert paths('loi n° 43-20') == [(True, '/ma/loi/43-20')]            # never Bulletin no. 43
    assert first('ظهير 1-58-376')['path'] == '/ma/dahir/1-58-376'
    # A pasted dahir title: the law it promulgates, and the dahir said as its promulgation.
    r = find('ظهير شريف رقم 1.03.194 صادر في 14 من رجب 1424 (11 سبتمبر 2003) بتنفيذ القانون رقم 65.99 المتعلق بمدونة الشغل')
    assert next((a['sure'], a['path']) for a in r['answers'] if a['kind'] == 'text') == (True, '/ma/loi/65-99')
    assert r['understood']['promulgated_by'] == '1.03.194'
    # The dahir alone, which the site does not hold as a text of its own: the law it promulgates.
    r = find('ظهير شريف رقم 1.03.194')
    assert r['answers'][0]['path'] == '/ma/loi/65-99' and r['answers'][0]['why'] == 'promulgated'
    # A number the site does not hold is said, never guessed.
    r = find('القانون رقم 99.99')
    assert r['answers'] == [{'kind': 'note', 'code': 'not_held', 'number': '99.99', 'type': 'law'}]


def test_a_title_that_says_the_least_beside_the_words_stands_first():
    # «قانون التعليم العالي»: the law on higher education before the agency that assesses it, an amending law last.
    text('loi/80-12', 'law', '80-12', 'قانون رقم 80.12 يتعلق بالوكالة الوطنية لتقييم وضمان جودة التعليم العالي والبحث العلمي', signed=date(2014, 7, 31))
    text('loi/67-16', 'law', '67-16', 'قانون رقم 67.16 يقضي بتعديل أحكام القانون رقم 80.12 المتعلق بالوكالة الوطنية لتقييم التعليم العالي', signed=date(2016, 8, 25))
    text('loi/1-00', 'law', '01-00', 'قانون رقم 01.00 يتعلق بتنظيم التعليم العالي', signed=date(2000, 5, 19))
    finder._KEPT.clear()
    assert paths('قانون التعليم العالي') == [(False, '/ma/loi/1-00'), (False, '/ma/loi/80-12'), (False, '/ma/loi/67-16')]


def test_the_letter_jurists_write_for_a_law_or_a_dahir():
    # «ق 31.08» is «القانون رقم 31.08»; «ظ.ش 1.03.194» the dahir, which opens the law it promulgates.
    assert paths('ق 43.20') == [(True, '/ma/loi/43-20')]
    assert paths('ق. 43.20') == [(True, '/ma/loi/43-20')]
    assert paths('ظ.ش 1.03.194') == [(True, '/ma/loi/65-99')]
    assert paths('ظ 1.03.194') == [(True, '/ma/loi/65-99')]
    assert paths('ق.م.م') == [(True, '/ma/loi/58-25')]                    # a short form stays a short form
    # A number word and a text's number, nothing else: «n° 43.20», «رقم 43.20» open law 43.20 as «43.20» does.
    for asked in ('n° 43.20', 'n°43-20', 'رقم 43.20', 'numéro 43.20', 'عدد 43.20'):
        assert paths(asked) == [(True, '/ma/loi/43-20')], asked


def test_an_article_citation_opens_the_article():
    a = first('المادة 16 من مدونة الأسرة')
    assert a['kind'] == 'article' and a['sure'] and a['path'] == '/ma/loi/70-03/art_16' and a['text']['path'] == '/ma/loi/70-03'
    assert first('المادة 2 من القانون رقم 43.20')['path'] == '/ma/loi/43-20/art_2'
    assert first('مدونة الشغل المادة 3')['path'] == '/ma/loi/65-99/art_3'
    # An article the text does not have: the text, not sure, and the number asked for.
    a = first('المادة 900 من مدونة الأسرة')
    assert (a['sure'], a['state'], a['path'], a['asked']) == (False, 'text_only', '/ma/loi/70-03', '900')


def test_an_article_named_the_repeated_one_is_not_its_neighbour():
    # «المادة 225 المكررة», as the tax code prints its own: the article «bis», never article 225.
    v = Version.objects.get(text__number='70-03')
    Article.objects.create(version=v, order=99, label='المادة 16 المكررة', number='16-bis', eid='art_16-bis', body='نص.')
    finder._KEPT.clear()
    for asked in ('المادة 16 المكررة من مدونة الأسرة', 'المادة 16 مكرر من مدونة الأسرة', 'المادة 16 المكرر من مدونة الأسرة'):
        assert first(asked)['path'] == '/ma/loi/70-03/art_16-bis', asked
    assert first('المادة 16 من مدونة الأسرة')['path'] == '/ma/loi/70-03/art_16'


def test_short_forms_and_names_a_text_had():
    assert paths('ق.م.م') == [(True, '/ma/loi/58-25')]
    assert paths('ق م م') == [(True, '/ma/loi/58-25')]
    assert paths('قمم') == [(True, '/ma/loi/58-25')]
    assert paths('م.أ') == [(True, '/ma/loi/70-03')]                      # never the direct social support law
    assert paths('CF') == [(True, '/ma/loi/70-03')]
    assert find('م.ش')['understood']['short'] is True
    # The former code and the one that replaced it: two answers, neither opened for the reader.
    assert paths('مدونة الأحوال الشخصية') == [(False, '/ma/dahir/1-57-343'), (False, '/ma/loi/70-03')]
    assert paths('قانون المحاكم الإدارية') == [(False, '/ma/loi/41-90'), (False, '/ma/loi/38-15')]


def test_a_code_by_its_name_is_sure_only_when_the_name_is_whole():
    assert paths('مدونة الأسرة')[0] == (True, '/ma/loi/70-03')
    assert paths('مدونه الاسره')[0] == (True, '/ma/loi/70-03')
    assert paths('code de la famille')[0] == (True, '/ma/loi/70-03')
    assert paths('قانون المسطرة المدنية')[0] == (True, '/ma/loi/58-25')
    # Words beside a name: the book is offered, never opened («زيادة الأسرة» is no name of the family code).
    assert all(not sure for sure, _ in paths('حقوق الأسرة بالمغرب'))
    # A law by words of its title is offered, not sure.
    assert paths('قانون التحكيم') == [(False, '/ma/loi/95-17')]
    assert paths('خدمات الثقة') == [(False, '/ma/loi/43-20')]


def test_a_finance_law_by_its_year_and_a_bill_never_as_the_law():
    assert paths('قانون المالية 2025') == [(True, '/ma/loi/60-24')]
    assert paths('loi de finances 2026') == [(True, '/ma/loi/50-25')]
    r = find('مشروع قانون المالية 2027')
    assert [(a['sure'], a['path'], a['why']) for a in r['answers']] == [(True, '/ma/projet-loi/60-26', 'bill')]
    assert find('قانون المالية 2027')['answers'] == [{'kind': 'note', 'code': 'no_finance_law', 'year': 2027}]


def test_a_text_by_its_day_in_either_calendar():
    r = find('ظهير 2 أكتوبر 1984')
    assert r['understood']['day'] == {'date': date(1984, 10, 2), 'hijri': '6 محرم 1405', 'estimate': False, 'kind': 'dahir'}
    # Two dahirs that day: the one the others cite, by far, is first and sure.
    assert [(a['sure'], a['path']) for a in r['answers']] == [(True, '/ma/dahir/1-84-177'), (False, '/ma/dahir/1-83-351')]
    assert paths('ظهير 6 محرم 1405')[0] == (True, '/ma/dahir/1-84-177')
    assert paths('dahir du 15 novembre 1958') == [(True, '/ma/dahir/1-58-376')]
    assert paths('ظهير 3 جمادى الأولى 1378') == [(True, '/ma/dahir/1-58-376')]
    # No text of that day: the nearest day's, said as such and not sure.
    r = find('ظهير 16 نونبر 1958')
    assert [(a['sure'], a['path']) for a in r['answers'] if a['kind'] == 'text'] == [(False, '/ma/dahir/1-58-376')]
    assert {'kind': 'note', 'code': 'near_day', 'date': date(1958, 11, 15)} in r['answers']
    assert find('ظهير 1 يناير 1930')['answers'] == [{'kind': 'note', 'code': 'no_text_that_day', 'date': date(1930, 1, 1)}]
    # A day alone: the texts signed then, none opened (the browser shows the day's issues).
    assert paths('2 أكتوبر 1984')[0] == (False, '/ma/dahir/1-84-177')


def test_a_kind_a_year_and_a_word():
    r = find('ظهير 1958 الجمعيات')
    assert r['understood']['year'] == 1958 and [(a['sure'], a['path']) for a in r['answers']] == [(True, '/ma/dahir/1-58-376')]
    assert paths('دستور 1996') == [(True, '/ma/dahir/1-96-157')]
    assert find('دستور 1980')['answers'] == [{'kind': 'note', 'code': 'no_text_that_year', 'year': 1980}]


def test_what_the_browser_reads_is_left_to_it():
    for q in ('7556 مكرر', '1958', 'عدد 5964 مكرر', 'آخر عدد', 'x', ''):
        assert find(q)['answers'] == [], q
    assert find('آخر عدد')['understood'] == {'newest': True}
    # An issue named as one is an issue, its date its own and no text's day.
    a = find('الجريدة الرسمية عدد 5167 بتاريخ 8 دجنبر 2003')['answers']
    assert a == []                                                       # not held here: nothing, never a text


def test_a_french_reference_never_opens_the_arabic_issue_of_its_number():
    """W10: «B.O. n° 5210 … p. 667» names the French edition's pages; the Arabic issue 5210 is offered, not opened."""
    from apps.sources.models import Edition, Issue
    Issue.objects.create(edition=Edition.GENERAL_AR, number=5210, date=date(2004, 5, 6))
    r = find('B.O. n° 5210 du 6 mai 2004, p. 667')
    assert [(a['kind'], a['sure']) for a in r['answers']] == [('issue', False)] and r['understood'].get('french') is True
    r = find('الجريدة الرسمية عدد 5210 بتاريخ 6 ماي 2004')
    assert [(a['kind'], a['sure']) for a in r['answers']] == [('issue', True)] and 'french' not in r['understood']


def test_the_answer_costs_a_fixed_number_of_queries(api, django_assert_max_num_queries):
    find('مدونة الأسرة')                                                # the names and the titles are kept in the process
    pasted = 'ظهير شريف رقم 1.03.194 صادر في 14 من رجب 1424 (11 سبتمبر 2003) بتنفيذ القانون رقم 65.99 المتعلق بمدونة الشغل'
    for q, ceiling in (('43.20', 4), ('المادة 16 من مدونة الأسرة', 6), ('ظهير 2 أكتوبر 1984', 4), ('ق.م.م', 2), ('قانون المالية 2025', 2),
                       ('قانون التحكيم', 1), ('ظهير 1958 الجمعيات', 4), (pasted, 6), ('مدونة الأحوال الشخصية', 4)):
        with django_assert_max_num_queries(ceiling):
            assert api.get('/api/corpus/find/', {'q': q}).status_code == 200, q


def test_a_year_lists_its_laws_and_dahirs_the_most_cited_named_first(api, django_assert_max_num_queries):
    """W8: 1984 is its dahirs by name, not only its issues; three queries whatever the year holds."""
    text('decret/2-84-130', 'decree', '2-84-130', 'مرسوم رقم 2.84.130 يغير المرسوم رقم 2.73.416', signed=date(1984, 10, 2))
    with django_assert_max_num_queries(3):
        d = api.get('/api/corpus/years/1984/').json()
    assert d['year'] == 1984 and d['counts'] == {'dahir': 2, 'decree': 1}
    assert [t['path'] for t in d['texts']] == ['/ma/dahir/1-83-351', '/ma/dahir/1-84-177']       # no decree in the list
    by_path = {t['path']: t for t in d['texts']}
    assert by_path['/ma/dahir/1-84-177']['cited'] == 25 and by_path['/ma/dahir/1-84-177']['number'] == '1.84.177'
    # The delegation dahir is cited too, but once: only the compensation dahir is named among the most cited.
    assert d['most_cited'] == ['/ma/dahir/1-84-177']
    assert api.get('/api/corpus/years/1800/').status_code == 404
    assert api.get('/api/corpus/years/2999/').status_code == 404


def test_a_titles_subject_is_what_the_text_is_about():
    from apps.corpus.services.titles import subject
    assert subject('قانون رقم 43.20 يتعلق بخدمات الثقة بشأن المعاملات الإلكترونية قسم تمهيدي أحكام عامة') == 'خدمات الثقة بشأن المعاملات الإلكترونية'
    assert subject('ظهير شريف رقم 1.84.177 صادر في 6 محرم 1405 (2 أكتوبر 1984) معتبر بمثابة قانون يتعلق بتعويض المصابين') == 'تعويض المصابين'
    assert subject('قانون المالية رقم 60.24 للسنة المالية 2025') == 'قانون المالية رقم 60.24 للسنة المالية 2025'
    assert subject('الظهير الشريف رقم 1.58.376 الصادر في 3 جمادى الأولى 1378 (15 نوفمبر 1958) بتنظيم حق تأسيس الجمعيات') == 'بتنظيم حق تأسيس الجمعيات'
    assert subject('قانون تنظيمي رقم 113.14 يتعلق بالجماعات قسم تمهيدي أحكام عامة') == 'الجماعات'
    assert subject('ظهير شريف رقم 1.83.351 بتفويض السلطة فيما يتعلق بإدارة الدفاع الوطني. الحمد لله وحده الطابع الشريف') == 'بتفويض السلطة فيما يتعلق بإدارة الدفاع الوطني'
    assert subject('ظهير شريف') == 'ظهير شريف'
    assert len(subject('قانون رقم 1.00 ' + 'كلمة ' * 60)) <= 97


def test_the_words_a_false_heading_took_go_back_between_their_neighbours():
    """W11: «الكتاب مقررو هذه اللجان …» was a line of the tax code's art. 225 bis, taken for a book's heading."""
    from apps.corpus.management.commands.mend_library import Command
    from apps.corpus.services.titles import subject
    lost = 'الكتاب مقررو هذه اللجان إلى الطرفين وفق الإجراءات المنصوص عليها في المادة 219 أعلاه خلال'
    fresh = f'يجب أن تكون المقررات مفصلة ومعللة، ويبلغها\n{lost}\nالأربعة (4) أشهر الموالية لتاريخ صدورها.'
    held = 'يجب أن تكون المقررات مفصلة ومعللة، ويبلغها الأربعة (4) أشهر الموالية لتاريخ صدورها.'
    assert Command.put_back(held, fresh, lost) == f'يجب أن تكون المقررات مفصلة ومعللة، ويبلغها {lost} الأربعة (4) أشهر الموالية لتاريخ صدورها.'
    assert Command.put_back('نص آخر لا يشبهه.', fresh, lost) == ''             # its place is not there: nothing is guessed
    assert subject('قانون رقم 45.18 يتعلق بتنظيم مهنة العاملين الاجتماعيين الـباب الأول أحكام عامة') == 'تنظيم مهنة العاملين الاجتماعيين'
