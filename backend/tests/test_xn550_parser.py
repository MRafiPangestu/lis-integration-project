"""XN-550 Phase 2 — pure parser and ``xn550_observed_envelope`` classification.

DB-free and socket-free. Inputs: the committed redacted fixture and mutations of
it built here (synthetic values only; masks stay masked). Field numbers are
ASTM 1-based.
"""
from __future__ import annotations

import ast
import dataclasses
import datetime
import hashlib
import pathlib
import re
from collections import Counter

import pytest

from app.integration.astm.assembler import (
    MAX_MESSAGE_BYTES,
    MAX_RECORDS_PER_MESSAGE,
    TOKEN_E1381_OR_CONTROL_BYTE,
    TOKEN_NON_ASCII_BYTE,
    TOKEN_UNEXPECTED_LF,
)
from app.integration.classification import Classification, MessageClass
from app.integration.parsers import xn550_astm as parser_module
from app.integration.parsers.registry import (
    PROTOCOL_ASTM_E1394_CR,
    PROTOCOL_HL7_MLLP,
    protocol_family,
    resolve_parser,
)
from app.integration.parsers.xn550_astm import (
    PARSER_KEY,
    PARSER_VERSION,
    POLICY_NAME,
    RULE_ENVELOPE_CONFORMANT,
    ConformantMessage,
    EnvelopeDeviation,
    Unparseable,
    classify_xn550,
    decode_escapes,
    ensure_not_patient_result,
    error_detail_for,
    parse_xn550_astm,
    resolve_xn550_policy,
)

FIXTURE = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"
)
FIXTURE_SHA256 = "2fcc8f38de8d6903595b5e876e00de352ace7005b805739486a22106ce543ad3"
ERROR_DETAIL_FORMAT = re.compile(r"^[A-Z0-9_]+( @record \d+( field \d+)?)?$")

# Record positions in the fixture: H P C O C R*42 C L
H, P, C1, O, C2, FIRST_R, LAST_R, C3, L = 0, 1, 2, 3, 4, 5, 46, 47, 48

SEEN: list = []  # every parse result produced in this module, for the PATIENT_RESULT sweep


def fixture_bytes() -> bytes:
    raw = FIXTURE.read_bytes()
    assert len(raw) == 2824 and hashlib.sha256(raw).hexdigest() == FIXTURE_SHA256
    return raw


def fixture_records() -> list[str]:
    return fixture_bytes().decode("ascii").split("\r")[:-1]


def build(records: list[str]) -> bytes:
    return ("\r".join(records) + "\r").encode("ascii")


def with_field(index: int, number: int, value: str) -> bytes:
    records = fixture_records()
    fields = records[index].split("|")
    fields[number - 1] = value
    records[index] = "|".join(fields)
    return build(records)


def parse(raw: bytes):
    result = parse_xn550_astm(raw)
    SEEN.append(result)
    return result


def assert_deviation(raw: bytes, token: str, record_index=None, field_number=None):
    result = parse(raw)
    assert isinstance(result, EnvelopeDeviation), result
    assert result.token == token
    if record_index is not None:
        assert result.record_index == record_index
    if field_number is not None:
        assert result.field_number == field_number
    classification = classify_xn550(result)
    assert classification == Classification(MessageClass.UNCLASSIFIED, token)
    return result


def assert_unparseable(raw: bytes, token: str):
    result = parse(raw)
    assert isinstance(result, Unparseable), result
    assert result.token == token
    assert classify_xn550(result) == Classification(MessageClass.UNPARSEABLE, token)
    return result


# --------------------------------------------------------------------------- #
# Fixture structure
# --------------------------------------------------------------------------- #


def test_fixture_bytes_and_record_inventory():
    raw = fixture_bytes()
    assert b"\n" not in raw and raw.count(b"\r") == 49 and raw.endswith(b"\r")
    types = "".join(r[0] for r in fixture_records())
    assert types == "HPCOC" + "R" * 42 + "CL"
    assert Counter(types) == Counter({"H": 1, "P": 1, "C": 3, "O": 1, "R": 42, "L": 1})


# --------------------------------------------------------------------------- #
# Conformant fixture
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def conformant() -> ConformantMessage:
    result = parse(fixture_bytes())
    assert isinstance(result, ConformantMessage)
    return result


def test_fixture_is_envelope_conformant_and_classified_unclassified(conformant):
    assert conformant.parser_version == PARSER_VERSION
    assert classify_xn550(conformant) == Classification(MessageClass.UNCLASSIFIED, RULE_ENVELOPE_CONFORMANT)
    assert error_detail_for(conformant) is None
    assert conformant.novelties == ()


def test_records_keep_raw_fields_and_exact_offsets(conformant):
    raw = fixture_bytes()
    assert len(conformant.records) == 49
    for record in conformant.records:
        text = raw[record.offset_start:record.offset_end].decode("ascii")
        assert text == "|".join(record.raw_fields)
        assert raw[record.offset_end:record.offset_end + 1] == b"\r"
        assert record.record_type == text[0]


def test_comment_records_are_preserved_and_never_results(conformant):
    assert [c.index for c in conformant.comments] == [C1, C2, C3]
    assert all("|".join(c.raw_fields) == "C|1||" for c in conformant.comments)
    assert {r.record_index for r in conformant.results}.isdisjoint({C1, C2, C3})


def test_sample_label_is_o4_component3_without_identity_semantics(conformant):
    assert conformant.order.sample_label == "XXXXXX"  # the committed mask, space padding stripped
    assert (conformant.order.o4_component1_raw, conformant.order.o4_component2_raw) == ("", "")
    assert conformant.order.o4_component4_raw == "M"
    field_names = {f.name for f in dataclasses.fields(ConformantMessage)}
    field_names |= {f.name for f in dataclasses.fields(type(conformant.order))}
    field_names |= {f.name for f in dataclasses.fields(type(conformant.patient))}
    forbidden = ("specimen", "patient_id", "mrn", "nomor_rm", "registrasi", "visit", "sex", "gender",
                 "birth", "dob", "barcode", "sequence_number", "rack", "position")
    assert not [n for n in field_names for f in forbidden if f in n]


def test_unknown_patient_fields_stay_raw_only(conformant):
    assert (conformant.patient.p5_populated, conformant.patient.p8_populated) == (True, True)
    patient = conformant.records[P]
    assert patient.raw_fields[4] == "XXXXX" and patient.raw_fields[7] == "XXXXXXXX"  # masks, raw only
    assert patient.raw_fields[8] == "F"  # P-9 kept raw; no attribute interprets it
    assert conformant.records[O].raw_fields[2] == ""  # O-3 raw


def test_analysis_at_is_r13(conformant):
    assert conformant.analysis_at_raw == "20260915023225"
    assert conformant.analysis_at == datetime.datetime(2026, 9, 15, 2, 32, 25)


def test_sender_is_kept_raw(conformant):
    assert conformant.sender_raw == "    XN-550^00-29^41122^^^^BD634545"


def test_result_shapes_and_verbatim_values(conformant):
    results = {r.test_code: r for r in conformant.results}
    assert len(conformant.results) == 42
    assert Counter(r.item_kind for r in conformant.results) == Counter(
        {"MEASURED": 28, "INTERPRETIVE": 10, "IMAGE_REFERENCE": 4}
    )
    assert [r.r_sequence for r in conformant.results] == list(range(1, 43))

    wbc = results["WBC"]
    assert (wbc.item_kind, wbc.value_raw, wbc.units_raw, wbc.abnormal_flag_raw) == ("MEASURED", "11.30", "10*3/uL", "N")
    assert (wbc.result_status_raw, wbc.test_code_qualifier) == ("F", "1")
    assert (results["MCV"].value_raw, results["MCV"].units_raw, results["MCV"].abnormal_flag_raw) == ("79.6", "fL", "L")
    assert (results["NEUT%"].value_raw, results["NEUT%"].abnormal_flag_raw) == ("76.3", "H")

    interpretive = results["Blasts/Abn_Lympho?"]
    assert (interpretive.item_kind, interpretive.value_raw, interpretive.units_raw) == ("INTERPRETIVE", "30", None)
    assert interpretive.abnormal_flag_raw is None and interpretive.test_code_qualifier is None

    image = results["SCAT_WDF"]
    assert (image.item_kind, image.value_raw, image.units_raw, image.abnormal_flag_raw) == ("IMAGE_REFERENCE", None, None, "N")
    raw_path = conformant.records[image.record_index].raw_fields[3]
    assert raw_path.startswith("PNG&R&")  # image path stays raw-only in the record span

    assert all(r.reference_range_raw is None for r in conformant.results)  # never fabricated
    assert all("PNG" not in (r.value_raw or "") for r in conformant.results)
    for result in conformant.results:
        span = conformant.records[result.record_index]
        assert (result.offset_start, result.offset_end) == (span.offset_start, span.offset_end)


def test_parse_is_deterministic():
    assert parse(fixture_bytes()) == parse(fixture_bytes())


def test_flag_only_shape_and_novelty_reporting_keep_values_verbatim():
    records = fixture_records()
    records[FIRST_R + 28] = records[FIRST_R + 28].replace("|30|||||F|", "||||A||F|")  # Blasts/... -> flag only
    records[FIRST_R] = records[FIRST_R].replace("|11.30|10*3/uL||N|", "|----|10*3/uL|4.0-10.0|X|")
    result = parse(build(records))
    assert isinstance(result, ConformantMessage)
    flag_only = result.results[28]
    assert (flag_only.item_kind, flag_only.value_raw, flag_only.abnormal_flag_raw) == ("FLAG_ONLY", None, "A")
    wbc = result.results[0]
    assert (wbc.value_raw, wbc.reference_range_raw, wbc.abnormal_flag_raw) == ("----", "4.0-10.0", "X")
    tokens = {(n.token, n.record_index, n.field_number) for n in result.novelties}
    assert tokens == {
        ("XN550_NOVELTY_NON_DECIMAL_VALUE", FIRST_R, 4),
        ("XN550_NOVELTY_POPULATED_FIELD", FIRST_R, 6),
        ("XN550_NOVELTY_FLAG", FIRST_R, 7),
    }
    assert classify_xn550(result).classification_rule == RULE_ENVELOPE_CONFORMANT


def test_unobserved_unit_and_test_code_are_novelties_not_deviations():
    records = fixture_records()
    records[FIRST_R] = records[FIRST_R].replace("^^^^WBC^1|11.30|10*3/uL|", "^^^^WDF-X^1|11.30|ch|")
    result = parse(build(records))
    assert isinstance(result, ConformantMessage)
    assert {n.token for n in result.novelties} == {"XN550_NOVELTY_TEST_CODE", "XN550_NOVELTY_UNIT"}
    assert result.results[0].units_raw == "ch" and result.results[0].test_code == "WDF-X"


def test_escape_sequences_are_decoded_only_in_normalised_values():
    assert decode_escapes("A&S&B&F&C&R&D&E&E") == "A^B|C\\D&E"
    assert decode_escapes("plain") == "plain"
    for bad in ("A&X&B", "A&B", "&", "A&&B"):
        assert decode_escapes(bad) is None
    raw = with_field(O, 4, "^^  SYNTH&S&LABEL^M")
    result = parse(raw)
    assert isinstance(result, ConformantMessage) and result.order.sample_label == "SYNTH^LABEL"


# --------------------------------------------------------------------------- #
# Unparseable (stages 1-3)
# --------------------------------------------------------------------------- #


def test_empty_input():
    assert_unparseable(b"", "XN550_EMPTY_MESSAGE")


def test_text_input_is_refused():
    with pytest.raises(TypeError):
        parse_xn550_astm(fixture_bytes().decode("ascii"))


def test_lf_present():
    assert_unparseable(fixture_bytes().replace(b"P|1|", b"P|1|\n", 1), TOKEN_UNEXPECTED_LF)


def test_crlf_record_terminators():
    assert_unparseable(fixture_bytes().replace(b"\r", b"\r\n"), TOKEN_UNEXPECTED_LF)


def test_non_ascii_byte():
    assert_unparseable(fixture_bytes().replace(b"XXXXXX", b"XX\xc3\xa9XX", 1), TOKEN_NON_ASCII_BYTE)


@pytest.mark.parametrize("control", [b"\x02", b"\x03", b"\x04", b"\x05", b"\x06", b"\x15", b"\x17", b"\x00"])
def test_control_bytes(control):
    assert_unparseable(fixture_bytes().replace(b"L|1|N", b"L|1|N" + control), TOKEN_E1381_OR_CONTROL_BYTE)


def test_oversized_input():
    records = fixture_records()
    records[FIRST_R] = records[FIRST_R].replace("11.30", "1" * MAX_MESSAGE_BYTES)
    assert_unparseable(build(records), "XN550_MESSAGE_TOO_LARGE")


def test_too_many_records():
    records = fixture_records()
    extra = [records[C1]] * (MAX_RECORDS_PER_MESSAGE)
    assert_unparseable(build(records[:C1] + extra + records[C1:]), "XN550_MESSAGE_TOO_LARGE")


def test_trailing_bytes_after_last_cr():
    assert_unparseable(fixture_bytes() + b"H|\\^&", "XN550_TRAILING_BYTES")


def test_empty_record():
    assert_unparseable(fixture_bytes().replace(b"C|1||\r", b"C|1||\r\r", 1), "XN550_EMPTY_RECORD")


@pytest.mark.parametrize("bad", ["R", "RR|1", "Lx", "|"])
def test_invalid_record_syntax(bad):
    records = fixture_records()
    records.insert(FIRST_R, bad)
    assert_unparseable(build(records), "XN550_INVALID_RECORD_SYNTAX")


@pytest.mark.parametrize("declaration", ["^~\\&", "\\^", "", "&^\\"])
def test_invalid_delimiter_declaration(declaration):
    records = fixture_records()
    records[H] = "H|" + declaration + records[H][len("H|\\^&"):]
    assert_unparseable(build(records), "XN550_UNEXPECTED_DELIMITERS")


# --------------------------------------------------------------------------- #
# Structural deviations (§6.4)
# --------------------------------------------------------------------------- #


def test_missing_header():
    assert_deviation(build(fixture_records()[1:]), "XN550_DEV_RECORD_SEQUENCE")


def test_missing_terminator():
    assert_deviation(build(fixture_records()[:-1]), "XN550_DEV_RECORD_SEQUENCE")


def test_terminator_before_results():
    records = fixture_records()
    terminator = records.pop()
    records.insert(FIRST_R, terminator)
    assert_deviation(build(records), "XN550_DEV_RECORD_SEQUENCE")


@pytest.mark.parametrize("record", ["X|1|SYNTH", "M|1|future-record", "Q|1|^SYNTH", "r|1|^^^^WBC^1"])
def test_unknown_or_future_record_type_fails_closed(record):
    records = fixture_records()
    records.insert(FIRST_R, record)
    assert_deviation(build(records), "XN550_DEV_UNEXPECTED_RECORD_TYPE", record_index=FIRST_R)


def test_uncontrolled_1102_byte_structure_is_not_promoted():
    """Synthetic reproduction of the class-UNKNOWN message's structure (§2.2): no C
    records, a 2-field P, a 3-component O-4, O-12 = Q, O-26 empty."""
    header = fixture_records()[H]
    order = ["O", "1", "", "^^      SYNTH-UNCTRL", "^^^^NEUT%"] + [""] * 21
    order[11], order[25] = "Q", ""
    results = [f"R|{i}|^^^^SYN{i}^1|{i}.0|%||N||F||lab||20260916101500" for i in range(1, 17)]
    result = assert_deviation(build([header, "P|1", "|".join(order), *results, "L|1|N"]), "XN550_DEV_RECORD_SEQUENCE")
    assert not hasattr(result, "results")


def test_field_count():
    records = fixture_records()
    records[FIRST_R + 3] += "|extra"
    assert_deviation(build(records), "XN550_DEV_FIELD_COUNT", record_index=FIRST_R + 3)


def test_patient_record_with_two_fields():
    records = fixture_records()
    records[P] = "P|1"
    assert_deviation(build(records), "XN550_DEV_FIELD_COUNT", record_index=P)


@pytest.mark.parametrize(("number", "value"), [(3, "CTRL-1"), (4, "x"), (7, "y"), (12, "z"), (13, "E1394-99")])
def test_header_deviation(number, value):
    assert_deviation(with_field(H, number, value), "XN550_DEV_HEADER", record_index=H, field_number=number)


def test_malformed_comment_does_not_become_a_result():
    records = fixture_records()
    records[C3] = "C|1|I|SYNTH COMMENT"  # 4 fields, like an observed C, but populated
    result = assert_deviation(build(records), "XN550_DEV_POPULATED_COMMENT", record_index=C3)
    assert [r.record_type for r in result.records].count("R") == 42
    assert result.records[C3].record_type == "C"


def test_populated_o3_is_new_identity_evidence_and_fails_closed():
    assert_deviation(with_field(O, 3, "SYNTH-SPECIMEN"), "XN550_DEV_O3_POPULATED", record_index=O, field_number=3)


@pytest.mark.parametrize("o4", ["^^SYNTH", "^^SYNTH^M^extra", "^^     ^M", "^^SYNTH\\x^M", "^^" + "S" * 101 + "^M"])
def test_o4_shape(o4):
    assert_deviation(with_field(O, 4, o4), "XN550_DEV_O4_SHAPE", record_index=O, field_number=4)


def test_o4_components_1_and_2_are_not_checked():
    result = parse(with_field(O, 4, "12^3^   SYNTH^M"))
    assert isinstance(result, ConformantMessage)
    assert (result.order.o4_component1_raw, result.order.o4_component2_raw) == ("12", "3")


def test_o12_not_observed_value():
    assert_deviation(with_field(O, 12, "Q"), "XN550_DEV_O12_NOT_OBSERVED_VALUE", record_index=O, field_number=12)


def test_o26_not_observed_value():
    assert_deviation(with_field(O, 26, ""), "XN550_DEV_O26_NOT_OBSERVED_VALUE", record_index=O, field_number=26)


@pytest.mark.parametrize("terminator", ["L|1|Q", "L|2|N", "L|1|"])
def test_terminator_deviation(terminator):
    records = fixture_records()
    records[L] = terminator
    assert_deviation(build(records), "XN550_DEV_TERMINATOR", record_index=L)


def test_result_sequence_gap():
    assert_deviation(with_field(FIRST_R + 5, 2, "99"), "XN550_DEV_R_SEQUENCE", record_index=FIRST_R + 5, field_number=2)


@pytest.mark.parametrize(("index", "value"), [(FIRST_R + 7, "20260915023226"), (FIRST_R, "2026091502322"), (FIRST_R, "20261340023225")])
def test_analysis_timestamp(index, value):
    records = fixture_records()
    if index == FIRST_R:
        records = [
            r if not r.startswith("R|") else "|".join(r.split("|")[:12] + [value])
            for r in records
        ]
        raw = build(records)
    else:
        raw = with_field(index, 13, value)
    assert_deviation(raw, "XN550_DEV_ANALYSIS_TIMESTAMP", field_number=13)


def test_non_final_result_status():
    assert_deviation(with_field(LAST_R, 9, "P"), "XN550_DEV_RESULT_STATUS", record_index=LAST_R, field_number=9)


def test_duplicate_test_code():
    records = fixture_records()
    records[FIRST_R + 1] = records[FIRST_R + 1].replace("^^^^RBC^1", "^^^^WBC^1")
    assert_deviation(build(records), "XN550_DEV_DUPLICATE_TEST_CODE", record_index=FIRST_R + 1)


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("^^^^WBC^1|", "^^^WBC^1|"),  # 5 components but units present
        ("^^^^WBC^1|", "X^^^^WBC^1|"),  # component 1 populated
        ("|11.30|10*3/uL|", "||10*3/uL|"),  # measured without value
        ("|11.30|", "|11^30|"),  # component delimiter inside value
        ("|10*3/uL|", "|10*3\\uL|"),  # repeat delimiter inside units
    ],
)
def test_malformed_result_does_not_silently_disappear(before, after):
    records = fixture_records()
    records[FIRST_R] = records[FIRST_R].replace(before, after, 1)
    result = assert_deviation(build(records), "XN550_DEV_R_SHAPE", record_index=FIRST_R)
    assert result.records[FIRST_R].record_type == "R"


def test_interpretive_value_out_of_shape():
    records = fixture_records()
    records[FIRST_R + 28] = records[FIRST_R + 28].replace("|30|", "|3000|")
    assert_deviation(build(records), "XN550_DEV_R_SHAPE", record_index=FIRST_R + 28)


def test_malformed_image_reference():
    records = fixture_records()
    records[FIRST_R + 38] = records[FIRST_R + 38].replace("&R&20260915&R&", "&R&20260915/", 1)
    assert_deviation(build(records), "XN550_DEV_R_SHAPE", record_index=FIRST_R + 38)


def test_value_too_long():
    records = fixture_records()
    records[FIRST_R] = records[FIRST_R].replace("|11.30|", "|" + "1" * 51 + "|")
    assert_deviation(build(records), "XN550_DEV_VALUE_LENGTH", record_index=FIRST_R, field_number=4)


def test_unknown_escape_in_a_normalised_value():
    records = fixture_records()
    records[FIRST_R] = records[FIRST_R].replace("|10*3/uL|", "|10&X&uL|")
    assert_deviation(build(records), "XN550_DEV_UNKNOWN_ESCAPE", record_index=FIRST_R, field_number=5)


# --------------------------------------------------------------------------- #
# Classification policy and error details
# --------------------------------------------------------------------------- #


def test_policy_resolution_is_exact():
    assert resolve_xn550_policy(POLICY_NAME) is classify_xn550
    for name in (None, "strict", "XN550_OBSERVED_ENVELOPE", "unverified_passthrough"):
        with pytest.raises(ValueError):
            resolve_xn550_policy(name)


def test_patient_result_guard():
    with pytest.raises(ValueError):
        ensure_not_patient_result(Classification(MessageClass.PATIENT_RESULT, "anything"))
    ok = Classification(MessageClass.UNCLASSIFIED, RULE_ENVELOPE_CONFORMANT)
    assert ensure_not_patient_result(ok) is ok
    with pytest.raises(TypeError):
        classify_xn550(object())


def test_error_detail_is_tokens_only():
    deviation = parse(with_field(O, 3, "SYNTH-SENTINEL-4242"))
    assert error_detail_for(deviation) == "XN550_DEV_O3_POPULATED @record 3 field 3"
    unparseable = parse(b"")
    assert error_detail_for(unparseable) == "XN550_EMPTY_MESSAGE"
    for result in (deviation, unparseable):
        detail = error_detail_for(result)
        assert ERROR_DETAIL_FORMAT.match(detail) and "SENTINEL" not in detail


def test_registry_binds_the_dedicated_parser_with_its_family():
    assert resolve_parser(PARSER_KEY) is parse_xn550_astm
    assert protocol_family(PARSER_KEY) == PROTOCOL_ASTM_E1394_CR
    assert protocol_family("bc5150_hl7") == PROTOCOL_HL7_MLLP


def test_parser_module_is_pure():
    tree = ast.parse(pathlib.Path(parser_module.__file__).read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    assert modules <= {
        "__future__", "datetime", "re", "dataclasses", "typing",
        "app.integration.astm.assembler", "app.integration.classification",
    }, modules


def test_no_parse_result_in_this_module_is_ever_patient_result():
    """Sweep every result produced above (runs last in file order)."""
    assert len(SEEN) > 60
    for result in SEEN:
        classification = classify_xn550(result)
        assert classification.message_class != MessageClass.PATIENT_RESULT
        assert classification.message_class in (MessageClass.UNCLASSIFIED, MessageClass.UNPARSEABLE)
        detail = error_detail_for(result)
        assert detail is None or ERROR_DETAIL_FORMAT.match(detail)
