r"""The machines that asked the site for something, counted once a night from nginx's access log (the analytics review,
15 Nov 2026): nothing runs during a request, and nothing of a request is kept but a count. In the first half of November
2026, 99 % of 1.75 million requests came from machines.

Each line is read for its time, its IP address, its User-Agent, the path it asked for and its status. The IP address only
says whether the request is the machine's own; it, the User-Agent and the path are never written anywhere. A day's
counts replace that day's `machine.*` rows of DayCount, which this module alone writes:

- `machine.requests`, key `<family>:<kind>`: the requests of a family of User-Agents (FAMILIES) for a kind of address
  (`kind_of`);
- `machine.status`, key `<family>:<2xx|3xx|4xx|5xx>`.

A family is a crawler, a link preview (someone shared a page), a script, `self` (the machine's own requests: deploy.sh's
checks, the prerender), `none` (no User-Agent) or `browser`: everything else, the people, counted as one family so a page
can say what share machines are. A machine that says nothing of itself is counted a browser.

The line is the one deploy/nginx.conf's `log_format law` writes, nginx's combined format with the request and the
referer cut at «?» (the format and the line, kept side by side with LINE below; the test reads the format from the file):

    '$remote_addr - - [$time_local] "$request_method $law_log_path $server_protocol" '
    '$status $body_bytes_sent "$law_log_referer" "$http_user_agent"'

    2001:db8::7 - - [14/Nov/2026:08:01:02 +0000] "GET /search HTTP/1.1" 200 5120 "https://example.org/a" "<the User-Agent>"

nginx escapes «"», «\» and every byte outside printable ASCII as \xXX, so a quoted field never holds a quote; a missing
value is «-», an empty User-Agent "", and a request line nginx could not read is "- - -". The stock combined format
reads too (an older log counted by hand): its query strings are cut here before the path is looked at. A line that
reads neither way is skipped and counted.

The time is the one nginx wrote with its offset, made Morocco's day by the pinned zone rules (TIME_ZONE): a line belongs
to the day it was written in, so a day's lines span the file rotated two nights before (logrotate comes up to an hour
after midnight), last night's and today's, all three in NGINX_LOGS. One pass over the files, line by line; the counts in
memory; one delete and one insert. A day whose lines are no longer in the logs keeps its counts."""
import gzip
import re
import zlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from datetime import timezone as offset_zone
from functools import lru_cache

from django.db import transaction
from django.utils import timezone

from apps.analytics import registry
from apps.analytics.models import DayCount

PREFIX = 'machine.'
REQUESTS, STATUS = 'machine.requests', 'machine.status'

# The IP address, the time to the minute and its offset, the request, the status, the User-Agent (the bytes, the user
# and the referer read past). The format: '$remote_addr - - [$time_local] "$request_method $law_log_path $server_protocol" $status
# $body_bytes_sent "$law_log_referer" "$http_user_agent"'.
LINE = re.compile(r'(\S+) \S+ \S+ \[(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}):\d{2} ([+-]\d{4})\] "([^"]*)" (\d{3}) '
                  r'(?:\d+|-) "[^"]*" "([^"]*)"\s*$')
MONTHS = {name: n for n, name in enumerate(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov',
                                            'Dec'), 1)}
# The machine's own requests come with no CF-Connecting-IP: nginx writes the address it was asked from.
SELF = {'127.0.0.1', '::1'}

# The families, the first that matches a User-Agent named (case aside). The names are the ones the project already uses
# (apps/seo/services/crawlers.py, TRAINING in apps/seo/views.py), lowercased.
FAMILIES = [(name, re.compile(pattern, re.I)) for name, pattern in (
    # The search engines. Google's crawler for Search (the page, its images, news and videos), then its others: Search
    # Console's test, Shopping, Ads, GoogleOther.
    ('googlebot', r'Googlebot'),
    ('google-other', r'Google-[a-z]+|GoogleOther|[a-z]+-Google\b'),
    ('bingbot', r'bingbot|BingPreview|msnbot|adidxbot'),
    ('applebot', r'Applebot'),
    ('yandex', r'Yandex'),
    ('duckduckbot', r'DuckDuck(Go-Favicons-)?Bot|DuckAssistBot'),
    ('baiduspider', r'Baiduspider'),
    # The assistants' makers: their training crawlers (robots.txt turns them away), their search crawlers and the
    # fetchers a user drives.
    ('gptbot', r'GPTBot'),
    ('oai-searchbot', r'OAI-SearchBot'),
    ('chatgpt-user', r'ChatGPT-User'),
    ('claudebot', r'ClaudeBot|anthropic-ai'),
    ('claude-searchbot', r'Claude-SearchBot'),
    ('claude-user', r'Claude-User'),
    ('perplexitybot', r'PerplexityBot'),
    ('perplexity-user', r'Perplexity-User'),
    # Other training crawlers.
    ('ccbot', r'CCBot'),
    ('bytespider', r'Bytespider'),
    ('amazonbot', r'Amazonbot'),
    ('meta-externalagent', r'meta-externalagent'),
    # Link previews: someone shared a page, or asked Meta's assistant about it. WhatsApp's fetcher begins with its name;
    # the browser inside the app begins as every browser's does, and is a person.
    ('facebookexternalhit', r'facebookexternalhit|meta-externalfetcher'),
    ('whatsapp', r'^WhatsApp/'),
    ('telegrambot', r'TelegramBot'),
    ('twitterbot', r'Twitterbot'),
    ('seo-tools', r'Semrush|Ahrefs|MJ12bot|DotBot|DataForSeoBot|serpstatbot|BLEXBot|Screaming Frog'),
    # Whatever checks that the site answers, or how fast.
    ('monitor', r'uptime|pingdom|statuscake|site24x7|monitor|hetrixtools|checkly|lighthouse'),
    ('script', r'^curl/|wget|python|go-http|\bjava/|okhttp|httpx|aiohttp|node-fetch|undici|axios|headless|libwww|scrapy'),
    # Any other machine that says so. A Cubot phone is a person.
    ('other-bot', r'(?<!cu)bot\b|bot/|crawl|spider|slurp'),
)]

# The kinds of address: Django's doors, the assistants' MCP server, the admin and files, then the pages' (registry.KINDS).
KINDS = ('api', 'mcp', 'admin', 'file') + registry.KINDS
FOLDERS =('/assets/', '/static/', '/media/', '/fonts/', '/brand/', '/icons/', '/geo/', '/blog/posters/', '/sitemaps/')
FILE = re.compile(r'\.(js|mjs|css|map|png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf|otf|json|xml|txt|webmanifest|wasm|gz|br|'
                  r'pdf|mp3|m4a|aac|mp4)$', re.I)
# The pages, by their address's first part, as the comment above registry.KINDS gives them; /ma/, /bo/, /topics/ and
# /blog/ are read further in kind_of.
PAGES = {
    'constitution': 'law', 'texts': 'law', 'pages': 'issue',
    'library': 'library', 'codes': 'library', 'new': 'library', 'places': 'library', 'words': 'library',
    'budget': 'budget', 'search': 'search', 'situations': 'topic',
    'discussion': 'talk', 'talk': 'talk', 'questions': 'talk', 'people': 'talk', 'explain': 'talk',
    'me': 'account', 'saved': 'account', 'account': 'account', 'login': 'account', 'register': 'account',
    'forgot': 'account', 'reset': 'account', 'connect': 'account', 'auth': 'account', 'letters': 'account',
    'review': 'account',
    'about': 'page', 'data': 'page', 'rules': 'page', 'privacy': 'page', 'corrections': 'page', 'check': 'page',
    'ai': 'page',
    'embed': 'embed',
}


def family_of(agent: str) -> str:
    """The family of a User-Agent as nginx wrote it («-» for none)."""
    if agent in ('', '-'):
        return 'none'
    for name, pattern in FAMILIES:
        if pattern.search(agent):
            return name
    return 'browser'


def kind_of(path: str) -> str:
    """The kind of address asked: `api` (/api/, and the assistants' sign-in beside it: /oauth/, /.well-known/), `mcp`,
    `admin`, `file` (the build's files, Django's static files, the sitemaps, robots.txt, the icons), else the page's kind
    by the rules above registry.KINDS (web/src/app/App.tsx's routes), `other` for an address the app does not know."""
    path = path.split('?', 1)[0]
    if path == '/api' or path.startswith(('/api/', '/oauth/', '/.well-known/')):
        return 'api'
    if path == '/mcp' or path.startswith('/mcp/'):
        return 'mcp'
    if path == '/admin' or path.startswith('/admin/'):
        return 'admin'
    if path.startswith(FOLDERS):
        return 'file'
    if not path.startswith('/'):
        return 'other'              # «-» (a request nginx could not read), «*», a host and its port
    parts = [part for part in path.split('/') if part]
    if not parts:
        return 'home'
    first = parts[0]
    if first == 'ma':
        return 'article' if len(parts) > 2 and parts[-1].startswith('art_') else 'law'
    if first == 'bo':
        return 'issue' if len(parts) >= 3 else 'library'          # /bo/<edition>/<number>, its quality page; /bo
    if first == 'topics':
        if len(parts) >= 3 and parts[2] == 'review':
            return 'account'                                     # a topic's reviewers' desk
        if len(parts) >= 4 and parts[2] in ('journeys', 'tools'):
            return {'journeys': 'journey', 'tools': 'tool'}[parts[2]]
        return 'topic'
    if first == 'blog':
        return 'post' if len(parts) >= 2 else 'blog'
    if first in PAGES:
        return PAGES[first]
    return 'file' if FILE.search(parts[-1]) else 'other'


@lru_cache(maxsize=8192)
def _day(minute: str, offset: str, zone) -> date:
    """«14/Nov/2026:23:59» and «+0100», nginx's time to the minute and its offset, as a day in `zone`."""
    day, month, rest = minute.split('/')
    year, hour, minutes = rest.split(':')
    sign = -1 if offset[0] == '-' else 1
    shift = offset_zone(sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5])))
    moment = datetime(int(year), MONTHS[month], int(day), int(hour), int(minutes), tzinfo=shift)
    return moment.astimezone(zone).date()


@dataclass(frozen=True)
class Line:
    address: str
    day: date           # Morocco's
    path: str           # without its query
    status: str
    agent: str


def parse(line: str) -> Line | None:
    """A line of the log, or None when it does not read as one."""
    found = LINE.match(line)
    if found is None:
        return None
    address, minute, offset, request, status, agent = found.groups()
    try:
        day = _day(minute, offset, timezone.get_default_timezone())
    except (KeyError, ValueError):
        return None
    # "GET /x HTTP/1.1", "- - -"; in a stock line, whatever the request line was.
    rest = request.partition(' ')[2]
    path = rest.rpartition(' ')[0] if ' ' in rest else rest
    return Line(address, day, path.split('?', 1)[0], status, agent)


@dataclass
class Tally:
    """A day's counts, and what reading the files met."""
    day: date
    requests: Counter = field(default_factory=Counter)      # (family, kind): requests
    statuses: Counter = field(default_factory=Counter)      # (family, '2xx' …): requests
    unread: int = 0                                         # lines that read as neither format
    files: list = field(default_factory=list)               # (path, lines, lines of the day, why it was not read whole)

    @property
    def total(self) -> int:
        return sum(self.requests.values())

    @property
    def machines(self) -> int:
        return self.total - sum(n for (family, _), n in self.requests.items() if family == 'browser')


def _open(path: str):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8', errors='replace')
    return open(path, encoding='utf-8', errors='replace')


def count(day: date, paths) -> Tally:
    """The requests of a Moroccan day in these log files, by family, kind and status. A file that is missing or cannot be
    read is noted with why, and the others read."""
    tally = Tally(day)
    families: dict = {}                     # each User-Agent's family, looked up once
    for path in paths:
        lines = kept = 0
        why = ''
        try:
            with _open(path) as log:
                for raw in log:
                    lines += 1
                    line = parse(raw)
                    if line is None:
                        tally.unread += 1
                        continue
                    if line.day != day:
                        continue
                    kept += 1
                    if line.address in SELF:
                        family = 'self'
                    elif (family := families.get(line.agent)) is None:
                        family = families[line.agent] = family_of(line.agent)
                    tally.requests[family, kind_of(line.path)] += 1
                    tally.statuses[family, f'{line.status[0]}xx'] += 1
        except (OSError, EOFError, zlib.error) as error:
            why = getattr(error, 'strerror', None) or str(error) or type(error).__name__
        tally.files.append((path, lines, kept, why))
    return tally


def write(tally: Tally) -> int:
    """The day's `machine.*` rows replaced by the tally's, in one transaction; how many rows."""
    rows = [DayCount(day=tally.day, metric=REQUESTS, key=f'{family}:{kind}', count=n)
            for (family, kind), n in sorted(tally.requests.items())]
    rows += [DayCount(day=tally.day, metric=STATUS, key=f'{family}:{status}', count=n)
             for (family, status), n in sorted(tally.statuses.items())]
    with transaction.atomic():
        DayCount.objects.filter(day=tally.day, metric__startswith=PREFIX).delete()
        DayCount.objects.bulk_create(rows)
    return len(rows)
