"""Voices and pictures: the door, the conversion every phone plays, the links, the metadata that never leaves."""
import io
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

from apps.accounts.services.refusals import Refused
from apps.discussion.tests.conftest import PATH, make_user, settle, signed_in
from apps.media.models import Clip, Picture
from apps.media.services import door, ranged, store

pytestmark = pytest.mark.django_db
needs_ffmpeg = pytest.mark.needs('ffmpeg')


def recording(tmp_path, seconds: float, ext: str, codec: str, extra=()) -> bytes:
    out = tmp_path / f'take.{ext}'
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i',
                    f'sine=frequency=220:duration={seconds}', '-ac', '1', '-c:a', codec, *extra,
                    '-metadata', 'location=+33.9716-006.8498/', '-metadata', 'title=secret', str(out)], check=True)
    return out.read_bytes()


def upload(data: bytes, name='take') -> SimpleUploadedFile:
    return SimpleUploadedFile(name, data, content_type='application/octet-stream')


@pytest.fixture
def media_writer(lease):
    """Three days old with a published contribution: voices and pictures are open to them."""
    return settle(make_user('nadia', days=10), lease)


@needs_ffmpeg
def test_a_browsers_webm_becomes_aac_every_phone_plays(api, media_writer, tmp_path):
    webm = recording(tmp_path, 3, 'webm', 'libopus')
    r = signed_in(api, media_writer).post('/api/discussion/voices/', {'voice': upload(webm), 'peaks': '[0.2, 1.4, -1]'},
                                          format='multipart')
    assert r.status_code == 201, r.content
    clip = Clip.objects.get()
    assert 2900 <= clip.duration_ms <= 3100 and clip.peaks == [0.2, 1.0, 0.0] and clip.state == 'draft'
    stored = store.path_of('voices', clip.file_name).read_bytes()
    assert stored[4:8] == b'ftyp' and door._mp4_ms(stored) > 0
    assert b'secret' not in stored and b'33.9716' not in stored


@needs_ffmpeg
def test_safaris_aac_is_taken_and_chromiums_opus_in_mp4_is_not(media_writer, tmp_path):
    assert 1900 <= door.read(recording(tmp_path, 2, 'm4a', 'aac')) <= 2100
    with pytest.raises(Refused) as refused:
        door.read(recording(tmp_path, 2, 'mp4', 'libopus'))
    assert refused.value.code == 'format'


@needs_ffmpeg
def test_a_fragmented_mp4_states_its_length_in_its_fragments(tmp_path):
    data = recording(tmp_path, 2, 'mp4', 'aac', ['-movflags', 'frag_keyframe+empty_moov'])
    assert 1900 <= door.read(data) <= 2100


def test_chromes_webm_without_a_duration_is_read_from_all_its_clusters():
    """Recorded by Chrome's MediaRecorder (2.6 s, a chunk a second): clusters of unknown size, no Info>Duration."""
    data = (Path(__file__).parent / 'fixtures' / 'chrome-2600ms.webm').read_bytes()
    assert 2400 <= door.read(data) <= 2700


@needs_ffmpeg
def test_two_minutes_at_most(api, media_writer, tmp_path):
    r = signed_in(api, media_writer).post('/api/discussion/voices/',
                                          {'voice': upload(recording(tmp_path, 125, 'webm', 'libopus'))},
                                          format='multipart')
    assert r.json()['errors'] == [{'field': 'voice', 'code': 'too_long'}]


def test_voices_and_pictures_open_after_three_days_and_a_published_contribution(api, writer):
    young = make_user('young', days=1)
    r = signed_in(api, young).post('/api/discussion/voices/', {'voice': upload(b'x' * 100)}, format='multipart')
    assert r.json()['errors'] == [{'field': 'voice', 'code': 'not_yet'}]


def test_not_audio_is_refused():
    with pytest.raises(Refused) as refused:
        door.read(b'GIF89a' + b'\0' * 64)
    assert refused.value.code == 'format'


@needs_ffmpeg
def test_a_voice_comment_plays_by_its_signed_link_with_ranges(api, media_writer, tmp_path, reader):
    clip = signed_in(api, media_writer).post('/api/discussion/voices/',
                                             {'voice': upload(recording(tmp_path, 2, 'webm', 'libopus'))},
                                             format='multipart').json()
    r = api.post('/api/discussion/contributions/', {'path': PATH, 'kind': 'post', 'title': 'عنوان', 'voice': clip['id']},
                 format='json')
    assert r.status_code == 201 and r.json()['voice']['duration_ms'] > 0
    src = signed_in(api, reader).get('/api/discussion/feed/', {'place': PATH}).json()['posts'][0]['voice']['src']
    whole = api.get(src)
    assert whole.status_code == 200 and whole['Cache-Control'].startswith('private, no-store')
    part = api.get(src, HTTP_RANGE='bytes=0-99')
    assert part.status_code == 206 and part['Content-Length'] == '100'
    assert api.get(src.replace('t=', 't=x')).status_code == 404


def test_a_voice_is_never_anonymous(api, media_writer):
    clip = Clip.objects.create(owner=media_writer, duration_ms=2000, size=10, file_name='x.m4a')
    r = signed_in(api, media_writer).post('/api/discussion/contributions/',
                                          {'path': PATH, 'kind': 'post', 'title': 'عنوان', 'voice': str(clip.pk),
                                           'anonymous': True}, format='json')
    assert r.json()['errors'] == [{'field': 'anonymous', 'code': 'voice'}]


@pytest.mark.parametrize('header, size, span', [
    ('bytes=0-99', 1000, (0, 99)), ('bytes=-100', 1000, (900, 999)), ('bytes=900-', 1000, (900, 999)),
    ('bytes=5-2', 1000, None), ('bytes=-0', 1000, None), ('items=0-1', 1000, None),
])
def test_ranges(header, size, span):
    assert ranged.span(header, size) == span


def gps_photo() -> bytes:
    img = Image.new('RGB', (2400, 1200), (200, 180, 160))
    exif = Image.Exif()
    exif[0x8825] = {1: 'N', 2: (33.0, 58.0, 17.0), 3: 'W', 4: (6.0, 50.0, 59.0)}
    exif[0x010F] = 'PhoneMaker'
    buf = io.BytesIO()
    img.save(buf, 'JPEG', exif=exif)
    return buf.getvalue()


def test_a_picture_loses_its_metadata_and_waits_until_its_author_is_contributor(api, media_writer, reader):
    raw = gps_photo()
    assert b'PhoneMaker' in raw
    pic = signed_in(api, media_writer).post('/api/discussion/pictures/',
                                            {'picture': upload(raw, 'p.jpg')}, format='multipart').json()
    picture = Picture.objects.get()
    full = store.path_of('pictures', picture.full_name).read_bytes()
    assert b'PhoneMaker' not in full and b'Exif' not in full and picture.width == 1600
    assert '?t=' in pic['full']
    r = api.post('/api/discussion/contributions/', {'path': PATH, 'kind': 'post', 'title': 'عنوان', 'body': 'بند من عقد',
                                                    'pictures': [pic['id']]}, format='json')
    assert r.json()['held'] is True
    assert signed_in(api, reader).get(pic['full'].split('?')[0]).status_code == 404
    assert api.get(pic['full']).status_code == 200


def test_three_pictures_at_most(api, media_writer):
    ids = [str(Picture.objects.create(owner=media_writer, width=1, height=1).pk) for _ in range(4)]
    r = signed_in(api, media_writer).post('/api/discussion/contributions/',
                                          {'path': PATH, 'kind': 'post', 'title': 'عنوان', 'body': 'صور', 'pictures': ids},
                                          format='json')
    assert r.json()['errors'] == [{'field': 'pictures', 'code': 'too_many'}]


def test_a_bomb_is_refused_not_a_crash(api, media_writer):
    img = Image.new('L', (9000, 9000))
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    r = signed_in(api, media_writer).post('/api/discussion/pictures/', {'picture': upload(buf.getvalue(), 'b.png')},
                                          format='multipart')
    assert r.json()['errors'] == [{'field': 'picture', 'code': 'invalid'}]


def test_the_nightly_job_keeps_the_promises(api, media_writer, reader):
    old_draft = Clip.objects.create(owner=media_writer, duration_ms=1, size=1,
                                    file_name=store.write('voices', b'x', 'm4a'))
    Clip.objects.filter(pk=old_draft.pk).update(created_at=timezone.now() - timedelta(hours=25))
    c = signed_in(api, media_writer).post('/api/discussion/contributions/',
                                          {'path': PATH, 'kind': 'post', 'title': 'عنوان', 'body': 'كلام'}, format='json').json()
    signed_in(api, reader).post(f'/api/discussion/contributions/{c["id"]}/report/', {'reason': 'abuse'},
                                format='json')
    signed_in(api, media_writer).delete(f'/api/discussion/contributions/{c["id"]}/')
    from apps.discussion.models import Contribution, Report
    Report.objects.update(status='reviewed', decided_at=timezone.now())
    call_command('keep_promises', stdout=io.StringIO())
    old_draft.refresh_from_db()
    assert old_draft.state == 'erased' and not store.path_of('voices', 'x').exists()
    assert Contribution.objects.get(pk=c['id']).erased_at is not None
