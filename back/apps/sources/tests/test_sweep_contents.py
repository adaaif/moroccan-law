"""`sweep_contents`: the issues of a span of years from the SGG's list, fetched once with --fetch, their first pages read
by the model in batches carrying many issues with --write, and the contents' lines that name a consumer's law kept in a
report. The SGG is a fake network and the model the API's stand-in; the files, their pages and images are real."""
import io
import json
import re
import time

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.sources.models import Issue, OcrRun, Page, TextSource
from apps.sources.tests.bo import DECREE, install, write_pdf
from apps.sources.tests.test_fetch import sgg_row
from apps.parliament.tests.pdfs import pdf_bytes

pytestmark = pytest.mark.django_db

LISTING = 'sources/consumer/sgg_bo_ar_list.json'
# A decree that names nothing of the consumer's law.
ELSEWHERE = ['مرسوم رقم 2.26.200 صادر في 13 نوفمبر 2026', 'بتعيين أعضاء المجلس الإداري للمكتب الوطني للسكك الحديدية',
             'رئيس الحكومة بناء على الدستور ولا سيما الفصل 90 منه', 'المادة الأولى يعين أعضاء المجلس الإداري لمدة ثلاث سنوات',
             'المادة الثانية يسند تنفيذ هذا المرسوم إلى وزير النقل واللوجستيك', 'وينشر هذا المرسوم بالجريدة الرسمية']


def reading(cid, params):
    """The page whole, or its two columns: the second and third lines, then the rest (the header comes from the whole
    page's reading)."""
    page = Page.objects.get(pk=int(re.match(r'p(\d+)', cid).group(1)))
    lines = page.layer_text.split('\r\n') if '\r\n' in page.layer_text else page.layer_text.splitlines()
    lines = [' '.join(line.split()) for line in lines if line.strip()]
    return {'': '\n'.join(lines), 'c0': '\n'.join(lines[1:3]), 'c1': '\n'.join(lines[3:])}[cid[len(f'p{page.pk}'):]]


def listing(root, rows):
    path = root / LISTING
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(rows))


def sweep(*args) -> str:
    out = io.StringIO()
    call_command('sweep_contents', LISTING, '--from', '2026', '--to', '2026', '--report', 'reports/sweep.json', *args,
                 stdout=out)
    return out.getvalue()


def test_without_fetch_only_the_issues_held_are_swept_and_nothing_is_read_without_write(sgg, tmp_path):
    held, wanted = sgg_row('7600', '2026-11-02'), sgg_row('7601', '2026-11-05')
    listing(tmp_path, [held, wanted, sgg_row('7500', '2025-12-01'), sgg_row('BIS-6168', '2026-11-03')])
    write_pdf(tmp_path / 'issues' / 'bo_ar' / 'BO_7600_ar.pdf', [DECREE])
    out = sweep('--ceiling', '1')
    assert out.splitlines() == ['2 issues 2026–2026', 'fetched 0, missing 1 (not held; --fetch fetches them)',
                                'nothing read: --write reads the first pages (paid)']
    assert sgg.asked == [] and not Issue.objects.exists() and not (tmp_path / 'reports' / 'sweep.json').exists()


def test_a_refusal_stops_the_sweep(sgg, tmp_path):
    listing(tmp_path, [sgg_row('7601', '2026-11-05')])
    sgg.pages = {'https://www.sgg.gov.ma/robots.txt': b'User-agent: *\nDisallow: /BO/\n'}
    with pytest.raises(CommandError, match=r'robots\.txt'):
        sweep('--ceiling', '1', '--fetch')
    assert not (tmp_path / 'issues' / 'bo_ar' / 'BO_7601_ar.pdf').exists()


def test_the_sweep_fetches_reads_the_first_pages_and_lists_the_lines_that_matter(sgg, settings, tmp_path, monkeypatch):
    rows = [sgg_row('7600', '2026-11-02'), sgg_row('7601', '2026-11-05'), sgg_row('7602', '2026-11-09'),
            sgg_row('7603', '2026-11-12'), sgg_row('7604 bis', '2026-11-13'), sgg_row('7700', '2027-01-04')]
    rows[4]['BoUrl'] = 'https://www.sgg.gov.ma/BO/AR/2026/BO_7604 bis_Ar.pdf'      # a space in the SGG's own link
    listing(tmp_path, rows)
    # A number that only ends like one of the consumer's (131.08), and a line too short to be a contents entry.
    write_pdf(tmp_path / 'issues' / 'bo_ar' / 'BO_7600_ar.pdf', [DECREE + ['قرار رقم 131.08 في شأن السكن', 'الأسعار'],
                                                                 ['ظهير شريف']])
    sgg.pages = {rows[1]['BoUrl']: pdf_bytes([['عدد 7601'] + DECREE[1:]], rtl=True),
                 rows[2]['BoUrl']: b'<html>Erreur</html>',                         # not a file: missing
                 'https://www.sgg.gov.ma/BO/AR/2026/BO_7604%20bis_Ar.pdf': pdf_bytes([ELSEWHERE], rtl=True)}

    claude = install(monkeypatch, settings, tmp_path, reading)
    monkeypatch.setattr(time, 'sleep', sgg.slept.append)             # the batches' polls too: no test waits

    # One issue a batch here; a batch of the first page costs $0.0006 (the page, then its two columns), and the sweep
    # stops before a third whose ceiling ($0.01121) would take it past $0.012.
    out = sweep('--fetch', '--write', '--pages', '1', '--chunk', '1', '--ceiling', '0.012')
    assert (tmp_path / 'issues' / 'bo_ar' / 'BO_7601_ar.pdf').read_bytes()[:4] == b'%PDF'
    assert (tmp_path / 'issues' / 'bo_ar' / 'BO_7604-bis_ar.pdf').exists()
    assert not (tmp_path / 'issues' / 'bo_ar' / 'BO_7602_ar.pdf').exists()
    lines = out.splitlines()
    assert lines[:2] == ['5 issues 2026–2026', '  7603: not fetched (HTTP Error 404: Not Found)']
    assert lines[2] == 'fetched 2, missing 2'
    assert 'issues 7600…7600: 1 pages (1 in two columns)' in lines and 'issues 7601…7601: 1 pages (1 in two columns)' in lines
    assert any(line.startswith('STOP before issues 7604-bis…7604-bis: the sweep has spent $0.0012') for line in lines)
    assert sgg.slept.count(2.1) == 4                                        # two seconds between the SGG's files
    assert '  spent by the sweep: $0.0006; issues with lines: 1' in lines
    assert '  spent by the sweep: $0.0012; issues with lines: 2' in lines

    issue = Issue.objects.get(number=7601)
    assert (issue.edition, str(issue.date), issue.document.url) == ('general_ar', '2026-11-05', rows[1]['BoUrl'])
    assert not OcrRun.objects.filter(page__document__issue__number=7604).exists()     # registered, stopped before reading
    # The first page only: three requests each (whole, then its two columns at 3192 px); the second page left.
    assert sorted(OcrRun.objects.values_list('page__document__issue__number', 'variant')) == [
        (7600, 'columns-3192'), (7600, 'page-1596'), (7601, 'columns-3192'), (7601, 'page-1596')]
    assert len(claude.requests()) == 6
    first = Page.objects.get(document__issue__number=7600, index=0)
    assert first.text_source == TextSource.OCR and first.text.split('\n\n')[0] == ' '.join(DECREE[0].split())
    report = json.loads((tmp_path / 'reports' / 'sweep.json').read_text())
    assert set(report) == {'7600', '7601'}
    assert report['7601'] == {'date': '2026-11-05', 'url': rows[1]['BoUrl'], 'lines': [
        {'line': 'بتطبيق القانون رقم 31.08 القاضي بتحديد تدابير لحماية المستهلك', 'numbers': ['31.08'],
         'words': ['المستهلك'], 'page': 0},
        {'line': 'كيفيات إعلام المستهلك بأسعار المنتوجات والسلع والخدمات', 'numbers': [], 'words': ['المستهلك'],
         'page': 0}]}
    assert len(report['7600']['lines']) == 2

    # Again with room: what was read is not read again, the issue stopped before is, and the report grows.
    out = sweep('--write', '--pages', '1', '--chunk', '1', '--ceiling', '1')
    assert 'issues 7604-bis…7604-bis: 1 pages (1 in two columns)' in out
    assert 'issues 7600…7600' not in out and len(claude.requests()) == 9
    # The sweep counts its own spending, not what was spent before it; an issue whose contents name nothing of the
    # consumer's is kept with no lines.
    assert out.splitlines()[-2:] == ['  spent by the sweep: $0.0006; issues with lines: 2',
                                     f'report: {tmp_path / "reports" / "sweep.json"} (3 issues)']
    report = json.loads((tmp_path / 'reports' / 'sweep.json').read_text())
    assert set(report) == {'7600', '7601', '7604-bis'} and report['7604-bis']['lines'] == []
    assert Issue.objects.get(number=7604, suffix='bis').document.pages.get(index=0).text != ''



def test_a_line_found_on_a_later_first_page_says_its_page(sgg, settings, tmp_path, monkeypatch):
    listing(tmp_path, [sgg_row('7600', '2026-11-02')])
    # The cover names nothing of the consumer's; the contents on the second page do.
    write_pdf(tmp_path / 'issues' / 'bo_ar' / 'BO_7600_ar.pdf', [ELSEWHERE, DECREE])
    install(monkeypatch, settings, tmp_path, reading)
    monkeypatch.setattr(time, 'sleep', sgg.slept.append)
    sweep('--write', '--pages', '2', '--ceiling', '1')
    lines = json.loads((tmp_path / 'reports' / 'sweep.json').read_text())['7600']['lines']
    assert [(line['page'], line['numbers'], line['words']) for line in lines] == [
        (1, ['31.08'], ['المستهلك']), (1, [], ['المستهلك'])]
