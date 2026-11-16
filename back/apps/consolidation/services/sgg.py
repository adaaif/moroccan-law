"""An SGG consolidated text, read from its repaired text layer (layer.py) into what the corpus keeps: its date
(«صيغة موطدة بتاريخ سبتمبر 2026»), where it was first published («ج.ر عدد 4796 …، ص : 1112»), its articles with
the headings above them, and each article's notes — the SGG's own record of what changed it:

    المادة 1
    (غيرت وتممت بموجب المادة الأولى من القانون رقم 34.05 …، ج.ر عدد 5397 بتاريخ 21 من محرم 1427 (20 فبراير
    2006)، ص : 458 ؛ وبموجب المادة الأولى من القانون رقم 013.26 …، ج.ر عدد 7533 …، ص: 5141)
"""
import re
from pathlib import Path
from dataclasses import dataclass, field
from datetime import date

from apps.consolidation.services import layer
from apps.consolidation.services.instructions.labels import number as article_number
from apps.corpus.services.issue_structure import ordinal_value, ordinal_words

MONTHS = {'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'ماي': 5, 'مايو': 5, 'يونيو': 6, 'يوليو': 7,
          'يوليوز': 7, 'غشت': 8, 'أغسطس': 8, 'شتنبر': 9, 'سبتمبر': 9, 'أكتوبر': 10, 'اكتوبر': 10, 'نونبر': 11,
          'نوفمبر': 11, 'دجنبر': 12, 'ديسمبر': 12, 'يبراير': 2}
RUNNING = re.compile(r'^\s*(?:\d{1,4}|الأمانة العامة للحكومة)\s*$')
# Numbered in digits, or in words: «الفصل العاشر», «الفصل الحادي عشر», «الفصل الثاني والعشرون», «الفصل السابع
# والعشرين», a tens word the layer split («الحادي والأر بعون»), «الفصل الثاني بعد المائة» (ordinal_value).
HEADING = re.compile(r'^(المادة|الفصل)\s+(\d+(?:\s*[.\-]\s*\d+)*|[ء-ي]+(?:\s+(?:عشرة?|و?[ء-ي]+(?:\s[ء-ي]+)?(?:ون|ين)))?(?:\s+بعد\s+(?:المائة|المئة))?)'
                     r'((?:\s+(?:المكررة|المكرر|مكررة|مكرر))(?:\s+(?:مرتين|ثلاث مرات|أربع مرات)|\s*\d{1,2})?)?\s*$')
DIVISION = re.compile(r'^(?:الكتاب|القسم|الجزء|الباب|الفرع|الفصل)\s+[^\s.]+(?:\s+(?:عشرة?|و[^\s.]+))?(?:\s+(?:المكرر|المكررة|مكرر))?\s*$')
# A stray dash after a division's word («الجزء- الخامس: التعويضات», Adala's social security dahir, p. 24) is dropped.
STRAY_DASH = re.compile(r'^(الكتاب|القسم|الجزء|الباب|الفرع)\s*-(?=\s)')
# Adala prints a division with its name on one line: «الباب الأول: نطاق التطبيق», «الباب الحادي عشر: المجلس الاقتصادي…»
# (a number in two words: the 2011 constitution's titles 11 to 14 were read as lines of the article before).
# Its name may hold commas («الباب الثالث: مدة العمل، الراحة الأسبوعية، والعطلة السنوية وأيام العطل», law 19.12).
NAMED_DIVISION = re.compile(r'^(?:الكتاب|القسم|الجزء|الباب|باب|الفرع|الفصل)\s+[^\s.]+(?:\s+(?:عشرة?|و[^\s.]+))?(?:\s+(?:المكرر|المكررة|مكرر))?\s*[:：]\s*\S'
                            r'[^.؛;]*$')
# A named division this long fills the line, and a short line right under it is the rest of its name: «الباب الخامس:
# الإجازات الخاصة ببعض المناسبات ورخص التغيب» / «الممنوحة لأسباب شخصية» (the labour code, p. 84).
WRAPS = 45
# Adala's footnote marks («⟦3⟧»): a line ends where its words end, not after its mark.
MARKS = re.compile(r'⟦\d+⟧')
# Adala's DOC prints a sub-article's number turned around: «الفصل -3 618 مكرر», «الفصل 106 1-», «الفصل 3-106» are
# 618-3 مكرر, 106-1 and 106-3 (H1 of the housing plan). A sub-number is never the larger.
TURNED = re.compile(r'^(المادة|الفصل)\s+(?:-\s*(\d+)\s+(\d+)|(\d+)\s+(\d+)\s*-|(\d{1,2})\s*-\s*(\d{3,4}))(?=\s|⟦|$)')


# Adala's 18.00 runs a numbered bis into its first line: «المادة 16 مكرر1 يتولى الجمع العام …». Cut when it follows
# on from the article before (16 or 17 after 16), so a reference to another article stays in its line.
RUN_IN_BIS = re.compile(r'^(المادة|الفصل)\s+(\d+)\s+مكرر\s*(\d{1,2})((?:⟦\d+⟧)*)\s+(?=\S)')


def _run_in_bis(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out, last = [], None
    for index, ln in lines:
        m = RUN_IN_BIS.match(ln)
        if m and last is not None and int(m.group(2)) in (last, last + 1):
            out += [(index, f'{m.group(1)} {m.group(2)} مكرر {m.group(3)}'), (index, ln[m.end():] + m.group(4))]
            last = int(m.group(2))
            continue
        if (h := HEADING.match(MARKS.sub('', ln).rstrip())) and (d := re.match(r'\d+', h.group(2))):
            last = int(d.group(0))
        out.append((index, ln))
    return out


# A heading and its note on one line, as the SGG's 52.05 prints its articles of 2016: «المادة221 (نسخت وعوضت بموجب
# المادة الثانية من القانون رقم 116.14 …)», «المادة 255 - 1 (أضيفت بموجب …)». Read as one line, the article stayed
# inside the one before it (the road topic's R1: the 30 days to pay, art. 221, were in art. 220).
HEAD_NOTE = re.compile(r'^(المادة|الفصل)\s*(\d+(?:\s*[.\-]\s*\d+)*(?:\s+(?:المكررة|المكرر|مكررة|مكرر))?)\s*'
                       r'(\((?:غيرت|تممت|غير|تمم|نسخت|نسخ|أضيفت|أضيف|عوضت|عوض|ألغيت|نقحت|حذفت).*)$')


# A heading set on the line of the article before's last words, the two glued at a stray U+FFFE: «املادة \ufffe55مدة
# صالحية الحامل …» is the end of art. 54's list, then «المادة 55» (52.05: arts 55, 65, 113, 139 were in their
# neighbours).
GLUED_HEADING = re.compile(r'^(المادة|الفصل)\s*\ufffe\s*(\d+(?:\s*[.\-]\s*\d+)*)\s*(\S.*)$')


def _note_after(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out = []
    for index, ln in lines:
        if m := HEAD_NOTE.match(ln):
            out += [(index, f'{m.group(1)} {m.group(2)}'), (index, m.group(3))]
        elif m := GLUED_HEADING.match(ln):
            out += [(index, m.group(3)), (index, f'{m.group(1)} {m.group(2)}')]
        else:
            out.append((index, ln.replace('\ufffe', '')))
    return out


def turned(ln: str) -> str:
    m = TURNED.match(ln)
    if not m:
        return ln
    main, sub = (m.group(3), m.group(2)) if m.group(2) else (m.group(4), m.group(5)) if m.group(4) else (m.group(7), m.group(6))
    return f'{m.group(1)} {main}-{sub}{ln[m.end():]}'
NOTE_END = re.compile(r'ص\s*:?\s*[()]?\s*\d+\s*[()]?(?=\s*$|\s+[^\s؛;،,0-9])')
REPEALED = re.compile(r'^\((?:نسخت|نسخ|ألغيت|حذفت)\)\s*[.،]?\s*$')
NOTE_VERBS = re.compile(r'^\((?:غيرت|تممت|غير|تمم|نسخت|نسخ|أضيفت|أضيف|عوضت|عوض|ألغيت|نقحت|حذفت|غيرت وتممت)')
# One amending text inside a note: «بموجب المادة الأولى من القانون رقم 013.26 … ج.ر عدد 7533 بتاريخ … ، ص: 5141».
BY = re.compile(r'بموجب\s+(?:(المادة|الفصل|البند)\s+(\S+(?:\s+(?:المكررة|مكرر))?)\s+من\s+)?'
                r'(القانون التنظيمي|القانون|المرسوم|الظهير الشريف|ظهير شريف|القرار|قرار|قانون المالية)[^ج]{0,60}?'
                r'رقم\s+(\d+(?:\.\d+)+)(.*?)ج\.?ر\.?\s*عدد\s*(\d+)\s*(مكرر)?(.*?)ص\s*:?\s*(\d+)', re.S)
DATE = re.compile(r'(\d{1,2})\s*(?:من\s+)?(' + '|'.join(MONTHS) + r')\s*(\d{4})')
VERB_OF = (('أضيف', 'added'), ('نسخ', 'repealed'), ('ألغي', 'repealed'), ('عوض', 'replaced'), ('غير', 'modified'),
           ('تمم', 'modified'), ('نقح', 'modified'))
KINDS = {'القانون التنظيمي': 'organic_law', 'القانون': 'law', 'قانون المالية': 'law', 'المرسوم': 'decree',
         'الظهير الشريف': 'dahir', 'ظهير شريف': 'dahir', 'القرار': 'order', 'قرار': 'order'}


@dataclass
class Note:
    verb: str                 # modified · added · repealed · replaced
    kind: str                 # law · decree · …
    number: str               # 013-26
    article: str              # «المادة الأولى» of the amending text, as printed
    issue: int
    issue_bis: bool
    page: int
    on: date | None


@dataclass
class SggArticle:
    label: str
    number: str
    heading_path: list[str]
    lines: list[str] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    note_text: str = ''
    page: int = 0             # 0-based index of the PDF page it starts on

    @property
    def body(self) -> str:
        return '\n'.join(self.lines).strip()


@dataclass
class SggText:
    title: str
    as_of: date | None
    first_issue: int | None
    first_page: int | None
    articles: list[SggArticle]
    stats: dict
    visas: str = ''             # «بناء على …» before the first article, one a line (T1 of the work plan)


# A decree's or an order's visas: from «بناء على» to the formula that ends them («رسم ما يلي», «قرر ما يلي»).
VISAS_END = re.compile(r'^(?:يرسم|رسم|قرر|يقرر)\s+ما\s+يلي|^(?:وبعد|ويعد|وبناء على اقتراح)')
FORMULA = re.compile(r'[،,]?\s*(?:أصدرن\s?ا\s+أمرنا|(?:يرسم|رسم|يقرر|قرر)\s+ما\s+يلي)')


def visas_of(head: list[str]) -> str:
    """The visas in a text's head lines, a line each (a visa wraps across the page's lines and ends at «؛»)."""
    start = next((k for k, ln in enumerate(head) if re.match(r'^بناء\s+على', ln)), None)
    if start is None:
        return ''
    run = []
    for ln in head[start:]:
        if VISAS_END.match(ln):
            break
        run.append(MARKS.sub('', ln).strip())
    joined = ' '.join(run)
    end = FORMULA.search(joined)
    joined = joined[:end.start()] if end else joined
    return '\n'.join(v.strip() for v in re.split(r'\s*[؛;]\s*|\s*[:.]\s*(?=وعلى\s)', joined) if v.strip())


def _date(s: str) -> date | None:
    m = DATE.search(s)
    if not m:
        return None
    try:
        return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def notes(note: str) -> list[Note]:
    out = []
    flat = re.sub(r'\s+', ' ', note)
    verb = next((v for stem, v in VERB_OF if stem in flat[:40]), 'modified')
    for m in BY.finditer(flat):
        # Each «بموجب» may carry its own verb when a note mixes them («غيرت … ثم نسخت …»).
        before = flat[max(0, m.start() - 30):m.start()]
        own = next((v for stem, v in VERB_OF if stem in before), verb)
        kind, number = KINDS.get(m.group(3), 'law'), m.group(4).replace('.', '-')
        # «القانون … الصادر بتنفيذه الظهير الشريف رقم 1.20.91»: a number shaped like a dahir's is the promulgating
        # dahir, whatever word came before it (47.06's art. 1 was «repealed by law 1-20-91»).
        if kind in ('law', 'organic_law') and re.fullmatch(r'1-\d{2}-\d+', number):
            kind = 'dahir'
        out.append(Note(verb=own, kind=kind, number=number,
                        article=f'{m.group(1)} {m.group(2)}' if m.group(1) else '', issue=int(m.group(6)),
                        issue_bis=bool(m.group(7)), page=int(m.group(9)), on=_date(m.group(8))))
    return out


def read(pages: list[str], word: str | None = None) -> SggText:
    """The document's pages (their raw text layer, in order) read into a text. `word` («المادة» or «الفصل») names the
    articles when the other word is more frequent only because the text quotes another's articles: law 103.13's own
    «المادة 1 … 18» quote the penal code's «الفصل 404 …», which then stay inside the article that quotes them."""
    stats = {'words': 0, 'turned': 0, 'unknown': 0}
    lines: list[tuple[int, str]] = []
    for index, raw in enumerate(pages):
        text, s = layer.repair(raw)
        for k in stats:
            stats[k] += s[k]
        for ln in text.splitlines():
            # «المادة221»: the number glued to its word (52.05's articles of 2016).
            ln = turned(re.sub(r'^(المادة|الفصل)(?=\d)', r'\1 ', STRAY_DASH.sub(r'\1', ln.strip())))
            if ln and not RUNNING.match(ln):
                lines.append((index, ln))
    lines = _note_after(_run_in_bis(lines))
    cover = ' '.join(ln for i, ln in lines if i == 0)
    m = re.search(r'(?:موطدة|محينة)\s+بتاريخ\s*(?:(\d{1,2})\s*)?(' + '|'.join(MONTHS) + r')\s*(\d{4})', cover)
    as_of = date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1) or 1)) if m else None
    title = ''
    # The articles are «المادة» or «الفصل», whichever the text numbers more; the other is a division.
    counts = {w: sum(1 for _, ln in lines if (h := HEADING.match(ln)) and h.group(1) == w) for w in ('المادة', 'الفصل')}
    quoted = word is not None
    word = word or max(counts, key=counts.get)
    heading = re.compile(rf'^({word})' + HEADING.pattern[len('^(المادة|الفصل)'):])
    # An article headed with its own title, as the nationality code (dahir 1.58.250) prints every one: «الفصل 5: تعريف
    # عبارة "في المغرب"». The title goes over the article, as a title printed on the line before it does.
    titled = re.compile(rf'^({word}\s+[^:：]+?)\s*[:：]\s*(\S[^.؛;]{{0,80}})$')
    start = next((k for k, (_, ln) in enumerate(lines) if heading.match(ln)), len(lines))
    head = [ln for i, ln in lines[:start] if i >= 1] or [ln for _, ln in lines[:start]]
    # The title runs from its first line to «كما تم تغييره …» or the BO reference «(ج.ر عدد …)».
    for k, ln in enumerate(head):
        if re.match(r'^(القانون|المرسوم|الظهير|ظهير|القرار|قرار|مرسوم)', ln):
            parts = [ln]
            for more in head[k + 1:k + 6]:
                if re.match(r'^(\(|كما\s|الحمد|إن\s|بناء|يعلم)', more) or 'ج.ر' in more or 'الجريدة الرسمية' in more:
                    break
                parts.append(more)
            title = re.sub(r'[،,]?\s*كما (?:تم|وقع) \S+(?: \S+)?\s*$', '', ' '.join(parts))
            title = re.sub(r'[،,]\s*$', '', title).strip()
            break
    pub = re.search(r'ج\.?ر\.?\s*عدد\s*(\d+).*?ص\s*:?\s*[()]?\s*(\d+)', ' '.join(head))

    # A constitution's «تصدير», its preamble, is part of the text (2011's says so itself): read as its own part, first,
    # from its word to the first division or article, and kept out of the title's lines.
    # A dahir that prints articles of its own first (1970's «يصدر جنابنا الشريف…») has it after them: a line of that
    # word alone, wherever it is.
    preamble = None
    at = next((k for k, (_, ln) in enumerate(lines) if ln.replace('ـ', '').strip(' :') in ('تصدير', 'التصدير')), None)
    if at is not None:
        end = next((k for k in range(at + 1, len(lines)) if DIVISION.match(lines[k][1].replace('ـ', ''))
                    or NAMED_DIVISION.match(lines[k][1].replace('ـ', '')) or heading.match(lines[k][1])), len(lines))
        body = [ln for _, ln in lines[at + 1:end]]
        if body:
            preamble = SggArticle(label='تصدير', number='preamble', heading_path=[], page=lines[at][0], lines=body)
            lines = lines[:at] + lines[end:]

    articles: list[SggArticle] = []
    headings: dict[str, str] = {}       # division word → its line, kept in order of depth
    pending: list[str] = []             # short lines since the last body line: headings unless a body follows
    in_note = False
    wrapped = None                      # the division whose name may go on to the next line
    nameless: set[str] = set()          # divisions printed without their name, which the next short line gives
    heading_marks: dict[int, str] = {}  # an article's heading's footnote marks, given to its body at the end
    for index, ln in lines:
        h = heading.match(ln)
        mark = ''
        if not h and (t := titled.match(MARKS.sub('', ln).rstrip())) and heading.match(t.group(1)) and not in_note:
            mark, ln, h = ''.join(MARKS.findall(ln)), t.group(1), heading.match(t.group(1))
            # The article names its title, so short lines before it end the article before («القانون», «بموجب مرسوم»).
            if articles:
                articles[-1].lines.extend(pending)
            pending = [t.group(2).strip()]
        if not h and MARKS.search(ln) and (h := heading.match(MARKS.sub('', ln).rstrip())):
            # A heading that carries its footnote's mark («الفصل 618-3 مكرر⟦173⟧»): the mark goes to the body.
            mark, ln = ''.join(MARKS.findall(ln)), MARKS.sub('', ln).rstrip()
        continues, wrapped = wrapped, None
        if continues and not h and not HEADING.match(ln) and not re.match(r'^(?:الكتاب|القسم|الجزء|الباب|باب|الفرع|الفصل)\s', ln) and not in_note \
                and len(MARKS.sub('', ln)) < WRAPS and not re.search(r'[.:؛;،,]\s*$', ln) and not re.match(r'^[-–•\d(]', ln):
            # A title printed bare, its name on the next line («الباب الأول» / «أحكام عامة», the 1996 constitution),
            # is one title: «الباب الأول: أحكام عامة».
            headings[continues] += (': ' if continues in nameless else ' ') + MARKS.sub('', ln).strip()
            nameless.discard(continues)
            continue
        if h and ' ' in h.group(2).strip() and ordinal_value(h.group(2)) is None \
                and not re.fullmatch(r'\d+(?:\s*[.\-]\s*\d+)+', h.group(2).strip()):     # «المادة 255 - 1» is one
            h = None
        if h and in_note:
            # A note left open (no «ص: …» to end it) ends at the next article, never swallows the rest (AMO 65.00
            # lost its articles 79 to 149 so).
            in_note = False
        if h and not in_note and articles and not articles[-1].lines and pending:
            # An article of one short line with no full stop («يحدد النظام الأساسي للقضاة بقانون تنظيمي», the 2011
            # constitution's art. 112) is that article's text, not a heading of the next.
            articles[-1].lines.append(pending.pop(0))
        if h and not in_note:
            # Lines just before an article's heading that read as headings («تعاريف», «الحقوق المعنوية»).
            # Not the title's own last line, left over before the first article (P12 of the polish review).
            path = list(headings.values()) + [p for p in pending if not DIVISION.match(p) and MARKS.sub('', p) not in title]
            # A word the layer split is put back in the label people read («الفصل الحادي والأربعون»).
            label = ln.replace(h.group(2), ordinal_words(h.group(2)), 1) if ' ' in h.group(2).strip() else ln
            articles.append(SggArticle(label=label, number=article_number(h.group(2), h.group(3)), heading_path=path,
                                       page=index))
            if mark:
                heading_marks[len(articles) - 1] = mark
            pending = []
            continue
        named = NAMED_DIVISION.match(MARKS.sub('', ln)) and len(ln) < 90 and not (word == 'الفصل' and ln.startswith('الفصل'))
        # A quoted article's heading («الفصل 404» inside law 103.13's «المادة 1») is a line of the quoting article.
        quoted_heading = quoted and HEADING.match(ln) and not heading.match(ln)
        if ((DIVISION.match(ln) and len(ln) < 40) or named or (word == 'المادة' and re.match(r'^الفصل\s+\S+\s*$', ln))) \
                and not in_note and not quoted_heading:
            level = ln.split()[0]
            # A higher division clears the ones under it.
            order = ['الكتاب', 'القسم', 'الجزء', 'الباب', 'باب', 'الفصل', 'الفرع']
            if level in order:
                for w in order[order.index(level):]:
                    headings.pop(w, None)
            headings[level] = MARKS.sub('', ln).strip() if named else ln
            if articles and pending and articles[-1].lines \
                    and not re.search(r'[.:؛;!؟?»")]\s*$', MARKS.sub('', articles[-1].lines[-1])):
                # Short lines before a division end the article before it when its sentence is open: the nationality
                # code's art. 15 lost «القانون», organic law 130.13's art. 69 «حيز التنفيذ ابتداء من فاتح يناير 2020».
                articles[-1].lines.extend(pending)
            wrapped = level if (named and len(headings[level]) >= WRAPS) or not named else None
            nameless.discard(level)
            if not named and DIVISION.match(ln):
                nameless.add(level)
            pending = []
            continue
        if articles and REPEALED.match(MARKS.sub('', ln)) and not articles[-1].lines and not in_note:
            # «(نسخت).»: the repealed article's whole body, not a note about it.
            articles[-1].lines.append(MARKS.sub('', ln).strip())
            continue
        if articles and (NOTE_VERBS.match(ln) or in_note) and not articles[-1].lines:
            # A note ends at its last page reference («ص : 1112)»); the layer may run the article on after it.
            end = NOTE_END.search(ln)
            articles[-1].note_text += ' ' + (ln[:end.end()] if end else ln)
            in_note = not end
            if end and ln[end.end():].strip():
                articles[-1].lines.append(ln[end.end():].strip())
            continue
        bare = MARKS.sub('', ln).rstrip()
        # A line ending in a number and its full stop, which the layer prints first («الفصل .84», «و82 و89 و.99»), ends a
        # sentence: it is the article's, never a heading of the next.
        short = len(bare) < 45 and not re.search(r'[.:؛;،,]\s*$|(?:^|[\sو])\.\d{1,4}$', bare) and not re.match(r'^[-–•\d(]', bare)
        if not articles:
            pending = pending + [ln] if short else []     # the title's lines are long or end in punctuation
            continue
        if ln.startswith(('(*)', '*')):
            # The SGG's footnote inside an article: «(*) حلت عبارة … بموجب المادة الثالثة من القانون رقم 013.26 …».
            articles[-1].note_text += ' (' + ln.lstrip('(*) ').strip() + ')'
            continue
        if short:
            pending.append(ln)
            continue
        if pending:
            articles[-1].lines.extend(pending)
            pending = []
        articles[-1].lines.append(ln)
    if pending and articles:
        articles[-1].lines.extend(pending)
    for k, mark in heading_marks.items():
        articles[k].lines.append(mark)
    if preamble:
        articles.insert(0, preamble)
    for a in articles:
        a.notes = notes(a.note_text)
        a.lines = [ln.replace('(*)', '').rstrip() for ln in a.lines]
    return SggText(title=title, as_of=as_of, first_issue=int(pub.group(1)) if pub else None,
                   first_page=int(pub.group(2)) if pub else None, articles=articles, stats=stats, visas=visas_of(head))


PAGE_TABLES = Path(__file__).resolve().parent.parent / 'data' / 'page_tables.yaml'


def page_tables(stem: str, articles: list[SggArticle]) -> int:
    """What the session read on a file's page images (data/page_tables.yaml), put in at every load. An entry with
    `from` replaces the article's end from those words (a table the layer flattened); with `after`, it is a head the
    reader lost, cut from the article before it at `from` (its body read whole in `table` when given, its divisions in
    `headings` when they are not its host's), or, with
    `was`, a head read with the wrong number; without either, it replaces the article's body, or adds a part the file
    has no words for (a scanned annex) after the articles. The count put in."""
    done = 0
    for entry in page_entries(stem):
        number = str(entry['article'])
        if 'after' in entry:
            at = next((k for k, a in enumerate(articles) if a.number == str(entry['after'])), None)
            if at is None:
                continue
            if 'was' in entry:         # «20» read where the page prints «28»
                if at + 1 < len(articles) and articles[at + 1].number == str(entry['was']):
                    articles[at + 1].number, articles[at + 1].label = number, entry['label']
                    done += 1
                continue
            host = articles[at]
            m = _anchor(entry['from']).search(host.body)
            if m is None:
                continue
            body = host.body
            host.lines = body[:m.start()].rstrip().splitlines()
            articles.insert(at + 1, SggArticle(label=entry['label'], number=number,
                                               heading_path=entry.get('headings', host.heading_path),
                                               lines=(entry.get('table') or body[m.start():]).strip().splitlines(),
                                               page=entry.get('page', host.page + 1) - 1))
            done += 1
            continue
        if 'from' not in entry:
            mine = next((a for a in articles if a.number == number), None)
            if mine is not None:       # the body read whole on the page
                mine.lines = entry['table'].strip().splitlines()
            else:
                articles.append(SggArticle(label=entry['label'], number=number, heading_path=[],
                                           lines=entry['table'].splitlines(), page=entry.get('page', 1) - 1))
            done += 1
            continue
        anchor = _anchor(entry['from'])
        for a in articles:
            body = a.body
            if a.number == number and (m := anchor.search(body)):
                a.lines = (body[:m.start()].rstrip() + '\n' + entry['table']).splitlines()
                done += 1
    return done


def _anchor(words: str) -> re.Pattern:
    return re.compile(r'\s+'.join(map(re.escape, words.split())))      # the layer cuts its lines anywhere


def page_entries(stem: str) -> list[dict]:
    import yaml
    return [e for e in (yaml.safe_load(PAGE_TABLES.read_text()) if PAGE_TABLES.exists() else []) if e['file'] == stem]
