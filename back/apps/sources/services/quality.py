"""How each page of an issue was read, said plainly: from the PDF's own text, read and confirmed by it, read
but not confirmed by it, or read from a scan with nothing to check against. And for the issue: which texts
its contents list that were not found in its pages."""
import hashlib
import json
from pathlib import Path

from django.conf import settings

from apps.sources.models import Issue, Page, TextSource
from apps.sources.services.issue import confirmed, reading_check

MIN_LAYER = 200


def fingerprint(page: Page) -> str:
    """What a page's measure was worked out from: its reading, where it came from and its layer's letters."""
    return hashlib.sha1(f'{page.text_source}|{page.layer_letters}|{page.text}'.encode(), usedforsecurity=False).hexdigest()[:16]


def measure(page: Page) -> dict:
    """How the page was read and what its layer confirms of it. The archive marks a scan whose kept reading may lack
    lines `short` itself (Z23 of the second-archive-run review, `archive.keep`)."""
    reading = _reading(page)
    check = reading_check(page, page.text) if reading in ('confirmed', 'unconfirmed') else None
    return {'of': fingerprint(page), 'reading': reading, 'check': check}


def measured(page: Page) -> dict:
    """The page's kept measure when it is of its present reading; else worked out now (a request never writes it)."""
    kept = page.quality
    return kept if kept and kept.get('of') == fingerprint(page) else measure(page)


def store(pages) -> int:
    """Measure pages whose reading was just chosen and keep it with them."""
    pages = list(pages)
    for page in pages:
        page.quality = measure(page)
    Page.objects.bulk_update(pages, ['quality'], batch_size=500)
    return len(pages)


def page_reading(page: Page) -> str:
    """layer · confirmed · unconfirmed · scan · short · none."""
    return measured(page)['reading']


def _reading(page: Page) -> str:
    if page.text_source == TextSource.LAYER:
        return 'layer'
    if not page.text:
        return 'none'
    if page.layer_letters < MIN_LAYER:
        return 'scan'
    return 'confirmed' if confirmed(page, page.text) else 'unconfirmed'


def texts_not_found(issue: Issue) -> list[dict]:
    """The contents' entries the structuring could not find in the pages (from the issue's texts.json)."""
    path = Path(settings.CORPUS_DIR) / 'reports' / 'issues' / issue.key / 'texts.json'
    if not path.exists():
        return []
    items = json.loads(path.read_text())
    return [{'title': i['toc']['title'], 'page': i['toc'].get('page')} for i in items if i.get('stop') == 'not_found']


def issue_quality(issue: Issue) -> dict:
    pages = []
    counts = {'layer': 0, 'confirmed': 0, 'unconfirmed': 0, 'scan': 0, 'short': 0, 'none': 0}
    for page in issue.document.pages.select_related('document').order_by('index'):
        m = measured(page)
        counts[m['reading']] += 1
        pages.append({'index': page.index, 'printed': page.printed_number, 'reading': m['reading'],
                      'suspect': len((m['check'] or {}).get('suspect', []))})
    return {'pages': pages, 'counts': counts, 'not_found': texts_not_found(issue)}
