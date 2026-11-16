"""A day of reading per reader (4 Nov 2026), so that one client cannot copy the whole corpus in a day: the list of
every text (/api/corpus/texts/) is the server's own, and each answer counts the law's words it gives.

What counts is what an answer gives of the law's words: the articles a text's answer carries, an article's preview, an
article put in a Word file, a printed page's reading, an outline's first words, an article on its discussion's page
(`metered`, for any other door that gives them). The day is Morocco's:

- a browser, known by its cookie, is given READING_BUDGET of them;
- every request without that cookie from one address together is given READING_BUDGET: a client that sends no cookie
  was a new browser each time;
- the browsers and those requests behind one address are given SHARED days together (an IPv6 address by its /56: a home
  line is given a /56 or a /48 and may use any of its 256 or 65,536 /64s); READING_OPERATOR_CEILING, when whoever runs
  the site sets it, holds every one of them on one network operator together.

A request without the cookie past its address's day, while the address's browsers may still read, is a newcomer: it is
given its cookie and asked again (a 307 to the same address), so a new reader behind a shared mobile address is never
refused for what others sent. Past the day the answer is 429 `reading.check` when Cloudflare's Turnstile is set (a person
who passes it is given a day of their own, a cookie until midnight; only past the day, and READING_PASSES an address a
day) and `reading.limit` when it is not. The server's own requests (the prerender through its tunnel, the jobs) are not
counted, nor are the search engines' crawlers from their published addresses
(apps/seo/services/crawlers.py). A law's page drawn with its words counts its articles too
(apps/corpus/services/heads.py): the words in the HTML are no way around the day.

A request with a key (X-Api-Key) is read by its access, not by a browser or an address: the access's articles a day
(apps/opendata/services/usage.py), counted with what its other doors gave (the versioned API, the assistants' server),
with no address ceiling; past them the answer is 429 (`key`, `articles`). A key that opens nothing never reaches here
on the site's doors (apps/opendata/middleware.py answers it 401); anywhere else it reads as no key.

Kept: a count under a key that changes every day (a hash of the day and the address), gone the next day; never the
address. The MCP has its own shares (apps/mcp/services/quotas.py)."""
import hashlib
import hmac
import json
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from django.conf import settings
from django.core import signing
from django.http import HttpResponseRedirect, JsonResponse
from django.utils import timezone

from apps.corpus.services import operators
from apps.opendata.throttles import address, bucket
from config.caching import counters as cache

LOOPBACK = {'127.0.0.1', '::1'}
COOKIE = 'reading_pass'
# A browser's own day (HM17 of the hard-moment review, 7 Nov 2026): operators put many subscribers behind one IPv4
# address, so everyone behind it shared one day, about a hundred article opens. A random number in a first-party cookie
# gives each browser its day; the address keeps a ceiling of SHARED days for all its browsers together, so a crawler
# that changes cookies is held as before; the requests with no cookie share one day of the address's.
READER = 'reader'
SHARED = 10
AGAIN = 'reader'            # the mark of a newcomer's request asked again with its new cookie
V6 = 56                     # the bits of an IPv6 address the day of reading counts by
SALT = 'apps.corpus.reading'
VERIFY = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'


def internal(request) -> bool:
    """The server's own request: the reader's address is the machine's (nginx and Cloudflare say the visitor's)."""
    return address(request) in LOOPBACK


def free(request) -> bool:
    """A request no day of reading holds: the server's own, or a search engine's crawler from an address its maker
    publishes (IX10 of the search-engines review: Google renders a page with the answers a browser asks for, from a few
    addresses, all day). The fetchers an assistant's user drives are readers like any other."""
    from apps.seo.services import crawlers
    return internal(request) or bool(crawlers.of(request))


def _seconds_left() -> int:
    now = timezone.localtime()
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=now.tzinfo)
    return max(60, int((midnight - now).total_seconds()))


def _passed(request) -> str:
    """The day's pass a reader got from the check, if it is today's."""
    try:
        held = signing.loads(request.COOKIES.get(COOKIE, ''), salt=SALT)
    except signing.BadSignature:
        return ''
    return held.get('id', '') if held.get('day') == str(timezone.localdate()) else ''


def _browser(request) -> str:
    """This browser's number, from its cookie, if the cookie is ours."""
    try:
        return signing.loads(request.COOKIES.get(READER, ''), salt=SALT).get('id', '')
    except signing.BadSignature:
        return ''


def _newcomer(request) -> str:
    """A browser that came without our cookie: a number of its own, given back with the answer, so that from its next
    request on it has a day of its own."""
    raw = getattr(request, '_request', request)
    if not getattr(raw, '_reader_new', ''):
        raw._reader_new = secrets.token_hex(8)
    return raw._reader_new


def _keyed(request):
    """The holder of the request's key when it carries one that opens something, else None."""
    from apps.opendata.services import keys
    try:
        return keys.holder(request)
    except keys.Refused:
        return None


def _reader(request) -> tuple[str, int]:
    """Whose day it is and what it holds: a pass, a browser by its cookie, or every request without the cookie from the
    address together. (A key's day is its access's: `_keyed`.)"""
    if passed := _passed(request):
        return f'pass:{passed}', settings.READING_BUDGET
    if browser := _browser(request):
        return f'browser:{browser}', settings.READING_BUDGET
    return f'cookieless:{_address(request)}', settings.READING_BUDGET


def _address(request) -> str:
    return bucket(address(request), v6=V6)


def _shared(request) -> str:
    """The ceiling's counter: every browser behind the address together."""
    return f'all:{_address(request)}'


def _operator(request) -> int | None:
    """The reader's network operator (its ASN), looked up once a request and only while its ceiling is set."""
    raw = getattr(request, '_request', request)
    if not hasattr(raw, '_reader_operator'):
        raw._reader_operator = operators.operator(address(request))
    return raw._reader_operator


def _limits(request, reader: str, budget: int) -> list[tuple[str, int]]:
    """The counts a reader's answers go to, each with its limit, its own day first; for a browser and for the
    requests without the cookie, their address's ceiling and, when READING_OPERATOR_CEILING is set, their network
    operator's. A pass is held by its own day alone."""
    limits = [(_key(reader), budget)]
    if reader.startswith(('browser:', 'cookieless:')):
        limits.append((_key(_shared(request)), budget * SHARED))
        if settings.READING_OPERATOR_CEILING and (asn := _operator(request)):
            limits.append((_key(f'operator:{asn}'), settings.READING_OPERATOR_CEILING))
    return limits


def _key(reader: str) -> str:
    day = timezone.localdate()
    return f'reading:{day:%Y%m%d}:' + hmac.new(settings.SECRET_KEY.encode(), f'{day}|{reader}'.encode(),
                                               hashlib.sha256).hexdigest()[:24]


def _state(request) -> str:
    """'' while this reader may read; 'new' for a request without the cookie past its address's day for such
    requests while the address's browsers may still read; 'reached' past the day; 'key' for a key's access past its
    articles today."""
    if held := _keyed(request):
        from apps.opendata.services import usage
        return 'key' if usage.reached(held) else ''
    if not settings.READING_BUDGET or free(request):
        return ''
    reader, budget = _reader(request)
    limits = _limits(request, reader, budget)
    counts = cache.get_many([key for key, _ in limits])
    past = [(counts.get(key) or 0) >= most for key, most in limits]
    if not any(past):
        return ''
    return 'new' if reader.startswith('cookieless:') and not any(past[1:]) else 'reached'


def reached(request) -> bool:
    """Whether this reader has had their day."""
    return bool(_state(request))


def checking() -> bool:
    return bool(settings.TURNSTILE_SITE_KEY and settings.TURNSTILE_SECRET_KEY)


def refused(request):
    """The answer for a reader past their day, None for the others. A plain Django response, so any view may send it."""
    state = _state(request)
    if not state:
        return None
    if state == 'key':
        # Counted on the access as a call refused for its articles, as the versioned API counts its own.
        from apps.opendata.services import usage
        usage.refuse(_keyed(request), 'articles')
        response = JsonResponse({'errors': [{'field': 'key', 'code': 'articles'}]}, status=429)
        response['Cache-Control'] = 'no-store'
        response['Retry-After'] = str(_seconds_left())
        return response
    raw = getattr(request, '_request', request)
    if state == 'new' and AGAIN not in raw.GET:
        return _welcome(raw)
    return _limit('check' if checking() else 'limit')


def _limit(code: str) -> JsonResponse:
    response = JsonResponse({'errors': [{'field': 'reading', 'code': code}]}, status=429)
    response['Cache-Control'] = 'no-store'
    response['Retry-After'] = str(_seconds_left())
    return response


def _welcome(raw):
    """A newcomer past its address's day for requests without the cookie: its cookie, and the same request asked again
    with it (307 keeps the method and the body). A browser follows it and has a day of its own; a client that keeps no
    cookie comes back marked and without one, and is refused."""
    query = raw.GET.copy()
    query[AGAIN] = '1'
    response = HttpResponseRedirect(f'{raw.path}?{query.urlencode()}')
    response.status_code = 307
    _given(response, _newcomer(raw))
    response['Cache-Control'] = 'no-store'
    return response


def metered(request, answer, n: int = 1):
    """A door other than a text's own that gives the law's words (an article on its discussion's page, a link's
    picture, a printed page's image, a source file): the refusal for a reader past their day, and `answer` is never
    called; else `answer()`, with `n` counted when it is a 200. An answer that raises (a 404) counts nothing."""
    if (stop := refused(request)) is not None:
        return stop
    response = answer()
    if response.status_code == 200:
        spend(request, n)
    return response


def spend(request, n: int) -> None:
    """Count what an answer gave: on the key's access for a keyed request, on the reader's day otherwise."""
    if n <= 0:
        return
    if held := _keyed(request):
        from apps.opendata.services import usage
        usage.spend(held, n)
        return
    if not settings.READING_BUDGET or free(request):
        return
    reader, budget = _reader(request)
    for key, _ in _limits(request, reader, budget):
        _add(key, n)
    getattr(request, '_request', request)._reader_counted = True
    if reader.startswith('cookieless:'):
        # Its cookie goes with the answer (`give`), and what it read is that browser's day already.
        _add(_key(f'browser:{_newcomer(request)}'), n)


def _add(key: str, n: int) -> None:
    timeout = 26 * 3600
    cache.add(key, 0, timeout=timeout)
    try:
        cache.incr(key, n)
    except ValueError:          # gone between add and incr
        cache.set(key, n, timeout=timeout)


def give(request, response):
    """The cookie for a browser that came without it and was counted (apps.corpus.middleware): a random number,
    nothing else, what lets it have its own day (/privacy says so). Such an answer is not one to share."""
    raw = getattr(request, '_request', request)
    new = getattr(raw, '_reader_new', '')
    if not new or not getattr(raw, '_reader_counted', False) or response.status_code >= 400:
        return response
    _given(response, new)
    response['Cache-Control'] = 'private, max-age=60'
    return response


def _given(response, new: str) -> None:
    response.set_cookie(READER, signing.dumps({'id': new}, salt=SALT), max_age=365 * 86400, httponly=True,
                        samesite='Lax', secure=not settings.DEBUG)


def no_pass(request) -> tuple[str, int] | None:
    """Why this reader is given no pass now (the error's code and status), None when they may be: a pass was given to
    anyone who solved a check, also before any limit, so a crawler could buy as many days as it liked. Now only a
    reader past their day may have one, and READING_PASSES an address a day."""
    if not reached(request):
        return 'not_reached', 400
    if (cache.get(_key(f'passes:{_address(request)}')) or 0) >= settings.READING_PASSES:
        return 'limit', 429
    return None


def verify(token: str, request) -> bool:
    """Cloudflare's word on a Turnstile token."""
    data = urllib.parse.urlencode({'secret': settings.TURNSTILE_SECRET_KEY, 'response': token,
                                   'remoteip': address(request)}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(VERIFY, data=data), timeout=10) as answer:
            return bool(json.load(answer).get('success'))
    except (OSError, ValueError):
        return False


def grant(request, response) -> None:
    """A day of one's own, until midnight: a cookie holding a random id and the day, signed; one of its address's
    passes for the day."""
    _add(_key(f'passes:{_address(request)}'), 1)
    held = signing.dumps({'id': secrets.token_hex(8), 'day': str(timezone.localdate())}, salt=SALT)
    response.set_cookie(COOKIE, held, max_age=_seconds_left(), secure=not settings.DEBUG, httponly=True, samesite='Lax')
