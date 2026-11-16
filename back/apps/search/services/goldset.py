"""The search measured: each question of a set must bring back its expected text, article or issue (or any of a
list of them) in the top 3 (the citation card counts as first), and is counted apart when it comes first. Run by
`manage.py search_eval`; the bar before launch is 8 in 10.

B1 of the search plan (24 Oct 2026): the sets written with today's rules (seed, everyday, work, housing, road,
consumer) are tuning questions, split once and for all into `tune` (3 in 4) and `dev` (1 in 4) by a hash of the
question; the `test` set (goldset/test.json) holds new questions only, and only its totals are ever shown. Every
question carries its segment: the register it is written in and what it asks for."""
import hashlib
import json
import re
from pathlib import Path

import ma_law

from apps.search.services.search.asking import ASKING
from apps.search.services.search.query import search, shown_paths
from apps.topics.services import kit

DIR = Path(__file__).resolve().parent.parent / 'goldset'
SEED = DIR / 'seed.json'
TEST = DIR / 'test.json'
TOP = 3

REGISTERS = ('msa', 'darija', 'darija_latin', 'french', 'english', 'professional')
INTENTS = ('citation', 'name', 'number', 'procedure', 'definition', 'question', 'words')

# The sets' own labels, as their authors wrote them.
LABELS = {'darija': 'darija', 'arabic': 'msa', 'msa': 'msa', 'french': 'french', 'fr': 'french', 'arabizi': 'darija_latin',
          'darija-latin': 'darija_latin', 'darija_latin': 'darija_latin', 'english': 'english', 'en': 'english',
          'professional': 'professional'}

# Words only Darija uses (folded), and Darija typed in Latin letters: a digit for a letter («3la», «9anoun»), or its
# common words.
DARIJA = frozenset(ma_law.fold(w) for w in """
واش شنو شنا شحال كيفاش علاش فين منين إمتى امتى ديال ديالي ديالو باش بغيت خاصني خصني عندي دابا كاين كاينة ماشي بزاف
واقيلا مول مولات الباطرون حيت غادي كنقدر نقدر يقدر كيقول كيخلص خدام خدمة الخدمة شي حتى لا ليا ليه ليها بلا
""".split())
LATIN_DARIJA = re.compile(r"\b(wach|wash|chno|chnou|ch7al|chhal|kifach|kifash|3la|3lach|bghit|dyal|dial|f(?:l|ch)|l9anoun|"
                          r"9anoun|kayn|kayna|machi|bzaf|daba|ila|chi|7ta|m3a|3and|3ndi|khas|khassni|mol|lmo[o]?l)\b|[a-z][2-9][a-z]|\b[2-9][a-z]{2,}",
                          re.IGNORECASE)
ENGLISH = re.compile(r"\b(what|how|the|is|are|does|can|my|law|in morocco|which|who|when|should|must|rights?)\b", re.IGNORECASE)

NUMBER = re.compile(r"شحال|كم |\bكم\b|combien|how (?:much|many|long)|ch7al|chhal|quel (?:délai|montant)|quelle durée", re.IGNORECASE)
PROCEDURE = re.compile(r"كيفاش|\bكيف\b|comment|how (?:do|to|can|should)|kifach|kifash|procédure|مسطرة|الإجراءات", re.IGNORECASE)
DEFINITION = re.compile(r"ما معنى|شنو معنى|ما هو|ما هي|شنو هو|شنو هي|c'?est quoi|qu'?est[- ]ce qu|définition|what (?:is|does)|"
                        r"meaning of|chno howa|chno hiya", re.IGNORECASE)


def split_of(question: str) -> str:
    """`dev` for one tuning question in four, `tune` for the rest, the same on every machine and every run."""
    digest = hashlib.sha1(ma_law.fold(question).encode(), usedforsecurity=False).hexdigest()
    return 'dev' if int(digest[:8], 16) % 4 == 0 else 'tune'


def register_of(item: dict) -> str:
    """The register a question is written in: the set's own label, else read from its letters and words."""
    if item.get('register') in REGISTERS:
        return item['register']
    if LABELS.get(item.get('lang') or ''):
        return LABELS[item['lang']]
    q = item['q']
    if not re.search(r'[؀-ۿ]', q):
        if LATIN_DARIJA.search(q):
            return 'darija_latin'
        return 'english' if len(ENGLISH.findall(q)) >= 2 else 'french'
    return 'darija' if any(w in DARIJA for w in ma_law.tokens(q)) else 'msa'


def intent_of(q: str) -> str:
    """What a question asks for, read from its own words; the first that fits."""
    from apps.corpus.services.codes import code_named

    cites = ma_law.parse_query(q)
    if any(c.get('article') or c.get('issue') or c.get('text_number') for c in cites):
        return 'citation'
    named = code_named(q)
    if named and ma_law.fold(named[1]) == ma_law.fold(q):
        return 'name'
    if NUMBER.search(q):
        return 'number'
    if DEFINITION.search(q):
        return 'definition'
    if PROCEDURE.search(q):
        return 'procedure'
    if '?' in q or '؟' in q or any(t in ASKING for t in ma_law.tokens(q)):
        return 'question'
    return 'words'


def sets() -> list[Path]:
    """The tuning sets, in name order (the test set apart)."""
    return sorted(p for p in DIR.glob('*.json') if p != TEST)


def _paths(result: dict) -> list[str]:
    """What a search answered, best first: the citation card, a famous article's card, then each text and its articles."""
    out = []
    jump = result.get('jump') or {}
    for key in ('article', 'text', 'issue'):
        if jump.get(key):
            out.append(jump[key]['path'])
    out += [c['path'] for c in result.get('famous') or []]
    for r in result['results'][:TOP]:
        out.append(r['text']['path'])
        out.extend(a['path'] for a in r['articles'])
    return out


def _first(result: dict) -> list[str]:
    """What a reader meets first: the citation card, else a famous article's card, else the first text and its first
    article."""
    jump = result.get('jump') or {}
    shown = [jump[key]['path'] for key in ('article', 'text', 'issue') if jump.get(key)] or \
        [c['path'] for c in (result.get('famous') or [])[:1]]
    if shown or not result['results']:
        return shown
    top = result['results'][0]
    return [top['text']['path'], *(a['path'] for a in top['articles'][:1])]


def evaluate(path: Path = SEED, split: str | None = None) -> dict:
    """Each question searched as a reader would; `split` keeps only that split's questions (`tune`, `dev`)."""
    data = json.loads(path.read_text())
    is_test = path == TEST
    rows = []
    for item in data['questions']:
        part = 'test' if is_test else split_of(item['q'])
        if split and part != split:
            continue
        r = search(item['q'], log=False)
        answered = _paths(r)
        expect = item['expect'] if isinstance(item['expect'], list) else [item['expect']]
        first = False
        if expect[0].startswith('missing:'):
            # A code not held here yet: the answer says so first.
            jump = r.get('jump') or {}
            hit = first = jump.get('state') == 'not_in_corpus' and (jump.get('citation') or {}).get('code') == expect[0][8:]
        else:
            right = lambda paths: any(p == e or p.startswith(e + '/') for p in paths for e in expect)  # noqa: B023 (called in this iteration)
            hit, first = right(answered), right(_first(r))
        # A door shown above the texts (X1) that leads to a journey or page citing the expected article answers the
        # question too, and first: it is what the reader meets. Counted apart, so the texts' own rate stays readable.
        door = False
        if not expect[0].startswith('missing:'):
            for d in kit.matching(r.get('arabizi') or item['q'])[:2]:
                if right(sorted(kit.door_cites(d['topic'], d['ref']))):
                    door = True
                    break
        rows.append({**item, 'hit': hit or door, 'first': first or door, 'by_door': door and not hit,
                     'understood_as': r['understood_as'], 'top': answered[:4], 'shown': shown_paths(r),
                     'split': part, 'register': register_of(item), 'intent': item.get('intent') or intent_of(item['q'])})
    hits = sum(r['hit'] for r in rows)
    firsts = sum(r['first'] for r in rows)
    return {'questions': len(rows), 'hits': hits, 'rate': round(hits / len(rows), 3) if rows else 0.0,
            'first': firsts, 'by_door': sum(r['by_door'] for r in rows), 'rows': rows}


def by_segment(rows: list[dict], key: str) -> dict[str, dict]:
    """{segment: {questions, hits, first, by_door}} for `key` (register, intent, split or set)."""
    out: dict[str, dict] = {}
    for r in rows:
        s = out.setdefault(r.get(key) or '-', {'questions': 0, 'hits': 0, 'first': 0, 'by_door': 0})
        s['questions'] += 1
        s['hits'] += r['hit']
        s['first'] += r['first']
        s['by_door'] += r['by_door']
    return dict(sorted(out.items()))
