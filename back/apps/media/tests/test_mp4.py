"""The MP4 reader (Safari's recorder writes MP4/AAC): the length a file's boxes state, read as the format writes them,
and the files it refuses. Each file is made here from a few boxes."""
import struct

import pytest

from apps.accounts.services.refusals import Refused
from apps.media.services import door
from apps.media.tests.craft import FTYP, box, mdhd, moof, mp4, mvhd, tfhd, trak, trun, u32

MOOV = mvhd(1000, 2500) + trak()            # 2.5 s


def refusal(data: bytes) -> str:
    with pytest.raises(Refused) as refused:
        door.read(data)
    assert refused.value.field == 'voice'
    return refused.value.code


@pytest.mark.parametrize('version, timescale, duration, ms', [
    (0, 1000, 2500, 2500),
    (1, 4_194_304, 2 ** 32, 1_024_000),     # a version 1 header: a duration past 32 bits
])
def test_the_movie_header_states_the_length_in_either_version(version, timescale, duration, ms):
    assert door.read(mp4(mvhd(timescale, duration, version), trak())) == ms


@pytest.mark.parametrize('moov', [
    struct.pack('>I', 1) + b'moov' + struct.pack('>Q', 16 + len(MOOV)) + MOOV,
    b'\x00\x00\x00\x00moov' + MOOV,
], ids=['64-bit-size', 'size-0-to-the-end'])
def test_a_box_may_state_its_size_in_64_bits_or_run_to_the_end_of_the_file(moov):
    assert door.read(FTYP + moov) == 2500


@pytest.mark.parametrize('data, read', [
    (box(b'ftyp', b'isom\x00\x00\x00\x00') + box(b'moov', MOOV), 2500),
    (box(b'ftyp', b'qt  \x00\x00\x00\x00') + box(b'moov', MOOV), 'format'),      # QuickTime's brand
    (box(b'free', b'isom\x00\x00\x00\x00') + box(b'moov', MOOV), 'format'),        # a brand, but in no ftyp box
], ids=['isom', 'quicktime', 'brand-outside-ftyp'])
def test_an_mp4_is_known_by_its_first_box_and_a_listed_brand(data, read):
    assert (door.read(data) if read != 'format' else refusal(data)) == read


@pytest.mark.parametrize('data, read', [
    (FTYP + box(b'free') + box(b'moov', MOOV), 2500),                              # a box of its header alone
    (FTYP + struct.pack('>I', 8 + len(MOOV) + 1) + b'moov' + MOOV, 'invalid'),     # one byte past the file
    (mp4(MOOV, b'\x00\x00\x00\x01trak' + struct.pack('>Q', 16)), 'one_track'),   # a 64-bit header alone, at the end
], ids=['eight-bytes', 'one-byte-past', 'sixteen-bytes-at-the-end'])
def test_a_box_is_read_to_its_last_byte_and_not_one_past(data, read):
    assert (door.read(data) if isinstance(read, int) else refusal(data)) == read


def test_a_box_cut_off_at_the_end_ends_the_walk_and_what_came_before_it_is_read():
    # a box whose 64-bit size has only three of its eight bytes: never read past the file
    assert door.read(mp4(MOOV, b'\x00\x00\x00\x01free\x00\x00\x00')) == 2500


@pytest.mark.parametrize('data, code', [
    (FTYP + box(b'free'), 'invalid'),
    (FTYP + b'\x00\x00\x00\x04' + box(b'moov', MOOV), 'invalid'),
    (FTYP + struct.pack('>I', 4096) + b'moov' + MOOV, 'invalid'),
    (mp4(mvhd(1000, 2500)), 'one_track'),
    (mp4(MOOV, trak()), 'one_track'),
    (mp4(mvhd(1000, 2500), box(b'trak')), 'format'),
    (mp4(trak()), 'invalid'),
    (mp4(mvhd(0, 2500), trak()), 'invalid'),
], ids=['no-movie', 'box-smaller-than-its-header', 'box-past-the-end', 'no-track', 'two-tracks',
        'track-describing-no-samples', 'no-movie-header', 'no-ticks-a-second'])
def test_a_file_that_does_not_hold_one_aac_track_with_its_header_is_refused(data, code):
    assert refusal(data) == code


def test_a_fragmented_file_adds_up_its_fragments_samples():
    data = mp4(mvhd(1000, 0), trak(media_header=mdhd(2000, version=1)), tail=(
        # 25 samples of the fragment's default 80 ticks, after a base offset and a description index: 2000
        moof(tfhd(0x1 | 0x2 | 0x8, struct.pack('>Q', 7), u32(9), u32(80)), trun(0x1 | 0x4, 25, u32(11), u32(13)))
        + moof(tfhd(0), trun(0, 5))                     # no default duration: nothing
        + moof(tfhd(0x8, u32(999)))                     # no run of samples: passed over
        + box(b'mdat', b'\x00' * 8)
        # each sample's duration and size, after a data offset and the first sample's flags: 600 + 400
        + moof(trun(0x1 | 0x4 | 0x100 | 0x200, 2, u32(11), u32(13), u32(600, 77, 400, 77)))))
    assert door.read(data) == 1500                      # 3000 ticks at 2000 a second


@pytest.mark.parametrize('count, read', [(1, 500), (2, 'invalid')])
def test_a_fragment_holds_the_samples_it_claims_to_its_last_byte(count, read):
    # one sample's duration held; claiming two runs four bytes past the fragment, into the next box
    data = mp4(mvhd(1000, 0), trak(media_header=mdhd(1000)), tail=moof(trun(0x100, count, u32(500))) + box(b'mdat'))
    assert (door.read(data) if read != 'invalid' else refusal(data)) == read


def test_a_fragmented_file_with_no_media_header_has_no_length():
    assert door.read(mp4(mvhd(1000, 0), trak(), tail=moof(trun(0x100, 1, u32(500))))) == 0

