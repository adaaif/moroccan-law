"""What a picture must be before it is decoded and written again: there, at most 12 MB, an image Pillow can open and
read whole; a photo's orientation is baked in."""
import io
import struct
import zlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.services.refusals import Refused
from apps.media.services import pictures


def refused(upload) -> str:
    with pytest.raises(Refused) as refusal:
        pictures.decode(upload)
    assert refusal.value.field == 'picture'
    return refusal.value.code


def chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))


def test_a_picture_must_be_there_and_at_most_12_mb():
    assert refused(None) == 'required'
    assert refused(SimpleUploadedFile('p.jpg', bytes(12 * 1024 * 1024 + 1))) == 'too_large'
    assert refused(SimpleUploadedFile('p.jpg', bytes(12 * 1024 * 1024))) == 'format'       # read, and no image


def test_a_header_past_pillows_own_cap_is_refused_as_it_is_opened():
    # 12000 x 12000 one-bit pixels stated in 57 bytes: past twice the process's 64 MP, Pillow refuses it at once
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 12000, 12000, 1, 0, 0, 0, 0)) + chunk(b'IEND', b'')
    assert refused(SimpleUploadedFile('p.png', png)) == 'invalid'


def test_a_picture_cut_short_is_refused_as_it_is_read():
    buf = io.BytesIO()
    Image.effect_noise((64, 64), 60).save(buf, 'PNG')
    whole = buf.getvalue()
    assert pictures.decode(SimpleUploadedFile('p.png', whole)).mode == 'RGB'
    assert refused(SimpleUploadedFile('p.png', whole[:len(whole) // 2])) == 'invalid'


def test_a_photos_orientation_is_baked_in():
    exif = Image.Exif()
    exif[0x0112] = 6                    # «turn 90° to show»: a phone held upright
    buf = io.BytesIO()
    Image.new('RGB', (40, 30)).save(buf, 'JPEG', exif=exif)
    assert pictures.decode(SimpleUploadedFile('p.jpg', buf.getvalue())).size == (30, 40)
