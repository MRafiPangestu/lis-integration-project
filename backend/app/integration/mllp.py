"""Minimal MLLP / HL7 frame helpers used by the ingestion path independently of
any vendor parser."""
from __future__ import annotations

from typing import Optional

# MLLP block characters. A frame is  <SB> payload <EB><CR>.
MLLP_SB = 0x0B  # <VT>  start block
MLLP_EB = b"\x1c\x0d"  # <FS><CR>  end block


def extract_frames(buffer: bytes) -> "tuple[list[bytes], bytes]":
    """Split a receive buffer into complete MLLP payloads plus the unconsumed tail.

    Returns ``(frames, remaining)``. Each frame is the payload *between* the
    start block and the end block, with both delimiters removed — the same
    value the ingestion path received before this helper existed.

    Framing is anchored on the start block rather than on the buffer's first
    byte. Anything preceding ``MLLP_SB`` is not part of a frame and is
    discarded. That is what makes the Mindray BC-5150's single-byte ``0x02``
    idle heartbeats harmless: previously they accumulated in the buffer and
    were prepended to the next frame, which pushed the ``MSH`` segment off the
    front and made an otherwise valid message unparseable.

    Bytes are only ever dropped from *before* a start block; the HL7 payload
    itself is never rewritten.

    When no start block is buffered, the tail is dropped rather than kept: no
    frame has begun, so everything present is pre-frame noise, and retaining it
    would let an idle instrument grow the buffer without bound.

    Known limitation (unchanged from the previous implementation): if a frame
    is truncated mid-transmission and a later frame follows, the two are not
    re-synchronised. No field evidence shows the BC-5150 doing this.
    """
    frames: "list[bytes]" = []

    while True:
        start = buffer.find(MLLP_SB)
        if start == -1:
            # No frame has begun — discard pre-frame noise (e.g. heartbeats).
            return frames, b""
        if start > 0:
            buffer = buffer[start:]

        # buffer[0] is the start block, so the end block cannot match at 0.
        end = buffer.find(MLLP_EB, 1)
        if end == -1:
            # Frame started but not yet terminated: keep it for the next read.
            return frames, buffer

        frames.append(buffer[1:end])
        buffer = buffer[end + len(MLLP_EB):]


def extract_control_id(raw_text: str) -> Optional[str]:
    """Return MSH-10 (Message Control ID) from a raw HL7 frame, or ``None``.

    Protocol-level and parser-independent: this lets the ingestion path build a
    failure ACK even when the vendor parser returns nothing or raises. It reads
    only the MSH segment and never interprets clinical content.
    """
    for segment in raw_text.replace("\n", "\r").split("\r"):
        segment = segment.strip()
        if not segment.startswith("MSH"):
            continue
        fields = segment.split("|")
        if len(fields) > 9:
            control_id = fields[9].strip()
            return control_id or None
        return None
    return None
