"""An amendment's wording put into the article it changes (row 19). The BO prints the new article with dots where
the old words stay:

    old:  يحدد هذا المرسوم، تطبيقا لأحكام الفصل 54 … لممارسة مهام القيادة ومهام ضابط على متن سفن الصيد البحري.
    new:  يحدد هذا المرسوم، ................ مهام ضابط على متن سفن الصيد البحري، وسفن مساعدة تربية الأحياء …

Paragraphs are matched first (by their number «16 -», «أ)», or their first words); a line of dots keeps the old
paragraphs it stands for; inside a paragraph, each run of dots keeps the old words between the words printed on
either side of it. When an anchor cannot be found the wording is not placed: `Unplaced` says why, and nothing is
guessed."""
import re
from difflib import SequenceMatcher

import ma_law

DOTS = re.compile(r'(?:\.\s*){4,}|…+')
ENUM = re.compile(r'^\s*(\d+|[ء-ي]|[IVX]+)\s*[-–)]')
END = re.compile(r'[.:؛;]\s*$')
PREFIXES = ('و', 'ف', 'ب', 'ل')
# «(الباقي لا تغيير فيه.)»: the rest of the article stays, as a line of dots would say.
REST = re.compile(r'^\(?\s*(?:الباقي|والباقي|الباقي من المادة)\s+(?:لا تغيير فيه|بدون تغيير|دون تغيير|لم يتغير)')
ANCHOR = 3


class Unplaced(Exception):
    """The wording could not be placed; the reason is a code («anchor», «paragraph», «part»)."""


def paragraphs(body: str) -> list[str]:
    """Physical lines joined into paragraphs: a line runs on unless it ends a sentence or the next one is numbered."""
    out: list[str] = []
    for line in (ln.strip() for ln in body.splitlines()):
        if not line:
            continue
        if line.startswith('|') or (out and out[-1].startswith('|')):
            out.append(line)        # a table's rows, and the line after one, stand on their own (52.05 art. 99)
            continue
        # A line ending in dots runs on: the dots stand inside the sentence.
        ended = END.search(out[-1]) and not DOTS.search(out[-1][-10:]) if out else True
        if out and not ended and not ENUM.match(line) and not DOTS.fullmatch(line) \
                and not DOTS.fullmatch(out[-1]) and not line.startswith('-') and not REST.match(line):
            out[-1] = f'{out[-1]} {line}'
        else:
            out.append(line)
    return out


def _key(word: str) -> str:
    return ma_law.fold(re.sub(r'[«»"():،,؛;.!؟?\-–]', '', word))


def _find(needle: list[str], hay: list[str], start: int) -> tuple[int, int, str] | None:
    """Where `needle`'s words stand in `hay` from word `start`: (begin, end, old prefix on the first word). Read
    letter by letter, so words a text layer split or joined («حسبالنوع», «علي هاو») still meet, and marks of
    punctuation are no part of it. A match starting one letter into an old word keeps that letter («و»)."""
    probe = stream(' '.join(needle))
    if not probe:
        return None
    owner: list[int] = []
    chars: list[str] = []
    for i, w in enumerate(hay):
        piece = stream(w)
        chars.append(piece)
        owner.extend([i] * len(piece))
    flat = ''.join(chars)
    offset = sum(len(c) for c in chars[:start])
    at = flat.find(probe, offset)
    if at < 0:
        return None
    begin, last = owner[at], owner[at + len(probe) - 1]
    into = at - sum(len(c) for c in chars[:begin])
    prefix = hay[begin][0] if into == 1 and hay[begin][:1] in PREFIXES else ''
    if into > 1 or (into == 1 and not prefix):
        return None                          # the match starts inside another word: no anchor
    return begin, last + 1, prefix


def _anchor(words: list[str], hay: list[str], start: int, tail: bool) -> tuple[int, int, str] | None:
    """The printed words next to a run of dots found in the old paragraph: three of them, else two, else one long
    word (new wording often ends where an old word begins again)."""
    for n in (ANCHOR, 2, 1):
        probe = words[-n:] if tail else words[:n]
        if n == 1 and len(_key(probe[0])) < 4:
            break
        hit = _find(probe, hay, start)
        if hit:
            return hit
    return None


def _fill_paragraph(template: str, old: str) -> str:
    """One paragraph with runs of dots, its gaps taken from the old paragraph."""
    pieces = [p.split() for p in DOTS.split(template)]
    if not any(_key(w) for w in pieces[0]):
        pieces[0] = []                       # «-……»: the old paragraph's own dash stays
    words = old.split()
    out: list[str] = list(pieces[0])
    cursor = 0
    if pieces[0]:
        hit = _anchor(pieces[0], words, 0, tail=True)
        if not hit:
            raise Unplaced('anchor')
        cursor = hit[1]
    for piece in pieces[1:]:
        if not any(_key(w) for w in piece):
            # The paragraph ends with dots (and perhaps its own «؛»): the old words to its end.
            rest = words[cursor:]
            if piece and rest and re.search(r'[.:؛;،]$', rest[-1]):
                rest[-1] = rest[-1][:-1]
            out.extend([w for w in rest if w] + piece)
            cursor = len(words)
            continue
        hit = _anchor(piece, words, cursor, tail=False)
        if not hit:
            raise Unplaced('anchor')
        begin, _, prefix = hit
        out.extend(words[cursor:begin])
        first = (prefix + piece[0]) if prefix else piece[0]
        out.extend([first] + piece[1:])
        tail = _anchor(piece, words, begin, tail=True)
        cursor = tail[1] if tail else len(words)
    return ' '.join(out)


def _same_start(a: str, b: str) -> bool:
    ea, eb = ENUM.match(a), ENUM.match(b)
    if ea and eb:
        return (ea.group(1) or ea.group(2)) == (eb.group(1) or eb.group(2))
    if ea or eb:
        return False
    ka = [_key(w) for w in DOTS.split(a)[0].split()[:ANCHOR]]
    kb = [_key(w) for w in DOTS.split(b)[0].split()[:ANCHOR]]
    return bool(ka) and ka == kb


def _same_end(a: str, b: str) -> bool:
    """«-…… تلاشيها ؛» is the old paragraph that ends «تلاشيها»."""
    ka = [k for k in (_key(w) for w in DOTS.split(a)[-1].split()) if k][-ANCHOR:]
    kb = [k for k in (_key(w) for w in b.split()) if k][-len(ka):] if ka else []
    return bool(ka) and ka == kb


def fill(template_lines: list[str], old_body: str) -> tuple[str, int]:
    """The article as the amendment leaves it, and how many old paragraphs it dropped without dots for them."""
    template = paragraphs('\n'.join(template_lines))
    old = paragraphs(old_body)
    out: list[str] = []
    j = 0
    dropped = 0
    keep_gap = False                         # a line of dots stands before this paragraph
    for t in template:
        if DOTS.fullmatch(t.strip()) or not DOTS.sub('', t).strip() or REST.match(t):
            keep_gap = True
            continue
        k = next((i for i in range(j, len(old)) if _same_start(t, old[i])), None)
        if k is None and DOTS.search(t):
            k = next((i for i in range(j, len(old)) if _same_end(t, old[i])), None)
        if k is None and keep_gap and DOTS.match(t):
            raise Unplaced('paragraph')
        if k is None:
            if DOTS.search(t):
                if j < len(old) and not keep_gap:
                    k = j                    # the next paragraph, changed from its first words
                else:
                    raise Unplaced('paragraph')
            else:
                out.append(t)                # a paragraph the amendment adds
                keep_gap = False
                continue
        if keep_gap:
            out.extend(old[j:k])
        else:
            dropped += k - j                 # paragraphs between were left out: the amendment drops them
        out.append(_fill_paragraph(t, old[k]) if DOTS.search(t) else t)
        j = k + 1
        keep_gap = False
    if keep_gap:
        out.extend(old[j:])
    else:
        dropped += len(old) - j
    return '\n'.join(out), dropped


def words_replaced(body: str, pairs: list[tuple[str, str]]) -> tuple[str, int]:
    """«تحل عبارة … محل عبارة …»: each old phrase put as the new one, wherever it stands (folded match)."""
    count = 0
    for old, new in pairs:
        pattern = r'\s+'.join(re.escape(w) for w in old.split())
        body, n = re.subn(pattern, new, body)
        count += n
    return body, count


def likeness(a: str, b: str) -> float:
    """How alike two wordings are, word by word, after folding (1.0 the same)."""
    ka = [_key(w) for w in a.split() if _key(w)]
    kb = [_key(w) for w in b.split() if _key(w)]
    if not ka and not kb:
        return 1.0
    return SequenceMatcher(None, ka, kb, autojunk=False).ratio()


def stream(text: str) -> str:
    """Letters only, folded, with the pairs a text layer may give either way made one («لا»/«ال»): for checking
    a wording against the SGG's text, whose layer splits and joins words («فيديو غرامات»)."""
    folded = ma_law.fold(text)
    folded = re.sub(r'[^\u0621-\u064A0-9A-Za-z]', '', folded)
    return folded.replace('لا', 'ال').replace('لم', 'مل')


def fragments_found(template_lines: list[str], body: str) -> float:
    """The share of the wording's printed stretches (three words or more) that stand, in order, in `body`: how a
    later consolidation agrees with our reading of an amendment when the old article is not in the corpus."""
    hay = stream(body)
    stretches = [p for line in template_lines for p in DOTS.split(line) if len(p.split()) >= ANCHOR]
    if not stretches:
        return 1.0
    found, cursor = 0, 0
    for s in stretches:
        probe = stream(' '.join(s.split()[:8]))
        at = hay.find(probe, cursor)
        if at < 0:
            at = hay.find(probe)
        if at >= 0:
            found += 1
            cursor = at + len(probe)
    return found / len(stretches)
