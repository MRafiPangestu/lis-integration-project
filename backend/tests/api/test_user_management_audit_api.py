"""M9.1b Phase F — user-management audit attribution, over real HTTP with a
real login flow. PostgreSQL-only, against ``lis_marina_permata_test``.

Covers: POST /api/users -> USER_CREATED, PATCH /api/users/{id}/status ->
USER_DISABLED/USER_REACTIVATED, POST /api/account/change-password ->
PASSWORD_CHANGED.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.api.routers.users import would_leave_no_active_admin
from app.core.database import get_db
from app.core.security import Role, hash_password
from app.main import app
from app.models import AuditEvent, User
from app.models.base import Base

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ADMIN_PASSWORD = "UmAuditAdminPass1"
ADMIN2_PASSWORD = "UmAuditAdmin2Pass1"
ANALYST_PASSWORD = "UmAuditAnalystPass1"


@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        session.add_all([
            User(
                username="um-admin1", nama_lengkap="UM Admin One",
                password_hash=hash_password(ADMIN_PASSWORD), role=Role.ADMIN.value, is_active=True,
            ),
            User(
                username="um-admin2", nama_lengkap="UM Admin Two",
                password_hash=hash_password(ADMIN2_PASSWORD), role=Role.ADMIN.value, is_active=True,
            ),
            User(
                username="um-analyst1", nama_lengkap="UM Analyst One",
                password_hash=hash_password(ANALYST_PASSWORD), role=Role.ANALYST.value, is_active=True,
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


def _audit_rows_for(session, entity_id: int) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(
        AuditEvent.entity_type == "USER", AuditEvent.entity_id == entity_id
    ).order_by(AuditEvent.id_audit)
    return list(session.scalars(stmt).all())


def _get_user_id(session, username: str) -> int:
    return session.scalar(select(User.id_user).where(User.username == username))


def _create_disposable_analyst(session, *, username: str, is_active: bool = True) -> User:
    """A fresh, throwaway ANALYST target for status-toggle tests, isolated
    from the shared ``um-analyst1`` fixture user."""
    user = User(
        username=username, nama_lengkap="Disposable Analyst",
        password_hash=hash_password("DisposablePass123"), role=Role.ANALYST.value, is_active=is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# 1-2. USER_CREATED
# --------------------------------------------------------------------------- #


def test_admin_creates_user_produces_one_event_no_sensitive_data(client, db_session):
    admin_token = _login(client, "um-admin1", ADMIN_PASSWORD)
    admin_id = _get_user_id(db_session, "um-admin1")
    unique = uuid.uuid4().hex[:10]

    response = client.post(
        "/api/users",
        headers=_auth_headers(admin_token),
        json={
            "username": f"created-{unique}",
            "nama_lengkap": "Newly Created",
            "password": "NewlyCreatedPass1",
            "role": "ANALYST",
        },
    )

    assert response.status_code == 201
    new_user_id = response.json()["id_user"]

    rows = _audit_rows_for(db_session, new_user_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "USER_CREATED"
    assert row.entity_type == "USER"
    assert row.entity_id == new_user_id
    assert row.outcome == "SUCCESS"
    assert row.id_user == admin_id, "actor must be the creating ADMIN, not the new account"
    assert row.actor_username == "um-admin1"
    assert row.actor_role == "ADMIN"
    assert row.state_before is None
    assert row.state_after == "True"

    # No sensitive data anywhere on the row.
    for value in (row.action, row.entity_type, str(row.state_before), str(row.state_after)):
        assert "NewlyCreatedPass1" not in value
    assert not hasattr(row, "password")
    assert not hasattr(row, "password_hash")


def test_analyst_cannot_create_user(client, db_session):
    analyst_token = _login(client, "um-analyst1", ANALYST_PASSWORD)
    unique = uuid.uuid4().hex[:10]

    response = client.post(
        "/api/users",
        headers=_auth_headers(analyst_token),
        json={
            "username": f"blocked-{unique}",
            "nama_lengkap": "Should Not Exist",
            "password": "ShouldNotExistPass1",
            "role": "ANALYST",
        },
    )

    assert response.status_code == 403
    assert db_session.scalar(select(User).where(User.username == f"blocked-{unique}")) is None


# --------------------------------------------------------------------------- #
# 3-5. USER_DISABLED / USER_REACTIVATED / no-op
# --------------------------------------------------------------------------- #


def test_admin_disables_analyst_produces_one_event(client, db_session):
    target = _create_disposable_analyst(db_session, username=f"disable-target-{uuid.uuid4().hex[:8]}")
    admin_token = _login(client, "um-admin1", ADMIN_PASSWORD)
    admin_id = _get_user_id(db_session, "um-admin1")

    response = client.patch(
        f"/api/users/{target.id_user}/status", headers=_auth_headers(admin_token), json={"is_active": False},
    )

    assert response.status_code == 200
    rows = _audit_rows_for(db_session, target.id_user)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "USER_DISABLED"
    assert row.id_user == admin_id
    assert row.entity_type == "USER"
    assert row.entity_id == target.id_user
    assert row.state_before == "True"
    assert row.state_after == "False"


def test_admin_reactivates_analyst_produces_one_event(client, db_session):
    target = _create_disposable_analyst(
        db_session, username=f"reactivate-target-{uuid.uuid4().hex[:8]}", is_active=False,
    )
    admin_token = _login(client, "um-admin1", ADMIN_PASSWORD)
    admin_id = _get_user_id(db_session, "um-admin1")

    response = client.patch(
        f"/api/users/{target.id_user}/status", headers=_auth_headers(admin_token), json={"is_active": True},
    )

    assert response.status_code == 200
    rows = _audit_rows_for(db_session, target.id_user)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "USER_REACTIVATED"
    assert row.id_user == admin_id
    assert row.state_before == "False"
    assert row.state_after == "True"


def test_noop_status_update_creates_zero_audit_events(client, db_session):
    target = _create_disposable_analyst(db_session, username=f"noop-target-{uuid.uuid4().hex[:8]}", is_active=True)
    admin_token = _login(client, "um-admin1", ADMIN_PASSWORD)

    response = client.patch(
        f"/api/users/{target.id_user}/status", headers=_auth_headers(admin_token), json={"is_active": True},
    )

    assert response.status_code == 200
    assert _audit_rows_for(db_session, target.id_user) == []


# --------------------------------------------------------------------------- #
# 6-7. Existing guards preserved, no audit event when blocked
# --------------------------------------------------------------------------- #


def test_admin_cannot_self_disable_and_creates_no_audit_event(client, db_session):
    admin_token = _login(client, "um-admin1", ADMIN_PASSWORD)
    admin_id = _get_user_id(db_session, "um-admin1")

    response = client.patch(
        f"/api/users/{admin_id}/status", headers=_auth_headers(admin_token), json={"is_active": False},
    )

    assert response.status_code == 409
    assert _audit_rows_for(db_session, admin_id) == []


def test_would_leave_no_active_admin_guard_blocks_and_is_unreachable_via_api():
    """``would_leave_no_active_admin`` (app/api/routers/users.py) is
    exercised directly here, not over HTTP. As its own docstring already
    documents (pre-existing, not introduced by Phase F): given the
    self-disable guard runs first, the *only* way to reach the "last active
    admin" branch through the live API would require the calling admin to be
    disabling themselves — which the self-disable check above already
    rejects first, every time. An admin disabling a *different* admin always
    leaves at least the caller themselves counted as active, so the branch
    can never actually return True from a real request. Fabricating an
    API-level 409 test for it would therefore misrepresent what happens; the
    guard's logic is instead verified directly, as its docstring itself
    recommends ("Extracted from the handler so the guard itself is directly
    testable")."""
    with TestingSessionLocal() as session:
        try:
            # This module's fixture admins (um-admin1, um-admin2) are real,
            # committed, active rows in this same test database — so making
            # `sole_admin` genuinely the only active ADMIN means temporarily
            # deactivating them too. Everything here is rolled back, never
            # committed, so it has no lasting effect on any other test.
            other_active_admins = session.scalars(
                select(User).where(User.role == Role.ADMIN.value, User.is_active.is_(True))
            ).all()
            for admin in other_active_admins:
                admin.is_active = False

            sole_admin = User(
                username=f"sole-admin-{uuid.uuid4().hex[:8]}", nama_lengkap="Sole Admin",
                password_hash=hash_password("SoleAdminPass123"), role=Role.ADMIN.value, is_active=True,
            )
            session.add(sole_admin)
            session.flush()  # visible within this transaction, not yet committed

            assert would_leave_no_active_admin(session, sole_admin) is True

            # Inverse sanity check: with a second active admin restored, the
            # guard no longer fires for the same target.
            if other_active_admins:
                other_active_admins[0].is_active = True
                session.flush()
                assert would_leave_no_active_admin(session, sole_admin) is False
        finally:
            session.rollback()  # never persisted


# --------------------------------------------------------------------------- #
# 8-11. PASSWORD_CHANGED
# --------------------------------------------------------------------------- #


def test_user_changes_own_password_produces_one_event_no_sensitive_data(client, db_session):
    target = _create_disposable_analyst(db_session, username=f"pwchange-{uuid.uuid4().hex[:8]}")
    target.password_hash = hash_password("OriginalOwnerPass1")
    db_session.commit()
    token = _login(client, target.username, "OriginalOwnerPass1")

    response = client.post(
        "/api/account/change-password",
        headers=_auth_headers(token),
        json={"current_password": "OriginalOwnerPass1", "new_password": "BrandNewOwnerPass1"},
    )

    assert response.status_code == 204
    rows = _audit_rows_for(db_session, target.id_user)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "PASSWORD_CHANGED"
    assert row.id_user == target.id_user
    assert row.actor_username == target.username
    assert row.entity_type == "USER"
    assert row.entity_id == target.id_user
    assert row.state_before is None
    assert row.state_after is None

    # No password/hash material anywhere on the row.
    for field_name in ("action", "entity_type", "actor_username", "actor_role"):
        value = getattr(row, field_name)
        assert "OriginalOwnerPass1" not in value
        assert "BrandNewOwnerPass1" not in value
    assert not hasattr(row, "password")
    assert not hasattr(row, "password_hash")


def test_wrong_current_password_returns_401_and_creates_no_event(client, db_session):
    target = _create_disposable_analyst(db_session, username=f"pwwrong-{uuid.uuid4().hex[:8]}")
    target.password_hash = hash_password("ActualPassword1")
    db_session.commit()
    token = _login(client, target.username, "ActualPassword1")

    response = client.post(
        "/api/account/change-password",
        headers=_auth_headers(token),
        json={"current_password": "TotallyWrongPassword1", "new_password": "WouldBeNewPass1"},
    )

    assert response.status_code == 401
    assert _audit_rows_for(db_session, target.id_user) == []
    # password truly unchanged: old password still logs in
    _login(client, target.username, "ActualPassword1")


def test_unauthenticated_password_change_returns_401_and_creates_no_event(client, db_session):
    # No entity to scope to (the caller is anonymous, so there is no
    # authenticated user to attribute to) — assert the *total* row count is
    # unchanged by this call instead.
    before_count = db_session.scalar(select(func.count(AuditEvent.id_audit)))

    response = client.post(
        "/api/account/change-password",
        json={"current_password": "whatever", "new_password": "NewPasswordAttempt1"},
    )

    assert response.status_code == 401
    after_count = db_session.scalar(select(func.count(AuditEvent.id_audit)))
    assert after_count == before_count


def test_analyst_password_change_attributed_to_analyst(client, db_session):
    token = _login(client, "um-analyst1", ANALYST_PASSWORD)
    analyst_id = _get_user_id(db_session, "um-analyst1")

    response = client.post(
        "/api/account/change-password",
        headers=_auth_headers(token),
        json={"current_password": ANALYST_PASSWORD, "new_password": "AnalystNewPass123"},
    )

    assert response.status_code == 204
    rows = _audit_rows_for(db_session, analyst_id)
    assert len(rows) == 1
    assert rows[0].action == "PASSWORD_CHANGED"
    assert rows[0].actor_username == "um-analyst1"
    assert rows[0].actor_role == "ANALYST"

    # restore for any later test relying on the original password
    db_session.get(User, analyst_id).password_hash = hash_password(ANALYST_PASSWORD)
    db_session.commit()


# --------------------------------------------------------------------------- #
# 12. Audit insert failure rolls back the business mutation
# --------------------------------------------------------------------------- #


def test_create_user_audit_insert_failure_rolls_back_creation(client, db_session, monkeypatch):
    admin_token = _login(client, "um-admin1", ADMIN_PASSWORD)
    unique = uuid.uuid4().hex[:10]
    original_add = db_session.add

    def failing_add(instance):
        if isinstance(instance, AuditEvent):
            raise IntegrityError("mocked audit insert failure", None, Exception("mocked"))
        return original_add(instance)

    monkeypatch.setattr(db_session, "add", failing_add)

    response = client.post(
        "/api/users",
        headers=_auth_headers(admin_token),
        json={
            "username": f"rollback-{unique}",
            "nama_lengkap": "Should Roll Back",
            "password": "ShouldRollBackPass1",
            "role": "ANALYST",
        },
    )

    assert response.status_code == 409
    monkeypatch.undo()
    assert db_session.scalar(select(User).where(User.username == f"rollback-{unique}")) is None, (
        "the new user must not exist — the audit-insert failure must have rolled back user creation too"
    )


# --------------------------------------------------------------------------- #
# 13. Forged actor attempt via body/query/header is ignored
# --------------------------------------------------------------------------- #


def test_actor_cannot_be_spoofed_on_user_management_endpoints(client, db_session):
    admin_token = _login(client, "um-admin1", ADMIN_PASSWORD)
    admin_id = _get_user_id(db_session, "um-admin1")
    other_admin_id = _get_user_id(db_session, "um-admin2")
    unique = uuid.uuid4().hex[:10]

    response = client.post(
        f"/api/users?id_user={other_admin_id}&actor_username=um-admin2",
        headers={**_auth_headers(admin_token), "X-User-Id": str(other_admin_id)},
        json={
            "username": f"spoof-{unique}",
            "nama_lengkap": "Spoof Target",
            "password": "SpoofTargetPass1",
            "role": "ANALYST",
            # extra, undeclared fields — CreateUserRequest has no id_user /
            # actor_username field, so these are simply ignored by Pydantic.
            "id_user": other_admin_id,
            "actor_username": "um-admin2",
            "actor_role": "ADMIN",
        },
    )

    assert response.status_code == 201
    new_user_id = response.json()["id_user"]
    row = _audit_rows_for(db_session, new_user_id)[0]
    assert row.id_user == admin_id, "recorded actor must be the authenticated caller, never a spoofed value"
    assert row.id_user != other_admin_id
    assert row.actor_username == "um-admin1"
