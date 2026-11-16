"""The counts from before 16 Nov 2026 brought in (`import_past_counts`, services/past.py): the request log's day totals
and the tool counter written as `past.*`, the same rows each time it runs, and nothing of a city or a person."""
import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

import manage
from apps.analytics.models import DayCount
from apps.analytics.services import past
from apps.topics.models import ToolUse

pytestmark = pytest.mark.django_db


def row(day='2026-10-25', kind='page', bot=False, country='MA', assistant='', rows=1, people=1):
    return {'day': day, 'kind': kind, 'bot': bot, 'country': country, 'assistant': assistant, 'rows': rows,
            'people': people, 'articles': 0}


LOG = [row(rows=10, people=4), row(country='FR', rows=3, people=2), row(country='', rows=1, people=1),
       row(bot=True, country='US', rows=50, people=9), row(kind='api', rows=40, people=4),
       row(kind='mcp', assistant='Claude', country='', rows=7, people=0),
       row(day='2026-11-15', kind='mcp', assistant='ChatGPT', rows=2, people=0),
       row(day='2026-11-15', kind='admin', bot=True, rows=6, people=1)]


def written() -> dict:
    return {(c.day.isoformat(), c.metric, c.key): c.count for c in DayCount.objects.all()}


def bring(tmp_path, rows=LOG) -> str:
    file = tmp_path / 'past.json'
    file.write_text(json.dumps(rows), encoding='utf-8')
    out = StringIO()
    call_command('import_past_counts', '--file', str(file), stdout=out)
    return out.getvalue()


def test_the_day_totals_become_past_counts(tmp_path):
    ToolUse.objects.bulk_create([ToolUse(on=date(2026, 11, 2), path='/topics/road/tools/fine', event='open', count=6),
                                 ToolUse(on=date(2026, 11, 2), path='/topics/road/tools/fine', event='share', count=2),
                                 ToolUse(on=date(2026, 11, 16), path='/topics/road/tools/fine', event='open', count=99)])
    said = bring(tmp_path)
    assert said == "11 counts from the request log's days, 2 from the tool counter\n"
    assert written() == {
        ('2026-10-25', 'past.requests', 'people'): 61, ('2026-10-25', 'past.requests', 'machines'): 50,
        ('2026-10-25', 'past.pages', ''): 14, ('2026-10-25', 'past.readers', ''): 7,
        ('2026-10-25', 'past.country', 'MA'): 4, ('2026-10-25', 'past.country', 'FR'): 2,
        ('2026-10-25', 'past.country', 'XX'): 1, ('2026-10-25', 'past.assistant', 'Claude'): 7,
        ('2026-11-15', 'past.requests', 'people'): 2, ('2026-11-15', 'past.requests', 'machines'): 6,
        ('2026-11-15', 'past.assistant', 'ChatGPT'): 2,
        ('2026-11-02', 'past.tool', '/topics/road/tools/fine:open'): 6,
        ('2026-11-02', 'past.tool', '/topics/road/tools/fine:share'): 2,
    }


def test_bringing_them_in_again_writes_the_same_rows_and_replaces_its_own(tmp_path):
    DayCount.objects.create(day=date(2026, 11, 14), metric='visits', key='', count=5)       # not its own: kept
    bring(tmp_path)
    once = written()
    bring(tmp_path)
    assert written() == once
    bring(tmp_path, [row(rows=2, people=2)])
    assert written() == {('2026-11-14', 'visits', ''): 5, ('2026-10-25', 'past.requests', 'people'): 2,
                         ('2026-10-25', 'past.pages', ''): 2, ('2026-10-25', 'past.readers', ''): 2,
                         ('2026-10-25', 'past.country', 'MA'): 2}


def test_a_file_that_cannot_be_read_is_refused_and_nothing_changes(tmp_path):
    bring(tmp_path)
    before = written()
    for text in ('not json', json.dumps([{'day': '2026-10-25'}])):
        bad = tmp_path / 'bad.json'
        bad.write_text(text, encoding='utf-8')
        with pytest.raises(CommandError, match=r'bad\.json'):
            call_command('import_past_counts', '--file', str(bad), stdout=StringIO())
    with pytest.raises(CommandError, match=r'absent\.json'):
        call_command('import_past_counts', '--file', str(tmp_path / 'absent.json'), stdout=StringIO())
    assert written() == before


@pytest.mark.skipif(not past.FILE.exists(), reason="the live site's own counts are not in the public tree")
def test_the_committed_file_holds_day_totals_and_nothing_of_a_city_or_a_person():
    rows = json.loads(past.FILE.read_text(encoding='utf-8'))
    assert rows and all(set(r) == {'day', 'kind', 'bot', 'country', 'assistant', 'rows', 'people', 'articles'}
                        for r in rows)
    assert min(r['day'] for r in rows) == '2026-10-25' and max(r['day'] for r in rows) == '2026-11-15'
    counted = past.from_log(rows)
    assert {metric for _, metric, _ in counted} == {'past.requests', 'past.pages', 'past.readers', 'past.country',
                                                    'past.assistant'}
    assert all(len(key) == 2 for _, metric, key in counted if metric == 'past.country')


def test_bringing_them_in_never_empties_the_kept_answers():
    """No answer reads the day counts: after any command not in READ_ONLY, manage.py empties every kept answer."""
    assert 'import_past_counts' in manage.READ_ONLY
