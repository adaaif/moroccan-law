"""Numbers and days as the Bulletin prints them: an article numbered in words, a text's number, an article's, a
Gregorian day in a text's words, and an old text's day that is only the day of a text its title cites."""
import re
import unicodedata
from datetime import date


_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
ORDINALS = {'الأول': 1, 'الأولى': 1, 'الثاني': 2, 'الثانية': 2, 'الثالث': 3, 'الثالثة': 3, 'الرابع': 4,
            'الرابعة': 4, 'الخامس': 5, 'الخامسة': 5, 'السادس': 6, 'السادسة': 6, 'السابع': 7, 'السابعة': 7,
            'الثامن': 8, 'الثامنة': 8, 'التاسع': 9, 'التاسعة': 9, 'العاشر': 10, 'العاشرة': 10, 'الاول': 1}
_UNITS = {'الحادي': 1, 'الحادية': 1, 'الواحد': 1, **{w: n for w, n in ORDINALS.items() if n < 10 and w not in ('الأول', 'الأولى', 'الاول')}}
_TENS = {'العشرون': 20, 'الثلاثون': 30, 'الأربعون': 40, 'الاربعون': 40, 'الخمسون': 50, 'الستون': 60, 'السبعون': 70,
         'الثمانون': 80, 'التسعون': 90}
# The same in the case a heading may put them («الفصل السابع والعشرين», the constitution of 1992).
_TENS |= {w[:-2] + 'ين': n for w, n in _TENS.items()}
_HUNDRED = ('المائة', 'المئة')
_WORDS = set(ORDINALS) | set(_UNITS) | set(_TENS) | {'عشر', 'عشرة', 'بعد', *_HUNDRED}


def ordinal_words(words: str) -> str:
    """The words with a word the text layer split put back together: «الحادي والأر بعون» → «الحادي والأربعون» (Adala's
    constitutions of 1992 and 1996). Words already whole are left as they are."""
    w = words.split()
    out: list[str] = []
    k = 0
    while k < len(w):
        if k + 1 < len(w) and w[k] not in _WORDS and w[k].lstrip('و') not in _WORDS \
                and (w[k] + w[k + 1] in _WORDS or (w[k] + w[k + 1]).removeprefix('و') in _WORDS):
            out.append(w[k] + w[k + 1])
            k += 2
        else:
            out.append(w[k])
            k += 1
    return ' '.join(out)


def ordinal_value(words: str) -> int | None:
    """An article numbered in words: «العاشر» → 10, «الحادي عشر» → 11, «الثالثة عشرة» → 13, «العشرون» → 20,
    «الحادي والعشرون» → 21 (the civil service statute numbers its «فصول» so), «المائة» → 100, «الثاني بعد المائة» →
    102 (the constitutions of 1992 and 1996). None for words that are not one."""
    w = ordinal_words(words).split()
    if w[-2:-1] == ['بعد'] and w[-1] in _HUNDRED:
        below = (ordinal_value(' '.join(w[:-2])) or _UNITS.get(' '.join(w[:-2]))) if len(w) > 2 else None
        return 100 + below if below and below < 100 else None
    if len(w) == 1:
        return ORDINALS.get(w[0]) or _TENS.get(w[0]) or (100 if w[0] in _HUNDRED else None)
    if len(w) == 2 and w[1] in ('عشر', 'عشرة') and w[0] in _UNITS:
        return 10 + _UNITS[w[0]]
    if len(w) == 2 and w[1].startswith('و') and w[1][1:] in _TENS and w[0] in _UNITS:
        return _TENS[w[1][1:]] + _UNITS[w[0]]
    if len(w) == 2 and w[1] in _TENS and w[0] in _UNITS:
        return _TENS[w[1]] + _UNITS[w[0]]        # its «و» left out: «الفصل الثاني السبعون» (Adala's 1992 constitution)
    return None
_NUMBER = re.compile(r'(\d+(?:[.\-/]\d+)+|\d+)')


def normalize_number(printed: str) -> str:
    """«013.26», «2.26.774», «1-58-376» → dashes; empty when nothing like a number is printed."""
    m = _NUMBER.search(unicodedata.normalize('NFKC', printed).translate(_DIGITS))
    return m.group(1).replace('.', '-').replace('/', '-') if m else ''


def article_number(label: str) -> str:
    label = unicodedata.normalize('NFKC', label).translate(_DIGITS)
    bis = '-bis' if 'مكرر' in label else ''
    m = re.search(r'\d+(?:[.\-]\d+)*', label)
    if m:
        return m.group(0) + bis
    for word, n in ORDINALS.items():
        if word in label.split():
            return f'{n}{bis}'
    return ''


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


_MONTHS = {'يناير': 1, 'ينير': 1, 'فبراير': 2, 'فبرابر': 2, 'يبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'إبريل': 4,
           'ماي': 5, 'مايو': 5, 'مايه': 5, 'يونيو': 6, 'يونيه': 6, 'يوليوز': 7, 'يوليو': 7, 'يوليه': 7, 'غشت': 8,
           'أغسطس': 8, 'شتنبر': 9, 'سبتمبر': 9, 'أكتوبر': 10, 'اكتوبر': 10, 'نونبر': 11, 'نوفمبر': 11, 'نوفنبر': 11,
           'دجنبر': 12, 'ديسمبر': 12}
# Before 1956 the year follows «سنة» («الموافق 29 شتنبر سنة 1933») and the months are spelled the protectorate's way.
_GREGORIAN = re.compile(r'(فاتح|\d{1,2})\s*(?:من\s+)?(' + '|'.join(sorted(_MONTHS, key=len, reverse=True))
                        + r')\s+(?:سنة\s+|عام\s+)?(\d{4})')


def _days(text: str) -> list[str]:
    """The Gregorian days printed in a text, in order (a heading's «(23 ماي 2000)», a closing's «في 30 يونيه 1971»)."""
    out = []
    for m in _GREGORIAN.finditer(text or ''):
        try:
            out.append(date(int(m.group(3)), _MONTHS[m.group(2)], 1 if m.group(1) == 'فاتح' else int(m.group(1))).isoformat())
        except ValueError:
            continue
    return out


# The words by which an old title names another text by its day («… بالظهير الشريف المؤرخ بسادس وعشري صفر 1334»).
_CITING = re.compile(r'المؤرخ|المورخ|الموءرخ|الموئرخ|الصادر|بتاريخ')


def cited_day(title: str, day: date | None, closing: str = '') -> bool:
    """An old text's day that is only the day of a text its title cites: the contents of 1913–1955 print no day of the
    text's own, and the reader took the cited dahir's (BO 479 of 1922: a dahir on selling the Makhzen's delimited lands
    dated 3 January 1916, the day of the dahir it names; the links by date then led there). A day before 1800 is a
    Hijri year read as Gregorian. The text's own day is then the one it signs («وحرر …»), or none. The cited
    day's year and month must follow the citing word: a text of November 1918 amending one of August 1918 keeps its day."""
    if day is None:
        return False
    if day.year < 1800:
        return True
    if day.isoformat() in _days(closing):
        return False
    alef = str.maketrans('أإآ', 'ااا')
    plain = (title or '').translate(_DIGITS).translate(alef)
    months = [name.translate(alef) for name, n in _MONTHS.items() if n == day.month]
    for m in _CITING.finditer(plain):
        cited = plain[m.end():m.end() + 160]
        if str(day.year) in cited and any(name in cited for name in months):
            return True
    return False
