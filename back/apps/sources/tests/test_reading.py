"""Pages read by the model as the pipeline sends them: a landscape table printed on its side read again turned upright
and kept that way, a page's columns read on their own, a page that lost lines read again in halves, and nothing sent
when there is nothing to read. The model is the API's stand-in (claude.py); the files and their images are real."""
import io
import re

import pytest
from django.core.management import call_command
from PIL import Image

from apps.sources.models import OcrRun, Page, TextSource
from apps.sources.services import ocr
from apps.sources.services.render import render_columns, render_page, render_strips
from apps.sources.tests.bo import DECREE, images, install, register, write_pdf

pytestmark = pytest.mark.django_db

HAIKU = 'claude-haiku-5-5'
WHOLE = '\n'.join(DECREE)


def process(*args, **opts) -> str:
    out = io.StringIO()
    call_command('process_issue', *args, stdout=out, **opts)
    return out.getvalue()


def test_a_page_printed_on_its_side_is_read_again_turned_upright_and_keeps_that_reading(settings, tmp_path, monkeypatch):
    def model(cid, params):
        # Read on its side the model misses rows; turned upright it reads them all.
        return WHOLE if cid.startswith('t') else DECREE[0]
    claude = install(monkeypatch, settings, tmp_path, model)
    write_pdf(tmp_path / 'issues' / 'bo_ar' / 'BO_7600_ar.pdf', [DECREE], turned=True)
    out = process('7600', '--write', steps='ingest,ocr', date='2026-11-02')
    assert '1 sideways pages, read again turned upright: 0' in out and 'column by column' not in out
    page = Page.objects.get()
    assert sorted(OcrRun.objects.values_list('variant', flat=True)) == ['page-1596', 'turned-1596']
    assert page.text == WHOLE and page.text_source == TextSource.OCR
    whole, turned = sorted(claude.requests(), key=lambda r: r['custom_id'])
    assert (whole['custom_id'], turned['custom_id']) == (f'p{page.pk}', f't{page.pk}')
    assert turned['params']['max_tokens'] == 16000 and whole['params']['max_tokens'] == 8000
    upright, = images(turned['params'])
    assert upright.size == images(whole['params'])[0].size[::-1]                 # a quarter turn of the page's image
    # Read again, nothing more is sent: the page has both its readings.
    process('7600', '--write', steps='ocr')
    assert len(claude.requests()) == 2


def test_a_born_digital_french_page_keeps_its_layer_and_nothing_is_sent(settings, tmp_path, monkeypatch):
    claude = install(monkeypatch, settings, tmp_path, lambda cid, params: 'Article premier')
    write_pdf(tmp_path / 'issues' / 'bo_fr' / 'BO_7600_fr.pdf', [['Article premier. ' * 30]])
    process('7600', '--write', steps='ingest,ocr', date='2026-11-02', edition='translation_fr')
    assert claude.requests() == [] and not OcrRun.objects.exists()
    assert Page.objects.get().text_source == TextSource.LAYER


def column_model(cid, params):
    """The text a crop shows: a column, or one half of a column or a page, by what the request says it is."""
    ask = params['messages'][0]['content'][1]['text']
    if 'half' in ask:
        return f'{"upper" if "upper half" in ask else "lower"} half of {cid}'
    return re.sub(r'^p\d+', 'column ', cid)


def test_the_columns_of_the_pages_that_split_are_read_on_their_own(settings, tmp_path, monkeypatch):
    claude = install(monkeypatch, settings, tmp_path, column_model)
    two = register(tmp_path, 7600, [DECREE]).document.pages.get()
    side = register(tmp_path, 7601, [DECREE]).document.pages.get()
    write_pdf(tmp_path / 'issues' / 'bo_ar' / 'BO_7601_ar.pdf', [DECREE], turned=True)    # the same file, set sideways
    ocr.allow_spending(log=lambda line: None)          # as the archive's commands do, given --write
    assert ocr.ocr_columns_batch([side], HAIKU, width=1596) == [] and claude.requests() == []
    assert not (tmp_path / settings.LLM_LEDGER).exists()                # no batch opened, not even an empty one

    [run] = ocr.ocr_columns_batch([two, side], HAIKU, width=1596)
    assert (run.page, run.variant, run.image_px, run.text) == (two, 'columns-1596', '1596w/2', 'column c0\n\ncolumn c1')
    assert (run.input_tokens, run.output_tokens, str(run.cost_usd), run.stop_reason) == (4000, 800, '0.000400', 'end_turn,end_turn')
    right, left = (images(r['params'])[0] for r in claude.requests())
    assert right.width + left.width == 1596 and right.height == left.height
    assert all(r['params']['messages'][0]['content'][1]['text'] == ocr.COLUMN_ASK.format(lang='Arabic')
               for r in claude.requests())


def test_a_page_that_lost_lines_is_read_again_in_halves(settings, tmp_path, monkeypatch):
    claude = install(monkeypatch, settings, tmp_path, column_model)
    page = register(tmp_path, 7600, [DECREE]).document.pages.get()
    side = register(tmp_path, 7601, [DECREE]).document.pages.get()
    write_pdf(tmp_path / 'issues' / 'bo_ar' / 'BO_7601_ar.pdf', [DECREE], turned=True)
    OcrRun.objects.create(page=page, engine=HAIKU, variant='page-1596', text='الجريدة الرسمية عدد 7600\nنص')
    ocr.allow_spending(log=lambda line: None)
    assert ocr.ocr_strips_batch([(side, True)], HAIKU, width=1596) == [] and claude.requests() == []
    assert not (tmp_path / settings.LLM_LEDGER).exists()

    by_columns, by_page = ocr.ocr_strips_batch([(page, True), (side, False)], HAIKU, width=1596)
    # Each column's halves in reading order, after the page's running head; the page whole in two halves.
    assert (by_columns.page, by_columns.variant, by_columns.image_px) == (page, 'strips-1596', '1596w/4')
    assert by_columns.text == (f'الجريدة الرسمية عدد 7600\nupper half of p{page.pk}s0\nlower half of p{page.pk}s1\n'
                               f'upper half of p{page.pk}s2\nlower half of p{page.pk}s3')
    assert (by_page.page, by_page.image_px) == (side, '1596w/2')
    assert by_page.text == f'upper half of p{side.pk}s0\nlower half of p{side.pk}s1'
    assert by_columns.input_tokens == 8000 and str(by_columns.cost_usd) == '0.000800'
    top, bottom = (images(r['params'])[0] for r in claude.requests() if r['custom_id'].startswith(f'p{side.pk}'))
    with Image.open(render_page(side)) as whole:
        assert top.width == bottom.width == 1596 and top.height + bottom.height == whole.height
    kept = render_strips(page, 1596, columns=True)
    assert [p.name for p in kept] == [f'0000-1596-cs{i}.png' for i in range(4)]
    assert render_strips(page, 1596, columns=True) == kept                    # drawn once


def test_nothing_to_read_sends_nothing(settings, tmp_path, monkeypatch):
    claude = install(monkeypatch, settings, tmp_path, column_model)
    side = register(tmp_path, 7601, [DECREE]).document.pages.get()
    write_pdf(tmp_path / 'issues' / 'bo_ar' / 'BO_7601_ar.pdf', [DECREE], turned=True)
    assert ocr.readings_in_parts([], [], [], HAIKU) is None
    assert ocr.ocr_readings_batch([], [], [], HAIKU) is None
    assert ocr.ocr_readings_batch([], [], [side], HAIKU) is None        # a sideways page has no columns to send
    assert claude.requests() == [] and not OcrRun.objects.exists()
    assert not (tmp_path / settings.LLM_LEDGER).exists()


def test_a_blank_page_has_no_columns(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    page = register(tmp_path, 7600, [[]]).document.pages.get()
    assert render_columns(page, upright=True) is None
