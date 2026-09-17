"""XN-550 Phase 2 — T2 classification of persisted raw messages against PostgreSQL.

PostgreSQL-only, against ``lis_marina_permata_test`` (never the stable PoC or DEV
database), following ``tests/test_ingestion.py``'s schema fixture. Every test
also proves that no clinical row and no audit row is created.
"""
from __future__ import annotations

import datetime
import hashlib
import pathlib
import socket
import threading
import time

import pytest
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import sessionmaker

from app.integration import listener as listener_module
from app.integration.astm.assembler import CompleteMessage, Fragment
from app.integration.classification import Classification, MessageClass
from app.integration.listener import ListenerTransport
from app.integration.parsers.xn550_astm import (
    PARSER_KEY,
    PARSER_VERSION,
    classify_xn550,
    parse_xn550_astm,
)
from app.integration.raw_capture import SessionContext, SqlRawCaptureStore
from app.integration.xn550_ingestion import Xn550ClassificationStage
from app.models import (
    AuditEvent,
    Instrument,
    InstrumentMessage,
    Order,
    Patient,
    Result,
    TestRun as ClinicalRun,  # aliased so pytest does not try to collect it
    Visit,
)
from app.models.base import Base

PG_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(PG_URL)
SessionTest = sessionmaker(bind=engine, autoflush=False, autocommit=False)
assert engine.url.database == "lis_marina_permata_test"

FIXTURE = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"
)
T0 = datetime.datetime(2026, 9, 17, 10, 0, 0)
SENTINEL = "SYNTH-SENTINEL-9C1E"


@pytest.fixture(scope="module")
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def clinical_and_audit_counts() -> dict:
    with SessionTest() as s:
        return {
            model.__tablename__: s.scalar(select(func.count()).select_from(model))
            for model in (Patient, Visit, Order, ClinicalRun, Result, AuditEvent)
        }


ZERO = {"patients": 0, "visits": 0, "orders": 0, "test_runs": 0, "results": 0, "audit_events": 0}


@pytest.fixture(autouse=True)
def _clean(_schema):
    with SessionTest() as s:
        for table in reversed(Base.metadata.sorted_tables):
            s.execute(table.delete())
        s.commit()
    yield
    assert clinical_and_audit_counts() == ZERO, "XN-550 classification must never create clinical or audit rows"


@pytest.fixture
def instrument_id() -> int:
    with SessionTest() as s:
        inst = Instrument(nama_mesin="Sysmex XN-550")
        s.add(inst)
        s.commit()
        return inst.id_instrument


@pytest.fixture
def store() -> SqlRawCaptureStore:
    return SqlRawCaptureStore(SessionTest)


def make_stage(parser=parse_xn550_astm, policy=classify_xn550) -> Xn550ClassificationStage:
    return Xn550ClassificationStage(
        session_factory=SessionTest, parser=parser, policy=policy,
        parser_key=PARSER_KEY, parser_version=PARSER_VERSION,
    )


def persist_raw(store, instrument_id, raw: bytes, start: int = 0) -> int:
    id_session = store.open_session(
        SessionContext(
            id_instrument=instrument_id, transport_mode="listener", local_address="127.0.0.1",
            local_port=5001, peer_address="127.0.0.1", peer_port=49671,
            ack_policy="ack_per_read_on_receive", opened_at=T0,
        )
    )
    event = CompleteMessage(
        raw=raw, offset_start=start, offset_end=start + len(raw), first_byte_at=T0,
        last_byte_at=T0, read_count=1, byte_class_token=None,
    )
    return store.persist_event(instrument_id, id_session, 1, event)


def row(id_message: int) -> InstrumentMessage:
    with SessionTest() as s:
        return s.get(InstrumentMessage, id_message)


def fixture_with_o3(value: str) -> bytes:
    records = FIXTURE.read_bytes().decode("ascii").split("\r")[:-1]
    fields = records[3].split("|")
    fields[2] = value
    records[3] = "|".join(fields)
    return ("\r".join(records) + "\r").encode("ascii")


# --------------------------------------------------------------------------- #
# Outcomes written back to the raw row
# --------------------------------------------------------------------------- #


def test_conformant_raw_row_is_classified_in_place(store, instrument_id):
    raw = FIXTURE.read_bytes()
    id_message = persist_raw(store, instrument_id, raw)
    before = row(id_message)

    assert make_stage().process(id_message) == "XN550_ENVELOPE_CONFORMANT"

    after = row(id_message)
    assert (after.parse_status, after.message_class) == ("Success", "UNCLASSIFIED")
    assert after.classification_rule == "XN550_ENVELOPE_CONFORMANT"
    assert after.error_detail is None
    assert (after.parser_key, after.parser_version) == ("xn550_astm_e1394", PARSER_VERSION)
    assert bytes(after.raw_bytes) == raw == bytes(before.raw_bytes)
    assert after.raw_sha256 == before.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert after.raw_message == before.raw_message
    assert after.duplicate_of_message_id is None
    assert after.message_class != MessageClass.PATIENT_RESULT.value


def test_structural_deviation_is_unclassified_with_token_only_detail(store, instrument_id):
    id_message = persist_raw(store, instrument_id, fixture_with_o3(SENTINEL))
    assert make_stage().process(id_message) == "XN550_DEV_O3_POPULATED"
    r = row(id_message)
    assert (r.parse_status, r.message_class, r.classification_rule) == ("Success", "UNCLASSIFIED", "XN550_DEV_O3_POPULATED")
    assert r.error_detail == "XN550_DEV_O3_POPULATED @record 3 field 3"
    assert SENTINEL not in r.error_detail


def test_unparseable_complete_message_is_failed(store, instrument_id):
    raw = FIXTURE.read_bytes().replace(b"C|1||\r", b"C|1||\r\r", 1)
    id_message = persist_raw(store, instrument_id, raw)
    assert make_stage().process(id_message) == "XN550_EMPTY_RECORD"
    r = row(id_message)
    assert (r.parse_status, r.message_class, r.classification_rule) == ("Failed", "UNPARSEABLE", "XN550_EMPTY_RECORD")
    assert r.error_detail == "XN550_EMPTY_RECORD @record 3"
    assert bytes(r.raw_bytes) == raw


def test_parser_reads_raw_bytes_not_raw_message(store, instrument_id):
    id_message = persist_raw(store, instrument_id, FIXTURE.read_bytes())
    with SessionTest() as s:
        s.execute(update(InstrumentMessage).where(InstrumentMessage.id_message == id_message).values(raw_message="garbage"))
        s.commit()
    assert make_stage().process(id_message) == "XN550_ENVELOPE_CONFORMANT"


def test_raw_integrity_mismatch_fails_closed(store, instrument_id):
    id_message = persist_raw(store, instrument_id, FIXTURE.read_bytes())
    with SessionTest() as s:
        s.execute(
            update(InstrumentMessage)
            .where(InstrumentMessage.id_message == id_message)
            .values(raw_sha256="0" * 64)
        )
        s.commit()
    assert make_stage().process(id_message) == "XN550_RAW_INTEGRITY_MISMATCH"
    r = row(id_message)
    assert (r.parse_status, r.message_class, r.error_detail) == ("Failed", "UNPARSEABLE", "XN550_RAW_INTEGRITY_MISMATCH")


def test_processing_is_idempotent_and_skips_non_pending_rows(store, instrument_id):
    id_message = persist_raw(store, instrument_id, FIXTURE.read_bytes())
    stage = make_stage()
    assert stage.process(id_message) == "XN550_ENVELOPE_CONFORMANT"
    assert stage.process(id_message) is None

    id_session = store.open_session(
        SessionContext(instrument_id, "listener", "127.0.0.1", 5001, "127.0.0.1", 1, "ack_per_read_on_receive", T0)
    )
    fragment_id = store.persist_event(
        instrument_id, id_session, 1,
        Fragment(b"H|\\^&", 0, 5, T0, T0, 1, "XN550_FRAGMENT_INCOMPLETE_AT_CLOSE"),
    )
    assert stage.process(fragment_id) is None
    assert row(fragment_id).classification_rule == "XN550_FRAGMENT_INCOMPLETE_AT_CLOSE"

    with SessionTest() as s:
        mllp = InstrumentMessage(id_instrument=instrument_id, raw_message="MSH|^~\\&|", parse_status="Pending")
        s.add(mllp)
        s.commit()
        mllp_id = mllp.id_message
    assert stage.process(mllp_id) is None
    assert row(mllp_id).message_class is None
    assert stage.process(987654) is None


# --------------------------------------------------------------------------- #
# Failure paths
# --------------------------------------------------------------------------- #


def test_parser_exception_records_t2_exception_without_payload(store, instrument_id):
    def exploding_parser(raw):
        raise RuntimeError(f"boom {SENTINEL} {raw[:20]!r}")

    id_message = persist_raw(store, instrument_id, FIXTURE.read_bytes())
    assert make_stage(parser=exploding_parser).process(id_message) == "XN550_T2_EXCEPTION"
    r = row(id_message)
    assert (r.parse_status, r.message_class, r.classification_rule) == ("Failed", "UNPARSEABLE", "XN550_T2_EXCEPTION")
    assert r.error_detail == "XN550_T2_EXCEPTION"
    assert bytes(r.raw_bytes) == FIXTURE.read_bytes()


def test_a_policy_that_returns_patient_result_is_refused(store, instrument_id):
    def rogue_policy(result):
        return Classification(MessageClass.PATIENT_RESULT, "ROGUE")

    id_message = persist_raw(store, instrument_id, FIXTURE.read_bytes())
    assert make_stage(policy=rogue_policy).process(id_message) == "XN550_T2_EXCEPTION"
    r = row(id_message)
    assert r.message_class == "UNPARSEABLE" and r.classification_rule == "XN550_T2_EXCEPTION"
    with SessionTest() as s:
        assert s.scalar(
            select(func.count()).select_from(InstrumentMessage).where(InstrumentMessage.message_class == "PATIENT_RESULT")
        ) == 0


def test_pending_rows_are_processed_in_id_order(store, instrument_id):
    first = persist_raw(store, instrument_id, FIXTURE.read_bytes())
    second = persist_raw(store, instrument_id, fixture_with_o3("X"))
    done = persist_raw(store, instrument_id, FIXTURE.read_bytes())
    stage = make_stage()
    stage.process(done)
    order: list[int] = []
    original = stage.process

    def spy(id_message):
        order.append(id_message)
        return original(id_message)

    stage.process = spy
    assert stage.process_pending(instrument_id) == 2
    assert order == [first, second]
    assert row(first).classification_rule == "XN550_ENVELOPE_CONFORMANT"
    assert row(second).classification_rule == "XN550_DEV_O3_POPULATED"


# --------------------------------------------------------------------------- #
# End to end: listener -> T1 -> T2 classification (G1 raw_only)
# --------------------------------------------------------------------------- #


def test_end_to_end_listener_classifies_raw_messages_and_nothing_else(store, instrument_id, monkeypatch):
    monkeypatch.setattr(listener_module, "READ_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(listener_module, "ACCEPT_TIMEOUT_SECONDS", 0.05)
    left_pending = persist_raw(store, instrument_id, FIXTURE.read_bytes(), start=0)  # crash between T1 and T2
    stage = make_stage()
    fixture = FIXTURE.read_bytes()
    deviation = fixture_with_o3("X")

    transport = ListenerTransport(
        id_instrument=instrument_id, instrument_key="sysmex_xn550_e2e", bind_host="127.0.0.1",
        bind_port=0, allowed_peers=("127.0.0.1",), ack_policy="ack_per_read_on_receive",
        store=store, status_writer=lambda i, s: None,
        on_raw_committed=stage.process,
        on_serve_start=lambda: stage.process_pending(instrument_id),
    )
    thread = threading.Thread(target=transport.serve_forever, daemon=True)
    thread.start()
    try:
        assert transport.wait_until_bound(5)
        client = socket.create_connection(("127.0.0.1", transport.bound_port), timeout=5)
        client.sendall(fixture[:1000])
        time.sleep(0.2)
        client.sendall(fixture[1000:] + deviation)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with SessionTest() as s:
                pending = s.scalar(
                    select(func.count()).select_from(InstrumentMessage).where(InstrumentMessage.parse_status == "Pending")
                )
                total = s.scalar(select(func.count()).select_from(InstrumentMessage))
            if total == 3 and pending == 0:
                break
            time.sleep(0.05)
        client.close()
    finally:
        transport.stop()
        thread.join(10)
    assert not thread.is_alive()

    with SessionTest() as s:
        rows = s.scalars(select(InstrumentMessage).order_by(InstrumentMessage.id_message)).all()
    assert [r.id_message for r in rows][0] == left_pending
    assert [r.classification_rule for r in rows] == [
        "XN550_ENVELOPE_CONFORMANT", "XN550_ENVELOPE_CONFORMANT", "XN550_DEV_O3_POPULATED",
    ]
    assert [bytes(r.raw_bytes) for r in rows[1:]] == [fixture, deviation]
    assert all(r.message_class == "UNCLASSIFIED" and r.parse_status == "Success" for r in rows)
    assert all(r.raw_sha256 == hashlib.sha256(bytes(r.raw_bytes)).hexdigest() for r in rows)
