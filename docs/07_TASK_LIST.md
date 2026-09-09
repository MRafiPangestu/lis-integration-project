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

- [ ] **M8.6** — Frontend Visual Polish (per `docs/M8.6_Investigation.md`)
  - [x] Retuned five existing design tokens (`--color-background` → `#F8FAFC`, `--color-border` → `#E2E8F0`, `--color-sidebar-bg` → `#0F172A`, `--color-sidebar-hover` → `#1E293B`, `--color-sidebar-text` → `#94A3B8`) and added ten structural tokens + five semantic tints in `index.css`, plus `.lis-input:focus` / `.custom-scrollbar` rules and a `.main-content` `--space-6` / ≤1199px `--space-4` padding split. No second palette, no new dependency. Every component colour/radius/shadow resolves through a custom property (DOM audit: zero inline `#hex` / `rgba()`)
  - [x] Sidebar: brand block (primary tile + inline activity glyph, `LIS Server` / `Marina Permata`), `INSTRUMENTS` section label, filled pill items with `--radius-md`, 8px round status-dot span with a conditional glow. Kept `id_instrument` identity + `onSelect`, `aria-current="page"`, the uppercase status word (never colour-only), skeleton/`role="alert"`/Retry behaviour, and the unchanged `matchMedia("(max-width: 900px)")` 64px icon-rail
  - [x] Header is instrument-aware — `nama_mesin` (ellipsis-truncating `<h1>` with `title`), real `protokol · tipe_koneksi` and `Last status: {last_status_at}` (each omitted when its data is null), and it hosts the MRN search. New props are optional so `MainLayout.tsx` still compiles. No Sync button, no Port field. §6C overflow contract implemented structurally: `min-width: 0` on every flex ancestor, metadata hidden below 1100px, search flex/min-width released to `0` at ≤900px — page never scrolls horizontally
  - [x] Removed the intermediate `AppShell` FilterBar band (double chrome); `FilterBar` is now a chrome-free inline field with a search-icon submit button; `OverviewHeader` (title + count only) and the chrome-free `DateRangeFilter` (segmented presets + inline inputs) compose as one flat toolbar in `OrderOverviewView`; the worklist `<table>`, `colSpan` empty row and `Pagination` footer fold into a single `--radius-lg` / `--shadow-card` panel whose horizontal scroll is panel-internal only
  - [x] Visual only: no backend, API, schema, navigation, date-serialization, instrument-identity, page-size or accessibility change. `commit()` / `invalid` in `DateRangeFilter`, the `{nomor_rm, id_visit, id_order}` drill-down, `delivery_status === null` → "Not finalised", the ⚠ + "N abnormal" + colour triad, and every `aria-*` / `scope="col"` / native `<button>` survive verbatim. `OrderDetailView`, all clinical/workflow/status components, `hooks/`, `api/`, `types/`, `dateRange.ts`, `MainLayout.tsx`, `StickyStatusBar.tsx`, `App.css` untouched; `App.tsx` changed by one line (`activeInstrument` prop)
  - [x] **R2 — Sidebar collapse:** sidebar opens expanded (260px) on every SPA load with no persistence (`useState(true)`, no localStorage/sessionStorage/URL); a native `<button>` toggle in the header (`aria-label` / `aria-expanded` / `aria-controls="instrument-sidebar"`) collapses it to the existing 64px in-flow rail and back. ≤900px keeps the forced rail and does not render the toggle. `aria-current` and `onSelect` identity unchanged
  - [x] **R2 — Search relocation:** Patient/RM search removed from the Header (`searchProps` prop and `FilterBar` import dropped from `Header`/`AppShell`); the existing `FilterBar` now sits in the overview toolbar above the worklist table, wired through `OrderOverviewView`'s new `searchProps`. Submit semantics, accessible name ("Search Patient / RM"), and the legacy MRN drill-down path are byte-identical; no client-side search/filter added; search is absent on the detail screen
  - [x] **R2 — `All` date preset:** presets are now `All | Today | Yesterday | Last 7 days | custom range`. `All` sends the presentation-only sentinel window `1900-01-01T00:00` / `2999-12-31T23:59` (three additive exports in `dateRange.ts`; the four existing helpers untouched) — both bounds always present so the M8.4 endpoint never 422s. `page_size=25`, server-side pagination, no full-dataset load, no backend change
  - [x] **R2 — Numbered pagination:** `Pagination` renders a centred sliding window of five page buttons with always-present first/last anchors and inert `aria-hidden` ellipses, plus prev/next chevrons. Every button calls the existing `onPageChange`; still server-side, still `page_size=25`; active/hover/focus/disabled states via `.lis-page-btn`; keyboard-operable
  - [x] **R2 — Shared button system:** `.lis-btn` (`--primary` / `--secondary` / `--ghost`) and `.lis-page-btn` / `.lis-select` added to `index.css` (one new token, `--color-border-strong: #94A3B8`). Applied to the detail Back button, `ConfirmationDialog`, `FinalRunWorkflow`, `SimrsSyncWorkflow`, `ErrorState` Retry, and the visit/order selects under a presentation-only boundary — `git diff -U0` over those files is `className` additions and `borderRadius` literal→token only; zero handler / state-machine / API / workflow / clinical / navigation change. 15 `borderRadius: "4px"` sites resolved to radius tokens (`borderRadius: "50%"` shape exempt)
  - [x] Verification: `npm run build` clean; `npm run lint` **13 errors, identical per-file/per-rule to the `468d6b7` baseline — zero new, zero in any Group 1/2/3 file**; manual V1–V27 run against `lis_marina_permata_dev` (sidebar expanded-on-load + toggle both directions at 1440/950, forced rail + no toggle at 860; header shows real `protokol · tipe_koneksi` + `Last status`, no search, no horizontal scroll; `All` → sentinel `date_from`/`date_to` in the network trace with no `Z`, `page_size=25`; Today/Yesterday/Last 7 days verbatim; exact-order drill-down; `colSpan` empty row; ⚠ + "N abnormal" triad; `ConfirmationDialog` open/cancel leaves the run unchanged; `py -m pytest tests -q` → 134 passed; no backend/`alembic`/`*.py` file touched)

**Completion Notes:**
- **M8.6** (frontend visual polish) — **Revision 2 implemented locally (uncommitted); pending independent audit.** Revision 1 restyled the M8.5 dashboard toward the `poc/mindray` visual language (navy sidebar with a brand block and filled pill items, an instrument-aware header, one flat overview toolbar, a single worklist panel). A browser review of the running UI then found five defects the source-only assessment missed (header metadata overlapping the search, search in the wrong region, no sidebar width control, pagination without position or extent, unstyled workflow buttons). `docs/M8.6_Investigation.md` **Revision 2** specified the corrections and this pass implements them: sidebar expanded on startup with a non-persistent manual collapse toggle to the existing 64px rail; Patient/RM search moved from the Header into the overview toolbar with FilterBar props/submit/accessible-naming preserved; an `All` date preset mapped to the existing M8.4 contract via a presentation-only sentinel range (no backend change, `page_size=25`, server-side); numbered server-side pagination with a frozen centred-window algorithm; and a shared `.lis-btn` / `.lis-page-btn` button system extended to the detail and workflow buttons under a presentation-only boundary (`className` + radius-token changes only). Build clean, lint byte-identical to the `468d6b7` baseline (13, zero new), backend suite 134 passed, no protected path touched. Milestone completes when the audit signs off.

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
- Order Overview API (`/api/instruments/{id}/orders`) is order-grained, instrument-scoped, date-bound, and server-paginated, with derivation in a service layer and finality / delivery / abnormal-count taken from the M7-consistent effective run.
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
| M8.2 — Ingestion Hardening & Classification | ✅ Complete |
| M8.2b — BC-5150 Background Rule | ✅ Complete (field-verified) |
| M8.3 — Parser Registry | ✅ Complete |
| M8.4 — Instrument Order Overview API | ✅ Complete |
| M8.5 — Enterprise Dashboard Integration | ✅ Complete |
| M8.6 — Frontend Visual Polish | In Progress (Revision 2) |
| M9 — QA & Hardening | Not Started |

