"""What a person checks: what `manage.py check_topic` reports (cited articles the site lacks, links to missing items,
items whose articles changed since their check), the items of a topic a person may check, a check recorded under the
account that made it, and everything the reviewer's desk reads."""
from collections import Counter, defaultdict
from datetime import date

from django.db import transaction

from apps.analytics.services.report import shown_under
from apps.topics.services.kit.folders import KINDS, _checks_changed, load
from apps.topics.services.kit.items import _resolve, articles, cited, links, state


def _holds(ref: str) -> bool:
    """Another topic's item a link names («tax:tools/own»): its folder's kinds, and the tools its hub lists."""
    other, own = ref.split(':', 1)
    kind, _, key = own.partition('/')
    content = load(other) or {}
    if kind == 'tools':
        return any(t['key'] == key for t in content.get('hub', {}).get('tools') or [])
    return key in (content.get(kind) or {})


def problems(slug: str) -> list[str]:
    """What `manage.py check_topic` reports: cited articles the site does not have, links to missing items or tools, items
    that need a check again."""
    content = load(slug)
    if content is None:
        return [f'{slug}: no folder']
    out = []
    every = cited(dict(content.items()))
    arts = articles(every)
    for p in sorted(every - set(arts)):
        out.append(f'cites a missing article: {p}')
    keys = {f'{kind}/{key}' for kind in KINDS for key in content[kind]}
    keys |= {f'tools/{t["key"]}' for t in content['hub'].get('tools') or []}
    for e in content['hub'].get('events') or []:
        if e.get('to') and ':' in e['to']:
            if not _holds(e['to']):
                out.append(f'door «{e["key"]}» leads to a missing {e["to"]}')
        elif e.get('to') and e['to'] not in keys and not e.get('tool'):
            out.append(f'door «{e["key"]}» leads to a missing {e["to"]}')
    for kind in KINDS:
        for key, item in content[kind].items():
            for ref in sorted(links(item) - keys):
                if ':' in ref and _holds(ref):
                    continue
                out.append(f'{kind}/{key} leads to a missing {ref}')
            for ref in item.get('series') or [] if kind == 'pages' else []:
                if ref not in content['series']:
                    out.append(f'{kind}/{key} shows a missing series {ref}')
    for kind in KINDS:
        for key, item in content[kind].items():
            if state(item, arts) == 'stale':
                out.append(f'{kind}/{key}: an article it cites changed since its check')
    return out


def items_of(slug: str) -> dict[str, dict]:
    """{ref: item} for every item of the topic a person may check: its journeys, lists, pages… and the hub's tools."""
    content = load(slug) or {'hub': {}, **{kind: {} for kind in KINDS}}
    found = {f'{kind}/{key}': item for kind in KINDS for key, item in content[kind].items()}
    found.update({f"tools/{t['key']}": t for t in content['hub'].get('tools') or [] if isinstance(t, dict) and t.get('key')})
    return found


def record_checks(slug: str, refs: list[str], by: str, on: str | None = None, user=None) -> dict:
    """Record that a person checked these items (the command's work, and the reviewer's desk's, `user` its account):
    who, when, and for all but a tool the digests of the articles it cites. Only items the topic has: a KeyError names
    the first it has not, and nothing is written. Returns {ref: {by, on}}."""
    from apps.topics.models import ItemCheck

    on = on or date.today().isoformat()
    known = items_of(slug)
    refs = list(dict.fromkeys(refs))
    missing = next((ref for ref in refs if ref not in known), None)
    if missing is not None:
        raise KeyError(missing)
    pages = {ref: cited(known[ref]) for ref in refs if not ref.startswith('tools/')}
    arts = articles(set().union(*pages.values())) if pages else {}
    rows = [ItemCheck(topic=slug, ref=ref, user=user, by=by[:80], on=on,
                      digests={p: arts[p]['digest'] for p in sorted(pages.get(ref, ())) if p in arts}) for ref in refs]
    with transaction.atomic():
        ItemCheck.objects.filter(topic=slug, ref__in=refs).delete()
        ItemCheck.objects.bulk_create(rows)
    _checks_changed()
    return {ref: {'by': by[:80], 'on': on} for ref in refs}


# The kinds whose items have a page of their own (web/src/topics/kit/TopicArea.tsx); series, rates and cards are shown
# inside other pages.
PAGED = ('journeys', 'checklists', 'pages', 'reform', 'tools')
READ_DAYS = 28


def _item_of(path: str, prefix: str) -> str | None:
    """The item a page of the topic shows: «/topics/road/tools/fine» (and a tool's own pages under it) is tools/fine,
    «/topics/road/reform» the reform's own page, reform/reform."""
    parts = path[len(prefix):].split('/')
    if parts == ['reform']:
        return 'reform/reform'
    return f'{parts[0]}/{parts[1]}' if len(parts) > 1 and parts[0] in PAGED else None


def _readers(slug: str) -> Counter:
    """{ref: times its page was shown in the last READ_DAYS days}, in one query for the whole topic."""
    prefix = f'/topics/{slug}/'
    read: Counter = Counter()
    for path, n in shown_under(prefix, days=READ_DAYS).items():
        if (ref := _item_of(path, prefix)) is not None:
            read[ref] += n
    return read


def _most_read_first(items: list[dict]) -> list[dict]:
    """Within each wave, its items most read first (the analytics review, 15 Nov 2026); ties keep their order, and an
    item no page shows comes last in its wave. Each wave's items take the places its items held, so the waves stay
    where they were in the list."""
    places = defaultdict(list)
    for i, item in enumerate(items):
        places[item['wave']].append(i)
    out = list(items)
    for held in places.values():
        ordered = sorted(held, key=lambda i: (items[i]['readers'] is None, -(items[i]['readers'] or 0), i))
        for place, i in zip(held, ordered):
            out[place] = items[i]
    return out


def review(slug: str) -> dict | None:
    """Everything a reviewer reads (R1 of the road tools review): each item of the topic, drafts included, with its
    state and wave, and the words of every article it cites, so a sentence is checked against its law on one screen.
    Each item carries `readers`, the times its page was shown in the last READ_DAYS days (None for an item without a
    page of its own), and each wave lists its items most read first."""
    content = load(slug)
    if content is None:
        return None
    waves = {ref: int(n) for n, refs in (content['hub'].get('waves') or {}).items() for ref in refs}
    every = cited(content)
    arts = articles(every)
    items = []
    for kind in KINDS:
        for key, item in content[kind].items():
            ref = f'{kind}/{key}'
            items.append({'ref': ref, 'kind': kind, 'key': key, 'title': item.get('title'), 'state': state(item, arts),
                          'checked': _resolve({'checked': item.get('checked')}, arts)['checked'], 'wave': waves.get(ref),
                          'item': _resolve(item, arts)})
    for t in content['hub'].get('tools') or []:
        ref = f'tools/{t["key"]}'
        items.append({'ref': ref, 'kind': 'tools', 'key': t['key'], 'title': t.get('title'),
                      'state': 'checked' if t.get('checked') else 'draft', 'open': bool(t.get('open')),
                      'checked': {'by': t['checked'].get('by'), 'on': t['checked'].get('on')} if t.get('checked') else None,
                      'wave': waves.get(ref), 'item': None})
    read = _readers(slug)
    for item in items:
        item['readers'] = read[item['ref']] if item['kind'] in PAGED else None
    return {'slug': slug, 'items': _most_read_first(items), 'bodies': {p: a['body'] for p, a in arts.items()}}
