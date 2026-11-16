"""Darija verbs brought to one form (HM1 of the hard-moment review, 7 Nov 2026): a door's words are written in one
person («شدوه البوليس», «طردوني», «بغيت نطلق», «مول الدار بغا يخرجني») and people ask in every other: «شداتو البوليس»,
«شدوني», «طردوها», «راجلي بغا يطلقني», «مولات الدار بغات تخرجني». A word's negation, its object pronoun, its subject's
ending and its aspect's prefix are set aside, on the door's words and on the question alike, so both meet on the verb
(«شد», «طرد», «طلق», «خرج», «مول»). Rules only, read on folded words (compare.fold: alefs one, ة as ه); a word with
«ال», a Latin word and a word of three letters or fewer are left as they are, but a three-letter word ending in «ا»
(«بغا», «عليا») loses it, as «بغات», «بغيت» and «علينا» do."""
from functools import lru_cache

# The object pronoun after a verb: «طردوني», «خرجها», «شدوه», «تبعهم»; «و» only after a subject's «ت»: «شداتو». A last «ه»
# after a consonant is a noun's «ة», folded, and goes too, so one meets its plural: «مخالفة التعمير», «مخالفات التعمير».
OBJECT = ('ني', 'ها', 'هم', 'كم', 'وه', 'اه', 'يه', 'ه', 'ك')
# The subject's ending, longest first: «بغيتو», «بغيتي», «بغينا», «بغيت», «طردات», «بغاو», «طردتو», «طردتي», «طردنا»,
# «طردو», «طردت».
SUBJECT = ('يتو', 'يتي', 'ينا', 'يت', 'ات', 'او', 'تو', 'تي', 'نا', 'و', 'ت')
# The aspect's prefix, longest first: «كيتشد», «كنطلق», «كتبتزني», «كيطردو», «كاين» stays (its rest is short).
PREFIX = ('كيت', 'كين', 'كت', 'كن', 'كي', 'كا', 'ت', 'ن', 'ي')


def _strip(word: str, endings: tuple[str, ...], keep: int) -> str:
    for e in endings:
        if word.endswith(e) and len(word) - len(e) >= keep:
            return word[:-len(e)]
    return word


# A preposition with its pronoun is the preposition: «عليا», «علينا», «عليها» → «علي»; «ليا», «ليه» → «لي».
PREPOSITIONS = {'علي': ('عليا', 'علي', 'عليه', 'عليها', 'علينا', 'عليهم', 'عليك', 'عليكم'),
                'لي': ('ليا', 'ليه', 'ليها', 'لينا', 'ليهم', 'ليك', 'ليكم'),
                'مع': ('معايا', 'معاه', 'معاها', 'معانا', 'معاهم', 'معاك'),
                'عند': ('عندي', 'عندو', 'عنده', 'عندها', 'عندنا', 'عندهم', 'عندك')}
_PREPOSITION = {form: base for base, forms in PREPOSITIONS.items() for form in forms}


@lru_cache(maxsize=65536)
def core(word: str) -> str:
    """One folded word's verb: «شداتو» → «شد», «كيطردونيش» → «طرد», «يخرجني» → «خرج»; other words as they are."""
    w = word
    if w in _PREPOSITION:
        return _PREPOSITION[w]
    if not w or not ('ء' <= w[0] <= 'ي') or w.startswith('ال') or len(w) <= 2:
        return w
    if len(w) == 3:
        return w[:-1] if w.endswith('ا') else w
    neg = False
    if w.startswith('ما') and w.endswith('ش') and len(w) >= 6:
        w, neg = w[2:-1], True
    elif w.startswith('م') and w.endswith('ش') and len(w) >= 6 and w[-2] in 'ويهات':
        w, neg = w[1:-1], True      # the negation glued on: «مخلصونيش» is «ما خلصونيش»
    elif w.endswith('ش') and len(w) >= 5 and w[-2] in 'ويهات':
        w = w[:-1]
    for e in OBJECT:
        if w.endswith(e) and len(w) - len(e) >= 2:
            # «وه», «اه», «يه» give back their vowel: «شدوه» → «شدو», then the subject's «و» goes.
            w = w[:-1] if e in ('وه', 'اه', 'يه') else w[:-len(e)]
            break
    if w.endswith('اتو') or (w.endswith('تو') and len(w) > 4):
        w = w[:-1]
    w = _strip(w, SUBJECT, 2)
    for p in PREFIX:
        if w.startswith(p) and len(w) - len(p) >= 3:
            w = w[len(p):]
            break
    if len(w) == 3 and w.endswith('ي'):
        w = w[:-1]
    # A negation glued on reads as the two words people also write: «ماخلصونيش», «مخلصونيش» → «ما خلص», as «ما خلصونيش».
    return f'ما {w}' if neg else w


def cored(phrase: str) -> str:
    """A folded phrase with each word's verb: «شدوه البوليس» → «شد البوليس»."""
    return ' '.join(core(t) for t in phrase.split())


@lru_cache(maxsize=16384)
def door_key(phrase: str) -> str | None:
    """What a door's folded words meet in a question's cored grams, or None when coring adds nothing or says too little:
    a phrase that does not change, or one word whose verb is shorter than three letters («تشد» stays «تشد» exact)."""
    key = cored(phrase)
    if key == phrase:
        return None
    if ' ' not in key and (len(key) < 3 or (key == phrase[:-1] and phrase.endswith('ه'))):
        # One noun alone keeps its «ة»: «خدامة» (a domestic worker) is no «خدام» (any worker).
        return None
    return key
