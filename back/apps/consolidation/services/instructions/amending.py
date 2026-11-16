"""An amending article read as instructions (row 19). The BO words them in a handful of ways:

    تغير وتتمم، على النحو التالي، أحكام المواد 1 و7 و24.2 (الفقرة الثانية) من القانون رقم 2.00 … :
    «المادة 1. - يقصد بالمصطلحات ................ المعاني التالية :
    يتمم القانون السالف الذكر رقم 2.00 بالمادة 7.1 التالية : «المادة 7.1. - …»
    تنسخ وتعوض، على النحو التالي، أحكام المادة 18 … : «المادة 18. - …»
    تنسخ أحكام المادة 9 من …
    تحل عبارة «منتج تسجيل صوتي» محل عبارة «منتج مسجل صوتي» في المواد 38 و51 من …

Each becomes Instructions: what is done (modify, add, replace, repeal, words), to which text, to which articles,
with the new wording as printed. A dotted wording («……») keeps the old words where the dots stand; filling it is
fill.py's job. Nothing here guesses: what is not read plainly is returned as `unclear` with its reason."""
import re
from dataclasses import dataclass, field

import ma_law

from apps.consolidation.services.instructions.labels import DOTS, number, plain
from apps.corpus.services.codes import dated

# The verbs, with what may come before them: a part number («I. -»), a date («ابتداء من فاتح يناير 2022،»).
_LEAD = r'^(?:[IVX]+\s*[.\-]\s*-?\s*)?(?:ابتداء من [^،:]{3,40}،\s*)?'
REPLACE = re.compile(_LEAD + r'(?:تنسخ|ينسخ)\s*(?:،\s*)?(?:و\s*)?(?:تعوض|يعوض)')
REPLACE_LATE = re.compile(r'^(?:تنسخ|ينسخ) (?:أحكام|مقتضيات).{0,200}?(?:وتعوض|ويعوض|وتعوض بما يلي|وتعوض كما يلي)')
MODIFY = re.compile(_LEAD + r'(?:تغير|يغير|تعدل|يعدل|تغيير)(?:\s*(?:و|أو)\s*(?:تتمم|يتمم|تتميم))?')
COMPLETE = re.compile(_LEAD + r'(?:تتمم|يتمم|تتتمم|تتميم)')
REPEAL = re.compile(_LEAD + r'(?:تنسخ|ينسخ|تلغى|يلغى)\s')
WORDS_TAKE = re.compile(r'(?:تحل|يحل)\s+(?:عبارة|عبارات|عبارتا|عبارتي|العبارة|العبارات|كلمة|كلمات|كلمتا|الكلمة|لفظة|ألفاظ|تسمية)')
WORDS_SWAP = re.compile(_LEAD + r'(?:تعوض|يعوض|تستبدل|يستبدل)\s+(?:عبارة|عبارات|عبارتا|عبارتي|العبارة|العبارات|كلمة|كلمات|الكلمة|لفظة|تسمية)')

# A quoted article's own heading: «المادة 7.1 . -», «الفصل 488. -», «المادة 5 المكررة مرتين. -», «المادة الأولى. -».
REST_LINE = re.compile(r'^\(?\s*(?:الباقي|والباقي)\s+(?:لا تغيير فيه|بدون تغيير|دون تغيير|لم يتغير)')
HEADING = re.compile(r'^«?\s*(المادة|الفصل|البند)\s+(\d+(?:\s*[.\-]\s*\d+)*|[ء-ي]+)'
                     r'((?:\s+(?:المكررة|المكرر|مكررة|مكرر))(?:\s+(?:مرتين|ثلاث مرات|أربع مرات|خمس مرات|ست مرات))?)?'
                     r'(?:\s*\(([^)]*)\))?\s*\.?\s*[-–—]')
# A division's heading among the quoted articles: «الباب الثاني», «الفرع الأول», «القسم السادس».
DIVISION = re.compile(r'^«?\s*(?:الكتاب|القسم|الجزء|الباب|الفرع|الفصل)\s+(?:[ء-ي]+|\d+)'
                      r'(?:\s+(?:المكرر|المكررة|مكرر))?\s*$')
# Only part of an article: «الفقرة الثالثة من المادة 43», «البند و) من المادة الأولى».
PART_OF = re.compile(r'(?:الفقرة|الفقرتين|الفقرات|البند|البنود|الجملة|المقطع)\s+[^،:«]{0,40}?\s+من\s+(?:المادة|الفصل)')
# The articles a lead names: «المواد 1 و7 و24.2 (الفقرة الثانية)», «المادة الأولى», «بالمادة 7.1», and a decree's
# articles by their ordinal words: «المادتين السابعة والثامنة» (decree 2.26.551 art. 2 on the passport's 2.08.310).
NAMED = re.compile(r'(?:^|\s|و)(\d+(?:[.\-]\d+)*|الأولى|الأول|ال(?:ثاني|ثالث|رابع|خامس|سادس|سابع|ثامن|تاسع|عاشر)ة?(?![ء-ي]))((?:\s+(?:المكررة|المكرر|مكررة|مكرر))(?:\s+(?:مرتين|ثلاث مرات|أربع مرات|خمس مرات|ست مرات))?)?'
                   r'(?:\s*\((الفقرة|الفقرتين|الفقرات|البند|البنود)\s*([^)]*)\))?')
PARTS = {'الأولى': 1, 'الثانية': 2, 'الثالثة': 3, 'الرابعة': 4, 'الخامسة': 5, 'السادسة': 6, 'السابعة': 7,
         'الثامنة': 8, 'التاسعة': 9, 'العاشرة': 10, 'الأخيرة': -1}


@dataclass
class Unit:
    """One article's new wording, as quoted."""
    label: str           # «المادة 7.1» as printed
    number: str          # 7-1
    lines: list[str]     # the quoted lines, «» and the heading taken off
    dotted: bool         # some words are kept from the old article («……»)
    part: tuple | None = None   # what its heading names of it: «المادة 5 (الفقرة الثالثة)» → ('الفقرة', [3])


@dataclass
class Instructions:
    action: str                                      # modify · add · replace · repeal · words · unclear
    target: dict | None = None                       # {'kind': 'law', 'number': '2-00'} or {'code': 'cgi'}
    articles: list[dict] = field(default_factory=list)   # [{'number': '24-2', 'part': ('الفقرة', [2])}]
    units: list[Unit] = field(default_factory=list)
    words: list[tuple[str, str]] = field(default_factory=list)   # [(old, new)]
    reason: str = ''


def _lead(body: str) -> str:
    """The instruction itself: what comes before the first quoted line (a lead ends with «:» at a line's end)."""
    m = re.search(r':\s*\n\s*«|:\s*«', body)
    return body[:m.start()] if m else body.split('\n', 1)[0]


FINANCE = re.compile(r'(?:قانون المالية|القانون المالي|قانون المالية المعدل)(?:\s+(?:لسنة|للسنة المالية)\s+\d{4})?\s+رقم\s+(\d+(?:\.\d+)+)')


def _target(lead: str) -> dict | None:
    """The text the lead amends: a finance law by its own number, else the first text it cites — never the dahir
    that promulgated it («… الصادر بتنفيذه الظهير الشريف رقم 1.13.115»)."""
    m = FINANCE.search(lead)
    cited = [dated(lead, c) for c in ma_law.parse_citations(lead)]
    # «… من المدونة العامة للضرائب المحدثة بموجب المادة 5 من قانون المالية رقم 43.06»: the code, not the law that made it.
    code = next((c for c in cited if c.get('code') and not c.get('text_number')), None)
    if m and not (code and code['start'] < m.start()):
        return {'kind': 'law', 'number': m.group(1).replace('.', '-')}
    for c in cited:
        if c.get('text_kind') == 'dahir' and 'بتنفيذه' in lead[max(0, c['start'] - 25):c['start']]:
            continue
        if c['kind'] == 'text' and c.get('text_number'):
            return {'kind': c['text_kind'], 'number': c['text_number']}
        if c.get('code'):
            return {'code': c['code']}
        # Before 1956 a text is named by its date (H9 of the Bulletin-from-No.-1 review), with the words that tell apart
        # the dahirs of one day.
        if c.get('date') and c.get('text_kind') and not c.get('text_number'):
            return {'kind': c['text_kind'], 'date': c['date'], 'words': lead[c['end']:c['end'] + 200]}
    m = re.search(r'(القانون التنظيمي|القانون|المرسوم|الظهير الشريف|القرار|قرار)[^\d]{0,40}?رقم\s+(\d+(?:\.\d+)+)', lead)
    if m:
        kind = {'القانون التنظيمي': 'organic_law', 'القانون': 'law', 'المرسوم': 'decree', 'الظهير الشريف': 'dahir'}.get(m.group(1), 'order')
        return {'kind': kind, 'number': m.group(2).replace('.', '-')}
    return None


def _named(lead: str) -> list[dict]:
    """The articles the lead lists after «المادة / المواد / الفصل / الفصول», with the part named for each."""
    m = re.search(r'(?:أحكام|مقتضيات)?\s*(?:ب)?(?:المادة|المواد|المادتين|المادتان|الفصل|الفصول|الفصلين|البند|البنود)\s+(.*?)(?:\s+(?:من|في)\s+(?:القانون|المرسوم|الظهير|القرار|قانون|مدونة|المدونة|الفصل|هذا)|\s+التالية|\s+الآتية|$)', lead)
    if not m:
        return []
    out = []
    for g in NAMED.finditer(m.group(1)):
        # An ordinal word names this article only right after the verb («تنسخ أحكام المادتين السابعة والثامنة»), never
        # inside the title of the text a lead names («ينسخ القرار … بتطبيق أحكام المادة الثانية من المرسوم …»).
        if not g.group(1)[0].isdigit() and g.group(1) not in ('الأولى', 'الأول') and len(lead[:m.start()]) > 30:
            continue
        if not g.group(1)[0].isdigit() and re.search(r'(?:الفقرة|الفقرتين|الفقرتان|الفقرات|البند|البنود)\s+(?:\S+\s+)?$',
                                                     m.group(1)[:g.start(1)]):
            continue                       # «المادة 12 الفقرة الثانية»: a paragraph's ordinal, not an article's
        part = None
        if g.group(3):
            which = [PARTS[w] for w in re.findall(r'\S+', g.group(4)) if w in PARTS]
            which += [int(d) for d in re.findall(r'\d+', g.group(4))]
            part = (g.group(3), which)
        out.append({'number': number(g.group(1), g.group(2)), 'part': part})
    return out


def _units(body: str) -> list[Unit]:
    """The quoted articles, split at each «المادة N. -» heading."""
    start = re.search(r':\s*\n?\s*«', body)
    if not start:
        return []
    quoted = body[start.end() - 1:]
    units: list[Unit] = []
    for raw in quoted.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = line.removeprefix('«').strip()
        h = HEADING.match(plain(line))
        if not h and DIVISION.match(plain(line)) and len(line) < 60:
            continue    # a division's heading: the articles under it are what is placed
        if h:
            rest = plain(line)[h.end():].strip()
            named = re.match(r'(الفقرتان|الفقرات|الفقرة)\s+(.*)', (h.group(4) or '').strip())
            which = [PARTS[w.removeprefix('و')] for w in re.findall(r'\S+', named.group(2))
                     if w.removeprefix('و') in PARTS] if named else []
            units.append(Unit(label=f'{h.group(1)} {h.group(2).strip()}{(h.group(3) or "")}', number=number(h.group(2), h.group(3)),
                              lines=[rest] if rest else [], dotted=False,
                              part=('الفقرة', which) if which else None))
        elif units:
            units[-1].lines.append(line)
        elif len(line) < 60 and not DOTS.search(line):
            continue     # a title above the first quoted article («السيارة الاقتصادية»)
        else:
            return []    # wording before any heading: a part of an article, said otherwise
    for u in units:
        # The quote closes on the wording's last line, before «(الباقي بدون تغيير.)» when the BO prints one.
        last = len(u.lines) - 1
        if last > 0 and REST_LINE.match(u.lines[last]):
            last -= 1
        if last >= 0 and u.lines[last].endswith('»'):
            u.lines[last] = u.lines[last][:-1].rstrip()
        u.lines = [strays(ln) for ln in u.lines if ln]
        u.dotted = any(DOTS.search(ln) for ln in u.lines)
    return units


def strays(s: str) -> str:
    """The BO opens every line of a quoted article with «; inside a paragraph those marks open nothing. Kept are
    the pairs that close («البث الإذاعي»)."""
    chars = list(s)
    opens: list[int] = []
    for i, c in enumerate(chars):
        if c == '«':
            if opens:
                chars[opens.pop()] = ''
            opens.append(i)
        elif c == '»':
            if opens:
                opens.pop()
            else:
                chars[i] = ''
    for i in opens:
        chars[i] = ''
    return re.sub(r'[ ]{2,}', ' ', ''.join(chars)).strip()


def _quoted(s: str) -> list[str]:
    return [q.strip() for q in re.findall(r'«([^«»]+)»', s)]


# What a whole-text repeal names right after its verb: the text itself («ينسخ القرار المذكور», «تنسخ أحكام المرسوم
# رقم …»), never a table, an annex or a paragraph of it.
# A repeal in stages may come between: «تنسخ ابتداء من فاتح يناير 2025، فيما يخص النشاطات غير الفلاحية، وابتداء من فاتح
# أبريل 2025، فيما يخص النشاطات الفلاحية، مقتضيات المرسوم رقم 2.23.799» (the minimum-wage decrees, work plan T4).
STAGES = r'(?:و?(?:ابتداء|اعتبارا) من [^،]{3,60}،\s*(?:فيما يخص [^،]{3,80}،\s*)?)'
WHOLE = re.compile(r'^\s*(?:،\s*)?' + STAGES + r'*(?:جميع\s+)?(?:أحكام|مقتضيات)?\s*'
                   r'(?P<kind>القانون|المرسوم|الظهير|القرار|المقرر|الأمر|المنشور|الدورية)')
# The kinds the word after the verb may name. When the first text the lead cites is of another kind, it belongs to
# the object's title, not the object: «ينسخ القرار المشترك … رقم 1799.16 … بتطبيق … القانون رقم 77.15» repeals an
# order whose number the citation reader missed, never law 77.15.
WHOLE_KINDS = {'القانون': ('law', 'organic_law'), 'الظهير': ('dahir', 'law'), 'المرسوم': ('decree', 'decree_law'),
               'القرار': ('order', 'decision'), 'المقرر': ('decision', 'order')}


def read(body: str) -> Instructions | None:
    """The instructions of one amending article, or None when it amends nothing."""
    text = plain(body).strip()
    lead = _lead(text)
    head = lead[:160]
    if WORDS_TAKE.search(head) and 'محل' in lead:
        # «تحل عبارة «A» محل عبارة «B» في …»: A takes B's place. «على التوالي» pairs several in order.
        before, after = lead.split('محل', 1)
        new, old = _quoted(before), _quoted(after)
        where = after.split('»')[-1] if '»' in after else after
        ins = Instructions('words', _target(where) or _target(lead), _named(where))
        if new and len(new) == len(old):
            ins.words = list(zip(old, new))
        elif len(new) == 1 and old:
            ins.words = [(o, new[0]) for o in old]
        else:
            ins.action, ins.reason = 'unclear', 'words_not_paired'
        return ins
    if WORDS_SWAP.search(head):
        # «تعوض عبارة «A» بعبارة «B»»: B takes A's place.
        m = re.search(r'«([^«»]+)».{0,80}?(?:ب|بال)(?:عبارة|عبارات|كلمة|كلمات|تسمية|لفظة)?\s*«([^«»]+)»', lead, re.S)
        ins = Instructions('words', _target(lead), _named(lead))
        if m:
            ins.words = [(m.group(1).strip(), m.group(2).strip())]
        else:
            ins.action, ins.reason = 'unclear', 'words_not_paired'
        return ins
    for action, pattern in (('replace', REPLACE), ('replace', REPLACE_LATE), ('modify', MODIFY), ('add', COMPLETE),  # noqa: B007 (read after the loop)
                            ('repeal', REPEAL)):
        if pattern.search(lead if pattern is REPLACE_LATE else head):
            break
    else:
        return None
    ins = Instructions(action, _target(lead), _named(lead))
    if action == 'repeal' and re.search(r'و(?:تعوض|يعوض)', lead):
        annex = re.search(r'الملحق|الجدول|الجداول|النموذج', lead)
        units = [] if annex else _units(text)
        if units:
            # «تنسخ أحكام المواد 50 (الفقرتان الثانية والثالثة) و52 … وتعوض على النحو التالي :» with each quoted (64.12
            # art. 139 on 65.00): the new wording of what it names.
            ins.action, ins.units = 'replace', units
            return ins
        ins.action, ins.reason = 'unclear', 'annex' if annex else 'replace_unquoted'
        return ins
    if action == 'repeal':
        if not ins.target:
            return None                    # «تلغى اعتمادات …»: a finance law's credits, not a text
        if PART_OF.search(lead):
            ins.action, ins.reason = 'unclear', 'part_of_article'
        elif not ins.articles:
            after = lead[REPEAL.search(lead).end():] if REPEAL.search(lead) else lead
            whole = WHOLE.match(after)
            if whole and 'kind' in ins.target and ins.target['kind'] not in WHOLE_KINDS.get(whole['kind'], (ins.target['kind'],)):
                ins.action, ins.reason = 'unclear', 'repeal_object'
            elif whole:
                ins.reason = 'whole_text'  # «ينسخ القرار رقم …»: the whole text goes
            else:                          # «ينسخ الجدولان رقم 1 و2 الملحقان بالمرسوم …»: a part, said otherwise
                ins.action = 'unclear'
                ins.reason = 'annex' if re.search(r'الجدول|الجداول|الملحق|الملاحق|النموذج|اللائحة|القائمة', after[:80]) \
                    else 'repeal_object'
        return ins
    ins.units = _units(text)
    if action == 'add' and not ins.units and ins.articles:
        ins.action, ins.reason = 'unclear', 'additions_not_quoted'
    elif not ins.units:
        # A table, an annex, a list or a title changed: no article to place it in.
        annex = re.search(r'الجدول|الجداول|الملحق|الملاحق|اللائحة|القائمة|النموذج|عنوان|البيان', lead)
        ins.action, ins.reason = 'unclear', 'annex' if annex else 'no_quoted_wording'
    elif action == 'modify' and not any(u.dotted or u.part for u in ins.units) and not any(a['part'] for a in ins.articles):
        ins.action = 'replace'             # «تغير … كما يلي» with each article printed whole
    return ins
