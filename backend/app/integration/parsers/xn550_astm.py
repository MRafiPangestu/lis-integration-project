"""Sysmex XN-550 ASTM E1394-97 parser and observed-envelope policy (XN-550 Phase 2).

Implements docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md §6
(record parsing), §7 (field map), §6.5 (R-record shapes) and the
``xn550_observed_envelope`` policy of §19.1.

Pure and deterministic: a function of ``bytes`` only. No database, socket,
settings, clock or logging. Field numbering is ASTM 1-based (``R``-4 value,
``R``-7 flag, ``R``-13 analysis timestamp).

What this module deliberately does NOT do:

* assign patient, specimen or visit identity — ``O``-4 component 3 is returned
  only as ``sample_label``, a display label; ``P``-5 / ``P``-8 are reported as
  presence booleans only; ``P``-9, ``O``-3 and ``O``-4 components 1/2/4 stay
  raw-only (the raw text of every field is kept in ``records``);
* interpret flags (``A`` / ``W`` included), units, interpretive scores or
  image paths, or infer QC / calibration / maintenance / startup classes;
* use any sequence number as an identifier;
* classify anything as ``MessageClass.PATIENT_RESULT`` — under this contract
  XN-550 messages are not promoted to the existing clinical path (§0.5).
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Callable, Optional, Union

from app.integration.astm.assembler import (
    MAX_MESSAGE_BYTES,
    MAX_RECORDS_PER_MESSAGE,
    byte_class_token,
)
from app.integration.classification import Classification, MessageClass

PARSER_KEY = "xn550_astm_e1394"
PARSER_VERSION = "xn550-astm-1.0.0"
POLICY_NAME = "xn550_observed_envelope"

# --- tokens -------------------------------------------------------------------

RULE_ENVELOPE_CONFORMANT = "XN550_ENVELOPE_CONFORMANT"

# UNPARSEABLE (stages 1-3). Byte-class tokens are the §5.3 tokens from the assembler.
TOKEN_EMPTY_MESSAGE = "XN550_EMPTY_MESSAGE"
TOKEN_MESSAGE_TOO_LARGE = "XN550_MESSAGE_TOO_LARGE"
TOKEN_DECODE_ERROR = "XN550_DECODE_ERROR"
TOKEN_TRAILING_BYTES = "XN550_TRAILING_BYTES"
TOKEN_EMPTY_RECORD = "XN550_EMPTY_RECORD"
TOKEN_INVALID_RECORD_SYNTAX = "XN550_INVALID_RECORD_SYNTAX"
TOKEN_UNEXPECTED_DELIMITERS = "XN550_UNEXPECTED_DELIMITERS"

# UNCLASSIFIED structural deviations (§6.4).
DEV_RECORD_SEQUENCE = "XN550_DEV_RECORD_SEQUENCE"
DEV_UNEXPECTED_RECORD_TYPE = "XN550_DEV_UNEXPECTED_RECORD_TYPE"
DEV_FIELD_COUNT = "XN550_DEV_FIELD_COUNT"
DEV_HEADER = "XN550_DEV_HEADER"
DEV_POPULATED_COMMENT = "XN550_DEV_POPULATED_COMMENT"
DEV_O3_POPULATED = "XN550_DEV_O3_POPULATED"
DEV_O4_SHAPE = "XN550_DEV_O4_SHAPE"
DEV_O12_NOT_OBSERVED_VALUE = "XN550_DEV_O12_NOT_OBSERVED_VALUE"
DEV_O26_NOT_OBSERVED_VALUE = "XN550_DEV_O26_NOT_OBSERVED_VALUE"
DEV_TERMINATOR = "XN550_DEV_TERMINATOR"
DEV_R_SEQUENCE = "XN550_DEV_R_SEQUENCE"
DEV_ANALYSIS_TIMESTAMP = "XN550_DEV_ANALYSIS_TIMESTAMP"
DEV_RESULT_STATUS = "XN550_DEV_RESULT_STATUS"
DEV_DUPLICATE_TEST_CODE = "XN550_DEV_DUPLICATE_TEST_CODE"
DEV_R_SHAPE = "XN550_DEV_R_SHAPE"
DEV_VALUE_LENGTH = "XN550_DEV_VALUE_LENGTH"
DEV_UNKNOWN_ESCAPE = "XN550_DEV_UNKNOWN_ESCAPE"

# Novelty (§18.1): logged by the ingestion stage, never a deviation, never stored.
NOVELTY_POPULATED_FIELD = "XN550_NOVELTY_POPULATED_FIELD"
NOVELTY_NON_DECIMAL_VALUE = "XN550_NOVELTY_NON_DECIMAL_VALUE"
NOVELTY_FLAG = "XN550_NOVELTY_FLAG"
NOVELTY_UNIT = "XN550_NOVELTY_UNIT"
NOVELTY_TEST_CODE = "XN550_NOVELTY_TEST_CODE"

# --- item kinds (§6.5) --------------------------------------------------------------

ITEM_IMAGE_REFERENCE = "IMAGE_REFERENCE"
ITEM_MEASURED = "MEASURED"
ITEM_INTERPRETIVE = "INTERPRETIVE"
ITEM_FLAG_ONLY = "FLAG_ONLY"

# --- observed envelope constants (§6.3, §2.2) --------------------------------------

DECLARED_DELIMITERS = "\\^&"  # H-2: repeat, component, escape
FIELD_DELIMITER = "|"
REPEAT_DELIMITER = "\\"
COMPONENT_DELIMITER = "^"
_ESCAPE_SEQUENCES = {"F": "|", "S": "^", "R": "\\", "E": "&"}

EXPECTED_FIELD_COUNTS = {"H": 13, "P": 26, "O": 26, "C": 4, "R": 13, "L": 3}
_RECORD_SEQUENCE = re.compile(r"HPCOCR+CL")
EXPECTED_COMMENT = "C|1||"
EXPECTED_TERMINATOR = "L|1|N"
EXPECTED_STANDARD_VERSION = "E1394-97"
OBSERVED_O12 = "N"
OBSERVED_O26 = "F"
OBSERVED_R9 = "F"

# Column widths the normalised values must fit (contract §10.3).
MAX_TEST_CODE = 50
MAX_TEST_CODE_QUALIFIER = 10
MAX_VALUE = 50
MAX_UNITS = 20
MAX_REFERENCE_RANGE = 100
MAX_FLAG = 10
MAX_STATUS = 5
MAX_SAMPLE_LABEL = 100

# Value domains observed in the 22 envelope-conformant corpus files (§2.2).
# Used only to report novelty — never to reject, rename or interpret.
OBSERVED_FLAGS = frozenset({"", "A", "H", "L", "N", "W"})
OBSERVED_UNITS = frozenset({"", "%", "10*3/uL", "10*6/uL", "fL", "g/dL", "pg"})
OBSERVED_TEST_CODES = frozenset({
    "Anemia", "Anisocytosis", "Atypical_Lympho?", "BASO#", "BASO%", "Blasts/Abn_Lympho?",
    "DIST_PLT", "DIST_RBC", "EO#", "EO%", "Fragments?", "HCT", "HGB", "HGB_Defect?", "IG#",
    "IG%", "IG_Present", "Iron_Deficiency?", "LYMPH#", "LYMPH%", "Left_Shift?", "Lymphocytosis",
    "Lymphopenia", "MACROR", "MCH", "MCHC", "MCV", "MICROR", "MONO#", "MONO%", "MPV",
    "Microcytosis", "Monocytosis", "NEUT#", "NEUT%", "NRBC?", "Neutrophilia", "P-LCR", "PCT",
    "PDW", "PLT", "PLT_Abn_Distribution", "PLT_Clumps?", "Positive_Count", "Positive_Diff",
    "Positive_Morph", "RBC", "RBC_Agglutination?", "RDW-CV", "RDW-SD", "SCAT_WDF",
    "SCAT_WDF-CBC", "Turbidity/HGB_Interference?", "WBC",
})

_ANALYSIS_TIMESTAMP = re.compile(r"[0-9]{14}")
_INTERPRETIVE_VALUE = re.compile(r"[0-9]{1,3}")
_DECIMAL_VALUE = re.compile(r"[0-9]+(\.[0-9]+)?")

# --- result types (§6.7) ----------------------------------------------------------------


@dataclass(frozen=True)
class RecordSpan:
    """One CR-terminated record. Offsets are byte offsets within the message,
    ``offset_end`` exclusive and excluding the terminating CR. ``raw_fields``
    holds the raw text of every field (field 1 = record type)."""

    index: int
    record_type: str
    offset_start: int
    offset_end: int
    raw_fields: tuple[str, ...]


@dataclass(frozen=True)
class Novelty:
    token: str
    record_index: int
    field_number: Optional[int]


@dataclass(frozen=True)
class PatientFieldPresence:
    """Presence only. The values of P-5 and P-8 have UNKNOWN meaning and are not copied."""

    p5_populated: bool
    p8_populated: bool


@dataclass(frozen=True)
class OrderFields:
    """``sample_label`` is O-4 component 3 (= the on-screen Sample No.), decoded and
    space-stripped. It is a display label — never a specimen, patient or visit key.
    Components 1, 2 and 4 are raw-only; their meaning is UNKNOWN."""

    sample_label: str
    o4_component1_raw: str
    o4_component2_raw: str
    o4_component4_raw: str


@dataclass(frozen=True)
class ResultRecord:
    record_index: int
    r_sequence: int
    test_code: str
    test_code_qualifier: Optional[str]  # R-3 component 6, meaning UNKNOWN
    item_kind: str
    value_raw: Optional[str]  # None for FLAG_ONLY and IMAGE_REFERENCE (image paths are raw-only)
    units_raw: Optional[str]
    reference_range_raw: Optional[str]  # never fabricated; None when the instrument sent none
    abnormal_flag_raw: Optional[str]  # verbatim; no meaning assigned
    result_status_raw: str
    offset_start: int
    offset_end: int


@dataclass(frozen=True)
class Unparseable:
    """Stages 1-3 failed: the bytes could not be read as ASTM records."""

    token: str
    record_index: Optional[int] = None
    field_number: Optional[int] = None
    parser_version: str = PARSER_VERSION


@dataclass(frozen=True)
class EnvelopeDeviation:
    """Parsed, but not the observed envelope (§6.4). Never normalised."""

    token: str
    record_index: Optional[int]
    field_number: Optional[int]
    records: tuple[RecordSpan, ...]
    parser_version: str = PARSER_VERSION


@dataclass(frozen=True)
class ConformantMessage:
    records: tuple[RecordSpan, ...]
    sender_raw: str  # H-5, raw; component meaning partly UNKNOWN; not an identity
    patient: PatientFieldPresence
    order: OrderFields
    analysis_at_raw: str  # R-13
    analysis_at: datetime.datetime  # R-13 on the instrument clock; not a transmission time
    results: tuple[ResultRecord, ...]
    comments: tuple[RecordSpan, ...]
    novelties: tuple[Novelty, ...]
    parser_version: str = PARSER_VERSION


AstmParseResult = Union[Unparseable, EnvelopeDeviation, ConformantMessage]


class _Deviation(Exception):
    """Internal control flow: first failing envelope check."""

    def __init__(self, token: str, record_index: Optional[int] = None, field_number: Optional[int] = None):
        super().__init__(token)
        self.token = token
        self.record_index = record_index
        self.field_number = field_number


# --- helpers ----------------------------------------------------------------------------------


def decode_escapes(value: str) -> Optional[str]:
    """Decode E1394 escape sequences. Returns ``None`` if any ``&`` is not part of a
    recognised ``&F&`` / ``&S&`` / ``&R&`` / ``&E&`` sequence."""
    if "&" not in value:
        return value
    out: list[str] = []
    i = 0
    while i < len(value):
        char = value[i]
        if char != "&":
            out.append(char)
            i += 1
            continue
        end = value.find("&", i + 1)
        if end == -1:
            return None
        replacement = _ESCAPE_SEQUENCES.get(value[i + 1:end])
        if replacement is None:
            return None
        out.append(replacement)
        i = end + 1
    return "".join(out)


def _field(record: RecordSpan, number: int) -> str:
    """ASTM 1-based field access (field 1 = record type)."""
    return record.raw_fields[number - 1]


def _is_image_reference(r3: list[str], value: str, units: str) -> bool:
    if not value.startswith("PNG&R&") or len(r3) != 5 or units:
        return False
    parts = value.split("&R&")
    return len(parts) == 3 and all(parts) and parts[2].endswith(".PNG")


def _shape(r3: list[str], value: str, units: str) -> Optional[str]:
    if len(r3) not in (5, 6) or any(r3[:4]):
        return None
    if _is_image_reference(r3, value, units):
        return ITEM_IMAGE_REFERENCE
    if len(r3) == 6 and r3[5] and value and units:
        return ITEM_MEASURED
    if len(r3) == 5 and not units and _INTERPRETIVE_VALUE.fullmatch(value):
        return ITEM_INTERPRETIVE
    if len(r3) == 5 and not units and value == "":
        return ITEM_FLAG_ONLY
    return None


# --- parser -------------------------------------------------------------------------------------


def parse_xn550_astm(raw: bytes) -> AstmParseResult:
    """Parse one complete XN-550 message from its exact received bytes."""
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise TypeError("parse_xn550_astm takes the exact raw bytes, not text")
    raw = bytes(raw)

    # Stage 1 — bounds, byte classes, strict ASCII.
    if len(raw) == 0:
        return Unparseable(TOKEN_EMPTY_MESSAGE)
    if len(raw) > MAX_MESSAGE_BYTES:
        return Unparseable(TOKEN_MESSAGE_TOO_LARGE)
    token = byte_class_token(raw)
    if token is not None:
        return Unparseable(token)
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:  # pragma: no cover - unreachable after byte_class_token
        return Unparseable(TOKEN_DECODE_ERROR)

    # Stage 2 — records.
    parts = text.split("\r")
    if parts[-1] != "":
        return Unparseable(TOKEN_TRAILING_BYTES, record_index=len(parts) - 1)
    lines = parts[:-1]
    if len(lines) > MAX_RECORDS_PER_MESSAGE:
        return Unparseable(TOKEN_MESSAGE_TOO_LARGE)
    records: list[RecordSpan] = []
    offset = 0
    for index, line in enumerate(lines):
        if line == "":
            return Unparseable(TOKEN_EMPTY_RECORD, record_index=index)
        if len(line) < 2 or line[1] != FIELD_DELIMITER:
            return Unparseable(TOKEN_INVALID_RECORD_SYNTAX, record_index=index)
        records.append(
            RecordSpan(
                index=index,
                record_type=line[0],
                offset_start=offset,
                offset_end=offset + len(line),
                raw_fields=tuple(line.split(FIELD_DELIMITER)),
            )
        )
        offset += len(line) + 1

    # Stage 3 — delimiter declaration (only when the first record is a header).
    if records[0].record_type == "H":
        header = records[0]
        if len(header.raw_fields) < 2 or header.raw_fields[1] != DECLARED_DELIMITERS:
            return Unparseable(TOKEN_UNEXPECTED_DELIMITERS, record_index=0, field_number=2)

    frozen_records = tuple(records)
    try:
        return _parse_envelope(frozen_records)
    except _Deviation as deviation:
        return EnvelopeDeviation(
            token=deviation.token,
            record_index=deviation.record_index,
            field_number=deviation.field_number,
            records=frozen_records,
        )


def _parse_envelope(records: tuple[RecordSpan, ...]) -> ConformantMessage:
    # #2 before #1: an unknown record type always breaks the sequence as well, so
    # checking the sequence first would make #2 unreachable (contract §19.5).
    for record in records:
        if record.record_type not in EXPECTED_FIELD_COUNTS:
            raise _Deviation(DEV_UNEXPECTED_RECORD_TYPE, record.index)

    # #1 record sequence
    if not _RECORD_SEQUENCE.fullmatch("".join(r.record_type for r in records)):
        raise _Deviation(DEV_RECORD_SEQUENCE)

    # #3 field counts
    for record in records:
        if len(record.raw_fields) != EXPECTED_FIELD_COUNTS[record.record_type]:
            raise _Deviation(DEV_FIELD_COUNT, record.index)

    header, patient, order = records[0], records[1], records[3]
    terminator = records[-1]
    comments = tuple(r for r in records if r.record_type == "C")
    results = tuple(r for r in records if r.record_type == "R")

    # #4 header
    for number in (3, 4, 6, 7, 8, 9, 10, 11, 12):
        if _field(header, number) != "":
            raise _Deviation(DEV_HEADER, header.index, number)
    if _field(header, 13) != EXPECTED_STANDARD_VERSION:
        raise _Deviation(DEV_HEADER, header.index, 13)

    # #5 comments
    for comment in comments:
        if FIELD_DELIMITER.join(comment.raw_fields) != EXPECTED_COMMENT:
            raise _Deviation(DEV_POPULATED_COMMENT, comment.index)

    # #6 O-3
    if _field(order, 3) != "":
        raise _Deviation(DEV_O3_POPULATED, order.index, 3)

    # #7 O-4
    o4 = _field(order, 4)
    if REPEAT_DELIMITER in o4:
        raise _Deviation(DEV_O4_SHAPE, order.index, 4)
    o4_components = o4.split(COMPONENT_DELIMITER)
    if len(o4_components) != 4:
        raise _Deviation(DEV_O4_SHAPE, order.index, 4)
    label_decoded = decode_escapes(o4_components[2])
    label_for_checks = label_decoded if label_decoded is not None else o4_components[2]
    sample_label = label_for_checks.strip(" ")
    if not sample_label or len(sample_label) > MAX_SAMPLE_LABEL:
        raise _Deviation(DEV_O4_SHAPE, order.index, 4)

    # #8 O-12, #9 O-26
    if _field(order, 12) != OBSERVED_O12:
        raise _Deviation(DEV_O12_NOT_OBSERVED_VALUE, order.index, 12)
    if _field(order, 26) != OBSERVED_O26:
        raise _Deviation(DEV_O26_NOT_OBSERVED_VALUE, order.index, 26)

    # #10 terminator
    if FIELD_DELIMITER.join(terminator.raw_fields) != EXPECTED_TERMINATOR:
        raise _Deviation(DEV_TERMINATOR, terminator.index)

    # #11 R-2 sequence
    for expected, record in enumerate(results, start=1):
        if _field(record, 2) != str(expected):
            raise _Deviation(DEV_R_SEQUENCE, record.index, 2)

    # #12 R-13 analysis timestamp
    analysis_at_raw = _field(results[0], 13)
    for record in results:
        if _field(record, 13) != analysis_at_raw:
            raise _Deviation(DEV_ANALYSIS_TIMESTAMP, record.index, 13)
    if not _ANALYSIS_TIMESTAMP.fullmatch(analysis_at_raw):
        raise _Deviation(DEV_ANALYSIS_TIMESTAMP, results[0].index, 13)
    try:
        analysis_at = datetime.datetime.strptime(analysis_at_raw, "%Y%m%d%H%M%S")
    except ValueError:
        raise _Deviation(DEV_ANALYSIS_TIMESTAMP, results[0].index, 13) from None

    # #13 R-9 status
    for record in results:
        if _field(record, 9) != OBSERVED_R9:
            raise _Deviation(DEV_RESULT_STATUS, record.index, 9)

    # #14 duplicate test codes
    seen_codes: set[str] = set()
    for record in results:
        r3 = _field(record, 3).split(COMPONENT_DELIMITER)
        if len(r3) >= 5:
            if r3[4] in seen_codes:
                raise _Deviation(DEV_DUPLICATE_TEST_CODE, record.index, 3)
            seen_codes.add(r3[4])

    # #15 shapes
    kinds: dict[int, str] = {}
    for record in results:
        r3_raw = _field(record, 3)
        value, units = _field(record, 4), _field(record, 5)
        if REPEAT_DELIMITER in r3_raw:
            raise _Deviation(DEV_R_SHAPE, record.index, 3)
        for number in (5, 7, 9):
            if REPEAT_DELIMITER in _field(record, number) or COMPONENT_DELIMITER in _field(record, number):
                raise _Deviation(DEV_R_SHAPE, record.index, number)
        kind = _shape(r3_raw.split(COMPONENT_DELIMITER), value, units)
        if kind is None:
            raise _Deviation(DEV_R_SHAPE, record.index, 3)
        if kind != ITEM_IMAGE_REFERENCE and (REPEAT_DELIMITER in value or COMPONENT_DELIMITER in value):
            raise _Deviation(DEV_R_SHAPE, record.index, 4)
        kinds[record.index] = kind

    # #16 lengths and #17 escapes are evaluated per normalised field; the first
    # failure of either, in table order, wins for the whole message.
    normalised: list[tuple[RecordSpan, str, dict[str, Optional[str]]]] = []
    length_failure: Optional[tuple[int, int]] = None
    escape_failure: Optional[tuple[int, int]] = None
    if label_decoded is None:
        escape_failure = (order.index, 4)
    for record in results:
        kind = kinds[record.index]
        r3 = _field(record, 3).split(COMPONENT_DELIMITER)
        raw_values = {
            "test_code": (r3[4], 3, MAX_TEST_CODE),
            "test_code_qualifier": (r3[5] if len(r3) == 6 else "", 3, MAX_TEST_CODE_QUALIFIER),
            "value": ("" if kind == ITEM_IMAGE_REFERENCE else _field(record, 4), 4, MAX_VALUE),
            "units": (_field(record, 5), 5, MAX_UNITS),
            "reference_range": (_field(record, 6), 6, MAX_REFERENCE_RANGE),
            "flag": (_field(record, 7), 7, MAX_FLAG),
            "status": (_field(record, 9), 9, MAX_STATUS),
        }
        decoded: dict[str, Optional[str]] = {}
        for name, (text, number, limit) in raw_values.items():
            value = decode_escapes(text)
            if value is None:
                escape_failure = escape_failure or (record.index, number)
                value = text
            if len(value) > limit:
                length_failure = length_failure or (record.index, number)
            decoded[name] = value
        normalised.append((record, kind, decoded))
    if length_failure is not None:
        raise _Deviation(DEV_VALUE_LENGTH, *length_failure)
    if escape_failure is not None:
        raise _Deviation(DEV_UNKNOWN_ESCAPE, *escape_failure)

    # Normalisation (§7, §10.3) and novelty (§18.1).
    novelties: list[Novelty] = []
    for number in list(range(6, 12)) + list(range(13, 26)):
        if _field(order, number) != "":
            novelties.append(Novelty(NOVELTY_POPULATED_FIELD, order.index, number))

    result_records: list[ResultRecord] = []
    for record, kind, values in normalised:
        for number in (6, 8, 10, 12):
            if _field(record, number) != "":
                novelties.append(Novelty(NOVELTY_POPULATED_FIELD, record.index, number))
        if values["test_code"] not in OBSERVED_TEST_CODES:
            novelties.append(Novelty(NOVELTY_TEST_CODE, record.index, 3))
        if values["units"] not in OBSERVED_UNITS:
            novelties.append(Novelty(NOVELTY_UNIT, record.index, 5))
        if values["flag"] not in OBSERVED_FLAGS:
            novelties.append(Novelty(NOVELTY_FLAG, record.index, 7))
        if kind == ITEM_MEASURED and not _DECIMAL_VALUE.fullmatch(values["value"]):
            novelties.append(Novelty(NOVELTY_NON_DECIMAL_VALUE, record.index, 4))
        result_records.append(
            ResultRecord(
                record_index=record.index,
                r_sequence=int(_field(record, 2)),
                test_code=values["test_code"],
                test_code_qualifier=values["test_code_qualifier"] or None,
                item_kind=kind,
                value_raw=values["value"] if kind in (ITEM_MEASURED, ITEM_INTERPRETIVE) else None,
                units_raw=values["units"] or None,
                reference_range_raw=values["reference_range"] or None,
                abnormal_flag_raw=values["flag"] or None,
                result_status_raw=values["status"],
                offset_start=record.offset_start,
                offset_end=record.offset_end,
            )
        )

    return ConformantMessage(
        records=records,
        sender_raw=_field(header, 5),
        patient=PatientFieldPresence(
            p5_populated=_field(patient, 5) != "",
            p8_populated=_field(patient, 8) != "",
        ),
        order=OrderFields(
            sample_label=sample_label,
            o4_component1_raw=o4_components[0],
            o4_component2_raw=o4_components[1],
            o4_component4_raw=o4_components[3],
        ),
        analysis_at_raw=analysis_at_raw,
        analysis_at=analysis_at,
        results=tuple(result_records),
        comments=comments,
        novelties=tuple(novelties),
    )


# --- policy (§19.1) ---------------------------------------------------------------------------


def ensure_not_patient_result(classification: Classification) -> Classification:
    """Hard guard: an XN-550 classification can never be PATIENT_RESULT under this contract."""
    if classification.message_class == MessageClass.PATIENT_RESULT:
        raise ValueError("XN-550 messages are not promoted to the clinical PATIENT_RESULT path")
    return classification


def classify_xn550(result: AstmParseResult) -> Classification:
    """``xn550_observed_envelope``. Layer B of the contract's §0.5 — never PATIENT_RESULT."""
    if isinstance(result, ConformantMessage):
        classification = Classification(MessageClass.UNCLASSIFIED, RULE_ENVELOPE_CONFORMANT)
    elif isinstance(result, EnvelopeDeviation):
        classification = Classification(MessageClass.UNCLASSIFIED, result.token)
    elif isinstance(result, Unparseable):
        classification = Classification(MessageClass.UNPARSEABLE, result.token)
    else:
        raise TypeError(f"not an XN-550 parse result: {type(result).__name__}")
    return ensure_not_patient_result(classification)


XN550_POLICIES: "dict[str, Callable[[AstmParseResult], Classification]]" = {
    POLICY_NAME: classify_xn550,
}


def resolve_xn550_policy(name: Optional[str]) -> Callable[[AstmParseResult], Classification]:
    """Exact match only; no fallback (unlike the HL7 strict default)."""
    try:
        return XN550_POLICIES[name]
    except KeyError:
        raise ValueError(f"unknown XN-550 classification_policy {name!r}") from None


def error_detail_for(result: AstmParseResult) -> Optional[str]:
    """``<TOKEN>[ @record <index>[ field <n>]]`` — stable tokens only, never field text."""
    if isinstance(result, ConformantMessage):
        return None
    detail = result.token
    if result.record_index is not None:
        detail += f" @record {result.record_index}"
        if result.field_number is not None:
            detail += f" field {result.field_number}"
    return detail
