"""Which text is which (rows L1 and L2 of the links review)."""
import datetime

import pytest

from apps.consolidation.models import Change
from apps.corpus.models import Alias, Text, TextType, Version
from apps.corpus.services import works
from apps.corpus.services.issue_structure import load_texts
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


def test_kind_and_number_give_the_address_whatever_the_zeros():
    assert works.fold('013-26') == '13-26' and works.fold('2-00') == '2-00' and works.fold('0') == '0'
    assert works.uri_for('law', '013-26', '013.26', 'x') == '/akn/ma/act/loi/13-26'
    assert works.uri_for('decree', '2-22-729', '2.22.729', 'x') == '/akn/ma/act/decret/2-22-729'
    assert works.uri_for('order', '3259-20', '3259.20', 'x') == '/akn/ma/act/arrete/3259-20'
    # A body's own numbering keeps its year-based address.
    assert works.uri_for('decision', '106', '106/ق/2022', '/akn/ma/act/decision/2022/106') == '/akn/ma/act/decision/2022/106'
    assert works.uri_for('decision', '16-20', 'P/EA/16.20', 'y') == 'y'
    assert works.uri_for('decision', '46-22', '46.22', 'z') == 'z'     # the audiovisual council's own numbering


def test_a_citation_is_matched_by_kind_never_by_a_number_alone():
    Text.objects.create(akn_uri='/akn/ma/act/decision/13-26', type=TextType.DECISION, number='13-26')
    # «القانون رقم 13.26» is the law, read or not: never the minister's decision with the same number.
    assert works.resolve('law', '13-26') == ('/akn/ma/act/loi/13-26', 'resolved')
    assert works.resolve(None, '13-26') == ('', 'unresolved')
    assert works.resolve(None, '2-22-729') == ('/akn/ma/act/decret/2-22-729', 'resolved')
    Text.objects.create(akn_uri='/akn/ma/act/loi-organique/65-13', type=TextType.ORGANIC_LAW, number='65-13')
    assert works.resolve('law', '065-13') == ('/akn/ma/act/loi-organique/65-13', 'resolved')


def _texts(number='66.19', title='قانون رقم 66.19 بتغيير وتتميم القانون رقم 2.00 المتعلق بحقوق المؤلف'):
    data = {'found': True, 'type': 'law', 'number_as_printed': number, 'title': title,
            'signed_on_gregorian': '2022-06-01', 'signed_on_hijri': '', 'authority': '', 'promulgating_dahir': '1.22.30',
            'preamble': [], 'closing': '', 'signatories': [], 'cites': [], 'amends': []}
    toc = {'type': 'law', 'number_as_printed': number, 'title': title, 'signed_on_gregorian': '2022-06-01',
           'signed_on_hijri': '', 'rubric': '', 'section': 'general', 'page': 3726}
    return [{'data': data, 'toc': toc, 'pages': [3726, 3728], 'front': title, 'tail': '',
             'articles': [{'label': 'المادة الأولى', 'body': 'نص.', 'page': 3726, 'heading_path': []}]}]


def test_a_text_cited_before_its_issue_is_read_is_filled_not_doubled():
    waiting = works.wait('/akn/ma/act/loi/66-19', 'law', '66-19', 'القانون رقم 66.19')
    Change.objects.create(text_uri='/akn/ma/act/loi/2-00', number='1', verb='modified', source='reading',
                          by_kind='law', by_number='66-19', by_uri='/akn/ma/act/loi/66-19')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7101, date=datetime.date(2022, 6, 20))
    load_texts(issue, _texts())
    text = Text.objects.get(number='66-19')
    assert text.pk == waiting.pk and text.akn_uri == '/akn/ma/act/loi/66-19' and text.versions.count() == 1
    # Its promulgating dahir leads to it.
    assert works.follow('/akn/ma/act/dahir/1-22-30') == '/akn/ma/act/loi/66-19'


def test_old_addresses_move_and_lead_to_the_text():
    from apps.consolidation.services.engine import readdress
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/2022/66-19', type=TextType.LAW, number='66-19')
    Version.objects.create(text=text, language='ar', valid_from=datetime.date(2022, 6, 20), consolidation='as_published')
    stub = Text.objects.create(akn_uri='/akn/ma/act/loi/066-19', type=TextType.LAW, number='066-19')
    Change.objects.create(text_uri=stub.akn_uri, number='1', verb='modified', source='reading', by_kind='law',
                          by_number='1-23', by_uri='/akn/ma/act/loi/1-23')
    readdress()
    text.refresh_from_db()
    assert text.akn_uri == '/akn/ma/act/loi/66-19' and not Text.objects.filter(pk=stub.pk).exists()
    assert Change.objects.get().text_uri == '/akn/ma/act/loi/66-19'
    assert works.text_at('/akn/ma/act/loi/2022/66-19') == (text, '/akn/ma/act/loi/66-19')
    assert Alias.objects.filter(alias='/akn/ma/act/loi/066-19', uri=text.akn_uri).exists()


def test_a_law_is_the_law_its_heading_names():
    from apps.consolidation.services.engine import readdress
    from apps.corpus.services.issue_structure import as_law
    data = {'type': 'law', 'title': '', 'number_as_printed': '01.23', 'promulgating_dahir': '1.23.56'}
    assert as_law(data, 'ظهير شريف رقم 1.23.56\nقانون رقم 83.21\nيتعلق بالشركات الجهوية متعددة الخدمات') == {
        **data, 'number_as_printed': '83.21', 'title': 'قانون رقم 83.21 يتعلق بالشركات الجهوية متعددة الخدمات'}
    # A heading that starts with a dahir's number is another text's, quoted: it names nothing.
    assert as_law(data, 'قانون رقم 1.93.228 الصادر في 22 من ربيع الأول 1414')['number_as_printed'] == '01.23'
    # Rows read before: an organic law filed as law 14.22, a law filed under the dahir's number.
    organic = Text.objects.create(akn_uri='/akn/ma/act/loi/14-22', type=TextType.LAW, number='14-22',
                                  title_ar='قانون تنظيمي رقم 48.22 يقضي بتغيير وتتميم القانون التنظيمي رقم 02.12')
    law = Text.objects.create(akn_uri='/akn/ma/act/loi/1-23', type=TextType.LAW, number='1-23',
                              title_ar='قانون رقم 83.21 يتعلق بالشركات الجهوية متعددة الخدمات')
    for t in (organic, law):
        Version.objects.create(text=t, language='ar', valid_from=datetime.date(2023, 3, 23), consolidation='as_published')
    cited = works.wait('/akn/ma/act/loi/83-21', 'law', '83-21', 'القانون رقم 83.21')
    readdress()
    organic.refresh_from_db(), law.refresh_from_db()
    assert (organic.akn_uri, organic.type, organic.number_as_printed) == ('/akn/ma/act/loi-organique/48-22', 'organic_law', '48.22')
    assert law.akn_uri == '/akn/ma/act/loi/83-21' and not Text.objects.filter(pk=cited.pk).exists()
    # The old addresses named other laws' numbers: a citation of law 14.22 or 1.23 never leads here.
    assert works.follow('/akn/ma/act/loi/14-22') == '/akn/ma/act/loi/14-22'
    assert works.follow('/akn/ma/act/loi/1-23') == '/akn/ma/act/loi/1-23'


def test_an_old_address_on_the_site_redirects(api):
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/66-19', type=TextType.LAW, number='66-19', title_ar='قانون')
    Alias.objects.create(alias='/akn/ma/act/loi/2022/66-19', uri=text.akn_uri, reason='moved')
    r = api.get('/api/corpus/at/ma/loi/2022/66-19/art_1/?window=40')
    assert r.status_code == 301 and r['Location'] == '/api/corpus/at/ma/loi/66-19/art_1/?window=40'


def test_a_number_written_as_the_bo_prints_it_leads_to_the_text(api):
    """/ma/loi/07-03 (the BO prints 07.03) is law 7.03's address, …/7-03, as a citation of it is (4 Nov 2026)."""
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/7-03', type=TextType.LAW, number='7-03', title_ar='قانون')
    assert works.text_at('/akn/ma/act/loi/07-03') == (text, '/akn/ma/act/loi/7-03')
    assert works.text_at('/akn/ma/act/loi/07.03') == (text, '/akn/ma/act/loi/7-03')
    assert works.canonical('/akn/ma/act/decret/02-22-729') == '/akn/ma/act/decret/2-22-729'
    # Only a numbered text's address: one with a year or an issue is never rewritten.
    assert works.canonical('/akn/ma/act/decision/2021/02-26') == '/akn/ma/act/decision/2021/02-26'
    assert works.text_at('/akn/ma/act/loi/08-03') == (None, '/akn/ma/act/loi/08-03')
    r = api.get('/api/corpus/at/ma/loi/07-03/art_1/?window=40')
    assert r.status_code == 301 and r['Location'] == '/api/corpus/at/ma/loi/7-03/art_1/?window=40'


@pytest.mark.django_db
def test_a_row_filed_as_a_law_under_a_dahirs_number_is_folded_into_the_dahir():
    """T2 of the work plan: the social security dahir 1.72.184 sat at loi/ and dahir/, its changes split."""
    from apps.consolidation.models import Change
    from apps.corpus.models import Text
    from apps.corpus.services import works
    Text.objects.create(akn_uri='/akn/ma/act/loi/1-72-184', type='law', number='1-72-184', title_ar='قانون رقم 1.72.184')
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1-72-184', type='dahir', number='1-72-184', title_ar='ظهير شريف')
    Text.objects.create(akn_uri='/akn/ma/act/loi/1-73-645', type='law', number='1-73-645', title_ar='قانون رقم 1.73.645')
    Change.objects.create(text_uri='/akn/ma/act/loi/1-72-184', number='53', verb='modified', source='links',
                          by_kind='law', by_number='2-24')
    assert works.fold_dahir_numbers(log=lambda *a: None) == {'folded': 1, 'moved': 1}
    assert Change.objects.get().text_uri == '/akn/ma/act/dahir/1-72-184'
    assert works.follow('/akn/ma/act/loi/1-72-184') == '/akn/ma/act/dahir/1-72-184'
    assert Text.objects.filter(akn_uri='/akn/ma/act/dahir/1-73-645', type='dahir').exists()


def test_a_ministers_order_filed_as_a_decision_moves_to_its_order_address():
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    from apps.follows.models import Follow
    assert works.ministers_order('قرار لوزير التجهيز والماء رقم 2709.10 صادر في 29 يوليو 2010', '2709.10')
    assert works.ministers_order('قرار مشترك لوزير الداخلية ووزير المالية', '1234.20')
    assert not works.ministers_order('قرار للهيئة العليا للاتصال السمعي البصري', '46.22')
    assert not works.ministers_order('قرار لوزير العدل', '106/ق/2022')
    title = 'قرار لوزير التجهيز والنقل رقم 2709.10 بشأن امتحان رخصة السياقة'
    text = Text.objects.create(akn_uri='/akn/ma/act/decision/2010/2709-10', type=TextType.DECISION, number='2709-10',
                               number_as_printed='2709.10', title_ar=title)
    user = get_user_model().objects.create_user('reader', 'r@example.org', 'a long phrase 7')
    Follow.objects.create(user=user, path='/ma/decision/2010/2709-10/art_3')
    call_command('retype_orders', '--write')
    text.refresh_from_db()
    assert (text.akn_uri, text.type) == ('/akn/ma/act/arrete/2709-10', 'order')
    assert Alias.objects.get(alias='/akn/ma/act/decision/2010/2709-10').uri == text.akn_uri
    # What a reader kept by the old path follows the text.
    assert Follow.objects.get(user=user).path == '/ma/arrete/2709-10/art_3'
    # And the next load files it as an order from the start.
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=5878, date=datetime.date(2010, 9, 30))
    texts = _texts('2701.10', 'قرار لوزير التجهيز والنقل رقم 2701.10 بشأن السياقة')
    texts[0]['data']['type'] = texts[0]['toc']['type'] = 'decision'
    load_texts(issue, texts)
    assert Text.objects.get(number='2701-10').type == 'order'


def test_a_number_read_backwards_from_an_old_scan_is_put_back_or_left_in_doubt():
    # The archive run (28 Oct 2026): Haiku read some old headings right to left, «290.81.1» for dahir 1.81.290.
    assert works.orient('290-81-1') == '1-81-290' and works.orient('560-75-2') == '2-75-560'
    assert works.orient('82-1482') == '1482-82' and works.orient('66-547') == '547-66' and works.orient('00-2') == '2-00'
    for kept in ('1-81-290', '2-22-729', '3-386-69', '66-19', '24-82', '20-2019', '1482-82', '3-56-06'):
        assert works.orient(kept) == kept
    on = datetime.date(1982, 12, 31)
    # Two groups of two digits read both ways: the year a law signed in 1982 can carry settles it.
    assert works.oriented('law', '82-24', '24-82', on) == ('24-82', False)
    # Both years possible (a law of 2001 or one of 2005, signed in 2005): in doubt, never guessed.
    assert works.oriented('law', '05-01', '01-05', datetime.date(2005, 1, 7)) == ('', True)
    # Read backwards in one place only, its year impossible and its reverse's possible: in doubt.
    assert works.oriented('law', '82-24', '', on) == ('', True)
    assert works.oriented('law', '66-19', '1-22-30', datetime.date(2022, 6, 1)) == ('66-19', False)
    # A body's own numbering is never turned.
    assert works.oriented('decision', '12-2021', '', on) == ('12-2021', False)
    # A citation read backwards in an old text links to the text it names.
    assert works.resolve('dahir', '290-81-1') == ('/akn/ma/act/dahir/1-81-290', 'resolved')
    assert works.resolve(None, '225-57-1') == ('/akn/ma/act/dahir/1-57-225', 'resolved')


def test_an_old_issues_text_gets_its_number_put_back_and_a_doubtful_one_its_issues_address():
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=3633, date=datetime.date(1982, 6, 16))
    texts = _texts('290.81.1', 'ظهير شريف رقم 1.81.290 بشأن تعيين موثقين')
    texts[0]['data']['type'] = texts[0]['toc']['type'] = 'dahir'
    texts[0]['toc']['number_as_printed'] = '1.81.290'
    texts[0]['data']['signed_on_gregorian'] = texts[0]['toc']['signed_on_gregorian'] = '1982-05-06'
    doubtful = _texts('82.24', 'قانون رقم 82.24')[0]
    doubtful['data']['signed_on_gregorian'] = doubtful['toc']['signed_on_gregorian'] = '1982-05-06'
    doubtful['toc']['number_as_printed'] = ''
    counts = load_texts(issue, texts + [doubtful])
    dahir = Text.objects.get(type='dahir')
    assert (dahir.akn_uri, dahir.number_as_printed) == ('/akn/ma/act/dahir/1-81-290', '1.81.290')
    law = Text.objects.get(type='law')
    assert law.akn_uri == '/akn/ma/act/loi/1982-06-16/bo3633-2' and law.number == '' and law.number_as_printed == '82.24'
    assert counts['in_doubt'] == 1


def test_an_issue_read_later_never_writes_over_a_text_the_corpus_already_holds():
    # 28 Oct 2026: the archive's load took Adala's 2.08.310, dated by Adala to its BO issue's day, for its own version
    # and replaced its words, its title and its kind with Haiku's reading of the first print (27 such texts).
    passport = Text.objects.create(akn_uri='/akn/ma/act/decret/2-08-310', type=TextType.DECREE, number='2-08-310',
                                   number_as_printed='2.08.310', title_ar='مرسوم رقم 2.08.310 بشأن جواز السفر')
    adala = Version.objects.create(text=passport, language='ar', valid_from=datetime.date(2008, 11, 6), consolidation='adala')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=5680, date=datetime.date(2008, 11, 6))
    texts = _texts('2.08.310', 'مرسوم رقم 2.08.310 صادر في 23 أكتوبر 2008 ديباجة')
    texts[0]['data']['type'] = texts[0]['toc']['type'] = 'decree'
    waiting = _texts('2.08.312', 'مرسوم رقم 2.08.312')[0]
    waiting['data']['type'] = waiting['toc']['type'] = 'decree'
    works.wait('/akn/ma/act/decret/2-08-312', 'decree', '2-08-312', 'المرسوم رقم 2.08.312')
    counts = load_texts(issue, texts + [waiting])
    passport.refresh_from_db()
    assert counts['held'] == 1 and passport.title_ar == 'مرسوم رقم 2.08.310 بشأن جواز السفر'
    assert list(passport.versions.values_list('pk', 'consolidation')) == [(adala.pk, 'adala')]
    assert passport.first_published_in is None
    # A text only cited until then is filled as before.
    assert Text.objects.get(akn_uri='/akn/ma/act/decret/2-08-312').first_published_in == issue


def test_only_a_law_is_folded_with_its_promulgating_dahir():
    # 28 Oct 2026: Haiku gave decree 2.72.513 the «promulgating dahir» 1.72.255, the dahir it applies; the load folded
    # the SGG's consolidation of that dahir into the decree and led the dahir's address to it.
    dahir = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-72-255', type=TextType.DAHIR, number='1-72-255',
                                title_ar='ظهير شريف بمثابة قانون رقم 1.72.255 يتعلق باستيراد المواد النفطية')
    Version.objects.create(text=dahir, language='ar', valid_from=datetime.date(2016, 3, 17), consolidation='sgg')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=3149, date=datetime.date(1973, 3, 7))
    texts = _texts('2.72.513', 'مرسوم رقم 2.72.513 بتطبيق الظهير الشريف رقم 1.72.255')
    texts[0]['data'].update(type='decree', promulgating_dahir='1.72.255', signed_on_gregorian='1973-02-22')
    texts[0]['toc'].update(type='decree', signed_on_gregorian='1973-02-22')
    load_texts(issue, texts)
    assert Text.objects.filter(akn_uri='/akn/ma/act/dahir/1-72-255', versions__consolidation='sgg').exists()
    assert not Alias.objects.filter(alias='/akn/ma/act/dahir/1-72-255').exists()
    # A law still joins its dahir: the dahir's address leads to it.
    load_texts(Issue.objects.create(edition=Edition.GENERAL_AR, number=7101, date=datetime.date(2022, 6, 20)), _texts())
    assert works.follow('/akn/ma/act/dahir/1-22-30') == '/akn/ma/act/loi/66-19'


def test_decrees_printed_under_one_entry_load_with_their_numbers_clipped_to_the_field():
    # BO 2716 (1964): six naturalisation decrees under one heading, «2.64.446 – 2.64.447 – … – 2.64.451».
    numbers = ' – '.join(f'2.64.{n}' for n in range(446, 452))
    texts = _texts(numbers, f'مراسيم رقم {numbers} تتعلق بمنح الجنسية المغربية')
    texts[0]['data'].update(type='decree', promulgating_dahir='', signed_on_hijri='4 رجب 1384 ' * 10)
    texts[0]['toc'].update(type='decree', section='special')
    load_texts(Issue.objects.create(edition=Edition.GENERAL_AR, number=2716, date=datetime.date(1964, 11, 25)), texts)
    text = Text.objects.get(first_published_in__number=2716)
    assert text.number_as_printed == numbers[:60] and len(text.signed_on_hijri) == 80
