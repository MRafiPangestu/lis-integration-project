"""M9.1b Phase E — sync-SIMRS produces exactly two audit events.

No source change was required for this phase: Phase D already threads one
resolved ``current_user`` into all three ``TestRunService`` calls
``sync_simrs`` makes (``start_delivery`` in its Phase 1, then
``mark_delivery_delivered``/``mark_delivery_failed`` in its Phase 3), and
Phase C already stages exactly one audit row per call, before that call's
own existing commit. This file exists purely to prove that composition holds
end to end over real HTTP, with the outbound SIMRS call mocked.

PostgreSQL-only, against ``lis_marina_permata_test``.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.core.security import Role, hash_password
from app.integration.simrs_client import SimrsClient, SimrsResponse
from app.main import app
from app.models import AuditEvent, Instrument, Order, Patient, TestRun, User, Visit
from app.models.base import Base

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ANALYST_PASSWORD = "SimAuditAnalystPass1"


@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        session.add(User(
            username="sim-analyst1",
            nama_lengkap="Sim Audit Analyst",
            password_hash=hash_password(ANALYST_PASSWORD),
            role=Role.ANALYST.value,
            is_active=True,
        ))
        session.commit()

    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(setup_database):
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]


def _login(client, username, password) -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_test_run(session, *, is_final=True, delivery_status="pending") -> TestRun:
    """A TestRun with the full Order/Visit/Patient chain sync-simrs's payload
    builder needs, plus at least one Result so the payload is representative."""
    unique = uuid.uuid4().hex[:12]
    inst = Instrument(nama_mesin="Mindray BC-5150", tipe_koneksi="TCP", protokol="HL7")
    session.add(inst)
    pat = Patient(nomor_rm=f"RM-SIM-{unique}", nama_lengkap="Sim Audit Test Patient")
    session.add(pat)
    session.flush()
    vis = Visit(id_pasien=pat.id_pasien, no_registrasi=f"REG-SIM-{unique}", waktu_kunjungan="2026-01-01 10:00:00")
    session.add(vis)
    session.flush()
    order = Order(id_visit=vis.id_visit, status_order="Diproses")
    session.add(order)
    session.flush()
    run = TestRun(
        id_order=order.id_order,
        id_instrument=inst.id_instrument,
        run_sequence=1,
        is_final=is_final,
        delivery_status=delivery_status,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _audit_rows_for(session, entity_id: int) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(
        AuditEvent.entity_type == "TEST_RUN", AuditEvent.entity_id == entity_id
    ).order_by(AuditEvent.id_audit)  # SERIAL PK — strictly monotonic insertion
    # order; deterministic across PostgreSQL, unlike relying on occurred_at
    # (a TIMESTAMP that could tie at coarse resolution).
    return list(session.scalars(stmt).all())


def _get_user_id(session, username: str) -> int:
    return session.scalar(select(User.id_user).where(User.username == username))


# --------------------------------------------------------------------------- #
# Success path — two audit rows: DELIVERY_STARTED, then DELIVERY_DELIVERED
# --------------------------------------------------------------------------- #


def test_sync_simrs_success_produces_started_then_delivered(client, db_session, monkeypatch):
    run = _make_test_run(db_session, is_final=True, delivery_status="pending")
    token = _login(client, "sim-analyst1", ANALYST_PASSWORD)
    analyst_id = _get_user_id(db_session, "sim-analyst1")

    monkeypatch.setattr(
        SimrsClient,
        "send",
        staticmethod(lambda payload: SimrsResponse(success=True, status_code=200, response_body={"ok": True})),
    )

    response = client.post(f"/api/test-runs/{run.id_run}/sync-simrs", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["simrs_success"] is True
    assert body["delivery_status"] == "delivered"

    rows = _audit_rows_for(db_session, run.id_run)
    assert len(rows) == 2, f"sync-simrs must produce exactly two audit rows, got {len(rows)}"

    started, delivered = rows
    assert started.action == "DELIVERY_STARTED"
    assert started.state_before == "pending"
    assert started.state_after == "sending"
    assert started.outcome == "SUCCESS"
    assert started.entity_type == "TEST_RUN"
    assert started.entity_id == run.id_run
    assert started.occurred_at is not None

    assert delivered.action == "DELIVERY_DELIVERED"
    assert delivered.state_before == "sending"
    assert delivered.state_after == "delivered"
    assert delivered.outcome == "SUCCESS"
    assert delivered.entity_type == "TEST_RUN"
    assert delivered.entity_id == run.id_run
    assert delivered.occurred_at is not None

    # Same authenticated actor on both rows.
    for row in (started, delivered):
        assert row.id_user == analyst_id
        assert row.actor_username == "sim-analyst1"
        assert row.actor_role == "ANALYST"

    # Deterministic ordering: STARTED was inserted (and committed) strictly
    # before DELIVERED — proven by primary-key order, not wall-clock ties.
    assert started.id_audit < delivered.id_audit


# --------------------------------------------------------------------------- #
# Failure path — two audit rows: DELIVERY_STARTED, then DELIVERY_FAILED.
# No second "failed" outcome is invented — outcome stays SUCCESS on both rows
# because both represent a successfully committed domain transition; the
# *business* result is carried by `action` and state_before/state_after.
# --------------------------------------------------------------------------- #


def test_sync_simrs_failure_produces_started_then_failed(client, db_session, monkeypatch):
    run = _make_test_run(db_session, is_final=True, delivery_status="pending")
    token = _login(client, "sim-analyst1", ANALYST_PASSWORD)
    analyst_id = _get_user_id(db_session, "sim-analyst1")

    monkeypatch.setattr(
        SimrsClient,
        "send",
        staticmethod(lambda payload: SimrsResponse(success=False, error="mocked SIMRS failure")),
    )

    response = client.post(f"/api/test-runs/{run.id_run}/sync-simrs", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["simrs_success"] is False
    assert body["delivery_status"] == "failed"

    rows = _audit_rows_for(db_session, run.id_run)
    assert len(rows) == 2

    started, failed = rows
    assert started.action == "DELIVERY_STARTED"
    assert started.outcome == "SUCCESS"  # the transition to 'sending' itself succeeded
    assert failed.action == "DELIVERY_FAILED"
    assert failed.state_before == "sending"
    assert failed.state_after == "failed"
    assert failed.outcome == "SUCCESS"  # recording the failed *delivery* is itself a successful commit

    for row in (started, failed):
        assert row.id_user == analyst_id
        assert row.actor_username == "sim-analyst1"
        assert row.actor_role == "ANALYST"


# --------------------------------------------------------------------------- #
# Rejected before any state transition: zero audit rows
# --------------------------------------------------------------------------- #


def test_sync_simrs_rejects_non_final_run_with_no_audit_rows(client, db_session, monkeypatch):
    run = _make_test_run(db_session, is_final=False, delivery_status="pending")
    token = _login(client, "sim-analyst1", ANALYST_PASSWORD)
    called = {"n": 0}
    monkeypatch.setattr(
        SimrsClient, "send",
        staticmethod(lambda payload: called.__setitem__("n", called["n"] + 1) or SimrsResponse(success=True)),
    )

    response = client.post(f"/api/test-runs/{run.id_run}/sync-simrs", headers=_auth_headers(token))

    assert response.status_code == 409
    assert called["n"] == 0, "SIMRS must never be called for a run that isn't final"
    assert _audit_rows_for(db_session, run.id_run) == []


# --------------------------------------------------------------------------- #
# Retry semantics: a fresh sync-simrs after a prior failure creates a new pair
# --------------------------------------------------------------------------- #


def test_sync_simrs_retry_after_failure_creates_a_new_audit_pair(client, db_session, monkeypatch):
    run = _make_test_run(db_session, is_final=True, delivery_status="pending")
    token = _login(client, "sim-analyst1", ANALYST_PASSWORD)

    monkeypatch.setattr(
        SimrsClient, "send",
        staticmethod(lambda payload: SimrsResponse(success=False, error="first attempt fails")),
    )
    first = client.post(f"/api/test-runs/{run.id_run}/sync-simrs", headers=_auth_headers(token))
    assert first.status_code == 200
    assert first.json()["delivery_status"] == "failed"
    assert [r.action for r in _audit_rows_for(db_session, run.id_run)] == [
        "DELIVERY_STARTED", "DELIVERY_FAILED",
    ]

    monkeypatch.setattr(
        SimrsClient, "send",
        staticmethod(lambda payload: SimrsResponse(success=True, status_code=200, response_body={})),
    )
    second = client.post(f"/api/test-runs/{run.id_run}/sync-simrs", headers=_auth_headers(token))
    assert second.status_code == 200
    assert second.json()["delivery_status"] == "delivered"

    rows = _audit_rows_for(db_session, run.id_run)
    assert [r.action for r in rows] == [
        "DELIVERY_STARTED", "DELIVERY_FAILED", "DELIVERY_STARTED", "DELIVERY_DELIVERED",
    ]


# --------------------------------------------------------------------------- #
# Transaction-boundary proof: Phase 1 is committed — visible to an
# independent connection — strictly before the outbound HTTP call begins.
# This is the safe alternative to process-death simulation: a second,
# genuinely separate session/connection against the same test database can
# only see Phase 1's write if it was actually committed, not merely flushed
# within the request's own session (which would see its own uncommitted
# writes regardless of commit state).
# --------------------------------------------------------------------------- #


def test_sync_simrs_phase1_is_committed_before_the_outbound_call(client, db_session, monkeypatch):
    run = _make_test_run(db_session, is_final=True, delivery_status="pending")
    token = _login(client, "sim-analyst1", ANALYST_PASSWORD)
    observed: dict = {}

    def fake_send(payload):
        with TestingSessionLocal() as outside:
            fresh = outside.get(TestRun, run.id_run)
            observed["delivery_status_visible_elsewhere"] = fresh.delivery_status
            observed["audit_row_count_visible_elsewhere"] = len(
                outside.scalars(
                    select(AuditEvent).where(
                        AuditEvent.entity_type == "TEST_RUN", AuditEvent.entity_id == run.id_run
                    )
                ).all()
            )
        return SimrsResponse(success=True, status_code=200, response_body={})

    monkeypatch.setattr(SimrsClient, "send", staticmethod(fake_send))

    response = client.post(f"/api/test-runs/{run.id_run}/sync-simrs", headers=_auth_headers(token))

    assert response.status_code == 200
    assert observed["delivery_status_visible_elsewhere"] == "sending", (
        "Phase 1 (start_delivery) must already be committed — visible to a "
        "wholly independent connection — before the outbound SIMRS call "
        "begins; no DB transaction may span the HTTP call"
    )
    assert observed["audit_row_count_visible_elsewhere"] == 1, (
        "only DELIVERY_STARTED exists at this point; the terminal event "
        "(DELIVERY_DELIVERED/DELIVERY_FAILED) is written by Phase 3, after "
        "the HTTP call returns, never before or during it"
    )
