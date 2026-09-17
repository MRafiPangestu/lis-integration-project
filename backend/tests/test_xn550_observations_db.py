"""XN-550 G2 unlinked observations against PostgreSQL (contract §10, §13, §14.2).

PostgreSQL-only, against ``lis_marina_permata_test`` (never the stable PoC or DEV
database). Covers result-set creation, byte-identity linking, possible
duplicates, the per-instrument advisory lock (contention, timeout, instrument
independence), T3 rollback, database invariants and log hygiene. Every test
also proves that no clinical or audit row is created and that nothing becomes
``PATIENT_RESULT``.
"""
from __future__ import annotations

import datetime
import pathlib
import re
import socket
import threading
import time

import pytest
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.integration import listener as listener_module
from app.integration import xn550_ingestion as ingestion_module
from app.integration import xn550_observations as observations_module
from app.integration.astm.assembler import CompleteMessage, Fragment
from app.integration.listener import ListenerTransport
from app.integration.parsers.xn550_astm import (
    PARSER_KEY,
    PARSER_VERSION,
    classify_xn550,
    parse_xn550_astm,
)
from app.integration.raw_capture import SessionContext, SqlRawCaptureStore
from app.integration.xn550_ingestion import Xn550ClassificationStage
from app.integration.xn550_normalize import (
    NormalizedItem,
    NormalizedResultSet,
    analysis_fingerprint_v1,
    normalize_xn550,
)
from app.integration.xn550_observations import T2_LOCK_NAMESPACE
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
from app.services.instrument_result_service import get_instrument_result_set, list_instrument_result_sets

PG_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(PG_URL)
SessionTest = sessionmaker(bind=engine, autoflush=False, autocommit=False)
assert engine.url.database == "lis_marina_permata_test"

FIXTURE = (
    pathlib.Path(__file__).resolve().parent
    / "fixtures" / "instruments" / "sysmex_xn550" / "patient_result_001.astm"
)
T0 = datetime.datetime(2026, 9, 18, 9, 0, 0)
REDELIVERY_NOTE = re.compile(r"^Redelivery: byte-identical to message \d+$")
TOKEN_FORMAT = re.compile(r"^[A-Z0-9_]+( @record \d+( field \d+)?)?$")


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
    assert clinical_and_audit_counts() == ZERO, "XN-550 observations must never create clinical or audit rows"
    with SessionTest() as s:
        assert s.scalar(
            select(func.count()).select_from(InstrumentMessage).where(InstrumentMessage.message_class == "PATIENT_RESULT")
        ) == 0


@pytest.fixture
def instrument_id() -> int:
    return make_instrument("Sysmex XN-550")


def make_instrument(name: str) -> int:
    with SessionTest() as s:
        inst = Instrument(nama_mesin=name)
        s.add(inst)
        s.commit()
        return inst.id_instrument


@pytest.fixture
def store() -> SqlRawCaptureStore:
    return SqlRawCaptureStore(SessionTest)


def make_stage(stage: str = "observations", parser=parse_xn550_astm) -> Xn550ClassificationStage:
    return Xn550ClassificationStage(
        session_factory=SessionTest, parser=parser, policy=classify_xn550,
        parser_key=PARSER_KEY, parser_version=PARSER_VERSION, ingestion_stage=stage,
    )


def persist_raw(store, instrument_id: int, raw: bytes, *, peer_port: int = 49671, received_at=T0) -> int:
    """One T1 row in its own session (sessions never enter duplicate decisions)."""
    id_session = store.open_session(
        SessionContext(
            id_instrument=instrument_id, transport_mode="listener", local_address="127.0.0.1",
            local_port=5001, peer_address="127.0.0.1", peer_port=peer_port,
            ack_policy="ack_per_read_on_receive", opened_at=received_at,
        )
    )
    event = CompleteMessage(
        raw=raw, offset_start=0, offset_end=len(raw), first_byte_at=received_at,
        last_byte_at=received_at, read_count=2, byte_class_token=None,
    )
    return store.persist_event(instrument_id, id_session, 1, event)


def fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def records_of(raw: bytes) -> list[str]:
    return raw.decode("ascii").split("\r")


def join(records: list[str]) -> bytes:
    return "\r".join(records).encode("ascii")


def with_folder_date_shift(raw: bytes) -> bytes:
    records = records_of(raw)
    index = next(i for i, record in enumerate(records) if "PNG&R&" in record)
    folder = records[index].split("PNG&R&", 1)[1][:8]
    records[index] = records[index].replace(f"PNG&R&{folder}", f"PNG&R&{int(folder) + 1:08d}", 1)
    return join(records)


def with_analysis_time(raw: bytes, stamp: str) -> bytes:
    return raw.replace(b"20260915023225", stamp.encode("ascii"))


def with_sample_label(raw: bytes, label: str) -> bytes:
    records = records_of(raw)
    order = records[3].split("|")
    components = order[3].split("^")
    components[2] = label
    order[3] = "^".join(components)
    records[3] = "|".join(order)
    return join(records)


def with_o3(raw: bytes) -> bytes:
    records = records_of(raw)
    order = records[3].split("|")
    order[2] = "SYNTH-O3"
    records[3] = "|".join(order)
    return join(records)


def message(id_message: int) -> InstrumentMessage:
    with SessionTest() as s:
        return s.get(InstrumentMessage, id_message)


def sets() -> list[InstrumentResultSet]:
    with SessionTest() as s:
        return s.scalars(select(InstrumentResultSet).order_by(InstrumentResultSet.id_result_set)).all()


def item_count() -> int:
    with SessionTest() as s:
        return s.scalar(select(func.count()).select_from(InstrumentResultItem))


def delivery_count(id_result_set: int) -> int:
    with SessionTest() as s:
        return get_instrument_result_set(s, id_result_set)["delivery_count"]


# --------------------------------------------------------------------------- #
# Result-set creation
# --------------------------------------------------------------------------- #


def test_conformant_delivery_creates_one_unlinked_result_set_with_all_items(store, instrument_id):
    raw = fixture_bytes()
    id_message = persist_raw(store, instrument_id, raw)
    assert make_stage().process(id_message) == "XN550_ENVELOPE_CONFORMANT"

    row = message(id_message)
    assert (row.parse_status, row.message_class, row.classification_rule) == ("Success", "UNCLASSIFIED", "XN550_ENVELOPE_CONFORMANT")
    assert (row.parser_key, row.parser_version) == (PARSER_KEY, PARSER_VERSION)
    assert row.duplicate_of_message_id is None and row.error_detail is None

    [result_set] = sets()
    assert result_set.id_message == id_message and result_set.id_instrument == instrument_id
    assert result_set.received_at == row.received_at
    assert result_set.analysis_at == datetime.datetime(2026, 9, 15, 2, 32, 25)
    assert result_set.sample_label == "XXXXXX"
    assert result_set.association_status == "UNRESOLVED"
    assert (result_set.duplicate_status, result_set.possible_duplicate_of) == ("NONE", None)
    assert (result_set.item_count, result_set.non_n_flag_item_count, result_set.image_reference_count) == (42, 6, 4)
    assert (result_set.p5_populated, result_set.p8_populated) == (True, True)
    assert result_set.fingerprint_version == 1
    # PV-2: re-running the parser over raw_bytes reproduces the stored fingerprint.
    assert result_set.analysis_fingerprint == analysis_fingerprint_v1(
        instrument_id, normalize_xn550(parse_xn550_astm(bytes(row.raw_bytes)))
    )

    with SessionTest() as s:
        items = s.scalars(
            select(InstrumentResultItem).where(InstrumentResultItem.id_result_set == result_set.id_result_set)
            .order_by(InstrumentResultItem.source_r_sequence)
        ).all()
    assert len(items) == 42 and [item.source_r_sequence for item in items] == list(range(1, 43))
    stored = bytes(row.raw_bytes)
    for item in items:  # PV-6
        assert stored[item.source_offset_end] == 0x0D
        assert stored[item.source_offset_start:item.source_offset_start + 2] == b"R|"
        if item.item_kind == "IMAGE_REFERENCE":
            assert item.value_raw is None and item.units_raw is None
        assert item.reference_range_raw is None
    assert delivery_count(result_set.id_result_set) == 1


def test_raw_only_stage_never_creates_a_set_but_still_links_redeliveries(store, instrument_id):
    raw = fixture_bytes()
    first = persist_raw(store, instrument_id, raw)
    second = persist_raw(store, instrument_id, raw, peer_port=49672)
    stage = make_stage("raw_only")
    assert stage.process(first) == stage.process(second) == "XN550_ENVELOPE_CONFORMANT"
    assert sets() == [] and item_count() == 0
    assert message(first).duplicate_of_message_id is None
    assert message(second).duplicate_of_message_id == first
    assert REDELIVERY_NOTE.fullmatch(message(second).error_detail)


def test_deviations_unparseable_rows_and_fragments_create_no_set_and_no_link(store, instrument_id):
    deviation = with_o3(fixture_bytes())
    a = persist_raw(store, instrument_id, deviation)
    b = persist_raw(store, instrument_id, deviation, peer_port=49672)
    c = persist_raw(store, instrument_id, b"H|\\^&\rL|1|N\r", peer_port=49673)
    stage = make_stage()
    assert stage.process(a) == stage.process(b) == "XN550_DEV_O3_POPULATED"
    assert stage.process(c) == "XN550_DEV_RECORD_SEQUENCE"
    id_session = store.open_session(
        SessionContext(instrument_id, "listener", "127.0.0.1", 5001, "127.0.0.1", 1, "ack_per_read_on_receive", T0)
    )
    fragment = store.persist_event(
        instrument_id, id_session, 1, Fragment(fixture_bytes()[:900], 0, 900, T0, T0, 1, "XN550_FRAGMENT_INCOMPLETE_AT_CLOSE")
    )
    assert stage.process(fragment) is None
    assert sets() == [] and item_count() == 0
    assert all(message(i).duplicate_of_message_id is None for i in (a, b, c, fragment))


# --------------------------------------------------------------------------- #
# Duplicate handling (§13)
# --------------------------------------------------------------------------- #


def test_byte_identical_redeliveries_link_to_the_lowest_id_and_create_no_second_set(store, instrument_id):
    raw = fixture_bytes()
    ids = [persist_raw(store, instrument_id, raw, peer_port=49671 + n) for n in range(3)]
    stage = make_stage()
    for id_message in ids:
        assert stage.process(id_message) == "XN550_ENVELOPE_CONFORMANT"
    [result_set] = sets()
    assert result_set.id_message == ids[0]
    assert [message(i).duplicate_of_message_id for i in ids] == [None, ids[0], ids[0]]  # never a chain
    assert message(ids[1]).error_detail == f"Redelivery: byte-identical to message {ids[0]}"
    assert delivery_count(result_set.id_result_set) == 3
    with SessionTest() as s:
        detail = get_instrument_result_set(s, result_set.id_result_set)
    assert [d["id_message"] for d in detail["deliveries"]] == ids


def test_redelivery_after_reconnect_in_a_new_session_is_linked_not_new(store, instrument_id):
    raw = fixture_bytes()
    first = persist_raw(store, instrument_id, raw, peer_port=49752)
    after_reconnect = persist_raw(store, instrument_id, raw, peer_port=49671, received_at=T0 + datetime.timedelta(hours=3))
    assert message(first).id_session != message(after_reconnect).id_session
    stage = make_stage()
    stage.process(first)
    stage.process(after_reconnect)
    assert len(sets()) == 1
    assert message(after_reconnect).duplicate_of_message_id == first


def test_same_content_with_different_bytes_is_a_possible_duplicate_of_the_lowest_id_set(store, instrument_id):
    raw = fixture_bytes()
    shifted = with_folder_date_shift(raw)
    shifted_twice = with_folder_date_shift(shifted)
    ids = [
        persist_raw(store, instrument_id, raw),
        persist_raw(store, instrument_id, shifted, peer_port=49672),
        persist_raw(store, instrument_id, shifted_twice, peer_port=49673),
    ]
    stage = make_stage()
    for id_message in ids:
        stage.process(id_message)
    first, second, third = sets()
    assert (first.duplicate_status, first.possible_duplicate_of) == ("NONE", None)
    assert (second.duplicate_status, second.possible_duplicate_of) == ("POSSIBLE_DUPLICATE", first.id_result_set)
    assert (third.duplicate_status, third.possible_duplicate_of) == ("POSSIBLE_DUPLICATE", first.id_result_set)
    assert first.analysis_fingerprint == second.analysis_fingerprint == third.analysis_fingerprint
    assert all(message(i).duplicate_of_message_id is None for i in ids)  # different bytes: no byte link


def test_genuine_new_analysis_is_a_new_set_with_no_duplicate_flag(store, instrument_id):
    raw = fixture_bytes()
    rerun = with_analysis_time(raw, "20260915031500")
    stage = make_stage()
    stage.process(persist_raw(store, instrument_id, raw))
    stage.process(persist_raw(store, instrument_id, rerun, peer_port=49672))
    first, second = sets()
    assert (second.duplicate_status, second.possible_duplicate_of) == ("NONE", None)
    assert first.analysis_fingerprint != second.analysis_fingerprint


def test_same_sample_no_with_different_results_is_never_a_duplicate(store, instrument_id):
    raw = with_sample_label(fixture_bytes(), "SYNTH-0042")
    other_results = raw.replace(b"|11.30|10*3/uL|", b"|6.20|10*3/uL|", 1)
    stage = make_stage()
    stage.process(persist_raw(store, instrument_id, raw))
    stage.process(persist_raw(store, instrument_id, other_results, peer_port=49672))
    first, second = sets()
    assert first.sample_label == second.sample_label == "SYNTH-0042"
    assert (second.duplicate_status, second.possible_duplicate_of) == ("NONE", None)


def test_bytes_first_seen_under_raw_only_get_exactly_one_set_on_redelivery_under_observations(store, instrument_id):
    raw = fixture_bytes()
    g1_row = persist_raw(store, instrument_id, raw)
    make_stage("raw_only").process(g1_row)
    before = message(g1_row)
    g2_row = persist_raw(store, instrument_id, raw, peer_port=49672)
    make_stage("observations").process(g2_row)
    [result_set] = sets()
    assert result_set.id_message == g2_row
    assert message(g2_row).duplicate_of_message_id == g1_row
    after = message(g1_row)
    assert (after.parse_status, after.classification_rule, after.duplicate_of_message_id, after.error_detail) == (
        before.parse_status, before.classification_rule, before.duplicate_of_message_id, before.error_detail,
    )
    assert delivery_count(result_set.id_result_set) == 2


def test_rows_classified_before_g2_are_never_backfilled_and_still_count_as_deliveries(store, instrument_id):
    raw = fixture_bytes()
    # A Phase-2 row: conformant, Success, no link (Phase 2 made no link).
    old_a = persist_raw(store, instrument_id, raw)
    old_b = persist_raw(store, instrument_id, raw, peer_port=49672)
    with SessionTest() as s:
        for id_message in (old_a, old_b):
            row = s.get(InstrumentMessage, id_message)
            row.parse_status, row.message_class = "Success", "UNCLASSIFIED"
            row.classification_rule, row.error_detail = "XN550_ENVELOPE_CONFORMANT", None
            row.parser_key, row.parser_version = PARSER_KEY, PARSER_VERSION
        s.commit()
    snapshot = {i: (message(i).duplicate_of_message_id, message(i).error_detail) for i in (old_a, old_b)}

    new = persist_raw(store, instrument_id, raw, peer_port=49673)
    make_stage().process(new)
    assert {i: (message(i).duplicate_of_message_id, message(i).error_detail) for i in (old_a, old_b)} == snapshot
    assert snapshot[old_b] == (None, None)  # the pre-G2 redelivery keeps NULL: no backfill
    assert message(new).duplicate_of_message_id == old_a
    [result_set] = sets()
    assert result_set.id_message == new
    assert delivery_count(result_set.id_result_set) == 3  # query-derived, independent of links


def test_a_failed_t2_delivery_does_not_block_a_later_identical_delivery(store, instrument_id):
    raw = fixture_bytes()
    first = persist_raw(store, instrument_id, raw)

    def exploding(_raw):
        raise RuntimeError("boom")

    assert make_stage(parser=exploding).process(first) == "XN550_T2_EXCEPTION"
    second = persist_raw(store, instrument_id, raw, peer_port=49672)
    assert make_stage().process(second) == "XN550_ENVELOPE_CONFORMANT"
    [result_set] = sets()
    assert result_set.id_message == second
    assert message(second).duplicate_of_message_id is None  # a Failed row is not a group member


def test_out_of_order_processing_never_links_to_a_higher_id_or_creates_a_second_set(store, instrument_id):
    raw = fixture_bytes()
    lower = persist_raw(store, instrument_id, raw)
    higher = persist_raw(store, instrument_id, raw, peer_port=49672)
    stage = make_stage()
    stage.process(higher)  # e.g. the lower row was delayed
    stage.process(lower)
    assert message(higher).duplicate_of_message_id is None
    assert message(lower).duplicate_of_message_id is None
    [result_set] = sets()
    assert result_set.id_message == higher
    assert delivery_count(result_set.id_result_set) == 2


def test_reprocessing_is_a_no_op(store, instrument_id):
    id_message = persist_raw(store, instrument_id, fixture_bytes())
    stage = make_stage()
    assert stage.process(id_message) == "XN550_ENVELOPE_CONFORMANT"
    assert stage.process(id_message) is None
    assert len(sets()) == 1 and item_count() == 42


# --------------------------------------------------------------------------- #
# T3 and the per-instrument advisory lock (§10.4 step 9, §14.2)
# --------------------------------------------------------------------------- #


def test_failure_after_the_set_insert_rolls_back_the_whole_t2_transaction(store, instrument_id, monkeypatch):
    raw = fixture_bytes()
    first = persist_raw(store, instrument_id, raw)
    make_stage().process(first)
    redelivery_of_other_bytes = persist_raw(store, instrument_id, with_folder_date_shift(raw), peer_port=49672)
    duplicate = persist_raw(store, instrument_id, raw, peer_port=49673)

    real = ingestion_module.normalize_xn550

    def poisoned(parsed):
        good = real(parsed)
        bad_item = NormalizedItem(**{**good.items[-1].__dict__, "value_raw": "PNG-SHOULD-NEVER-BE-STORED"})
        return NormalizedResultSet(**{**good.__dict__, "items": good.items[:-1] + (bad_item,)})

    monkeypatch.setattr(ingestion_module, "normalize_xn550", poisoned)
    assert make_stage().process(redelivery_of_other_bytes) == "XN550_T2_EXCEPTION"
    row = message(redelivery_of_other_bytes)
    assert (row.parse_status, row.message_class, row.classification_rule, row.error_detail) == (
        "Failed", "UNPARSEABLE", "XN550_T2_EXCEPTION", "XN550_T2_EXCEPTION",
    )
    assert len(sets()) == 1 and item_count() == 42  # no partial set or items survive

    # a failed linking transaction leaves no link either
    def boom(*_args, **_kwargs):
        raise RuntimeError("fail after linking")

    monkeypatch.setattr(ingestion_module, "group_owns_result_set", boom)
    assert make_stage().process(duplicate) == "XN550_T2_EXCEPTION"
    assert message(duplicate).duplicate_of_message_id is None


def _hold_lock(id_instrument: int):
    connection = engine.connect()
    connection.execute(text("SELECT pg_advisory_lock(:ns, :id)"), {"ns": T2_LOCK_NAMESPACE, "id": id_instrument})
    connection.commit()
    return connection


def _release_lock(connection, id_instrument: int) -> None:
    connection.execute(text("SELECT pg_advisory_unlock(:ns, :id)"), {"ns": T2_LOCK_NAMESPACE, "id": id_instrument})
    connection.commit()
    connection.close()


def test_lock_timeout_fails_safely_with_no_partial_observation(store, instrument_id, monkeypatch):
    monkeypatch.setattr(observations_module, "T2_LOCK_TIMEOUT", "300ms")
    id_message = persist_raw(store, instrument_id, fixture_bytes())
    holder = _hold_lock(instrument_id)
    try:
        started = time.monotonic()
        assert make_stage().process(id_message) == "XN550_T2_EXCEPTION"
        assert time.monotonic() - started < 10
    finally:
        _release_lock(holder, instrument_id)
    row = message(id_message)
    assert (row.parse_status, row.classification_rule, row.duplicate_of_message_id) == ("Failed", "XN550_T2_EXCEPTION", None)
    assert sets() == [] and item_count() == 0


def test_separate_instruments_do_not_block_each_other(store, instrument_id, monkeypatch):
    monkeypatch.setattr(observations_module, "T2_LOCK_TIMEOUT", "2s")
    other_instrument = make_instrument("Sysmex XN-550 (second analyser)")
    id_message = persist_raw(store, other_instrument, fixture_bytes())
    holder = _hold_lock(instrument_id)
    try:
        started = time.monotonic()
        assert make_stage().process(id_message) == "XN550_ENVELOPE_CONFORMANT"
        assert time.monotonic() - started < 1.5
    finally:
        _release_lock(holder, instrument_id)
    [result_set] = sets()
    assert result_set.id_instrument == other_instrument


def test_concurrent_identical_deliveries_create_at_most_one_result_set(store, instrument_id):
    raw = fixture_bytes()
    first = persist_raw(store, instrument_id, raw)
    second = persist_raw(store, instrument_id, raw, peer_port=49672)
    stage = make_stage()
    results: dict[int, str] = {}
    errors: list[BaseException] = []

    def work(id_message: int) -> None:
        try:
            results[id_message] = stage.process(id_message)
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    holder = _hold_lock(instrument_id)
    threads = [threading.Thread(target=work, args=(i,)) for i in (second, first)]
    try:
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with engine.connect() as probe:
                waiting = probe.scalar(
                    text(
                        "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted "
                        "AND classid = :ns AND objid = :id"
                    ),
                    {"ns": T2_LOCK_NAMESPACE, "id": instrument_id},
                )
            if waiting == 2:
                break
            time.sleep(0.05)
        assert waiting == 2, "both T2 transactions must be queued on the per-instrument lock"
    finally:
        _release_lock(holder, instrument_id)
        for thread in threads:
            thread.join(30)
    assert not errors and all(not thread.is_alive() for thread in threads)
    assert results == {first: "XN550_ENVELOPE_CONFORMANT", second: "XN550_ENVELOPE_CONFORMANT"}
    assert len(sets()) == 1 and item_count() == 42
    links = {i: message(i).duplicate_of_message_id for i in (first, second)}
    assert links[first] is None and links[second] in (None, first)
    [result_set] = sets()
    assert delivery_count(result_set.id_result_set) == 2


# --------------------------------------------------------------------------- #
# Database invariants (§10.2, §10.3)
# --------------------------------------------------------------------------- #


def _set_row(id_message: int, id_instrument: int, **overrides) -> InstrumentResultSet:
    values = dict(
        id_message=id_message, id_instrument=id_instrument, received_at=T0, analysis_at=T0,
        sample_label="SYNTH-0001", association_status="UNRESOLVED", analysis_fingerprint="0" * 64,
        fingerprint_version=1, duplicate_status="NONE", possible_duplicate_of=None,
        p5_populated=False, p8_populated=False, item_count=0, non_n_flag_item_count=0, image_reference_count=0,
    )
    values.update(overrides)
    return InstrumentResultSet(**values)


def _expect_integrity_error(*rows) -> None:
    with SessionTest() as s:
        s.add_all(rows)
        with pytest.raises(IntegrityError):
            s.flush()
        s.rollback()


def test_identity_and_duplicate_invariants_are_enforced_by_the_database(store, instrument_id):
    m1 = persist_raw(store, instrument_id, fixture_bytes())
    m2 = persist_raw(store, instrument_id, fixture_bytes(), peer_port=49672)
    m3 = persist_raw(store, instrument_id, fixture_bytes(), peer_port=49673)
    _expect_integrity_error(_set_row(m1, instrument_id, association_status="RESOLVED"))
    _expect_integrity_error(_set_row(m1, instrument_id, duplicate_status="POSSIBLE_DUPLICATE"))
    _expect_integrity_error(_set_row(m1, instrument_id, duplicate_status="OTHER"))
    with SessionTest() as s:
        anchor = _set_row(m1, instrument_id, id_result_set=500)
        s.add(anchor)
        s.commit()
    _expect_integrity_error(_set_row(m2, instrument_id, possible_duplicate_of=500))  # NONE with a pointer
    _expect_integrity_error(
        _set_row(m2, instrument_id, id_result_set=400, duplicate_status="POSSIBLE_DUPLICATE", possible_duplicate_of=500)
    )  # pointer to a higher id
    _expect_integrity_error(_set_row(m1, instrument_id))  # second set for the same message
    with SessionTest() as s:
        s.add(_set_row(m2, instrument_id, id_result_set=600, duplicate_status="POSSIBLE_DUPLICATE", possible_duplicate_of=500))
        s.flush()
        s.add(_set_row(m3, instrument_id, id_result_set=700))
        s.commit()


def _item_row(id_result_set: int, **overrides) -> InstrumentResultItem:
    values = dict(
        id_result_set=id_result_set, source_record_index=5, source_offset_start=431, source_offset_end=485,
        source_r_sequence=1, item_kind="MEASURED", test_code="WBC", test_code_qualifier="1", value_raw="11.30",
        units_raw="10*3/uL", reference_range_raw=None, abnormal_flag_raw="N", result_status_raw="F",
    )
    values.update(overrides)
    return InstrumentResultItem(**values)


def test_item_invariants_and_restrict_foreign_keys(store, instrument_id):
    m1 = persist_raw(store, instrument_id, fixture_bytes())
    with SessionTest() as s:
        s.add(_set_row(m1, instrument_id, id_result_set=900))
        s.flush()  # no ORM relationship: flush the parent before the child
        s.add(_item_row(900))
        s.commit()
    _expect_integrity_error(_item_row(900, source_record_index=6, test_code="SCAT_WDF", item_kind="IMAGE_REFERENCE", value_raw="PNG"))
    _expect_integrity_error(_item_row(900, source_record_index=6, test_code="RBC", item_kind="MEASURED", value_raw=None))
    _expect_integrity_error(_item_row(900, source_record_index=6, test_code="RBC", item_kind="OTHER"))
    _expect_integrity_error(_item_row(900, test_code="RBC"))  # same record index
    _expect_integrity_error(_item_row(900, source_record_index=6))  # same test code
    with SessionTest() as s, pytest.raises(IntegrityError):
        s.execute(delete(InstrumentMessage).where(InstrumentMessage.id_message == m1))
        s.flush()
    with SessionTest() as s, pytest.raises(IntegrityError):
        s.execute(delete(InstrumentResultSet).where(InstrumentResultSet.id_result_set == 900))
        s.flush()


def test_no_index_or_constraint_contains_sample_label():
    with engine.connect() as connection:
        index_defs = connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE tablename LIKE 'instrument_result_%'")
        ).scalars().all()
        constraint_defs = connection.execute(
            text(
                # PK / UNIQUE / FK / CHECK / EXCLUDE. PostgreSQL 18 also lists NOT NULL
                # as contype 'n'; a NOT NULL column is not a lookup constraint.
                "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname LIKE 'instrument_result_%' AND c.contype IN ('p', 'u', 'f', 'c', 'x')"
            )
        ).scalars().all()
    assert index_defs and constraint_defs
    assert not any("sample_label" in definition for definition in index_defs + constraint_defs)
    fk_defs = [d for d in constraint_defs if d.startswith("FOREIGN KEY")]
    assert len(fk_defs) == 4 and all("ON DELETE RESTRICT" in d for d in fk_defs)
    assert not any(clinical in d for d in fk_defs for clinical in ("patients", "visits", "orders", "test_runs", "results"))


# --------------------------------------------------------------------------- #
# Hygiene and end to end
# --------------------------------------------------------------------------- #


def test_logs_and_error_details_carry_no_label_or_image_path(store, instrument_id, caplog):
    sentinel = "SYNTH-LOGCHECK-G2A"
    raw = with_sample_label(fixture_bytes(), sentinel)
    caplog.set_level("DEBUG")
    stage = make_stage()
    ids = [persist_raw(store, instrument_id, raw), persist_raw(store, instrument_id, raw, peer_port=49672)]
    shifted = persist_raw(store, instrument_id, with_folder_date_shift(raw), peer_port=49673)
    deviation = persist_raw(store, instrument_id, with_o3(raw), peer_port=49674)
    for id_message in ids + [shifted, deviation]:
        stage.process(id_message)
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert sentinel not in logged and "PNG&R&" not in logged and "XXXXXX" not in logged
    for id_message in ids + [shifted, deviation]:
        detail = message(id_message).error_detail
        assert detail is None or TOKEN_FORMAT.fullmatch(detail) or REDELIVERY_NOTE.fullmatch(detail)


def test_service_list_never_filters_by_label_and_orders_newest_first(store, instrument_id):
    stage = make_stage()
    for n, stamp in enumerate(("20260915031000", "20260915032000", "20260915033000")):
        raw = with_sample_label(with_analysis_time(fixture_bytes(), stamp), "SYNTH-0007")
        stage.process(persist_raw(store, instrument_id, raw, peer_port=49700 + n, received_at=T0 + datetime.timedelta(minutes=n)))
    with SessionTest() as s:
        items, total = list_instrument_result_sets(
            s, received_from=T0, received_to=T0 + datetime.timedelta(hours=1), id_instrument=instrument_id, page=1, page_size=2,
        )
    assert total == 3 and len(items) == 2
    assert [item["received_at"] for item in items] == [T0 + datetime.timedelta(minutes=2), T0 + datetime.timedelta(minutes=1)]


def test_end_to_end_multi_select_burst_creates_five_rows_and_five_sets(store, instrument_id, monkeypatch):
    monkeypatch.setattr(listener_module, "READ_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(listener_module, "ACCEPT_TIMEOUT_SECONDS", 0.05)
    stage = make_stage()
    messages = [
        with_sample_label(with_analysis_time(fixture_bytes(), f"2026091503{n:02d}00"), f"SYNTH-{n:04d}") for n in range(5)
    ]
    transport = ListenerTransport(
        id_instrument=instrument_id, instrument_key="sysmex_xn550_g2_e2e", bind_host="127.0.0.1",
        bind_port=0, allowed_peers=("127.0.0.1",), ack_policy="ack_per_read_on_receive",
        store=store, status_writer=lambda i, s: None,
        on_raw_committed=stage.process, on_serve_start=lambda: stage.process_pending(instrument_id),
    )
    thread = threading.Thread(target=transport.serve_forever, daemon=True)
    thread.start()
    try:
        assert transport.wait_until_bound(5)
        client = socket.create_connection(("127.0.0.1", transport.bound_port), timeout=5)
        started = time.monotonic()
        for payload in messages:
            client.sendall(payload)
        assert time.monotonic() - started < 0.6
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and len(sets()) < 5:
            time.sleep(0.05)
        client.close()
    finally:
        transport.stop()
        thread.join(10)
    assert not thread.is_alive()
    with SessionTest() as s:
        rows = s.scalars(select(InstrumentMessage).order_by(InstrumentMessage.id_message)).all()
        session_count = s.scalar(select(func.count()).select_from(InstrumentSession))
    assert [row.session_message_index for row in rows] == [1, 2, 3, 4, 5]
    assert session_count == 1
    result_sets = sets()
    assert len(result_sets) == 5
    assert [result_set.sample_label for result_set in result_sets] == [f"SYNTH-{n:04d}" for n in range(5)]
    assert all(result_set.duplicate_status == "NONE" for result_set in result_sets)
