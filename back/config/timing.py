"""Each stage of an answer timed (B27 of the search plan): a service starts a stopwatch, `lap = laps()`, and calls
`lap('words')` where each stage ends; the answer carries the stages in its Server-Timing header («words;dur=12.4,
snippets;dur=3.1»), which a browser's network panel and `perf_report` read. Outside a request nothing is kept.

The header goes only to the machine itself (a request with no proxy in between: perf_report, the jobs, a developer's
server) and to signed-in staff: it says which stage of a query costs most and whether an answer was built or kept,
which a client has no use for."""
import time
from contextvars import ContextVar

from django.utils.functional import SimpleLazyObject, empty

_stages: ContextVar[dict | None] = ContextVar('stages', default=None)
LOOPBACK = {'127.0.0.1', '::1'}


def laps():
    last = time.perf_counter()

    def lap(name: str):
        nonlocal last
        now = time.perf_counter()
        if (seen := _stages.get()) is not None:
            seen[name] = seen.get(name, 0) + (now - last) * 1000
        last = now
    return lap


def shown_to(request) -> bool:
    """The machine itself, with no proxy in between (the public always comes through nginx, which sets
    X-Forwarded-For), or staff whose account the answer already knew (never a query of its own to find out)."""
    if request.META.get('REMOTE_ADDR') in LOOPBACK and 'HTTP_X_FORWARDED_FOR' not in request.META:
        return True
    user = request.__dict__.get('user')
    if user is None or (isinstance(user, SimpleLazyObject) and user._wrapped is empty):
        return False
    return bool(getattr(user, 'is_authenticated', False) and user.is_staff)


class ServerTiming:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _stages.set({})
        try:
            response = self.get_response(request)
            seen = _stages.get()
        finally:
            _stages.reset(token)
        if seen and shown_to(request):
            response['Server-Timing'] = ', '.join(f'{name};dur={ms:.1f}' for name, ms in seen.items())
        return response
