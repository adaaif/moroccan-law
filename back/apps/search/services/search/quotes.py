"""Words in a row. Words between quotes are searched as typed (31 Oct 2026): their folded forms, the letters Arabic
writes on the front of the first word («بالقوة القاهرة» for «"القوة القاهرة"»), the phrase as the index holds it, the
pattern every text that holds it matches, and the hits read again as typed. `_phrase`: any words as the index holds
them, side by side, which lifts the articles that hold them in a row."""
import re
from functools import lru_cache

import ma_law

from apps.search.models import SearchEntry

_ARABIC = re.compile(r'[\u0600-\u06FF]')
# Any of the quotes a phone or a keyboard types, opening or closing; one left open runs to the end of the query.
QUOTED = re.compile(r'["“”„«»]([^"“”„«»]*)(?:["“”„«»]|$)')


def quoted(query: str) -> tuple[list[str], list[str], str]:
    """The words typed between quotes, folded (for _quote_spans), the same as typed (to be said), and the query
    without them; a quote holding no word is dropped."""
    folded, typed = [], []
    for m in QUOTED.finditer(query):
        words = ma_law.tokens(m.group(1))
        if words and ' '.join(words) not in folded:
            folded.append(' '.join(words))
            typed.append(' '.join(m.group(1).split()))
    return folded, typed, ' '.join(QUOTED.sub(' ', query).split())


def _fronts(word: str) -> list[str]:
    """A quoted phrase's first word as the text may write it, with the letters Arabic puts on a word's front: «و» or «ف»,
    then «ب», «ل», «ك» or «س» («بقوة», «وسيعاقب»), and for a word with «ال» its «ل» form («للقوة»). «"القوة القاهرة"» is
    found in «بالقوة القاهرة» and «والقوة القاهرة» (31 Oct 2026: the same words, in the same order, with the same
    letters); the phrase still ends where its last word ends, so «"العقد"» never finds «العقدة»."""
    if not _ARABIC.search(word):
        return [word]
    if word.startswith('ال') and len(word) > 2:
        return [c + b + word for c in ('', 'و', 'ف') for b in ('', 'ب', 'ك')] + [c + 'لل' + word[2:] for c in ('', 'و', 'ف')]
    return [c + b + word for c in ('', 'و', 'ف') for b in ('', 'ب', 'ل', 'ك', 'س')]


@lru_cache(maxsize=256)
def _quote_pattern(phrase: str) -> re.Pattern:
    """A quoted phrase (folded) in a text's folded words, spaced: its first word in any of its fronts, the others as typed."""
    first, _, rest = phrase.partition(' ')
    fronts = '|'.join(re.escape(f) for f in sorted(_fronts(first), key=len, reverse=True))
    return re.compile(rf'(?<!\S)(?:{fronts}){" " + re.escape(rest) if rest else ""}(?!\S)')


def _quote_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    """Where a quoted phrase stands in a text, as the text writes it («بالقوة القاهرة» for «"القوه القاهره"»)."""
    found = dict.fromkeys(m.group(0) for m in _quote_pattern(phrase).finditer(' '.join(ma_law.tokens(text))))
    return sorted({span for form in found for span in ma_law.find_folded(text, form)})


@lru_cache(maxsize=256)
def _phrase_forms(phrase: str) -> tuple[str, ...]:
    """A quoted phrase as the index holds it, stems side by side, once for each front of its first word whose stem the
    index keeps apart («بقوة» is «بقو», while «بالقوة» is «قو» like «القوة»)."""
    first, _, rest = phrase.partition(' ')
    return tuple(dict.fromkeys(f for f in (_phrase(f'{front} {rest}') for front in _fronts(first)) if f))


# The letters ma_law.fold makes one, harakat and tatweel it drops, and what may stand between two words: a quoted phrase
# as a pattern on the words as stored (_loose), which finds every way the text writes it and a little more.
_FOLDED_FROM = {'ا': 'اأإآٱ', 'و': 'وؤ', 'ي': 'يئىی', 'ه': 'هة', 'ك': 'كک',
                **{d: d + chr(0x660 + int(d)) + chr(0x6F0 + int(d)) for d in '0123456789'},
                'a': 'aàâäá', 'e': 'eéèêë', 'i': 'iîïí', 'o': 'oôöó', 'u': 'uùûüú', 'c': 'cç'}
_MARKS = '[\u0640\u064B-\u065F\u0670]*'
_BETWEEN = '[^\u0621-\u063A\u0641-\u064A0-9A-Za-z\u00C0-\u024F]+'


def _loose(phrase: str) -> str:
    """A PostgreSQL pattern (case aside) that every text holding the quoted phrase, in any of its forms, matches: each
    folded letter as the letters it folds from, harakat between them, anything but a letter between the words, the first
    word's «ال» as «لل» too. _exactly reads its matches again."""
    def letters(word):
        return ''.join((f'[{_FOLDED_FROM[c]}]' if c in _FOLDED_FROM else re.escape(c)) + _MARKS for c in word)
    first, *rest = phrase.split()
    head = f'(?:{letters("ال")}|ل{_MARKS}ل{_MARKS}){letters(first[2:])}' if first.startswith('ال') and len(first) > 2 else letters(first)
    return _BETWEEN.join([head] + [letters(w) for w in rest])


def _needs_reading(phrase: str) -> bool:
    """A phrase the index's stems cannot tell from its other forms: Arabic, or any word the index stems."""
    return bool(_ARABIC.search(phrase)) or ma_law.index_terms(phrase) != phrase.split()


def _exact_terms(phrases: list[str]) -> list[str]:
    """The stems BM25 requires for the quoted words besides their phrase: those of every word after the first (whose stem
    changes with its front), their search terms or every word when they are all small words. None for a phrase of one
    word: its phrase alone finds it."""
    out: list[str] = []
    for p in phrases:
        rest = p.partition(' ')[2]
        out += [t for t in (ma_law.search_terms(rest) or ma_law.index_terms(rest)) if t not in out]
    return out


def _exactly(hits: list[tuple], phrases: list[str]) -> list[tuple]:
    """The hits that hold each quoted phrase as typed: the index holds its words stemmed («العقد» and «العقود» are one
    stem), so an article's words and a title's are read again, in one query. A phrase in Latin letters needs no reading:
    ma_law does not stem it, so the index's phrase is already the words as typed (and holds the article's French)."""
    arabic = [_quote_pattern(p) for p in phrases if _needs_reading(p)]
    if not hits or not arabic:
        return hits
    rows = {pk: ' '.join(ma_law.tokens(f'{label}\n{body}' if kind == SearchEntry.Kind.ARTICLE else folded))
            for pk, kind, label, body, folded in SearchEntry.objects.filter(pk__in=[h[0] for h in hits]).values_list(
                'pk', 'kind', 'label', 'body', 'title_folded')}
    return [h for h in hits if h[0] in rows and all(pattern.search(rows[h[0]]) for pattern in arabic)]


def _phrase(words: str) -> str:
    return ' '.join(ma_law.index_terms(words))
