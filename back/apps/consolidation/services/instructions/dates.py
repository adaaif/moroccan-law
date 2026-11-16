"""When a text takes effect, from the sentence of its final provisions that says so in the BO's set phrases (rows
L5–L8 of the links review): on publication, on a day it states, after a delay counted from its publication or from
the first of a month after it, or on a condition, kept in its own words; and the day an amending article sets for
itself before its verb. The months as the Bulletin has spelled them since 1912, its days in words, its Hijri dates."""
import re
from dataclasses import dataclass

from apps.consolidation.services.instructions.amending import _LEAD, STAGES
from apps.consolidation.services.instructions.labels import plain
from apps.corpus.services.issue_structure import ordinal_value

# The months as the Bulletin has spelled them since 1912: «يونيه», «يوليه», «دسمبر» and «نوفنبر» are the protectorate's
# and the first years of independence's (RD3 of the readers review: 153 orders said «ابتداء من فاتح يناير سنة 1955»
# and were read as waiting for a condition).
MONTH = ('يناير|فبراير|مارس|أبريل|ابريل|ماي|مايو|يونيو|يونيه|يوليو|يوليوز|يوليه|غشت|أغسطس|شتنبر|سبتمبر|أكتوبر|اكتوبر|'
         'نونبر|نوفمبر|نوفنبر|دجنبر|ديسمبر|دسمبر')
MONTHS = {'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'ماي': 5, 'مايو': 5, 'يونيو': 6, 'يونيه': 6,
          'يوليو': 7, 'يوليوز': 7, 'يوليه': 7, 'غشت': 8, 'أغسطس': 8, 'شتنبر': 9, 'سبتمبر': 9, 'أكتوبر': 10,
          'اكتوبر': 10, 'نونبر': 11, 'نوفمبر': 11, 'نوفنبر': 11, 'دجنبر': 12, 'ديسمبر': 12, 'دسمبر': 12}
# A day of the month in words, as the Bulletin wrote it until the 1950s: «رابع مارس 1948», «عشرين شتنبر سنة 1926»,
# «ثاني وعشري غشت سنة 1923».
_UNIT_DAYS = {'حادي': 1, 'ثاني': 2, 'ثالث': 3, 'رابع': 4, 'خامس': 5, 'سادس': 6, 'سابع': 7, 'ثامن': 8, 'تاسع': 9}
DAY_WORDS = {'فاتح': 1, 'عاشر': 10, 'عشرين': 20, 'ثلاثين': 30, **{w: n for w, n in _UNIT_DAYS.items() if n > 1},
             **{f'{w} عشر': 10 + n for w, n in _UNIT_DAYS.items()},
             **{f'{w} {tens}': 20 + n for w, n in _UNIT_DAYS.items() for tens in ('وعشري', 'وعشرين')},
             'حادي وثلاثين': 31}
_DAY = '|'.join(sorted(DAY_WORDS, key=len, reverse=True))
# «فاتح يناير 2027», «15 يونيه سنة 1937», «فاتح يوليوز من سنة 1960».
DAY_MONTH_YEAR = re.compile(rf'(?<![\w])({_DAY}|\d{{1,2}})\s+(?:من\s+)?({MONTH})\s+(?:(?:من\s+)?سنة\s+\.?)?(\d{{4}})')
# What the code read before RD3: today's months, the day in digits. Kept for the sentences nothing surer reads.
_DAY_MONTH_YEAR_BEFORE = re.compile(r'(فاتح|\d{1,2})\s+(?:من\s+)?(يناير|فبراير|مارس|أبريل|ابريل|ماي|مايو|يونيو|يوليو|يوليوز|غشت|'
                                    r'أغسطس|شتنبر|سبتمبر|أكتوبر|اكتوبر|نونبر|نوفمبر|دجنبر|ديسمبر)\s+(\d{4})')
# The date a clause leads to: right after «ابتداء من», a Hijri day before it or not («ابتداء من 4 شعبان 1401 (7 يونيه
# 1981)», «… الموافق 12 مارس سنة 1949»). Any other date in the sentence is another text's («الصادر في … (26 يوليو 2019)»).
_HIJRI = r'(?:فاتح|\d{1,2})\s+(?:من\s+)?\S+(?:\s+\S+)?\s+(?:عام\s+|سنة\s+)?\d{4}'
# The day of a text the sentence cites: «الصادر في 4 شعبان 1416 (26 ديسمبر 1995)», «بتاريخ 22 من صفر 1430 (18 فبراير 2009)».
CITED = re.compile(rf'(?:الصادرة?|المؤرخة?|بتاريخ)\s+(?:في\s+|يوم\s+)?(?:{_HIJRI}\s*(?:\(\s*|،?\s*(?:ال)?موافق\s+(?:ل\s*)?))?$')
LED = re.compile(rf'(?:[إا]بتداء\s+من|اعتبارا\s+من)\s+(?:يوم\s+|تاريخ\s+)?(?:{_HIJRI}\s*(?:\(|،?\s*(?:ال)?موافق\s+(?:ل\s*)?))?$')
# A reading that left Persian letters where the page prints Arabic ones («دیسمبر»).
_PERSIAN = str.maketrans('یک', 'يك')
NUMBERS = {'شهر': 1, 'شهرين': 2, 'ثلاثة': 3, 'أربعة': 4, 'خمسة': 5, 'ستة': 6, 'سبعة': 7, 'ثمانية': 8, 'تسعة': 9,
           'عشرة': 10, 'اثني عشر': 12, 'سنة': 12, 'سنتين': 24, 'ثلاث': 36}
THE_TEXT = r'(?:هذا|هذه)\s+(?:القانون|المرسوم|القرار|المقرر|الظهير|المدونة|النص|الأحكام|المقتضيات)'
IN_FORCE = re.compile(r'(?:حيز التنفيذ|حيز التطبيق|يعمل به|يعمل بها|ويعمل ب|يجري العمل|يسري العمل|يسري مفعول)')
PUBLICATION = re.compile(r'(?:ابتداء من|اعتبارا من|من|في|فور|بمجرد|ب)\s*(?:يوم\s+|تاريخ\s+)?(?:نشره|نشرها|نشر هذا|صدوره)|فور نشره|بمجرد نشره')
DELAY = re.compile(r'بعد\s+(?:مضي\s+|انصرام\s+|انقضاء\s+)?(?:أجل\s+)?(\S+(?:\s+عشر)?)\s*(?:\(\d+\)\s*)?(أشهر|شهرا|شهر|شهرين|سنة|سنتين|يوما|أيام)')
AFTER = re.compile(DELAY.pattern + r'[^.]{0,40}?تاريخ\s+(?:نشره|نشرها|نشر)')
NEXT_WEEK = re.compile(r'اليوم الأول من الأسبوع الموالي لتاريخ نشره')
# The first of the month after publication («فاتح الشهر الموالي لتاريخ نشره», «… للشهر الذي تم فيه نشر هذا القانون»),
# and a delay counted from it when one is said («بعد انقضاء اثني عشر شهرا، تحتسب ابتداء من فاتح الشهر الموالي …»).
NEXT_MONTH = re.compile(r'فاتح\s+الشهر\s+الموالي\s+(?:لتاريخ\s+نشر|للشهر\s+الذي\s+(?:تم\s+فيه\s+)?(?:ينشر|تنشر|نشر))')
# A day counted from publication in the other set phrases (RD3 of the readers review, 10 Nov 2026: the criminal
# procedure code, in every court since 1 October 2003, read «يدخل حيز التنفيذ حين يتحقق ما يقوله» because its art. 756
# says «ابتداء من اليوم الأول للشهر التاسع عشر الموالي لنشره»). _FOLLOWS is «the one after»; _ITS_ISSUE what it follows.
_FOLLOWS = r'(?:الموالي|التالي|التابع|الذي\s+يلي)(?:\s+مباشرة)?'
_ITS_ISSUE = r'(?:ل?(?:شهر\s+|تاريخ\s+|يوم\s+)*ل?نشر|ل?لشهر\s+الذي\s+(?:تم\s+فيه\s+)?(?:ينشر|تنشر|نشر))'
_ORDINAL = r'(ال\S+(?:\s+عشرة?)?)'
# «اليوم الأول من الشهر السادس الموالي لشهر نشره», «فاتح الشهر الثالث الموالي لتاريخ نشره», «اليوم الأول من الشهر
# الموالي لنشره»: the first day of the nth month after the month that printed it (the first when none is said).
NTH_MONTH = re.compile(rf'(?:فاتح\s+الشهر|اليوم\s+ال[أا]ول\s+(?:من\s+الشهر|للشهر))\s+(?:{_ORDINAL}\s+)?{_FOLLOWS}\s+{_ITS_ISSUE}')
# «بعد انصرام الشهر الثالث الموالي للشهر الذي ينشر فيه» (law 15.97): once that month has ended, so the first of the next.
MONTH_ENDED = re.compile(rf'بعد\s+(?:انصرام|انقضاء|مضي|نهاية)\s+الشهر\s+{_ORDINAL}\s+{_FOLLOWS}\s+{_ITS_ISSUE}')
# «في اليوم الخامس عشر التالي لنشره», «في اليوم الذي يلي تاريخ نشره».
NTH_DAY = re.compile(rf'اليوم\s+(?:{_ORDINAL}\s+)?{_FOLLOWS}\s+{_ITS_ISSUE}')
# «سنة بعد تاريخ نشره», «ثلاثة (3) أشهر بعد تاريخ نشره», «في أجل أقصاه ستة أشهر بعد تاريخ نشره»: the delay before the
# publication it is counted from (AFTER reads it the other way round).
THEN_PUBLICATION = re.compile(r'(?:(\S+(?:\s+عشرة?)?)\s*(?:\(\d+\)\s*)?)?(أشهر|شهرا|شهرين|شهر|سنتين|سنوات|سنة|يوما|أيام)\s+'
                              r'(?:بعد|من)\s+(?:تاريخ\s+)?نشر(?:ه|ها)(?!\w)')
COUNTS = {'واحد': 1, 'واحدة': 1, 'ثلاثة': 3, 'ثلاث': 3, 'أربعة': 4, 'أربع': 4, 'خمسة': 5, 'خمس': 5, 'ستة': 6, 'ست': 6,
          'سبعة': 7, 'سبع': 7, 'ثمانية': 8, 'ثماني': 8, 'تسعة': 9, 'تسع': 9, 'عشرة': 10, 'عشر': 10, 'اثني عشر': 12,
          'اثنا عشر': 12, 'خمسة عشر': 15, 'ثمانية عشر': 18, 'ثلاثين': 30, 'ثلاثون': 30, 'ستين': 60, 'ستون': 60,
          'تسعين': 90, 'تسعون': 90}
# The text's own end, never its start: «يسري مفعول هذا القرار إلى غاية نهاية شهر دجنبر 2020».
UNTIL = re.compile(r'(?:إلى|الى)\s+غاية|لغاية')
# A time to comply is not the text's start: «… خلال أجل لا يتعدى سنة من تاريخ نشره».
WITHIN = re.compile(r'(?:خلال|داخل|غضون|لا\s+[يت]تجاوز|لا\s+[يت]تعدى)\s+(?:أجل\s+)?(?:لا\s+[يت]تجاوز\s+|لا\s+[يت]تعدى\s+)?$')
# Where an old text's closing formula starts («… والسلام وحرر بالرباط في 11 رمضان 1371 موافق 4 يونيه سنة 1952 … واذن
# بنشره»): the day it was signed and the leave to print it are never its entry into force.
CLOSING = re.compile(r'\s+والسلام(?=\s|$)|\s+و?حرر\s+ب')
SINCE = re.compile(r'[إا]بتداء\s+من|اعتبارا\s+من')
# «ابتداء من السنة الجامعية 2026-2027», «من الموسم الدراسي 2010/2011», «ابتداء من السنة المالية 2025».
YEAR_OF = re.compile(r'(?:[إا]بتداء\s+من|اعتبارا\s+من|من)\s+(?:السنة|الموسم|الدخول)\s+(الدراسية?|الجامعية?|التكوينية?|التربوية?|'
                     r'المدرسي|المالية)\s+(\d{4})(?:\s*[-/]\s*(\d{4}))?')


def date_in(words: str):
    """«فاتح يناير 2027» → 2027-01-01; None when the words name no day."""
    m = DAY_MONTH_YEAR.search(words.translate(_PERSIAN))
    return _day(m) if m else None


def _day(m):
    """The date a DAY_MONTH_YEAR match says; None when the calendar has no such day."""
    from datetime import date
    day = DAY_WORDS.get(m.group(1)) or int(m.group(1))
    try:
        return date(int(m.group(3)), MONTHS[m.group(2)], day)
    except ValueError:
        return None


def _stated(sentence: str, verb_end: int, published) -> tuple | None:
    """(day, where) of the day a clause states: the date «ابتداء من» leads to, else the one right after the verb («حيز
    التنفيذ في فاتح يناير 2004»); else, as before RD3, the first date in a sentence that says «ابتداء من» somewhere. Never
    a date that comes after the words «من تاريخ نشره»: that one belongs to a text it repeals."""
    text = sentence.translate(_PERSIAN)
    for m in DAY_MONTH_YEAR.finditer(text):
        if LED.search(text[:m.start()]) and _day(m):
            return _day(m), m.start()
    at_verb = re.match(rf'\W{{0,3}}(?:في|يوم)\s+(?:{_HIJRI}\s*\(\s*)?', text[verb_end:])
    m = DAY_MONTH_YEAR.match(text, verb_end + at_verb.end()) if at_verb else None
    if m and _day(m):
        return _day(m), m.start()
    if not re.search(r'ابتداء من|اعتبارا من|من\s+(?:فاتح|\d)', sentence):
        return None
    for m in _DAY_MONTH_YEAR_BEFORE.finditer(sentence):
        if published and published.start() < m.start():
            break
        if not CITED.search(sentence[:m.start()]):
            return date_in(sentence[m.start():]), m.start()
    return None


@dataclass
class When:
    rule: str            # publication · stated · after · condition
    on: object = None    # a date, or None (on publication: the issue's date is filled in by the caller)
    months: int = 0      # after: the delay
    days: int = 0
    next_week: bool = False
    next_month: bool = False
    words: str = ''


def _delay(m) -> tuple[int, int] | None:
    """(months, days) a DELAY match says; None when its number is not one the code reads."""
    n = NUMBERS.get(m.group(1).strip(), None)
    if n is None and m.group(1).isdigit():
        n = int(m.group(1))
    unit = m.group(2)
    if n is None:
        return None
    if unit in ('يوما', 'أيام'):
        return 0, n
    if unit in ('شهرين', 'سنتين'):
        return (2 if unit == 'شهرين' else 24), 0
    return n * (12 if unit in ('سنة', 'سنتين') and n < 12 else 1), 0


def _span(count: str | None, unit: str) -> tuple[int, int] | None:
    """(months, days) of a delay said before its publication («ستة أشهر», «سنة», «30 يوما»); None when its number is not
    one the code reads: a number word it does not know is never taken for one («عشرين شهرا»)."""
    if unit == 'شهرين':
        return 2, 0
    if unit == 'سنتين':
        return 24, 0
    count = (count or '').strip()
    n = int(count) if count.isdigit() else COUNTS.get(count)
    if n is None:
        # «سنة بعد تاريخ نشره», «شهر بعد نشره»: one, unless the word before is a number the table lacks.
        if unit not in ('سنة', 'شهر') or re.search(r'(?:عشرة?|ون|ين)$', count):
            return None
        n = 1
    if unit in ('يوما', 'أيام'):
        return 0, n
    return n * (12 if unit in ('سنة', 'سنوات') else 1), 0


def _year_of(sentence: str):
    """The first day of the year a clause names: the budget year's 1 January (the calendar year since 2001), and a
    school, university or training year's 1 September once that day has come. Before it the clause stays what it is, a
    condition in its own words: the day a school year opens is set each year, and no day is shown that no text says."""
    from datetime import date
    m = YEAR_OF.search(sentence)
    if not m:
        return None
    year = int(m.group(2))
    if m.group(1) == 'المالية':
        return date(year, 1, 1) if year >= 2001 and not m.group(3) else None
    if m.group(3) and int(m.group(3)) == year + 1 and date(year, 9, 1) <= date.today():
        return date(year, 9, 1)
    return None


def in_force(body: str) -> When | None:
    """When the whole text takes effect, from the sentence that says so of «هذا القانون / المرسوم / القرار …» (an
    article's own dates, «تدخل مقتضيات المادة 5 …», are not the text's). A quoted line is the amended text's wording, not
    this one's: law 01.05 quotes 65.00's new art. 147 («تدخل أحكام هذا القانون … ابتداء من تاريخ النشر … للنصوص التطبيقية»)."""
    own = '\n'.join(line for line in body.splitlines() if not line.lstrip().startswith('«'))
    # A line the scan broke mid-sentence runs on («… ابتداء من فاتح الشهر الموالي لتاريخ\nنشره بالجريدة الرسمية»,
    # law 120.13 art. 3).
    own = re.sub(r'(?<![.؛:])\n(?!\s*[-–•])', ' ', own)
    for sentence in re.split(r'(?<=[.؛])\s+|\n', plain(own)):
        if not IN_FORCE.search(sentence) or not re.search(THE_TEXT + r'|ينشر\s+(?:هذا|هذه)', sentence):
            continue
        sets = re.search(r'(?:^|\s)(?:ي|ت)دخل\s', sentence)
        its = r'دخول(?:ه|ها)\s+حيز'
        if not sets and (re.search(r'دخول\s+' + THE_TEXT + r'(?:\s+(?:التنظيمي|المالي|الإطار))?\s+حيز', sentence)
                         # «… قبل تاريخ دخوله حيز التطبيق»: a mention too, unless the sentence sets the day elsewhere
                         # («يجري العمل بمقتضيات هذا القانون ابتداء من فاتح أكتوبر 2003 غير أن المقررات الصادرة قبل …»).
                         or (re.search(its, sentence)
                             and not IN_FORCE.search(re.sub(its + r'\s+(?:التنفيذ|التطبيق)', '', sentence)))):
            # It names the text's entry into force, it does not set it: «ينسخ، ابتداء من تاريخ دخول هذا القانون …»,
            # «لا تطبق الجزاءات … قبل دخول هذا القانون حيز التنفيذ», «… إلى غاية دخول هذا القانون حيز التنفيذ» (law 07.20,
            # H5 of the housing plan). Only «يدخل / تدخل … حيز التنفيذ» sets it.
            continue
        if re.search(r'(?:المادة|المواد|الفصل|الفصول|البند)\s+\d', sentence.split('حيز')[0][:120]) and \
                not re.search(r'أحكام هذا|مقتضيات هذا', sentence):
            continue
        if UNTIL.search(sentence) and not SINCE.search(sentence):
            # Its end, not its start: the text takes effect as one that says nothing does.
            continue
        words = sentence.strip()[:300]
        whole, sentence = sentence, CLOSING.split(sentence, maxsplit=1)[0]
        said = IN_FORCE.search(sentence)
        if said is None:
            continue
        if NEXT_WEEK.search(sentence):
            return When('after', next_week=True, words=words)
        if NEXT_MONTH.search(sentence):
            m = DELAY.search(sentence)
            delay = _delay(m) if m else (0, 0)
            if delay is not None:
                return When('after', months=delay[0], days=delay[1], next_month=True, words=words)
        m = AFTER.search(sentence)
        delay = _delay(m) if m else None
        if delay is not None:
            return When('after', months=delay[0], days=delay[1], words=words)
        m = NTH_MONTH.search(sentence)
        nth = (ordinal_value(m.group(1)) if m.group(1) else 1) if m else None
        if nth:
            return When('after', months=nth - 1, next_month=True, words=words)
        m = MONTH_ENDED.search(sentence)
        nth = ordinal_value(m.group(1)) if m else None
        if nth:
            return When('after', months=nth, next_month=True, words=words)
        m = NTH_DAY.search(sentence)
        nth = (ordinal_value(m.group(1)) if m.group(1) else 1) if m else None
        if nth:
            return When('after', days=nth, words=words)
        published = PUBLICATION.search(sentence)
        m = THEN_PUBLICATION.search(sentence)
        delay = _span(m.group(1), m.group(2)) if m else None
        if delay is not None and not WITHIN.search(sentence[:m.start()]) and not (published and published.start() < m.start()):
            return When('after', months=delay[0], days=delay[1], words=words)
        stated = _stated(sentence, said.end(), published)
        if stated and stated[0]:
            return When('stated', on=stated[0], words=words)
        year = _year_of(sentence)
        if year:
            return When('stated', on=year, words=words)
        if published or PUBLICATION.search(whole):
            # In the closing formula too («… واذن بنشره»), as before RD3: an old text nothing surer reads stays as it was.
            return When('publication', words=words)
        if re.fullmatch(r'(?:ه|ها|هما)?\W*', sentence[said.end():]):
            # «ينشر هذا القرار بالجريدة الرسمية ويعمل به.»: nothing after the verb, so from its publication.
            return When('publication', words=words)
        return When('condition', words=words)
    return None


STAGED = re.compile(r'^(?:تنسخ|ينسخ|تلغى|يلغى)\s*،?\s*(' + STAGES + r'{2,})')


def lead_date(body: str):
    """A date the amending article sets for itself before its verb: «ابتداء من فاتح يناير 2022، تغير …»; for a repeal
    in stages, the last one, when the whole text is gone."""
    staged = STAGED.match(plain(body).strip())
    if staged:
        days = [date_in(d) for d in re.findall(r'(?:ابتداء|اعتبارا) من ([^،]{3,60})،', staged.group(1))]
        return max(days) if days and all(days) else None
    m = re.match(_LEAD, plain(body).strip())
    lead = plain(body).strip()[:m.end() + 80] if m else ''
    found = re.search(r'ابتداء من ([^،:]{3,40})،', lead)
    return date_in(found.group(1)) if found else None
