"""A text's lines into its articles: «المادة» (or «الفصل») headings taken in order, with their divisions, subjects and
pages; a law of one article; and a text whose words are one piece."""
import re

from apps.corpus.services.issue_structure.printed import article_number
from apps.sources.services.compare import fold


_ARTICLE_WORDS = ('المادة', 'الفصل')
_DIVISION = re.compile(r'^(?:الكتاب|القسم|الباب|الفرع|الجزء|الفصل|الفقرة)\s+\S+(?:\s+\S+){0,3}$')
_TAIL = re.compile(r'^(?:وحرر|حرر|صدر|ملحق|الملحق|جدول|الجدول)\b')


def _article_head(line: str, word: str) -> tuple[str, str] | None:
    """«المادة 3» or «المادة 3. - النص…» → (label, the body's first words). Never a quoted («…) article, nor a
    table's «المادة "8"». Tatweel is ignored («المــادة»)."""
    line = line.replace('\u0640', '')
    flipped = re.match(rf'^(\d+(?:\s+(?:مكرر|المكررة?))?)\s+{word}\s*[.:]?$', line)
    if flipped:                       # «7 المادة»: a scan read left to right
        line = f'{word} {flipped.group(1)}'
    if not line.startswith(word + ' '):
        return None
    m = re.match(rf'^({word}\s+[^.\-–:]+?)\s*\.\s*[-–]\s*(.*)$', line)
    head, rest = (m.group(1).strip(), m.group(2).strip()) if m else (line.rstrip(' .:'), '')
    if (not m and len(line.split()) > 5) or '"' in head or '«' in head:
        return None
    return head, rest


def _follows(number: str, previous: str | None) -> bool:
    """Articles run in order: the first is 1; then the next or the one after (a heading the OCR lost), or a «مكرر»
    of the last. A quoted article whose « was lost (an amending law's «المادة 82») is not taken for the next."""
    if previous is None:
        return number in ('1', '')
    base = previous.split('-')[0]
    if not number or not base.isdigit():
        return True
    head = number.split('-')[0]
    return (head.isdigit() and int(base) < int(head) <= int(base) + 2) or (head == base and number != previous)


def _is_subject(line: str) -> bool:
    words = line.split()
    # A table's last row («| 1000 | 2857 يوما فما فوق |») is the end of the article above, never the next one's subject.
    return (0 < len(words) <= 12 and not line.startswith(('«', '"', '-', '•', '*', '|')) and _ARTICLE_WORDS[0] not in line
            and words[0] not in ('أو', 'و', 'ثم', 'أن', 'التي', 'الذي', 'من', 'في', 'على')   # a sentence's tail
            and not re.search(r'[.؛;:،,»]\s*$', line) and not re.match(r'^[IVX]+\s*[-.]', line)
            and bool(re.search(r'[\u0621-\u064A]{3}', line)))


def _resumes(number: str, previous: str | None, after: list[str]) -> bool:
    """Headings the OCR lost (2016: «المادة 4» and «5» sat on table pages): a jump of up to five is taken when the
    next two headings carry on from it (6, 7, 8). Quoted articles rarely come three in a row unquoted."""
    if previous is None or not number.isdigit() or not previous.split('-')[0].isdigit():
        return False
    n, p = int(number), int(previous.split('-')[0])
    return p < n <= p + 5 and [a.split('-')[0] for a in after] == [str(n + 1), str(n + 2)]


def split_articles(lines: list[tuple[int, str]]) -> dict:
    """The text's lines → its front (dahir, title), articles with their divisions and page, and its tail
    (signatures, annexes). Articles are «المادة» headings; «الفصل» when the text has no «المادة»."""
    word = 'المادة' if any(_article_head(line, 'المادة') for _, line in lines) else 'الفصل'
    candidates = [(n, article_number(head[0])) for n, (_, line) in enumerate(lines)
                  if (head := _article_head(line, word))]
    heads, previous = set(), None
    for k, (n, number) in enumerate(candidates):
        if _follows(number, previous) or _resumes(number, previous, [c[1] for c in candidates[k + 1:k + 3]]):
            heads.add(n)
            previous = number
    last = max(heads) if heads else len(lines)   # signatures and annexes only come after the last article
    front, articles, tail, path = [], [], [], {}
    n, last_body = 0, -1      # last_body: the last line that went into an article's body
    while n < len(lines):
        page, line = lines[n]
        head = _article_head(line, word) if n in heads else None
        if head and not tail:
            # A short unpunctuated line just above the heading is the article's subject («إحداث مناصب مالية»),
            # not the end of the article before it.
            before = articles[-1]['lines'] if articles and last_body == n - 1 else []
            subject = before.pop() if before and _is_subject(before[-1]) else ''
            articles.append({'label': head[0], 'page': page,
                             'heading_path': list(path.values()) + ([subject] if subject else []),
                             'lines': [head[1]] if head[1] else []})
        elif articles and not tail and _DIVISION.match(line.replace('\u0640', '')) and not line.startswith(word):
            title = line
            if n + 1 < len(lines) and len(lines[n + 1][1].split()) <= 12 and not _article_head(lines[n + 1][1], word) \
                    and not _DIVISION.match(lines[n + 1][1]):
                title, n = f'{line}: {lines[n + 1][1]}', n + 1
            level = line.split()[0]
            keys = list(path)
            path = {k: path[k] for k in keys[:keys.index(level)]} if level in path else path
            path[level] = title
        elif not articles and _DIVISION.match(line) and not line.startswith(word):
            path[line.split()[0]] = line          # a division before the first article opens it
            if n + 1 < len(lines) and len(lines[n + 1][1].split()) <= 12 and not _article_head(lines[n + 1][1], word):
                path[line.split()[0]], n = f'{line}: {lines[n + 1][1]}', n + 1
        elif articles and (tail or (n > last and _TAIL.match(line))):
            tail.append(line)
        elif articles:
            articles[-1]['lines'].append(line)
            last_body = n
        else:
            front.append(line)
        n += 1
    for article in articles:
        article['body'] = '\n'.join(article.pop('lines')).strip()
    if not articles:
        return single_article(lines)
    return {'front': '\n'.join(front), 'articles': articles, 'tail': '\n'.join(tail)}


def single_article(lines: list[tuple[int, str]]) -> dict:
    """A law of one article («مادة فريدة»: most approve a convention) has no «المادة» heading: its one article runs
    from that line to the signatures."""
    at = next((n for n, (_, line) in enumerate(lines) if _SINGLE.match(line.strip())), None)
    if at is None:
        return {'front': '\n'.join(line for _, line in lines), 'articles': [], 'tail': ''}
    body, tail = [], []
    rest = _SINGLE.match(lines[at][1].strip()).group(1)
    for _, line in lines[at + 1:]:
        if tail or _TAIL.match(line):
            tail.append(line)
        else:
            body.append(line)
    return {'front': '\n'.join(line for _, line in lines[:at]),
            'articles': [{'label': 'مادة فريدة', 'page': lines[at][0], 'heading_path': [],
                          'body': '\n'.join(([rest] if rest else []) + body).strip()}],
            'tail': '\n'.join(tail)}


# Texts whose words are one piece whatever «المادة» lines they hold: an opinion or a report (they quote the bill they
# weigh: the CESE's opinion on 97.15 was cut into the bill's 49 articles), a Constitutional Court decision (it quotes
# the law it rules on) and a corrigendum (it quotes the words it puts right: «بدلا من: … يقرأ: …»).
_ONE_PIECE = re.compile(r'^(?:رأي|التقرير|تقرير|استدراك)\s|^قرار\b.*المحكمة الدستورية|\bم\.د\b')
# Where a decision's words end and its signatures begin («وصدر بمقر المحكمة الدستورية…», «الإمضاءات :»).
_END = re.compile(r'^(?:وحرر|حرر|صدر|وصدر|الإمضاءات|ملحق|الملحق|ملاحق|جدول|الجدول)\b')
_NUMBERED = re.compile(r'\bرقم\s+[\d.]+\d\s+صادر\s+في')
# The lines between two texts: their section, and the authority the next one is printed under.
_BETWEEN = re.compile(r'^(?:نصوص عامة|نصوص خاصة|إعلانات وبلاغات|وزارة|الأمانة العامة للحكومة)')


def _opening(line: str) -> str:
    """A heading's words before its number: «قرار», «بموجب مقرر للامين العام» (folded)."""
    words = fold(line).split()
    return ' '.join(words[:min(words.index('رقم') if 'رقم' in words else 4, 4)])


def one_piece(title: str, number: str = '') -> bool:
    """(Not a law about the court: «القانون التنظيمي رقم 066.13 المتعلق بالمحكمة الدستورية» has articles.)"""
    return bool(_ONE_PIECE.search(title or '') or 'م.د' in (number or ''))


def whole_text(item: dict, data: dict, rubrics: set[str]) -> dict:
    """A text with no article of its own (a Constitutional Court decision, an architect's licence) or whose «المادة»
    lines quote another text (an opinion): its words as one article with no label, as printed from after its heading
    to its signatures, visas included (the version then keeps no preamble of its own). Until 20 Oct 2026 such a text
    kept its title alone (2,763 of them), or another text's articles."""
    lines = item.get('front', '').splitlines()
    for a in item['articles']:
        lines += [a['label']] + a['body'].splitlines()
    lines = [line for line in lines + item.get('tail', '').splitlines() if line.strip()]
    titles = [fold(t) for t in (data.get('title', ''), item['toc'].get('title', '')) if t]
    # The heading: a line that opens as the title does, among the first (a running header the page cut may come
    # before it: «المجلس الأعلى للاتصـ», BO 6739 bis), then the lines it wraps over.
    start = next((k + 1 for k in range(min(4, len(lines)))
                  if len(head := fold(lines[k])[:30]) >= 20 and any(t.startswith(head) for t in titles)), 0)
    opening = _opening(lines[max(start - 1, 0)]) if lines else ''
    while start < len(lines) and len(fold(lines[start])) > 3 and any(fold(lines[start]) in t for t in titles):
        start += 1
    # It ends at its signatures, or where a line opens as its own heading did with another number: the next text of
    # the same kind, which the contents missed («بموجب مقرر للأمين العام للحكومة رقم 2407.20 صادر في…»).
    end = next((n for n in range(start + 1, len(lines)) if _END.match(lines[n].strip())
                or (opening and _opening(lines[n]) == opening and _NUMBERED.search(lines[n]))), len(lines))
    body = lines[start:end]
    while body and (_BETWEEN.match(body[-1].strip()) or body[-1].strip(' .') in rubrics):
        body.pop()
    if not body:
        return item
    return {**item, 'front': '\n'.join(lines[:start]), 'tail': '\n'.join(lines[end:]),
            'articles': [{'label': '', 'page': item['pages'][0], 'heading_path': [], 'body': '\n'.join(body)}]}


_SINGLE = re.compile(r'^(?:مادة فريدة|مادة وحيدة)\s*[.:]?\s*(?:[-–]\s*(.*))?$')
