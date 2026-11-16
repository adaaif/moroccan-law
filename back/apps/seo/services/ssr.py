"""The app's page drawn on the server (IX1 of the search-engines review, 9 Nov 2026): Django sends the answers a page asks for to
the drawing service (web/scripts/ssr-server.mjs, the law-ssr unit, SSR_URL) and gets its HTML back. Nothing is drawn
without SSR_URL (development, the tests); a page the service does not draw gives '' and is sent with its head alone,
as before.

The service draws one page at a time. When it is too slow (no answer in SSR_TIMEOUT seconds), busy (503: its short
queue is full) or down, no page is sent to it for SSR_REST seconds: every worker had waited out the timeout on every
page, so about three requests a second for laws not drawn yet held all of them and the API stopped with them. That pause
is kept with the limits' counts (config/caching.py `counters`), so every worker keeps it. A page it could not draw
(500) is that page's own fault: the others go on being drawn."""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from config.caching import counters

log = logging.getLogger(__name__)
RESTING = 'ssr:resting'


def resting() -> bool:
    """Whether the service is left alone for now."""
    try:
        return bool(counters.get(RESTING))
    except Exception:  # noqa: BLE001 — without the store, the page is drawn as before
        return False


def _rest(path: str, why) -> None:
    log.warning('ssr: %s not drawn (%s); nothing sent for %s s', path, why, settings.SSR_REST)
    if settings.SSR_REST > 0:
        try:
            counters.set(RESTING, 1, timeout=settings.SSR_REST)
        except Exception:  # noqa: BLE001
            pass


def draw(path: str, seed: list[tuple[list, bytes]], one: str = '') -> str:
    """The HTML of the app at `path` with these [query key, answer as sent] pairs; '' when it could not be drawn."""
    if not settings.SSR_URL or resting():
        return ''
    body = b'[' + b','.join(b'[' + json.dumps(key).encode() + b',' + data + b']' for key, data in seed) + b']'
    query = urllib.parse.urlencode({'path': path, **({'one': one} if one else {})})
    request = urllib.request.Request(f"{settings.SSR_URL.rstrip('/')}/render?{query}", data=body,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=settings.SSR_TIMEOUT) as answer:
            return answer.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        if exc.code == 503:
            _rest(path, exc)
        else:
            log.warning('ssr: %s not drawn (%s)', path, exc)
        return ''
    except OSError as exc:          # no answer in time, refused, cut: the service, not the page
        _rest(path, exc)
        return ''
    except ValueError as exc:
        log.warning('ssr: %s not drawn (%s)', path, exc)
        return ''
