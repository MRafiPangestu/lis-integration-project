"""XN-550 G2 normaliser, fingerprint v1 and identity resolver — DB-free.

Contract §10.2–§10.4, §11.1 (PV-6), §12.4 and §13.4, including the frozen FP1
test vector. Synthetic inputs only: labels are obviously synthetic and values
arbitrary (§20.1); the committed fixture is already redacted.
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import pathlib
from collections import Counter

import pytest

from app.integration import xn550_normalize as normalize_module
from app.integration.parsers.xn550_astm import (
    ConformantMessage,
    EnvelopeDeviation,
    Unparseable,
    parse_xn550_astm,
)
from app.integration.xn550_normalize import (
    ASSOCIATION_UNRESOLVED,
    FINGERPRINT_VERSION,
    IDENTITY_NOTICE,
    NormalizedItem,
    NormalizedResultSet,
    analysis_fingerprint_v1,
    encode_fp1,
    normalize_xn550,
    resolve_identity,
)

FIXTURE = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"
)

# --- the frozen §13.4 test vector ------------------------------------------------------

VECTOR_FP1 = (
    b"26:xn550-analysis-fingerprint1:11:314:2026091710000010:SYNTH-00011:13:WBC1:18:MEASURED5:11.307:10*3/uL-1:N1:F"
    b"1:218:Blasts/Abn_Lympho?-12:INTERPRETIVE3:100---1:F"
    b"1:38:SCAT_WDF-15:IMAGE_REFERENCE---1:N1:F"
)
VECTOR_FINGERPRINT = "6e813274a0a03d00176b8c5454906851efd539c5ff45758455734bafa197bd67"


def _item(seq, code, qualifier, kind, value, units, ref, flag, status="F") -> NormalizedItem:
    return NormalizedItem(
        source_record_index=4 + seq, source_offset_start=100 * seq, source_offset_end=100 * seq + 50,
        source_r_sequence=seq, item_kind=kind, test_code=code, test_code_qualifier=qualifier,
        value_raw=value, units_raw=units, reference_range_raw=ref, abnormal_flag_raw=flag,
        result_status_raw=status,
    )


def vector_set(items=None, **overrides) -> NormalizedResultSet:
    base = dict(
        analysis_at_raw="20260917100000",
        analysis_at=datetime.datetime(2026, 9, 17, 10, 0, 0),
        sample_label="SYNTH-0001",
        p5_populated=False,
        p8_populated=False,
        items=items if items is not None else (
            _item(1, "WBC", "1", "MEASURED", "11.30", "10*3/uL", None, "N"),
            _item(2, "Blasts/Abn_Lympho?", None, "INTERPRETIVE", "100", None, None, None),
            _item(3, "SCAT_WDF", None, "IMAGE_REFERENCE", None, None, None, "N"),
        ),
    )
    base.update(overrides)
    return NormalizedResultSet(**base)


def test_frozen_fp1_test_vector_bytes_and_hash():
    fp1 = encode_fp1(3, vector_set())
    assert len(fp1) == 201
    assert fp1 == VECTOR_FP1
    assert analysis_fingerprint_v1(3, vector_set()) == VECTOR_FINGERPRINT
    assert hashlib.sha256(VECTOR_FP1).hexdigest() == VECTOR_FINGERPRINT
    assert FINGERPRINT_VERSION == 1


def test_fingerprint_is_deterministic_and_independent_of_item_input_order():
    ordered = vector_set()
    shuffled = vector_set(items=tuple(reversed(ordered.items)))
    assert analysis_fingerprint_v1(3, ordered) == analysis_fingerprint_v1(3, shuffled) == VECTOR_FINGERPRINT
    assert len({analysis_fingerprint_v1(3, vector_set()) for _ in range(5)}) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"analysis_at_raw": "20260917100001"},
        {"sample_label": "SYNTH-0002"},
        {"items": (_item(1, "WBC", "1", "MEASURED", "11.31", "10*3/uL", None, "N"),)},
    ],
)
def test_semantic_inputs_change_the_fingerprint(change):
    assert analysis_fingerprint_v1(3, vector_set(**change)) != VECTOR_FINGERPRINT


def test_instrument_is_part_of_the_fingerprint():
    assert analysis_fingerprint_v1(4, vector_set()) != VECTOR_FINGERPRINT


def test_null_and_empty_string_encode_differently():
    with_null = vector_set(items=(_item(1, "WBC", None, "MEASURED", "1", "u", None, "N"),))
    with_empty = vector_set(items=(_item(1, "WBC", "", "MEASURED", "1", "u", None, "N"),))
    assert encode_fp1(3, with_null) != encode_fp1(3, with_empty)
    assert b"-" in encode_fp1(3, with_null) and b"0:" in encode_fp1(3, with_empty)


def test_presence_booleans_are_not_fingerprint_inputs():
    assert analysis_fingerprint_v1(3, vector_set(p5_populated=True, p8_populated=True)) == VECTOR_FINGERPRINT


def test_non_ascii_or_negative_inputs_fail_instead_of_being_replaced():
    with pytest.raises(UnicodeEncodeError):
        encode_fp1(3, vector_set(sample_label="SYNTH-é"))
    with pytest.raises(ValueError):
        encode_fp1(-1, vector_set())


def test_fingerprint_uses_no_json():
    source = pathlib.Path(normalize_module.__file__).read_text(encoding="utf-8")
    assert "json" not in source.lower().replace("no json", "")


# --- normalisation of the committed fixture ----------------------------------------------


def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def with_record(raw: bytes, index: int, old: str, new: str) -> bytes:
    records = raw.decode("ascii").split("\r")
    assert old in records[index]
    records[index] = records[index].replace(old, new, 1)
    return "\r".join(records).encode("ascii")


def test_fixture_normalises_to_one_set_with_42_items_of_the_verified_shapes():
    raw = fixture_bytes()
    parsed = parse_xn550_astm(raw)
    assert isinstance(parsed, ConformantMessage)
    normalized = normalize_xn550(parsed)

    assert normalized.analysis_at_raw == "20260915023225"
    assert normalized.analysis_at == datetime.datetime(2026, 9, 15, 2, 32, 25)
    assert normalized.sample_label == "XXXXXX"  # redaction mask, display label only
    assert (normalized.p5_populated, normalized.p8_populated) == (True, True)
    assert normalized.item_count == 42
    assert Counter(item.item_kind for item in normalized.items) == Counter(
        {"MEASURED": 28, "INTERPRETIVE": 10, "IMAGE_REFERENCE": 4}
    )
    assert normalized.image_reference_count == 4
    assert normalized.non_n_flag_item_count == 6  # 3 H + 3 L; A/W absent from this fixture
    assert [item.source_r_sequence for item in normalized.items] == list(range(1, 43))

    by_code = {item.test_code: item for item in normalized.items}
    wbc = by_code["WBC"]
    assert (wbc.item_kind, wbc.value_raw, wbc.units_raw, wbc.abnormal_flag_raw, wbc.test_code_qualifier) == (
        "MEASURED", "11.30", "10*3/uL", "N", "1",
    )
    assert (by_code["MCV"].value_raw, by_code["MCV"].units_raw, by_code["MCV"].abnormal_flag_raw) == ("79.6", "fL", "L")
    assert (by_code["NEUT%"].value_raw, by_code["NEUT%"].abnormal_flag_raw) == ("76.3", "H")
    interpretive = by_code["Blasts/Abn_Lympho?"]
    assert (interpretive.item_kind, interpretive.value_raw, interpretive.units_raw, interpretive.abnormal_flag_raw) == (
        "INTERPRETIVE", "30", None, None,
    )
    for item in normalized.items:
        assert item.reference_range_raw is None  # never fabricated
        assert item.result_status_raw == "F"
        if item.item_kind == "IMAGE_REFERENCE":
            assert item.value_raw is None and item.units_raw is None
            assert item.test_code in {"SCAT_WDF", "SCAT_WDF-CBC", "DIST_RBC", "DIST_PLT"}
        assert "PNG" not in (item.value_raw or "")


def test_item_offsets_satisfy_pv6_against_the_raw_bytes():
    raw = fixture_bytes()
    normalized = normalize_xn550(parse_xn550_astm(raw))
    for item in normalized.items:
        assert 0 <= item.source_offset_start < item.source_offset_end < len(raw)
        assert raw[item.source_offset_end] == 0x0D
        assert raw[item.source_offset_start:item.source_offset_start + 2] == b"R|"
        fields = raw[item.source_offset_start:item.source_offset_end].decode("ascii").split("|")
        assert fields[1] == str(item.source_r_sequence)
        assert fields[2].split("^")[4] == item.test_code


def test_image_path_folder_date_does_not_change_the_fingerprint():
    raw = fixture_bytes()
    records = raw.decode("ascii").split("\r")
    image_index = next(i for i, record in enumerate(records) if "PNG&R&" in record)
    folder = records[image_index].split("PNG&R&", 1)[1][:8]
    changed = with_record(raw, image_index, f"PNG&R&{folder}", f"PNG&R&{int(folder) + 1:08d}")
    assert changed != raw
    first = normalize_xn550(parse_xn550_astm(raw))
    second = normalize_xn550(parse_xn550_astm(changed))
    assert analysis_fingerprint_v1(3, first) == analysis_fingerprint_v1(3, second)


def test_analysis_time_or_value_change_gives_a_new_fingerprint():
    raw = fixture_bytes()
    base = analysis_fingerprint_v1(3, normalize_xn550(parse_xn550_astm(raw)))
    new_time = raw.replace(b"20260915023225", b"20260915023226")
    new_value = raw.replace(b"|11.30|10*3/uL|", b"|11.40|10*3/uL|", 1)
    assert analysis_fingerprint_v1(3, normalize_xn550(parse_xn550_astm(new_time))) != base
    assert analysis_fingerprint_v1(3, normalize_xn550(parse_xn550_astm(new_value))) != base


def test_mixed_shapes_with_flag_only_and_unknown_flags_are_kept_verbatim():
    raw = fixture_bytes()
    records = raw.decode("ascii").split("\r")
    # interpretive score -> flag-only record with flag A; a measured flag -> W
    idx_interp = next(i for i, r in enumerate(records) if "^^^^Left_Shift?|" in r)
    records[idx_interp] = records[idx_interp].replace("^^^^Left_Shift?|0|||", "^^^^Left_Shift?||||A", 1)
    idx_plt = next(i for i, r in enumerate(records) if "^^^^PLT^1|" in r)
    fields = records[idx_plt].split("|")
    fields[6] = "W"
    records[idx_plt] = "|".join(fields)
    parsed = parse_xn550_astm("\r".join(records).encode("ascii"))
    assert isinstance(parsed, ConformantMessage), parsed
    normalized = normalize_xn550(parsed)
    by_code = {item.test_code: item for item in normalized.items}
    assert (by_code["Left_Shift?"].item_kind, by_code["Left_Shift?"].value_raw, by_code["Left_Shift?"].abnormal_flag_raw) == (
        "FLAG_ONLY", None, "A",
    )
    assert by_code["PLT"].abnormal_flag_raw == "W"
    assert normalized.non_n_flag_item_count == 8  # 3 H + 3 L + A + W, counted lexically


def test_structural_deviation_and_unparseable_input_are_never_normalised():
    raw = fixture_bytes()
    records = raw.decode("ascii").split("\r")
    order = records[3].split("|")
    order[2] = "SYNTH-O3"
    records[3] = "|".join(order)
    deviation = parse_xn550_astm("\r".join(records).encode("ascii"))
    assert isinstance(deviation, EnvelopeDeviation)
    with pytest.raises(TypeError):
        normalize_xn550(deviation)
    unparseable = parse_xn550_astm(b"")
    assert isinstance(unparseable, Unparseable)
    with pytest.raises(TypeError):
        normalize_xn550(unparseable)


def test_uncontrolled_1102_byte_structure_is_a_deviation_and_never_normalised():
    raw = fixture_bytes()
    records = raw.decode("ascii").split("\r")[:-1]
    header, order = records[0], records[3].split("|")
    order[3] = "^^SYNTH-1102"  # 3-component O-4
    order[11], order[25] = "Q", ""
    results = [r for r in records if r.startswith("R|")]
    message = "\r".join([header, "P|1", "|".join(order), *results, "L|1|N"]) + "\r"
    parsed = parse_xn550_astm(message.encode("ascii"))
    assert isinstance(parsed, EnvelopeDeviation)
    assert parsed.token == "XN550_DEV_RECORD_SEQUENCE"
    with pytest.raises(TypeError):
        normalize_xn550(parsed)


def test_identity_resolver_is_constant_unresolved():
    resolution = resolve_identity(vector_set())
    assert (resolution.status, resolution.reason) == (ASSOCIATION_UNRESOLVED, IDENTITY_NOTICE)
    assert ASSOCIATION_UNRESOLVED == "UNRESOLVED"


def test_normalize_module_is_pure():
    tree = ast.parse(pathlib.Path(normalize_module.__file__).read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    assert modules <= {
        "__future__", "datetime", "hashlib", "dataclasses", "typing",
        "app.integration.parsers.xn550_astm",
    }, modules
