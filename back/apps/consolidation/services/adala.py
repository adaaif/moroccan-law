"""A text from Adala, the Ministry of Justice's portal (row 3: filling the shelf), read from its PDF's text layer.

Adala's PDFs are made in Word. Read as the SGG's are (sgg.read), Word's print runs into the articles: the page
numbers («- 41 -»), the footnotes at the foot of a page, and the footnote marks, which the layer prints at the
start of a line of their own («…بقرار من وزير» / «4 العدل» / «؛») or before a heading («2 المادة 15»). Each
character's size tells them apart: the law is set in the text's main size, the footnotes smaller, the marks
smaller still. So each page is rebuilt from its characters: the body with its marks taken out, the footnotes
apart. A footnote opens with its number («-4 …», «2 - …»); one carried over from the page before has none.

A mark becomes «⟦4⟧» in the body, and after sgg.read each article takes the footnotes marked in it. The footnotes
are kept as Adala printed them, not read yet: a few record an amendment, most name the order or decree that
carries an article out.
"""
import re
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass, field

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from apps.consolidation.services import layer, sgg

PAGE_NUMBER = re.compile(r'^\s*-\s*\d{1,4}\s*-\s*$')
OPENS = re.compile(r'^\s*(?:-\s*(\d{1,3})\s+|(\d{1,3})\s*-\s+)')
PUNCTUATION = re.compile(r'^\s*[.:؛;،,]+\s*$')
RUN_IN = re.compile(r'^(المادة|الفصل)(?=\d)')
LEADING = re.compile(r'^(\d{1,3})\s+')
MARK = re.compile(r'⟦(\d+)⟧')
PROMULGATES = re.compile(r'بتنفيذ\s+((?:القانون|قانون)(?:\s+التنظيمي)?\s+رقم\s+\d+(?:\.\d+)+.*)$')
FOOTNOTE_SIZE = 0.9     # a line all smaller than this share of the main size is a footnote's
MARK_SIZE = 0.75        # a digit smaller than this share of its line's letters is a mark
SAME_LINE = 0.35        # runs whose baselines are closer than this share of the main size are one line
SYMBOL = str.maketrans({'\uf02d': '-', '\uf0b7': '•'})     # Word's Symbol-font dash and bullet, in the private area
OCR_WHEN = 0.3          # a layer whose words are unknown three times in ten is no text: read the page images
OCR_SCALE = 4           # 288 dpi: Tesseract reads Adala's 16 pt Arabic well at this size
OCR_FOOT = 0.88         # a line lower than this share of the page's usual line height is a footnote's
# Letters an image reading confuses by their dots: a word the corpus does not know is put right only into one it
# prints often («رفم» → «رقم»).
DOTS = ['قف', 'بتثني', 'ةه', 'جحخ', 'رز', 'دذ', 'عغ', 'صض', 'سش', 'طظ']


@dataclass
class Footnote:
    number: int
    page: int               # 0-based index of the PDF page it starts on
    text: str
    article: str = ''       # the label of the article that marks it; empty for the text's own


@dataclass
class AdalaText:
    text: sgg.SggText
    footnotes: list[Footnote] = field(default_factory=list)
    preamble: str = ''      # the articles of the dahir that approves a code («الفصل الأول … التاسع»), before its own


Char = tuple[str, float, float]         # a character, its size, its bottom on the page


def _lines(textpage) -> list[list[Char]]:
    """The page's characters with their sizes and places, run by run as the layer gives them."""
    count = textpage.count_chars()
    chars = textpage.get_text_range(0, count)
    lines, line = [], []
    for k, ch in enumerate(chars):
        if ch in '\r\n':
            if line:
                lines.append(line)
            line = []
        else:
            line.append((ch, pdfium_c.FPDFText_GetFontSize(textpage, k), textpage.get_charbox(k, loose=True)[1]))
    if line:
        lines.append(line)
    return lines


def _main_size(pages: list[list[list[Char]]]) -> float:
    sizes = Counter(round(s, 1) for page in pages for line in page for ch, s, _ in line if not ch.isspace())
    return sizes.most_common(1)[0][0]


def _run(line: list[Char]) -> tuple[str, list[int], float]:
    """A run's words with its marks taken out, its marks, and its baseline. A mark is a digit set small beside its
    run's letters (a title is set larger than the articles)."""
    letters = Counter(round(s, 1) for ch, s, _ in line if not ch.isspace() and not ch.isdigit())
    size = letters.most_common(1)[0][0] if letters else 0
    words, marks, digits = [], [], ''
    for ch, s, _ in line + [(' ', size, 0.0)]:
        if ch.isdigit() and s < size * MARK_SIZE:
            digits += ch
            continue
        if digits:
            marks.append(int(digits))
            digits = ''
        words.append(ch)
    bottoms = sorted(b for ch, s, b in line if not ch.isspace() and s >= size * MARK_SIZE)
    return ''.join(words).strip(), marks, bottoms[len(bottoms) // 2] if bottoms else 0.0


def _base(number: str) -> int | None:
    m = re.match(r'(\d+)', number or '')
    return int(m.group(1)) if m else None


def keep_quoted(articles: list) -> list:
    """A law that adds a chapter to another text prints that text's articles under its own («يتمم القسم الأول من الكتاب
    الأول … بالباب الرابع كالآتي:», law 24.09 art. 65, then the DOC's 106-1 to 106-14): an article numbered far from the
    law's own run, after one whose words end on «:», is the other text's, and stays in the article that quotes it, as
    the French edition prints it. The law's next own article (66 after 65) ends the quote."""
    out: list = []
    host = None
    for a in articles:
        n = _base(a.number)
        if host is not None and n is not None and '-' in a.number and abs(n - _base(host.number)) > 1:
            host.lines += [a.label, *a.lines]
            continue
        host = a if a.lines and a.lines[-1].rstrip().endswith(':') and _base(a.number) is not None else None
        out.append(a)
    return out


def split_page(lines: list[list[Char]], main: float) -> tuple[list[str], list[str]]:
    """A page's body lines (its marks as «⟦n⟧») and its footnote lines.

    The layer cuts a printed line at its mark: «…بقرار من وزير» / «4 العدل» / «؛» is «…بقرار من وزير العدل⁴؛», and
    «2 المادة 15» is the heading «المادة 15» marked. The runs on one baseline are joined back into their line."""
    lines = [ln for ln in lines if not PAGE_NUMBER.match(''.join(ch for ch, *_ in ln))]
    small = [all(s < main * FOOTNOTE_SIZE for ch, s, _ in ln if not ch.isspace()) for ln in lines]
    foot = len(lines)
    while foot and small[foot - 1]:     # the footnotes are the page's last lines, all set small
        foot -= 1
    printed: list[tuple[str, list[int], float]] = []
    for ln in lines[:foot]:
        words, marks, base = _run(ln)
        if printed and abs(printed[-1][2] - base) < main * SAME_LINE:
            before, marked, _ = printed[-1]
            printed[-1] = (before + words if PUNCTUATION.match(words) else f'{before} {words}', marked + marks, base)
        else:
            printed.append((words, marks, base))
    body: list[str] = []
    for words, marks, _ in printed:
        # Word justifies with tatweel («ظـهـير») and sets its list dashes in the Symbol font.
        words = RUN_IN.sub(r'\1 ', words.replace('ـ', '').translate(SYMBOL).strip())
        # A heading never opens with a number: «5 الفصل 14» is a mark, though some are set full size.
        if (m := LEADING.match(words)) and sgg.HEADING.match(words[m.end():]):
            words, marks = words[m.end():], marks + [int(m.group(1))]
        tokens = ''.join(f'⟦{n}⟧' for n in marks)
        if marks and sgg.HEADING.match(words):
            body += [words, f'{tokens}.']     # «⟦2⟧.» ends in a stop, so sgg.read keeps it in the article
        else:
            body.append(words + tokens)
    return body, [''.join(ch for ch, *_ in ln).strip() for ln in lines[foot:]]


def footnotes(pages: list[list[str]]) -> list[Footnote]:
    """The footnotes from each page's footnote lines: a line opening with one of the next few numbers starts one
    (Adala's numbering skips one at times: the penal code goes from 49 to 51), any other line runs on the one
    before, across pages too."""
    out: list[Footnote] = []
    for index, lines in enumerate(pages):
        for ln in lines:
            m = OPENS.match(ln)
            n = int(m.group(1) or m.group(2)) if m else None
            if n is not None and (not out or 0 < n - out[-1].number <= 5):
                out.append(Footnote(number=n, page=index, text=ln[m.end():].strip()))
            elif out:
                out[-1].text += '\n' + ln
    for f in out:
        f.text = layer.repair(f.text)[0]
    return out


def _dots(line: str, words: dict[str, int]) -> str:
    def fix(m: re.Match) -> str:
        w = m.group(0)
        if words.get(w):
            return w
        best, best_n = w, 0
        for i, ch in enumerate(w):
            for group in DOTS:
                if ch in group:
                    for other in group.replace(ch, ''):
                        form = w[:i] + other + w[i + 1:]
                        if words.get(form, 0) > best_n:
                            best, best_n = form, words[form]
        return best if best_n >= 10 else w
    return re.sub(r'[ء-ي]{3,}', fix, line)


def ocr_pages(path: str) -> list[tuple[list[str], list[str]]]:
    """Each page read from its image by Tesseract (the free witness), for a file whose text layer is no text (decree
    2.10.311 on the driving licence: «يج إيداع الطل» for «يجب إيداع الطلب»): its body lines and its footnote lines,
    told apart by their height as the layer's are by their size. The marks are lost: a footnote is the text's."""
    words = layer.lexicon()
    out = []
    pdf = pdfium.PdfDocument(path)
    try:
        for i in range(len(pdf)):
            with tempfile.NamedTemporaryFile(suffix='.png') as f:
                pdf[i].render(scale=OCR_SCALE).to_pil().convert('L').save(f.name)
                tsv = subprocess.run(['tesseract', f.name, '-', '-l', 'ara', '--psm', '6', 'tsv'],
                                     capture_output=True, text=True, check=True).stdout
            found: dict[tuple, list] = {}
            for row in tsv.splitlines()[1:]:
                c = row.split('\t')
                if len(c) >= 12 and c[0] == '5' and c[11].strip():
                    found.setdefault((int(c[2]), int(c[3]), int(c[4])), []).append((int(c[7]), int(c[9]), c[11]))
            rows = sorted((min(t for t, _, _ in ws), max(h for _, h, _ in ws), ' '.join(w for _, _, w in ws))
                          for ws in found.values())
            rows = [r for r in rows if not PAGE_NUMBER.match(r[2]) and not re.fullmatch(r'\s*\d{1,3}\s*', r[2])]
            if not rows:
                out.append(([], []))
                continue
            usual = sorted(h for _, h, _ in rows)[len(rows) // 2]
            foot = len(rows)
            while foot and rows[foot - 1][1] < usual * OCR_FOOT:
                foot -= 1
            # Tesseract gives an Arabic line's brackets and quotes as drawn: «)29 سبتمبر 2010(» is «(29 سبتمبر 2010)».
            mirror = str.maketrans('()«»', ')(»«')
            body = [RUN_IN.sub(r'\1 ', _dots(t, words)).translate(mirror) for _, _, t in rows[:foot]]
            out.append((body, [_dots(t, words).translate(mirror) for _, _, t in rows[foot:]]))
    finally:
        pdf.close()
    return _headings(out)


OCR_HEADING = re.compile(r'^(المادة|الفصل)\s+(\S+)(?:\s+\d{1,2})?\s*$')


def _headings(pages: list[tuple[list[str], list[str]]]) -> list[tuple[list[str], list[str]]]:
    """Article headings as an image reading leaves them, put right by their order: the footnote mark that follows
    one is dropped («المادة 2 3» is article 2, marked 3), and a number misread between two that follow each other is
    the one between («المادة ©» after 8 and before 10 is 9)."""
    spots = [(p, k, m.group(1), m.group(2)) for p, (body, _) in enumerate(pages) for k, line in enumerate(body)
             if (m := OCR_HEADING.match(line.strip()))]
    numbers = [int(n) if n.isdigit() else (1 if n in ('الأولى', 'الأول') else None) for *_, n in spots]
    for i, (p, k, word, label) in enumerate(spots):
        n = numbers[i]
        before = numbers[i - 1] if i else 0
        after = numbers[i + 1] if i + 1 < len(numbers) else None
        if before is not None and n != before + 1 and after == before + 2:
            n = numbers[i] = before + 1
        pages[p][0][k] = f'{word} {label if label in ("الأولى", "الأول") else n if n is not None else label}'
    return pages


# A heading run into its article's first line, as the 1984 dahir on accident victims prints them: «المادة األولى
# مكررة . - يراد بما يلي …» is the heading «المادة الأولى مكررة» and the line «يراد بما يلي …».
RUN_HEADING = re.compile(r'^((?:المادة|الفصل)\s+\S+(?:\s+(?:عشرة?|و\S+ون))?'
                         r'(?:\s+(?:مكررة|مكرر)(?:\s+(?:مرتين|ثلاث\s+مرات|أربع\s+مرات))?)?)'
                         r'\s*\.\s*[-–]\s*(.+)$')


# A marked heading the layer sets at the end of the line before it («… ولكنه 10 المادة الثامنة», «… عيشهم من 11
# المادة الحادية عشرة»: the dahir's articles law 70.24 rewrote carry a footnote mark, and Word anchors it there).
# Only a marked one: «في المادة الخامسة» ending a line is a reference.
TRAILING_HEADING = re.compile(r'^(.*\S)\s+((?:المادة|الفصل)\s+\S+(?:\s+(?:عشرة?|و\S+ون))?)\s*((?:⟦\d+⟧)+)$')


# A run-in heading whose mark has two digits, which the layer gives words first and heading last («. - يجب على مقاولة
# التأمين أن تقوم … المادة التاسعة عشرة⟦16⟧»: the dahir's arts 8, 11, 13, 16–27 bis, the road plan): the words
# were the article's first line, and stayed with the article before.
REVERSED_RUN_IN = re.compile(r'^[-–.\s]*[-–]\s*(?:\.\s*)?(\S.*?)\s+((?:المادة|الفصل)\s+\S+(?:\s+(?:عشرة?|و\S+ون))?'
                             r'(?:\s+(?:مكررة|مكرر)(?:\s+(?:مرتين|ثلاث\s+مرات|أربع\s+مرات))?)?)\s*((?:⟦\d+⟧)+)$')


# A titled heading numbered in digits, which the layer gives colon first: «الفصل :5 تعريف عبارة "في المغرب"» is «الفصل 5:
# تعريف …» (the nationality code). And the title of a heading whose mark has two digits, set on the line before it and
# turned around: «المحلي : الاختصاص» / «الفصل الثامن والثلاثون» / «⟦23⟧.» is «الفصل الثامن والثلاثون: الاختصاص المحلي».
DIGIT_TITLED = re.compile(r'^(المادة|الفصل)\s*:\s*(\d{1,3})\s+(\S.*)$')
TURNED_TITLE = re.compile(r'^([^:.؛;]*?)\s*:\s*([^:.؛;]+)$')
DIVISION_WORD = re.compile(r'(?:^|\s)(?:الكتاب|القسم|الجزء|الباب|باب|الفرع)(?:\s|$)')


def _titles(lines: list[str]) -> list[str]:
    out: list[str] = []
    for k, line in enumerate(lines):
        # Matched on the repaired words; a line left as it is stays unrepaired (repair twice turns brackets back).
        words = layer.repair(line)[0].strip()
        bare = sgg.MARKS.sub('', words).strip()
        before = layer.repair(out[-1])[0].strip() if out else ''
        marked = k + 1 < len(lines) and re.fullmatch(r'\s*(?:⟦\d+⟧)+\s*\.?\s*', lines[k + 1])
        if before and sgg.HEADING.match(bare) and (m := TURNED_TITLE.match(before)) and len(before) < 70 \
                and (before.startswith(':') or marked) and not DIVISION_WORD.search(before):
            title = ' '.join(filter(None, (m.group(2).strip(), m.group(1).strip())))
            out[-1] = f'{bare}: {title}' + ''.join(sgg.MARKS.findall(words))
            continue
        out.append(DIGIT_TITLED.sub(r'\1 \2: \3', words) if DIGIT_TITLED.match(words) else line)
    return out


def _run_in(body: list[str]) -> list[str]:
    out = []
    for line in body:
        if m := RUN_HEADING.match(line):
            out += [layer.repair(m.group(1))[0], m.group(2)]
        elif m := REVERSED_RUN_IN.match(line):
            out += [layer.repair(m.group(2))[0], f'{m.group(3)}.', m.group(1)]
        elif m := TRAILING_HEADING.match(line):
            out += [m.group(1), layer.repair(m.group(2))[0], f'{m.group(3)}.']
        else:
            out.append(line)
    return _titles(out)


def read(path: str, word: str | None = None) -> AdalaText:
    pdf = pdfium.PdfDocument(path)
    try:
        pages = [_lines(pdf[i].get_textpage()) for i in range(len(pdf))]
    finally:
        pdf.close()
    main = _main_size(pages)
    split = [(_run_in(body), foot) for body, foot in (split_page(lines, main) for lines in pages)]
    text = sgg.read(['\n'.join(body) for body, _ in split], word)
    if text.stats['words'] and text.stats['unknown'] > OCR_WHEN * text.stats['words']:
        split = ocr_pages(path)
        # The cover's «صيغة محينة بتاريخ …» is set small: on an image it reads as a footnote line.
        cover = [line for line in split[0][1] if 'صيغة' in line] if split else []
        split = [(cover + split[0][0], split[0][1])] + split[1:] if cover else split
        text = sgg.read(['\n'.join(body) for body, _ in split], word)
        text.stats['read_by'] = 'tesseract'
    notes = {f.number: f for f in footnotes([foot for _, foot in split])}
    for a in text.articles:
        for n in MARK.findall('\n'.join(a.lines)):
            if int(n) in notes:
                notes[int(n)].article = a.label
        a.lines = [line for line in (MARK.sub('', ln).rstrip() for ln in a.lines) if not PUNCTUATION.match(line)]
        a.heading_path = [MARK.sub('', h).strip() for h in a.heading_path]
    # A code approved by a dahir (the penal code) prints the dahir's own articles first; the code's numbering then
    # starts again at 1. The dahir's go to the preamble, so the code's articles keep their addresses.
    restart = next((k for k, a in enumerate(text.articles)
                    if k and a.number == '1' and any(b.number != 'preamble' for b in text.articles[:k])), 0)
    preamble = '\n\n'.join(f'{a.label}\n{a.body}' for a in text.articles[:restart] if a.number != 'preamble')
    # The constitution's own «تصدير» stays with it, first, whatever the dahir before it printed.
    text.articles = [a for a in text.articles[:restart] if a.number == 'preamble'] + text.articles[restart:]
    text.articles = keep_quoted(text.articles)
    # A dahir's title runs on a line that opens with its date, «(26 نونبر 1962) بالمصادقة على مجموعة القانون
    # الجنائي»; sgg.read stops a title at «(», where the SGG's own reference line starts.
    head = [layer.repair(ln)[0].strip() for body, _ in split[:4] for ln in body]
    if text.title in head and (k := head.index(text.title)) + 1 < len(head) and sgg.DATE.match(head[k + 1][1:]):
        text.title = f'{text.title} {head[k + 1]}'
        # …and the law's name may run on to the next line, which its footnote mark ends: «… المتعلق بمحاربة» /
        # «العنف ضد النساء⟦1⟧» (law 103.13).
        for more in head[k + 2:k + 4]:
            if MARK.search(text.title) or re.match(r'^(الحمد|الطابع|يعلم|بناء|\()', more):
                break
            text.title = f'{text.title} {more}'
    # The list of amending texts under the title is not the title («… 52.05 كما وقع تغييره وتتميمه ب: - مرسوم …»).
    text.title = re.split(r'\s+كما\s+وقع\s+تغيير', text.title)[0].rstrip(' :،,')
    title_marks = [int(n) for n in MARK.findall(text.title)]
    text.title = MARK.sub('', text.title).strip()
    # A mark the layer gave in the text's own size reads as a number after the title («… بتنفيذ نص الدستور 1»).
    if (m := re.search(r'\s(\d{1,2})$', text.title)) and int(m.group(1)) in notes and not title_marks:
        title_marks, text.title = [int(m.group(1))], text.title[:m.start()].rstrip()
    # A law is headed by the dahir that promulgates it («ظهير شريف رقم 1.13.111 … بتنفيذ القانون رقم 67.12 المتعلق
    # …»): the text is the law, titled from «القانون» on, as the BO pipeline files it.
    if m := PROMULGATES.search(text.title):
        text.title = m.group(1).rstrip(' .')
    # The title's footnote names the BO issue that first published the text: «الجريدة الرسمية عدد 5184 … ص .418»;
    # the penal code's is its first footnote, marked in the dahir's preamble.
    first = min(notes, default=None)
    if not title_marks and first and not notes[first].article and notes[first].text.startswith('الجريدة الرسمية'):
        title_marks = [first]
    for n in title_marks:
        if n in notes and (m := re.search(r'عدد\s*(\d+).*?ص\s*[.:]?\s*(\d+)', notes[n].text, re.S)):
            text.first_issue, text.first_page = int(m.group(1)), int(m.group(2))
    return AdalaText(text=text, footnotes=list(notes.values()), preamble=preamble or text.visas)


# A footnote that says what changed its article (row L9 of the links review): «تم تغيير وتتميم الفقرة الأولى من المادة
# 15 أعلاه، بمقتضى المادة الفريدة القانون رقم 65.21 …، الجريدة الرسمية عدد 7006 …، ص. 5650». Adala names the
# changing text by kind and number, and its BO issue and page only now and then.
CHANGED = re.compile(r'(?:تم\s+)?(?:تغيير|تتميم|تعديل|أضيفت|أضيف|إضافة|نسخ|نسخت|إلغاء|ألغيت|تعوض|عوضت|تعويض|حذف)')
VERB_OF = (('أضيف', 'added'), ('إضافة', 'added'), ('نسخ', 'repealed'), ('إلغاء', 'repealed'), ('ألغي', 'repealed'),
           ('حذف', 'repealed'), ('عوض', 'replaced'), ('تعويض', 'replaced'), ('تعوض', 'replaced'))
ISSUE = re.compile(r'الجريدة الرسمية\s+عدد\s+(\d{3,5})\s*(مكرر)?.{0,80}?ص\s*\.?\s*:?\s*(\d{1,5})', re.S)


def footnote_changes(text: str) -> list[dict]:
    """What a footnote says changed its article: [{verb, kind, number, issue, bis, page}], the dahir that
    promulgated the changing law left out."""
    import ma_law
    flat = re.sub(r'\s+', ' ', text)
    verb_at = CHANGED.search(flat[:80])
    if not verb_at:
        return []
    verb = next((v for stem, v in VERB_OF if stem in verb_at.group(0)), 'modified')
    out = []
    for c in ma_law.parse_citations(flat):
        if c['kind'] != 'text' or not c.get('text_number'):
            continue
        if c.get('text_kind') == 'dahir' and 'بتنفيذه' in flat[max(0, c['start'] - 25):c['start']]:
            continue
        issue = ISSUE.search(flat, c['end'])
        out.append({'verb': verb, 'kind': c.get('text_kind') or 'law', 'number': c['text_number'],
                    'issue': int(issue.group(1)) if issue else None, 'bis': bool(issue and issue.group(2)),
                    'page': int(issue.group(3)) if issue else None})
        break           # the first text named is the one that changed the article
    return out
