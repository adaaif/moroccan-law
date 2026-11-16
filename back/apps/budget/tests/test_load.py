"""`load_finance_law`: a finance law from the corpus into budget lines (the balance and the posts from their articles,
tables B to G from the BO pages after them), then its checks. The law is `world`'s: 2026's balance with its tables cut
down to a few lines that still add up."""
from decimal import Decimal

import pytest

from apps.budget.models import FinanceLaw
from apps.budget.services.load import load_finance_law, table_chunks
from apps.budget.tests import world
from apps.sources.models import Page

pytestmark = pytest.mark.django_db


def rows(law, table, *fields):
    return [tuple(getattr(line, f) for f in fields) for line in law.lines.filter(table=table)]


def test_a_finance_law_is_read_from_its_articles_and_its_annexed_tables_and_all_its_checks_pass():
    text = world.law_2026()
    law = load_finance_law(text, year=2026, kind='law', number='50.25')
    assert (law.title, law.text, law.document) == (text.title_ar, text, text.first_published_in.document)
    assert {t: law.lines.filter(table=t).count() for t in ('balance', 'posts', 'A', 'B', 'C', 'D', 'E', 'F', 'G')} == {
        'balance': 40, 'posts': 4, 'A': 0, 'B': 5, 'C': 5, 'D': 2, 'E': 1, 'F': 1, 'G': 1}
    # Each line under its ministry, on its printed page; the tables of the texts before and after are not the law's.
    assert rows(law, 'B', 'code', 'section', 'label', 'amount', 'is_total', 'page') == [
        ('1.2.1.1.0.06.000', 'وزارة العدل', 'الموظفون والأعوان', Decimal('4120912000'), False, 100),
        ('1.2.1.2.0.06.000', 'وزارة العدل', 'المعدات والنفقات المختلفة', Decimal('879088000'), False, 100),
        ('1.2.1.1.0.12.000', 'وزارة الصحة والحماية الاجتماعية', 'الموظفون والأعوان', Decimal('200000000000'), False, 100),
        ('1.2.1.3.0.13.000', 'وزارة الصحة والحماية الاجتماعية', 'التكاليف المشتركة - التسيير', Decimal('142490689000'),
         False, 101),
        ('', 'وزارة الصحة والحماية الاجتماعية', 'مجموع الجدول «ب»', Decimal('347490689000'), True, 101)]
    # A two-credit row is payment and commitment, whichever order its sum says it was read in; a single figure has no
    # commitment, two equal figures have none to speak of.
    assert rows(law, 'C', 'label', 'amount', 'commitment') == [
        ('وزارة العدل', Decimal('1000000000'), Decimal('500000000')),
        ('قطاع الصحة', Decimal('6000000000'), Decimal('3000000000')),
        ('وزارة التجهيز والماء', Decimal('2000000000'), Decimal('0')),
        ('الاستثمار - النفقات الطارئة والمخصصات الاحتياطية', Decimal('127106794000'), None),
        ('مجموع الجدول «ج»', Decimal('136106794000'), Decimal('3500000000'))]
    assert rows(law, 'F', 'amount', 'commitment', 'page') == [(Decimal('257133000'), Decimal('42867000'), 103)]
    assert rows(law, 'D', 'amount') == [(Decimal('44050556000'),), (Decimal('64166376000'),)]
    # The posts: a ministry's sector and the posts swapped to regularise a staff are not counted again.
    assert rows(law, 'posts', 'label', 'amount', 'is_total', 'page') == [
        ('وزارة العدل', 1000, False, 100), ('وزارة الصحة و الحماية الاجتماعية', 30000, False, 100),
        ('وزارة الداخلية', 5000, False, 100), ('المجموع', 36000, True, 100)]
    balance = {line.key: (line.amount, line.page) for line in law.lines.filter(table='balance')}
    assert balance['ordinary_revenue'] == (Decimal('421325037000'), 100)
    assert balance['state_balance'] == (Decimal('-107577973000'), 100)
    # Each figure's article: the first that names its table alone (not the balance, which names B; not 41, which
    # names two; not 50, which comes after 42); table A's article states no checked figure.
    assert law.sources == {'balance': '37', 'posts': '20', 'B': '42', 'C': '43', 'D': '44', 'E': '45', 'F': '46',
                           'G': '47'}
    assert law.stated == {'posts': ['36395', '36000', '395'], 'B': ['347490689000'],
                          'C': ['139606794000', '136106794000'], 'D': ['108216932000'], 'E': ['1738331000'],
                          'F': ['300000000', '257133000'], 'G': ['167488686000']}
    assert len(law.checks) == 31 and all(c['ok'] for c in law.checks) and law.checked_at is not None
    assert next(c for c in law.checks if c['id'] == 'debt')['tables'] == ['D']     # D was read: it vouches for D
    assert law.tables_checked() == {'balance', 'posts', 'B', 'C', 'D', 'E', 'F', 'G'}


def test_loading_again_replaces_its_lines_and_a_misread_figure_hides_its_table_alone():
    text = world.law_2026()
    load_finance_law(text, year=2026, kind='law', number='50.25')
    text.title_ar = 'قانون المالية رقم 50.25 للسنة المالية 2026 (كما صحح)'
    text.save()
    pages = Page.objects.filter(document__issue=text.first_published_in)
    page, after = pages.get(printed_number=100), pages.get(printed_number=101),
    page.text = page.text.replace('879 088 000', '879 038 000')         # one figure of table B misread
    page.save()
    # Table C's justice row with its total misread (neither order adds up): payment and commitment are kept as
    # printed. Its equipment row with two figures that differ: the first is the payment, no commitment.
    after.text = after.text.replace('500 000 000 | 1 500 000 000', '500 000 000 | 1 600 000 000')
    after.save()
    later = pages.get(printed_number=102)
    later.text = later.text.replace('2 000 000 000 | | 2 000 000 000', '2 000 000 000 | | 1 000 000 000')
    later.save()
    law = load_finance_law(text, year=2026, kind='law', number='50.25')
    assert FinanceLaw.objects.get() == law and law.title == text.title_ar
    assert law.lines.filter(table='B').count() == 5 and law.lines.count() == 59
    assert rows(law, 'C', 'label', 'amount', 'commitment')[0::2] == [
        ('وزارة العدل', Decimal('1000000000'), Decimal('500000000')),
        ('وزارة التجهيز والماء', Decimal('2000000000'), None),
        ('مجموع الجدول «ج»', Decimal('136106794000'), Decimal('3500000000'))]
    failed = [(c['name'], c['expected'], c['found']) for c in law.checks if not c['ok']]
    assert failed == [('table B: running costs (art. 42)', '347490689000', '347490639000.00'),
                      ('table B against the balance', '347490689000.00', '347490639000.00')]
    assert law.tables_checked() == {'balance', 'posts', 'C', 'D', 'E', 'F', 'G'}


@pytest.mark.parametrize('change, stated', [
    ({}, ['36395', '36000', '395']),
    ({'يتم إحداث': 'يتـم إحداث'}, ['36395', '36000', '395']),       # the bill's own file stretches «يتـم»
    ({'لتوزيع 395 منصبا': 'لتوزيعها'}, []),                          # one of the three figures not read: none
])
def test_the_posts_article_states_its_three_figures_or_none(change, stated):
    body = world.POSTS
    for old, new in change.items():
        body = body.replace(old, new)
    text = world.finance_text(None, [('المادة 20', '20', body, [])], kind='bill', uri='/akn/ma/act/projet-loi/60-26')
    law = load_finance_law(text, year=2027, kind='bill', number='60.26')
    assert law.stated == {'posts': stated}
    assert [c['id'] for c in law.checks if c['tables'] == ['posts']] == ['posts_list'] + ['posts_parts'] * bool(stated)
    assert 'posts' in law.tables_checked()


def test_a_cell_the_reading_ran_a_paragraph_into_is_cut_to_its_column():
    words = 'نفقات ' * 90                  # 540 letters
    heading = 'وزارة ' * 55                 # 330 letters
    pages = [world.HEAD, '\n'.join([
        world.HEAD, 'الجدول - ب -',
        f'| 1.2.1.1.0.07.000 | {words}| 1 000 000 |',
        # A bold heading run into a row whose figures do not line up with its labels: the row is read whole.
        f'| 1.2.1.1.0.08.000 | **{heading}**<br>الموظفون والأعوان | 2 000 000<br>-<br>- |'])]
    posts = world.POSTS.replace('| وزارة الداخلية | 5.000 |', f'| {words} | 5.000 |')
    text = world.finance_text(world.bulletin(pages), [('المادة 20', '20', posts, [])], pages='100')
    law = load_finance_law(text, year=2026, kind='law', number='50.25')
    first, second = law.lines.filter(table='B')
    assert (first.label, first.amount) == (words.strip()[:500], 1000000)
    assert (second.section, second.label, second.amount) == (heading.strip()[:300], 'الموظفون والأعوان', 2000000)
    assert law.lines.get(table='posts', amount=5000).label == words.strip()[:500]


def test_a_tables_lines_come_from_the_texts_own_pages_and_a_bill_apart_from_its_annexes_has_none():
    issue = world.bulletin(world.PAGES)
    one_page = world.finance_text(issue, pages='103')
    assert {t: [page for page, _ in lines] for t, lines in table_chunks(one_page).items()} == {'F': [103], 'G': [103]}
    assert table_chunks(world.finance_text(None, uri='/akn/ma/act/projet-loi/60-26', kind='bill')) == {}
