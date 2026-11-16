"""The site's MCP server (MC9–MC20 of the MCP review, 3 Nov 2026): five read-only tools on the official Python SDK,
stateless Streamable HTTP with plain JSON answers.

It runs as its own service, law-mcp (uvicorn, config/mcp_asgi.py), with Django loaded in the process: the tools call the
services the site's API uses and share its kept answers. nginx sends /mcp here.

Open to everyone since 3 Nov 2026 (the sign-in is kept for tools that will need an account): MCP_AUTH 'open'
needs no sign-in; a token from the site's sign-in (apps.oauth, built and advertised either way) is still read, and its
account's own limits apply. MCP_AUTH 'required' answers any call without a live token 401, pointing at the
protected-resource metadata (Claude signs in only on a 401). Tools that need an account come later, beside the open ones,
so a connection made today keeps working.
"""
import json
import logging
from contextvars import ContextVar
from typing import Annotated, Any

import anyio
from django.conf import settings
from django.db import close_old_connections
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, Icon, TextContent, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

from apps.mcp.services import law, origin, quotas
from apps.mcp.services.quotas import Caller
from apps.oauth.services import tokens
from apps.opendata.services import gate as open_data, keys, usage


def instructions() -> str:
    """MC16: what the data is, said in the first 512 characters (ChatGPT reads them most; Claude's review refuses
    instructions about how to behave), under the site's name."""
    return (
        f'{settings.SITE_NAME} (قانون) serves Moroccan law from the Bulletin officiel, article by article: the Arabic '
        'text, the official French translation where the BO printed one, and the BO issue and page each comes from. '
        'Consolidated versions are unofficial; the Bulletin officiel prevails. A projet de loi is a bill, not law. '
        'Results are the text of the law, not legal advice. Each result has a link to cite. Ask in Arabic, French or '
        'Darija.'
    )


SCOPE = 'law:read'
READ_ONLY = dict(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
# Who is calling, set by the gate in front for the tools (a context variable reaches their worker threads).
CALLER: ContextVar[Caller | None] = ContextVar('mcp_caller', default=None)
COUNTING_THREADS = 2
CAP = 64 * 1024            # the bytes of a call's body read for its method and _meta; a longer one is counted, not read
log = logging.getLogger(__name__)


def security() -> dict:
    """Each tool's security scheme, which ChatGPT reads to offer linking or not (OpenAI Apps SDK, «Authentication»)."""
    if settings.MCP_AUTH == 'required':
        return {'securitySchemes': [{'type': 'oauth2', 'scopes': [SCOPE]}]}
    return {'securitySchemes': [{'type': 'noauth'}]}


def _resource_metadata_url() -> str:
    return settings.OAUTH_ISSUER + '/.well-known/oauth-protected-resource/mcp'


# ── Calling Django from the event loop ───────────────────────────────────────

def _db(fn, *args, **kwargs):
    """A unit of Django work in a worker thread, with the connection checks a Django request makes around it."""
    close_old_connections()
    try:
        return fn(*args, **kwargs)
    finally:
        close_old_connections()


def _caller() -> Caller:
    caller = CALLER.get()
    if caller is None:
        raise PermissionError('no caller')
    return caller


def _error(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type='text', text=message)], is_error=True)


def _run(tool: str, work, *, bodies: bool):
    """Count the call against the caller's share, do the work, count what it served. A Problem or a Limit is an answer
    the model can act on, not a failure."""
    caller = _caller()
    try:
        _db(quotas.charge, caller, bodies=bodies)
        result, served = _db(work)
    except (quotas.Limit, law.Problem) as exc:
        return _error(str(exc))
    _db(quotas.served, caller, tool, served)
    return result


# ── The tools ────────────────────────────────────────────────────────────────

class ReadOut(BaseModel):
    model_config = ConfigDict(extra='allow')
    law: dict[str, Any]
    version: dict[str, Any] | None
    on: str | None
    articles: list[dict[str, Any]]
    range: list[int]
    total: int
    next: str | None


class ReferencesOut(BaseModel):
    model_config = ConfigDict(extra='allow')
    since: str | None
    references: list[dict[str, Any]]


class BulletinOut(BaseModel):
    model_config = ConfigDict(extra='allow')
    issues: list[dict[str, Any]]


def _json_text(data: dict) -> CallToolResult:
    """search and fetch answer as ChatGPT's deep research and company knowledge expect: one text block of JSON."""
    return CallToolResult(content=[TextContent(type='text', text=json.dumps(data, ensure_ascii=False, default=str))])


def search(query: Annotated[str, Field(description='A question or words in Arabic, French or Darija, a citation '
                                                   '(«المادة 53 من مدونة الشغل», «art. 6 loi 31-13»), a law\'s '
                                                   'everyday name, a BO issue number, or "words in quotes" for an '
                                                   'exact phrase.', max_length=300)]) -> CallToolResult:
    """Search Moroccan law in {site}: every text of the Bulletin officiel, article by article. Returns up to 10
    articles and texts, best first, each with its id, title, link, a snippet and whether it is in force. Use fetch with
    an id to read the whole article or text."""
    def work():
        return _json_text(law.search(query)), 0
    return _run('search', work, bodies=False)


def fetch(id: Annotated[str, Field(description='An id from search, such as /ma/loi/65-99/art_51 (an article), '
                                               '/ma/loi/65-99 (a text) or bo/7533 (a Bulletin officiel issue); a '
                                               '3adala.com link works too.', max_length=300)]) -> CallToolResult:
    """Read one item from {site} by its id. An article gives its full Arabic text, the official French where the BO
    printed one, whether it is in force, the BO issue and page of its text, its version and the texts that changed it. A
    law or decree gives its facts and its outline with each article's id. A BO issue gives the texts it published."""
    def work():
        item, served = law.fetch(id)
        return _json_text(item), served
    return _run('fetch', work, bodies=True)


def read_articles(
        id: Annotated[str, Field(description='A text\'s id (/ma/loi/65-99) or an article\'s id to start from.',
                                 max_length=300)],
        start: Annotated[str | int, Field(description='The article number to start from, e.g. 51 or "51 مكرر"; empty '
                                                      'starts at the article in the id, or the first.')] = '',
        count: Annotated[int, Field(description='How many articles, 1 to 20.', ge=1, le=20)] = 10,
        on: Annotated[str, Field(description='A date (YYYY-MM-DD) to read the articles as they stood that day; '
                                             'empty for today.', max_length=10)] = '',
        french: Annotated[bool, Field(description='Also give the official French where the BO printed one.')] = False,
) -> Annotated[CallToolResult, ReadOut]:
    """Read up to 20 consecutive articles of a Moroccan text (a chapter, or what follows an article), optionally as
    they stood on a past date, for what applied when something happened. Says which version it is and where to read
    on."""
    def work():
        text, data, served = law.read_articles(id, start=str(start)[:20], count=count, on=on, french=french)
        return CallToolResult(content=[TextContent(type='text', text=text)], structured_content=data), served
    return _run('read_articles', work, bodies=True)


def check_references(
        references: Annotated[list[Annotated[str, Field(max_length=200)]],
                              Field(description='The references alone, as written, e.g. ["المادة 52 من مدونة الأسرة", '
                                                '"Dahir n° 1-03-194", "art. 6 loi 31-13"]. Never a whole document.',
                                    min_length=1, max_length=50)],
        since: Annotated[str, Field(description='A date (YYYY-MM-DD): also say whether each changed after it.',
                                    max_length=10)] = '',
) -> Annotated[CallToolResult, ReferencesOut]:
    """Check references to Moroccan law, as written in an answer or found in a document: for each, whether {site}
    finds it, which text and article it is, whether it is in force or repealed, whether it changed after a date, and
    its link."""
    def work():
        text, data = law.check_references(references, since)
        return CallToolResult(content=[TextContent(type='text', text=text)], structured_content=data), 0
    return _run('check_references', work, bodies=False)


def get_bulletin(issue: Annotated[str, Field(description='An issue number, e.g. 7533 or 7533-bis; empty for the '
                                                         'latest week.', max_length=40)] = '') -> Annotated[CallToolResult, BulletinOut]:
    """List what the Bulletin officiel published: by default the latest week's issues of its Arabic general edition,
    or one issue by its number. Each text with its kind, title, page and link."""
    def work():
        data = law.bulletin(issue)
        return CallToolResult(content=[TextContent(type='text', text=law.bulletin_text(data))],
                              structured_content=law.bulletin_data(data)), 0
    return _run('get_bulletin', work, bodies=False)


def described(tool) -> str:
    """A tool's description: its docstring, with the site's name where it says {site}."""
    return tool.__doc__.replace('{site}', settings.SITE_NAME)


def build() -> MCPServer:
    # The app's own icons, each size a client may ask for. claude.ai shows none of them: it asks Google for the favicon of
    # the address's last two labels (anthropics/claude-ai-mcp#152, 3 Nov 2026): the old address's parent domain showed
    # another site's icon until the site's own domain, 3adala.com, on 4 Nov 2026.
    site = settings.SITE_URL.rstrip('/')
    icons = [Icon(src=f'{site}/icons/{name}', mime_type='image/png', sizes=[size])
             for name, size in (('favicon-48.png', '48x48'), ('icon-192.png', '192x192'), ('icon-512.png', '512x512'))]
    server = MCPServer(
        name=settings.SITE_NAME, title=f'قانون المغرب · {settings.SITE_NAME}', instructions=instructions(),
        website_url=settings.SITE_URL, version='1', icons=icons,
        description='Moroccan law from the Bulletin officiel, article by article, in Arabic and French.',
    )
    # A fixed order (the 2026-07-28 spec asks for it; it helps the assistants' prompt caches).
    server.add_tool(search, title='البحث في القانون · Rechercher dans la loi',
                    description=described(search),
                    annotations=ToolAnnotations(**READ_ONLY), meta=security(), structured_output=False)
    server.add_tool(fetch, title='قراءة مادة أو نص · Lire un article ou un texte',
                    description=described(fetch),
                    annotations=ToolAnnotations(**READ_ONLY), meta=security(), structured_output=False)
    server.add_tool(read_articles, title='قراءة مواد متتالية · Lire des articles à la suite',
                    description=described(read_articles),
                    annotations=ToolAnnotations(**READ_ONLY), meta=security())
    server.add_tool(check_references, title='التحقق من الإحالات · Vérifier des références',
                    description=described(check_references),
                    annotations=ToolAnnotations(**READ_ONLY), meta=security())
    server.add_tool(get_bulletin, title='الجريدة الرسمية · Le Bulletin officiel',
                    description=described(get_bulletin),
                    annotations=ToolAnnotations(**READ_ONLY), meta=security())
    return server


# ── The gate in front of it (MC19) ───────────────────────────────────────────

async def _read(receive) -> tuple[bytes, list[dict]]:
    """A request's body, read whole before the SDK reads it (nginx caps it), and the messages to hand the SDK again."""
    body, messages = bytearray(), []
    while True:
        message = await receive()
        messages.append(message)
        if message['type'] != 'http.request':
            break
        body.extend(message.get('body', b''))
        if not message.get('more_body'):
            break
    return bytes(body), messages


def _again(messages: list[dict], receive):
    async def inner():
        return messages.pop(0) if messages else await receive()
    return inner


def _asked(body: bytes) -> tuple[str, dict]:
    """A JSON-RPC call's method and its `_meta` (a batch, from a 2025-03 client, by its first message); ('', {}) for a
    body that is no such call or is longer than CAP, which is not parsed."""
    if len(body) > CAP:
        return '', {}
    try:
        data = json.loads(body)
    except ValueError:
        return '', {}
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        return '', {}
    params = data.get('params') if isinstance(data.get('params'), dict) else {}
    meta = params.get('_meta') if isinstance(params.get('_meta'), dict) else {}
    return str(data.get('method') or ''), meta


class Gate:
    """Who is calling. A live access token for MCP_RESOURCE: its account. Otherwise, with MCP_AUTH 'open', the
    assistant's platform by its address range (a ChatGPT user by its subject too), a direct caller's key (X-Api-Key:
    its access, whose own limits it spends; a key that opens nothing is a 401, a key while the keyed API is closed or
    whose access has no API a 403, each in the site's error shape), or the direct caller's address (a token that does
    not verify is set aside, never a dead end for someone who once connected); with MCP_AUTH 'required', a 401 naming
    the protected-resource metadata and the scope. CORS preflights pass. A platform's users are never read by a key.

    Every request counts against the caller's share: a tool call in its tool, which says the limit as its answer; any
    other request here, a 429 once the share is spent. The counts are kept in the counters store, reached from threads of
    their own: nothing waits on the network in the event loop, and the tools' threads never hold up a count."""

    def __init__(self, app):
        self.app = app
        self.limited = False
        self.counting = None

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] == 'OPTIONS':
            return await self.app(scope, receive, send)
        if not self.limited:
            # The tools' threads, each holding a database connection while it works (MC20).
            anyio.to_thread.current_default_thread_limiter().total_tokens = settings.MCP_THREADS
            # The counts of the requests that are not tool calls: two threads of their own, a few milliseconds each.
            self.counting = anyio.CapacityLimiter(COUNTING_THREADS)
            self.limited = True
        # The call's body first: its method says whether a tool counts it, its _meta who calls.
        body = b''
        if scope['method'] == 'POST':
            body, received = await _read(receive)
            receive = _again(received, receive)
        method, meta = _asked(body)
        headers = dict(scope.get('headers') or [])
        header = headers.get(b'authorization', b'').decode('latin-1')
        raw = header[7:].strip() if header[:7].lower() == 'bearer ' else ''
        row = await anyio.to_thread.run_sync(_db, tokens.verify, raw) if raw else None
        reset = None
        if row is not None:
            grant = row.grant
            user = AuthenticatedUser(AccessToken(
                token=raw, client_id=grant.client.client_id, scopes=grant.scope.split(), resource=grant.resource,
                expires_at=int(row.expires_at.timestamp()), subject=str(grant.user_id),
                claims={'grant': grant.pk, 'iss': settings.OAUTH_ISSUER}))
            scope['user'] = user
            reset = auth_context_var.set(user)
            caller = Caller('account', str(grant.user_id), 'accounts', grant.pk)
        elif settings.MCP_AUTH == 'required':
            return await self._refuse(send, given=bool(raw))
        else:
            ip = (scope.get('client') or ('', 0))[0]
            name = origin.platform(ip)
            key = '' if name else headers.get(b'x-api-key', b'').decode('latin-1').strip()
            if key:
                held = await self._key(send, key)
                if held is None:
                    return
                caller = Caller('key', str(held.access), 'keys', holder=held)
                send = self._with_limits(send, held)
            else:
                # ChatGPT says which of its users calls (openai/subject), read only from its own ranges: a share each.
                subject = quotas.subject_key(meta.get('openai/subject')) if name == 'chatgpt' else ''
                caller = (Caller('platform', name, name, subject=subject) if name else
                          Caller('address', origin.bucket(ip),
                                 'direct:' + origin.client_name(headers.get(b'user-agent', b'').decode('latin-1'))))
        if method != 'tools/call':
            try:
                await anyio.to_thread.run_sync(_db, quotas.charge, caller, limiter=self.counting)
            except quotas.Limit as exc:
                try:
                    return await self._limit(send, exc)
                finally:
                    if reset is not None:
                        auth_context_var.reset(reset)
            except Exception:
                # The counts' store does not answer: a request that reads no law (the handshake, the tools' list) goes
                # on uncounted, and the log says so. A tool call still fails in its tool, where the law is read.
                log.exception('mcp: a request could not be counted')
        mark = CALLER.set(caller)
        try:
            await self.app(scope, receive, send)
        finally:
            CALLER.reset(mark)
            if reset is not None:
                auth_context_var.reset(reset)

    async def _key(self, send, key: str):
        """The holder of a direct caller's key, or None once its refusal is sent."""
        try:
            held = await anyio.to_thread.run_sync(_db, keys.read, key)
        except keys.Refused as refused:
            return await self._refusal(send, 401, 'key', refused.code)
        if open_data.position() == open_data.CLOSED:
            return await self._refusal(send, 403, 'access', 'closed')
        if not held.api:
            return await self._refusal(send, 403, 'access', 'no_api')
        return held

    def _with_limits(self, send, held):
        """A key's answers carry its access's RateLimit-Policy and RateLimit, read as the answer starts."""
        async def inner(message):
            if message['type'] == 'http.response.start':
                try:
                    said = await anyio.to_thread.run_sync(usage.headers, held, limiter=self.counting)
                except Exception:
                    log.exception('mcp: a key\'s limits could not be read for its answer')
                    said = {}
                message = {**message, 'headers': [*message.get('headers', []),
                                                  *((k.lower().encode(), v.encode()) for k, v in said.items())]}
            await send(message)
        return inner

    @staticmethod
    async def _refusal(send, status: int, field: str, code: str) -> None:
        body = json.dumps({'errors': [{'field': field, 'code': code}]}).encode()
        await send({'type': 'http.response.start', 'status': status, 'headers': [
            (b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())]})
        await send({'type': 'http.response.body', 'body': body})

    @staticmethod
    async def _limit(send, exc: quotas.Limit):
        """A request past its share that is not a tool call: a 429 with when to come back, its words in JSON-RPC."""
        body = json.dumps({'jsonrpc': '2.0', 'id': None, 'error': {'code': -32000, 'message': str(exc)}}).encode()
        await send({'type': 'http.response.start', 'status': 429, 'headers': [
            (b'content-type', b'application/json'), (b'content-length', str(len(body)).encode()),
            (b'retry-after', str(max(exc.retry, 1)).encode())]})
        await send({'type': 'http.response.body', 'body': body})

    @staticmethod
    async def _refuse(send, *, given: bool):
        parts = [f'resource_metadata="{_resource_metadata_url()}"', f'scope="{SCOPE}"']
        if given:
            parts.insert(0, 'error="invalid_token", error_description="The token is unknown, expired or revoked"')
        body = json.dumps({'error': 'invalid_token' if given else 'unauthorized',
                           'error_description': f'Sign in with your {settings.SITE_NAME} account.'}).encode()
        await send({'type': 'http.response.start', 'status': 401, 'headers': [
            (b'content-type', b'application/json'), (b'content-length', str(len(body)).encode()),
            (b'www-authenticate', ('Bearer ' + ', '.join(parts)).encode())]})
        await send({'type': 'http.response.body', 'body': body})


def asgi():
    """The ASGI app: CORS (browser clients such as the MCP Inspector), then the gate, then the SDK's stateless
    Streamable HTTP endpoint at /mcp answering in JSON. Both wrappers pass the lifespan through to the SDK's app."""
    app = build().streamable_http_app(
        streamable_http_path='/mcp', json_response=True, stateless_http=True,
        # Behind nginx and a bearer token: the SDK's localhost-only host check does not apply.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    return CORSMiddleware(Gate(app), allow_origins=['*'], allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'],
                          allow_headers=['*'], expose_headers=['Mcp-Session-Id', 'WWW-Authenticate'])
