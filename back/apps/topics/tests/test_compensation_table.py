"""`build_compensation_table` (R3, R13 of the road plan): law 70.24's capitals assembled from BO 7478's pages 851–858 as
read, checked by the table's own steps, with art. 5's four transitional rows; it refuses when a page or a row is
missing. A small table here: capital = 100,000 + 3 × earnings − 1,000 × age, one cell misprinted, one left blank."""
import json
from datetime import date

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document, Issue, Page
from apps.topics.management.commands import build_compensation_table as command

pytestmark = pytest.mark.django_db

EARNINGS = (10_000, 11_000, 12_000)
AGES = tuple(range(18, 26))
BANDS = {851: (18, 19), 853: (20, 21), 855: (22, 23), 857: (24, 25)}
MISPRINT = (11_000, 21)          # printed 10,000 above what its row and its column give
MINIMUM = (10_270, 11_270, 12_270, 13_270)
PRINTED = (12_270, 10_270, 13_270, 11_270)       # art. 5's rows as its tables give them: not in their years' order


def capital(e, a):
    return 100_000 + 3 * e - 1_000 * a + (10_000 if (e, a) == MISPRINT else 0)


def table(head, rows, earnings_first):
    """A table as the BO's pages are read: the earnings named in the first column, or in the last with the ages falling
    (the columns of a right-to-left table read from the left)."""
    def line(earnings, cells):
        return '| ' + ' | '.join([earnings, *cells] if earnings_first else [*cells[::-1], earnings]) + ' |'
    return [line('الأجر السنوي', head), '|---|---|---|', *(line(e, cells) for e, cells in rows)]


def band_pages(first, ages):
    """A band's two pages, the first band's earnings first and the others' last; 11,000 read before 10,000, and 12,000
    on the second page, its cell at age 24 printed blank, its cell at age 19 not read (a short row), its cell at the
    band's first age bold."""
    head = [f'إلى غاية {a} سنة' if a == 18 else f'{a} سنة' for a in ages]

    def row(e):
        cells = ['—' if (e, a) == (12_000, 24) else str(capital(e, a)) for a in ages]
        if e == 12_000:
            cells[0] = f'**{cells[0]}**'
            cells = cells[:1] if ages[1] == 19 else cells
        return str(e), cells
    one = ['الجريدة الرسمية', *table(head, [row(11_000), row(10_000)], first == 851)]
    two = table(head, [row(12_000)], first == 851)
    return {first: '\n'.join(one), first + 1: '\n'.join(two)}


def art5(earnings=PRINTED, ages=AGES, short=False):
    """Art. 5's transitional rows, its ages in two tables, the first with the earnings first, the second with them last;
    `short`: the first row of the first table without its last cell."""
    tables = []
    for part, earnings_first in ((ages[:4], True), (ages[4:], False)):
        rows = [(str(e), [str(50_000 + 2 * e - 500 * a) for a in part]) for e in earnings]
        if short and earnings_first:
            rows[0] = (rows[0][0], rows[0][1][:-1])
        lines = table([f'{a} سنة' for a in part], rows, earnings_first)
        tables.append('\n'.join([*lines[:2], '| بالدرهم | | | | |', *lines[2:]]))
    return 'تحدد مبالغ رأس المال الأدنى كما يلي:\n| السنة | 2026 |\n' + '\n\n'.join(tables)


@pytest.fixture
def out(tmp_path, monkeypatch):
    path = tmp_path / 'compensation.json'
    monkeypatch.setattr(command, 'OUT', path)        # never the code's own road/compensation.json
    return path


def issue(pages, body=None):
    scan = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='8' * 64, path='bo/7478.pdf',
                                   mime='application/pdf', bytes=1, language='ar', fetched_at=timezone.now())
    Issue.objects.create(edition='general_ar', number=7478, date=date(2026, 1, 29), document=scan)
    Page.objects.bulk_create(Page(document=scan, index=n - 851, printed_number=n, kind='scan', text=t)
                             for n, t in pages.items())
    if body is not None:
        text = Text.objects.create(akn_uri='/akn/ma/act/loi/70-24', type='law', number='70-24', title_ar='قانون رقم 70.24')
        v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 1, 29),
                                   consolidation=Consolidation.AS_PUBLISHED)
        Article.objects.create(version=v, order=5, label='المادة 5', number='5', eid='art_5', body=body)


def every_page():
    pages = {}
    for first, ages in BANDS.items():
        pages |= band_pages(first, ages)
    return pages


def test_the_table_is_assembled_from_its_eight_pages_with_its_misprint_named_and_art_5s_rows(out, capsys):
    issue(every_page(), art5())
    call_command('build_compensation_table')
    data = json.loads(out.read_text(encoding='utf-8'))
    printed = capital(*MISPRINT)
    assert data == {
        'source': {'law': '/ma/loi/70-24', 'issue': 7478, 'pages': '851-858', 'in_force': '2026-01-29',
                   'dahir': '/ma/dahir/1-84-177/art_5'},
        'earnings': list(EARNINGS), 'ages': list(AGES),
        'capital': {str(e): [None if (e, a) in ((12_000, 19), (12_000, 24)) else capital(e, a) for a in AGES]
                    for e in EARNINGS},
        'page': {'10000': [851, 851, 853, 853, 855, 855, 857, 857], '11000': [851, 851, 853, 853, 855, 855, 857, 857],
                 '12000': [852, None, 854, 854, 856, 856, None, 858]},
        'holes': [[12_000, 19], [12_000, 24]],
        'misprints': [{'earnings': 11_000, 'age': 21, 'printed': printed, 'steps': printed - 10_000, 'page': 853}],
        'minimum': [{'from': on, 'earnings': e, 'capital': [50_000 + 2 * e - 500 * a for a in AGES]}
                    for on, e in zip(('2026-01-29', '2027-01-01', '2028-01-01', '2029-01-01'), MINIMUM)],
    }
    assert capsys.readouterr().out.splitlines() == [
        '3 earnings × 8 ages = 22 cells; 2 holes; 1 cells breaking the steps',
        f"  {{'earnings': 11000, 'age': 21, 'printed': {printed}, 'steps': {printed - 10_000}, 'page': 853}}",
    ]


def test_a_missing_page_is_named_and_nothing_is_written(out):
    pages = every_page()
    del pages[856]
    issue(pages, art5())
    with pytest.raises(CommandError, match=r'^pages missing: \[856\]$'):
        call_command('build_compensation_table')
    assert not out.exists()


@pytest.mark.parametrize('body, read', [
    (None, 0),                                          # art. 5 not held here
    (art5(earnings=PRINTED[:3]), 3),                    # a transitional year missing
    (art5(ages=AGES[:-1]), 4),                          # an age missing from each row
    (art5(short=True), 4),                              # a cell not read in one row
], ids=['absent', 'three-years', 'an-age-short', 'a-cell-short'])
def test_art_5_must_give_four_rows_at_every_age_of_the_table(out, body, read):
    issue(every_page(), body)
    with pytest.raises(CommandError, match=rf'^law 70\.24 art\. 5: {read} transitional rows read, each needs ages 18–25$'):
        call_command('build_compensation_table')
    assert not out.exists()
