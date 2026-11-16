"""The logo, the wordmark «قانون المغرب» (9 Nov 2026): the share pictures draw the same file the site shows."""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from apps.corpus.services import wordmark
from apps.corpus.services.cards import mark

SITE = Path(__file__).resolve().parents[4] / 'web' / 'public' / 'brand' / 'wordmark.svg'


@pytest.mark.skipif(not SITE.exists(), reason='the web app is not beside the back')
def test_the_pictures_draw_the_sites_wordmark():
    assert wordmark.SVG.read_bytes() == SITE.read_bytes()


def test_the_wordmark_is_drawn_whole_and_its_letters_open():
    m = wordmark.mask(132)
    assert m.height == 132 and 120 < m.width < 145                      # about as wide as it is tall
    ink = m.point(lambda v: 255 if v > 127 else 0).histogram()[255] / (m.width * m.height)
    assert 0.15 < ink < 0.5                                            # letters, not a filled block
    polygons, box = wordmark.shape()
    assert len(polygons) == 17 and box == (44.0, 48.0, 374.0, 366.0)


def test_a_share_picture_carries_it_and_the_address(settings):
    settings.SITE_URL = 'https://3adala.com'
    img = Image.new('RGB', (1200, 630), (244, 242, 238))
    left = mark(ImageDraw.Draw(img), 1120, 48, 66)
    assert left < 1120 - 66                                            # the address beside the wordmark
    assert img.crop((1120 - 70, 48, 1120, 114)).getcolors(100000) and img.getpixel((1180, 300)) == (244, 242, 238)
