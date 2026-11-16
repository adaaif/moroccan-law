"""The WebM reader (Chrome, Edge, Firefox and Android record WebM/Opus): the length its Info states, or its clusters
carry when it states none, the bounded walks a crafted file cannot stretch, and the files it refuses. Each file is made
here from a few elements."""
import struct

import pytest

from apps.accounts.services.refusals import Refused
from apps.media.services import door
from apps.media.tests.craft import (BLOCK, BLOCK_GROUP, DOCTYPE, DURATION, EBML, INFO, SEGMENT, SIMPLE_BLOCK, TAGS,
                                    UNKNOWN, VOID, block, cluster, el, header, info, track, tracks, webm)


def refusal(data: bytes) -> str:
    with pytest.raises(Refused) as refused:
        door.read(data)
    assert refused.value.field == 'voice'
    return refused.value.code


def test_the_info_states_the_length_in_its_own_ticks_and_other_elements_are_passed_over():
    # 5000 ticks of half a millisecond; a Void before the segment and one among the tracks
    data = header() + el(VOID, b'\x00' * 3) + el(SEGMENT, info(5000.0, scale=500_000) + tracks(el(VOID), track()),
                                                size=UNKNOWN)
    assert door.read(data) == 2500


def test_a_duration_may_be_a_four_byte_float():
    assert door.read(webm(el(INFO, el(DURATION, struct.pack('>f', 2500.0))), tracks(track()))) == 2500


@pytest.mark.parametrize('data, code', [
    (webm(info(3000.0), tracks(track()), head=header(b'matroska')), 'invalid'),
    (header() + el(VOID, b'\x00' * 8), 'invalid'),
    (header() + el(SEGMENT, size=(0x4000 | 200).to_bytes(2, 'big')) + info(3000.0) + tracks(track()), 'invalid'),
    (header() + el(SEGMENT, size=(0x4000 | len(info(3000.0) + tracks(track())) + 1).to_bytes(2, 'big'))
     + info(3000.0) + tracks(track()), 'invalid'),
    (webm(info(3000.0)), 'one_track'),
    (webm(info(3000.0), tracks(track(), track())), 'one_track'),
    (webm(info(3000.0), tracks(track(kind=1))), 'one_track'),
    (webm(info(3000.0), tracks(track(codec=b'A_VORBIS'))), 'format'),
], ids=['matroska', 'no-segment', 'segment-past-the-end', 'segment-one-byte-past', 'no-track', 'two-tracks', 'video',
        'vorbis'])
def test_a_webm_that_does_not_hold_one_opus_track_is_refused(data, code):
    assert refusal(data) == code


@pytest.mark.parametrize('size, code', [(15, 'format'), (16, 'invalid')])
def test_fewer_than_sixteen_bytes_are_no_recording(size, code):
    assert refusal((b'\x1a\x45\xdf\xa3' + b'\x00' * 16)[:size]) == code


@pytest.mark.parametrize('body, read', [
    (el(DOCTYPE, b'webm') + b'\x00', 2000),
    (b'\x00' + el(DOCTYPE, b'webm'), 'invalid'),
])
def test_a_header_is_read_up_to_the_first_bytes_that_are_no_element(body, read):
    data = webm(info(2000.0), tracks(track()), head=el(EBML, body))
    assert (door.read(data) if read != 'invalid' else refusal(data)) == read


@pytest.mark.parametrize('voids, read', [(4095, 2000), (4096, 'invalid')])
def test_a_list_of_elements_is_walked_4096_steps_at_most(voids, read):
    # the header's doctype after `voids` empty elements: the 4096th step reads it, the 4097th is never taken
    head = el(EBML, el(VOID) * voids + el(DOCTYPE, b'webm'))
    data = webm(info(2000.0), tracks(track()), head=head)
    assert (door.read(data) if read != 'invalid' else refusal(data)) == read


@pytest.mark.parametrize('clusters, ms', [
    ((cluster(0, block(500)), cluster(1000, el(BLOCK_GROUP, block(800, eid=BLOCK)))), 1800),    # a group's block
    # a block with no track number: neither its 30000 ticks nor the next cluster's id are read as its time; then zeros
    # where an element would be: the walk ends
    ((cluster(0, block(500)), cluster(1000, block(30000, number=b'\x00')), cluster(1200, block(100)), b'\x00\x00'),
     1300),
    ((cluster(0, block(900), block(300)),), 900),                                   # a block earlier than the one before
    ((cluster(2000, block(0)), cluster(500, block(100)), cluster(600, block(0))), 2000),    # a cluster earlier too
    ((cluster(0, block(700)), b'\xa3'), 700),                                       # the file ends after an element's id
    ((cluster(0, el(SIMPLE_BLOCK, b'\x81' + struct.pack('>h', 700) + b'\x80')),), 700),      # four bytes: read
    ((cluster(0, block(500), el(SIMPLE_BLOCK, b'\x81' + struct.pack('>h', 9000))),), 500),    # three: no block
    ((cluster(0, el(SIMPLE_BLOCK, b'\x01' + b'\x00' * 6 + b'\x01' + struct.pack('>h', 700))),), 700),
    ((cluster(0, block(500), el(SIMPLE_BLOCK, b'\x01' + b'\x00' * 6 + b'\x01\x23'), block(100)),), 500),
], ids=['group', 'no-track-number', 'block-out-of-order', 'cluster-out-of-order', 'cut-after-an-id', 'four-byte-block',
        'three-byte-block', 'eight-byte-track-number-and-time', 'eight-byte-track-number-and-half-a-time'])
def test_with_no_duration_the_last_block_of_the_clusters_says_the_length(clusters, ms):
    assert door.read(webm(info(), tracks(track()), *clusters)) == ms


def test_an_element_of_unknown_size_is_walked_into():
    data = webm(info(), tracks(track()), el(TAGS, cluster(0, block(1500)), size=UNKNOWN))
    assert door.read(data) == 1500


@pytest.mark.parametrize('voids, ms', [(199_992, 5000), (199_993, 1500)])
def test_the_clusters_are_walked_200000_steps_at_most(voids, ms):
    # five steps before the empty elements, three after: the last block is the 200,000th step or the 200,001st
    data = webm(info(), tracks(track()), cluster(0, block(1500)), el(VOID) * voids, cluster(0, block(5000)))
    assert door.read(data) == ms
