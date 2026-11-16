"""Serving a file with byte ranges: without 206 answers Chromium treats a file as
unseekable. Every answer is `no-store`: the link is short-lived, and no browser or CDN may keep a copy that outlives
it or a deletion."""
import re
from pathlib import Path

from django.http import FileResponse, StreamingHttpResponse

_RANGE = re.compile(r'bytes=(\d{1,15})?-(\d{1,15})?$')
_CHUNK = 64 * 1024


def _uncached(response):
    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, no-store, max-age=0'
    return response


def _slice(path: Path, start: int, length: int):
    with path.open('rb') as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            data = fh.read(min(_CHUNK, remaining))
            if not data:
                return
            remaining -= len(data)
            yield data


def span(header: str, size: int) -> tuple[int, int] | None:
    """(first, last) byte of a satisfiable single range, else None. `bytes=-N` is the last N bytes."""
    match = _RANGE.match(header)
    if match is None or size == 0:
        return None
    first, last = match[1], match[2]
    if first is None and last is None:
        return None
    if first is None:
        count = int(last)
        return (max(0, size - count), size - 1) if count > 0 else None
    start = int(first)
    end = min(int(last), size - 1) if last is not None else size - 1
    return (start, end) if start <= end else None


def respond(request, path: Path, content_type: str):
    size = path.stat().st_size
    found = span(request.headers.get('Range', ''), size)
    if found is None:
        return _uncached(FileResponse(path.open('rb'), content_type=content_type))
    start, end = found
    response = StreamingHttpResponse(_slice(path, start, end - start + 1), content_type=content_type, status=206)
    response['Content-Range'] = f'bytes {start}-{end}/{size}'
    response['Content-Length'] = str(end - start + 1)
    return _uncached(response)
