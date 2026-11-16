"""The proofreader (R7 of the for-everyone review): finds in Adala's and the SGG's texts the words their PDFs' ligatures
turned round and the loader could not put right («لإلثبات» for «للإثبات», «ألوالدها» for «لأولادها»), and proposes each
fix for a person to confirm. It never applies one.

The measure is the BO as the OCR read it (the texts as published), not the loader's lexicon: a word the BO never
prints that turns into one it prints at least RIGHT_MIN times («ألم الأم» → «لأم الأم»); or a word the BO prints less often than its turned form,
whose pairs with its neighbours the BO never prints while it prints the turned pairs at least PAIR_MIN times
(«ثالثة أشهر» → «ثلاثة أشهر», «العالقة الزوجية» → «العلاقة الزوجية»; not «من المحل» → «من الملح»). Words drawn out with
a tatweel («فـي») are the printer's style, not an error.

`split` (N3 of the read-and-trusted review, 27 Oct 2026): Adala's PDFs break a word where their layer breaks a run of
letters, so the Labour Code's art. 66 read «وتو ابعها», «اعتي اديا», «النقابي ين». Two pieces the BO hardly prints (the
second may be one or two letters), with one space between them, that join into a word the BO prints SPLIT_MIN times or
more, are proposed joined, the lam-alef the layer turned in them put back («الاستغ الالت» → «الاستغلالات»). A word cut
in three («أن ي زو دهم») is not found: read on the page."""
import re
from collections import Counter
from itertools import pairwise

from apps.consolidation.services.layer import TURN, _turns
from apps.corpus.models import Article, Consolidation
from apps.corpus.services.addresses import article_path
from apps.quality.models import Correction

WORD = re.compile(r'[ء-يٱ-ۓ]+')
RIGHT_MIN = 3
PAIR_MIN = 2
CHECKED = (Consolidation.ADALA, Consolidation.SGG)
SPLIT_MIN = 5
PIECE_MAX = 2
SPLIT_CHECKED = (Consolidation.ADALA, Consolidation.SGG, Consolidation.DGI)


def printed_words() -> Counter:
    """How often the BO prints each word, as the OCR read it."""
    counts: Counter = Counter()
    rows = Article.objects.filter(version__consolidation=Consolidation.AS_PUBLISHED, version__language='ar')
    for body in rows.values_list('body', flat=True).iterator(chunk_size=2000):
        counts.update(WORD.findall(body))
    return counts


def _pairs_printed(wanted: set[tuple[str, str]]) -> Counter:
    counts: Counter = Counter()
    rows = Article.objects.filter(version__consolidation=Consolidation.AS_PUBLISHED, version__language='ar')
    for body in rows.values_list('body', flat=True).iterator(chunk_size=2000):
        words = WORD.findall(body)
        for pair in pairwise(words):
            if pair in wanted:
                counts[pair] += 1
    return counts


def suggest(words: Counter | None = None, consolidations=CHECKED) -> int:
    """Proposes what it finds; what was proposed before (applied or set aside) is not proposed again."""
    words = printed_words() if words is None else words
    found: dict[tuple, dict] = {}
    context: list[tuple] = []
    rows = (Article.objects.filter(version__consolidation__in=consolidations, version__language='ar')
            .values_list('version__text__akn_uri', 'eid', 'body'))
    for uri, eid, body in rows.iterator(chunk_size=500):
        tokens = WORD.findall(body)
        for i, w in enumerate(tokens):
            if len(w) < 3 or not TURN.search(w):
                continue
            before, after = (tokens[i - 1] if i else ''), (tokens[i + 1] if i + 1 < len(tokens) else '')
            turned = max(_turns(w), key=lambda f: words.get(f, 0))
            n = words.get(turned, 0)
            if not words.get(w) and n >= RIGHT_MIN:
                found[(article_path(uri, eid), w, before, after)] = {
                    'right': turned, 'source': Correction.Source.PROOFREAD, 'evidence': {'wrong': 0, 'right': n}}
            elif words.get(w) and n >= RIGHT_MIN and n >= words[w]:
                context.append((article_path(uri, eid), w, before, after, turned))
    if context:
        wanted = {p for _, w, b, a, f in context for p in ((b, w), (w, a), (b, f), (f, a))}
        pairs = _pairs_printed(wanted)
        for path, w, b, a, f in context:
            as_is = pairs[(b, w)] + pairs[(w, a)]
            turned = pairs[(b, f)] + pairs[(f, a)]
            if not as_is and turned >= PAIR_MIN:
                found[(path, w, b, a)] = {'right': f, 'source': Correction.Source.CONTEXT,
                                          'evidence': {'wrong': 0, 'right': turned, 'pair': True}}
    known = set(Correction.objects.values_list('path', 'wrong', 'before', 'after'))
    new = [Correction(path=p, wrong=w, before=b, after=a, **v) for (p, w, b, a), v in found.items()
           if (p, w, b, a) not in known]
    Correction.objects.bulk_create(new, ignore_conflicts=True)
    return len(new)


def splits(words: Counter, consolidations=SPLIT_CHECKED, paths: set[str] | None = None):
    """Each word cut in two, as (article path, «a b», word before, word after, joined, how often the BO prints it)."""
    rows = (Article.objects.filter(version__consolidation__in=consolidations, version__language='ar')
            .values_list('version__text__akn_uri', 'eid', 'body'))
    for uri, eid, body in rows.iterator(chunk_size=500):
        path = article_path(uri, eid)
        if paths is not None and path not in paths:
            continue
        tokens = WORD.findall(body)
        for i, (a, b) in enumerate(pairwise(tokens)):
            if words.get(a, 0) > PIECE_MAX or (words.get(b, 0) > PIECE_MAX and len(b) > 2):
                continue
            joined = a + b
            # The layer may also have turned a lam-alef in it («الاستغ الالت» is «الاستغلالات»).
            if words.get(joined, 0) < SPLIT_MIN and TURN.search(joined):
                joined = max(_turns(joined), key=lambda f: words.get(f, 0))
            n = words.get(joined, 0)
            if n < SPLIT_MIN:
                continue
            # One space between them, nothing else: never two words a line, a comma or a number keeps apart.
            if not re.search(rf'(?<![ء-ي]){a} {b}(?![ء-ي])', body):
                continue
            yield path, f'{a} {b}', tokens[i - 1] if i else '', tokens[i + 2] if i + 2 < len(tokens) else '', joined, n


def split(words: Counter | None = None, consolidations=SPLIT_CHECKED) -> int:
    """Proposes each word cut in two, joined (never applied here); what was proposed before is not proposed again."""
    words = printed_words() if words is None else words
    found = {(p, w, b, a): {'right': j, 'source': Correction.Source.SPLIT, 'evidence': {'wrong': 0, 'right': n}}
             for p, w, b, a, j, n in splits(words, consolidations)}
    known = set(Correction.objects.values_list('path', 'wrong', 'before', 'after'))
    new = [Correction(path=p, wrong=w, before=b, after=a, **v) for (p, w, b, a), v in found.items()
           if (p, w, b, a) not in known]
    Correction.objects.bulk_create(new, ignore_conflicts=True)
    return len(new)
