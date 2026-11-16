"""What the access desk reads (/api/access/desk/, for a superuser): what waits, every request and access, their use,
the editions and who took them, the log of every act. The desk's acts are the services' own (services/requests.py,
access.py, keys.py); this module only reads.

Each read costs a fixed number of queries whatever the rows hold (the tests hold each to a ceiling). Lists are read a
page at a time by a cursor, the row's time and id (its waiting time for a queue, its creation time otherwise; the
event's for the log), never an offset: a page stays the same however many rows arrive before it.

Days are Morocco's. The day an answer is due counts working days, Monday to Friday; public holidays are not counted
out (services/requests.py `due_on`)."""
import base64
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, F, Max, OuterRef, Q, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Ban
from apps.opendata.models import Access, AccessDay, ApiKey, Download, Event, Request
from apps.opendata.services import access as accesses
from apps.opendata.services import editions, gate, usage
from apps.opendata.services import requests as asked

PAGE = 50                   # rows a page of a list
SHOWN = 50                  # rows of each list on the overview (the lists have the rest)
ENDING_DAYS = 30            # an access «ending» ends within this many days
SPARK_DAYS = 30             # an access row's days of calls
SHEET_DAYS = 30             # an access sheet's days that saw use
DOWNLOADS = 50              # an access sheet's newest downloads
EDITION_DOWNLOADS = 20      # an edition's newest downloads
QUESTIONS = 3               # the lines a superuser asked last, offered again
EARLIER = 20                # an account's earlier requests on a request's sheet
USE_MOST_DAYS = 366         # the longest window the use reads
BUSIEST = 5

REQUEST_STATES = ('waiting', 'more', 'accepted', 'declined', 'all')
ACCESS_STATES = ('live', 'ending', 'ended', 'unused', 'all')


# ── The cursor ─────────────────────────────────────────────────────────────────────────────────────────────────────

def _cursor(at: datetime, pk: int) -> str:
    return base64.urlsafe_b64encode(f'{at.isoformat()}|{pk}'.encode()).decode().rstrip('=')


def _read_cursor(value) -> tuple[datetime, int] | None:
    """The time and id a cursor names; None for none; 400 (`cursor`, `invalid`) for anything else."""
    if value in (None, ''):
        return None
    try:
        raw = base64.urlsafe_b64decode(str(value) + '=' * (-len(str(value)) % 4)).decode()
        at, pk = raw.split('|')
        at, pk = datetime.fromisoformat(at), int(pk)
    except (ValueError, UnicodeDecodeError):
        raise Refused('cursor', 'invalid') from None
    if timezone.is_naive(at) or not 0 < pk < 2**63:
        raise Refused('cursor', 'invalid')
    return at, pk


def _page(rows, cursor, field: str, newest_first: bool) -> tuple[list, str | None]:
    """One page of `rows` ordered by `field` and id, after `cursor`: the rows and the next page's cursor."""
    found = _read_cursor(cursor)
    sign = '-' if newest_first else ''
    rows = rows.order_by(f'{sign}{field}', f'{sign}pk')
    if found:
        at, pk = found
        past = 'lt' if newest_first else 'gt'
        rows = rows.filter(Q(**{f'{field}__{past}': at}) | Q(**{field: at, f'pk__{past}': pk}))
    got = list(rows[:PAGE + 1])
    more = len(got) > PAGE
    got = got[:PAGE]
    return got, _cursor(getattr(got[-1], field), got[-1].pk) if more else None


def _words(q) -> str:
    if q is None:
        return ''
    if not isinstance(q, str):
        raise Refused('q', 'invalid')
    return ' '.join(q.split())[:100]


# ── The rows the desk acts on ──────────────────────────────────────────────────────────────────────────────────────

def the_request(pk: int) -> Request:
    r = Request.objects.select_related('user', 'change_of').filter(pk=pk).first()
    if r is None:
        raise Refused('request', 'not_found', 404)
    return r


def the_access(pk: int) -> Access:
    a = Access.objects.filter(pk=pk).first()
    if a is None:
        raise Refused('access', 'not_found', 404)
    return a


def the_key(pk: int) -> ApiKey:
    k = ApiKey.objects.filter(pk=pk).first()
    if k is None:
        raise Refused('key', 'not_found', 404)
    return k


# ── Rows ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def request_row(r: Request, today: date) -> dict:
    """A request as the desk's lists show it. `r.user` is read with it."""
    due = asked.due_on(r)
    return {'id': r.pk, 'name': r.name, 'kind': r.kind, 'username': r.user.username, 'wants_api': r.wants_api,
            'wants_data': r.wants_data, 'volume': r.volume, 'commercial': r.commercial, 'state': r.state,
            'created_at': r.created_at, 'waiting_since': r.waiting_since, 'due_on': due,
            'days_left': asked.days_left(due, today),
            'answered': r.state == Request.State.WAITING and bool(r.answer), 'change_of': r.change_of_id,
            'wanted_size': r.wanted_size, 'reason': r.reason}


def _accesses():
    """Accesses with their account and request, their last day of use and their live keys, in their own query."""
    return (Access.objects.select_related('user', 'request')
            .annotate(last_used=Max('keys__last_used_on'),
                      live_keys=Count('keys', filter=Q(keys__ended_at=None), distinct=True)))


def _sparks(ids: list[int], today: date) -> dict:
    """{access: (its calls a day over SPARK_DAYS days, oldest first, today last; calls; articles)}: one query."""
    first = today - timedelta(days=SPARK_DAYS - 1)
    out = {}
    for access, day, calls, articles in AccessDay.objects.filter(
            access_id__in=ids, day__gte=first, day__lte=today).values_list('access_id', 'day', 'calls', 'articles'):
        spark, c, a = out.setdefault(access, ([0] * SPARK_DAYS, 0, 0))
        spark[(day - first).days] = calls
        out[access] = (spark, c + calls, a + articles)
    return out


def access_row(a: Access, sparks: dict) -> dict:
    """An access as the desk's lists show it, read by `_accesses` with its days from `_sparks`."""
    spark, calls, articles = sparks.get(a.pk, ([0] * SPARK_DAYS, 0, 0))
    usable = a.usable
    return {'id': a.pk, 'name': a.request.name, 'kind': a.request.kind, 'username': a.user.username, 'api': a.api,
            'data': a.data, 'size': a.size, 'limits': a.limits(), 'ends_on': a.ends_on,
            'state': Access.State.LIVE if usable else Access.State.ENDED,
            'ended_reason': a.ended_reason or ('' if usable else Access.Ended.EXPIRED), 'last_used_on': a.last_used,
            'keys': a.live_keys if usable else 0, 'calls_30': calls, 'articles_30': articles, 'spark': spark}


def _access_rows(rows: list[Access], today: date) -> list[dict]:
    sparks = _sparks([a.pk for a in rows], today) if rows else {}
    return [access_row(a, sparks) for a in rows]


def event_row(e: Event) -> dict:
    """An act as the log and the sheets show it, read with its author, its request and its access's request."""
    asker = e.request if e.request_id else (e.access.request if e.access_id else None)
    return {'at': e.at, 'by': e.by.username if e.by_id else None, 'act': e.act, 'request': e.request_id,
            'access': e.access_id, 'name': asker.name if asker else '', 'details': e.details}


def _events():
    return Event.objects.select_related('by', 'request', 'access__request')


def _account(user_id: int) -> dict:
    """The account behind a request or an access, with its standing in the discussion: its published posts and
    comments, those a reviewer removed, and whether it is paused now. One query."""
    now = timezone.now()
    paused = Ban.objects.filter(user=OuterRef('pk'), ended_at=None).filter(Q(until=None) | Q(until__gt=now))
    published = Q(contributions__held_at=None, contributions__hidden_at=None, contributions__removed_at=None,
                  contributions__deleted_at=None, contributions__erased_at=None)
    u = (get_user_model().objects.filter(pk=user_id)
         .annotate(posts=Count('contributions', filter=published),
                   removed=Count('contributions', filter=Q(contributions__removed_at__isnull=False)),
                   paused=Exists(paused))
         .get())
    return {'id': u.pk, 'username': u.username, 'display_name': u.display_name, 'email': u.email,
            'email_proven': bool(u.email_proven_at), 'joined': u.date_joined, 'days': (now - u.date_joined).days,
            'posts': u.posts, 'removed': u.removed, 'paused': u.paused}


# ── The overview ───────────────────────────────────────────────────────────────────────────────────────────────────

def next_edition_on(today: date, latest: editions.Edition | None) -> date:
    """The day the next edition is written: the first of each month (deploy/law-edition.timer); today, on a first
    whose edition is not written yet."""
    if today.day == 1 and (latest is None or latest.date != today.isoformat()):
        return today
    return date(today.year + today.month // 12, today.month % 12 + 1, 1)


def programme() -> dict:
    """How the programme stands: the switch's position, where the staff's letters go, the terms' date, the days to an
    answer, the sizes, the newest edition and the day of the next. No query."""
    latest = editions.latest()
    return {'position': gate.position(), 'letter_to': list(settings.ACCESS_LETTER_TO), 'terms': settings.ACCESS_TERMS,
            'answer_days': settings.ACCESS_ANSWER_DAYS, 'sizes': settings.ACCESS_SIZES,
            'edition': {'date': latest.date, 'sha256': latest.sha256} if latest else None,
            'next_edition_on': next_edition_on(timezone.localdate(), latest)}


def overview() -> dict:
    """The desk's first page: the state; the requests waiting for the staff, the longest-waiting first; those waiting
    for their account's answer; the live accesses that end within ENDING_DAYS days; the figures. SHOWN rows a list."""
    today = timezone.localdate()
    queue = Request.objects.select_related('user')
    waiting = list(queue.filter(state=Request.State.WAITING).order_by('waiting_since', 'pk')[:SHOWN])
    more = list(queue.filter(state=Request.State.MORE).order_by('decided_at', 'pk')[:SHOWN])
    soon = today + timedelta(days=ENDING_DAYS)
    ending = list(_accesses().filter(state=Access.State.LIVE, ends_on__gte=today, ends_on__lte=soon)
                  .order_by('ends_on', 'pk')[:SHOWN])
    figures = asked.counted(today)
    figures.update(Access.objects.filter(state=Access.State.LIVE, ends_on__gte=today).aggregate(
        live=Count('pk', distinct=True), keys=Count('keys', filter=Q(keys__ended_at=None), distinct=True)))
    return {'state': programme(), 'waiting': [request_row(r, today) for r in waiting],
            'asked': [request_row(r, today) for r in more], 'ending': _access_rows(ending, today),
            'figures': figures}


# ── Requests ───────────────────────────────────────────────────────────────────────────────────────────────────────

def requests_page(state: str = 'waiting', q=None, cursor=None) -> dict:
    """A page of requests in a state (or all), matching `q` in the name given, the username or the address: the
    queues (`waiting`, `more`) the longest-waiting first, the others the newest first; with the counts by state."""
    state = state or 'waiting'
    if state not in REQUEST_STATES:
        raise Refused('state', 'invalid')
    q = _words(q)
    rows = Request.objects.select_related('user')
    if q:
        rows = rows.filter(Q(name__icontains=q) | Q(user__username__icontains=q) | Q(user__email__icontains=q))
    counts = rows.aggregate(**{s: Count('pk', filter=Q(state=s)) for s in Request.State.values})
    if state != 'all':
        rows = rows.filter(state=state)
    queue = state in Request.OPEN
    got, after = _page(rows, cursor, 'waiting_since' if queue else 'created_at', newest_first=not queue)
    today = timezone.localdate()
    return {'results': [request_row(r, today) for r in got], 'next': after, 'counts': counts}


def _proposed(r: Request, today: date) -> dict:
    """What accepting starts with: what was asked; the size named, else the volume's (a change request keeps its
    access's size and end date unless it named a size); an end date a year ahead."""
    if r.change_of_id:
        return {'api': r.wants_api, 'data': r.wants_data, 'size': r.wanted_size or r.change_of.size,
                'ends_on': r.change_of.ends_on}
    return {'api': r.wants_api, 'data': r.wants_data, 'size': r.wanted_size or asked.SIZE_OF_VOLUME[r.volume],
            'ends_on': accesses.default_end(today)}


def _questions(me) -> list[str]:
    """The lines this superuser asked last, three at most, each once, the newest first."""
    out = []
    for details in (Event.objects.filter(act=Event.Act.ASKED, by=me).order_by('-at', '-pk')
                    .values_list('details', flat=True)[:30]):
        line = (details or {}).get('line')
        if line and line not in out:
            out.append(line)
    return out[:QUESTIONS]


def request_sheet(pk: int, me) -> dict:
    """A request with what deciding needs: its answers, the account and its standing, its earlier requests, its
    newest access, what accepting proposes, this superuser's last questions, its history; whether `me` may decide it
    (open, and not their own)."""
    r = Request.objects.select_related('user', 'decided_by', 'change_of').filter(pk=pk).first()
    if r is None:
        raise Refused('request', 'not_found', 404)
    today = timezone.localdate()
    held = r.change_of
    row = {**request_row(r, today), 'purpose': r.purpose, 'runs_at': r.runs_at, 'terms': r.terms, 'asked': r.asked,
           'answer': r.answer, 'decided_at': r.decided_at,
           'decided_by': r.decided_by.username if r.decided_by_id else None,
           'holds': {'api': held.api, 'data': held.data, 'size': held.size} if held else None}
    earlier = (Request.objects.filter(user_id=r.user_id).exclude(pk=r.pk).order_by('-created_at', '-pk')
               .values('id', 'state', 'created_at', 'decided_at', 'reason', 'wants_api', 'wants_data',
                       'change_of')[:EARLIER])
    newest = _accesses().filter(user_id=r.user_id).order_by('-created_at', '-pk').first()
    return {'request': row, 'account': _account(r.user_id), 'earlier': list(earlier),
            'access': _access_rows([newest], today)[0] if newest else None, 'proposed': _proposed(r, today),
            'questions': _questions(me),
            'history': [event_row(e) for e in _events().filter(request=r).order_by('at', 'pk')],
            'may_decide': r.state in Request.OPEN and r.user_id != me.pk and bool(me.is_superuser)}


# ── Accesses ───────────────────────────────────────────────────────────────────────────────────────────────────────

def _access_states(today: date) -> dict:
    live = Q(state=Access.State.LIVE, ends_on__gte=today)
    return {'live': live, 'ending': live & Q(ends_on__lte=today + timedelta(days=ENDING_DAYS)), 'ended': ~live,
            'unused': live & Q(used=False)}


def accesses_page(state: str = 'live', q=None, cursor=None) -> dict:
    """A page of accesses in a state (`live`, `ending` within ENDING_DAYS days, `ended`, `unused`: live and never
    used, or `all`), matching `q` in the name its request gave, the username or the address, the newest first; with
    the counts by state."""
    state = state or 'live'
    if state not in ACCESS_STATES:
        raise Refused('state', 'invalid')
    q = _words(q)
    today = timezone.localdate()
    states = _access_states(today)
    base = Access.objects.annotate(used=Exists(AccessDay.objects.filter(access=OuterRef('pk'))))
    if q:
        base = base.filter(Q(request__name__icontains=q) | Q(user__username__icontains=q)
                           | Q(user__email__icontains=q))
    counts = base.aggregate(**{name: Count('pk', filter=where) for name, where in states.items()})
    chosen = base if state == 'all' else base.filter(states[state])
    rows = _accesses().filter(pk__in=chosen.values('pk'))
    got, after = _page(rows, cursor, 'created_at', newest_first=True)
    return {'results': _access_rows(got, today), 'next': after, 'counts': counts}


def access_sheet(pk: int) -> dict:
    """An access with its request, its account, its keys, its last SHEET_DAYS days that saw use (today's as counted
    now) by door and limit, its newest downloads and its history (its own acts and its requests')."""
    a = _accesses().select_related('ended_by').filter(pk=pk).first()
    if a is None:
        raise Refused('access', 'not_found', 404)
    today = timezone.localdate()
    held = {d.day: {'calls': d.calls, 'articles': d.articles, 'doors': d.doors, 'limits': d.limits}
            for d in AccessDay.objects.filter(access=a).order_by('-day')[:SHEET_DAYS]}
    held.update(usage.live(a.pk, [today - timedelta(days=k) for k in range(usage.DAY_KEPT // 86400)]))
    days = [{'day': d, **held[d]} for d in sorted(held)[-SHEET_DAYS:]]
    doors = {}
    for d in days:
        for door, n in d['doors'].items():
            doors[door] = doors.get(door, 0) + n
    r = a.request
    row = {**_access_rows([a], today)[0], 'created_at': a.created_at, 'renewed_at': a.renewed_at,
           'ended_at': a.ended_at, 'ended_by': a.ended_by.username if a.ended_by_id else None}
    history = _events().filter(Q(access=a) | Q(request_id=a.request_id) | Q(request__change_of=a)).order_by('at', 'pk')
    return {
        'access': row,
        'request': {'id': r.pk, 'name': r.name, 'kind': r.kind, 'purpose': r.purpose, 'runs_at': r.runs_at,
                    'volume': r.volume, 'commercial': r.commercial, 'terms': r.terms},
        'account': _account(a.user_id),
        'keys': list(ApiKey.objects.filter(access=a).order_by('created_at', 'pk')
                     .values('id', 'name', 'prefix', 'created_at', 'last_used_on', 'ended_at')),
        'days': days, 'doors': doors,
        'downloads': list(Download.objects.filter(access=a).order_by('-at', '-pk')
                          .values('edition', 'file', 'by', 'at')[:DOWNLOADS]),
        'history': [event_row(e) for e in history],
    }


# ── Use, editions, the log ─────────────────────────────────────────────────────────────────────────────────────────

def days_asked(value) -> int:
    """The `days` a use is read over: 1 to USE_MOST_DAYS, 30 when not said."""
    if value in (None, ''):
        return 30
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise Refused('days', 'invalid') from None
    if not 1 <= n <= USE_MOST_DAYS:
        raise Refused('days', 'invalid')
    return n


def use(days: int = 30) -> dict:
    """Use across every access over `days` days: calls and articles a day (the days that saw use, oldest first), calls
    by door, the five busiest accesses, who was refused for a limit today (from the counters, true to the minute),
    and the totals. Never what was asked."""
    today = timezone.localdate()
    first = today - timedelta(days=days - 1)
    by_day, doors, by_access = {}, {}, {}
    for access, day, calls, articles, its_doors in AccessDay.objects.filter(day__gte=first, day__lte=today).values_list(
            'access_id', 'day', 'calls', 'articles', 'doors'):
        c, a = by_day.get(day, (0, 0))
        by_day[day] = (c + calls, a + articles)
        c, a = by_access.get(access, (0, 0))
        by_access[access] = (c + calls, a + articles)
        for door, n in (its_doors or {}).items():
            doors[door] = doors.get(door, 0) + n
    top = sorted(by_access, key=lambda k: (-by_access[k][0], -by_access[k][1], k))[:BUSIEST]
    live = list(Access.objects.filter(Q(pk__in=top) | Q(state=Access.State.LIVE, ends_on__gte=today))
                .values('pk', 'state', 'ends_on', 'request__name'))
    names = {row['pk']: row['request__name'] for row in live}
    limited = usage.limited([row['pk'] for row in live
                             if row['state'] == Access.State.LIVE and row['ends_on'] >= today])
    return {
        'days': [{'day': d, 'calls': c, 'articles': a} for d, (c, a) in sorted(by_day.items())],
        'doors': dict(sorted(doors.items(), key=lambda kv: -kv[1])),
        'busiest': [{'access': k, 'name': names.get(k, ''), 'calls': by_access[k][0], 'articles': by_access[k][1]}
                    for k in top],
        'limited_today': [{'access': k, 'name': names.get(k, ''), 'limits': limits}
                          for k, limits in sorted(limited.items())],
        'totals': {'calls': sum(c for c, _ in by_access.values()), 'articles': sum(a for _, a in by_access.values()),
                   'accesses': len(by_access)},
    }


def editions_list() -> dict:
    """Every edition written, the newest first: its date, hash and counts, its bytes and files while it is on disk
    (each file with the times it was taken), its newest downloads and who took them; and the day of the next."""
    on_disk = {e.date: e for e in editions.listed()}
    taken = {}
    for edition, file, n in Download.objects.values('edition', 'file').annotate(n=Count('pk')).values_list(
            'edition', 'file', 'n'):
        taken[(edition, file)] = n
    newest = (Download.objects.select_related('access__request')
              .annotate(n=Window(RowNumber(), partition_by=F('edition'), order_by=(F('at').desc(), F('pk').desc())))
              .filter(n__lte=EDITION_DOWNLOADS).order_by('edition', '-at', '-pk'))
    downloads = {}
    for d in newest:
        downloads.setdefault(d.edition, []).append(
            {'access': d.access_id, 'name': d.access.request.name, 'file': d.file, 'by': d.by, 'at': d.at})
    out, given = [], set()
    for entry in editions.history(counts=True):
        disk = on_disk.get(entry['date'])
        here = disk is not None and disk.sha256 == entry['sha256']
        # A day's downloads go to the edition of that day still on disk (an export run twice wrote two), or to the
        # day's newest when none is.
        gets = entry['date'] not in given and (here or disk is None)
        if gets:
            given.add(entry['date'])
        files = disk.manifest.get('files', {}) if here else {}
        out.append({'date': entry['date'], 'sha256': entry['sha256'], 'texts': entry.get('texts'),
                    'articles': entry.get('articles'), 'versions': entry.get('versions'),
                    'bytes': sum(f.get('bytes', 0) for f in files.values()) if here else None, 'on_disk': here,
                    'files': [{'name': name, 'bytes': f.get('bytes'), 'taken': taken.get((entry['date'], name), 0)}
                              for name, f in files.items()],
                    'downloads': downloads.get(entry['date'], []) if gets else []})
    latest = editions.latest()
    return {'editions': out, 'next_on': next_edition_on(timezone.localdate(), latest)}


def log_page(cursor=None) -> dict:
    """A page of every act, the newest first."""
    got, after = _page(_events(), cursor, 'at', newest_first=True)
    return {'results': [event_row(e) for e in got], 'next': after}
