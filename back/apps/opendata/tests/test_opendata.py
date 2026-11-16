"""Open data: the dump (JSON lines, Akoma Ntoso, manifest, licence), its download, the public API's limits
and the keys that raise them."""
import gzip
import json
import zipfile
from datetime import date
from xml.dom import minidom

import pytest
from django.core.cache import cache

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.opendata.models import ApiKey
from apps.opendata.tests.helpers import keyed
from apps.opendata.services.dump import write_dump
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


@pytest.fixture
def law():
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10))
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26',
                               number_as_printed='12.26', title_ar='قانون رقم 12.26 يتعلق بالصحافة',
                               first_published_in=issue, signed_on=date(2026, 7, 1))
    v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 8, 10),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body='**نص** أول.')
    return text


def test_the_dump(law, settings, tmp_path, api):
    settings.OPEN_DATA_DIR = tmp_path
    settings.OPEN_DATA = 'open'
    out = write_dump(log=lambda m: None)
    record = json.loads(gzip.open(out / 'texts.jsonl.gz', 'rt').readline())
    assert record['path'] == '/ma/loi/12-26' and record['articles'][0]['path'] == '/ma/loi/12-26/art_1'
    assert record['source'] == {'issue': '7533', 'edition': 'general_ar', 'date': '2026-08-10', 'page': None,
                                'sha256': None}
    xml = zipfile.ZipFile(out / 'akn.zip').read('akn_ma_act_loi_12-26.xml')
    doc = minidom.parseString(xml)
    assert doc.getElementsByTagName('FRBRuri')[0].getAttribute('value') == '/akn/ma/act/loi/12-26'
    assert doc.getElementsByTagName('num')[0].firstChild.data == 'المادة الأولى'
    manifest = api.get('/api/open/').json()
    assert manifest['texts'] == 1 and set(manifest['files']) == {
        'texts.jsonl.gz', 'versions.jsonl.gz', 'french.jsonl.gz', 'changes.jsonl.gz', 'issues.jsonl.gz',
        'aliases.jsonl.gz', 'akn.zip', 'LICENCE.txt', 'README.md', 'schema.json', 'CHANGELOG.md'}
    r = api.get('/api/open/latest/akn.zip')
    assert r.status_code == 200 and r['Content-Disposition'].startswith('attachment')
    assert api.get('/api/open/latest/../../etc').status_code == 404


def test_each_record_says_what_kind_of_version_it_holds_and_when(law, settings, tmp_path, api):
    # The newest version of a text may be a consolidation, a machine's or a translation from the official French:
    # the dump says which, as the site does, and when it stands.
    settings.OPEN_DATA_DIR = tmp_path
    settings.OPEN_DATA = 'open'
    Version.objects.filter(text=law).update(valid_to=date(2026, 9, 1))
    machine = Version.objects.create(text=law, language='ar', valid_from=date(2026, 9, 1),
                                     consolidation=Consolidation.MACHINE)
    Article.objects.create(version=machine, order=1, label='المادة الأولى', number='1', eid='art_1', body='نص محين.')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7410, date=date(2025, 6, 2))
    translated = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-1', type='decree', number='2-25-1',
                                     title_ar='مرسوم', first_published_in=issue)
    v = Version.objects.create(text=translated, language='ar', valid_from=date(2025, 6, 2), translated_from='fr',
                               consolidation=Consolidation.TRANSLATION)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body='ترجمة.')
    out = write_dump(log=lambda m: None)
    records = {r['akn_uri']: r for r in map(json.loads, gzip.open(out / 'texts.jsonl.gz', 'rt'))}
    assert records[law.akn_uri]['version'] == {'kind': 'machine', 'language': 'ar', 'valid_from': '2026-09-01',
                                               'valid_to': None, 'translated_from': None, 'file': None, 'pages': None}
    assert records[translated.akn_uri]['version']['kind'] == 'translation'
    assert records[translated.akn_uri]['version']['translated_from'] == 'fr'
    manifest = json.loads((out / 'manifest.json').read_text())
    assert {'as_published', 'machine', 'translation', 'bill'} <= set(manifest['version_kinds'])
    xml = minidom.parseString(zipfile.ZipFile(out / 'akn.zip').read('akn_ma_act_decret_2-25-1.xml'))
    assert xml.getElementsByTagName('FRBRauthoritative')[0].getAttribute('value') == 'false'
    own = xml.getElementsByTagName('law:version')[0]
    assert (own.getAttribute('kind'), own.getAttribute('translatedFrom')) == ('translation', 'fr')
    consolidated = minidom.parseString(zipfile.ZipFile(out / 'akn.zip').read('akn_ma_act_loi_12-26.xml'))
    assert consolidated.getElementsByTagName('law:version')[0].getAttribute('kind') == 'machine'


def test_closed(law, settings, tmp_path, api):
    """Closed (2 Nov 2026): the dump on disk is kept, nothing of it is served; the figures still are."""
    settings.OPEN_DATA_DIR = tmp_path
    settings.OPEN_DATA = 'closed'
    out = write_dump(log=lambda m: None)
    closed = {'errors': [{'field': 'open_data', 'code': 'closed'}]}
    for url in ('/api/open/', '/api/open/latest/texts.jsonl.gz', '/api/open/latest/manifest.json',
                f'/api/open/{out.name}/README.md', f'/api/open/{out.name}/RECEIPT.txt'):
        r = api.get(url)
        assert (r.status_code, r.json()) == (403, closed)
    assert api.get('/api/open/about/').status_code == 200


def test_limits_and_keys(law, settings, api):
    cache.clear()
    settings.PUBLIC_API_RATES = {'anonymous': '2/min'}
    settings.OPEN_DATA = 'request'
    # The machine's own jobs are not counted…
    assert [api.get('/api/corpus/issues/', REMOTE_ADDR='127.0.0.1').status_code for _ in range(3)] == [200] * 3
    # …the public, coming through the proxy, is.
    seen = [api.get('/api/corpus/issues/', HTTP_X_FORWARDED_FOR='41.92.1.2').status_code for _ in range(3)]
    assert seen == [200, 200, 429]
    # A key is counted on its access's own minute (four for this partner), not on the address it comes from.
    _, key = keyed(size='partner', minute=4)
    answers = [api.get('/api/corpus/issues/', HTTP_X_API_KEY=key, HTTP_X_FORWARDED_FOR='41.92.1.2') for _ in range(5)]
    assert [r.status_code for r in answers] == [200, 200, 200, 200, 429]
    assert answers[-1].json() == {'errors': [{'field': 'key', 'code': 'minute'}]}
    assert 1 <= int(answers[-1]['Retry-After']) <= 60
    assert ApiKey.objects.get().key_hash != key        # only the hash is kept


def test_about_counts_the_newest_version_and_gives_the_address(law, settings, api):
    cache.clear()
    settings.CONTACT_EMAIL = 'contact@example.org'
    newer = Version.objects.create(text=law, language='ar', valid_from=date(2026, 9, 1),
                                   consolidation=Consolidation.AS_PUBLISHED)
    for order in (1, 2):
        Article.objects.create(version=newer, order=order, label=f'المادة {order}', number=str(order), body='نص.')
    about = api.get('/api/open/about/').json()
    assert (about['texts'], about['articles'], about['issues']) == (1, 2, 1)
    assert about['contact'] == 'contact@example.org' and about['corrections'] == 0



def test_about_gives_the_codes_repository_once_it_is_set(law, settings, api):
    # Beside the kept counts, as the address is: set it, and the next answer gives it.
    cache.clear()
    settings.SOURCE_URL = ''
    assert api.get('/api/open/about/').json()['source'] == ''
    settings.SOURCE_URL = 'https://example.org/site'
    assert api.get('/api/open/about/').json()['source'] == 'https://example.org/site'


def test_about_counts_only_the_explanations_a_reader_may_see(law, settings, api):
    # 31 Oct 2026: the page said 13 reviewed explanations, the development's seeds, while the public site showed none.
    from django.utils import timezone

    from apps.accounts.models import User
    from apps.explain.models import Explanation

    cache.clear()
    settings.SHOW_DEMO_PEOPLE = False
    staff = User.objects.create_user('demo-staff', 'staff@demo.law.invalid', 'x-long-pass-1')
    reviewer = User.objects.create_user('reviewer-real', 'reviewer@example.com', 'x-long-pass-1')
    for n, by in enumerate((staff, reviewer), 1):
        Explanation.objects.create(path=f'/ma/loi/1-26/art_{n}', body='شرح.', reviewed_at=timezone.now(),
                                   reviewed_by=by)
    assert api.get('/api/open/about/').json()['explanations'] == 1
