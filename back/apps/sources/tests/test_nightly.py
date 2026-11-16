"""The night's run (`fetch_new_issues --fetch --write`, deploy/fetch.sh) and the conventions' edition read the same way:
the SGG's new issues fetched, each read end to end by `process_issue` within the night's ceiling, its texts loaded and
indexed for search; an issue the SGG does not serve is tried three nights, one that fails is said and passed. The SGG is
a fake network and the model the API's stand-in; the files, their pages and the pipeline are real."""
import io
import json
import re

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Article, Text
from apps.parliament.tests.pdfs import pdf_bytes
from apps.search.models import SearchEntry
from apps.sources.models import Issue, OcrRun, Page, TextSource
from apps.sources.tests.bo import DECREE, install
from apps.sources.tests.test_fetch import sgg_row

pytestmark = pytest.mark.django_db

SGG = 'https://www.sgg.gov.ma'
ENDPOINT = f'{SGG}/DesktopModules/MVC/TableListBO/BO/AjaxMethod'
TOKEN_PAGE = b'<input name="__RequestVerificationToken" type="hidden" value="tok" />'

# BO 7600 as printed: its contents, then law 10.20 on page 1530; each page's running head carries its folio.
CONTENTS = ['الجريدة الرسمية عدد 7600 - 2026 - 1529', 'فهرست', 'نصوص عامة',
            'قانون رقم 10.20 يتعلق بالشغل المنزلي ........ 1530'] + DECREE
LAW = ['الجريدة الرسمية عدد 7600 - 2026 - 1530',
       'ظهير شريف رقم 1.25.02 صادر في 21 من شعبان 1446 (20 فبراير 2025) بتنفيذ القانون رقم 10.20 يتعلق بالشغل المنزلي.',
       'الحمد لله وحده،', 'وحرر بالرباط في 21 من شعبان 1446 (20 فبراير 2025).', 'قانون رقم 10.20', 'يتعلق بالشغل المنزلي',
       'المادة الأولى', 'يطبق هذا القانون على العمال المنزليين.', 'المادة 2', 'يدخل هذا القانون حيز التنفيذ من تاريخ نشره.']
# The model's description of the law, as the texts step asks for it.
DATA = {'found': True, 'type': 'law', 'number_as_printed': '10.20', 'title': 'قانون رقم 10.20 يتعلق بالشغل المنزلي',
        'signed_on_gregorian': '2025-02-20', 'signed_on_hijri': '', 'authority': '', 'promulgating_dahir': '1.25.02',
        'preamble': [], 'closing': '', 'signatories': [], 'cites': [], 'amends': []}
TOC = [{'section': 'general', 'rubric': '', 'type': 'law', 'number_as_printed': '10.20',
        'title': 'ظهير شريف رقم 1.25.02 صادر في 21 من شعبان 1446 (20 فبراير 2025) بتنفيذ القانون رقم 10.20',
        'signed_on_gregorian': '2025-02-20', 'signed_on_hijri': '', 'page': 1530}]


def model(cid, params):
    """What the model reads: a page whole, or its two columns below the running head; the contents; a text."""
    if cid.startswith('toc-'):
        return {'entries': TOC if cid == 'toc-7600' else []}
    if not isinstance(params['messages'][0]['content'], list):            # a text to describe, from its lines
        return DATA
    pk, column = re.fullmatch(r'[pt](\d+)(c\d)?', cid).groups()
    page = Page.objects.select_related('document__issue').get(pk=pk)
    lines = {7600: [CONTENTS, LAW]}.get(page.document.issue.number, [DECREE, DECREE])[page.index]
    return {None: '\n'.join(lines), 'c0': '\n'.join(lines[1:4]), 'c1': '\n'.join(lines[4:])}[column]


def run(*args) -> tuple[str, str]:
    out, err = io.StringIO(), io.StringIO()
    call_command(*args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def the_list(sgg, rows):
    sgg.pages.update({f'{SGG}/arabe/BulletinOfficiel.aspx': TOKEN_PAGE, ENDPOINT: json.dumps(rows).encode()})


def test_the_night_fetches_reads_loads_and_indexes_each_new_issue(sgg, settings, tmp_path, monkeypatch):
    import time
    claude = install(monkeypatch, settings, tmp_path, model)
    monkeypatch.setattr(time, 'sleep', sgg.slept.append)
    rows = [sgg_row('7600', '2026-11-02'), sgg_row('7601', '2026-11-05'), sgg_row('7602', '2026-11-09'),
            sgg_row('7410', '2025-04-03'), sgg_row('7599', '2026-10-29'), sgg_row('bis-6168', '2013-07-08')]
    the_list(sgg, rows)
    sgg.pages.update({rows[0]['BoUrl']: pdf_bytes([CONTENTS, LAW], rtl=True),
                      rows[2]['BoUrl']: b'%PDF-1.7 cut short by the SGG'})          # a PDF that cannot be read
    Issue.objects.create(edition='general_ar', number=7599, date='2026-10-29')
    (tmp_path / 'reports').mkdir()
    (tmp_path / 'reports' / 'fetch_new_issues.json').write_text(json.dumps(
        {'begun': {}, 'finished': {}, 'failed': {'7410': 3}}))                     # three nights without a file

    out, err = run('fetch_new_issues', '--fetch', '--write', '--per-run', '1')
    lines = out.splitlines()
    assert re.fullmatch(r'list: 6 issues \(sha256 [0-9a-f]{16}…\); 3 not held since 2019-01-01: 7600, 7601, 7602', lines[0])
    assert lines[1] == 'left after 3 failed nights: 7410'
    assert 'registered BO 7600 (General edition (Arabic, authoritative), 2026-11-02): 2 pages' in lines
    assert 'printed pages start at 1529' in lines and 'texts read: 1 of 1' in lines
    assert re.search(r'^read 7600; [1-9]\d* search entries written$', out, re.M)
    assert lines[-1] == 'spent 0.0016 (ceiling tonight 1.00)'      # 8 requests: 2 pages, their 4 columns, contents, text
    assert f'7601: HTTP Error 404: Not Found ({rows[1]["BoUrl"]}); night 1 of 3' in err
    assert re.search(r'^7602 failed:\nTraceback', err, re.M)

    state = json.loads((tmp_path / 'reports' / 'fetch_new_issues.json').read_text())
    assert set(state['finished']) == {'7600'} and set(state['begun']) == {'7600', '7602'}
    assert state['failed'] == {'7410': 3, '7601': 1}
    assert state['asked']['listed'] == 6 and (state['asked']['newest'], state['asked']['newest_date']) == ('7602', '2026-11-09')
    manifest = (tmp_path / 'issues' / 'bo_ar' / 'MANIFEST.tsv').read_text().splitlines()
    assert [line.split('\t')[0] for line in manifest] == ['BO_7600_ar.pdf', 'BO_7602_ar.pdf']

    # The issue read end to end: its pages kept their readings, numbered by their running heads, its law loaded and
    # found by search; the contents and the text were asked of the model, the pages read whole and by columns.
    issue = Issue.objects.get(number=7600)
    pages = list(issue.document.pages.order_by('index'))
    assert [p.printed_number for p in pages] == [1529, 1530] and all(p.text_source == TextSource.OCR for p in pages)
    assert sorted(OcrRun.objects.filter(page__in=pages).values_list('page__index', 'variant')) == [
        (0, 'columns-3192'), (0, 'page-1596'), (1, 'columns-3192'), (1, 'page-1596')]
    law = Text.objects.get(akn_uri='/akn/ma/act/loi/10-20')
    assert law.first_published_in == issue and Article.objects.filter(version__text=law).count() == 2
    assert SearchEntry.objects.filter(text_path='/ma/loi/10-20').exists()
    assert {r['custom_id'] for r in claude.requests()} >= {'toc-7600', 't0', f'p{pages[0].pk}', f'p{pages[1].pk}'}
    coverage = json.loads((tmp_path / 'reports' / 'coverage.json').read_text())['7600']
    assert (coverage['listed'], coverage['loaded']) == (1, 1)

    # The next night: what was read is held, 7601 is tried again, the failed 7602 too.
    sgg.asked.clear()
    out, err = run('fetch_new_issues', '--fetch', '--write', '--per-run', '1')
    assert out.splitlines()[0].endswith('2 not held since 2019-01-01: 7601, 7602')
    assert json.loads((tmp_path / 'reports' / 'fetch_new_issues.json').read_text())['failed']['7601'] == 2
    assert rows[0]['BoUrl'] not in sgg.asked


def test_without_fetch_the_night_says_what_it_would_fetch(sgg, settings, tmp_path, monkeypatch):
    install(monkeypatch, settings, tmp_path, model)
    the_list(sgg, [sgg_row('7601', '2026-11-05')])
    out, _ = run('fetch_new_issues', '--write', '--per-run', '0.5')
    assert out.splitlines()[1:] == ['7601: not held; --fetch fetches it', 'spent 0.0000 (ceiling tonight 0.50)']
    assert not (tmp_path / 'issues' / 'bo_ar' / 'BO_7601_ar.pdf').exists()


def test_a_list_robots_txt_closes_stops_the_night(sgg):
    sgg.pages = {f'{SGG}/robots.txt': b'User-agent: *\nDisallow: /arabe/\n'}
    with pytest.raises(CommandError, match=r'robots\.txt'):
        run('fetch_new_issues', '--fetch')
    assert sgg.asked == [f'{SGG}/robots.txt']


def test_the_conventions_kept_are_read_until_the_run_s_ceiling(sgg, settings, tmp_path, monkeypatch):
    claude = install(monkeypatch, settings, tmp_path, model)
    kept = tmp_path / 'sources' / 'sgg_bo'
    kept.mkdir(parents=True)
    rows = [sgg_row('12', '2026-03-02'), sgg_row('13', '2026-06-15'), sgg_row('14', '2026-10-20')]
    (kept / 'index_ar_3110_2026-11-01T000000Z.json').write_text(json.dumps(rows[:1]))
    (kept / 'index_ar_3110_2026-11-08T000000Z.json').write_text(json.dumps(rows))     # the newest is read
    folder = tmp_path / 'issues' / 'eci_ar'
    folder.mkdir(parents=True)
    for number in (12, 13):
        (folder / f'ECI_{number}_ar.pdf').write_bytes(pdf_bytes([DECREE], rtl=True))

    # A ceiling no page fits: the first issue is registered, nothing is sent, the run stops.
    out, _ = run('fetch_conventions', '--kept', '--write', '--per-run', '0.001')
    assert re.search(r'^12: the budget is reached \(page 1: worst case \$0\.\d+, \$0\.0010 left of the budget; 1 pages left '
                     r'for a later run\); read again on a later run$', out, re.M)
    assert out.splitlines()[-1] == 'spent 0.0000 (ceiling 0.00)'
    assert claude.requests() == [] and not Issue.objects.filter(number=13).exists()

    settings.OCR_BUDGET_USD = 10.0          # the run's ceiling is its own process's: a new run starts from the cap
    out, _ = run('fetch_conventions', '--kept', '--write', '--per-run', '1')
    for number in (12, 13):
        issue = Issue.objects.get(edition='conventions_ar', number=number)
        assert issue.document.path == f'issues/eci_ar/ECI_{number}_ar.pdf'
        assert issue.document.pages.get().text_source == TextSource.OCR
    assert not Issue.objects.filter(number=14).exists()                                 # not held: never fetched
    assert sgg.asked == [] and out.splitlines()[-1].startswith('spent 0.00')
