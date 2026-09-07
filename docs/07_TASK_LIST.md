# Task List — LIS Middleware MVP

## Implementation Roadmap

9 milestones structured for safe, incremental delivery with clear checkpoints.

```text
M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9
DB    BE   Integ  Run   API  SIMRS  FE   Multi  QA
```

---

# M1 — Database Foundation

## Objective

Create the final PostgreSQL schema that implements the documented data hierarchy (`Patient → Visit → Order → Test Run → Result`) with all constraints, indexes, and invariants required by the specification.

## Tasks

- [x] **M1.1** — Design and review final PostgreSQL DDL
  - [x] Define all 11 tables (`patients`, `visits`, `orders`, `test_runs`, `results`, `instrument_messages`, `instruments`, `units`, `doctors`, `test_groups`, `tests`)
  - [x] Define all primary keys, foreign keys, and NOT NULL constraints
  - [x] Define all UNIQUE constraints (`nomor_rm`, `no_registrasi`, `kode_tes`, `kode_unit`)
  - [x] Define `UNIQUE(id_run, parameter_tes)` on `results`
  - [x] Define Partial Unique Index: `idx_unique_final_run_per_order` on `test_runs(id_order) WHERE is_final = TRUE`
  - [ ] Define recommended indexes for query performance — deferred; the M1 migration created only the uniqueness / partial-unique indexes. Non-unique query-performance indexes are created by the milestone that needs them (see M8.4).
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

- **M1** — Database must be migrated. (pending M1.2)
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

- [ ] **M8.2** — Ingestion Hardening & Classification Mechanism
  - [ ] Verify the existing Order → Test Run → Result hierarchy and `run_sequence` behavior (always insert new runs, never overwrite); preserve current semantics
  - [ ] Verify the existing exact-retransmission idempotency check and retain it as foundational protection
  - [ ] Guarantee raw-message persistence on every processing path, including unexpected exceptions (a rollback can currently lose the raw message)
  - [ ] Make failure ACK behavior independent of parser success, so malformed or unexpected input still produces an appropriate instrument response
  - [ ] Ensure unexpected `run_sequence` uniqueness errors do not silently discard the clinical message
  - [ ] Do not redesign concurrency or add locking unless strictly necessary
  - Classification mechanism:
    - [ ] Implement a classification mechanism (not a vendor-specific rule) supporting patient-result, non-patient/background, unclassified, and unparseable states where appropriate
    - [ ] Record a traceable classification reason/rule for each message
    - [ ] Fail closed: when classification is uncertain, do not treat the message as a patient result
    - [ ] Unclassified messages remain raw-persisted but must not create clinical Test Runs or Results
    - [ ] Capture and preserve `IS`-typed OBX metadata currently discarded by the parser, for future evidence-based classification
  - Specimen / visit identity:
    - [ ] Investigate and define the specimen → visit/order identity rule for messages without a patient identifier; preserve legitimate repeat-run semantics; resolve the collision risk before production multi-instrument ingestion; base the rule on verified instrument behavior and clinical requirements (no date-scoped or arbitrary replacement key)
  - Ingestion-critical tests:
    - [ ] Parser behavior
    - [ ] Classification mechanism and fail-closed handling
    - [ ] Exact-retransmission behavior
    - [ ] `run_sequence` behavior
    - [ ] Error / rollback path for raw-message persistence

- [ ] **M8.2b** — Field-Verified BC-5150 Classification Rule
  - [ ] **BLOCKED** — pending field evidence or recovered PoC evidence of a BC-5150 background / QC / calibration sample (none is currently committed to the repository)
  - [ ] Once evidence exists, define the concrete BC-5150 classification rule against it
  - [ ] Do not commit a hardcoded background formula (e.g. `OBR-3 == "Background"`) or any other vendor-specific rule until evidence exists

- [ ] **M8.3** — Protocol Abstraction & Parser Registry
  - [ ] Define a common parser interface/adapter for message ingestion (keep minimal)
  - [ ] Implement a parser registry
  - [ ] Select parsers dynamically using explicit instrument configuration
  - [ ] Keep the BC-5150 HL7 parser as the first concrete implementation
  - [ ] Unregistered or unbound instruments fail loudly — no silent fallback
  - [ ] Defer ASTM until field-verified evidence exists; no speculative protocol-family hierarchies or plugin discovery systems

- [ ] **M8.4** — Patient Overview API
  - [ ] Before implementation, define: row identity, latest-run definition, finality definition, delivery-status definition, abnormal-count definition
  - [ ] Treat the overview as an order-oriented operational view that still displays patient identity (drill-down targets an order); do not promise patient-level identity resolution the current BC-5150 data cannot support
  - [ ] Use a deterministic `latest run` definition with `run_sequence` as the primary ordering signal
  - [ ] Derive finality and delivery status consistently from the final run at order scope; define the no-final-run case explicitly
  - [ ] Compute abnormal count as `flag_abnormalitas IS NOT NULL`, matching the current parser semantics (`'N'` and empty values are normalized to `NULL`; abnormal flags such as `'H~N'` are normalized to `'H'`). Confirm with a one-time query that no unexpected legacy values exist before relying on this predicate.
  - [ ] Implement `GET /api/instruments/{instrument_id}/patients` with instrument scope, a date bound for operational use, and deterministic server-side pagination (no keyset pagination unless necessary)
  - [ ] Put derivation logic in a service layer, not the router
  - [ ] Create the query-performance indexes this endpoint requires as part of M8.4 database work, based on verified schema; do not invent indexes for tables/columns whose state is not verified by repository evidence

- [ ] **M8.5** — Enterprise Dashboard Integration
  - [ ] Implement instrument sidebar navigation
  - [ ] Display the paginated Patient Overview table
  - [ ] Drill down from an overview row into the existing M7 clinical detail workflow
  - [ ] Extract the M7 detail body from `App.tsx` into a reusable detail view accepting an initial patient identifier and order identifier
  - [ ] Reuse existing M7 components; do not rewrite `ResultTable`, `ResultRow`, `ResultFlag`, `TestRunSelector`, `FinalRunWorkflow`, or `SimrsSyncWorkflow`
  - [ ] Use view state for navigation; do not add React Router unless a later requirement proves URL routing is necessary
  - [ ] Resolve whether the new sidebar replaces the existing `StickyStatusBar` to avoid duplicate instrument-navigation responsibilities

## Dependencies

- **M3** — Single-instrument integration must work on new schema.
- **M5** — API foundation must exist.
- **M7** — Clinical dashboard components must exist for drill-down.

## Acceptance Criteria

- Instrument connectivity is resolved from configuration; the Integration Service is not bound to BC-5150 specifics.
- The Integration Service handles multiple instruments concurrently (one thread per instrument) with fault isolation and reconnect.
- Raw messages are persisted on every path, including unexpected failure; ACK behavior does not depend on parser success.
- The classification mechanism exists; unclassified messages are raw-persisted only and never create clinical Test Runs or Results.
- The concrete BC-5150 classification rule (M8.2b) remains blocked until field evidence exists.
- The specimen → visit/order identity rule is defined from verified instrument behavior before production multi-instrument ingestion.
- Parser abstraction and registry select parsers from explicit configuration; unbound instruments fail loudly; ASTM deferred.
- Patient Overview API is instrument-scoped, date-bound, and server-paginated, with derivation in a service layer and defined finality / delivery / abnormal-count semantics.
- Dashboard provides instrument-based navigation and drills down into reused M7 clinical components without rewriting them.

---
# M9 — QA & Hardening

## Objective

Add authentication, message deduplication, QC filtering, test coverage, and production hardening.

## Tasks

- [ ] **M9.1** — Authentication / RBAC
  - [ ] Implement authentication mechanism (JWT or equivalent)
  - [ ] Define roles: Analyst, Administrator
  - [ ] Protect API endpoints by role
  - [ ] Protect Final Run and SIMRS sync actions

- [ ] **M9.2** — Message Deduplication Refinement
  - [ ] Per-instrument deduplication refinement (foundational exact-retransmission handling stays in M8.2)
  - [ ] Retransmissions with changed timestamps
  - [ ] Supplementary keys such as HL7 Control ID where justified

- [ ] **M9.3** — QC / Calibration Filtering Refinement
  - [ ] Expanded per-instrument QC / calibration rules from field-verified instrument-specific semantics
  - [ ] Filter QC / calibration data from patient results
  - [ ] Validate that the conservative fail-closed mechanism does not incorrectly quarantine genuine patient results

- [ ] **M9.4** — Test suite
  - [ ] Backend unit tests (parser, services, business logic)
  - [ ] API integration tests
  - [ ] Database constraint tests
  - [ ] Frontend component tests
  - [ ] End-to-end test scenarios from QA Test Plan

- [ ] **M9.5** — Production hardening
  - [ ] Structured logging (replace print statements)
  - [ ] Connection pooling
  - [ ] CORS restriction for production
  - [ ] Error handling standardization
  - [ ] Input validation

- [ ] **M9.6** — UI Auto-Refresh
  - [ ] Implement auto-refresh / polling mechanism for dashboard
  - [ ] Ensure race condition safety during mutations

## Dependencies

- **M1–M8** — All core features must be implemented.

## Acceptance Criteria

- QA Test Plan scenarios (TC-*) pass.
- Authentication prevents unauthorized access.
- Duplicate messages do not create duplicate clinical records.
- QC data does not appear as patient results.
- Test coverage exists for critical paths.
- No print-based logging in production code.

---

# Milestone Dependency Graph

```text
M1 ──► M2 ──► M3 ──► M4 ──► M5 ──► M6
                                │      │
                                ▼      ▼
                               M7 ◄────┘
                                │
                               M8
                                │
                               M9
```

# Progress Summary

| Milestone | Status |
|---|---|
| M1 — Database Foundation | ✅ Complete |
| M2 — Backend Foundation | ✅ Complete |
| M3 — Integration Service | ✅ Complete |
| M4 — Test Run Domain | ✅ Complete |
| M5 — API | 🟢 Complete |
| M6 — SIMRS | 🟢 Complete |
| M7 — Frontend | 🟢 Complete |
| M8.1 — Instrument Config & Supervisor | ✅ Complete |
| M8.2–M8.5 — Ingestion Hardening & Dashboard | In Progress |
| M9 — QA & Hardening | Not Started |

