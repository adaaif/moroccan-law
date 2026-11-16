"""The Monday letter (`analytics_letter`): the week's ten figures beside the week before, in plain text, to
ANALYTICS_LETTER_TO; nothing without an address, a failure said by the command; the report's queries and no more."""
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import manage
from apps.analytics.services import letter, report
from apps.analytics.tests.test_report import NOW, TODAY, a_fortnight, counts
from apps.opendata.services import requests as access_requests

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def monday(monkeypatch):
    monkeypatch.setattr(timezone, 'localdate', lambda *a: TODAY)


def run() -> str:
    out = StringIO()
    call_command('analytics_letter', stdout=out)
    return out.getvalue()


def test_without_an_address_nothing_is_read_or_sent(settings, django_assert_num_queries):
    settings.ANALYTICS_LETTER_TO = []
    with django_assert_num_queries(0):
        assert run() == 'ANALYTICS_LETTER_TO is empty: no letter sent\n'
    assert mail.outbox == []


def test_the_letter_says_the_ten_figures_in_plain_text(settings):
    settings.ANALYTICS_LETTER_TO = ['team@example.org', 'second@example.org']
    settings.SITE_URL = 'https://example.org'
    a_fortnight()
    counts(NOW[0], 'speed.lcp.p75', **{'article:desk': 9000})            # a desk's speed is not the phone's
    assert '«3adala: the week of 8 Nov 2026 to 14 Nov 2026» sent to 2 addresses' in run()
    [sent] = mail.outbox
    assert sent.to == ['team@example.org', 'second@example.org'] and not getattr(sent, 'alternatives', None)     # no HTML
    assert sent.subject == '3adala: the week of 8 Nov 2026 to 14 Nov 2026'
    body = sent.body
    assert 'beside 1 Nov 2026 to 7 Nov 2026.' in body
    assert ' 1. Readers: 70 (before 42, +67%)\n' in body
    assert ' 2. Visits: 140 (before 105, +33%)\n' in body
    assert ' 3. Returning visits: 35.0% (before 20.0%, +15.0 points)\n' in body
    assert ' 4. Pages shown: 350 (before 280, +25%)\n' in body
    assert ' 5. Most read: /ma/loi/65-99/art_53 (84), /topics/road (21)\n' in body
    assert ' 6. Searches on the site: 10 (before 4, +150%); with no result: 20.0% (before 0.0%, +20.0 points)\n' in body
    assert " 7. Assistants' calls: 315 (before 245, +29%)\n" in body
    assert ' 8. Tools opened: 35 (before 35, +0%); reaching a result: 40.0% (before 20.0%, +20.0 points)\n' in body
    assert ' 9. Articles on phones, LCP (median of the daily 75th percentiles): 2,000 ms, good (before 4,500 ms)\n' in body
    assert '10. Errors: 7 in the app, 0 failed API calls, 14 missing pages (before 7, 0, 14)\n' in body
    assert body.rstrip().endswith('The whole report: https://example.org/admin/analytics/')
    assert '<' not in body


def test_an_empty_week_says_none_and_no_measure():
    _, body = letter.letter(TODAY)
    assert ' 3. Returning visits: none (before none)\n' in body and ' 5. Most read: none\n' in body
    assert 'LCP (median of the daily 75th percentiles): no measure\n' in body
    counts(NOW[0], 'speed.lcp.p75', **{'article:phone': 3100})
    counts(NOW[0], 'speed.n', **{'article:phone': 2})
    assert 'percentiles): 3,100 ms, needs work (before none)\n' in letter.letter(TODAY)[1]


def test_a_letter_the_mail_service_refuses_fails_the_command(settings):
    settings.ANALYTICS_LETTER_TO = ['team@example.org']
    settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    settings.EMAIL_HOST, settings.EMAIL_PORT = '127.0.0.1', 9   # nothing listens there, as with no Resend key
    with pytest.raises(CommandError, match='not sent'):
        run()


def test_the_letter_reads_what_the_report_reads(settings):
    settings.ANALYTICS_LETTER_TO = ['team@example.org']
    a_fortnight()
    with CaptureQueriesContext(connection) as seen:
        run()
    assert len(seen.captured_queries) == report.QUERIES + access_requests.QUERIES + access_requests.DECISION_QUERIES


def test_the_letter_never_empties_the_kept_answers():
    """It writes nothing an answer reads: after any command not in READ_ONLY, manage.py empties every kept answer."""
    assert 'analytics_letter' in manage.READ_ONLY


def test_the_letter_lists_the_week_s_decisions_on_access(settings, monkeypatch):
    from datetime import datetime, timedelta

    from apps.discussion.tests.conftest import make_user
    from apps.opendata.models import Event
    from apps.opendata.services import log
    from apps.opendata.tests.helpers import accepted, asked

    settings.ANALYTICS_LETTER_TO = ['team@example.org']
    monkeypatch.setattr(access_requests, 'DECISIONS_SHOWN', 3)
    chief = make_user('chief', staff=True)
    request = asked(username='salma')
    access = accepted(username='hamid')
    in_week = timezone.make_aware(datetime(2026, 11, 10, 12))

    def noted(act, at, **kw):
        Event.objects.filter(pk=log.note(act, **kw).pk).update(at=at)
    noted('accepted', in_week, by=chief, request=request, access=access, api=True, data=True, size='app',
          ends_on='2027-11-10')
    noted('asked', in_week + timedelta(hours=1), by=chief, request=request, line='Which lab?')
    noted('ended', in_week + timedelta(hours=2), by=access.user, access=access, reason='asked')     # its holder's
    noted('ended', in_week + timedelta(hours=3), access=access, reason='expired')                  # the night's
    noted('renewed', in_week + timedelta(hours=4), by=chief, access=access, ends_on='2027-12-01')
    noted('declined', in_week + timedelta(hours=5), by=chief, request=request, reason='scope')
    noted('declined', timezone.make_aware(datetime(2026, 11, 3, 9)), by=chief, request=request, reason='later')
    _, body = letter.letter(TODAY)
    assert ('The staff\'s decisions on access this week:\n'
            '- chief accepted A research group (salma): the API and the database, size app, until 2027-11-10.\n'
            '- chief asked for more of A research group (salma): asked «Which lab?».\n'
            '- chief renewed the access of A research group (hamid): until 2027-12-01.\n'
            '- and 1 more.\n') in body
    Event.objects.all().delete()
    assert 'The staff\'s decisions on access this week: none.\n' in letter.letter(TODAY)[1]
