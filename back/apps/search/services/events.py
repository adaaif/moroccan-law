"""What readers do after a search (B3 of the search plan, 24 Oct 2026), kept on the search's own anonymous row: the
answers it showed (SearchLog.shown), and each answer opened, saved, shared or copied, and whether the reader found
what they looked for (SearchEvent). Nothing names the reader. The words typed go after 90 days; the counts stay."""
import re
from datetime import timedelta

from django.utils import timezone

from apps.search.models import SearchEvent, SearchLog

PATH = re.compile(r'^/[A-Za-z0-9_\-./]{1,199}$')
BUCKETS = (10, 60, 300, 900)
KEEP_DAYS = 90


def bucket(seconds) -> int | None:
    """How long an article stayed open, rounded up to 10 s, a minute, five minutes or a quarter of an hour."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return None
    return next((b for b in BUCKETS if seconds <= b), BUCKETS[-1])


def record(log, kind, path='', rank=None, seconds=None) -> list[tuple[str, str]]:
    """Keep one event; the refusals in the one error shape's (field, code) pairs."""
    if kind not in SearchEvent.Kind.values:
        return [('kind', 'invalid')]
    if not isinstance(log, int):
        return [('log', 'invalid')]
    if path and (not isinstance(path, str) or not PATH.match(path)):
        return [('path', 'invalid')]
    if rank is not None and (not isinstance(rank, int) or not 0 <= rank <= 500):
        return [('rank', 'invalid')]
    row = SearchLog.objects.filter(pk=log).only('pk', 'opened').first()
    if row is None:
        return [('log', 'not_found')]
    SearchEvent.objects.create(log=row, kind=kind, path=path or '', rank=rank, seconds=bucket(seconds))
    if kind == SearchEvent.Kind.OPENED and rank is not None and row.opened is None:
        SearchLog.objects.filter(pk=log, opened__isnull=True).update(opened=rank)
    return []


def prune(days: int = KEEP_DAYS) -> int:
    """The words of searches older than `days` blanked; their counts, answers shown and events stay. Returns how many."""
    cutoff = timezone.now() - timedelta(days=days)
    return SearchLog.objects.filter(at__lt=cutoff).exclude(query='', folded='').update(query='', folded='')
