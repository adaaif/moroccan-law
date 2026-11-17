"""What a reader typed, read as words: folded stems without the letters Arabic writes on a word's front, the kind of
text it names, a Gregorian day, and the two spellings the citation reader does not know written as it knows them
(`spelled`)."""
import re
from datetime import date

import ma_law


# Words that name no text by themselves, folded as `ma_law.fold` leaves them.
_STOP = {'قانون', 'مدونه', 'ظهير', 'شريف', 'رقم', 'متعلق', 'يتعلق', 'في', 'من', 'علي', 'عن', 'شان', 'بشان', 'loi', 'code', 'dahir',
         'le', 'la', 'les', 'du', 'de', 'des', 'sur', 'relatif', 'relative', 'au', 'aux', 'd', 'l', 'n', 'no', 'portant', 'و',
         'جديد', 'مغربي', 'مغرب', 'marocain', 'marocaine', 'maroc', 'nouveau', 'nouvelle',
         # an issue's words: the browser reads issues from its map
         'عدد', 'مكرر', 'جريده', 'رسميه', 'ص', 'صفحه', 'bis', 'ter', 'bo', 'bulletin', 'officiel', 'page', 'p'}
_KINDS = [('dahir', re.compile(r'(?:^| )(?:ال)?ظهير(?: |$)|(?:^| )dahir(?: |$)')),
          ('law', re.compile(r'(?:^| )(?:ال)?قانون(?: |$)|(?:^| )loi(?: |$)')),
          ('decree', re.compile(r'(?:^| )(?:ال)?مرسوم(?: |$)|(?:^| )decret(?: |$)')),
          ('order', re.compile(r'(?:^| )(?:ال)?قرار(?: |$)|(?:^| )arrete(?: |$)'))]
_MONTHS = [['يناير', 'جانفي', 'janvier'], ['فبراير', 'فيفري', 'fevrier'], ['مارس', 'mars'], ['ابريل', 'افريل', 'avril'],
           ['ماي', 'مايو', 'mai'], ['يونيو', 'يونيه', 'جوان', 'juin'], ['يوليوز', 'يوليو', 'جويليه', 'juillet'],
           ['غشت', 'اغسطس', 'اغشت', 'اوت', 'aout'], ['شتنبر', 'سبتمبر', 'septembre'], ['اكتوبر', 'octobre'],
           ['نونبر', 'نوفمبر', 'novembre'], ['دجنبر', 'ديسمبر', 'decembre']]
_MONTH = {name: i + 1 for i, names in enumerate(_MONTHS) for name in names}
_WORDED = re.compile(r'(?<!\d)(\d{1,2}|فاتح|1er)\s*(?:er\s+)?(?:من\s+)?(' + '|'.join(sorted(_MONTH, key=len, reverse=True))
                     + r')\s+(?:سنه\s+)?(\d{4})(?!\d)')
_FIGURES = re.compile(r'(?<!\d)(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})(?!\d)')


def stem(word: str) -> str:
    """A folded word without the letters Arabic writes on its front: «للوظيفه» and «الوظيفه» are one word."""
    if len(word) > 4 and word.startswith('لل'):
        return word[2:]
    if len(word) > 5 and word[0] in 'بوكف' and word[1:3] == 'ال':
        return word[3:]
    if len(word) > 4 and word.startswith('ال'):
        return word[2:]
    return word


def stems(text: str) -> list[str]:
    return [stem(w) for w in ma_law.fold(text).split()]


_ABOUT = {'يتعلق', 'متعلق', 'تتعلق', 'متعلقه'}


def title_stems(title: str) -> list[str]:
    """A title's words as a reader would type them: «يتعلق بخطة العدالة» holds «خطة», not «بخطة»."""
    out, before = [], ''
    for w in ma_law.fold(title).split():
        out.append(stem(w[1:]) if before in _ABOUT and w.startswith('ب') and len(w) > 3 and not w.startswith('بال') else stem(w))
        before = stem(w)
    return out


def words(text: str) -> list[str]:
    """The words of `text` that can name a text."""
    return [w for w in stems(text) if len(w) > 1 and w not in _STOP and not w.isdigit()]


def kind_of(folded: str) -> str:
    return next((kind for kind, pattern in _KINDS if pattern.search(folded)), '')


def gregorian(folded: str) -> tuple[date, str] | None:
    """(the day, the words read) of a Gregorian date written in figures or with a month's name."""
    m = _WORDED.search(folded)
    if m:
        day = int(m.group(1)) if m.group(1).isdigit() else 1
        month, year = _MONTH[m.group(2)], int(m.group(3))
    else:
        m = _FIGURES.search(folded)
        if not m:
            return None
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        found = date(year, month, day)
    except ValueError:
        return None
    return (found, m.group(0)) if 1912 <= year <= 2100 else None


_BIS = re.compile(r'(?<=\d)\s+ال(مكرر(?:ة)?)(?!\w)')
# «ق 31.08», «ظ.ش 1.58.376»: the letter jurists write for «قانون» and «ظهير شريف» before a number.
# After the letter: spaces, an optional dot, then at least one space. `_GAP` says it so a run of spaces is read one
# way only («\s*\.?\s+» split it in every way, and «ظ» with 300 spaces took a fifth of a second).
_GAP = r'(?:\s+(?:\.\s+)?|\.\s+)'
_LETTER = [(re.compile(rf'(?<![\w.])ق{_GAP}(?=\d{{1,3}}[.\-]\d{{2}}(?!\d))'), 'القانون رقم '),
           (re.compile(rf'(?<![\w.])ظ(?:\s*(?:\.\s*)?ش)?{_GAP}(?=1[.\-]\d{{2}}[.\-]\d{{1,3}}(?!\d))'), 'الظهير الشريف رقم '),
           # «n° 17-95», «رقم 17.95» and nothing else: the number word goes, a text's number alone is read as one.
           (re.compile(r'^\s*(?:n\s*°|n[o°]\.?|num[ée]ro|رقم|عدد)\s*(?=\d{1,3}(?:[.\-]\d{1,3}){1,2}\s*$)', re.I), '')]


def spelled(q: str) -> str:
    """What a reader typed with the two spellings the citation reader does not know written as it knows them:
    «ق 31.08» → «القانون رقم 31.08», «المادة 225 المكررة» → «المادة 225 مكرر». The library's box, the header's
    suggestions and the search page all read a citation through it, so the three read alike (W3)."""
    for letter, word in _LETTER:
        q = letter.sub(word, q)
    return _BIS.sub(r' \1', q)
