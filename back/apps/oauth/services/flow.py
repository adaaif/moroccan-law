"""The authorization request, from the assistant's link to the person's answer on /connect (MC7).

`authorize` checks what the assistant asked for. Until its redirect is known good, a refusal is shown on the site's own page
(`Shown`); after, it goes back to an assistant the site knows as an RFC 6749 error with `state` and `iss`, and any other
client's is shown on the site's page too: no page a client chose is opened without the person's answer. A request waits
OAUTH_REQUEST_SECONDS for the person. Approving needs a signed-in account with a proven email (C2).
"""
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.oauth.models import AuthRequest, Grant
from apps.oauth.services import clients, tokens

SCOPE = 'law:read'
SUPPORTED_SCOPES = {SCOPE, 'offline_access'}


class Shown(Exception):
    """A refusal the site shows itself: the redirect cannot be trusted with it."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class Back(Exception):
    """A refusal sent back to the assistant's redirect."""

    def __init__(self, url: str):
        super().__init__(url)
        self.url = url


def with_params(uri: str, params: dict) -> str:
    parts = urlsplit(uri)
    query = parse_qsl(parts.query, keep_blank_values=True) + [(k, v) for k, v in params.items() if v is not None]
    return urlunsplit(parts._replace(query=urlencode(query)))


def _error(redirect_uri: str, state: str, error: str, description: str = '') -> Back:
    return Back(with_params(redirect_uri, {'error': error, 'error_description': description or None,
                                           'state': state or None, 'iss': settings.OAUTH_ISSUER}))


def authorize(params) -> str:
    """The raw id of a waiting request for /connect, or Shown / Back. Only a client the site knows is sent its refusals
    back: for any other, this address would be a way to send people from the site to a page of its choosing."""
    client_id = params.get('client_id', '')
    try:
        client = clients.find(client_id)
    except Refused as exc:
        raise Shown('client_' + exc.code) from exc
    redirect_uri = params.get('redirect_uri', '')
    if not redirect_uri and len(client.redirect_uris) == 1:
        redirect_uri = client.redirect_uris[0]
    if not redirect_uri or not clients.redirect_allowed(client, redirect_uri):
        raise Shown('redirect')
    state = params.get('state', '')[:1000]
    known = clients.is_known(client)

    def refuse(shown: str, error: str, description: str) -> Exception:
        return _error(redirect_uri, state, error, description) if known else Shown(shown)

    if params.get('response_type') != 'code':
        raise refuse('response_type', 'unsupported_response_type', 'Only the code flow is offered.')
    challenge = params.get('code_challenge', '')
    if params.get('code_challenge_method') != 'S256' or not 43 <= len(challenge) <= 128:
        raise refuse('pkce', 'invalid_request', 'PKCE with S256 is required.')
    resource = params.get('resource', '') or settings.MCP_RESOURCE
    if not tokens.same_resource(resource, settings.MCP_RESOURCE):
        raise refuse('resource', 'invalid_target', f'{settings.SITE_NAME} issues tokens for its MCP server only.')
    asked = set((params.get('scope') or SCOPE).split())
    if not asked & SUPPORTED_SCOPES:
        raise refuse('scope', 'invalid_scope', 'The scope offered is law:read.')
    raw = secrets.token_urlsafe(24)
    AuthRequest.objects.create(digest=tokens.digest(raw), client=client, redirect_uri=redirect_uri, state=state,
                               code_challenge=challenge, scope=SCOPE, resource=settings.MCP_RESOURCE,
                               expires_at=timezone.now() + timedelta(seconds=settings.OAUTH_REQUEST_SECONDS))
    return raw


def _waiting(raw: str) -> AuthRequest:
    raw = raw if isinstance(raw, str) else ''        # a JSON body's number or list is no request's id
    row = (AuthRequest.objects.select_related('client').filter(digest=tokens.digest(raw)).first())
    if row is None or row.decided_at or row.expires_at <= timezone.now():
        raise Refused('request', 'expired', 410)
    return row


def describe(raw: str) -> dict:
    """What /connect shows: the host the answer goes to (its headline, checked again by the page before it leaves), who
    asks, for how long."""
    row = _waiting(raw)
    client = row.client
    known = clients.known_as(client)
    return {'client': {'name': known or client.name, 'known': bool(known), 'domain': clients.shown_domain(client),
                       'self_named': not known},
            'redirect_host': clients.redirect_host(row.redirect_uri),
            'loopback': clients.is_loopback(row.redirect_uri), 'scope': row.scope,
            'expires_at': row.expires_at}


def approve(raw: str, user) -> str:
    """The person's yes: a code for the assistant, at its redirect. One connection per account and assistant."""
    if not user.email_proven_at:
        raise Refused('email', 'not_proven', 403)
    with transaction.atomic():
        row = _waiting(raw)
        if AuthRequest.objects.filter(pk=row.pk, decided_at=None).update(decided_at=timezone.now()) != 1:
            raise Refused('request', 'expired', 410)
        grant = Grant.objects.filter(user=user, client=row.client, revoked_at=None).first()
        if grant is None:
            grant = Grant.objects.create(user=user, client=row.client, scope=row.scope, resource=row.resource)
        code = tokens.issue_code(grant, row.redirect_uri, row.code_challenge)
    return with_params(row.redirect_uri, {'code': code, 'state': row.state or None, 'iss': settings.OAUTH_ISSUER})


def deny(raw: str) -> str:
    row = _waiting(raw)
    AuthRequest.objects.filter(pk=row.pk, decided_at=None).update(decided_at=timezone.now())
    return with_params(row.redirect_uri, {'error': 'access_denied', 'state': row.state or None,
                                          'iss': settings.OAUTH_ISSUER})
