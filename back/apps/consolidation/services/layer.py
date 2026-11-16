"""The SGG's PDFs carry a text layer in reading order, but their fonts draw some letter pairs as one ligature and the
layer gives that pair back reversed: «الأمانة» comes out «األمانة», «المنتج» «املنتج», «لإنجاز» «إلنجاز», «ولا»
«وال»; the guillemets come out mirrored (» … «). A word the corpus never uses is put right by turning such pairs
back until it reads as a word the corpus uses; a word the corpus knows is left alone unless the turned form is far
more common («وال» → «ولا»). The corpus's words come from the BO pages read by the OCR, not from any text layer.

Nothing here invents a word: a word that no turn makes known stays as it came and is counted, so each page says
how much of it is still unknown."""
import json
import math
import re
from collections import Counter
from functools import lru_cache
from itertools import pairwise, product
from pathlib import Path

from django.conf import settings

TASHKEEL = re.compile('[ً-ْٰـ]')
WORD = re.compile(r'[ء-يٱ-ۓ]+')
# The pairs a ligature reverses: lam then alef (any hamza), lam then meem, jeem, hah, khah.
PAIRS = {'ال': 'لا', 'أل': 'لأ', 'إل': 'لإ', 'آل': 'لآ', 'مل': 'لم', 'جل': 'لج', 'حل': 'لح', 'خل': 'لخ'}
TURN = re.compile('|'.join(PAIRS))
# The second font (Adobe Arabic, the SGG's notes and some texts) reverses these too: «الظهري» is «الظهير», «مبوجب»
# «بموجب», «الرشيف» «الشريف», «فرباير» «فبراير», «حامية» «حماية», «يف» «في», «الثاين» «الثاني», «عىل» «على»,
# «التخيل» «التخلي», «الرتخيص» «الترخيص», «البرصية» «البصرية», «القايض» «القاضي». Tried only on a word the
# corpus does not know (these pairs are common in correct words).
SECOND = {'ري', 'مب', 'رش', 'رب', 'ام', 'يف', 'ين', 'ىل', 'يل', 'رت', 'رص', 'يض', 'نه', 'از', 'مت', 'ىض'}
SECOND_TURN = re.compile('|'.join(SECOND))
PERSIAN = str.maketrans({'ھ': 'ه', 'ی': 'ي', 'ک': 'ك', 'ە': 'ه'})
SHORT = {'في', 'من', 'أو', 'لا', 'ما', 'عن', 'إن', 'أن', 'لم', 'لن', 'قد', 'هو', 'هي', 'بل', 'كل', 'إذ', 'ثم', 'مع', 'كما'}
COMMON = 20          # a known word gives way to a turned form this many times more common
SWAP_MIN = 5         # an unknown word takes a swapped form the corpus uses at least this often
LEXICON = 'derived/lexicon.json'
# The article before a ligature is certain: a word never begins «امل», «اال», «األ», «اإل», «اآل» («املقرض» is
# «المقرض» even when the corpus has never printed it).
ARTICLE = re.compile(r'^((?:و|ف|ب|ك)?)ا(مل|ال|أل|إل|آل)')
# The SGG's own notes use words the BO rarely prints: known, so they are left as they read.
NOTES = ('غيرت', 'وغيرت', 'تممت', 'وتممت', 'تمم', 'وتمم', 'نسخت', 'ونسخت', 'عوضت', 'وعوضت', 'أضيفت', 'وأضيفت',
         'موطدة', 'صيغتها', 'مقروئية', 'يحتج', 'المنشورة')


def build_lexicon(bodies) -> Counter:
    counts: Counter = Counter()
    for body in bodies:
        counts.update(WORD.findall(TASHKEEL.sub('', body)))
    return counts


def save_lexicon(counts: Counter) -> Path:
    path = Path(settings.CORPUS_DIR) / LEXICON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(counts), ensure_ascii=False))
    return path


@lru_cache(maxsize=1)
def lexicon() -> dict[str, int]:
    path = Path(settings.CORPUS_DIR) / LEXICON
    words = json.loads(path.read_text()) if path.exists() else {}
    for w in NOTES:
        words.setdefault(w, 100)
    return words


def _turns(word: str):
    """Every way of turning back some of the word's suspect pairs (at most 6 places: 64 forms)."""
    spots = list(TURN.finditer(word))[:6]
    for choice in product((False, True), repeat=len(spots)):
        if not any(choice):
            continue
        out, last = [], 0
        for m, turn in zip(spots, choice):
            out.append(word[last:m.start()])
            out.append(PAIRS[m.group(0)] if turn else m.group(0))
            last = m.end()
        out.append(word[last:])
        yield ''.join(out)


# A word's stems for the turn test: the word with a conjunction, a preposition or the article off its front and a
# pronoun or an ending off its back, every way it can be cut («وبخلافه» → «خلاف», «يتحملان» → «يتحمل»).
FRONTS = ('', 'و', 'ف', 'ب', 'ل', 'ك', 'لل', 'ال', 'وال', 'فال', 'بال', 'كال', 'ولل', 'وب', 'ول', 'فب', 'فل')
BACKS = ('', 'ه', 'ها', 'هم', 'هما', 'ة', 'ا', 'ات', 'ان', 'ين', 'ون', 'ي', 'كم', 'نا')


def _unstretched(word: str):
    """The word with each run of «م» cut to one or to none (at most 4 runs: 81 forms), never the word itself."""
    # A run opening the word after its front is the word's own letters, whatever its length: a stretching stroke joins
    # two letters and never comes first («المرهون»; «ممنوع» was cut to «نوع», 1962 constitution's art. 3).
    # Nor after the last letter: a run that ends the word keeps one «م» («الرسممم» → «الرسم», never «مجموعتهم» →
    # «مجموعته»).
    runs = [m for m in re.finditer('م+', word) if word[:m.start()] not in FRONTS][:4]
    for choice in product(*[(m.group(0), 'م') if m.end() == len(word) else (m.group(0), 'م', '') for m in runs]):
        out, last = [], 0
        for m, keep in zip(runs, choice):
            out.append(word[last:m.start()] + keep)
            last = m.end()
        form = ''.join(out) + word[last:]
        if form != word and len(form) >= 2:
            yield form


def _stem_count(word: str, words: dict[str, int]) -> int:
    return max((words.get(word[len(f):len(word) - len(b)], 0) for f in FRONTS if word.startswith(f)
                for b in BACKS if word.endswith(b) and len(word) - len(f) - len(b) >= 3), default=0)


def _swaps(word: str, most: int = 3):
    """The word with up to `most` of the second font's pairs turned back, none overlapping."""
    spots = [m.start() for m in SECOND_TURN.finditer(word)]
    spots += [i for i in range(len(word) - 1) if word[i:i + 2] in SECOND and i not in spots]
    spots = sorted(set(spots))[:8]
    for choice in product((False, True), repeat=len(spots)):
        picked = [i for i, on in zip(spots, choice) if on]
        if not picked or len(picked) > most or any(b - a < 2 for a, b in pairwise(picked)):
            continue
        chars = list(word)
        for i in picked:
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
        yield ''.join(chars)


def segment(token: str, words: dict[str, int]) -> str | None:
    """A run of words the layer printed without spaces («علىموافقةالشخصاملزمعمشاركته») cut into the likeliest
    words, each repaired; None unless every piece but one short stretch is a known word."""
    total = sum(words.values()) or 1
    n = len(token)
    best: list[tuple[float, list[str], int] | None] = [None] * (n + 1)
    best[0] = (0.0, [], 0)
    for i in range(n):
        if best[i] is None:
            continue
        score, pieces, unknown = best[i]
        for j in range(i + 1, min(n, i + 16) + 1):
            fixed, known = _repair_one(token[i:j], words)
            if len(fixed) <= 2 and fixed not in SHORT:
                continue         # «ها», «ين», «و» are never a word of their own
            if known and words.get(fixed, 0) < 3:
                known = False    # a word read once may be the OCR's slip: no ground to cut on
            if known:
                s = math.log(max(words.get(fixed, 1), 1) / total)
                u = 0
            elif j - i >= 3:
                s, u = -8.0 * (j - i), j - i
            else:
                continue
            cand = (score + s, pieces + [fixed], unknown + u)
            if best[j] is None or cand[0] > best[j][0]:
                best[j] = cand
    if best[n] is None:
        return None
    _, pieces, unknown = best[n]
    if len(pieces) < 2 or unknown > 6:
        return None
    return ' '.join(pieces)


def repair_word(word: str, words: dict[str, int]) -> tuple[str, bool]:
    """(the word as it should read, whether it is known); a run of words with no spaces is cut."""
    out, known = _repair_one(word, words)
    # A word whose stem the corpus knows is one word, its pronoun kept on it («لتاريخهما», not «لتاريخ هما»); and a word
    # turned back on its stem stays whole («الختيارها» is «لاختيارها», not «الخ تيارها»: the 2011 constitution).
    if not known and out == TASHKEEL.sub('', word) and len(word) >= 9 and _stem_count(TASHKEEL.sub('', word), words) < 2:
        cut = segment(TASHKEEL.sub('', word), words)
        if cut:
            return cut, True
    return out, known


def _repair_one(word: str, words: dict[str, int]) -> tuple[str, bool]:
    bare = TASHKEEL.sub('', word)
    if 'هلل' in bare and not words.get(bare):
        # The «لله» ligature comes out backwards: «الحمد هلل», «شعار المملكة: هللا، الوطن، الملك» (Adala's constitutions).
        for form in (re.sub(r'هللا$', 'الله', bare), bare.replace('هلل', 'لله')):
            if form != bare and words.get(form):
                return form, True
    seen = words.get(bare, 0)
    best, best_n = bare, seen
    lam = list(_turns(bare)) if TURN.search(bare) else []
    for form in lam:
        n = words.get(form, 0)
        if n > best_n:
            best, best_n = form, n
    if best is not bare and seen and best_n < COMMON * seen:
        best, best_n = bare, seen
    if not best_n and 2 <= len(bare) <= 16:
        # Unknown either way: the second font's pairs too, on the word and on each lam turn («األوىل» → «الأولى»),
        # kept only when the corpus uses the result a few times.
        for base in [bare] + lam[:16]:
            for form in _swaps(base):
                n = words.get(form, 0)
                if n >= SWAP_MIN and n > best_n:
                    best, best_n = form, n
    if not best_n and 'م' in bare and _stem_count(bare, words) < 2:
        # Adala's Word files print the stretching stroke (kashida) as «م»: «الرسممم», «اسمترجاع الأقسماط»,
        # «بالنسمممممبة» are «الرسم», «استرجاع الأقساط», «بالنسبة» (H1 of the housing plan). Not where the word's own
        # stem is known: «بالممثل», «توقيعهما» are right.
        n, form = max(((words.get(f, 0), f) for f in _unstretched(bare)), default=(0, bare))
        if n >= 2:
            return form, True
    if not best_n and lam:
        # Unknown either way: the turn whose stems the corpus knows well, better than the printed word's
        # («يتحمالن» → «يتحملان» on «يتحمل», «بخالفه» → «بخلافه» on «خلاف»): the DOC's old words, H1 of the housing
        # plan, are rarely in the lexicon whole.
        own = _stem_count(bare, words)
        n, form = max((_stem_count(form, words), form) for form in lam)
        if n >= 2 and n >= 3 * own:
            return form, False
    if not best_n and 'ص' in bare:
        # Adala's road decrees print the ligature «طع» as «ص»: «تقاصا», «التقاصات» are «تقاطعا», «التقاطعات».
        n, form = max(((words.get(f, 0), f) for f in (bare[:i] + 'طع' + bare[i + 1:]
                                                      for i, ch in enumerate(bare) if ch == 'ص')), default=(0, bare))
        if n >= 3:
            return form, True
    if not best_n and ARTICLE.match(bare):
        # Put right, though still a word the corpus does not know.
        return ARTICLE.sub(lambda m: f'{m.group(1)}ا{PAIRS[m.group(2)]}', bare), False
    return (best if best is not bare else word), best_n > 0


JOIN_MIN = 5          # a split word is joined only into one the corpus prints at least this often
PIECE = re.compile(r'^[ء-يٱ-ۓً-ْٰـ]+$')


def join_split(line: str, words: dict[str, int], stats: dict | None = None) -> str:
    """Words the layer cut with spaces put back together: «الطر ف» → «الطرف», «ي م كن» → «يمكن», «لأل ج ي ر» →
    «للأجير» (the labour code's file, T1 of the work plan). Up to four pieces are joined when one of them is a stray
    letter or a word the corpus never prints, and the whole, as repaired, is a word it prints JOIN_MIN times."""
    tokens = line.split(' ')
    out, i = [], 0
    while i < len(tokens):
        for size in (4, 3, 2):
            pieces = tokens[i:i + size]
            if len(pieces) < size:
                continue
            # The first piece may open with a mark («(», «»») and the last close with one («.», «،»).
            lead = re.match(r'^[^ء-يٱ-ۓ]*', pieces[0]).group(0)
            trail = re.search(r'[^ء-يٱ-ۓً-ْٰـ]*$', pieces[-1]).group(0)
            pieces = [pieces[0][len(lead):]] + pieces[1:-1] + [pieces[-1][:len(pieces[-1]) - len(trail)]]
            if not all(PIECE.match(p) for p in pieces):
                continue
            stray = any(len(TASHKEEL.sub('', p)) == 1 or not words.get(TASHKEEL.sub('', p)) for p in pieces)
            whole, known = _repair_one(''.join(pieces), words)
            if stray and known and words.get(TASHKEEL.sub('', whole), 0) >= JOIN_MIN:
                out.append(lead + whole + trail)
                i += size
                if stats is not None:
                    stats['joined'] = stats.get('joined', 0) + size - 1
                break
        else:
            out.append(tokens[i])
            i += 1
    return ' '.join(out)


# A turned lam-alif that makes another real word, put right by the words around it: Adala's 18.00 prints «الملاك»
# as «المالك» (an owner) 100 times over, «جميع المالك المشتركين» (H2 of the housing plan).
PHRASES = [
    (re.compile(r'(?<![ء-ي])(ال|لل|وال|بال|مال)مالك(?=\s+(?:ال)?مشترك(?:ين|ون)(?![ء-ي]))'), r'\1ملاك'),
    (re.compile(r'(?<![ء-ي])(جميع|لجميع|ولجميع|مجموع|كافة|لكافة|أحد|بعض|باقي|لباقي|هؤلاء|أغلبية|ثلث|نصف|أرباع|إجماع|بإجماع|'
                r'اتحاد|لاتحاد|واتحاد|اتحادات)(\s+)(ال)?مالك(?![ء-ي])'), r'\1\2\3ملاك'),
    (re.compile(r'(?<![ء-ي])مالك(?=\s+مشترك(?:ين|ون)(?![ء-ي]))'), 'ملاك'),
    (re.compile(r'(?<![ء-ي])على(\s+)خالف(\s+)ذلك'), r'على\1خلاف\2ذلك'),
    # «ثالثة أشهر» (third) for «ثلاثة أشهر» (three): 67.12 art 74, 18.00 art 16 مكرر 4.
    (re.compile(r'(?<![ء-ي])ثالثة(?=\s+(?:[()]\d+[()]\s*)?(?:أشهر|أيام|أسابيع|سنوات|أعوام)(?![ء-ي]))'), 'ثلاثة'),
    (re.compile(r'(?<![ء-ي])ثالث(?=\s+(?:[()]\d+[()]\s*)?(?:سنوات|ساعات|مرات)(?![ء-ي]))'), 'ثلاث'),
    # 67.12 art 54's «في حالة طالق الزوجين» (a divorced woman) for «طلاق» (a divorce).
    (re.compile(r'(?<![ء-ي])(حالة|بعد|عند)(\s+)طالق(?=\s+الزوج)'), r'\1\2طلاق'),
    # 67.12's «يعتبر محتال دون حق ولا سند» (an occupant, «محتلا») and «وصال موقعا» (a receipt, «وصلا»).
    (re.compile(r'(?<![ء-ي])محتال(?=\s+(?:للمحل\s+)?(?:دون|بدون|بغير)\s+(?:حق|سند))'), 'محتلا'),
    (re.compile(r'(?<![ء-ي])وصال(?=\s+(?:موقعا|مكتوبا|يتضمن|بذلك))'), 'وصلا'),
]


def repair(text: str, words: dict[str, int] | None = None) -> tuple[str, dict]:
    """The layer's text put right, and {words, turned, unknown}."""
    words = lexicon() if words is None else words
    stats = {'words': 0, 'turned': 0, 'unknown': 0}

    def fix(m: re.Match) -> str:
        stats['words'] += 1
        out, known = repair_word(m.group(0), words)
        stats['turned'] += out != m.group(0)
        stats['unknown'] += not known
        return out

    # A stray replacement mark splits some words («القا�ضي»); the layer's no-break spaces and carriage returns go.
    text = text.replace('\ufffd', '').replace('\xa0', ' ').replace('\r', '').translate(PERSIAN)
    text = '\n'.join(join_split(line, words, stats) for line in text.split('\n'))
    text = WORD.sub(fix, text)
    for wrong, right in PHRASES:
        text, n = wrong.subn(right, text)
        stats['turned'] += n
    # The guillemets and parentheses come out mirrored.
    text = text.translate(str.maketrans('«»()', '»«)('))
    # …except around Latin letters, which the layer gave the right way round: «(AM (» is «(AM)».
    text = re.sub(r'\(\s*([A-Za-z0-9][A-Za-z0-9 .\-]*?)\s*\(', r'(\1)', text)
    return text, stats


# The files whose own text layer becomes a version's articles: their pages are shown as the articles read them.
REPAIRED_SOURCES = ('adala', 'sgg_consolidated', 'dgi')


def page_text(page) -> tuple[str, bool]:
    """(a page's text as readers see it, whether it was put right): the text layer of an Adala or SGG file after the
    repairs its articles had (P14 of the polish review: «العالقات», «األول» on the page a reader opens to check
    «العلاقات», «الأول»); any other page as it was read."""
    if page.text and page.text_source == 'layer' and page.document.source in REPAIRED_SOURCES \
            and page.document.language == 'ar':
        return repair(page.text)[0], True
    return page.text, False
