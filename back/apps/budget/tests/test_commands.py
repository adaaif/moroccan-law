"""The budget's commands on the corpus: `load_finance_law` (one law by its printed number, every check said),
`load_finance_laws` (every finance law found by its title) and `diagnose_table` (the blocks of a table that do not add
up to their own subtotal)."""
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.budget.models import FinanceLaw
from apps.budget.tests import world
from apps.corpus.models import Consolidation, Text, Version

pytestmark = pytest.mark.django_db


def run(*args) -> str:
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def test_a_law_is_loaded_by_its_printed_number_and_every_check_is_said():
    text = world.law_2026()
    said = run('load_finance_law', '50.25', '--year', '2026').splitlines()
    assert said[0] == 'Finance law (قانون المالية) 2026 (50.25): balance 40, posts 4, A 0, B 5, C 5, D 2, E 1, F 1, G 1'
    assert said[1] == '  ok   balance: tax_revenue: expected 376081156000.00, found 376081156000.00'
    assert ('  ok   table B: running costs (art. 42): expected 347490689000, found 347490689000.00 (the article, in '
            'figures)') in said
    assert len(said) == 33 and said[-1] == "shown: ['B', 'C', 'D', 'E', 'F', 'G', 'balance', 'posts']"
    assert FinanceLaw.objects.get().text == text
    # A bill of that number is never this law: asked for as a bill, there is none.
    with pytest.raises(CommandError, match=r'^No text 50.25 in the corpus: run process_issue on its BO issue first\.$'):
        run('load_finance_law', '50.25', '--year', '2026', '--kind', 'bill')


def test_a_bill_is_loaded_from_its_own_text_never_from_the_law_of_its_number():
    # A decree of that number with no version yet is no text to read.
    Text.objects.create(akn_uri='/akn/ma/act/decret/60-26', type='decree', number='60-26')
    posts = world.POSTS.replace('يتم إحداث', 'يتـم إحداث')          # the bill's own file stretches its letters
    bill = world.finance_text(None, [('المادة 20', '20', posts, []), ('المادة 38', '38', world.BALANCE, [])],
                              uri='/akn/ma/act/projet-loi/60-26', number='60-26', printed='60.26', kind='bill',
                              title='مشروع قانون المالية رقم 60.26 للسنة المالية 2027')
    law = world.finance_text(None, [('المادة الأولى', '1', 'نص.', [])], uri='/akn/ma/act/loi/60-26', number='60-26',
                             printed='60.26', title='قانون المالية رقم 60.26 للسنة المالية 2027')
    said = run('load_finance_law', '60.26', '--year', '2027', '--kind', 'bill').splitlines()
    # Its annexes are files of their own: no table read, none checked.
    assert said[0] == 'Finance bill (مشروع قانون المالية) 2027 (60.26): balance 40, posts 4, A 0, B 0, C 0, D 0, E 0, F 0, G 0'
    assert said[-3:] == ['  ok   posts: the ministries add up to the total: expected 36000.00, found 36000.00',
                         '  ok   posts: the parts add up to the posts created: expected 36395, found 36395',
                         "shown: ['balance', 'posts']"]
    assert len(said) == 19
    said = run('load_finance_law', '60.26', '--year', '2027').splitlines()
    assert '  FAIL balance: tax_revenue: expected None, found None (line missing)' in said
    assert '  FAIL table B: running costs (art. 42): expected None, found None (table not read)' in said
    assert said[-1] == 'shown: []'
    assert {(f.kind, f.text) for f in FinanceLaw.objects.all()} == {('bill', bill), ('law', law)}


def titled(title: str, uri: str, *, versions: int = 1, issue=None, pages: str = '') -> Text:
    text = Text.objects.create(akn_uri=uri, type='law', title_ar=title, first_published_in=issue)
    for n in range(versions):
        Version.objects.create(text=text, language='ar', valid_from=f'20{10 + n}-01-01', source_pages=pages,
                               consolidation=Consolidation.AS_PUBLISHED)
    return text


def test_every_finance_law_in_the_corpus_is_found_by_its_title_loaded_and_said_newest_first():
    titled('قانون المالية رقم 80.18 للسنة المالية 2019', '/akn/ma/act/loi/80-18')
    # Its BO issue is known but not its pages: this law fails, the others are loaded.
    titled('قانون المالية رقم 26.04 للسنة المالية 2005', '/akn/ma/act/loi/26-04', issue=world.bulletin(['نص'], number=5600, suffix=''))
    titled('قانون المالية رقم 38.07 لسنة 2008', '/akn/ma/act/loi/38-07')
    world.law_2026()                                                    # two versions: loaded once
    titled('قانون المالية رقم 70.19 للسنة المالية 2020', '/akn/ma/act/loi/70-19')
    titled('قانون المالية لسنة 2010 رقم 48.09 للسنة المالية 2010', '/akn/ma/act/loi/48-09')
    titled('قانون المالية المعدل رقم 35.20 للسنة المالية 2020', '/akn/ma/act/loi/35-20', versions=2)
    titled('قانون المالية رقم 43.10 السنة المالية 2011', '/akn/ma/act/loi/43-10')    # the reading dropped «لل»
    titled('قانون المالية: نص لم يقرأ عنوانه', '/akn/ma/act/loi/1-00')
    titled('قرار المحكمة الدستورية بشأن قانون المالية رقم 50.25 للسنة المالية 2026', '/akn/ma/act/decision/1-26')
    titled('قانون المالية رقم 12.98 للسنة المالية 1999', '/akn/ma/act/loi/12-98', versions=0)
    first_six = "['balance: tax_revenue', 'balance: non_tax_revenue', 'balance: ordinary_revenue', 'balance: running', " \
                "'balance: ordinary_spending', 'balance: ordinary_balance']"
    assert run('load_finance_laws').splitlines() == [
        "2026 law 50.25: 31/31 checks, shown ['B', 'C', 'D', 'E', 'F', 'G', 'balance', 'posts']",
        f'2020 amending 35.20: 0/21 checks, shown []; failing: {first_six}',
        f'2020 law 70.19: 0/21 checks, shown []; failing: {first_six}',
        f'2019 law 80.18: 0/21 checks, shown []; failing: {first_six}',
        f'2011 law 43.10: 0/21 checks, shown []; failing: {first_six}',
        f'2010 law 48.09: 0/21 checks, shown []; failing: {first_six}',
        f'2008 law 38.07: 0/21 checks, shown []; failing: {first_six}',
        "2005 law 26.04: FAILED ValueError: invalid literal for int() with base 10: ''"]
    assert sorted(FinanceLaw.objects.values_list('year', 'kind', 'number', 'text__akn_uri')) == [
        (2008, 'law', '38.07', '/akn/ma/act/loi/38-07'), (2010, 'law', '48.09', '/akn/ma/act/loi/48-09'),
        (2011, 'law', '43.10', '/akn/ma/act/loi/43-10'), (2019, 'law', '80.18', '/akn/ma/act/loi/80-18'),
        (2020, 'amending', '35.20', '/akn/ma/act/loi/35-20'), (2020, 'law', '70.19', '/akn/ma/act/loi/70-19'),
        (2026, 'law', '50.25', world.URI)]


SUBTOTAL = 'مجموع ميزانيات مرافق الدولة المسيرة بصورة مستقلة التابعة لوزارة الصحة والحماية الاجتماعية'
TABLES = [
    '\n'.join(['الجدول - ب -',
               '| 1.2.1.1.0.06.000 | الموظفون والأعوان | 4 000 000 |',
               '| | مجموع وزارة العدل | 4 000 000 |',
               'الجدول «و»',
               '| الفصول | المرافق | اعتمادات الأداء | اعتمادات الالتزام | المجموع |',
               '|---|---|---|---|---|',
               '| 3.2.2.2.0.06.001 | مركز نشر المعلومة القانونية | 1 000 000 | 500 000 | 1 500 000 |',
               '| 3.2.2.2.0.06.002 | المعهد العالي للقضاء | 3 000 000 | 1 000 000 | 2 000 000 |',
               '| | مجموع وزارة العدل | 3 000 000 | 1 500 000 | 4 500 000 |']),
    '| 3.2.2.2.0.12.001 | المركز الاستشفائي الإقليمي | 4 000 000 | - | 4 000 000 |',
    '\n'.join(['| 3.2.2.2.0.12.002 | المركز الاستشفائي الجامعي | 3 000 000 | | 3 000 000 |',
               f'| | {SUBTOTAL} | 7 500 000 | - | 7 500 000 |',
               '| 3.2.2.2.0.20.001 | مختبر التجارب العمومية | 250 000 | | 250 000 |']),
]


def test_a_tables_blocks_that_do_not_add_up_to_their_subtotal_are_said_with_their_pages():
    text = world.finance_text(world.bulletin(TABLES, number=7259, suffix='', first=100), [], pages='100-102')
    FinanceLaw.objects.create(year=2024, kind='law', number='55.23', title=text.title_ar, text=text)
    # A two-credit row adds its payment, whichever order it was read in.
    assert run('diagnose_table', '2024', 'F').splitlines() == [
        f'DIFF p[101, 102] {SUBTOTAL[:80]}: total 7500000, lines 7000000, missing 500000',
        '7 rows; after the last total: 250000']
    assert run('diagnose_table', '2024', 'F', '-v', '2').splitlines()[0] == \
        'ok   p[100] مجموع وزارة العدل: total 3000000, lines 3000000, missing 0'
    assert run('diagnose_table', '2024', 'B', '-v', '2').splitlines() == [
        'ok   p[100] مجموع وزارة العدل: total 4000000, lines 4000000, missing 0', '2 rows; after the last total: 0']
    with pytest.raises(FinanceLaw.DoesNotExist):
        run('diagnose_table', '2024', 'F', '--kind', 'amending')
