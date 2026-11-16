"""A finance law's figures out of its OCR'd pages: the balance (art. 37), the credits the articles state, the
posts created, and tables A to G. Nothing is computed here; `checks.py` decides what can be shown."""
import re
from decimal import Decimal

from apps.sources.services.compare import fold

# The balance's lines, in the order the article prints them. Each is matched to the next line holding its words,
# so a short label («الداخلي») can only take the line meant for it. Labels are kept to their distinctive words:
# the OCR misspells the rest («الممائلة»).
BALANCE = [
    ('ordinary_revenue', 'المداخيل العادية للميزانية العامة'),
    ('tax_revenue', 'المداخيل الضريبية'),
    ('direct_taxes', 'الضرائب المباشرة'),
    ('indirect_taxes', 'الضرائب غير المباشرة'),
    ('customs', 'الرسوم الجمركية'),
    ('registration', 'رسوم التسجيل والتمبر'),
    ('non_tax_revenue', 'المداخيل غير الضريبية'),
    ('privatisation', 'حصيلة تفويت مساهمات الدولة'),
    ('monopolies', 'حصيلة مؤسسات الاحتكار'),
    ('domain', 'عائدات أملاك الدولة'),
    ('other_revenue', 'موارد مختلفة'),
    ('gifts', 'موارد الهبات والوصايا'),
    ('ordinary_spending', 'النفقات العادية للميزانية العامة'),
    ('running', 'نفقات التسيير'),
    ('staff', 'نفقات الموظفين'),
    ('materials', 'نفقات المعدات والنفقات المختلفة'),
    ('common', 'التكاليف المشتركة'),
    ('tax_refunds', 'الإرجاعات الضريبية'),
    ('contingencies', 'النفقات الطارئة والمخصصات الاحتياطية'),
    ('interest', 'نفقات الفوائد والعمولات'),
    ('ordinary_balance', 'الرصيد العادي'),
    ('investment', 'نفقات الاستثمار للميزانية العامة'),
    ('general_balance', 'رصيد الميزانية العامة'),
    ('segma_revenue', 'موارد ميزانيات مرافق الدولة المسيرة بصورة مستقلة'),
    ('segma_spending', 'نفقات ميزانيات مرافق الدولة المسيرة بصورة مستقلة'),
    ('segma_running', 'نفقات الاستغلال'),
    ('segma_investment', 'نفقات الاستثمار'),
    ('segma_balance', 'رصيد مرافق الدولة المسيرة بصورة مستقلة'),
    ('cst_revenue', 'موارد الحسابات الخصوصية للخزينة'),
    ('cst_spending', 'نفقات الحسابات الخصوصية للخزينة'),
    ('cst_balance', 'رصيد الحسابات الخصوصية للخزينة'),
    ('state_balance', 'رصيد ميزانية الدولة'),
    ('amortisation', 'استهلاكات الدين العمومي المتوسط والطويل الأجل'),
    ('amortisation_internal', 'الداخلي'),
    ('amortisation_external', 'الخارجي'),
    ('gross_needs', 'الإجمالية لتمويل ميزانية الدولة'),
    ('borrowing', 'موارد الاقتراضات المتوسطة والطويلة الأجل'),
    ('borrowing_internal', 'الداخلية'),
    ('borrowing_external', 'الخارجية'),
    ('remaining_needs', 'المتبقية لتمويل ميزانية الدولة'),
]

# An amount as the OCR writes it: «421.325.037.000», «421 325 037 000», «38.562,85», «-106.323.002.000».
_AMOUNT = re.compile(r'(?<![\d.,])(\d{1,3}(?:[ . ]\d{3})+|\d{4,})(?:,(\d{1,2}))?(?![\d])')
_MARKER = re.compile(r'\(\s*\d{1,2}\s*\)')            # «(1)», «(5) = (4)-(3)»: the balance's line numbers
CODE = re.compile(r'\d\.\d\.\d\.\d\.\d\.\d{2}\.\d{3}')  # a budget code: «1.2.1.1.0.06.000»
# No amount of a Moroccan budget reaches 10 trillion dirhams (the whole budget is under one trillion).
MAX_DIGITS = 13


def amounts_in(line: str) -> list[tuple[Decimal, int, int]]:
    """Every amount in a line with its span, signed when a minus sign touches it on either side."""
    clean = _MARKER.sub(lambda m: ' ' * len(m.group(0)), line)
    out = []
    for m in _AMOUNT.finditer(clean):
        whole = re.sub(r'\D', '', m.group(1))
        if len(whole) > MAX_DIGITS:      # two amounts the reading ran together («200000200000150000»)
            continue
        digits = whole + (f'.{m.group(2)}' if m.group(2) else '')
        before, after = clean[max(0, m.start() - 2):m.start()], clean[m.end():m.end() + 2]
        sign = -1 if re.search(r'[-–−]\s?$', before) or re.match(r'^\s?[-–−]', after) else 1
        out.append((sign * Decimal(digits), m.start(), m.end()))
    return out


def _squeeze(text: str) -> str:
    """Folded and without spaces: the OCR drops or adds them («الاستثمارللميزانية», «و الوصايا»)."""
    return fold(text).replace(' ', '')


def parse_balance(text: str) -> list[dict]:
    """The balance article's lines → [{key, label, amount}], in order. A label may run over several lines; its
    amount closes it. A dash where the amount belongs is zero."""
    rows, pending, k = [], '', 0
    for raw in text.splitlines():
        line = raw.strip().strip('|').strip()
        if not line:
            continue
        found = amounts_in(line)
        # A dash or «للتذكرة» (pro memoria) where the amount belongs is zero.
        nothing = not found and (re.search(r'[.…\s|]\s*[-–]\s*\|?$', line) or 'للتذكرة' in line)
        if not found and not nothing:
            pending = f'{pending} {line}'.strip()
            continue
        # The line's own words first: a heading printed without its amount («نفقات ميزانيات مرافق الدولة… :»)
        # must not take the amount of the line under it. The label above is joined only when the line alone
        # names nothing (a label that runs over two lines).
        for text in (_squeeze(line), _squeeze(f'{pending} {line}')):
            match = next((j for j in range(k, len(BALANCE)) if _squeeze(BALANCE[j][1]) in text), None)
            if match is not None:
                key, label = BALANCE[match]
                rows.append({'key': key, 'label': label, 'amount': found[-1][0] if found else Decimal(0)})
                k = match + 1
                break
        pending = ''
    return rows


def stated_amounts(text: str) -> list[Decimal]:
    """The amounts an article states in figures, in order: «(347.490.689.000) درهم»."""
    return [a for part in re.findall(r'\(([\d. ,]+)\)', text) for a, _, _ in amounts_in(part)]


def parse_posts(text: str) -> list[dict]:
    """Art. «إحداث مناصب مالية»: each ministry with its number of posts, and the totals. A table row is read by
    its cells in whatever order the OCR wrote them (label | count, or count | label)."""
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('|'):
            cells = [c.replace('**', '').strip() for c in line.strip('|').split('|')]
            labels = [c for c in cells if re.search(r'[\u0621-\u064A]', c)]
            counts = [c for c in cells if re.fullmatch(r'\d{1,3}(?:[ .]\d{3})*|\d+', c)]
            if len(labels) != 1 or len(counts) != 1:
                continue
            label, count = re.sub(r'[.…]{2,}', ' ', labels[0]).strip(' .:'), counts[0]
        else:
            m = re.match(r'^(.*?[\u0621-\u064A].*?)[\s.…|]+(\d{1,3}(?:[ .]\d{3})*|\d+)\s*\|?$', line)
            if not m:
                continue
            label, count = m.group(1).strip(' .:'), m.group(2)
        if 'منصب' in label and not label.startswith('المجموع'):
            continue
        if label.startswith(('-', '–', '•')):
            continue        # a sector under its ministry («- قطاع التربية الوطنية»): the ministry's line counts it
        label = label.rstrip(' :')
        rows.append({'label': label, 'amount': Decimal(re.sub(r'\D', '', count)), 'is_total': label.startswith('المجموع')})
    return rows


_ARABIC = re.compile(r'[\u0621-\u064A]')
_MEMO = 'للتذكرة'      # «pro memoria»: a line kept in the budget with no estimate


def _cell_amount(cell: str) -> Decimal | None:
    cell = cell.replace('**', '').strip()
    if cell == _MEMO or re.fullmatch(r'[-–]+', cell):
        return Decimal(0)
    found = amounts_in(cell)
    return found[0][0] if len(found) == 1 else None


def _clean(cell: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[.…]{2,}', ' ', cell.replace('**', ''))).strip(' -–.…')


_BR = re.compile(r'<br\s*/?>')


def _unpack(cells: list[str]) -> list[list[str]]:
    """A row the OCR packed with several («**وزارة العدل**<br>مركز…<br>المعهد…<br>**مجموع…**», its codes and amounts
    packed alike) → one row each. Leading bold headings have no amount; the codes go, in order, to the rows that
    are neither headings nor totals. A row that does not line up is returned as it was."""
    split = [_BR.split(c) for c in cells]
    worded = [i for i, c in enumerate(cells) if _ARABIC.search(c) and c.strip() != _MEMO]
    if not worded or len(split[worded[-1]]) == 1:
        return [cells]
    at = worded[-1]
    labels = split[at]
    headings = 0
    while headings < len(labels) and labels[headings].strip().startswith('**') \
            and not _clean(labels[headings]).startswith(('مجموع', 'المجموع')):
        headings += 1
    items = [n for n, label in enumerate(labels) if n >= headings and not _clean(label).startswith(('مجموع', 'المجموع'))]
    out = [[''] * len(cells) for _ in labels]
    for i, parts in enumerate(split):
        if i == at:
            column = labels
        elif i > at:
            if len(parts) == len(labels):
                column = parts
            elif len(parts) == len(labels) - headings:
                column = [''] * headings + parts
            else:
                return [cells]
        else:
            if len(parts) == len(labels):
                column = parts
            elif len(parts) <= len(items):
                column = [''] * len(labels)
                for n, part in zip(items, parts):
                    column[n] = part
            else:
                return [cells]
        for n, part in enumerate(column):
            out[n][i] = part.strip()
    return out


def _reading_order(cells: list[str]) -> list[str]:
    """A row the OCR wrote left to right (amount | label | code): the code after the label gives it away."""
    worded = [i for i, c in enumerate(cells) if _ARABIC.search(c) and c.strip() != _MEMO]
    if worded and any(CODE.search(c) for c in cells[worded[-1] + 1:]) and not any(CODE.search(c) for c in cells[:worded[0]]):
        return cells[::-1]
    return cells


def parse_coded_table(lines: list[tuple[int, str]]) -> list[dict]:
    """A table of budget lines → [{code, section, label, amounts, page, is_total}]. Read by cells: the label is
    the last cell with words, the amounts are the cells after it («للتذكرة» and «-» are zero), the budget code is
    in a cell before it. A row with words and no amount names the ministry (the section) of the rows under it, and
    so does a bold heading run into its first row («**وزارة الصحة**<br>المركز…»); «مجموع» rows are totals. Header
    rows (the row above «|---|») are skipped."""
    rows, section = [], ''
    table = [(page, line.strip()) for page, line in lines if line.strip().startswith('|')]
    cells_of = [[c.strip() for c in line.strip('|').split('|')] for _, line in table]
    rule = [all(set(c) <= set('-: ') for c in cells) for cells in cells_of]
    unpacked = []
    for n, ((page, _), cells) in enumerate(zip(table, cells_of)):
        if rule[n] or (n + 1 < len(rule) and rule[n + 1]):
            continue
        unpacked.extend((page, _reading_order(row)) for row in _unpack(cells))
    for page, cells in unpacked:
        worded = [i for i, c in enumerate(cells) if _ARABIC.search(c) and c != _MEMO]
        if not worded:
            continue
        at = worded[-1]
        parts = re.split(r'<br\s*/?>', cells[at])
        if len(parts) > 1 and parts[0].strip().startswith('**'):
            section, parts = _clean(parts[0]), parts[1:]
        label = _clean(' '.join(parts))
        found = [_cell_amount(c) for c in cells[at + 1:] if c.strip()]
        code = next((m.group(0) for c in cells[:at] if (m := CODE.search(c))), '')
        if not found or any(a is None for a in found):
            if not code and len(label) < 160:
                section = label
            continue
        rows.append({'code': code, 'section': section, 'label': label, 'amounts': found, 'page': page,
                     'is_total': label.startswith(('المجموع', 'مجموع'))})
    return rows
