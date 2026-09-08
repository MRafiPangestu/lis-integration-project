"""Minimal MLLP / HL7 frame helpers used by the ingestion path independently of
any vendor parser."""
from __future__ import annotations

from typing import Optional


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
