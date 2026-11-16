"""Pictures (D5). Every upload is decoded and written again as a fresh WebP with no
metadata: a phone photo's EXIF can carry where it was taken. The orientation is baked in first. Names and numbers
were blurred in the browser; the server cannot know what a picture shows, so a reviewer sees it before readers do
until its author is «مساهم»."""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from apps.accounts.services.refusals import Refused
from apps.media.models import Picture
from apps.media.services import store

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
# The formats a phone sends, and the only readers Pillow is let try: any other (EPS runs Ghostscript on what was sent;
# PSD, TIFF, JPEG 2000 and the rest have decoders no phone needs) is refused before a byte is decoded.
ALLOWED = ('JPEG', 'PNG', 'WEBP')
# A phone's photo is 12 to 16 megapixels at most; a decompression bomb is small on disk and enormous in memory, and the
# turn and the two copies below hold about three of it at once.
MAX_PIXELS = 20_000_000
FULL, THUMB = 1600, 480
# Pillow's own cap for the whole process (the page scans too), above ours. Its error for it is not an OSError, so it is
# named here.
Image.MAX_IMAGE_PIXELS = 64_000_000
_DECODE_ERRORS = (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError)


def decode(upload, field: str = 'picture') -> Image.Image:
    if upload is None:
        raise Refused(field, 'required')
    if (upload.size or 0) > MAX_UPLOAD_BYTES:
        raise Refused(field, 'too_large')
    try:
        opened = Image.open(upload, formats=ALLOWED)
    except UnidentifiedImageError:
        raise Refused(field, 'format') from None
    except _DECODE_ERRORS:
        raise Refused(field, 'invalid') from None
    # The size is read from the header, before decoding.
    if opened.width * opened.height > MAX_PIXELS:
        raise Refused(field, 'invalid')
    try:
        opened.load()
    except _DECODE_ERRORS:
        raise Refused(field, 'invalid') from None
    img = ImageOps.exif_transpose(opened)
    return img if img.mode in ('RGB', 'RGBA') else img.convert('RGB')


def webp(img: Image.Image, side: int, quality: int) -> tuple[bytes, int, int]:
    """A fresh WebP no wider or taller than `side`: no exif argument, so no metadata."""
    out = img.copy()
    out.thumbnail((side, side), Image.Resampling.LANCZOS)
    buf = BytesIO()
    out.save(buf, 'WEBP', quality=quality)
    return buf.getvalue(), out.width, out.height


def upload(user, file) -> Picture:
    img = decode(file)
    full, width, height = webp(img, FULL, 82)
    thumb, _, _ = webp(img, THUMB, 78)
    return Picture.objects.create(owner=user, full_name=store.write('pictures', full, 'webp'),
                                  thumb_name=store.write('pictures', thumb, 'webp'), width=width, height=height)
