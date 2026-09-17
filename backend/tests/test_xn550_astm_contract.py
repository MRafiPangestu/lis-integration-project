"""Sysmex XN-550 — ASTM fixture contract (evidence, not implementation).

This module pins what the **real redacted field capture** structurally is, so
that a future XN-550 parser is written against observed evidence rather than
against the survey report's prose. It is deliberately a *contract*, not a
parser:

* **No production parsing code is exercised here.** This module stays the
  evidence contract; the dedicated XN-550 parser (``app/integration/parsers/
  xn550_astm.py``, XN-550 Phase 2) is tested against it separately in
  ``tests/test_xn550_parser.py``. It deliberately does not reuse ``ParsedHL7``,
  which requires ``nomor_rm`` / ``nama_lengkap`` / ``specimen_no`` — populating
  those from this message would mean *asserting* patient and specimen semantics
  that ``docs/instruments/sysmex_xn550/README.md`` §5.1 records as **UNKNOWN**.
  Only the registry guard at the end of this module imports production code.
* **Only evidence-backed structure is asserted.** Record counts, ordering,
  delimiters, and the ASTM E1394-97 ``R``-record field layout are observable in
  the capture. Field *meaning* beyond that is not, and is left unasserted on
  purpose — see ``test_contract_does_not_assert_unverified_semantics``.
* **DB-free and analyzer-free.** The committed fixture is the only input; no
  PostgreSQL, no socket, no dependency on ``D:\\SurveyLIS`` at runtime.

Evidence: ``docs/instruments/sysmex_xn550/FIELD_REPORT.md`` (survey of
15 September 2026, one session, one message). Per
``docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md`` §12.2 a single session yields at
most a CANDIDATE rule — these assertions describe *this capture*, and are not a
claim about XN-550 behaviour in general.
"""
from __future__ import annotations

import hashlib
import pathlib
from collections import Counter
from datetime import datetime

import pytest

FIXTURE = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"
)

# Pinned from the committed fixture. A change here means the evidence artefact
# itself changed, which must be a deliberate, reviewed act — not a side effect.
FIXTURE_SHA256 = "2fcc8f38de8d6903595b5e876e00de352ace7005b805739486a22106ce543ad3"
FIXTURE_BYTES = 2824

# Observed record inventory (H P C O C R*42 C L).
EXPECTED_RECORD_TYPE_COUNTS = {"H": 1, "P": 1, "O": 1, "C": 3, "R": 42, "L": 1}
EXPECTED_TOTAL_RECORDS = 49

# ASTM E1394-97 delimiters, as declared by this message in H-2.
FIELD_D, REPEAT_D, COMPONENT_D, ESCAPE_D = "|", "\\", "^", "&"


# --------------------------------------------------------------------------- #
# Fixture access — minimal, test-local. Deliberately NOT a parser abstraction.
# --------------------------------------------------------------------------- #


def _raw_bytes() -> bytes:
    """The fixture exactly as committed. Read as bytes: the record terminator
    is a bare CR, which Python's universal-newline handling would rewrite."""
    return FIXTURE.read_bytes()


def _records() -> list[str]:
    """Split on the CR record terminator, dropping the empty trailing element."""
    return [r.decode("ascii") for r in _raw_bytes().split(b"\r") if r]


def _fields(record: str) -> list[str]:
    return record.split(FIELD_D)


def _components(field: str) -> list[str]:
    return field.split(COMPONENT_D)


def _of_type(record_type: str) -> list[str]:
    return [r for r in _records() if r.startswith(record_type + FIELD_D)]


@pytest.fixture(scope="module")
def records() -> list[str]:
    return _records()


@pytest.fixture(scope="module")
def result_records() -> list[str]:
    return _of_type("R")


# --------------------------------------------------------------------------- #
# 1. The artefact itself
# --------------------------------------------------------------------------- #


def test_xn550_fixture_exists_and_is_unmodified():
    """Pins the evidence artefact. A failure means the capture changed."""
    assert FIXTURE.is_file(), f"missing XN-550 fixture: {FIXTURE}"
    raw = _raw_bytes()
    assert len(raw) == FIXTURE_BYTES
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256


def test_xn550_fixture_uses_bare_cr_record_terminators():
    """VERIFIED: the instrument terminated records with CR (0x0D) and sent no
    LF at all. Reading this file with universal newlines silently corrupts the
    record structure, so the contract states it explicitly."""
    raw = _raw_bytes()
    assert b"\n" not in raw, "fixture must contain no LF"
    assert b"\r\n" not in raw, "fixture must contain no CRLF"
    assert raw.count(b"\r") == EXPECTED_TOTAL_RECORDS
    assert raw.endswith(b"\r"), "final record is CR-terminated"


def test_xn550_fixture_contains_no_phi():
    """The committed artefact is a redacted derivative
    (``docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md`` §12.4). The three redacted
    tokens must stay masked, and the masks must still be present — a test that
    only checked for absence would also pass on an empty file."""
    patient = _fields(_of_type("P")[0])
    order = _fields(_of_type("O")[0])

    assert patient[4] == "XXXXX", "patient-id mask missing from P-5"
    assert patient[7] == "XXXXXXXX", "date-of-birth mask missing from P-8"
    assert "XXXXXX" in order[3], "patient-name mask missing from O-4"

    # The name also appears inside four graphic-reference filenames. Counted at
    # field level, not by raw substring: the 8-character date-of-birth mask
    # contains the 6-character name mask, so a whole-file count would be
    # confounded by it.
    graphic = [
        r for r in _of_type("R") if _fields(r)[3].startswith("PNG" + ESCAPE_D)
    ]
    assert len(graphic) == 4
    assert all("XXXXXX" in _fields(r)[3] for r in graphic)


# --------------------------------------------------------------------------- #
# 2. Record structure and ordering
# --------------------------------------------------------------------------- #


def test_xn550_fixture_record_structure(records):
    """VERIFIED record inventory: exactly one H, one P, one O, three C,
    42 R and one L."""
    assert len(records) == EXPECTED_TOTAL_RECORDS
    assert Counter(r[0] for r in records) == Counter(EXPECTED_RECORD_TYPE_COUNTS)


def test_xn550_fixture_record_order(records):
    """VERIFIED ordering: H opens the message, L closes it, P precedes O, and
    every R falls between the O record and the terminator."""
    types = "".join(r[0] for r in records)
    assert types == "HPCOC" + "R" * 42 + "CL"

    assert types[0] == "H"
    assert types[-1] == "L"
    assert types.index("P") < types.index("O") < types.index("R")
    assert types.rindex("R") < types.index("L")


def test_xn550_fixture_preserves_control_records(records):
    """The three C (comment) records must survive as C records and must never
    be folded into the R set.

    **What the capture shows:** all three are ``C|1||`` — sequence 1, with an
    empty comment source and empty comment text. They are structurally present
    but carry **no payload**, so nothing in this message can be semantically
    classified from them. Their positions follow the ASTM E1394-97 hierarchy
    (a comment attaches to the record it follows): one after P, one after O,
    one after the final R.

    They are asserted here so that a future parser is written knowing they
    exist. ``ParsedHL7`` has no comment representation today; that is recorded
    as an open extension point in ``docs/instruments/sysmex_xn550/README.md``
    and is deliberately **not** designed here.
    """
    comments = _of_type("C")
    assert len(comments) == 3
    assert all(c == "C|1||" for c in comments), (
        "every C record in this capture is empty; a populated one would be new "
        "evidence and must not be silently accepted by this contract"
    )

    types = [r[0] for r in records]
    assert types[types.index("P") + 1] == "C", "comment expected after P"
    assert types[types.index("O") + 1] == "C", "comment expected after O"
    assert types[-2] == "C", "comment expected after the final R"

    # A C record must never be mistaken for a result.
    assert all(not c.startswith("R") for c in comments)
    assert len(_of_type("R")) == 42


def test_xn550_fixture_declares_astm_delimiters(records):
    """VERIFIED: H-2 declares the repeat / component / escape delimiters, and
    all three are actually used in the message body."""
    header = records[0]
    assert _fields(header)[1] == REPEAT_D + COMPONENT_D + ESCAPE_D  # "\^&"

    order = _of_type("O")[0]
    assert REPEAT_D in _fields(order)[4], "O-5 separates test codes with '\\'"

    assert COMPONENT_D in _fields(_of_type("R")[0])[2], "R-2 is component-structured"

    graphic = [r for r in _of_type("R") if _fields(r)[3].startswith("PNG" + ESCAPE_D)]
    assert graphic, "escape delimiter '&' is used inside graphic result values"


# --------------------------------------------------------------------------- #
# 3. R-record extraction — the part a parser will have to reproduce
# --------------------------------------------------------------------------- #


def test_xn550_fixture_result_records_have_uniform_field_layout(result_records):
    """VERIFIED: every R record has the same 13 fields, so positional
    extraction is well-defined for this message."""
    assert len(result_records) == 42
    assert {len(_fields(r)) for r in result_records} == {13}


def test_xn550_fixture_result_sequence_is_contiguous(result_records):
    """VERIFIED: R-1 runs 1..42 with no gaps or repeats."""
    assert [int(_fields(r)[1]) for r in result_records] == list(range(1, 43))


def test_xn550_fixture_result_extraction(result_records):
    """VERIFIED extraction points, by ASTM E1394-97 position:

    R-2 universal test id (test name = component 5) · R-3 value ·
    R-4 units · R-6 abnormal flag · R-8 result status · R-12 timestamp.
    """
    first = _fields(result_records[0])
    assert _components(first[2])[4] == "WBC"
    assert first[3] == "11.30"
    assert first[4] == "10*3/uL"
    assert first[6] == "N"
    assert first[8] == "F"
    assert first[12] == "20260915023225"

    by_name = {
        _components(_fields(r)[2])[4]: _fields(r) for r in result_records
    }
    # Spot-checks across all three flag states observed in the capture.
    assert (by_name["RBC"][3], by_name["RBC"][4], by_name["RBC"][6]) == ("4.75", "10*6/uL", "N")
    assert (by_name["MCV"][3], by_name["MCV"][4], by_name["MCV"][6]) == ("79.6", "fL", "L")
    assert (by_name["NEUT%"][3], by_name["NEUT%"][4], by_name["NEUT%"][6]) == ("76.3", "%", "H")


def test_xn550_fixture_result_status_and_timestamp_are_uniform(result_records):
    """VERIFIED: every result is final (R-8 = 'F'), carries the same operator
    id (R-10 = 'lab'), and shares one run timestamp (R-12)."""
    assert {_fields(r)[8] for r in result_records} == {"F"}
    assert {_fields(r)[10] for r in result_records} == {"lab"}

    timestamps = {_fields(r)[12] for r in result_records}
    assert timestamps == {"20260915023225"}
    parsed = datetime.strptime(timestamps.pop(), "%Y%m%d%H%M%S")
    assert (parsed.year, parsed.month, parsed.day) == (2026, 9, 15)


def test_xn550_fixture_abnormal_flags_are_from_the_observed_set(result_records):
    """VERIFIED: R-6 is 'N', 'H', 'L' or empty in this capture.

    The empty ones are exactly the 10 interpretive-flag results, which carry no
    units either. Whether other flag values exist on this instrument is
    **UNKNOWN** — one message cannot establish the full domain.
    """
    flags = Counter(_fields(r)[6] for r in result_records)
    assert set(flags) == {"N", "H", "L", ""}
    assert flags["N"] == 26 and flags["H"] == 3 and flags["L"] == 3 and flags[""] == 10


def test_xn550_fixture_result_reference_ranges_are_absent(result_records):
    """VERIFIED, and load-bearing: R-5 (reference range) is empty on **every**
    result. The BC-5150 HL7 path populates
    ``Result.reference_range_snapshot``; this instrument supplied nothing to
    populate it with. A future parser must not fabricate one."""
    assert all(_fields(r)[5] == "" for r in result_records)


def test_xn550_fixture_result_shapes(result_records):
    """VERIFIED: the 42 results are not homogeneous. Three distinct shapes
    coexist, and a parser that assumes 'R record == numeric measurement' will
    mishandle 14 of them.

    * 28 measured values — units present, flag present, test id ends '^1'
    * 10 interpretive flags — no units, no flag (e.g. 'Blasts/Abn_Lympho?')
    *  4 graphic references — value is a 'PNG&...' filename reference

    What the interpretive-flag *values* mean (30, 0, 20, 90 ...) is **UNKNOWN**
    and is not asserted.
    """
    measured, interpretive, graphic = [], [], []
    for record in result_records:
        f = _fields(record)
        if f[3].startswith("PNG" + ESCAPE_D):
            graphic.append(record)
        elif f[4]:
            measured.append(record)
        else:
            interpretive.append(record)

    assert (len(measured), len(interpretive), len(graphic)) == (28, 10, 4)
    assert len(measured) + len(interpretive) + len(graphic) == len(result_records)

    assert all(_components(_fields(r)[2])[5] == "1" for r in measured)
    assert all(_components(_fields(r)[2])[4].endswith("?") for r in interpretive)
    assert {_components(_fields(r)[2])[4] for r in graphic} == {
        "SCAT_WDF", "SCAT_WDF-CBC", "DIST_RBC", "DIST_PLT",
    }


# --------------------------------------------------------------------------- #
# 4. The boundary — what this contract deliberately does NOT establish
# --------------------------------------------------------------------------- #


def test_contract_does_not_assert_unverified_semantics():
    """A guard on the contract itself.

    Two fields carry identity-looking values and their meaning is unverified:
    P-5 holds a bare numeric id of unknown provenance, and the patient name
    appears in **O-4** (instrument specimen id) rather than in the P record.

    **O-3 — the ASTM specimen-id field — is empty**, which is why
    ``docs/instruments/sysmex_xn550/README.md`` §5.1 records that no specimen
    or barcode identifier is identifiable anywhere in this message. That
    emptiness is asserted here so a future capture carrying a populated O-3
    registers as new evidence instead of passing unnoticed.

    This test asserts only presence or absence, never meaning. Deliberately NOT
    asserted anywhere in this module: that P-5 is an MRN; that O-3 or O-4 is a
    specimen id or barcode; any Patient / Visit / Order mapping; any
    deduplication or retransmission identity; any QC, calibration or
    maintenance classification; and any wire-level ASTM E1381 framing
    behaviour (the fixture is a de-framed record stream — FIELD_REPORT §3.3).
    """
    patient = _fields(_of_type("P")[0])
    order = _fields(_of_type("O")[0])

    assert patient[4] != "", "P-5 is populated; its meaning is UNKNOWN"
    assert order[3] != "", "O-4 is populated; its meaning is UNKNOWN"
    assert order[2] == "", "O-3 (specimen id) is empty in this capture"


def test_only_the_dedicated_xn550_astm_parser_is_registered():
    """Registry guard (updated deliberately in XN-550 Phase 2, contract §19.1).

    The registry holds exactly ``bc5150_hl7`` and the dedicated
    ``xn550_astm_e1394`` parser — no generic ASTM parser. Every other ASTM-looking
    key still fails loudly (``docs/09`` §5.2 — fail-closed, no fallback)."""
    from app.integration.parsers.registry import (
        KNOWN_PARSER_KEYS,
        ParserNotRegisteredError,
        resolve_parser,
    )

    assert KNOWN_PARSER_KEYS == frozenset({"bc5150_hl7", "xn550_astm_e1394"})
    for key in ("xn550_astm", "sysmex_xn550", "astm_generic"):
        with pytest.raises(ParserNotRegisteredError):
            resolve_parser(key)
