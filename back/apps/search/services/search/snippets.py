"""A result's snippet: the stretch of an article around its first matched word, or its first quoted phrase, as
segments with the matched words marked; a long article read a stretch at a time."""
import bisect
import re

import ma_law

from apps.search.services.search.quotes import _quote_spans

SNIPPET = (22, 5)      # a result's snippet: two lines, the word in the first

_WORD = re.compile(r'\S+')
_TO_SPACE = re.compile(r'\S*')       # from a place in a word to the space after it
LONG = 4000         # characters: a longer article is read a stretch at a time for its snippet


def _hit_at(text: str, wanted: set[str]) -> int | None:
    """Where the first word whose stem the query holds starts, None when none, -1 when ma_law's words and spans disagree
    (should not happen): three calls into ma_law (the stems, the folded words, where the hit's folded word stands)
    instead of two a word (S21 of the performance audit)."""
    stems = ma_law.index_terms(text)
    t = next((i for i, stem in enumerate(stems) if stem in wanted), None)
    if t is None:
        return None
    folded = ma_law.tokens(text)
    nth = sum(1 for w in folded[:t] if w == folded[t])
    spans = ma_law.find_folded(text, folded[t])
    return spans[nth][0] if nth < len(spans) else -1


def _first_hit(body: str, words: list[tuple[int, int]], wanted: set[str]) -> int:
    """The index of the first word whose stem the query holds, 0 when none."""
    at = _hit_at(body, wanted)
    if at is None:
        return 0
    if at < 0:          # the slow way, word by word
        return next((i for i, (s0, e0) in enumerate(words)
                     if any(ma_law.stem(w) in wanted for w in ma_law.tokens(body[s0:e0]))), 0)
    return max(0, bisect.bisect_right([s0 for s0, _ in words], at) - 1)


def _stretch(body: str, wanted: set[str]) -> tuple[str, bool, bool]:
    """A long article's stretch around its first hit, found LONG characters at a time and cut at spaces, and whether
    text is left out before and after it: an annex of 157,000 characters was split and stemmed whole for two lines
    (450 ms for «ف 418 ق.ل.ع», B27)."""
    lo = at = 0
    while lo < len(body):
        hi = _TO_SPACE.match(body, lo + LONG).end()
        found = _hit_at(body[lo:hi], wanted)
        if found is not None:
            at = lo + max(found, 0)
            break
        lo = hi
    return _around(body, at)


def _around(body: str, at: int) -> tuple[str, bool, bool]:
    start = min(at, _TO_SPACE.match(body, at - 400).end()) if at > 400 else 0
    end = _TO_SPACE.match(body, at + LONG).end()
    return body[start:end], start > 0, end < len(body)


def _quoted_at(body: str, exact: list[str]) -> list[tuple[int, int]]:
    """Where the quoted phrases stand in a text, as it writes them, in order."""
    return sorted(span for p in exact for span in _quote_spans(body, p))


def snippet(body: str, terms: list[str], size: int = 40, before: int = 12, exact: list[str] | None = None) -> list[dict]:
    """The stretch of an article around its first matched word, as segments [{t, hit}], the matched words
    marked (a word is matched when its stem is one of the query's). `before`: the words kept ahead of it. `exact`: the
    quoted phrases (folded), matched as typed and side by side; the stretch starts at the first of them."""
    wanted = set(terms)
    head = tail = False
    if len(body) > LONG and exact and (spans := _quoted_at(body, exact)):
        body, head, tail = _around(body, spans[0][0])
    elif wanted and len(body) > LONG:
        body, head, tail = _stretch(body, wanted)
    # The OCR's Markdown (table pipes and rules, bold marks) is no part of a snippet.
    body = re.sub(r'\*\*|-{3,}|\|', ' ', body)
    words = [(m.start(), m.end()) for m in _WORD.finditer(body)]
    spans = _quoted_at(body, exact) if exact else []
    if spans:
        first = max(0, bisect.bisect_right([s0 for s0, _ in words], spans[0][0]) - 1)
    else:
        first = _first_hit(body, words, wanted) if wanted else 0
    lo = max(0, first - before)
    hi = min(len(words), lo + size)
    hits = {i for i in range(lo, hi)
            if any(words[i][0] < e and words[i][1] > s for s, e in spans)
            or any(ma_law.stem(w) in wanted for w in ma_law.tokens(body[words[i][0]:words[i][1]]))}
    out: list[dict] = []
    if lo or head:
        out.append({'t': '… ', 'hit': False})
    for i in range(lo, hi):
        s0, e0 = words[i]
        out.append({'t': body[s0:e0], 'hit': i in hits})
        if i < hi - 1:
            out.append({'t': ' ', 'hit': False})
    if hi < len(words) or tail:
        out.append({'t': ' …', 'hit': False})
    # Neighbouring plain segments merged.
    merged: list[dict] = []
    for seg in out:
        if merged and not seg['hit'] and not merged[-1]['hit']:
            merged[-1]['t'] += seg['t']
        else:
            merged.append(dict(seg))
    return merged
