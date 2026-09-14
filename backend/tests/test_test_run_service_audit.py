"""M9.1b Phase C — TestRunService audit attribution (service layer only).

Exercises the five TestRunService methods directly (no HTTP, no router —
the routers are not updated until Phase D and currently call these methods
without the new required ``actor`` parameter). PostgreSQL-only, against
``lis_marina_permata_test``.

Uses a REEAL persisted ``User`` row as the actor for every test — per the
M9.1b task brief, the ``id_user=0`` stub pattern used by the API-level test
modules must not be reintroduced here, since ``audit_events.id_user`` is now
a real foreign key to ``users.id_user``.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.security import Role, hash_password
from app.models import AuditEvent, Instrument, Order, Patient, TestRun, User, Visit
from app.models.base import Base
from app.services.test_run_service import TestRunService

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean(_schema):
    with TestingSessionLocal() as s:
        for table in reversed(Base.metadata.sorted_tables):
            s.execute(table.delete())
        s.commit()
    yield


@pytest.fixture
def session():
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def actor(session) -> User:
    """A real, persisted ANALYST user — the only kind of actor
    ``audit_events.id_user`` may legitimately reference."""
    user = User(
        username="svc-analyst",
        nama_lengkap="Service Test Analyst",
        password_hash=hash_password("ServiceAnalystPass1"),
        role=Role.ANALYST.value,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def other_actor(session) -> User:
    """A second real, persisted ADMIN user, for cross-actor assertions."""
    user = User(
        username="svc-admin",
        nama_lengkap="Service Test Admin",
        password_hash=hash_password("ServiceAdminPass1"),
        role=Role.ADMIN.value,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_test_run(session, *, is_final=False, delivery_status="pending") -> TestRun:
    unique = uuid.uuid4().hex[:12]
    inst = Instrument(nama_mesin="Mindray BC-5150", tipe_koneksi="TCP", protokol="HL7")
    session.add(inst)
    pat = Patient(nomor_rm=f"RM-SVC-{unique}", nama_lengkap="Service Test Patient")
    session.add(pat)
    session.flush()
    vis = Visit(id_pasien=pat.id_pasien, no_registrasi=f"REG-SVC-{unique}", waktu_kunjungan="2026-01-01 10:00:00")
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


def _audit_rows_for(session, test_run: TestRun) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(
        AuditEvent.entity_type == "TEST_RUN", AuditEvent.entity_id == test_run.id_run
    ).order_by(AuditEvent.id_audit)
    return list(session.scalars(stmt).all())


# --------------------------------------------------------------------------- #
# 1-3. Successful transitions create exactly one audit event
# --------------------------------------------------------------------------- #


def test_finalize_creates_exactly_one_audit_event(session, actor):
    run = _make_test_run(session, is_final=False)

    TestRunService.finalize_run(session, run.id_run, actor)

    rows = _audit_rows_for(session, run)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "TEST_RUN_FINALIZED"
    assert row.entity_type == "TEST_RUN"
    assert row.entity_id == run.id_run
    assert row.outcome == "SUCCESS"
    assert row.state_before == "False"
    assert row.state_after == "True"


def test_unfinalize_creates_exactly_one_audit_event(session, actor):
    run = _make_test_run(session, is_final=True)

    TestRunService.unfinalize_run(session, run.id_run, actor)

    rows = _audit_rows_for(session, run)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "TEST_RUN_UNFINALIZED"
    assert row.state_before == "True"
    assert row.state_after == "False"


def test_delivery_start_creates_exactly_one_audit_event(session, actor):
    run = _make_test_run(session, is_final=True, delivery_status="pending")

    TestRunService.start_delivery(session, run.id_run, actor)

    rows = _audit_rows_for(session, run)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "DELIVERY_STARTED"
    assert row.state_before == "pending"
    assert row.state_after == "sending"


def test_delivery_delivered_creates_exactly_one_audit_event(session, actor):
    run = _make_test_run(session, is_final=True, delivery_status="sending")

    TestRunService.mark_delivery_delivered(session, run.id_run, actor)

    rows = _audit_rows_for(session, run)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "DELIVERY_DELIVERED"
    assert row.state_before == "sending"
    assert row.state_after == "delivered"


def test_delivery_failed_creates_exactly_one_audit_event(session, actor):
    run = _make_test_run(session, is_final=True, delivery_status="sending")

    TestRunService.mark_delivery_failed(session, run.id_run, actor)

    rows = _audit_rows_for(session, run)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "DELIVERY_FAILED"
    assert row.state_before == "sending"
    assert row.state_after == "failed"


# --------------------------------------------------------------------------- #
# 4-5. No-op short-circuits create zero audit events (idempotency preserved)
# --------------------------------------------------------------------------- #


def test_noop_finalize_creates_zero_events(session, actor):
    run = _make_test_run(session, is_final=True)  # already final

    result = TestRunService.finalize_run(session, run.id_run, actor)

    assert result.is_final is True
    assert _audit_rows_for(session, run) == []


def test_noop_unfinalize_creates_zero_events(session, actor):
    run = _make_test_run(session, is_final=False)  # already not final

    result = TestRunService.unfinalize_run(session, run.id_run, actor)

    assert result.is_final is False
    assert _audit_rows_for(session, run) == []


def test_finalize_unfinalize_finalize_preserves_all_three_audit_rows(session, actor):
    run = _make_test_run(session, is_final=False)

    TestRunService.finalize_run(session, run.id_run, actor)
    TestRunService.unfinalize_run(session, run.id_run, actor)
    TestRunService.finalize_run(session, run.id_run, actor)

    rows = _audit_rows_for(session, run)
    assert [r.action for r in rows] == [
        "TEST_RUN_FINALIZED",
        "TEST_RUN_UNFINALIZED",
        "TEST_RUN_FINALIZED",
    ]


# --------------------------------------------------------------------------- #
# 6. Audit insert failure rolls back the business mutation
# --------------------------------------------------------------------------- #


def test_audit_insert_failure_rolls_back_finalize(session):
    """A transient (never-persisted) actor has no matching `users` row, so
    the AuditEvent's id_user FK fails at commit — finalize_run must roll
    back is_final along with it, not partially apply the mutation."""
    run = _make_test_run(session, is_final=False)
    ghost_actor = User(
        id_user=999_999,  # deliberately not a real row
        username="ghost",
        nama_lengkap="Ghost",
        password_hash="unused",
        role=Role.ANALYST.value,
        is_active=True,
    )

    with pytest.raises(Exception):
        TestRunService.finalize_run(session, run.id_run, ghost_actor)

    session.rollback()
    fresh = session.get(TestRun, run.id_run)
    session.refresh(fresh)
    assert fresh.is_final is False, "mutation must not survive a failed audit insert"
    assert _audit_rows_for(session, run) == []


# --------------------------------------------------------------------------- #
# 7. Actor fields copied correctly
# --------------------------------------------------------------------------- #


def test_actor_fields_copied_correctly(session, actor):
    run = _make_test_run(session, is_final=False)

    TestRunService.finalize_run(session, run.id_run, actor)

    row = _audit_rows_for(session, run)[0]
    assert row.id_user == actor.id_user
    assert row.actor_username == actor.username
    assert row.actor_role == actor.role


def test_different_actors_are_recorded_distinctly(session, actor, other_actor):
    run1 = _make_test_run(session, is_final=False)
    run2 = _make_test_run(session, is_final=False)

    TestRunService.finalize_run(session, run1.id_run, actor)
    TestRunService.finalize_run(session, run2.id_run, other_actor)

    row1 = _audit_rows_for(session, run1)[0]
    row2 = _audit_rows_for(session, run2)[0]
    assert row1.actor_username == "svc-analyst"
    assert row1.actor_role == "ANALYST"
    assert row2.actor_username == "svc-admin"
    assert row2.actor_role == "ADMIN"


# --------------------------------------------------------------------------- #
# Occurred-at comes from the server default, not application code
# --------------------------------------------------------------------------- #


def test_occurred_at_is_populated_by_server_default(session, actor):
    run = _make_test_run(session, is_final=False)

    TestRunService.finalize_run(session, run.id_run, actor)

    row = _audit_rows_for(session, run)[0]
    assert row.occurred_at is not None
