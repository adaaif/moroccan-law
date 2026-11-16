"""A key, from the request that carries it to the access it belongs to, and the keys an account makes for its access.

`holder(request)` is the one way in: every door that reads a key (the site's own API through the key's middleware,
the day of reading, the versioned API, the download, the assistants' server through `read`) asks it, so a key means
the same thing everywhere.

A key is looked up once a request (remembered on the request) and what was found is kept a minute in the default
cache under the key's hash: a busy key costs no query for itself, and a wrong key that has a key's shape cannot be used
to hammer the database either (its refusal is kept the same minute). A key without a key's shape or checksum is
refused before any lookup. Ending a key forgets what was kept of it, so it stops at once (`end`, `forget`).

Making a key and ending one leave an event (services/log.py): by its holder, or by the staff for a key that leaked
(`end_by_staff`, with a letter telling the holder which key, and to make a new one)."""
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused as Refusal
from apps.opendata.models import Access, ApiKey, Event, hash_key, well_formed
from apps.opendata.services import log

HEADER = 'X-Api-Key'
KEPT_SECONDS = 60
NAME_MOST = 60
_MEMO = '_access_key_holder'


@dataclass(frozen=True)
class Holder:
    """What a live key opens: its access, the account, what was granted, and the access's three limits (requests a
    minute, calls a day, articles a day)."""
    key: int
    access: int
    user: int
    api: bool
    data: bool
    minute: int
    calls: int
    articles: int


class Refused(Exception):
    """A key that opens nothing: `code` is `invalid` (no such key), `ended` (the key or its access was ended) or
    `expired` (the access's end date passed). Every door answers it 401 (`key`, `code`)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def sent(request) -> str:
    """The key a request carries, or ''. Only the header is read, never the query string: an address ends up in
    logs."""
    return (request.headers.get(HEADER) or '').strip()


def _kept(key_hash: str) -> str:
    return f'apikey:1:{key_hash}'


def _look_up(key_hash: str) -> tuple[str, Holder | None, object]:
    """('', the holder, the access's end date) for a live key; (the refusal's code, None, None) otherwise."""
    row = ApiKey.objects.select_related('access').filter(key_hash=key_hash).first()
    if row is None:
        return 'invalid', None, None
    access = row.access
    if row.ended_at or access.state != Access.State.LIVE:
        return 'ended', None, None
    return '', Holder(key=row.pk, access=access.pk, user=access.user_id, api=access.api, data=access.data,
                      **access.limits()), access.ends_on


def read(key: str) -> Holder:
    """The holder of `key`, or `Refused`. Kept KEPT_SECONDS under the key's hash, refusals included; the end date is
    compared with today's at each read, so an access stops at its date's midnight whatever was kept."""
    if not well_formed(key):
        raise Refused('invalid')
    key_hash = hash_key(key)
    found = cache.get(_kept(key_hash))
    if found is None:
        found = _look_up(key_hash)
        cache.set(_kept(key_hash), found, KEPT_SECONDS)
    code, held, ends_on = found
    if code:
        raise Refused(code)
    if ends_on < timezone.localdate():
        raise Refused('expired')
    return held


def holder(request) -> Holder | None:
    """Who a request's key belongs to; None when it carries no key; `Refused` when its key opens nothing. Resolved once
    a request: a second door that asks (the day of reading after the site's limits) is answered from the request."""
    raw = getattr(request, '_request', request)
    if not hasattr(raw, _MEMO):
        key = sent(raw)
        try:
            setattr(raw, _MEMO, read(key) if key else None)
        except Refused as refused:
            setattr(raw, _MEMO, refused)
    found = getattr(raw, _MEMO)
    if isinstance(found, Refused):
        raise Refused(found.code)
    return found


def issue(access: Access, name: str = '') -> tuple[ApiKey, str]:
    return ApiKey.issue(access, name)


def end(key: ApiKey, by=None) -> None:
    """End a key: it opens nothing from now on, on every door and every worker (what was kept of it is forgotten). `by`
    is who ended it, kept in its event: its holder, or a superuser."""
    if key.ended_at is None:
        key.ended_at = timezone.now()
        key.save(update_fields=['ended_at'])
        log.note(Event.Act.KEY_ENDED, by=by, access=key.access_id, key=key.pk)
    forget(key.key_hash)


def end_by_staff(key: ApiKey, by) -> ApiKey:
    """A superuser ends a key that leaked: the access stays, and a letter tells its holder which key stopped (its name
    and first characters) and to make a new one."""
    from apps.accounts.services import mail
    from apps.opendata.services import access as accesses

    if not getattr(by, 'is_superuser', False):
        raise Refusal('by', 'not_superuser', 403)
    with transaction.atomic():
        row = ApiKey.objects.select_for_update(of=('self',)).select_related('access__user').filter(pk=key.pk).first()
        if row is None or row.ended_at is not None:
            raise Refusal('key', 'ended', 409)
        end(row, by=by)
    access, user = row.access, row.access.user
    name = row.name or mail.ACCESS_WORDS[mail.language(user)]['unnamed']
    accesses.write_to(user, 'access_key_ended', api=access.api, data=access.data, key=name, prefix=f'{row.prefix}…')
    key.ended_at = row.ended_at
    return row


def forget(key_hash: str) -> None:
    """Drop what is kept of a key between requests, so an ended key or access stops at once. Once now, and once more
    when the transaction that ended it commits: a request that read the key's row before the commit could have kept it
    alive again in between."""
    cache.delete(_kept(key_hash))
    transaction.on_commit(lambda: cache.delete(_kept(key_hash)))


# ── An account's own keys (GET/POST /api/access/keys/, DELETE /api/access/keys/<id>/) ──────────────────────────

def _usable(user) -> Access:
    access = Access.live_of(user)
    if access is None:
        raise Refusal('access', 'none', 403)
    return access


def _row(key: ApiKey) -> dict:
    return {'id': key.pk, 'name': key.name, 'prefix': key.prefix, 'created_at': key.created_at,
            'last_used_on': key.last_used_on}


def shown(user) -> dict:
    """What an account's page shows of its access's keys and their use: the live keys (never a key itself), the three
    limits, today's calls and articles, and the last 30 days that saw use, oldest first."""
    from apps.opendata.services import usage

    access = _usable(user)
    live = access.keys.filter(ended_at__isnull=True).order_by('created_at', 'pk')
    return {'keys': [_row(k) for k in live], 'limits': access.limits(), 'today': usage.today(access.pk),
            'days': usage.days(access.pk)}


def make(user, name='') -> dict:
    """A new key of the account's access, the key itself in the answer: the only time it is given. At most
    ACCESS_KEYS live keys an access, so one can replace the other without a break."""
    if not isinstance(name, str):
        raise Refusal('name', 'invalid')
    name = name.strip()
    if len(name) > NAME_MOST:
        raise Refusal('name', 'too_long')
    with transaction.atomic():
        # Two requests at once could each count one key and make a third: the access's row is held while counting.
        access = Access.objects.select_for_update().get(pk=_usable(user).pk)
        if access.keys.filter(ended_at__isnull=True).count() >= settings.ACCESS_KEYS:
            raise Refusal('keys', 'full', 409)
        row, key = issue(access, name)
        log.note(Event.Act.KEY_MADE, by=user, access=access, key=row.pk)
    return {'key': key, 'id': row.pk, 'name': row.name, 'prefix': row.prefix}


def drop(user, pk) -> None:
    """End one of the account's live keys."""
    access = _usable(user)
    row = access.keys.filter(pk=pk, ended_at__isnull=True).first()
    if row is None:
        raise Refusal('key', 'not_found', 404)
    end(row, by=user)
