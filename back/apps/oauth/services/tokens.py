"""Codes and tokens (MC5): opaque random strings handed out once, kept as SHA-256 digests.

- A code is exchanged once, within OAUTH_CODE_SECONDS, with the PKCE verifier (S256) and the redirect it was issued for.
- An access token lives OAUTH_ACCESS_SECONDS, a refresh token OAUTH_REFRESH_DAYS. A refresh token is replaced each time
  it is used. One used again after its replacement ends the whole grant (it was stolen, or copied), except within
  REPLAY_SECONDS, when the answer that replaced it is given again: a phone on 3G that lost the answer is not signed out.
- Every token is for one resource, the MCP server (RFC 8707), and one scope.
"""
import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.oauth.models import Client, Code, Grant, Token

REPLAY_SECONDS = 120


class OAuthError(Exception):
    """An RFC 6749 error answer: {error, error_description}."""

    def __init__(self, error: str, description: str = '', status: int = 400):
        super().__init__(error)
        self.error, self.description, self.status = error, description, status


def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def same_resource(a: str, b: str) -> bool:
    """RFC 8707 resource identifiers compared as the MCP authorization spec asks: scheme and host in any case, no trailing
    slash."""
    def norm(u: str) -> str:
        u = (u or '').strip().rstrip('/')
        scheme, _, rest = u.partition('://')
        host, slash, path = rest.partition('/')
        return f'{scheme.lower()}://{host.lower()}{slash}{path}'
    return norm(a) == norm(b)


def issue_code(grant: Grant, redirect_uri: str, challenge: str) -> str:
    raw = secrets.token_urlsafe(32)
    Code.objects.create(digest=digest(raw), grant=grant, redirect_uri=redirect_uri, code_challenge=challenge,
                        expires_at=timezone.now() + timedelta(seconds=settings.OAUTH_CODE_SECONDS))
    return raw


def _pair(grant: Grant) -> dict:
    now = timezone.now()
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    Token.objects.bulk_create([
        Token(digest=digest(access), kind=Token.Kind.ACCESS, grant=grant,
              expires_at=now + timedelta(seconds=settings.OAUTH_ACCESS_SECONDS)),
        Token(digest=digest(refresh), kind=Token.Kind.REFRESH, grant=grant,
              expires_at=now + timedelta(days=settings.OAUTH_REFRESH_DAYS)),
    ])
    return {'access_token': access, 'token_type': 'Bearer', 'expires_in': settings.OAUTH_ACCESS_SECONDS,
            'refresh_token': refresh, 'scope': grant.scope}


def _pkce_ok(verifier: str, challenge: str) -> bool:
    if not verifier or not 43 <= len(verifier) <= 128:
        return False
    made = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    return hmac.compare_digest(made, challenge)


def _check_resource(grant: Grant, resource: str) -> None:
    if resource and not same_resource(resource, grant.resource):
        raise OAuthError('invalid_target', f'This token is for the {settings.SITE_NAME} MCP server.')


def exchange_code(*, client_id: str, code: str, redirect_uri: str, verifier: str, resource: str = '') -> dict:
    """The code spent first, whatever follows: a code tried with a wrong verifier is gone for good (RFC 6749 §10.5)."""
    if not code:
        raise OAuthError('invalid_request', 'code is required.')
    now = timezone.now()
    with transaction.atomic():
        row = (Code.objects.select_for_update().select_related('grant__client', 'grant__user')
               .filter(digest=digest(code)).first())
        spent = row is not None and not row.used_at and row.expires_at > now
        if spent:
            row.used_at = now
            row.save(update_fields=['used_at'])
    if not spent:
        raise OAuthError('invalid_grant', 'The code is unknown, used or expired.')
    grant = row.grant
    if grant.client.client_id != client_id:
        raise OAuthError('invalid_grant', 'The code was issued to another client.')
    if redirect_uri != row.redirect_uri:
        raise OAuthError('invalid_grant', 'redirect_uri differs from the authorization request.')
    if not _pkce_ok(verifier, row.code_challenge):
        raise OAuthError('invalid_grant', 'The PKCE verifier does not match.')
    _check_resource(grant, resource)
    if grant.revoked_at or not _user_ok(grant.user):
        raise OAuthError('invalid_grant', 'The connection was ended.')
    Client.objects.filter(pk=grant.client_id).update(used_at=timezone.now())
    return _pair(grant)


def refresh(*, client_id: str, token: str, resource: str = '') -> dict:
    if not token:
        raise OAuthError('invalid_request', 'refresh_token is required.')
    key = digest(token)
    reused = None
    with transaction.atomic():
        row = (Token.objects.select_for_update().select_related('grant__client', 'grant__user')
               .filter(digest=key, kind=Token.Kind.REFRESH).first())
        if row is None or row.expires_at <= timezone.now():
            raise OAuthError('invalid_grant', 'The refresh token is unknown or expired.')
        grant = row.grant
        if grant.client.client_id != client_id:
            raise OAuthError('invalid_grant', 'The refresh token was issued to another client.')
        if grant.revoked_at or not _user_ok(grant.user):
            raise OAuthError('invalid_grant', 'The connection was ended.')
        _check_resource(grant, resource)
        if row.replaced_at:
            reused = grant
        else:
            row.replaced_at = timezone.now()
            row.save(update_fields=['replaced_at'])
            answer = _pair(grant)
    if reused is not None:
        again = cache.get(f'oauth:replay:{key}')
        if again:
            return json.loads(again)
        # Used again after it was replaced: whoever holds it is not the client it was given to. Ended outside the
        # transaction above, which the refusal would roll back.
        Grant.objects.filter(pk=reused.pk).update(revoked_at=timezone.now())
        raise OAuthError('invalid_grant', 'The refresh token was already used.')
    cache.set(f'oauth:replay:{key}', json.dumps(answer), REPLAY_SECONDS)
    return answer


def revoke(token: str) -> None:
    """RFC 7009: the token's grant ends (an assistant that signs out is disconnected); an unknown token is no error."""
    row = Token.objects.filter(digest=digest(token or '')).first()
    if row is not None:
        Grant.objects.filter(pk=row.grant_id, revoked_at=None).update(revoked_at=timezone.now())


def _user_ok(user) -> bool:
    return user.is_active and not user.deleted_at


def verify(raw: str):
    """The live access token `raw`, with its grant, client and user; None for anything else. One indexed query."""
    if not raw:
        return None
    row = (Token.objects.select_related('grant__user', 'grant__client')
           .filter(digest=digest(raw), kind=Token.Kind.ACCESS, expires_at__gt=timezone.now(), grant__revoked_at=None)
           .first())
    if row is None or not _user_ok(row.grant.user) or not same_resource(row.grant.resource, settings.MCP_RESOURCE):
        return None
    return row


def end_all(user) -> int:
    """Every connection of the account ended: a new password, a reset, the account deleted (C3)."""
    return Grant.objects.filter(user=user, revoked_at=None).update(revoked_at=timezone.now())
