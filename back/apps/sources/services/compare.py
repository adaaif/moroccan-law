"""Comparing two readings of a page: a folded form, a character error rate and a word F1.

The text layers of born-digital BO pages put lam-alef ligatures in the wrong order («األنشطة»), so a
comparison against them can run «lam-alef blind»: alef and lam are dropped from both sides and every
other letter is scored.
"""
import re
import unicodedata
from collections import Counter

from rapidfuzz.distance import Levenshtein

_DIACRITICS = re.compile('[ؐ-ًؚ-ٰٟۖ-ۭ]')
_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')


def fold(text: str, *, lam_alef_blind: bool = False) -> str:
    t = unicodedata.normalize('NFKC', text)
    t = re.sub(r'<[^>]{1,20}>', ' ', t)  # markup an engine adds in table cells (<br>)
    t = _DIACRITICS.sub('', t).replace('ـ', '')
    t = re.sub('[أإآٱ]', 'ا', t).replace('ى', 'ي').replace('ة', 'ه').translate(_DIGITS).lower()
    t = re.sub(r'[\W_]+', ' ', t)
    if lam_alef_blind:
        t = re.sub('[ال]', '', t)
    return ' '.join(t.split())


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate of `hypothesis` against `reference` (already folded); order matters."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return Levenshtein.distance(reference, hypothesis) / len(reference)


def word_f1(reference: str, hypothesis: str) -> float:
    """Word overlap regardless of order (columns read in another order cost nothing)."""
    ref, hyp = Counter(reference.split()), Counter(hypothesis.split())
    if not ref and not hyp:
        return 1.0
    common = sum((ref & hyp).values())
    if not common:
        return 0.0
    precision, recall = common / sum(hyp.values()), common / sum(ref.values())
    return 2 * precision * recall / (precision + recall)


def scores(reference: str, hypothesis: str, *, lam_alef_blind: bool = False) -> dict[str, float]:
    ref, hyp = fold(reference, lam_alef_blind=lam_alef_blind), fold(hypothesis, lam_alef_blind=lam_alef_blind)
    return {'cer': round(cer(ref, hyp), 4), 'word_f1': round(word_f1(ref, hyp), 4),
            'ref_chars': len(ref), 'hyp_chars': len(hyp)}
