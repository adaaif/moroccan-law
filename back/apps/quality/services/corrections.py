"""Putting a word right (R7 of the for-everyone review): only a person applies a correction or sets it aside, and an applied
one is applied again whenever its text is loaded anew, so a reload never brings an error back."""
import difflib
import re

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.corpus.models import Article, Text
from apps.corpus.services import generation
from apps.corpus.services.addresses import article_path, split_path
from apps.quality.models import Correction

WORD = re.compile(r'[ء-يٱ-ۓ]+')


def put_right(body: str, c: Correction) -> str:
    """The body with the word put right where its neighbours are the ones recorded; the rest untouched. Words a
    ligature also cut apart («لا تممت عين» for «المتمتعين») are found as they stand, whatever their spaces.
    The right words are put in as written: never read as a pattern (a «\\frac» once became a form feed, BO 3751 p8)."""
    if not c.wrong:
        # A page the reading left empty, read on its image (an unread page of the Bulletin, 6 Nov 2026): the reading
        # takes the empty page, and only while it is empty. A body with words in it is never touched: an empty
        # «wrong» would otherwise match at every boundary of a page read anew and paste the reading everywhere.
        return c.right if not body.strip() else body
    if c.wrong in c.right and c.right in body:
        # A fix that only adds words (a heading's lost half, 58.25's «… والأقسام المتخصصة في القضاء الإداري») is never
        # applied where its words already stand: a machine version copies corrected articles and puts them right again.
        return c.right.join(put_right(part, c) for part in body.split(c.right))
    if ' ' in c.wrong.strip():
        words = [re.escape(w) for w in c.wrong.split()]
        return re.sub(r'(?<![ء-ي])' + r'\s+'.join(words) + r'(?![ء-ي])', lambda m: c.right, body)
    if not WORD.fullmatch(c.wrong):
        # A word with letters of another alphabet in it («وحרר»): not a word of the Arabic tokens below, so it is
        # found as it stands, between anything but letters.
        return re.sub(r'(?<!\w)' + re.escape(c.wrong) + r'(?!\w)', lambda m: c.right, body)
    spans = [(m.start(), m.end(), m.group(0)) for m in WORD.finditer(body)]
    out, last = [], 0
    for i, (start, end, w) in enumerate(spans):
        if w != c.wrong:
            continue
        before = spans[i - 1][2] if i else ''
        after = spans[i + 1][2] if i + 1 < len(spans) else ''
        if (not c.before or before == c.before) and (not c.after or after == c.after):
            out.append(body[last:start] + c.right)
            last = end
    return ''.join(out) + body[last:] if out else body


def headings_right(path: list[str], fixes: list[Correction]) -> list[str]:
    """A division's headings with the words put right that apply to the whole text's headings (a correction whose
    evidence says `headings`: Adala prints «الأهلية والوالية» over twenty articles, and one reading mends them all)."""
    out = []
    for h in path:
        for c in fixes:
            h = put_right(h, c)
        out.append(h)
    return out


def _articles(path: str):
    uri, eid = split_path(path)
    return Article.objects.filter(version__text__akn_uri=uri, version__language='ar', eid=eid)


def apply(user, pk: int) -> Correction:
    c = Correction.objects.filter(pk=pk).first()
    if c is None:
        raise Refused('correction', 'not_found', 404)
    with transaction.atomic():
        changed = 0
        for a in _articles(c.path):
            body = put_right(a.body, c)
            if body != a.body:
                a.body = body
                a.save(update_fields=['body'])
                changed += 1
        if not changed and c.status != Correction.Status.APPLIED:
            raise Refused('correction', 'not_found', 404)
        c.status, c.decided_by, c.decided_at = Correction.Status.APPLIED, user, timezone.now()
        c.save(update_fields=['status', 'decided_by', 'decided_at'])
        Text.objects.filter(akn_uri=split_path(c.path)[0]).update(updated_at=timezone.now())
    generation.bump('corpus')       # the article's words changed: no answer kept before shows them again
    return c


def reject(user, pk: int) -> Correction:
    c = Correction.objects.filter(pk=pk).first()
    if c is None:
        raise Refused('correction', 'not_found', 404)
    c.status, c.decided_by, c.decided_at = Correction.Status.REJECTED, user, timezone.now()
    c.save(update_fields=['status', 'decided_by', 'decided_at'])
    return c


def reapply(articles: list[Article], akn_uri: str) -> int:
    """After a load: the corrections a person applied to this text, applied to its new articles."""
    by_path: dict[str, list[Correction]] = {}
    headings: list[Correction] = []
    for c in Correction.objects.filter(status=Correction.Status.APPLIED,
                                       path__startswith=article_path(akn_uri, '')):
        if c.evidence.get('headings'):
            headings.append(c)
        else:
            by_path.setdefault(c.path, []).append(c)
    changed = []
    for a in articles:
        body = a.body
        for c in by_path.get(article_path(akn_uri, a.eid), []):
            body = put_right(body, c)
        heading = headings_right(a.heading_path or [], headings) if headings else a.heading_path
        if body != a.body or heading != a.heading_path:
            a.body, a.heading_path = body, heading
            changed.append(a)
    Article.objects.bulk_update(changed, ['body', 'heading_path'])
    return len(changed)


def page_path(issue, index: int) -> str:
    """A page as its corrections are kept: «/bo/general_ar/2512#p2», its place in the file (0-based), which no
    renumbering of the printed pages moves (FX2 of the mended-Bulletin review)."""
    return f'/bo/{issue.edition}/{issue.key}#p{index}'


def reapply_pages(pages) -> int:
    """After pages are read anew (or loaded again): the corrections read against their images, applied to the new
    readings in memory; the caller saves. Returns how many pages changed."""
    from apps.sources.models import Issue
    pages = list(pages)
    issues = {i.document_id: i for i in Issue.objects.filter(document_id__in={p.document_id for p in pages})}
    paths = {page_path(issues[p.document_id], p.index): p for p in pages if p.document_id in issues}
    changed = set()
    for c in Correction.objects.filter(status=Correction.Status.APPLIED, path__in=list(paths)).order_by('pk'):
        page = paths[c.path]
        text = put_right(page.text, c)
        if text != page.text:
            page.text = text
            changed.add(page.pk)
    return len(changed)


LONG = 240      # letters: past this a correction is a page read again, and the list shows what changed in it
SHOWN_RUNS = 3


def _what_changed(wrong: str, right: str) -> tuple[str, str, int]:
    """A long correction as the words that changed, three around each, and in how many places (RD22 of the readers
    review, 9 Nov 2026). A page read again is recorded whole, 6,800 letters at the median: the list of the newest
    hundred was 1 MB, and 560,000 px tall on a phone."""
    if len(wrong) + len(right) <= LONG:
        return wrong, right, 1
    a, b = wrong.split(), right.split()
    was, now, places = [], [], 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        places += 1
        if places <= SHOWN_RUNS:
            was.append(' '.join(a[max(0, i1 - 3):i2 + 3]))
            now.append(' '.join(b[max(0, j1 - 3):j2 + 3]))
    return ' … '.join(was)[:2 * LONG], ' … '.join(now)[:2 * LONG], places


DECIDE = 'quality.change_correction'


def may_decide(user) -> bool:
    """Who applies a correction or sets it aside: staff given the right to change corrections (in the admin, on the
    account or through a group). A superuser has every right; being staff alone is not enough to change the law's
    words."""
    return bool(user and user.is_authenticated and user.is_staff and user.has_perm(DECIDE))


def listed(viewer) -> dict:
    """/corrections: what was put right, newest first; for whoever may decide, what waits. The readers' list is kept
    until the next correction (setting two readings of a page side by side a hundred times is seconds of work)."""
    from apps.quality.models import Report
    staff = may_decide(viewer)
    rows = _rows(staff) if staff else generation.kept(['corrections', 'readers'], lambda: _rows(False))
    # What readers filed since the site opened: the reports of its making (six test rows of October) are not readers'.
    reports = Report.objects.all() if settings.SHOW_DEMO_PEOPLE else Report.objects.filter(created_at__gte=settings.DEMO_UNTIL)
    return {**rows, 'can_decide': staff,
            'counts': {'applied': Correction.objects.filter(status=Correction.Status.APPLIED).count(),
                       'waiting': Correction.objects.filter(status=Correction.Status.SUGGESTED).count(),
                       'reports_open': reports.filter(status=Report.Status.OPEN).count(),
                       'reports_fixed': reports.filter(status=Report.Status.FIXED).count()}}


def _rows(staff: bool) -> dict:
    from apps.corpus.services.codes import everyday_name
    applied = list(Correction.objects.filter(status=Correction.Status.APPLIED).order_by('-decided_at')[:100])
    waiting = list(Correction.objects.filter(status=Correction.Status.SUGGESTED).order_by('path', 'id')[:200]) if staff else []
    uris = {split_path(c.path)[0] for c in applied + waiting}
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=uris)}
    labels = {(a.version.text.akn_uri, a.eid): a.label for a in Article.objects.filter(
        version__text__akn_uri__in=uris, eid__in={split_path(c.path)[1] for c in applied + waiting}).select_related('version__text')}

    def row(c: Correction) -> dict:
        uri, eid = split_path(c.path)
        t = texts.get(uri)
        name = (everyday_name(t) or {}).get('ar') or t.title_ar if t else ''
        wrong, right, places = _what_changed(c.wrong, c.right)
        return {'id': c.pk, 'path': c.path, 'article': labels.get((uri, eid), ''), 'text': name, 'wrong': wrong,
                'right': right, 'places': places, 'before': c.before, 'after': c.after, 'source': c.source,
                'evidence': c.evidence, 'on': (c.decided_at or c.created_at).isoformat()}
    return {'applied': [row(c) for c in applied], 'waiting': [row(c) for c in waiting]}
