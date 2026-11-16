from decimal import Decimal

import pytest

from apps.budget.models import FinanceLaw, Line
from apps.budget.services.checks import run_checks
from apps.budget.services.extract import BALANCE, parse_balance
from apps.budget.tests.test_extract import BALANCE_2026


def _law_with_balance(**changes) -> FinanceLaw:
    law = FinanceLaw.objects.create(year=2026, kind='law', number='50.25', title='قانون المالية')
    for n, row in enumerate(parse_balance(BALANCE_2026)):
        amount = changes.get(row['key'], row['amount'])
        Line.objects.create(finance_law=law, table='balance', order=n, key=row['key'], label=row['label'], amount=amount)
    return law


def _table(law, table, amounts, commitments=None):
    for n, amount in enumerate(amounts):
        Line.objects.create(finance_law=law, table=table, order=n, code=f'1.2.1.1.0.{n:02d}.000', label='سطر',
                            amount=Decimal(amount), commitment=None if commitments is None else Decimal(commitments[n]))


@pytest.mark.django_db
def test_the_2026_balance_passes_every_sum_and_is_shown():
    law = _law_with_balance()
    checks = run_checks(law, {})
    sums = [c for c in checks if c['id'] == 'sum']
    assert len(sums) == 15 and all(c['ok'] for c in sums)
    assert 'balance' in law.tables_checked()


@pytest.mark.django_db
def test_one_wrong_figure_fails_its_sum_and_hides_the_whole_balance():
    law = _law_with_balance(customs=Decimal('18180175001'))
    run_checks(law, {})
    failed = [c for c in law.checks if not c['ok'] and c['id'] == 'sum']
    assert [c['args']['line'] for c in failed] == ['tax_revenue']
    assert 'balance' not in law.tables_checked()


@pytest.mark.django_db
def test_a_table_is_shown_only_when_it_adds_up_to_its_article_and_to_the_balance():
    law = _law_with_balance()
    _table(law, 'B', ['300000000000', '47490689000'])
    _table(law, 'C', ['100000000000', '36106794000'], ['50000000000', '29506574000'])
    run_checks(law, {'B': [Decimal('347490689000')], 'C': [Decimal('215613368000'), Decimal('136106794000')]})
    assert {'B', 'C', 'balance'} <= law.tables_checked()
    Line.objects.filter(finance_law=law, table='B', order=1).update(amount=Decimal('47490688000'))
    run_checks(law, {'B': [Decimal('347490689000')], 'C': [Decimal('215613368000'), Decimal('136106794000')]})
    assert 'B' not in law.tables_checked() and 'C' in law.tables_checked()


def _law_without(*keys, kind='law') -> FinanceLaw:
    law = FinanceLaw.objects.create(year=2026, kind=kind, number='50.25', title='قانون المالية')
    Line.objects.bulk_create(Line(finance_law=law, table='balance', order=n, key=row['key'], label=row['label'],
                                  amount=row['amount'])
                             for n, row in enumerate(parse_balance(BALANCE_2026)) if row['key'] not in keys)
    return law


@pytest.mark.parametrize('dropped, failing, shown', [
    # A subtotal the law prints without its amount: its sums are skipped, everything it is made of being there.
    ({'ordinary_revenue'}, [], True),
    # A line the sum needs is missing: the sum cannot be done, and fails.
    ({'direct_taxes'}, [('tax_revenue', '376081156000.00', None, 'line missing')], False),
    # A subtotal missing with one of its parts: neither it nor the sum above it can be done.
    ({'tax_revenue', 'direct_taxes'}, [('tax_revenue', None, None, 'line missing'),
                                       ('ordinary_revenue', '421325037000.00', None, 'line missing')], False),
])
@pytest.mark.django_db
def test_a_subtotal_the_law_does_not_print_is_no_missing_figure(dropped, failing, shown):
    law = _law_without(*dropped, kind='bill')      # a bill's annexes are not read: the balance's checks alone
    checks = run_checks(law, {})
    assert [(c['args']['line'], c['expected'], c['found'], c['source']) for c in checks if not c['ok']] == failing
    assert len(checks) == 15 - 2 * (dropped == {'ordinary_revenue'})
    assert ('balance' in law.tables_checked()) is shown


@pytest.mark.django_db
def test_a_table_with_no_balance_read_is_checked_against_its_article_alone():
    # A law in the layout before organic law 130.13: no balance to disagree with.
    law = _law_without(*[key for key, _ in BALANCE])
    _table(law, 'B', ['300000000000', '47490689000'])
    _table(law, 'D', ['44050556000', '64166376000'])
    checks = run_checks(law, {'B': [Decimal('347490689000')], 'D': [Decimal('108216932000')]})
    assert [(c['id'], c['ok']) for c in checks if c['tables'] in (['B'], ['D'])] == [('table_article', True),
                                                                                     ('table_article', True)]
    assert {'B', 'D'} <= law.tables_checked() and 'balance' not in law.tables_checked()


@pytest.mark.parametrize('debt, read, tables, balance_shown', [
    ('108216932000', False, ['balance'], True),
    ('108216932001', False, ['balance'], False),     # art. 44 against the balance alone: the balance is implicated
    ('108216932000', True, ['D'], True),
    ('108216932001', True, ['D'], True),             # table D was read: it is the one that answers for it
])
@pytest.mark.django_db
def test_the_debt_credits_vouch_for_table_d_when_it_was_read_else_for_the_balance(debt, read, tables, balance_shown):
    law = _law_without(kind='bill')
    if read:
        _table(law, 'D', ['44050556000', '64166376000'])
    checks = run_checks(law, {'D': [Decimal(debt)]})
    debt_check = next(c for c in checks if c['id'] == 'debt')
    assert (debt_check['tables'], debt_check['ok']) == (tables, debt == '108216932000')
    assert ('balance' in law.tables_checked()) is balance_shown


@pytest.mark.parametrize('lines, stated, checks', [
    ([('وزارة العدل', 1000, False), ('المجموع', 1000, True)], ['1395', '1000', '395'],
     [('posts_list', True, ''), ('posts_parts', True, '')]),
    ([('وزارة العدل', 1000, False), ('المجموع', 1000, True)], ['1395', '1000', '394'],
     [('posts_list', True, ''), ('posts_parts', False, '')]),
    ([('وزارة العدل', 1000, False)], [], [('posts_list', False, 'list not read')]),           # no total read
    ([], ['1395', '1000', '395'], [('posts_list', False, 'list not read'), ('posts_parts', True, '')]),
    ([], ['1395'], [('posts_list', False, 'list not read')]),       # one figure is no sum
    ([], [], []),
])
@pytest.mark.django_db
def test_the_posts_are_shown_when_the_ministries_add_up_to_the_total_and_the_parts_to_the_posts(lines, stated, checks):
    law = _law_without(kind='bill')
    Line.objects.bulk_create(Line(finance_law=law, table='posts', order=n, label=label, amount=count, is_total=total)
                             for n, (label, count, total) in enumerate(lines))
    got = run_checks(law, {'posts': [Decimal(s) for s in stated]} if stated else {})
    assert [(c['id'], c['ok'], c['source']) for c in got if c['tables'] == ['posts']] == checks
    assert ('posts' in law.tables_checked()) is (bool(checks) and all(ok for _, ok, _ in checks))
