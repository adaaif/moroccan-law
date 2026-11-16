"""The Hijri calendar as the Bulletin itself dates things (W4 of the library-search review, 10 Nov 2026).

Morocco's Hijri months begin when the crescent is seen: no table of astronomy gives the Bulletin's dates. But every text
and every issue prints both dates, and those pairs fix the first day of each month: «9 رمضان 1331 (12 غشت 1913)» puts
1 Ramadan 1331 on 4 August 1913. `data/hijri_months.json` keeps the first day of every month the pairs agree on
(`manage.py hijri_months --write` builds it from the texts' and the issues' own dates); a month they do not fix is
counted from the nearest one they do, and said to be an estimate."""
import json
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import ma_law

FILE = Path(__file__).resolve().parent.parent / 'data' / 'hijri_months.json'
MONTHS = ['محرم', 'صفر', 'ربيع الأول', 'ربيع الآخر', 'جمادى الأولى', 'جمادى الآخرة', 'رجب', 'شعبان', 'رمضان', 'شوال',
          'ذو القعدة', 'ذو الحجة']
# The spellings the Bulletin and people give each month, as `ma_law.fold` leaves them.
_NAMES = [('محرم', 1), ('صفر', 2), ('ربيع الاول', 3), ('ربيع الثاني', 4), ('ربيع الاخر', 4), ('جمادي الاولي', 5),
          ('جمادي الاول', 5), ('جمادي الثانيه', 6), ('جمادي الاخره', 6), ('جمادي الثاني', 6), ('جمادي الاخر', 6), ('رجب', 7),
          ('شعبان', 8), ('رمضان', 9), ('شوال', 10), ('ذي القعده', 11), ('ذو القعده', 11), ('القعده', 11), ('قعده', 11),
          ('ذي الحجه', 12), ('ذو الحجه', 12), ('الحجه', 12), ('حجه', 12)]
_NUMBER = dict(_NAMES)
_DATE = re.compile(r'(?<!\d)(\d{1,2}|فاتح)\s+(?:من\s+)?(' + '|'.join(sorted(_NUMBER, key=len, reverse=True))
                   + r')(?:\s+(?:المعظم|الحرام|الخير|الفرد|الابرك))?\s+(?:عام\s+|سنه\s+)?(1[34]\d\d)(?!\d)')
LUNATION = 29.530588


def parse(text: str) -> tuple[int, int, int, str] | None:
    """(day, month, year, the words read) of the first Hijri date written in `text`: «9 رمضان 1331», «فاتح محرم 1405»,
    «14 من رجب 1424»."""
    folded = ma_law.fold(text)
    m = _DATE.search(folded)
    if not m:
        return None
    day = 1 if m.group(1) == 'فاتح' else int(m.group(1))
    if not 1 <= day <= 30:
        return None
    return day, _NUMBER[m.group(2)], int(m.group(3)), m.group(0)


@lru_cache(maxsize=1)
def _starts() -> dict[tuple[int, int], date]:
    try:
        raw = json.loads(FILE.read_text())
    except FileNotFoundError:
        return {}
    return {tuple(map(int, k.split('-'))): date.fromisoformat(v) for k, v in raw.items()}


@lru_cache(maxsize=1)
def _ordered() -> list[tuple[date, int, int]]:
    return sorted((d, y, m) for (y, m), d in _starts().items())


def month_start(year: int, month: int) -> tuple[date, bool] | None:
    """(the Gregorian day of the month's 1st, whether the Bulletin's dates fix it)."""
    known = _starts()
    if (year, month) in known:
        return known[(year, month)], True
    if not known:
        return None
    (y, m), start = min(known.items(), key=lambda item: abs((year * 12 + month) - (item[0][0] * 12 + item[0][1])))
    return start + timedelta(days=round(((year * 12 + month) - (y * 12 + m)) * LUNATION)), False


def to_gregorian(day: int, month: int, year: int) -> tuple[date, bool] | None:
    found = month_start(year, month)
    return None if found is None else (found[0] + timedelta(days=day - 1), found[1])


def from_gregorian(on: date) -> tuple[int, int, int] | None:
    """(day, month, year) of a Gregorian day, when the month it falls in is one the Bulletin's dates fix."""
    rows = _ordered()
    lo, hi, at = 0, len(rows) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if rows[mid][0] <= on:
            at, lo = mid, mid + 1
        else:
            hi = mid - 1
    if at < 0:
        return None
    start, year, month = rows[at]
    day = (on - start).days + 1
    return (day, month, year) if 1 <= day <= 30 else None


def said(day: int, month: int, year: int) -> str:
    return f'{day} {MONTHS[month - 1]} {year}'


FAR = 3                                                     # days a sighted month may stand from the arithmetic one


def tabular(year: int, month: int) -> date:
    """The 1st of a month in the arithmetic (civil) Hijri calendar: never shown to a reader, only the fence a printed
    pair must stand near to be believed. Morocco's sighted months fall within two days of it."""
    jdn = (11 * year + 3) // 30 + 354 * year + 30 * month - (month - 1) // 2 + 1 + 1948440 - 385
    return date.fromordinal(jdn - 1721425)


def tabulate(pairs) -> tuple[dict[str, str], dict]:
    """The first day of each month from (Gregorian day, Hijri date as printed) pairs: the day most pairs give, when two
    at least and half of them agree, among the pairs that stand within FAR days of the arithmetic calendar. Returns the
    table and what was counted."""
    from collections import Counter, defaultdict
    votes: dict[tuple[int, int], Counter] = defaultdict(Counter)
    read = 0
    for on, printed in pairs:
        found = parse(printed or '')
        if found is None or on is None:
            continue
        day, month, year, _ = found
        votes[(year, month)][on - timedelta(days=day - 1)] += 1
        read += 1
    table, weak, off = {}, 0, 0
    for key, counter in votes.items():
        # A pair further than FAR days from the arithmetic calendar is a misprint or a misreading (a year one off puts a
        # month 354 days away; «محرم 1331» printed for 1332 once outvoted the month's own pairs): it does not vote.
        about = tabular(*key)
        near = Counter({start: n for start, n in counter.items() if abs((start - about).days) <= FAR})
        off += sum(counter.values()) - sum(near.values())
        if not near:
            weak += 1
            continue
        (start, n), = near.most_common(1)
        if n >= 2 and n * 2 >= sum(near.values()):
            table[f'{key[0]}-{key[1]}'] = start.isoformat()
        else:
            weak += 1
    ordered = dict(sorted(table.items(), key=lambda kv: tuple(map(int, kv[0].split('-')))))
    return ordered, {'pairs': read, 'months': len(ordered), 'unsettled': weak, 'set_aside': off}
