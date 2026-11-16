"""The tax code as the DGI publishes it (the tax review, T1, 26 Oct 2026): the yearly edition of the Code général des
impôts, Arabic and French, made in Word like Adala's files, so read the same way (services/adala.py: each page rebuilt
from its characters, the footnotes apart by their size, turned letters put right by the lexicon). What differs is the
page's own shape:

- a heading prints its number between its marks in visual order, «المادة -.2 الأشخاص…», «المادة .13 - عوائد…», «المادة 20
  -. الإقرار…», for «المادة 2.- …»: put back before the reader cuts articles;
- the book ends with its table of contents, each line a heading and a page after dotted leaders: left out;
- a footnote names only the finance law that gave the passage its words («المادة 8 من قانون المالية رقم 60.24 للسنة
  المالية 2025»): each such law is a witness that it changed the article (`footnote_laws`).

The edition is unofficial: the BO prevails, and the finance laws the site reads say what changed and when."""
import re

import pypdfium2 as pdfium

from apps.consolidation.services import adala, sgg

# «المادة -.2 …», «المادة .13 - …», «المادة 20 -. …», «المادة 40 -. …», «المادة الأولى-. …»: the number and its «.-».
_TIMES = r'(?:\s+(?:مرتين|ثلاث مرات|أربع مرات|خمس مرات|ست مرات|سبع مرات))?'
_HEAD = [
    # The title before the number, in the page's visual order: «-. عائدات شهادات الصكوك  المادة 14 المكررة⟦2⟧».
    (re.compile(r'^\.?\s*[-–]\s*\.?\s*(\S.*?)\s{2,}المادة\s+(\d{1,3})\s+(المكررة' + _TIMES + r')\s*\.?\s*((?:⟦\d+⟧)?)\s*\.?\s*$'),
     r'المادة \2 \3.- \1\4'),
    (re.compile(r'^(المادة|الفصل)\s*\.\s*[-–]\s*(\d+)(?!\d)\s*'), r'\1 \2.- '),
    (re.compile(r'^(المادة|الفصل)\s*[-–]\s*\.\s*(\d+)(?!\d)\s*'), r'\1 \2.- '),
    (re.compile(r'^(المادة|الفصل)\s*\.\s*(\d+)\s*[-–]\s*'), r'\1 \2.- '),
    (re.compile(r'^(المادة|الفصل)\s+(\d+)\s*[-–]\s*\.\s*'), r'\1 \2.- '),
    (re.compile(r'^(المادة|الفصل)\s+(\d+)\s*\.\s*[-–]\s*'), r'\1 \2.- '),
    (re.compile(r'^(المادة|الفصل)\s+(الأولى|األولى)\s*[-–]?\s*\.\s*[-–]?\s*'), r'\1 الأولى.- '),
]
# A line of the table of contents: words, dotted leaders, a page number.
_CONTENTS = re.compile(r'\.{6,}\s*\d*\s*$|^\s*\d{1,4}\s*\.{6,}')


def heading(line: str) -> str:
    for pattern, repl in _HEAD:
        if pattern.match(line):
            line = pattern.sub(repl, line, count=1)
            break
    # «المادة 82.- المكررة -إقرار …»: the mark moved before the bis word.
    return re.sub(r'^المادة (\d+)\.- (المكررة' + _TIMES + r')\s*[-–.]*\s*', r'المادة \1 \2.- ', line)


BIS = {'': '', 'مرتين': '-ter', 'ثلاث مرات': '-quater', 'أربع مرات': '-quinquies', 'خمس مرات': '-sexies',
       'ست مرات': '-septies', 'سبع مرات': '-octies'}
# A heading, once its marks are put back: «المادة 15 المكررة مرتين.- عائدات الكراء», «المادة الأولى.- تعريف».
ARTICLE = re.compile(r'^المادة\s+(الأولى|\d{1,3})(?:\s+(?:المكررة|المكرر|مكررة|مكرر)(?:\s+(مرتين|ثلاث مرات|أربع مرات|خمس مرات|ست مرات|سبع مرات))?)?'
                     r'\s*(?:\.\s*[-–]|[-–]\s*\.|[-–])\s*(.*)$')
_ANNEXES = re.compile(r'^المقتضيات الجبائية المتعلقة بالمدونة العامة للضرائب\s*$')
LONE = re.compile(r'^المادة\s+(\d{1,3})((?:\s+(?:المكررة|مكررة)' + _TIMES + r')?)\s*(?:⟦\d+⟧)?\s*$')
REPEALED = re.compile(r'\((?:تنسخ|نسخت|ملغاة)\)\s*(?:⟦\d+⟧)?')
LEADS = re.compile(r'(?:^|\s)(?:في|من|إليه|إليها|عليه|عليها|بمقتضى|بموجب|و|أو|لأحكام|أحكام)\s*$')
CARRIES = re.compile(r'^(?:أعلاه|أدناه|من|في|و|أو|،|؛|\.|المشار|المنصوص|بعده|قبله)')
# A line that only starts with a reference to an article: «المادة 82 - III أدناه بتخفيض …».
REFERENCE = re.compile(r'^\s*[IVXΙ]+\b|(?:^|\s)(?:أدناه|أعلاه|المشار\s+إليه|المشار\s+إليها|المنصوص\s+عليه|المنصوص\s+عليها)(?=[\s،.؛]|$)')
# A line that opens a new paragraph: a list's mark («I.-», «ألف-», «1°-», «-», «•»), or a division.
OPENS = re.compile(r'^(?:[IVXΙ]+\s*[-.–]|[A-Z]\s*[-.–]|[ء-ي]{1,4}\s*[-–]|\d{1,2}\s*°|\(?\d{1,2}\s*[-–)]|[-–•●▪]\s*\S|"|«)')
# A division's own line with its title: its second word counts it («الكتاب الثاني: المساطر الجبائية»). Without that, a
# line of body text that a wrap starts on «الكتاب» was taken for a book: art. 225's «… يبلغ الكُتّاب مقررو هذه اللجان إلى
# الطرفين …» (the committees' clerks) headed arts 226–248 of the 2026 edition and cost them their own headings. «القسم
# الفرعي الأول» is the edition's sub-title.
_ORDINAL = (r'(?:ال(?:تمهيدي|تمهيدية|أول|أولى|اول|اولى|ثاني|ثانية|ثالث|ثالثة|رابع|رابعة|خامس|خامسة|سادس|سادسة|سابع|سابعة|ثامن|ثامنة|'
            r'تاسع|تاسعة|عاشر|عاشرة|حادي|حادية|عشرون|ثلاثون|فريد|وحيد|أخير)|\d{1,3}|[IVXΙ]{1,6})')
NUMBERED = re.compile(rf'^(الكتاب|القسم|الجزء|الباب|الفرع)\s+(?:(?:الفرعي|الفرعية)\s+)?{_ORDINAL}(?=[\s:.\-–]|$)')
ENDS = re.compile(r'[.:؛!؟?»"]\s*$')


def cut(pages: list[list[str]]) -> 'sgg.SggText':
    """The edition's articles, in order: a heading whose number is the next one, or a bis of the one before, starts an
    article (a heading's number elsewhere is a reference: «المادة 41 أعلاه» has no «.-»); the divisions above become its
    headings; its lines are joined into paragraphs."""
    from apps.consolidation.services import layer
    words = layer.lexicon()
    articles: list[sgg.SggArticle] = []
    used: set[str] = set()
    heads: dict[int, str] = {}
    last = 0
    stats = {'words': 0, 'turned': 0, 'unknown': 0}

    def fix(line: str) -> str:
        out, st = layer.repair(line, words)
        for k in stats:
            stats[k] += st[k]
        return out

    # «غير المقيمين  المادة -.15 …»: a heading the layer put on the line before's baseline starts a line of its own.
    flat = [(index, part) for index, lines in enumerate(pages) for raw in lines
            for part in re.split(r'\s{2,}(?=المادة\s*[-–.]+\s*\d)', raw)]
    cleaned = [(index, tidy(fix(heading(raw)).strip())) for index, raw in flat]
    cleaned = [(index, line) for index, line in cleaned
               if line and not _RUNNING.match(line) and not re.fullmatch(r'\d{1,4}', line)]
    titled = False
    for pos, (index, line) in enumerate(cleaned):
        # A heading alone on its line, its title (or «(تنسخ)») on the next: unless the next carries on a sentence.
        lone = LONE.match(line)
        if lone and not (pos + 1 < len(cleaned) and not CARRIES.match(cleaned[pos + 1][1])
                         and not (pos and LEADS.search(cleaned[pos - 1][1]))):
            lone = None
        if (lone and pos + 1 < len(cleaned) and not CARRIES.match(cleaned[pos + 1][1])
                and not (pos and LEADS.search(cleaned[pos - 1][1]))):
            line = f'المادة {lone.group(1)}{lone.group(2) or ""}.-'
        elif titled:
            titled = False
            if REPEALED.fullmatch(line):
                articles[-1].lines = [line]
                continue
            if (len(line) < 90 and not ENDS.search(adala.MARK.sub('', line)) and not OPENS.match(line)
                    and not ARTICLE.match(line) and not re.match(r'^(?:الكتاب|القسم|الجزء|الباب|الفرع)\s', line)):
                articles[-1].heading_path.append(line)
                continue
        m = ARTICLE.match(line)
        n = (1 if m.group(1) == 'الأولى' else int(m.group(1))) if m else None
        bis = m and m.group(0).split()[2:3] and re.search(r'المكررة|المكرر|مكررة|مكرر', m.group(0)[:40])
        if m and m.group(3) and REFERENCE.search(m.group(3)[:30]):
            m = None
        times = m.group(2) if m and bis else None
        number = (str(n) + (('-bis' if not times else BIS[times]) if bis else '')) if m else ''
        # A number not seen yet, up to three past the highest: the layer gives some headings out of the page's order
        # (art. 15's after art. 16's); the articles are put back in order at the end.
        if m and number not in used and n <= last + 3:
            label = line[:m.start(3)].rstrip(' .-–') if m.group(3) is not None else line.rstrip(' .-–')
            label = re.sub(r'\s*[.\-–]+\s*$', '', label)
            title = (m.group(3) or '').strip()
            # «المادة 98.- (تنسخ)»: a repealed article, its word its body (the mark goes with it).
            gone = REPEALED.match(title)
            art = sgg.SggArticle(label=label, number=number, page=index,
                                 heading_path=[heads[k] for k in sorted(heads)] + ([title] if title and not gone else []))
            if gone:
                art.lines = [gone.group(0).strip()]
            articles.append(art)
            used.add(number)
            last = max(last, n)
            titled = bool(lone) and not title
            continue
        d = sgg.DIVISION.match(line) or NUMBERED.match(line)
        if d and len(line) < 90 and not ENDS.search(line):
            level = {'الكتاب': 0, 'الجزء': 1, 'القسم': 2, 'الباب': 3, 'الفرع': 4}.get(line.split()[0], 5)
            heads = {k: v for k, v in heads.items() if k < level}
            heads[level] = line
            continue
        if not articles:
            continue
        body = articles[-1].lines
        if body and REPEALED.fullmatch(body[0]) and not adala.MARK.fullmatch(line):
            continue                                        # nothing follows a repeal but the next heading
        if body and adala.MARK.fullmatch(line):          # a mark on its own: it belongs to the words before it
            body[-1] = f'{body[-1]}{line}'
            continue
        if body and not ENDS.search(adala.MARK.sub('', body[-1])) and not OPENS.match(line):
            body[-1] = f'{body[-1]} {line}'
        else:
            body.append(line)
    rank = {'': 0, '-bis': 1, '-ter': 2, '-quater': 3, '-quinquies': 4, '-sexies': 5, '-septies': 6, '-octies': 7}
    articles.sort(key=lambda a: (int(re.match(r'\d+', a.number).group(0)), rank.get(a.number[len(re.match(r'\d+', a.number).group(0)):], 9)))
    return sgg.SggText(title='المدونة العامة للضرائب', as_of=None, first_issue=None, first_page=None, articles=articles,
                       stats=stats)


def _marks(lines: list, main: float) -> list:
    """A run that is only digits set small (7 pt in 12 pt text) is a footnote's mark: written ⟦n⟧ at the text's size,
    so the page keeps it beside its words and the mark is then taken out."""
    out = []
    for run in lines:
        ink = [(ch, s, b) for ch, s, b in run if not ch.isspace()]
        if ink and all(ch.isdigit() for ch, _, _ in ink) and max(s for _, s, _ in ink) < main * adala.MARK_SIZE:
            b = ink[0][2]
            run = [('⟦', main, b), *[(ch, main, b) for ch, _, _ in ink], ('⟧', main, b)]
        out.append(run)
    return out


# The layer's shapes put back: an amount's groups in visual order («000 40» for 40 000), a percent before its number
# («%10»), a list's mark turned («-1°», «I-.», «-61I»), the running head («126 المدونة العامة للضرائب»).
_RUNNING = re.compile(r'^(?:\d{1,4}\s+)?المدونة العامة للضرائب(?:\s+\d{1,4})?$')


def tidy(line: str) -> str:
    from apps.sources.services.issue import _SPACED, _unreverse
    line = _SPACED.sub(_unreverse, line)
    # «001 100» is 100 001: no amount starts with a group of «00».
    line = re.sub(r'(?<![\d.,])(00\d)\s(\d{1,3})(?![\d,])', lambda m: f'{m.group(2)} {m.group(1)}', line)
    line = re.sub(r'\)(\d[\d\s.,%]*)\(', r'(\1)', line)
    line = re.sub(r'\)(تنسخ|ينسخ|نسخت|ملغاة)\(', r'(\1)', line)
    line = re.sub(r'%\s?(\d+(?:[.,]\d+)?)', r'\1%', line)
    line = re.sub(r'(^|\s)-(\d{1,2})°', r'\1\2°-', line)
    line = re.sub(r'^([IVXΙ]+)\s*-\s*\.', r'\1.-', line)
    line = re.sub(r'^-\s*\.\s*([IVX]+)(?=\s)', r'\1.-', line)
    line = re.sub(r'-(\d{1,3})([IVX]+)\b', r'\1-\2', line)
    return line


# A footnote the layer set at the text's size, inside the body: «تم إدراج هذه الفقرة بمقتضى البند I من المادة 8 من قانون
# المالية لسنة 2018» (the body names a finance law by its number, «قانون المالية رقم 110.13», never «لسنة 2018»).
_NOTE_AR = re.compile(r'\s*(?:كما\s+)?تمت?\s+\S+[^\n]{0,200}?ب?مقتضى[^\n]{0,120}?قانون المالية(?:\s+المعدل)?\s+لسنة'
                      r'(?:\s*\.?\d{4})?(?:\s*وتغيير\S*[^\n]{0,120}?لسنة(?:\s*\.?\d{4})?)?\s*\.?')


def read(path: str) -> 'adala.AdalaText':
    """The edition read whole: its articles and its footnotes, each tied to the article that marks it."""
    pdf = pdfium.PdfDocument(path)
    try:
        pages = [adala._lines(pdf[i].get_textpage()) for i in range(len(pdf))]
    finally:
        pdf.close()
    main = adala._main_size(pages)
    split = []
    for lines in pages:
        body, foot = adala.split_page(_marks(lines, main), main)
        body = [ln for ln in adala._run_in(body) if not _CONTENTS.search(ln) and not _RUNNING.match(ln.strip())]
        # The code ends at art. 303; the finance laws' provisions the edition annexes («المقتضيات الجبائية …
        # المنصوص عليها في قوانين المالية») are other texts, already on the site from the BO.
        end = next((i for i, ln in enumerate(body) if _ANNEXES.match(ln.strip())), None)
        if end is not None:
            split.append((body[:end], foot))
            break
        split.append((body, foot))
    text = cut([body for body, _ in split])
    notes = {f.number: f for f in adala.footnotes([foot for _, foot in split])}
    for a in text.articles:
        for n in adala.MARK.findall('\n'.join(a.heading_path[-1:] + a.lines)):
            if int(n) in notes and not notes[int(n)].article:
                notes[int(n)].article = a.label
        a.lines = [line for line in (_NOTE_AR.sub('', adala.MARK.sub('', ln)).strip() for ln in a.lines)
                   if line and not adala.PUNCTUATION.match(line)]
        a.heading_path = [adala.MARK.sub('', h).strip() for h in a.heading_path]
    return adala.AdalaText(text=text, footnotes=list(notes.values()))


# «المادة 8 من قانون المالية رقم 60.24 للسنة المالية 2025», «Article 7 de la loi de finances n° 48-09 pour l'année
# budgétaire 2010»: each finance law a footnote names, with its article.
_LAW_AR = re.compile(r'(?:المادة|المواد)\s+([^\s]+(?:\s+(?:المكررة|مكرر))?)\s+من\s+قانون\s+المالية\s+(?:المعدل\s+)?(?:رقم\s+)?(\d{1,3}\s*[.\-]\s*\d{2})')
_LAW_FR = re.compile(r'[Aa]rticles?\s+([\w\- ]+?)\s+de\s+la\s+loi\s+de\s+finances\s+(?:rectificative\s+)?n°\s*(\d{1,3}\s*[.\-]\s*\d{2})')


def footnote_laws(text: str) -> list[dict]:
    """The finance laws (and their articles) a footnote names, in its order: [{'number': '60.24', 'article': '8'}]; the
    form «Articles 7 et 9 des lois de finances respectives n° 43-10 et n° 115-12» pairs them in order."""
    flat = re.sub(r'\s+', ' ', text)
    found = [{'article': m.group(1).strip(), 'number': re.sub(r'\s*[.\-]\s*', '.', m.group(2))}
             for m in [*_LAW_AR.finditer(flat), *_LAW_FR.finditer(flat)]]
    if not found and 'lois de finances' in flat:
        numbers = [re.sub(r'\s*[.\-]\s*', '.', n) for n in re.findall(r'n°\s*(\d{1,3}\s*-\s*\d{2})', flat)]
        arts = re.match(r'\s*[Aa]rticles?\s+([\w\s,\-]+?)\s+des\s+lois', flat)
        cited = [a for a in re.split(r'\s*(?:,|\bet\b)\s*', arts.group(1)) if a] if arts else []
        found = [{'article': cited[k] if k < len(cited) else '', 'number': n} for k, n in enumerate(numbers)]
    seen, out = set(), []
    for f in found:
        if f['number'] not in seen:
            seen.add(f['number'])
            out.append(f)
    return out


_NOTE = re.compile(r'^\s*(\d{1,4})\s+(\S.*)$')


def footnotes(pages: list[list[str]]) -> list:
    """The French edition's footnotes: a line opening with the next number and a space starts one («419 Article 9 de la
    loi de finances …»); any other line runs on the one before, across pages too."""
    out: list[adala.Footnote] = []
    for index, lines in enumerate(pages):
        for ln in lines:
            m = _NOTE.match(ln)
            n = int(m.group(1)) if m else None
            if n is not None and (not out or 0 < n - out[-1].number <= 6):
                out.append(adala.Footnote(number=n, page=index, text=m.group(2).strip()))
            elif out and ln.strip():
                out[-1].text += ' ' + ln.strip()
    return out


# The running head the layer leaves among the words: «7 CODE GÉNÉRAL DES IMPÔTS» (the page's number, the code's name).
_FR_RUNNING = re.compile(r'\s*\b\d{1,3}\s+CODE GÉNÉRAL DES IMPÔTS\b\s*|\s*\bCODE GÉNÉRAL DES IMPÔTS\s+\d{1,3}\b\s*')
_FR_DIVISION = re.compile(r'\s+(?:LIVRE|TITRE|CHAPITRE|Chapitre|Section|Sous-section|PARTIE|Première partie|Deuxième partie|'
                          r'PREMIERE PARTIE|DEUXIEME PARTIE|TROISIEME PARTIE)'
                          r'\s+(?:[IVX]+\b|PREMIER|premier|unique|UNIQUE)(?![^\n]{0,3}(?:ci-dessus|ci-dessous|du présent|de la présente))')


def read_french(path: str) -> tuple[list[dict], list]:
    """The French edition: its articles cut at their «Article N.-» headings (translations/services/adala_fr.py's
    reader, which knows Word's pages), and its footnotes, each tied to the article whose words carry its mark."""
    from apps.translations.services import adala_fr

    pdf = pdfium.PdfDocument(path)
    try:
        pages = [adala._lines(pdf[i].get_textpage()) for i in range(len(pdf))]
    finally:
        pdf.close()
    main = adala._main_size(pages)
    # The preface names «Article 5 de la loi de finances» before the code's own «Article premier».
    articles = adala_fr.read(path, start='Article premier.-')
    for a in articles:
        # The divisions printed before the next article stay with this one's words: they are headings, not its text.
        body = _FR_RUNNING.sub(lambda m: '\n' if '\n' in m.group(0) else ' ', a['body'])
        body = _FR_DIVISION.split(body, maxsplit=1)[0].strip()
        # «(abrogé) IV.- REGIME DE L’AUTO-ENTREPRENEUR»: a repealed article, then the heading of the ones after it.
        a['body'] = '(abrogé)' if body.startswith('(abrogé)') and len(body) < 200 else re.sub(r'[ \t]{2,}', ' ', body)
    # The marks each article carries, page by page: an article's first page and those up to the next one's.
    starts = [a['page'] for a in articles]
    feet, owner = [], {}
    for index, page in enumerate(pages):
        body, foot = adala.split_page(page, main)
        feet.append(foot)
        k = max((j for j, p in enumerate(starts) if p <= index + 1), default=None)
        for line in body:
            for n in adala.MARK.findall(line):
                if k is not None:
                    owner.setdefault(int(n), k)
    notes = footnotes(feet)
    for f in notes:
        if f.number in owner:
            f.article = articles[owner[f.number]]['number']
    return articles, notes
