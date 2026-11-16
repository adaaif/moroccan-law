"""Before voices and pictures are switched on (DISCUSSION_MEDIA): what a crafted file can make the door do. The files
are made here, a few bytes each."""
import io
import struct
import subprocess
import time

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import EpsImagePlugin, Image

from apps.accounts.services.refusals import Refused
from apps.discussion.models import Contribution, Discussion
from apps.discussion.services import review
from apps.discussion.tests.conftest import PATH, make_user, signed_in, staff  # noqa: F401  (a fixture)
from apps.media.models import Clip, Picture, State
from apps.media.services import door, pictures

needs_ffmpeg = pytest.mark.needs('ffmpeg')


def box(kind: bytes, body: bytes) -> bytes:
    return struct.pack('>I', 8 + len(body)) + kind + body


def fragmented(moofs: int) -> bytes:
    """An MP4 whose header states no length, then `moofs` fragments of 32 bytes, each claiming as many samples as the
    rest of the file holds: every fragment made the reader walk to the end of the file."""
    mvhd = box(b'mvhd', b'\x00' * 12 + struct.pack('>II', 1000, 0) + b'\x00' * 80)
    mdhd = box(b'mdhd', b'\x00' * 12 + struct.pack('>II', 48000, 0) + b'\x00' * 4)
    stsd = box(b'stsd', b'\x00' * 8 + box(b'mp4a', b'\x00' * 28))
    trak = box(b'trak', box(b'mdia', mdhd + box(b'minf', box(b'stbl', stsd))))
    head = box(b'ftyp', b'M4A \x00\x00\x00\x00') + box(b'moov', mvhd + trak)
    size = len(head) + 32 * moofs
    out = [head]
    for i in range(moofs):
        after = len(head) + 32 * (i + 1)                      # where this fragment's samples would start
        trun = box(b'trun', b'\x00\x00\x01\x00' + struct.pack('>I', (size - after) // 4))   # sample durations
        out.append(box(b'moof', box(b'traf', trun)))
    return b''.join(out)


def test_a_fragment_cannot_claim_more_samples_than_it_holds():
    data = fragmented(2048)                                    # 64 KB: before, about a second of work per 10 KB more
    started = time.perf_counter()
    with pytest.raises(Refused) as refused:
        door.read(data)
    assert refused.value.code == 'invalid' and time.perf_counter() - started < 0.5


@pytest.mark.parametrize('duration', [float('inf'), float('nan')])
def test_a_length_no_clock_can_show_is_refused_not_a_crash(duration):
    ebml = b'\x1a\x45\xdf\xa3' + b'\x87' + b'\x42\x82\x84webm'
    info = b'\x15\x49\xa9\x66' + b'\x8b' + b'\x44\x89\x88' + struct.pack('>d', duration)
    track = b'\xae' + b'\x8c' + b'\x83\x81\x02' + b'\x86\x87A_OPUS\x00'
    data = ebml + b'\x18\x53\x80\x67' + b'\x01\xff\xff\xff\xff\xff\xff\xff' + info + b'\x16\x54\xae\x6b' + bytes(
        [0x80 | len(track)]) + track
    with pytest.raises(Refused) as refused:
        door.read(data)
    assert refused.value.code == 'invalid'


def test_ffmpeg_reads_the_container_the_door_proved_and_stops_past_two_minutes(monkeypatch, settings):
    ran = []

    def run(cmd, **kwargs):
        ran.append(cmd)
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(door, 'FFMPEG', '/usr/bin/ffmpeg')
    monkeypatch.setattr(door.subprocess, 'run', run)
    for kind, fmt, codec in (('webm', 'webm', 'opus'), ('mp4', 'mp4', 'aac')):
        with pytest.raises(Refused):
            door._transcode(b'x' * 64, kind)
        cmd = ran[-1]
        given = cmd.index('-i')
        assert cmd[cmd.index('-f') + 1] == fmt and cmd.index('-f') < given
        assert cmd[cmd.index('-c:a') + 1] == codec and cmd.index('-c:a') < given
        assert cmd[cmd.index('-t', given) + 1] == str(settings.VOICE_SECONDS + 1)


@needs_ffmpeg
def test_a_file_that_states_five_seconds_and_holds_more_is_measured_by_what_ffmpeg_wrote(tmp_path, monkeypatch):
    out = tmp_path / 'long.webm'
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=130',
                    '-ac', '1', '-c:a', 'libopus', str(out)], check=True)
    monkeypatch.setattr(door, 'read', lambda data: 5000)       # its header lies: five seconds
    with pytest.raises(Refused) as refused:
        door.prepare(SimpleUploadedFile('take', out.read_bytes()))
    assert refused.value.code == 'too_long'


def test_a_picture_in_another_format_is_never_decoded(monkeypatch):
    def ghostscript(*args, **kwargs):
        raise AssertionError('Ghostscript reached from an upload')

    monkeypatch.setattr(EpsImagePlugin, 'Ghostscript', ghostscript)
    eps = b'%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 8 8\nnewpath 0 0 moveto 8 8 lineto stroke\nshowpage\n%%EOF\n'
    with pytest.raises(Refused) as refused:
        pictures.decode(SimpleUploadedFile('p.eps', eps))
    assert refused.value.code == 'format'
    gif = io.BytesIO()
    Image.new('RGB', (4, 4)).save(gif, 'GIF')
    with pytest.raises(Refused) as refused:
        pictures.decode(SimpleUploadedFile('p.gif', gif.getvalue()))
    assert refused.value.code == 'format'


def test_a_picture_past_twenty_megapixels_is_refused_before_it_is_decoded():
    big = io.BytesIO()
    Image.new('1', (5000, 4001)).save(big, 'PNG')             # small on disk, 20,005,000 pixels
    with pytest.raises(Refused) as refused:
        pictures.decode(SimpleUploadedFile('p.png', big.getvalue()))
    assert refused.value.code == 'invalid'
    fits = io.BytesIO()
    Image.new('RGB', (40, 30)).save(fits, 'PNG')
    assert pictures.decode(SimpleUploadedFile('p.png', fits.getvalue())).size == (40, 30)


@pytest.mark.django_db
def test_a_contribution_hidden_by_reports_hides_its_voice_and_pictures_until_a_reviewer_keeps_it(api, staff):
    place = Discussion.objects.create(path=PATH, text_path=PATH)
    author = make_user('salma')
    clip = Clip.objects.create(owner=author, duration_ms=3000, size=10, file_name='v.m4a', state=State.LIVE)
    picture = Picture.objects.create(owner=author, full_name='p.webp', thumb_name='t.webp', width=1, height=1,
                                     state=State.LIVE)
    c = Contribution.objects.create(discussion=place, author=author, kind='post', title='منشور', body='كلام', clip=clip)
    c.pictures.add(picture)
    for name in ('o1', 'o2', 'o3'):
        signed_in(api, make_user(name, days=4)).post(f'/api/discussion/contributions/{c.pk}/report/',
                                                     {'reason': 'exposing'}, format='json')
    assert Contribution.objects.get(pk=c.pk).hidden_at is not None
    assert {Clip.objects.get(pk=clip.pk).state, Picture.objects.get(pk=picture.pk).state} == {State.EVIDENCE}
    review.keep(staff, c.pk)
    assert {Clip.objects.get(pk=clip.pk).state, Picture.objects.get(pk=picture.pk).state} == {State.LIVE}
