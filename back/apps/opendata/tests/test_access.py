"""An access's life (services/access.py): ended with its keys at once, in the same few queries however many end;
renewed; expired by the night's job (`end_accesses`), with the letter 30 days before; and the account's own data: its
export holds its requests, accesses, days and downloads but never a key, and its deletion ends its access."""
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import manage
from apps.accounts.services.refusals import Refused
from apps.discussion.tests.conftest import make_user
from apps.opendata.models import Access, AccessDay, ApiKey, Download, Request
from apps.opendata.services import access as accesses
from apps.opendata.services import keys
from apps.opendata.tests.helpers import accepted, asked, keyed

pytestmark = pytest.mark.django_db


@pytest.fixture
def forgotten(monkeypatch):
    """The key hashes `keys.forget` was given."""
    seen = []
    monkeypatch.setattr(keys, 'forget', seen.append)
    return seen


@pytest.fixture
def chief():
    chief = make_user('chief', staff=True)
    chief.is_superuser = True
    chief.save()
    return chief


def test_ending_an_access_ends_its_live_keys_at_once(forgotten, chief, django_capture_on_commit_callbacks):
    access, key = keyed()
    ApiKey.issue(access, 'second')
    old, _ = ApiKey.issue(access, 'old')
    ApiKey.objects.filter(pk=old.pk).update(ended_at=timezone.now() - timedelta(days=3))
    with django_capture_on_commit_callbacks(execute=True) as committed:
        accesses.end(access, Access.Ended.LEAKED, by=chief)
    assert len(committed) == 1                  # dropped again once the writes are committed
    access.refresh_from_db()
    assert (access.state, access.ended_reason, access.ended_by, access.ended_at is not None) == (
        'ended', 'leaked', chief, True)
    assert not ApiKey.objects.filter(access=access, ended_at=None).exists()
    live = set(ApiKey.objects.exclude(pk=old.pk).values_list('key_hash', flat=True))
    assert set(forgotten) == live and len(forgotten) == 2 * len(live)
    with pytest.raises(keys.Refused) as refused:
        keys.read(key)
    assert refused.value.code == 'ended'
    [letter] = mail.outbox
    assert 'ظهر أحد مفاتيحه حيث يقرؤه غيرك.' in letter.body
    accesses.end(access, Access.Ended.TERMS, by=chief)          # ended already: left as it was, no second letter
    access.refresh_from_db()
    assert access.ended_reason == 'leaked' and len(mail.outbox) == 1


def test_an_end_needs_one_of_the_reasons():
    with pytest.raises(Refused):
        accesses.end(accepted(), 'bored')


def test_ending_many_costs_what_ending_one_does(forgotten):
    def ended(n: int) -> int:
        made = [keyed(accepted(username=f'h{n}-{i}', days=-1))[0] for i in range(n)]
        for a in made:
            ApiKey.issue(a, 'second')
        with CaptureQueriesContext(connection) as queries:
            assert len(accesses.end_rows(Access.objects.filter(pk__in=[a.pk for a in made]),
                                         Access.Ended.EXPIRED)) == n
        return len([q for q in queries.captured_queries if not q['sql'].startswith(('SAVEPOINT', 'RELEASE'))])
    assert ended(1) == ended(12) == 5           # the accesses read and ended, their live keys read and ended, one
    # event each in one write
    assert accesses.end_rows(Access.objects.none(), Access.Ended.EXPIRED) == []


def test_the_night_ends_the_accesses_past_their_date_and_warns_those_ending_in_30_days(forgotten, settings):
    settings.SITE_URL = 'https://example.org'
    past, _ = keyed(accepted(username='past', days=-1))
    today_ends = accepted(username='today', days=0)             # its last day is today: still open
    warned = accepted(username='warned', days=accesses.WARN_DAYS, data=True)
    later = accepted(username='later', days=accesses.WARN_DAYS + 1)
    out = StringIO()
    call_command('end_accesses', stdout=out)
    assert out.getvalue() == '1 accesses ended, 1 holders told their access ends in 30 days, 0 requests emptied\n'
    for a, state in ((past, 'ended'), (today_ends, 'live'), (warned, 'live'), (later, 'live')):
        a.refresh_from_db()
        assert a.state == state
    assert past.ended_reason == 'expired' and past.ended_by is None
    assert not ApiKey.objects.filter(access=past, ended_at=None).exists()
    letters = {m.to[0]: m for m in mail.outbox}
    assert len(mail.outbox) == 2 and set(letters) == {'past@example.org', 'warned@example.org'}
    assert 'حلّ تاريخ انتهائه.' in letters['past@example.org'].body
    warning = letters['warned@example.org']
    assert f'{warned.ends_on:%d/%m/%Y}' in warning.subject and 'قاعدة البيانات' in warning.body
    assert 'https://example.org/data/access' in warning.body


def test_the_nights_job_writes_nothing_a_public_answer_reads():
    """After any command not in READ_ONLY, manage.py empties every kept answer; the night's script runs it."""
    assert 'end_accesses' in manage.READ_ONLY
    night = (Path(django_settings.BASE_DIR).parent / 'deploy' / 'nightly.sh').read_text()
    assert 'manage.py end_accesses' in night


def test_renewing_gives_a_new_end_date(chief):
    access = accepted(days=10)
    staff = make_user('staff', staff=True)
    with pytest.raises(Refused):
        accesses.renew(access, staff)
    accesses.renew(access, chief)
    assert access.ends_on == accesses.default_end() and access.renewed_at
    chosen = timezone.localdate() + timedelta(days=45)
    accesses.renew(access, chief, chosen)
    access.refresh_from_db()
    assert access.ends_on == chosen
    for day in (timezone.localdate(), date(2020, 1, 1)):
        with pytest.raises(Refused) as refused:
            accesses.renew(access, chief, day)
        assert refused.value.code == 'past'
    accesses.end(access, Access.Ended.UNUSED, by=chief)
    with pytest.raises(Refused) as refused:
        accesses.renew(access, chief)
    assert refused.value.code == 'ended'


def test_the_export_holds_the_accounts_access_but_never_a_key(api, django_assert_max_num_queries):
    access, key = keyed(data=True)
    asked(access.user, state=Request.State.DECLINED, reason='later', decided_at=timezone.now())
    AccessDay.objects.create(access=access, day=timezone.localdate(), calls=12, articles=40, doors={'v1.search': 12})
    Download.objects.create(access=access, edition='2026-11-01', file='texts.jsonl.gz', sha256='a' * 64, by='key')
    api.force_authenticate(access.user)
    data = api.get('/api/auth/me/export/').json()
    assert [r['state'] for r in data['access_requests']] == ['accepted', 'declined']
    assert data['access_requests'][0]['purpose'] == 'How a code changed over time.'
    [held] = data['accesses']
    assert (held['id'], held['data'], held['state'], held['limits']) == (access.pk, True, 'live',
                                                                       django_settings.ACCESS_SIZES['app'])
    assert data['access_days'] == [{'access': access.pk, 'day': timezone.localdate().isoformat(), 'calls': 12,
                                    'articles': 40, 'doors': {'v1.search': 12}}]
    assert data['downloads'][0]['file'] == 'texts.jsonl.gz'
    text = str(data)
    row = ApiKey.objects.get(access=access)
    assert key not in text and row.key_hash not in text and row.prefix not in text
    with CaptureQueriesContext(connection) as few:
        accesses.export(access.user)
    for _ in range(5):
        a = accepted(username=f'more-{_}')
        Access.objects.filter(pk=a.pk).update(user=access.user, state='ended')
        AccessDay.objects.create(access=a, day=timezone.localdate(), calls=1)
        Download.objects.create(access=a, edition='2026-11-01', file='akn.zip', by='account')
    with django_assert_max_num_queries(len(few)):
        assert len(accesses.export(access.user)['accesses']) == 6


def test_deleting_the_account_ends_its_access_and_empties_its_requests(api, forgotten):
    access, _ = keyed()
    user = access.user
    asked(user, state=Request.State.DECLINED, reason='later', decided_at=timezone.now(), runs_at='https://x.org',
          asked='Who?', answer='Us.')
    api.force_authenticate(user)
    assert api.post('/api/auth/me/delete/', {'password': 'a long secret 2026'}, format='json').status_code == 204
    access.refresh_from_db()
    assert (access.state, access.ended_reason, access.ended_by) == ('ended', 'account', None)
    assert not ApiKey.objects.filter(access=access, ended_at=None).exists() and forgotten
    rows = list(Request.objects.filter(user=user).values('name', 'purpose', 'runs_at', 'asked', 'answer', 'state'))
    assert rows and all(r['name'] == r['purpose'] == r['runs_at'] == r['asked'] == r['answer'] == '' for r in rows)
    assert {r['state'] for r in rows} == {'accepted', 'declined'}
    assert mail.outbox == []                       # no letter to an address being erased
