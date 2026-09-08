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
    Result,
    TestRun,
)
from app.models.base import Base

PG_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(PG_URL)
SessionTest = sessionmaker(bind=engine, autoflush=False, autocommit=False)

STRICT = lambda parsed: classify(parsed, resolve_policy("strict"))
PASSTHROUGH = lambda parsed: classify(parsed, resolve_policy("unverified_passthrough"))


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
