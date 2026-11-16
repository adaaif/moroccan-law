"""Every request a fetcher makes to another site goes through here: the SGG, Adala, the Chamber of Representatives and
the press feeds the finance bill's watcher reads.

- One name, settings.FETCH_USER_AGENT: the project's own, with the page that says who runs it and how to write to us.
  Never a browser's, and never another site's: it has no default, and while it is empty nothing is sent (`Unnamed`).
- Only https, and only the hosts in HOSTS, redirects included: an address taken from a list or a page that names
  another host (a tampered page, a local address) is refused (`Outside`), and the fetcher passes that one file.
- A file is kept under a name it was given only once `safe_name` says it is a plain name (no folder, no «..»).
- Each host's robots.txt is read once per run and obeyed. A robots.txt that cannot be read (the site is down, or
  refuses us) means nothing is fetched from that host this run.
- A site that asks us to slow down (429 or 503) is waited for as long as its Retry-After says, up to WAIT_MAX seconds
  and TRIES times; past that, or on 401 or 403, the run stops (`Refused`). Nothing here tries another way round a
  refusal: a person asks the site.

The fetchers' own pace (one file at a time, two seconds apart) stays theirs; a robots.txt Crawl-delay longer than it
is waited too.
"""
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from django.conf import settings

WAIT_MAX = 300      # seconds: a site that asks for a longer wait is left for a later run
TRIES = 3           # answers of 429 or 503 before the run stops
WAIT_DEFAULT = 60   # a 429 or 503 with no Retry-After

# Every host a fetcher may ask, for every fetcher: the official sources, and the outlets whose feeds the finance bill's
# watcher lists for a person to read (`watch_finance_bill --press`).
HOSTS = {
    'www.sgg.gov.ma', 'sgg.gov.ma',                                         # the Bulletin, its lists, consolidations
    'adala.justice.gov.ma',                                                 # the Ministry of Justice's portal
    'www.chambredesrepresentants.ma', 'chambredesrepresentants.ma',         # bills, the finance bill's dossier
    'www.hespress.com', 'fr.hespress.com', 'medias24.com', 'www.telquel.ma', 'www.leseco.ma',
}


class Outside(ValueError):
    """An address that is not https or not on a host in HOSTS: that one file is passed (a ValueError, as the fetchers
    pass a bad address)."""


def check(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != 'https' or (parts.hostname or '').lower() not in HOSTS or parts.username or parts.port:
        raise Outside(f'{url}: not an address the fetchers may ask (https on {", ".join(sorted(HOSTS))})')
    return url


def safe_name(name: str) -> str:
    """`name` as a file name if it is a plain one: no folder, not «.» or «..», nothing hidden; else Outside."""
    plain = PurePosixPath(name.replace('\\', '/')).name
    if not name or plain != name or plain in ('.', '..') or plain.startswith('.'):
        raise Outside(f'{name!r}: not a plain file name')
    return plain


class Refused(RuntimeError):
    """The site said no, or asked for more patience than a run has: the run stops here. Not an URLError, so the
    fetchers' «one file failed, go on» never swallows it."""


class Unnamed(Refused):
    """FETCH_USER_AGENT is empty: the run stops before its first request, as on a refusal. A copy of this code tells
    the sites it reads who runs it; it never speaks under the name of the site it was copied from."""


UNNAMED = ('FETCH_USER_AGENT is empty: set it to your project\'s name and a page that says who runs it, such as '
           '«example/1 (+https://example.org/about)» (back/.env.example). Nothing was fetched.')


def agent() -> str:
    """The name every request gives, or `Unnamed` before anything is sent."""
    name = settings.FETCH_USER_AGENT.strip()
    if not name:
        raise Unnamed(UNNAMED)
    return name


class _Redirects(urllib.request.HTTPRedirectHandler):
    """A redirect is followed only to an address `check` allows, as robots.txt there allows."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check(newurl)
        if not robots(newurl).can_fetch(agent(), newurl):
            raise Refused(f'{newurl}: robots.txt of {_origin(newurl)} asks us not to fetch it; nothing fetched')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def opener() -> urllib.request.OpenerDirector:
    """An opener for one run: cookies kept between its requests (the SGG's list answers only a request that carries
    the cookie its page set), redirects checked."""
    import http.cookiejar

    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), _Redirects())


_ROBOTS: dict[str, urllib.robotparser.RobotFileParser] = {}
_LAST: dict[str, float] = {}


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f'{parts.scheme}://{parts.netloc}'


def robots(url: str, *, via=None) -> urllib.robotparser.RobotFileParser:
    """The robots.txt of the url's host, read once per process. 404 and the other «not there» answers allow
    everything (RFC 9309); 401 and 403 refuse everything; a host whose robots.txt cannot be read is not fetched."""
    origin = _origin(check(url))
    if origin in _ROBOTS:
        return _ROBOTS[origin]
    parser = urllib.robotparser.RobotFileParser(origin + '/robots.txt')
    request = urllib.request.Request(origin + '/robots.txt', headers={'User-Agent': agent()})
    try:
        with (via or urllib.request.build_opener(_Redirects())).open(request, timeout=30) as answer:
            parser.parse(answer.read(512_000).decode('utf-8', 'replace').splitlines())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise Refused(f'{origin} refuses its robots.txt to us ({exc.code}): nothing fetched; ask the site') from exc
        if exc.code == 429 or exc.code >= 500:
            raise Refused(f'{origin}/robots.txt could not be read ({exc.code}): nothing fetched this run') from exc
        parser.allow_all = True
    except (urllib.error.URLError, OSError) as exc:
        raise Refused(f'{origin}/robots.txt could not be read ({exc}): nothing fetched this run') from exc
    _ROBOTS[origin] = parser
    return parser


def _retry_after(value: str | None) -> float:
    """Retry-After in seconds: a number of seconds, or an HTTP date."""
    if not value:
        return WAIT_DEFAULT
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        return max(0.0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError):
        return WAIT_DEFAULT


def get(url: str, *, via=None, headers: dict | None = None, timeout: float = 120) -> bytes:
    """The body at `url`, asked under the site's name once its robots.txt allows it. `via` is the run's opener (its
    cookies); `headers` are added to the request. Network failures and other HTTP errors raise as urllib raises them,
    for the fetcher to say and pass; refusals raise `Refused`."""
    via = via or urllib.request.build_opener(_Redirects())
    rules = robots(check(url), via=via)
    if not rules.can_fetch(agent(), url):
        raise Refused(f'{url}: robots.txt of {_origin(url)} asks us not to fetch it; nothing fetched')
    origin = _origin(url)
    delay = rules.crawl_delay(agent())
    if delay and origin in _LAST:
        time.sleep(max(0.0, float(delay) - (time.monotonic() - _LAST[origin])))
    request = urllib.request.Request(url, headers={**(headers or {}), 'User-Agent': agent()})
    for attempt in range(1, TRIES + 1):
        _LAST[origin] = time.monotonic()
        try:
            with via.open(request, timeout=timeout) as answer:
                return answer.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise Refused(f'{url}: the site refused it ({exc.code}); the run stops: ask the site') from exc
            if exc.code not in (429, 503):
                raise
            wait = _retry_after(exc.headers.get('Retry-After') if exc.headers else None)
            if wait > WAIT_MAX or attempt == TRIES:
                raise Refused(f'{url}: the site asks us to wait ({exc.code}, {wait:.0f} s); the run stops, '
                              'a later one goes on') from exc
            time.sleep(wait)
    raise AssertionError('unreachable')
