"""Pictures drawn because someone asked for one (config/drawing.py; OP15 of the open-source audit): a few at a time in the
whole site and a share a minute an address, those drawn already served whatever the counts, each written whole before
anyone can read it, and each folder kept under its size, the least lately used removed first. The printed page's
image for reading is drawn into its own folder and never leaves a PNG under renders/."""
import hashlib
import os
import time

import pypdfium2 as pdfium
import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.sources.models import Document, Page
from config import drawing
from config.caching import counters

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def counts():
    counters.clear()
    yield
    counters.clear()


def Asker(ip='203.0.113.7'):
    """A request from `ip`, as nginx passes it on."""
    return RequestFactory().get('/', HTTP_X_FORWARDED_FOR=ip)


def test_a_picture_is_written_whole_then_renamed(tmp_path):
    out = tmp_path / 'cards' / 'a.png'

    def draw(part):
        assert not out.exists() and part.parent == out.parent and part.name.startswith('.')
        part.write_bytes(b'png')
    assert drawing.picture(out, draw, Asker()) == out
    assert out.read_bytes() == b'png' and os.listdir(out.parent) == ['a.png']
    # Drawn already: served, never drawn again.
    assert drawing.picture(out, lambda part: pytest.fail('drawn again'), Asker()) == out


def test_a_drawing_that_fails_leaves_nothing_and_gives_its_place_back(tmp_path, settings):
    settings.DRAWING_AT_ONCE = 1
    out = tmp_path / 'a.png'

    def broken(part):
        part.write_bytes(b'half')
        raise OSError('the page cannot be read')
    with pytest.raises(OSError, match='the page cannot be read'):
        drawing.picture(out, broken, Asker())
    assert os.listdir(tmp_path) == []
    drawing.picture(out, lambda part: part.write_bytes(b'png'), Asker())


def test_no_more_than_a_few_are_drawn_at_once_in_the_whole_site(tmp_path, settings):
    settings.DRAWING_AT_ONCE = 2
    counters.add('drawing:place:0', 1, timeout=60)        # two other workers are drawing
    counters.add('drawing:place:1', 1, timeout=60)
    with pytest.raises(drawing.Busy):
        drawing.picture(tmp_path / 'b.png', lambda part: pytest.fail('drawn while busy'), Asker('198.51.100.1'))
    (tmp_path / 'a.png').write_bytes(b'png')              # one drawn already is served meanwhile
    assert drawing.picture(tmp_path / 'a.png', lambda part: pytest.fail('drawn'), Asker()) == tmp_path / 'a.png'
    counters.delete('drawing:place:1')                    # one of them is done
    drawing.picture(tmp_path / 'b.png', lambda part: part.write_bytes(b'png'), Asker('198.51.100.1'))


def test_an_address_draws_its_share_a_minute_and_the_others_draw_on(tmp_path, settings):
    settings.DRAWING_PER_MINUTE = 2
    for name in ('a', 'b'):
        drawing.picture(tmp_path / f'{name}.png', lambda part: part.write_bytes(b'png'), Asker())
    with pytest.raises(drawing.Busy):
        drawing.picture(tmp_path / 'c.png', lambda part: part.write_bytes(b'png'), Asker())
    assert drawing.picture(tmp_path / 'a.png', lambda part: pytest.fail('drawn'), Asker()) == tmp_path / 'a.png'
    drawing.picture(tmp_path / 'c.png', lambda part: part.write_bytes(b'png'), Asker('198.51.100.1'))


def test_a_folder_keeps_its_size_the_least_lately_used_removed_first(tmp_path):
    now = time.time()
    for i, name in enumerate(['old.png', 'used.png', 'new.png', 'newer.png']):
        (tmp_path / name).write_bytes(b'x' * 100)
        os.utime(tmp_path / name, (now - 1000 + i * 100, now - 1000 + i * 100))
    os.utime(tmp_path / 'used.png')                       # served lately
    (tmp_path / 'topics').mkdir()                         # a folder of its own is not counted
    (tmp_path / 'topics' / 'family.png').write_bytes(b'x' * 1000)
    (tmp_path / '.part.png').write_bytes(b'x')            # a drawing that died two hours ago
    os.utime(tmp_path / '.part.png', (now - 7200, now - 7200))
    assert drawing.keep(tmp_path, 300) == 2
    assert sorted(os.listdir(tmp_path)) == ['newer.png', 'topics', 'used.png']
    assert drawing.keep(tmp_path, 300) == 0


def test_a_drawing_keeps_its_folder_under_its_size(tmp_path, settings):
    settings.DRAWN_FOLDER_MOST = 250
    for name in ('a', 'b', 'c'):
        drawing.picture(tmp_path / f'{name}.png', lambda part: part.write_bytes(b'x' * 100), Asker())
        os.utime(tmp_path / f'{name}.png', (time.time() - ord('z') + ord(name),) * 2)
        counters.delete(f'drawing:looked:{tmp_path}')     # a minute later
    assert sorted(os.listdir(tmp_path)) == ['b.png', 'c.png']


@pytest.fixture
def issue_page(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(595, 842)
    (tmp_path / 'issues').mkdir()
    pdf.save(str(tmp_path / 'issues' / 'BO_7556_ar.pdf'))
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=hashlib.sha256(b'7556').hexdigest(),
                                  path='issues/BO_7556_ar.pdf', mime='application/pdf', language='ar', bytes=1,
                                  page_count=1, fetched_at=timezone.now())
    return Page.objects.create(document=doc, index=0, kind='text_layer', text='نص', text_source='layer')


def test_a_page_drawn_for_a_reader_goes_to_its_own_folder(api, issue_page, tmp_path):
    from PIL import Image
    url = f'/api/sources/documents/{issue_page.document_id}/pages/0/image/'
    r = api.get(url, {'w': '900'})
    assert r.status_code == 200 and r['Content-Type'] == 'image/webp'
    b''.join(r.streaming_content)
    drawn = tmp_path / 'drawn' / f'{issue_page.document.sha256[:16]}-0000-900.webp'
    with Image.open(drawn) as im:
        assert (im.format, im.width) == ('WEBP', 900)
    assert not (tmp_path / 'renders').exists()            # no PNG left for good under renders/ for a reader
    r = api.get(url)
    assert r.status_code == 200 and r['Content-Type'] == 'image/png'
    r.close()


def test_a_page_is_not_drawn_while_the_site_draws_others_but_one_drawn_ahead_is_served(api, issue_page, tmp_path,
                                                                                        settings):
    settings.DRAWING_AT_ONCE = 1
    counters.add('drawing:place:0', 1, timeout=60)
    url = f'/api/sources/documents/{issue_page.document_id}/pages/0/image/'
    r = api.get(url, {'w': '900'})
    assert r.status_code == 503 and r['Retry-After'] == '10'
    assert r.json() == {'errors': [{'field': 'picture', 'code': 'busy'}]}
    ahead = tmp_path / 'renders' / issue_page.document.sha256[:16] / '0000-900.webp'   # draw_pages's, at a deploy
    ahead.parent.mkdir(parents=True)
    ahead.write_bytes(b'RIFF')
    r = api.get(url, {'w': '900'})
    assert r.status_code == 200 and b''.join(r.streaming_content) == b'RIFF'
