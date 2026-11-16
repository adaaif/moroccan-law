"""The BO's words made plain for matching its set phrases (diacritics and tatweel out, Western digits, single
spaces), and an article's number as the corpus keeps it, read off its printed label («المادة 5 المكررة مرتين» →
5-ter)."""
import re
import unicodedata

from apps.corpus.services.issue_structure import ORDINALS, ordinal_value

TASHKEEL = re.compile('[ً-ْٰـ]')
DOTS = re.compile(r'(?:\.\s*){4,}|…+')


def plain(s: str) -> str:
    """Diacritics and tatweel out, Arabic digits Western, spaces single: only for matching the BO's set phrases."""
    s = unicodedata.normalize('NFKC', s)
    s = s.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789'))
    # A tatweel standing alone is the BO's dash («المادة 147 (الفقرة الأولى). ـ تدخل», law 01.05 on 65.00).
    s = re.sub(r'(?<=[.)\s])\u0640+(?=\s)', '-', s)
    return re.sub(r'[ \t]+', ' ', TASHKEEL.sub('', s))


def number(digits: str, bis: str | None = None) -> str:
    """The article's number as the corpus keeps it: «7.1» → 7-1, «5 المكررة مرتين» → 5-ter, «الأولى» → 1."""
    if not digits.strip()[:1].isdigit():
        # «الحادي عشر» → 11; a label read on past its number («الأولى من») keeps its first word's.
        value = ordinal_value(digits) or ordinal_value(digits.split()[0] if digits.split() else '')
        digits = str(value or ORDINALS.get(digits.strip().removeprefix('ال'), '') or '')
    digits = re.sub(r'\s+', '', digits)
    n = digits.replace('.', '-')
    # The BO prints a DOC sub-article turned around, «الفصل 3-618» (law 41.25): a sub-number is never the larger.
    if m := re.fullmatch(r'(\d{1,2})-(\d{3,4})', n):
        n = f'{m.group(2)}-{m.group(1)}'
    if bis:
        series = re.search(r'\d+', bis)
        # «16 مكرر 4» (18.00's numbered series, H2 of the housing plan) → 16-bis-4.
        n += f'-bis-{series.group(0)}' if series else ('-ter' if 'مرتين' in bis else '-quater' if 'ثلاث' in bis
                                                      else '-quinquies' if 'أربع' in bis else '-sexies' if 'خمس' in bis
                                                      else '-septies' if 'ست ' in bis + ' ' else '-bis')
    return n


LABEL = re.compile(r'(?:المادة|الفصل|البند)\s+(\d+(?:\s*[.\-]\s*\d+)*|[\u0621-\u064A]+(?:\s+(?:عشرة?|و?[\u0621-\u064A]+(?:ون|ين)))?(?:\s+بعد\s+(?:المائة|المئة))?)'
                   r'((?:\s+(?:المكررة|المكرر|مكررة|مكرر))(?:\s+(?:مرتين|ثلاث مرات|أربع مرات|خمس مرات|ست مرات)|\s*\d{1,2}(?!\d))?)?')


def label_key(label: str) -> str:
    """An article's number read off its printed label, the same way for every version: «المادة 5 المكررة مرتين»
    → 5-ter, «الفصل 488» → 488, «المادة الأولى» → 1."""
    m = LABEL.search(plain(label))
    return number(m.group(1), m.group(2)) if m else ''
