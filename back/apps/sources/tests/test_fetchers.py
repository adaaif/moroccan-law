"""The fetchers, each through its command: the SGG's French edition and its consolidated texts, an Adala file, the
conventions' edition. Each lists by default, fetches with --fetch once a file, keeps what it fetched with its hash, says
and passes one file that fails, and stops on a refusal. The sites are a fake network (conftest.py); the files are
real PDFs."""
import hashlib
import io
import json
import re
from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Text
from apps.parliament.tests.pdfs import pdf_bytes
from apps.sources.models import Document, Issue
from apps.sources.services import fetch
from apps.sources.tests.bo import DECREE, write_pdf
from apps.sources.tests.test_fetch import sgg_row

PDF = pdf_bytes([DECREE], rtl=True)
SGG = 'https://www.sgg.gov.ma'
ENDPOINT = f'{SGG}/DesktopModules/MVC/TableListBO/BO/AjaxMethod'
TOKEN_PAGE = b'<input name="__RequestVerificationToken" type="hidden" value="tok" />'


def run(*args) -> tuple[str, str]:
    out, err = io.StringIO(), io.StringIO()
    call_command(*args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def manifest(folder) -> list[list[str]]:
    return [line.split('\t') for line in (folder / 'MANIFEST.tsv').read_text().splitlines()]


# ── fetch_bo_french ────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_french_edition_is_fetched_once_an_issue_and_a_bad_one_is_said_and_passed(sgg, tmp_path):
    rows = [sgg_row('7400', '2025-01-02', 'FR'), sgg_row('7401', '2025-01-09', 'FR'), sgg_row('7402', '2025-01-16', 'FR'),
            sgg_row('7403', '2025-01-23', 'FR'), sgg_row('12/a', '2025-01-30', 'FR'), sgg_row(' 1 ', '1912-11-01', 'FR')]
    rows[5]['BoUrl'] = 'BO/fr/1912/bo_1_ fr.pdf'                   # the list writes some links bare, some with a space
    conventions = [sgg_row('20', '2024-05-01', 'FR')]
    sgg.pages = {f'{SGG}/BulletinOfficiel.aspx': TOKEN_PAGE,
                 ENDPOINT: lambda headers: json.dumps({'2873': rows, '3076': conventions}[headers['Moduleid']]).encode(),
                 f'{SGG}/BO/fr/1912/bo_1_%20fr.pdf': PDF, rows[1]['BoUrl']: PDF, rows[3]['BoUrl']: b'<html>Erreur</html>',
                 conventions[0]['BoUrl']: PDF}
    (tmp_path / 'issues' / 'bo_fr').mkdir(parents=True)
    (tmp_path / 'issues' / 'bo_fr' / 'BO_7400_fr.pdf').write_bytes(PDF)

    out, err = run('fetch_bo_french', '--before', '1913')
    assert re.fullmatch(r'index: bo_fr 6, eci_fr 1 issues; kept as index_fr_\d{4}-\d\d-\d\dT\d{6}Z\.json '
                        r'\(sha256 [0-9a-f]{16}…\)', out.splitlines()[0])
    assert out.splitlines()[1] == '1 issues to fetch (dated before 1913)' and err == ''
    [kept] = (tmp_path / 'sources' / 'sgg_bo').glob('index_fr_*.json')
    assert json.loads(kept.read_text()) == {'bo_fr': rows, 'eci_fr': conventions}

    out, err = run('fetch_bo_french', '--fetch', '--limit', '2', '--pause', '0.5')
    assert out.splitlines()[1] == '5 issues to fetch'
    assert out.splitlines()[2].startswith('2 of 2: 2 fetched, 0 failed, ') and out.splitlines()[3] == 'done: 2 fetched, 0 failed of 2'
    assert err.splitlines() == ["'BO_12/a_fr.pdf': not a plain file name"]
    folder = tmp_path / 'issues' / 'bo_fr'
    assert (folder / 'BO_1_fr.pdf').read_bytes() == PDF and (folder / 'BO_7401_fr.pdf').read_bytes() == PDF
    first, second = manifest(folder)
    assert first[:4] == ['BO_1_fr.pdf', f'{SGG}/BO/fr/1912/bo_1_%20fr.pdf', hashlib.sha256(PDF).hexdigest(), str(len(PDF))]
    assert first[5:] == ['1', '1912-11-01'] and second[5:] == ['7401', '2025-01-09']
    assert sgg.slept.count(0.5) == 2 and not (tmp_path / 'issues' / 'eci_fr' / 'ECI_20_fr.pdf').exists()

    out, err = run('fetch_bo_french', '--fetch', '--pause', '0')                  # a rerun asks only what is missing
    assert out.splitlines()[2].startswith('3 of 3: 1 fetched, 2 failed, ')
    assert out.splitlines()[3:] == ['done: 1 fetched, 2 failed of 3']
    assert err.splitlines()[1:] == [f'BO_7402_fr.pdf: HTTP Error 404: Not Found ({rows[2]["BoUrl"]})',
                                    f'BO_7403_fr.pdf: not a PDF (19 bytes, {rows[3]["BoUrl"]})']
    assert not (folder / 'BO_7403_fr.pdf').exists() and not list(folder.glob('*.part')) and len(manifest(folder)) == 2
    assert (tmp_path / 'issues' / 'eci_fr' / 'ECI_20_fr.pdf').read_bytes() == PDF
    assert manifest(tmp_path / 'issues' / 'eci_fr')[0][5:] == ['20', '2024-05-01']


# ── fetch_sgg_consolidated ─────────────────────────────────────────────────────────────────────────────────────────

LIST = f'{SGG}/arabe/textesconsolides.aspx'
CONSOLIDATED = ('<a href="/arabe/textesconsolides/2_00.pdf">قانون رقم 2.00 <b>المتعلق</b>\n بحقوق المؤلف &amp; الحقوق</a>'
                '<a href="https://www.sgg.gov.ma/arabe/textesconsolides/52_05.pdf">مدونة السير</a>'
                '<a href="/arabe/textesconsolides/.hidden.pdf">x</a>'
                '<a href="https://elsewhere.example/textesconsolides/9_99.pdf">نص في موقع آخر</a>'
                '<a href="/arabe/textesconsolides/1_58_376.pdf">ظهير الحريات العامة</a>'
                '<a href="/arabe/textesconsolides/3_99.pdf">نص يرفض</a>').encode()


@pytest.mark.django_db
def test_the_sgg_s_consolidated_texts_are_listed_fetched_once_and_registered(sgg, tmp_path):
    sgg.pages = {LIST: CONSOLIDATED, f'{SGG}/arabe/textesconsolides/2_00.pdf': PDF,
                 f'{SGG}/arabe/textesconsolides/1_58_376.pdf': b'<html></html>', f'{SGG}/arabe/textesconsolides/3_99.pdf': 403}
    folder = tmp_path / 'sources' / 'sgg_consolidated'
    write_pdf(folder / '52_05.pdf', [DECREE, DECREE])

    out, _ = run('fetch_sgg_consolidated')
    assert out.splitlines() == ['        2_00  to fetch  قانون رقم 2.00 المتعلق بحقوق المؤلف & الحقوق',
                                '       52_05      held  مدونة السير', '        9_99  to fetch  نص في موقع آخر',
                                '    1_58_376  to fetch  ظهير الحريات العامة', '        3_99  to fetch  نص يرفض',
                                '5 texts, 4 not held: --fetch fetches them and registers every text']
    assert not Document.objects.exists()

    out, _ = run('fetch_sgg_consolidated', '--fetch', '--only', '2_00', '52_05')
    assert out.splitlines() == ['        2_00     1 pages  قانون رقم 2.00 المتعلق بحقوق المؤلف & الحقوق',
                                '       52_05     2 pages  مدونة السير', '2 texts, 1 fetched now']
    law = Document.objects.get(meta__stem='2_00')
    assert (law.source, law.kind, law.url, law.title, law.path, law.meta['list_order']) == (
        'sgg_consolidated', 'consolidated_text', f'{SGG}/arabe/textesconsolides/2_00.pdf',
        'قانون رقم 2.00 المتعلق بحقوق المؤلف & الحقوق', 'sources/sgg_consolidated/2_00.pdf', 1)
    held = Document.objects.get(meta__stem='52_05')               # held already: registered without a fetch
    assert (held.title, held.url, held.meta, held.page_count) == (
        'مدونة السير', f'{SGG}/arabe/textesconsolides/52_05.pdf', {'stem': '52_05', 'list_order': 2}, 2)
    assert sgg.slept == [2]

    out, err = io.StringIO(), io.StringIO()
    with pytest.raises(CommandError, match='refused it'):     # a refusal stops the run, the files before it kept
        call_command('fetch_sgg_consolidated', '--fetch', stdout=out, stderr=err)
    assert err.getvalue().splitlines() == [
        'https://elsewhere.example/textesconsolides/9_99.pdf: not an address the fetchers may ask '
        f'(https on {", ".join(sorted(fetch.HOSTS))})',
        '1_58_376: not a PDF (13 bytes)']
    assert Document.objects.count() == 2 and not (folder / '1_58_376.pdf').exists()


@pytest.mark.django_db
def test_a_list_robots_txt_closes_stops_the_consolidated_texts(sgg):
    sgg.pages = {f'{SGG}/robots.txt': b'User-agent: *\nDisallow: /arabe/\n', LIST: CONSOLIDATED}
    with pytest.raises(CommandError, match=r'robots\.txt'):
        run('fetch_sgg_consolidated')
    assert LIST not in sgg.asked


# ── fetch_adala ────────────────────────────────────────────────────────────────────────────────────────────────────

ADALA = 'https://adala.justice.gov.ma/api/uploads/2025/03/21/قانون 15.01.pdf'


@pytest.mark.django_db
def test_an_adala_file_is_fetched_kept_and_registered(sgg, tmp_path):
    quoted = 'https://adala.justice.gov.ma/api/uploads/2025/03/21/' \
             '%D9%82%D8%A7%D9%86%D9%88%D9%86%2015.01.pdf'
    sgg.pages = {quoted: PDF}
    with pytest.raises(CommandError, match=r'only adala\.justice\.gov\.ma'):
        run('fetch_adala', 'https://www.sgg.gov.ma/a.pdf', '--name', 'a', '--fetch')
    with pytest.raises(CommandError, match='--name or --kept'):
        run('fetch_adala', ADALA)
    out, _ = run('fetch_adala', ADALA, '--name', 'kafala_15_01', '--fetch', '--language', 'fr')
    doc = Document.objects.get()
    assert out.strip() == f'sources/adala/kafala_15_01.pdf: 1 pages, sha256 {doc.sha256[:12]}…'
    assert (doc.source, doc.kind, doc.language, doc.url, doc.sha256) == ('adala', 'text', 'fr', ADALA,
                                                                          hashlib.sha256(PDF).hexdigest())
    assert (tmp_path / 'sources' / 'adala' / 'kafala_15_01.pdf').read_bytes() == PDF


@pytest.mark.django_db
@pytest.mark.parametrize('answer, refusal', [(b'<html>404</html>', 'not a PDF'), (403, 'refused it')])
def test_an_adala_answer_that_is_no_file_registers_nothing(sgg, tmp_path, answer, refusal):
    sgg.pages = {'https://adala.justice.gov.ma/api/uploads/a.pdf': answer}
    with pytest.raises(CommandError, match=refusal):
        run('fetch_adala', 'https://adala.justice.gov.ma/api/uploads/a.pdf', '--name', 'a', '--fetch')
    assert not Document.objects.exists() and not (tmp_path / 'sources' / 'adala' / 'a.pdf').exists()


@pytest.mark.django_db
def test_an_adala_file_fetched_before_is_registered_as_it_is(sgg, tmp_path):
    write_pdf(tmp_path / 'sources' / 'road' / 'adala_2_10_420.pdf', [DECREE, DECREE])
    (tmp_path / 'sources' / 'road' / 'page.html').write_text('<html></html>')
    with pytest.raises(CommandError, match='not a PDF'):
        run('fetch_adala', ADALA, '--kept', 'sources/road/page.html')
    out, _ = run('fetch_adala', ADALA, '--kept', 'sources/road/adala_2_10_420.pdf')
    doc = Document.objects.get()
    assert out.startswith('sources/road/adala_2_10_420.pdf: 2 pages, sha256 ') and doc.pages.count() == 2
    assert sgg.asked == []


# ── fetch_conventions ──────────────────────────────────────────────────────────────────────────────────────────────

def conventions(sgg, rows):
    sgg.pages.update({f'{SGG}/arabe/BulletinOfficiel.aspx': TOKEN_PAGE,
                      ENDPOINT: lambda headers: json.dumps(rows).encode() if headers['Moduleid'] == '3110' else b'[]'})


@pytest.mark.django_db
def test_the_conventions_edition_lists_what_is_not_read_and_fetches_it_with_fetch(sgg, tmp_path):
    rows = [sgg_row('14', '2026-10-20'), sgg_row('11', '2026-01-10'), sgg_row('12', '2026-03-02'),
            sgg_row('13', '2026-06-15')]
    rows[3]['BoUrl'] = '/BO/AR/2026/ECI_13_Ar.pdf'
    conventions(sgg, rows)
    sgg.pages.update({rows[2]['BoUrl']: PDF, f'{SGG}/BO/AR/2026/ECI_13_Ar.pdf': b'not a file'})
    read = Issue.objects.create(edition='conventions_ar', number=11, date=date(2026, 1, 10))
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1-25-90', type='dahir', title_ar='ظهير شريف', first_published_in=read)

    out, err = run('fetch_conventions')
    assert re.fullmatch(r'list: 4 issues \(sha256 [0-9a-f]{16}…\); not read: 12, 13, 14', out.strip())
    [kept] = (tmp_path / 'sources' / 'sgg_bo').glob('index_ar_3110_*.json')
    assert json.loads(kept.read_text()) == rows
    assert not (tmp_path / 'issues' / 'eci_ar').exists()

    out, err = run('fetch_conventions', '--fetch')
    folder = tmp_path / 'issues' / 'eci_ar'
    assert out.splitlines()[1] == f'12: {len(PDF)} bytes'
    assert err.splitlines() == ['13: not a PDF (10 bytes)', f'14: HTTP Error 404: Not Found ({rows[0]["BoUrl"]})']
    assert (folder / 'ECI_12_ar.pdf').read_bytes() == PDF and not (folder / 'ECI_13_ar.pdf').exists()
    assert manifest(folder) == [['ECI_12_ar.pdf', rows[2]['BoUrl'], hashlib.sha256(PDF).hexdigest(), str(len(PDF)),
                                 manifest(folder)[0][4], '12', '2026-03-02']]
    assert sgg.slept.count(2.0) == 3

    sgg.asked.clear()
    run('fetch_conventions', '--fetch')                     # held: never fetched again
    assert rows[2]['BoUrl'] not in sgg.asked and len(manifest(folder)) == 1

    for number in (12, 13, 14):
        issue = Issue.objects.create(edition='conventions_ar', number=number, date=date(2026, 3, 2))
        Text.objects.create(akn_uri=f'/akn/ma/act/dahir/1-25-{number}', type='dahir', title_ar='ظهير', first_published_in=issue)
    sgg.asked.clear()
    out, _ = run('fetch_conventions', '--fetch')
    assert out.strip().endswith('not read: none') and sgg.asked[-1] == ENDPOINT


@pytest.mark.django_db
def test_a_refusal_stops_the_conventions_edition(sgg):
    sgg.pages = {f'{SGG}/robots.txt': b'User-agent: *\nDisallow: /DesktopModules/\n',
                 f'{SGG}/arabe/BulletinOfficiel.aspx': TOKEN_PAGE}
    with pytest.raises(CommandError, match=r'robots\.txt'):
        run('fetch_conventions', '--fetch')
    assert ENDPOINT not in sgg.asked
