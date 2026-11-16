"""Printed page numbers put right (FX4 of the mended-Bulletin review, 2 Nov 2026). The Bulletin numbers its pages through
the year; an issue whose readings kept no page number (old readings rarely keep the running head) was left starting
at page 1 in the middle of a year: BO 73's page 407 showed as page 3. 112 issues, about 2,985 pages.

`misnumbered` finds them and proposes the start the issues around them give (the previous issue's last page + 1):
sure when the next issue starts right after; otherwise `confirm` reads the printed number at the top of a page or two
with Tesseract and keeps the start the page itself prints. `renumber` moves the issue's pages, its texts' first page
and pages, and its articles' printed page by the same amount.

`text_pages` puts a text's first page where its own pages begin when it stood elsewhere: the issue's first page, the
contents page that lists it (decree 2.20.30 «page 830», printed on 844–845), or none; a page either side is left."""
import re
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction
from django.db.models import Count, Max, Q

from apps.sources.models import Issue, Page


@dataclass
class Proposal:
    issue: Issue
    pages: int
    start: int                  # the start the neighbours give
    sure: bool                  # the next issue starts right after this one's pages
    evidence: list[str] = field(default_factory=list)


def misnumbered(edition: str | None = None) -> list[Proposal]:
    """Mid-year issues stored as starting on page 1 while the issues before and after run past them."""
    span = {d: (n, last) for d, n, last in Page.objects.values('document').annotate(
        n=Count('pk'), last=Max('printed_number')).values_list('document', 'n', 'last')}
    issues = Issue.objects.filter(copy_of__isnull=True, document__isnull=False).select_related('document')
    if edition:
        issues = issues.filter(edition=edition)
    by_year = defaultdict(list)
    for i in issues.order_by('date', 'number', 'suffix'):
        by_year[(i.edition, i.date.year)].append(i)
    out = []
    for rows in by_year.values():
        for k, issue in enumerate(rows):
            if issue.first_page_number != 1 or k == 0:
                continue
            n = span.get(issue.document_id, (0, 0))[0]
            prev_last = span.get(rows[k - 1].document_id, (0, None))[1]
            nxt = rows[k + 1].first_page_number if k + 1 < len(rows) else None
            if not prev_last or prev_last <= 1:
                continue
            if nxt is not None and nxt <= prev_last:
                continue                 # the next issue starts its own count: not this one's to say
            out.append(Proposal(issue, n, prev_last + 1, sure=nxt == prev_last + 1 + n))
    return out


def neighbour_start(issue: Issue) -> int | None:
    """The page an issue starts on when the year runs on from the issue before it in the same edition (its last
    printed page + 1); None for a year's first issue or when the issue before has no pages numbered."""
    before = (Issue.objects.filter(edition=issue.edition, copy_of__isnull=True, date__year=issue.date.year,
                                   document__isnull=False)
              .filter(Q(date__lt=issue.date) | Q(date=issue.date, number__lt=issue.number))
              .order_by('-date', '-number').first())
    if before is None:
        return None
    last = Page.objects.filter(document=before.document_id).aggregate(last=Max('printed_number'))['last']
    return last + 1 if last and last > 1 else None


_DIGITS = re.compile(r'\d{1,5}')


def printed_numbers(page: Page, width: int = 1400) -> list[int]:
    """The numbers Tesseract reads in the top tenth of a page (digits only), where the Bulletin prints its page
    number beside the issue's number and date."""
    from apps.sources.services.render import _render
    image = _render(page, width)
    w, h = image.size
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'top.png'
        image.crop((0, 0, w, int(h * 0.10))).save(path)
        out = subprocess.run(['tesseract', str(path), 'stdout', '--psm', '6', '-c', 'tessedit_char_whitelist=0123456789 '],
                             capture_output=True, text=True, timeout=60)
    return [int(n) for n in _DIGITS.findall(out.stdout)]


def confirm(p: Proposal) -> bool:
    """Whether the pages print the start: the neighbours' start when one page prints its number (counted on from that
    start); a start up to eight pages later that two pages agree on (unnumbered pages between two issues: BO 919 starts
    at 1321, its neighbours say 1320); or one up to twelve pages away that three pages agree on (BO 124: five pages
    print a start of 343, its neighbours say 334). Pages 2 to 10 of the file, each read at two sizes."""
    seen = defaultdict(set)
    for page in Page.objects.filter(document=p.issue.document_id, index__in=range(1, 10)).order_by('index'):
        for width in (2000, 2600):
            for n in printed_numbers(page, width):
                if p.start - 2 <= n - page.index <= p.start + 12:
                    seen[n - page.index].add(page.index)
        if p.start in seen:
            p.evidence.append(f'page {page.index + 1} prints {p.start + page.index}')
            return True
    agreed = sorted(((len(where), s) for s, where in seen.items()
                     if len(where) >= 3 or (len(where) >= 2 and p.start <= s <= p.start + 8)), reverse=True)
    if agreed:
        p.start = agreed[0][1]
        p.evidence.append(f'{agreed[0][0]} pages print a start of {p.start}')
        return True
    p.evidence.append('no page number read' if not seen else 'starts read: ' + str({s: sorted(w) for s, w in seen.items()}))
    return False


def _shift_range(value: str, delta: int, low: int, high: int) -> str:
    m = re.fullmatch(r'(\d+)-(\d+)', value or '')
    if not m or not (low <= int(m.group(1)) <= high):
        return value
    return f'{int(m.group(1)) + delta}-{int(m.group(2)) + delta}'


def _shift_files(issue: Issue, delta: int, low: int, high: int) -> None:
    """The issue's texts.json and toc.json moved with its pages, so a reload keeps the numbering (a copy of each is
    kept first, *.before-renumber.json)."""
    import json
    from apps.corpus.services.recut import workdir
    folder = workdir(issue)

    def moved(n):
        return n + delta if isinstance(n, int) and low <= n <= high else n
    for name in ('texts.json', 'toc.json'):
        path = folder / name
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        kept = path.with_name(name.replace('.json', '.before-renumber.json'))
        if not kept.exists():
            kept.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        for item in data:
            if name == 'toc.json':
                item['page'] = moved(item.get('page'))
                continue
            if item.get('pages'):
                item['pages'] = [moved(n) for n in item['pages']]
            if isinstance(item.get('toc'), dict):
                item['toc']['page'] = moved(item['toc'].get('page'))
            for a in item.get('articles') or []:
                a['page'] = moved(a.get('page'))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


@transaction.atomic
def renumber(issue: Issue, start: int, files: bool = False) -> dict:
    """The issue's pages numbered from `start`, and its texts, versions and articles moved with them; with `files`, its
    texts.json and toc.json too (the corpus of record; a trial copy of the database leaves the shared files alone)."""
    from apps.corpus.models import Article, Text, Version
    old = issue.first_page_number or 1
    delta = start - old
    pages = list(Page.objects.filter(document=issue.document_id))
    low, high = old, old + len(pages) - 1
    for page in pages:
        page.printed_number = page.index + start
    Page.objects.bulk_update(pages, ['printed_number'], batch_size=500)
    Issue.objects.filter(pk=issue.pk).update(first_page_number=start)
    texts = list(Text.objects.filter(first_published_in=issue))
    for t in texts:
        if t.first_published_page is not None and low <= t.first_published_page <= high:
            t.first_published_page += delta
    Text.objects.bulk_update(texts, ['first_published_page'], batch_size=500)
    versions = list(Version.objects.filter(text__in=texts, consolidation='as_published'))
    for v in versions:
        v.source_pages = _shift_range(v.source_pages, delta, low, high)
    Version.objects.bulk_update(versions, ['source_pages'], batch_size=500)
    articles = list(Article.objects.filter(version__in=versions, printed_page__gte=low, printed_page__lte=high))
    for a in articles:
        a.printed_page += delta
    Article.objects.bulk_update(articles, ['printed_page'], batch_size=1000)
    if files and delta:
        _shift_files(issue, delta, low, high)
    return {'pages': len(pages), 'texts': len(texts), 'articles': len(articles), 'delta': delta}


def text_pages(issue_ids=None, write: bool = False) -> list[tuple[str, int | None, int]]:
    """Texts whose first page is not where their own pages begin, when those pages lie inside the issue: (address,
    stored first page, first page). With `write`, each is put right."""
    from apps.corpus.models import Text, Version
    rows = (Version.objects.filter(consolidation='as_published', text__first_published_in__isnull=False)
            .select_related('text__first_published_in'))
    if issue_ids is not None:
        rows = rows.filter(text__first_published_in__in=issue_ids)
    span = {d: (n, last) for d, n, last in Page.objects.values('document').annotate(
        n=Count('pk'), last=Max('printed_number')).values_list('document', 'n', 'last')}
    out, fixed = [], {}
    for v in rows.iterator(chunk_size=2000):
        issue = v.text.first_published_in
        m = re.fullmatch(r'(\d+)-(\d+)', v.source_pages or '')
        if not m or issue.first_page_number is None or v.text_id in fixed:
            continue
        first, last_page = int(m.group(1)), span.get(issue.document_id, (0, None))[1]
        if last_page is None or not (issue.first_page_number <= first <= last_page):
            continue
        stored, end = v.text.first_published_page, int(m.group(2))
        # A page or so either side is the contents' word against the cut's (a heading, a promulgating dahir on the page
        # before): the Bulletin's own contents are kept. Off by more, or none, the text's own pages are.
        if not stored or stored < first - 1 or stored > end + 1:
            out.append((v.text.akn_uri, stored, first))
            fixed[v.text_id] = first
    if write:
        rows = [Text(pk=pk, first_published_page=first) for pk, first in fixed.items()]
        Text.objects.bulk_update(rows, ['first_published_page'], batch_size=1000)
    return out
