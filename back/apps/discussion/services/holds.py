"""What holds a contribution for a reviewer before anyone reads it, by fixed patterns (D8: no model reads the
discussion). A hold is never a refusal: a reviewer publishes it or removes it, and sees what was matched.

- A phone number, an email address, a CIN or a RIB: someone's own details, or another person's.
- A link to a site other than the official ones.
- A case number as courts write it (1234/1201/2024).
- A word from the insult list, with the prefixes Arabic joins to it («ال», «و», «ب», «ل»…) and its letters doubled.

Every pattern reads the words folded first (`fold`): Arabic-Indic, Persian and full-width digits as Western ones;
invisible characters (zero-width spaces and joiners, direction marks, the soft hyphen), tatweel and vowel marks out;
hamza seats, «ة», «ى» and the Persian letters as the plain Arabic letters; «[.]» as a dot. One character slipped into a
number or a word got past each pattern. The spans still point into the words as written.

The same patterns read the names shown beside what people write (`in_name`, `shown_name`): a phone number or an
insult as a name broke the rules on every card.
"""
import re
import unicodedata
from functools import lru_cache
from urllib.parse import urlparse

from django.conf import settings

# Characters that show nothing: put inside a number or a word, they hid it from the patterns.
_INVISIBLE = frozenset('\u00ad\u034f\u061c\u0640\u115f\u1160\u17b4\u17b5\u180e\u200b\u200c\u200d\u200e\u200f'
                       '\u202a\u202b\u202c\u202d\u202e\u2060\u2061\u2062\u2063\u2064\u2066\u2067\u2068\u2069\ufeff')
_DIGITS = dict(zip('\u0660\u0661\u0662\u0663\u0664\u0665\u0666\u0667\u0668\u0669'  # Arabic-Indic
                    '\u06f0\u06f1\u06f2\u06f3\u06f4\u06f5\u06f6\u06f7\u06f8\u06f9', '01234567890123456789'))  # Persian
# The same letter written another way: «ة» and «ى» as Arabic folds them for search, Persian and Urdu letters as Arabic.
_LETTERS = {'\u0629': '\u0647', '\u0649': '\u064a', '\u06cc': '\u064a', '\u06cd': '\u064a', '\u06d2': '\u064a',
            '\u06a9': '\u0643', '\u06aa': '\u0643', '\u06be': '\u0647', '\u06c0': '\u0647', '\u06c1': '\u0647',
            '\u0671': '\u0627', '\u0672': '\u0627', '\u0673': '\u0627'}
# «evil[.]com», «evil(.)com»: a dot in brackets is a dot.
_DOTS = re.compile(r'[\[({]\.[\])}]')


def fold(text: str) -> tuple[str, list[int]]:
    """The words as the patterns read them, and for each folded character the index of the character it came from.
    Case is kept (a spaced CIN is read in capitals only); the patterns that need it ignore it themselves."""
    out: list[str] = []
    where: list[int] = []
    for i, ch in enumerate(text):
        if ch in _INVISIBLE:
            continue
        for f in unicodedata.normalize('NFKD', ch):
            if unicodedata.category(f) == 'Mn' or f in _INVISIBLE:
                continue                                      # vowel marks, hamza seats, accents
            out.append(_LETTERS.get(f, _DIGITS.get(f, f)))
            where.append(i)
    folded = ''.join(out)
    for m in reversed(list(_DOTS.finditer(folded))):        # «[.]» becomes «.», from the end so offsets hold
        s, e = m.span()
        folded = folded[:s] + '.' + folded[e:]
        where = where[:s] + [where[s + 1]] + where[e:]
    return folded, where


# A Moroccan mobile or landline: 06…, +212 6…, 00212…, or 212 written alone; a space, a dot or a hyphen between any
# digits, or «/» between pairs («06/12/34/56/78», never a date).
PHONE = re.compile(r'(?<!\d)(?:(?:(?:\+|00)?\s?212[\s.-]?\(?0?\)?[\s.-]?|0)[5-8](?:[\s.-]?\d){8}|0[5-8](?:/\d\d){4})(?!\d)')
# From the start of a run of name characters only: «a-a-a-…» with no «@» made it quadratic.
EMAIL = re.compile(r'(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
# A CIN: one or two Latin letters joined to five or six digits («BE123456»); spaced («BE 123 456») only in capitals,
# so «de 50000» and «DH 50 000» stay words.
CIN = re.compile(r'(?<![A-Za-z0-9])(?:[A-Za-z]{1,2}\d{5,6}|(?!DH\b)[A-Z]{1,2}[\s-]?\d(?:\s?\d){4,5})(?![A-Za-z0-9])')
RIB = re.compile(r'(?<!\d)(?:\d[\s-]?){23}\d(?!\d)|\bMA\d{2}(?:\s?\d{4}){5,6}\b', re.IGNORECASE)
# The second form starts where no word, dot or hyphen stands before it: «a-a-a-…» made it quadratic.
LINK = re.compile(r'(?:https?://|www\.)[^\s<>«»"]+|(?<![\w.-])[\w-]+(?:\.[\w-]+)*\.(?:com|ma|net|org|fr|info|io|me|co|'
                  r'ly|gl|xyz|app|site|online|shop|store|biz|top|live|link|click|tk|cc|tv|us|uk)\b(?:/[^\s<>«»"]*)?',
                  re.IGNORECASE)
CASE = re.compile(r'(?<!\d)\d{1,6}\s?/\s?\d{4}\s?/\s?\d{4}(?!\d)')
OFFICIAL = ('gov.ma', 'justice.gov.ma', 'sgg.gov.ma', 'chambredesrepresentants.ma', 'chambredesconseillers.ma',
            'cour-constitutionnelle.ma', 'cspj.ma', 'cndp.ma', 'courdescomptes.ma', 'mahakim.ma')

# Insults only, never words the law itself uses (an animal, a thief): a held contribution costs a reviewer a
# minute, a law reader's word held every time costs the discussion.
_INSULTS = """
قحبة قحاب قحبه شرموطة شرموط شراميط منيوك منيوكة زامل زوامل الزامل طبون زب زبي نيك نيكو نكمك ولد_القحبة
بنت_القحبة تفو مخنث لعن_دين لعن_الدين يلعن_دين حمار_الله
pute putain salope connard connasse enculé encule fdp ntm nique niquer batard bâtard
""".split()
INSULTS = [w.replace('_', ' ') for w in _INSULTS]
# What Arabic joins in front of a word: «و» or «ف», then the article («ال», «بال», «لل», «كال»); «ب», «ل» or «ك»
# alone only before a word of four letters or more («بنيك» is «your sons», «لزب» a word of its own).
_PREFIX = '(?:[وف]?(?:ال|لل|بال|كال)?)'
_PREFIX_LONG = '(?:[وف]?(?:ال|لل|بال|كال|[بلك])?)'


def _word(w: str) -> str:
    """An insult folded as the words are, each letter allowed to repeat («قحححبة»), words apart by any space."""
    folded = fold(w)[0].lower()
    letters = r'\s+'.join(''.join(f'{re.escape(c)}+' for c in part) for part in folded.split())
    arabic = any('\u0600' <= c <= '\u06ff' for c in folded)
    prefix = (_PREFIX_LONG if len(folded.split()[0]) >= 4 else _PREFIX) if arabic else ''
    return rf'(?<![\w]){prefix}{letters}(?![\w])'


_INSULT = re.compile('|'.join(_word(w) for w in INSULTS), re.IGNORECASE)


def _official(link: str) -> bool:
    # A browser reads «\» as «/»: «https://evil.com\.gov.ma/» goes to evil.com. A link with a user name in it
    # («evil.com:443\@x.gov.ma») is never official.
    link = link.replace('\\', '/')
    try:
        parsed = urlparse(link if '://' in link else f'http://{link}')
        host = parsed.hostname or ''
    except ValueError:          # «https://[»: no address a browser opens, so none of the official ones
        return False
    if '@' in parsed.netloc:
        return False
    own = urlparse(settings.SITE_URL).hostname or ''
    return host == own or any(host == d or host.endswith(f'.{d}') for d in OFFICIAL)


def scan(body: str) -> tuple[list[str], list[list]]:
    """(reasons, spans [start, end, reason]) found in the words; the spans point into `body` as written."""
    folded, where = fold(body or '')
    spans: list[list] = []
    taken: list[tuple[int, int]] = []

    def add(match, reason):
        s, e = match.span()
        if e <= s:
            return
        start, end = where[s], where[e - 1] + 1
        # A mark or an invisible character right after the match belongs to it (a redaction takes it too).
        while end < len(body) and (body[end] in _INVISIBLE or unicodedata.category(body[end]) == 'Mn'):
            end += 1
        if any(a < end and start < b for a, b in taken):
            return
        taken.append((start, end))
        spans.append([start, end, reason])

    for m in (EMAIL.finditer(folded) if '@' in folded else ()):
        add(m, 'email')
    for m in LINK.finditer(folded):
        if not _official(m.group()):
            add(m, 'link')
    for m in RIB.finditer(folded):
        add(m, 'rib')
    for m in PHONE.finditer(folded):
        add(m, 'phone')
    for m in CASE.finditer(folded):
        add(m, 'case')
    for m in CIN.finditer(folded):
        add(m, 'cin')
    for m in _INSULT.finditer(folded):
        add(m, 'insult')
    spans.sort()
    return sorted({s[2] for s in spans}), spans


@lru_cache(maxsize=4096)
def in_name(name: str) -> tuple[str, ...]:
    """What the patterns find in a name or a username: (), or the reasons, as `scan` gives them. Sign-up and the
    profile refuse a name that holds one; the discussion shows the next name in its place (`shown_name`)."""
    return tuple(scan(name or '')[0])


def shown_name(user) -> str:
    """The name readers see beside someone's words: the name they chose, else their username, whichever the patterns
    find nothing in; '' when both hold something."""
    for name in (user.display_name, user.username):
        if name and not in_name(name):
            return name
    return ''
