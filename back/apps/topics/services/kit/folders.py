"""Each topic's folder read and kept in the process, with the checks people recorded: the files known by their names and
times, the checks read once a version of the token in the shared cache, the caches a new check or a test clears; the
topics that have a folder; and `citing`, what cites each article across the folders, built once from them. `warm`
reads them all before a worker's first request (config/wsgi.py). Every cache of the kit lives here."""
import json
import logging
import time
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings
from django.core.cache import caches

from apps.topics.services.kit.items import articles, cited_in_order, shown
from config.inside import inside

BASE = Path(__file__).resolve().parent.parent.parent
KINDS = ('journeys', 'checklists', 'pages', 'reform', 'series', 'rates', 'cards')
log = logging.getLogger(__name__)


def folder(slug: str) -> Path:
    """A topic's folder. A slug that would name a place outside the topics' own folder names one that is not there:
    the address's converter already keeps a slug to letters, digits and dashes, and this holds for any other caller."""
    return inside(BASE, slug.replace('-', '_')) or BASE / '.none'


def load(slug: str) -> dict | None:
    """The topic's files with its checks: {'hub': {...}, 'journeys': {key: item}, …}; None for a topic without a
    folder. Read again when a file changes or a check is recorded, so either shows without a restart."""
    return _merged(slug, _files(slug), checks_version())


def stamp(slug: str) -> tuple:
    """What changes when the topic does: its files by name and time, and the checks' version."""
    files = _files(slug)
    return (*files, ('checks', checks_version())) if files else ()


def _files(slug: str) -> tuple:
    root = folder(slug)
    return tuple(sorted((p.name, p.stat().st_mtime_ns) for p in [*root.glob('*.yaml'), *root.glob('*.json')])) \
        if root.is_dir() else ()


# The checks' version: a token in the shared cache that every recorded check changes, read at most once a second by a
# process. A check made in one worker shows in every worker within the second; a token the cache lost is made again,
# and every worker reads the checks once more. Without the cache, a check shows in the other workers at their restart.
CHECKS_KEY = 'topics:checks'
_seen = {'at': 0.0, 'version': ''}


def checks_version() -> str:
    now = time.monotonic()
    if _seen['version'] and now - _seen['at'] < 1:
        return _seen['version']
    try:
        cache = caches['default']
        version = cache.get(CHECKS_KEY)
        if version is None:
            cache.add(CHECKS_KEY, str(time.time_ns()), timeout=None)
            version = cache.get(CHECKS_KEY)
    except Exception:  # the cache down: the checks this process read stand
        log.warning("topics: the checks' version could not be read", exc_info=True)
        version = None
    _seen.update(at=now, version=version or '-')
    return _seen['version']


def _checks_changed() -> None:
    try:
        caches['default'].set(CHECKS_KEY, str(time.time_ns()), timeout=None)
    except Exception:
        log.warning("topics: the checks' version could not be changed", exc_info=True)
    _seen.update(at=0.0, version='')
    _merged.cache_clear()
    _checks.cache_clear()


@lru_cache(maxsize=2)
def _checks(version: str) -> dict[str, dict[str, dict]]:
    """{topic: {ref: {by, on, digests}}}: every check, in one query a version."""
    from apps.topics.models import ItemCheck

    out: dict[str, dict[str, dict]] = {}
    for c in ItemCheck.objects.values('topic', 'ref', 'by', 'on', 'digests'):
        out.setdefault(c['topic'], {})[c['ref']] = {'by': c['by'], 'on': c['on'].isoformat(), 'digests': c['digests']}
    return out


@lru_cache(maxsize=32)
def _merged(slug: str, files: tuple, version: str) -> dict | None:
    """The folder's items, each checked one carrying its `checked` block; the files' own reading is not changed."""
    content = _load(slug, files)
    checks = _checks(version).get(slug) if content is not None else None
    if not checks:
        return content
    out = dict(content)
    for ref, c in checks.items():
        kind, _, key = ref.partition('/')
        if kind in KINDS and key in content[kind]:
            if out[kind] is content[kind]:
                out[kind] = dict(content[kind])
            out[kind][key] = {**content[kind][key], 'checked': c}
    tools = {ref.partition('/')[2]: c for ref, c in checks.items() if ref.startswith('tools/')}
    if tools and content['hub'].get('tools'):
        out['hub'] = {**content['hub'], 'tools': [{**t, 'checked': tools[t['key']]} if t.get('key') in tools else t
                                                  for t in content['hub']['tools']]}
    return out


def warm() -> None:
    """Every topic's files read into this process (config/wsgi.py, before a worker's first request): read on a topic's
    first request instead, they cost that reader about a second, in each worker."""
    from apps.topics.services.topics import load as topics
    for t in topics():
        load(t['slug'])
    citing()


@lru_cache(maxsize=32)
def _load(slug: str, stamp: tuple) -> dict | None:
    root = folder(slug)
    if not (root / 'hub.yaml').exists():
        return None
    out = {'hub': yaml.safe_load((root / 'hub.yaml').read_text(encoding='utf-8')) or {}}
    for kind in KINDS:
        path = root / f'{kind}.yaml'
        items = yaml.safe_load(path.read_text(encoding='utf-8')) if path.exists() else None
        if isinstance(items, dict) and kind == 'series':     # series.yaml: the files, then the series read from them
            files = items.get('files') or {}
            items = [{**s, 'files': {y['from']: files[y['from']] for y in s['years']}} for s in items['series']]
        elif isinstance(items, dict):         # reform.yaml is one item
            items = [{'key': kind, **items}]
        if kind == 'rates':                   # a row too big for YAML names its file (the road's capital table)
            for item in items or []:
                for row in item.get('rows') or []:
                    if row.get('table'):
                        row['values'] = json.loads((root / row['table']).read_text(encoding='utf-8'))
        out[kind] = {i['key']: i for i in items or []}
    return out


def _clear() -> None:
    _load.cache_clear()
    _merged.cache_clear()
    _checks.cache_clear()
    _citing.cache_clear()
    _seen.update(at=0.0, version='')


load.cache_clear = _clear     # type: ignore[attr-defined]


def _folders() -> list[str]:
    return sorted(d.name.replace('_', '-') for d in BASE.iterdir() if (d / 'hub.yaml').exists())


# What an article leads to (HM20 of the hard-moment review): the topic items that cite it, the tools first (they
# answer with the reader's numbers), then the journeys, the lists, the pages and the changes.
CITING = ('tools', 'journeys', 'checklists', 'pages', 'reform')


def citing() -> dict[str, dict[str, list[dict]]]:
    """{text address: {article eid: [the items that cite it]}} across every topic's folder: each item a reader may see
    (`shown`), its topic, title, address and whether a person checked it. Built once a process for the folders' files and
    the drafts' setting (`warm` builds it before a worker's first request), then a lookup: no query."""
    from apps.topics.services import topics as every
    return _citing(tuple((t['slug'], stamp(t['slug'])) for t in every.load()), bool(settings.SHOW_DRAFTS))


@lru_cache(maxsize=4)
def _citing(stamps: tuple, drafts: bool) -> dict[str, dict[str, list[dict]]]:
    from apps.topics.services import topics as every

    out: dict[str, dict[str, list[dict]]] = {}
    for t in every.load():
        content = load(t['slug'])
        if content is None:
            continue
        items = [('tools', tool['key'], tool) for tool in content['hub'].get('tools') or []]
        items += [(kind, key, item) for kind in CITING[1:] for key, item in content[kind].items()]
        for kind, key, item in items:
            if not shown(item) or not item.get('title'):
                continue
            ref = f'{kind}/{key}'
            checked = item.get('checked') or None
            paths = cited_in_order(item)
            # A bill's item (the 2027 bill's tool, its pages, an announced change) speaks of what is not law: said so,
            # and after the items on the law in force.
            bill = bool(item.get('bill') or item.get('stage') in ('bill', 'announced')
                        or (kind == 'tools' and any('/projet-loi/' in p for p in paths)))
            entry = {'topic': t['slug'], 'name': t.get('short') or t['name'], 'ref': ref, 'kind': kind, 'bill': bill,
                     'path': f"/topics/{t['slug']}/reform" if ref == 'reform/reform' else f"/topics/{t['slug']}/{ref}",
                     'title': item['title'], 'open': bool(item.get('open')), 'checked': bool(checked),
                     # A page's check keeps the digests of what it cited: an article changed since makes it «stale».
                     '_digests': (checked or {}).get('digests') if kind != 'tools' else None}
            for at, path in enumerate(paths):
                uri, _, eid = path.rpartition('/')
                if uri and eid.startswith('art_'):
                    out.setdefault(uri, {}).setdefault(eid, []).append({**entry, '_at': at})
    for arts in out.values():
        for _eid, entries in arts.items():
            # The law's items before a bill's; the tools first, then by how near the item's start the article stands (a
            # journey's first step cites it).
            entries.sort(key=lambda e: (e['bill'], CITING.index(e['kind']), e['_at']))
    return out


def cites_of(text: str) -> dict:
    """The items that cite each article of one text (`/ma/loi/65-99`), as `citing` keeps them, each with its state:
    'draft' (never checked), 'stale' (an article it cites changed since its check), 'checked'. Checked pages' articles
    are read in one batch, so the answer takes the same few queries whatever the text."""
    found = citing().get(text.rstrip('/'), {})
    digests = {p for entries in found.values() for e in entries for p in (e['_digests'] or {})}
    now = articles(digests) if digests else {}

    def one(e: dict) -> dict:
        state = 'checked' if e['checked'] else 'draft'
        if e['_digests'] and any((now.get(p) or {}).get('digest') != d for p, d in e['_digests'].items()):
            state = 'stale'
        return {k: v for k, v in e.items() if not k.startswith('_') and k != 'checked'} | {'state': state}
    return {'articles': {eid: [one(e) for e in entries] for eid, entries in found.items()}}
