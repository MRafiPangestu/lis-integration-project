"""M9.0 — automated migration-chain integration test.

Turns the previously ad-hoc Phase 2D / Phase 3A validation into a
repository-resident test: it provisions a **disposable** PostgreSQL database
from empty using the real Alembic environment (``python -m alembic upgrade``),
then asserts the resulting revision and structural schema invariants.

Scope: upgrade / provisioning, plus the downgrades M9.1a, M9.1b, XN-550
Phase 1 and XN-550 G2 add, and ORM/migration parity for the G2 tables.

* This is NOT a general downgrade test. ``b1f9dbe772fa.downgrade()`` is a
  known separate defect (unnamed-FK drops), still untested here; R0 downgrade
  was validated separately in scratch. ``27e00bcff992`` (M9.1a ``users``),
  ``28aa370f5dbe`` (M9.1b ``audit_events``), ``5d2e8b7c41a9`` (XN-550
  Phase 1 raw capture) and ``8a3023944bd1`` (XN-550 G2 unlinked observations)
  are the exceptions — their downgrades are real and are exercised below.
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
M9_1B = "28aa370f5dbe"
XN550_PHASE1 = "5d2e8b7c41a9"
HEAD = "8a3023944bd1"
EXPECTED_CHAIN = [
    R0,
    "b1f9dbe772fa",
    "4a24240f8c32",
    "621889e316b5",
    "c5465739f048",
    "4aff9e134f16",
    "27e00bcff992",
    M9_1B,
    XN550_PHASE1,
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
    "audit_events",
    "doctors",
    "instrument_messages",
    "instrument_result_items",
    "instrument_result_sets",
    "instrument_sessions",
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
    ("audit_events", "audit"),
    ("doctors", "dokter"),
    ("instrument_messages", "message"),
    ("instrument_result_items", "item"),
    ("instrument_result_sets", "result_set"),
    ("instrument_sessions", "session"),
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
_AUDIT_EVENTS_INDEXES = {
    "idx_audit_events_entity",
    "idx_audit_events_actor",
}
_XN550_PHASE1_MESSAGE_COLUMNS = (
    "id_session", "session_message_index", "stream_offset_start", "stream_offset_end",
    "raw_bytes", "raw_sha256", "raw_length", "first_byte_at", "read_count",
    "framing", "parser_key", "parser_version", "duplicate_of_message_id",
)
_XN550_PHASE1_INDEXES = {
    "idx_instrument_sessions_instrument_opened",
    "idx_instrument_messages_instrument_sha256",
    "idx_instrument_messages_instrument_received",
    "idx_instrument_messages_duplicate_of",
}
_XN550_G2_TABLES = {"instrument_result_sets", "instrument_result_items"}
_XN550_G2_INDEX_DEFS = {
    "idx_instrument_result_sets_fingerprint": (
        "(id_instrument, fingerprint_version, analysis_fingerprint, id_result_set)"
    ),
    "idx_instrument_result_sets_received": "(received_at DESC, id_result_set DESC)",
    "idx_instrument_result_sets_instrument_received": "(id_instrument, received_at DESC, id_result_set DESC)",
}
_XN550_G2_CONSTRAINTS = {
    "instrument_result_sets_pkey",
    "uk_instrument_result_sets_id_message",
    "fk_instrument_result_sets_id_message_instrument_messages",
    "fk_instrument_result_sets_id_instrument_instruments",
    "fk_instrument_result_sets_possible_duplicate_of",
    "ck_instrument_result_sets_association_status",
    "ck_instrument_result_sets_duplicate_state",
    "instrument_result_items_pkey",
    "uk_instrument_result_items_set_record",
    "uk_instrument_result_items_set_test_code",
    "fk_instrument_result_items_id_result_set",
    "ck_instrument_result_items_item_kind",
    "ck_instrument_result_items_value_by_kind",
}
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
    # M9.1a (27e00bcff992) added exactly one table (`users`): +1 PK, +1
    # UNIQUE (username), +0 FK, +0 CHECK, +7 NOT NULL columns, +2 indexes.
    # M9.1b (28aa370f5dbe) adds exactly one more table (`audit_events`): +1
    # PK, +0 UNIQUE, +1 FK (id_user -> users.id_user, ON DELETE RESTRICT),
    # +0 CHECK, +8 NOT NULL columns (id_audit, actor_username, actor_role,
    # action, entity_type, entity_id, occurred_at, outcome — id_user,
    # state_before, state_after are nullable), +3 indexes (audit_events_pkey,
    # idx_audit_events_entity, idx_audit_events_actor).
    # XN-550 Phase 1 (5d2e8b7c41a9) adds `instrument_sessions` (+1 PK, +1 FK
    # to instruments, +14 NOT NULL columns, +2 indexes: pkey and
    # idx_instrument_sessions_instrument_opened) and 13 nullable columns on
    # `instrument_messages` (+2 FK, +1 UNIQUE uk_instrument_messages_session_offset
    # with its backing index, +2 CHECK, +3 non-unique indexes).
    # XN-550 G2 (8a3023944bd1) adds `instrument_result_sets` (+1 PK, +1 UNIQUE
    # id_message, +3 FK ON DELETE RESTRICT, +2 CHECK, +16 NOT NULL columns, +5
    # indexes: pkey, the UNIQUE backing index and three non-unique indexes) and
    # `instrument_result_items` (+1 PK, +2 UNIQUE, +1 FK ON DELETE RESTRICT,
    # +2 CHECK, +9 NOT NULL columns, +3 indexes: pkey and two UNIQUE backing
    # indexes; deliberately no separate (id_result_set) index).
    # Numbers below are measured against the real migration output on a
    # throwaway scratch database, not estimated.
    assert snap.count("p") == 16
    assert snap.count("u") == 10
    assert snap.count("f") == 18
    assert snap.count("c") == 6
    assert len(snap.not_null_columns()) == 95
    assert len(snap.index_names()) == 40


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

    # 28aa370f5dbe — M9.1b audit_events table (hand-authored, not
    # autogenerated — design doc §13 item 1, same rule as 27e00bcff992).
    assert "audit_events" in snap.tables
    for column in (
        "id_audit", "id_user", "actor_username", "actor_role", "action",
        "entity_type", "entity_id", "occurred_at", "outcome",
        "state_before", "state_after",
    ):
        assert ("audit_events", column) in snap.columns, f"audit_events.{column} missing"
    for column in ("id_user", "state_before", "state_after"):
        assert snap.columns[("audit_events", column)]["nullable"] is True, (
            f"audit_events.{column} should be nullable"
        )
    for column in (
        "id_audit", "actor_username", "actor_role", "action",
        "entity_type", "entity_id", "occurred_at", "outcome",
    ):
        assert snap.columns[("audit_events", column)]["nullable"] is False, (
            f"audit_events.{column} should be NOT NULL"
        )
    assert _AUDIT_EVENTS_INDEXES <= snap.index_names()
    audit_fks = [c for c in snap.constraints if c[1] == "audit_events" and c[2] == "f"]
    assert len(audit_fks) == 1, f"audit_events should have exactly one FK: {audit_fks}"
    assert "ON DELETE RESTRICT" in audit_fks[0][3], (
        f"audit_events.id_user FK should be ON DELETE RESTRICT: {audit_fks[0][3]}"
    )
    assert not any(c[1] == "audit_events" and c[2] == "c" for c in snap.constraints), (
        "action/entity_type/outcome are app-level enums (VARCHAR), not DB CHECK constraints"
    )
    # entity_id is deliberately not a foreign key (design doc §6.1) — the
    # single FK above must be id_user, not entity_id.
    assert audit_fks[0][0] != "fk_audit_events_entity_id", "entity_id must not become a foreign key"

    # 5d2e8b7c41a9 — XN-550 Phase 1 raw capture (contract §9.1, §9.2).
    assert "instrument_sessions" in snap.tables
    for column in ("closed_at", "close_reason"):
        assert snap.columns[("instrument_sessions", column)]["nullable"] is True
    for column in (
        "id_session", "id_instrument", "transport_mode", "local_address", "local_port",
        "peer_address", "peer_port", "ack_policy", "opened_at", "bytes_received",
        "reads_count", "acks_sent", "messages_completed", "fragments_count",
    ):
        assert snap.columns[("instrument_sessions", column)]["nullable"] is False, column
    for column in _XN550_PHASE1_MESSAGE_COLUMNS:
        assert snap.columns[("instrument_messages", column)]["nullable"] is True, (
            f"instrument_messages.{column} must be nullable (additive, no backfill)"
        )
    assert snap.columns[("instrument_messages", "raw_bytes")]["type"] == "bytea"
    assert snap.columns[("instrument_messages", "raw_sha256")]["len"] == 64
    assert _XN550_PHASE1_INDEXES <= snap.index_names()
    assert {
        "uk_instrument_messages_session_offset",
        "ck_instrument_messages_raw_length",
        "ck_instrument_messages_raw_sha256",
    } <= snap.constraint_names()
    # Byte identity is deliberately NOT unique: same-day retransmissions are
    # byte-identical and every delivery is kept (contract §9.2, §13).
    assert not any(
        table == "instrument_messages" and is_unique and "raw_sha256" in definition
        for table, _, is_unique, definition in snap.indexes
    )
    assert not any(
        table == "instrument_messages" and "raw_sha256" in definition
        for table, definition in snap.unique_constraint_columns()
    )


def test_fresh_install_has_xn550_g2_observation_objects(scratch_at_head: str) -> None:
    """8a3023944bd1: XN-550 G2 unlinked observations (contract §10.2, §10.3)."""
    snap = SchemaSnapshot(scratch_at_head)
    assert _XN550_G2_TABLES <= snap.tables
    for (table, column), info in snap.columns.items():
        if table == "instrument_result_sets":
            assert info["nullable"] is (column == "possible_duplicate_of"), column
        if table == "instrument_result_items":
            nullable = column in {
                "test_code_qualifier", "value_raw", "units_raw", "reference_range_raw", "abnormal_flag_raw",
            }
            assert info["nullable"] is nullable, column
    assert snap.columns[("instrument_result_sets", "sample_label")]["len"] == 100
    assert snap.columns[("instrument_result_sets", "analysis_fingerprint")]["len"] == 64
    assert snap.columns[("instrument_result_sets", "fingerprint_version")]["type"] == "integer"
    assert snap.columns[("instrument_result_items", "source_r_sequence")]["type"] == "integer"

    g2_constraints = {c[0]: c for c in snap.constraints if c[1] in _XN550_G2_TABLES}
    assert set(g2_constraints) == _XN550_G2_CONSTRAINTS
    fks = [c for c in g2_constraints.values() if c[2] == "f"]
    assert len(fks) == 4 and all("ON DELETE RESTRICT" in c[3] for c in fks)
    referenced = {c[3].split("REFERENCES ", 1)[1].split("(", 1)[0] for c in fks}
    assert referenced == {"instrument_messages", "instruments", "instrument_result_sets"}, referenced
    assert "'UNRESOLVED'" in g2_constraints["ck_instrument_result_sets_association_status"][3]
    duplicate_state = g2_constraints["ck_instrument_result_sets_duplicate_state"][3]
    assert "possible_duplicate_of < id_result_set" in duplicate_state
    value_rule = g2_constraints["ck_instrument_result_items_value_by_kind"][3]
    assert "IMAGE_REFERENCE" in value_rule and "value_raw IS NULL" in value_rule

    g2_indexes = {
        name: (unique, definition)
        for table, name, unique, definition in snap.indexes
        if table in _XN550_G2_TABLES
    }
    assert set(g2_indexes) == set(_XN550_G2_INDEX_DEFS) | {
        "instrument_result_sets_pkey", "uk_instrument_result_sets_id_message",
        "instrument_result_items_pkey", "uk_instrument_result_items_set_record",
        "uk_instrument_result_items_set_test_code",
    }
    for name, columns in _XN550_G2_INDEX_DEFS.items():
        unique, definition = g2_indexes[name]
        assert not unique and definition.endswith(columns), (name, definition)
    # contract §12.3 / AC-XN-18: nothing indexes or constrains the display label,
    # and no content column is unique.
    assert not any("sample_label" in definition for _, definition in g2_indexes.values())
    assert not any("sample_label" in c[3] for c in g2_constraints.values())
    for column in ("analysis_fingerprint", "analysis_at", "received_at"):
        assert not any(unique and column in definition for unique, definition in g2_indexes.values()), column


def _scratch_from_orm_models(name: str) -> None:
    """Create *name* and build its schema from the ORM metadata (not Alembic)."""
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    import app.models  # noqa: F401  (registers every model on Base.metadata)
    from app.models.base import Base

    _assert_scratch_name(name)
    _create_scratch_database(name)
    url = URL.create(
        "postgresql", username=PG["user"], password=PG["password"], host=PG["host"], port=PG["port"], database=name,
    )
    orm_engine = create_engine(url)
    try:
        Base.metadata.create_all(bind=orm_engine)
    finally:
        orm_engine.dispose()


def test_xn550_g2_orm_models_match_the_migration_exactly(scratch_at_head: str) -> None:
    """ORM/migration parity for the two G2 tables: columns, constraints (names,
    kinds, definitions) and indexes (names, uniqueness, definitions). Scoped to
    the G2 tables because the known F-2 / F-3 drifts are elsewhere."""
    _require_postgres()
    orm_db = _new_scratch_name()
    try:
        _scratch_from_orm_models(orm_db)
        from_orm = SchemaSnapshot(orm_db)
    finally:
        _drop_scratch_database(orm_db)
    assert not _database_exists(orm_db)
    from_migration = SchemaSnapshot(scratch_at_head)

    def g2_view(snap: SchemaSnapshot):
        return (
            {k: v for k, v in snap.columns.items() if k[0] in _XN550_G2_TABLES},
            {c for c in snap.constraints if c[1] in _XN550_G2_TABLES},
            {i for i in snap.indexes if i[0] in _XN550_G2_TABLES},
        )

    orm_columns, orm_constraints, orm_indexes = g2_view(from_orm)
    mig_columns, mig_constraints, mig_indexes = g2_view(from_migration)
    assert orm_columns and orm_constraints and orm_indexes
    assert orm_columns == mig_columns
    assert orm_constraints == mig_constraints
    assert orm_indexes == mig_indexes


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


def test_xn550_g2_migration_downgrade_removes_only_its_objects(scratch_at_head: str) -> None:
    """``8a3023944bd1``'s downgrade: one step down must remove exactly the two
    G2 tables (with their constraints, indexes and sequences) and nothing else;
    upgrading back to head must restore the same structure. Runs first among the
    downgrade tests (each later one passes through this downgrade)."""
    before = SchemaSnapshot(scratch_at_head)
    assert _XN550_G2_TABLES <= before.tables

    _alembic_or_fail(scratch_at_head, "downgrade", XN550_PHASE1)
    mid = SchemaSnapshot(scratch_at_head)
    assert mid.alembic_version == XN550_PHASE1
    assert mid.tables == before.tables - _XN550_G2_TABLES
    assert set(mid.columns) == {key for key in before.columns if key[0] not in _XN550_G2_TABLES}
    assert mid.sequences == before.sequences - {
        "instrument_result_sets_id_result_set_seq", "instrument_result_items_id_item_seq",
    }
    assert not (_XN550_G2_CONSTRAINTS & mid.constraint_names())
    assert not (set(_XN550_G2_INDEX_DEFS) & mid.index_names())
    # exactly the Phase 1 head numbers
    assert (mid.count("p"), mid.count("u"), mid.count("f"), mid.count("c")) == (14, 7, 14, 2)
    assert len(mid.not_null_columns()) == 70
    assert len(mid.index_names()) == 32

    _alembic_or_fail(scratch_at_head, "upgrade", "head")
    after = SchemaSnapshot(scratch_at_head)
    assert after.alembic_version == HEAD
    assert after.tables == before.tables
    assert after.columns == before.columns
    assert set(after.constraints) == set(before.constraints)
    assert set(after.indexes) == set(before.indexes)


def test_xn550_phase1_migration_downgrade_removes_only_its_objects(scratch_at_head: str) -> None:
    """``5d2e8b7c41a9``'s downgrade is exercised here: one step down must
    remove ``instrument_sessions`` and exactly the 13 added
    ``instrument_messages`` columns, constraints and indexes — nothing else —
    and upgrading back to head must restore the same structure. Downgrading from
    head to ``28aa370f5dbe`` passes through the G2 downgrade first, so the G2
    tables are removed too."""
    before = SchemaSnapshot(scratch_at_head)
    assert "instrument_sessions" in before.tables

    _alembic_or_fail(scratch_at_head, "downgrade", M9_1B)
    mid = SchemaSnapshot(scratch_at_head)
    assert mid.alembic_version == M9_1B
    assert mid.tables == before.tables - {"instrument_sessions"} - _XN550_G2_TABLES
    removed_columns = {("instrument_messages", c) for c in _XN550_PHASE1_MESSAGE_COLUMNS}
    assert set(mid.columns) == {
        key for key in before.columns
        if key[0] != "instrument_sessions" and key[0] not in _XN550_G2_TABLES
    } - removed_columns
    assert not (_XN550_PHASE1_INDEXES & mid.index_names())
    assert (mid.count("p"), mid.count("u"), mid.count("f"), mid.count("c")) == (13, 6, 11, 0)
    assert len(mid.not_null_columns()) == 56
    assert len(mid.index_names()) == 26

    _alembic_or_fail(scratch_at_head, "upgrade", "head")
    after = SchemaSnapshot(scratch_at_head)
    assert after.alembic_version == HEAD
    assert after.tables == before.tables
    assert after.columns == before.columns
    assert after.constraint_names() == before.constraint_names()
    assert after.index_names() == before.index_names()


def test_audit_events_migration_downgrade_drops_audit_events_cleanly(scratch_at_head: str) -> None:
    """``28aa370f5dbe``'s downgrade is exercised here. Downgrading from head to
    ``27e00bcff992`` necessarily passes through the G2 and ``5d2e8b7c41a9``
    downgrades first (the G2 tables, ``instrument_sessions``), then removes
    ``audit_events``; upgrading
    back to head must be idempotent. Runs before the ``users`` downgrade test
    below, which downgrades further and removes ``users`` too."""
    before = SchemaSnapshot(scratch_at_head)
    assert "audit_events" in before.tables

    _alembic_or_fail(scratch_at_head, "downgrade", "27e00bcff992")
    mid = SchemaSnapshot(scratch_at_head)
    assert "audit_events" not in mid.tables
    assert mid.tables == before.tables - {"audit_events", "instrument_sessions"} - _XN550_G2_TABLES
    assert mid.alembic_version == "27e00bcff992"

    _alembic_or_fail(scratch_at_head, "upgrade", "head")
    after = SchemaSnapshot(scratch_at_head)
    assert after.tables == before.tables
    assert after.alembic_version == HEAD


def test_users_migration_downgrade_drops_users_cleanly(scratch_at_head: str) -> None:
    """Unlike ``b1f9dbe772fa``'s known-broken downgrade (F-4, a separate
    defect), ``27e00bcff992``'s downgrade is exercised here. Downgrading from
    head to ``4aff9e134f16`` necessarily passes through ``5d2e8b7c41a9``'s and
    ``28aa370f5dbe``'s own downgrades first — ``audit_events.id_user``
    references ``users``, so Alembic must drop the dependent table before the
    one it references — so ``instrument_sessions``, ``audit_events`` and
    ``users`` are removed together; upgrading back to head must be idempotent.
    Placed last among the ``scratch_at_head`` tests — it is the only one that
    mutates the shared module-scoped fixture database this far."""
    before = SchemaSnapshot(scratch_at_head)
    assert "users" in before.tables
    assert "audit_events" in before.tables

    _alembic_or_fail(scratch_at_head, "downgrade", "4aff9e134f16")
    mid = SchemaSnapshot(scratch_at_head)
    assert "users" not in mid.tables
    assert "audit_events" not in mid.tables
    assert mid.tables == before.tables - {"users", "audit_events", "instrument_sessions"} - _XN550_G2_TABLES
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
