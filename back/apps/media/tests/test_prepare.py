"""The door's own refusals before and after ffmpeg, and the waveform a recording brings."""
import json
import subprocess

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.services.refusals import Refused
from apps.media.services import door
from apps.media.tests.craft import info, track, tracks, webm


def refused(upload) -> str:
    with pytest.raises(Refused) as refusal:
        door.prepare(upload)
    assert refusal.value.field == 'voice'
    return refusal.value.code


@pytest.mark.parametrize('size, code', [(None, 'required'), (65, 'too_large'), (64, 'format')])
def test_an_upload_must_be_there_and_no_larger_than_the_limit(settings, size, code):
    settings.VOICE_MAX_BYTES = 64
    assert refused(None if size is None else SimpleUploadedFile('take', b'\x00' * size)) == code


@pytest.mark.parametrize('ms, code', [(999, 'empty'), (1000, 'unreadable'), (120_999, 'unreadable'),
                                      (121_000, 'too_long')])
def test_the_length_a_recording_states_is_one_second_to_two_minutes_and_nothing_is_kept_without_ffmpeg(
        settings, monkeypatch, ms, code):
    settings.VOICE_SECONDS = 120
    monkeypatch.setattr(door, 'FFMPEG', None)           # a machine without ffmpeg: what passes is never kept as sent
    assert refused(SimpleUploadedFile('take', webm(info(float(ms)), tracks(track())))) == code


@pytest.mark.needs('ffmpeg')
def test_safaris_aac_is_converted_too_mono_at_48_khz(tmp_path):
    take = tmp_path / 'take.m4a'
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i',
                    'sine=frequency=220:duration=2', '-ac', '2', '-ar', '44100', '-c:a', 'aac', str(take)], check=True)
    audio = door.prepare(SimpleUploadedFile('take', take.read_bytes()))
    kept = tmp_path / 'kept.m4a'
    kept.write_bytes(audio.data)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(kept)],
                           check=True, capture_output=True, text=True)
    (stream,) = json.loads(probe.stdout)['streams']
    assert (stream['codec_name'], stream['channels'], stream['sample_rate']) == ('aac', 1, '48000')
    assert 1900 <= audio.duration_ms <= 2100 and audio.duration_ms == door.read(audio.data)


@pytest.mark.parametrize('raw, peaks', [
    ([0.25, True, 1.5, -2], [0.25, 1.0, 0.0]),          # as JSON brings a list: a true is no number
    ('', []),
    ('[0.12345]', [0.123]),
    ([i / 400 for i in range(400)], [round(i / 400, 3) for i in range(0, 400, 2)]),    # strided down to 200
    ([i / 1000 for i in range(201)], [i / 1000 for i in range(200)]),                   # one past 200: strided too
])
def test_the_waveform_is_numbers_from_0_to_1_at_most_200(raw, peaks):
    assert door.clean_peaks(raw) == peaks


@pytest.mark.parametrize('raw', ['[0.5,', '{"a": 1}', '"5"', 7, None])
def test_a_waveform_that_is_no_list_of_numbers_is_refused(raw):
    with pytest.raises(Refused) as refusal:
        door.clean_peaks(raw)
    assert (refusal.value.field, refusal.value.code) == ('peaks', 'invalid')
