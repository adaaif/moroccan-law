"""The Bulletin's own pages as witness for a text taken from a file's layer (RD1 of the readers review, 9 Nov 2026).

The codes people read most were loaded from the text layers of Adala's, the SGG's and the tax office's PDFs, and a layer
turns «لا» and «ال» round, swaps two letters and cuts a word where a vowel mark stands: the 2011 Constitution said «الدين
الإسلامي الحنفي» for «الحنيف» and «حمى لالمة» for «حمى الملة». `witness` (services/witness.py) needs the text's own
version as published, which these texts do not have. This one needs only the pages: every Arabic issue from No. 1 has
been read, so the issue that printed a text holds a second, independent reading of each article nothing has amended.

Each article is found in the pages read around the text's day by its runs of four words, then set beside them word by
word. Only small differences count (a word cut in two, letters turned or swapped: two letters apart at most), in an
article whose words otherwise agree; an amended article agrees too little and is left out. Either side can be the wrong
one: a difference is a place to read on the page's image, never a correction by itself. Nothing is written.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import timedelta
from difflib import SequenceMatcher

from apps.corpus.models import Text
from apps.sources.models import Edition, Issue, Page

LAYERS = ('adala', 'sgg', 'dgi')
# How long after its day a text may wait for its issue (the 2003 criminal procedure code: signed 3 Oct 2002, printed 30 Jan 2003).
WINDOW = timedelta(days=150)
# The penal code was signed on 26 November 1962 and printed on 5 June 1963; the expropriation law waited thirteen months.
LONG_WAIT = timedelta(days=420)
# An article is witnessed when this share of its words stand in the pages in their order: under it the law changed, or
# the pages are another text's.
AGREE = 0.85
_MARKS = re.compile(r'[ً-ْٰـ]')
_WORD = re.compile(r'[ء-يً-ْٰ]+|\d+')


def words(text: str) -> list[str]:
    """A text's words as the two readings can be compared: vowel marks and the hamza's seat set aside."""
    return [re.sub('[إأآٱ]', 'ا', _MARKS.sub('', w)) for w in _WORD.findall(text)]


def _apart(a: str, b: str) -> int:
    """How many letters apart two short strings are (9 when their lengths say more than two)."""
    if abs(len(a) - len(b)) > 2:
        return 9
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        new = [i]
        for j, y in enumerate(b, 1):
            new.append(min(row[j] + 1, new[-1] + 1, row[j - 1] + (x != y)))
        row = new
    return row[-1]


def slips(layer: list[str], pages: list[str], index: dict | None = None) -> list[dict] | None:
    """The small differences between an article's words and the pages': None when the pages do not hold the article."""
    if len(layer) < 8:
        return None
    if index is None:
        index = runs(pages)
    votes: dict[int, int] = defaultdict(int)
    for j in range(len(layer) - 3):
        for i in index.get(tuple(layer[j:j + 4]), ()):
            votes[(i - j) // 50] += 1
    if not votes or max(votes.values()) < max(2, len(layer) // 12):
        return None
    start = max(0, max(votes, key=votes.get) * 50 - 80)
    there = pages[start:start + len(layer) + 220]
    match = SequenceMatcher(None, layer, there, autojunk=False)
    blocks = [b for b in match.get_matching_blocks() if b.size]
    if sum(b.size for b in blocks) < AGREE * len(layer):
        return None
    first, last = blocks[0], blocks[-1]
    out = []
    for tag, i1, i2, j1, j2 in match.get_opcodes():
        if tag != 'replace' or j1 < first.b or j1 > last.b + last.size:
            continue
        mine, theirs = layer[i1:i2], there[j1:j2]
        if len(mine) > 3 or len(theirs) > 3:
            continue
        a, b = ''.join(mine), ''.join(theirs)
        if a == b and len(mine) <= len(theirs):
            continue        # the Bulletin's reading spaced a word the file keeps whole («و المؤسسات»): not the file's slip
        if a == b or _apart(a, b) <= 2:
            out.append({'layer': ' '.join(mine), 'bulletin': ' '.join(theirs),
                        'around': ' '.join(layer[max(0, i1 - 3):i1] + ['[' + ' '.join(mine) + ']'] + layer[i2:i2 + 3])})
    return out


def runs(pages: list[str]) -> dict:
    """Where each run of four words stands in the pages."""
    index: dict[tuple, list[int]] = defaultdict(list)
    for i in range(len(pages) - 3):
        index[tuple(pages[i:i + 4])].append(i)
    return index


def compare(text: Text) -> dict:
    """A text held from a file's layer against the Bulletin's pages around its day: how many articles the pages witness,
    how many agree word for word, and each small difference to read on the page."""
    version = text.versions.filter(language='ar', consolidation__in=LAYERS).order_by('-valid_from').first()
    if version is None:
        return {'text': text.akn_uri, 'error': 'not held from a file'}
    day = text.first_published_in.date if text.first_published_in_id else text.signed_on
    if day is None:
        return {'text': text.akn_uri, 'error': 'no day recorded: its issue cannot be found'}
    issues = list(Issue.objects.filter(edition=Edition.GENERAL_AR, date__gte=day - timedelta(days=3), date__lte=day + WINDOW)
                  .order_by('date', 'number').values_list('document_id', flat=True))
    read: list[str] = []
    rows = Page.objects.filter(document_id__in=issues).exclude(text='').values_list('document_id', 'index', 'text')
    for _, _, body in sorted(rows, key=lambda r: (issues.index(r[0]), r[1])):
        read += words(body)
    if len(read) < 500:
        return {'text': text.akn_uri, 'error': f'no page read near {day}'}
    index = runs(read)
    articles = list(version.articles.order_by('order').values_list('number', 'eid', 'body'))
    witnessed = agree = 0
    found = []
    for number, eid, body in articles:
        got = slips(words(body), read, index)
        if got is None:
            continue
        witnessed += 1
        agree += not got
        found += [{'number': number, 'eid': eid, **g} for g in got]
    return {'text': text.akn_uri, 'layer': version.consolidation, 'day': str(day), 'articles': len(articles),
            'witnessed': witnessed, 'agree': agree, 'slips': found}


# ── where a text was first printed ───────────────────────────────────────────────────────────────────────────────


def _number(text: Text) -> str | None:
    """A text's printed number as a pattern («0?65[.]99» finds «65.99» and «065.99»); None when it has none to be told by
    (a constitution, the 1913 dahirs)."""
    printed = (text.number_as_printed or text.number.replace('-', '.')).strip()
    return '0?' + re.escape(printed.lstrip('0')) if re.fullmatch(r'\d[\d.]*\d', printed) else None


def _cite(text: Text) -> str | None:
    """How a text is named with its day: a law by the dahir that promulgated it («القانون رقم 65.99 … الصادر بتنفيذه الظهير
    الشريف رقم 1.03.194 بتاريخ 14 من رجب 1424 (11 سبتمبر 2003)»), any other by the day right after its own number
    («مرسوم رقم 2.10.312 صادر في 20 من شوال 1431 (29 سبتمبر 2010)»). The group is the Gregorian day."""
    number = _number(text)
    if number is None:
        return None
    if text.type in ('law', 'organic_law'):
        return rf'رقم {number} [^()]{{0,250}}?الصادر(?:ة)? بتنفيذه(?:ا)?[^()]{{0,130}}\(([^()]{{6,40}})\)'
    return rf'رقم {number} (?:(?:ال)?(?:صادر|مؤرخ)(?:ة)? )?(?:في|بتاريخ) [^()]{{0,60}}\(([^()]{{6,40}})\)'


def signed_day(text: Text):
    """The day a text was signed: the one its own heading gives right after its own number, in its title or the first
    lines of its preamble; else the day the visas of other texts give it (cited_day); else, for a law, the promulgating
    dahir's day on the Bulletin's own page (promulgated_day). Never the first date a heading holds: a decree's heading
    names the law it applies with that law's day (decree 2.10.312 read 11 February 2010, the road code's). A text with
    no number is told by the first date of its title («الظهير الشريف الصادر في 9 رمضان 1331 (12 أغسطس 1913)»)."""
    from apps.consolidation.services.instructions import date_in, plain
    cite = _cite(text)
    if cite is None:
        return date_in(plain(text.title_ar or ''))
    version = text.versions.filter(language='ar').order_by('-valid_from').first()
    for words in (text.title_ar, (version.preamble if version else '')[:900]):
        said = re.search(cite, plain(words or ''))
        day = date_in(plain(said.group(1))) if said else None
        if day:
            return day
    return cited_day(text)[0] or promulgated_day(text)


def promulgated_day(text: Text):
    """The day of the dahir that promulgated a law, read on the Bulletin's own page: «ظهير شريف رقم 1.13.111 صادر في 15
    من محرم 1435 (19 نوفمبر 2013) بتنفيذ القانون رقم 67.12». For a law whose heading names no day and that too few
    visas cite. The earliest issue that prints the heading; None when no page does."""
    from apps.consolidation.services.instructions import date_in, plain
    number = _number(text)
    if text.type not in ('law', 'organic_law') or number is None:
        return None
    heading = rf'ظهير شريف رقم [0-9.]+ صادر في [^()]{{0,60}}\(([^()]{{6,40}})\)\s+بتنفيذ القانون (?:التنظيمي )?رقم {number}(?![0-9.])'
    days = []
    for document, body in Page.objects.filter(text__regex=heading).values_list('document_id', 'text')[:40]:
        issue = Issue.objects.filter(document_id=document, edition=Edition.GENERAL_AR).values_list('date', flat=True).first()
        for said in re.findall(heading, body):
            day = date_in(plain(said))
            if day and issue and timedelta(0) <= issue - day <= LONG_WAIT:
                days.append((issue, day))
    return min(days)[1] if days else None


def cited_day(text: Text) -> tuple:
    """The day other texts give a text when they cite it in their visas (_cite). (day, how many say it): the day most of
    them agree on, (None, 0) when they disagree or none cites it. One citation alone is a lead the issue must confirm
    (find_first_issues). The Labour Code's own heading, as the ministry's file gives it, names no day."""
    from collections import Counter

    from apps.consolidation.services.instructions import date_in, plain
    from apps.corpus.models import Version
    cite = _cite(text)
    if cite is None:
        return None, 0
    days: Counter = Counter()
    for preamble in Version.objects.filter(preamble__regex=cite).exclude(text=text).values_list('preamble', flat=True)[:400]:
        for said in re.findall(cite, preamble):
            day = date_in(plain(said))
            if day:
                days[day] += 1
    if not days:
        return None, 0
    day, n = days.most_common(1)[0]
    return (day, n) if n >= 0.6 * sum(days.values()) else (None, 0)


def first_print(text: Text, day=None, wait: timedelta = WINDOW) -> dict:
    """The issue that first printed a text held from a file, and the page its first articles stand on, found as
    `compare` finds its words: by runs of four words in the Arabic issues read from its day (RD5 of
    the readers review: 38 of the library's 46 books held from a file named no Bulletin, and the issue that printed the family
    code listed two texts for its 39 pages). The issue is the one that holds the most of its articles; a text amended
    since still keeps most of them. Nothing is written."""
    version = text.versions.filter(language='ar', consolidation__in=LAYERS).order_by('-valid_from').first()
    day = day or (text.first_published_in.date if text.first_published_in_id else text.signed_on) or signed_day(text)
    if version is None or day is None:
        return {'text': text.akn_uri, 'day': str(day) if day else None, 'error': 'not held from a file' if version is None else 'no day found'}
    issues = list(Issue.objects.filter(edition=Edition.GENERAL_AR, date__gte=day - timedelta(days=3), date__lte=day + wait)
                  .order_by('date', 'number').values('id', 'document_id', 'number', 'suffix', 'date'))
    by_document = {i['document_id']: i for i in issues}
    read: list[str] = []
    stops: list[tuple[int, int, int | None, int]] = []        # (first word, issue id, printed page, index in the file)
    rows = Page.objects.filter(document_id__in=by_document).exclude(text='').values_list('document_id', 'index', 'printed_number', 'text')
    order = {i['document_id']: n for n, i in enumerate(issues)}
    for document, index, printed, body in sorted(rows, key=lambda r: (order[r[0]], r[1])):
        stops.append((len(read), by_document[document]['id'], printed, index))
        read += words(body)
    if len(read) < 500:
        return {'text': text.akn_uri, 'day': str(day), 'error': f'no page read near {day}'}
    index = runs(read)
    starts = [s[0] for s in stops]
    from bisect import bisect_right
    votes: dict[int, int] = defaultdict(int)
    pages: dict[int, list] = defaultdict(list)
    articles = [a for a in version.articles.order_by('order').values_list('number', 'body') if len(words(a[1])) >= 8]
    for n, (_, body) in enumerate(articles[:120]):
        mine = words(body)
        seen: dict[int, int] = defaultdict(int)
        where: dict[int, tuple] = {}
        for j in range(0, len(mine) - 3, 2):
            for at in index.get(tuple(mine[j:j + 4]), ()):
                stop = stops[bisect_right(starts, at) - 1]
                seen[stop[1]] += 1
                where.setdefault(stop[1], (stop[2], stop[3]))
        if seen:
            issue, hits = max(seen.items(), key=lambda kv: kv[1])
            if hits >= max(2, len(mine) // 24):
                votes[issue] += 1
                pages[issue].append((n, where[issue]))
    # The issue is the one that holds the most of its articles AND names it on the pages before them: organic law 27.11
    # stood better in the issue that printed its sister 28.11, and a decree's copy stands in the issue of the law it
    # applies and quotes. The cover and the table of contents name every text: passed over while a later page names
    # this one (the penal code begins on the very page that carries the masthead of BO 2640 bis). A text with no
    # number is taken on its articles alone.
    number = _number(text)
    names = re.compile(r'(?<![\d.])' + number + r'(?![\d.])') if number else None
    asked = min(len(articles), 120)
    issue = found = first = None
    for candidate, n in sorted(votes.items(), key=lambda kv: -kv[1])[:4]:
        held = next(i for i in issues if i['id'] == candidate)
        at = min(pages[candidate])[1]
        if names is None:
            issue, found, first = candidate, n, at
            break
        if n < max(2, 0.2 * asked):
            break
        named = [(printed, 'ISSN' in body or 'فهرست' in body or body.lstrip().startswith('صفحة'))
                 for printed, body in (Page.objects.filter(document_id=held['document_id'], index__lte=at[1], index__gte=at[1] - 8)
                                       .order_by('index').values_list('printed_number', 'text'))
                 if printed and names.search(body.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')))]
        while len(named) > 1 and named[0][1]:
            named.pop(0)
        if named:
            issue, found, first = candidate, n, (named[0][0], at[1])
            break
    share = 0.5 if names is None else 0.2
    if (issue is None or found < share * asked) and wait < LONG_WAIT:
        return first_print(text, day, LONG_WAIT)
    if issue is None:
        return {'text': text.akn_uri, 'day': str(day),
                'error': 'no issue read after that day holds its articles' + (' and names it' if votes else '')}
    held = next(i for i in issues if i['id'] == issue)
    return {'text': text.akn_uri, 'day': str(day), 'issue': issue, 'number': held['number'], 'suffix': held['suffix'],
            'date': str(held['date']), 'page': first[0], 'index': first[1], 'articles': asked, 'found': found,
            'named': names is not None,
            'next': sorted(((votes[i], next(x['number'] for x in issues if x['id'] == i)) for i in votes if i != issue), reverse=True)[:2]}
