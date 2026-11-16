"""What an edition of the database holds (services/dump.py) and which editions may be served (services/editions.py):
every version through time, the official French, which text changes which in every state, the issues, the older
addresses; each line valid against the edition's own schema.json; each file's hash and lines in the manifest; the
manifest's hash dated in editions.jsonl; only editions of today's format and licence listed, the newest three kept."""
import gzip
import hashlib
import json
from datetime import date

import jsonschema
import pytest
from django.utils import timezone

from apps.consolidation.models import Change
from apps.corpus.models import Alias, Article, Consolidation, Text, Version
from apps.opendata.services import dump, editions
from apps.sources.models import Document, Edition, Issue
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db
SHA = 'ab' * 32


def lines(out, name: str) -> list[dict]:
    return [json.loads(line) for line in gzip.open(out / name, 'rt', encoding='utf-8')]


def write(monkeypatch=None, day: date | None = None):
    if monkeypatch and day:
        monkeypatch.setattr(dump.timezone, 'localdate', lambda: day)
    return dump.write_dump(log=lambda m: None)


@pytest.fixture
def corpus(settings, tmp_path):
    """A law printed in an issue held with its file, consolidated twice since (Adala's, then the machine's); a decree
    whose Arabic is a translation from the French; the law's official French; its changes from every source and in
    every state; an issue that is a copy of another; an older address."""
    settings.OPEN_DATA_DIR = tmp_path / 'open'
    document = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=SHA, path='BO_7533_ar.pdf',
                                       mime='application/pdf', language='ar', bytes=2048, page_count=96,
                                       url='https://www.sgg.gov.ma/BO/AR/2026/BO_7533_Ar.pdf', fetched_at=timezone.now())
    adala = Document.objects.create(source='adala', kind='consolidated_text', sha256='cd' * 32, path='adala/12-26.pdf',
                                    mime='application/pdf', language='ar', bytes=10, fetched_at=timezone.now())
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, date=date(2026, 8, 10), document=document,
                                 first_page_number=5001, hijri_date='5 ربيع الأول 1448')
    Issue.objects.create(edition=Edition.GENERAL_AR, number=7533, suffix='bis', date=date(2026, 8, 11), copy_of=issue)
    law = Text.objects.create(akn_uri='/akn/ma/act/loi/12-26', type='law', number='12-26', number_as_printed='12.26',
                              title_ar='قانون رقم 12.26 يتعلق بالصحافة', first_published_in=issue,
                              first_published_page=5010, signed_on=date(2026, 7, 1))
    for start, end, kind, source, body in (
            (date(2026, 8, 10), date(2026, 9, 1), Consolidation.AS_PUBLISHED, document, 'نص كما نشر.'),
            (date(2026, 9, 1), date(2026, 10, 1), Consolidation.ADALA, adala, 'نص عدالة.'),
            (date(2026, 10, 1), None, Consolidation.MACHINE, None, 'نص محين آليا.')):
        v = Version.objects.create(text=law, language='ar', valid_from=start, valid_to=end, consolidation=kind,
                                   source_document=source, source_pages='5010-5012' if source else '')
        for n in (1, 2):
            Article.objects.create(version=v, order=n, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                                   body=f'{body} {n}', printed_page=5010 + n, heading_path=['الباب الأول'])
    decree = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-1', type='decree', number='2-25-1', title_ar='مرسوم')
    v = Version.objects.create(text=decree, language='ar', valid_from=date(2025, 6, 2), translated_from='fr',
                               consolidation=Consolidation.TRANSLATION)
    Article.objects.create(version=v, order=1, label='المادة الأولى', number='1', eid='art_1', body='ترجمة.')
    FrenchText.objects.create(text_uri=law.akn_uri, type='law', number='12-26', title='Loi n° 12-26 relative à la presse',
                              signed_on=date(2026, 7, 1), issue_number=7534, issue_date=date(2026, 8, 13),
                              document_sha='ef' * 32, pages='1203-1205')
    for n, label in ((1, 'Article premier'), (2, 'Article 2')):
        FrenchArticle.objects.create(text_uri=law.akn_uri, order=n, label=label, number=str(n), body=f'Texte {n}.',
                                     printed_page=1203)
    by = {'by_kind': 'law', 'by_number': '13-26', 'by_uri': '/akn/ma/act/loi/13-26'}
    for source, state in ((Change.Source.READING, 'read'), (Change.Source.READING, 'checked'),
                          (Change.Source.READING, 'confirmed'), (Change.Source.READING, 'conflict'),
                          (Change.Source.READING, 'unclear'), (Change.Source.SGG, ''), (Change.Source.ADALA, ''),
                          (Change.Source.DGI, ''), (Change.Source.BILL, 'proposed'), (Change.Source.MODEL, ''),
                          (Change.Source.BILL, '')):
        Change.objects.create(text_uri=law.akn_uri, number='2', verb='modified', source=source, state=state, issue=7540,
                              page=5200, published_on=date(2026, 9, 1), effective_on=date(2026, 10, 1),
                              effective_rule='stated', **by)
    Alias.objects.create(alias='/akn/ma/act/loi/2026/12-26', uri=law.akn_uri, reason=Alias.Reason.MOVED)
    return law


def test_the_edition_holds_every_version_the_french_the_changes_the_issues_and_the_addresses(corpus):
    out = write()
    texts = {r['akn_uri']: r for r in lines(out, 'texts.jsonl.gz')}
    law = texts['/akn/ma/act/loi/12-26']
    # The newest version, with its pages; the text's source names the Bulletin's file by its hash.
    assert law['version']['kind'] == 'machine' and law['version']['file'] is None
    assert law['source'] == {'issue': '7533', 'edition': 'general_ar', 'date': '2026-08-10', 'page': 5010, 'sha256': SHA}
    assert [a['page'] for a in law['articles']] == [5011, 5012]
    # Every other version, each marked by its kind and holding its own articles: no version is written twice.
    others = lines(out, 'versions.jsonl.gz')
    assert [(r['akn_uri'], r['version']['kind']) for r in others] == [(corpus.akn_uri, 'as_published'),
                                                                       (corpus.akn_uri, 'adala')]
    assert others[0]['version']['file'] == {'source': 'sgg_bo', 'sha256': SHA}
    assert others[0]['version']['pages'] == '5010-5012' and others[0]['version']['valid_to'] == '2026-09-01'
    assert others[1]['version']['file']['source'] == 'adala'
    bodies = [a['body'] for r in [*texts.values(), *others] for a in r['articles']]
    assert len(bodies) == len(set(bodies)) == 7
    assert texts['/akn/ma/act/decret/2-25-1']['version']['kind'] == 'translation'
    # The official French, article by article, with the issue that printed it.
    (french,) = lines(out, 'french.jsonl.gz')
    assert french['source'] == {'edition': 'translation_fr', 'issue': '7534', 'date': '2026-08-13', 'pages': '1203-1205',
                                'sha256': 'ef' * 32}
    assert [(a['label'], a['number'], a['page']) for a in french['articles']] == [('Article premier', '1', 1203),
                                                                                    ('Article 2', '2', 1203)]
    # Every change read from the Bulletin, whatever its state, and what the official consolidations state; a bill's
    # proposals as proposals; never a model's list.
    changes = lines(out, 'changes.jsonl.gz')
    assert [(c['source'], c['state']) for c in changes] == [
        ('reading', 'read'), ('reading', 'checked'), ('reading', 'confirmed'), ('reading', 'conflict'),
        ('reading', 'unclear'), ('sgg', None), ('adala', None), ('dgi', None), ('bill', 'proposed')]
    assert changes[0]['by'] == {'akn_uri': '/akn/ma/act/loi/13-26', 'path': '/ma/loi/13-26', 'kind': 'law',
                                'number': '13-26', 'article': None}
    assert (changes[0]['issue'], changes[0]['takes_effect'], changes[0]['target_path']) == ('7540', '2026-10-01',
                                                                                             '/ma/loi/12-26')
    # The issues held, and the older address.
    issues = {i['key']: i for i in lines(out, 'issues.jsonl.gz')}
    assert issues['7533']['file'] == {'sha256': SHA, 'pages': 96, 'bytes': 2048,
                                      'url': 'https://www.sgg.gov.ma/BO/AR/2026/BO_7533_Ar.pdf'}
    assert issues['7533']['path'] == '/bo/general_ar/7533' and issues['7533']['first_page'] == 5001
    assert issues['7533-bis']['copy_of'] == '7533' and issues['7533-bis']['file'] is None
    assert lines(out, 'aliases.jsonl.gz') == [{'alias': '/akn/ma/act/loi/2026/12-26', 'alias_path': '/ma/loi/2026/12-26',
                                               'akn_uri': corpus.akn_uri, 'path': '/ma/loi/12-26', 'reason': 'moved'}]


def test_every_line_is_valid_against_the_editions_own_schema(corpus):
    out = write()
    schema = json.loads((out / 'schema.json').read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    for name in editions.DATA:
        if name.endswith('.jsonl.gz'):
            check = jsonschema.Draft202012Validator({**schema, '$ref': f'#/$defs/{name.removesuffix(".jsonl.gz")}'})
            found = lines(out, name)
            assert found, name
            for record in found:
                check.validate(record)


def test_the_manifest_counts_every_file_and_hashes_it_as_written(corpus, settings):
    out = write()
    manifest = json.loads((out / 'manifest.json').read_text())
    assert manifest['format'] == editions.FORMAT and manifest['date'] == timezone.localdate().isoformat()
    assert (manifest['texts'], manifest['articles'], manifest['versions']) == (2, 3, 4)
    assert set(manifest['files']) == set(editions.DATA) | set(editions.DESCRIBE) - {'manifest.json'}
    for name, said in manifest['files'].items():
        data = (out / name).read_bytes()
        assert said['bytes'] == len(data) and said['sha256'] == hashlib.sha256(data).hexdigest(), name
        if name.endswith('.jsonl.gz'):
            assert said['lines'] == len(lines(out, name)), name
    assert manifest['files']['akn.zip']['entries'] == 2
    assert manifest['licence'].startswith('ODbL') and 'translation' in manifest['version_kinds']
    # The words shipped with it name the site and its format, never a placeholder.
    readme = (out / 'README.md').read_text()
    assert settings.SITE_NAME in readme and f'format {editions.FORMAT}' in readme
    assert settings.SITE_URL.rstrip('/') + '/api/open/' in readme
    for name in editions.DESCRIBE:
        assert '@SITE' not in (out / name).read_text() and '@FORMAT@' not in (out / name).read_text(), name


def test_the_licence_says_what_is_not_official_and_who_answers_for_named_people(corpus, settings):
    text = (write() / 'LICENCE.txt').read_text()
    assert settings.SITE_NAME in text and 'ODbL' in text and '2-00' in text
    assert 'artificial intelligence' in text and 'الذكاء الاصطناعي' in text and '`machine`' in text
    assert '09-08' in text and '09.08' in text


def test_the_edition_is_dated_by_moroccos_day_and_its_manifest_hash_recorded(corpus, monkeypatch):
    out = write(monkeypatch, date(2026, 12, 1))
    assert out.name == '2026-12-01' and (out.parent / 'latest').resolve() == out
    (line,) = [json.loads(x) for x in (out.parent / editions.LOG).read_text().splitlines()]
    sha = hashlib.sha256((out / 'manifest.json').read_bytes()).hexdigest()
    assert line == {'date': '2026-12-01', 'sha256': sha, 'texts': 2, 'articles': 3, 'versions': 4}
    # Written again the same day: one folder, two lines, the newer first in the history.
    Text.objects.filter(pk=corpus.pk).update(title_ar='قانون رقم 12.26 المتعلق بالصحافة والنشر')
    again = write(monkeypatch, date(2026, 12, 1))
    newer = hashlib.sha256((again / 'manifest.json').read_bytes()).hexdigest()
    assert newer != sha and [e['sha256'] for e in editions.history()] == [newer, sha]
    assert sorted(p.name for p in out.parent.iterdir()) == ['2026-12-01', editions.LOG, 'latest']


def test_only_editions_of_todays_format_and_licence_are_served_and_three_are_kept(corpus, monkeypatch, settings):
    root = editions.root()
    root.mkdir(parents=True)
    # An edition written before, under another licence and without a format: never listed, never let go.
    old = root / '2026-10-20'
    old.mkdir()
    (old / 'manifest.json').write_text(json.dumps({'date': '2026-10-20', 'licence': 'CC BY 4.0', 'texts': 1}))
    (root / '2026-10-21').mkdir()                     # no manifest at all
    days = [date(2027, month, 1) for month in (1, 2, 3, 4)]
    for day in days:
        write(monkeypatch, day)
    assert [e.date for e in editions.listed()] == ['2027-04-01', '2027-03-01', '2027-02-01']
    assert editions.latest().date == '2027-04-01' and editions.find('latest').date == '2027-04-01'
    assert editions.find('2027-01-01') is None and editions.find('2026-10-20') is None
    assert editions.find('../2027-02-01') is None and editions.find('2027-99-99') is None
    assert old.is_dir() and (root / '2026-10-21').is_dir() and not (root / '2027-01-01').exists()
    # The record keeps the edition let go, with its hash.
    assert [e['date'] for e in editions.history()] == ['2027-04-01', '2027-03-01', '2027-02-01', '2027-01-01']
    # A manifest in an older format is not listed either, nor one whose date is not its folder's.
    newest = root / '2027-04-01' / 'manifest.json'
    manifest = json.loads(newest.read_text())
    newest.write_text(json.dumps({**manifest, 'format': editions.FORMAT - 1}))
    assert editions.latest().date == '2027-03-01'
    newest.write_text(json.dumps({**manifest, 'date': '2027-04-02'}))
    assert editions.latest().date == '2027-03-01'


def test_an_edition_copied_by_hand_is_in_the_history_and_a_folder_of_another_hand_is_never_overwritten(
        corpus, monkeypatch):
    out = write(monkeypatch, date(2027, 1, 1))
    (out.parent / editions.LOG).unlink()
    assert editions.history() == [{'date': '2027-01-01', 'sha256': editions.latest().sha256}]
    other = out.parent / '2027-02-01'
    other.mkdir()
    (other / 'notes.txt').write_text('kept')
    with pytest.raises(FileExistsError):
        write(monkeypatch, date(2027, 2, 1))
    assert (other / 'notes.txt').read_text() == 'kept'


def test_what_a_stopped_export_left_is_cleared_and_the_files_are_readable_by_nginx(corpus, monkeypatch):
    root = editions.root()
    (root / '.2026-12-01.part').mkdir(parents=True)
    (root / '.2026-12-01.part' / 'texts.jsonl.gz').write_bytes(b'half')
    out = write(monkeypatch, date(2027, 1, 1))
    assert not (root / '.2026-12-01.part').exists()
    assert out.stat().st_mode & 0o777 == 0o755
    assert {p.stat().st_mode & 0o777 for p in out.iterdir()} == {0o644}


def test_the_command_writes_the_edition_and_says_so(corpus):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    assert editions.listed() == [] and editions.history() == []          # nothing written yet, no folder at all
    call_command('export_open_data', stdout=out)
    assert 'open data: 2 texts, 3 articles, 4 versions' in out.getvalue()
    # A line of the record that does not read is passed over.
    with open(editions.root() / editions.LOG, 'a') as log:
        log.write('not json\n{"date": "2026-01-01"}\n')
    assert [e['date'] for e in editions.history()] == [timezone.localdate().isoformat()]
