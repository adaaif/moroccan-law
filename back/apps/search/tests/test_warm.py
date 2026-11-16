"""After a deploy the last 7 days' most shown pages are asked again as a machine (`warm_answers`, 31 Oct 2026; read from
the measures' day counts since 15 Nov 2026), a law's with the text answer the app reads; with no count, nothing."""
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

import manage
from apps.analytics.models import DayCount
from apps.analytics.services import record

pytestmark = pytest.mark.django_db

TODAY = date(2026, 11, 15)


@pytest.fixture
def asked(monkeypatch):
    monkeypatch.setattr(timezone, 'localdate', lambda *a: TODAY)
    seen = []

    class Answer:
        def read(self):
            return b'{}'

    def urlopen(request, timeout):
        seen.append((request.full_url, request.get_header('User-agent'), request.get_header('Host')))
        if request.full_url.endswith('/broken'):
            raise OSError('refused')
        return Answer()

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    return seen


def warm(*args) -> str:
    out = StringIO()
    call_command('warm_answers', '--base', 'http://127.0.0.1:8041', '--host', 'example.org', *args, stdout=out)
    return out.getvalue()


def test_the_weeks_most_shown_pages_are_asked_again_as_a_machine(asked):
    for day, path, n in ((TODAY - timedelta(1), '/topics/housing', 5), (TODAY - timedelta(2), '/ma/loi/2-00/art_1', 9),
                         (TODAY - timedelta(7), '/topics/housing', 6), (TODAY - timedelta(3), '/broken', 1),
                         (TODAY - timedelta(8), '/library', 50), (TODAY, '/search', 70)):
        DayCount.objects.create(day=day, metric='page.path', key=path, count=n)
    DayCount.objects.create(day=TODAY - timedelta(1), metric='page.missing.path', key='/gone', count=80)
    said = warm()
    assert [url for url, _, _ in asked] == ['http://127.0.0.1:8041/topics/housing',
                                            'http://127.0.0.1:8041/ma/loi/2-00/art_1',
                                            'http://127.0.0.1:8041/api/corpus/at/ma/loi/2-00/art_1/?window=30',
                                            'http://127.0.0.1:8041/broken']
    assert all(host == 'example.org' for _, _, host in asked)
    assert all(record.BOTS.search(agent) for _, agent, _ in asked)         # the measures' door leaves it out
    assert '3 pages warmed (4 answers)' in said and '1 failed' in said
    asked.clear()
    assert '1 pages warmed' in warm('--top', '1') and [url for url, _, _ in asked] == ['http://127.0.0.1:8041/topics/housing']


def test_with_no_count_yet_nothing_is_warmed(asked):
    assert 'nothing to warm' in warm() and asked == []


def test_the_warm_up_never_empties_what_it_built():
    """After any command not in READ_ONLY, manage.py empties every kept answer: the warm-up's own, as it ended."""
    assert 'warm_answers' in manage.READ_ONLY
