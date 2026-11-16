"""The memorandum cut out of a bill as filed (row 11)."""
from apps.parliament.services.memoranda import bill_file, bill_page, memorandum, names_bill


def test_the_memorandum_runs_from_its_heading_to_the_bills_own():
    pages = ['المملكة المغربية\nرئيس الحكومة\nمشروع قانون رقم 013.26\nبتغيير وتتميم القانون رقم 2.00',
             'مذكرة تقديمية\nيأتي مشروع هذا القانون لملاءمة التشريع الوطني مع التطور الرقمي.\n2\n'
             'ويهدف مشروع قانون رقم 013.26 إلى حماية أفضل للمؤلفين.\nمشروع قانون رقم 013.26\nالمادة الأولى\nتغير …']
    text, ended = memorandum(pages)
    assert ended
    assert text.splitlines() == ['يأتي مشروع هذا القانون لملاءمة التشريع الوطني مع التطور الرقمي.',
                                 'ويهدف مشروع قانون رقم 013.26 إلى حماية أفضل للمؤلفين.']


def test_a_bill_without_a_memorandum_and_one_that_runs_on():
    assert memorandum(['مشروع قانون رقم 1.25\nالمادة الأولى']) == ('', False)
    assert memorandum(['المذكرة التقديمية\nفقرة أولى.']) == ('فقرة أولى.', False)


def test_the_bill_is_found_by_the_chambers_search_and_its_page():
    results = ('<a href="/ar/RapportL1-041.25">تقرير لجنة العدل حول مشروع قانون رقم 041.25</a>'
               '<a href="/ar/%D8%A7%D9%84%D9%86%D8%B5%D9%88%D8%B5-%D8%A7%D9%84%D8%AA%D8%B4%D8%B1%D9%8A%D8%B9%D9%8A%D8%A9/mshrw-04125">'
               '244 15/05/2026 مشروع قانون رقم 041.25 بتغيير القانون رقم 39.08</a>')
    assert bill_page(results, '041.25').endswith('/mshrw-04125')
    assert bill_page(results, '41.25') is None
    page = ('<a href="/sites/default/files/loi/Rapport_com_Lec_1_64.23.pdf">r</a>'
            '<a href="/sites/default/files/loi/Projet_loi_64.23.pdf">p</a>')
    assert bill_file(page) == 'https://www.chambredesrepresentants.ma/sites/default/files/loi/Projet_loi_64.23.pdf'


def test_a_bill_file_must_print_its_own_number():
    assert names_bill(['مشروع قانون رقم 59.24 يتعلق ب…'], '59.24')
    assert not names_bill(['مشروع قانون رقم 59.25 يتعلق ب…'], '59.24')
    assert names_bill(['مشروع قانون رقم ٠١٣.٢٦'], '013.26')
