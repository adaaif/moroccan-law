"""Which addresses are pages (12 Nov 2026). nginx answers 404 for an address the app has no route for, and the shell,
never offered to a search engine, for a route the deploy wrote no page for (deploy/nginx.conf): its two lines of routes
are kept here to the app's own (web/src/app/App.tsx), and the sitemap's pages to those that have a head."""
import re
from pathlib import Path

import pytest
from django.conf import settings

from apps.seo.services import sitemaps

REPO = Path(settings.BASE_DIR).parent
NGINX = REPO / 'deploy' / 'nginx.conf'
APP = REPO / 'web' / 'src' / 'app' / 'App.tsx'
PRERENDER = REPO / 'web' / 'scripts' / 'prerender.mjs'
HEADERS = REPO / 'deploy' / 'nginx-headers.conf'
# Routes with a location of their own in nginx: Django's pages, the consent page and the embedded article.
OWN = {'ma', 'search', 'words', 'texts', 'connect', 'embed'}
# What nginx gives to something else than the shell: a route's name among the shell's would take it over (a regex
# location is chosen before a prefix one).
ELSEWHERE = {'ma', 'api', 'admin', 'static', 'assets', 'fonts', 'gate', 'oauth', 'mcp', 'sitemaps', 'art', 'brand'}

pytestmark = pytest.mark.skipif(not (NGINX.exists() and APP.exists()), reason='the repository is not beside the app')


def _routes() -> set[str]:
    """The first part of every address the app routes: `path="/x/…"`, and the lists of paths it maps over."""
    source = APP.read_text(encoding='utf-8')
    body = source[source.index('<Routes>'):source.index('</Routes>')]
    paths = re.findall(r'path="(/[^"]*)"', body) + re.findall(r"'(/[^']*)'", body)
    return {p.split('/')[1] for p in paths} - {'', '*'}


def _nginx() -> tuple[set[str], set[str]]:
    """nginx's two lines of routes: the never indexed, and the pages (a file with its head, else the shell)."""
    conf = NGINX.read_text(encoding='utf-8')
    never = re.search(r'location ~ \^/\(([a-z|-]+)\)\(/\|\$\)\|\^/topics/\[\^/\]\+/review \{', conf)
    pages = re.search(r'location ~ \^/\(([a-z|-]+)\)\(/\|\$\) \{\n\s+auth_request /_gate;\n(?:.*\n)*?\s+try_files \$uri \$uri/index\.html @shell;', conf)
    assert never and pages, 'the two lines of routes were not found in deploy/nginx.conf'
    return set(never.group(1).split('|')), set(pages.group(1).split('|'))


def test_every_route_of_the_app_is_a_page_for_nginx():
    never, pages = _nginx()
    assert _routes() - never - pages - OWN == set()          # a route nginx does not know would answer 404
    assert never & pages == set()
    assert (never | pages) & ELSEWHERE == set()


def test_what_is_not_a_route_is_said_as_not_found():
    conf = NGINX.read_text(encoding='utf-8')
    last = conf[conf.rindex('location / {'):]
    assert 'try_files $uri $uri/index.html =404;' in last and 'error_page 404 /index.html;' in last
    shell = conf[conf.index('location @shell {'):conf.index('location / {', conf.index('location @shell {'))]
    assert 'X-Robots-Tag "noindex, nofollow" always' in shell         # the same bytes at every address: never offered


def test_the_sitemap_offers_only_pages_with_a_head():
    # Django heads /words; the deploy draws the home, the topics and the blog, and heads the others it names.
    written = PRERENDER.read_text(encoding='utf-8')
    years = "`/budget/${b.year}`" in written
    for path in sitemaps.PAGES:
        headed = path in {'/', '/topics', '/blog', '/words'} or f"'{path}'" in written or (years and re.fullmatch(r'/budget/\d{4}', path))
        assert headed, f'{path} is in the sitemap and has no head of its own'


def test_peoples_words_are_never_offered_to_a_search_engine():
    # D9: the discussion's posts (/talk), the explanations people write (/explain), the reviewers' desks and letters.
    never, pages = _nginx()
    for route in ('discussion', 'talk', 'explain', 'people', 'questions', 'review', 'letters'):
        assert route in never and route not in pages, route


def _servers() -> dict[str, str]:
    """{server_name: its block}, for the server blocks of nginx.conf and of a server's own names (deploy/private/,
    a private folder the public tree leaves out: read where it is)."""
    texts = [NGINX.read_text(encoding='utf-8')]
    texts += [p.read_text(encoding='utf-8') for p in sorted((REPO / 'deploy' / 'private').glob('nginx-*.conf'))]
    found = {}
    for text in texts:
        for block in re.split(r'^server \{$', text, flags=re.M)[1:]:
            found[re.search(r'server_name ([^;]+);', block).group(1)] = block
    return found


def _main_server() -> str:
    conf = NGINX.read_text(encoding='utf-8')
    start = conf.index('listen 127.0.0.1:8041 default_server;')
    return conf[start:]


def _locations(server: str) -> dict[str, str]:
    """{the location line: its body}, for the locations at the server's first level (their nested ones inside)."""
    found, depth, head, body = {}, 0, None, []
    for line in server.split('\n'):
        stripped = re.sub(r'(^|\s)#.*$', '', line).strip()           # without its comment
        if depth == 0 and stripped.startswith('location') and stripped.endswith('}'):     # a location on one line
            found[stripped[:stripped.index('{') + 1]] = stripped[stripped.index('{') + 1:-1].strip()
            continue
        if depth == 0 and stripped.startswith('location') and stripped.endswith('{'):
            head, body, depth = stripped, [], 1
            continue
        if head is not None:
            depth += stripped.count('{') - stripped.count('}')
            if depth <= 0:
                found[head], head, depth = '\n'.join(body), None, 0
            else:
                body.append(stripped)
    return found


def test_every_answer_carries_the_headers_and_the_robots_word():
    # A location with an add_header of its own loses the server's: it says the headers file and the robots' word again.
    server = _main_server()
    assert 'include /etc/nginx/law-headers.conf;' in re.split(r'\n\s*location ', server)[0]
    locations = _locations(server)
    assert len(locations) > 20
    for head, body in locations.items():
        if 'add_header' in body:
            assert 'include /etc/nginx/law-headers.conf;' in body, head
            assert 'add_header X-Robots-Tag' in body, head


def test_only_the_embedded_article_may_be_framed_by_another_site():
    locations = _locations(_main_server())
    assert 'set $law_framing any;' in locations['location ^~ /embed/ {']
    assert 'set $law_framing none;' in locations['location = /connect {']
    others = [head for head, body in locations.items() if 'set $law_framing' in body]
    assert sorted(others) == ['location = /connect {', 'location ^~ /embed/ {']
    conf = NGINX.read_text(encoding='utf-8')
    assert re.search(r"map \$law_framing \$law_frame_ancestors \{\s*default \"; frame-ancestors 'self'\";", conf)


def test_the_policy_forbids_plugins_and_bases_and_reports_the_rest():
    headers = HEADERS.read_text(encoding='utf-8')

    def directives(name):
        policy = re.search(rf'add_header {name} "([^"]+)" always;', headers).group(1)
        assert policy.endswith('$law_frame_ancestors'), name
        return {d.split()[0]: d.split()[1:] for d in policy.removesuffix('$law_frame_ancestors').split('; ')}

    enforced = directives('Content-Security-Policy')
    assert enforced == {'object-src': ["'none'"], 'base-uri': ["'none'"]}
    reported = directives('Content-Security-Policy-Report-Only')
    assert reported['default-src'] == ["'self'"]
    assert reported['script-src'] == ["'self'", "'wasm-unsafe-eval'", 'https://challenges.cloudflare.com']
    assert reported['frame-src'] == ["'self'", 'https://challenges.cloudflare.com']
    assert 'add_header X-Content-Type-Options "nosniff" always;' in headers
    assert 'add_header X-Frame-Options $law_xfo always;' in headers


@pytest.mark.django_db
def test_django_answers_are_never_framed_by_another_site(client):
    assert client.get('/robots.txt')['X-Frame-Options'] == 'SAMEORIGIN'


def _visitor_map() -> list[tuple[str, str]]:
    conf = NGINX.read_text(encoding='utf-8')
    block = conf[conf.index('map $remote_addr $law_visitor {'):]
    block = block[:block.index('\n}')]
    return [(m.group(1) or m.group(2), m.group(3)) for m in
            re.finditer(r'^\s+(?:"([^"]+)"|(\S+))\s+("[^"]*"|\S+);$', block, re.M)]


def _visitor(address: str) -> str:
    """What nginx's map gives for an address as nginx writes it (RFC 5952, as Python's ipaddress does)."""
    for source, value in _visitor_map():
        if source == 'default':
            return address
        if source.startswith('~'):
            m = re.search(source[1:].replace('(?<', '(?P<'), address)
            if m:
                return re.sub(r'\$(law_v6b|law_v6)', lambda v: m.group(v.group(1)), value)  # noqa: B023 (called in this iteration)
        elif source == address:
            return value.strip('"')
    raise AssertionError('the map has no default')


def test_a_visitor_is_an_ipv4_address_or_an_ipv6_64():
    import ipaddress
    import random

    assert _visitor('127.0.0.1') == '' and _visitor('::1') == ''          # the machine itself: never counted
    assert _visitor('196.200.1.7') == '196.200.1.7'
    rng = random.Random(7)
    for _ in range(3000):
        groups = [rng.choice([0, 0, 0, rng.randrange(1, 0x10000)]) for _ in range(8)]
        groups[0] = groups[0] or 0x2a01
        address = ipaddress.IPv6Address(':'.join(f'{g:x}' for g in groups))
        key = _visitor(address.compressed)
        assert [int(g, 16) for g in key.split(':')] == groups[:4], (address.compressed, key)


def test_every_door_to_django_or_the_mcp_has_a_limit():
    # A flood would hold the workers: each location that hands a request on is limited, but the gate's own question
    # (internal) and a law nginx did not find a page for (counted at /ma/ already).
    unlimited = {'location = /_gate {', 'location @law {'}
    for head, body in _locations(_main_server()).items():
        if 'proxy_pass' in body and head not in unlimited:
            assert 'limit_req zone=' in body, head
    assert 'limit_req zone=law_pages' in _locations(_main_server())['location /ma/ {']
    conf = NGINX.read_text(encoding='utf-8')
    for name, server in _servers().items():                            # 429 from every server that hands a request on
        assert 'proxy_pass' not in server or 'limit_req_status 429;' in server, name
    # Every zone counts the visitor (the admin's sign-in counts the visitor's POSTs: $law_signin).
    assert all(z.startswith(('limit_req_zone $law_visitor ', 'limit_req_zone $law_signin '))
               for z in re.findall(r'^limit_req_zone .*$', conf, re.M))


def test_the_admins_password_tries_are_few():
    conf = NGINX.read_text(encoding='utf-8')
    signin = _locations(_main_server())['location = /admin/login/ {']
    assert 'limit_req zone=law_signin burst=5 nodelay;' in signin
    assert re.search(r'map \$request_method \$law_signin \{\s*POST\s+\$law_visitor;\s*default "";\s*\}', conf)
    assert re.search(r'limit_req_zone \$law_signin zone=law_signin:\S+ rate=([0-9]+)r/m;', conf)


def _size(value: str) -> int:
    return int(value[:-1]) * {'k': 1024, 'm': 1024 * 1024}[value[-1]]


def _body_limits() -> dict[str, int]:
    """{location line, or 'server': its client_max_body_size}, the nested locations of /api/ included."""
    server = _main_server()
    found = {'server': _size(re.search(r'^    client_max_body_size (\S+);', server, re.M).group(1))}
    for head, size in re.findall(r'^\s*(location [^\n]*\{)\n(?:\s*#[^\n]*\n|[^\n{}]*\n)*?\s*client_max_body_size (\S+);', server, re.M):
        found[head.strip()] = _size(size)
    return found


def test_a_request_carries_kilobytes_but_where_django_takes_more():
    import uuid

    from django.urls import reverse

    from apps.media.services import pictures
    from apps.search.api.views import MAX_CITATIONS

    limits = _body_limits()
    assert limits['server'] == 64 * 1024                          # the API, the sign-ins, the gate, every other door
    uploads = [head for head in limits if 'discussion' in head]
    assert len(uploads) == 2
    biggest = max(pictures.MAX_UPLOAD_BYTES, settings.VOICE_MAX_BYTES)
    for path in (reverse('discussion-voices'), reverse('discussion-pictures'),
                 reverse('discussion-review-picture', kwargs={'pk': 12, 'picture_id': uuid.uuid4()})):
        head = next(h for h in uploads if re.search(h.split()[2], path))
        assert biggest < limits[head] <= 32 * 1024 * 1024, path
    assert reverse('discussion-voices') + 'x/' not in ''.join(uploads)
    # The citations of a long pasted document, as the citation checker sends them.
    import json

    import ma_law
    document = ' '.join(f'وفقا للمادة {i} من القانون رقم 65.00 والفصل {i + 1} من الظهير الشريف رقم 1.58.250'
                        for i in range(MAX_CITATIONS))
    body = json.dumps({'citations': ma_law.parse_citations(document)[:MAX_CITATIONS], 'since': None}, ensure_ascii=False)
    assert len(body.encode()) * 2 < limits['location = /api/search/resolve/ {']
    assert limits['location /admin/ {'] > settings.DATA_UPLOAD_MAX_MEMORY_SIZE
    assert limits['location = /mcp {'] == 256 * 1024


def test_plain_http_is_sent_to_https_and_kept_there():
    conf = NGINX.read_text(encoding='utf-8')
    block = conf[conf.index('map "$http_cf_visitor $request_method" $law_to_https {'):]
    entries = re.findall(r"^\s+'~([^']+)'\s+(\d+);$", block[:block.index('\n}')], re.M)

    def to_https(visitor: str, method: str) -> str:
        return next((code for pattern, code in entries if re.search(pattern, f'{visitor} {method}')), '')

    assert to_https('{"scheme":"http"}', 'GET') == '301' and to_https('{"scheme":"http"}', 'HEAD') == '301'
    assert to_https('{"scheme":"http"}', 'POST') == '308'                 # the method and the body kept
    assert to_https('{"scheme":"https"}', 'GET') == '' and to_https('{"scheme":"https"}', 'POST') == ''
    assert to_https('', 'GET') == ''                                       # the machine's own requests
    proxies = {name: server for name, server in _servers().items() if 'proxy_pass' in server}
    assert '@DOMAIN@' in proxies
    for name, server in proxies.items():
        server = server[:server.index('\n    location')]
        for code in ('301', '308'):
            assert f'if ($law_to_https = {code}) {{ return {code} https://$server_name$request_uri; }}' in server, name
    headers = HEADERS.read_text(encoding='utf-8')
    assert 'add_header Strict-Transport-Security "max-age=2592000" always;' in headers   # a month, no preload


def test_the_mcp_server_closes_with_the_site():
    # While GATE_PASSWORD is set, the law is not read through /mcp either: the gate's cookie or the API's refusal.
    mcp = _locations(_main_server())['location = /mcp {']
    assert 'auth_request /_gate;' in mcp and 'error_page 401 = @gate_locked;' in mcp
    locked = _locations(_main_server())['location @gate_locked {']
    assert '''return 401 '{"errors": [{"field": "gate", "code": "locked"}]}';''' in locked
    # An older address kept for the assistants (a server's own names, where it has one) closes too.
    for name, server in _servers().items():
        if name != '@DOMAIN@' and 'location = /mcp {' in server:
            old = server[server.index('location = /mcp {'):server.index('location / {')]
            assert '''if ($law_gate = closed) { return 401 '{"errors": [{"field": "gate", "code": "locked"}]}'; }''' in old
