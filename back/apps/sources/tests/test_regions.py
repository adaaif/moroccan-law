"""An article's place on its printed page (U14 of the Moroccan-design review)."""
from apps.sources.services import regions

HEAD = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext'


def word(line: int, left: int, top: int, text: str, width: int = 60) -> str:
    return f'5\t1\t1\t1\t{line}\t1\t{left}\t{top}\t{width}\t28\t90\t{text}'


def test_an_articles_number_is_read_from_its_label():
    assert regions.number_of('المادة 49') == '49'
    assert regions.number_of('الفصل 618-3') == '618-3'
    assert regions.number_of('المادة الأولى') == '1'
    assert regions.number_of('Article 1er') == '1'


def test_an_article_runs_from_its_heading_to_the_next_in_its_column(monkeypatch):
    # Two columns: art. 1 heads the right one, art. 2 starts lower in it; the left column's lines are not art. 1's.
    rows = [HEAD,
            word(1, 1100, 100, 'المادة'), word(1, 1050, 100, '1', 30),
            word(2, 820, 140, 'لا يجوز لأي شخص', 700), word(3, 820, 180, 'أن يسوق مركبة', 700),
            word(4, 1100, 240, 'المادة'), word(4, 1050, 240, '2', 30),
            word(5, 820, 280, 'استثناء من أحكام', 700),
            word(6, 80, 120, 'نص في العمود الأيسر', 700), word(7, 80, 600, 'نص آخر', 700)]
    monkeypatch.setattr(regions, 'lines_of', lambda page: (regions.parse('\n'.join(rows)), (1600, 1000)))
    r = regions.region(None, 'المادة 1')
    assert (r['top'], r['bottom']) == (round(88 / 1000, 4), round(220 / 1000, 4))
    assert r['left'] > 0.5                                                  # the right column only
    assert regions.region(None, 'المادة 9') is None


def test_a_page_for_reading_is_a_webp_as_wide_as_asked(monkeypatch, tmp_path, settings):
    # U16 of the Moroccan-design review: 900 px for a phone, from the OCR render, kept beside it.
    from types import SimpleNamespace

    from PIL import Image
    from apps.sources.services import render
    settings.CORPUS_DIR = tmp_path
    png = tmp_path / 'page.png'
    Image.new('L', (1596, 2258), 255).save(png)
    monkeypatch.setattr(render, 'render_page', lambda page: png)
    page = SimpleNamespace(index=3, document=SimpleNamespace(sha256='ab' * 32))
    out = render.web_image(page, 900)
    with Image.open(out) as im:
        assert (im.format, im.width) == ('WEBP', 900)
    assert render.web_image(page, 900) == out                       # kept


def test_a_page_not_read_yet_is_never_read_in_the_request(api, db, monkeypatch, tmp_path, settings):
    # N13 of the read-and-trusted review: «not yet», on tonight's list, Tesseract never called.
    import hashlib

    from apps.sources.models import Document, Page, PageKind
    settings.CORPUS_DIR = tmp_path
    from django.utils import timezone
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(b'7551').hexdigest(),
                                  path='x.pdf', mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now())
    page = Page.objects.create(document=doc, index=3, kind=PageKind.TEXT_LAYER)
    monkeypatch.setattr(regions, 'lines_of', lambda page: (_ for _ in ()).throw(AssertionError('Tesseract in a request')))
    r = api.get(f'/api/sources/documents/{doc.pk}/pages/3/region/', {'label': 'المادة 65'})
    assert r.json() == {'region': None, 'waiting': True}
    assert r['Cache-Control'] == 'public, max-age=300'
    assert regions.wanted_path().read_text() == f'{doc.pk} 3\n'

    # Tonight's job reads it; tomorrow the answer comes from its boxes.
    from django.core.management import call_command

    def read(p):
        regions.boxes_path(p).parent.mkdir(parents=True, exist_ok=True)
        regions.boxes_path(p).write_text('\n'.join([HEAD, word(1, 1100, 100, 'المادة'), word(1, 1050, 100, '65', 30)]))
        return regions.parse(regions.boxes_path(p).read_text()), (1600, 1000)
    monkeypatch.setattr(regions, 'lines_of', read)
    call_command('read_regions', '--wanted-only', '--minutes', '1')
    assert regions.read_yet(page)
    assert regions.wanted_path().read_text() == ''
    assert api.get(f'/api/sources/documents/{doc.pk}/pages/3/region/', {'label': 'المادة 65'}).json()['region'] is not None


def test_until_tonights_read_the_witness_frames_the_articles_column(api, db, monkeypatch, tmp_path, settings):
    # HM39 of the hard-moment review: a 1963 dahir's page opened on «الفصل 1» showed no frame (its boxes not read
    # yet). The witness's lines (150 dpi) are read already: the heading among them frames the column, a misread number
    # («الفصل <.») found as the one above «الفصل 2».
    import hashlib

    from django.utils import timezone

    from apps.sources.models import Document, Page, PageKind
    from apps.sources.services import witness
    settings.CORPUS_DIR = tmp_path
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(b'2622').hexdigest(),
                                  path='x.pdf', mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now())
    Page.objects.create(document=doc, index=7, kind=PageKind.TEXT_LAYER)
    seen = {'w': 1400, 'h': 1800, 'lines': [
        [940, 270, 1020, 297, 'الفصل 5', 90], [740, 310, 1300, 340, 'يؤذن للجماعات الحضرية في أن تبرم اقتراضات', 88],
        [330, 770, 415, 800, 'الفصل <.', 65], [100, 810, 660, 840, 'يؤذن للجماعات الحضرية في أن تبرم', 85],
        [100, 850, 660, 880, 'اقتراضات لدى صندوق الإيداع والتسيير', 85],
        [330, 1550, 416, 1585, 'الفصل 2.', 62], [100, 1600, 660, 1630, 'يسند تنفيذ ظهيرنا هذا', 80]]}
    monkeypatch.setattr(witness, 'of', lambda page: seen)
    monkeypatch.setattr(regions, 'lines_of', lambda page: (_ for _ in ()).throw(AssertionError('Tesseract in a request')))
    r = api.get(f'/api/sources/documents/{doc.pk}/pages/7/region/', {'label': 'الفصل 1'}).json()
    assert r['waiting'] is True and r['region']['right'] < 0.5                   # the left column
    assert (r['region']['top'], r['region']['bottom']) == (round(758 / 1800, 4), round(892 / 1800, 4))
    assert api.get(f'/api/sources/documents/{doc.pk}/pages/7/region/', {'label': 'الفصل 5'}).json()['region']['left'] > 0.5
    monkeypatch.setattr(witness, 'of', lambda page: None)                      # a page the witness never read
    assert api.get(f'/api/sources/documents/{doc.pk}/pages/7/region/', {'label': 'الفصل 1'}).json()['region'] is None
