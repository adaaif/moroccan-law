"""«المتابعة بحساب Google»: signing in, or up, with a Google account (9 Nov 2026).

The web sends the tab to Google's own sign-in page and Google sends it back with a signed ID TOKEN (web/src/features/
accounts/google.ts). Its signature is checked against Google's public keys, that it was minted for OUR client id
(GOOGLE_OAUTH_CLIENT_IDS), that it carries the nonce the web put in Google's link, and that Google says the address is
verified. No password crosses and no OAuth session is kept: the token is a one-shot proof traded for our own pair, as a
password sign-in is.

What the site takes from Google: the address and `sub` (Google's number for the person), nothing else; not the name, not
the picture (the scope asks for `openid email` alone). A new account chooses its username at the door like any other:
Google's name is usually the person's legal one, and a username signs what they write.

Linking: an identity is bound to an account by `sub`, never by the address (an address can change on Google's side,
`sub` cannot). The address is read once, the first time a `sub` is met, to find an account that already exists; safe
only because Google asserts `email_verified`, checked first: an unverified Google address would let anyone who opens a
Google account with someone else's email walk into theirs.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused

log = logging.getLogger(__name__)

ISSUERS = ('accounts.google.com', 'https://accounts.google.com')
_transport = None


def _request():
    """One transport for the process: a kept-alive connection to Google's keys."""
    global _transport
    if _transport is None:
        from google.auth.transport import requests as google_requests
        _transport = google_requests.Request()
    return _transport


def client_id() -> str:
    """What the web builds Google's link from; '' while Google is off (the web shows no button)."""
    return settings.GOOGLE_OAUTH_CLIENT_ID if settings.GOOGLE_OAUTH_CLIENT_IDS else ''


def _invalid() -> Refused:
    return Refused('google', 'invalid', 401)


def verify(token: str, *, nonce: str = '') -> dict:
    """Google's signed claims, or a refusal. Every fact used is a claim Google signed; nothing is taken from the
    request's body. The nonce is required for the web's client id: a token lifted from another sign-in cannot be
    replayed through this one."""
    from google.oauth2 import id_token

    audiences = settings.GOOGLE_OAUTH_CLIENT_IDS
    if not audiences:
        raise Refused('google', 'off', 503)
    if not token:
        raise _invalid()
    try:
        # audience=None on purpose: several client ids may be accepted (the web's, a phone's); compared below
        claims = id_token.verify_oauth2_token(token, _request(), clock_skew_in_seconds=10)
    except Exception as exc:  # ValueError for every bad shape, transport errors too
        log.info('google id_token refused: %s', exc)
        raise _invalid() from exc
    if claims.get('iss') not in ISSUERS or not claims.get('sub'):
        raise _invalid()
    if claims.get('aud') not in audiences:
        # Signed by Google, but minted for someone else's app: accepting it would hand that app's owner every account.
        log.warning('google id_token for a foreign audience: %r', claims.get('aud'))
        raise _invalid()
    if (nonce or claims.get('aud') == settings.GOOGLE_OAUTH_CLIENT_ID) and (not nonce or claims.get('nonce') != nonce):
        raise _invalid()
    if not (claims.get('email') or '').strip():
        raise Refused('google', 'no_email')
    if not claims.get('email_verified'):
        raise Refused('google', 'email_unverified')
    return claims


def address(claims: dict) -> str:
    return claims['email'].strip().lower()


def find(claims: dict):
    """The account these claims sign into: the one bound to `sub`, else the one holding the verified address; None for
    nobody yet. A deleted account's row holds neither."""
    User = get_user_model()
    return (User.objects.filter(google_sub=claims['sub']).first()
            or User.objects.filter(email__iexact=address(claims)).first())


@transaction.atomic
def link(user, claims: dict):
    """Bind the identity to an account (nothing to do once bound) and answer the account as it now is. Google's word
    proves the address, as the six-digit code does. When it had never been proven, whoever set the account's password
    may not own the inbox (an account opened in someone else's name, waiting for them): the proven owner takes it alone,
    the password voided, every session and every assistant's connection ended; «نسيت كلمة السر» gives them a
    password of their own.

    The row is locked and read again first: what decides is the account as it is now, not as it was found. An account
    found by its address that moved to another one meanwhile is not bound (`google.invalid`: the person tries again)."""
    from apps.accounts.services.passwords import end_sessions, staff
    from apps.oauth.services.tokens import end_all

    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if staff(user):
        # A staff account opens the admin: its password alone opens it, never an inbox's owner (passwords.py).
        raise Refused('login', 'staff', 403)
    if user.google_sub == claims['sub']:
        return user
    if user.google_sub:
        # The address now belongs to ANOTHER Google account (an address given to someone new): the bound one stays the key.
        raise Refused('google', 'other', 409)
    if user.email.lower() != address(claims):
        raise _invalid()
    user.google_sub = claims['sub']
    fields, voided = ['google_sub'], False
    if user.email_proven_at is None:
        user.email_proven_at = timezone.now()
        fields.append('email_proven_at')
        if user.has_usable_password():
            user.set_unusable_password()
            fields.append('password')
            voided = True
    user.save(update_fields=fields)
    if voided:
        end_sessions(user)
        end_all(user)
    return user


def create(claims: dict, *, username: str, preferred_language: str = 'ar'):
    """A new account for these claims with the username the person chose: its door is Google, no password until a reset
    sets one; its address proven (Google said so). Returns (user, created): a double tap finds what the first made."""
    from apps.accounts.services.accounts import name_held

    User = get_user_model()
    username = username.strip()
    if name_held(username):
        raise Refused('username', 'held')
    if User.objects.filter(username__iexact=username).exists():
        raise Refused('username', 'username_taken')
    try:
        with transaction.atomic():
            user = User.objects.create_user(username=username, email=address(claims), password=None,
                                            preferred_language=preferred_language, google_sub=claims['sub'],
                                            email_proven_at=timezone.now())
        return user, True
    except IntegrityError as exc:
        known = find(claims)
        if known is not None:            # the address or the sub arrived meanwhile: a double tap, signed in
            return link(known, claims), False
        raise Refused('username', 'username_taken') from exc
