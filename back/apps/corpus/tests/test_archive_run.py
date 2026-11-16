"""`manage.py archive` (the Bulletin-to-1956 review): the plan's PDFs registered, where the run stands, the pilot's
measures, and the texts phase taking its issues a chunk at a time, stopping alone when the key or the budget is spent.
The model's answers come from a stand-in for the API; the PDFs are made here."""
import json
from datetime import date
from decimal import Decimal
from io import StringIO

import pypdfium2 as pdfium
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.tests import claude
from apps.corpus.tests.test_process_issue import DATA, ORDER
from apps.corpus.tests.test_recut import PAGES as READ, TOC
from apps.sources.models import Document, Edition, Issue, OcrRun, Page
from apps.sources.services import archive
from apps.sources.services.ocr import SpendingNotAllowed

pytestmark = pytest.mark.django_db
HAIKU = 'claude-haiku-5-5'
# The pages as read, each with its running head: the texts step numbers the pages again by their folios (Z27).
# Its last page also prints a minister's decision, a special text of the third kind.
PAGES = [f'الجريدة الرسمية {1529 + i}\n{text}' for i, text in enumerate(READ)]
PAGES[-1] += ('\nمقرر لوزير التشغيل رقم 12.25 صادر في 14 من رجب 1446 (15 يناير 2025) بتعيين أعضاء لجنة.\n'
              'المادة الأولى\nيعين أعضاء اللجنة.')
DECISION = {'section': 'special', 'rubric': '', 'type': 'decision', 'number_as_printed': '12.25', 'page': 1531,
            'title': 'مقرر لوزير التشغيل رقم 12.25 صادر في 14 من رجب 1446 (15 يناير 2025) بتعيين أعضاء لجنة',
            'signed_on_gregorian': '2025-01-15', 'signed_on_hijri': ''}


def run(*args, **opts) -> str:
    out = StringIO()
    call_command('archive', *args, stdout=out, **opts)
    return out.getvalue()


def plan(tmp_path, keys, pilot=(), dates=None):
    (tmp_path / 'archive').mkdir(exist_ok=True)
    (tmp_path / 'archive' / 'plan.json').write_text(json.dumps({'pilot': list(pilot), 'issues': [
        {'key': k, 'year': 2025, 'date': (dates or {}).get(k, '2025-03-03'), 'url': f'https://example.org/BO_{k}_Ar.pdf',
         'path': f'2025/BO_{k}_Ar.pdf'} for k in keys]}))


def held(number, pages=PAGES, day=date(2025, 3, 3)):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=str(number).ljust(64, '0'),
                                  path=f'BO_{number}_ar.pdf', mime='application/pdf', language='ar', bytes=1,
                                  fetched_at=timezone.now(), page_count=len(pages))
    for i, text in enumerate(pages):
        Page.objects.create(document=doc, index=i, printed_number=1529 + i, text=text)
    return Issue.objects.create(edition=Edition.GENERAL_AR, number=number, date=day, document=doc, first_page_number=1529)


def contents(tmp_path, key, toc):
    work = tmp_path / 'reports' / 'issues' / key
    work.mkdir(parents=True, exist_ok=True)
    (work / 'toc.json').write_text(json.dumps(toc, ensure_ascii=False))


def blank_pdf(path, pages=2):
    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.save(str(path))


def test_register_links_each_plans_pdf_once_and_sets_aside_one_pdfium_cannot_open(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    with pytest.raises(CommandError, match='--pdfs is needed'):
        call_command('archive', 'register')
    held(2685)
    plan(tmp_path, ['2685', '2686', '2687', '2688-bis'])
    pdfs = tmp_path / 'pdfs'
    (pdfs / '2025').mkdir(parents=True)
    (pdfs / '2025' / 'BO_2687_Ar.pdf').write_bytes(b'not a pdf')
    blank_pdf(pdfs / '2025' / 'BO_2688-bis_Ar.pdf')
    said = run('register', pdfs=str(pdfs))
    assert f'2686: no PDF yet at {pdfs}/2025/BO_2686_Ar.pdf' in said
    assert '2687: not registered, see state/register/2687.error' in said
    assert said.rstrip().endswith('registered 1; 2 in all')
    issue = Issue.objects.get(number=2688, suffix='bis')
    assert issue.document.meta['archive'] == '2025/BO_2688-bis_Ar.pdf' and issue.document.pages.count() == 2
    assert (issue.date, issue.document.url) == (date(2025, 3, 3), 'https://example.org/BO_2688-bis_Ar.pdf')
    assert (tmp_path / 'issues' / 'bo_ar' / 'BO_2688-bis_ar.pdf').resolve() == pdfs / '2025' / 'BO_2688-bis_Ar.pdf'
    assert (archive.root() / 'state' / 'register' / '2687.error').exists()
    # Run again: what is registered is passed over.
    assert run('register', pdfs=str(pdfs)).rstrip().endswith('registered 0; 2 in all')


def test_status_says_where_the_run_stands(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    plan(tmp_path, ['7383', '7384'])
    issue = held(7383)
    page = issue.document.pages.first()
    OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text='نص', cost_usd=Decimal('0.001'))
    OcrRun.objects.create(page=page, engine=HAIKU, variant='columns-3192', text='نص', cost_usd=Decimal('0.002'))
    archive.mark('read', '7383', 'done')
    archive.mark('read', '7384', 'error', 'Traceback …\nRuntimeError: the API answered 529')
    archive.mark('catalog', '7384', 'claim', 'host 1')
    (tmp_path / 'tess').mkdir()
    (tmp_path / 'tess' / 'BO_7383_Ar.json.gz').write_bytes(b'')
    (archive.root() / 'doubts').mkdir()
    (archive.root() / 'doubts' / '7383.json').write_text(json.dumps({'pages': [3, 5]}))
    (archive.root() / 'STOP').write_text('stopped for the night')
    out = json.loads(run('status', '--json'))
    assert {k: out[k] for k in ('issues', 'registered', 'tesseract_issues', 'pages_read', 'readings', 'doubtful_pages',
                                'stopped')} == {'issues': 2, 'registered': 1, 'tesseract_issues': 1, 'pages_read': 1,
                                                'readings': 2, 'doubtful_pages': 2,
                                                'stopped': 'STOP: stopped for the night'}
    assert (Decimal(out['spent']), Decimal(out['in_flight']), out['budget']) == (Decimal('0.003'), 0, 10.0)
    assert out['phases']['read'] == {'done': 1, 'claim': 0, 'error': 1}
    assert out['phases']['catalog'] == {'done': 0, 'claim': 1, 'error': 0}
    assert out['last_errors'] == ['read/7384: RuntimeError: the API answered 529']
    assert '            issues: 2\n' in run('status')


def test_report_gives_the_pilots_measures_by_variant(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    plan(tmp_path, ['7383', '7384'], pilot=['7383', '7384'])
    issue = held(7383)
    held(7384)                                                           # in the pilot, not done: left out
    for page in issue.document.pages.all():
        OcrRun.objects.create(page=page, engine=HAIKU, variant='columns-3192', text='الفصل الأول نص كامل',
                              cost_usd=Decimal('0.002'), input_tokens=8000, output_tokens=1800)
        OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text='الفصل الأول نص',
                              cost_usd=Decimal('0.001'), input_tokens=4000, output_tokens=1500)
        OcrRun.objects.create(page=page, engine='claude-sonnet-5-5', variant='page-1596', text='x')
    archive.mark('pilot', '7383', 'done', json.dumps({'texts': 3, 'found': 2, 'doubts': 1}))
    said = run('report')
    assert said.startswith('2025 7383: 2/3 texts found, 1 doubts, ') and said.count('\n') == 1
    assert 'page-1596 $0.003000 F1 0.8571' in said and 'columns-3192 $0.006000 F1 None' in said
    [row] = json.loads((archive.root() / 'pilot.json').read_text())
    assert (row['key'], row['year'], row['found'], row['texts'], row['doubts']) == ('7383', 2025, 2, 3, 1)
    assert row['variants']['page-1596'] == {'pages': 3, 'cost': '0.003000', 'in': 12000, 'out': 4500, 'ratio_median': 1.15,
                                            'f1_vs_columns_3192': 0.8571}
    # With --keys, the 1913–1955 pilot's own file.
    run('report', keys='7383')
    assert (archive.root() / 'pilot_1913.json').exists()


@pytest.fixture
def texts_phase(tmp_path, settings, monkeypatch):
    """Two issues read and catalogued; the API answers every text with 10.20's description."""
    answers = {'7383-t0': DATA, '7385-t0': DATA}
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: answers.get(cid))
    plan(tmp_path, ['7383', '7384', '7385', '7386'])
    for number in (7383, 7385):
        held(number)
        contents(tmp_path, str(number), [TOC[0], ORDER, DECISION])
        archive.mark('read', str(number), 'done')
    held(7386)                                                         # catalogued, not read yet: the texts step waits
    contents(tmp_path, '7386', TOC)
    return sent


def test_the_texts_phase_describes_a_kind_and_those_before_it_and_the_special_texts_by_code(texts_phase, tmp_path):
    said = run('work', 'texts', '--write', only='rules', code=True, chunk=2)
    assert 'texts-rules: nothing left for this worker' in said
    for key in ('7383', '7385'):
        summary = json.loads((archive.root() / 'state' / 'texts-rules' / f'{key}.done').read_text())
        assert {k: summary[k] for k in ('texts', 'found', 'by_code', 'sent', 'contents_again', 'chunk')} == {
            'texts': 3, 'found': 2, 'by_code': 1, 'sent': 1, 'contents_again': False, 'chunk': 2}
        law, order, decision = json.loads((tmp_path / 'reports' / 'issues' / key / 'texts.json').read_text())
        assert law['data'] == DATA and order['stop'] == 'code' and order['data']['number_as_printed'] == '148.25'
        assert (decision['data'], decision['stop'], decision['pages']) == (None, 'later', [1531, 1531])   # it waits
    # The law alone went to the model, both issues' in one batch; the order was described by code.
    assert [r['custom_id'] for r in texts_phase.requests()] == ['7383-t0', '7385-t0']
    assert not archive.done('texts-rules', '7386')


def test_the_general_texts_alone_are_described_with_general(texts_phase, tmp_path):
    run('work', 'texts', '--write', '--general', keys='7383')
    law, order, decision = json.loads((tmp_path / 'reports' / 'issues' / '7383' / 'texts.json').read_text())
    assert law['data'] == DATA and (order['data'], order['stop']) == (decision['data'], decision['stop']) == (None, 'later')


def test_a_worker_stops_alone_when_its_key_or_the_budget_is_spent_and_never_unasked(texts_phase, settings, monkeypatch):
    with pytest.raises(SpendingNotAllowed):
        run('work', 'texts', keys='7383')
    monkeypatch.setenv('ARCHIVE_KEY_NAME', 'second')
    texts_phase.refusals = [(400, 'Your credit balance is too low to access the Anthropic API.')]
    assert 'out of credit (second): ' in run('work', 'texts', '--write', keys='7383')
    assert 'credit balance is too low' in (archive.root() / 'NO_CREDIT-second').read_text()
    assert not archive.done('texts', '7383')
    assert not (archive.root() / 'state' / 'texts' / '7383.claim').exists()            # left for another worker
    settings.OCR_BUDGET_USD = 0.0
    assert 'budget reached: ' in run('work', 'texts', '--write', keys='7383')
    assert 'would pass the $0.00 budget' in (archive.root() / 'STOP_BUDGET').read_text()
    assert 'STOP_BUDGET: ' in run('work', 'texts', '--write', keys='7383')              # every worker stops on it
    assert texts_phase.requests() == []


def test_a_worker_takes_its_limit_and_passes_issues_not_held(texts_phase):
    said = run('work', 'texts', '--write', keys='7383,9999,7385', limit=1, chunk=1)
    assert archive.done('texts', '7383') and not archive.done('texts', '7385')
    assert 'nothing left' not in said


def test_a_contents_the_catalog_missed_is_read_again_by_halves_or_the_issue_is_set_aside(tmp_path, settings, monkeypatch):
    early = {**TOC[0], 'page': 1529, 'number_as_printed': '9.20'}
    answers = {'toc-7383': None, 'toc-7383-2-0': {'entries': [early, TOC[0]]}, 'toc-7383-2-1': {'entries': [TOC[0]]},
               '7383-t1': DATA}
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: answers.get(cid))
    plan(tmp_path, ['7383', '7384', '7387'])
    for number in (7383, 7384):
        held(number)
        contents(tmp_path, str(number), [])                              # the catalog read no entry
        archive.mark('read', str(number), 'done')
    held(7387, pages=['', '', ''])                                       # nothing read on its first pages
    contents(tmp_path, '7387', [])
    archive.mark('read', '7387', 'done')
    run('work', 'texts', '--write', chunk=3)
    # 7383's halves answered: each keeps the entries of its own pages.
    assert json.loads((tmp_path / 'reports' / 'issues' / '7383' / 'toc.json').read_text()) == [early, TOC[0]]
    assert json.loads((archive.root() / 'state' / 'texts' / '7383.done').read_text())['contents_again'] is True
    assert (archive.root() / 'state' / 'texts' / '7384.error').read_text() == \
        'contents not read, even in eighths (errored)'
    assert (archive.root() / 'state' / 'texts' / '7387.error').read_text() == 'no text on the contents pages'
    assert 'toc-7384-8-7' in [r['custom_id'] for r in sent.requests()]


def test_an_issue_travels_with_its_doubts_and_an_import_refuses_another_pdf(tmp_path, settings):
    import gzip

    from apps.sources.services import issue as issue_service
    settings.CORPUS_DIR = tmp_path / 'there'
    with pytest.raises(CommandError, match='--out is needed'):
        call_command('archive', 'export')
    with pytest.raises(CommandError, match='--french needs --keys'):
        call_command('archive', 'export', '--french', out=str(tmp_path / 'out'))
    with pytest.raises(CommandError, match='import needs --folder and --pdfs'):
        call_command('archive', 'import', folder=str(tmp_path / 'out'))
    blank_pdf(tmp_path / 'pdfs' / '2025' / 'BO_7383_Ar.pdf')
    link = tmp_path / 'there' / 'issues' / 'bo_ar' / 'BO_7383_ar.pdf'
    link.parent.mkdir(parents=True)
    link.symlink_to(tmp_path / 'pdfs' / '2025' / 'BO_7383_Ar.pdf')
    issue = issue_service.register(link, edition=Edition.GENERAL_AR, number=7383, day=date(2025, 3, 3))
    issue.document.meta = {'archive': '2025/BO_7383_Ar.pdf'}
    issue.document.save()
    Issue.objects.filter(pk=issue.pk).update(first_page_number=1341, hijri_date='2 رمضان 1446')
    plan(tmp_path / 'there', ['7383'])
    archive.mark('read', '7383', 'done')
    (archive.root() / 'doubts').mkdir()
    (archive.root() / 'doubts' / '7383.json').write_text(json.dumps({'median': 1.1, 'pages': [{'index': 1}]}))
    assert run('export', out=str(tmp_path / 'out'), keys='7383,9999').endswith('exported 1 issues to ' + str(tmp_path / 'out') + '\n')
    assert run('export', out=str(tmp_path / 'out')).endswith('exported 0 issues to ' + str(tmp_path / 'out') + '\n')
    # A page the file names that this PDF does not have is passed over.
    bundle = tmp_path / 'out' / '7383.json.gz'
    with gzip.open(bundle, 'rt', encoding='utf-8') as f:
        b = json.load(f)
    b['pages'].append({**b['pages'][0], 'index': 99})
    with gzip.open(bundle, 'wt', encoding='utf-8') as f:
        json.dump(b, f)
    Issue.objects.all().delete()
    Document.objects.all().delete()

    settings.CORPUS_DIR = tmp_path / 'here'
    said = run('import', folder=str(tmp_path / 'out'), pdfs=str(tmp_path / 'pdfs'))
    assert 'imported: 1 issues registered, 0 readings added, 0 issues read here before kept as they were' in said
    assert json.loads((tmp_path / 'here' / 'archive' / 'doubts' / '7383.json').read_text())['pages'] == [{'index': 1}]
    imported = Issue.objects.get(number=7383)
    assert (imported.first_page_number, imported.hijri_date) == (1341, '2 رمضان 1446')
    assert imported.document.pages.count() == 2
    assert imported.document.meta == {'archive': '2025/BO_7383_Ar.pdf', 'archive_read': True}
    # The same number from another file is left as it is.
    Document.objects.update(sha256='0' * 64)
    assert '7383: already here from another file; left as it is' in run(
        'import', folder=str(tmp_path / 'out'), pdfs=str(tmp_path / 'pdfs'))
    # A PDF here that is not the one the run read is refused.
    Issue.objects.all().delete()
    Document.objects.all().delete()
    blank_pdf(tmp_path / 'pdfs' / '2025' / 'BO_7383_Ar.pdf', pages=3)
    (tmp_path / 'here' / 'issues' / 'bo_ar' / 'BO_7383_ar.pdf').unlink()
    with pytest.raises(CommandError, match='7383: the PDF here is not the one the archive run read'):
        call_command('archive', 'import', folder=str(tmp_path / 'out'), pdfs=str(tmp_path / 'pdfs'))


def test_a_phase_takes_only_the_issues_ready_for_it(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    with pytest.raises(CommandError, match='work needs a phase'):
        call_command('archive', 'work')
    plan(tmp_path, ['7383', '7384', '7385'], pilot=['7383'], dates={'7384': '2025-03-10'})
    for number in (7383, 7384, 7385):
        held(number)
    archive.mark('pilot', '7383', 'done')
    assert run('work', 'pilot').endswith('pilot: nothing left for this worker\n')
    # By kind, the decisions that change another text first (7385's contents hold one), then the newest.
    contents(tmp_path, '7384', [{**ORDER, 'type': 'decision', 'title': 'مقرر بتعيين أعضاء'}])
    contents(tmp_path, '7385', [{**ORDER, 'type': 'decision', 'title': 'مقرر بتغيير المقرر رقم 12.20'}])
    (archive.root() / 'order.json').write_text(json.dumps(['7383', '7384', '7385']))
    from apps.corpus.management.commands.archive import Command
    assert Command().decisions_first(['7383', '7384', '7385']) == ['7385', '7384', '7383']
    # 7383 is not catalogued, 7384 was read whole before reading by kind, 7385 is waiting for Tesseract's witness …
    archive.mark('catalog', '7384', 'done')
    archive.mark('read', '7384', 'done')
    assert run('work', 'read', only='decisions').endswith('read-decisions: nothing left for this worker\n')
    # … and the fix is for issues read already.
    assert run('work', 'fix', keys='7383,7385').endswith('fix: nothing left for this worker\n')
