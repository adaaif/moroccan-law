"""Recordings made byte by byte: the few boxes or elements each container needs for the door to read it, as the
formats write them (ISO/IEC 14496-12 for MP4, Matroska's EBML for WebM), and nothing else."""
import struct

# ── MP4 ────────────────────────────────────────────────────────────────────


def box(kind: bytes, body: bytes = b'') -> bytes:
    return struct.pack('>I', 8 + len(body)) + kind + body


def full(flags: int, *fields: bytes) -> bytes:
    """A full box's body: version 0, 24 bits of flags, then its fields."""
    return struct.pack('>I', flags) + b''.join(fields)


def u32(*values: int) -> bytes:
    return struct.pack(f'>{len(values)}I', *values)


def mvhd(timescale: int, duration: int, version: int = 0) -> bytes:
    if version == 1:            # 64-bit creation and modification times, then a 64-bit duration
        return box(b'mvhd', b'\x01\x00\x00\x00' + b'\x00' * 16 + struct.pack('>IQ', timescale, duration) + b'\x00' * 80)
    return box(b'mvhd', b'\x00' * 12 + u32(timescale, duration) + b'\x00' * 80)


def mdhd(timescale: int, version: int = 0) -> bytes:
    if version == 1:
        return box(b'mdhd', b'\x01\x00\x00\x00' + b'\x00' * 16 + struct.pack('>IQ', timescale, 0) + b'\x00' * 4)
    return box(b'mdhd', b'\x00' * 12 + u32(timescale, 0) + b'\x00' * 4)


def trak(codec: bytes = b'mp4a', media_header: bytes = b'') -> bytes:
    stsd = box(b'stsd', b'\x00' * 8 + box(codec, b'\x00' * 28))
    return box(b'trak', box(b'mdia', media_header + box(b'minf', box(b'stbl', stsd))))


def moof(*traf: bytes) -> bytes:
    return box(b'moof', box(b'traf', b''.join(traf)))


def tfhd(flags: int, *fields: bytes) -> bytes:
    return box(b'tfhd', full(flags, u32(1), *fields))           # track 1


def trun(flags: int, count: int, *fields: bytes) -> bytes:
    return box(b'trun', full(flags, u32(count), *fields))


FTYP = box(b'ftyp', b'M4A \x00\x00\x00\x00')


def mp4(*moov: bytes, tail: bytes = b'') -> bytes:
    return FTYP + box(b'moov', b''.join(moov)) + tail


# ── WebM ───────────────────────────────────────────────────────────────────

EBML, DOCTYPE, SEGMENT, INFO, SCALE, DURATION = 0x1A45DFA3, 0x4282, 0x18538067, 0x1549A966, 0x2AD7B1, 0x4489
TRACKS, TRACK_ENTRY, TRACK_TYPE, CODEC_ID, VOID, TAGS = 0x1654AE6B, 0xAE, 0x83, 0x86, 0xEC, 0x1254C367
CLUSTER, TIMECODE, SIMPLE_BLOCK, BLOCK_GROUP, BLOCK = 0x1F43B675, 0xE7, 0xA3, 0xA0, 0xA1
UNKNOWN = b'\x01\xff\xff\xff\xff\xff\xff\xff'                   # a size of all ones: «unknown», as Chrome writes


def el(eid: int, body: bytes = b'', *, size: bytes | None = None) -> bytes:
    """An element: its id, its size as a two-byte vint (or `size` as given), its body."""
    head = eid.to_bytes((eid.bit_length() + 7) // 8, 'big')
    return head + (size if size is not None else (0x4000 | len(body)).to_bytes(2, 'big')) + body


def header(doctype: bytes = b'webm') -> bytes:
    return el(EBML, el(DOCTYPE, doctype))


def info(ms: float | None = None, scale: int | None = None) -> bytes:
    return el(INFO, (el(SCALE, scale.to_bytes(4, 'big')) if scale else b'')
              + (el(DURATION, struct.pack('>d', ms)) if ms is not None else b''))


def track(kind: int = 2, codec: bytes = b'A_OPUS') -> bytes:
    return el(TRACK_ENTRY, el(TRACK_TYPE, bytes([kind])) + el(CODEC_ID, codec))


def tracks(*entries: bytes) -> bytes:
    return el(TRACKS, b''.join(entries))


def block(timecode: int, eid: int = SIMPLE_BLOCK, number: bytes = b'\x81') -> bytes:
    """A block of track `number` (a vint) at `timecode` ticks after its cluster's, with four bytes of frame."""
    return el(eid, number + struct.pack('>h', timecode) + b'\x80' + b'\x00' * 4)


def cluster(timecode: int, *blocks: bytes) -> bytes:
    return el(CLUSTER, el(TIMECODE, struct.pack('>H', timecode)) + b''.join(blocks), size=UNKNOWN)


def webm(*segment: bytes, head: bytes | None = None) -> bytes:
    return (header() if head is None else head) + el(SEGMENT, b''.join(segment), size=UNKNOWN)
