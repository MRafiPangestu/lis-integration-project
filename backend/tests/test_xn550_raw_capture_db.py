"""XN-550 Phase 1 — T1 raw capture persistence (contract §9) against PostgreSQL.

PostgreSQL-only, against ``lis_marina_permata_test`` (never the stable PoC or
DEV database), following ``tests/test_ingestion.py``'s schema fixture. Includes
one end-to-end run: real loopback listener -> real store -> real rows.
"""
from __future__ import annotations

import datetime
import hashlib
import pathlib
import socket
import threading
import time

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.integration import listener as listener_module
from app.integration.astm.assembler import (
    FRAGMENT_INCOMPLETE_AT_CLOSE,
    TOKEN_E1381_OR_CONTROL_BYTE,
    CompleteMessage,
    Fragment,
)
from app.integration.listener import ACK_BYTE, ListenerTransport
from app.integration.raw_capture import (
    CLOSE_PEER_CLOSED,
    CLOSE_RECOVERED_AT_STARTUP,
    SessionContext,
    SessionCounters,
    SqlRawCaptureStore,
)
from app.models import (
    AuditEvent,
    Instrument,
    InstrumentMessage,
    InstrumentSession,
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
def store() -> SqlRawCaptureStore:
    return SqlRawCaptureStore(SessionTest)


@pytest.fixture
def instrument_id() -> int:
    with SessionTest() as s:
        inst = Instrument(nama_mesin="Sysmex XN-550")
        s.add(inst)
        s.commit()
        return inst.id_instrument


def ctx(id_instrument: int, opened_at=T0) -> SessionContext:
    return SessionContext(
        id_instrument=id_instrument,
        transport_mode="listener",
        local_address="127.0.0.1",
        local_port=5001,
        peer_address="127.0.0.1",
        peer_port=49671,
        ack_policy="ack_per_read_on_receive",
        opened_at=opened_at,
    )


def complete(raw: bytes, start: int = 0, token=None) -> CompleteMessage:
    return CompleteMessage(
        raw=raw, offset_start=start, offset_end=start + len(raw),
        first_byte_at=T0, last_byte_at=T0 + datetime.timedelta(milliseconds=40),
        read_count=2, byte_class_token=token,
    )


def clinical_and_audit_counts() -> dict:
    with SessionTest() as s:
        return {
            model.__tablename__: s.scalar(select(func.count()).select_from(model))
            for model in (Patient, Visit, Order, ClinicalRun, Result, AuditEvent)
        }


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #


def test_session_open_and_close_round_trip(store, instrument_id):
    id_session = store.open_session(ctx(instrument_id))
    closed_at = T0 + datetime.timedelta(minutes=5)
    counters = SessionCounters(bytes_received=2824, reads_count=2, acks_sent=2, messages_completed=1)
    store.close_session(id_session, CLOSE_PEER_CLOSED, counters, closed_at)
    with SessionTest() as s:
        row = s.get(InstrumentSession, id_session)
        assert (row.transport_mode, row.local_port, row.peer_port) == ("listener", 5001, 49671)
        assert row.ack_policy == "ack_per_read_on_receive"
        assert (row.opened_at, row.closed_at, row.close_reason) == (T0, closed_at, CLOSE_PEER_CLOSED)
        assert (row.bytes_received, row.reads_count, row.acks_sent) == (2824, 2, 2)
        assert (row.messages_completed, row.fragments_count) == (1, 0)


def test_orphan_sessions_are_closed_at_startup(store, instrument_id):
    open_id = store.open_session(ctx(instrument_id))
    done_id = store.open_session(ctx(instrument_id))
    store.close_session(done_id, CLOSE_PEER_CLOSED, SessionCounters(), T0)
    later = T0 + datetime.timedelta(hours=1)
    assert store.close_orphan_sessions(instrument_id, later) == 1
    with SessionTest() as s:
        assert s.get(InstrumentSession, open_id).close_reason == CLOSE_RECOVERED_AT_STARTUP
        assert s.get(InstrumentSession, open_id).closed_at == later
        assert s.get(InstrumentSession, done_id).close_reason == CLOSE_PEER_CLOSED
    assert store.close_orphan_sessions(instrument_id, later) == 0


def test_health_check(store):
    assert store.health_check() is True


# --------------------------------------------------------------------------- #
# Raw messages
# --------------------------------------------------------------------------- #


def test_complete_message_is_stored_exactly_and_left_pending(store, instrument_id):
    raw = FIXTURE.read_bytes()
    id_session = store.open_session(ctx(instrument_id))
    id_message = store.persist_event(instrument_id, id_session, 1, complete(raw, start=10))
    with SessionTest() as s:
        row = s.get(InstrumentMessage, id_message)
        assert bytes(row.raw_bytes) == raw
        assert row.raw_sha256 == hashlib.sha256(bytes(row.raw_bytes)).hexdigest()
        assert row.raw_sha256 == "2fcc8f38de8d6903595b5e876e00de352ace7005b805739486a22106ce543ad3"
        assert row.raw_length == len(raw) == 2824
        assert (row.id_session, row.session_message_index) == (id_session, 1)
        assert (row.stream_offset_start, row.stream_offset_end) == (10, 10 + len(raw))
        assert row.first_byte_at == T0
        assert row.received_at == T0 + datetime.timedelta(milliseconds=40)
        assert row.read_count == 2
        assert row.framing == "ASTM_CR_RECORDS"
        assert row.parse_status == "Pending"
        assert row.message_class is None and row.classification_rule is None
        assert row.error_detail is None
        assert row.parser_key is None and row.parser_version is None
        assert row.duplicate_of_message_id is None
        assert row.raw_message == raw.decode("ascii")


def test_fragment_is_stored_as_unparseable_with_its_token(store, instrument_id):
    id_session = store.open_session(ctx(instrument_id))
    fragment = Fragment(
        raw=b"H|\\^&|||SYN", offset_start=0, offset_end=11, first_byte_at=T0,
        last_byte_at=T0, read_count=1, reason=FRAGMENT_INCOMPLETE_AT_CLOSE,
    )
    id_message = store.persist_event(instrument_id, id_session, 1, fragment)
    with SessionTest() as s:
        row = s.get(InstrumentMessage, id_message)
        assert bytes(row.raw_bytes) == b"H|\\^&|||SYN"
        assert (row.parse_status, row.message_class) == ("Failed", "UNPARSEABLE")
        assert row.classification_rule == row.error_detail == FRAGMENT_INCOMPLETE_AT_CLOSE


def test_control_and_nul_bytes_are_preserved_in_raw_bytes(store, instrument_id):
    raw = b"H|\\^&\x00\x02|||SYN\rL|1|N\r"
    id_session = store.open_session(ctx(instrument_id))
    id_message = store.persist_event(
        instrument_id, id_session, 1, complete(raw, token=TOKEN_E1381_OR_CONTROL_BYTE)
    )
    with SessionTest() as s:
        row = s.get(InstrumentMessage, id_message)
        assert bytes(row.raw_bytes) == raw
        assert row.raw_sha256 == hashlib.sha256(raw).hexdigest()
        assert "\x00" not in row.raw_message and "�" in row.raw_message
        assert (row.parse_status, row.message_class) == ("Failed", "UNPARSEABLE")
        assert row.classification_rule == TOKEN_E1381_OR_CONTROL_BYTE


def test_identical_bytes_are_kept_as_separate_deliveries(store, instrument_id):
    raw = FIXTURE.read_bytes()
    id_session = store.open_session(ctx(instrument_id))
    first = store.persist_event(instrument_id, id_session, 1, complete(raw, start=0))
    second = store.persist_event(instrument_id, id_session, 2, complete(raw, start=len(raw)))
    assert first != second
    with SessionTest() as s:
        rows = s.scalars(select(InstrumentMessage).order_by(InstrumentMessage.id_message)).all()
        assert [r.raw_sha256 for r in rows] == [rows[0].raw_sha256] * 2
        assert all(r.duplicate_of_message_id is None for r in rows)


def test_same_session_offset_cannot_start_two_rows(store, instrument_id):
    id_session = store.open_session(ctx(instrument_id))
    store.persist_event(instrument_id, id_session, 1, complete(b"H|a\rL|1|N\r", start=0))
    with pytest.raises(IntegrityError):
        store.persist_event(instrument_id, id_session, 2, complete(b"H|b\rL|1|N\r", start=0))


@pytest.mark.parametrize(
    "overrides",
    [{"raw_length": 999}, {"raw_sha256": None}],
)
def test_raw_integrity_checks(instrument_id, overrides):
    raw = b"H|x\rL|1|N\r"
    values = dict(
        id_instrument=instrument_id, raw_message="x", parse_status="Pending",
        raw_bytes=raw, raw_sha256=hashlib.sha256(raw).hexdigest(), raw_length=len(raw),
    )
    values.update(overrides)
    with SessionTest() as s:
        s.add(InstrumentMessage(**values))
        with pytest.raises(IntegrityError):
            s.commit()


def test_mllp_style_row_without_raw_capture_columns_is_still_valid(instrument_id):
    with SessionTest() as s:
        s.add(InstrumentMessage(id_instrument=instrument_id, raw_message="MSH|^~\\&|", parse_status="Success"))
        s.commit()
        row = s.scalars(select(InstrumentMessage)).one()
        assert row.raw_bytes is None and row.id_session is None and row.raw_sha256 is None


# --------------------------------------------------------------------------- #
# End to end: loopback listener -> real store -> rows
# --------------------------------------------------------------------------- #


def test_end_to_end_listener_raw_capture_creates_no_clinical_or_audit_rows(instrument_id, monkeypatch):
    monkeypatch.setattr(listener_module, "READ_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(listener_module, "ACCEPT_TIMEOUT_SECONDS", 0.05)
    statuses: list[str] = []
    before = clinical_and_audit_counts()

    fixture = FIXTURE.read_bytes()
    second = b"H|\\^&|||SYNTH\rP|1\rO|1||^^SYNTH-E2E^M|\rR|1|^^^^SYN^1|1.0|u||N||F||lab||20260917100000\rL|1|N\r"
    transport = ListenerTransport(
        id_instrument=instrument_id, instrument_key="sysmex_xn550_e2e", bind_host="127.0.0.1",
        bind_port=0, allowed_peers=("127.0.0.1",), ack_policy="ack_per_read_on_receive",
        store=SqlRawCaptureStore(SessionTest), status_writer=lambda i, s: statuses.append(s),
    )
    thread = threading.Thread(target=transport.serve_forever, daemon=True)
    thread.start()
    try:
        assert transport.wait_until_bound(5)
        client = socket.create_connection(("127.0.0.1", transport.bound_port), timeout=5)
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        client.sendall(fixture[:1460])
        time.sleep(0.2)
        client.sendall(fixture[1460:] + second)
        time.sleep(0.5)
        client.settimeout(0.5)
        acks = b""
        try:
            while True:
                chunk = client.recv(64)
                if not chunk:
                    break
                acks += chunk
        except socket.timeout:
            pass
        client.close()

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with SessionTest() as s:
                row = s.scalars(select(InstrumentSession)).first()
                if row is not None and row.closed_at is not None:
                    break
            time.sleep(0.05)
    finally:
        transport.stop()
        thread.join(10)
    assert not thread.is_alive()

    with SessionTest() as s:
        session_row = s.scalars(select(InstrumentSession)).one()
        messages = s.scalars(select(InstrumentMessage).order_by(InstrumentMessage.session_message_index)).all()
    assert session_row.close_reason == CLOSE_PEER_CLOSED
    assert [bytes(m.raw_bytes) for m in messages] == [fixture, second]
    for m in messages:
        assert m.raw_sha256 == hashlib.sha256(bytes(m.raw_bytes)).hexdigest()
        assert m.id_session == session_row.id_session and m.parse_status == "Pending"
    assert [m.session_message_index for m in messages] == [1, 2]
    assert messages[0].stream_offset_end == messages[1].stream_offset_start
    assert session_row.bytes_received == len(fixture) + len(second)
    assert session_row.acks_sent == session_row.reads_count == len(acks)
    assert acks == ACK_BYTE * len(acks)
    assert session_row.messages_completed == 2 and session_row.fragments_count == 0
    assert "LISTENING" in statuses and "CONNECTED" in statuses

    assert clinical_and_audit_counts() == before == {
        "patients": 0, "visits": 0, "orders": 0, "test_runs": 0, "results": 0, "audit_events": 0,
    }
