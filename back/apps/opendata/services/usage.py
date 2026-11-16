"""What an access uses: its three limits and its counts, per access and Morocco's day.

The limits belong to the access, not to the key: two keys of one access (one replacing the other) share them.
- requests a minute (`Holder.minute`), a calendar minute;
- calls a day (`Holder.calls`);
- articles a day (`Holder.articles`): the law's articles its answers gave.

A door that a key opens calls, in this order:
1. `keys.holder(request)` (or `keys.read(key)`): the holder, None without a key, `keys.Refused` for a key that opens
   nothing (answered 401 (`key`, its code)).
2. `charge(holder, door)` before the work: one call counted on the access's minute and day, or `Limit` past a limit
   (answered 429 (`key`, `limit.code`) with `Retry-After: limit.retry`); nothing is counted then.
3. `spend(holder, n)` after the work, with the articles the answer gave (when the count is known only then).
4. `headers(holder)` on the answer: `RateLimit-Policy` and `RateLimit`, as the IETF draft
   draft-ietf-httpapi-ratelimit-headers writes them.

A call refused for a limit is counted too, apart, by limit (`minute`, `calls`, `articles`): here when `charge` refuses,
and by the day of reading when it refuses a key past its articles (`refuse`). The desk says who reached a limit today
from these counts (`limited`).

Counted in the `counters` store, never a database row a call: the day's totals are copied into `AccessDay` at most
once a minute an access (an upsert of the totals, by whichever worker counts the access's next call or refusal), and
the day before is copied once more on the next day's first call. Nothing is kept of what was asked, nor of an
address."""
from datetime import datetime, timedelta

from django.db import IntegrityError
from django.utils import timezone

from apps.opendata.models import AccessDay, ApiKey
from config.caching import counters

# The doors a key is counted on: the site's own API and pages, the assistants' server, the versioned API's reads, a
# download of the edition. An unknown door is a mistake in the code, refused at once.
DOORS = ('site', 'mcp', 'v1.search', 'v1.text', 'v1.articles', 'v1.references', 'v1.bulletin', 'v1.changes', 'open')
# The doors whose answers are the law's words: refused once the day's articles are spent. The others (a search, a list,
# the references) still answer. The site's own API meets its articles in the day of reading
# (apps/corpus/services/reading.py), the assistants' server says per tool (`bodies`).
BODIES = frozenset({'v1.text', 'v1.articles'})
# A day's counts outlive the day, so that the next day's first call can still copy its last minute into AccessDay.
DAY_KEPT = 3 * 86400
MINUTE_KEPT = 120
# The limits a call may be refused for, counted by name.
LIMITS = ('minute', 'calls', 'articles')


class Limit(Exception):
    """A limit reached: `code` is `minute`, `calls` or `articles`; `retry` the seconds until it starts again."""

    def __init__(self, code: str, retry: int):
        super().__init__(code)
        self.code, self.retry = code, max(int(retry), 1)


def _day(access: int, day) -> str:
    return f'usage:{access}:{day:%Y%m%d}'


def _minute(access: int, now: datetime) -> str:
    return f'usage:{access}:m:{now:%Y%m%d%H%M}'


def _to_midnight(now: datetime) -> int:
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=now.tzinfo)
    return int((midnight - now).total_seconds())


def _add(key: str, n: int, timeout: int) -> None:
    counters.add(key, 0, timeout=timeout)
    try:
        counters.incr(key, n)
    except ValueError:          # gone between add and incr
        counters.set(key, n, timeout=timeout)


def charge(holder, door: str, articles: int = 0, *, bodies: bool | None = None) -> None:
    """Count one call of `holder`'s access on `door` (one of DOORS), and `articles` when the call knows already what it
    gives. `Limit` past the access's minute or its calls today, or, for a call that gives the law's words (`bodies`:
    by default the doors of BODIES), once its articles today reached their limit; nothing is counted then. The call
    that reaches the articles' limit is served whole: a limit is past when it is reached, before a call."""
    if door not in DOORS:
        raise ValueError(f'no such door: {door!r}')
    bodies = door in BODIES if bodies is None else bodies
    now = timezone.localtime()
    day, minute = _day(holder.access, now.date()), _minute(holder.access, now)
    counts = counters.get_many([minute, f'{day}:calls', f'{day}:articles'])
    if (counts.get(minute) or 0) >= holder.minute:
        raise _refused(holder, now, Limit('minute', 60 - now.second))
    if (counts.get(f'{day}:calls') or 0) >= holder.calls:
        raise _refused(holder, now, Limit('calls', _to_midnight(now)))
    if bodies and (counts.get(f'{day}:articles') or 0) >= holder.articles:
        raise _refused(holder, now, Limit('articles', _to_midnight(now)))
    _add(minute, 1, MINUTE_KEPT)
    _add(f'{day}:calls', 1, DAY_KEPT)
    _add(f'{day}:door:{door}', 1, DAY_KEPT)
    if articles > 0:
        _add(f'{day}:articles', articles, DAY_KEPT)
    _written(holder, now)


def _refused(holder, now: datetime, limit: Limit) -> Limit:
    """Count a call refused for `limit` on the access's day, and copy the day as a call would; the limit is given
    back for the caller to raise."""
    _add(f'{_day(holder.access, now.date())}:limit:{limit.code}', 1, DAY_KEPT)
    _fold_now(holder.access, now)
    return limit


def refuse(holder, code: str) -> None:
    """Count a call refused for the limit `code` (one of LIMITS) by a door that holds the limit itself: the day of
    reading, past a key's articles (apps/corpus/services/reading.py)."""
    if code not in LIMITS:
        raise ValueError(f'no such limit: {code!r}')
    _refused(holder, timezone.localtime(), Limit(code, 1))


def spend(holder, articles: int) -> None:
    """Add the articles an answer gave to a call already charged."""
    if articles > 0:
        _add(f'{_day(holder.access, timezone.localdate())}:articles', articles, DAY_KEPT)


def reached(holder) -> bool:
    """Whether the access's articles today reached their limit (the day of reading asks before it gives any)."""
    return (counters.get(f'{_day(holder.access, timezone.localdate())}:articles') or 0) >= holder.articles


def headers(holder) -> dict:
    """The answer's `RateLimit-Policy` (the access's requests a minute and calls a day) and `RateLimit` (what is left of
    each and the seconds until it starts again)."""
    now = timezone.localtime()
    day, minute = _day(holder.access, now.date()), _minute(holder.access, now)
    counts = counters.get_many([minute, f'{day}:calls'])
    minute_left = max(holder.minute - (counts.get(minute) or 0), 0)
    day_left = max(holder.calls - (counts.get(f'{day}:calls') or 0), 0)
    return {'RateLimit-Policy': f'"minute";q={holder.minute};w=60, "day";q={holder.calls};w=86400',
            'RateLimit': f'"minute";r={minute_left};t={max(60 - now.second, 1)}, '
                         f'"day";r={day_left};t={_to_midnight(now)}'}


_PARTS = ('calls', 'articles', *(f'door:{x}' for x in DOORS), *(f'limit:{x}' for x in LIMITS))


def _counted(access: int, days: list) -> dict:
    """{day: (calls, articles, {door: calls}, {limit: refused})} from the counters, for the days they still hold."""
    counts = counters.get_many([f'{_day(access, d)}:{what}' for d in days for what in _PARTS])
    out = {}
    for d in days:
        base = _day(access, d)
        calls, articles = counts.get(f'{base}:calls') or 0, counts.get(f'{base}:articles') or 0
        limits = {x: n for x in LIMITS if (n := counts.get(f'{base}:limit:{x}'))}
        if calls or articles or limits:
            out[d] = (calls, articles, {x: n for x in DOORS if (n := counts.get(f'{base}:door:{x}'))}, limits)
    return out


def live(access: int, days: list) -> dict:
    """{day: {'calls', 'articles', 'doors', 'limits'}} as the counters hold them now, for those of `days` they still
    hold (today's, and the days before for DAY_KEPT): one call."""
    return {d: {'calls': c, 'articles': a, 'doors': doors, 'limits': limits}
            for d, (c, a, doors, limits) in _counted(access, days).items()}


def fold(access: int, days: list) -> None:
    """Copy the counters' totals of `days` into AccessDay: one upsert. The totals, not what was added since the last
    copy, so any worker may copy and a copy said twice changes nothing."""
    rows = [AccessDay(access_id=access, day=d, calls=calls, articles=articles, doors=doors, limits=limits)
            for d, (calls, articles, doors, limits) in _counted(access, days).items()]
    if not rows:
        return
    try:
        AccessDay.objects.bulk_create(rows, update_conflicts=True, unique_fields=['access', 'day'],
                                      update_fields=['calls', 'articles', 'doors', 'limits'])
    except IntegrityError:
        # The access's row is gone (its account was removed outright) while a key of it is still remembered for its
        # last minute: there is nothing left to count for, and the call is not failed for it.
        pass


def _written(holder, now: datetime) -> None:
    """The writes a call may cause, each at most so often: the key's day of use once a day, the access's day into
    AccessDay once a minute of the clock (and the day before once, on a day's first copy)."""
    today = now.date()
    if counters.add(f'usage:key:{holder.key}:used:{today:%Y%m%d}', 1, timeout=DAY_KEPT):
        ApiKey.objects.filter(pk=holder.key).exclude(last_used_on=today).update(last_used_on=today)
    _fold_now(holder.access, now)


def _fold_now(access: int, now: datetime) -> None:
    """The access's day copied into AccessDay, once a minute of the clock at most (and the day before once, on a
    day's first copy)."""
    today = now.date()
    if counters.add(f'usage:{access}:folded:{now:%Y%m%d%H%M}', 1, timeout=MINUTE_KEPT):
        days = [today]
        if counters.add(f'usage:{access}:closed:{today - timedelta(days=1):%Y%m%d}', 1, timeout=DAY_KEPT):
            days.append(today - timedelta(days=1))
        fold(access, days)


def limited(accesses: list[int]) -> dict:
    """{access: {'minute', 'calls', 'articles'}} for those of `accesses` refused for a limit today: the calls refused
    by limit, read from the counters in one call, so it is true to the minute."""
    base = {a: _day(a, timezone.localdate()) for a in accesses}
    counts = counters.get_many([f'{b}:limit:{x}' for b in base.values() for x in LIMITS])
    out = {}
    for a, b in base.items():
        found = {x: counts.get(f'{b}:limit:{x}') or 0 for x in LIMITS}
        if any(found.values()):
            out[a] = found
    return out


def today(access: int) -> dict:
    """The access's calls and articles today, as counted now."""
    calls, articles, *_ = _counted(access, [timezone.localdate()]).get(timezone.localdate(), (0, 0))
    return {'calls': calls, 'articles': articles}


def days(access: int, n: int = 30) -> list[dict]:
    """The access's last `n` days that saw use, oldest first: {'day': 'YYYY-MM-DD', 'calls', 'articles'}. AccessDay's
    rows, with the counters' own figures for the days they still hold (today's and the last minute of the days
    before, which may not be copied yet). One query."""
    last = timezone.localdate()
    first = last - timedelta(days=n - 1)
    held = {r['day']: (r['calls'], r['articles']) for r in AccessDay.objects.filter(
        access_id=access, day__gte=first, day__lte=last).values('day', 'calls', 'articles')}
    live = _counted(access, [last - timedelta(days=k) for k in range(min(n, DAY_KEPT // 86400))])
    out = []
    for d in sorted(set(held) | set(live)):
        calls, articles = held.get(d, (0, 0))
        if d in live:
            calls, articles = max(calls, live[d][0]), max(articles, live[d][1])
        if calls or articles:
            out.append({'day': d.isoformat(), 'calls': calls, 'articles': articles})
    return out
