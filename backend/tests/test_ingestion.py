"""M8.2 ingestion hardening & classification test suite.

Repeat-run / run_sequence cases run against PostgreSQL (the partial unique index
behaves differently under SQLite), reusing the existing test database.
"""
import logging

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.integration import repository
from app.integration.classification import (
    Classification,
    MessageClass,
    classify,
    resolve_policy,
)
from app.integration.mllp import extract_control_id
from app.integration.parsers.hl7 import parse_hl7_bc5150
from app.integration.repository import process_message
from app.models import (
    Instrument,
    InstrumentMessage,
    Order,
    Patient,
    Result,
    TestRun,
    Visit,
)
from app.models.base import Base

PG_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(PG_URL)
SessionTest = sessionmaker(bind=engine, autoflush=False, autocommit=False)

STRICT = lambda parsed: classify(parsed, resolve_policy("strict"))
PASSTHROUGH = lambda parsed: classify(parsed, resolve_policy("unverified_passthrough"))
BC5150 = lambda parsed: classify(parsed, resolve_policy("bc5150_field_verified"))
BC5150_NAME = lambda parsed: classify(parsed, resolve_policy("bc5150_name_passthrough"))


# --- fixtures -------------------------------------------------------------

@pytest.fixture(scope="module")
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean(_schema):
    with SessionTest() as s:
        for table in reversed(Base.metadata.sorted_tables):
            s.execute(table.delete())
        s.commit()
    yield


@pytest.fixture
def session():
    s = SessionTest()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def instrument_id(session):
    inst = Instrument(nama_mesin="Mindray BC-5150", protokol="HL7", tipe_koneksi="TCP/IP")
    session.add(inst)
    session.commit()
    return inst.id_instrument


# --- helpers -----------------------------------------------------------

class FakeTransport:
    def __init__(self):
        self.acks = []  # (control_id, success, error)

    def send_ack(self, control_id, success=True, error=""):
        self.acks.append((control_id, success, error))

    def send_command(self, command):  # pragma: no cover
        raise NotImplementedError


def hl7_message(control_id="MSGID1", obr3="30", obr7="20230519094058",
                *, include_is=True, with_results=True) -> bytes:
    segs = [
        r"MSH|^~\&|||||20260901145257||ORU^R01|" + control_id + r"|P|2.3.1||||||UNICODE",
        "PID|1||^^^^MR||^supartini|||Female",
        "PV1|1",
        f"OBR|1||{obr3}|00001^Automated Count^99MRC|||{obr7}|||||||||||||||||HM||||||||Administrator",
    ]
    if include_is:
        segs.append("OBX|1|IS|08001^Take Mode^99MRC||O||||||F")
    if with_results:
        segs.append("OBX|2|NM|6690-2^WBC^LN||18.40|10*3/uL|4.00-10.00|H~N|||F")
        segs.append("OBX|3|NM|718-7^HGB^LN||12.8|g/dL|11.0-16.0|N|||F")
    if include_is:
        segs.append("OBX|4|IS|12002^Leucocytosis^99MRC||T||||||F")
    return "\r".join(segs).encode("utf-8")


def run_message(raw_frame, instrument_id, *, parser=parse_hl7_bc5150,
                classify_fn=STRICT, identity_prefix="BC5150-") -> FakeTransport:
    transport = FakeTransport()
    with SessionTest() as s:
        process_message(
            raw_frame, transport, instrument_id, s,
            parser=parser, identity_prefix=identity_prefix, classify_fn=classify_fn,
        )
    return transport


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


# =====================================================================
# A. Parser behaviour
# =====================================================================

def test_parser_clinical_extraction_unchanged():
    parsed = parse_hl7_bc5150(hl7_message().decode())
    assert parsed is not None
    assert parsed.control_id == "MSGID1"
    assert [r.parameter_tes for r in parsed.results] == ["WBC", "HGB"]
    wbc, hgb = parsed.results
    assert (wbc.nilai_hasil, wbc.satuan, wbc.flag_abnormalitas, wbc.reference_range_snapshot) == \
        ("18.40", "10*3/uL", "H", "4.00-10.00")
    assert hgb.flag_abnormalitas is None  # 'N' normalised to None
    assert parsed.order.specimen_no == "30"


# =====================================================================
# B. IS-typed OBX metadata
# =====================================================================

def test_is_metadata_is_preserved_without_touching_clinical_results():
    parsed = parse_hl7_bc5150(hl7_message().decode())
    captured = {(m.obx_type, m.identifier, m.value) for m in parsed.is_metadata}
    assert ("IS", "08001^Take Mode^99MRC", "O") in captured
    assert ("IS", "12002^Leucocytosis^99MRC", "T") in captured
    assert len(parsed.results) == 2  # unchanged


def test_is_metadata_respects_graphic_keyword_protection():
    raw = "\r".join([
        r"MSH|^~\&|||||x||ORU^R01|G1|P|2.3.1",
        "OBX|1|IS|08500^Histogram Data^99MRC||blob||||||F",
        "OBX|2|IS|08600^Scattergram^99MRC||blob||||||F",
    ])
    assert parse_hl7_bc5150(raw).is_metadata == []


def test_only_is_typed_obx_captured_not_other_non_numeric():
    raw = "\r".join([
        r"MSH|^~\&|||||x||ORU^R01|G2|P|2.3.1",
        "OBX|1|CE|1234^Coded^L||value||||||F",
        "OBX|2|IS|9999^Flag^99MRC||X||||||F",
    ])
    parsed = parse_hl7_bc5150(raw)
    assert [m.identifier for m in parsed.is_metadata] == ["9999^Flag^99MRC"]
    assert parsed.results == []


# =====================================================================
# C. Classification mechanism
# =====================================================================

def test_unconfigured_policy_resolves_to_strict_unclassified():
    parsed = parse_hl7_bc5150(hl7_message().decode())
    c = classify(parsed, resolve_policy(None))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.classification_rule == "strict"


def test_strict_policy_on_valid_parsed_message_is_unclassified():
    parsed = parse_hl7_bc5150(hl7_message().decode())
    assert classify(parsed, resolve_policy("strict")).message_class is MessageClass.UNCLASSIFIED


def test_explicit_passthrough_policy_yields_patient_result():
    parsed = parse_hl7_bc5150(hl7_message().decode())
    c = classify(parsed, resolve_policy("unverified_passthrough"))
    assert c.message_class is MessageClass.PATIENT_RESULT
    assert c.classification_rule == "unverified_passthrough"


def test_unknown_policy_name_falls_back_to_strict(caplog):
    parsed = parse_hl7_bc5150(hl7_message().decode())
    with caplog.at_level(logging.WARNING):
        c = classify(parsed, resolve_policy("totally-made-up"))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert "unknown classification_policy" in caplog.text


def test_classifier_exception_fails_closed_to_unclassified():
    def boom(parsed):
        raise RuntimeError("policy exploded")

    parsed = parse_hl7_bc5150(hl7_message().decode())
    c = classify(parsed, boom)
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.classification_rule == "classifier_error"


def test_parser_none_classifies_as_unparseable():
    c = classify(None, resolve_policy("unverified_passthrough"))
    assert c.message_class is MessageClass.UNPARSEABLE
    assert c.classification_rule == "unparseable"


def test_non_patient_creates_no_clinical_rows(session, instrument_id):
    tr = run_message(
        hl7_message(), instrument_id,
        classify_fn=lambda p: Classification(MessageClass.NON_PATIENT, "test.non_patient"),
    )
    assert count(session, TestRun) == 0
    assert count(session, Result) == 0
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.message_class == "NON_PATIENT"
    assert m.classification_rule == "test.non_patient"
    assert m.parse_status == "Success"
    assert tr.acks == [("MSGID1", True, "")]  # message received & stored


# =====================================================================
# D. Structural fail-closed property
# =====================================================================

@pytest.mark.parametrize("mc,rule", [
    (MessageClass.NON_PATIENT, "t.np"),
    (MessageClass.UNCLASSIFIED, "t.uc"),
])
def test_non_patient_result_classes_never_persist_clinical_rows(session, instrument_id, mc, rule):
    run_message(hl7_message(), instrument_id,
                classify_fn=lambda p: Classification(mc, rule))
    assert count(session, TestRun) == 0
    assert count(session, Result) == 0
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.message_class == mc.value


def test_unparseable_never_persists_clinical_rows(session, instrument_id):
    run_message(b"NOT HL7 AT ALL", instrument_id,
                parser=lambda t: None, classify_fn=PASSTHROUGH)
    assert count(session, TestRun) == 0
    assert count(session, Result) == 0
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.message_class == "UNPARSEABLE"


def test_every_terminal_message_has_message_class(session, instrument_id):
    run_message(hl7_message(control_id="A"), instrument_id, classify_fn=STRICT)
    run_message(b"garbage", instrument_id, parser=lambda t: None, classify_fn=STRICT)
    run_message(hl7_message(control_id="C", obr3="7", obr7="20230101010101"),
                instrument_id, classify_fn=PASSTHROUGH)
    for m in session.scalars(select(InstrumentMessage)).all():
        assert m.message_class is not None


# =====================================================================
# E. Raw-message persistence across failures
# =====================================================================

def test_raw_row_survives_parser_exception(session, instrument_id):
    def boom(text):
        raise ValueError("parser exploded")

    run_message(hl7_message(), instrument_id, parser=boom, classify_fn=STRICT)
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.raw_message.startswith("MSH")
    assert m.parse_status == "Failed"
    assert "ValueError: parser exploded" in m.error_detail
    assert m.message_class == "UNPARSEABLE"
    assert m.classification_rule == "unparseable.parser_error"


def test_raw_row_survives_post_parse_integrity_error(session, instrument_id, monkeypatch):
    run_message(hl7_message(obr3="55", obr7="20230101080000"), instrument_id, classify_fn=PASSTHROUGH)
    monkeypatch.setattr(repository, "_next_run_sequence", lambda s, o: 1)  # collide
    run_message(hl7_message(obr3="55", obr7="20230202080000"), instrument_id, classify_fn=PASSTHROUGH)

    assert count(session, TestRun) == 1  # only the first
    msgs = session.scalars(select(InstrumentMessage).order_by(InstrumentMessage.id_message)).all()
    assert len(msgs) == 2
    assert msgs[1].parse_status == "Failed"
    assert "IntegrityError" in msgs[1].error_detail
    assert msgs[1].message_class == "PATIENT_RESULT"


def test_raw_row_survives_unexpected_exception(session, instrument_id, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("kaboom in persistence")

    monkeypatch.setattr(repository, "_next_run_sequence", boom)
    run_message(hl7_message(), instrument_id, classify_fn=PASSTHROUGH)
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.parse_status == "Failed"
    assert "RuntimeError: kaboom in persistence" in m.error_detail
    assert m.message_class == "PATIENT_RESULT"  # classified before the failure


# =====================================================================
# F. ACK behaviour (timing position unchanged)
# =====================================================================

def test_parser_exception_sends_ae_using_raw_frame_control_id(instrument_id):
    def boom(text):
        raise ValueError("x")

    tr = run_message(hl7_message(control_id="CTRL9"), instrument_id, parser=boom, classify_fn=STRICT)
    assert tr.acks == [("CTRL9", False, "Ingestion error")]


def test_parser_none_sends_ae_using_raw_frame_control_id(instrument_id):
    tr = run_message(hl7_message(control_id="CTRL7"), instrument_id,
                     parser=lambda t: None, classify_fn=STRICT)
    assert tr.acks == [("CTRL7", False, "Unparseable message")]


def test_ae_control_id_comes_from_raw_frame_not_parser(instrument_id):
    raw = ("\r".join([r"MSH|^~\&|||||x||ORU^R01|RAWID|P|2.3.1", "PID|1"])).encode()
    tr = run_message(raw, instrument_id, parser=lambda t: None, classify_fn=STRICT)
    assert tr.acks[0][0] == "RAWID"
    assert extract_control_id(raw.decode()) == "RAWID"


def test_ae_uses_empty_control_id_when_no_msh10_available(instrument_id, caplog):
    with caplog.at_level(logging.WARNING):
        tr = run_message(b"PID|1||x", instrument_id, parser=lambda t: None, classify_fn=STRICT)
    assert tr.acks == [("", False, "Unparseable message")]
    assert "no MSH-10" in caplog.text


# =====================================================================
# G. Error observability
# =====================================================================

def test_original_exception_is_observable_in_logs_and_message(session, instrument_id, caplog):
    def boom(text):
        raise KeyError("SECRET_MARKER_42")

    with caplog.at_level(logging.ERROR):
        run_message(hl7_message(), instrument_id, parser=boom, classify_fn=STRICT)

    m = session.scalars(select(InstrumentMessage)).one()
    assert "SECRET_MARKER_42" in m.error_detail
    assert any(
        r.exc_info and "SECRET_MARKER_42" in repr(r.exc_info[1])
        for r in caplog.records
    )


# =====================================================================
# H. Idempotency (exact retransmission)
# =====================================================================

def test_exact_retransmission_stays_idempotent_and_persists_raw(session, instrument_id):
    frame = hl7_message(control_id="R1", obr3="71", obr7="20230101101010")
    tr1 = run_message(frame, instrument_id, classify_fn=PASSTHROUGH)
    tr2 = run_message(frame, instrument_id, classify_fn=PASSTHROUGH)

    assert count(session, TestRun) == 1
    assert count(session, Result) == 2
    msgs = session.scalars(select(InstrumentMessage)).all()
    assert len(msgs) == 2  # both raw rows kept
    assert tr1.acks == [("R1", True, "")]
    assert tr2.acks == [("R1", True, "")]
    retrans = [m for m in msgs if m.error_detail and "Retransmission" in m.error_detail]
    assert len(retrans) == 1
    assert retrans[0].message_class == "PATIENT_RESULT"
    assert retrans[0].parse_status == "Success"


# =====================================================================
# I. Repeat-run / run_sequence (PostgreSQL)
# =====================================================================

def test_different_waktu_run_creates_new_testrun_and_increments_sequence(session, instrument_id):
    run_message(hl7_message(obr3="80", obr7="20230101090000"), instrument_id, classify_fn=PASSTHROUGH)
    run_message(hl7_message(obr3="80", obr7="20230102090000"), instrument_id, classify_fn=PASSTHROUGH)

    runs = session.scalars(select(TestRun).order_by(TestRun.run_sequence)).all()
    assert [r.run_sequence for r in runs] == [1, 2]
    assert runs[0].id_order == runs[1].id_order


def test_new_run_leaves_previous_results_untouched(session, instrument_id):
    run_message(hl7_message(obr3="81", obr7="20230101090000"), instrument_id, classify_fn=PASSTHROUGH)
    first_run = session.scalars(select(TestRun)).one()
    before = {
        r.id_hasil: (r.parameter_tes, r.nilai_hasil, r.flag_abnormalitas)
        for r in session.scalars(select(Result)).all()
    }

    run_message(hl7_message(obr3="81", obr7="20230102090000"), instrument_id, classify_fn=PASSTHROUGH)

    after = {
        r.id_hasil: (r.parameter_tes, r.nilai_hasil, r.flag_abnormalitas)
        for r in session.scalars(select(Result).where(Result.id_run == first_run.id_run)).all()
    }
    assert after == before


def test_run_sequence_uniqueness_conflict_preserves_clinical_message(session, instrument_id, monkeypatch):
    run_message(hl7_message(obr3="99", obr7="20230101080000"), instrument_id, classify_fn=PASSTHROUGH)
    monkeypatch.setattr(repository, "_next_run_sequence", lambda s, o: 1)
    tr = run_message(hl7_message(obr3="99", obr7="20230103080000"), instrument_id, classify_fn=PASSTHROUGH)

    assert count(session, TestRun) == 1
    msgs = session.scalars(select(InstrumentMessage).order_by(InstrumentMessage.id_message)).all()
    assert len(msgs) == 2
    assert msgs[1].parse_status == "Failed"
    assert "IntegrityError" in msgs[1].error_detail
    assert msgs[1].raw_message.startswith("MSH")
    assert tr.acks == [("MSGID1", False, "Ingestion error")]


# =====================================================================
# J. Regression: clinical extraction with the patient-result gate open
# =====================================================================

def test_clinical_persistence_matches_parser_output_when_gate_open(session, instrument_id):
    run_message(hl7_message(obr3="123", obr7="20230505050505"), instrument_id, classify_fn=PASSTHROUGH)

    results = session.scalars(select(Result).order_by(Result.id_hasil)).all()
    got = [
        (r.parameter_tes, r.nilai_hasil, r.satuan, r.flag_abnormalitas, r.reference_range_snapshot)
        for r in results
    ]
    assert got == [
        ("WBC", "18.40", "10*3/uL", "H", "4.00-10.00"),
        ("HGB", "12.8", "g/dL", None, "11.0-16.0"),
    ]
    run = session.scalars(select(TestRun)).one()
    assert (run.run_sequence, run.is_final, run.delivery_status) == (1, False, "pending")
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.parse_status == "Success"
    assert m.message_class == "PATIENT_RESULT"
    assert m.classification_rule == "unverified_passthrough"


# =====================================================================
# K. M8.2b — field-verified BC-5150 "Background" classification rule
# =====================================================================
#
# Field evidence (committed captures / physical UI screenshots):
#   * patient samples 28, 29, 30, 31 — PID metadata present, numeric results
#   * "Background" run — OBR-3 literally "Background", PID-3 empty,
#     WBC ~0.05, RBC 0.00, PLT 0-1, histogram/scattergram present
#
# The ONLY field-verified fact: OBR-3 (normalised) == "background" -> NON_PATIENT.
# Everything else stays UNCLASSIFIED (fail closed). There is no field evidence
# that a non-"Background" message is a patient result, and QC / calibration /
# maintenance / control categories are unverified — so the policy must never
# emit PATIENT_RESULT.


def bc5150_background_message(control_id="BG359", obr3="Background") -> bytes:
    """Real field-shaped BC-5150 Background capture (sample 359)."""
    segs = [
        r"MSH|^~\&|||||20260901150000||ORU^R01|" + control_id + r"|P|2.3.1||||||UNICODE",
        "PID|1||||||||",  # PID-3 empty, no patient identity
        "PV1|1",
        f"OBR|1||{obr3}|00001^Automated Count^99MRC|||20260901150000|||||||||||||||||HM||||||||Administrator",
        "OBX|1|IS|08001^Take Mode^99MRC||O||||||F",
        "OBX|2|NM|6690-2^WBC^LN||0.06|10*3/uL|4.00-10.00|L|||F",
        "OBX|3|NM|789-8^RBC^LN||0.00|10*6/uL|3.50-5.50|L|||F",
        "OBX|4|NM|4544-3^HCT^LN||0.0|%|37.0-54.0|L|||F",
        "OBX|5|NM|777-3^PLT^LN||1|10*3/uL|100-300|L|||F",
        "OBX|6|IS|00700^WBC Histogram^99MRC||AAECAwQF||||||F",
    ]
    return "\r".join(segs).encode("utf-8")


def bc5150_patient_message(control_id="P30", obr3="30", *, pid3_empty=False) -> bytes:
    """Field-shaped BC-5150 patient sample (30/31)."""
    pid = "PID|1||||||||" if pid3_empty else "PID|1||M000123^^^^MR||^supartini|||Female"
    segs = [
        r"MSH|^~\&|||||20260901145257||ORU^R01|" + control_id + r"|P|2.3.1||||||UNICODE",
        pid,
        "PV1|1",
        f"OBR|1||{obr3}|00001^Automated Count^99MRC|||20260901145257|||||||||||||||||HM||||||||Administrator",
        "OBX|1|IS|08001^Take Mode^99MRC||O||||||F",
        "OBX|2|NM|6690-2^WBC^LN||7.50|10*3/uL|4.00-10.00|N|||F",
        "OBX|3|NM|718-7^HGB^LN||13.2|g/dL|11.0-16.0|N|||F",
    ]
    return "\r".join(segs).encode("utf-8")


# --- classifier unit level (deterministic, DB-free) -------------------

def test_bc5150_background_message_is_non_patient():
    parsed = parse_hl7_bc5150(bc5150_background_message().decode())
    assert parsed is not None
    assert parsed.order.specimen_no == "Background"  # parser keeps OBR-3 as data
    c = classify(parsed, resolve_policy("bc5150_field_verified"))
    assert c.message_class is MessageClass.NON_PATIENT
    assert c.classification_rule == "OBR3_BACKGROUND"


@pytest.mark.parametrize("obr3", ["Background", "background", "BACKGROUND", "  Background  ", "background\t"])
def test_bc5150_background_normalisation(obr3):
    parsed = parse_hl7_bc5150(bc5150_background_message(obr3=obr3).decode())
    c = classify(parsed, resolve_policy("bc5150_field_verified"))
    assert c.message_class is MessageClass.NON_PATIENT
    assert c.classification_rule == "OBR3_BACKGROUND"


def test_bc5150_second_background_capture_is_non_patient():
    # WBC 0.05 / RBC 0.00 / PLT 0 variant
    raw = "\r".join([
        r"MSH|^~\&|||||20260901151500||ORU^R01|BG2|P|2.3.1||||||UNICODE",
        "PID|1||||||||",
        r"OBR|1||Background|00001^Automated Count^99MRC|||20260901151500",
        "OBX|1|NM|6690-2^WBC^LN||0.05|10*3/uL|4.00-10.00|L|||F",
        "OBX|2|NM|789-8^RBC^LN||0.00|10*6/uL|3.50-5.50|L|||F",
        "OBX|3|NM|777-3^PLT^LN||0|10*3/uL|100-300|L|||F",
    ])
    c = classify(parse_hl7_bc5150(raw), resolve_policy("bc5150_field_verified"))
    assert c.message_class is MessageClass.NON_PATIENT


def test_bc5150_non_background_is_unclassified_not_patient_or_non_patient():
    # Real patient samples 30/31: the Background rule must not misfire on them,
    # but there is no field evidence to positively call them PATIENT_RESULT, so
    # the fail-closed outcome is UNCLASSIFIED.
    for obr3 in ("30", "31"):
        parsed = parse_hl7_bc5150(bc5150_patient_message(obr3=obr3).decode())
        c = classify(parsed, resolve_policy("bc5150_field_verified"))
        assert c.message_class is MessageClass.UNCLASSIFIED, obr3
        assert c.classification_rule == "BC5150_BACKGROUND_ONLY"
        assert c.message_class is not MessageClass.PATIENT_RESULT
        assert c.message_class is not MessageClass.NON_PATIENT


def test_bc5150_field_verified_never_emits_patient_result():
    # Structural fail-closed property: no non-"Background" input can become
    # PATIENT_RESULT merely by not matching "Background".
    samples = [
        bc5150_patient_message(obr3="30"),
        bc5150_patient_message(obr3="31", pid3_empty=True),
        bc5150_background_message(obr3="QC"),
        bc5150_background_message(obr3="Calibration"),
        bc5150_background_message(obr3="Control"),
        bc5150_background_message(obr3="Maintenance"),
        bc5150_background_message(obr3=""),
        bc5150_background_message(obr3="Backgroundish"),
    ]
    for raw in samples:
        c = classify(parse_hl7_bc5150(raw.decode()), resolve_policy("bc5150_field_verified"))
        assert c.message_class is not MessageClass.PATIENT_RESULT, raw


def test_bc5150_unverified_non_patient_categories_stay_unclassified():
    # QC / Calibration etc. are NOT "Background" and have no field evidence:
    # they must be UNCLASSIFIED, never NON_PATIENT (no formula invented) and
    # never PATIENT_RESULT.
    for obr3 in ("QC", "Calibration", "Maintenance", "Control"):
        c = classify(
            parse_hl7_bc5150(bc5150_background_message(obr3=obr3).decode()),
            resolve_policy("bc5150_field_verified"),
        )
        assert c.message_class is MessageClass.UNCLASSIFIED, obr3
        assert c.classification_rule == "BC5150_BACKGROUND_ONLY"


def test_bc5150_pid3_empty_alone_does_not_yield_non_patient():
    # OBR-3 = "30" but PID-3 completely empty -> not NON_PATIENT (PID-3 is not a
    # discriminator); fail-closed outcome is UNCLASSIFIED.
    parsed = parse_hl7_bc5150(bc5150_patient_message(obr3="30", pid3_empty=True).decode())
    assert parsed.patient.nomor_rm == ""  # PID-3 really is empty
    c = classify(parsed, resolve_policy("bc5150_field_verified"))
    assert c.message_class is not MessageClass.NON_PATIENT
    assert c.message_class is MessageClass.UNCLASSIFIED


def test_bc5150_zero_values_alone_do_not_yield_non_patient():
    # Near-zero numerics with OBR-3 = "31": values are not a discriminator, so
    # not NON_PATIENT; fail-closed outcome is UNCLASSIFIED.
    raw = "\r".join([
        r"MSH|^~\&|||||20260901145300||ORU^R01|P31|P|2.3.1||||||UNICODE",
        "PID|1||M000999^^^^MR||^lowcount|||Male",
        r"OBR|1||31|00001^Automated Count^99MRC|||20260901145300",
        "OBX|1|NM|6690-2^WBC^LN||0.06|10*3/uL|4.00-10.00|L|||F",
        "OBX|2|NM|777-3^PLT^LN||1|10*3/uL|100-300|L|||F",
    ])
    c = classify(parse_hl7_bc5150(raw), resolve_policy("bc5150_field_verified"))
    assert c.message_class is not MessageClass.NON_PATIENT
    assert c.message_class is MessageClass.UNCLASSIFIED


# --- full ingestion (PostgreSQL) -------------------------------------

def test_bc5150_background_full_ingestion_creates_no_clinical_rows(session, instrument_id):
    tr = run_message(bc5150_background_message(control_id="BG359"), instrument_id, classify_fn=BC5150)

    # raw message persisted with queryable classification metadata
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.raw_message.startswith("MSH")
    assert m.parse_status == "Success"
    assert m.message_class == "NON_PATIENT"
    assert m.classification_rule == "OBR3_BACKGROUND"

    # no clinical or synthetic-identity rows at all
    assert count(session, TestRun) == 0
    assert count(session, Result) == 0
    assert count(session, Patient) == 0
    assert count(session, Visit) == 0
    assert count(session, Order) == 0

    # normal ACK behaviour preserved (message received & stored)
    assert tr.acks == [("BG359", True, "")]


def test_bc5150_non_background_full_ingestion_is_unclassified_no_clinical_rows(session, instrument_id):
    # Under the field-verified policy, sample 30 is UNCLASSIFIED -> raw only.
    tr = run_message(bc5150_patient_message(control_id="P30", obr3="30"), instrument_id, classify_fn=BC5150)

    m = session.scalars(select(InstrumentMessage)).one()
    assert m.raw_message.startswith("MSH")
    assert m.parse_status == "Success"
    assert m.message_class == "UNCLASSIFIED"
    assert m.classification_rule == "BC5150_BACKGROUND_ONLY"

    assert count(session, TestRun) == 0
    assert count(session, Result) == 0
    assert count(session, Patient) == 0
    assert count(session, Visit) == 0
    assert count(session, Order) == 0
    assert tr.acks == [("P30", True, "")]


def test_bc5150_background_and_non_background_both_stay_out_of_clinical_tables(session, instrument_id):
    run_message(bc5150_background_message(control_id="BG"), instrument_id, classify_fn=BC5150)
    run_message(bc5150_patient_message(control_id="P31", obr3="31"), instrument_id, classify_fn=BC5150)

    assert count(session, TestRun) == 0
    assert count(session, Result) == 0
    classes = sorted(m.message_class for m in session.scalars(select(InstrumentMessage)).all())
    assert classes == ["NON_PATIENT", "UNCLASSIFIED"]


# --- M9.3: evidence state after BC-5150 field session 1 ---------------
#
# Session 1 (docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md §5.5) verified the
# Background rule live and produced the first patient/Background field
# comparison. It did NOT produce a QC, calibration, control or maintenance
# capture, so no positive PATIENT_RESULT rule is approved (§9.5).
#
# Two shapes below come from that session and are not represented by the
# older fixtures:
#   * PID-3 is the literal "^^^^MR" in BOTH patient and Background frames —
#     components empty, so it discriminates nothing.
#   * Background carries clinical-style NM values, including a masked HGB.
#
# The historical Comm. All corpus additionally contains 20 messages with an
# empty PID-5 and a numeric OBR-3. Those are NOT proven to be QC; they may be
# unlabelled patient specimens, control material, or another workflow. They
# must therefore stay UNCLASSIFIED.
#
# Patient names in these fixtures are pseudonymised tokens (§3 of the
# validation document), never real identifiers.


def bc5150_observed_patient_message(control_id="P42", obr3="42") -> bytes:
    """Session-1 patient shape: PID-3 '^^^^MR', PID-5 populated, IS metadata."""
    return "\r".join([
        r"MSH|^~\&|||||20260909141852||ORU^R01|" + control_id + r"|P|2.3.1||||||UNICODE",
        "PID|1||^^^^MR||^PT-01|||Female",
        f"OBR|1||{obr3}|00001^Automated Count^99MRC|||20230518195453|||||||||||||||||HM||||||||Administrator",
        "OBX|1|IS|08001^Take Mode^99MRC||O||||||F",
        "OBX|2|IS|08003^Test Mode^99MRC||CBC+DIFF||||||F",
        "OBX|3|NM|6690-2^WBC^LN||13.13|10*3/uL|4.00-10.00|H|||F",
        "OBX|4|NM|718-7^HGB^LN||11.6|g/dL|11.0-16.0|N|||F",
    ]).encode("utf-8")


def bc5150_unlabelled_numeric_message(control_id="U01", obr3="43") -> bytes:
    """The unidentified corpus shape: empty PID-5, numeric OBR-3, CBC payload.

    Ground truth is UNKNOWN — it may be an unlabelled patient specimen or
    non-patient material. It must not be classified either way.
    """
    return "\r".join([
        r"MSH|^~\&|||||20260909142000||ORU^R01|" + control_id + r"|P|2.3.1||||||UNICODE",
        "PID|1||^^^^MR",
        f"OBR|1||{obr3}|00001^Automated Count^99MRC|||20230518200000|||||||||||||||||HM",
        "OBX|1|IS|08001^Take Mode^99MRC||O||||||F",
        "OBX|2|NM|6690-2^WBC^LN||6.80|10*3/uL|4.00-10.00|N|||F",
        "OBX|3|NM|718-7^HGB^LN||12.9|g/dL|11.0-16.0|N|||F",
    ]).encode("utf-8")


def bc5150_observed_background_message(control_id="BG4") -> bytes:
    """Session-1 Background shape: no PID-5 field, masked HGB, no IS metadata."""
    return "\r".join([
        r"MSH|^~\&|||||20260909142344||ORU^R01|" + control_id + r"|P|2.3.1||||||UNICODE",
        "PID|1||^^^^MR",
        r"OBR|1||Background|00001^Automated Count^99MRC|||20230822094531|||||||||||||||||HM",
        "OBX|1|NM|6690-2^WBC^LN||0.05|10*3/uL|4.00-10.00|L|||F",
        "OBX|2|NM|789-8^RBC^LN||0.00|10*6/uL|3.50-5.50|L|||F",
        "OBX|3|ST|718-7^HGB^LN||*****|g/dL|11.0-16.0||||F",
        "OBX|4|NM|4544-3^HCT^LN||0.0|%|37.0-54.0|L|||F",
        "OBX|5|NM|777-3^PLT^LN||0|10*3/uL|100-300|L|||F",
    ]).encode("utf-8")


def test_bc5150_observed_pid3_shape_is_not_a_discriminator():
    # '^^^^MR' appears in BOTH categories and parses to an empty nomor_rm, so
    # only OBR-3 separates them.
    patient = parse_hl7_bc5150(bc5150_observed_patient_message().decode())
    background = parse_hl7_bc5150(bc5150_observed_background_message().decode())

    assert patient.patient.nomor_rm == ""
    assert background.patient.nomor_rm == ""

    assert classify(patient, resolve_policy("bc5150_field_verified")).message_class \
        is MessageClass.UNCLASSIFIED
    assert classify(background, resolve_policy("bc5150_field_verified")).message_class \
        is MessageClass.NON_PATIENT


def test_bc5150_named_patient_like_message_is_not_patient_result():
    # PID-5 populated + numeric OBR-3. No approved rule promotes this, so the
    # fail-closed outcome stands (§9.5: positive patient rule NOT APPROVED).
    parsed = parse_hl7_bc5150(bc5150_observed_patient_message().decode())
    assert parsed.patient.nama_lengkap == "PT-01"  # PID-5 really is populated
    assert parsed.order.specimen_no == "42"        # OBR-3 really is numeric

    c = classify(parsed, resolve_policy("bc5150_field_verified"))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.classification_rule == "BC5150_BACKGROUND_ONLY"
    assert c.message_class is not MessageClass.PATIENT_RESULT


@pytest.mark.parametrize("obr3", ["43", "1", "359", "1010"])
def test_bc5150_unlabelled_numeric_specimen_is_unclassified(obr3):
    # Empty PID-5 + numeric OBR-3: ground truth UNKNOWN. Must be neither
    # PATIENT_RESULT nor NON_PATIENT — emptiness of PID-5 must not imply QC.
    parsed = parse_hl7_bc5150(bc5150_unlabelled_numeric_message(obr3=obr3).decode())
    assert parsed.patient.nama_lengkap == "UNKNOWN"  # PID-5 absent -> sentinel
    assert parsed.results, "fixture must carry a clinical payload"

    c = classify(parsed, resolve_policy("bc5150_field_verified"))
    assert c.message_class is MessageClass.UNCLASSIFIED, obr3
    assert c.classification_rule == "BC5150_BACKGROUND_ONLY"
    assert c.message_class is not MessageClass.NON_PATIENT
    assert c.message_class is not MessageClass.PATIENT_RESULT


def test_bc5150_is_metadata_alone_does_not_yield_patient_result():
    # IS metadata (Take/Test Mode) is parsed but must not drive classification.
    parsed = parse_hl7_bc5150(bc5150_observed_patient_message().decode())
    assert len(parsed.is_metadata) == 2, "fixture must actually carry IS metadata"

    c = classify(parsed, resolve_policy("bc5150_field_verified"))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.message_class is not MessageClass.PATIENT_RESULT


def test_bc5150_background_clinical_style_obx_does_not_override_background():
    # Background emits accepted clinical values (WBC 0.05, RBC 0.00, PLT 0) and
    # a masked HGB. Presence of a clinical payload is not a patient signal.
    parsed = parse_hl7_bc5150(bc5150_observed_background_message().decode())
    values = {r.parameter_tes: r.nilai_hasil for r in parsed.results}
    assert values["WBC"] == "0.05" and values["RBC"] == "0.00" and values["HGB"] == "*****"
    assert not parsed.is_metadata, "session-1 Background carried no IS metadata"

    c = classify(parsed, resolve_policy("bc5150_field_verified"))
    assert c.message_class is MessageClass.NON_PATIENT
    assert c.classification_rule == "OBR3_BACKGROUND"


def test_bc5150_rule_tokens_are_stable_and_distinct():
    # The two BC-5150 tokens are part of the persisted contract
    # (instrument_messages.classification_rule) and must not drift.
    from app.integration.classification import (
        RULE_BC5150_BACKGROUND_ONLY,
        RULE_OBR3_BACKGROUND,
    )

    assert RULE_OBR3_BACKGROUND == "OBR3_BACKGROUND"
    assert RULE_BC5150_BACKGROUND_ONLY == "BC5150_BACKGROUND_ONLY"
    assert RULE_OBR3_BACKGROUND != RULE_BC5150_BACKGROUND_ONLY

    policy = resolve_policy("bc5150_field_verified")
    emitted = {
        classify(parse_hl7_bc5150(raw.decode()), policy).classification_rule
        for raw in (
            bc5150_observed_background_message(),
            bc5150_observed_patient_message(),
            bc5150_unlabelled_numeric_message(),
        )
    }
    assert emitted == {RULE_OBR3_BACKGROUND, RULE_BC5150_BACKGROUND_ONLY}


def test_bc5150_unlabelled_numeric_full_ingestion_creates_no_clinical_rows(session, instrument_id):
    # The decisive safety property for the unidentified corpus: raw audit row
    # only, positive ACK, and zero clinical or synthetic-identity rows.
    tr = run_message(bc5150_unlabelled_numeric_message(control_id="U01"), instrument_id,
                     classify_fn=BC5150)

    m = session.scalars(select(InstrumentMessage)).one()
    assert m.parse_status == "Success"
    assert m.message_class == "UNCLASSIFIED"
    assert m.classification_rule == "BC5150_BACKGROUND_ONLY"

    assert count(session, TestRun) == 0
    assert count(session, Result) == 0
    assert count(session, Patient) == 0
    assert count(session, Visit) == 0
    assert count(session, Order) == 0
    assert tr.acks == [("U01", True, "")]


def test_bc5150_observed_session1_shapes_stay_out_of_clinical_tables(session, instrument_id):
    # All three session-1 shapes together: only the Background one is classified.
    run_message(bc5150_observed_background_message(control_id="BG4"), instrument_id, classify_fn=BC5150)
    run_message(bc5150_observed_patient_message(control_id="P42"), instrument_id, classify_fn=BC5150)
    run_message(bc5150_unlabelled_numeric_message(control_id="U01"), instrument_id, classify_fn=BC5150)

    assert count(session, TestRun) == 0
    assert count(session, Result) == 0
    assert count(session, Patient) == 0
    assert count(session, Visit) == 0
    assert count(session, Order) == 0

    classes = sorted(m.message_class for m in session.scalars(select(InstrumentMessage)).all())
    assert classes == ["NON_PATIENT", "UNCLASSIFIED", "UNCLASSIFIED"]


def test_bc5150_patient_ingestion_remains_available_as_separate_explicit_decision(session, instrument_id):
    # The clinical path is preserved, but as an explicit owner decision
    # (`unverified_passthrough`) — it is NOT hidden inside bc5150_field_verified.
    tr = run_message(bc5150_patient_message(control_id="P30", obr3="30"), instrument_id, classify_fn=PASSTHROUGH)

    run = session.scalars(select(TestRun)).one()
    assert (run.run_sequence, run.is_final, run.delivery_status) == (1, False, "pending")
    results = session.scalars(select(Result).order_by(Result.id_hasil)).all()
    assert [(r.parameter_tes, r.nilai_hasil) for r in results] == [("WBC", "7.50"), ("HGB", "13.2")]
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.message_class == "PATIENT_RESULT"
    assert m.classification_rule == "unverified_passthrough"
    assert tr.acks == [("P30", True, "")]


# --- configuration wiring -------------------------------------------

def test_bc5150_field_verified_policy_is_selectable_and_documented():
    from app.core.config import BACKEND_DIR, load_instrument_configs

    assert resolve_policy("bc5150_field_verified") is not None
    cfgs = load_instrument_configs(BACKEND_DIR / "instruments.example.json")
    bc5150 = next(c for c in cfgs if c.instrument_name == "Mindray BC-5150")
    assert bc5150.classification_policy == "bc5150_field_verified"


# =====================================================================
# G. bc5150_name_passthrough  —  owner-approved HIGH-RISK name passthrough
#
# NOT an evidence rule (docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md §9.5 still
# records that a positive *evidence* rule is NOT APPROVED). This is an explicit
# risk-accepted operational policy so observed named patient runs reach the
# clinical pipeline. Behaviour:
#     OBR-3 == "Background"           -> NON_PATIENT   / OBR3_BACKGROUND
#     non-Background + real PID-5     -> PATIENT_RESULT / BC5150_NAME_PASSTHROUGH
#     non-Background + ""/"UNKNOWN"   -> UNCLASSIFIED  / BC5150_NAME_ABSENT
# =====================================================================

def _named_bc5150(control_id="N1", obr3="42", pid5="^supartini", with_obx=True) -> bytes:
    segs = [
        r"MSH|^~\&|||||20260909142000||ORU^R01|" + control_id + r"|P|2.3.1||||||UNICODE",
        f"PID|1||^^^^MR||{pid5}|||Female",
        f"OBR|1||{obr3}|00001^Automated Count^99MRC|||20230518200000|||||||||||||||||HM",
    ]
    if with_obx:
        segs.append("OBX|1|NM|6690-2^WBC^LN||6.80|10*3/uL|4.00-10.00|N|||F")
        segs.append("OBX|2|NM|718-7^HGB^LN||12.9|g/dL|11.0-16.0|N|||F")
    return "\r".join(segs).encode("utf-8")


# --- classifier unit level ------------------------------------------

def test_name_passthrough_background_is_non_patient_even_with_clinical_obx():
    # (req 1) Background wins over everything: name populated + clinical OBX.
    parsed = parse_hl7_bc5150(_named_bc5150(obr3="Background").decode())
    assert parsed.patient.nama_lengkap == "supartini"
    assert parsed.results, "fixture carries a clinical-looking payload"

    c = classify(parsed, resolve_policy("bc5150_name_passthrough"))
    assert c.message_class is MessageClass.NON_PATIENT
    assert c.classification_rule == "OBR3_BACKGROUND"


@pytest.mark.parametrize("obr3", ["Background", "background", "  BACKGROUND  ", "background\t"])
def test_name_passthrough_background_normalisation(obr3):
    c = classify(
        parse_hl7_bc5150(_named_bc5150(obr3=obr3).decode()),
        resolve_policy("bc5150_name_passthrough"),
    )
    assert c.message_class is MessageClass.NON_PATIENT
    assert c.classification_rule == "OBR3_BACKGROUND"


@pytest.mark.parametrize("obr3", ["42", "1", "359", "1010"])
def test_name_passthrough_named_non_background_is_patient_result(obr3):
    # (req 2, 8) The one high-risk promotion, and its exact provenance token.
    parsed = parse_hl7_bc5150(_named_bc5150(obr3=obr3, pid5="^supartini").decode())
    assert parsed.patient.nama_lengkap == "supartini"
    assert parsed.order.specimen_no == obr3

    c = classify(parsed, resolve_policy("bc5150_name_passthrough"))
    assert c.message_class is MessageClass.PATIENT_RESULT, obr3
    assert c.classification_rule == "BC5150_NAME_PASSTHROUGH"


def test_name_passthrough_empty_pid5_is_unclassified():
    # (req 3) PID-5 absent -> parser sentinel "UNKNOWN" -> UNCLASSIFIED.
    parsed = parse_hl7_bc5150(_named_bc5150(obr3="42", pid5="").decode())
    assert parsed.patient.nama_lengkap == "UNKNOWN"

    c = classify(parsed, resolve_policy("bc5150_name_passthrough"))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.classification_rule == "BC5150_NAME_ABSENT"
    assert c.message_class is not MessageClass.PATIENT_RESULT
    assert c.message_class is not MessageClass.NON_PATIENT


@pytest.mark.parametrize("pid5", ["^UNKNOWN", "^unknown", "^UnKnOwN", "UNKNOWN^^^^"])
def test_name_passthrough_literal_unknown_is_unclassified(pid5):
    # (req 4, 6) The literal sentinel in any case is excluded, not promoted.
    parsed = parse_hl7_bc5150(_named_bc5150(obr3="42", pid5=pid5).decode())
    c = classify(parsed, resolve_policy("bc5150_name_passthrough"))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.classification_rule == "BC5150_NAME_ABSENT"


@pytest.mark.parametrize("pid5", ["   ", "^   ^", " ^ ^ "])
def test_name_passthrough_whitespace_only_pid5_is_unclassified(pid5):
    # (req 5) Whitespace-only PID-5 collapses to the sentinel.
    parsed = parse_hl7_bc5150(_named_bc5150(obr3="42", pid5=pid5).decode())
    assert parsed.patient.nama_lengkap == "UNKNOWN"
    c = classify(parsed, resolve_policy("bc5150_name_passthrough"))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.classification_rule == "BC5150_NAME_ABSENT"


def test_name_passthrough_preserves_the_parsed_patient_name():
    # (req 6) Surrounding whitespace on PID-5 does not block promotion, and the
    # stored/parsed name is the parser's value, never rewritten by the policy.
    parsed = parse_hl7_bc5150(_named_bc5150(obr3="42", pid5="^  Supartini  ").decode())
    assert parsed.patient.nama_lengkap == "Supartini"  # parser trims components
    c = classify(parsed, resolve_policy("bc5150_name_passthrough"))
    assert c.message_class is MessageClass.PATIENT_RESULT
    assert parsed.patient.nama_lengkap == "Supartini"  # unchanged by classify()


def test_name_passthrough_numeric_obr3_without_name_stays_unclassified():
    # (req 9) No hidden fallback: numeric OBR-3 alone does not promote.
    parsed = parse_hl7_bc5150(bc5150_unlabelled_numeric_message(obr3="43").decode())
    assert parsed.patient.nama_lengkap == "UNKNOWN"
    c = classify(parsed, resolve_policy("bc5150_name_passthrough"))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.classification_rule == "BC5150_NAME_ABSENT"


def test_name_passthrough_clinical_obx_without_name_stays_unclassified():
    # (req 9) Presence of a clinical payload is not a patient signal.
    parsed = parse_hl7_bc5150(_named_bc5150(obr3="42", pid5="", with_obx=True).decode())
    assert parsed.patient.nama_lengkap == "UNKNOWN"
    assert parsed.results, "fixture carries a clinical payload"
    c = classify(parsed, resolve_policy("bc5150_name_passthrough"))
    assert c.message_class is MessageClass.UNCLASSIFIED
    assert c.message_class is not MessageClass.PATIENT_RESULT


def test_name_passthrough_rule_tokens_are_stable_and_distinct():
    from app.integration.classification import (
        RULE_BC5150_NAME_ABSENT,
        RULE_BC5150_NAME_PASSTHROUGH,
        RULE_OBR3_BACKGROUND,
    )

    assert RULE_BC5150_NAME_PASSTHROUGH == "BC5150_NAME_PASSTHROUGH"
    assert RULE_BC5150_NAME_ABSENT == "BC5150_NAME_ABSENT"
    assert len({RULE_BC5150_NAME_PASSTHROUGH, RULE_BC5150_NAME_ABSENT,
                RULE_OBR3_BACKGROUND, "BC5150_BACKGROUND_ONLY"}) == 4

    policy = resolve_policy("bc5150_name_passthrough")
    emitted = {
        classify(parse_hl7_bc5150(raw.decode()), policy).classification_rule
        for raw in (
            _named_bc5150(obr3="Background"),
            _named_bc5150(obr3="42", pid5="^supartini"),
            _named_bc5150(obr3="42", pid5=""),
        )
    }
    assert emitted == {RULE_OBR3_BACKGROUND, RULE_BC5150_NAME_PASSTHROUGH, RULE_BC5150_NAME_ABSENT}


# --- full ingestion (PostgreSQL) -----------------------------------

def test_name_passthrough_named_message_persists_full_clinical_hierarchy(session, instrument_id):
    # (req 2) The high-risk promotion drives the EXISTING pipeline: Visit ->
    # Order -> TestRun -> Result, unchanged. classification_rule is persisted.
    tr = run_message(
        bc5150_patient_message(control_id="NP1", obr3="30"), instrument_id,
        classify_fn=BC5150_NAME,
    )

    m = session.scalars(select(InstrumentMessage)).one()
    assert m.parse_status == "Success"
    assert m.message_class == "PATIENT_RESULT"
    assert m.classification_rule == "BC5150_NAME_PASSTHROUGH"

    run = session.scalars(select(TestRun)).one()
    assert (run.run_sequence, run.is_final, run.delivery_status) == (1, False, "pending")
    assert run.id_instrument == instrument_id and run.id_message == m.id_message

    results = session.scalars(select(Result).order_by(Result.id_hasil)).all()
    assert [(r.parameter_tes, r.nilai_hasil) for r in results] == [("WBC", "7.50"), ("HGB", "13.2")]

    patient = session.scalars(select(Patient)).one()
    assert patient.nama_lengkap == "supartini"  # PID-5 value stored verbatim
    assert count(session, Visit) == 1 and count(session, Order) == 1
    assert tr.acks == [("NP1", True, "")]


def test_name_passthrough_background_full_ingestion_creates_no_clinical_rows(session, instrument_id):
    # (req 1) Background stays raw-only even under this policy.
    tr = run_message(
        _named_bc5150(control_id="NP_BG", obr3="Background"), instrument_id,
        classify_fn=BC5150_NAME,
    )
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.parse_status == "Success"
    assert m.message_class == "NON_PATIENT"
    assert m.classification_rule == "OBR3_BACKGROUND"
    assert count(session, TestRun) == count(session, Result) == 0
    assert count(session, Patient) == count(session, Visit) == count(session, Order) == 0
    assert tr.acks == [("NP_BG", True, "")]


def test_name_passthrough_unnamed_full_ingestion_creates_no_clinical_rows(session, instrument_id):
    # (req 3, 9) Unnamed non-Background stays raw-only: fail-closed gate intact.
    tr = run_message(
        bc5150_unlabelled_numeric_message(control_id="NP_U", obr3="43"), instrument_id,
        classify_fn=BC5150_NAME,
    )
    m = session.scalars(select(InstrumentMessage)).one()
    assert m.parse_status == "Success"
    assert m.message_class == "UNCLASSIFIED"
    assert m.classification_rule == "BC5150_NAME_ABSENT"
    assert count(session, TestRun) == count(session, Result) == 0
    assert count(session, Patient) == count(session, Visit) == count(session, Order) == 0
    assert tr.acks == [("NP_U", True, "")]


# --- regression: other policies / instruments unchanged -------------

def test_name_passthrough_does_not_change_strict_or_field_verified():
    # (req 7) Same named non-Background message under the other policies is still
    # fail-closed. Only bc5150_name_passthrough promotes it.
    parsed = parse_hl7_bc5150(_named_bc5150(obr3="42", pid5="^supartini").decode())

    assert classify(parsed, resolve_policy("strict")).message_class is MessageClass.UNCLASSIFIED
    fv = classify(parsed, resolve_policy("bc5150_field_verified"))
    assert fv.message_class is MessageClass.UNCLASSIFIED
    assert fv.classification_rule == "BC5150_BACKGROUND_ONLY"
    assert classify(parsed, resolve_policy("bc5150_name_passthrough")).message_class \
        is MessageClass.PATIENT_RESULT


def test_name_passthrough_only_this_policy_emits_patient_result_from_a_named_message():
    # (req 8) Structural: across every registered policy, PATIENT_RESULT for this
    # named non-Background BC-5150 message comes only from the explicit passthrough
    # policies, and the field-verified evidence policy never does.
    from app.integration.classification import KNOWN_POLICIES

    parsed = parse_hl7_bc5150(_named_bc5150(obr3="42", pid5="^supartini").decode())
    emitting = {
        name for name in KNOWN_POLICIES
        if classify(parsed, resolve_policy(name)).message_class is MessageClass.PATIENT_RESULT
    }
    assert emitting == {"bc5150_name_passthrough", "unverified_passthrough"}
    assert "bc5150_field_verified" not in emitting


def test_name_passthrough_is_selectable_and_wired_from_instrument_config(tmp_path):
    # (req 7 / provenance) A config selecting the new policy resolves to it, and
    # the token it emits for a promoted message is exactly BC5150_NAME_PASSTHROUGH.
    import json

    from app.core.config import load_instrument_configs
    from app.integration.classification import _bc5150_name_passthrough

    path = tmp_path / "instruments.json"
    path.write_text(json.dumps({"instruments": [{
        "key": "mindray_bc5150", "instrument_name": "Mindray BC-5150",
        "host": "127.0.0.1", "port": 5100, "mode": "client",
        "parser_key": "bc5150_hl7", "identity_prefix": "BC5150-", "enabled": True,
        "classification_policy": "bc5150_name_passthrough",
    }]}), encoding="utf-8")

    cfg = load_instrument_configs(path)[0]
    assert cfg.classification_policy == "bc5150_name_passthrough"
    assert resolve_policy(cfg.classification_policy) is _bc5150_name_passthrough
