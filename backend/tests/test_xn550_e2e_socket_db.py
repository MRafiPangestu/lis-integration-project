"""XN-550 development end-to-end: TCP socket -> listener -> database (G2).

Every layer here is the real one and wired exactly as ``run_integration.py``
wires it: a real ``ListenerTransport`` on a loopback port, the real
``SqlRawCaptureStore``, the real ``Xn550ClassificationStage`` at
``ingestion_stage="observations"``, and PostgreSQL. The bytes are delivered by
the development simulator (``tests/simulate_xn550.py``) over an actual socket,
so nothing in this module injects a message directly.

PostgreSQL-only, against ``lis_marina_permata_test`` — never the stable PoC and
never DEV. This proves the *software* path on a developer machine. It is not
physical instrument validation and it is not a soak.
"""
from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import simulate_xn550 as simulator
from app.integration.astm.assembler import FRAGMENT_INCOMPLETE_AT_CLOSE, FRAMING_ASTM_CR_RECORDS
from app.integration.listener import ListenerTransport
from app.integration.parsers.xn550_astm import (
    PARSER_KEY,
    PARSER_VERSION,
    classify_xn550,
    parse_xn550_astm,
)
from app.integration.raw_capture import SqlRawCaptureStore
from app.integration.xn550_ingestion import Xn550ClassificationStage
from app.models import (
    AuditEvent,
    Instrument,
    InstrumentMessage,
    InstrumentResultItem,
    InstrumentResultSet,
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

CONFORMANT = "XN550_ENVELOPE_CONFORMANT"
WAIT = 10.0


@pytest.fixture(scope="module")
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def live(_schema):
    """A listening LIS with the real store and the real G2 classification stage."""
    with SessionTest() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        instrument = Instrument(nama_mesin="Sysmex XN-550 (simulated)")
        session.add(instrument)
        session.commit()
        id_instrument = instrument.id_instrument

    stage = Xn550ClassificationStage(
        session_factory=SessionTest,
        parser=parse_xn550_astm,
        policy=classify_xn550,
        parser_key=PARSER_KEY,
        parser_version=PARSER_VERSION,
        ingestion_stage="observations",
    )
    statuses: list[str] = []
    transport = ListenerTransport(
        id_instrument=id_instrument,
        instrument_key="sysmex_xn550_dev_sim",
        bind_host="127.0.0.1",
        bind_port=0,
        allowed_peers=("127.0.0.1",),
        ack_policy="ack_per_read_on_receive",
        store=SqlRawCaptureStore(SessionTest),
        status_writer=lambda _id, status: statuses.append(status),
        on_raw_committed=stage.process,
    )
    thread = threading.Thread(target=transport.serve_forever, daemon=True)
    thread.start()
    assert transport.wait_until_bound(WAIT)

    yield {"port": transport.bound_port, "id_instrument": id_instrument, "statuses": statuses}

    transport.stop()
    thread.join(WAIT)
    assert not thread.is_alive(), "listener thread did not stop"


def deliver(mode: str, port: int, **kwargs) -> None:
    """Run one simulator mode against the live listener."""
    payloads = simulator.messages_for(mode, kwargs.pop("count", 3))
    writes = simulator.writes_for(mode, payloads, kwargs.pop("chunk_size", 200))
    simulator.send(writes, port=port, verbose=False, **kwargs)


def wait_for(predicate, timeout: float = WAIT, interval: float = 0.02):
    """Work the listener does after the socket closes is not synchronous."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def rows(model, order_by=None):
    with SessionTest() as session:
        statement = select(model)
        if order_by is not None:
            statement = statement.order_by(order_by)
        return list(session.scalars(statement))


def clinical_counts() -> dict:
    with SessionTest() as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (Patient, Visit, Order, ClinicalRun, Result, AuditEvent)
        }


ZERO = {"patients": 0, "visits": 0, "orders": 0, "test_runs": 0, "results": 0, "audit_events": 0}


def test_one_conformant_message_over_a_real_socket_becomes_one_result_set(live):
    """socket -> listener -> raw capture -> classification -> result set + items."""
    sent = simulator.load_fixture()
    deliver("single", live["port"])

    messages = rows(InstrumentMessage, InstrumentMessage.id_message)
    assert len(messages) == 1
    message = messages[0]

    # The bytes on the wire are the bytes in the database.
    assert message.raw_bytes == sent
    assert message.raw_length == len(sent)
    assert message.framing == FRAMING_ASTM_CR_RECORDS
    assert message.parse_status == "Success"
    assert message.classification_rule == CONFORMANT
    assert message.message_class != "PATIENT_RESULT"
    assert message.parser_key == PARSER_KEY

    sets = rows(InstrumentResultSet)
    assert len(sets) == 1
    result_set = sets[0]
    assert result_set.id_message == message.id_message
    assert result_set.id_instrument == live["id_instrument"]

    items = rows(InstrumentResultItem, InstrumentResultItem.source_r_sequence)
    assert len(items) == result_set.item_count > 0
    assert [item.source_r_sequence for item in items] == sorted(item.source_r_sequence for item in items)
    assert all(item.id_result_set == result_set.id_result_set for item in items)

    # A session row exists with the listener's provenance.
    sessions = rows(InstrumentSession)
    assert len(sessions) == 1 and sessions[0].id_instrument == live["id_instrument"]


def test_identity_stays_unresolved_and_the_label_is_display_only(live):
    deliver("single", live["port"])
    result_set = rows(InstrumentResultSet)[0]

    assert result_set.association_status == "UNRESOLVED"
    assert result_set.duplicate_status == "NONE"
    assert result_set.possible_duplicate_of is None
    # A label is stored for display; it resolves nothing and links to nothing.
    assert isinstance(result_set.sample_label, str) and result_set.sample_label
    for attribute in ("id_patient", "id_visit", "id_order", "id_test_run", "id_result"):
        assert not hasattr(result_set, attribute), attribute


def test_the_whole_socket_path_creates_no_clinical_and_no_audit_row(live):
    deliver("multi", live["port"], count=3)

    assert len(rows(InstrumentResultSet)) == 3
    assert clinical_counts() == ZERO
    assert all(message.message_class != "PATIENT_RESULT" for message in rows(InstrumentMessage))


def test_a_byte_identical_retransmission_creates_no_second_result_set(live):
    deliver("retransmit", live["port"])

    messages = rows(InstrumentMessage, InstrumentMessage.id_message)
    assert len(messages) == 2
    assert messages[0].raw_bytes == messages[1].raw_bytes
    assert messages[0].raw_sha256 == messages[1].raw_sha256

    # Two deliveries, one observation, and the later one points back at the first.
    sets = rows(InstrumentResultSet)
    assert len(sets) == 1 and sets[0].id_message == messages[0].id_message
    assert messages[1].duplicate_of_message_id == messages[0].id_message
    assert clinical_counts() == ZERO


def test_same_content_with_different_bytes_is_flagged_not_suppressed(live):
    deliver("same-fingerprint", live["port"])

    sets = rows(InstrumentResultSet, InstrumentResultSet.id_result_set)
    assert len(sets) == 2, "different bytes are a different delivery, never suppressed"
    assert sets[0].analysis_fingerprint == sets[1].analysis_fingerprint
    assert sets[0].duplicate_status == "NONE" and sets[0].possible_duplicate_of is None
    assert sets[1].duplicate_status == "POSSIBLE_DUPLICATE"
    assert sets[1].possible_duplicate_of == sets[0].id_result_set


def test_a_fragmented_transmission_is_reassembled_across_reads(live):
    """One message split over many writes is one row with the exact bytes."""
    sent = simulator.load_fixture()
    deliver("fragmented", live["port"], chunk_size=200)

    messages = rows(InstrumentMessage, InstrumentMessage.id_message)
    assert len(messages) == 1, "a recv() is not a message"
    assert messages[0].raw_bytes == sent
    assert messages[0].parse_status == "Success"
    assert messages[0].classification_rule == CONFORMANT
    assert len(rows(InstrumentResultSet)) == 1
    assert rows(InstrumentResultSet)[0].item_count == len(rows(InstrumentResultItem))


def test_a_connection_closed_mid_message_persists_a_fragment_and_no_observation(live):
    deliver("close-mid-message", live["port"])

    # The fragment is written when the peer closes, not while it is writing.
    assert wait_for(lambda: len(rows(InstrumentMessage)) == 1), "no fragment was persisted"
    messages = rows(InstrumentMessage)
    assert len(messages) == 1
    assert messages[0].error_detail == FRAGMENT_INCOMPLETE_AT_CLOSE
    assert rows(InstrumentResultSet) == []
    assert rows(InstrumentResultItem) == []
    assert clinical_counts() == ZERO


def test_a_deviation_message_is_recorded_and_creates_no_observation(live):
    deliver("deviation", live["port"])

    messages = rows(InstrumentMessage)
    assert len(messages) == 1
    assert messages[0].classification_rule == "XN550_DEV_POPULATED_COMMENT"
    assert messages[0].message_class != "PATIENT_RESULT"
    assert rows(InstrumentResultSet) == [], "only conformant envelopes are normalised"
    assert clinical_counts() == ZERO
