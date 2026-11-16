"""The machines counted from nginx's access log (apps/analytics/services/machines.py, `count_machines`): the parser on the
lines deploy/nginx.conf's `log_format law` writes (rendered here from the file's own format, and lines a real nginx
wrote), the families and the kinds, a day's lines across the files, the day's rows replaced and no other's, the same
queries whatever the lines, a missing file; and the deploy's files that make the log: no query string in it, every
server writing it, its own folder and rotation, and the night's line."""
import gzip
import re
from datetime import UTC, date, datetime
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import manage
from apps.analytics.models import DayCount
from apps.analytics.services import machines

REPO = Path(settings.BASE_DIR).parent
DEPLOY = REPO / 'deploy'
NGINX = DEPLOY / 'nginx.conf'
DAY = date(2026, 11, 14)
# The lines are written by deploy/nginx.conf's own format.
pytestmark = pytest.mark.skipif(not NGINX.exists(), reason='the repository is not beside the app')

# Lines nginx 1.30 wrote with deploy/nginx.conf (rendered, in a container, 15 Nov 2026), each answering a request sent
# for it: /search?q=…&x=1 from Google's results page; an article?from=share from an IPv6 address, with a referer that holds
# a space and a User-Agent in Arabic letters; a page with an empty User-Agent and a file with none; the www name's
# redirect; the machine's own request; an address with a quote and a backslash (and a query), a User-Agent likewise; a
# request line nginx could not read.
WRITTEN = date(2026, 11, 15)
NGINX_WROTE = [
    r'203.0.113.9 - - [15/Nov/2026:23:24:12 +0000] "GET /search HTTP/1.1" 502 157 "https://www.google.com/search" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"',
    r'2001:db8::7 - - [15/Nov/2026:23:24:13 +0000] "GET /ma/loi/65-99/art_53 HTTP/1.1" 502 157 "https://example.com/a b" "Mozilla/5.0 (Linux; Android 14) \xD8\xAA\xD8\xAC\xD8\xB1\xD8\xA8\xD8\xA9"',
    r'198.51.100.4 - - [15/Nov/2026:23:24:13 +0000] "GET /topics/road HTTP/1.1" 200 36 "-" ""',
    r'198.51.100.5 - - [15/Nov/2026:23:24:13 +0000] "GET /assets/a.js HTTP/1.1" 200 2 "-" "-"',
    r'198.51.100.6 - - [15/Nov/2026:23:24:13 +0000] "GET /x HTTP/1.1" 302 145 "-" "curl/8.5.0"',
    r'127.0.0.1 - - [15/Nov/2026:23:24:13 +0000] "GET / HTTP/1.1" 200 36 "-" "curl/8.5.0"',
    r'203.0.113.10 - - [15/Nov/2026:23:24:13 +0000] "GET /ma/a\x22b\x5Cc HTTP/1.1" 499 0 "-" "a \x22quoted\x22 agent\x5Cx"',
    r'127.0.0.1 - - [15/Nov/2026:23:24:13 +0000] "- - -" 400 157 "-" "-"',
]
GOOGLE = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
PHONE = 'Mozilla/5.0 (Linux; Android 14; SM-A155F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36'


# The log's format, read from deploy/nginx.conf, and a line written by it as nginx would.

def _conf() -> str:
    return NGINX.read_text(encoding='utf-8')


def _format() -> str:
    found = re.search(r"^log_format law escape=default ((?:'[^']*'\s*)+);", _conf(), re.M)
    assert found, 'no log_format law in deploy/nginx.conf'
    return ''.join(re.findall(r"'([^']*)'", found.group(1)))


def _map(source: str, target: str):
    """nginx's map from `source` to `target`, as a function of the source's value (None: the value is missing)."""
    conf = _conf()
    block = conf[conf.index(f'map {source} {target} {{'):]
    entries = re.findall(r'^\s+"([^"]*)"\s+("[^"]*"|\S+);$', block[:block.index('\n}')], re.M)

    def mapped(value):
        value = value or ''                         # a missing variable is the empty string to a map
        for key, result in entries:
            if not key.startswith('~') and key == value:
                return result.strip('"')
        for key, result in entries:
            if key.startswith('~') and (m := re.search(key[1:].replace('(?<', '(?P<'), value)):
                return re.sub(r'\$(\w+)', lambda v: m.group(v.group(1)), result)
        raise AssertionError(f'{target} has no entry for {value!r}')
    return mapped


def _escaped(value: str | None) -> str:
    """A variable's value as nginx writes it (escape=default): «-» when it is missing, «"», «\\» and every byte outside
    printable ASCII as \\xXX."""
    if value is None:
        return '-'
    return ''.join(f'\\x{b:02X}' if b in (0x22, 0x5C) or b < 0x20 or b > 0x7E else chr(b) for b in value.encode())


def written(*, address='203.0.113.9', when='14/Nov/2026:10:00:00 +0000', method='GET', uri='/', protocol='HTTP/1.1',
            status=200, size=512, referer=None, agent: str | None = PHONE) -> str:
    """The line `log_format law` writes for a request (None: the header was not sent)."""
    values = {'remote_addr': address, 'time_local': when, 'request_method': method,
              'law_log_path': _map('$request_uri', '$law_log_path')(uri), 'server_protocol': protocol,
              'status': str(status), 'body_bytes_sent': str(size),
              'law_log_referer': _map('$http_referer', '$law_log_referer')(referer), 'http_user_agent': agent}
    return re.sub(r'\$(\w+)', lambda m: _escaped(values[m.group(1)]), _format())


def test_the_log_names_no_query_and_no_cookie():
    variables = set(re.findall(r'\$(\w+)', _format()))
    assert variables == {'remote_addr', 'time_local', 'request_method', 'law_log_path', 'server_protocol', 'status',
                         'body_bytes_sent', 'law_log_referer', 'http_user_agent'}
    for whole in ('request', 'request_uri', 'args', 'query_string', 'http_referer', 'uri', 'remote_user'):
        assert whole not in variables
    assert not any(v.startswith(('arg_', 'cookie_', 'http_cookie', 'http_authorization', 'sent_http')) for v in variables)
    # The two maps read the original address and the referer, and keep what comes before «?».
    path, referer = _map('$request_uri', '$law_log_path'), _map('$http_referer', '$law_log_referer')
    assert path('/search?q=%D8%B7%D9%84%D8%A7%D9%82&x=1') == '/search' and path('/ma/loi/65-99') == '/ma/loi/65-99'
    assert path('/?') == '/' and path(None) == '-'
    assert referer('https://example.org/a?b=c') == 'https://example.org/a' and referer(None) == '-'
    # The log and its format are said at the http level, outside every server (the maps beside them).
    head = _conf()[:_conf().index('\nserver {')]
    assert 'log_format law ' in head and 'map $request_uri $law_log_path {' in head
    assert not re.search(r'^\s*access_log ', head, re.M)          # one here would be added to nginx.conf's stock log


def _servers() -> list[tuple[str, str]]:
    """(server_name, its block) for the server blocks of nginx.conf and of a server's own names (deploy/private/, a
    private folder the public tree leaves out: read where it is)."""
    texts = [_conf()] + [p.read_text(encoding='utf-8') for p in sorted((DEPLOY / 'private').glob('nginx-*.conf'))]
    return [(re.search(r'server_name ([^;]+);', block).group(1), block)
            for text in texts for block in re.split(r'^server \{$', text, flags=re.M)[1:]]


def test_every_server_of_the_site_writes_the_law_log():
    servers = _servers()
    assert len(servers) >= 2
    for name, block in servers:
        top = block[:block.index('\n    location')]
        assert '\n    access_log /var/log/nginx/law/access.log law;\n' in top, name
        # The address in the log is the reader's, as Cloudflare saw it.
        assert 'set_real_ip_from 127.0.0.1;' in top and 'real_ip_header CF-Connecting-IP;' in top, name
        assert not re.search(r'access_log (?!/var/log/nginx/law/access\.log law;|off;)', block), name


def test_the_log_has_a_folder_and_a_rotation_of_its_own():
    rule = (DEPLOY / 'logrotate-nginx').read_text(encoding='utf-8')
    body = rule[rule.index('/var/log/nginx/law/*.log {'):]
    options = {line.strip() for line in body.splitlines()[1:]}
    assert {'daily', 'rotate 7', 'missingok', 'notifempty', 'compress', 'delaycompress', 'create 0640 www-data adm',
            'sharedscripts', 'postrotate', 'endscript'} <= options
    # The folder nginx writes in is the rule's, and not the stock rule's (/var/log/nginx/*.log).
    logs = set(re.findall(r'access_log (\S+) law;', _conf()))
    assert logs == {'/var/log/nginx/law/access.log'}
    # deploy.sh --system makes the folder and installs the rule before nginx is tested and reloaded.
    deploy = (DEPLOY / 'deploy.sh').read_text(encoding='utf-8')
    system = deploy[deploy.index('if [ "$SYSTEM" = --system ]; then'):]
    made = system.index('sudo install -d -o root -g adm -m 755 /var/log/nginx/law\n')
    installed = system.index('sudo install -m 644 ../deploy/logrotate-nginx /etc/logrotate.d/law-nginx\n')
    assert made < system.index('sudo nginx -t') and installed < system.index('sudo nginx -t')
    # The night reads the rule's three newest files.
    example = (REPO / 'back' / '.env.example').read_text(encoding='utf-8')
    assert ('# NGINX_LOGS=/var/log/nginx/law/access.log.2.gz,/var/log/nginx/law/access.log.1,'
            '/var/log/nginx/law/access.log\n') in example


def test_the_night_counts_the_machines_before_the_dump_and_goes_on_when_it_fails():
    night = (DEPLOY / 'nightly.sh').read_text(encoding='utf-8')
    line = '"$ROOT/venv/bin/python" manage.py count_machines || echo \'count_machines failed\' >&2\n'
    assert line in night
    assert night.index('manage.py merge_search_index') < night.index(line) < night.index('pg_dump')


def test_the_count_never_empties_the_kept_answers():
    """It writes no row an answer reads: after any command not in READ_ONLY, manage.py empties every kept answer."""
    assert 'count_machines' in manage.READ_ONLY


# The parser.

def test_the_parser_reads_the_lines_nginx_wrote():
    read = [machines.parse(line) for line in NGINX_WROTE]
    assert all(read) and {line.day for line in read} == {WRITTEN}
    assert [line.path for line in read] == ['/search', '/ma/loi/65-99/art_53', '/topics/road', '/assets/a.js', '/x', '/',
                                            r'/ma/a\x22b\x5Cc', '-']
    assert [line.status for line in read] == ['502', '502', '200', '200', '302', '200', '499', '400']
    assert read[1].address == '2001:db8::7' and read[5].address == '127.0.0.1'
    assert read[2].agent == '' and read[3].agent == '-' and read[6].agent == r'a \x22quoted\x22 agent\x5Cx'


@pytest.mark.parametrize('request_', [
    {'uri': '/search?q=%D8%B7%D9%84%D8%A7%D9%82', 'referer': 'https://www.google.com/search?q=x'},
    {'address': '2001:db8:4006:812::200e', 'uri': '/ma/loi/65-99/art_53', 'agent': None, 'referer': None},
    {'uri': '/ma/a"b\\c d?q="1', 'agent': 'a "quoted" agent\\x', 'referer': 'https://example.org/a b?c'},
    {'uri': '/', 'agent': '', 'method': 'HEAD', 'protocol': 'HTTP/2.0', 'status': 304, 'size': 0},
    {'uri': '/words', 'agent': 'Mozilla/5.0 (Linux; Android 14) تجربة', 'when': '15/Nov/2026:00:30:00 +0100'},
])
def test_the_parser_reads_what_the_format_writes(request_):
    line = machines.parse(written(**request_))
    uri = request_['uri'].split('?')[0]
    assert line.path == _escaped(uri) and line.status == str(request_.get('status', 200))
    assert line.address == request_.get('address', '203.0.113.9')
    assert line.agent == _escaped(request_.get('agent', PHONE)) and line.day == DAY


@pytest.mark.parametrize('stamp, day', [
    ('14/Nov/2026:23:59:59 +0000', date(2026, 11, 14)),
    ('15/Nov/2026:00:30:00 +0100', date(2026, 11, 14)),        # 23:30 at Greenwich
    ('14/Nov/2026:23:30:00 -0100', date(2026, 11, 15)),
    ('19/Sep/2026:23:30:00 +0000', date(2026, 9, 20)),         # Morocco an hour ahead, until 20 Sep 2026 (decree 2.26.530)
    ('20/Sep/2026:23:30:00 +0000', date(2026, 9, 20)),
])
def test_a_line_is_on_moroccos_day_whatever_offset_nginx_wrote(stamp, day):
    assert machines.parse(written(when=stamp)).day == day


@pytest.mark.parametrize('line', [
    '', 'garbage', NGINX_WROTE[0][:60],
    NGINX_WROTE[0].replace('/Nov/', '/Nov./'), NGINX_WROTE[0].replace('/Nov/', '/Noe/'),
    NGINX_WROTE[0].replace('[15/', '[32/'), NGINX_WROTE[0].replace(' 502 ', ' 5o2 '),
])
def test_a_line_that_does_not_read_is_none(line):
    assert machines.parse(line) is None


def test_a_stock_combined_line_reads_and_loses_its_query():
    stock = ('203.0.113.9 - - [14/Nov/2026:10:00:00 +0000] "GET /search?q=%D8%B7 HTTP/1.1" 200 512 '
             '"https://example.org/?a=b" "curl/8.5.0"')
    line = machines.parse(stock)
    assert line.path == '/search' and machines.family_of(line.agent) == 'script'


# Families and kinds.

@pytest.mark.parametrize('agent, family', [
    (GOOGLE, 'googlebot'),
    ('Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.122 '
     'Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)', 'googlebot'),
    ('Googlebot-Image/1.0', 'googlebot'),
    ('Mozilla/5.0 (compatible; Google-InspectionTool/1.0;)', 'google-other'),
    ('Mozilla/5.0 (compatible; GoogleOther)', 'google-other'),
    ('Mozilla/5.0 (X11; Linux x86_64; Storebot-Google/1.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 '
     'Safari/537.36', 'google-other'),
    ('AdsBot-Google (+http://www.google.com/adsbot.html)', 'google-other'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) '
     'Chrome/116.0.1938.76 Safari/537.36', 'bingbot'),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15 '
     '(Applebot/0.1; +http://www.apple.com/go/applebot)', 'applebot'),
    ('Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)', 'yandex'),
    ('DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)', 'duckduckbot'),
    ('Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)', 'baiduspider'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)', 'gptbot'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot',
     'oai-searchbot'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot',
     'chatgpt-user'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)', 'claudebot'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0; +Claude-SearchBot@anthropic.com)',
     'claude-searchbot'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)',
     'claude-user'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)',
     'perplexitybot'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)',
     'perplexity-user'),
    ('CCBot/2.0 (https://commoncrawl.org/faq/)', 'ccbot'),
    ('Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; '
     'spider-feedback@bytedance.com)', 'bytespider'),
    ('Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amazonbot/0.1; +https://developer.amazon.com/support/'
     'amazonbot) Chrome/119.0.6045.214 Safari/537.36', 'amazonbot'),
    ('meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)', 'meta-externalagent'),
    ('facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)', 'facebookexternalhit'),
    ('meta-externalfetcher/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)', 'facebookexternalhit'),
    ('WhatsApp/2.23.20.0 A', 'whatsapp'),
    ('TelegramBot (like TwitterBot)', 'telegrambot'),
    ('Twitterbot/1.0', 'twitterbot'),
    ('Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)', 'seo-tools'),
    ('Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)', 'seo-tools'),
    ('Mozilla/5.0 (compatible; MJ12bot/v1.4.8; http://mj12bot.com/)', 'seo-tools'),
    ('Mozilla/5.0 (compatible; DotBot/1.2; +https://opensiteexplorer.org/dotbot; help@moz.com)', 'seo-tools'),
    ('Mozilla/5.0+(compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)', 'monitor'),
    ('Pingdom.com_bot_version_1.4_(http://www.pingdom.com/)', 'monitor'),
    ('Mozilla/5.0 (Linux; Android 11; moto g power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile '
     'Safari/537.36 Chrome-Lighthouse', 'monitor'),
    ('curl/8.5.0', 'script'), ('Wget/1.21.4', 'script'), ('python-requests/2.32.3', 'script'),
    ('Python/3.12 aiohttp/3.10.5', 'script'), ('python-httpx/0.27.0', 'script'), ('Go-http-client/2.0', 'script'),
    ('Java/17.0.2', 'script'), ('okhttp/4.12.0', 'script'), ('node-fetch/1.0 (+https://github.com/bitinn/node-fetch)', 'script'),
    ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/131.0.0.0 Safari/537.36', 'script'),
    ('Mozilla/5.0 (compatible; LinkedInBot/1.0)', 'other-bot'), ('Slackbot-LinkExpanding 1.0', 'other-bot'),
    ('Mozilla/5.0 (compatible; SeznamBot/4.0; +https://o-seznam.cz/napoveda/vyhledavani/en/seznambot-crawler/)', 'other-bot'),
    ('ia_archiver crawler', 'other-bot'), ('Mozilla/5.0 (compatible; Yahoo! Slurp)', 'other-bot'),
    ('', 'none'), ('-', 'none'),
    (PHONE, 'browser'),
    ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
     '[FBAN/FBIOS;FBAV/490.0.0.40.108]', 'browser'),
    ('Mozilla/5.0 (Linux; Android 14; SM-A155F Build/UP1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 '
     'Chrome/141.0.0.0 Mobile Safari/537.36 WhatsApp/2.24.25.78', 'browser'),     # the browser inside WhatsApp
    ('Mozilla/5.0 (Linux; Android 10; CUBOT X30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile '
     'Safari/537.36', 'browser'),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 '
     'Edg/141.0.0.0', 'browser'),
])
def test_a_user_agent_has_its_family(agent, family):
    assert machines.family_of(agent) == family


@pytest.mark.parametrize('path, kind', [
    ('/api/corpus/texts/', 'api'), ('/api', 'api'), ('/oauth/token', 'api'), ('/.well-known/oauth-authorization-server', 'api'),
    ('/mcp', 'mcp'), ('/admin/', 'admin'), ('/admin/login/', 'admin'),
    ('/assets/index-abc123.js', 'file'), ('/static/admin/css/base.css', 'file'), ('/fonts/markazi.woff2', 'file'),
    ('/brand/mark.svg', 'file'), ('/icons/icon-192.png', 'file'), ('/blog/posters/one.webp', 'file'),
    ('/sitemaps/texts-1.xml', 'file'), ('/sitemap.xml', 'file'), ('/robots.txt', 'file'), ('/favicon.ico', 'file'),
    ('/sw.js', 'file'), ('/manifest.webmanifest', 'file'), ('/indexnow.txt', 'file'),
    ('/', 'home'),
    ('/ma/loi/65-99', 'law'), ('/ma/code/doc', 'law'), ('/constitution', 'law'), ('/texts/12', 'law'),
    ('/ma/loi/65-99/art_53', 'article'), ('/ma/code/doc/art_417-3', 'article'),
    ('/bo/bo_ar/7533', 'issue'), ('/bo/bo_ar/7465-bis/quality', 'issue'), ('/pages/12/3', 'issue'),
    ('/library', 'library'), ('/codes', 'library'), ('/bo', 'library'), ('/new', 'library'), ('/places/fes', 'library'),
    ('/words', 'library'), ('/words/talaq', 'library'),
    ('/budget', 'budget'), ('/budget/2027', 'budget'), ('/search', 'search'),
    ('/topics', 'topic'), ('/topics/road', 'topic'), ('/topics/road/checklists/after', 'topic'),
    ('/topics/family/reform', 'topic'), ('/situations/fired', 'topic'),
    ('/topics/road/journeys/accident', 'journey'), ('/topics/road/tools/fine', 'tool'), ('/topics/tax/tools/salary/2027', 'tool'),
    ('/blog', 'blog'), ('/blog/seventy-years', 'post'),
    ('/talk', 'talk'), ('/discussion/ma/loi/65-99', 'talk'), ('/questions', 'talk'), ('/people/someone', 'talk'),
    ('/explain/ma/loi/65-99/art_53', 'talk'),
    ('/me', 'account'), ('/saved', 'account'), ('/account', 'account'), ('/login', 'account'), ('/connect', 'account'),
    ('/auth/google', 'account'), ('/letters/stop', 'account'), ('/review', 'account'), ('/topics/road/review', 'account'),
    ('/about', 'page'), ('/data', 'page'), ('/rules', 'page'), ('/privacy', 'page'), ('/corrections', 'page'),
    ('/check', 'page'), ('/ai', 'page'),
    ('/embed/ma/loi/65-99/art_53', 'embed'),
    ('/wp-login.php', 'other'), ('/.env', 'other'), ('/art/12', 'other'), ('-', 'other'), ('*', 'other'),
])
def test_an_address_has_its_kind(path, kind):
    assert machines.kind_of(path) == kind


# A day's count.

def _file(path: Path, lines: list[str]) -> str:
    text = ''.join(f'{line}\n' for line in lines)
    if path.suffix == '.gz':
        with gzip.open(path, 'wt', encoding='utf-8') as out:
            out.write(text)
    else:
        path.write_text(text, encoding='utf-8')
    return str(path)


def _logs(folder: Path, scale: int = 1) -> list[str]:
    """The three files a night reads: the one rotated the night before last (its last lines are DAY's first), last
    night's (DAY's), today's (DAY's last lines, then the next day's)."""
    before = [written(when='13/Nov/2026:12:00:00 +0000')] * 3 + [written(when='14/Nov/2026:00:20:00 +0000', agent=GOOGLE)]
    night = [written(when='14/Nov/2026:10:00:00 +0000', uri='/ma/loi/65-99/art_53?from=share')] * 2 * scale
    night += [written(when='14/Nov/2026:11:00:00 +0000', agent=GOOGLE, uri='/ma/loi/65-99', status=200)] * 3 * scale
    night += [written(when='14/Nov/2026:12:00:00 +0000', agent='curl/8.5.0', uri='/wp-login.php', status=404)] * scale
    night += [written(when='14/Nov/2026:13:00:00 +0000', address='127.0.0.1', agent='node', uri='/api/topics/road/')]
    night += ['garbage', '']
    today = [written(when='15/Nov/2026:00:10:00 +0100', agent=None, uri='/robots.txt', status=301)]   # still the 14th
    today += [written(when='15/Nov/2026:00:40:00 +0000', agent=GOOGLE)] * 2
    return [_file(folder / 'access.log.2.gz', before), _file(folder / 'access.log.1', night),
            _file(folder / 'access.log', today)]


def test_a_days_lines_are_counted_across_the_three_files(tmp_path):
    tally = machines.count(DAY, _logs(tmp_path))
    assert tally.requests == {('browser', 'article'): 2, ('googlebot', 'law'): 3, ('googlebot', 'home'): 1,
                              ('script', 'other'): 1, ('self', 'api'): 1, ('none', 'file'): 1}
    assert tally.statuses == {('browser', '2xx'): 2, ('googlebot', '2xx'): 4, ('script', '4xx'): 1, ('self', '2xx'): 1,
                              ('none', '3xx'): 1}
    assert tally.total == 9 and tally.machines == 7 and tally.unread == 2
    assert [(Path(p).name, lines, kept, why) for p, lines, kept, why in tally.files] == [
        ('access.log.2.gz', 4, 1, ''), ('access.log.1', 9, 7, ''), ('access.log', 3, 1, '')]


@pytest.mark.django_db
def test_counting_a_day_again_replaces_its_machine_rows_and_nothing_else(tmp_path):
    others = [DayCount(day=DAY, metric='page.path', key='/', count=5), DayCount(day=DAY, metric='visit.country', key='MA', count=2),
              DayCount(day=DAY, metric='machines', key='', count=1),                 # not the prefix: another writer's
              DayCount(day=date(2026, 11, 13), metric='machine.requests', key='gptbot:law', count=9)]
    DayCount.objects.bulk_create(others + [DayCount(day=DAY, metric='machine.requests', key='gptbot:law', count=4)])
    logs = _logs(tmp_path)
    assert machines.write(machines.count(DAY, logs)) == 11
    first = set(DayCount.objects.values_list('day', 'metric', 'key', 'count'))
    machines.write(machines.count(DAY, logs))
    assert set(DayCount.objects.values_list('day', 'metric', 'key', 'count')) == first
    assert {(c.day, c.metric, c.key, c.count) for c in others} <= first
    assert (DAY, 'machine.requests', 'gptbot:law', 4) not in first
    assert (DAY, 'machine.requests', 'googlebot:law', 3) in first and (DAY, 'machine.status', 'none:3xx', 1) in first


@pytest.mark.django_db
def test_nothing_of_a_request_is_written_but_its_family_kind_and_status(tmp_path):
    machines.write(machines.count(DAY, _logs(tmp_path)))
    families = {name for name, _ in machines.FAMILIES} | {'self', 'none', 'browser'}
    for metric, key in DayCount.objects.values_list('metric', 'key'):
        family, what = key.split(':')
        assert family in families and re.fullmatch(r'[a-z0-9]+', what), (metric, key)
        assert what in (machines.KINDS if metric == machines.REQUESTS else ('1xx', '2xx', '3xx', '4xx', '5xx'))


def _queries(logs) -> int:
    with CaptureQueriesContext(connection) as seen:
        machines.write(machines.count(DAY, logs))
    return len(seen.captured_queries)


@pytest.mark.django_db
def test_a_count_costs_the_same_queries_for_a_few_lines_or_many(tmp_path):
    (tmp_path / 'few').mkdir()
    (tmp_path / 'many').mkdir()
    few = _queries(_logs(tmp_path / 'few'))
    many = _queries(_logs(tmp_path / 'many', scale=200))
    assert few == many <= 6
    assert DayCount.objects.get(day=DAY, metric='machine.requests', key='googlebot:law').count == 600


@pytest.fixture
def morning(monkeypatch):
    """15 November 2026, 03:30 in Morocco: the night's job."""
    monkeypatch.setattr(timezone, 'now', lambda: datetime(2026, 11, 15, 3, 30, tzinfo=UTC))


def run(*args) -> list[str]:
    out = StringIO()
    call_command('count_machines', *args, stdout=out)
    return out.getvalue().splitlines()


@pytest.mark.django_db
def test_the_night_counts_yesterday_from_the_logs_it_is_given(morning, settings, tmp_path):
    settings.NGINX_LOGS = _logs(tmp_path)
    said = run()
    assert said[:3] == [f'{tmp_path}/access.log.2.gz: 4 lines, 1 of 2026-11-14', f'{tmp_path}/access.log.1: 9 lines, 7 of 2026-11-14',
                        f'{tmp_path}/access.log: 3 lines, 1 of 2026-11-14']
    assert said[3] == '2026-11-14: 9 requests, 7 by machines (77.8 %), 11 counts'
    assert said[-1] == '2 lines not read'
    assert DayCount.objects.filter(day=DAY, metric__startswith='machine.').count() == 11


@pytest.mark.django_db
def test_a_missing_file_is_said_and_passed_over(morning, tmp_path):
    logs = _logs(tmp_path)
    said = run('--log', str(tmp_path / 'access.log.3.gz'), *logs[1:])
    assert said[0] == f'{tmp_path}/access.log.3.gz: not read (No such file or directory)'
    assert '2026-11-14: 8 requests' in said[3] and said[-1] == '2 lines not read'


@pytest.mark.django_db
def test_a_compressed_file_cut_short_counts_what_it_holds(morning, tmp_path):
    lines = [written(when='14/Nov/2026:10:00:00 +0000', uri=f'/ma/loi/65-99/art_{n}') for n in range(5000)]
    whole = Path(_file(tmp_path / 'access.log.2.gz', lines))
    whole.write_bytes(whole.read_bytes()[:len(whole.read_bytes()) // 2])
    said = run('--log', str(whole))
    read = int(re.match(rf'{whole}: (\d+) lines, \1 of 2026-11-14, then stopped \(.+\)$', said[0]).group(1))
    assert 0 < read < 5000 and said[1].startswith(f'2026-11-14: {read} requests')


@pytest.mark.django_db
def test_a_day_no_longer_in_the_logs_keeps_its_counts(morning, tmp_path):
    DayCount.objects.create(day=date(2026, 11, 1), metric='machine.requests', key='gptbot:law', count=4)
    said = run('--day', '2026-11-01', '--log', *_logs(tmp_path), str(tmp_path / 'nowhere.log'))
    assert said[-2:] == ['2026-11-01: no request in these files, its counts left as they were', '2 lines not read']
    assert DayCount.objects.get(day=date(2026, 11, 1)).count == 4


@pytest.mark.django_db
def test_the_first_night_after_the_deploy_has_no_log_and_ends_well(morning, settings, tmp_path):
    settings.NGINX_LOGS = [str(tmp_path / 'access.log.2.gz'), str(tmp_path / 'access.log.1')]
    said = run()
    assert said == [f'{tmp_path}/access.log.2.gz: not read (No such file or directory)',
                    f'{tmp_path}/access.log.1: not read (No such file or directory)',
                    '2026-11-14: no request in these files, its counts left as they were', '0 lines not read']
    assert not DayCount.objects.exists()


def test_a_day_that_is_no_day_is_refused():
    with pytest.raises(CommandError, match='not a day'):
        run('--day', '2026-13-01')


@pytest.mark.django_db
def test_folding_the_day_again_keeps_its_machines(tmp_path):
    from apps.analytics.services import fold
    machines.write(machines.count(DAY, _logs(tmp_path)))
    fold.fold(DAY)
    assert DayCount.objects.filter(day=DAY, metric__startswith='machine.').count() == 11
