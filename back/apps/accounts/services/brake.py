"""The brake on wrong passwords, per account AND address.

The «auth» throttle counts an address and has to stay loose (a Moroccan carrier puts a city behind one address), so
nothing stopped a script guessing one account's password for as long as it liked. Failures are counted in the cache:

- ONE ADDRESS ON ONE ACCOUNT: LOGIN_BRAKE_FAILURES within LOGIN_BRAKE_WINDOW_S and that address waits LOGIN_BRAKE_LOCK_S
  on that account. A stranger who knows a username locks only their own address out.
- THE ACCOUNT FROM EVERYWHERE: LOGIN_BRAKE_ACCOUNT_FAILURES within the window lock the account for every address.

The lock is on the password door only (sign-in, and the doors that ask for the password again: a new password, a new
address, deleting the account): a reset link still gets the account's holder in, and a completed reset or a new
password lifts both levels (`clear(user)`). A correct password never slips through a lock. A sign-in clears its own
address's count.
The address is the one the throttles count (nginx's, from Cloudflare's header).

With Cloudflare's Turnstile set (the check the day of reading uses: corpus/services/reading.py), a lock at the sign-in
asks for the check instead of refusing: a person who passes it has their password judged, and a wrong one still counts.
So a stranger's wrong passwords cannot keep an account's holder out, nor the holder's neighbours behind one carrier
address; each try past the threshold costs a check. Without the keys, the lock refuses as it always did.
"""
import time

from django.conf import settings
from config.caching import counters as cache
from apps.opendata.throttles import ident


def address(request) -> str:
    return ident(request) or '-'


def _gen(user) -> int:
    """The account's generation: `clear(user)` moves it on, which forgets every address's count and lock at once."""
    return int(cache.get(f'brake:gen:{user.pk}') or 0)


def _keys(user, ip):
    base = f'brake:{user.pk}:{_gen(user)}'
    return {'here_n': f'{base}:{ip}:n', 'here_until': f'{base}:{ip}:until',
            'all_n': f'{base}:n', 'all_until': f'{base}:until'}


def _left(until) -> int:
    return max(0, int(until - time.time())) if until else 0


def wait(user, ip: str) -> int:
    """Seconds this address must still wait before trying a password on this account; 0 when it may."""
    k = _keys(user, ip)
    got = cache.get_many([k['here_until'], k['all_until']])
    return max(_left(got.get(k['here_until'])), _left(got.get(k['all_until'])))


def _count(key) -> int:
    cache.add(key, 0, timeout=settings.LOGIN_BRAKE_WINDOW_S)
    try:
        return cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, timeout=settings.LOGIN_BRAKE_WINDOW_S)
        return 1


def failed(user, ip: str) -> int:
    """Count one wrong password from `ip`; the wait when this one locked a level, else 0."""
    k = _keys(user, ip)
    lock = settings.LOGIN_BRAKE_LOCK_S
    locked = False
    for n, until, limit in (('here_n', 'here_until', settings.LOGIN_BRAKE_FAILURES),
                            ('all_n', 'all_until', settings.LOGIN_BRAKE_ACCOUNT_FAILURES)):
        if _count(k[n]) >= limit:
            cache.set(k[until], time.time() + lock, timeout=lock)
            cache.delete(k[n])
            locked = True
    return lock if locked else 0


def clear(user, ip: str | None = None) -> None:
    """A sign-in from `ip` clears that address's count. Without an address (a reset, a new password): every level and
    every address."""
    if ip is not None:
        k = _keys(user, ip)
        cache.delete_many([k['here_n'], k['here_until']])
        return
    # No expiry: the generation must outlive every count and lock made under it.
    cache.set(f'brake:gen:{user.pk}', _gen(user) + 1, timeout=None)


# What the backend found, for the view that answers: `authenticate()` returns an account or None, and the sign-in
# says more than «wrong» (the minutes of a lock, a typo's fix when no account holds the address).

def _raw(request):
    return getattr(request, '_request', request)


def mark(request, **found) -> None:
    if request is not None:
        raw = _raw(request)
        raw._brake = {**getattr(raw, '_brake', {}), **found}


def held(request) -> int:
    """Seconds the brake held this request's password check (0: it was checked)."""
    return (getattr(_raw(request), '_brake', None) or {}).get('wait', 0)


def known(request) -> bool:
    """Whether this request's login named an account that may sign in."""
    return bool((getattr(_raw(request), '_brake', None) or {}).get('known'))


def offer(request, token: str) -> None:
    """The Turnstile token a sign-in carries, judged only if the brake holds (an answer from Cloudflare each time)."""
    mark(request, check=str(token or '')[:2048])


def checking() -> bool:
    """Whether a lock asks for Turnstile (both keys set) rather than refusing."""
    from apps.corpus.services import reading
    return reading.checking()


def passed(request) -> bool:
    """Whether this request carries a Turnstile token Cloudflare accepts."""
    token = (getattr(_raw(request), '_brake', None) or {}).get('check', '') if request is not None else ''
    if not token or not checking():
        return False
    from apps.corpus.services import reading
    return reading.verify(token, request)
