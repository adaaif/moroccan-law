"""The law's own arithmetic, re-done. A figure is shown only when every check on its table passes: a wrong number
on a budget page would cost the site its trust. Every check is exact (Decimal), never «close enough»."""
from decimal import Decimal

from django.utils import timezone

from apps.budget.models import FinanceLaw, Line

# The balance's sums: a line, and the lines that add up to it (a minus sign subtracts).
BALANCE_SUMS = [
    ('tax_revenue', ['direct_taxes', 'indirect_taxes', 'customs', 'registration']),
    ('non_tax_revenue', ['privatisation', 'monopolies', 'domain', 'other_revenue', 'gifts']),
    ('ordinary_revenue', ['tax_revenue', 'non_tax_revenue']),
    ('running', ['staff', 'materials', 'common', 'tax_refunds', 'contingencies']),
    ('ordinary_spending', ['running', 'interest']),
    ('ordinary_balance', ['ordinary_revenue', '-ordinary_spending']),
    ('general_balance', ['ordinary_balance', '-investment']),
    ('segma_spending', ['segma_running', 'segma_investment']),
    ('segma_balance', ['segma_revenue', '-segma_spending']),
    ('cst_balance', ['cst_revenue', '-cst_spending']),
    ('state_balance', ['general_balance', 'segma_balance', 'cst_balance']),
    ('amortisation', ['amortisation_internal', 'amortisation_external']),
    ('gross_needs', ['state_balance', '-amortisation']),
    ('borrowing', ['borrowing_internal', 'borrowing_external']),
    ('remaining_needs', ['gross_needs', 'borrowing']),
]

# What each table must add up to: its article's stated amount, and the balance's line.
TABLE_TOTALS = {
    'B': ('running', 'running costs (art. 42)'),
    'C': ('investment', 'investment, payment credits (art. 43)'),
    'D': (None, 'public debt (art. 44)'),
    'E': ('segma_running', 'autonomous services, running costs (art. 45)'),
    'F': ('segma_investment', 'autonomous services, investment, payment credits (art. 46)'),
    'G': ('cst_spending', 'special accounts (art. 47)'),
}


def _check(name: str, expected, found, tables: list[str], source: str = '', *, id: str = '', **args) -> dict:
    """`id` and `args` let a page say the check in its own language («balance» line «tax_revenue»…)."""
    ok = expected is not None and found is not None and Decimal(expected) == Decimal(found)
    return {'name': name, 'id': id, 'args': args, 'expected': None if expected is None else str(expected),
            'found': None if found is None else str(found), 'ok': ok, 'tables': tables, 'source': source}


def run_checks(law: FinanceLaw, stated: dict[str, list[Decimal]]) -> list[dict]:
    """`stated`: the amounts each table's article states in figures, by table letter (art. 42 → 'B'…)."""
    checks = []
    balance = {line.key: line.amount for line in law.lines.filter(table='balance')}
    sums = dict(BALANCE_SUMS)
    for key, parts in BALANCE_SUMS:
        missing = [p.lstrip('-') for p in parts if p.lstrip('-') not in balance] + ([key] if key not in balance else [])
        # A subtotal the law does not print (2024: «نفقات ميزانيات مرافق الدولة… :» with no amount, its parts
        # under it) is no missing figure: its checks are skipped when everything it is made of is there.
        if missing and all(m in sums and all(q.lstrip('-') in balance for q in sums[m]) for m in missing):
            continue
        if missing:
            checks.append(_check(f'balance: {key}', balance.get(key), None, ['balance'], 'line missing',
                                 id='sum', line=key))
            continue
        total = sum((-balance[p[1:]] if p.startswith('-') else balance[p]) for p in parts)
        checks.append(_check(f'balance: {key}', balance[key], total, ['balance'], id='sum', line=key))

    for table, (balance_key, what) in TABLE_TOTALS.items():
        lines = list(law.lines.filter(table=table, is_total=False))
        if not lines:
            # A bill's annexes are files of their own, not read: no table, so nothing to check (and nothing shown).
            if law.kind == 'bill':
                continue
            checks.append(_check(f'table {table}: {what}', None, None, [table], 'table not read',
                                 id='table_article', table=table))
            continue
        paid = sum((line.amount or 0) for line in lines)
        said = stated.get(table) or []
        # Two-column tables (payment and commitment credits): the article gives the whole, then the payments.
        expected = said[-1] if table in ('C', 'F') and len(said) > 1 else (said[0] if said else None)
        checks.append(_check(f'table {table}: {what}', expected, paid, [table], 'the article, in figures',
                             id='table_article', table=table))
        if table in ('C', 'F') and len(said) > 1:
            whole = paid + sum((line.commitment or 0) for line in lines)
            checks.append(_check(f'table {table}: payment and commitment credits', said[0], whole, [table],
                                 id='table_two_credits', table=table))
        if balance_key and balance.get(balance_key) is not None:
            # A disagreement implicates the table: the balance stands on its own sums. With no balance read
            # (a law in the layout before organic law 130.13) there is nothing to disagree with.
            checks.append(_check(f'table {table} against the balance', balance.get(balance_key), paid,
                                 [table], id='table_balance', table=table, line=balance_key))
    if 'interest' in balance and 'amortisation' in balance and stated.get('D'):
        # Art. 44's amount against the balance: it vouches for table D only when D was read (a bill's annexes are
        # other files: the check is the balance's then, and no empty table D is shown).
        tables = ['D'] if law.lines.filter(table='D').exists() else ['balance']
        checks.append(_check('debt credits: interest and repayments', stated['D'][0],
                             balance['interest'] + balance['amortisation'], tables, id='debt'))

    posts = list(law.lines.filter(table='posts'))
    listed = [line for line in posts if not line.is_total]
    totals = [line for line in posts if line.is_total]
    if listed and totals:
        checks.append(_check('posts: the ministries add up to the total', totals[0].amount,
                             sum(line.amount for line in listed), ['posts'], id='posts_list'))
    elif posts or stated.get('posts'):
        checks.append(_check('posts: the ministries add up to the total', None, None, ['posts'], 'list not read',
                             id='posts_list'))
    if stated.get('posts') and len(stated['posts']) >= 2:
        checks.append(_check('posts: the parts add up to the posts created', stated['posts'][0],
                             sum(stated['posts'][1:]), ['posts'], id='posts_parts'))

    law.checks, law.checked_at = checks, timezone.now()
    law.stated = {table: [str(a) for a in amounts] for table, amounts in stated.items()}
    law.save(update_fields=['checks', 'checked_at', 'stated'])
    return checks


def failing(law: FinanceLaw) -> list[dict]:
    return [c for c in law.checks if not c['ok']]


def shown_lines(law: FinanceLaw, table: str) -> list[Line]:
    """A table's lines, only when its every check passed."""
    return list(law.lines.filter(table=table)) if table in law.tables_checked() else []
