"""First-admin bootstrap (M9.1a, design doc §11).

Interactive CLI only. Never a migration, never an application-startup
auto-create — either would install a known credential on every deployment
(design §11.2). With no admin, the system is correctly, visibly locked: no
one can log in until an operator runs this.

Usage:
    py scripts/create_admin.py --username <name>
    py scripts/create_admin.py --username <name> --force   # allow a second admin

The password is never accepted as a CLI argument or environment variable —
only via an interactive, unechoed getpass prompt, confirmed twice.
"""
import argparse
import getpass
import sys
from pathlib import Path

# Add backend directory to PYTHONPATH so imports work, mirroring
# scripts/seed_master_data.py.
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import Role, hash_password, validate_password_policy
from app.models.user import User

# DATABASE SAFETY CHECK
#
# Unlike seed_master_data.py (strictly dev-only master data), this script is
# meant to run on every real deployment path: fresh install, legacy
# stamp-then-upgrade, and existing dev (04_DATABASE_DESIGN.md §29.1-29.3).
# The one database it must NEVER touch is the stable PoC — it is not in the
# migration lifecycle and this bootstrap has no business writing to it.
STABLE_POC_DB = "lis_marina_permata"


class CreateAdminError(Exception):
    """A known, expected abort condition (not a bug) — the CLI prints
    ``str(exc)`` and exits non-zero; a test can assert on it directly."""


def abort_if_stable_poc(db_name: str) -> None:
    if db_name == STABLE_POC_DB:
        raise CreateAdminError(
            f"ABORT: active database is '{db_name}'. create_admin.py must never run "
            f"against the stable PoC database ('{STABLE_POC_DB}') — it is not in the "
            "migration lifecycle (04_DATABASE_DESIGN.md §29.4)."
        )


def create_admin_user(
    session: Session,
    username: str,
    nama_lengkap: str,
    password: str,
    force: bool = False,
) -> User:
    """The database logic, isolated from ``getpass``/``argparse`` so it can
    be exercised directly by tests (``tests/test_create_admin.py``).

    Raises ``CreateAdminError`` for every expected abort condition; never
    silently no-ops and never falls back to a default credential.
    """
    existing_admin = session.scalar(select(User).where(User.role == Role.ADMIN.value))
    if existing_admin is not None and not force:
        raise CreateAdminError(
            f"ABORT: an ADMIN account already exists ('{existing_admin.username}'). "
            "Pass --force to create another one anyway."
        )

    existing_username = session.scalar(select(User).where(User.username == username))
    if existing_username is not None:
        raise CreateAdminError(f"ABORT: username '{username}' is already taken.")

    validate_password_policy(password)

    user = User(
        username=username,
        nama_lengkap=nama_lengkap,
        password_hash=hash_password(password),
        role=Role.ADMIN.value,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise CreateAdminError(
            f"ABORT: could not create user '{username}' (database constraint violation)."
        )

    session.refresh(user)
    return user


def _prompt_password() -> str:
    while True:
        password = getpass.getpass("New admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match. Try again.\n")
            continue
        try:
            validate_password_policy(password)
        except Exception as exc:  # HTTPException from the shared validator
            detail = getattr(exc, "detail", str(exc))
            print(f"{detail}\n")
            continue
        return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first (or an additional) ADMIN user.")
    parser.add_argument("--username", required=True, help="Login username for the new admin.")
    parser.add_argument(
        "--nama-lengkap",
        default=None,
        help="Display name. Defaults to the username if omitted.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Create the admin even if one or more ADMIN accounts already exist.",
    )
    args = parser.parse_args()

    try:
        abort_if_stable_poc(settings.DB_NAME)
    except CreateAdminError as exc:
        print(str(exc))
        sys.exit(1)

    print(f"Target database: {settings.DB_NAME} @ {settings.DB_HOST}:{settings.DB_PORT}")

    with SessionLocal() as session:
        # Fail fast on the two known abort conditions before ever prompting
        # for a password — nothing worse than typing a password twice only
        # to be told the username was taken.
        try:
            existing_admin = session.scalar(select(User).where(User.role == Role.ADMIN.value))
            if existing_admin is not None and not args.force:
                raise CreateAdminError(
                    f"ABORT: an ADMIN account already exists ('{existing_admin.username}'). "
                    "Pass --force to create another one anyway."
                )
            if session.scalar(select(User).where(User.username == args.username)) is not None:
                raise CreateAdminError(f"ABORT: username '{args.username}' is already taken.")
        except CreateAdminError as exc:
            print(str(exc))
            sys.exit(1)

        password = _prompt_password()

        try:
            user = create_admin_user(
                session,
                username=args.username,
                nama_lengkap=args.nama_lengkap or args.username,
                password=password,
                force=args.force,
            )
        except CreateAdminError as exc:
            print(str(exc))
            sys.exit(1)

        print(f"Created ADMIN user '{user.username}' (id_user={user.id_user}).")


if __name__ == "__main__":
    main()
