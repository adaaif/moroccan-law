"""Which dahir promulgates a law, read from the Bulletin's own sentence (W3 of the library-search review, 10 Nov 2026).

234 laws were held without their dahir's number (the copies taken from a ministry's file open on the law itself), the
family code and the Labour Code among them, so «ظهير شريف رقم 1.04.22» found nothing. But every text that cites a law
writes «القانون رقم 70.03 بمثابة مدونة الأسرة الصادر بتنفيذه الظهير الشريف رقم 1.04.22»: the sentences vote, and a law
gets its dahir only when they are many, agree, and the dahir's year can be the law's. Never a guess: of the 140
laws whose dahir was already known and whose sentences pass the same bar, the sentences disagree with none."""
import re
from collections import Counter, defaultdict

_NUMBER = r'(\d{1,3})[.\-\s]{1,3}(\d{2})'
# «القانون رقم N … الصادر بتنفيذه الظهير الشريف رقم D», no other number and no sentence end between the two.
PAIR = re.compile(r'القانون(?:\s+التنظيمي|\s+الإطار|\s+الاطار)?\s+رقم\s+' + _NUMBER
                  + r'(?P<between>(?:(?!رقم\s*\d)[^.؛])*?)الصادر\s+ب?تنفيذه\s+الظهير\s+الشريف\s+رقم\s+'
                  r'(1)[.\-\s]{1,3}(\d{2})[.\-\s]{1,3}(\d{1,3})(?!\d)')
BETWEEN = 220                                               # characters a law's name may take before «الصادر بتنفيذه»
ENOUGH, AGREE, YEARS = 4, 0.9, 6                            # sentences at least, their share, years from bill to dahir
LIKE = '%تنفيذه الظهير الشريف رقم%'                           # what a body must hold to be worth reading


def key(number: str) -> str:
    """A law's number as the votes are kept: «07-03» and «7.03» are one law."""
    a, _, b = number.replace('.', '-').partition('-')
    return f'{int(a)}-{b}' if a.isdigit() else number


def read(bodies) -> dict[str, Counter]:
    """{law's key: Counter of the dahirs its sentences name, as printed}."""
    votes: dict[str, Counter] = defaultdict(Counter)
    for body in bodies:
        for m in PAIR.finditer(body or ''):
            if len(m.group('between')) <= BETWEEN:
                votes[f'{int(m.group(1))}-{m.group(2)}'][f'{m.group(4)}.{m.group(5)}.{m.group(6)}'] += 1
    return votes


def _year(two: str) -> int:
    return int(two) + (1900 if int(two) >= 30 else 2000)


def settled(law: str, counted: Counter) -> str | None:
    """The dahir the sentences settle on for this law, or None: ENOUGH of them, AGREE of all, and a dahir numbered in
    the law's own year or the few after it (a law's number carries its bill's year)."""
    if not counted:
        return None
    (dahir, n), = counted.most_common(1)
    if n < ENOUGH or n < AGREE * sum(counted.values()):
        return None
    try:
        gap = _year(dahir.split('.')[1]) - _year(key(law).split('-')[1])
    except (IndexError, ValueError):
        return None
    return dahir if 0 <= gap <= YEARS else None


def same(a: str, b: str) -> bool:
    """«1.07.02» and «1.7.2» are one dahir."""
    parts = lambda s: [int(p) for p in re.split(r'[.\-]', s) if p.isdigit()]
    return parts(a) == parts(b)
