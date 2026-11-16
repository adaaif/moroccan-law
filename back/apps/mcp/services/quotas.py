"""The MCP server's shares (MC17), counted in the counters store across its workers, in Morocco's time.

Who calls decides the share (apps/mcp/services/origin.py):
- an account (a token from the site's sign-in): MCP_QUOTAS, C4 «tight», a day;
- an assistant's platform without an account (Claude, ChatGPT): MCP_PLATFORM_LIMITS, one share for all its users, an hour
  (a day let one user empty it for everyone until midnight);
- a ChatGPT user, known by the conversation subject ChatGPT sends: MCP_SUBJECT_LIMITS, an hour, inside the platform's
  share and counted first, so one user is held before the others are;
- a direct caller without an account: MCP_ADDRESS_LIMITS, its address's own, a day;
- a direct caller with a key (X-Api-Key) whose access includes the API: the access's own limits and day, shared with
  its other doors (apps/opendata/services/usage.py, door `mcp`), in place of its address's.

Every request to /mcp counts: the gate (apps/mcp/server.py) counts the requests that are not tool calls, each tool counts
its own call and says the limit itself. Past a share the caller is told what was reached and when it resets. When a
platform's share for the hour is half spent, the log says so and an `Alert` row is kept for the admin (no letter).
The open data stays closed (2 Nov 2026): the connector is no door to the whole corpus. What is kept: counts per origin
and day (Tally), and per connection for an account (Day): never an address, never a question (MC18)."""
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.mcp.models import Alert, Tally
from apps.oauth.models import Day, Grant
from config.caching import counters as cache

log = logging.getLogger(__name__)


class Limit(Exception):
    def __init__(self, message: str, retry: int = 60):
        super().__init__(message)
        self.retry = retry           # seconds until the share that was reached starts again


@dataclass(frozen=True)
class Caller:
    """kind: 'account', 'platform', 'address' or 'key'; key: the user's id, the platform's name, the address's bucket
    or the access's id; origin: the day's count it goes to; grant: the connection, for an account; subject: a ChatGPT
    user's key (a digest of the subject ChatGPT sends, never the subject itself), for a share of its own; holder: what a
    key opens, for a key."""
    kind: str
    key: str
    origin: str
    grant: int | None = None
    subject: str = ''
    holder: object = None


WHO = {'account': 'This account', 'platform': 'Everyone on this assistant', 'subject': 'This ChatGPT account',
       'address': 'This address', 'key': "This key's access"}


def subject_key(subject) -> str:
    """The key a ChatGPT user's share is counted under: a digest, so the store never holds ChatGPT's id."""
    if not isinstance(subject, str) or not subject or len(subject) > 200:
        return ''
    return hashlib.sha256(f'chatgpt|{subject}'.encode()).hexdigest()[:24]


def _limits(kind: str) -> dict:
    return {'account': settings.MCP_QUOTAS, 'platform': settings.MCP_PLATFORM_LIMITS, 'subject': settings.MCP_SUBJECT_LIMITS,
            'address': settings.MCP_ADDRESS_LIMITS}[kind]


def _shares(caller: Caller) -> list[tuple[str, str, dict]]:
    """(the counts' key, the kind it is said of, the share), a ChatGPT user's own before its platform's."""
    shares = [(f'mcp:subject:{caller.subject}', 'subject')] if caller.subject else []
    shares.append((f'mcp:{caller.kind}:{caller.key}', caller.kind))
    return [(base, kind, _limits(kind)) for base, kind in shares]


def _period(share: dict) -> str:
    return 'hour' if 'hour' in share else 'day'


def _window(period: str, now: datetime) -> tuple[str, int, int]:
    """The window's stamp, how long its count is kept, and the seconds until it ends."""
    if period == 'minute':
        return f'{now:%Y%m%d%H%M}', 120, 60 - now.second
    if period == 'hour':
        return f'{now:%Y%m%d%H}', 2 * 3600, 3600 - now.minute * 60 - now.second
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=now.tzinfo)
    return f'{now:%Y%m%d}', 26 * 3600, int((midnight - now).total_seconds())


def _count(key: str, by: int, timeout: int) -> int:
    cache.add(key, 0, timeout=timeout)
    try:
        return cache.incr(key, by)
    except ValueError:          # expired between add and incr
        cache.set(key, by, timeout=timeout)
        return by


def _resets(period: str, left: int) -> str:
    if period == 'hour':
        return f'{max(left // 60, 1)} min (on the hour, Morocco time)'
    hours, rest = divmod(left, 3600)
    return f'{hours} h {rest // 60} min (midnight, Morocco time)'


def _half(kind: str, origin: str, what: str, period: str, limit: int, before: int, after: int) -> None:
    """A platform's share for the hour half spent: said once in the log and kept as a row for the admin."""
    half = (limit + 1) // 2
    if kind != 'platform' or not limit or not before < half <= after:
        return
    log.warning('mcp: %s has used half its %s an %s (%s of %s)', origin, what, period, after, limit)
    Alert.objects.create(origin=origin[:60], share=what, period=period, limit=limit)


def charge(caller: Caller, *, bodies: bool = False) -> None:
    """Count one request; Limit when the caller is past its minute's or period's share, or past its article bodies for
    a tool that serves them (`bodies`). A share that refuses stops the count: a user held by its own share spends
    nothing of its platform's."""
    if caller.holder is not None:
        return _charge_key(caller.holder, bodies)
    now = timezone.localtime()
    minute, minute_keep, minute_left = _window('minute', now)
    for base, kind, q in _shares(caller):
        who, period = WHO[kind], _period(q)
        stamp, keep, left = _window(period, now)
        if _count(f'{base}:m:{minute}', 1, minute_keep) > q['minute']:
            raise Limit(f"{who} reached its {q['minute']} calls a minute to {settings.SITE_NAME}. Wait a minute.", minute_left)
        calls = _count(f'{base}:{period[0]}:{stamp}', 1, keep)
        if calls > q[period]:
            when = 'this hour' if period == 'hour' else 'today'
            raise Limit(f"{who} reached its {q[period]} calls {when} to {settings.SITE_NAME}. It resets in {_resets(period, left)}. "
                        f'The law stays readable on {settings.SITE_URL}.', left)
        _half(kind, caller.origin, 'calls', period, q[period], calls - 1, calls)
        if bodies and (cache.get(f'{base}:a:{stamp}') or 0) >= q['articles']:
            when = 'this hour' if period == 'hour' else 'today'
            raise Limit(f"{who} was given {q['articles']} articles {when}. It resets in {_resets(period, left)}. Search "
                        f'still answers; the articles stay readable on {settings.SITE_URL}.', left)


def _charge_key(holder, bodies: bool) -> None:
    """A key's call, on its access's limits (door `mcp`): a usage.Limit said in the words the tools give the model."""
    from apps.opendata.services import usage
    try:
        usage.charge(holder, 'mcp', bodies=bodies)
    except usage.Limit as limit:
        who, left = WHO['key'], limit.retry
        if limit.code == 'minute':
            raise Limit(f'{who} reached its {holder.minute} calls a minute to {settings.SITE_NAME}. Wait a minute.',
                        left) from None
        if limit.code == 'calls':
            raise Limit(f'{who} reached its {holder.calls} calls today to {settings.SITE_NAME}. It resets in '
                        f"{_resets('day', left)}. The law stays readable on {settings.SITE_URL}.", left) from None
        raise Limit(f'{who} was given {holder.articles} articles today. It resets in {_resets("day", left)}. Search '
                    f'still answers; the articles stay readable on {settings.SITE_URL}.', left) from None


def _tally(model, filters: dict, tool: str, articles: int) -> None:
    row, _ = model.objects.get_or_create(**filters)
    tools = dict(row.tools or {})
    tools[tool] = tools.get(tool, 0) + 1
    model.objects.filter(pk=row.pk).update(calls=F('calls') + 1, articles=F('articles') + articles, tools=tools)


def served(caller: Caller, tool: str, articles: int) -> None:
    """After a call: the article bodies counted against the shares (a key's on its access), the day's counts written (a
    few small queries)."""
    now = timezone.localtime()
    if caller.holder is not None:
        from apps.opendata.services import usage
        usage.spend(caller.holder, articles)
    elif articles:
        for base, kind, q in _shares(caller):
            period = _period(q)
            stamp, keep, _ = _window(period, now)
            given = _count(f'{base}:a:{stamp}', articles, keep)
            _half(kind, caller.origin, 'articles', period, q['articles'], given - articles, given)
    today = now.date()
    _tally(Tally, {'day': today, 'origin': caller.origin}, tool, articles)
    if caller.grant:
        _tally(Day, {'grant_id': caller.grant, 'day': today}, tool, articles)
        # When the connection was last used, written at most once a minute.
        if cache.add(f'mcp:used:{caller.grant}', 1, 60):
            Grant.objects.filter(pk=caller.grant).update(used_at=timezone.now())
