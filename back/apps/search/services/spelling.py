"""B6 of the search plan: what people type that is not yet the law's words. Darija in Latin letters («wach mol dar
y9der ykhrjni») is written in Arabic letters the way the law spells its words, so the rest of search (the words people
use, the topics' doors, the asking words set aside) reads it as it reads Darija; and a word that finds nothing is
offered as the word of the index it most likely meant, one letter away.

The spellings come from ma_law (Rust, the same at index and query time); the choice between them is the corpus's:
the spelling whose stem the law uses most."""
import json
import re
from functools import lru_cache
from pathlib import Path

import ma_law

from apps.search.services.index import term_counts

SPELLINGS = 48
# Darija's small words in Latin letters, as Darija writes them in Arabic letters (ASKING sets them aside then).
SMALL = {'wach': 'واش', 'wash': 'واش', 'chno': 'شنو', 'chnou': 'شنو', 'chnu': 'شنو', 'kifach': 'كيفاش', 'kifash': 'كيفاش',
         'bghit': 'بغيت', 'dyal': 'ديال', 'dial': 'ديال', 'f': 'في', 'fl': 'في', 'l': 'ل', 'b': 'ب', 'w': 'و',
         '3la': 'على', 'ila': 'إلى', 'bla': 'بلا', 'machi': 'ماشي', 'daba': 'دابا', 'bzaf': 'بزاف', 'chi': 'شي',
         'ch7al': 'شحال', 'chhal': 'شحال', 'fin': 'فين', '3lach': 'علاش', 'wa9tach': 'وقتاش', 'kayn': 'كاين'}
CLITICS = ('l', 'el', 'al', 'f', 'b', 'w')
# The topics' everyday words as people type them («kra», «tlaq», «khdma»), as the law spells them: the likeliest
# spelling of a short word is often wrong («nafa9a» read «نفق», «lkra» «القر») and ma_law does not take «kra dyal dar»
# for Darija without a digit (UX7 of the phone-test review).
LEXICON_PATH = Path(__file__).resolve().parent.parent / 'data' / 'darija_latin.json'


@lru_cache(maxsize=1)
def lexicon() -> dict[str, str]:
    return {k: v for k, v in json.loads(LEXICON_PATH.read_text(encoding='utf-8')).items() if k != '_'}


@lru_cache(maxsize=1)
def french_words() -> dict[str, int]:
    """How often each folded word occurs in the official French the site holds: Darija borrows these as they are."""
    from collections import Counter

    from apps.translations.models import FrenchArticle

    counts: Counter = Counter()
    for body in FrenchArticle.objects.values_list('body', flat=True).iterator(chunk_size=500):
        counts.update(ma_law.tokens(body))
    return dict(counts)


def _weight(arabic: str) -> int:
    """How much the law uses a spelling: its stems' counts in the index."""
    counts = term_counts()
    stems = ma_law.index_terms(arabic)
    return sum(counts.get(s, 0) for s in stems) // max(len(stems), 1)


FRENCH_MIN = 20       # a Latin word the corpus's French uses this often stays French: «permis», «assurance»
FAR_MORE = 5         # another spelling wins over the likeliest only when the law uses it this many times more
# A longer word is no word of Darija (the test sets' longest is 17 letters, «auto-entrepreneur») nor of the law, and
# its spellings and its edits cost more with each letter: it stays as typed.
LONGEST = 30


@lru_cache(maxsize=4096)
def word(latin: str) -> str:
    """One word of Arabizi in Arabic letters: a small word as Darija writes it; a French word the corpus knows, as it is
    (Darija borrows them: «permis», «assurance»); else the likeliest spelling, or one the law uses far more, a clitic
    («l9anoun») tried apart («القانون»). A word longer than LONGEST comes back as typed."""
    if len(latin) > LONGEST:
        return latin
    low = latin.lower()
    if low in SMALL:
        return SMALL[low]
    if low in lexicon():
        return lexicon()[low]
    if low.isalpha() and (french_words().get(ma_law.fold(low), 0) >= FRENCH_MIN or _looks_french(low)):
        return latin
    if low.startswith('aa'):
        low = '3' + low[2:]          # «aandi»: a doubled a opens on ع
    options = [(s, s) for s in ma_law.arabizi_spellings(low, SPELLINGS)]
    for clitic in CLITICS:
        if low.startswith(clitic) and len(low) - len(clitic) >= 3:
            arabic = 'ال' if clitic in ('l', 'el', 'al') else {'f': 'ف', 'b': 'ب', 'w': 'و'}[clitic]
            options += [(arabic + s, s) for s in ma_law.arabizi_spellings(low[len(clitic):], SPELLINGS)]
    if not options:
        return latin
    likeliest = options[0]
    best = max(options, key=lambda o: (_weight(o[1]), -options.index(o)))
    return best[0] if _weight(best[1]) >= FAR_MORE * max(_weight(likeliest[1]), 1) else likeliest[0]


def arabizi(query: str) -> str | None:
    """The query in Arabic letters when it is Darija typed in Latin letters, else None: ma_law's test, or every word
    of it the topics' Darija (`lexicon`) or a Darija small word («kra dyal dar», «tlaq»). A question that mixes in
    words of neither («vignette tomobil chhal», «chkaya l cndp») is left to them: turned into Arabic letters it lost 6
    of the test sets' 75 Latin questions (UX7)."""
    words = [w.strip('?!.,;:()«»"\'') for w in query.split()]
    letters = [w.lower() for w in words if any(c.isalpha() for c in w)]
    darija = bool(letters) and all(w in lexicon() or w in SMALL for w in letters)
    if not darija and not ma_law.is_arabizi(query) and not _mostly_darija(letters):
        return None
    return ' '.join(word(w) if any(c.isalpha() for c in w) else w for w in words if w) or None


def _mostly_darija(letters: list[str]) -> bool:
    """An all-Latin question most of whose words Darija knows and few French does (HM1 of the hard-moment review:
    «mol dar bgha ykhrjni mn dar» found dahirs classing Dar Batha as a monument): at least two words the lexicon or the
    small words hold, at least half of its words, and none French."""
    if len(letters) < 2 or any(not w.isascii() for w in letters):
        return False
    known = sum(1 for w in letters if w in lexicon() or w in SMALL)
    french = sum(1 for w in letters if w not in SMALL and w not in lexicon() and (
        french_words().get(ma_law.fold(w), 0) >= FRENCH_MIN or _looks_french(w)))
    return known >= 2 and known * 2 >= len(letters) and french == 0


_FRENCH_ENDS = ('tion', 'ment', 'ette', 'eur', 'eurs', 'ais', 'oir', 'ique', 'ance', 'ence', 'age', 'aire')


def _looks_french(word: str) -> bool:
    """A word French spells and Darija in Latin letters does not: an accent, or a French ending («vignette»)."""
    return any(c in word for c in 'éèêàâçîôûù') or (len(word) > 4 and word.endswith(_FRENCH_ENDS))


ARABIC_LETTERS = 'ابتثجحخدذرزسشصضطظعغفقكلمنهويءئؤة'
KNOWN = 3          # a word whose stem the index holds this often is no typo
LIKELY = 20        # a correction must be this common in the index


# Letters people put for one another (sound or keyboard): a change between them is a likely slip, ten times as likely.
CONFUSED = {frozenset(p) for p in ('ضظ', 'قف', 'سص', 'تط', 'ذز', 'ذظ', 'زظ', 'هح', 'هة', 'عغ', 'يى', 'ءا', 'ئي', 'ؤو',
                                   'دذ', 'ثس', 'كق', 'جغ')}
SLIP = 10


def correct(word: str) -> str | None:
    """The word of the index one letter away (dropped, added, swapped or changed) that is likeliest: how often the law
    uses it, ten times more when the change is between letters people confuse (ض and ظ, ق and ف…); None when the word
    typed is the index's, or nothing near is common enough."""
    folded = ma_law.fold(word)
    if len(folded) > LONGEST:
        return None                 # no word of the law is this long, and its edits cost the square of its length
    counts = term_counts()
    if not folded or not any('\u0621' <= c <= '\u064a' for c in folded) or counts.get(ma_law.stem(folded), 0) >= KNOWN:
        return None
    edits: dict[str, int] = {}
    for i in range(len(folded)):
        edits.setdefault(folded[:i] + folded[i + 1:], 1)
        for c in ARABIC_LETTERS:
            if c != folded[i]:
                key = folded[:i] + c + folded[i + 1:]
                edits[key] = max(edits.get(key, 0), SLIP if frozenset((c, folded[i])) in CONFUSED else 1)
    for i in range(len(folded) - 1):
        edits.setdefault(folded[:i] + folded[i + 1] + folded[i] + folded[i + 2:], 1)
    for i in range(len(folded) + 1):
        for c in ARABIC_LETTERS:
            edits.setdefault(folded[:i] + c + folded[i:], 1)
    best = max(((counts.get(ma_law.stem(e), 0), likely, e) for e, likely in edits.items() if len(e) >= 2),
               key=lambda t: (t[0] * t[1], t[0]), default=(0, 1, ''))
    return best[2] if best[0] >= LIKELY else None


def _unknown(word: str, counts: dict) -> bool:
    """A word of Arabic letters alone (no digit, no Latin) whose stem the index holds less than KNOWN times."""
    folded = ma_law.fold(word)
    return bool(re.fullmatch('[\u0621-\u064a]+', folded)) and counts.get(ma_law.stem(folded), 0) < KNOWN


def corrected(query: str) -> str | None:
    """The query with its one mistyped word put right, or None. A slip is one word among the law's own («نفقة الطلاف»):
    a question with several words the law never uses is another way of speaking, and its Darija was turned into other
    words of the law («نرجع حاجة شريتها» into «مرجع حاجة شريطها»: two of three such tuning questions lost)."""
    words = query.split()
    counts = term_counts()
    unknown = [i for i, w in enumerate(words) if _unknown(w, counts)]
    if len(unknown) != 1:
        return None
    fix = correct(words[unknown[0]])
    return ' '.join(fix if i == unknown[0] else w for i, w in enumerate(words)) if fix else None
