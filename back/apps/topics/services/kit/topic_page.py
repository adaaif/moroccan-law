"""What a topic's page shows a reader: its hub (the doors, the tools, the red band, the learning path, the beliefs,
the changes), an item's own page, the next and the last dated change, the law's calendar across the topics and the
topics page's moments; whether an item, this topic's or another's, may be shown, and where a door leads."""
from apps.topics.services.kit.folders import KINDS, load
from apps.topics.services.kit.items import _resolve, articles, cited, shown, state


def page(slug: str, kind: str, key: str) -> dict | None:
    """One journey, checklist, page, the reform or a series, resolved for a reader; None when absent or unchecked."""
    content = load(slug)
    item = (content or {}).get(kind, {}).get(key)
    if item is None or not shown(item):
        return None
    arts = articles(cited(item))
    out = {**_resolve(item, arts), 'kind': kind, 'state': state(item, arts)}
    if kind == 'pages' and item.get('series'):     # the numbers page carries its series
        out['series'] = [s for s in (page(slug, 'series', k) for k in item['series']) if s]
    return out


def hub(slug: str) -> dict | None:
    """What the topic's page adds: its doors and its tools, each shown when what it leads to may be shown (a tool that
    runs on the phone once a person checked it), and the reform's one line."""
    content = load(slug)
    if content is None:
        return None
    h = content['hub']
    available = {f'{kind}/{key}' for kind in KINDS for key, item in content[kind].items() if shown(item)}

    def keep(entries):
        return [e for e in entries or [] if (reachable(e['to'], available) if e.get('to') else shown(e))]
    changes = [{'key': key, 'title': r.get('title'), **_reform_line(r)} for key, r in content['reform'].items()
               if key != 'reform' and shown(r)]
    tools = keep(h.get('tools'))
    # The emergency's door (T6 of the road tools review), shown when what it leads to may be shown; the learning path
    # (T4), each step a door of this topic named by its title.
    urgent = h.get('urgent')
    if urgent and not reachable(urgent['to'], available | {f'tools/{t["key"]}' for t in tools}):
        urgent = None
    titled = {f'tools/{t["key"]}': t for t in tools} | {f'{kind}/{key}': item for kind in KINDS
                                                         for key, item in content[kind].items() if shown(item)}
    learn = [{'to': ref, 'title': titled[ref]['title'], 'icon': titled[ref].get('icon')} for ref in h.get('learn') or []
             if ref in titled]
    # The beliefs the law contradicts (D3 of the consumer plan), each a short card leading to the page that answers it.
    beliefs = [b for b in h.get('beliefs') or [] if reachable(b['to'], available)]
    # A door may open a tool straight away (the tax's salary door): reachable once that tool is shown.
    doors = [e for e in h.get('events') or [] if reachable(e['to'], available | {f'tools/{t["key"]}' for t in tools})
             or (not e.get('to') and shown(e))]
    return {'events': doors, 'tools': tools, 'urgent': urgent and band(content, urgent), 'learn': learn,
            'beliefs': beliefs, 'doors_title': h.get('doors_title'), 'next': upcoming(content), 'last': latest(content),
            'reform': page(slug, 'reform', 'reform') and _reform_line(content['reform'].get('reform')),
            # A topic with several changes to follow (T14 of the work plan): each one's stage and line; the question
            # that says which of the topic's rules are the reader's (T5), kept on the phone.
            'changes': changes, 'profile': h.get('profile'),
            # How the topic draws its doors' numbers (`tag`: a price tag, the consumer's) and the stages its doors stand in
            # (the consumer-receipt review): passed as written; a stage names doors by their keys.
            'marks': h.get('marks'), 'stages': h.get('stages')}


def band(content: dict, urgent: dict) -> dict:
    """The red band as it is drawn (A7 and C1 of the road-signposted review): its first acts are the answers of the
    journey's steps it names, said once a person may see that journey; its numbers each come with the official page
    that gives them."""
    out = {k: v for k, v in urgent.items() if k != 'acts'}
    acts = urgent.get('acts') or {}
    journey = content.get('journeys', {}).get(acts.get('journey') or '')
    if journey and shown(journey):
        steps = journey.get('steps') or []
        out['acts'] = [steps[i].get('answer') or steps[i]['title'] for i in acts.get('steps') or [] if i < len(steps)]
    return out


def upcoming(content: dict, today: str | None = None) -> list[dict]:
    """The topic's next dated changes (A11 of the road-signposted review): the timeline entries of the changes a reader may
    see that fall after today, soonest first, two at most; the card says the date, never a count of stages. A reform
    (`reform/reform`), a bill or an announcement is not law and never counts."""
    from django.utils import timezone

    today = today or timezone.localdate().isoformat()
    found = [{'date': str(e['date']), 'text': e['text'], 'change': key, 'title': r.get('title')}
             for key, r in content.get('reform', {}).items() if key != 'reform' and shown(r)
             and r.get('stage') not in ('bill', 'announced')
             for e in r.get('timeline') or [] if str(e.get('date', '')) > today and e.get('text')]
    return sorted(found, key=lambda e: e['date'])[:2]


def latest(content: dict, today: str | None = None) -> dict | None:
    """The last dated change already passed (E9 of the work-counted review): the newest timeline entry, up to today, of the
    changes a reader may see, said in words when no change is ahead. A reform (`reform/reform`) is not law and never
    counts."""
    from django.utils import timezone

    today = today or timezone.localdate().isoformat()
    found = [{'date': str(e['date']), 'text': e['text'], 'change': key, 'title': r.get('title')}
             for key, r in content.get('reform', {}).items() if key != 'reform' and shown(r) and r.get('stage') == 'in_force'
             for e in r.get('timeline') or [] if str(e.get('date', '')) <= today and e.get('text')]
    return max(found, key=lambda e: e['date'], default=None)


def calendar(today: str | None = None, ahead: int = 4, behind: int = 5, back_days: int = 240) -> dict:
    """The law's calendar around today, across the topics (30 Oct 2026, the home): the dated entries of the changes a
    reader may see, the next ones soonest first and the latest ones newest first, one an entry's change on each side. A
    bill's or an announcement's dates are not law and never count. Each says its topic, the change's page and, when its
    entry cites one, the text it is about."""
    from datetime import date, timedelta

    from django.utils import timezone

    from apps.topics.services import topics as every

    today = today or timezone.localdate().isoformat()
    since = (date.fromisoformat(today) - timedelta(days=back_days)).isoformat()
    events = []
    for t in every.load():
        content = load(t['slug'])
        for key, r in (content or {}).get('reform', {}).items():
            if key == 'reform' or not shown(r) or r.get('stage') in ('bill', 'announced'):
                continue
            for e in r.get('timeline') or []:
                day = str(e.get('date', ''))
                if not day or not e.get('text') or day < since:
                    continue
                text = next((c.rsplit('/', 1)[0] for c in e.get('cites') or [] if '/art_' in c), None)
                events.append({'date': day, 'label': e.get('short') or r.get('title'), 'title': r.get('title'),
                               'topic': {'slug': t['slug'], 'name': t.get('short') or t['name']}, 'change': key,
                               'path': f"/topics/{t['slug']}/reform/{key}", 'text': text, 'stage': r.get('stage'),
                               'line': r.get('line')})

    def one_each(rows):
        seen = set()
        return [e for e in rows if (e['topic']['slug'], e['change']) not in seen and not seen.add((e['topic']['slug'], e['change']))]
    return {'today': today,
            'ahead': one_each(sorted((e for e in events if e['date'] > today), key=lambda e: e['date']))[:ahead],
            'behind': one_each(sorted((e for e in events if e['date'] <= today), key=lambda e: e['date'], reverse=True))[:behind]}


def reachable(ref: str, available: set[str]) -> bool:
    """An item may be shown: one of this topic's, or another topic's («family:journeys/divorce», H17 of the housing
    plan), as that topic shows it."""
    if ':' not in ref:
        return ref in available
    other, own = ref.split(':', 1)
    content = load(other)
    if content is None or '/' not in own:
        return False
    kind, key = own.split('/', 1)
    # Another topic's tool («tax:tools/own») stands in its hub, shown as that topic shows it.
    item = (next((t for t in content['hub'].get('tools') or [] if t['key'] == key), None) if kind == 'tools'
            else content.get(kind, {}).get(key))
    return item is not None and shown(item)


def _reform_line(r: dict | None) -> dict | None:
    if not r:
        return None
    return {'stage': r.get('stage'), 'checked_on': r.get('checked_on'), 'line': r.get('line')}


def door_path(slug: str, d: dict) -> tuple[str, str, str]:
    """Where a door of `slug`'s folder leads: (its topic, the item within it, the address), a door of another topic's
    item («work:journeys/…») to that topic's page, the reform's own door to the reform."""
    ref = d.get('to') or f'tools/{d["key"]}'
    topic, own = ref.split(':', 1) if ':' in ref else (slug, ref)
    return topic, own, f'/topics/{topic}/reform' if own == 'reform/reform' else f'/topics/{topic}/{own}'


def moments(today: str, most: int = 6) -> list[dict]:
    """The topics page (30 Oct 2026): each topic's moments as people say them («طردوني», «زاد
    عليا فالكرا»), each with the one line that answers it, the first `most` in its folder's order, how many it has, and
    its next dated change. Only what may be shown; from the folders alone, no query."""
    from apps.topics.services import topics as every

    out = []
    for t in every.load():
        h = hub(t['slug'])
        doors = [{'key': d['key'], 'title': d['title'], 'lead': d.get('lead'), 'path': door_path(t['slug'], d)[2]}
                 for d in (h or {}).get('events') or [] if d.get('moment', True)]
        nxt = upcoming(load(t['slug']), today)[:1] if h else []
        out.append({'slug': t['slug'], 'doors': doors[:most], 'count': len(doors),
                    'next': (nxt and {'date': nxt[0]['date'], 'title': nxt[0]['title'],
                                      'path': f"/topics/{t['slug']}/reform/{nxt[0]['change']}"}) or None})
    return out
