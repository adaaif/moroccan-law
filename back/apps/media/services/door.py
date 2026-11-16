"""The one audio door (D4). Nothing is stored that did not pass through here.

Two containers come in, because two kinds of browser record:
- WebM/Opus from Chrome, Edge, Firefox and Android (`MediaRecorder`). Chromium's own «audio/mp4» is Opus inside
  MP4, which plays nowhere on an iPhone, so it is refused by its codec, whatever its name.
- MP4/AAC from Safari.

The door proves, from the bytes, the container, one audio track and its codec (Opus in WebM, AAC in MP4), and the
duration the file itself states (a WebM without one, as WebKit writes, is read off its clusters). Then **every**
recording goes through ffmpeg: AAC in MP4, mono, 48 kbps, loudness brought to −16 LUFS, every tag dropped. What
ffmpeg writes is checked again. The conversion is not best effort: a recording ffmpeg cannot turn into AAC is
refused: an iPhone must be able to play every voice on the site.

A file is written by whoever sends it, so nothing it states is trusted further than it can be checked: a fragment's
samples must fit in the fragment; ffmpeg is told the container the door proved and its one decoder, and writes at most
VOICE_SECONDS + 1 seconds; the length kept is the one measured in what ffmpeg wrote, not the one the file stated.
"""
import math
import os
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass

from django.conf import settings

from apps.accounts.services.refusals import Refused

_BRANDS = {b'M4A ', b'isom', b'iso2', b'mp41', b'mp42', b'3gp4', b'iso5', b'iso6', b'dash'}
_AAC = b'mp4a'
_EBML_MAGIC = b'\x1a\x45\xdf\xa3'
FFMPEG = shutil.which('ffmpeg')
TRANSCODE_TIMEOUT_S = 60
MAX_PEAKS = 200


@dataclass(frozen=True)
class Audio:
    data: bytes
    duration_ms: int


def _refuse(code: str) -> Refused:
    return Refused('voice', code)


# ── MP4 ────────────────────────────────────────────────────────────────────

def _boxes(data: bytes, start: int, end: int):
    """(type, body_start, box_end) for each MP4 box in data[start:end]."""
    offset = start
    while offset + 8 <= end:
        (size,) = struct.unpack_from('>I', data, offset)
        kind = data[offset + 4:offset + 8]
        body = offset + 8
        if size == 1:
            if body + 8 > end:
                return
            (size,) = struct.unpack_from('>Q', data, body)
            body += 8
        elif size == 0:
            size = end - offset
        if size < 8 or offset + size > end:
            return
        yield kind, body, offset + size
        offset += size


def _child(data: bytes, start: int, end: int, path: list[bytes]):
    if not path:
        return start, end
    for kind, body, box_end in _boxes(data, start, end):
        if kind == path[0]:
            return _child(data, body, box_end, path[1:])
    return None


def _mp4_ms(data: bytes) -> int:
    if data[4:8] != b'ftyp' or data[8:12] not in _BRANDS:
        raise _refuse('format')
    moov = _child(data, 0, len(data), [b'moov'])
    if moov is None:
        raise _refuse('invalid')
    traks = [b for k, b, e in _boxes(data, *moov) if k == b'trak']
    if len(traks) != 1:
        raise _refuse('one_track')
    stsd = _child(data, *moov, [b'trak', b'mdia', b'minf', b'stbl', b'stsd'])
    entry = next((k for k, _b, _e in _boxes(data, stsd[0] + 8, stsd[1])), None) if stsd else None
    if entry != _AAC:
        raise _refuse('format')
    header = _child(data, *moov, [b'mvhd'])
    if header is None:
        raise _refuse('invalid')
    body = header[0]
    if data[body] == 1:
        (timescale,) = struct.unpack_from('>I', data, body + 20)
        (duration,) = struct.unpack_from('>Q', data, body + 24)
    else:
        (timescale,) = struct.unpack_from('>I', data, body + 12)
        (duration,) = struct.unpack_from('>I', data, body + 16)
    if timescale <= 0:
        raise _refuse('invalid')
    if duration == 0:
        # A fragmented MP4 (Safari's recorder can write one) states nothing in its mvhd: its fragments say it.
        duration, timescale = _fragments(data, moov)
    return round(duration * 1000 / timescale) if timescale else 0


def _fragments(data: bytes, moov) -> tuple[int, int]:
    mdhd = _child(data, *moov, [b'trak', b'mdia', b'mdhd'])
    if mdhd is None:
        return 0, 0
    body = mdhd[0]
    (timescale,) = struct.unpack_from('>I', data, body + (20 if data[body] == 1 else 12))
    total = 0
    for kind, body, end in _boxes(data, 0, len(data)):
        if kind != b'moof':
            continue
        trun = _child(data, body, end, [b'traf', b'trun'])
        tfhd = _child(data, body, end, [b'traf', b'tfhd'])
        if trun is None:
            continue
        flags = int.from_bytes(data[trun[0] + 1:trun[0] + 4], 'big')
        (count,) = struct.unpack_from('>I', data, trun[0] + 4)
        offset = trun[0] + 8 + (4 if flags & 0x1 else 0) + (4 if flags & 0x4 else 0)
        default = 0
        if tfhd is not None:
            tf_flags = int.from_bytes(data[tfhd[0] + 1:tfhd[0] + 4], 'big')
            at = tfhd[0] + 8 + (8 if tf_flags & 0x1 else 0) + (4 if tf_flags & 0x2 else 0)
            if tf_flags & 0x8:
                (default,) = struct.unpack_from('>I', data, at)
        per = 4 * sum(bool(flags & f) for f in (0x100, 0x200, 0x400, 0x800))
        if flags & 0x100:
            # The samples a fragment claims are inside it: a count past its end made every fragment walk to the end of
            # the file, a time that grew with the square of its size.
            if offset + count * per > trun[1]:
                raise ValueError('a fragment claims more samples than it holds')
            for i in range(count):
                total += struct.unpack_from('>I', data, offset + i * per)[0]
        else:
            total += count * default
    return total, timescale


# ── WebM ───────────────────────────────────────────────────────────────────

_EBML_HEADER, _SEGMENT, _INFO, _TRACKS, _TRACK_ENTRY = 0x1A45DFA3, 0x18538067, 0x1549A966, 0x1654AE6B, 0xAE
_DOCTYPE, _TIMECODE_SCALE, _DURATION, _TRACK_TYPE, _CODEC_ID = 0x4282, 0x2AD7B1, 0x4489, 0x83, 0x86
_CLUSTER, _TIMECODE, _SIMPLE_BLOCK, _BLOCK_GROUP, _BLOCK = 0x1F43B675, 0xE7, 0xA3, 0xA0, 0xA1
_EBML_MAX_STEPS = 4096


def _vint(data: bytes, offset: int, *, keep_marker: bool):
    if offset >= len(data) or data[offset] == 0:
        raise ValueError('bad vint')
    width = 9 - data[offset].bit_length()
    if offset + width > len(data):
        raise ValueError('truncated')
    raw = int.from_bytes(data[offset:offset + width], 'big')
    if keep_marker:
        return raw, offset + width
    mask = (1 << (7 * width)) - 1
    value = raw & mask
    return (None if value == mask else value), offset + width


def _elements(data: bytes, start: int, end: int):
    offset = start
    for _ in range(_EBML_MAX_STEPS):
        if offset >= end:
            return
        try:
            eid, after = _vint(data, offset, keep_marker=True)
            size, body = _vint(data, after, keep_marker=False)
        except ValueError:
            return
        body_end = end if size is None else body + size
        if body_end > end or body_end <= offset:
            return
        yield eid, body, body_end
        offset = body_end


def _cluster_ticks(data: bytes, start: int, end: int) -> int:
    """The last moment the clusters carry, for a WebM whose Info states no duration (Chrome's and WebKit's
    recorders never go back to write it). Chrome writes its clusters with an unknown size, so the segment is walked
    flat: into every cluster and block group, past every other element by its size."""
    latest = base = relative = 0
    offset = start
    for _ in range(200_000):
        if offset >= end:
            break
        try:
            eid, after = _vint(data, offset, keep_marker=True)
            size, body = _vint(data, after, keep_marker=False)
        except ValueError:
            break
        if eid == _CLUSTER:
            latest = max(latest, base + relative)
            base = relative = 0
            offset = body
            continue
        if eid == _BLOCK_GROUP or size is None:
            offset = body
            continue
        if eid == _TIMECODE:
            base = int.from_bytes(data[body:body + size], 'big')
        elif eid in (_SIMPLE_BLOCK, _BLOCK) and size >= 4:
            try:
                _track, at = _vint(data, body, keep_marker=False)
            except ValueError:
                at = body + size
            if at + 2 <= body + size:
                relative = max(relative, int.from_bytes(data[at:at + 2], 'big', signed=True))
        offset = body + size
    return max(latest, base + relative)


def _webm_ms(data: bytes) -> int:
    doctype = segment = None
    for eid, body, end in _elements(data, 0, len(data)):
        if eid == _EBML_HEADER:
            for cid, cb, ce in _elements(data, body, end):
                if cid == _DOCTYPE:
                    doctype = data[cb:ce].split(b'\x00')[0]
        elif eid == _SEGMENT:
            segment = (body, end)
            break
    if doctype != b'webm' or segment is None:
        raise _refuse('invalid')
    scale, duration, tracks = 1_000_000, None, 0
    for eid, body, end in _elements(data, *segment):
        if eid == _INFO:
            for cid, cb, ce in _elements(data, body, end):
                if cid == _TIMECODE_SCALE:
                    scale = int.from_bytes(data[cb:ce], 'big') or scale
                elif cid == _DURATION:
                    raw = data[cb:ce]
                    duration = struct.unpack('>f' if len(raw) == 4 else '>d', raw)[0] if len(raw) in (4, 8) else None
                    if duration is not None and not math.isfinite(duration):
                        raise _refuse('invalid')
        elif eid == _TRACKS:
            for tid, tb, te in _elements(data, body, end):
                if tid != _TRACK_ENTRY:
                    continue
                tracks += 1
                kind = codec = None
                for cid, cb, ce in _elements(data, tb, te):
                    if cid == _TRACK_TYPE:
                        kind = int.from_bytes(data[cb:ce], 'big')
                    elif cid == _CODEC_ID:
                        codec = data[cb:ce].split(b'\x00')[0]
                if kind != 2:
                    raise _refuse('one_track')
                if codec != b'A_OPUS':
                    raise _refuse('format')
            if duration is not None:
                break
    if tracks != 1:
        raise _refuse('one_track')
    if not duration:
        duration = _cluster_ticks(data, *segment)
    return round(duration * scale / 1_000_000)


# ── the door ───────────────────────────────────────────────────────────────

def read(data: bytes) -> int:
    """The recording's length in milliseconds, having proved what it is."""
    if len(data) < 16:
        raise _refuse('format')
    try:
        return _webm_ms(data) if data[:4] == _EBML_MAGIC else _mp4_ms(data)
    except (struct.error, IndexError, ValueError, OverflowError):     # an infinite or oversized length
        raise _refuse('invalid') from None


# The container the door proved, as ffmpeg names its reader, and the one decoder its codec needs: ffmpeg never guesses
# a format or a codec from the bytes (an «mp4a» entry may name MP3, AC-3 or Vorbis).
READERS = {'webm': ('webm', 'opus'), 'mp4': ('mp4', 'aac')}


def _transcode(data: bytes, kind: str) -> bytes:
    if FFMPEG is None:
        raise _refuse('unreadable')
    container, decoder = READERS[kind]
    with tempfile.TemporaryDirectory(prefix='law-voice-') as tmp:
        src, dst = os.path.join(tmp, 'in'), os.path.join(tmp, 'out.m4a')
        with open(src, 'wb') as fh:
            fh.write(data)
        cmd = [FFMPEG, '-nostdin', '-loglevel', 'error', '-y', '-f', container, '-c:a', decoder, '-i', src,
               '-vn', '-sn', '-dn', '-map', '0:a:0', '-map_metadata', '-1', '-ac', '1',
               '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000',
               # One second past the longest voice: a file that says five seconds and holds an hour is cut here, and
               # refused below by the length measured in what was written.
               '-t', str(settings.VOICE_SECONDS + 1),
               '-c:a', 'aac', '-b:a', '48k', '-movflags', '+faststart', dst]
        try:
            subprocess.run(cmd, check=True, timeout=TRANSCODE_TIMEOUT_S, capture_output=True)
            with open(dst, 'rb') as fh:
                return fh.read()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            raise _refuse('unreadable') from None


def prepare(upload) -> Audio:
    """Check an upload and turn it into the AAC every phone plays. Refusals name the field `voice`."""
    if upload is None:
        raise _refuse('required')
    if (upload.size or 0) > settings.VOICE_MAX_BYTES:
        raise _refuse('too_large')
    data = upload.read()
    duration_ms = read(data)
    if duration_ms < 1000:
        raise _refuse('empty')
    # A hair of slack for encoder padding: a clock that shows 2:00 is not refused for 2:00.4.
    longest = settings.VOICE_SECONDS * 1000 + 999
    if duration_ms > longest:
        raise _refuse('too_long')
    out = _transcode(data, 'webm' if data[:4] == _EBML_MAGIC else 'mp4')
    try:
        written = _mp4_ms(out)
    except (Refused, struct.error, IndexError, ValueError, OverflowError):     # no fault of the file that was sent
        raise _refuse('unreadable') from None
    if written <= 0:
        raise _refuse('unreadable')
    # What was written is what is kept, and its length is the one a listener hears: the stated one was the sender's.
    if written > longest:
        raise _refuse('too_long')
    return Audio(out, written)


def clean_peaks(raw: object) -> list[float]:
    """The waveform measured at the microphone: numbers in 0..1, strided down to 200."""
    import json

    if isinstance(raw, str):
        try:
            raw = json.loads(raw or '[]')
        except ValueError:
            raise Refused('peaks', 'invalid') from None
    if not isinstance(raw, list):
        raise Refused('peaks', 'invalid')
    try:
        values = [min(1.0, max(0.0, float(v))) for v in raw if not isinstance(v, bool)]
    except (TypeError, ValueError, OverflowError):      # a number of 400 digits is no float
        raise Refused('peaks', 'invalid') from None
    if len(values) > MAX_PEAKS:
        step = len(values) / MAX_PEAKS
        values = [values[int(i * step)] for i in range(MAX_PEAKS)]
    return [round(v, 3) for v in values]
