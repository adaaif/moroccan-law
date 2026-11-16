"""A finance law from the corpus into budget lines: the balance and the posts from their articles, tables A to G
from the BO pages after the articles. Then the checks decide what can be shown."""
import re
from decimal import Decimal

from django.db import transaction

from apps.budget.models import FinanceLaw, Line
from apps.budget.services.checks import run_checks
from apps.budget.services.extract import parse_balance, parse_coded_table, parse_posts, stated_amounts
from apps.corpus.models import Text
from apps.corpus.services.issue_structure import issue_lines
from apps.sources.services.compare import fold

LETTERS = {'أ': 'A', 'ا': 'A', 'ب': 'B', 'ج': 'C', 'د': 'D', 'هـ': 'E', 'ه': 'E', 'و': 'F', 'ز': 'G'}
_TABLE_HEAD = re.compile(r'^الجدول\s*[-–(«»"\']*\s*(هـ|[أابجدهوز])\s*[-–)«»"\']*\s*$')
_TABLE_REF = re.compile(r'الجدول\s*[«»"\'(]*\s*(هـ|[أابجدهوز])\s*[«»"\')]')


def table_chunks(text: Text) -> dict[str, list[tuple[int, str]]]:
    """The law's annexed tables: each heading «الجدول - ب -» to the next, with its printed pages. A bill printed apart
    from its annexes (the ministry's files, the finance-bill review, P4) has none."""
    if text.first_published_in_id is None:
        return {}
    version = text.versions.order_by('-valid_from').first()
    lo, _, hi = version.source_pages.partition('-')
    lines = [(page, line) for page, line in issue_lines(text.first_published_in)
             if int(lo) <= page <= int(hi or lo)]
    chunks, current = {}, None
    for page, line in lines:
        m = _TABLE_HEAD.match(line.replace('ـ', ''))
        if m:
            current = LETTERS[m.group(1)]
            chunks.setdefault(current, [])
            continue
        if current:
            chunks[current].append((page, line))
    return chunks


_POSTS = [r'يتم إحداث\s+([\d.\s]+?)\s*منصب', r'(?m)^\s*1\s*-\s*([\d.\s]+?)\s*منصب', r'لتوزيع\s+([\d.\s]+?)\s*منصب']


def posts_stated(body: str) -> list[Decimal]:
    """The posts article's own sum: the posts created, those listed by ministry, those the Head of Government
    distributes. (A later clause swaps posts at one ministry to regularise its staff: no new job, not counted.)"""
    body = body.replace('ـ', '')    # the bill's own file stretches «يتـم»
    found = [re.search(pattern, body) for pattern in _POSTS]
    return [Decimal(re.sub(r'\D', '', m.group(1))) for m in found] if all(found) else []


def _columns(amounts: list[Decimal]) -> tuple[Decimal, Decimal | None]:
    """A two-credit row → (payment, commitment). The table prints payment, commitment, total; a «-» for no
    commitment leaves payment and total. The row's own sum says which reading holds."""
    if len(amounts) >= 3:
        p, c, t = amounts[:3]
        if p + c == t:
            return p, c
        if t + c == p:          # read the other way round: total, commitment, payment
            return t, c
        return p, c
    if len(amounts) == 2 and amounts[0] == amounts[1]:
        return amounts[0], Decimal(0)
    return amounts[0], None


@transaction.atomic
def load_finance_law(text: Text, *, year: int, kind: str, number: str) -> FinanceLaw:
    issue = text.first_published_in
    law, _ = FinanceLaw.objects.update_or_create(year=year, kind=kind, number=number, defaults={
        'title': text.title_ar, 'text': text, 'document': issue.document if issue else None})
    law.lines.all().delete()
    articles = list(text.versions.order_by('-valid_from').first().articles.order_by('order'))
    lines, stated, sources = [], {}, {}

    balance_art = next((a for a in articles if fold('المداخيل العادية للميزانية العامة') in fold(a.body)), None)
    if balance_art:
        sources['balance'] = balance_art.number
        for n, row in enumerate(parse_balance(balance_art.body)):
            lines.append(Line(finance_law=law, table='balance', order=n, key=row['key'], label=row['label'],
                              amount=row['amount'], page=balance_art.printed_page))

    posts_art = next((a for a in articles if 'منصب' in a.body and 'إحداث' in a.body), None)
    if posts_art:
        sources['posts'] = posts_art.number
        stated['posts'] = posts_stated(posts_art.body)
        for n, row in enumerate(parse_posts(posts_art.body)):
            lines.append(Line(finance_law=law, table='posts', order=n, label=row['label'][:500],
                              amount=row['amount'], is_total=row['is_total'], page=posts_art.printed_page))

    for article in articles:
        refs = {LETTERS[m] for m in _TABLE_REF.findall(article.body)}
        if len(refs) == 1 and (letter := refs.pop()) in 'BCDEFG' and article is not balance_art:
            stated.setdefault(letter, stated_amounts(article.body))
            sources.setdefault(letter, article.number)

    for letter, chunk in table_chunks(text).items():
        for n, row in enumerate(parse_coded_table(chunk)):
            payment, commitment = (_columns(row['amounts']) if letter in 'CF'
                                   else (row['amounts'][0], None))
            lines.append(Line(finance_law=law, table=letter, order=n, code=row['code'], section=row['section'][:300],
                              label=row['label'][:500], amount=payment, commitment=commitment,
                              is_total=row['is_total'], page=row['page']))
    Line.objects.bulk_create(lines)
    law.sources = sources
    law.save(update_fields=['sources'])
    run_checks(law, stated)
    return law

