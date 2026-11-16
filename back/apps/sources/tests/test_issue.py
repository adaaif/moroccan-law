import hashlib
from pathlib import Path

import pytest
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.sources.models import Document, OcrRun, Page, PageKind
from apps.sources.services.issue import amounts, best_run, coverage, reading_check
from apps.sources.services.render import is_sideways, render_columns


def _page(tmp_path: Path, *, layer_letters=1000, pdf: Path | None = None) -> Page:
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(str(tmp_path).encode()).hexdigest(),
                                  path=pdf.name if pdf else 'none.pdf', mime='application/pdf', language='ar', bytes=1,
                                  fetched_at=timezone.now())
    return Page.objects.create(document=doc, index=0, kind=PageKind.TEXT_LAYER, layer_letters=layer_letters)


@pytest.mark.django_db
def test_coverage_counts_the_letters_read_against_the_text_layer(tmp_path):
    page = _page(tmp_path, layer_letters=1000)
    assert coverage(page, 'المادة 39 - ' * 100) == 0.6
    assert coverage(_page(tmp_path / 'scan', layer_letters=0), 'المادة') is None


@pytest.mark.django_db
def test_a_page_keeps_the_reading_closest_to_its_layer_not_the_newest(tmp_path, monkeypatch):
    monkeypatch.setattr('apps.sources.services.issue.is_sideways', lambda page: False)
    page = _page(tmp_path, layer_letters=1000)
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-1596', text='ب' * 450)
    columns = OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='columns-3192', text='ب' * 980)
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='columns-3192', text='ب' * 600)
    assert best_run(page, 'claude-haiku-5-5') == columns
    assert best_run(page, 'claude-sonnet-5-5') is None


def _two_column_pdf(path: Path, *, rule: bool, turned: bool = False) -> Path:
    """A page drawn like the BO: a header and its rule, then two columns of text lines."""
    image = Image.new('L', (1200, 1700), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 1140, 80), fill=0)          # the running header
    draw.rectangle((60, 110, 1140, 114), fill=0)        # the rule under it, full width
    for y in range(160, 1600, 40):
        draw.rectangle((620, y, 1140, y + 14), fill=0)  # right column
        draw.rectangle((60, y, 580, y + 14), fill=0)    # left column
    if rule:
        draw.rectangle((599, 150, 601, 1610), fill=0)
    if turned:
        image = image.rotate(-90, expand=True)
    image.save(path, 'PDF', resolution=150)
    return path


@pytest.mark.django_db
@pytest.mark.parametrize('rule', [True, False])
@pytest.mark.needs('tesseract')
def test_a_two_column_page_is_cut_between_its_columns_below_the_header(tmp_path, settings, rule):
    settings.CORPUS_DIR = tmp_path
    page = _page(tmp_path, layer_letters=0, pdf=_two_column_pdf(tmp_path / 'p.pdf', rule=rule))
    right, left = (Image.open(p) for p in render_columns(page))
    assert right.width == pytest.approx(left.width, rel=0.1)
    assert right.height < 0.95 * 2 * 1596 * 1700 / 1200   # the header is cut off


@pytest.mark.django_db
@pytest.mark.needs('tesseract')
def test_a_page_without_a_gutter_is_not_cut(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    image = Image.new('L', (1200, 1700), 255)
    draw = ImageDraw.Draw(image)
    for y in range(160, 1600, 40):
        draw.rectangle((60, y, 1140, y + 14), fill=0)   # full-width lines
    image.save(tmp_path / 'full.pdf', 'PDF', resolution=150)
    assert render_columns(_page(tmp_path, layer_letters=0, pdf=tmp_path / 'full.pdf')) is None


@pytest.mark.django_db
def test_a_table_page_is_checked_by_its_amounts_and_keeps_the_reading_with_most_of_them(tmp_path, monkeypatch):
    monkeypatch.setattr('apps.sources.services.issue.is_sideways', lambda page: False)
    page = _page(tmp_path, layer_letters=4000)
    page.layer_text = ' '.join(f'{n}.000,00' for n in range(100, 130))   # the layer holds 30 amounts
    page.save()
    assert amounts(page, '100.000,00 101.000,00 999.000,00') == (3, 2)
    assert reading_check(page, '100.000,00') == {'amounts_read': 1, 'amounts_in_layer': 1}
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-1596', text='100.000,00 ' * 4)
    fuller = OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-1596',
                                   text=' '.join(f'{n}.000,00' for n in range(100, 120)))
    assert best_run(page, 'claude-haiku-5-5') == fuller


@pytest.mark.django_db
def test_a_sideways_page_keeps_its_upright_reading_and_an_upright_page_never_does(tmp_path, monkeypatch):
    page = _page(tmp_path, layer_letters=1000)
    whole = OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-1596', text='ب' * 1000)
    turned = OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='turned-1596', text='ب' * 700)
    monkeypatch.setattr('apps.sources.services.issue.is_sideways', lambda page: True)
    assert best_run(page, 'claude-haiku-5-5') == turned
    monkeypatch.setattr('apps.sources.services.issue.is_sideways', lambda page: False)
    assert best_run(page, 'claude-haiku-5-5') == whole


@pytest.mark.django_db
def test_a_scan_is_turned_the_way_tesseract_says_and_a_sideways_page_is_never_cut(tmp_path, settings, monkeypatch):
    settings.CORPUS_DIR = tmp_path
    page = _page(tmp_path, layer_letters=0, pdf=_two_column_pdf(tmp_path / 'up.pdf', rule=True))
    monkeypatch.setattr('apps.sources.services.render._osd_rotation', lambda image: 0)
    assert not is_sideways(page)
    monkeypatch.setattr('apps.sources.services.render._osd_rotation', lambda image: 270)
    assert is_sideways(page)
    assert render_columns(page) is None


def test_grouped_amounts_are_read_both_ways_in_the_layer_which_reverses_their_groups():
    from apps.sources.services.issue import _amounts
    assert '421325037000' in _amounts('000 037 325 421', layer=True)
    assert '26292000' in _amounts('000 292 26', layer=True)
    assert _amounts('421.325.037.000 | 26 292 000 | 38.562,85') == ['3856285', '421325037000', '26292000']
    assert _amounts('الفصول 42 و 50 سنة 2026') == []


def test_amounts_copied_in_visual_order_are_put_back_and_law_numbers_are_left_alone():
    from apps.sources.services.issue import clean_reading
    assert clean_reading('| موارد الحسابات | 000 715 233 166 |') == '| موارد الحسابات | 166 233 715 000 |'
    assert clean_reading('رصيد (7) ...... 000 971 254 1-') == 'رصيد (7) ...... -1 254 971 000'
    assert clean_reading('مبلغ 000 000 200 درهم') == 'مبلغ 200 000 000 درهم'
    assert clean_reading('| 000 3 000 | - | 000 8 700 |') == '| 3 000 000 | - | 8 700 000 |'
    assert clean_reading('القانون رقم 103.12 و 421 325 037 000 و 26 292 000') == \
        'القانون رقم 103.12 و 421 325 037 000 و 26 292 000'


@pytest.mark.django_db
def test_pages_past_1400_are_numbered_by_their_headers_not_the_day(tmp_path):
    """BO 7278 (29 Feb 2024): its pages run 1397 to 1428; skipping every 14xx as a Hijri year left the day, «19»."""
    import datetime

    from apps.sources.models import Edition, Issue
    from apps.sources.services.issue import number_pages
    doc = _page(tmp_path).document
    doc.pages.all().delete()
    heads = ['السنة الثالثة عشرة بعد المائة - عدد 7278 19 شعبان 1445 (29 فبراير 2024)',
             '1398 الجريدة الرسمية عدد 7278 - 19 شعبان 1445 (29 فبراير 2024)',
             'عدد 7278 - 19 شعبان 1445 (29 فبراير 2024) الجريدة الرسمية 1399',
             '1400 الجريدة الرسمية عدد 7278 - 19 شعبان 1445 (29 فبراير 2024)',
             'عدد 7278 - 19 شعبان 1445 (29 فبراير 2024) الجريدة الرسمية 1401']
    for i, head in enumerate(heads):
        Page.objects.create(document=doc, index=i, kind=PageKind.TEXT_LAYER, text=head + '\nنص')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7278, date=datetime.date(2024, 2, 29), document=doc)
    assert number_pages(issue) == 1397
    assert doc.pages.get(index=4).printed_number == 1401


@pytest.mark.django_db
def test_a_short_issue_is_numbered_by_its_page_not_the_day_of_its_date_or_its_price(tmp_path):
    """BO 6964 bis (27 Feb 2021) has 3 pages: the day «15» outvoted its one numbered page, 1692."""
    import datetime

    from apps.sources.models import Edition, Issue
    from apps.sources.services.issue import number_pages
    doc = _page(tmp_path).document
    doc.pages.all().delete()
    heads = ['السنة العاشرة بعد المائة - عدد 6964 مكرر 15 رجب 1442 (27 فبراير 2021)',
             '1692 الجريدة الرسمية عدد 6964 مكرر - 15 رجب 1442 (27 فبراير 2021)',
             'ثمن النسخة بمقر المطبعة الرسمية : 10 دراهم']
    for i, head in enumerate(heads):
        Page.objects.create(document=doc, index=i, kind=PageKind.TEXT_LAYER, text=head + '\nنص')
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=6964, suffix='bis', date=datetime.date(2021, 2, 27),
                                 document=doc)
    assert number_pages(issue) == 1691
    assert doc.pages.get(index=1).printed_number == 1692


@pytest.mark.django_db
def test_a_pages_measure_is_kept_with_its_reading_and_worked_out_again_when_it_changes(tmp_path):
    # S11 of the performance audit: an issue's quality page counted every page's letters on each visit.
    from apps.sources.models import TextSource
    from apps.sources.services.quality import measure, measured, page_reading, store

    page = _page(tmp_path, layer_letters=600)
    page.text, page.text_source = 'نص المادة الأولى ' * 40, TextSource.OCR
    page.save()
    store([page])
    page.refresh_from_db()
    assert page.quality['reading'] == 'confirmed' and measured(page) is page.quality
    page.text = 'كلمة ' * 10                     # another reading: the kept measure is not of it
    assert measured(page) == measure(page) and page_reading(page) == 'unconfirmed'


def test_arabic_letters_are_counted_as_before():
    import random

    from apps.sources.services.ingest import letters

    random.seed(3)
    alphabet = [chr(c) for c in range(0x0600, 0x0670)] + list('abc 123.\n«»')
    for _ in range(200):
        text = ''.join(random.choice(alphabet) for _ in range(random.randint(0, 400)))
        assert letters(text, 'ar') == sum('ء' <= ch <= 'ي' for ch in text)
