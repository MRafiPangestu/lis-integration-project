"""M9.0 — automated migration-chain integration test.

Turns the previously ad-hoc Phase 2D / Phase 3A validation into a
repository-resident test: it provisions a **disposable** PostgreSQL database
from empty using the real Alembic environment (``python -m alembic upgrade``),
then asserts the resulting revision and structural schema invariants.

Scope: upgrade / provisioning, plus the one downgrade M9.1a adds.

* This is NOT a general downgrade test. ``b1f9dbe772fa.downgrade()`` is a
  known separate defect (unnamed-FK drops), still untested here; R0 downgrade
  was validated separately in scratch. ``27e00bcff992`` (M9.1a ``users``) is
  the one exception — its downgrade is real and is exercised below.
* This test does NOT create, fix or assert-away F-2
  (``UNIQUE(patients.nomor_rm)``). It asserts F-2 stays **absent**, documenting
  that the chain reproduces the fresh-install schema minus that pending
  remediation.

Safety: every write-capable operation targets only a uniquely generated
``zz_m90_test_<hex>`` database. The four project databases (and the postgres /
template databases) are on a hard deny-list; the stable PoC name is never used
as a target or a fallback. The scratch database is dropped in teardown even on
failure.

If a PostgreSQL server that accepts ``CREATE DATABASE`` is not reachable the
tests **skip with an explicit reason** (they never pass silently). In this
project's environment PostgreSQL is available and the tests run for real.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Iterator

import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from app.core.config import settings

# --------------------------------------------------------------------------- #
# Paths / connection
# --------------------------------------------------------------------------- #

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_DIR = BACKEND_DIR / "alembic"

PG = dict(
    host=settings.DB_HOST,
    port=settings.DB_PORT,
    user=settings.DB_USER,
    password=settings.DB_PASSWORD,
)

# --------------------------------------------------------------------------- #
# Migration-graph source of truth
# --------------------------------------------------------------------------- #

R0 = "8e973e84a9d7"
HEAD = "27e00bcff992"
EXPECTED_CHAIN = [
    R0,
    "b1f9dbe772fa",
    "4a24240f8c32",
    "621889e316b5",
    "c5465739f048",
    "4aff9e134f16",
    HEAD,
]

# --------------------------------------------------------------------------- #
# Database-name safety guard
# --------------------------------------------------------------------------- #

_SCRATCH_RE = re.compile(r"^zz_m90_test_[a-z0-9_]+$")
_DENY = frozenset(
    {
        "lis_marina_permata",
        "lis_marina_permata_dev",
        "lis_marina_permata_test",
        "lis_marina_permata_migration_test",
        "postgres",
        "template0",
        "template1",
    }
)


def _assert_scratch_name(name: str) -> None:
    """Fail hard unless *name* is a disposable migration-test database."""
    if name in _DENY:
        raise AssertionError(f"REFUSED: {name!r} is a protected database")
    if "lis_marina_permata" in name:
        raise AssertionError(f"REFUSED: {name!r} contains a project DB prefix")
    if not _SCRATCH_RE.match(name):
        raise AssertionError(
            f"REFUSED: {name!r} does not match {_SCRATCH_RE.pattern}"
        )


def _new_scratch_name() -> str:
    name = f"zz_m90_test_{uuid.uuid4().hex[:16]}"
    _assert_scratch_name(name)
    return name


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #


def _admin_connection() -> psycopg2.extensions.connection:
    """Autocommit connection to the ``postgres`` maintenance database.

    Never used as a migration target — only to CREATE / DROP scratch databases.
    """
    conn = psycopg2.connect(dbname="postgres", **PG)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def _database_exists(name: str) -> bool:
    conn = _admin_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def _create_scratch_database(name: str) -> None:
    _assert_scratch_name(name)
    conn = _admin_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            if cur.fetchone() is not None:
                raise AssertionError(f"scratch database {name!r} already exists")
            cur.execute(
                sql.SQL(
                    "CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'"
                ).format(sql.Identifier(name))
            )
    finally:
        conn.close()


def _drop_scratch_database(name: str) -> None:
    """Drop *name*. Refuses any non-scratch target."""
    _assert_scratch_name(name)
    conn = _admin_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (name,),
            )
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name))
            )
    finally:
        conn.close()


def _run_alembic(db_name: str, *args: str) -> subprocess.CompletedProcess:
    """Run the real Alembic CLI against *db_name* in a controlled environment.

    The scratch database name is injected via ``DB_NAME`` (the project's
    documented override); ``alembic/env.py`` builds ``settings.database_url``
    from it. The application's default database cannot leak in because a fresh
    interpreter reads the override before ``app.core.config`` is imported.
    """
    _assert_scratch_name(db_name)
    env = dict(os.environ)
    env["DB_NAME"] = db_name
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


def _alembic_or_fail(db_name: str, *args: str) -> subprocess.CompletedProcess:
    proc = _run_alembic(db_name, *args)
    if proc.returncode != 0:
        raise AssertionError(
            f"`alembic {' '.join(args)}` failed against {db_name} "
            f"(exit {proc.returncode})\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}"
        )
    return proc


# --------------------------------------------------------------------------- #
# Read-only schema introspection
# --------------------------------------------------------------------------- #


class SchemaSnapshot:
    """Structural facts about the ``public`` schema of one database.

    ``alembic_version`` bookkeeping is excluded from the object collections and
    counts; its presence and content are exposed separately.
    """

    _BOOKKEEPING = "alembic_version"

    def __init__(self, db_name: str) -> None:
        _assert_scratch_name(db_name)
        conn = psycopg2.connect(dbname=db_name, **PG)
        conn.set_session(readonly=True, autocommit=True)
        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """
            )
            all_tables = {r[0] for r in cur.fetchall()}
            self.has_alembic_version = self._BOOKKEEPING in all_tables
            self.tables = all_tables - {self._BOOKKEEPING}

            self.alembic_version: str | None = None
            if self.has_alembic_version:
                cur.execute("SELECT version_num FROM alembic_version")
                rows = [r[0] for r in cur.fetchall()]
                assert len(rows) == 1, f"alembic_version rows: {rows}"
                self.alembic_version = rows[0]

            cur.execute(
                """
                SELECT table_name, column_name, is_nullable, data_type,
                       character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'public'
                """
            )
            # {(table, column): {"nullable": bool, "type": str, "len": int|None}}
            self.columns: dict[tuple[str, str], dict] = {}
            for tn, cn, nullable, dtype, clen in cur.fetchall():
                if tn == self._BOOKKEEPING:
                    continue
                self.columns[(tn, cn)] = {
                    "nullable": nullable == "YES",
                    "type": dtype,
                    "len": clen,
                }

            cur.execute(
                """
                SELECT c.conname, t.relname, c.contype,
                       pg_get_constraintdef(c.oid, true)
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public' AND c.contype IN ('p', 'u', 'f', 'c')
                """
            )
            # list of (name, table, type, definition)
            self.constraints = [
                row for row in cur.fetchall() if row[1] != self._BOOKKEEPING
            ]

            cur.execute(
                """
                SELECT t.relname, i.relname, ix.indisunique,
                       pg_get_indexdef(ix.indexrelid, 0, true)
                FROM pg_index ix
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_class t ON t.oid = ix.indrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                """
            )
            self.indexes = [
                row for row in cur.fetchall() if row[0] != self._BOOKKEEPING
            ]

            cur.execute(
                """
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'S'
                """
            )
            self.sequences = {r[0] for r in cur.fetchall()}

            cur.close()
        finally:
            conn.close()

    # -- convenience views -------------------------------------------------- #

    def constraint_names(self) -> set[str]:
        return {c[0] for c in self.constraints}

    def index_names(self) -> set[str]:
        return {i[1] for i in self.indexes}

    def count(self, contype: str) -> int:
        return sum(1 for c in self.constraints if c[2] == contype)

    def not_null_columns(self) -> set[tuple[str, str]]:
        return {k for k, v in self.columns.items() if not v["nullable"]}

    def unique_constraint_columns(self) -> list[tuple[str, str]]:
        """(table, definition) for every UNIQUE constraint."""
        return [(c[1], c[3]) for c in self.constraints if c[2] == "u"]


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


_PG_CAPABILITY: bool | None = None


def _require_postgres() -> None:
    """Skip (loudly, with a reason) unless we can actually CREATE / DROP a DB.

    Probes the full capability once per session: connect to the maintenance
    database and create + drop a throwaway ``zz_m90_test_*`` database. Any
    failure — server down, auth, missing ``CREATEDB`` privilege — skips rather
    than errors, so the suite still runs in an environment without a usable
    PostgreSQL server. It never passes silently: the skip reason is explicit.
    """
    global _PG_CAPABILITY
    if _PG_CAPABILITY is True:
        return
    if _PG_CAPABILITY is False:
        pytest.skip("PostgreSQL CREATE DATABASE capability unavailable (see first skip)")

    probe = _new_scratch_name()
    created = False
    try:
        _create_scratch_database(probe)
        created = True
    except psycopg2.Error as exc:  # pragma: no cover - environment dependent
        _PG_CAPABILITY = False
        pytest.skip(
            "M9.0 migration-chain integration test needs a live PostgreSQL "
            "server that accepts CREATE DATABASE at "
            f"{PG['host']}:{PG['port']} as user {PG['user']!r}. "
            f"Capability probe failed: {exc!r}"
        )
    finally:
        if created:
            try:
                _drop_scratch_database(probe)
            except psycopg2.Error:  # pragma: no cover
                pass
    _PG_CAPABILITY = True


def _provision(name: str, target: str) -> None:
    """Create *name* empty and run ``alembic upgrade <target>`` against it."""
    _create_scratch_database(name)
    assert _database_exists(name)
    pre = SchemaSnapshot(name)
    assert pre.tables == set(), f"scratch DB not empty: {pre.tables}"
    assert not pre.has_alembic_version

    _alembic_or_fail(name, "upgrade", target)

    reported = _alembic_or_fail(name, "current").stdout
    expected = HEAD if target == "head" else target
    assert expected in reported, (
        f"`alembic current` did not report {expected}:\n{reported}"
    )


@pytest.fixture(scope="module")
def scratch_at_head() -> Iterator[str]:
    """A fresh scratch DB provisioned from empty with ``alembic upgrade head``."""
    _require_postgres()
    name = _new_scratch_name()
    try:
        _provision(name, "head")
        yield name
    finally:
        _drop_scratch_database(name)  # DROP DATABASE IF EXISTS — safe if never created
        assert not _database_exists(name), (
            f"CLEANUP FAILED — scratch database {name} still exists; "
            "no other database was touched"
        )


@pytest.fixture(scope="module")
def scratch_at_r0() -> Iterator[str]:
    """A fresh scratch DB provisioned from empty with ``alembic upgrade <R0>``."""
    _require_postgres()
    name = _new_scratch_name()
    try:
        _provision(name, R0)
        yield name
    finally:
        _drop_scratch_database(name)
        assert not _database_exists(name), (
            f"CLEANUP FAILED — scratch database {name} still exists; "
            "no other database was touched"
        )


# --------------------------------------------------------------------------- #
# 1. Migration graph (no database required)
# --------------------------------------------------------------------------- #


def _script_directory():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    return ScriptDirectory.from_config(cfg)


def test_migration_graph_is_linear_single_root_single_head() -> None:
    script = _script_directory()

    assert list(script.get_bases()) == [R0], script.get_bases()
    assert list(script.get_heads()) == [HEAD], script.get_heads()

    revs = {r.revision: r for r in script.walk_revisions()}
    assert set(revs) == set(EXPECTED_CHAIN)

    # exactly one child per revision (no branch), and no cycle (walk terminates)
    order: list[str] = []
    node: str | None = R0
    while node is not None:
        order.append(node)
        children = [
            r.revision for r in revs.values() if r.down_revision == node
        ]
        assert len(children) <= 1, f"branch at {node}: {children}"
        node = children[0] if children else None

    assert order == EXPECTED_CHAIN, order
    assert revs[R0].down_revision is None
    assert revs["b1f9dbe772fa"].down_revision == R0


# --------------------------------------------------------------------------- #
# 2. Fresh install reaches head with the expected schema
# --------------------------------------------------------------------------- #

_FINAL_TABLES = {
    "doctors",
    "instrument_messages",
    "instruments",
    "orders",
    "patients",
    "results",
    "test_groups",
    "test_runs",
    "tests",
    "units",
    "users",
    "visits",
}
_FINAL_SEQUENCES = {f"{t}_id_{c}_seq" for t, c in [
    ("doctors", "dokter"),
    ("instrument_messages", "message"),
    ("instruments", "instrument"),
    ("orders", "order"),
    ("patients", "pasien"),
    ("results", "hasil"),
    ("test_groups", "group"),
    ("test_runs", "run"),
    ("tests", "test"),
    ("units", "unit"),
    ("users", "user"),
    ("visits", "visit"),
]}
_M8_4_INDEXES = {
    "ix_test_runs_id_instrument_id_order",
    "ix_orders_id_visit",
    "ix_visits_id_pasien",
    "ix_orders_waktu_order_id_order",
}
# columns that M1 removes from the legacy schema — must be gone at head
_M1_REMOVED_COLUMNS = {
    ("orders", "no_registrasi"),
    ("orders", "id_pasien"),
    ("results", "id_order"),
    ("results", "id_instrument"),
    ("results", "id_message"),
    ("results", "status_hasil"),
    ("results", "divalidasi_oleh"),
    ("results", "waktu_validasi"),
}


def test_fresh_install_reaches_head_revision(scratch_at_head: str) -> None:
    snap = SchemaSnapshot(scratch_at_head)
    assert snap.has_alembic_version
    assert snap.alembic_version == HEAD


def test_fresh_install_table_and_sequence_inventory(scratch_at_head: str) -> None:
    snap = SchemaSnapshot(scratch_at_head)
    assert snap.tables == _FINAL_TABLES
    assert snap.sequences == _FINAL_SEQUENCES  # 9 legacy + visits + test_runs


def test_fresh_install_constraint_and_index_counts(scratch_at_head: str) -> None:
    snap = SchemaSnapshot(scratch_at_head)
    # counts exclude the alembic_version bookkeeping table.
    # M9.1a (27e00bcff992) adds exactly one table (`users`): +1 PK, +1 UNIQUE
    # (username), +0 FK, +0 CHECK, +7 NOT NULL columns (id_user, username,
    # nama_lengkap, password_hash, role, is_active, created_at —
    # last_login_at is nullable), +2 indexes (users_pkey, users_username_key).
    # Numbers below are measured against the real migration output on a
    # throwaway scratch database, not estimated.
    assert snap.count("p") == 12
    assert snap.count("u") == 6
    assert snap.count("f") == 10
    assert snap.count("c") == 0
    assert len(snap.not_null_columns()) == 48
    assert len(snap.index_names()) == 23


def test_fresh_install_has_m1_m82_m84_objects(scratch_at_head: str) -> None:
    snap = SchemaSnapshot(scratch_at_head)

    # M1 structural additions
    assert {"visits", "test_runs"} <= snap.tables
    assert ("results", "id_run") in snap.columns
    assert ("orders", "id_visit") in snap.columns
    assert ("instrument_messages", "error_detail") in snap.columns
    assert {"uk_run_parameter", "uk_order_run_sequence"} <= snap.constraint_names()
    assert "idx_unique_final_run_per_order" in snap.index_names()

    # 621889e316b5 — instrument runtime status
    assert ("instruments", "connection_status") in snap.columns
    assert ("instruments", "last_status_at") in snap.columns

    # c5465739f048 — M8.2 message classification
    assert ("instrument_messages", "message_class") in snap.columns
    assert ("instrument_messages", "classification_rule") in snap.columns

    # 4aff9e134f16 — the four M8.4 query indexes
    assert _M8_4_INDEXES <= snap.index_names()

    # 27e00bcff992 — M9.1a users table (hand-authored, not autogenerated —
    # design doc §10.4). No FK: users is standalone, not clinical data.
    assert "users" in snap.tables
    for column in (
        "id_user", "username", "nama_lengkap", "password_hash",
        "role", "is_active", "created_at", "last_login_at",
    ):
        assert ("users", column) in snap.columns, f"users.{column} missing"
    assert snap.columns[("users", "last_login_at")]["nullable"] is True
    for column in ("id_user", "username", "nama_lengkap", "password_hash", "role", "is_active", "created_at"):
        assert snap.columns[("users", column)]["nullable"] is False, f"users.{column} should be NOT NULL"
    assert "users_username_key" in snap.constraint_names()
    assert not any(c[1] == "users" and c[2] == "f" for c in snap.constraints), (
        "users must have no foreign keys — it is Workflow Metadata, not Clinical Data"
    )
    assert not any(c[1] == "users" and c[2] == "c" for c in snap.constraints), (
        "role is an app-level enum (VARCHAR), not a DB CHECK constraint — design §8.2"
    )


def test_fresh_install_dropped_legacy_columns(scratch_at_head: str) -> None:
    snap = SchemaSnapshot(scratch_at_head)
    present = _M1_REMOVED_COLUMNS & set(snap.columns)
    assert not present, f"columns M1 should have removed are still present: {present}"


# --------------------------------------------------------------------------- #
# 3. F-2 stays intentionally absent  (this test must NOT fix F-2)
# --------------------------------------------------------------------------- #


def _nomor_rm_is_unique(snap: SchemaSnapshot) -> bool:
    for table, definition in snap.unique_constraint_columns():
        if table == "patients" and "nomor_rm" in definition:
            return True
    for table, index_name, is_unique, definition in snap.indexes:
        if table == "patients" and is_unique and "nomor_rm" in definition:
            if index_name != "patients_pkey":
                return True
    return False


def test_f2_absent_at_head(scratch_at_head: str) -> None:
    snap = SchemaSnapshot(scratch_at_head)
    col = snap.columns[("patients", "nomor_rm")]
    assert col["nullable"] is False, "patients.nomor_rm must be NOT NULL"
    assert not _nomor_rm_is_unique(snap), (
        "patients.nomor_rm is UNIQUE — F-2 must remain a separate remediation, "
        "not introduced by the migration chain"
    )
    assert "patients_nomor_rm_key" not in snap.constraint_names()
    assert "patients_nomor_rm_key" not in snap.index_names()


def test_users_migration_downgrade_drops_users_cleanly(scratch_at_head: str) -> None:
    """Unlike ``b1f9dbe772fa``'s known-broken downgrade (F-4, a separate
    defect), ``27e00bcff992``'s downgrade is exercised here: it must remove
    ``users`` and nothing else, and upgrading back to head must be
    idempotent. Placed last among the ``scratch_at_head`` tests — it is the
    only one that mutates the shared module-scoped fixture database."""
    before = SchemaSnapshot(scratch_at_head)
    assert "users" in before.tables

    _alembic_or_fail(scratch_at_head, "downgrade", "4aff9e134f16")
    mid = SchemaSnapshot(scratch_at_head)
    assert "users" not in mid.tables
    assert mid.tables == before.tables - {"users"}
    assert mid.alembic_version == "4aff9e134f16"

    # Restore head so the fixture is unchanged for any later test — none use
    # it today (it is module-scoped and this is declared last), but a future
    # addition must not silently inherit a downgraded database.
    _alembic_or_fail(scratch_at_head, "upgrade", "head")
    after = SchemaSnapshot(scratch_at_head)
    assert after.tables == before.tables
    assert after.alembic_version == HEAD


# --------------------------------------------------------------------------- #
# 4. R0 alone is the pre-M1 legacy baseline
# --------------------------------------------------------------------------- #

_R0_TABLES = {
    "doctors",
    "instrument_messages",
    "instruments",
    "orders",
    "patients",
    "results",
    "test_groups",
    "tests",
    "units",
}
_R0_LEGACY_ONLY_COLUMNS = {
    ("orders", "no_registrasi"),
    ("orders", "id_pasien"),
    ("results", "id_order"),
    ("results", "id_instrument"),
    ("results", "id_message"),
    ("results", "status_hasil"),
    ("results", "divalidasi_oleh"),
    ("results", "waktu_validasi"),
}
_R0_MUST_BE_ABSENT_TABLES = {"visits", "test_runs"}
_R0_MUST_BE_ABSENT_COLUMNS = {
    ("results", "id_run"),
    ("orders", "id_visit"),
    ("instrument_messages", "error_detail"),
    ("instruments", "connection_status"),
    ("instruments", "last_status_at"),
    ("instrument_messages", "message_class"),
    ("instrument_messages", "classification_rule"),
}
_R0_MUST_BE_ABSENT_CONSTRAINTS = {"uk_run_parameter", "uk_order_run_sequence"}
_R0_MUST_BE_ABSENT_INDEXES = {"idx_unique_final_run_per_order"} | _M8_4_INDEXES


def test_r0_only_revision(scratch_at_r0: str) -> None:
    snap = SchemaSnapshot(scratch_at_r0)
    assert snap.has_alembic_version
    assert snap.alembic_version == R0


def test_r0_only_legacy_inventory(scratch_at_r0: str) -> None:
    snap = SchemaSnapshot(scratch_at_r0)
    assert snap.tables == _R0_TABLES
    assert len(snap.sequences) == 9
    assert snap.count("p") == 9
    assert snap.count("u") == 4
    assert snap.count("f") == 8
    assert snap.count("c") == 0
    assert len(snap.not_null_columns()) == 21
    assert len(snap.index_names()) == 13  # PK/UNIQUE backing only


def test_r0_only_keeps_legacy_columns(scratch_at_r0: str) -> None:
    snap = SchemaSnapshot(scratch_at_r0)
    missing = _R0_LEGACY_ONLY_COLUMNS - set(snap.columns)
    assert not missing, f"R0 dropped legacy columns it must keep: {missing}"


def test_r0_only_has_no_m1_or_later_objects(scratch_at_r0: str) -> None:
    snap = SchemaSnapshot(scratch_at_r0)
    assert not (_R0_MUST_BE_ABSENT_TABLES & snap.tables)
    assert not (_R0_MUST_BE_ABSENT_COLUMNS & set(snap.columns))
    assert not (_R0_MUST_BE_ABSENT_CONSTRAINTS & snap.constraint_names())
    assert not (_R0_MUST_BE_ABSENT_INDEXES & snap.index_names())


def test_r0_only_f2_absent(scratch_at_r0: str) -> None:
    snap = SchemaSnapshot(scratch_at_r0)
    assert snap.columns[("patients", "nomor_rm")]["nullable"] is False
    assert not _nomor_rm_is_unique(snap)
    assert "patients_nomor_rm_key" not in snap.constraint_names()
    assert "patients_nomor_rm_key" not in snap.index_names()
