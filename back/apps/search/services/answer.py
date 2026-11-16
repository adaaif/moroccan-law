"""B15 of the search plan (25 Oct 2026): the box that answers first. A question (not a citation, a name or a few words)
gets the law's own sentence that answers it best, from the first article of the first text: the sentence of that article
holding most of the question's words, the words marked; for «شحال», «combien» or «how long», the number in bold. The
number is the law's own words, found by a pattern or by B9's facts (services/surrogates.py) and only where it stands
word for word in the sentence. Nothing is written but the law."""
import re

import ma_law

from apps.search.services.goldset import NUMBER, intent_of

ASKS = {'question', 'number', 'procedure', 'definition'}
# A question about a duration, an amount, a rate or an age, besides «شحال» and its kind (goldset.NUMBER).
AMOUNT = re.compile(r'\bمد[ةه]\b|\bأجل\b|\bاجل\b|آجال|مبلغ|نسب[ةه]|\bسن\b|délai|durée|montant|taux|\bâge\b|how (?:long|old)',
                    re.IGNORECASE)
MOST_WORDS = 60          # a longer sentence is shown as the stretch around its first marked word
STRETCH = (45, 10)
FACT_WORDS = 4           # a B9 fact longer than this is a phrase, not a number
_SENTENCE = re.compile(r'(?<=[.؛;!؟?])\s+|\n+')
_WORD = re.compile(r'\S+')
_UNIT = (r'(?:%|في المائ[ةه]|درهما?|دراهم|يوما|أياما?|ايام|ساع[ةه]|ساعات|شهرا|أشهر|اشهر|شهور|سن[ةه]|سنوات|سنين|'
         r'أسبوعا?|أسابيع|jours?|mois|ans?|années?|heures?|semaines?|dirhams?|days?|months?|years?|hours?|weeks?)')
_NUMWORD = r'(?:ال)?(?:واحد|اثن|ثلاث|أربع|اربع|خمس|ست|سبع|ثمان|تسع|عشر|مائ|مئ|ألف|آلاف|مليون|ملايين)\S*'
NUMBERS = re.compile(rf'\d+(?:[.,]\d+)?\s*{_UNIT}|{_NUMWORD}(?:\s+و?{_NUMWORD})*\s+{_UNIT}|'
                     r'\b(?:يومين|شهرين|سنتين|ساعتين|أسبوعين)\b', re.IGNORECASE)


def asks(query: str) -> bool:
    return intent_of(query) in ASKS


def asks_amount(query: str) -> bool:
    return bool(NUMBER.search(query) or AMOUNT.search(query))


def best_sentence(body: str, terms: list[str], *, amount: bool, facts: list[str] = ()) -> list[dict] | None:
    """The sentence of `body` that holds most of `terms` (the first one when none does), as segments [{t, hit, num}];
    for a question about an amount, the best sentence that states one, its number in bold. None when there is nothing
    to show."""
    wanted = set(terms)
    sentences = [s.strip() for s in _SENTENCE.split(re.sub(r'\*\*|-{3,}|\|', ' ', body)) if s and s.strip()]
    if not sentences:
        return None
    scored = [(len(wanted & set(ma_law.index_terms(s))), -i, s) for i, s in enumerate(sentences)]
    if amount:
        stating = [x for x in scored if _numbers(x[2], facts)]
        scored = stating or scored
    _, _, chosen = max(scored)
    return _segments(chosen, wanted, _numbers(chosen, facts) if amount else [])


def _numbers(sentence: str, facts: list[str]) -> list[tuple[int, int]]:
    """Where the sentence states a number: the pattern's spans and B9's facts found word for word."""
    spans = [m.span() for m in NUMBERS.finditer(sentence)]
    if spans:
        return spans
    for fact in facts:      # a number written another way («ثلث الأجرة»): B9's words, when short and found as written
        at = sentence.find(fact) if 2 < len(fact) and len(fact.split()) <= FACT_WORDS else -1
        if at >= 0:
            spans.append((at, at + len(fact)))
    return spans


def _segments(sentence: str, wanted: set[str], numbers: list[tuple[int, int]]) -> list[dict]:
    words = [m.span() for m in _WORD.finditer(sentence)]
    lo, hi, head, tail = 0, len(words), False, False
    if len(words) > MOST_WORDS:
        first = next((i for i, (a, b) in enumerate(words) if _hit(sentence[a:b], wanted)), 0)
        if numbers:
            first = next((i for i, (a, b) in enumerate(words) if any(s <= a < e for s, e in numbers)), first)
        lo = max(0, first - STRETCH[1])
        hi = min(len(words), lo + STRETCH[0])
        head, tail = lo > 0, hi < len(words)
    marks = [(_hit(sentence[a:b], wanted), any(s <= a < e or a <= s < b for s, e in numbers)) for a, b in words[lo:hi]]
    out: list[dict] = [{'t': '… ', 'hit': False, 'num': False}] if head else []
    for k, (a, b) in enumerate(words[lo:hi]):
        out.append({'t': sentence[a:b], 'hit': marks[k][0], 'num': marks[k][1]})
        if k < len(marks) - 1:      # a space inside a number («ستة أشهر») is part of it
            out.append({'t': ' ', 'hit': False, 'num': marks[k][1] and marks[k + 1][1]})
    if tail:
        out.append({'t': ' …', 'hit': False, 'num': False})
    merged: list[dict] = []
    for seg in out:
        if merged and (merged[-1]['hit'], merged[-1]['num']) == (seg['hit'], seg['num']) and not seg['hit']:
            merged[-1]['t'] += seg['t']
        else:
            merged.append(seg)
    return merged


def _hit(word: str, wanted: set[str]) -> bool:
    return any(ma_law.stem(w) in wanted for w in ma_law.tokens(word))
