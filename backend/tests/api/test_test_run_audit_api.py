"""M9.1b Phase D — router actor propagation, exercised over real HTTP with a
real login flow (no dependency overrides for auth). PostgreSQL-only, against
``lis_marina_permata_test``.

Complements tests/test_test_run_service_audit.py (Phase C, service layer
only, no router) and tests/api/test_test_runs_api.py (business logic, single
stub-free actor). This file's job is narrower and specific to Phase D: prove
that the six clinical mutation routes correctly thread the *authenticated*
caller into the audit trail, that the caller cannot substitute a different
identity, and that a denied request produces no audit row at all.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.core.security import Role, hash_password
from app.main import app
from app.models import AuditEvent, Instrument, Order, Patient, TestRun, User, Visit
from app.models.base import Base

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ANALYST_PASSWORD = "AuditApiAnalystPass1"
ADMIN_PASSWORD = "AuditApiAdminPass1"


@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        session.add_all([
            User(
                username="audit-analyst1",
                nama_lengkap="Audit Analyst",
                password_hash=hash_password(ANALYST_PASSWORD),
                role=Role.ANALYST.value,
                is_active=True,
            ),
            User(
                username="audit-admin1",
                nama_lengkap="Audit Admin",
                password_hash=hash_password(ADMIN_PASSWORD),
                role=Role.ADMIN.value,
                is_active=True,
            ),
        ])
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


def _make_test_run(session, *, is_final=False, delivery_status="pending") -> TestRun:
    unique = uuid.uuid4().hex[:12]
    inst = Instrument(nama_mesin="Mindray BC-5150", tipe_koneksi="TCP", protokol="HL7")
    session.add(inst)
    pat = Patient(nomor_rm=f"RM-AUD-{unique}", nama_lengkap="Audit API Test Patient")
    session.add(pat)
    session.flush()
    vis = Visit(id_pasien=pat.id_pasien, no_registrasi=f"REG-AUD-{unique}", waktu_kunjungan="2026-01-01 10:00:00")
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


def _audit_rows_for(session, entity_type: str, entity_id: int) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(
        AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id
    ).order_by(AuditEvent.id_audit)
    return list(session.scalars(stmt).all())


def _get_user_id(session, username: str) -> int:
    return session.scalar(select(User.id_user).where(User.username == username))


# --------------------------------------------------------------------------- #
# 1-2. Correct actor recorded for both roles (OD-1 = Option B: both may act)
# --------------------------------------------------------------------------- #


def test_analyst_finalize_creates_one_event_with_correct_actor(client, db_session):
    run = _make_test_run(db_session, is_final=False)
    token = _login(client, "audit-analyst1", ANALYST_PASSWORD)

    response = client.post(f"/api/test-runs/{run.id_run}/finalize", headers=_auth_headers(token))

    assert response.status_code == 200
    rows = _audit_rows_for(db_session, "TEST_RUN", run.id_run)
    assert len(rows) == 1
    assert rows[0].action == "TEST_RUN_FINALIZED"
    assert rows[0].id_user == _get_user_id(db_session, "audit-analyst1")
    assert rows[0].actor_username == "audit-analyst1"
    assert rows[0].actor_role == "ANALYST"


def test_admin_finalize_creates_one_event_with_correct_actor(client, db_session):
    run = _make_test_run(db_session, is_final=False)
    token = _login(client, "audit-admin1", ADMIN_PASSWORD)

    response = client.post(f"/api/test-runs/{run.id_run}/finalize", headers=_auth_headers(token))

    assert response.status_code == 200
    rows = _audit_rows_for(db_session, "TEST_RUN", run.id_run)
    assert len(rows) == 1
    assert rows[0].id_user == _get_user_id(db_session, "audit-admin1")
    assert rows[0].actor_username == "audit-admin1"
    assert rows[0].actor_role == "ADMIN"


# --------------------------------------------------------------------------- #
# 3. Actor cannot be spoofed via body / query / header
# --------------------------------------------------------------------------- #


def test_actor_cannot_be_spoofed_via_body_query_or_header(client, db_session):
    """The route accepts no body/query field for identity, and a client
    cannot override get_current_user's resolved identity by asserting one
    through any request channel — the recorded actor must still be the
    authenticated caller, never the spoofed value."""
    run = _make_test_run(db_session, is_final=False)
    real_analyst_id = _get_user_id(db_session, "audit-analyst1")
    admin_id = _get_user_id(db_session, "audit-admin1")
    token = _login(client, "audit-analyst1", ANALYST_PASSWORD)

    response = client.post(
        f"/api/test-runs/{run.id_run}/finalize?id_user={admin_id}&actor_username=audit-admin1&role=ADMIN",
        headers={
            **_auth_headers(token),
            "X-User-Id": str(admin_id),
            "X-Actor-Username": "audit-admin1",
        },
        json={"id_user": admin_id, "actor_username": "audit-admin1", "actor_role": "ADMIN"},
    )

    assert response.status_code == 200
    rows = _audit_rows_for(db_session, "TEST_RUN", run.id_run)
    assert len(rows) == 1
    assert rows[0].id_user == real_analyst_id, "spoofed id_user must not have been recorded"
    assert rows[0].id_user != admin_id
    assert rows[0].actor_username == "audit-analyst1"
    assert rows[0].actor_role == "ANALYST"


# --------------------------------------------------------------------------- #
# 4. Unauthenticated mutation: 401, zero new audit events
# --------------------------------------------------------------------------- #


def test_unauthenticated_finalize_returns_401_and_creates_no_audit_event(client, db_session):
    run = _make_test_run(db_session, is_final=False)

    response = client.post(f"/api/test-runs/{run.id_run}/finalize")

    assert response.status_code == 401
    assert _audit_rows_for(db_session, "TEST_RUN", run.id_run) == []


def test_unauthenticated_delivery_start_returns_401_and_creates_no_audit_event(client, db_session):
    run = _make_test_run(db_session, is_final=True, delivery_status="pending")

    response = client.post(f"/api/test-runs/{run.id_run}/delivery/start")

    assert response.status_code == 401
    assert _audit_rows_for(db_session, "TEST_RUN", run.id_run) == []


# --------------------------------------------------------------------------- #
# 5. RBAC continuity — both roles may still perform clinical mutations,
#    delivery/start wiring also proven (not just finalize)
# --------------------------------------------------------------------------- #


def test_delivery_start_creates_one_event_with_correct_actor(client, db_session):
    run = _make_test_run(db_session, is_final=True, delivery_status="pending")
    token = _login(client, "audit-analyst1", ANALYST_PASSWORD)

    response = client.post(f"/api/test-runs/{run.id_run}/delivery/start", headers=_auth_headers(token))

    assert response.status_code == 200
    rows = _audit_rows_for(db_session, "TEST_RUN", run.id_run)
    assert len(rows) == 1
    assert rows[0].action == "DELIVERY_STARTED"
    assert rows[0].actor_username == "audit-analyst1"


# --------------------------------------------------------------------------- #
# 6. No-op finalize still produces zero audit events, at the API layer too
# --------------------------------------------------------------------------- #


def test_noop_finalize_via_api_creates_no_new_audit_event(client, db_session):
    run = _make_test_run(db_session, is_final=False)
    token = _login(client, "audit-analyst1", ANALYST_PASSWORD)

    first = client.post(f"/api/test-runs/{run.id_run}/finalize", headers=_auth_headers(token))
    assert first.status_code == 200
    assert len(_audit_rows_for(db_session, "TEST_RUN", run.id_run)) == 1

    second = client.post(f"/api/test-runs/{run.id_run}/finalize", headers=_auth_headers(token))
    assert second.status_code == 200
    assert second.json()["is_final"] is True
    assert len(_audit_rows_for(db_session, "TEST_RUN", run.id_run)) == 1, (
        "a no-op (already-final) finalize must not add a second audit row"
    )
