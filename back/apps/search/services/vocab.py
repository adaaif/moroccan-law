"""The everyday-words list (row 1, decision C2): a query that says «AMO», «الكرا» or «patente» is also searched
as the law says it («التأمين الإجباري الأساسي عن المرض», «الكراء», «الرسم المهني»). Only approved entries
(apps/search/data/everyday.json) are read; nothing runs a model at search time."""
import json
import re
from functools import lru_cache
from pathlib import Path

import ma_law
from django.conf import settings

FILE = Path(__file__).resolve().parent.parent / 'data' / 'everyday.json'


@lru_cache(maxsize=1)
def entries() -> list[tuple[str, list[str]]]:
    """[(folded typed words, [the law's terms])] — longest typed form first, so «عقد الكرا» wins over «الكرا». The
    topics' doors are entries too: each door's words mean its `means` (H7 of the housing plan), approved with the door."""
    data = json.loads(FILE.read_text()) if FILE.exists() else {'entries': []}
    # A door's phrase first: it names the article the door opens («caution» is the rent deposit, «ضمانة الكراء»).
    out = doors()
    seen = {typed for typed, _ in out}
    for e in data['entries']:
        for typed in e['typed']:
            if ma_law.fold(typed) not in seen:
                out.append((ma_law.fold(typed), e['means']))
                seen.add(ma_law.fold(typed))
    if settings.SEARCH_THESAURUS:
        # B10: the thesaurus's people's words for its legal terms, after the lists people approved.
        from apps.search.services.thesaurus import people_words
        for typed, means in people_words():
            if typed not in seen:
                out.append((typed, means))
                seen.add(typed)
    return sorted(out, key=lambda x: -len(x[0]))


def doors() -> list[tuple[str, list[str]]]:
    """(folded word, [the law's phrase]) for every topic door that names the phrase its words mean."""
    from apps.topics.services import kit

    out = []
    for slug in kit._folders():
        hub = kit.load(slug)['hub']
        for d in [*(hub.get('events') or []), *(hub.get('tools') or [])]:
            means = d.get('means')
            # One phrase for all the door's words, or a phrase for each group of them (the syndic's door: the syndic,
            # and the charges).
            groups = means.items() if isinstance(means, dict) else [(means, d.get('words') or [])] if means else []
            for phrase, words in groups:
                out += [(ma_law.fold(w), [phrase]) for w in words]
    return out


def whole(query: str) -> bool:
    """The query is one everyday form and nothing else («CNSS»): the law's term is searched first, since the few
    articles that write «CNSS» in Latin letters are not where the answer is."""
    folded = ma_law.fold(query)
    return any(folded == typed for typed, _ in entries())


def rewrites(query: str) -> list[str]:
    """The query again with each everyday form found in it (as whole words) put as the law says it; when it holds
    several, first with all of them put so («caution loyer» → «ضمانة الكراء الوجيبة الكرائية»)."""
    folded = f' {ma_law.fold(query)} '
    found = [(typed, means) for typed, means in entries() if f' {typed} ' in folded]
    out = []
    if len(found) > 1:
        every = folded
        for typed, means in found:
            every = every.replace(f' {typed} ', f' {means[0]} ')
        out.append(every.strip())
    for typed, means in found:
        for meaning in means:
            out.append(folded.replace(f' {typed} ', f' {meaning} ').strip())
    return out


def meanings(query: str) -> str:
    """What the everyday forms in the query mean, together, without its other words: «الصابو» → «توقيف المركبات».
    The longest form first, and a meaning said once."""
    folded = f' {ma_law.fold(query)} '
    out: list[str] = []
    for typed, means in entries():
        if f' {typed} ' in folded and means[0] not in out:
            out.append(means[0])
            folded = folded.replace(f' {typed} ', ' ')
    return ' '.join(out)


def door_forms(door: dict | None) -> dict[str, str]:
    """{folded typed form: the law's phrase} of the one door a search shows first ({topic, slug}), short phrases only: a
    door's `means` that is a whole rule («يجب على كل مواطن مغربي يبلغ 16 سنة…») is no name for a word."""
    from apps.topics.services import kit

    if not door:
        return {}
    hub = (kit.load(door['topic']) or {}).get('hub') or {}
    for d in [*(hub.get('events') or []), *(hub.get('tools') or [])]:
        if f"{door['topic']}-{d['key']}" != door['slug']:
            continue
        means = d.get('means')
        groups = means.items() if isinstance(means, dict) else [(means, d.get('words') or [])] if means else []
        return {ma_law.fold(w): phrase for phrase, words in groups if len(phrase.split()) <= 6 for w in words}
    return {}


def everyday_forms() -> dict[str, str]:
    """{folded typed form: the law's term} of the approved everyday list alone (data/everyday.json)."""
    data = json.loads(FILE.read_text()) if FILE.exists() else {'entries': []}
    return {ma_law.fold(typed): e['means'][0] for e in data['entries'] for typed in e['typed']}


def gloss(query: str, door: dict | None = None) -> list[dict]:
    """The question as typed, each everyday form in it with the law's words under it (the search page's «بكلام
    القانون», 30 Oct 2026): «مول الدار بغا يزيد فالكرا» → [{t: «مول الدار »}, {t: «بغا يزيد فالكرا», law: «الزيادة في
    الوجيبة الكرائية»}]. From the approved lists alone (the doors' words, everyday.json); the longest form first, a
    form's first word also read without «ف», «و», «ال»… as the doors read it. [] when no form is in it."""
    from apps.topics.services.topics import _variants

    # The law's words for the door shown first and the approved everyday list, never another door's (HM10 of
    # the hard-moment review: «تسرقات ليا لاكارط» was glossed with the first card's rule, «التعويض» with the medicine refund).
    forms = {**everyday_forms(), **door_forms(door)}
    longest = max((len(typed.split()) for typed in forms), default=0)
    parts = [p for p in re.split(r'(\s+)', query.strip()) if p]
    words = [(f, i) for i, p in enumerate(parts) if p.strip() for f in ma_law.fold(p).split()]
    spans: list[tuple[int, int, str]] = []      # (first part, last part, the law's words)
    k = 0
    while k < len(words):
        found = None
        for n in range(min(longest, len(words) - k), 0, -1):
            rest = [w for w, _ in words[k + 1:k + n]]
            for first in sorted(_variants(words[k][0]), key=len, reverse=True):
                law = forms.get(' '.join([first, *rest]))
                if law and ma_law.fold(law) != ' '.join([first, *rest]):
                    found = (n, law)
                    break
            if found:
                break
        if found:
            spans.append((words[k][1], words[k + found[0] - 1][1], found[1]))
            k += found[0]
        else:
            k += 1
    if not spans:
        return []
    out: list[dict] = []
    at = 0
    for first, last, law in spans:
        if first > at:
            out.append({'t': ''.join(parts[at:first])})
        out.append({'t': ''.join(parts[first:last + 1]), 'law': law})
        at = last + 1
    if at < len(parts):
        out.append({'t': ''.join(parts[at:])})
    return out
