"""The OCR trial of 18 Oct 2026, as a stranger reruns it: the sample files registered (`ingest_samples`), the selected
pages read by each engine, never twice and never paid without --write (`ocr_trial`), then scored (`ocr_report`). The
model is the API's stand-in (claude.py); Tesseract and the files are real."""
import io
import json
from datetime import UTC, datetime

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.sources.models import Document, Issue, OcrRun, Page
from apps.sources.services.ocr import SpendingNotAllowed
from apps.sources.tests.bo import DECREE, images, install, write_pdf

pytestmark = pytest.mark.django_db

READ = '\n'.join(DECREE)


def run(*args) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def samples(root):
    folder = root / 'samples'
    write_pdf(folder / 'bo_ar' / 'BO_7600_ar.pdf', [DECREE])
    write_pdf(folder / 'court' / 'decision.pdf', [DECREE, []])
    (folder / 'code').mkdir()
    (folder / 'code' / 'doc.html').write_text('<html><body>الفصل 1</body></html>')
    (folder / 'manifest.json').write_text(json.dumps([
        {'kind': 'bo_issue', 'edition': 'general_ar', 'number': 7600, 'date': '2026-11-02', 'lang': 'ar',
         'path': 'bo_ar/BO_7600_ar.pdf', 'url': 'https://www.sgg.gov.ma/BO/AR/2026/BO_7600_Ar.pdf'},
        {'kind': 'court_decision', 'lang': 'ar', 'path': 'court/decision.pdf', 'url': 'https://www.cour.example/d.pdf',
         'title': 'قرار', 'court': 'المحكمة الدستورية', 'other': 'not kept'},
        {'kind': 'code_html', 'lang': 'ar', 'path': 'code/doc.html', 'url': 'a page saved by hand', 'folder': 'code'},
    ], ensure_ascii=False))


def test_the_trial_registers_reads_each_page_once_and_scores_it(settings, tmp_path, monkeypatch):
    claude = install(monkeypatch, settings, tmp_path, lambda cid, params: READ)
    samples(tmp_path)
    assert run('ingest_samples').splitlines() == ['samples/bo_ar/BO_7600_ar.pdf: 1 pages',
                                                  'samples/court/decision.pdf: 2 pages', 'samples/code/doc.html: - pages']
    bo, court, html = Document.objects.order_by('pk')
    assert (bo.source, bo.kind, bo.url, bo.issue.number, str(bo.issue.date)) == \
        ('sgg_bo', 'bo_issue', 'https://www.sgg.gov.ma/BO/AR/2026/BO_7600_Ar.pdf', 7600, '2026-11-02')
    assert (court.source, court.kind, court.title, court.meta) == \
        ('constitutional_court', 'court_decision', 'قرار', {'court': 'المحكمة الدستورية'})
    assert (html.source, html.kind, html.url, html.mime, html.meta) == ('other', 'code_page', '', 'text/html', {'folder': 'code'})
    assert not html.pages.exists()
    run('ingest_samples')                                                  # a second run registers nothing twice
    assert Document.objects.count() == 3 and Issue.objects.count() == 1

    (tmp_path / 'samples' / 'ocr_selection.json').write_text(json.dumps([
        {'path': 'samples/bo_ar/BO_7600_ar.pdf', 'index': 0, 'group': 'digital_ar'}]))
    with pytest.raises(SpendingNotAllowed):
        run('ocr_trial', '--engines', 'haiku')
    assert not OcrRun.objects.exists()

    out = run('ocr_trial', '--engines', 'haiku,opus', '--write')
    assert [line for line in out.splitlines() if 'batch' not in line] == [     # less the batches' own log
        'haiku: 1 pages, $0.0002', 'opus: 1 pages, $0.0080', 'spent so far: $0.0082 of $10.00']
    [request] = claude.requests()[:1]
    assert request['params']['messages'][0]['content'][1]['text'] == 'Transcribe this Arabic page.'
    assert images(request['params'])[0].width == 1596
    out = run('ocr_trial', '--engines', 'haiku,sonnet', '--now', '--write')     # haiku has read it: only sonnet now
    [line, total] = out.splitlines()
    assert line.startswith('sonnet samples/bo_ar/BO_7600_ar.pdf p.1: 400 tokens out, $0.008000, ') and total == 'spent so far: $0.0162 of $10.00'
    assert len(claude.sent) == 1 and claude.sent[0]['model'] == 'claude-sonnet-5-5'
    runs = {r.engine: r for r in OcrRun.objects.all()}
    assert runs['claude-sonnet-5-5'].text == READ and runs['claude-sonnet-5-5'].variant == 'page-1596'
    assert runs['claude-haiku-5-5'].batch_id == 'msgbatch_01' and runs['claude-opus-5-5'].batch_id == 'msgbatch_02'

    run('ocr_report')
    report = json.loads((tmp_path / 'reports' / 'ocr_trial.json').read_text())
    assert report['spent_usd'] == 0.0162 and report['budget_usd'] == 10.0
    [page] = report['pages']
    assert page['against'] == 'text_layer' and page['layer_broken'] == ''
    for engine in ('claude-haiku-5-5', 'claude-sonnet-5-5', 'claude-opus-5-5'):
        assert page['engines'][engine]['cer'] == 0 and page['engines'][engine]['word_f1'] == 1.0
    assert report['summary']['digital_ar']['claude-opus-5-5'] == {
        'pages': 1, 'word_f1': 1.0, 'cer': 0.0, 'cost_per_page': 0.008, 'output_tokens_per_page': 400}


@pytest.mark.needs('tesseract')
def test_tesseract_reads_a_trial_page_for_free_and_once(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    samples(tmp_path)
    run('ingest_samples')
    (tmp_path / 'samples' / 'ocr_selection.json').write_text(json.dumps([
        {'path': 'samples/bo_ar/BO_7600_ar.pdf', 'index': 0, 'group': 'digital_ar'},
        {'path': 'samples/court/decision.pdf', 'index': 1, 'group': 'scan_ar'}]))
    out = run('ocr_trial', '--limit', '1')                 # tesseract is the default engine, and free
    assert out.splitlines()[0].startswith('tesseract samples/bo_ar/BO_7600_ar.pdf p.1: ') and out.splitlines()[1] == 'spent so far: $0.0000 of $10.00'
    run_ = OcrRun.objects.get()
    assert run_.engine == 'tesseract-5' and run_.cost_usd == 0 and 'المستهلك' in run_.text
    assert run('ocr_trial', '--limit', '1').splitlines() == ['spent so far: $0.0000 of $10.00']   # never twice


def test_a_selected_page_not_registered_stops_the_trial(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    (tmp_path / 'samples').mkdir()
    (tmp_path / 'samples' / 'ocr_selection.json').write_text(json.dumps([{'path': 'samples/x.pdf', 'index': 3, 'group': 'g'}]))
    with pytest.raises(CommandError, match=r'No page 3 in samples/x\.pdf: run ingest_samples first'):
        run('ocr_trial')


def _scored(path, index, layer, runs):
    doc, _ = Document.objects.get_or_create(
        path=path, defaults={'source': 'sgg_bo', 'kind': 'bo_issue', 'sha256': path, 'mime': 'application/pdf', 'bytes': 1,
                             'language': 'fr' if '_fr' in path else 'ar', 'fetched_at': datetime(2026, 10, 18, tzinfo=UTC)})
    page = Page.objects.create(document=doc, index=index, kind='scan', layer_text=layer)
    for engine, text, cost in runs:
        OcrRun.objects.create(page=page, engine=engine, text=text, cost_usd=cost, input_tokens=100, output_tokens=len(text))


def test_scans_and_broken_layers_are_scored_against_opus_and_each_group_averaged(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    printed = 'Article premier Le présent arrêté'
    _scored('samples/bo_fr/BO_7500_fr.pdf', 0, '', [('claude-opus-5-5', printed, '0.01'),
                                                     ('claude-haiku-5-5', 'Article premier Le présent', '0.001')])
    _scored('samples/bo_fr/BO_7544_fr.pdf', 40, 'Ø§Ù„Ù…Ø§Ø¯Ø©', [('claude-opus-5-5', printed, '0.01'),
                                                                  ('claude-haiku-5-5', printed, '0.001')])
    # No Opus reading: nothing to score against, yet its cost and length count in the group's.
    _scored('samples/bo_fr/BO_7501_fr.pdf', 0, '', [('tesseract-5', 'Artic1e premier', '0'),
                                                     ('claude-haiku-5-5', 'Article', '0.005')])
    _scored('samples/bo_fr/BO_7502_fr.pdf', 0, '', [('claude-opus-5-5', printed, '0.02'),
                                                     ('claude-haiku-5-5', 'Artic1e premier Le présent arrêté ici', '0.003')])
    (tmp_path / 'samples').mkdir()
    (tmp_path / 'samples' / 'ocr_selection.json').write_text(json.dumps([
        {'path': 'samples/bo_fr/BO_7500_fr.pdf', 'index': 0, 'group': 'scan_fr'},
        {'path': 'samples/bo_fr/BO_7544_fr.pdf', 'index': 40, 'group': 'digital_fr'},
        {'path': 'samples/bo_fr/BO_7501_fr.pdf', 'index': 0, 'group': 'scan_fr'},
        {'path': 'samples/bo_fr/BO_7502_fr.pdf', 'index': 0, 'group': 'scan_fr'}]))
    out = run('ocr_report')
    report = json.loads((tmp_path / 'reports' / 'ocr_trial.json').read_text())
    scan, broken, alone, other = report['pages']
    assert scan['against'] == 'opus' and 'cer' not in scan['engines']['claude-opus-5-5']
    assert scan['engines']['claude-haiku-5-5']['word_f1'] == pytest.approx(0.8889, abs=1e-4)
    assert broken['against'] == 'opus' and broken['layer_broken'] == 'Arabic table extracted as mojibake'
    assert broken['engines']['claude-haiku-5-5']['cer'] == 0
    assert 'cer' not in alone['engines']['tesseract-5'] and 'cer' not in alone['engines']['claude-haiku-5-5']
    summary = report['summary']
    assert set(summary) == {'scan_fr', 'digital_fr_layer_broken'}
    # A group's figures are the means of its pages: Haiku's scores over the two pages Opus read (they differ), its
    # cost and length over all three.
    one, two = scan['engines']['claude-haiku-5-5'], other['engines']['claude-haiku-5-5']
    assert one['word_f1'] != two['word_f1'] and one['cer'] != two['cer']
    assert summary['scan_fr']['claude-haiku-5-5'] == {
        'pages': 3, 'word_f1': round((one['word_f1'] + two['word_f1']) / 2, 4), 'cer': round((one['cer'] + two['cer']) / 2, 4),
        'cost_per_page': 0.003, 'output_tokens_per_page': round((26 + 7 + 37) / 3)}
    assert summary['scan_fr']['claude-opus-5-5'] == {'pages': 2, 'word_f1': None, 'cer': None, 'cost_per_page': 0.015,
                                                     'output_tokens_per_page': 33}
    assert summary['scan_fr']['tesseract-5'] == {'pages': 1, 'word_f1': None, 'cer': None, 'cost_per_page': 0.0,
                                                 'output_tokens_per_page': 15}
    assert summary['digital_fr_layer_broken']['claude-haiku-5-5']['word_f1'] == 1.0
    assert report['spent_usd'] == 0.05
    assert out.splitlines()[0] == 'scan_fr' and out.splitlines()[-1] == 'spent $0.05 of $10.0'
