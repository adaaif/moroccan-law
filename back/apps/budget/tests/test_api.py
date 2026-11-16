"""/api/budget/: a finance law's figures for readers, only from the tables whose every check passed; the years side by
side by their headline figures. Every list costs the same queries for a few rows as for many."""
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.budget.models import FinanceLaw, Line
from apps.budget.services.checks import run_checks
from apps.budget.services.extract import BALANCE, parse_balance
from apps.budget.services.load import load_finance_law
from apps.budget.tests import world
from apps.budget.tests.test_extract import BALANCE_2026
from apps.consolidation.models import Change
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document, Edition, Issue, Page

pytestmark = pytest.mark.django_db

NOT_FOUND = {'errors': [{'field': 'request', 'code': 'not_found'}]}
CGI = '/akn/ma/act/code/cgi'


def changes_by(uri, rows):
    Change.objects.bulk_create(Change(text_uri=to, number=n, verb='modified', source=source, by_kind='law',
                                      by_number='50-25', by_uri=uri) for to, n, source in rows)


def queries(api, url) -> tuple[int, dict]:
    with CaptureQueriesContext(connection) as seen:
        r = api.get(url)
    assert r.status_code == 200
    return len(seen), r.json()


def ministries(d):
    return [(m['code'], m['name'], m['state'], m['running'], m['investment'], m['commitment'], m['posts'], m['pages'])
            for m in d['ministries']]


@pytest.fixture
def law_2026():
    text = world.law_2026()
    return load_finance_law(text, year=2026, kind='law', number='50.25')


def test_a_year_answers_its_checked_figures_by_ministry_with_their_articles_and_pages(api, law_2026):
    text, doc = law_2026.text, law_2026.document
    Text.objects.create(akn_uri=CGI, type='code', title_ar='المدونة العامة للضرائب')
    Text.objects.create(akn_uri='/akn/ma/act/loi/25-00', type='law', number_as_printed='25.00')     # its title not read
    changes_by(world.URI, [(CGI, '73', 'reading'), (CGI, '6', 'reading'), ('/akn/ma/act/loi/25-00', '3', 'reading'),
                           ('/akn/ma/act/decret/2-99-1', '1', 'reading'),
                           ('/akn/ma/act/loi/7-81', '2', 'bill')])       # a bill's proposal is not the law's change
    d = api.get('/api/budget/laws/2026/').json()
    assert {k: d[k] for k in ('year', 'kind', 'number', 'title', 'filed', 'text_id', 'dahir', 'signed_on', 'issue')} == {
        'year': 2026, 'kind': 'law', 'number': '50.25', 'title': text.title_ar, 'filed': None, 'text_id': text.id,
        'dahir': '1.25.105', 'signed_on': '2025-12-27',
        'issue': {'edition': 'general_ar', 'key': '7465-bis', 'number': 7465, 'suffix': 'bis', 'date': '2025-12-31',
                  'document_id': doc.id}}
    assert d['page_index'] == {'99': 0, '100': 1, '101': 2, '102': 3, '103': 4, '104': 5}
    assert len(d['articles']) == 12 and d['articles']['42'] == {'eid': 'art_42', 'page': 100}
    assert len(d['balance']) == 40 and d['balance']['state_balance'] == {'amount': '-107577973000.00', 'page': 100}
    assert d['posts'] == [{'label': 'وزارة العدل', 'count': 1000, 'total': False},
                          {'label': 'وزارة الصحة و الحماية الاجتماعية', 'count': 30000, 'total': False},
                          {'label': 'وزارة الداخلية', 'count': 5000, 'total': False},
                          {'label': 'المجموع', 'count': 36000, 'total': True}]
    # Each ministry by the code's sixth part, its name from table B (C names it otherwise), the state's own charges
    # apart, its posts matched however the table spaces its «و»; the largest first.
    assert ministries(d) == [
        ('12', 'وزارة الصحة والحماية الاجتماعية', '', '200000000000.00', '6000000000.00', '3000000000.00', 30000,
         [100, 101]),
        ('common', 'التكاليف المشتركة - التسيير', 'common', '142490689000.00', '0', '0', None, [101]),
        ('contingencies', 'النفقات الطارئة والمخصصات الاحتياطية', 'contingencies', '0', '127106794000.00', '0', None,
         [102]),
        ('06', 'وزارة العدل', '', '5000000000.00', '1000000000.00', '500000000.00', 1000, [100, 101]),
        ('20', 'وزارة التجهيز والماء', '', '0', '2000000000.00', '0', None, [102])]
    assert d['ministries'][3]['chapters'] == [
        {'code': '1.2.1.1.0.06.000', 'label': 'الموظفون والأعوان', 'amount': '4120912000.00', 'page': 100},
        {'code': '1.2.1.2.0.06.000', 'label': 'المعدات والنفقات المختلفة', 'amount': '879088000.00', 'page': 100}]
    assert d['stated'] == {'posts': ['36395', '36000', '395'], 'B': ['347490689000'], 'C': ['139606794000', '136106794000'],
                           'D': ['108216932000'], 'E': ['1738331000'], 'F': ['300000000', '257133000'],
                           'G': ['167488686000']}
    assert d['sources']['balance'] == '37' and d['sources']['B'] == '42'
    # What the law does: each article under a subject of its own, in its part; the texts it changes, named.
    assert d['contents']['articles'] == [
        {'number': '1', 'eid': 'art_1', 'label': 'المادة الأولى', 'subject': 'الرسوم الجمركية', 'part': 'الباب الثاني',
         'page': 100},
        {'number': '20', 'eid': 'art_20', 'label': 'المادة 20', 'subject': 'مناصب مالية', 'part': 'الباب الثاني',
         'page': 100},
        {'number': '38', 'eid': 'art_38', 'label': 'المادة 38', 'subject': 'الموارد', 'part': 'الجزء الثاني', 'page': 100}]
    assert sorted(d['contents']['changes'], key=lambda c: c['path']) == [
        {'id': Text.objects.get(akn_uri=CGI).id, 'title': 'المدونة العامة للضرائب', 'type': 'code', 'number': '',
         'count': 2, 'path': '/ma/code/cgi'},
        {'id': None, 'title': '', 'type': '', 'number': '', 'count': 1, 'path': '/ma/decret/2-99-1'},
        {'id': Text.objects.get(number_as_printed='25.00').id, 'title': '', 'type': 'law', 'number': '25.00',
         'count': 1, 'path': '/ma/loi/25-00'}]
    checks = d['checks']
    assert (checks['count'], checks['passed'], checks['shown']) == (31, 31, ['B', 'C', 'D', 'E', 'F', 'G', 'balance', 'posts'])
    assert len(checks['items']) == 31 and checks['checked_at'] == law_2026.checked_at.isoformat().replace('+00:00', 'Z')


def test_a_table_that_fails_a_check_comes_back_empty_and_a_failing_balance_hides_the_balance(api, law_2026):
    page = Page.objects.get(document=law_2026.document, printed_number=100)
    page.text = page.text.replace('879 088 000', '879 038 000')
    page.save()
    article = Article.objects.get(version__text=law_2026.text, number='37', version__valid_from=date(2026, 7, 1))
    article.body = article.body.replace('18.180.175.000', '18.180.175.001')
    article.save()
    load_finance_law(law_2026.text, year=2026, kind='law', number='50.25')
    d = api.get('/api/budget/laws/2026/').json()
    assert d['balance'] is None and 'B' not in d['stated'] and d['posts'][-1]['count'] == 36000
    # Without table B the ministries come from table C alone, by its own names.
    assert ministries(d) == [
        ('contingencies', 'النفقات الطارئة والمخصصات الاحتياطية', 'contingencies', '0', '127106794000.00', '0', None,
         [102]),
        ('12', 'قطاع الصحة', '', '0', '6000000000.00', '3000000000.00', None, [101]),
        ('20', 'وزارة التجهيز والماء', '', '0', '2000000000.00', '0', None, [102]),
        ('06', 'وزارة العدل', '', '0', '1000000000.00', '500000000.00', 1000, [101])]
    assert (d['checks']['count'], d['checks']['passed'], d['checks']['shown']) == (
        31, 28, ['C', 'D', 'E', 'F', 'G', 'posts'])
    assert api.get('/api/budget/laws/').json()[0]['headline'] is None


def bill(year=2027, number='60-26'):
    """A bill as filed and as the first chamber voted it: the later stage stored first."""
    text = Text.objects.create(akn_uri=f'/akn/ma/act/projet-loi/{number}', type='bill', number=number,
                               title_ar=f'مشروع قانون المالية رقم {number.replace("-", ".")} للسنة المالية {year}')
    filed = Document.objects.create(source='mef', kind='parliament', sha256=number.ljust(64, 'f'), path='plf.pdf',
                                    mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now())
    Version.objects.create(text=text, language='ar', valid_from=date(year - 1, 11, 15), consolidation=Consolidation.BILL)
    Version.objects.create(text=text, language='ar', valid_from=date(year - 1, 10, 20), consolidation=Consolidation.BILL,
                           source_document=filed)
    return text, filed


def test_a_year_without_a_kind_answers_its_law_else_its_bill_and_a_missing_one_is_404(api):
    text, filed = bill()
    FinanceLaw.objects.create(year=2027, kind='bill', number='60.26', title=text.title_ar, text=text)
    changes_by(text.akn_uri, [(CGI, '73', 'bill'), (CGI, '6', 'bill'), (CGI, '9', 'reading')])
    d = api.get('/api/budget/laws/2027/').json()
    assert (d['kind'], d['issue'], d['dahir']) == ('bill', None, '')
    assert d['filed'] == {'on': '2026-10-20', 'document_id': filed.id, 'path': '/ma/projet-loi/60-26'}
    assert [(c['path'], c['count']) for c in d['contents']['changes']] == [('/ma/code/cgi', 2)]     # its proposals
    r = api.get('/api/budget/laws/2027/', {'kind': 'law'})
    assert (r.status_code, r.json()) == (404, NOT_FOUND)
    # A year with its law and its bill answers the law, unless the bill is asked for; a law kept without its text has
    # no pages, articles or contents.
    FinanceLaw.objects.create(year=2026, kind='law', number='50.25', title='قانون المالية رقم 50.25')
    FinanceLaw.objects.create(year=2026, kind='bill', number='50.25', title='مشروع قانون المالية رقم 50.25',
                              text=bill(2026, '50-25')[0])
    d = api.get('/api/budget/laws/2026/').json()
    assert {k: d[k] for k in ('kind', 'text_id', 'filed', 'issue', 'page_index', 'articles', 'balance', 'posts',
                              'ministries', 'stated', 'contents', 'checks')} == {
        'kind': 'law', 'text_id': None, 'filed': None, 'issue': None, 'page_index': {}, 'articles': {}, 'balance': None,
        'posts': None, 'ministries': [], 'stated': {}, 'contents': {'articles': [], 'changes': []},
        'checks': {'count': 0, 'passed': 0, 'shown': [], 'items': [], 'checked_at': None}}
    assert api.get('/api/budget/laws/2026/', {'kind': 'bill'}).json()['filed']['on'] == '2025-10-20'
    for url, query in (('/api/budget/laws/2030/', {}), ('/api/budget/laws/2026/', {'kind': 'settlement'})):
        r = api.get(url, query)
        assert (r.status_code, r.json()) == (404, NOT_FOUND)


def law_with(year, kind='law', *, drop=(), posts=(), stated=(), number=1):
    """A law kept with its BO issue and text, the 2026 balance less the lines in `drop`, its posts as (label, count)
    with the total last, and the figures its posts article states; checked."""
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=6000 + number, date=date(year - 1, 12, 31))
    text = Text.objects.create(akn_uri=f'/akn/ma/act/loi/{number}-{year}', type='law', first_published_in=issue)
    Version.objects.create(text=text, language='ar', valid_from=date(year, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    law = FinanceLaw.objects.create(year=year, kind=kind, number=f'{number}.{year % 100}', title='قانون المالية', text=text)
    lines = [Line(finance_law=law, table='balance', order=n, key=row['key'], label=row['label'], amount=row['amount'])
             for n, row in enumerate(parse_balance(BALANCE_2026)) if row['key'] not in drop]
    lines += [Line(finance_law=law, table='posts', order=n, label=label, amount=count, is_total=n == len(posts) - 1)
              for n, (label, count) in enumerate(posts)]
    Line.objects.bulk_create(lines)
    run_checks(law, {'posts': [Decimal(s) for s in stated]} if stated else {})
    return law


POSTS = [('وزارة العدل', 1000), ('وزارة الداخلية', 25000), ('المجموع', 26000)]


def test_the_years_side_by_side_each_with_its_headline_figures_when_its_balance_passed(api):
    law_with(2025, drop={'borrowing'}, posts=POSTS, number=1)       # its borrowing not printed: its parts add up
    law_with(2020, 'law', number=2)
    law_with(2027, 'bill', drop={key for key, _ in BALANCE}, number=3)
    law_with(2026, posts=POSTS, stated=['26395', '26000', '395'], number=4)
    law_with(2024, drop={'ordinary_revenue'}, posts=POSTS, number=5)      # revenue not printed: no headline
    law_with(2023, posts=POSTS[:2] + [('المجموع', 26001)], stated=['26395', '26000', '395'],
             number=6)                                                        # posts that do not add up are not said
    law_with(2020, 'amending', number=7)
    d = api.get('/api/budget/laws/').json()
    assert [(law['year'], law['kind']) for law in d] == [(2027, 'bill'), (2026, 'law'), (2025, 'law'), (2024, 'law'),
                                                         (2023, 'law'), (2020, 'amending'), (2020, 'law')]
    full = {'revenue': '421325037000.00', 'spending': '527648039000.00', 'deficit': '107577973000.00',
            'borrowing': '123000000000.00'}
    assert [law['headline'] for law in d] == [
        None, {**full, 'posts': 26395}, {**full, 'borrowing': None, 'posts': 26000}, None, {**full, 'posts': None},
        {**full, 'posts': None}, {**full, 'posts': None}]
    assert d[1]['issue'] == {'edition': 'general_ar', 'key': '6004', 'number': 6004, 'suffix': '', 'date': '2025-12-31',
                             'document_id': None}


def test_the_list_costs_the_same_queries_for_two_years_as_for_six(api):
    for year in (2026, 2025):
        law_with(year, posts=POSTS, stated=['26395', '26000', '395'], number=year)
    few, d = queries(api, '/api/budget/laws/')
    assert len(d) == 2
    for year in (2024, 2023, 2022):
        law_with(year, posts=POSTS, number=year)
    FinanceLaw.objects.create(year=2027, kind='bill', number='60.26', title='مشروع', text=bill()[0])
    many, d = queries(api, '/api/budget/laws/')
    assert len(d) == 6 and d[0]['filed']['on'] == '2026-10-20' and many == few


def test_a_years_answer_costs_the_same_queries_for_a_few_lines_as_for_many(api, law_2026):
    changes_by(world.URI, [(CGI, '73', 'reading')])
    few, d = queries(api, '/api/budget/laws/2026/')
    # Five more ministries in B and C (at zero, so the tables still add up), their posts, articles and changes.
    Line.objects.bulk_create(
        [Line(finance_law=law_2026, table=t, order=50 + n, code=f'1.2.{2 if t == "C" else 1}.1.0.{30 + n}.000',
              section=f'وزارة {n}', label=f'وزارة {n}', amount=0, page=101) for n in range(5) for t in 'BC']
        + [Line(finance_law=law_2026, table='posts', order=50 + n, label=f'وزارة {n}', amount=0) for n in range(5)]
        # The ministry's heading repeated otherwise on the next page: its first name stays.
        + [Line(finance_law=law_2026, table='B', order=59, code='1.2.1.2.0.30.000', section='تابع - وزارة 0',
                label='المعدات', amount=0, page=102)]
        # A line whose code was not read stands apart, under no ministry's number.
        + [Line(finance_law=law_2026, table='B', order=60, label='سطر بلا رمز', section='مرفق لم يقرأ رمزه', amount=0)]
        # A line of the posts that carries the state's own charges' name: the state is no ministry, it gets none.
        + [Line(finance_law=law_2026, table='posts', order=60, label='التكاليف المشتركة - التسيير', amount=0)])
    version = law_2026.text.versions.get(valid_from=date(2026, 7, 1))
    Article.objects.bulk_create(Article(version=version, order=50 + n, label=f'المادة {60 + n}', number=f'{60 + n}',
                                        body='نص.', heading_path=[f'موضوع {n}']) for n in range(5))
    changes_by(world.URI, [(f'/akn/ma/act/loi/{n}-99', '1', 'reading') for n in range(5)])
    many, d = queries(api, '/api/budget/laws/2026/')
    assert len(d['ministries']) == 11 and len(d['contents']['articles']) == 8 and len(d['contents']['changes']) == 6
    assert [(m['code'], m['name'], m['posts'], m['pages']) for m in d['ministries'] if m['code'] in ('', '30', 'common')] == [
        ('common', 'التكاليف المشتركة - التسيير', None, [101]), ('30', 'وزارة 0', 0, [101, 102]), ('', 'مرفق لم يقرأ رمزه', None, [])]
    assert many == few
