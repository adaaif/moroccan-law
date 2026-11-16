"""What the reading model wrote about its own work, taken out of what readers see (FX5 of the mended-Bulletin review,
2 Nov 2026). The model sometimes talks: «Note: the table below is transcribed as printed», «Let me transcribe
carefully.», «(title logo, rendered as text)», «ولم أستطع قراءتها». About 1,050 Arabic page readings and 383 published
articles carried such lines. Three kinds:

- a remark on method (how it read: columns, order, the masthead) goes;
- a remark that something was not read («the remaining rows are not legible», «تعذر قراءة …») becomes «[…]», so the
  reader still sees that words are missing;
- a retry («Let me restart the transcription», «Corrected full transcription:») goes with the failed attempt above it,
  block by block, as long as each block's words come again after the retry; a block the retry does not repeat stays.

Descriptions of a figure («[Chart: …]», «[Map: …]») and markers of a signature or a stamp are left as they are: they
stand for something printed. `strip` is idempotent; `found` counts what `strip` would take out, for `data_health`."""
import difflib
import re
from collections import Counter
from itertools import pairwise

# Words that say the text was not (fully) read: such a remark becomes «[…]».
_OMITTED = re.compile(
    r'(?i)(?:illegib|unreadable|not (?:fully |reliably |clearly )?(?:legible|readable|transcribed|read)|could not|cannot|'
    r'can\'t|unable|remaining (?:rows|entries|lines|text)|partial|incomplete|omitted|stopped|cut off|missing|faint|'
    r'غير مقروء|غير واضح|تعذر|يتعذر|لم تُنقل|لم تنقل|لم يُنقل|لم ينقل|لم أستطع|لم أتمكن|المتبقية|الباقية|جزئي)')

_META = (r'(?:transcri\w*|render\w*|illegib\w*|legib\w*|unreadable|unclear|stylized|calligraph\w*|logo|masthead|rotated|'
         r'reading order|right[- ]to[- ]left|left[- ]to[- ]right|best[- ]effort|reproduced|as printed|'
         r'the (?:page|image|scan|table|column|row|text) (?:above|below|is|was|has|shows|appears|continues|follows)|'
         r'continues|follows|faint|blurr\w*|cut off|cropped)')
_AR_META = (r'(?:غير مقروء|غير مقروءة|غير واضح|غير واضحة|يتعذر|تعذرت|تعذر|لم أستطع|لم أتمكن|نقلتها|نقلته|نُقل|يُنقل|'
            r'كما يظهر|القراءة من)')
# A described figure or a printed mark: kept.
_FIGURE = re.compile(r'^[ \t]*[\[(][ \t]*(?:Chart|Diagram|Figure|Map|Graph|Image|Photo|Picture|Signature|Stamp|Seal|'
                     r'خريطة|رسم|صورة|شكل|توقيع|طابع|خاتم)\b')

# A retry: the model gave up on what it had written and starts again.
_RETRY = re.compile(
    r'(?i)(?:text above was an error|restart(?:ing)? the transcription|(?:full|correct(?:ed)?) transcription follows|'
    r'corrected (?:full |complete )?transcription|corrected (?:version|table)|transcription of this column follows|'
    r'the transcription above contains|above is malformed|table above is (?:malformed|incomplete|wrong)|'
    r'let me (?:correct|redo|restart|give the correct|start over|try again|re-?transcribe|transcribe (?:it )?(?:carefully|properly|again))|'
    r'^\W*(?:final|full|complete|revised) (?:transcription|table)\b|^\W*wait\b|^\W*correction\b)')

_LINES = [
    ('note', re.compile(r'^[ \t>*_]*[\[(]?[ \t*_]*(?:Note|NOTE|N\.B\.)[ \t]*:[ \t]*(?:the|The|this|This|I\b|a |A |an |An |'
                        r'transcri|table|Table|page|Page|column|Column|row|text|Text|left|right|it |It )[^\n]*$', re.M)),
    ('chatter', re.compile(r'^[ \t>*_]*(?:Let me\b|Let\'s\b|I will\b|I\'ll\b|I cannot\b|I can\'t\b|I could\b|I transcribe\b|'
                           r'Wait,|Correction\b[^\n]{0,40}(?::|below|follows)|(?:Final|Corrected|Full|Complete|Revised)(?: full| complete)? '
                           r'(?:transcription|table|version)\b|Transcription (?:of|continues|follows)\b|'
                           r'This (?:page|is a|table|image)\b|The page (?:appears|is|has|contains|shows|seems)\b|'
                           r'Here is\b|Below is\b|Continuing\b|Continued (?:from|on)\b)[^\n]*$', re.M)),
    ('bracket', re.compile(r'^[ \t>*_]*[\[(][ \t]*(?=[^\])\n]*\b' + _META + r')[A-Z][^\])\n]*[\])][ \t*_]*$', re.M)),
    ('ar-note', re.compile(r'^[ \t>*_]*[\[(]?[ \t]*ملاحظة[ \t]*:?(?=[^\n]*' + _AR_META + r')[^\n]*$', re.M)),
    ('ar-bracket', re.compile(r'^[ \t>*_]*[\[(][ \t]*(?=[^\])\n]*' + _AR_META + r')[^\])\n]{0,300}[\])][ \t*_]*$', re.M)),
]
_INLINE = [
    ('illegible', re.compile(r'[\[(][ \t]*(?:illegible|unreadable|unclear|غير مقروء|غير مقروءة|غير واضح|غير واضحة)'
                             r'[^\])\n]{0,80}[\])]', re.I), '[…]'),
    ('aside', re.compile(r'[ \t]*\((?=[^)\n]{0,240}\b(?:render\w*|transcri\w*|stylized|calligraph\w*|logo|illegib\w*|'
                         r'legib\w*)\b)[^)\n]{0,240}\)'), None),
    ('ar-aside', re.compile(r'[ \t]*\((?=[^)\n]{0,240}(?:يُنقل|ينقل كما|كما يظهر|نقلتها|نُقل هنا|لم أستطع|تعذرت قراءة|'
                            r'يتعذر قراءة))[^)\n]{0,240}\)'), None),
]
_LOGO = re.compile(r'\[[ \t]*(?:[Tt]he )?(?:[Mm]asthead |[Tt]itle )?(?:logo|Logo|LOGO|graphic)[ \t]*:[ \t]*'
                   r'([^\]\n]{1,160}?)(?:[ \t]*—[^\]\n]*)?\]')
_MARK = '[…]'
_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي'})
_WORD = re.compile(r'[0-9A-Za-zء-ي]+')


def _pairs(text: str) -> set[tuple[str, str]]:
    words = [w.translate(_FOLD).lower() for w in _WORD.findall(text)]
    return set(pairwise(words))


def _cut_retries(text: str, counts: Counter) -> str:
    """Each retry line goes, with the failed attempt just above it: the blocks the retry starts again with. The cut
    grows upward from the retry one block at a time while the text after the retry opens with it; the first block it
    does not open with stays. A block repeated only by formula (each land notice's «وصرح طالب التسجيل …», the same
    deeds under three notices of one applicant) is not where the retry starts, so it stays."""
    for _ in range(20):                     # a page holds a handful of retries at most
        line = next((m for m in re.finditer(r'^[^\n]*$', text, re.M) if m.group(0).strip()
                     and _RETRY.search(m.group(0)) and _is_remark(m.group(0))), None)
        if line is None:
            return text
        before, after = text[:line.start()], text[line.end():]
        blocks = re.split(r'(\n[ \t]*\n)', before)    # blocks and the blank lines between them
        keep = len(blocks)          # blocks[keep:] go
        k = len(blocks)
        while k > 0:
            k -= 1
            if not _WORD.search(blocks[k]):
                continue            # a blank line or a table rule goes with what is around it
            if not _starts(''.join(blocks[k:]), after):
                break
            keep = k
        if _WORD.search(''.join(blocks[keep:])):
            counts['retry'] += 1
        else:
            counts['retry-unsure'] += 1     # nothing the retry starts again with: the attempt, if any, stays
        text = ''.join(blocks[:keep]).rstrip() + '\n\n' + after.lstrip('\n')
        counts['retry-line'] += 1
    return text


def _words(text: str) -> list[str]:
    return [w.translate(_FOLD).lower() for w in _WORD.findall(text)]


def _starts(cut: str, after: str) -> bool:
    """Whether `after` starts again with `cut`. Prose: the cut's first words open `after` (a match that begins at its
    first or second word), and half its words or more come again in order within its length and a half. A table: six
    in ten of its numbers come again among the next table's first cells (a retry often mends a row's order)."""
    words, again = _words(cut), _words(after)
    if not words:
        return True
    if all(not ln.strip() or ln.lstrip().startswith('|') for ln in cut.strip().splitlines()):
        numbers = [w for w in words if any(c.isdigit() for c in w)]
        if len(numbers) >= 3:
            pool = {w for w in again[:len(words) * 2 + 20] if any(c.isdigit() for c in w)}
            return sum(n in pool for n in numbers) * 10 >= len(numbers) * 6
    head = difflib.SequenceMatcher(None, words[:12], again[:18], autojunk=False).get_matching_blocks()
    if not any(b.a <= 2 and b.b <= 5 and b.size >= min(2, len(words)) for b in head):
        return False
    window = again[:len(words) * 3 // 2 + 10]
    matched = sum(b.size for b in difflib.SequenceMatcher(None, words, window, autojunk=False).get_matching_blocks())
    return matched * 2 >= len(words)


def _is_remark(line: str) -> bool:
    return any(rx.fullmatch(line) for _, rx in _LINES)


def _line(match: re.Match, counts: Counter, name: str) -> str:
    line = match.group(0)
    if _FIGURE.match(line):
        return line
    counts[name] += 1
    return _MARK if _OMITTED.search(line) else ''


def strip(text: str, counts: Counter | None = None) -> str:
    """The reading without the model's remarks (see the module's docstring). `counts`, when given, is told what went."""
    if not text:
        return text
    counts = Counter() if counts is None else counts
    text = _cut_retries(text, counts)
    text = _LOGO.sub(lambda m: counts.update(['logo']) or m.group(1), text)    # the masthead's words stay
    for name, rx in _LINES:
        text = rx.sub(lambda m, n=name: _line(m, counts, n), text)
    for name, rx, rep in _INLINE:
        def swap(m, n=name, r=rep):
            counts[n] += 1
            if r is None:
                return ' ' + _MARK if _OMITTED.search(m.group(0)) else ''
            return m.expand(r)
        text = rx.sub(swap, text)
    text = re.sub(r'(?:\[…\][ \t]*\n?[ \t]*){2,}', _MARK + '\n', text)    # one mark for marks in a row
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def found(text: str) -> Counter:
    """What `strip` would take out of `text`, by kind; empty for a clean reading."""
    counts = Counter()
    strip(text, counts)
    return counts
