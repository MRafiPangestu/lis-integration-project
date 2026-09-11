"""M9.1a — first-admin bootstrap (scripts/create_admin.py).

Tests the extracted database logic directly (``create_admin_user`` /
``abort_if_stable_poc``), bypassing ``getpass`` — on Windows, ``getpass``
reads from the console directly (``msvcrt``) and ignores redirected stdin,
so the interactive prompt itself cannot be driven from an automated test.
PostgreSQL-only, against ``lis_marina_permata_test``.
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.base import Base
from app.models.user import User
from scripts.create_admin import STABLE_POC_DB, CreateAdminError, abort_if_stable_poc, create_admin_user

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = TestingSessionLocal()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(bind=engine)


def test_abort_if_stable_poc_refuses_the_stable_poc_name():
    with pytest.raises(CreateAdminError):
        abort_if_stable_poc(STABLE_POC_DB)


def test_abort_if_stable_poc_allows_dev_and_test_names():
    abort_if_stable_poc("lis_marina_permata_dev")
    abort_if_stable_poc("lis_marina_permata_test")


def test_create_admin_user_creates_an_admin(session):
    user = create_admin_user(
        session, username="first-admin", nama_lengkap="First Admin", password="FirstAdminPass1"
    )
    assert user.id_user is not None
    assert user.role == "ADMIN"
    assert user.is_active is True
    assert user.password_hash != "FirstAdminPass1"  # never stored in plaintext


def test_create_admin_user_refuses_a_second_admin_without_force(session):
    create_admin_user(session, "admin-one", "Admin One", "AdminOnePass1")
    with pytest.raises(CreateAdminError, match="already exists"):
        create_admin_user(session, "admin-two", "Admin Two", "AdminTwoPass1")


def test_create_admin_user_allows_a_second_admin_with_force(session):
    create_admin_user(session, "admin-one", "Admin One", "AdminOnePass1")
    second = create_admin_user(
        session, "admin-two", "Admin Two", "AdminTwoPass1", force=True
    )
    assert second.role == "ADMIN"


def test_create_admin_user_refuses_duplicate_username(session):
    create_admin_user(session, "dupe", "Dupe", "DupePassword1")
    with pytest.raises(CreateAdminError, match="already taken"):
        create_admin_user(session, "dupe", "Dupe Again", "DupePassword2", force=True)


def test_create_admin_user_enforces_password_policy(session):
    with pytest.raises(Exception):  # HTTPException(422) from validate_password_policy
        create_admin_user(session, "weak-pw-admin", "Weak", "short")
