"""The free commands on pages and issues: where the budget stands, the Hijri dates read from the mastheads, each page's
reading measured, each page's best reading kept again. Nothing here is paid; the pages are real files where a command
reads them."""
import io
import json
import os
from datetime import UTC, date, datetime

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from apps.sources.models import Document, Issue, OcrRun, Page, TextSource
from apps.sources.services.quality import fingerprint
from apps.parliament.tests.pdfs import write_pdf
from apps.sources.services.issue import register as register_issue
from apps.sources.tests.bo import DECREE, letters, register

pytestmark = pytest.mark.django_db

HAIKU = 'claude-haiku-5-5'


def run(*args) -> str:
    out = io.StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def bo(number, day, first_page='', layer=''):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'h{number}', path=f'BO_{number}.pdf',
                                  mime='application/pdf', bytes=1, language='ar', fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    issue = Issue.objects.create(edition='general_ar', number=number, date=day, document=doc)
    if first_page is not None:
        Page.objects.create(document=doc, index=0, kind='scan', text=first_page, layer_text=layer)
    return issue


# ── budget ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_budget_says_what_is_spent_held_and_left(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    settings.OCR_BUDGET_USD = 5.0
    page = Page.objects.create(document=bo(7600, date(2026, 11, 2), first_page=None).document, index=0, kind='scan')
    OcrRun.objects.create(page=page, engine=HAIKU, cost_usd='0.25')
    (tmp_path / 'reports').mkdir()
    (tmp_path / settings.LLM_LEDGER).write_text(json.dumps([{'kind': 'texts', 'cost_usd': 0.5}]))
    (tmp_path / 'reports' / 'inflight.json').write_text(json.dumps({
        'mine': {'worst': '1.25', 'pid': os.getpid(), 'what': 'readings'},
        'gone': {'worst': '9', 'pid': 999_999_999, 'what': 'a dead worker'}}))     # a dead process holds nothing
    assert run('budget').strip() == 'spent $0.7500, in flight $1.2500, cap $5.00, left $3.0000'
    assert run('budget', '--left').strip() == '3.0000'


# ── read_hijri_dates ───────────────────────────────────────────────────────────────────────────────────────────────

def test_the_hijri_dates_are_read_from_the_mastheads_and_kept_with_write():
    masthead = 'عدد 7465 مكرر 25 جمادى الآخرة 1447 (16 ديسمبر 2025)'
    dated = bo(7465, date(2025, 12, 16), first_page='', layer=masthead)        # no reading yet: its layer is read
    wrong = bo(7466, date(2025, 12, 18), first_page='عدد 7466 25 جمادى الآخرة 1447 (16 ديسمبر 2025)')
    bo(7467, date(2025, 12, 22), first_page=None)                               # no page
    kept = bo(7468, date(2026, 1, 1), first_page='عدد 7468 11 رجب 1447 (فاتح يناير 2026)')
    Issue.objects.filter(pk=kept.pk).update(hijri_date='as printed before')
    Issue.objects.create(edition='general_ar', number=7469, date=date(2026, 1, 5))   # no file at all: never asked

    assert run('read_hijri_dates').strip() == '1 of 3 issues dated in Hijri (not written: --write)'
    assert not Issue.objects.exclude(hijri_date='').exclude(pk=kept.pk).exists()
    assert run('read_hijri_dates', '--write').strip() == '1 of 3 issues dated in Hijri'
    dated.refresh_from_db()
    wrong.refresh_from_db()
    assert dated.hijri_date == '25 جمادى الآخرة 1447' and wrong.hijri_date == ''
    assert run('read_hijri_dates', '--all', '--write').strip() == '2 of 4 issues dated in Hijri'
    kept.refresh_from_db()
    assert kept.hijri_date == '11 رجب 1447'


# ── measure_pages ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_each_page_s_reading_is_measured_once_unless_all_are_asked(monkeypatch):
    from apps.sources.management.commands import measure_pages
    monkeypatch.setattr(measure_pages, 'CHUNK', 2)          # the pages are stored in chunks: a full one, then the rest
    doc = bo(7600, date(2026, 11, 2), first_page=None).document
    layer = Page.objects.create(document=doc, index=0, kind='text_layer', text_source=TextSource.LAYER,
                                layer_text='نص', layer_letters=900, text='نص')
    scan = Page.objects.create(document=doc, index=1, kind='scan', text_source=TextSource.OCR, text='الفصل الأول')
    blank = Page.objects.create(document=doc, index=2, kind='blank')
    done = Page.objects.create(document=doc, index=3, kind='scan', text_source=TextSource.OCR, text='الفصل الثاني')
    Page.objects.filter(pk=done.pk).update(quality={'of': fingerprint(done), 'reading': 'kept as it was', 'check': None})
    stale = Page.objects.create(document=doc, index=4, kind='scan', text_source=TextSource.OCR, text='الفصل الثالث',
                                quality={'of': 'an older reading', 'reading': 'none', 'check': None})

    assert run('measure_pages').strip() == 'pages measured: 4, already measured: 1'
    readings = {p.pk: p.quality for p in Page.objects.all()}
    assert readings[layer.pk] == {'of': fingerprint(layer), 'reading': 'layer', 'check': None}
    assert readings[scan.pk]['reading'] == 'scan' and readings[blank.pk]['reading'] == 'none'
    assert readings[stale.pk] == {'of': fingerprint(stale), 'reading': 'scan', 'check': None}
    assert readings[done.pk]['reading'] == 'kept as it was'
    assert run('measure_pages', '--all').strip() == 'pages measured: 5, already measured: 0'
    assert Page.objects.get(pk=done.pk).quality['reading'] == 'scan'


# ── keep_best_readings ─────────────────────────────────────────────────────────────────────────────────────────────

FRENCH = ['Décret n° 2-26-100 du 2 novembre 2026 pris pour l’application de la loi n° 31-08',
          'édictant des mesures de protection du consommateur.', 'Article premier. – Les modalités d’information',
          'du consommateur sur les prix des produits et services sont fixées par arrêté.',
          'Article 2. – Le ministre de l’industrie et du commerce est chargé de son exécution.']


def _read(issue, texts):
    pages = list(issue.document.pages.order_by('index'))
    for page, said in zip(pages, texts, strict=False):
        for text in said:
            OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text=text)
    return pages


def test_each_named_issue_keeps_its_pages_best_readings(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    issue = register(tmp_path, 7600, [DECREE, DECREE])
    whole = '\n'.join(DECREE)
    # Page 0: the reading nearest its layer's letters wins, the model's remark out; page 1, never read, keeps its layer.
    p0, p1 = _read(issue, [['المادة الأولى', whole + '\n\nLet me transcribe carefully.'], []])
    other = register(tmp_path, 7601, [DECREE])
    _read(other, [['مرسوم']])
    # The French edition's issue of the same number, read by the model too: only --edition names it.
    french = register_issue(write_pdf(tmp_path / 'issues' / 'bo_fr' / 'BO_7600_fr.pdf', [FRENCH]), number=7600,
                            edition='translation_fr', day=date(2026, 11, 2))
    [fr] = _read(french, [['\n'.join(FRENCH) + '\n\nLet me transcribe carefully.']])

    assert run('keep_best_readings', '7600').strip() == '7600: 1 pages changed: 0'
    p0.refresh_from_db()
    p1.refresh_from_db()
    assert p0.text == whole and p0.text_source == TextSource.OCR
    assert p0.quality['reading'] == 'confirmed' and p0.quality['of'] == fingerprint(p0)
    assert p1.text_source == TextSource.LAYER
    assert Page.objects.get(document=other.document).text_source == TextSource.LAYER     # not named: left
    fr.refresh_from_db()
    assert fr.text_source == TextSource.LAYER                                             # another edition: left
    assert run('keep_best_readings', '7600').strip() == ''                                # again: nothing changes
    assert run('keep_best_readings', '7600', '--edition', 'translation_fr').strip() == '7600: 1 pages changed: 0'
    fr.refresh_from_db()
    assert fr.text == '\n'.join(FRENCH) and fr.text_source == TextSource.OCR


def test_every_issue_or_a_recount_runs_only_on_the_database_named(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    issue = register(tmp_path, 7600, [DECREE])
    [page] = _read(issue, [['\n'.join(DECREE[:5])]])
    register(tmp_path, 7601, [DECREE])                       # never read by the model: not among «every issue»
    Page.objects.filter(pk=page.pk).update(layer_letters=3)   # counted before ingest counted as it does now
    for args in [(), ('7600', '--recount'), ('--yes-on', 'another_database')]:
        with pytest.raises(CommandError, match='--yes-on'):
            run('keep_best_readings', *args)
    page.refresh_from_db()
    assert page.layer_letters == 3 and page.text_source == TextSource.LAYER

    out = run('keep_best_readings', '--recount', '--yes-on', connection.settings_dict['NAME'])
    assert out.splitlines() == ['layer letters recounted on 1 pages', '7600: 1 pages changed: 0']
    page.refresh_from_db()
    assert page.layer_letters == letters(DECREE) and page.text == '\n'.join(DECREE[:5])
