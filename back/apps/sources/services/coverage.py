"""Which BO issues the site has read (row L5 of the links review), so «no change found» is said only of the issues read.

The issues there are: the general edition's queue from 2019 (CORPUS_DIR/reports/runs/queue_2019_2026.txt, one line
an issue, made from the SGG's list and the archive) and every issue registered since. An issue is read once its
contents have been gone through: each legal text they list either loaded or named as not found in the pages. One
that lists only reports and notices (a bis issue printing the human rights council's report) is read with no text.
The tally per issue is kept in CORPUS_DIR/reports/coverage.json, written by the links pipeline (`refresh`).

Once the archive's issues are here (Z23 of the second-archive-run review, 29 Oct 2026), its queue of every issue from
1956 to 2018 (queue_1956_2018.txt, from the archive's plan) joins: an old issue is read when its laws, general texts,
special decrees and orders are; the decisions it lists and the site has not read yet are counted apart («waiting»).
The queue reaches back to No. 1 of 1913 once the plan says so (H10 of the Bulletin-from-No.-1 review, 1 Nov 2026: the
plan's `coverage_from`, set when the official section before 1956 is read); its first day is the site's first.
"""
import json
import time
from datetime import date
from pathlib import Path

from django.conf import settings

from apps.sources.models import Edition, Issue

FROM = date(2019, 1, 1)
QUEUE = 'queue_2019_2026.txt'
ARCHIVE_FROM = date(1956, 1, 1)
ARCHIVE_QUEUE = 'queue_1956_2018.txt'
LEGAL = {'law', 'organic_law', 'dahir', 'decree', 'decree_law', 'order', 'decision'}
_cache: dict = {}


def _path() -> Path:
    return Path(settings.CORPUS_DIR) / 'reports' / 'coverage.json'


def start() -> date:
    """The first day the site reads: 1956 once the archive's queue is here (its first issue's day when that is earlier:
    No. 1 of 1913 once the years before 1956 are read), 2019 before."""
    try:
        with open(Path(settings.CORPUS_DIR) / 'reports' / 'runs' / ARCHIVE_QUEUE) as f:
            first = f.readline().split()
    except OSError:
        return FROM
    try:
        return min(ARCHIVE_FROM, date.fromisoformat(first[1]))
    except (IndexError, ValueError):
        return ARCHIVE_FROM


def _known() -> dict[str, date]:
    known: dict[str, date] = {}
    first = start()
    for name in (QUEUE, ARCHIVE_QUEUE):
        try:
            lines = (Path(settings.CORPUS_DIR) / 'reports' / 'runs' / name).read_text().splitlines()
        except OSError:
            lines = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 2 and parts[0][:1].isdigit():
                try:
                    day = date.fromisoformat(parts[1])
                except ValueError:
                    continue
                if day >= first:
                    known[parts[0]] = day
    for issue in Issue.objects.filter(edition=Edition.GENERAL_AR, date__gte=first):
        known.setdefault(issue.key, issue.date)
    return known


def loaded_of(keys) -> dict[tuple[int, str], int]:
    """How many texts each of these issues first published, by (number, suffix), in one query for all of them."""
    from django.db.models import Count

    from apps.corpus.models import Text
    numbers = {Issue.parse_key(key)[0] for key in keys}
    rows = (Text.objects.filter(first_published_in__edition=Edition.GENERAL_AR, first_published_in__number__in=numbers)
            .values_list('first_published_in__number', 'first_published_in__suffix').annotate(n=Count('id')).order_by())
    return {(number, suffix): n for number, suffix, n in rows} if numbers else {}


def tally(key: str, loaded: dict | None = None) -> dict | None:
    """{listed, loaded, unfound, waiting, waiting_rules}: the legal texts an issue's contents list, those loaded and
    those not found in its pages; those whose pages the archive has not read yet, decisions apart from the rest;
    None when the issue has not been gone through. `loaded`: `loaded_of` for many issues, read once."""
    from apps.sources.services.archive import kind_of
    path = Path(settings.CORPUS_DIR) / 'reports' / 'issues' / key / 'texts.json'
    try:
        entries = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    number, suffix = Issue.parse_key(key)
    loaded = (loaded if loaded is not None else loaded_of([key])).get((number, suffix), 0)
    if not loaded and any((e.get('toc') or {}).get('title', '').strip() in ('فهرست', 'فهرس', 'الفهرس') for e in entries):
        return None     # the contents were not read (BO 7504 came back as one entry, «فهرست»)
    legal = [e for e in entries if (e.get('toc') or {}).get('type') in LEGAL]
    later = [e for e in legal if e.get('stop') == 'later']
    legal = [e for e in legal if e.get('stop') != 'later']
    unfound = [e['toc'].get('title', '')[:160] for e in legal if not (e.get('data') or {}).get('found')]
    rules = sum(1 for e in later if kind_of(e['toc']) <= 1)
    return {'listed': len(legal), 'loaded': loaded, 'unfound': len(unfound), 'unfound_titles': unfound[:20],
            'waiting': len(later) - rules, 'waiting_rules': rules}


def refresh(keys: list[str] | None = None) -> dict:
    """The tally of every issue (or of `keys`) written to coverage.json."""
    path = _path()
    try:
        saved = json.loads(path.read_text()) if keys else {}
    except (OSError, ValueError):
        saved = {}
    known = _known()
    asked = [key for key in (keys if keys else known) if key in known]
    loaded = loaded_of(asked)       # every issue's loaded texts in one query (one an issue before)
    for key in asked:
        t = tally(key, loaded)
        saved[key] = {'date': known[key].isoformat(), **(t or {'listed': None})}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(saved, ensure_ascii=False, indent=0))
    tmp.replace(path)
    _cache.clear()
    return saved


def _read(entry: dict) -> bool:
    if entry.get('listed') is None or entry.get('waiting_rules'):
        return False
    return entry['loaded'] > 0 or entry['listed'] == 0 or entry['unfound'] < entry['listed']


def ledger(fresh: bool = False) -> dict:
    """{from, known, read, latest, missing: [{key, date}], unfound, waiting}: the issues from 2019 on (1956 with the
    archive), oldest first; `unfound` is the legal texts listed in read issues but not found in their pages,
    `waiting` the read issues whose decisions are not read yet."""
    path = _path()
    try:
        stamp = path.stat().st_mtime
    except OSError:
        stamp = 0
    if not fresh and _cache.get('stamp') == stamp and _cache.get('at', 0) > time.time() - 300:
        return _cache['ledger']
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        saved = {}
    known = _known()
    for key, day in known.items():
        saved.setdefault(key, {'date': day.isoformat(), 'listed': None})
    rows = sorted(({**v, 'key': k, 'date': date.fromisoformat(v['date'])} for k, v in saved.items()
                   if k in known), key=lambda r: (r['date'], Issue.parse_key(r['key'])))
    read = [r for r in rows if _read(r)]
    missing = [{'key': r['key'], 'date': r['date']} for r in rows if not _read(r)]
    unfound = [{'key': r['key'], 'date': r['date'], 'count': r['unfound']} for r in read if r.get('unfound')]
    waiting = [{'key': r['key'], 'date': r['date']} for r in read if r.get('waiting')]
    latest = read[-1] if read else None
    out = {'from': start(), 'known': len(rows), 'read': len(read), 'missing': missing, 'unfound': unfound,
           'waiting': waiting, 'latest': {'key': latest['key'], 'date': latest['date']} if latest else None}
    _cache.update(stamp=stamp, at=time.time(), ledger=out)
    return out


def since(day: date | None) -> dict:
    """What the site has read after `day` (a text's publication) up to its latest issue: the issues it has not, the legal
    texts listed in those it has but not found in their pages, and how many of them still have decisions to read.
    A day before the site's first (1956 with the archive, 2019 before) is outside what it reads."""
    led = ledger()
    if day is None or day < led['from']:
        return {'before': True, 'from': led['from'], 'latest': led['latest'], 'missing': [], 'unfound': 0, 'waiting': 0}
    last = led['latest']['date'] if led['latest'] else day
    missing = [m for m in led['missing'] if day < m['date'] <= last]
    unfound = sum(u['count'] for u in led['unfound'] if day < u['date'] <= last)
    waiting = sum(1 for w in led['waiting'] if day < w['date'] <= last)
    return {'before': False, 'from': day, 'latest': led['latest'], 'missing': missing, 'unfound': unfound,
            'waiting': waiting}
