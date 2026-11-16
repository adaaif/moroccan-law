"""The titles a suggestion finds as the words are typed: every text's title row, kept in the process while the
corpus generation holds and in a file a new worker reads (RD13 of the readers review), joined in one string in which a
typed word is looked for where a word starts; then ranked: the words together first, the shelf's code, the kingdom's
own texts, laws before decrees, the newest."""
import bisect
import fcntl
import hashlib
import marshal
import os
import re
import tempfile
import time
from pathlib import Path

from django.conf import settings
from django.db.models import F

from apps.search.models import SearchEntry
from apps.search.services.search.bm25 import _shelf_paths

# Letters typed (spaces aside) before the box offers a topic, a guide, a word, a code or a title: one or two name none,
# and «ال» was in 1.5 million places of the titles. A number of two digits still opens its famous articles («49»).
SUGGEST_FROM = 3

_TITLES: dict = {'generation': None, 'rows': [], 'blob': '', 'starts': []}
TITLES_READ = 5000     # places of a typed word a suggestion reads in the titles at most (see _titles)


def _titles_table() -> list[tuple]:
    """Every title row, laws before decrees before orders, the newest first: the order _titles ranks them in after the
    words, so a walk that stops early has read the ones it would rank first."""
    return list(SearchEntry.objects.filter(kind=SearchEntry.Kind.TEXT)
                .order_by('-weight', F('year').desc(nulls_last=True), '-id')
                .values_list('id', 'text_path', 'title_folded', 'weight', 'year'))


def _titles_file(gen: str) -> Path:
    name = hashlib.sha1(f'{settings.DATABASES["default"].get("NAME")}:{gen}'.encode(), usedforsecurity=False).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / f'law-titles-{os.getuid()}' / f'{name}.rows'


def _titles_kept(gen: str) -> list[tuple]:
    """The title rows of one corpus generation, from the file the first worker to need them kept, else from the table
    (RD13 of the readers review, 9 Nov 2026). Each worker read every title again on its first suggestion, a heavy
    query that grew slower when several workers ran it together, and workers are replaced often. Now the table is
    read once a generation, one worker at a time (the others wait for its file, not for the table),
    and a new worker reads the file. A file that cannot be read or written costs nothing but the old way."""
    path = _titles_file(gen)

    def kept():
        # marshal reads 190,000 rows in a tenth of the time JSON takes, and runs nothing it reads; the folder is the
        # server's own (0700).
        rows = marshal.loads(path.read_bytes())  # noqa: S302 — the server's own file, as said above
        if not isinstance(rows, list):
            raise ValueError(path)
        return rows

    unread = (OSError, ValueError, EOFError, TypeError)
    try:
        return kept()
    except unread:
        pass
    try:
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with open(path.parent / 'lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return kept()                       # another worker wrote it while this one waited
            except unread:
                pass
            rows = _titles_table()
            tmp = path.with_suffix(f'.{os.getpid()}.tmp')
            tmp.write_bytes(marshal.dumps(rows))
            os.replace(tmp, path)
            for old in path.parent.glob('*.rows'):  # the generations before this one: nobody reads them again
                if old != path and old.stat().st_mtime < time.time() - 3600:
                    old.unlink(missing_ok=True)
            return rows
    except OSError:
        return _titles_table()


def _title_rows() -> tuple[list[tuple], str, list[int]]:
    """(rows, blob, starts): every text's title row (row id, text address, folded title, weight, year), and the folded
    titles joined by a line break with where each starts, kept in the process for as long as the corpus generation
    holds (S23 of the performance audit): suggestions find titles in memory, not with a LIKE over every title. Without
    a generation (no Redis), read each time."""
    from apps.corpus.services import generation

    gen = generation.current('corpus')
    if gen is None or gen != _TITLES['generation']:
        rows = _titles_table() if gen is None else _titles_kept(gen)
        starts, at = [], 0
        for r in rows:
            starts.append(at)
            at += len(r[2]) + 1
        blob = '\n'.join(r[2] for r in rows)
        if gen is None:
            return rows, blob, starts
        _TITLES.update(generation=gen, rows=rows, blob=blob, starts=starts)
    return _TITLES['rows'], _TITLES['blob'], _TITLES['starts']


_FRONTS = ('وال', 'بال', 'فال', 'كال', 'لل', 'ال', 'و', 'ب', 'ل', 'ف', 'ك')


def _word_start(blob: str, at: int) -> bool:
    """`at` opens a word of `blob` (folded titles joined by line breaks), or follows one of Arabic's front letters there."""
    if at == 0 or not blob[at - 1].isalnum():
        return True
    for front in _FRONTS:
        k = at - len(front)
        if k >= 0 and blob[k:at] == front and (k == 0 or not blob[k - 1].isalnum()):
            return True
    return False


def _holds_word(title: str, word: str) -> bool:
    at = title.find(word)
    while at != -1:
        if _word_start(title, at):
            return True
        at = title.find(word, at + 1)
    return False


# A title that says its text only changes another (folded as the titles are kept).
_AMENDS = re.compile(r'(?:بتغيير|بتتميم|يغير|يتمم|تغير بموجبه|يتم بمقتضاه|يغير بمقتضاه|يقضي بتغيير|يقضي بتتميم|بنسخ|بالمصادقه علي المرسوم بقانون)')


def _places(blob: str, starts: list[int], word: str) -> tuple[set[int], bool]:
    """The titles (by row) in which `word` opens a word, read from at most TITLES_READ of its places in `blob`, and
    whether that was all of them."""
    seen: set[int] = set()
    at, read = blob.find(word), 0
    while at != -1 and read < TITLES_READ:
        read += 1
        # A word's start only, after a space or the letters Arabic writes on a word's front (HM36 of
        # the hard-moment review: «طردوني» suggested a 1915 dahir by «طرد» inside «بنوطردام»).
        if _word_start(blob, at):
            seen.add(bisect.bisect_right(starts, at) - 1)
        at = blob.find(word, at + 1)
    return seen, at == -1


def _titles(words: list[str], limit: int) -> list[tuple]:
    """The texts whose folded title holds every word typed: the words as typed, together, first; a title that opens on
    them before one that holds them later; then laws before decrees, the newest, the shortest title. One word is looked
    for in all the titles at once (one string), the others only in the titles that hold it."""
    if not words:
        return []
    # A word of fewer than three letters names no title: «ق.م.م» (three letters as words) made this walk every «ق» of
    # 192,000 titles, and «ال» every one of its 1.5 million places, seconds of a worker for one suggestion.
    if len(max(words, key=len)) < SUGGEST_FROM:
        return []
    rows, blob, starts = _title_rows()
    phrase = ' '.join(words)
    # The longest word first, then the others, until one has fewer than TITLES_READ places: the titles that hold every
    # word are among that one's. When each is that common («رقم» is in 160,000 titles, «قرار» in 150,000), the longest
    # one's first places stand. The titles come laws first and the newest first (_titles_table), the order the ranking
    # below keeps after the words, so what such a word leaves unread are orders and old texts.
    cut = None
    for word in sorted(dict.fromkeys(w for w in words if len(w) >= SUGGEST_FROM), key=len, reverse=True):
        seen, whole = _places(blob, starts, word)
        if whole:
            break
        cut = seen if cut is None else cut
    else:
        seen = cut
    found = [rows[i] for i in seen if all(_holds_word(rows[i][2], w) for w in words)]
    shelf = set(_shelf_paths())
    # The shelf's code before the laws that amend it («مدونة الش»: the Labour Code, then 032.26 and 02.21).
    # The kingdom's own texts before the protectorate's, and a text before the laws that only amend one (RD9): «الشيك»
    # offered a dahir of 1973 that ends the functions of a man named «الشيكر» before the commerce code's laws.
    found.sort(key=lambda r: (phrase not in r[2], r[1] not in shelf, r[4] is not None and r[4] < 1956, bool(_AMENDS.search(r[2])),
                              not r[2].startswith(phrase), -r[3], r[4] is None, -(r[4] or 0), len(r[2]), -r[0]))
    return [(r[1],) for r in found[:limit]]
