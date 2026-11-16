"""The counts kept before the measures began (the analytics review, 15 Nov 2026: brought in, without the city), written
into the day counts as `past.*`, so the staff's page sets the first weeks beside the new counts.

Two sources:
- data/past_counts.json, the removed request log's day totals (25 Oct to 15 Nov 2026): a row per day, kind of request,
  machine or not, country and assistant, with its requests (`rows`), its people (the log's keys of a day, `people`)
  and its articles. No city, no person, no address;
- the topics' tool counter (apps.topics ToolUse), its days before FIRST_DAY.

Written, by day:
- `past.pages`: the pages people were shown (kind page, no machine), their requests;
- `past.readers`: the people of those pages. A person was a key of one day in one country: one seen in two countries
  that day is in two rows, and so counted twice;
- `past.requests`, key `people` or `machines`: the requests of every kind;
- `past.country`, key the country (XX when the log had none): the people shown pages;
- `past.assistant`, key the assistant as the log named it: the assistants' calls (kind mcp);
- `past.tool`, key `<path>:<event>`: the tool counter's counts.

Bringing them in again replaces whatever `past.*` held: the same in, the same out."""
import json
from collections import Counter
from datetime import date
from pathlib import Path

from django.db import transaction

from apps.analytics.models import DayCount
from apps.topics.models import ToolUse

PREFIX = 'past.'
# The measures' first day: what the tool counter holds from it on is counted by the measures (tool.step).
FIRST_DAY = date(2026, 11, 16)
FILE = Path(__file__).resolve().parent.parent / 'data' / 'past_counts.json'


def from_log(rows: list[dict]) -> Counter:
    """{(day, metric, key): count} from the request log's day totals."""
    counts: Counter = Counter()
    for r in rows:
        day, n, people = date.fromisoformat(r['day']), int(r['rows']), int(r['people'])
        counts[day, 'past.requests', 'machines' if r['bot'] else 'people'] += n
        if r['kind'] == 'page' and not r['bot']:
            counts[day, 'past.pages', ''] += n
            counts[day, 'past.readers', ''] += people
            counts[day, 'past.country', r['country'] or 'XX'] += people
        if r['kind'] == 'mcp':
            counts[day, 'past.assistant', r['assistant']] += n
    return counts


def from_tools() -> Counter:
    """{(day, metric, key): count} from the tool counter, in one query."""
    counts: Counter = Counter()
    for on, path, event, n in ToolUse.objects.filter(on__lt=FIRST_DAY).values_list('on', 'path', 'event', 'count'):
        counts[on, 'past.tool', f'{path}:{event}'] += n
    return counts


def bring_in(path: Path = FILE) -> dict[str, int]:
    """`past.*` written again from the file and the tool counter: how many counts each gave."""
    log, tools = from_log(json.loads(Path(path).read_text(encoding='utf-8'))), from_tools()
    with transaction.atomic():
        DayCount.objects.filter(metric__startswith=PREFIX).delete()
        DayCount.objects.bulk_create(DayCount(day=day, metric=metric, key=key, count=n)
                                     for (day, metric, key), n in (log | tools).items() if n > 0)
    return {'log': len(log), 'tools': len(tools)}
