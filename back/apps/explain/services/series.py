"""The Bulletin's series (/new, 1 Nov 2026): most of a week is texts of one form printed one after another, twenty decrees
«يتعلق باختصاصات وزير …», twenty-two decisions of the Competition Council «المتعلق بتولي …», fourteen «بتفويض الإمضاء».
Listed one by one they drowned the rest; folded, a series is one bundle whose shared words are said once and whose members
are named by what differs. Read from the titles by code alone: nothing is ranked, nothing is summarised, every member keeps
its own address.

A title is its kind word («مرسوم», «قرار مشترك»), who issued it («لوزير الفلاحة …», often left out after the first of a
run, as the Bulletin prints them) and its act, from the first word that says what it does («بتحديد», «يتعلق», «يقضي»).
Texts share a series when their kind and the act's first two words are the same; the general section folds only a long
series or one whose act shares four words, so that three unrelated «مرسوم بتغيير المرسوم …» keep their own rows."""
import re
from collections import Counter

# What a title holds that is never shared: its number and its dates.
NUMBER = re.compile(r'(?:رقم|عدد)\s+[\d./\-]+(?:ق/\d+)?')
DATE = re.compile(r'(?:ال)?(?:صادر(?:ة)?|المؤرخ(?:ة)?)\s+(?:في|بتاريخ)\s+[^()]{0,60}\([^)]*\)'
                  r'|بتاريخ\s+[^()]{0,60}\([^)]*\)|\((?:فاتح|\d{1,2})\s+\S+\s+\d{4}\)')
MARKS = re.compile(r'[«»"()،,؛:.]')
# The first word of the act: a verbal noun after «ب», or a verb the Bulletin opens an act with.
ACT = re.compile(r'^(?:ب\S+|يتعلق|تتعلق|المتعلق|المتعلقة|يقضي|يقضيان|القاضي|يرخص|ترخص|يتضمن|يحدد|يغير|يتمم|ينسخ|يعين)$')
# «للسيدة» and «للسيد» license the same way.
SAME = {'للسيدة': 'للسيد', 'السيدة': 'السيد'}
SMALLEST = 3
LABEL = 90


def words(title: str) -> list[str]:
    t = DATE.sub(' ', NUMBER.sub(' ', title))
    return [SAME.get(w, w) for w in MARKS.sub(' ', t).split()]


def parts(title: str) -> tuple[str, str, list[str]] | None:
    """(kind, issuer, act) as words, or None for a title with no act two words long."""
    w = words(title)
    if len(w) < 3:
        return None
    start = 2 if w[1] == 'مشترك' else 1
    act = next((k for k in range(start, len(w)) if ACT.match(w[k])), None)
    if act is None or act + 1 >= len(w):
        return None
    issuer = w[start:act]
    if issuer:     # «لوزير», «للأمين العام»: the issuer named without its «ل»
        first = issuer[0]
        issuer = ['ال' + first[2:] if first.startswith('لل') else first[1:] if first.startswith('ل') else first, *issuer[1:]]
    return ' '.join(w[:start]), ' '.join(issuer), w[act:]


def _shared(lists: list[list[str]]) -> list[str]:
    out = []
    for column in zip(*lists):
        if len(set(column)) > 1:
            break
        out.append(column[0])
    return out


def _clip(s: str) -> str:
    return s if len(s) <= LABEL else s[:LABEL].rsplit(' ', 1)[0] + '…'


def fold(rows: list[dict], general: bool) -> dict[str, dict]:
    """Mark each row of a series with `series` (its id) and `part` (what names it in the bundle); return the series by
    id: their shared words (`head`) and size. `rows` are in the Bulletin's order and each has a `title` and a `number`."""
    keyed: dict[tuple, list[tuple[dict, tuple]]] = {}
    for r in rows:
        p = parts(r['title'])
        if p:
            keyed.setdefault((p[0], p[2][0], p[2][1]), []).append((r, p))
    found: dict[str, dict] = {}
    for _key, members in keyed.items():
        acts = [p[2] for _, p in members]
        shared = _shared(acts)
        if len(members) < SMALLEST or (general and len(members) < 5 and len(shared) < 4):
            continue
        issuers = {p[1] for _, p in members if p[1]}
        one = len(issuers) <= 1
        sid = f'{"g" if general else "s"}{len(found) + 1}'
        kind = members[0][1][0]
        head = ' '.join([kind, *([next(iter(issuers))] if one and issuers else []), *shared])
        for r, (_, issuer, act) in members:
            rest = ' '.join(act[len(shared):])
            label = rest if one else (f'{issuer}: {rest}' if rest else issuer)
            r['series'], r['part'] = sid, _clip(label.strip())
        found[sid] = {'head': head, 'size': len(members), 'issuers': [] if one else _issuers(members)}
    return found


def _issuers(members: list[tuple[dict, tuple]]) -> list[dict]:
    """A series several authorities signed («بتفويض الإمضاء»): who, and how many each, the most first."""
    return [{'name': name or '', 'count': n} for name, n in Counter(p[1] for _, p in members).most_common()]
