"""The password in front of the whole site while it is shown to a few (25 Oct 2026). One shared password
(GATE_PASSWORD; empty, no gate), a signed cookie for 30 days that a changed password voids. nginx asks `check/` before
every file it serves and every call to the MCP server; GateMiddleware asks the same of every request Django answers."""
import hmac

from django.conf import settings
from django.core import signing
from django.utils.crypto import salted_hmac

from config.caching import counters as cache

COOKIE = 'law_gate'
DAYS = 30
TRIES = 10              # wrong passwords from one address in TRIES_MINUTES before it waits
TRIES_MINUTES = 10


def on() -> bool:
    return bool(settings.GATE_PASSWORD)


ADMITTED = 'in'         # what the cookie says: nothing about the password


def _signer() -> signing.TimestampSigner:
    """The cookie's signer, keyed by the password and SECRET_KEY together. The cookie carries a constant, so it tells
    nothing of the password, and no guess can be tried against it without the server's secret (it once carried the first
    64 bits of the password's unsalted hash); a changed password changes the key and voids every cookie."""
    key = salted_hmac('law.gate.key', settings.GATE_PASSWORD, secret=settings.SECRET_KEY, algorithm='sha256')
    return signing.TimestampSigner(key=key.hexdigest(), salt='law.gate')


def ticket() -> str:
    return _signer().sign(ADMITTED)


def admitted(request) -> bool:
    value = request.COOKIES.get(COOKIE, '')
    try:
        return hmac.compare_digest(_signer().unsign(value, max_age=DAYS * 86400), ADMITTED)
    except signing.BadSignature:
        return False


def client(request) -> str:
    """The reader's address: the last one nginx appended, as the public API counts it (NUM_PROXIES 1), an IPv6 one by
    its /64 (apps/opendata/throttles.py `bucket`)."""
    from apps.opendata.throttles import bucket
    return bucket(request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[-1].strip() or request.META.get('REMOTE_ADDR', ''))


def attempt(request, password: str) -> str:
    """'ok', 'wrong' or 'wait' (too many wrong ones from this address)."""
    key = f'gate:tries:{client(request)}'
    if cache.get(key, 0) >= TRIES:
        return 'wait'
    if hmac.compare_digest(password.encode(), settings.GATE_PASSWORD.encode()):
        return 'ok'
    cache.add(key, 0, TRIES_MINUTES * 60)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, TRIES_MINUTES * 60)
    return 'wrong'
