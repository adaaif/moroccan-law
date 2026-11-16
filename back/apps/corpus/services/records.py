"""Dates, titles and twins that cannot be right (FX7 of the mended-Bulletin review, 2 Nov 2026).

- `dates`: a text dated after the issue that published it takes the day its own closing signs («وحرر بالرباط في …
  الموافق 11 غشت سنة 1943»), the last such day on or before the issue; one whose closing names none is listed.
- `twins`: one printed text cut twice in an issue (one title, or titles alike on one page, and their words alike):
  the fuller cut stays, the other folds into it, its address leading there.
- Bare titles («ظهير شريف» and nothing else) are put right by hand in mended_proven.yaml, from their pages."""
import difflib
import re
from collections import defaultdict
from datetime import date

from django.db.models import Count, F, Sum
from django.db.models.functions import Length

from apps.corpus.models import Article, Text, Version
from apps.corpus.services.issue_structure import _days

_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ة': 'ه'})


def dates(write: bool = False) -> tuple[list[tuple[str, date, date]], list[str]]:
    """(address, stored day, signed day) for each text put right; the addresses whose closing names no day."""
    fixed, left = [], []
    rows = (Text.objects.filter(first_published_in__isnull=False, signed_on__gt=F('first_published_in__date'))
            .select_related('first_published_in'))
    closings = defaultdict(str)
    for text_id, closing in Version.objects.filter(text__in=rows, consolidation='as_published').values_list(
            'text_id', 'closing'):
        closings[text_id] += '\n' + (closing or '')
    for t in rows:
        days = [d for d in map(date.fromisoformat, _days(closings[t.pk])) if d <= t.first_published_in.date]
        if days:
            fixed.append((t.akn_uri, t.signed_on, days[-1]))
            if write:
                Text.objects.filter(pk=t.pk).update(signed_on=days[-1])
        else:
            left.append(t.akn_uri)
    return fixed, left


def _key(title: str) -> str:
    return re.sub(r'\W+', ' ', (title or '').translate(_FOLD)).strip()


_KINDS = {'قرار', 'وزيري', 'ظهير', 'شريف', 'مقرر', 'مرسوم', 'منشور', 'قرارا'}
_SHAPE = str.maketrans({'ب': 'ٮ', 'ت': 'ٮ', 'ث': 'ٮ', 'ن': 'ٮ', 'ي': 'ٮ', 'ج': 'ح', 'خ': 'ح', 'ذ': 'د', 'ز': 'ر',
                        'ش': 'س', 'ض': 'ص', 'ظ': 'ط', 'غ': 'ع', 'ق': 'ڡ', 'ف': 'ڡ'})


def same_title(ka: str, kb: str) -> bool:
    """Two folded titles of one text: alike but for dots and spelling, a kind word left out («قرار وزيري»), a year at
    the end. «… بمدينة مكناس» and «… بمدينة الرباط» are two texts; «فى تعيين» and «في تعيين» one."""
    def words(k):
        k = re.sub(r'(?<!\S)في\s+', 'ب', k)          # «في تخلي» is «بتخلي»: the same heading written two ways
        w = [x for x in k.split() if x not in _KINDS]
        while w and w[-1].isdigit():
            w.pop()
        return w
    a, b = words(ka), words(kb)
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        if op != 'replace' or a2 - a1 != b2 - b1:
            return False
        if any(x.translate(_SHAPE) != y.translate(_SHAPE) for x, y in zip(a[a1:a2], b[b1:b2])):
            return False
    return bool(a)


def _words(text_ids) -> dict[int, list[str]]:
    words = defaultdict(list)
    rows = (Article.objects.filter(version__text__in=text_ids, version__consolidation='as_published')
            .order_by('version__text', 'order').values_list('version__text', 'body'))
    for text_id, body in rows:
        words[text_id].extend(_key(body).split()[:400])
    return words


def twins(write: bool = False) -> list[tuple[str, str]]:
    """(folded address, kept address) for each text cut twice in one issue: same folded title (or alike, eight in ten,
    on the same page), and, when both have words, the shorter cut's words (95 in 100) and figures in the fuller. The kept one has the more articles
    and words; with `write` the other folds into it (`works.fold_copy`, alias reason «twin»)."""
    from apps.corpus.models import Alias
    from apps.corpus.services import works
    texts = list(Text.objects.filter(versions__consolidation='as_published', first_published_in__isnull=False)
                 .values_list('pk', 'akn_uri', 'first_published_in', 'title_ar', 'number', 'first_published_page')
                 .distinct())
    by_issue = defaultdict(list)
    for row in texts:
        by_issue[row[2]].append(row)
    from apps.sources.models import Issue
    # A cover that took texts from its copies (FX3): their pages were counted from other starts and their titles
    # misread otherwise (BO 610: «فبيئة» and «قبيلة»), so titles alike count on any page there.
    covers = set(Issue.objects.filter(copies__isnull=False).values_list('pk', flat=True))
    # A row made from a contents line has no words and the contents' page: it meets the text it names anywhere in the
    # issue (FX6, the fold of «a row made from a contents line into the text it names»).
    empty = set(Text.objects.filter(pk__in=[r[0] for r in texts]).exclude(
        versions__articles__isnull=False).values_list('pk', flat=True))
    pairs = []
    for issue_id, rows in by_issue.items():
        if len(rows) < 2:
            continue
        keys = {r[0]: _key(r[3]) for r in rows}
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if a[4] and b[4] and a[4] != b[4]:
                    continue                    # two numbers: two texts
                ka, kb = keys[a[0]], keys[b[0]]
                if len(ka) < 12 or len(kb) < 12:
                    continue
                same = ka == kb
                listed = (a[0] in empty) != (b[0] in empty)         # one a contents line, the other the text
                ratio = 0.75 if issue_id in covers else 0.85 if listed else 0.8
                alike = not same and (a[5] == b[5] or issue_id in covers or listed) and \
                    difflib.SequenceMatcher(None, ka, kb, autojunk=False).ratio() >= ratio
                if same or alike:
                    pairs.append((a, b))
    words = _words({r[0] for p in pairs for r in p})
    size = {r['version__text']: (r['n'], r['letters'] or 0) for r in Article.objects.filter(
        version__text__in={r[0] for p in pairs for r in p}, version__consolidation='as_published')
        .values('version__text').annotate(n=Count('pk'), letters=Sum(Length('body')))}
    out, gone = [], set()
    for a, b in pairs:
        if a[0] in gone or b[0] in gone:
            continue
        wa, wb = words.get(a[0], []), words.get(b[0], [])
        ka, kb = _key(a[3]), _key(b[3])
        cover_only = False
        if ka != kb and not same_title(ka, kb):
            # Titles that differ by more than dots and spelling («السيد دوس…», «السيد سال…»: two notices) name two
            # texts, but on a cover whose copies misread a title otherwise when their words agree almost wholly.
            if not (a[2] in covers and wa and wb):
                continue
            cover_only = True
        if wa and wb:
            small, big = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
            matched = sum(m.size for m in difflib.SequenceMatcher(None, small, big, autojunk=False).get_matching_blocks())
            figures = {w for w in small if w.isdigit()}, {w for w in big if w.isdigit()}
            if cover_only and (matched < 0.98 * len(small) or figures[0] != figures[1]):
                continue
            if matched < 0.95 * len(small) or not figures[0] <= figures[1]:
                continue                        # the same heading over other words or figures: two texts
        keep, fold = (a, b) if size.get(a[0], (0, 0)) >= size.get(b[0], (0, 0)) else (b, a)
        out.append((fold[1], keep[1]))
        gone.add(fold[0])
        if write:
            works.fold_copy(Text.objects.get(pk=fold[0]), Text.objects.get(pk=keep[0]), reason=Alias.Reason.TWIN)
    return out
