"""XN-550 Phase 1 — CR-record message assembler (contract §5).

DB-free, socket-free. Inputs are the committed redacted fixture and synthetic
messages built here (obviously synthetic labels, no PHI).
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import pathlib
import random

import pytest

from app.integration.astm import assembler as assembler_module
from app.integration.astm.assembler import (
    FRAGMENT_BYTES_OUTSIDE_MESSAGE,
    FRAGMENT_INCOMPLETE_AT_CLOSE,
    FRAGMENT_SIZE_LIMIT,
    FRAGMENT_TRUNCATED_BY_NEW_HEADER,
    MAX_MESSAGE_BYTES,
    MAX_OUT_OF_MESSAGE_BYTES,
    MAX_RECORDS_PER_MESSAGE,
    TOKEN_E1381_OR_CONTROL_BYTE,
    TOKEN_NON_ASCII_BYTE,
    TOKEN_UNEXPECTED_LF,
    AstmRecordAssembler,
    CompleteMessage,
    Fragment,
    byte_class_token,
)

FIXTURE = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"
)
FIXTURE_SHA256 = "2fcc8f38de8d6903595b5e876e00de352ace7005b805739486a22106ce543ad3"

T0 = datetime.datetime(2026, 9, 17, 10, 0, 0)


def at(i: int) -> datetime.datetime:
    return T0 + datetime.timedelta(milliseconds=i)


def synthetic_message(label: str, results: int = 3) -> bytes:
    records = [
        "H|\\^&|||SYNTH-ANALYZER^0^0^^^^SYNTH0001||||||||E1394-97",
        "P|1",
        "C|1||",
        f"O|1||^^{label}^M|^^^^SYNTH1",
        "C|1||",
    ]
    records += [f"R|{i}|^^^^SYN{i}^1|{i}.0|u||N||F||lab||20260917100000" for i in range(1, results + 1)]
    records += ["C|1||", "L|1|N"]
    return ("\r".join(records) + "\r").encode("ascii")


def feed_chunks(asm: AstmRecordAssembler, chunks: list[bytes]) -> list:
    events = []
    for i, chunk in enumerate(chunks):
        events.extend(asm.feed(chunk, at(i)))
    return events


def split_at(data: bytes, cuts: list[int]) -> list[bytes]:
    bounds = [0, *sorted(cuts), len(data)]
    return [data[a:b] for a, b in zip(bounds, bounds[1:]) if b > a]


def assert_reconstructs(events: list, stream: bytes) -> None:
    """PV-3: events are contiguous and reproduce the stream exactly."""
    position = 0
    for event in events:
        assert event.offset_start == position
        assert event.offset_end == position + len(event.raw)
        position = event.offset_end
    assert b"".join(e.raw for e in events) == stream


@pytest.fixture(scope="module")
def fixture_bytes() -> bytes:
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256
    return raw


# --------------------------------------------------------------------------- #
# Single message
# --------------------------------------------------------------------------- #


def test_fixture_in_one_read_is_one_complete_message(fixture_bytes):
    asm = AstmRecordAssembler()
    events = asm.feed(fixture_bytes, at(0))
    assert len(events) == 1
    msg = events[0]
    assert isinstance(msg, CompleteMessage)
    assert msg.raw == fixture_bytes
    assert hashlib.sha256(msg.raw).hexdigest() == FIXTURE_SHA256
    assert (msg.offset_start, msg.offset_end) == (0, len(fixture_bytes))
    assert msg.read_count == 1
    assert msg.first_byte_at == msg.last_byte_at == at(0)
    assert msg.byte_class_token is None
    assert asm.close() == []


def test_every_two_way_split_of_the_fixture_yields_the_exact_message(fixture_bytes):
    for cut in range(1, len(fixture_bytes)):
        asm = AstmRecordAssembler()
        events = feed_chunks(asm, [fixture_bytes[:cut], fixture_bytes[cut:]])
        assert len(events) == 1, cut
        assert events[0].raw == fixture_bytes, cut
        assert events[0].read_count == 2, cut
        assert events[0].first_byte_at == at(0) and events[0].last_byte_at == at(1)
        assert asm.close() == []


def test_random_chunkings_of_the_fixture_yield_the_exact_message(fixture_bytes):
    rng = random.Random(20260917)
    for _ in range(1000):
        cuts = rng.sample(range(1, len(fixture_bytes)), rng.randint(1, 40))
        chunks = split_at(fixture_bytes, cuts)
        asm = AstmRecordAssembler()
        events = feed_chunks(asm, chunks)
        assert len(events) == 1
        assert hashlib.sha256(events[0].raw).hexdigest() == FIXTURE_SHA256
        assert events[0].read_count == len(chunks)
        assert asm.close() == []


def test_one_byte_reads(fixture_bytes):
    asm = AstmRecordAssembler()
    events = feed_chunks(asm, [bytes([b]) for b in fixture_bytes])
    assert len(events) == 1
    assert events[0].raw == fixture_bytes
    assert events[0].read_count == len(fixture_bytes)


# --------------------------------------------------------------------------- #
# Multiple messages in one session
# --------------------------------------------------------------------------- #


def test_multiple_messages_coalesced_into_one_read(fixture_bytes):
    messages = [synthetic_message("SYNTH-0001"), fixture_bytes, synthetic_message("SYNTH-0002", 7)]
    stream = b"".join(messages)
    asm = AstmRecordAssembler()
    events = asm.feed(stream, at(5))
    assert [e.raw for e in events] == messages
    assert all(isinstance(e, CompleteMessage) and e.read_count == 1 for e in events)
    assert_reconstructs(events, stream)


def test_read_spanning_two_messages_counts_for_both():
    first, second = synthetic_message("SYNTH-A"), synthetic_message("SYNTH-B")
    stream = first + second
    cuts = [len(first) - 5, len(first) + 5]
    events = feed_chunks(AstmRecordAssembler(), split_at(stream, cuts))
    assert [e.raw for e in events] == [first, second]
    assert events[0].read_count == 2 and events[1].read_count == 2
    assert events[0].last_byte_at == at(1) and events[1].first_byte_at == at(1)


def test_interleaved_random_splits_across_many_messages_preserve_order_and_bytes(fixture_bytes):
    rng = random.Random(7)
    messages = [synthetic_message(f"SYNTH-{i:04d}", rng.randint(1, 45)) for i in range(20)]
    messages.insert(10, fixture_bytes)
    stream = b"".join(messages)
    for _ in range(50):
        cuts = rng.sample(range(1, len(stream)), rng.randint(1, 200))
        asm = AstmRecordAssembler()
        events = feed_chunks(asm, split_at(stream, cuts)) + asm.close()
        assert [e.raw for e in events] == messages
        assert_reconstructs(events, stream)


# --------------------------------------------------------------------------- #
# Fragments and malformed boundaries
# --------------------------------------------------------------------------- #


def test_bytes_before_a_header_become_an_outside_fragment():
    junk = b"garbage\rL|1|N\r"
    msg = synthetic_message("SYNTH-0003")
    events = AstmRecordAssembler().feed(junk + msg, at(0))
    assert isinstance(events[0], Fragment) and events[0].reason == FRAGMENT_BYTES_OUTSIDE_MESSAGE
    assert events[0].raw == junk
    assert isinstance(events[1], CompleteMessage) and events[1].raw == msg


def test_terminator_without_header_is_never_a_message():
    stream = b"L|1|N\r"
    asm = AstmRecordAssembler()
    assert asm.feed(stream, at(0)) == []
    closed = asm.close()
    assert len(closed) == 1 and closed[0].reason == FRAGMENT_BYTES_OUTSIDE_MESSAGE


def test_new_header_before_terminator_truncates_the_open_message():
    msg = synthetic_message("SYNTH-0004")
    cut = msg[: msg.index(b"R|2|")]
    events = AstmRecordAssembler().feed(cut + msg, at(0))
    assert isinstance(events[0], Fragment) and events[0].reason == FRAGMENT_TRUNCATED_BY_NEW_HEADER
    assert events[0].raw == cut
    assert isinstance(events[1], CompleteMessage) and events[1].raw == msg
    assert_reconstructs(events, cut + msg)


def test_close_mid_message_keeps_the_bytes_as_incomplete_fragment():
    msg = synthetic_message("SYNTH-0005")
    partial = msg[: len(msg) // 2]  # ends mid-record
    asm = AstmRecordAssembler()
    assert asm.feed(partial, at(0)) == []
    assert asm.has_incomplete_message
    events = asm.close()
    assert len(events) == 1 and events[0].reason == FRAGMENT_INCOMPLETE_AT_CLOSE
    assert events[0].raw == partial
    assert asm.close() == []


def test_partial_header_record_at_close_is_preserved():
    asm = AstmRecordAssembler()
    assert asm.feed(b"H|\\^&|||SYN", at(0)) == []
    assert asm.has_incomplete_message
    events = asm.close()
    assert len(events) == 1 and events[0].reason == FRAGMENT_INCOMPLETE_AT_CLOSE
    assert events[0].raw == b"H|\\^&|||SYN"


def test_close_in_idle_emits_outside_bytes_then_unterminated_tail():
    asm = AstmRecordAssembler()
    asm.feed(b"noise\rmore", at(0))
    events = asm.close()
    assert [(e.reason, e.raw) for e in events] == [
        (FRAGMENT_BYTES_OUTSIDE_MESSAGE, b"noise\r"),
        (FRAGMENT_INCOMPLETE_AT_CLOSE, b"more"),
    ]
    assert_reconstructs(events, b"noise\rmore")


def test_feed_after_close_is_refused():
    asm = AstmRecordAssembler()
    asm.close()
    with pytest.raises(RuntimeError):
        asm.feed(b"H|", at(0))


def test_empty_records_inside_a_message_are_kept():
    msg = synthetic_message("SYNTH-0006").replace(b"P|1\r", b"P|1\r\r")
    events = AstmRecordAssembler().feed(msg, at(0))
    assert len(events) == 1 and events[0].raw == msg


# --------------------------------------------------------------------------- #
# Byte classes (§5.3) — bytes preserved, token reported
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("insert", "token"),
    [
        (b"\x02", TOKEN_E1381_OR_CONTROL_BYTE),
        (b"\x05", TOKEN_E1381_OR_CONTROL_BYTE),
        (b"\x15", TOKEN_E1381_OR_CONTROL_BYTE),
        (b"\x00", TOKEN_E1381_OR_CONTROL_BYTE),
        (b"\n", TOKEN_UNEXPECTED_LF),
        (b"\x80", TOKEN_NON_ASCII_BYTE),
    ],
)
def test_byte_class_tokens_preserve_raw_bytes(insert, token):
    msg = synthetic_message("SYNTH-0007").replace(b"P|1\r", b"P|1" + insert + b"\r")
    events = AstmRecordAssembler().feed(msg, at(0))
    assert len(events) == 1 and isinstance(events[0], CompleteMessage)
    assert events[0].raw == msg
    assert events[0].byte_class_token == token


def test_control_byte_takes_precedence_over_lf_and_non_ascii():
    assert byte_class_token(b"\n\x80\x03") == TOKEN_E1381_OR_CONTROL_BYTE
    assert byte_class_token(b"\n\x80") == TOKEN_UNEXPECTED_LF
    assert byte_class_token(b"H|\r") is None


# --------------------------------------------------------------------------- #
# Size limits (§5.6)
# --------------------------------------------------------------------------- #


def test_oversized_message_becomes_size_limit_fragment_and_scanning_resumes():
    header = b"H|\\^&|||SYNTH\r"
    filler = b"R|1|" + b"X" * (MAX_MESSAGE_BYTES - len(header) - 4)
    # The byte right after the size-limit cut is "H|": it continues the cut
    # record, so it must NOT start a message.
    trap = b"H|trap-in-continuation\rL|1|N\r"
    good = synthetic_message("SYNTH-0008")
    stream = header + filler + trap + good
    asm = AstmRecordAssembler()
    events = feed_chunks(asm, split_at(stream, [1000, 70000])) + asm.close()
    assert [type(e).__name__ for e in events] == ["Fragment", "Fragment", "CompleteMessage"]
    assert events[0].reason == FRAGMENT_SIZE_LIMIT
    assert events[0].raw == header + filler and len(events[0].raw) == MAX_MESSAGE_BYTES
    assert events[1].reason == FRAGMENT_BYTES_OUTSIDE_MESSAGE and events[1].raw == trap
    assert events[2].raw == good
    assert_reconstructs(events, stream)


def test_size_limit_reached_exactly_at_a_record_boundary_does_not_poison_the_next_record():
    junk = b"J" * (MAX_OUT_OF_MESSAGE_BYTES - 1) + b"\r"  # outside segment exactly full
    good = synthetic_message("SYNTH-0010")
    stream = junk + b"Z\r" + good
    asm = AstmRecordAssembler()
    events = asm.feed(stream, at(0)) + asm.close()
    assert events[0].reason == FRAGMENT_SIZE_LIMIT and events[0].raw == junk
    assert events[1].reason == FRAGMENT_BYTES_OUTSIDE_MESSAGE and events[1].raw == b"Z\r"
    assert isinstance(events[2], CompleteMessage) and events[2].raw == good
    assert_reconstructs(events, stream)


def test_too_many_records_becomes_size_limit_fragment():
    records = ["H|\\^&|||SYNTH"] + [f"R|{i}|^^^^S^1|1|u||N||F||lab||20260917100000" for i in range(MAX_RECORDS_PER_MESSAGE + 1)]
    stream = ("\r".join(records) + "\rL|1|N\r").encode("ascii")
    asm = AstmRecordAssembler()
    events = asm.feed(stream, at(0)) + asm.close()
    assert isinstance(events[0], Fragment) and events[0].reason == FRAGMENT_SIZE_LIMIT
    assert not any(isinstance(e, CompleteMessage) for e in events)
    assert_reconstructs(events, stream)


def test_large_outside_segment_is_bounded_and_does_not_cut_a_following_header():
    junk = (b"J" * 99 + b"\r") * (MAX_OUT_OF_MESSAGE_BYTES // 100)  # exactly the outside limit
    good = synthetic_message("SYNTH-0009")
    stream = junk + good
    asm = AstmRecordAssembler()
    events = feed_chunks(asm, split_at(stream, [4096 * k for k in range(1, 20)])) + asm.close()
    assert isinstance(events[-1], CompleteMessage) and events[-1].raw == good
    assert all(isinstance(e, Fragment) for e in events[:-1])
    assert all(len(e.raw) <= MAX_OUT_OF_MESSAGE_BYTES for e in events[:-1])
    assert_reconstructs(events, stream)


# --------------------------------------------------------------------------- #
# Purity
# --------------------------------------------------------------------------- #


def test_assembler_module_imports_no_io_or_database_code():
    tree = ast.parse(pathlib.Path(assembler_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "datetime", "dataclasses", "typing"}, imported
