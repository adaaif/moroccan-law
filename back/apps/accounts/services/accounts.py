"""Accounts: sign-up, sign-in lookup, profile, sessions.

Refusals are `AccountError` with (field, code) pairs; the clients translate
the codes, the server sends no sentences.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.services import addresses


class AccountError(Exception):
    """(field, code) pairs, or (field, code, extra) when the sentence needs data (a suggested address)."""

    def __init__(self, errors: list[tuple]):
        super().__init__(errors)
        self.errors = errors


def address_error(verdict: addresses.Verdict) -> tuple:
    return ('email', verdict.code, {'suggestion': verdict.suggestion} if verdict.suggestion else {})


def normalize_email(email: str) -> str:
    return email.strip().lower()


def name_held(name: str) -> bool:
    """Whether the discussion's fixed patterns find something in a name: a phone number, an address, a link, an insult.
    A name stands beside everything its holder writes, so it may hold nothing a post may not. Asked when a name is
    chosen; an account that already holds one keeps it (the discussion shows the next name in its place)."""
    from apps.discussion.services.holds import in_name
    return bool(name) and bool(in_name(name))


def find_login_user(login: str):
    """The account a sign-in names: an address when it holds «@», else a username."""
    login = login.strip()
    lookup = 'email__iexact' if '@' in login else 'username__iexact'
    return get_user_model().objects.filter(**{lookup: login}).first()


def register(*, username: str, email: str, password: str,
             display_name: str = '', preferred_language: str = 'ar', email_confirmed: bool = False):
    """A new account. The address is checked first (a misspelt provider is answered with its fix until the person keeps
    theirs: `email_confirmed`; a throwaway inbox is refused: addresses.py)."""
    User = get_user_model()
    username = username.strip()
    verdict = addresses.check(email, confirmed=email_confirmed)
    email = normalize_email(verdict.email)
    display_name = display_name.strip()

    errors = []
    if name_held(username):
        errors.append(('username', 'held'))
    elif User.objects.filter(username__iexact=username).exists():
        errors.append(('username', 'username_taken'))
    if name_held(display_name):
        errors.append(('display_name', 'held'))
    if verdict.code:
        errors.append(address_error(verdict))
    elif User.objects.filter(email__iexact=email).exists():
        errors.append(('email', 'email_taken'))
    try:
        validate_password(password, user=User(username=username, email=email,
                                              display_name=display_name))
    except ValidationError as exc:
        # The first broken rule only: one thing to fix at a time.
        errors.append(('password', exc.error_list[0].code))
    if errors:
        raise AccountError(errors)

    try:
        with transaction.atomic():
            return User.objects.create_user(
                username=username,
                email=email,
                password=password,
                display_name=display_name,
                preferred_language=preferred_language,
            )
    except IntegrityError as exc:
        # Two sign-ups with one name or address at once: the second is told as if it came after.
        raise AccountError([('username', 'username_taken')] if User.objects.filter(username__iexact=username).exists()
                           else [('email', 'email_taken')]) from exc


def change_email(user, *, email: str, confirmed: bool = False) -> bool:
    """A new address for the account (a typo at sign-up was for life): checked as at sign-up, unproven until the code
    sent to it comes back. The old address, if it was proven, is told where the account went. The caller has asked for
    the password. True when the code went.

    The Google binding goes with the old address, and so do the assistants' connections. Google opens an account by the
    address it holds; once the address is another, the account may later be taken over by that address's real owner
    («email in use» leads them in, a reset gives them a password), and a binding made under the old address would
    still open it for whoever made it. A person who changes their address signs in with their password, or binds Google
    again under the new one."""
    from apps.accounts.models import EmailCode
    from apps.accounts.services import codes, mail
    from apps.accounts.services.refusals import Refused
    from apps.oauth.services.tokens import end_all

    User = get_user_model()
    verdict = addresses.check(email, confirmed=confirmed)
    if verdict.code:
        raise AccountError([address_error(verdict)])
    new = normalize_email(verdict.email)
    try:
        with transaction.atomic():
            # The row locked: a code or a reset link being proven at this moment waits, then finds the new address
            # (codes.prove, passwords.confirm_reset).
            locked = User.objects.select_for_update().get(pk=user.pk)
            if new == locked.email.lower():
                return False
            if User.objects.filter(email__iexact=new).exclude(pk=user.pk).exists():
                raise AccountError([('email', 'email_taken')])
            old, proven_at = locked.email, locked.email_proven_at
            User.objects.filter(pk=user.pk).update(email=new, email_proven_at=None, google_sub=None)
            # Every live code dies with the address: the next one goes to the new address.
            now = timezone.now()
            EmailCode.objects.filter(user=user, used_at=None, expires_at__gt=now).update(expires_at=now)
    except IntegrityError as exc:
        raise AccountError([('email', 'email_taken')]) from exc
    user.email, user.email_proven_at, user.google_sub = new, None, None
    end_all(user)
    if proven_at:
        mail.send(user, 'email_changed', to=old, new=new)
    try:
        codes.send_proof(user)
    except Refused:
        return False
    return True


def tokens_for(user) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


def logout(refresh: str) -> None:
    """End this device's session: its refresh token can no longer be used."""
    try:
        RefreshToken(refresh).blacklist()
    except TokenError as exc:
        raise AccountError([('refresh', 'token_invalid')]) from exc


def update_profile(user, *, display_name: str | None = None,
                   preferred_language: str | None = None, address_form: str | None = None,
                   email_notices: bool | None = None):
    """The profile's fields that were sent. A new name the patterns find something in is refused (`display_name.held`);
    the name the account already holds is kept as it is."""
    if display_name is not None and display_name.strip() != user.display_name and name_held(display_name.strip()):
        raise AccountError([('display_name', 'held')])
    fields = []
    if address_form is not None:
        user.address_form = address_form
        fields.append('address_form')
    if email_notices is not None:
        user.email_notices = email_notices
        fields.append('email_notices')
    if display_name is not None:
        user.display_name = display_name.strip()
        fields.append('display_name')
    if preferred_language is not None:
        user.preferred_language = preferred_language
        fields.append('preferred_language')
    if fields:
        user.save(update_fields=fields)
    return user
