"""Who is asking: an assistant identified by its Client ID Metadata Document (MC6), or registered (RFC 7591, kept for the
clients that only register).

A metadata document is a URL the asker chooses, fetched by this server, and every fetch leaves from the server's own
connection. So a document is fetched only from the hosts in OAUTH_METADATA_HOSTS (the assistants the consent page names);
any other client registers at /oauth/register, which fetches nothing. A fetch goes over https to public addresses only
(the address checked, then connected to as checked: no second lookup), follows no redirect, reads 5 KB at most, and ends
within OAUTH_METADATA_SECONDS from the first packet to the last byte, however slowly the host answers. A document is kept
CIMD_KEEP_SECONDS; a refusal OAUTH_METADATA_REFUSAL_SECONDS, so a host that fails is not asked again on every request.
"""
import hashlib
import http.client
import io
import ipaddress
import json
import re
import secrets
import socket
import ssl
import time
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.oauth.models import Client
from config.caching import counters

MAX_DOCUMENT = 5 * 1024
LOOPBACK = {'localhost', '127.0.0.1', '[::1]'}
# The assistants the site names itself on the consent page, by exact host (a subdomain is not the company's own page);
# any other client is shown by the host its answer goes to, with the name it gives itself (C7: any https client).
KNOWN = {'claude.ai': 'Claude', 'claude.com': 'Claude', 'chatgpt.com': 'ChatGPT', 'openai.com': 'ChatGPT'}
# A redirect's start as a browser and Python read it alike: the scheme, then a host of plain DNS labels whose last one
# starts with a letter (a browser reads «0x7f000001» or «127.1» as an address), or a loopback address, then an optional
# port, then the path, the query or the end. Whatever else (a backslash, «@», «%» or a letter of another alphabet in the
# host, a space or a control character anywhere) is read differently by the two, so it is refused.
_START = re.compile(r'(https?)://((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)*[a-z](?:[a-z0-9-]*[a-z0-9])?'
                    r'|127\.0\.0\.1|\[::1\])(?::([0-9]{1,5}))?(?=[/?]|$)', re.IGNORECASE)


class FetchError(Exception):
    pass


def known_name(host: str) -> str:
    return KNOWN.get((host or '').lower(), '')


def redirect_host(uri) -> str:
    """The host a redirect sends the person to («[::1]» for IPv6, as a browser writes it), when this server and a
    browser read the same one; '' for any redirect they could read apart."""
    if not isinstance(uri, str) or not uri or len(uri) > 2000:
        return ''
    if any(not 33 <= ord(c) <= 126 for c in uri) or '\\' in uri or '@' in uri:
        return ''
    start = _START.match(uri)
    parts = _split(uri)
    if start is None or parts is None or parts.fragment:
        return ''
    host = start.group(2).lower()
    if parts.scheme != start.group(1).lower() or parts.hostname != host.strip('[]'):
        return ''                   # never expected: the two readings are compared, not assumed
    if parts.scheme == 'http' and host not in LOOPBACK:
        return ''
    return host


def known_as(client: Client) -> str:
    """The name the consent page gives `client` as an assistant the site knows, or ''. A metadata document speaks for the
    host it is fetched from; a registration, which anyone can make, is known only when every one of its redirects goes
    to a host known by that one name."""
    if client.kind == Client.Kind.CIMD:
        return known_name(client.domain)
    names = {known_name(redirect_host(uri)) for uri in client.redirect_uris or ['']}
    return names.pop() if len(names) == 1 else ''


def is_known(client: Client) -> bool:
    return bool(known_as(client))


def shown_domain(client: Client) -> str:
    """Where a client lives, for the account page: a document's host, or a registration's redirect hosts."""
    if client.kind == Client.Kind.CIMD:
        return client.domain
    return _domain(client.redirect_uris or [])


def is_cimd(client_id: str) -> bool:
    return isinstance(client_id, str) and client_id.startswith('https://')


def _public_address(host: str, port: int) -> str:
    """The address `host` resolves to, when every address it resolves to is public; else FetchError."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchError('dns') from exc
    addresses = {info[4][0] for info in infos}
    if not addresses or any(not ipaddress.ip_address(a.split('%')[0]).is_global for a in addresses):
        raise FetchError('private_address')
    return sorted(addresses)[0]


def listed(host: str) -> bool:
    """Whether this server fetches metadata documents from `host` (OAUTH_METADATA_HOSTS, exact names)."""
    return (host or '').lower() in {h.strip().lower() for h in settings.OAUTH_METADATA_HOSTS if h.strip()}


class _Deadline:
    """A connected socket whose every read and write must end by one moment. A timeout per read never fires for a host
    that sends a byte every few seconds; this one ends the whole exchange. http.client reads the answer through it."""

    def __init__(self, sock, deadline: float):
        self.sock, self.deadline = sock, deadline

    def _arm(self) -> None:
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('deadline')
        self.sock.settimeout(left)

    def sendall(self, data) -> None:
        self._arm()
        self.sock.sendall(data)

    def recv_into(self, buffer, nbytes: int = 0) -> int:
        self._arm()
        return self.sock.recv_into(buffer, nbytes)

    def makefile(self, mode='rb', buffering=None):
        return io.BufferedReader(socket.SocketIO(self, 'rb'))

    def _decref_socketios(self) -> None:
        pass

    def close(self) -> None:
        pass                        # the real socket is closed by fetch_document, once the answer is read


def _connect(address: str, port: int, host: str, deadline: float, context: ssl.SSLContext):
    """A TLS connection to `address`, its certificate checked for `host`, made before the deadline."""
    raw = socket.create_connection((address, port), timeout=max(deadline - time.monotonic(), 0.001))
    try:
        tls = context.wrap_socket(raw, server_hostname=host, do_handshake_on_connect=False)
    except BaseException:
        raw.close()
        raise
    try:
        tls.settimeout(max(deadline - time.monotonic(), 0.001))
        tls.do_handshake()          # one timeout for the whole handshake
    except BaseException:
        tls.close()
        raise
    return tls


def fetch_document(url: str) -> dict:
    """The metadata document at `url`, as JSON; FetchError when it cannot be had safely."""
    parts = _split(url)
    if parts is None or parts.scheme != 'https' or not parts.hostname or parts.username or parts.password:
        raise FetchError('scheme')
    host, port = parts.hostname, parts.port or 443
    if not listed(host):
        raise FetchError('unlisted')
    deadline = time.monotonic() + settings.OAUTH_METADATA_SECONDS
    address = _public_address(host, port)
    path = (parts.path or '/') + (f'?{parts.query}' if parts.query else '')
    context, sock = ssl.create_default_context(), None
    context.minimum_version = ssl.TLSVersion.TLSv1_2    # Python's default since 3.10, written so it stays
    try:
        sock = _connect(address, port, host, deadline, context)
        conn = http.client.HTTPSConnection(host, port, context=context)
        conn.sock = _Deadline(sock, deadline)       # connected and checked above: http.client never connects itself
        conn.request('GET', path, headers={'Accept': 'application/json', 'User-Agent': f'{settings.SITE_NAME}-OAuth/1',
                                           'Connection': 'close'})
        response = conn.getresponse()
        length = response.getheader('Content-Length') or ''
        if response.status == 200 and length.isdigit() and int(length) > MAX_DOCUMENT:
            raise FetchError('too_large')
        body = response.read(MAX_DOCUMENT + 1) if response.status == 200 else b''
    except TimeoutError as exc:
        raise FetchError('timeout') from exc
    except (OSError, http.client.HTTPException) as exc:
        raise FetchError('network') from exc
    finally:
        if sock is not None:
            sock.close()
    if response.status != 200:
        raise FetchError(f'status_{response.status}')
    if len(body) > MAX_DOCUMENT:
        raise FetchError('too_large')
    try:
        doc = json.loads(body)
    except ValueError as exc:
        raise FetchError('not_json') from exc
    if not isinstance(doc, dict):
        raise FetchError('not_json')
    return doc


def _split(url: str):
    """urlsplit, or None for what it cannot read (an unclosed «[», a port out of range): a refusal, never an error."""
    try:
        parts = urlsplit(url)
        parts.port                  # noqa: B018 (reading it checks it)
    except ValueError:
        return None
    return parts


def _valid_cimd_url(url: str) -> bool:
    """draft-ietf-oauth-client-id-metadata-document: https, a path, no fragment, no dot segments, no credentials."""
    parts = _split(url)
    if parts is None or len(url) > 500 or len(parts.hostname or '') > 253:      # the client_id and domain columns
        return False
    segments = parts.path.split('/')
    return (parts.scheme == 'https' and bool(parts.hostname) and parts.path not in ('', '/') and not parts.fragment
            and not parts.username and '.' not in segments and '..' not in segments)


def _redirects(value) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > 10:
        raise Refused('redirect_uris', 'invalid')
    for uri in value:
        if not redirect_host(uri):          # https, or http to this computer; one host for every reader
            raise Refused('redirect_uris', 'invalid')
    return list(value)


def _domain(redirects: list[str]) -> str:
    """Every host a client's redirects go to, so none hides behind another."""
    return ', '.join(sorted({redirect_host(u) for u in redirects} - {''}))[:255]


def _refusal_key(client_id: str) -> str:
    return 'oauth:refused:' + hashlib.sha256(client_id.encode()).hexdigest()[:32]


def by_metadata(client_id: str) -> Client:
    """The client a metadata document names, read again once a day; only from a listed host."""
    if not _valid_cimd_url(client_id):
        raise Refused('client_id', 'invalid')
    host = urlsplit(client_id).hostname or ''
    if not listed(host):
        raise Refused('client_id', 'unlisted')         # it registers instead: nothing is fetched
    client = Client.objects.filter(client_id=client_id).first()
    fresh = client and client.fetched_at and client.fetched_at > timezone.now() - timedelta(seconds=settings.CIMD_KEEP_SECONDS)
    if fresh:
        return client
    # A refusal of the last few minutes stands: no new fetch for each request while their host is down or wrong.
    refused = counters.get(_refusal_key(client_id))
    if refused == 'unreachable' and client is not None:
        return client
    if refused:
        raise Refused('client_id', refused)
    try:
        doc = fetch_document(client_id)
    except FetchError as exc:
        counters.set(_refusal_key(client_id), 'unreachable', settings.OAUTH_METADATA_REFUSAL_SECONDS)
        if client is not None:
            return client           # the copy of yesterday rather than no sign-in while their host is down
        raise Refused('client_id', 'unreachable') from exc
    try:
        redirects = _document(doc, client_id)
    except Refused:
        counters.set(_refusal_key(client_id), 'invalid', settings.OAUTH_METADATA_REFUSAL_SECONDS)
        raise
    values = _cimd_values(doc, host, redirects)
    client, _ = Client.objects.update_or_create(client_id=client_id, defaults=values)
    return client


def _document(doc: dict, client_id: str) -> list[str]:
    """The redirects of a document that names itself and asks for no secret; Refused otherwise."""
    if doc.get('client_id') != client_id or 'client_secret' in doc:
        raise Refused('client_id', 'invalid')
    if doc.get('token_endpoint_auth_method', 'none') != 'none':
        raise Refused('client_id', 'invalid')
    return _redirects(doc.get('redirect_uris'))


def _cimd_values(doc: dict, host: str, redirects: list[str]) -> dict:
    return {'kind': Client.Kind.CIMD, 'name': known_name(host) or str(doc.get('client_name') or '')[:120],
            'domain': host, 'redirect_uris': redirects, 'fetched_at': timezone.now()}


def register(meta: dict) -> Client:
    """RFC 7591: a public client (no secret), its redirects https or loopback."""
    if not isinstance(meta, dict):
        raise Refused('client_metadata', 'invalid')
    if meta.get('token_endpoint_auth_method', 'none') != 'none':
        raise Refused('token_endpoint_auth_method', 'invalid')
    grants = meta.get('grant_types') or ['authorization_code', 'refresh_token']
    if not isinstance(grants, list) or not all(isinstance(g, str) for g in grants) or \
            not set(grants) <= {'authorization_code', 'refresh_token'}:
        raise Refused('grant_types', 'invalid')
    responses = meta.get('response_types') or ['code']
    if responses != ['code']:
        raise Refused('response_types', 'invalid')
    redirects = _redirects(meta.get('redirect_uris'))
    name = str(meta.get('client_name') or '')[:120]
    return Client.objects.create(client_id='qc_' + secrets.token_urlsafe(18), kind=Client.Kind.DCR, name=name,
                                 domain=_domain(redirects), redirect_uris=redirects)


def find(client_id: str) -> Client:
    if not client_id:
        raise Refused('client_id', 'required')
    if is_cimd(client_id):
        return by_metadata(client_id)
    client = Client.objects.filter(client_id=client_id, kind=Client.Kind.DCR).first()
    if client is None:
        raise Refused('client_id', 'invalid')
    return client


def redirect_allowed(client: Client, uri: str) -> bool:
    """Exactly one of the client's redirects; a loopback one matches on any port (RFC 8252 §7.3, and Claude Code declares
    http://localhost/callback and http://127.0.0.1/callback and listens on a port of the moment)."""
    if not redirect_host(uri):
        return False                        # a client kept from before the check gets it here
    if uri in client.redirect_uris:
        return True
    asked = _split(uri)
    if asked.scheme != 'http' or asked.hostname not in ('localhost', '127.0.0.1', '::1'):
        return False
    for registered in client.redirect_uris:
        r = _split(registered) if redirect_host(registered) else None
        if r is not None and (r.scheme, r.hostname, r.path, r.query) == (asked.scheme, asked.hostname, asked.path, asked.query):
            return True
    return False


def is_loopback(uri: str) -> bool:
    return redirect_host(uri) in LOOPBACK
