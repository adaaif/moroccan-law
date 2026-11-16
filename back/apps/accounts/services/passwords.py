"""The password: asked again before what a stolen session must not do, changed, and set anew from a link sent to the
account's address when it is forgotten (3 Nov 2026, as sign-up opened with real letters).

- `checked`: the current password at a door that asks for it again (a new password, a new address, leaving), through
  the brake on wrong passwords.
- `change`: a new password ends every session (the other devices are signed out) and this device gets a fresh pair.
- The reset: `request_reset` takes a username or an address and mails a link to the account's address; `confirm_reset`
  sets the new password and signs in. The link is `/reset#u=…&t=…`: what follows «#» never reaches a server, so the
  token is in no log. It works PASSWORD_RESET_TIMEOUT and once (Django's token: a new password, a new address or a
  sign-in ends it). Asked by an address, the answer says plainly whether an account holds it (sign-up already says
  «email in use») and shows it back masked («ka•••@gmail.com»); asked by a username, it says only that a letter
  went: usernames are public, and an address's domain (an employer's, a firm's) can name the person behind one.
  Opened, the link proves the address: it came to that inbox.
- A staff account is sent no link (`login.staff`): it opens the admin, so its password alone opens it.
"""
from math import ceil

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.services import addresses, brake, mail
from apps.accounts.services.accounts import tokens_for
from apps.accounts.services.refusals import Refused


def _locked(seconds: int) -> Refused:
    return Refused('password', 'locked', 429, minutes=max(1, ceil(seconds / 60)))


def checked(user, password: object, ip: str) -> None:
    """The current password, asked again; a wrong one counts with the sign-in's brake."""
    wait = brake.wait(user, ip)
    if wait:
        raise _locked(wait)
    if not user.check_password(str(password or '')):
        wait = brake.failed(user, ip)
        if wait:
            raise _locked(wait)
        raise Refused('password', 'invalid')


def validated(password: object, user, field: str) -> str:
    """A new password by the sign-up's rules; the first broken rule is the code."""
    password = str(password or '')
    if not password:
        raise Refused(field, 'required')
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        raise Refused(field, exc.error_list[0].code) from exc
    return password


def end_sessions(user) -> None:
    """Every refresh token the account holds refused from now on: its devices are signed out once their access token
    ends (30 minutes at most). Two queries, whatever the number of devices."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    live = OutstandingToken.objects.filter(user=user, expires_at__gt=timezone.now(), blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create([BlacklistedToken(token_id=pk) for pk in live.values_list('pk', flat=True)],
                                         ignore_conflicts=True)


def _set_password(user, password: str, *, link_to: str | None = None) -> dict[str, str]:
    """The new password written, every other session and assistant ended, the brake lifted; this device's new pair.

    `link_to`: the address a reset link went to. The password is written, and that address proven (the link came to
    that inbox), only while the account's row still holds it: never onto an account that moved to another address
    meanwhile. Access tokens carry a mark of the password they were made under (CHECK_REVOKE_TOKEN), so the old ones
    die here too."""
    user.set_password(password)
    if link_to is None:
        user.save(update_fields=['password'])
    else:
        fields, now = {'password': user.password}, timezone.now()
        if not user.email_proven_at:
            fields['email_proven_at'] = now
        if not get_user_model().objects.filter(pk=user.pk, email=link_to).update(**fields):
            raise Refused('link', 'dead')
        user.email_proven_at = user.email_proven_at or now
    end_sessions(user)
    # The assistants connected with the old password are disconnected too (C3 of the MCP review).
    from apps.oauth.services.tokens import end_all
    end_all(user)
    brake.clear(user)
    return tokens_for(user)


def _new_password(user, password: str) -> dict[str, str]:
    tokens = _set_password(user, password)
    mail.send(user, 'password_changed')
    return tokens


def change(user, *, password: object, new_password: object, ip: str) -> dict[str, str]:
    """A new password from the account page: the other devices are signed out, this one gets a fresh pair."""
    checked(user, password, ip)
    return _new_password(user, validated(new_password, user, 'new_password'))


def _accounts():
    return get_user_model().objects.filter(is_active=True, deleted_at=None)


def staff(user) -> bool:
    return bool(user.is_staff or user.is_superuser)


def request_reset(login: object) -> dict[str, str]:
    """Mail a reset link to the account a username or an address names. Answers {to}, the address masked, when the
    asker typed it; {} when they named a username."""
    login = str(login or '').strip()
    if not login:
        raise Refused('login', 'required')
    typed = '@' in login
    if typed:
        user = _accounts().filter(email__iexact=addresses.clean_address(login)).first()
        if user is None:
            fix = addresses.typed_fix(login)
            if fix and fix.lower() != login.lower():
                raise Refused('login', 'typo', 404, suggestion=fix)
            raise Refused('login', 'no_email', 404)
    else:
        user = _accounts().filter(username__iexact=login).first()
        if user is None:
            raise Refused('login', 'no_username', 404)
    if staff(user):
        # A staff account opens the admin: it is opened by its password alone, never by a letter to an inbox.
        raise Refused('login', 'staff', 403)
    if addresses.mail_blocked(user.email):
        raise Refused('login', 'unreachable', 409)
    # Past the cooldown, or past the inbox's letters of the day, the answer is the same as a sent one: the link already
    # sent still works.
    if mail.may_mail(user, 'reset') and mail.may_reach(user.email, 'reset'):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        link = f'{settings.SITE_URL}/reset#u={uid}&t={default_token_generator.make_token(user)}'
        if not mail.send(user, 'reset', link=link, hours=settings.PASSWORD_RESET_TIMEOUT // 3600):
            raise Refused('login', 'not_sent', 503)
    return {'to': addresses.mask(user.email)} if typed else {}


def _reset_user(uid: object, token: object, *, lock: bool = False):
    """The account a link names, if its token is good. `lock`: the row locked until the transaction ends, so the token
    is judged on the address the row holds now, and no new address lands before the new password does."""
    try:
        pk = int(force_str(urlsafe_base64_decode(str(uid or '')[:64])))
    except (TypeError, ValueError, OverflowError):
        return None
    rows = _accounts().filter(pk=pk)
    user = (rows.select_for_update() if lock else rows).first()
    if user is None or not default_token_generator.check_token(user, str(token or '')[:128]):
        return None
    return user


def check_reset(uid: object, token: object) -> dict[str, str]:
    """Is this link still good? Asked when its page opens, so a dead link says so before a password is typed."""
    user = _reset_user(uid, token)
    if user is None:
        raise Refused('link', 'dead')
    return {'username': user.username}


def confirm_reset(uid: object, token: object, password: object):
    """The new password from the link: set, the address proven, every other device signed out, this one signed in."""
    with transaction.atomic():
        user = _reset_user(uid, token, lock=True)
        if user is None:
            raise Refused('link', 'dead')
        tokens = _set_password(user, validated(password, user, 'password'), link_to=user.email)
    mail.send(user, 'password_changed')    # once the row is free: a letter can take seconds
    return user, tokens
