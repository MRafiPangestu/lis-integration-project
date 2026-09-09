"""MLLP framing tests (BC-5150 0x02 heartbeat regression).

Field evidence: the physical Mindray BC-5150 emits single-byte 0x02 bytes while
idle. Both historically working tools discarded them before HL7 framing
(`poc/mindray:backend/lis_server.py:156-157` and the external raw capture
client). The M8 transport rewrite dropped that handling, so the heartbeats
accumulated in the receive buffer and were prepended to the next frame. Live
captures in `instrument_messages` show the result: frames beginning
`\\x02...\\x02\\x0bMSH|...` classified UNPARSEABLE, while the one frame that
arrived with no heartbeat prefix parsed and classified correctly.

`extract_frames` fixes this by anchoring on the MLLP start block instead of on
the buffer's first byte. These tests pin that behaviour, and — critically —
pin that a byte-clean frame still yields exactly the payload it did before.
"""
import pytest

from app.integration.mllp import MLLP_EB, MLLP_SB, extract_control_id, extract_frames

SB = bytes([MLLP_SB])  # b"\x0b"
EB = MLLP_EB           # b"\x1c\x0d"
HEARTBEAT = b"\x02"

HL7 = (
    b"MSH|^~\\&|||||20260901145257||ORU^R01|P30|P|2.3.1||||||UNICODE\r"
    b"PID|1||M000123^^^^MR||^supartini|||Female\r"
    b"OBR|1||30|00001^Automated Count^99MRC|||20260901145257\r"
    b"OBX|1|NM|6690-2^WBC^LN||7.50|10*3/uL|4.00-10.00|N|||F\r"
)
HL7_B = HL7.replace(b"|P30|", b"|P31|").replace(b"||30|", b"||31|")


def framed(payload: bytes) -> bytes:
    return SB + payload + EB


# --- baseline: unchanged behaviour for clean input -----------------------

def test_clean_frame_yields_payload_without_delimiters():
    frames, rest = extract_frames(framed(HL7))
    assert frames == [HL7]
    assert rest == b""


def test_clean_frame_payload_is_parseable_end_to_end():
    # Guards the actual regression: the payload must still expose MSH-10.
    frames, _ = extract_frames(framed(HL7))
    assert extract_control_id(frames[0].decode()) == "P30"


# --- the regression: 0x02 heartbeats -------------------------------------

def test_single_leading_heartbeat_is_discarded():
    frames, rest = extract_frames(HEARTBEAT + framed(HL7))
    assert frames == [HL7]
    assert rest == b""


@pytest.mark.parametrize("count", [2, 8, 9, 64])
def test_multiple_leading_heartbeats_are_discarded(count):
    # Live captures showed 2, 8 and 9 accumulated heartbeats.
    frames, rest = extract_frames(HEARTBEAT * count + framed(HL7))
    assert frames == [HL7]
    assert rest == b""


@pytest.mark.parametrize("count", [1, 5, 40])
def test_heartbeats_between_reads_do_not_accumulate(count):
    """Heartbeats arriving in their own recv() must not survive to the next one.

    This is the exact live failure mode: idle heartbeats sat in the buffer and
    were prepended to the frame that followed.
    """
    buffer = b""
    for _ in range(count):
        buffer += HEARTBEAT
        frames, buffer = extract_frames(buffer)
        assert frames == []
        assert buffer == b""  # dropped, not carried forward

    buffer += framed(HL7)
    frames, buffer = extract_frames(buffer)
    assert frames == [HL7]
    assert buffer == b""


def test_heartbeats_interleaved_between_two_frames():
    buffer = framed(HL7) + HEARTBEAT * 3 + framed(HL7_B)
    frames, rest = extract_frames(buffer)
    assert frames == [HL7, HL7_B]
    assert rest == b""


def test_heartbeat_only_buffer_yields_nothing_and_does_not_grow():
    frames, rest = extract_frames(HEARTBEAT * 1000)
    assert frames == []
    assert rest == b""


# --- multiple frames in one recv() ---------------------------------------

def test_multiple_frames_in_one_receive():
    frames, rest = extract_frames(framed(HL7) + framed(HL7_B))
    assert frames == [HL7, HL7_B]
    assert rest == b""


def test_three_frames_with_leading_heartbeats():
    buffer = HEARTBEAT * 4 + framed(HL7) + framed(HL7_B) + framed(HL7)
    frames, rest = extract_frames(buffer)
    assert frames == [HL7, HL7_B, HL7]
    assert rest == b""


# --- incomplete frames across recv() boundaries --------------------------

def test_incomplete_frame_is_retained_until_terminated():
    whole = framed(HL7)
    head, tail = whole[:40], whole[40:]

    frames, buffer = extract_frames(head)
    assert frames == []
    assert buffer == head  # retained verbatim, start block included

    frames, buffer = extract_frames(buffer + tail)
    assert frames == [HL7]
    assert buffer == b""


def test_frame_split_byte_by_byte_across_many_reads():
    whole = HEARTBEAT * 3 + framed(HL7)
    buffer = b""
    collected = []
    for i in range(len(whole)):
        buffer += whole[i:i + 1]
        frames, buffer = extract_frames(buffer)
        collected.extend(frames)
    assert collected == [HL7]
    assert buffer == b""


def test_end_block_split_across_reads():
    # <FS> arrives in one read, <CR> in the next.
    whole = framed(HL7)
    head, tail = whole[:-1], whole[-1:]
    frames, buffer = extract_frames(head)
    assert frames == []
    frames, buffer = extract_frames(buffer + tail)
    assert frames == [HL7]
    assert buffer == b""


def test_second_frame_incomplete_first_still_delivered():
    partial = framed(HL7_B)[:30]
    frames, buffer = extract_frames(framed(HL7) + partial)
    assert frames == [HL7]
    assert buffer == partial


# --- malformed / unexpected bytes before the start block -----------------

@pytest.mark.parametrize(
    "noise",
    [
        b"\x02",
        b"\x02\x02\x02",
        b"\x06",                  # ACK
        b"\x05",                  # ENQ
        b"\x00\xff\x7f",          # arbitrary binary
        b"garbage text",
        b"\x1c\x0d",              # a stray end block with no start block
        b"MSH|^~\\&|no-start-block\r",
    ],
)
def test_noise_before_start_block_is_discarded(noise):
    frames, rest = extract_frames(noise + framed(HL7))
    assert frames == [HL7]
    assert rest == b""


def test_noise_without_any_frame_is_dropped():
    frames, rest = extract_frames(b"\x02\x06\x05garbage")
    assert frames == []
    assert rest == b""


def test_empty_buffer():
    assert extract_frames(b"") == ([], b"")


# --- payload integrity ----------------------------------------------------

def test_payload_containing_start_block_byte_is_not_truncated():
    payload = b"MSH|^~\\&|x\rOBX|1|ST|A||has\x0bvertical-tab|||\r"
    frames, rest = extract_frames(framed(payload))
    assert frames == [payload]
    assert rest == b""


def test_binary_payload_is_passed_through_unmodified():
    payload = b"MSH|^~\\&|bin\rOBX|1|ED|H||" + bytes(range(3, 28)) + b"\r"
    frames, _ = extract_frames(framed(payload))
    assert frames == [payload]


def test_empty_payload_frame():
    frames, rest = extract_frames(SB + EB)
    assert frames == [b""]
    assert rest == b""
