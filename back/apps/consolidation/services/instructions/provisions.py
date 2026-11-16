"""What else an article says about other texts (rows L5–L8 of the links review), beyond the instructions `read`
reads: which texts its final provisions repeal whole («تنسخ … لا سيما : - القانون رقم 19.88 …»), where the references to
a repealed text now lead («تعتبر الإحالات إلى … إحالات إلى … هذا القانون») and which implementing texts outlive it
(«تظل سارية المفعول النصوص المتخذة لتطبيقه»); and what a title's own formula says it does to which text (amends,
repeals, applies, corrects, rules on). Each is read only in the BO's set phrases; anything else is left unread."""
import re
from dataclasses import dataclass, field

import ma_law

from apps.consolidation.services.instructions.amending import _lead
from apps.consolidation.services.instructions.dates import MONTH, THE_TEXT, date_in
from apps.consolidation.services.instructions.labels import plain


@dataclass
class Clause:
    kind: str                       # repeal · redirect · keep
    citations: list = field(default_factory=list)   # ma_law citations (dicts), offsets in the article's body
    words: str = ''
    on: object = None               # repeal: a date the clause states
    same_date: bool = False         # repeal: «ابتداء من نفس التاريخ / التاريخ المذكور»: the text's own date


REPEAL_AT = re.compile(r'(?:^|(?<=[\s.،:;\-–)]))(تنسخ|ينسخ|تلغى|يلغى|نسخت)(?:\s+|\s*،\s*)'
                       r'(?:،\s*)?(?:(ابتداء من|اعتبارا من)\s+(تاريخ دخول ' + THE_TEXT + r' حيز التنفيذ|تاريخ [^،]{0,50}?|'
                       r'هذا التاريخ|نفس التاريخ|التاريخ المذكور|'
                       rf'(?:فاتح|\d{{1,2}})\s+(?:{MONTH})\s+\d{{4}})\s*،?\s*)?')
OBJECT = re.compile(r'(?:أحكام|مقتضيات|المادة|المواد|الفصل|الفصول|القانون|المرسوم|الظهير|القرار|المقرر|'
                    r'بموجب|جميع)')
# «وعلى الأخص» is the criminal procedure code's (art. 756: the 1959 code it repeals read «عُدّل بعد صدوره» until RD3 of
# the readers review).
ESPECIALLY = re.compile(r'(?:ولا سيما|لا سيما|ولاسيما|لاسيما|وخاصة|خاصة|وبالخصوص|خصوصا|وعلى الأخص|على الأخص|'
                        r'وعلى الخصوص|على الخصوص|وبالأخص|بالأخص)')
# A citation that names only a part of what is repealed: «الفقرة الثانية من المادة 39», «النقطة (ب) من البند (ب) من
# الفصل 3», «الأحكام المتعلقة بـ… الواردة في الجزء الثاني من المرسوم». The part is not read: never the whole.
PART_BEFORE = re.compile(r'(?:(?:الفقرة|الفقرتان|الفقرتين|الفقرات|البند|البندان|البنود|النقطة|النقط|القسم|القسمان|الأقسام|'
                         r'المادة|المادتان|المادتين|المواد|الفصل|الفصلان|الفصلين|الفصول|'
                         r'الجزء|الجزءان|الأجزاء|الجملة|المقطع|العبارة|الجدول|الملحق)\b[^،.؛]{0,60}?\s+من|'
                         r'(?:الواردة|المنصوص عليها|المضمنة|المتعلقة)\s+(?:في|ب)[^،.؛]{0,60}?)\s*$')


# The part said after the text it is taken from: «تنسخ أحكام القانون رقم 9.97 المتعلق بمدونة الانتخابات، الصادر بتنفيذه …
# (2 أبريل 1997) كما وقع تغييره وتتميمه، المتعلقة باللوائح الانتخابية العامة …» repeals those provisions, never the
# electoral code (law 57.11, art. 136). The words agree with «أحكام», not with the law: after its day or «كما وقع
# تغييره وتتميمه», a comma, then «المتعلقة ب / الواردة في».
PART_AFTER = re.compile(r'(?:\)|تغييره\s+وتتميمه|تغييرها\s+وتتميمها)\s*،\s*(?:المتعلقة|الواردة|المتصلة|الخاصة)\s+(?:ب|في)')
# «تنسخ جميع المقتضيات المخالفة لهذا المرسوم، ولاسيما تلك الواردة في: - القرار … ؛ - والمرسوم رقم 2.74.526 …»: the
# contrary provisions those texts hold, never the texts.
THOSE_IN = re.compile(r'\s*تلك\s+(?:الواردة|المنصوص\s+عليها|المضمنة)\s+في')


def _cited(segment: str, offset: int, whole_only: bool = False) -> list[dict]:
    """The texts and articles a stretch names, offsets moved to the article's; a promulgating dahir left out, and with
    `whole_only` (a repeal) any citation of which only a part is named."""
    out = []
    for c in ma_law.parse_citations(segment):
        if whole_only and PART_BEFORE.search(segment[max(0, c['start'] - 90):c['start']]):
            continue
        if c.get('text_kind') == 'dahir' and 'بتنفيذه' in segment[max(0, c['start'] - 25):c['start']]:
            continue
        if c['kind'] == 'issue':
            continue
        if c['kind'] == 'article' and not (c.get('text_number') or c.get('code')):
            continue
        out.append({**c, 'start': c['start'] + offset, 'end': c['end'] + offset})
    return out


STOP = re.compile(r'[.؛](?=\s|$)')       # a sentence's end; never the dot inside «23.98»
ITEM = re.compile(r'\n\s*[-–•*]|؛|;|\n')    # where one item of a list of repealed texts ends


def _objects(segment: str, offset: int) -> list[dict]:
    """The texts a clause repeals or redirects: the first text each item of its list names, by kind and number.
    What follows in an item is that text's own title («المرسوم رقم 2.19.719 … بتطبيق القانون رقم 99.15»), never
    an object; an item that names only a part of its text («الفقرة الثانية من الفصل 219 من …») is left out, and so
    is a code named only by its name (which code it was depends on the year)."""
    out = []
    starts = [0] + [m.end() for m in ITEM.finditer(segment)]
    ends = [m.start() for m in ITEM.finditer(segment)] + [len(segment)]
    for a, b in zip(starts, ends):
        item = segment[a:b]
        cites = [c for c in ma_law.parse_citations(item) if c['kind'] != 'issue'
                 and not (c.get('text_kind') == 'dahir' and 'بتنفيذه' in item[max(0, c['start'] - 25):c['start']])
                 and not (c['kind'] == 'article' and not (c.get('text_number') or c.get('code')))]
        if not cites:
            continue
        first = cites[0]
        if not first.get('text_number') or PART_BEFORE.search(item[max(0, first['start'] - 90):first['start']]) \
                or PART_AFTER.search(item, first['end']):
            continue
        out.append({**first, 'start': first['start'] + a + offset, 'end': first['end'] + a + offset})
    return out


def _sentence_end(text: str, start: int) -> int:
    """Where a clause's words stop: the end of its sentence or line, and the list under it when it ends in «:» or
    names texts «لا سيما»."""
    m = STOP.search(text, start)
    end = m.end() if m else len(text)
    line_end = text.find('\n', start)
    if line_end == -1 or line_end >= end:
        return end
    if not (text[start:line_end].rstrip().endswith(':') or ESPECIALLY.search(text, start, line_end)):
        return line_end
    end = line_end
    while end < len(text):
        nxt = text.find('\n', end + 1)
        nxt = len(text) if nxt == -1 else nxt
        if not re.match(r'\s*(?:[-–•*]|\d{1,2}\s*[-–.)])', text[end + 1:nxt]):     # «- …», «1 - …»
            break
        end = nxt
    return end


def _sentence_start(text: str, at: int) -> int:
    ends = [m.end() for m in re.finditer(r'[.؛](?=\s)|\n', text[:at])]
    return ends[-1] if ends else 0


def clauses(body: str, instructed: bool = False) -> list[Clause]:
    """Repeals, redirects and kept implementing texts said anywhere in an article. `instructed`: the article opens
    with an instruction `read` reads, so its opening repeal is that instruction's."""
    text = body
    flat = plain(body)
    if len(flat) != len(text):
        text = flat      # offsets are the plain text's: plain() only drops marks, which ma_law folds anyway
    out: list[Clause] = []
    lead_end = len(_lead(text)) if instructed else 0
    for m in REPEAL_AT.finditer(text):
        if m.start() < lead_end:
            continue
        rest = text[m.end():m.end() + 40]
        # A list under it: «ينسخ، ابتداء من …: 1 - الظهير الشريف … ؛ 2 - …» (law 58.25, art. 644).
        rest = rest[re.match(r'[:\s]*(?:\d+\s*[-–.)]\s*)?', rest).end():]
        if not OBJECT.match(rest):
            continue
        end = _sentence_end(text, m.end())
        segment_start = m.end()
        if rest.startswith('جميع'):
            especially = ESPECIALLY.search(text, m.end(), end)
            if not especially:
                continue           # «جميع المقتضيات المخالفة»: no text named, nothing to place
            segment_start = especially.end()
            if THOSE_IN.match(text, segment_start):
                continue
        cited = _objects(text[segment_start:end], segment_start)
        if not cited:
            continue
        before = re.search(r'(?:ابتداء|اعتبارا)\s+من\s+([^،.]{3,40}?)\s*،?\s*$', text[max(0, m.start() - 60):m.start()])
        when = m.group(3) or (before.group(1) if before else '')
        out.append(Clause('repeal', cited, text[m.start():end].strip()[:600], on=date_in(when) if when else None,
                          same_date=bool(when) and not date_in(when)))
    for m in re.finditer(r'الإحالات?\s+(?:الواردة\s+)?إلى', text):
        end = _sentence_end(text, m.end())
        sentence = text[m.start():end]
        if not re.search(r'(?:إحالات?|بالإحالة|بالإحالات)\s+إلى', sentence[10:]) or not re.search(THE_TEXT, sentence):
            continue
        stop = re.search(r'(?:،\s*)?(?:الواردة|المضمنة|إحالات?\s+إلى|بالإحالة)', text[m.end():end])
        cited = _objects(text[m.end():m.end() + stop.start()], m.end()) if stop else []
        if cited:
            out.append(Clause('redirect', cited, sentence.strip()[:600]))
    for m in re.finditer(r'(?:تظل|تبقى|يظل|يبقى)\s+(?:\S+\s+){0,3}?(?:سارية|ساري)', text):
        start = _sentence_start(text, m.start())
        end = _sentence_end(text, m.end())
        sentence = text[start:end]
        if not re.search(r'النصوص\s+(?:التنظيمية\s+)?(?:المتخذة|الصادرة)\s+(?:ل|تطبيقا\s+ل|من\s+أجل\s+)', sentence):
            continue
        cited = [c for c in _cited(sentence, start) if c['kind'] == 'text' and c.get('text_number')][:1]
        if cited:
            out.append(Clause('keep', cited, sentence.strip()[:600]))
    return out


# A title's own formula: «مرسوم رقم 2.22.431 بتغيير وتتميم المرسوم رقم 2.12.349 …», «… بتطبيق القانون رقم 31.13».
TITLE_AMENDS = re.compile(r'(?:بتغيير|بتتميم|بتعديل|بتغييره|وتتميم|بنسخ وتعويض|بنسخ)\b')
TITLE_APPLIES = re.compile(r'(?:بتطبيق|لتطبيق|بتحديد كيفيات تطبيق|بتحديد شروط تطبيق|بتحديد كيفية تطبيق|تطبيقا ل)')
TITLE_CORRECTS = re.compile(r'(?:استدراك|إصلاح خطأ|إصلاح خطإ)')
TITLE_RULES = re.compile(r'المحكمة الدستورية')


def title_links(title: str, own: str = '') -> list[tuple[str, dict]]:
    """[(relation, citation)] a title states: amends, repeals, applies, corrects or rules_on, with the text named
    right after the formula (never the dahir that promulgated it). The formula must be the title's own: one that
    follows another text's citation belongs to that text's title, quoted («قرار … طبقا لمقتضيات المرسوم رقم 2.21.582
    بتطبيق القانون رقم 72.18» applies the decree, not the law). `own` is the text's own number, which its title names."""
    t = plain(title)
    own = own.lstrip('0')
    others = [c['start'] for c in ma_law.parse_citations(t)
              if c.get('text_number') and c['text_number'].lstrip('0') != own]
    out = []
    for relation, pattern in (('repeals', re.compile(r'بنسخ(?!\s+وتعويض)')), ('amends', TITLE_AMENDS),
                              ('applies', TITLE_APPLIES), ('corrects', TITLE_CORRECTS), ('rules_on', TITLE_RULES)):
        m = pattern.search(t)
        if not m or (relation != 'corrects' and any(start < m.start() for start in others)):
            continue
        for c in _cited(t[m.end():], m.end()):
            if c['kind'] == 'text' or c.get('text_number') or c.get('code'):
                out.append((relation, c))
                if relation != 'applies':
                    break
    return out
