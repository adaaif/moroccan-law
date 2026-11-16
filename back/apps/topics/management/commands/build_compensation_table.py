"""The table of law 70.24 (R3 and R13 of the road plan): the capital («رأس المال المعتمد») by yearly earnings and age
that the 1984 dahir on accident victims applies since 29 January 2026, assembled from BO 7478's pages 851–858 as the site
read them, and checked by its own arithmetic: a capital falls with age along a row and rises with earnings down a
column. A cell that breaks both, where its row and its column agree on another figure, is a misprint of the BO's: it is
kept as printed (the BO prevails) and named, with what the table's steps give. Five, each read against the page image:
66,000 at 41 (p. 853), 330,000 at 33 and 480,000 at 30 (p. 854), 114,000 at 44 (p. 855), 640,000 at 55 (p. 858).
The four transitional minimum rows of law 70.24 art. 5 (2026–2029) are read from that
article as the site holds it. Writes apps/topics/road/compensation.json, which the compensation tool reads.

    build_compensation_table
"""
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.corpus.models import Article
from apps.sources.models import Issue

OUT = Path(__file__).resolve().parents[2] / 'road' / 'compensation.json'
PAGES = range(851, 859)         # four age bands, each on two pages: earnings to 117,000, then from 120,000


def _rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if not line.startswith('|') or set(line) <= set('|-: '):
            continue
        cells = [c.strip().strip('*').strip() for c in line.strip().strip('|').split('|')]
        rows.append(cells)
    return rows


def _ages(header: list[str]) -> list[int | None]:
    """A header's cells as ages: «إلى غاية 18 سنة» is 18 (and under), «63 أو أكثر» is 63 (and over)."""
    out = []
    for cell in header:
        m = re.search(r'\d+', cell)
        out.append(int(m.group(0)) if m and 'الأجر' not in cell else None)
    return out


# Law 70.24 art. 5: for the four years from its entry into force, the minimum earnings and their capitals step up each
# 1 January (10,270 from 29 January 2026, then 11,270, 12,270, 13,270); the annex's own minimum (14,270) comes after.
STEPS = ('2026-01-29', '2027-01-01', '2028-01-01', '2029-01-01')


def minimum_rows(body: str) -> list[dict]:
    """Art. 5's transitional rows, read from its tables (ages in each table's head, earnings in the column so named)."""
    rows: dict[int, dict[int, int]] = {}
    ages: list[int | None] = []
    earn_at = 0
    for cells in _rows(body):
        if any('الأجر' in c for c in cells):
            ages, earn_at = _ages(cells), next(k for k, c in enumerate(cells) if 'الأجر' in c)
            continue
        if not ages or earn_at >= len(cells) or not re.fullmatch(r'\d+', cells[earn_at]):
            continue
        earnings = int(cells[earn_at])
        for k, age in enumerate(ages):
            if age is not None and k < len(cells) and re.fullmatch(r'\d+', cells[k]):
                rows.setdefault(earnings, {})[age] = int(cells[k])
    return [{'from': on, 'earnings': e, 'capital': rows[e]} for on, e in zip(STEPS, sorted(rows))]


def off_steps(grid: dict[int, dict[int, int]]) -> list[dict]:
    """The cells the table's own steps put elsewhere. A printed figure off by δ stands δ above the middle of its row's
    neighbours and, by the same δ, above its column's (earnings step unevenly, so the column is interpolated). A kink
    the whole table shares (age 37 from 670,000 up) moves the row alone and is the law's, not a misprint."""
    earnings = sorted(grid)
    ages = sorted({a for row in grid.values() for a in row})
    out = []
    for i in range(1, len(earnings) - 1):
        e0, e, e2 = earnings[i - 1:i + 2]
        t = (e - e0) / (e2 - e0)
        for j in range(1, len(ages) - 1):
            v = grid[e].get(ages[j])
            left, right = grid[e].get(ages[j - 1]), grid[e].get(ages[j + 1])
            up, down = grid[e0].get(ages[j]), grid[e2].get(ages[j])
            if None in (v, left, right, up, down):
                continue
            row, column = v - (left + right) / 2, v - (up * (1 - t) + down * t)
            if min(abs(row), abs(column)) >= 1000 and abs(row - column) <= abs(row) / 10:
                out.append({'earnings': e, 'age': ages[j], 'printed': v, 'steps': round(v - row)})
    return out


class Command(BaseCommand):
    help = "Assemble and check law 70.24's table of capitals from BO 7478, into apps/topics/road/compensation.json."

    def handle(self, *args, **opts):
        issue = Issue.objects.get(edition='general_ar', number=7478, suffix='')
        pages = {p.printed_number: _rows(p.text) for p in issue.document.pages.filter(printed_number__in=PAGES)}
        if set(pages) != set(PAGES):
            raise CommandError(f'pages missing: {sorted(set(PAGES) - set(pages))}')
        grid: dict[int, dict[int, int]] = {}         # earnings → age → capital
        where: dict[tuple[int, int], int] = {}        # (earnings, age) → printed page
        for first in (851, 853, 855, 857):
            header = next(r for r in pages[first] if any('الأجر' in c for c in r))
            ages = _ages(header)
            earn_at = next(k for k, c in enumerate(header) if 'الأجر' in c)
            for page in (first, first + 1):
                for row in pages[page]:
                    if row is header or not re.fullmatch(r'\d+', row[earn_at] if earn_at < len(row) else ''):
                        continue
                    earnings = int(row[earn_at])
                    for k, age in enumerate(ages):
                        if age is None or k >= len(row) or not re.fullmatch(r'\d+', row[k]):
                            continue
                        grid.setdefault(earnings, {})[age] = int(row[k])
                        where[(earnings, age)] = page
        earnings = sorted(grid)
        ages = sorted({a for row in grid.values() for a in row})
        holes = [(e, a) for e in earnings for a in ages if a not in grid[e]]
        misprints = [{**m, 'page': where[(m['earnings'], m['age'])]} for m in off_steps(grid)]
        art5 = Article.objects.filter(version__text__akn_uri='/akn/ma/act/loi/70-24', eid='art_5').first()
        steps = minimum_rows(art5.body) if art5 else []
        if len(steps) != 4 or any(sorted(m['capital']) != ages for m in steps):
            raise CommandError(f'law 70.24 art. 5: {len(steps)} transitional rows read, each needs ages {ages[0]}–{ages[-1]}')
        data = {
            'source': {'law': '/ma/loi/70-24', 'issue': 7478, 'pages': '851-858', 'in_force': '2026-01-29',
                       'dahir': '/ma/dahir/1-84-177/art_5'},
            'earnings': earnings, 'ages': ages,
            'capital': {str(e): [grid[e].get(a) for a in ages] for e in earnings},
            'page': {str(e): [where.get((e, a)) for a in ages] for e in earnings},
            'holes': holes, 'misprints': misprints,
            'minimum': [{**m, 'capital': [m['capital'][a] for a in ages]} for m in steps],
        }
        OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
        self.stdout.write(f'{len(earnings)} earnings × {len(ages)} ages = {sum(len(r) for r in grid.values())} cells; '
                          f'{len(holes)} holes; {len(misprints)} cells breaking the steps')
        for m in misprints:
            self.stdout.write(f'  {m}')
