"""The six-digit code that proves an address (D3).

- Neither the address nor the code is stored: both are HMAC digests keyed on SECRET_KEY.
- A code lives EMAIL_CODE_TTL_MINUTES, is spent once and burns after EMAIL_CODE_MAX_TRIES tries. Asking again
  replaces the live one once the new one went; a new address ends every live code.
- An account gets EMAIL_CODES_PER_HOUR letters an hour, counted from the table itself (several workers share it); an
  inbox gets ACCOUNT_MAIL_PER_ADDRESS codes a day, whichever account asks (mail.may_reach).
- A letter the mail service did not take is no code: its row goes, and the request says so (`email.not_sent`). An address
  on a misspelt provider is sent nothing (`email.unreachable`): the person changes it from their account.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import EmailCode
from apps.accounts.services import addresses, mail
from apps.accounts.services.refusals import Refused

DIGITS = 6


def _digest(*parts: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), '\x1f'.join(parts).encode(), hashlib.sha256).hexdigest()


def email_digest(email: str) -> str:
    return _digest('email', email.strip().lower())


def _code_digest(email_hash: str, purpose: str, code: str) -> str:
    return _digest('code', email_hash, purpose, code)


def send_proof(user) -> None:
    """Mail a code to the account's address."""
    if user.email_proven_at:
        raise Refused('email', 'already_proven', 409)
    if addresses.mail_blocked(user.email):
        raise Refused('email', 'unreachable', 409)
    hour_ago = timezone.now() - timedelta(hours=1)
    if EmailCode.objects.filter(user=user, purpose=EmailCode.Purpose.PROVE, created_at__gte=hour_ago).count() \
            >= settings.EMAIL_CODES_PER_HOUR:
        raise Refused('email', 'too_many_codes', 429)
    if not mail.may_reach(user.email, 'code'):
        raise Refused('email', 'too_many_today', 429)
    email_hash = email_digest(user.email)
    code = f'{secrets.randbelow(10 ** DIGITS):0{DIGITS}d}'
    row = EmailCode.objects.create(email_digest=email_hash, purpose=EmailCode.Purpose.PROVE, user=user,
                                   code_digest=_code_digest(email_hash, EmailCode.Purpose.PROVE, code),
                                   expires_at=timezone.now() + timedelta(minutes=settings.EMAIL_CODE_TTL_MINUTES))
    if not mail.send(user, 'code', code=code, minutes=settings.EMAIL_CODE_TTL_MINUTES):
        # The code already sent still works.
        row.delete()
        raise Refused('email', 'not_sent', 503)
    EmailCode.objects.filter(email_digest=email_hash, purpose=EmailCode.Purpose.PROVE, used_at=None).exclude(
        pk=row.pk).update(expires_at=timezone.now())


def prove(user, code: object) -> None:
    """The live code opens the address it was sent to, while the account still holds that address.

    The address is read from the account's row, not from the request's copy of the account: a new address saved by
    another request a moment earlier must not be the one proven. A try is counted before the code is compared, in one
    conditional update, so guesses sent in parallel each spend a try. A wrong try counts though the request fails."""
    User = get_user_model()
    current = User.objects.filter(pk=user.pk).values_list('email', 'email_proven_at').first()
    if current is None:
        raise Refused('code', 'invalid')
    email, proven_at = current
    if proven_at:
        user.email, user.email_proven_at = email, proven_at
        return
    digits = ''.join(ch for ch in str(code or '')[:64] if ch.isdigit())
    email_hash = email_digest(email)
    row = (EmailCode.objects.filter(email_digest=email_hash, purpose=EmailCode.Purpose.PROVE, user=user,
                                    used_at=None, expires_at__gt=timezone.now())
           .order_by('-created_at').first())
    if row is None or not EmailCode.objects.filter(pk=row.pk, tries__lt=settings.EMAIL_CODE_MAX_TRIES).update(
            tries=F('tries') + 1):
        raise Refused('code', 'invalid')
    if len(digits) != DIGITS or not hmac.compare_digest(
            row.code_digest, _code_digest(email_hash, EmailCode.Purpose.PROVE, digits)):
        raise Refused('code', 'invalid')
    now = timezone.now()
    with transaction.atomic():
        list(User.objects.select_for_update().filter(pk=user.pk).values_list('pk', flat=True))
        # Of two requests holding the same row, only one spends it; and the address is proven only while the row
        # still holds the one the code went to.
        proven = (EmailCode.objects.filter(pk=row.pk, used_at=None).update(used_at=now)
                  and User.objects.filter(pk=user.pk, email=email, email_proven_at=None).update(email_proven_at=now))
    if not proven:
        raise Refused('code', 'invalid')
    user.email, user.email_proven_at = email, now
