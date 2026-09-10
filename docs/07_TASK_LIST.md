# Task List — LIS Middleware MVP

## Implementation Roadmap

Milestones structured for safe, incremental delivery with clear checkpoints.

```text
M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 → M10
```

`M1` database · `M2` backend · `M3` integration · `M4` test-run domain · `M5` API ·
`M6` SIMRS · `M7` frontend · `M8` multi-instrument + dashboard ·
`M9` deployment / security / verification · `M10` functional completion

Release readiness is tracked separately from milestone status — see **Release Gates**.

---

## Document Authority

**`07_TASK_LIST.md` is authoritative for milestone status, and for nothing else.**

| Domain | Authoritative document |
|---|---|
| Business scope, boundaries, MVP success criteria | `01_PROJECT_BRIEF.md` |
| Functional / non-functional requirements, actors, acceptance criteria, out-of-scope | `02_PRD.md` |
| Architecture, deployment, security posture | `03_SYSTEM_DESIGN.md` |
| PostgreSQL schema, constraints, finality / traceability rules | `04_DATABASE_DESIGN.md` |
| Verification method, test cases, QA baseline, release sign-off | `06_QA_TEST_PLAN.md` |
| Instrument identity, master data, seed eligibility | `08_MASTER_DATA.md` |
| Physical instrument behaviour and field evidence | `09_PHYSICAL_INSTRUMENT_VALIDATION.md` |
| Frozen milestone decisions | `M8.4_Investigation.md`, `M8.5_Investigation.md`, `M8.6_Investigation.md` |

Where this document conflicts with any of the above, **the authoritative document prevails and this document must be reconciled to it.** Content from those documents may be cited here; it must not be redefined here.

Documents under `docs/audits/` are **analysis records, not product requirements** and not source-of-truth specifications. An audit may prompt a reconciliation of this file; it never originates a requirement.

**Milestone-scoped prohibitions are not project-wide prohibitions.** A constraint written into an investigation document binds that milestone only. In particular, `M8.6_Investigation.md` §11 prohibited polling and new dependencies **within M8.6**; that prohibition does not block M10.1 auto-refresh and does not permanently prevent frontend test tooling (M9.4).

---

## Milestone Status Model

Five status values only.

| Status | Meaning |
|---|---|
| **COMPLETE** | Implemented, and every acceptance criterion in that milestone's own section is evidenced (see the completion rule below) |
| **IMPLEMENTED** | Implementation exists and is believed correct, but one or more acceptance criteria are not yet evidenced |
| **BLOCKED** | Progress depends on an input the project does not control (physical instrument access, lab management, an external system specification) |
| **DEFERRED** | Deliberately postponed by a cited project decision |
| **NOT STARTED** | No work has begun |

A parent milestone takes the weakest status of its children.

`COMPLETE (as scoped)` is **not** a sixth status. It is `COMPLETE` plus a documented **Known Deviation** — used where a contractual requirement was omitted from that milestone's own acceptance criteria and is discharged elsewhere. It preserves history without asserting the requirement is met.

---

## Rule for Marking a Milestone COMPLETE

A milestone may be marked **COMPLETE** only when every acceptance criterion in its own section is demonstrated by at least one evidence class below, cited alongside it.

| Class | Evidence |
|---|---|
| **E1** | **Automated test** — a named test or test file that fails if the criterion regresses |
| **E2** | **Reproducible structural check** — a named command or inspection any reader can re-run (`alembic heads`, `npm run build`, a schema comparison). Also covers a criterion satisfied *by construction*, provided the absent surface is explicitly identified |
| **E3** | **Cited investigation verification** — a named, executed verification item from that milestone's investigation document |
| **E4** | **Dated physical evidence** — a dated entry in `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §18 |

**E4 is required only for criteria that assert real instrument behaviour.** A criterion satisfiable in software alone is fully served by E1–E3 and must never be blocked on physical evidence.

If any criterion lacks evidence, the milestone is **IMPLEMENTED**, not COMPLETE. A milestone must close its own verification obligations; it may not defer them into another milestone.

**Completion Notes are historical records.** They describe the state at the time they were written and are not edited to match later numbers. Status lines, this file's Progress Summary, and the Release Gates section describe the **current** state and are kept current.

---

## Owner Decisions Outstanding

Recorded here so they are visible rather than silently assumed. None is treated as decided.

| ID | Decision | Current position |
|---|---|---|
| **OD-1** | RBAC model: Option A (ANALYST clinical / ADMIN system-only) vs Option B (ADMIN inherits ANALYST plus system and user management) | **Option B is the recommendation, not an owner decision.** If B is selected, M9.1b audit attribution becomes mandatory |
| **OD-2** | M9.0 database baseline strategy | **Resolved.** M9.0 Phase 1 (`d335bc4`) selected the evidence-derived historical baseline (Option A′ / investigation OD-B), not a squashed final-schema baseline; Phase 2 (`d273e7f`) implemented it as root revision `8e973e84a9d7` (R0). The legacy schema was captured from `lis_marina_permata` (`1c14380`) and deterministically canonicalised (`f16081f`), not reconstructed |
| **OD-3** | `M8.6_Investigation.md` O8 — should MRN search remain reachable from the detail screen? | The document's recommended default ("no") was applied during implementation. **Owner confirmation outstanding** |
| **OD-4** | Target interim release posture | **Posture 1 is the recommendation, not an approved decision.** See Release Gates |
| **OD-5** | `GET /api/results` and the `useResults` hook have no current consumer — keep and test, or retire? | **Undecided. Both are retained.** No deletion is proposed by this reconciliation |

---

# M1 — Database Foundation

**Status: COMPLETE (as scoped)** — evidence E2 (`alembic heads` → single head `4aff9e134f16`; 11 ORM `__tablename__` values match `04_DATABASE_DESIGN.md` §4–§10 one-to-one).

> **Known Deviation — fresh-install database provisioning.** M1's acceptance criteria were satisfied against the **development database**. They never required, and this milestone never delivered, the ability to provision a database from empty: revision `b1f9dbe772fa` creates only `visits` and `test_runs` and alters three tables that must already exist, and `4a24240f8c32` is a no-op. The migration chain therefore assumes a pre-existing database. **The nature and remediation of that assumption are unresolved and are the subject of M9.0 — no baseline strategy is chosen here, and no legacy schema is asserted.** M1's shipped scope is unchanged and is not reopened.

## Objective

Create the final PostgreSQL schema that implements the documented data hierarchy (`Patient → Visit → Order → Test Run → Result`) with all constraints, indexes, and invariants required by the specification.

## Tasks

- [x] **M1.1** — Design and review final PostgreSQL DDL
  - [x] Define all 11 tables (`patients`, `visits`, `orders`, `test_runs`, `results`, `instrument_messages`, `instruments`, `units`, `doctors`, `test_groups`, `tests`)
  - [x] Define all primary keys, foreign keys, and NOT NULL constraints
  - [x] Define all UNIQUE constraints (`nomor_rm`, `no_registrasi`, `kode_tes`, `kode_unit`)
  - [x] Define `UNIQUE(id_run, parameter_tes)` on `results`
  - [x] Define Partial Unique Index: `idx_unique_final_run_per_order` on `test_runs(id_order) WHERE is_final = TRUE`
  - [x] Define recommended indexes for query performance — deferred at M1; the M1 migration created only the uniqueness / partial-unique indexes. Non-unique query-performance indexes are created by the milestone that needs them (see M8.4).
    - **Discharged by M8.4** (migration `4aff9e134f16`): four additive query-performance indexes created; the optional fifth deliberately omitted with the reasoning recorded in the migration docstring. This deferral is closed.
  - [x] Verify no `status_hasil` field exists
  - [x] Verify `id_instrument` and `id_message` are on `test_runs`, not `results`
  - [x] Verify `delivery_status` and `delivered_at` are on `test_runs`

- [x] **M1.2** — Execute migration on development database
  - [x] Back up existing database (if data exists)
  - [x] Run `alembic upgrade head` to apply `b1f9dbe772fa_M1_initial_schema`
  - [x] Verify all tables created correctly
  - [x] Verify all constraints enforced
  - [x] Verify Partial Unique Index works (test inserting two `is_final = TRUE` for one order — must fail)
  - [x] Verify `UNIQUE(id_run, parameter_tes)` works

- [x] **M1.3** — Seed essential master data
  - [x] Insert 9 instrument identities into `instruments`
  - [x] Seed BC-5150 with field-verified HL7 / TCP/IP configuration
  - [x] Insert 10 confirmed `units` records
  - [x] Insert 6 primary `test_groups` records
  - [x] Implement idempotent seed behavior
  - [x] Ensure strict development database safety protection

## Dependencies

None — this is the first milestone.

## Acceptance Criteria

- All 11 tables exist with correct columns, types, and constraints.
- Partial Unique Index prevents two final runs per order at the database level.
- `UNIQUE(id_run, parameter_tes)` prevents duplicate parameters within a single test run.
- Same `parameter_tes` can exist across different test runs of the same order.
- No `status_hasil` field exists anywhere.
- `results` has no `id_order`, `id_instrument`, or `id_message` columns.
- `test_runs` has `id_instrument`, `id_message`, `is_final`, `delivery_status`, `delivered_at`.
- Foreign keys enforce referential integrity.

---

# M2 — Backend Foundation

**Status: COMPLETE** — evidence E2 (11 models import and match the DDL; `requirements.txt` pinned; Alembic initialised; FastAPI application starts).

## Objective

Establish the FastAPI project structure with SQLAlchemy 2.x models, database configuration, Pydantic schemas, and the foundation for services and repositories. No business logic yet — only the structural skeleton.

## Tasks

- [x] **M2.1** — Create backend project structure
  - [x] Create package directories (`app/`, `app/models/`, `app/schemas/`, `app/api/`, `app/services/`, `app/core/`, `app/integration/`)
  - [x] Create `app/__init__.py` and sub-package init files
  - [x] Create `app/main.py` (FastAPI application factory)
  - [x] Create `app/core/config.py` (settings from `.env`)
  - [x] Create `app/core/database.py` (SQLAlchemy engine, session factory)

- [x] **M2.2** — Create SQLAlchemy models
  - [x] `app/models/patient.py` — Patient model
  - [x] `app/models/visit.py` — Visit model
  - [x] `app/models/order.py` — Order model
  - [x] `app/models/test_run.py` — TestRun model (with `is_final`, `delivery_status`, `delivered_at`)
  - [x] `app/models/result.py` — Result model (immutable clinical fields)
  - [x] `app/models/instrument.py` — Instrument model
  - [x] `app/models/instrument_message.py` — InstrumentMessage model
  - [x] `app/models/unit.py` — Unit model
  - [x] `app/models/doctor.py` — Doctor model
  - [x] `app/models/test_group.py` — TestGroup model
  - [x] `app/models/test_catalog.py` — Test catalog model
  - [x] `app/models/__init__.py` — Export all models

- [x] **M2.3** — Create dependency management
  - [x] Create `requirements.txt` with pinned versions
  - [x] Install all dependencies successfully

- [x] **M2.4** — Create Alembic migration infrastructure
  - [x] Initialize Alembic (`alembic init alembic`)
  - [x] Configure `alembic/env.py` (imports models, reads DB URL from `.env`)
  - [x] Generate initial migration: `alembic revision --autogenerate -m "M1_initial_schema"` → `b1f9dbe772fa`
  - [x] Verify migration content (20/20 automated checks passed)

- [x] **M2.5** — Verify model ↔ DDL alignment
  - [x] All 11 models import without errors
  - [x] FastAPI app starts without errors
  - [x] Migration autogenerated correctly from models

## Dependencies

- **M1** design approved before M2 models finalized. ✅

## Acceptance Criteria

- [x] Backend has clean package structure under `backend/app/`.
- [x] All 11 SQLAlchemy models exist and match the DDL 1:1.
- [x] Database session configuration works with `.env` settings.
- [x] `requirements.txt` lists all dependencies with pinned versions.
- [x] Alembic is initialized and initial migration is generated.
- [x] No legacy schema artifacts (`status_hasil`, `results.id_order`, etc.) in models.
- [x] FastAPI application starts without errors.

---

# M3 — Integration Service Refactor

**Status: COMPLETE (superseded by M8.1 / M8.2)** — evidence E1 (ingestion tests in `backend/tests/test_ingestion.py`). The single-instrument path delivered here was extended by M8.1 (`fc78533`, `e3a2495`) and hardened by M8.2 (`486880c`). Recorded as history; not reopened.

## Objective

Refactor the existing Integration Service (`alt_server.py`) to use the new database schema. The service must create `Visit`, `Order`, `Test Run`, and `Result` records using the correct hierarchy and must never overwrite clinical data.

## Tasks

- [x] **M3.1** — Refactor data persistence to new schema
  - [x] Replace `INSERT INTO orders (id_pasien)` with Visit + Order creation
  - [x] Create `test_runs` record for each instrument message
  - [x] Insert results with `id_run` FK (not `id_order`)
  - [x] Remove `ON CONFLICT DO UPDATE` — use plain INSERT
  - [x] Compute `run_sequence` as MAX+1 per order
  - [x] Link `id_instrument` and `id_message` to `test_runs`

- [x] **M3.2** — Use SQLAlchemy session from M2
  - [x] Replace raw `psycopg2` with SQLAlchemy ORM
  - [x] Use proper transaction management (session.commit / rollback)

- [x] **M3.3** — Configuration cleanup
  - [x] Read all config from `.env` / settings
  - [x] Remove hardcoded DB credentials and instrument IP

- [x] **M3.4** — Verify immutability
  - [x] Confirm re-run creates a new Test Run (not overwrite)
  - [x] Confirm previous Test Run results are untouched

## Dependencies

- **M1** — Database Foundation must be completed. ✅
- **M2** — SQLAlchemy models and session config must exist. ✅

## Acceptance Criteria

- Integration Service writes to the new schema correctly.
- Re-running a sample creates Test Run #2 without modifying Test Run #1.
- All results are linked to `test_runs`, not `orders`.
- No UPSERT / ON CONFLICT logic remains.
- Raw messages stored in `instrument_messages`.
- `run_sequence` is correctly incremented.

---

# M4 — Test Run Domain (Business Logic)

**Status: COMPLETE** — evidence E1 (`backend/tests/api/test_test_runs_api.py`, 20 tests covering finalize / unfinalize / delivery transitions) and E2 (partial unique index `idx_unique_final_run_per_order`; no clinical-mutation service method or endpoint exists in `app/services/` or `app/api/routers/`).

## Objective

Implement the core business logic for Test Run management: final run selection (with atomic swap), delivery status lifecycle, and clinical data immutability enforcement at the service layer.

## Tasks

- [x] **M4.1** — Final Run selection service
  - [x] Implement explicit finalization policy (HTTP 409 if another run is already final)
  - [x] Require client to explicitly unfinalize previous final run before setting a new one
  - [x] Verify Partial Unique Index protects against race conditions
  - [x] Ensure clinical data is not modified during finalization

- [x] **M4.2** — Delivery status lifecycle
  - [x] Implement status transitions: `pending → sending → delivered / failed`
  - [x] Ensure only final runs can be sent to SIMRS

- [x] **M4.3** — Immutability enforcement at service layer
  - [x] Ensure no service method can update clinical result fields
  - [x] Ensure no API-accessible mutation path for clinical data

## Dependencies

- **M2** — Models must exist. ✅
- **M3** — Integration Service must populate data correctly.

## Acceptance Criteria

- Selecting a final run enforces explicit transition (rejects if another run is final).
- Database prevents two final runs for the same order.
- Delivery status transitions correctly.
- No code path exists to mutate `nilai_hasil`, `satuan`, `flag_abnormalitas`, `parameter_tes`, `reference_range_snapshot`, or `waktu_hasil`.

---

# M5 — API Layer

**Status: IMPLEMENTED — verification incomplete.** All five sub-milestones are implemented and remain checked below; the acceptance criterion *"All specified endpoints return correct data"* is not yet evidenced for three of them.

> **Verification gap.** No automated test exercises:
> - `GET /api/results` (M5.1)
> - `GET /api/patients/{nomor_rm}/history` (M5.3) — this endpoint serves `02_PRD.md` FR-17 / AC-12
> - `GET /api/instruments/status` (M5.4)
>
> Evidenced today (E1): `GET /api/orders/{order_id}/test-runs` and the Test Run mutation endpoints (M5.2). Closed by **M9.4** item 1. Implementation is not in question and no sub-task is unchecked on account of this gap.

## Objective

Build the FastAPI REST endpoints for the dashboard and external integrations.

## Tasks

- [x] **M5.1** — Result retrieval API
  - [x] `GET /api/results` — paginated, filterable result list
  - [x] Filter by instrument, date, patient/RM, delivery status, final status
  - [x] Include Patient, Visit, Order, Test Run context

- [x] **M5.2** — Test Run API
  - [x] `GET /api/orders/{order_id}/test-runs` — list test runs for an order
  - [x] `POST /api/test-runs/{run_id}/finalize` — set final run (calls M4 service)
  - [x] `POST /api/test-runs/{run_id}/unfinalize` — explicit unfinalize run (calls M4 service)
  - [x] Response includes updated test run state

- [x] **M5.3** — Historical Result API
  - [x] `GET /api/patients/{nomor_rm}/history` — result history by Nomor RM
  - [x] Returns Visit → Order → Test Run → Result hierarchy

- [x] **M5.4** — Instrument status API
  - [x] `GET /api/instruments/status` — connection state of all instruments
  - [x] Design Integration Service → FastAPI status communication mechanism

- [x] **M5.5** — Pydantic schemas
  - [x] Request/response schemas for all endpoints
  - [x] Ensure clinical fields are read-only in response schemas

## Dependencies

- **M4** — Business logic services must exist.

## Acceptance Criteria

- All specified endpoints return correct data.
- Filters work correctly.
- No endpoint exposes mutation of clinical values.
- Historical API returns full traceability chain.
- Instrument status is available.

---

# M6 — SIMRS Integration

**Status: IMPLEMENTED — verification incomplete; end-to-end delivery externally blocked.** The gateway is built and all sub-tasks remain checked below.

> **Verification gap.** No automated test covers `SimrsClient`, `build_simrs_payload`, or `POST /api/test-runs/{run_id}/sync-simrs`. The delivery **state machine** is evidenced (E1, via the `delivery/start` · `delivery/success` · `delivery/fail` API tests); the **push path itself** is not. Closed by **M9.4** items 1 and 2.
>
> **External blocker.** Real end-to-end delivery to SIMRS has never been exercised: `SIMRS_BASE_URL` is unset, so `SimrsClient.send()` returns a configuration error and sends nothing. The missing input is the **SIMRS Integration Specification** (`01_PROJECT_BRIEF.md` §7 and `02_PRD.md` FR-17 both defer endpoint, payload and authentication to that specification). This is tracked as release gate **RG-2** — a gate, not a new milestone; the code already exists.

## Objective

Implement the SIMRS push gateway: send final Test Run results to the SIMRS endpoint and track delivery status.

## Tasks

- [x] **M6.1** — SIMRS integration module
  - [x] Build HTTP POST client for SIMRS endpoint
  - [x] Construct payload from final Test Run results
  - [x] Handle SIMRS response (success / failure)

- [x] **M6.2** — Delivery workflow
  - [x] `POST /api/test-runs/{id}/sync-simrs` — trigger push
  - [x] Update `delivery_status` through lifecycle
  - [x] Record `delivered_at` timestamp on success
  - [x] Handle retry on failure

- [x] **M6.3** — Delivery status API
  - [x] Expose delivery status in Test Run API responses
  - [x] Prevent duplicate concurrent sends

## Dependencies

- **M4** — Delivery status lifecycle must exist.
- **M5** — API infrastructure must exist.

## Acceptance Criteria

- Final Test Run results can be sent to a configured SIMRS endpoint.
- `delivery_status` transitions through `pending → sending → delivered/failed`.
- Retry works without modifying clinical data.
- `delivered_at` is recorded.

---

# M7 — Frontend

**Status: COMPLETE (as scoped)** — evidence E3 (the M8.5 §17 Tier-1 and M8.6 §13 V1–V27 manual verification runs against `lis_marina_permata_dev`) and E2 (`npm run build`).

> **Known Deviation — FR-07 / AC-09 automatic dashboard update.** `02_PRD.md` FR-07 requires the dashboard to update automatically after new data is processed, without a manual page refresh, and AC-09 states it as an acceptance criterion; `06_QA_TEST_PLAN.md` §18 carries it in the QA baseline. **M7's own acceptance criteria omitted it**, so the milestone closed without it. It is a functional requirement, not hardening. M7's shipped scope is unchanged and is not reopened; the requirement is discharged by **M10.1**.

> **Verification note.** M7 behaviours are evidenced by manual checklists (E3), not by automated tests. Frontend test tooling and automated component tests are **M9.4** item 5. This does not change M7's status: E3 is a valid evidence class.

## Objective

Build the React dashboard per the Design System specification, implementing all required components, workflows, and visual standards.

## Tasks

- [x] **M7.1** — Design System foundation
  - [x] Implement color tokens, typography, spacing per spec
  - [x] Configure Inter + Roboto Mono fonts
  - [x] Light mode theme (no dark mode for MVP)

- [x] **M7.2** — Layout structure
  - [x] Header
  - [x] Instrument Connection Status Bar (sticky)
  - [x] Filter Bar
  - [x] Patient/Order Summary panel
  - [x] Test Run Selector
  - [x] Result Table
  - [x] Workflow action area

- [x] **M7.3** — Core components
  - [x] `InstrumentStatusBar` / `InstrumentStatusItem`
  - [x] `PatientSummary` / `OrderSummary`
  - [x] `TestRunSelector` / `TestRunTab`
  - [x] `ResultTable` / `ResultRow` / `ResultFlag`
  - [x] `FinalRunButton` + confirmation dialog
  - [x] `SimrsDeliveryStatus` / `SimrsSyncButton`
  - [x] `FilterBar` / `SearchInput`
  - [x] `LoadingState` / `EmptyState` / `ErrorState`

- [x] **M7.4** — API integration
  - [x] API client layer (axios or fetch wrapper)
  - [x] React hooks for data fetching

- [x] **M7.5** — Workflow interactions
  - [x] Set Final Run with confirmation dialog
  - [x] Sync to SIMRS with loading/success/failure feedback
  - [x] Retry delivery
  - [x] Toast/notification system

- [x] **M7.6** — View-only enforcement
  - [x] Verify no `<input>`, `contenteditable`, or edit buttons for clinical data
  - [x] Accessibility: flags use icon + label + color (not color only)


## Dependencies

- **M5** — API endpoints must exist.
- **M6** — SIMRS sync endpoint must exist.

## Acceptance Criteria

- Dashboard displays all required information per Design System spec.
- Instrument status bar shows 9 instruments with connection state.
- Test Run selector allows switching between runs.
- Final Run selection works with confirmation.
- SIMRS sync works with status feedback.
- Clinical data is strictly view-only.
- Abnormal flags use icon + label + color.
- Design System colors, fonts, and spacing are applied.

---

# M8 — Multi-Instrument Support & Enterprise Dashboard

**Status: COMPLETE** (M8.1 · M8.2 · M8.2b · M8.3 · M8.4 · M8.5 · M8.6 all COMPLETE). Two items were deliberately deferred and one is blocked on field evidence; each is recorded against its own sub-milestone below and none of them prevents M8 from being complete as scoped.

| Sub-milestone | Status | Open item carried forward |
|---|---|---|
| M8.1 | COMPLETE | Rollout to instruments 2–9 is release gate **RG-1**, not M8.1 debt |
| M8.2 | COMPLETE | Specimen → visit/order identity rule **DEFERRED** (cited in-milestone) |
| M8.2b | COMPLETE | QC / calibration / maintenance extension **BLOCKED** on field evidence → **M9.3b** |
| M8.3 | COMPLETE | ASTM **DEFERRED** (cited in-milestone) |
| M8.4 | COMPLETE | Investigation decision D4 (`total_runs`) consciously not implemented |
| M8.5 | COMPLETE | Tier-2 frontend tests deferred under the investigation's own permitted fallback → **M9.4** |
| M8.6 | COMPLETE | Decision F3 (search availability) applied; open question O8 unconfirmed by owner (**OD-3**) |

> **M8 frozen decisions are not reopened by this reconciliation.** `M8.4_Investigation.md`, `M8.5_Investigation.md` and `M8.6_Investigation.md` remain binding within their scopes.

## Objective

Extend the Integration Service to handle concurrent connections from all 9 instruments, ensure clinical ingestion correctness, and provide an enterprise Patient Overview dashboard.

## Tasks

- [x] **M8.1** — Instrument Configuration & Connection Lifecycle
  - [x] Resolve and document the configuration source for instrument connectivity; extend application Settings/configuration rather than adding a new configuration-management subsystem
    - Implemented in M8.1-A (fc78533): InstrumentConfig contract, load_instrument_configs, Settings.instruments property
  - [x] Support per-instrument endpoint information required by the current implementation (host, port, protocol, instrument identity)
    - Implemented in M8.1-A: InstrumentConfig with host, port, parser_key, identity_prefix fields
  - [x] Allow `mode` as configuration metadata, but support only `client` mode in M8; defer listener/server mode until field verification proves it is required
    - Implemented in M8.1-A: mode field with validator restricting to "client" mode
  - [x] Quarantine or remove the legacy single-instrument files (`alt_server.py`, `lis_server.py`, `api.py`, `hl7_parser.py`) so they cannot be confused with the active integration path — before implementation proceeds
    - Completed in M8.1-A: moved to backend/legacy/ as renames
  - [x] Remove hardcoded parser selection from the integration path
    - Completed in M8.1-A/B: runtime parser resolution via resolve_parser() and parser_key config
  - [x] Remove the hardcoded `BC5150-` identity prefix from generic ingestion logic
    - Completed in M8.1-A: identity_prefix is per-instrument from config
  - [x] Resolve instrument identity/configuration from instrument-specific configuration rather than fixed numeric IDs
    - Implemented in M8.1-A: RuntimeInstrument binds config to resolved Instrument record via instrument_name
  - [x] Run one thread per instrument, compatible with the existing blocking-socket and synchronous SQLAlchemy architecture
    - Implemented in M8.1-B (e3a2495): Supervisor.start() launches one worker thread per enabled instrument
  - [x] Fault isolation: one instrument's failure must not affect others
    - Implemented in M8.1-B: Supervisor detects dead workers and restarts only the affected instrument's thread
  - [x] Implement reconnect behavior and persist connection status
    - Completed in M8.1-A/B: InstrumentClient.recv_loop() handles reconnect; write_instrument_status() persists connection_status
  - [x] Remove the development-database-only guard that currently prevents status persistence outside the dev database
    - Completed in M8.1-A/B: write_instrument_status() no longer checks database type; status writes work on all environments

**Completion Notes:**
- **M8.1-A** (fc78533): Instrument Configuration Contract & Inventory — InstrumentConfig, runtime identity resolution, parser binding, legacy code quarantine. 34 tests pass.
- **M8.1-B** (e3a2495): Multi-Instrument Supervisor & Runtime Lifecycle — Worker lifecycle management, dead-worker detection/restart, deterministic shutdown. 47 tests pass.

- [x] **M8.2** — Ingestion Hardening & Classification Mechanism
  - [x] Verify the existing Order → Test Run → Result hierarchy and `run_sequence` behavior (always insert new runs, never overwrite); preserve current semantics
    - Verified in 486880c: semantics unchanged; new runs always created; never overwritten
  - [x] Verify the existing exact-retransmission idempotency check and retain it as foundational protection
    - Verified in 486880c: exact-retransmission behavior preserved unchanged
  - [x] Guarantee raw-message persistence on every processing path, including unexpected exceptions (a rollback can currently lose the raw message)
    - Implemented in 486880c: T1/T2/T3 transaction model ensures raw persistence on all paths
  - [x] Make failure ACK behavior independent of parser success, so malformed or unexpected input still produces an appropriate instrument response
    - Implemented in 486880c: failure ACK generated from raw MSH-10 when parser=None or parser raises
  - [x] Ensure unexpected `run_sequence` uniqueness errors do not silently discard the clinical message
    - Implemented in 486880c: IntegrityError on run_sequence is persisted as raw message; no silent loss
  - [x] Do not redesign concurrency or add locking unless strictly necessary
    - Verified in 486880c: existing SQLAlchemy concurrency semantics preserved; no new locking added
  - Classification mechanism:
    - [x] Implement a classification mechanism (not a vendor-specific rule) supporting patient-result, non-patient/background, unclassified, and unparseable states where appropriate
      - Implemented in 486880c: generic classification mechanism with PATIENT_RESULT, NON_PATIENT, UNCLASSIFIED, UNPARSEABLE states
    - [x] Record a traceable classification reason/rule for each message
      - Implemented in 486880c: classification_rule field added to InstrumentMessage; populated by classify() function
    - [x] Fail closed: when classification is uncertain, do not treat the message as a patient result
      - Implemented in 486880c: strict defaults; only PATIENT_RESULT reaches clinical persistence
    - [x] Unclassified messages remain raw-persisted but must not create clinical Test Runs or Results
      - Implemented in 486880c: UNCLASSIFIED messages create no TestRun/Result; only raw message persisted
    - [x] Capture and preserve `IS`-typed OBX metadata currently discarded by the parser, for future evidence-based classification
      - Implemented in 486880c: IS-type segments preserved in classification metadata; not discarded
  - Specimen / visit identity:
    - [ ] Investigate and define the specimen → visit/order identity rule for messages without a patient identifier; preserve legitimate repeat-run semantics; resolve the collision risk before production multi-instrument ingestion; base the rule on verified instrument behavior and clinical requirements (no date-scoped or arbitrary replacement key)
      - **Not changed in M8.2** — remains blocked pending field evidence and clinical requirements investigation
      - **Status: DEFERRED.** Carried by this milestone's own acceptance criterion ("…before production multi-instrument ingestion") and by release gate **RG-3**. Evidence dependencies are recorded in `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §10 (T-BC-A, T-BC-O, T-ID-02, question Q4). Ingestion still derives `no_registrasi` as `identity_prefix + OBR-3`; no replacement key is proposed here.
  - Ingestion-critical tests:
    - [x] Parser behavior
      - Implemented in 486880c: 28 new ingestion tests covering parser paths and exceptions
    - [x] Classification mechanism and fail-closed handling
      - Implemented in 486880c: comprehensive classification tests with fail-closed verification
    - [x] Exact-retransmission behavior
      - Implemented in 486880c: exact-retransmission idempotency tests
    - [x] `run_sequence` behavior
      - Implemented in 486880c: run_sequence increment and conflict tests
    - [x] Error / rollback path for raw-message persistence
      - Implemented in 486880c: T1/T2/T3 transaction rollback path tests

**Completion Notes:**
- **M8.2** (486880c): Ingestion Hardening & Generic Classification — Raw-message persistence on all transaction paths (T1 parser=None, T2 parser exception, T3 post-parse IntegrityError). Parser-independent failure ACK from MSH-10. Generic fail-closed classification mechanism with PATIENT_RESULT / NON_PATIENT / UNCLASSIFIED / UNPARSEABLE states. IS-type OBX metadata preserved. Exact-retransmission and run_sequence semantics preserved. 28 new ingestion tests. 75 total backend tests passing.
- **M8.2b** (38a40fb): Fail-Closed BC-5150 Background Rule — Field evidence from physical BC-5150 (patient samples 30/31, Background runs) confirms OBR-3 = "Background" identifies non-patient samples. Rule implemented and fail-closed. QC/calibration/maintenance remain unclassified pending further field evidence. Patient ingestion available only through explicit unverified_passthrough policy. 92 backend tests pass.

- [x] **M8.2b** — Field-Verified BC-5150 Classification Rule
  - [x] Field evidence obtained and committed: physical BC-5150 patient samples 30/31 and Background runs
    - Implemented in 38a40fb: OBR-3 stripped and casefolded equals "background" -> NON_PATIENT / OBR3_BACKGROUND
  - [x] Once evidence exists, define the concrete BC-5150 classification rule against it
    - Implemented in 38a40fb: _bc5150_field_verified() policy encodes only the field-proven fact
  - [x] Do not commit a hardcoded background formula (e.g. `OBR-3 == "Background"`) or any other vendor-specific rule until evidence exists
    - Verified in 38a40fb: only OBR-3 "Background" is encoded; no QC/calibration/maintenance/Take Mode inference; fail-closed -> UNCLASSIFIED
  - [ ] Extend beyond Background if additional field evidence emerges for QC, calibration, maintenance, control
    - Not completed: QC/calibration/maintenance classification remain UNCLASSIFIED pending further field-verified evidence
    - **Status: BLOCKED** on physical evidence (`09_PHYSICAL_INSTRUMENT_VALIDATION.md` §9.2 / §18.1: QC, calibration, maintenance and control all have **zero captures**; T-BC-K ×2 on different days plus L, M, N, H are required, gated by lab-management question Q1). Tracked forward as **M9.3b**. No speculative QC rule is proposed.

- [x] **M8.3** — Protocol Abstraction & Parser Registry
  - [x] Define a common parser interface/adapter for message ingestion (keep minimal)
    - Implemented: `ParserFn = Callable[[str], Optional[ParsedHL7]]` type alias in `parsers/__init__.py`
  - [x] Implement a parser registry
    - Implemented: Static `_PARSERS` dictionary in `parsers/registry.py` with exact-match lookup
  - [x] Select parsers dynamically using explicit instrument configuration
    - Implemented: `resolve_parser(parser_key)` returns parser from registry; startup pre-validation before Supervisor
  - [x] Keep the BC-5150 HL7 parser as the first concrete implementation
    - Registered as `bc5150_hl7`: `"bc5150_hl7": parse_hl7_bc5150`
  - [x] Unregistered or unbound instruments fail loudly — no silent fallback
    - Implemented: `ParserNotRegisteredError` on unknown key; exact dictionary lookup only
  - [x] Defer ASTM until field-verified evidence exists; no speculative protocol-family hierarchies or plugin discovery systems
    - Verified: Static registry, no dynamic import, no plugin discovery, no fallback inference

**Completion Notes:**
- **M8.3** (parser registry): Parser interface moved to `parsers` package. Static exact-match registry with no fallback/inference/dynamic import/DB dependency. `ParserNotRegisteredError` replaces `InstrumentConfigError` for unknown parser keys. BC-5150 parser pre-registered. Startup validation retained. 107 backend tests pass.

**Current status — M8.3: COMPLETE**, evidence E1 (`backend/tests/test_parser_registry.py`). **ASTM support is DEFERRED** by this milestone's own decision — a deliberate project choice pending field-verified evidence, not a failure and not an external block. A second protocol family is introduced only when a real corpus exists for it (`09_PHYSICAL_INSTRUMENT_VALIDATION.md` §11.4, §16).

- [x] **M8.4** — Instrument Order Overview API
  - [x] Row grain frozen as **one Order** (not Patient/Visit/TestRun); an order is included when the requested instrument has ≥ 1 TestRun for it (EXISTS semi-join, no fan-out); patient identity is displayed but the view stays order-grained
  - [x] Effective run = M7's finality-first selection restricted to the requested instrument: `ORDER BY is_final DESC, run_sequence DESC, id_run DESC` → first row (no `waktu_run` ordering key; `run_sequence` is NOT NULL / MAX+1 / UNIQUE per order, `id_run DESC` is the defensive tie-breaker)
  - [x] `is_final` taken from the effective run; no-final-run is a normal state, not an error
  - [x] `delivery_status` / `delivered_at` = effective run's values when it is the final run, else **NULL** (no synthetic delivery state introduced; TestRun state machine unchanged)
  - [x] Abnormal count = `COUNT(results WHERE flag_abnormalitas IS NOT NULL)` for the **effective run only** (never summed across reruns / the whole order)
  - [x] Date filter on `Order.waktu_order`, half-open `[date_from, date_to)`, both required, `date_to > date_from` (422 otherwise), no implicit "today"; timestamps treated as server-local naive datetimes (schema is `TIMESTAMP WITHOUT TIME ZONE`, single-site on-premise) — no timezone schema change
  - [x] Endpoint is `GET /api/instruments/{instrument_id}/orders` (corrected from `/patients` — the API is order-grained). Unknown instrument → 404; valid request with no matching orders → 200 `items: []`, `total: 0`
  - [x] Offset/limit pagination (`page` ≥ 1 default 1, `page_size` 1–100 default 50); response `{items, page, page_size, total}`; final order `waktu_order DESC, id_order DESC` (mandatory `id_order` tie-breaker); `total` is the true qualifying order count, never inflated by run/result joins
  - [x] New summary schema `OrderOverviewRow` / `PaginatedOrderOverviewResponse` in `app/schemas/overview.py` — no clinical result values (does not reuse the M7 detail schema); `total_runs` omitted (optional, not required by the MVP contract)
  - [x] Derivation logic in `app/services/overview_service.py` (`get_instrument_order_overview`) using PostgreSQL `LATERAL` for the single effective run + scoped abnormal count; router only validates params / instrument existence and delegates
  - [x] Four additive query-performance indexes in migration `4aff9e134f16` (down_revision `c5465739f048`): `test_runs (id_instrument, id_order)`, `orders (id_visit)`, `visits (id_pasien)`, `orders (waktu_order DESC, id_order DESC)`. Optional 5th index on `test_runs (id_order, is_final DESC, run_sequence DESC)` NOT added — EXPLAIN showed the existing `uk_order_run_sequence` fully covers the 1–3-row effective-run ordering.

**Completion Notes:**
- **M8.4** (instrument order overview): order-grained, instrument-scoped operational worklist consistent with M7 detail semantics. Service-layer LATERAL query, no row fan-out, accurate `total`. 27 PostgreSQL tests (`tests/test_order_overview.py`). 134 backend tests pass. Ingestion / classification / identity / ACK / parser registry / TestRun workflow unchanged.

**Current status — M8.4: COMPLETE**, evidence E1 (`backend/tests/test_order_overview.py`, 27 tests) and E3 (`M8.4_Investigation.md` frozen decisions §3–§12 verified in `app/services/overview_service.py`). Investigation decision **D4 (`total_runs`) was consciously not implemented** — it was a proposed default rather than a frozen decision, and M8.5 decision D5 ("Run N" shown when `effective_run_sequence > 1`) covers the operator need. This is a deliberate choice, not outstanding debt.

- [x] **M8.5** — Enterprise Dashboard Integration (per `docs/M8.5_Investigation.md`)
  - [x] Permanent left `Sidebar` (`components/layout/Sidebar.tsx`): 240px, all instruments from `GET /api/instruments/status` (`id_instrument` as identity — never array index, never a hardcoded PoC id), status dot + text reusing the `CONNECTED / RECONNECTING / DISCONNECTED / UNKNOWN` vocabulary, `aria-current="page"` + accent on the active item, no polling, manual `refetch` retry, 64px icon rail below ~900px
  - [x] `StickyStatusBar` retired from the shell (superseded by the sidebar); the file is kept untouched for reversibility. New `AppShell` (`components/layout/AppShell.tsx`) replaces `MainLayout`'s two-column role; `FilterBar` relocated into the shell as the always-available MRN lookup that drives the search→detail path
  - [x] `OrderOverviewView` consumes the M8.4 `GET /api/instruments/{id}/orders` via `useInstrumentOrders` (fixed `page_size` 25) and `getInstrumentOrders` (`URLSearchParams`, `apiClient.get`). Compact semantic `<table>` worklist — one Order per row, patient name as the primary anchor; columns Patient / Order time (`waktu_order`, dd/MM HH:mm) / Status (`status_order` + `Final` badge, `delivery_status` badge, `Not finalised` UI label when `delivery_status === null`) / Abnormal (`—` at 0, else icon + count + text, `--color-flag-high`) / chevron affordance. `Run N` shown only when `effective_run_sequence > 1`
  - [x] `DateRangeFilter`: two `<input type="datetime-local">` + Today / Yesterday / Last 7 days presets, default Today `[00:00, next 00:00)`. Values sent **verbatim** as server-local naive strings — no `toISOString()`, no `Z`, no offset (verified in the network trace). `date_to <= date_from` shows an inline error and suppresses the request; the API 422 is only a fallback. Any date change resets `page` to 1
  - [x] Server-side offset `Pagination`: `‹ Previous` / `Next ›` + "Showing X–Y of Z"; Previous disabled at `page === 1`, Next disabled when `page * page_size >= total`; no page-number list, no cursor pagination
  - [x] State-based navigation in `App` (no React Router, no Redux/Zustand/Context): `activeInstrumentId`, `detailTarget: { nomorRm, idVisit, idOrder } | null`, `dateFrom` / `dateTo`, `page`, plus the legacy `searchNomorRm`. Row click → `detailTarget` carries **all three** of `nomor_rm` + `id_visit` + `id_order`; instrument switch clears `detailTarget` and resets `page`; overview filter/page state lives in `App` so returning from detail restores context with no refetch of state
  - [x] `OrderDetailView` (`components/detail/OrderDetailView.tsx`) — **extraction, not a rewrite**: the M7 detail state, helpers, effects, handlers and render body moved verbatim from `App.tsx` with props `{ nomorRm, initialVisitId?, initialOrderId?, onBack? }`. Visit/order preselection seeded from the props so the coordinating effects validate rather than override; the M7 effective-run rule and all clinical components (`PatientSummary`, `VisitOrderSelector`, `TestRunSelector`, `FinalRunWorkflow`, `SimrsSyncWorkflow`, `ResultTable`, `ResultRow`, `ResultFlag`, `ConfirmationDialog`, `ToastProvider`) are unchanged. The legacy MRN search renders the same component with no `initial*` ids, preserving today's behaviour
  - [x] Styling: current-branch design system remains authoritative; the only addition is the three sidebar tokens in `index.css` (`--color-sidebar-bg` / `--color-sidebar-hover` / `--color-sidebar-text`, harmonised with `#111827`). No React Router, no second palette, no PoC visual system, no PoC instrument data
  - [x] Manual verification against `lis_marina_permata_dev` (9 real instruments): sidebar list, default = first API instrument, instrument switch, worklist rendering, `Not finalised` / abnormal signals, date presets + verbatim serialization (no `Z`), page-reset-on-change, pagination bounds, row click opening the **exact** clicked order (not the newest), Back restoring the worklist, and the legacy MRN search all confirmed working. `npm run build` passes; `npm run lint` unchanged from baseline (13 pre-existing errors, 0 new)

**Completion Notes:**
- **M8.5** (enterprise dashboard): state-based two-view shell (Sidebar + Overview/Detail), M8.4 order-overview worklist, M7 detail extracted to `OrderDetailView` and reused by both the worklist drill-down and the legacy MRN search. `StickyStatusBar` retired from the shell (file retained). Four additive sidebar/overview frontend modules + three CSS tokens; no backend, migration, M8.3/M8.4, or clinical-component change. No React Router, no new global state, no polling, no frontend test framework.

**Current status — M8.5: COMPLETE**, evidence E3 (the §17 Tier-1 manual checklist executed against `lis_marina_permata_dev`) and E2 (`npm run build`; `npm run lint` unchanged from the `468d6b7` baseline).
- **Tier-2 frontend testing was legitimately DEFERRED**, not skipped: `M8.5_Investigation.md` §20 D4 offered two permitted paths and explicitly allowed "accept Tier 1 + the manual checklist and move all of §17 to M9.4". That fallback was taken. The 16 §17 scenarios are carried by **M9.4** item 5.
- **`MainLayout.tsx` and `StickyStatusBar.tsx` are intentionally retained.** Decision D1 froze "retire it from the shell, **keep the file**", and `M8.6_Investigation.md` §10 lists both under "Must NOT change" while §11 forbids deleting retained files. **They are not dead code and must not be deleted.**

- [x] **M8.6** — Frontend Visual Polish (per `docs/M8.6_Investigation.md`)
  - [x] Retuned five existing design tokens (`--color-background` → `#F8FAFC`, `--color-border` → `#E2E8F0`, `--color-sidebar-bg` → `#0F172A`, `--color-sidebar-hover` → `#1E293B`, `--color-sidebar-text` → `#94A3B8`) and added ten structural tokens + five semantic tints in `index.css`, plus `.lis-input:focus` / `.custom-scrollbar` rules and a `.main-content` `--space-6` / ≤1199px `--space-4` padding split. No second palette, no new dependency. Every component colour/radius/shadow resolves through a custom property (DOM audit: zero inline `#hex` / `rgba()`)
  - [x] Sidebar: brand block (primary tile + inline activity glyph, `LIS Server` / `Marina Permata`), `INSTRUMENTS` section label, filled pill items with `--radius-md`, 8px round status-dot span with a conditional glow. Kept `id_instrument` identity + `onSelect`, `aria-current="page"`, the uppercase status word (never colour-only), skeleton/`role="alert"`/Retry behaviour, and the unchanged `matchMedia("(max-width: 900px)")` 64px icon-rail
  - [x] Header is instrument-aware — `nama_mesin` (ellipsis-truncating `<h1>` with `title`), real `protokol · tipe_koneksi` and `Last status: {last_status_at}` (each omitted when its data is null). New props are optional so `MainLayout.tsx` still compiles. No Sync button, no Port field. §6C overflow contract implemented structurally: `min-width: 0` on every flex ancestor, metadata hidden below 1100px, search flex/min-width released to `0` at ≤900px — page never scrolls horizontally. (**R2:** MRN search moved from Header to overview toolbar per §6D-E)
  - [x] Removed the intermediate `AppShell` FilterBar band (double chrome); `FilterBar` is now a chrome-free inline field with a search-icon submit button; `OverviewHeader` (title + count only) and the chrome-free `DateRangeFilter` (segmented presets + inline inputs) compose as one flat toolbar in `OrderOverviewView`; the worklist `<table>`, `colSpan` empty row and `Pagination` footer fold into a single `--radius-lg` / `--shadow-card` panel whose horizontal scroll is panel-internal only
  - [x] Visual only: no backend, API, schema, navigation, date-serialization, instrument-identity, page-size or accessibility change. `commit()` / `invalid` in `DateRangeFilter`, the `{nomor_rm, id_visit, id_order}` drill-down, `delivery_status === null` → "Not finalised", the ⚠ + "N abnormal" + colour triad, and every `aria-*` / `scope="col"` / native `<button>` survive verbatim. `OrderDetailView`, all clinical/workflow/status components, `hooks/`, `api/`, `types/`, `MainLayout.tsx`, `StickyStatusBar.tsx`, `App.css` untouched; `dateRange.ts` expanded (§6E: sentinel range window); `App.tsx` changed by one line (`activeInstrument` prop)
  - [x] **R2 — Sidebar collapse:** sidebar opens expanded (260px) on every SPA load with no persistence (`useState(true)`, no localStorage/sessionStorage/URL); a native `<button>` toggle in the header (`aria-label` / `aria-expanded` / `aria-controls="instrument-sidebar"`) collapses it to the existing 64px in-flow rail and back. ≤900px keeps the forced rail and does not render the toggle. `aria-current` and `onSelect` identity unchanged
  - [x] **R2 — Search relocation:** Patient/RM search removed from the Header (`searchProps` prop and `FilterBar` import dropped from `Header`/`AppShell`); the existing `FilterBar` now sits in the overview toolbar above the worklist table, wired through `OrderOverviewView`'s new `searchProps`. Submit semantics, accessible name ("Search Patient / RM"), and the legacy MRN drill-down path are byte-identical; no client-side search/filter added; search is absent on the detail screen
  - [x] **R2 — `All` date preset:** presets are now `All | Today | Yesterday | Last 7 days | custom range`. `All` sends the presentation-only sentinel window `1900-01-01T00:00` / `2999-12-31T23:59` (three additive exports in `dateRange.ts`; the four existing helpers untouched) — both bounds always present so the M8.4 endpoint never 422s. `page_size=25`, server-side pagination, no full-dataset load, no backend change
  - [x] **R2 — Numbered pagination:** `Pagination` renders a centred sliding window of five page buttons with always-present first/last anchors and inert `aria-hidden` ellipses, plus prev/next chevrons. Every button calls the existing `onPageChange`; still server-side, still `page_size=25`; active/hover/focus/disabled states via `.lis-page-btn`; keyboard-operable
  - [x] **R2 — Shared button system:** `.lis-btn` (`--primary` / `--secondary` / `--ghost`) and `.lis-page-btn` / `.lis-select` added to `index.css` (one new token, `--color-border-strong: #94A3B8`). Applied to the detail Back button, `ConfirmationDialog`, `FinalRunWorkflow`, `SimrsSyncWorkflow`, `ErrorState` Retry, and the visit/order selects under a presentation-only boundary — `git diff -U0` over those files is `className` additions and `borderRadius` literal→token only; zero handler / state-machine / API / workflow / clinical / navigation change. 15 `borderRadius: "4px"` sites resolved to radius tokens (`borderRadius: "50%"` shape exempt)
  - [x] Verification: `npm run build` clean; `npm run lint` **13 errors, identical per-file/per-rule to the `468d6b7` baseline — zero new, zero in any Group 1/2/3 file**; manual V1–V27 run against `lis_marina_permata_dev` (sidebar expanded-on-load + toggle both directions at 1440/950, forced rail + no toggle at 860; header shows real `protokol · tipe_koneksi` + `Last status`, no search, no horizontal scroll; `All` → sentinel `date_from`/`date_to` in the network trace with no `Z`, `page_size=25`; Today/Yesterday/Last 7 days verbatim; exact-order drill-down; `colSpan` empty row; ⚠ + "N abnormal" triad; `ConfirmationDialog` open/cancel leaves the run unchanged; `py -m pytest tests -q` → 134 passed; no backend/`alembic`/`*.py` file touched)

**Completion Notes:**
- **M8.6** (frontend visual polish): **Revision 2 complete and released.** Commits: `15db322` (feat/complete M8.6 revision 2, 27 files) + `7b19a48` (fix/sidebar header junction). Revision 1 restyled the M8.5 dashboard toward `poc/mindray` (navy sidebar, brand block, filled pills, instrument-aware header, flat toolbar, single panel). Browser review found five defects: header metadata overlap, search in wrong region, no sidebar width control, pagination styling, unstyled buttons. Revision 2 specified corrections: sidebar expanded on startup with manual collapse toggle to 64px rail; Patient/RM search relocated to overview toolbar (FilterBar props/submit preserved); `All` date preset mapped via sentinel range `1900-01-01`/`2999-12-31` (no backend change, `page_size=25`, server-side); numbered server-side pagination (centred-window, five-button frame); `.lis-btn`/`.lis-page-btn` button system (detail + workflow, presentation-only, zero handler/API/clinical change). Independent Opus audit: PASS. Build clean, lint identical to baseline (13 errors, zero new), backend 134 passed, no protected path modified. Post-release refinement `7b19a48` aligned Sidebar/Header 64px junction.

**Current status — M8.6: COMPLETE**, evidence E3 (§13 V1–V27 executed) and E2 (`npm run build`; lint at baseline). Frozen decisions **F1–F7** stand as recorded in `M8.6_Investigation.md` §15 and are not reopened.
- **F3 changed behaviour, not only presentation.** Relocating the MRN search to the overview toolbar means the search is **no longer available on the detail screen** or during the three instrument-level states. Every functional property of the search→detail path was preserved; the availability surface narrowed. Recorded here so it is not mistaken for a regression.
- **Open question O8** (should MRN search remain reachable from the detail screen?) was answered by the document's recommended default and applied. **Owner confirmation is outstanding — see OD-3.**
- **M8.6 §11's prohibitions on polling and on new dependencies were scoped to M8.6.** They do not bind **M10.1** (auto-refresh) or **M9.4** (frontend test tooling).
- **`MainLayout.tsx` and `StickyStatusBar.tsx` remain intentionally retained** under §10 "Must NOT change" and §11's ban on deleting retained files.

## Dependencies

- **M3** — Single-instrument integration must work on new schema.
- **M5** — API foundation must exist.
- **M7** — Clinical dashboard components must exist for drill-down.

## Acceptance Criteria

- Instrument connectivity is resolved from configuration; the Integration Service is not bound to BC-5150 specifics.
- The Integration Service handles multiple instruments concurrently (one thread per instrument) with fault isolation and reconnect.
- Raw messages are persisted on every path, including unexpected failure; ACK behavior does not depend on parser success.
- The classification mechanism exists; unclassified messages are raw-persisted only and never create clinical Test Runs or Results.
- The BC-5150 Background classification rule (M8.2b) is field-verified and implemented; QC/calibration/maintenance expansion remains deferred pending additional field evidence.
- The specimen → visit/order identity rule is defined from verified instrument behavior before production multi-instrument ingestion.
- Parser abstraction and registry select parsers from explicit configuration; unbound instruments fail loudly; ASTM deferred.
- Order Overview API (`/api/instruments/{id}/orders`) is order-grained, instrument-scoped, date-bound, and server-paginated, with derivation in a service layer and finality / delivery / abnormal-count taken from the M7-consistent effective run.
- Dashboard provides instrument-based navigation and drills down into reused M7 clinical components without rewriting them.

---

# M9 — Deployment, Security & Verification Readiness

*Retitled from "QA & Hardening". The former title grouped a functional requirement (auto-refresh) with hardening work, which is how FR-07 went unnoticed; that item now lives in M10.1. Numbering of M9.1–M9.5 is preserved because `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §15 maps M9 items by number.*

## Objective

Make the system deployable, access-controlled, attributable and verified. Physical-evidence-dependent classification and deduplication work is tracked here but is blocked outside the project's control.

## Tasks

### M9.0 — Deployment & Migration Foundation — **IMPLEMENTED**

The migration chain was not self-sufficient from an empty database (see M1's Known Deviation), and no test exercises Alembic — both API test modules build their schema with `Base.metadata.create_all()`, so migrations and the ORM are two unverified-equivalent schema sources. R0 (below) closes the first gap; the Alembic test remains open.

**Implemented (`d273e7f`).** Phase 1 (`d335bc4`, `docs/M9.0_Investigation.md`) empirically confirmed the failure — `alembic upgrade head` from empty fails at `b1f9dbe772fa` with `relation "patients" does not exist` — and established the pre-M1 schema from a live read-only `pg_dump` of `lis_marina_permata` rather than by reconstruction. That schema was committed as `backend/schema/legacy_schema.sql` (`1c14380`) and deterministically canonicalised to `backend/schema/canonical_legacy_schema.sql` via `canonicalize_legacy_schema.py` (`f16081f`). Phase 2 implemented the evidence-derived baseline (investigation Option A′) as root revision `8e973e84a9d7` (**R0**), which executes the canonical legacy DDL as raw SQL, and repointed `b1f9dbe772fa.down_revision` to it. The graph is now single-root, single-head: `8e973e84a9d7 → b1f9dbe772fa → 4a24240f8c32 → 621889e316b5 → c5465739f048 → 4aff9e134f16` (`alembic heads` → `4aff9e134f16`). Validated: canonical artifact executes on an empty scratch database and reconstructs the legacy schema exactly (Phase 2D PASS); a fresh `alembic upgrade` to R0 matches the canonical baseline; the existing chain replays from R0 to head; a second empty database provisions straight to head with an identical result; R0 downgrade succeeds on a fresh scratch database; the chain-provisioned schema matches `lis_marina_permata_dev` except the single intentional `patients.nomor_rm` UNIQUE difference; the stable PoC `lis_marina_permata` was inspected read-only and never migrated, stamped or altered; `py -m pytest tests -q` → 176 passed (Phase 3A validation report). Phase 3B pre-commit review: **APPROVED WITH MINOR FOLLOW-UP**.

**Not yet COMPLETE.** Two M9.0 deliverables below remain open — the automated migration-chain check in the test suite (this is the Acceptance-Criteria item "the migration chain is exercised by an automated check"; the Phase 3A validation used ad-hoc scratch databases and uncommitted scripts, so no E1/E2 evidence exists in-repo) and the `04_DATABASE_DESIGN.md` provisioning section. Three schema-consistency defects are **out of R0's scope and are not resolved by M9.0** — each remains a distinct remediation: the missing `UNIQUE(patients.nomor_rm)` in the migration chain (`M9.0_Investigation.md` §7.2, F-2 — deliberately excluded from R0, which reproduces legacy truth); the ORM / M8.4-index autogenerate drift (`M9.0_Investigation.md` §7.3, F-3); and the broken `b1f9dbe772fa.downgrade()` unnamed-FK path (flagged by the Phase 3B review; `b1f9dbe772fa` is left byte-unchanged except its `down_revision`).

- [x] **Phase 1 — Investigation.** (`d335bc4` — `docs/M9.0_Investigation.md`) Established, from live read-only evidence, the pre-M1 schema, and that `4a24240f8c32` ("Legacy baseline") is a no-op historical stamp. Recommended Option A′ (evidence-derived historical baseline).
  - [x] Confirm empirically, on a scratch database, where `alembic upgrade head` first fails from empty — fails at `b1f9dbe772fa` (`CREATE TABLE visits … REFERENCES patients`; `relation "patients" does not exist`); atomic rollback, no partial schema (`M9.0_Investigation.md` §5)
  - [x] Establish the legacy schema from evidence — **do not reconstruct or infer it** — schema-only `pg_dump` of `lis_marina_permata`, committed as `backend/schema/legacy_schema.sql` (`1c14380`)
  - [x] Evaluate remediation options and record the choice with its reasoning — `M9.0_Investigation.md` §8–§9; Option A′ (evidence-derived historical baseline) selected over squash / idempotent / external-bootstrap alternatives
  - **Baseline strategy selected — OD-2 resolved:** evidence-derived historical baseline (Option A′). Canonical baseline plus its deterministic generator committed as `f16081f` (`backend/schema/canonical_legacy_schema.sql`, `canonicalize_legacy_schema.py`).
- [x] **Phase 2 — Implementation.** (`d273e7f`) Root revision `8e973e84a9d7` (R0) executes the canonical legacy DDL as raw SQL; `b1f9dbe772fa.down_revision` repointed to R0. Graph: one root `8e973e84a9d7`, one head `4aff9e134f16`. Validated Phase 2D / 3A; reviewed Phase 3B (see the status note above).
- [ ] Add migration verification to the test suite: provision a scratch database through the migration chain and assert the result matches `Base.metadata` — **open** (Acceptance-Criteria item; blocks COMPLETE)
- [ ] Add a provisioning section to `04_DATABASE_DESIGN.md` documenting the fresh-install path and the legacy-upgrade path — **open** (blocks COMPLETE)

**Dependencies:** none. **Release impact:** gate in every posture. **External blockers:** none.

### M9.1a — Security Foundation — **NOT STARTED**

Every API endpoint is currently unauthenticated, including the Final Run and SIMRS actions. Basis: `02_PRD.md` NFR-09 and AC-12; `03_SYSTEM_DESIGN.md` §11; `06_QA_TEST_PLAN.md` TC-SEC-01, TC-SEC-03, TC-HIST-03.

- [ ] Authentication mechanism (JWT or equivalent), with explicit and configurable token lifetime
- [ ] Password storage using a modern hashing scheme; never plaintext
- [ ] Define roles and represent them explicitly rather than as scattered string checks
- [ ] Protect API endpoints by role; deny by default
- [ ] Protect Final Run, unfinalize, delivery transitions and SIMRS sync from anonymous callers
- [ ] Restrict CORS for production *(moved here from the former M9.5 list — CORS configuration is inseparable from the authentication model)*
- [ ] Login / logout and authenticated-client integration in the frontend
- [ ] Tests: login success and failure, missing / invalid / expired token, wrong role, authorised role, and a check that no endpoint outside an explicit public allowlist is reachable anonymously

> **RBAC direction.** Option B (ADMIN inherits all ANALYST permissions plus system and user management) is the **recommendation** recorded under **OD-1**. It is **not an owner decision** and must not be implemented as settled until confirmed. `02_PRD.md` §3 defines one human actor (Laboratory Analyst); `03_SYSTEM_DESIGN.md` §11.2 presents its two-role tree explicitly as an example ("Contoh:") and states that actual rights are adjustable.

**Dependencies:** M9.0 (its `users` migration should land on a reconciled chain). **Release impact:** gate in every posture.

### M9.1b — Audit Attribution — **NOT STARTED**

`02_PRD.md` NFR-08 requires workflow audit information to include the identity of the user who performed the activity; `03_SYSTEM_DESIGN.md` §12 lists final-run selection among the activities to be traceable. No user identity is recorded on any workflow mutation today.

- [ ] Record the acting user on: finalize, unfinalize, delivery state transitions, SIMRS sync
- [ ] Schema change to carry the attribution, with its migration
- [ ] Tests asserting attribution is recorded and is not spoofable by the caller

> **Especially required if OD-1 resolves to Option B**, since role would then no longer distinguish who performed a clinical workflow action; attribution becomes the only remaining control satisfying NFR-08.

**Dependencies:** M9.1a. **Release impact:** gate in every posture.

### M9.2 — Message Deduplication Refinement — **BLOCKED**

- [ ] Per-instrument deduplication refinement (foundational exact-retransmission handling stays in M8.2)
- [ ] Retransmissions with changed timestamps
- [ ] Supplementary keys such as HL7 Control ID where justified

**Blocker (physical evidence, `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §8):** T-BC-B (genuine repeat run), T-BC-D, E, F, I, R, and T-ID-02. §8.5 records that the existing M8.2 guard **has never been exercised in the field** — under the fail-closed policy a BC-5150 message returns before the guard is reached. §8.5 also states that **no deduplication algorithm should be chosen** before those tests complete; none is proposed here.

> **Conditional release gate.** **Not** a gate for Posture 1 — no clinical rows are created, so there is nothing to duplicate. **Required before Posture 2** (`PATIENT_RESULT` enablement), where the guard becomes reachable and a resend with a changed OBR-7 would create a duplicate clinical run.

### M9.3a — Fail-Closed Classification, Validated — **COMPLETE**

Discharges the third bullet of the original M9.3 scope: *validate that the conservative fail-closed mechanism does not incorrectly quarantine genuine patient results.* The validation was performed and recorded; its outcome is that under `bc5150_field_verified` every non-Background BC-5150 message is `UNCLASSIFIED` and creates no clinical rows — accepted as safe-but-inert pending a positive rule.

- [x] Fail-closed BC-5150 behaviour: OBR-3 `Background` → `NON_PATIENT`; every other parseable message → `UNCLASSIFIED`, creating no Patient / Visit / Order / TestRun / Result
- [x] Quarantine behaviour validated and its consequences recorded
- [x] Behaviour pinned against regression

> **Provenance — do not misattribute.** The production behaviour was implemented in **`38a40fb` (M8.2b)**. Commit **`28ad9b3` changed no production code**: it added regression tests (`backend/tests/test_ingestion.py`) and field-evidence records (`09_PHYSICAL_INSTRUMENT_VALIDATION.md`) only. `28ad9b3` supplied **verification and evidence**, not behaviour.

**Evidence:** E1 — 28 BC-5150 tests in `backend/tests/test_ingestion.py` §K, including assertions that unlabelled and patient-like messages create no clinical rows. E4 — `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §18 (T-BC-J), §5.7 (27 consistent historical Background captures plus 2 live session-1 captures, no counter-example), §9.4–§9.5 (the quarantine consequence, and positive `PATIENT_RESULT` recorded as NOT APPROVED).

### M9.3b — QC / Calibration Filtering — **BLOCKED**

- [ ] Expanded per-instrument QC / calibration rules from field-verified instrument-specific semantics
- [ ] Filter QC / calibration data from patient results

**Blocker (physical evidence, `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §9):** QC, calibration, maintenance and control material all have **zero captures**. Required: T-BC-K twice on different days, plus L, M, N and H; scheduling depends on lab-management question Q1. §9.5 records positive patient classification as **NOT APPROVED**, with one candidate falsified and the rest unresolved. **No QC or positive-patient rule is proposed here.**

> **Conditional release gate.** **Not** a gate for Posture 1 — nothing is classified `PATIENT_RESULT`, so QC cannot contaminate a patient record. **Required before Posture 2**, where a misclassified QC run would write control-material values into a patient record.

### M9.4 — QA Debt Closure — **NOT STARTED**

A **finite, closed backlog** of verification debt that already exists. It is **not** a destination for future test obligations: under the completion rule above, each milestone closes its own verification. Nothing may be added to this list.

- [ ] **1. API tests** for the four untested endpoints: `GET /api/results`; `GET /api/patients/{nomor_rm}/history` (FR-17 / AC-12); `GET /api/instruments/status`; `POST /api/test-runs/{run_id}/sync-simrs` (FR-16 / AC-11)
  - *Three of these belong to M5's verification gap; `sync-simrs` belongs to M6's. `GET /api/results` is subject to **OD-5** — settle whether it is kept before writing tests for it. It is retained either way; nothing is deleted by this reconciliation.*
- [ ] **2. SIMRS module unit tests** — `SimrsClient` and `build_simrs_payload`, with the outbound call mocked
- [ ] **3. `backend/tests/conftest.py`** — none exists; each test module currently builds its own engine and fixtures
- [ ] **4. Dedicated database-constraint suite** — constraint behaviour is presently asserted only indirectly, via `IntegrityError` paths inside the ingestion and Test Run API tests
- [ ] **5. Frontend test tooling plus the `M8.5_Investigation.md` §17 Tier-2 scenarios 1–16** *(M8.6's ban on new dependencies was milestone-scoped and does not apply)*
- [ ] **6. Redacted field-corpus regression fixtures** (`09_PHYSICAL_INSTRUMENT_VALIDATION.md` §12.4, §16 step 4) — session-1 raw frames currently exist only in the development database. Redaction is required before any capture becomes a committed fixture.

**Dependencies:** M9.1a — authentication changes the setup of every API test, so writing them first would mean writing them twice. **Release impact:** gate in every posture.

### M9.5 — Production Hardening — **NOT STARTED**

- [ ] Structured logging (replace the remaining `print` statements in `app/integration/client.py` and `app/integration/instruments.py`)
- [ ] Error handling standardisation
- [ ] Input validation
- [ ] Connection pooling and related operational hardening

*CORS restriction moved to M9.1a.*

> **Partially blocked.** ACK-timeout and reconnect-interval tuning depends on `09_PHYSICAL_INSTRUMENT_VALIDATION.md` T-BC-T, which itself depends on lab-management question Q3 (whether an ACK may be withheld on a production instrument). The current 5-second connect and reconnect constants remain unvalidated. The rest of this milestone is unblocked.

### M9.6 — **VACATED**

Formerly "UI Auto-Refresh". **Automatic dashboard update is not hardening** — it is `02_PRD.md` FR-07 with acceptance criterion AC-09, and it appears in the `06_QA_TEST_PLAN.md` §18 baseline. Classifying it under "QA & Hardening" is why it was not recognised as an unmet contractual requirement when M7 closed. The requirement moves to **M10.1** under Functional Completion. The number is retained here, vacated, so existing references to "M9.6" resolve.

## Dependencies

- **M1–M8** — core features implemented.
- **M9.0** precedes M9.1a. **M9.1a** precedes M9.1b and M9.4, and precedes **M9.5** for consistency of the hardened surface (soft — M9.5 is otherwise unblocked).
- **M9.2**, **M9.3b** are independent of the above and blocked on physical evidence.

## Acceptance Criteria

- A database can be provisioned reproducibly, and the migration chain is exercised by an automated check (M9.0).
- Authentication prevents unauthorised access; no data endpoint is reachable anonymously (M9.1a; `06_QA_TEST_PLAN.md` TC-SEC-01, TC-SEC-03, TC-HIST-03).
- Workflow mutations record the acting user (M9.1b; `02_PRD.md` NFR-08).
- The four untested endpoints and the SIMRS module have automated coverage (M9.4).
- No print-based logging in production code (M9.5).
- Deduplication and QC criteria are **conditional on release posture** — see Release Gates. They are not acceptance criteria for Posture 1.

---

# M10 — Functional Completion

## Objective

Deliver the contractual functional requirement that remained after M8, and close M7's omitted acceptance criterion.

## Tasks

### M10.1 — Automatic Dashboard Update — **NOT STARTED**

Discharges `02_PRD.md` **FR-07** and **AC-09**, and closes the Known Deviation recorded against M7. Also carried in the `06_QA_TEST_PLAN.md` §18 QA baseline.

- [ ] Update the worklist automatically after new data is processed, with no manual page refresh
- [ ] Guarantee race safety with in-flight workflow mutations — the M7 per-run mutation lock in `frontend/src/hooks/useMutations.ts` must not be bypassed or duplicated
- [ ] Preserve existing pagination and date-range semantics; refresh must not silently move the operator's page or window
- [ ] Automated test coverage plus a manual verification pass

> **Implementation is not constrained to polling.** Polling or another suitable mechanism may be used. `M8.6_Investigation.md` §11's prohibition on `setInterval` / `setTimeout` and on new dependencies was **scoped to M8.6** and does not apply to this milestone.

**Development dependencies:** none — the M8.4 overview API already supplies the required data, and no backend change is anticipated.
**Release dependency:** if the consumed endpoint is protected by then, the refresh path must handle authentication and token expiry (M9.1a).
**Release impact:** gate in every posture.

## Dependencies

- **M8.4** — the overview API this consumes already exists.
- **M9.1a** — release-level dependency only (authenticated refresh), not a development blocker.

## Acceptance Criteria

- A newly processed result appears in the dashboard without a manual page refresh (AC-09).
- An automatic refresh cannot corrupt, cancel or race an active finalize / unfinalize / SIMRS-sync mutation.
- Evidence: E1 automated test plus E3 manual verification.

---

# Release Gates

Release gates are conditions on **shipping**, not units of work. A gate blocked by something outside the project is recorded with its external owner and is **never** restated as an engineering milestone.

**Which gates apply depends on the release posture.** Deduplication and QC classification are not gates for a fail-closed pilot, and *are* gates once clinical results are enabled. Neither is universally non-gating.

## Posture 1 — Fail-closed pilot

BC-5150 ingests, raw-persists, ACKs, and classifies Background as `NON_PATIENT`; everything else is `UNCLASSIFIED`. **No Patient / Visit / Order / TestRun / Result rows are created for the BC-5150.**

This posture demonstrates transport, MLLP framing, `MSA|AA` acknowledgement, the raw-message audit trail, Background classification, and the dashboard shell. **It must not be described as a clinical end-to-end workflow**, and the worklist will contain no BC-5150 clinical data.

| Gate | Required |
|---|---|
| M9.0 Deployment & Migration Foundation | **Yes** |
| M9.1a Security Foundation | **Yes** |
| M9.1b Audit Attribution | **Yes** |
| M9.4 QA Debt Closure | **Yes** |
| M9.5 Production Hardening | **Yes** |
| M10.1 Automatic Dashboard Update | **Yes** |
| M9.2 dedup · M9.3b QC · specimen identity | **No** — nothing clinical is persisted |
| RG-1 second instrument · RG-2 SIMRS E2E | **No** |

*Recommended interim target (**OD-4**) — a recommendation, not an approved decision.*

## Posture 2 — Clinical enablement for BC-5150

`PATIENT_RESULT` is enabled and clinical rows are created from instrument data.

| Gate | Required |
|---|---|
| All Posture 1 gates | **Yes** |
| M9.2 Deduplication Refinement | **Yes** — the M8.2 guard becomes reachable; a resend with a changed OBR-7 would create a duplicate clinical run |
| M9.3b QC / Calibration Filtering | **Yes** — a misclassified QC run would write control-material values into a patient record |
| Specimen → visit/order identity decision (M8.2 deferral) | **Yes** — if the specimen counter recycles, two patients collapse into one Visit / Order |
| RG-3 `PATIENT_RESULT` enablement | **Yes** — the composite of the three above |
| RG-1 second instrument · RG-2 SIMRS E2E | **No** |

**`PATIENT_RESULT` must not be enabled unless all three clear.** `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §9.6 states that M9.3 and the §10 identity question must **both** clear — neither alone is sufficient.

## Posture 3 — Full MVP sign-off

| Gate | Required |
|---|---|
| All Posture 2 gates | **Yes** |
| RG-1 Second instrument / multi-instrument isolation | **Yes** — externally blocked |
| RG-2 SIMRS end-to-end delivery | **Yes** — externally blocked |
| Historical Result API verified (FR-17 / AC-12) | **Yes** — requires M9.1a authorisation plus M9.4 item 1 |

Basis: `06_QA_TEST_PLAN.md` §21 sign-off criteria.

> **Posture 3 is not reachable by engineering effort alone.** Sign-off items §21.6 (multi-instrument isolation) and §21.7 (SIMRS delivery) depend on a second physical instrument and on the SIMRS Integration Specification respectively. Both should be raised with their owners now rather than discovered at sign-off.

## Release Gate Register

| ID | Gate | Requirement basis | Engineering work | External blocker | External owner |
|---|---|---|---|---|---|
| **RG-1** | Second instrument / multi-instrument isolation | `02_PRD.md` AC-01, AC-13; `06_QA_TEST_PLAN.md` §21.6 | **No new milestone.** Configuration entry, a parser for that instrument, and a field session | Physical access to a second instrument; `09_PHYSICAL_INSTRUMENT_VALIDATION.md` question Q5 (which instruments are in routine clinical use) | Lab management |
| **RG-2** | SIMRS end-to-end delivery | `02_PRD.md` AC-11, FR-16; `06_QA_TEST_PLAN.md` §21.7 | **None — the code already exists** (M6) | SIMRS Integration Specification: endpoint, payload contract and authentication are deferred to it by `01_PROJECT_BRIEF.md` §7 and `02_PRD.md` FR-17 | Project owner / hospital IT (SIMRS vendor) |
| **RG-3** | `PATIENT_RESULT` enablement for BC-5150 | `02_PRD.md` FR-04; `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §9.5, §9.6 | M9.2 **and** M9.3b **and** the specimen-identity decision | Physical evidence: T-BC-K ×2, T-BC-B, T-ID-02; lab-management questions Q1 and Q4 | Project owner, on field evidence |

**RG-1, RG-2 and RG-3 are gates, not milestones.** They are deliberately not numbered as M10.2 / M10.3: modelling an external dependency as an engineering task would imply work that does not exist.

---

# Milestone Dependency Graph

Development dependencies only. Release gates are separate and are listed above.

```text
M1 ──► M2 ──► M3 ──► M4 ──► M5 ──► M6 ──► M7 ──► M8
                                                  │
   ┌──────────────────┬───────────────────────────┴──────────────────┐
   ▼                  ▼                                              ▼
 M9.0              M9.2   [BLOCKED — physical evidence]           M10.1
   │               M9.3a  [COMPLETE — behaviour from M8.2b]      FR-07 / AC-09
   ▼               M9.3b  [BLOCKED — physical evidence]          closes M7
 M9.1a
   │
   ├──► M9.1b
   ├──► M9.4
   └──► M9.5

Sequential:  M9.0 → M9.1a → { M9.1b, M9.4 }.
Independent: M9.0, M9.2, M9.3b and M10.1 do not depend on one another.
M9.5 depends on M9.1a only for consistency of the hardened surface; it is
     otherwise unblocked except for its ACK / reconnect timing constants.
M10.1 needs M9.1a at release time (authenticated refresh), not to start.
```

# Progress Summary

Status vocabulary and the completion rule are defined at the top of this document.

| Milestone | Status | Note |
|---|---|---|
| M1 — Database Foundation | ✅ COMPLETE (as scoped) | Known Deviation: fresh-install provisioning → M9.0 |
| M2 — Backend Foundation | ✅ COMPLETE | — |
| M3 — Integration Service | ✅ COMPLETE (superseded) | Extended by M8.1 / M8.2 |
| M4 — Test Run Domain | ✅ COMPLETE | — |
| M5 — API | 🟡 IMPLEMENTED | Verification gap: 3 endpoints untested → M9.4 |
| M6 — SIMRS | 🟡 IMPLEMENTED | Verification gap → M9.4; real E2E → RG-2 (external) |
| M7 — Frontend | ✅ COMPLETE (as scoped) | Known Deviation: FR-07 / AC-09 → M10.1 |
| M8.1 — Instrument Config & Supervisor | ✅ COMPLETE | Instruments 2–9 rollout → RG-1 (external) |
| M8.2 — Ingestion Hardening & Classification | ✅ COMPLETE | Specimen identity DEFERRED → RG-3 |
| M8.2b — BC-5150 Background Rule | ✅ COMPLETE (field-verified) | QC extension BLOCKED → M9.3b |
| M8.3 — Parser Registry | ✅ COMPLETE | ASTM DEFERRED |
| M8.4 — Instrument Order Overview API | ✅ COMPLETE | D4 `total_runs` consciously not implemented |
| M8.5 — Enterprise Dashboard Integration | ✅ COMPLETE | Tier-2 tests deferred by permitted fallback → M9.4 |
| M8.6 — Frontend Visual Polish | ✅ COMPLETE | F3 behavioural note; O8 unconfirmed (OD-3) |
| M9.0 — Deployment & Migration Foundation | 🟡 IMPLEMENTED | Root migration R0 `8e973e84a9d7` implemented + validated (`d273e7f`); one root, one head; OD-2 resolved (Option A′). Open for COMPLETE: automated migration-chain test, `04_DATABASE_DESIGN.md` provisioning section. F-2 (`nomor_rm` UNIQUE), F-3 (M8.4 index drift) and the M1 downgrade defect remain separate. Gate in every posture |
| M9.1a — Security Foundation | ⬜ NOT STARTED | Gate in every posture; RBAC option undecided (OD-1) |
| M9.1b — Audit Attribution | ⬜ NOT STARTED | Gate in every posture; NFR-08 |
| M9.2 — Deduplication Refinement | ⛔ BLOCKED | Physical evidence; gate from Posture 2 |
| M9.3a — Fail-Closed Classification, Validated | ✅ COMPLETE | Behaviour from `38a40fb`; verification added by `28ad9b3` |
| M9.3b — QC / Calibration Filtering | ⛔ BLOCKED | Physical evidence; gate from Posture 2 |
| M9.4 — QA Debt Closure | ⬜ NOT STARTED | Gate in every posture; closed backlog of six items |
| M9.5 — Production Hardening | ⬜ NOT STARTED | Gate in every posture; timing constants blocked on T-BC-T |
| M9.6 — UI Auto-Refresh | ⊘ VACATED | Moved to M10.1 — functional requirement, not hardening |
| M10.1 — Automatic Dashboard Update | ⬜ NOT STARTED | Gate in every posture; FR-07 / AC-09; closes M7 |

| Release gate | Status | Owner |
|---|---|---|
| RG-1 — Second instrument / isolation | ⛔ Externally blocked | Lab management |
| RG-2 — SIMRS end-to-end delivery | ⛔ Externally blocked | Project owner / hospital IT |
| RG-3 — `PATIENT_RESULT` enablement | ⛔ Blocked (physical evidence) | Project owner |

