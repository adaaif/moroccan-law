"""Pictures drawn because someone asked for one: a printed page's image for reading, a link's picture, a card made to
be forwarded (OP15 of the open-source audit). Each was drawn on its first request and kept for good, so one address
asking for new ones kept workers drawing (a long article's card took more than a second and a half) and the folders
grew without end.

- At most DRAWING_AT_ONCE pictures are drawn at a time in the whole site, and one address draws at most
  DRAWING_PER_MINUTE new ones a minute. Past either, `Busy`: the door answers 503 `picture.busy` at once, and nothing is
  drawn. A picture already drawn is served whatever the counts: what honest readers behind one mobile address ask for,
  and what a platform's link previews fetch from its few addresses, is mostly drawn already, and drawing is what costs.
- A picture is written whole to a file of its own and renamed into place: no reader is sent a half-written file.
- Each folder keeps at most DRAWN_FOLDER_MOST bytes: past it, the pictures used least lately are removed (serving one
  renews its time, once a day at most), looked at once a minute at most, after a drawing. One removed is drawn again
  when it is asked for."""
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse

from config.caching import counters

HELD = 60          # seconds a drawing holds its place at most: a worker killed while drawing gives it back by then
RENEWED = 24 * 3600
LOOKED = 60
RETRY = 10


class Busy(Exception):
    """No picture may be drawn now: every place is taken, or the address drew its share this minute."""


def busy() -> JsonResponse:
    response = JsonResponse({'errors': [{'field': 'picture', 'code': 'busy'}]}, status=503)
    response['Retry-After'] = str(RETRY)
    response['Cache-Control'] = 'no-store'
    return response


def picture(out: Path, draw: Callable[[Path], None], request=None) -> Path:
    """`out`, drawn by `draw(path)` into a file renamed to it when it is not there yet. Raises Busy. `request` is the
    asker's, whose address is counted (none for the server's own commands, which draw without counts)."""
    if out.exists():
        _used(out)
        return out
    place = _take(request) if request is not None else None
    try:
        if not out.exists():            # another worker may have drawn it meanwhile
            out.parent.mkdir(parents=True, exist_ok=True)
            part = out.with_name(f'.{out.stem}.{secrets.token_hex(4)}{out.suffix}')
            try:
                draw(part)
                part.replace(out)
            finally:
                part.unlink(missing_ok=True)
    finally:
        if place:
            counters.delete(place)
    if request is not None and counters.add(f'drawing:looked:{out.parent}', 1, timeout=LOOKED):
        keep(out.parent, settings.DRAWN_FOLDER_MOST)
    return out


def _take(request) -> str:
    """A place to draw in, held until the drawing ends; Busy when none is free or the address drew its share."""
    from apps.opendata.throttles import ident

    place = next((f'drawing:place:{i}' for i in range(settings.DRAWING_AT_ONCE)
                  if counters.add(f'drawing:place:{i}', 1, timeout=HELD)), None)
    if place is None:
        raise Busy
    minute = f'drawing:by:{ident(request)}:{int(time.time() // 60)}'
    counters.add(minute, 0, timeout=120)
    if counters.incr(minute) > settings.DRAWING_PER_MINUTE:
        counters.delete(place)
        raise Busy
    return place


def _used(path: Path) -> None:
    try:
        if time.time() - path.stat().st_mtime > RENEWED:
            os.utime(path)
    except OSError:
        pass


def keep(folder: Path, most: int) -> int:
    """The folder's pictures (its files, not its folders) brought under `most` bytes, to nine tenths of it, the least
    lately used removed first; a part left by a drawing that died is removed after an hour. Gives how many were removed."""
    now = time.time()
    files, total, removed = [], 0, 0
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return 0
    for entry in entries:
        try:
            if not entry.is_file(follow_symlinks=False):
                continue
            st = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if entry.name.startswith('.'):
            if now - st.st_mtime > 3600:
                Path(entry.path).unlink(missing_ok=True)
            continue
        files.append((st.st_mtime, st.st_size, entry.path))
        total += st.st_size
    if total <= most:
        return 0
    for _, size, path in sorted(files):
        if total <= most * 0.9:
            break
        Path(path).unlink(missing_ok=True)
        total -= size
        removed += 1
    return removed
