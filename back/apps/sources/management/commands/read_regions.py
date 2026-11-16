"""The word boxes of the pages articles stand on, read ahead (N13 of the read-and-trusted review), so lighting an article
on its printed page never runs Tesseract inside a request. One page at a time, for --minutes at most: the pages readers
asked for first (`regions.want`); then, for --words-minutes at most, the pages of the doubtful words «ساهم» asks
visitors about (apps/quality/services/place.py `run`: their words placed on the page); then the documents of the
shelf's and the topics' named texts, then every issue's pages, newest first. A page already read is skipped; the next
night goes on where this one stopped. Every page read has its doubtful words placed.

    nice -n 19 manage.py read_regions --minutes 240     # the server's timer (deploy/law-regions.timer)
"""
import time

from django.core.management.base import BaseCommand

from apps.corpus.models import Version, latest_ids
from apps.corpus.services import codes
from apps.quality.services import place
from apps.sources.models import Issue, Page
from apps.sources.services import regions


class Command(BaseCommand):
    help = 'Read ahead the word boxes of the pages articles stand on (Tesseract, one page at a time).'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=float, default=240)
        parser.add_argument('--wanted-only', action='store_true')
        parser.add_argument('--words-minutes', type=float, default=45,
                            help="Minutes at most for the doubtful words' pages, after the pages readers asked for.")

    def handle(self, *args, minutes, wanted_only, words_minutes, **options):
        stop = time.monotonic() + minutes * 60
        wanted = read_wanted()
        done = empty = placed = 0
        words = {'read': 0, 'placed': 0}

        def doubtful():
            words.update(place.run(min(stop, time.monotonic() + words_minutes * 60)))

        for page in pages(wanted, wanted_only, then=doubtful if words_minutes > 0 else None):
            if time.monotonic() > stop:
                break
            if regions.read_yet(page):
                continue
            lines, _ = regions.lines_of(page)
            done += bool(lines)
            empty += not lines
            placed += place.place_page(page)
        # The list keeps only the pages still to read (a page gone since counts as read).
        left = {(p.document_id, p.index) for p in _pages_of(wanted) if not regions.read_yet(p)}
        regions.wanted_path().write_text(''.join(f'{d} {i}\n' for d, i in sorted(left))) if wanted else None
        self.stdout.write(f'{done} pages read, {empty} without words; {len(left)} asked for still to read; '
                          f"{words['read']} pages of doubtful words read, {placed + words['placed']} words placed")


def read_wanted() -> set[tuple[int, int]]:
    path = regions.wanted_path()
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            out.add((int(parts[0]), int(parts[1])))
    return out


def _pages_of(keys: set[tuple[int, int]]) -> list[Page]:
    rows = Page.objects.select_related('document').filter(document_id__in={d for d, _ in keys})
    return sorted((p for p in rows if (p.document_id, p.index) in keys), key=lambda p: (p.document_id, p.index))


def pages(wanted: set[tuple[int, int]], wanted_only: bool, then=None):
    """Asked for first, then the named texts' documents, then the issues newest first; each page once. `then` is
    called between the pages asked for and the others (the doubtful words' share of the night)."""
    seen: set[tuple[int, int]] = set()

    def fresh(rows):
        for page in rows:
            if (page.document_id, page.index) not in seen:
                seen.add((page.document_id, page.index))
                yield page

    yield from fresh(_pages_of(wanted))
    if wanted_only:
        return
    if then is not None:
        then()
    texts = [t for t in codes.texts_of([k for k, _ in codes.SHELF + codes.MORE]).values() if t is not None]
    rows = Version.objects.filter(text__in=texts).values_list('pk', 'text_id', 'valid_from', 'consolidation')
    latest = set(latest_ids(rows).values())
    docs = set(Version.objects.filter(pk__in=latest, source_document__isnull=False)
               .values_list('source_document_id', flat=True))
    docs |= set(Issue.objects.filter(pk__in={t.first_published_in_id for t in texts}, document__isnull=False)
                .values_list('document_id', flat=True))
    yield from fresh(Page.objects.select_related('document').filter(document_id__in=docs)
                     .order_by('document_id', 'index').iterator(chunk_size=500))
    yield from fresh(Page.objects.select_related('document').filter(document__issue__isnull=False)
                     .order_by('-document__issue__date', 'index').iterator(chunk_size=500))
