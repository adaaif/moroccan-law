"""The door every measure comes in by (POST /api/measure/, the analytics review, 15 Nov 2026): a batch of events from
one page of the app, checked against the registry and written whole, or refused whole.

Refused (400, nothing written): a name the registry does not know; a property it does not list for that name, or a value
outside its rule; a kind, path, language, screen or build outside theirs; a field the door does not read; more than
MOST_EVENTS events. The view refuses a body over MOST_BYTES. A path loses its query and fragment before it is checked,
and they are never kept.

Dropped without a word (204, nothing written, so a machine learns nothing about the rules): everything while
ANALYTICS_OPEN is off; a browser that sends Sec-GPC: 1 (Global Privacy Control); a search engine's crawler by its
published addresses (apps/seo/services/crawlers.py); a User-Agent that says it is a machine (BOTS), or none. The
User-Agent and the address are read for those checks and nothing else: they are never stored or logged. Whether an
address belongs to a data centre is not known here (apps/corpus/services/operators.py gives an operator's number, not
what it runs).

Written: the batch's events in one INSERT, each at the hour it came in, never a minute. For each visit's first page
(page.shown with entry), the country Cloudflare saw (CF-IPCountry) is counted on its own, in one upsert a batch, in
DayCount 'visit.country' for Morocco's day: the country is never on an event row, so no row can be tied to one.

Nothing here reads the request's cookies, its Authorization header or its account: the view has no authentication
(`authentication_classes = []`), and `facts_of` reads only the headers named. A signed-in reader's batch writes the same
rows as anyone's. A failure while writing is logged and the reader's page answered 204 all the same."""
import logging
import re
from dataclasses import dataclass

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.analytics import registry
from apps.analytics.models import DayCount, Event
from apps.analytics.services import sources
from apps.opendata.throttles import address
from apps.seo.services import crawlers

log = logging.getLogger(__name__)

# The machines that say what they are, as the request log flagged them (apps/visits, removed on 15 Nov 2026), less
# «whatsapp» and «telegram»: their link previews run no script and send no measure, and the browsers inside those
# apps say their names too.
BOTS = re.compile(r'bot\b|bot/|crawl|spider|slurp|curl|wget|python|httpx|aiohttp|go-http|java/|okhttp|headless|'
                  r'lighthouse|facebookexternalhit|preview|monitor|uptime|scan', re.I)
BATCH_KEYS = {'lang', 'screen', 'build', 'events'}
EVENT_KEYS = {'name', 'kind', 'path', 'flow', 'props'}
COUNTRY = re.compile(r'[A-Z]{2}')
_PATH = re.compile(registry.PATH)
_BUILD = re.compile(registry.BUILD)


@dataclass(frozen=True)
class Facts:
    """What the door reads of a request besides its body: for the checks, then dropped."""
    agent: str
    address: str
    gpc: bool
    country: str


def facts_of(request) -> Facts:
    """The few headers the door reads: the User-Agent, Global Privacy Control, Cloudflare's country, and the address
    (apps.opendata.throttles.address: Cloudflare's view of the reader, else the one nginx appended)."""
    meta = request.META
    country = meta.get('HTTP_CF_IPCOUNTRY', '').strip().upper()
    return Facts(agent=meta.get('HTTP_USER_AGENT', ''), address=address(request),
                 gpc=meta.get('HTTP_SEC_GPC', '').strip() == '1',
                 country=country if COUNTRY.fullmatch(country) else 'XX')


def ignored(facts: Facts) -> bool:
    """Whether the request is dropped without a word: the door closed, a reader who asked not to be counted, or a
    machine."""
    return (not settings.ANALYTICS_OPEN or facts.gpc or not facts.agent or BOTS.search(facts.agent) is not None
            or bool(crawlers.crawler(facts.address)))


def _word(batch: dict, name: str, allowed) -> str:
    value = batch.get(name)
    if value is None:
        raise Refused(name, 'required')
    if not isinstance(value, str) or not allowed(value):
        raise Refused(name, 'invalid')
    return value


def _path(at: str, value) -> str:
    if value is None:
        raise Refused(f'{at}.path', 'required')
    if not isinstance(value, str):
        raise Refused(f'{at}.path', 'invalid')
    path = value.split('?', 1)[0].split('#', 1)[0]
    if not _PATH.fullmatch(path):
        raise Refused(f'{at}.path', 'invalid')
    return path


def _flow(at: str, value) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= registry.FLOW_MOST:
        raise Refused(f'{at}.flow', 'invalid')
    return value


def _props(at: str, name: str, value) -> dict:
    """The properties as stored: each checked by its rule and cleaned (a number to its band, a host lowercased); a
    missing or null one left out. A visit's first page, and an address that led nowhere from outside the site, get
    their `source` from their `ref` when the browser gave none."""
    rules = registry.MEASURES[name].props
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise Refused(f'{at}.props', 'invalid')
    if value.keys() - rules.keys():
        raise Refused(f'{at}.props', 'unexpected')
    props = {}
    for key, raw in value.items():
        if raw is None:
            continue
        if not rules[key].valid(raw):
            raise Refused(f'{at}.props.{key}', 'invalid')
        props[key] = rules[key].clean(raw)
    if name == 'page.shown':
        if props.get('entry') is True:
            props.setdefault('source', sources.of(props.get('ref')))
        else:
            for key in registry.ENTRY_ONLY:
                if key in props:
                    raise Refused(f'{at}.props.{key}', 'entry_only')
    elif name == 'page.missing' and props.get('inside') is not True:
        props.setdefault('source', sources.of(props.get('ref')))
    return props


def read(batch, hour) -> list[Event]:
    """The batch's events as rows, every one checked; the first refusal raised (Refused) and nothing kept."""
    if not isinstance(batch, dict):
        raise Refused('body', 'invalid')
    if batch.keys() - BATCH_KEYS:
        raise Refused('body', 'unexpected')
    lang = _word(batch, 'lang', registry.LANGS.__contains__)
    screen = _word(batch, 'screen', registry.SCREENS.__contains__)
    build = _word(batch, 'build', lambda v: _BUILD.fullmatch(v) is not None)
    events = batch.get('events')
    if events is None:
        raise Refused('events', 'required')
    if not isinstance(events, list):
        raise Refused('events', 'invalid')
    if len(events) > registry.MOST_EVENTS:
        raise Refused('events', 'too_many')
    rows = []
    for i, event in enumerate(events):
        at = f'events.{i}'
        if not isinstance(event, dict):
            raise Refused(at, 'invalid')
        if event.keys() - EVENT_KEYS:
            raise Refused(at, 'unexpected')
        name = event.get('name')
        if name is None:
            raise Refused(f'{at}.name', 'required')
        if not isinstance(name, str) or name not in registry.MEASURES:
            raise Refused(f'{at}.name', 'unknown')
        kind = event.get('kind')
        if kind is None:
            raise Refused(f'{at}.kind', 'required')
        if not isinstance(kind, str) or kind not in registry.KINDS:
            raise Refused(f'{at}.kind', 'invalid')
        rows.append(Event(hour=hour, name=name, kind=kind, path=_path(at, event.get('path')),
                          flow=_flow(at, event.get('flow')), props=_props(at, name, event.get('props')),
                          lang=lang, screen=screen, build=build))
    return rows


def _count(day, metric: str, key: str, n: int) -> None:
    """One more `n` on a day's count, made or added to in one statement (SQLite and PostgreSQL both read it)."""
    q = connection.ops.quote_name
    table = q(DayCount._meta.db_table)
    on, of, by, total = (q(c) for c in ('day', 'metric', 'key', 'count'))
    # The model's own names alone are written into the statement; every value is a parameter.
    sql = (f'INSERT INTO {table} ({on}, {of}, {by}, {total}) VALUES (%s, %s, %s, %s) '  # noqa: S608
           f'ON CONFLICT ({on}, {of}, {by}) DO UPDATE SET {total} = {table}.{total} + excluded.{total}')
    with connection.cursor() as cursor:
        cursor.execute(sql, [connection.ops.adapt_datefield_value(day), metric, key, n])


def _write(rows: list[Event], country: str) -> None:
    entries = sum(1 for row in rows if row.name == 'page.shown' and row.props.get('entry') is True)
    with transaction.atomic():
        Event.objects.bulk_create(rows)
        if entries:
            _count(timezone.localdate(), 'visit.country', country, entries)


def record(batch, facts: Facts) -> int:
    """The batch written: the rows it made (0 when a failure kept them out). A refusal raises Refused before anything is
    written; any other failure is logged and never reaches the reader."""
    hour = timezone.now().replace(minute=0, second=0, microsecond=0)
    try:
        rows = read(batch, hour)
    except Refused:
        raise
    except Exception:  # logged: a fault in the door costs the batch, never the reader's page
        log.exception('analytics: a batch could not be read')
        return 0
    if not rows:
        return 0
    try:
        _write(rows, facts.country)
    except Exception:  # logged: a measure lost never fails the reader's page
        log.exception('analytics: a batch of %s events was not written', len(rows))
        return 0
    return len(rows)
