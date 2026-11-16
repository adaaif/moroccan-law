"""An issue's lines and where each of its texts starts: the running heads left out, a contents entry found again in
the pages by its number, or by its kind and its title's own words."""
import re

from apps.corpus.services.issue_structure.toc import _before_1956
from apps.sources.models import Issue


_HEADER = re.compile(r'الجريدة الرسمية')
_MARKS = re.compile(r'^#{1,6}\s+|^\*\*|\*\*$')
_DECOR = re.compile(r'^[\s*ـ_\-–—.•]*$')


def running_head(line: str, number: int) -> bool:
    """A line that is the running head or a piece of it, wherever the reading put it: a column read alone can bring
    it mid-page, cut in two («عدد 5932 - 3 جمادى الأولى 1432 (7 أبريل 2011)», then «الجريدة الرسمية»; 31.08 held
    nine of them in its articles, 24 Oct 2026). Nothing is left once the paper's name, the issue's number, its two
    dates and the folio are taken out; a sentence citing the issue keeps its other words."""
    if not (re.search(rf'عدد\s*{number}(?!\d)', line) or re.fullmatch(r'[\d\s|]*الجريدة الرسمية[\d\s|]*', line)):
        return False
    rest = re.sub(r'الجريدة|الرسمية', ' ', line)            # the name read in part («… (7 أبريل 2011) الرسمية»)
    rest = re.sub(rf'عدد\s*{number}(?:\s*مكرر)?', ' ', rest)
    rest = re.sub(r'\([^()]*\d{4}\s*\)', ' ', rest)                                   # (7 أبريل 2011)
    rest = re.sub(r'\d{1,2}\s+[\u0621-\u064a]+(?:\s+[\u0621-\u064a]+)?\s+\d{4}', ' ', rest)   # 3 جمادى الأولى 1432
    return not re.sub(r'[\d\s\-–—|.:،,]+', '', rest)


def issue_lines(issue: Issue) -> list[tuple[int, str]]:
    """Every line of the issue with its printed page; running headers and rules left out."""
    out = []
    for page in issue.document.pages.order_by('index'):
        # The OCR sometimes marks headings as Markdown («## المادة 38», «**المادة 38**»): the marks go.
        lines = [_MARKS.sub('', line.strip()).strip() for line in page.text.splitlines()]
        lines = [line for n, line in enumerate(lines) if line and not (n < 3 and _HEADER.search(line)
                 and str(issue.number) in line) and not running_head(line, issue.number) and not _DECOR.match(line)]
        out.extend((page.printed_number, line) for line in lines)
    return out


_KINDS = {'ظهير', 'مرسوم', 'قرار', 'قانون', 'مقرر', 'منشور', 'دورية', 'اتفاقية', 'قرار مشترك', 'أمر'}


_TATWEEL = '\u0640'
# Words a title's search leaves out: too common to tell one text from the next.
_PLAIN = {'في', 'من', 'على', 'إلى', 'الى', 'عن', 'بشأن', 'بتاريخ', 'صادر', 'الصادر', 'رقم', 'المتعلق', 'يتعلق', 'و',
          'بتغيير', 'بتتميم', 'شريف', 'الشريف', 'لوزير', 'للوزير', 'وزير'}


def _words(text: str) -> list[str]:
    from apps.sources.services.compare import fold
    return [w for w in fold(text.replace(_TATWEEL, '')).split() if len(w) > 2 and w not in _PLAIN and not w.isdigit()]


def _digits(text: str) -> str:
    """A number's parts joined by a dot, whatever printed them: «588-67», «2/64/083» and «64. 667» are «588.67»,
    «2.64.083» and «64.667»."""
    return re.sub(r'(?<=\d)\s*[.\-/]\s*(?=\d)', '.', text)


# An old issue's contents: «فهرست» on its first page, the titles listed bare (no page, no dots: BO 150 of 1916, BO 479 of
# 1922), until the first text's «الحمد لله وحده».
_CONTENTS_HEAD = re.compile(r'^\s*(?:فهرست|فهرس|الفهرس|فهرسة)\s*$')
_BODY_OPENS = re.compile(r'^\s*الحمد\s+لله')


def contents_block(lines: list[tuple[int, str]]) -> tuple[int, int]:
    """(the contents' first line, the body's first «الحمد لله») of an old issue whose contents list bare titles, or
    (0, 0): its first two pages at most."""
    head = next((n for n, (_, text) in enumerate(lines[:80]) if _CONTENTS_HEAD.match(text)), None)
    if head is None:
        return 0, 0
    pages = {lines[head][0], (lines[head][0] or 0) + 1}
    for n in range(head + 1, len(lines)):
        if lines[n][0] not in pages:
            return 0, 0
        if _BODY_OPENS.match(lines[n][1]):
            return head, n
    return 0, 0


def _start_of(lines: list[tuple[int, str]], entry: dict, after: int,
              contents: tuple[int, int] = (0, 0)) -> int | None:
    """The line where a contents entry's text begins: its first «… رقم N» (or «عدد 2026/ق/120», the Competition
    Council's) named again, on or after its page. A long title wraps, so a line is read with the one after it.
    Elongations are ignored («قـرار» is «قرار»: the 1956–2018 scans' readings keep them). An entry without a number
    (a dahir before 1957, the 1960s ministers' orders «قرار لوزير الفلاحة بتاريخ 4 مارس 1964») is found by its kind
    and most of its title's own words (the Bulletin-to-1956 review: 103 of 103 such entries were missed)."""
    title = entry['title'].replace(_TATWEEL, '')
    m = re.search(r'(?:رقم|عدد)\s+([^\s،,]*\d[^\s،,]*)', title)
    number, kind = (m.group(1).rstrip('.') if m else ''), (title.split() or [''])[0]
    if not number and entry.get('number_as_printed'):
        # A title the contents give without «رقم» names its number apart (BO 3240: «الاتفاقية المبرمة …», printed
        # «ظهير شريف رقم 1.74.414 … بنشر الاتفاقية»); not printed there, the title's words find it as before (BO 6419's
        # convention, published by a dahir named apart).
        apart = next((n for n in re.findall(r'\d[\d.\-]*\d', entry['number_as_printed'])
                      if sum(c.isdigit() for c in n) >= 4), '')
        if apart and (found := _start_of(lines, {**entry, 'title': f'{title} رقم {apart}', 'number_as_printed': ''},
                                         after, contents)) is not None:
            return found
        return _start_of(lines, {**entry, 'number_as_printed': ''}, after, contents)
    # The entry's first word is its kind («ظهير», «مرسوم»…) when the model kept it; a title it cut short
    # («رقم 2.22.729 …») is found by its number alone; a general text with neither, by its title's words (the 1958
    # Royal Charter, «العهد الملكي الذي أعلن عنه صاحب الجلالة …», 31 Oct 2026).
    typed = kind in _KINDS
    if not number and not typed and (entry.get('section') != 'general' or len(_words(title)) < 5):
        return None
    wanted = _words(title)[:8] if not number else []
    if not number and len(wanted) < 3:
        return None
    # Two titles may share their first words («قرار وزيري في الاعلان أنه من المصلحة العمومية انشاء …» and «… احداث …»,
    # BO 2154): of the headings that pass, the one with most of the whole title's words wins.
    whole, passed = set(_words(title)), []
    for n in range(after, len(lines)):
        if passed and (len(passed) == 6 or n > passed[0][1] + 600):
            break
        page, line = lines[n]
        line = line.replace(_TATWEEL, '')
        # A short notice reads «بموجب مقرر … رقم 1704.26 …»: the kind comes after «بموجب».
        opening = re.sub(r'^(?:بموجب|بمقتضى)\s+', '', line)
        # A page early: the contents' page numbers slip by one now and then (BO 7549). A line of the contents
        # itself (dot leaders, a page number) is never the text.
        if page is None or page < entry['page'] - 1 or (typed and not opening.startswith(kind)) \
                or re.search(r'[.…]{5,}\s*\d*\s*$', line):
            continue
        if number:
            # A scan's reading may give a number's parts in visual order: «86.563» for the contents' «563.86» (BO
            # 3844, 1986).
            # A wrapped title goes on on the next line («… رقم 1524.26»); the next text's own heading never does.
            # Parts are joined by a dot, a dash or a slash, with a space now and then: the contents' «588-67» is
            # printed «588.67» (BO 2984), their «667.64» reversed with a space, «64. 667» (BO 3565).
            nxt = lines[n + 1][1].replace(_TATWEEL, '') if n + 1 < len(lines) else ''
            joined = line + ' ' + ('' if (nxt.split() or [''])[0] in _KINDS else nxt)
            plain = _digits(number)
            # As printed too: a number the contents cut short («2009- 733» listed «2009-», BO 5707).
            if any(form in joined for form in (number, '.'.join(reversed(number.split('.'))))) or \
                    any(form in _digits(joined) for form in (plain, '.'.join(reversed(plain.split('.'))))):
                return n
        else:
            # The heading itself names some of the title, the lines that go on from it the rest (never the next
            # text's heading).
            following = []
            for k in range(n + 1, min(n + 3, len(lines))):
                nxt = lines[k][1].replace(_TATWEEL, '')
                if (nxt.split() or [''])[0] in _KINDS:
                    break
                following.append(nxt)
            # Before 1956 the kind is printed alone, centred («ظهير شريف», «قرار وزيري»), its subject on the line under
            # it: that line is the heading's own (the Bulletin-from-No.-1 review's pilot found 76 of 152 such texts).
            heading = f'{line} {following[0]}' if len(line.split()) <= 3 and following else line
            # A bare title of the contents is never the text: there only the first text's heading stands, just over
            # the body's first «الحمد لله».
            if contents[0] <= n < contents[1] - 4:
                continue
            own, words = set(_words(heading)), set(_words(line + ' ' + ' '.join(following)))
            if sum(1 for w in wanted if w in own) >= 2 and sum(1 for w in wanted if w in words) >= 0.6 * len(wanted):
                more = set(_words(' '.join(text for _, text in lines[n:n + 4])))
                passed.append((len(whole & more), n))
    if passed:
        return max(passed, key=lambda p: (p[0], -p[1]))[1]
    return None


def segment_issue(issue: Issue, toc: list[dict]) -> list[tuple[int, int] | None]:
    """Each contents entry's lines: from its own title line to the next text's."""
    lines = issue_lines(issue)
    # Searched in page order: a table of contents may list texts out of it (BO 7154 bis lists decrees from its
    # last pages before the finance law on its first), and each search starts after the text before.
    starts, after = [None] * len(toc), 0
    taken: set[int] = set()
    contents = contents_block(lines) if _before_1956(issue) else (0, 0)
    for i in sorted(range(len(toc)), key=lambda i: (toc[i]['page'], i)):
        n = _start_of(lines, toc[i], after, contents)
        if n is None:            # a text found too far on (a citation read as a title) must not hide the ones before
            first = next((k for k, (page, _) in enumerate(lines) if page is not None and page >= toc[i]['page'] - 1),
                         len(lines))
            n = _start_of(lines, toc[i], first, contents)
            n = None if n in taken else n
        starts[i] = n
        if n is not None:
            taken.add(n)
            after = max(after, n + 1)
    found = [n for n in starts if n is not None] + [len(lines)]
    return [None if n is None else (n, min(m for m in found if m > n)) for n in starts]
