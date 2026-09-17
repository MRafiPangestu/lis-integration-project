"""XN-550 G2 normaliser, analysis fingerprint v1 and identity resolver (pure).

Implements docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md
§10.2–§10.4 (what one result set and its items contain), §11.1 (offsets and
semantic text), §13.4 (fingerprint v1 and its FP1 byte encoding) and §12.4
(identity resolver).

Pure and deterministic: a function of the parse result only. No database,
socket, settings, clock or logging.

Identity boundary (contract §12.3): ``sample_label`` is carried as a display
label only; the identity resolver always answers ``UNRESOLVED``; nothing here
derives a patient, specimen, visit or order key, and ``source_r_sequence`` is the
ASTM ``R``-2 result-record sequence, never an instrument UI sequence number.
"""
from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from typing import Optional, Union

from app.integration.parsers.xn550_astm import (
    ITEM_IMAGE_REFERENCE,
    ConformantMessage,
)

FINGERPRINT_VERSION = 1
FINGERPRINT_DOMAIN_TAG = "xn550-analysis-fingerprint"

# Identity status (contract §10.2, §12.4). The only value under this contract.
ASSOCIATION_UNRESOLVED = "UNRESOLVED"
IDENTITY_NOTICE = "XN550_NO_VERIFIED_SPECIMEN_OR_PATIENT_IDENTIFIER"

# Duplicate status (contract §13.3). A flag only; never suppresses a set.
DUPLICATE_NONE = "NONE"
DUPLICATE_POSSIBLE = "POSSIBLE_DUPLICATE"


@dataclass(frozen=True)
class NormalizedItem:
    """One ``R`` record as stored in ``instrument_result_items`` (contract §10.3).

    Offsets are message-relative wire-byte offsets ``[start, end)`` excluding
    the record's CR. ``*_raw`` values are uninterpreted semantic text (escape
    decoded, otherwise verbatim), not wire bytes.
    """

    source_record_index: int
    source_offset_start: int
    source_offset_end: int
    source_r_sequence: int
    item_kind: str
    test_code: str
    test_code_qualifier: Optional[str]
    value_raw: Optional[str]
    units_raw: Optional[str]
    reference_range_raw: Optional[str]
    abnormal_flag_raw: Optional[str]
    result_status_raw: str


@dataclass(frozen=True)
class NormalizedResultSet:
    """The parse-derived content of one ``instrument_result_sets`` row (contract §10.2)."""

    analysis_at_raw: str  # R-13, the 14 wire digits (fingerprint input)
    analysis_at: datetime.datetime  # instrument clock, never corrected
    sample_label: str  # O-4 component 3 — display label only
    p5_populated: bool  # presence only; internal metadata
    p8_populated: bool  # presence only; internal metadata
    items: tuple[NormalizedItem, ...]  # ascending source_r_sequence

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def non_n_flag_item_count(self) -> int:
        """Lexical: flag present and not exactly ``N``. Asserts no clinical meaning."""
        return sum(1 for item in self.items if item.abnormal_flag_raw is not None and item.abnormal_flag_raw != "N")

    @property
    def image_reference_count(self) -> int:
        return sum(1 for item in self.items if item.item_kind == ITEM_IMAGE_REFERENCE)


@dataclass(frozen=True)
class IdentityResolution:
    status: str
    reason: str


def normalize_xn550(parsed: ConformantMessage) -> NormalizedResultSet:
    """Normalise one envelope-conformant message. Anything else is refused.

    Structural deviations, unparseable messages and fragments are never
    normalised (contract §10.4 steps 1–2).
    """
    if not isinstance(parsed, ConformantMessage):
        raise TypeError(f"only XN550_ENVELOPE_CONFORMANT messages are normalised, got {type(parsed).__name__}")
    items = tuple(
        NormalizedItem(
            source_record_index=record.record_index,
            source_offset_start=record.offset_start,
            source_offset_end=record.offset_end,
            source_r_sequence=record.r_sequence,
            item_kind=record.item_kind,
            test_code=record.test_code,
            test_code_qualifier=record.test_code_qualifier,
            value_raw=record.value_raw,
            units_raw=record.units_raw,
            reference_range_raw=record.reference_range_raw,
            abnormal_flag_raw=record.abnormal_flag_raw,
            result_status_raw=record.result_status_raw,
        )
        for record in sorted(parsed.results, key=lambda result: result.r_sequence)
    )
    return NormalizedResultSet(
        analysis_at_raw=parsed.analysis_at_raw,
        analysis_at=parsed.analysis_at,
        sample_label=parsed.order.sample_label,
        p5_populated=parsed.patient.p5_populated,
        p8_populated=parsed.patient.p8_populated,
        items=items,
    )


# --- fingerprint v1 (contract §13.4) ---------------------------------------------------


def _encode(value: Union[None, int, str]) -> bytes:
    """FP1 field encoding.

    NULL    -> b"-"
    text    -> ASCII decimal byte length, b":", the text as US-ASCII bytes
    integer -> the encoding of its decimal digits (no sign, no leading zeros)
    """
    if value is None:
        return b"-"
    if isinstance(value, bool):
        raise TypeError("booleans are not fingerprint inputs")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("fingerprint integers are non-negative")
        value = str(value)
    if not isinstance(value, str):
        raise TypeError(f"unsupported fingerprint input type {type(value).__name__}")
    data = value.encode("ascii")  # non-ASCII raises: a T2 exception, never replaced or skipped
    return str(len(data)).encode("ascii") + b":" + data


def encode_fp1(id_instrument: int, normalized: NormalizedResultSet) -> bytes:
    """The exact FP1 byte string of contract §13.4 (fixed field order, no JSON)."""
    parts = [
        _encode(FINGERPRINT_DOMAIN_TAG),
        _encode(FINGERPRINT_VERSION),
        _encode(id_instrument),
        _encode(normalized.analysis_at_raw),
        _encode(normalized.sample_label),
    ]
    for item in sorted(normalized.items, key=lambda entry: entry.source_r_sequence):
        parts.extend(
            (
                _encode(item.source_r_sequence),
                _encode(item.test_code),
                _encode(item.test_code_qualifier),
                _encode(item.item_kind),
                # Image paths are never normalised: value_raw is always None for
                # IMAGE_REFERENCE (and FLAG_ONLY), so no path can reach FP1.
                _encode(item.value_raw),
                _encode(item.units_raw),
                _encode(item.reference_range_raw),
                _encode(item.abnormal_flag_raw),
                _encode(item.result_status_raw),
            )
        )
    return b"".join(parts)


def analysis_fingerprint_v1(id_instrument: int, normalized: NormalizedResultSet) -> str:
    """Lowercase hex SHA-256 of FP1 (64 characters)."""
    return hashlib.sha256(encode_fp1(id_instrument, normalized)).hexdigest()


# --- identity resolver (contract §12.4) --------------------------------------------------


def resolve_identity(normalized: NormalizedResultSet) -> IdentityResolution:
    """Constant seam: no verified specimen or patient identifier exists."""
    return IdentityResolution(status=ASSOCIATION_UNRESOLVED, reason=IDENTITY_NOTICE)
