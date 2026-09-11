"""M9.1a — authentication, authorization and password-change tests.

PostgreSQL-only, against ``lis_marina_permata_test`` (the project's
established test database — see tests/api/test_test_runs_api.py). Exercises
the real login flow end to end: no ``get_current_user`` override here, unlike
the business-logic test modules.
"""
import datetime
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.routers.users import would_leave_no_active_admin
from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models.base import Base
from app.models.user import User

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ANALYST_PASSWORD = "AnalystPass123"
ADMIN_PASSWORD = "AdminPass1234"
INACTIVE_PASSWORD = "InactivePass1"


@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        session.add_all([
            User(
                username="analyst1",
                nama_lengkap="Analyst One",
                password_hash=hash_password(ANALYST_PASSWORD),
                role="ANALYST",
                is_active=True,
            ),
            User(
                username="admin1",
                nama_lengkap="Admin One",
                password_hash=hash_password(ADMIN_PASSWORD),
                role="ADMIN",
                is_active=True,
            ),
            User(
                username="inactive1",
                nama_lengkap="Inactive One",
                password_hash=hash_password(INACTIVE_PASSWORD),
                role="ANALYST",
                is_active=False,
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


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def _token_for(client, username, password) -> str:
    response = _login(client, username, password)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #


def test_login_success_returns_token_and_role(client):
    response = _login(client, "analyst1", ANALYST_PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert body["user"]["username"] == "analyst1"
    assert body["user"]["role"] == "ANALYST"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_login_wrong_password_rejected(client):
    response = _login(client, "analyst1", "totally-wrong-password")
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_unknown_username_rejected_with_same_message(client):
    response = _login(client, "no-such-user", "whatever-password")
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_login_inactive_user_rejected_with_same_message(client):
    """Correct password, disabled account — still the generic message, not a
    distinct "account disabled" response (no enumeration oracle)."""
    response = _login(client, "inactive1", INACTIVE_PASSWORD)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


def test_failed_login_has_fixed_delay(client):
    started = time.monotonic()
    _login(client, "analyst1", "wrong-password-again")
    elapsed = time.monotonic() - started
    assert elapsed >= 0.85, f"expected ~1s delay on failed login, got {elapsed:.3f}s"


def test_successful_login_has_no_deliberate_delay(client):
    started = time.monotonic()
    _login(client, "analyst1", ANALYST_PASSWORD)
    elapsed = time.monotonic() - started
    assert elapsed < 0.85


# --------------------------------------------------------------------------- #
# Token validation
# --------------------------------------------------------------------------- #


def test_valid_token_grants_access_to_protected_endpoint(client):
    token = _token_for(client, "analyst1", ANALYST_PASSWORD)
    response = client.get("/api/results", headers=_auth_headers(token))
    assert response.status_code == 200


def test_missing_token_rejected(client):
    response = client.get("/api/results")
    assert response.status_code == 401


def test_malformed_token_rejected(client):
    response = client.get("/api/results", headers=_auth_headers("not-a-jwt-at-all"))
    assert response.status_code == 401


def test_wrong_signing_key_rejected(client):
    bad_token = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.datetime.now(datetime.timezone.utc),
            "exp": datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=5),
        },
        "a-completely-different-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get("/api/results", headers=_auth_headers(bad_token))
    assert response.status_code == 401


def test_expired_token_rejected(client):
    now = datetime.datetime.now(datetime.timezone.utc)
    expired_token = jwt.encode(
        {"sub": "1", "iat": now - datetime.timedelta(hours=9), "exp": now - datetime.timedelta(hours=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get("/api/results", headers=_auth_headers(expired_token))
    assert response.status_code == 401


def test_alg_none_token_rejected(client):
    """Algorithm-confusion / alg=none forgery: the header's own alg is never
    trusted (design §6.2, threat 9) — algorithms=[...] is pinned server-side."""
    now = datetime.datetime.now(datetime.timezone.utc)
    forged = jwt.encode(
        {"sub": "1", "iat": now, "exp": now + datetime.timedelta(minutes=5)},
        "",
        algorithm="none",
    )
    response = client.get("/api/results", headers=_auth_headers(forged))
    assert response.status_code == 401


def test_token_for_unknown_user_id_rejected(client):
    now = datetime.datetime.now(datetime.timezone.utc)
    token = jwt.encode(
        {"sub": "999999", "iat": now, "exp": now + datetime.timedelta(minutes=5)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    response = client.get("/api/results", headers=_auth_headers(token))
    assert response.status_code == 401


def test_disabling_user_revokes_access_on_next_request(client, db_session):
    """§6.3 revocation: disabling an account is effective on the very next
    request, without waiting for the 8-hour token expiry — no blacklist."""
    revocable = User(
        username="revoke-me",
        nama_lengkap="Revoke Me",
        password_hash=hash_password("RevokeMePass1"),
        role="ANALYST",
        is_active=True,
    )
    db_session.add(revocable)
    db_session.commit()
    db_session.refresh(revocable)

    token = _token_for(client, "revoke-me", "RevokeMePass1")
    assert client.get("/api/results", headers=_auth_headers(token)).status_code == 200

    revocable.is_active = False
    db_session.commit()

    response = client.get("/api/results", headers=_auth_headers(token))
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# PHI / mutation endpoints anonymous-rejection
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/results"),
        ("GET", "/api/patients/RM-NOPE/history"),
        ("GET", "/api/instruments/status"),
        ("GET", "/api/instruments/1/orders?date_from=2026-01-01T00:00:00&date_to=2026-01-02T00:00:00"),
        ("GET", "/api/orders/1/test-runs"),
        ("POST", "/api/test-runs/1/finalize"),
        ("POST", "/api/test-runs/1/unfinalize"),
        ("POST", "/api/test-runs/1/delivery/start"),
        ("POST", "/api/test-runs/1/delivery/success"),
        ("POST", "/api/test-runs/1/delivery/fail"),
        ("POST", "/api/test-runs/1/sync-simrs"),
        ("POST", "/api/account/change-password"),
        ("GET", "/api/users"),
        ("POST", "/api/users"),
        ("PATCH", "/api/users/1/status"),
    ],
)
def test_phi_and_mutation_endpoints_reject_anonymous_calls(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401, f"{method} {path} was reachable anonymously"


# --------------------------------------------------------------------------- #
# Roles (OD-1 = Option B: ADMIN inherits ANALYST + user management)
# --------------------------------------------------------------------------- #


def test_analyst_can_perform_clinical_mutation(client):
    token = _token_for(client, "analyst1", ANALYST_PASSWORD)
    # finalize on a run that does not exist still proves the role check
    # passes (403 would mean rejected-by-role; 404 means it reached the
    # service layer, i.e. authorization succeeded).
    response = client.post("/api/test-runs/999999/finalize", headers=_auth_headers(token))
    assert response.status_code == 404


def test_admin_inherits_analyst_clinical_capability(client):
    token = _token_for(client, "admin1", ADMIN_PASSWORD)
    response = client.post("/api/test-runs/999999/finalize", headers=_auth_headers(token))
    assert response.status_code == 404  # not 403 — ADMIN is not excluded


def test_analyst_cannot_manage_users(client):
    token = _token_for(client, "analyst1", ANALYST_PASSWORD)
    response = client.get("/api/users", headers=_auth_headers(token))
    assert response.status_code == 403


def test_admin_can_list_users_without_password_hash(client):
    token = _token_for(client, "admin1", ADMIN_PASSWORD)
    response = client.get("/api/users", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 2
    for user in body:
        assert "password_hash" not in user
        assert "password" not in user


def test_admin_can_create_user(client):
    token = _token_for(client, "admin1", ADMIN_PASSWORD)
    response = client.post(
        "/api/users",
        headers=_auth_headers(token),
        json={
            "username": "new-analyst",
            "nama_lengkap": "New Analyst",
            "password": "NewAnalystPass1",
            "role": "ANALYST",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "new-analyst"
    assert body["is_active"] is True
    assert "password_hash" not in body


def test_admin_create_user_duplicate_username_rejected(client):
    token = _token_for(client, "admin1", ADMIN_PASSWORD)
    response = client.post(
        "/api/users",
        headers=_auth_headers(token),
        json={
            "username": "analyst1",
            "nama_lengkap": "Duplicate",
            "password": "DuplicatePass1",
            "role": "ANALYST",
        },
    )
    assert response.status_code == 409


def test_admin_create_user_weak_password_rejected(client):
    token = _token_for(client, "admin1", ADMIN_PASSWORD)
    response = client.post(
        "/api/users",
        headers=_auth_headers(token),
        json={
            "username": "weak-pw-user",
            "nama_lengkap": "Weak Pw",
            "password": "short",
            "role": "ANALYST",
        },
    )
    assert response.status_code == 422


def test_analyst_cannot_create_user(client):
    token = _token_for(client, "analyst1", ANALYST_PASSWORD)
    response = client.post(
        "/api/users",
        headers=_auth_headers(token),
        json={
            "username": "should-not-be-created",
            "nama_lengkap": "Nope",
            "password": "ShouldNotWork1",
            "role": "ANALYST",
        },
    )
    assert response.status_code == 403


def test_admin_can_disable_a_user(client, db_session):
    token = _token_for(client, "admin1", ADMIN_PASSWORD)
    target = db_session.scalar(select(User).where(User.username == "analyst1"))
    response = client.patch(
        f"/api/users/{target.id_user}/status",
        headers=_auth_headers(token),
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # restore for any later test in this module
    client.patch(
        f"/api/users/{target.id_user}/status",
        headers=_auth_headers(token),
        json={"is_active": True},
    )


def test_disabled_analyst_can_be_reactivated(client, db_session):
    """Reactivation is deliberately unguarded — it can only ever restore
    access, never remove it."""
    token = _token_for(client, "admin1", ADMIN_PASSWORD)
    target = db_session.scalar(select(User).where(User.username == "analyst1"))

    disabled = client.patch(
        f"/api/users/{target.id_user}/status",
        headers=_auth_headers(token),
        json={"is_active": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    # the account really is revoked while disabled
    assert _login(client, "analyst1", ANALYST_PASSWORD).status_code == 401

    restored = client.patch(
        f"/api/users/{target.id_user}/status",
        headers=_auth_headers(token),
        json={"is_active": True},
    )
    assert restored.status_code == 200
    assert restored.json()["is_active"] is True
    assert _login(client, "analyst1", ANALYST_PASSWORD).status_code == 200


# --------------------------------------------------------------------------- #
# Last-admin safety (M9.1a review finding M-3)
# --------------------------------------------------------------------------- #


def test_admin_cannot_disable_itself(client, db_session):
    token = _token_for(client, "admin1", ADMIN_PASSWORD)
    me = db_session.scalar(select(User).where(User.username == "admin1"))

    response = client.patch(
        f"/api/users/{me.id_user}/status",
        headers=_auth_headers(token),
        json={"is_active": False},
    )
    assert response.status_code == 409

    db_session.refresh(me)
    assert me.is_active is True, "a rejected self-disable must not have taken effect"


def test_admin_can_disable_another_admin_when_one_remains(client, db_session):
    token = _token_for(client, "admin1", ADMIN_PASSWORD)

    created = client.post(
        "/api/users",
        headers=_auth_headers(token),
        json={
            "username": "second-admin",
            "nama_lengkap": "Second Admin",
            "password": "SecondAdminPass1",
            "role": "ADMIN",
        },
    )
    assert created.status_code == 201
    second_admin_id = created.json()["id_user"]

    try:
        response = client.patch(
            f"/api/users/{second_admin_id}/status",
            headers=_auth_headers(token),
            json={"is_active": False},
        )
        assert response.status_code == 200, response.text
        assert response.json()["is_active"] is False
    finally:
        target = db_session.get(User, second_admin_id)
        if target is not None:
            db_session.delete(target)
            db_session.commit()


def test_guard_blocks_disabling_the_last_active_admin(db_session):
    """Direct test of the guard itself.

    The self-disable rule makes this condition unreachable through the API
    today (the caller is necessarily an active ADMIN and cannot be the
    target, so one always remains). The guard is defence in depth, so it is
    tested where it can actually be reached — if the self-disable rule is
    ever relaxed, this is what still prevents a full lockout.
    """
    sole_admin = db_session.scalar(select(User).where(User.username == "admin1"))
    analyst = db_session.scalar(select(User).where(User.username == "analyst1"))

    # admin1 is the only ADMIN in this module's fixture data.
    assert would_leave_no_active_admin(db_session, sole_admin) is True
    # An analyst is never the last admin.
    assert would_leave_no_active_admin(db_session, analyst) is False

    second = User(
        username="guard-check-admin",
        nama_lengkap="Guard Check Admin",
        password_hash=hash_password("GuardCheckPass1"),
        role="ADMIN",
        is_active=True,
    )
    db_session.add(second)
    db_session.commit()
    try:
        # With a second active ADMIN present, neither is the last one.
        assert would_leave_no_active_admin(db_session, sole_admin) is False
        assert would_leave_no_active_admin(db_session, second) is False

        # An ADMIN that is already inactive cannot reduce the active count.
        second.is_active = False
        db_session.commit()
        assert would_leave_no_active_admin(db_session, second) is False
        assert would_leave_no_active_admin(db_session, sole_admin) is True
    finally:
        db_session.delete(second)
        db_session.commit()


# --------------------------------------------------------------------------- #
# Role is read from the live user row, never from the token (design §6.3)
# --------------------------------------------------------------------------- #


def test_forged_admin_role_claim_does_not_grant_admin_access(client, db_session):
    """T-1 regression guard.

    A validly signed token for an ANALYST, with ``role: "ADMIN"`` injected
    into the payload, must not reach an ADMIN-only endpoint. Authorization
    resolves the role from the live ``User`` row, so the claim is inert —
    this test fails the moment anyone "optimises" that into reading the
    token instead.
    """
    analyst = db_session.scalar(select(User).where(User.username == "analyst1"))
    now = datetime.datetime.now(datetime.timezone.utc)

    forged = jwt.encode(
        {
            "sub": str(analyst.id_user),
            "iat": now,
            "exp": now + datetime.timedelta(minutes=5),
            "role": "ADMIN",  # attacker-supplied, correctly signed, must be ignored
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    # The token itself is valid — it authenticates fine on a normal endpoint.
    assert client.get("/api/results", headers=_auth_headers(forged)).status_code == 200

    # ...but the injected role buys nothing.
    forged_response = client.get("/api/users", headers=_auth_headers(forged))
    assert forged_response.status_code == 403, (
        "role must come from the database row, not the JWT claim"
    )

    # Contrast: a genuine ADMIN, whose token carries no role claim at all,
    # does succeed on the same endpoint.
    admin_token = _token_for(client, "admin1", ADMIN_PASSWORD)
    assert "role" not in jwt.decode(
        admin_token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    assert client.get("/api/users", headers=_auth_headers(admin_token)).status_code == 200


# --------------------------------------------------------------------------- #
# Self-service password change (OD-S4)
# --------------------------------------------------------------------------- #


def test_change_password_requires_current_password(client, db_session):
    user = User(
        username="pwchange-1",
        nama_lengkap="Password Change",
        password_hash=hash_password("OriginalPass123"),
        role="ANALYST",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    token = _token_for(client, "pwchange-1", "OriginalPass123")

    wrong = client.post(
        "/api/account/change-password",
        headers=_auth_headers(token),
        json={"current_password": "wrong-current", "new_password": "BrandNewPass123"},
    )
    assert wrong.status_code == 401

    weak = client.post(
        "/api/account/change-password",
        headers=_auth_headers(token),
        json={"current_password": "OriginalPass123", "new_password": "short"},
    )
    assert weak.status_code == 422

    ok = client.post(
        "/api/account/change-password",
        headers=_auth_headers(token),
        json={"current_password": "OriginalPass123", "new_password": "BrandNewPass123"},
    )
    assert ok.status_code == 204

    # old password no longer works; new one does
    assert _login(client, "pwchange-1", "OriginalPass123").status_code == 401
    assert _login(client, "pwchange-1", "BrandNewPass123").status_code == 200


def test_change_password_requires_authentication(client):
    response = client.post(
        "/api/account/change-password",
        json={"current_password": "x", "new_password": "BrandNewPass123"},
    )
    assert response.status_code == 401
