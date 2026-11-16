"""No malformed request answers 500 at any address of apps.media (OP53 of the open-source audit): a list where an object
is read, a NUL, other digits, an impossible date, a number past any column, an over-long string. The shapes and the
walk over every route are `knock` and `malformed` in back/conftest.py."""
import pytest


def test_no_malformed_request_answers_500(knock, malformed):
    assert knock('media', malformed) == []

import struct  # noqa: E402

from apps.accounts.services.refusals import Refused  # noqa: E402
from apps.media.services import door  # noqa: E402


def _element(eid: int, body: bytes) -> bytes:
    return eid.to_bytes((eid.bit_length() + 7) // 8, 'big') + bytes([0x80 | len(body)]) + body


def test_a_recording_that_states_an_endless_length_is_refused():
    """An infinite Duration (or a TimecodeScale past any length) raised OverflowError, which the reader let through."""
    info = _element(0x1549A966, _element(0x2AD7B1, (1_000_000).to_bytes(3, 'big'))
                    + _element(0x4489, struct.pack('>d', float('inf'))))
    tracks = _element(0x1654AE6B, _element(0xAE, _element(0x83, b'\x02') + _element(0x86, b'A_OPUS')))
    webm = _element(0x1A45DFA3, _element(0x4282, b'webm')) + _element(0x18538067, info + tracks)
    with pytest.raises(Refused) as refused:
        door.read(webm)
    assert (refused.value.field, refused.value.code) == ('voice', 'invalid')


def test_a_peak_of_four_hundred_digits_is_refused():
    with pytest.raises(Refused) as refused:
        door.clean_peaks('[0.5, ' + '9' * 400 + ']')
    assert (refused.value.field, refused.value.code) == ('peaks', 'invalid')
    assert door.clean_peaks('[0.5, 2, -1]') == [0.5, 1.0, 0.0]
