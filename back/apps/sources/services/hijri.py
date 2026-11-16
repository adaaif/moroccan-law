"""An issue's Hijri date as its masthead prints it (U13 of the Moroccan-design review): «عدد 7465 مكرر 25 جمادى
الآخرة 1447 (16 ديسمبر 2025)». Kept only when the Gregorian date in brackets is the issue's own, so a misread masthead
never dates an issue wrong. Free: read from the first page's reading.

Before 1956 the masthead prints the Hijri day first and the Gregorian after «الموافق», without brackets: «الرباط في
16 جمادى الاولى عام 1370 … الموافق 23 يبراير سنة 1951» (the Bulletin-from-No.-1 review, 1 Nov 2026); the months as the
protectorate's Bulletin spelled them (يبراير, مايه, يونيه, نونبر; جمادى الاولى, ربيع النبوي)."""
import re
from datetime import date

HIJRI = ('محرم|صفر|ربيع الأول|ربيع الاول|ربيع الآخر|ربيع الثاني|ربيع النبوي|جمادى الأولى|جمادى الاولى|جمادي الاولى|'
         'جمادى الآخرة|جمادى الاخرة|جمادى الثانية|جمادي الثانية|رجب|شعبان|رمضان|شوال|ذو القعدة|ذي القعدة|ذو الحجة|'
         'ذي الحجة')
GREGORIAN = {'يناير': 1, 'ينير': 1, 'فبراير': 2, 'يبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'إبريل': 4, 'ماي': 5,
             'مايو': 5, 'مايه': 5, 'يونيو': 6, 'يونيه': 6, 'يوليوز': 7, 'يوليو': 7, 'يوليه': 7, 'غشت': 8, 'أغسطس': 8,
             'شتنبر': 9, 'سبتمبر': 9, 'أكتوبر': 10, 'اكتوبر': 10, 'نونبر': 11, 'نوفمبر': 11, 'نوفنبر': 11, 'دجنبر': 12,
             'ديسمبر': 12}
_MONTHS = '|'.join(sorted(GREGORIAN, key=len, reverse=True))
MASTHEAD = re.compile(rf'(فاتح|\d{{1,2}})\s+(?:من\s+)?({HIJRI})\s+(1[34]\d\d)\s*\(\s*(فاتح|\d{{1,2}})\s+'
                      rf'({_MONTHS})\s+((?:19|20)\d\d)\s*\)')
# Before 1956: «16 جمادى الاولى عام 1370», then within a few lines «الموافق 23 يبراير سنة 1951».
OLD_MASTHEAD = re.compile(rf'(فاتح|\d{{1,2}})\s+(?:من\s+)?({HIJRI})\s+(?:عام\s+)?(1[34]\d\d)[^\d]{{0,160}}?'
                          rf'الموافق\s+(?:ل\s*)?(فاتح|\d{{1,2}})\s+({_MONTHS})\s+(?:سنة\s+|عام\s+)?(19\d\d)')


def read(text: str, on: date) -> str:
    """«25 جمادى الآخرة 1447» from a first page's words when its Gregorian date says `on`; else ''."""
    for pattern in (MASTHEAD, OLD_MASTHEAD):
        for m in pattern.finditer(text[:2000]):
            day = 1 if m.group(4) == 'فاتح' else int(m.group(4))
            if (int(m.group(6)), GREGORIAN[m.group(5)], day) == (on.year, on.month, on.day):
                return f'{m.group(1)} {m.group(2)} {m.group(3)}'
    return ''
