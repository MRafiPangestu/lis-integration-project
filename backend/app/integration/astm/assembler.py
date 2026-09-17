"""CR-record ASTM message assembler (XN-550 contract §5).

Turns one session's received byte stream into complete messages and fragments.
Pure: no sockets, no database, no clock, no parsing of field content. Record
recognition uses only the first two bytes of a CR-terminated record (``H|``
starts a message, ``L|`` ends it).

Invariants (contract §5.1):

* a ``recv()`` is never a message and a connection is never a message;
* state is per session — create one assembler per accepted connection;
* every byte fed ends up in exactly one emitted event (complete message or
  fragment), so concatenating all events in order reproduces the stream.

E1381 framing is **not** handled here: field evidence for the tested XN-550
configuration shows bare-CR records with no E1381 bytes. Control bytes are
preserved and reported through ``byte_class_token`` (§5.3); an E1381 de-framing
layer, if ever needed, sits below this class (§5.8).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional, Union

FRAMING_ASTM_CR_RECORDS = "ASTM_CR_RECORDS"

# Resource guards, not semantics (contract §5.6).
MAX_MESSAGE_BYTES = 65_536
MAX_RECORDS_PER_MESSAGE = 512
MAX_OUT_OF_MESSAGE_BYTES = 65_536

# Byte-class tokens (contract §5.3), checked in this order.
TOKEN_E1381_OR_CONTROL_BYTE = "XN550_E1381_OR_CONTROL_BYTE"
TOKEN_UNEXPECTED_LF = "XN550_UNEXPECTED_LF"
TOKEN_NON_ASCII_BYTE = "XN550_NON_ASCII_BYTE"

# Fragment reasons (contract §5.5).
FRAGMENT_INCOMPLETE_AT_CLOSE = "XN550_FRAGMENT_INCOMPLETE_AT_CLOSE"
FRAGMENT_TRUNCATED_BY_NEW_HEADER = "XN550_FRAGMENT_TRUNCATED_BY_NEW_HEADER"
FRAGMENT_BYTES_OUTSIDE_MESSAGE = "XN550_FRAGMENT_BYTES_OUTSIDE_MESSAGE"
FRAGMENT_SIZE_LIMIT = "XN550_FRAGMENT_SIZE_LIMIT"

_CR = 0x0D
_LF = 0x0A
_HEADER = b"H|"
_TERMINATOR = b"L|"


@dataclass(frozen=True)
class CompleteMessage:
    """Bytes from the first byte of an ``H`` record through the CR ending the next ``L`` record."""

    raw: bytes
    offset_start: int  # inclusive, from byte 0 of the session stream
    offset_end: int  # exclusive
    first_byte_at: datetime.datetime
    last_byte_at: datetime.datetime
    read_count: int
    byte_class_token: Optional[str]


@dataclass(frozen=True)
class Fragment:
    """Bytes that are not a complete message. Never parsed."""

    raw: bytes
    offset_start: int
    offset_end: int
    first_byte_at: datetime.datetime
    last_byte_at: datetime.datetime
    read_count: int
    reason: str


AssemblerEvent = Union[CompleteMessage, Fragment]


def byte_class_token(raw: bytes) -> Optional[str]:
    """Return the §5.3 token for *raw*, or ``None`` when it contains only CR and printable ASCII."""
    control = lf = non_ascii = False
    for b in raw:
        if b >= 0x80:
            non_ascii = True
        elif b == _LF:
            lf = True
        elif b < 0x20 and b != _CR:
            control = True
    if control:
        return TOKEN_E1381_OR_CONTROL_BYTE
    if lf:
        return TOKEN_UNEXPECTED_LF
    if non_ascii:
        return TOKEN_NON_ASCII_BYTE
    return None


class _Span:
    """Contiguous stream bytes plus the read provenance needed for an event."""

    __slots__ = ("data", "start", "first_at", "last_at", "first_read", "last_read", "reads")

    def __init__(self) -> None:
        self.data = bytearray()
        self.start = 0
        self.first_at: Optional[datetime.datetime] = None
        self.last_at: Optional[datetime.datetime] = None
        self.first_read = 0
        self.last_read = 0
        self.reads = 0

    def __len__(self) -> int:
        return len(self.data)

    def add(self, piece: bytes, offset: int, read_id: int, read_at: datetime.datetime) -> None:
        if not piece:
            return
        if not self.data:
            self.start = offset
            self.first_at = read_at
            self.first_read = read_id
            self.reads = 1
        elif read_id != self.last_read:
            self.reads += 1
        self.last_read = read_id
        self.last_at = read_at
        self.data += piece

    def absorb(self, other: "_Span") -> None:
        """Append *other*, which must directly follow this span in the stream."""
        if not other.data:
            return
        if not self.data:
            self.start = other.start
            self.first_at = other.first_at
            self.first_read = other.first_read
            self.reads = other.reads
        else:
            self.reads += other.reads - (1 if other.first_read == self.last_read else 0)
        self.last_read = other.last_read
        self.last_at = other.last_at
        self.data += other.data


class AstmRecordAssembler:
    """Per-session CR-record message assembler. Not thread-safe; one owner."""

    def __init__(self) -> None:
        self._offset = 0
        self._read_id = 0
        self._in_message = False
        self._message = _Span()
        self._records = 0
        self._outside = _Span()
        self._pending = _Span()  # the current, not yet CR-terminated record
        # True when _pending continues a record already cut by a size limit:
        # it can never start a message, whatever its first bytes are.
        self._pending_is_continuation = False
        self._closed = False

    # -- introspection --------------------------------------------------------

    @property
    def stream_offset(self) -> int:
        """Total bytes fed so far."""
        return self._offset

    @property
    def has_incomplete_message(self) -> bool:
        """True while bytes of a message (or a record that may start one) are buffered."""
        return self._in_message or (
            not self._pending_is_continuation and bytes(self._pending.data[:1]) == _HEADER[:1]
        )

    # -- feeding --------------------------------------------------------------

    def feed(self, chunk: bytes, read_at: datetime.datetime) -> list[AssemblerEvent]:
        """Consume one socket read. Returns the events it completes, in stream order."""
        if self._closed:
            raise RuntimeError("assembler is closed")
        events: list[AssemblerEvent] = []
        if not chunk:
            return events
        self._read_id += 1
        read_id = self._read_id
        pos = 0
        size = len(chunk)
        while pos < size:
            cr = chunk.find(b"\r", pos)
            end = size if cr == -1 else cr + 1
            piece = chunk[pos:end]
            room = self._room(piece)
            if len(piece) > room:
                self._pending.add(piece[:room], self._offset, read_id, read_at)
                self._offset += room
                pos += room
                self._emit_size_limit(events)
                continue
            self._pending.add(piece, self._offset, read_id, read_at)
            self._offset += len(piece)
            pos = end
            if cr != -1:
                self._complete_record(events)
        return events

    def close(self) -> list[AssemblerEvent]:
        """End of session: emit whatever is still buffered, in stream order."""
        if self._closed:
            return []
        self._closed = True
        events: list[AssemblerEvent] = []
        if self._in_message:
            self._message.absorb(self._pending)
            self._pending = _Span()
            events.append(self._fragment(self._message, FRAGMENT_INCOMPLETE_AT_CLOSE))
            self._message = _Span()
            self._in_message = False
            return events
        if self._outside.data:
            events.append(self._fragment(self._outside, FRAGMENT_BYTES_OUTSIDE_MESSAGE))
            self._outside = _Span()
        if self._pending.data:
            events.append(self._fragment(self._pending, FRAGMENT_INCOMPLETE_AT_CLOSE))
            self._pending = _Span()
        return events

    # -- internals ------------------------------------------------------------

    def _pending_starts_message(self) -> bool:
        return not self._pending_is_continuation and bytes(self._pending.data[:2]) == _HEADER

    def _room(self, piece: bytes) -> int:
        """Bytes the pending record may still grow by before a size limit is hit.

        A record that starts a message is measured against the message limit
        only: buffered out-of-message bytes are flushed separately when it
        completes, so they must not shorten a real message.
        """
        if self._in_message:
            return MAX_MESSAGE_BYTES - len(self._message) - len(self._pending)
        head = (bytes(self._pending.data[:2]) + piece[:2])[:2]
        if not self._pending_is_continuation and head == _HEADER:
            return MAX_MESSAGE_BYTES - len(self._pending)
        return MAX_OUT_OF_MESSAGE_BYTES - len(self._outside) - len(self._pending)

    def _emit_size_limit(self, events: list[AssemblerEvent]) -> None:
        cut_mid_record = len(self._pending) > 0
        if self._in_message:
            self._message.absorb(self._pending)
            events.append(self._fragment(self._message, FRAGMENT_SIZE_LIMIT))
            self._message = _Span()
            self._in_message = False
        elif self._pending_starts_message():
            if self._outside.data:
                events.append(self._fragment(self._outside, FRAGMENT_BYTES_OUTSIDE_MESSAGE))
                self._outside = _Span()
            events.append(self._fragment(self._pending, FRAGMENT_SIZE_LIMIT))
        else:
            self._outside.absorb(self._pending)
            events.append(self._fragment(self._outside, FRAGMENT_SIZE_LIMIT))
            self._outside = _Span()
        self._pending = _Span()
        self._records = 0
        # If a record was cut, whatever follows until the next CR belongs to it
        # and can never start a message. If the limit was reached exactly at a
        # record boundary, the next byte starts a fresh record.
        self._pending_is_continuation = cut_mid_record

    def _complete_record(self, events: list[AssemblerEvent]) -> None:
        record = self._pending
        starts_message = self._pending_starts_message()
        is_terminator = not self._pending_is_continuation and bytes(record.data[:2]) == _TERMINATOR
        self._pending = _Span()
        self._pending_is_continuation = False

        if not self._in_message:
            if starts_message:
                if self._outside.data:
                    events.append(self._fragment(self._outside, FRAGMENT_BYTES_OUTSIDE_MESSAGE))
                    self._outside = _Span()
                self._message.absorb(record)
                self._records = 1
                self._in_message = True
            else:
                self._outside.absorb(record)
            return

        if starts_message:
            events.append(self._fragment(self._message, FRAGMENT_TRUNCATED_BY_NEW_HEADER))
            self._message = _Span()
            self._message.absorb(record)
            self._records = 1
            return

        self._message.absorb(record)
        self._records += 1
        if self._records > MAX_RECORDS_PER_MESSAGE:
            events.append(self._fragment(self._message, FRAGMENT_SIZE_LIMIT))
            self._reset_message()
        elif is_terminator:
            events.append(self._complete(self._message))
            self._reset_message()

    def _reset_message(self) -> None:
        self._message = _Span()
        self._records = 0
        self._in_message = False

    @staticmethod
    def _complete(span: _Span) -> CompleteMessage:
        raw = bytes(span.data)
        return CompleteMessage(
            raw=raw,
            offset_start=span.start,
            offset_end=span.start + len(raw),
            first_byte_at=span.first_at,
            last_byte_at=span.last_at,
            read_count=span.reads,
            byte_class_token=byte_class_token(raw),
        )

    @staticmethod
    def _fragment(span: _Span, reason: str) -> Fragment:
        raw = bytes(span.data)
        return Fragment(
            raw=raw,
            offset_start=span.start,
            offset_end=span.start + len(raw),
            first_byte_at=span.first_at,
            last_byte_at=span.last_at,
            read_count=span.reads,
            reason=reason,
        )
