"""The database's door (/api/open/): the three positions; while it is given on request, a data file only to an access
that includes the database (by its account, its key or a ticket), each one kept as a Download and five a day; the
manifest with its own hash; the receipt; nginx sending the file when OPEN_DATA_ACCEL is set; and a cost in queries that
does not grow with what was taken before."""
import json
from datetime import date, timedelta

import pytest
from django.core import signing
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.tests.conftest import make_user, signed_in
from apps.opendata.models import Access, ApiKey, Download, hash_key
from apps.opendata.services import downloads, dump, editions, keys
from apps.opendata.tests.helpers import accepted, keyed
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db
DATA = sorted(editions.DATA)


def errors(r):
    return [(e['field'], e['code']) for e in r.json()['errors']]


@pytest.fixture
def edition(settings, tmp_path):
    """One text, its edition written, the door given on request."""
    settings.OPEN_DATA_DIR = tmp_path / 'open'
    settings.OPEN_DATA = 'request'
    settings.OPEN_DATA_ACCEL = ''
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26', number_as_printed='12.26',
                               title_ar='قانون رقم 12.26', first_published_in=issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 8, 10),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body='نص.')
    return editions.read(dump.write_dump(log=lambda m: None))


def holder(*, data=True, api=False, name='holder'):
    access = accepted(data=data, api=api, username=name)
    return access, access.user


def ticket_of(client, file, edition='latest'):
    r = client.post('/api/open/ticket/', {'file': file, 'edition': edition}, format='json')
    assert r.status_code == 200, r.content
    return r.json()['url']


def test_on_request_the_files_that_describe_an_edition_go_to_anyone(edition, api):
    for name in editions.DESCRIBE:
        r = api.get(f'/api/open/latest/{name}')
        assert r.status_code == 200 and r.content == (edition.folder / name).read_bytes(), name
        assert r.get('Cache-Control', '').startswith('public'), name
    assert api.get(f'/api/open/{edition.date}/README.md').status_code == 200
    manifest = api.get('/api/open/').json()
    assert manifest['sha256'] == edition.sha256 and manifest['format'] == editions.FORMAT
    assert manifest['editions'] == [{'date': edition.date, 'sha256': edition.sha256}]
    assert manifest['files']['texts.jsonl.gz'] == edition.file('texts.jsonl.gz')


def test_on_request_a_data_file_asks_who_is_calling(edition, api):
    # Nobody named.
    r = api.get('/api/open/latest/texts.jsonl.gz')
    assert (r.status_code, errors(r)) == (401, [('open_data', 'request')]) and r['Cache-Control'] == 'private'
    # Signed in without an access, with an access that holds the API alone, or one that ended.
    assert errors(signed_in(api, make_user('reader')).get('/api/open/latest/texts.jsonl.gz')) == [
        ('open_data', 'no_access')]
    _, user = holder(data=False, api=True, name='apis')
    assert signed_in(api, user).get('/api/open/latest/texts.jsonl.gz').status_code == 403
    access, user = holder(name='ended')
    Access.objects.filter(pk=access.pk).update(state=Access.State.ENDED)
    assert signed_in(api, user).get('/api/open/latest/akn.zip').status_code == 403
    assert not Download.objects.exists()


def test_the_account_its_key_and_its_ticket_each_take_a_file_and_each_is_kept(edition, api):
    access, user = holder()
    client = signed_in(api, user)
    r = client.get('/api/open/latest/texts.jsonl.gz')
    assert r.status_code == 200 and b''.join(r.streaming_content) == (edition.folder / 'texts.jsonl.gz').read_bytes()
    assert r['Cache-Control'] == 'no-store' and r['Content-Disposition'].startswith('attachment')
    api.force_authenticate(None)
    key = ApiKey.issue(access, 'server')[1]
    assert api.get(f'/api/open/{edition.date}/akn.zip', HTTP_X_API_KEY=key).status_code == 200
    url = ticket_of(signed_in(api, user), 'changes.jsonl.gz')
    api.force_authenticate(None)
    assert url.startswith('/api/open/latest/changes.jsonl.gz?t=')
    assert api.get(url).status_code == 200
    kept = list(Download.objects.order_by('pk').values_list('access_id', 'edition', 'file', 'sha256', 'by'))
    assert kept == [(access.pk, edition.date, 'texts.jsonl.gz', edition.file('texts.jsonl.gz')['sha256'], 'account'),
                    (access.pk, edition.date, 'akn.zip', edition.file('akn.zip')['sha256'], 'key'),
                    (access.pk, edition.date, 'changes.jsonl.gz', edition.file('changes.jsonl.gz')['sha256'], 'account')]


def test_a_real_session_token_is_read_and_one_that_does_not_hold_is_a_401(edition, api):
    _, user = holder()
    token = str(RefreshToken.for_user(user).access_token)
    assert api.get('/api/open/latest/issues.jsonl.gz', HTTP_AUTHORIZATION=f'Bearer {token}').status_code == 200
    r = api.get('/api/open/latest/issues.jsonl.gz', HTTP_AUTHORIZATION='Bearer not-a-token')
    assert r.status_code == 401 and r['WWW-Authenticate'].startswith('Bearer')


def test_a_key_that_opens_nothing_or_holds_the_api_alone_takes_nothing(edition, api):
    r = api.get('/api/open/latest/texts.jsonl.gz', HTTP_X_API_KEY='law_not-a-key')
    assert (r.status_code, errors(r)) == (401, [('key', 'invalid')]) and r['Cache-Control'] == 'private'
    access, key = keyed(username='apionly')         # the API, not the database
    r = api.get('/api/open/latest/texts.jsonl.gz', HTTP_X_API_KEY=key)
    assert (r.status_code, errors(r)) == (403, [('open_data', 'no_access')])
    # What a key opens is kept a minute (services/keys.py): these rows are changed behind its back, so it is forgotten.
    Access.objects.filter(pk=access.pk).update(ends_on=timezone.localdate() - timedelta(days=1))
    keys.forget(hash_key(key))
    assert errors(api.get('/api/open/latest/texts.jsonl.gz', HTTP_X_API_KEY=key)) == [('key', 'expired')]
    Access.objects.filter(pk=access.pk).update(state=Access.State.ENDED)
    keys.forget(hash_key(key))
    assert errors(api.get('/api/open/latest/texts.jsonl.gz', HTTP_X_API_KEY=key)) == [('key', 'ended')]
    assert not Download.objects.exists()


def test_a_ticket_opens_one_file_of_one_edition_for_ten_minutes_and_only_while_its_access_lasts(edition, api,
                                                                                               monkeypatch):
    access, user = holder()
    url = ticket_of(signed_in(api, user), 'texts.jsonl.gz', edition.date)
    api.force_authenticate(None)
    token = url.split('?t=')[1]
    assert url.startswith(f'/api/open/{edition.date}/texts.jsonl.gz?t=')
    # Another file, a forged token.
    assert errors(api.get(f'/api/open/latest/akn.zip?t={token}')) == [('ticket', 'invalid')]
    assert errors(api.get('/api/open/latest/akn.zip?t=forged')) == [('ticket', 'invalid')]
    # Past ten minutes.
    monkeypatch.setattr(downloads, 'TICKET_SECONDS', -1)
    r = api.get(url)
    assert (r.status_code, errors(r)) == (401, [('ticket', 'expired')])
    monkeypatch.setattr(downloads, 'TICKET_SECONDS', 600)
    assert api.get(url).status_code == 200
    # The access ended since.
    Access.objects.filter(pk=access.pk).update(state=Access.State.ENDED)
    assert errors(api.get(url)) == [('open_data', 'no_access')]
    # A signed token that names something else is no ticket either.
    other = signing.dumps({'a': 'x', 'e': edition.date, 'f': 'texts.jsonl.gz'}, salt=downloads.SALT)
    assert errors(api.get(f'/api/open/latest/texts.jsonl.gz?t={other}')) == [('open_data', 'no_access')]


def test_a_ticket_is_asked_for_a_data_file_or_the_receipt_of_an_edition_held(edition, api):
    _, user = holder()
    client = signed_in(api, user)
    for body, refusal in (({'file': 'manifest.json'}, ('file', 'invalid')), ({'file': ['akn.zip']}, ('file', 'invalid')),
                          ({}, ('file', 'invalid')), ({'file': 'akn.zip', 'edition': '2020-01-01'}, ('edition', 'unknown')),
                          ({'file': 'akn.zip', 'edition': ['latest']}, ('edition', 'unknown'))):
        r = client.post('/api/open/ticket/', body, format='json')
        assert (r.status_code, errors(r)) == (400, [refusal]), body
    assert ticket_of(client, downloads.RECEIPT).startswith('/api/open/latest/RECEIPT.txt?t=')
    assert signed_in(api, make_user('nobody')).post('/api/open/ticket/', {'file': 'akn.zip'}, format='json').status_code == 403
    api.force_authenticate(None)
    assert api.post('/api/open/ticket/', {'file': 'akn.zip'}, format='json').status_code == 401


def test_five_files_a_day_leave_an_access_and_the_same_file_again_is_not_counted(edition, api, settings):
    access, key = keyed(api=False, data=True)
    for name in DATA[:5]:
        assert api.get(f'/api/open/latest/{name}', HTTP_X_API_KEY=key).status_code == 200, name
    # Resumed, or taken again: the same file of the same edition that day.
    assert api.get(f'/api/open/latest/{DATA[0]}', HTTP_X_API_KEY=key).status_code == 200
    r = api.get(f'/api/open/latest/{DATA[5]}', HTTP_X_API_KEY=key)
    assert (r.status_code, errors(r)) == (429, [('open_data', 'daily')])
    assert 0 < int(r['Retry-After']) <= 86400
    assert Download.objects.filter(access=access).count() == 5
    # A look at a file's size takes nothing.
    assert api.head(f'/api/open/latest/{DATA[6]}', HTTP_X_API_KEY=key).status_code == 200
    # Yesterday's files are yesterday's.
    Download.objects.update(at=timezone.now() - timedelta(days=1))
    assert api.get(f'/api/open/latest/{DATA[5]}', HTTP_X_API_KEY=key).status_code == 200


def test_open_every_file_goes_to_anyone_and_nothing_is_kept(edition, api, settings):
    settings.OPEN_DATA = 'open'
    for name in DATA:
        assert api.get(f'/api/open/latest/{name}').status_code == 200, name
    assert errors(api.get('/api/open/latest/akn.zip', HTTP_X_API_KEY='law_not-a-key')) == [('key', 'invalid')]
    assert not Download.objects.exists()
    # The receipt still names its holder: it asks who is calling.
    assert api.get(f'/api/open/{edition.date}/RECEIPT.txt').status_code == 401


def test_nginx_sends_the_file_when_django_names_its_internal_address(edition, api, settings):
    settings.OPEN_DATA_ACCEL = '/_open/'
    _, key = keyed(api=False, data=True)
    r = api.get('/api/open/latest/versions.jsonl.gz', HTTP_X_API_KEY=key)
    assert r.status_code == 200 and r.content == b''
    assert r['X-Accel-Redirect'] == f'/_open/{edition.date}/versions.jsonl.gz'
    assert r['Content-Type'] == 'application/gzip' and r['Cache-Control'] == 'no-store' and 'ETag' not in r
    assert r['Content-Disposition'] == f'attachment; filename="3adala-{edition.date}-versions.jsonl.gz"'


def test_only_an_edition_of_todays_format_is_served(edition, api, settings):
    old = editions.root() / '2026-10-20'
    old.mkdir()
    (old / 'manifest.json').write_text(json.dumps({'date': '2026-10-20', 'licence': 'CC BY 4.0'}))
    (old / 'texts.jsonl.gz').write_bytes(b'old')
    settings.OPEN_DATA = 'open'
    for url in ('/api/open/2026-10-20/texts.jsonl.gz', '/api/open/2026-10-20/manifest.json', '/api/open/2027-01-01/akn.zip',
                '/api/open/latest/secrets.txt', '/api/open/latest/..', '/api/open/tomorrow/akn.zip'):
        assert api.get(url).status_code == 404, url
    (edition.folder / 'README.md').unlink()
    assert api.get('/api/open/latest/README.md').status_code == 404
    (edition.folder / 'manifest.json').unlink()
    assert api.get('/api/open/').status_code == 404


def test_the_receipt_names_the_holder_the_edition_and_its_hash(edition, api):
    access, user = holder(name='receipt')
    r = signed_in(api, user).get(f'/api/open/{edition.date}/RECEIPT.txt')
    assert r.status_code == 200 and r['Cache-Control'] == 'private' and r['Content-Type'].startswith('text/plain')
    text = r.content.decode()
    for said in (access.request.name, f'{access.pk}', edition.date, edition.sha256, access.request.terms, 'ODbL 1.0',
                 timezone.localdate().isoformat(), 'Titulaire', 'الحامل'):
        assert said in text, said
    assert not Download.objects.exists()
    url = ticket_of(signed_in(api, user), downloads.RECEIPT, edition.date)
    api.force_authenticate(None)
    assert edition.sha256 in api.get(url).content.decode()


def test_a_data_file_costs_the_same_queries_whatever_was_taken_before(edition, api, django_assert_max_num_queries):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _, key = keyed(api=False, data=True)
    costs = []
    for name in DATA[:5]:
        with CaptureQueriesContext(connection) as queries:
            assert api.get(f'/api/open/latest/{name}', HTTP_X_API_KEY=key).status_code == 200
        costs.append(len(queries))
    # The key (asked of the database once, then kept a minute), the day's files, the new row.
    assert costs[0] <= 4 and len(set(costs[1:])) == 1 and costs[1] <= costs[0], costs
    with django_assert_max_num_queries(0):
        assert api.get('/api/open/').status_code == 200
        assert api.get('/api/open/latest/manifest.json').status_code == 200
