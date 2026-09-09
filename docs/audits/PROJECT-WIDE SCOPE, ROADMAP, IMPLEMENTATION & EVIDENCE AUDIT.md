> Status: READ-ONLY AUDIT RECORD
> Authority: NON-AUTHORITATIVE
> Purpose: Project audit / reconciliation
> Audited commit: 28ad9b3
> Date: 2026-09-XX
> Supersession: This document does not override PRD, System Design,
> Database Design, QA Plan, Physical Validation, or milestone decision records.

This is a large audit. Let me gather the evidence systematically before drawing conclusions.

No files were modified. Full audit below.

---

# **PROJECT-WIDE AUDIT — LIS Middleware (RS Marina Permata)**

**Scope:** read-only. Branch `refactor/orm-architecture`, HEAD `28ad9b3`, working tree clean, `git rev-parse HEAD origin/refactor/orm-architecture` → identical. Backend suite re-run this session: **176 passed**.

---

## **1\. Executive summary**

The project is in better shape than the task list suggests in one respect and worse in another. The clinical ingestion path is genuinely well-engineered, evidence-disciplined, and now field-proven against real hardware. But **three contractual MVP requirements are unassigned to any milestone, and there is no working path to create a production database.**

**Five findings that change the roadmap:**

| ID | Finding | Severity | Basis |
| ----- | ----- | ----- | ----- |
| **F-1** | **No fresh-database provisioning path exists.** `alembic upgrade head` cannot succeed on an empty database | **Critical** | REPO-CONFIRMED |
| **F-2** | 4 of 11 endpoints have **zero** API tests, including both SIMRS-facing ones (AC-11, AC-12). The entire SIMRS module has zero tests, yet M6 is marked Complete | **High** | REPO-CONFIRMED |
| **F-3** | **FR-07 / AC-09 (automatic dashboard update) is contractual** and unimplemented; M7 was closed without it and it now sits in M9.6, mislabelled as "hardening" | **High** | REPO-CONFIRMED |
| **F-4** | **NFR-08 mandates user identity in the workflow audit trail.** No user model exists; `finalize` / `sync-simrs` record no actor | **High** | REPO-CONFIRMED |
| **F-9** | **8 of 9 MVP instruments are unintegrated.** `instruments.json` contains only the BC-5150, so AC-01 / AC-13 / QA §21.6 (multi-instrument isolation) cannot be demonstrated at all | **High** | REPO-CONFIRMED |

**One correction to my own prior output, because it changes a decision:** in the M9.1 design last turn I stated the QA plan contains no auth test cases. It does — `TC-SEC-01`, `TC-SEC-02`, `TC-SEC-03` and `TC-HIST-03` (`docs/06_QA_TEST_PLAN.md:1032,1125-1147`). Authentication testing is contractually specified, not something M9.1 introduces. This also reverses my RBAC recommendation — see §7.

**What is genuinely solid:** the M8.2 three-stage transaction model, the fail-closed classification mechanism, the MLLP framing fix, and the evidence discipline in `docs/09`. Those should not be reopened.

---

## **2\. Current project state**

| Dimension | State | Evidence |
| ----- | ----- | ----- |
| Git | `28ad9b3`, clean, synced with origin | `git status`, `git rev-parse` |
| Backend tests | 176 passed, 4 pre-existing warnings | `py -m pytest tests -q` |
| Migrations | 5 revisions, single linear head `4aff9e134f16` | `alembic/versions/` |
| ORM | 11 models, tablenames match `04_DATABASE_DESIGN.md` 1:1 | `grep __tablename__` |
| API surface | 11 endpoints, **0 authenticated** | `app/api/routers/` |
| Frontend | React 19 \+ Vite, **no router, no test tooling** | `frontend/package.json` |
| Instruments configured | **1 of 9** (BC-5150, enabled, `bc5150_field_verified`) | `backend/instruments.json` |
| SIMRS | Implemented, **`SIMRS_BASE_URL` absent from `.env`** → returns a configuration error, never sends | `simrs_client.py:21-25`; `.env` keys |
| Physical validation | BC-5150 session 1 complete; QC/dedup sessions outstanding | `docs/09` §5.5, §18 |

---

## **3\. M1–M9 status matrix**

| Milestone | Roadmap status | Actual implementation | Evidence | Final status |
| ----- | ----- | ----- | ----- | ----- |
| **M1.1** DDL \+ indexes | ✅ (index sub-item `[ ]`, deferred) | DDL done; deferred query indexes discharged by M8.4 | `4aff9e134f16` creates 4 indexes | **COMPLETE** (deferral honoured) |
| **M1.2** Migration on dev | ✅ | Works on the **legacy** DB only. **No fresh-install path** | `b1f9dbe772fa` creates only `visits`\+`test_runs`, ALTERs 3 pre-existing tables; `4a24240f8c32` is `pass` | **PARTIAL — F-1** |
| **M1.3** Seed master data | ✅ | `scripts/seed_master_data.py` | `ffe72ac` | **COMPLETE** |
| **M2** Backend foundation | ✅ | 11 models, session config, Alembic, pinned deps | tablename check; `requirements.txt` | **COMPLETE** |
| **M3** Integration refactor | ✅ | Superseded and extended by M8.1/M8.2 | `486880c`, `fc78533` | **COMPLETE (superseded)** |
| **M4** Test Run domain | ✅ | `test_run_service.py`; finality \+ delivery lifecycle | 20 API tests | **COMPLETE** |
| **M5.1** Results API | ✅ | Implemented (\~120 lines, 10 filters). **0 tests, 0 consumers** | no `/api/results` in tests; `useResults` unimported | **PARTIAL — dead path** |
| **M5.2** Test Run API | ✅ | Implemented \+ tested | `test_test_runs_api.py` | **COMPLETE** |
| **M5.3** Historical API (FR-17/AC-12) | ✅ | Implemented. **0 tests** | no `/api/patients` in tests | **PARTIAL** |
| **M5.4** Instrument status | ✅ | Implemented. **0 tests** | no `/api/instruments/status` in tests | **PARTIAL** |
| **M5.5** Pydantic schemas | ✅ | 3 schema modules | `app/schemas/` | **COMPLETE** |
| **M6** SIMRS integration | ✅ | Implemented. **0 tests, unconfigured, never exercised** | no `simrs` match in `tests/`; `SIMRS_BASE_URL` absent | **PARTIAL — blocked on external spec** |
| **M7** Frontend | ✅ | Dashboard complete **except FR-07/AC-09 auto-refresh** | no `setInterval`/polling in `src/` | **PARTIAL — F-3** |
| **M8.1** Config & supervisor | ✅ | Verified | `fc78533`, `e3a2495`, 13+11 tests | **COMPLETE** |
| **M8.2** Ingestion hardening | ✅ (identity sub-item `[ ]`) | T1/T2/T3, classification mechanism, dedup guard | `486880c`, 48 tests | **COMPLETE**; specimen-identity **DEFERRED (documented)** |
| **M8.2b** BC-5150 rule | ✅ (extend sub-item `[ ]`) | Background rule only, fail-closed | `38a40fb` | **COMPLETE**; extension **BLOCKED** |
| **M8.3** Parser registry | ✅ | Registry \+ explicit binding; ASTM deferred | `0dede85`, 10 tests | **COMPLETE** (ASTM **DEFERRED**) |
| **M8.4** Overview API | ✅ | Implemented \+ 27 tests \+ indexes | `fe78668` | **COMPLETE** |
| **M8.5** Dashboard integration | ✅ | Implemented | `468d6b7` | **COMPLETE** |
| **M8.6** Visual polish | ✅ | Rev 2 \+ junction fix | `15db322`, `7b19a48` | **COMPLETE** |
| **M9.1** Auth / RBAC | ☐ | Zero code | no JWT/hashing/User anywhere | **NOT STARTED** |
| **M9.2** Dedup refinement | ☐ | Zero code; guard unreachable for BC-5150 | `repository.py:101-106` returns before `:126` | **BLOCKED** (analyzer) |
| **M9.3** QC filtering | ☐ **(stale)** | Fail-closed half shipped in `28ad9b3`; QC half has zero evidence | `docs/09` §9.4, §9.5 | **PARTIAL / BLOCKED** |
| **M9.4** Test suite | ☐ | Backend 176; **frontend tooling absent**; no corpus fixtures | `package.json` has no test runner | **PARTIAL** |
| **M9.5** Prod hardening | ☐ | 9 `print()`; CORS `*` | `client.py`, `instruments.py`, `main.py:11` | **NOT STARTED** |
| **M9.6** UI auto-refresh | ☐ | Zero code — **but this is FR-07, contractual** | no polling in `src/` | **NOT STARTED — misclassified** |

**Implemented but unchecked:** M9.3's fail-closed behaviour (`28ad9b3`); M9 shows `Not Started` at `07_TASK_LIST.md:612`.  
 **Checked but not fully implemented:** M5.1/M5.3/M5.4 (untested), M6 (untested/unconfigured), M7 (missing FR-07), M1.2 (no fresh-install path).  
 **Stale text:** `docs/09` §15 says "165 passing as of `19d333e`" — now 176\.

---

## **4\. PRD vs System Design reconciliation**

### **Authority rule — documented, but incomplete**

`docs/02_PRD.md:761-771` **does** define the hierarchy: Brief \= goals/scope; PRD \= *what* the system must do; System Design \= *how*; Database Design \= data representation. So **PRD wins on requirements, System Design wins on architecture.** That rule is real and citable.

**What it does not cover:** nothing is declared authoritative for **milestone status**, **field evidence**, or **deployment configuration**. That is the actual ambiguity (see §14).

### **Contractual vs optional**

| Item | Status | Source |
| ----- | ----- | ----- |
| Multi-instrument connectivity, isolation | **Contractual** | FR-01, AC-01, AC-13 |
| HL7/ASTM processing | **Contractual** (ASTM deferred by M8.3) | FR-02, AC-02 |
| Raw message traceability | **Contractual** | FR-03, AC-03 |
| Histogram/scattergram exclusion | **Explicitly permitted** | FR-04 |
| **Automatic dashboard update, no manual refresh** | **Contractual** | **FR-07, AC-09** |
| Abnormality highlighting (not colour-only) | **Contractual** | FR-09, AC-10 |
| Multiple Test Runs, no overwrite, one final per order | **Contractual** | FR-13–15, AC-06–08 |
| SIMRS push with 4 distinguishable delivery states | **Contractual** | FR-16, AC-11 |
| Historical Result API **to authorised callers** | **Contractual** | FR-17, AC-12 |
| **Workflow audit including user identity** | **Contractual** | **NFR-08** |
| Access control on LIS functions and API | **Contractual** | NFR-09 |
| On-premise, no internet dependency | **Contractual** | NFR-10 |
| EMR, billing, inventory, manual entry, clinical value editing | **Explicitly out of scope** | PRD §7; Brief §4.2 |

### **Contradictions found**

| \# | PRD | System Design / implementation | Verdict |
| ----- | ----- | ----- | ----- |
| 1 | **§3 defines exactly one human actor: Laboratory Analyst.** No Administrator actor | §11.2 shows `Analis` / `Administrator`, prefixed **"Contoh:"** and followed by *"Hak akses aktual dapat disesuaikan dengan kebutuhan rumah sakit"* | **Not a contradiction — a gap.** SysDesign's role tree is explicitly an *example*. No document contractually defines an Administrator. **Decisive for §7** |
| 2 | FR-16 delivery states: `Pending` / `Sending` / **`Success`** / `Failed` | DB design \+ code use `pending` / `sending` / **`delivered`** / `failed` | **Cosmetic.** PRD requires *distinguishability*, which is met. DB Design owns the literal token. Worth one doc note, not a change |
| 3 | §3.1 Analyst may finalize **and** send to SIMRS | §11.2 example gives Analis "Select Final Run" but not SIMRS send | PRD wins (it owns *what*). Analyst gets both |
| 4 | Brief §7 / FR-17: SIMRS→LIS GET API | No inbound SIMRS auth, no service account; `SIMRS_API_KEY` is **outbound only** (`simrs_client.py:33`) | **Genuine gap.** AC-12 says "terotorisasi"; nothing enforces it |

**SIMRS communication direction is unambiguous and currently one-way:** LIS→SIMRS POST is implemented (`simrs_client.py`); SIMRS→LIS GET is *specified* (FR-17) and *served* by `/api/patients/{rm}/history`, but with no authorisation and no test.

---

## **5\. Task List vs repository reconciliation**

**Stale / incorrect entries requiring reconciliation (documentation only):**

1. `07_TASK_LIST.md:612` — `M9 | Not Started` despite `28ad9b3`.  
2. All M9.3 checkboxes `[ ]` — the fail-closed half shipped; the QC half is blocked. Neither state is representable by a single checkbox.  
3. M5/M6 marked ✅ with no test coverage — the acceptance criterion "All specified endpoints return correct data" (`:239`) is asserted, not demonstrated.  
4. M7 marked ✅ though FR-07 is unmet; M7's acceptance-criteria list (`:341-348`) simply omits auto-refresh, so the milestone closed against an incomplete criteria set.  
5. `docs/09` §15 — "165 passing".  
6. `alembic/env.py:14` — "All 11 models" (correct today; will be 12 after M9.1).

**Duplicated responsibility:** M8.2's dedup guard and M9.2's "dedup refinement" describe the same mechanism at different maturity levels — correctly cross-referenced (`M9.2` says "foundational … stays in M8.2"), so this is fine as written.

**Milestone boundary errors:**

* **M9.6 is not hardening.** FR-07 is a functional dashboard requirement (PRD §4.2). It belongs with M7 and was left behind.  
* **M9.4 "Test suite" is a milestone-shaped hole.** Treating tests as a *later* milestone is the direct cause of M5 and M6 shipping untested. Testing should be an exit criterion of each milestone, not a milestone.  
* **Three contractual items are assigned to no milestone at all:** fresh-DB provisioning (F-1), audit attribution (NFR-08, F-4), and instrument rollout beyond BC-5150 (F-9).

---

## **6\. M9 dependency graph**

                   ┌─────────────────────────────────────────┐  
  FULLY UNBLOCKED   │ M9.1a Auth/RBAC                         │  
  (no external      │ M9.6  Auto-refresh (FR-07 — CONTRACTUAL)│  
   dependency)      │ M9.5  logging / CORS / errors / pooling │  
                    │ M9.4a backend+API tests, FE tooling     │  
                    │ F-1   fresh-DB provisioning  ◄─ CRITICAL│  
                    └────────────────┬────────────────────────┘  
                                     │  
                    ┌────────────────▼────────────────────────┐  
   BLOCKED BY       │ M9.1b Audit attribution (NFR-08)        │  
   ANOTHER M9 TASK  │   needs M9.1a (no user id without users)│  
                    │ M9.4b auth tests → need M9.1a           │  
                    │ TC-SEC-01/03, TC-HIST-03 → need M9.1a   │  
                    └─────────────────────────────────────────┘

   ANALYZER-        T-BC-K ×2 (different days), L, M, N, H  
   DEPENDENT        └─► M9.3 QC rules  
                    └─► positive PATIENT\_RESULT rule  
                    T-BC-B, D, E, F, I, R  
                    └─► M9.2 dedup algorithm  
                    T-ID-02  ─► specimen identity ─► S1 stop condition  
                              (§9.6: BOTH M9.3 and §10 must clear  
                               before PATIENT\_RESULT is enabled)

   LAB-MANAGEMENT-  Q1 (QC on demand?)  ─► schedules T-BC-K  
   DEPENDENT        Q3 (may we withhold ACK?) ─► T-BC-T ─► M9.5 timing  
                    Q5 (which instruments are in routine use?) ─► rollout order  
                    Q7 (serial→Ethernet budget?) ─► RS-232 group

   EXTERNAL-SYSTEM- SIMRS Integration Specification (not yet available)  
   DEPENDENT        └─► AC-11 end-to-end verification, QA §21.7  
                    └─► inbound SIMRS auth contract (AC-12)

   INSTRUMENT-      2nd instrument (XN-550 / BS-200E) physical access  
   ACCESS-DEPENDENT └─► AC-01, AC-13, QA §21.6 multi-instrument isolation

**Parallelisable now:** M9.1a ∥ M9.6 ∥ F-1 ∥ M9.5 ∥ M9.4a — they touch disjoint files.  
 **Strictly sequential:** M9.1a → M9.1b → M9.4b. F-1 → any deployment.  
 **Minimum path to a defensible M9 release:** F-1 → M9.1a → M9.1b → M9.6 → M9.4a/b → M9.5. That path requires **no analyzer access**. M9.2 and M9.3 cannot be on the critical path — and, importantly, need not be: the fail-closed policy is already safe.

---

## **7\. RBAC recommendation — Option B, reversing my prior advice**

Last turn I recommended Option A (ADMIN excluded from clinical writes). **Re-examining the source documents for this audit, I no longer think that is right.** Three pieces of evidence I had not weighed:

1. **`docs/02_PRD.md` §3 — the authoritative actors document — defines exactly one human role: Laboratory Analyst.** There is no Administrator actor anywhere in the PRD.  
2. **`docs/03_SYSTEM_DESIGN.md` §11.2 labels its two-role tree "Contoh:" (example)** and adds that actual rights are adjustable to hospital needs. It is illustrative, not contractual. I previously cited it as if it were binding.  
3. **`TC-SEC-02` is satisfied architecturally, not by RBAC.** It requires that no user can modify or delete clinical results — and **no such endpoint exists** (PRD §2.1, NFR-02, Brief §4.2, and the 11-endpoint surface). The separation-of-duties argument for Option A was therefore protecting against a risk the architecture already eliminates.

### **Recommendation: Option B — ADMIN inherits all ANALYST permissions, plus user/system management.**

| Criterion | Assessment |
| ----- | ----- |
| PRD | Defines one human actor; an ADMIN role is an *operational* necessity (someone must create accounts), not a clinical distinction |
| System Design | §11.2 is explicitly an example and invites adjustment |
| Deployment model | Single on-prem server, one lab, internal LAN (§13) |
| Lab size | Small — 9 instruments; realistically the lab supervisor is both administrator and analyst |
| Clinical workflow | An administrator who cannot finalize cannot assist during an incident |
| **Separation of duties** | The value at risk is *clinical result mutation*, which **no role can perform** — there is no endpoint. RBAC is not the control that protects it |
| **Operational practicality** | Option A forces two accounts per person. In a small lab that predictably leads to **shared credentials**, which destroys attribution — making NFR-08 *worse*, not better |
| Auditability | Option B is safe **only** with per-action user attribution |

### **Consequences of choosing Option B — stated explicitly, as requested**

* **ADMIN inherits these clinical actions:** `finalize`, `unfinalize`, `delivery/start`, `delivery/success`, `delivery/fail`, `sync-simrs`, plus all reads.  
* **Operations still needing additional controls:** none require a *further role*, but `unfinalize` and `sync-simrs` warrant (a) the existing confirmation dialog, and (b) mandatory audit rows. `sync-simrs` additionally transmits patient data to an external system and should log actor, run id, outcome and timestamp.  
* **Audit attribution becomes MANDATORY, not optional.** With role no longer distinguishing actors, `id_user` on finalization and delivery events is the *only* remaining way to satisfy NFR-08 and QA §19 evidence requirements. **M9.1b is promoted from "nice, next" to a hard requirement shipped with M9.1.** This is the single most important consequence of the reversal.  
* **A third role is unnecessary.** Two roles cover every endpoint that exists. Add one only when an endpoint appears that ADMIN should reach and ANALYST should not, beyond user management.

**Everything else in the M9.1 design from the previous turn stands** — argon2-cffi (passlib is unusable on this Python 3.13.7: `import crypt` → `ModuleNotFoundError`), PyJWT/HS256, 8-hour token, no refresh token, per-request DB check, `sessionStorage`, explicit CORS allowlist. Only the role matrix changes: the six clinical POSTs become `ANALYST or ADMIN`.

---

## **8\. API / backend / frontend coverage map**

| PRD | Endpoint | Service | Entity | Frontend consumer | API test |
| ----- | ----- | ----- | ----- | ----- | ----- |
| FR-06, FR-01 | `GET /api/instruments/status` | inline | `Instrument` | `useInstruments` → `Sidebar` | ❌ **none** |
| FR-06, FR-08 | `GET /api/instruments/{id}/orders` | `overview_service` | Order+TestRun+Result | `useInstrumentOrders` | ✅ 27 |
| FR-13, FR-14 | `GET /api/orders/{id}/test-runs` | `TestRunService` | `TestRun` | `useOrderTestRuns` | ✅ |
| FR-08, FR-09 | `GET /api/results` | inline (\~120 ln) | `Result` | ❌ **dead** (`useResults` unimported) | ❌ **none** |
| **FR-17, AC-12** | `GET /api/patients/{rm}/history` | inline | full chain | `usePatientHistory` | ❌ **none** |
| FR-15, AC-07 | `POST …/finalize` | `TestRunService` | `TestRun` | `FinalRunWorkflow` | ✅ |
| FR-15, AC-08 | `POST …/unfinalize` | `TestRunService` | `TestRun` | `FinalRunWorkflow` | ✅ |
| FR-18 | `POST …/delivery/{start,success,fail}` | `TestRunService` | `TestRun` | via sync | ✅ |
| **FR-16, AC-11** | `POST …/sync-simrs` | inline \+ `SimrsClient` | `TestRun` | `SimrsSyncWorkflow` | ❌ **none** |
| **FR-07, AC-09** | — | — | — | — | **NOT IMPLEMENTED** |
| NFR-09, NFR-08 | — | — | — | — | **NOT IMPLEMENTED** |

### **Dead paths (REPO-CONFIRMED)**

* `frontend/src/components/layout/MainLayout.tsx` — **0 importers**  
* `frontend/src/components/layout/StickyStatusBar.tsx` — **0 importers** (only referenced in a comment at `Sidebar.tsx:15-16`). Note this was the M7 component satisfying "Instrument status bar shows 9 instruments"; its function moved to `Sidebar`, so the capability survives — but **QA §18 "Instrument status terlihat" should be re-verified against the new component**  
* `frontend/src/hooks/useResults.ts` \+ `api/endpoints.ts::getResults` — 0 consumers  
* `GET /api/results` — implemented, untested, unconsumed

### **Missing paths**

* FR-07 auto-refresh (no polling mechanism anywhere)  
* Authentication / authorisation (all 11 endpoints open)  
* Audit attribution (no actor recorded on any workflow mutation)  
* Inbound SIMRS authorisation for FR-17

**Duplicated semantics:** `/api/results` and `/api/instruments/{id}/orders` both serve result browsing at different grains. Not a defect — but only one is used, and the unused one carries the higher maintenance cost.

---

## **9\. Database / migration consistency**

**ORM ↔ documented schema: consistent.** All 11 `__tablename__` values match `04_DATABASE_DESIGN.md` §4–§10 exactly (`units, doctors, test_groups, tests, instruments, patients, visits, orders, instrument_messages, test_runs, results`). No undocumented tables or models.

**Migration chain: linear, single head.** `b1f9dbe772fa → 4a24240f8c32 → 621889e316b5 → c5465739f048 → 4aff9e134f16`.

### **F-1 — the critical finding (REPO-CONFIRMED)**

`b1f9dbe772fa_m1_initial_schema.py` is **not** an initial-schema migration despite its name. Reading its operations:

* `op.create_table('visits', …)` with `ForeignKeyConstraint(['id_pasien'], ['patients.id_pasien'])` — requires `patients` to already exist  
* `op.create_table('test_runs', …)`  
* `op.add_column('instrument_messages', …)`, `op.alter_column('orders', …)`, `op.drop_constraint('orders_no_registrasi_key', …)`, `op.drop_column('results', 'status_hasil')` — all **assume pre-existing tables**

It creates **2 of 11 tables**. The other 9 (`units`, `doctors`, `test_groups`, `tests`, `instruments`, `patients`, `orders`, `instrument_messages`, `results`) are never created by any migration. `4a24240f8c32_legacy_baseline.py` is a no-op (`upgrade(): pass`).

**Consequence:** `alembic upgrade head` against an empty database will fail at the first `add_column` on a non-existent table. There is **no reproducible way to stand up a new production database.**

*Fact vs inference:* the migration contents are fact. The failure is a deterministic inference from those contents — I did **not** execute it, because that would create a database. It should be empirically confirmed on a scratch DB before the fix is designed.

### **Drift risks**

| Risk | Detail |
| ----- | ----- |
| **Migrations are never exercised by the test suite** | Both API test files call `Base.metadata.create_all(bind=engine)` (`test_test_runs_api.py:22-23`, `test_order_overview.py:32-33`). Tests validate the **ORM**, not the migration chain. A migration could be wrong indefinitely and 176 tests would still pass — which is exactly how F-1 survived |
| Two divergent schema sources | Test/CI schema \= ORM metadata. Dev schema \= legacy DB \+ migrations. These are asserted to agree; nothing verifies it |
| M9.1 `users` migration | Additive, low risk — but it will be the **first** migration whose fresh-install correctness matters |
| Hardcoded credentials | `postgresql://postgres:super-user@localhost:5432/lis_marina_permata_test` in two committed test files. Pre-existing; not a runtime vulnerability (test DB, localhost) but real credential hygiene |

---

## **10\. Test coverage matrix**

| Layer | Coverage | Gap |
| ----- | ----- | ----- |
| Backend unit — parser/classification/MLLP | **Strong** — 48 ingestion \+ 19 framing | — |
| Backend unit — config/registry/identity/supervisor | **Good** — 11+10+3+13 | — |
| Service layer | **Indirect** — `TestRunService` and `overview_service` via API tests | `SimrsClient`, `build_simrs_payload`: **zero** |
| API integration | **7 of 11 endpoints** | `results`, `patients/history`, `instruments/status`, `sync-simrs`: **zero** |
| DB constraints | **Partial** — `uk_order_run_sequence` and final-run partial index via service tests | No direct constraint tests; migrations untested |
| Frontend | **Zero** — no vitest/jest/testing-library in `package.json` | Entire layer |
| End-to-end | **Zero** — 46 TC-\* cases in the QA plan, none automated | Full |
| Physical regression | **Zero committed fixtures** — session-1 raw frames live only in the dev DB | `docs/09` §16 step 4 "partially done" |

**Mapping to acceptance criteria — the load-bearing gaps:**

| AC | Automated? |
| ----- | ----- |
| AC-06, AC-07, AC-08 (Test Run, final, constraint) | ✅ |
| AC-01, AC-13 (multi-instrument, isolation) | ❌ — only 1 instrument configured |
| **AC-11 (SIMRS push)** | ❌ — endpoint and client both untested |
| **AC-12 (Historical API)** | ❌ |
| AC-09 (auto update) | ❌ — feature absent |
| TC-SEC-01/02/03, TC-HIST-03 | ❌ — auth absent |

**Tests that could give false confidence:**

1. `Base.metadata.create_all()` implies "the schema works" while never touching migrations (F-1).  
2. M5/M6 acceptance criteria are marked satisfied on the strength of a suite that never calls four of those endpoints.

**Not observed:** no test asserts private implementation details rather than behaviour. The ingestion and framing suites in particular assert parsed fields and outcomes, not internals — that discipline is sound and should be the template for the missing suites.

---

## **11\. Field evidence matrix — BC-5150**

Labels preserved exactly as `docs/09` defines them.

| Question | Status | Evidence |
| ----- | ----- | ----- |
| Transport role (LIS \= TCP client) | **VERIFIED** | §4.3, §18 T-CONN-01; packet capture |
| Endpoint `10.0.0.2:5100` | **VERIFIED** | §4.3 |
| Protocol HL7 2.3.1 over MLLP | **VERIFIED** | §18 T-CONN-01 |
| Framing `0x0B` … `0x1C 0x0D` | **VERIFIED** | §18 T-FRAME-01 |
| `0x02` idle heartbeat | **VERIFIED** | §18 T-FRAME-01; fix `19d333e`; 19 tests |
| ACK `MSA|AA` accepted | **VERIFIED** | §5.5; live `id_message=152` |
| **Background → NON\_PATIENT** | **VERIFIED** | 27 historical (§5.7) \+ 2 live (T-BC-J); no counter-example |
| Patient message *shape* | **VERIFIED (shape)** / **INSUFFICIENT (diversity)** | T-BC-A, n=1 distinct specimen |
| **Positive PATIENT\_RESULT rule** | **NOT APPROVED** | §9.5; 1 candidate falsified, 4 CANDIDATE |
| PID-5 populated as discriminator | **CANDIDATE** | §9.5 — falsifiable only by T-BC-K |
| OBR-3 numeric as discriminator | **CANDIDATE** | §9.5 |
| `IS` metadata as discriminator | **CANDIDATE** | §9.5 |
| Clinical OBX present as discriminator | **REJECTED — falsified** | Background emits clinical OBX (§9.5) |
| **The 20 PID-5-empty numeric messages** | **UNKNOWN** | §5.7 — 3 mutually exclusive explanations; **not proven QC** |
| QC / control | **UNKNOWN — zero captures** | §18.1 |
| Calibration | **UNKNOWN — zero captures** | §18.1 |
| Maintenance | **UNKNOWN — zero captures** | §18.1 |
| Startup / self-test | **UNKNOWN** | T-BC-H outstanding |
| Manual retransmission: MSH-7/MSH-10 change | **VERIFIED** (manual resend only) | §8.5, T-BC-C / T-BC-C-P |
| OBR-3 / OBR-7 invariant across manual resend | **VERIFIED** (same scope) | §8.5 — S2 did not trigger |
| MSH-10 globally unique | **VERIFIED FALSE** — repeats across messages | §18 MSH-10 census |
| Reconnect-resend / ACK-timeout resend | **UNKNOWN** | T-BC-I, T-BC-T |
| Genuine repeat run reuses OBR-3/OBR-7 | **UNKNOWN** | T-BC-B — the decisive dedup case |
| Dedup guard exercised in the field | **REPO-CONFIRMED: never** | §8.5; `repository.py:101-106` precedes `:126` |
| Specimen counter recycling | **UNKNOWN** | T-ID-02, Q4 — stop condition S1 |
| Instruments 2–9 | **UNKNOWN** — all categories | §18.1 final row |

**Blocking map:**

* **M9.2 blocked by:** T-BC-B (decisive), plus D, E, F, I, R, T-ID-02  
* **M9.3 blocked by:** T-BC-K ×2 on different days, plus L, M, N, H  
* **Production `PATIENT_RESULT` enablement blocked by BOTH:** M9.3 *and* the §10 specimen-identity question (§9.6 — "Neither alone is sufficient"), i.e. T-BC-K **and** T-ID-02/Q4

---

## **12\. Scope creep and missing scope**

### **Scope creep — almost none found**

I looked specifically for it and the codebase is disciplined:

| Candidate | Verdict |
| ----- | ----- |
| Parser registry abstraction (M8.3) | **Justified** — FR-01/FR-02 require 9 instruments and 2 protocol families |
| Classification mechanism vs. a BC-5150 `if` | **Justified** — FR-04 is generic; the mechanism/policy split is what keeps the vendor rule opt-in |
| Three-stage T1/T2/T3 transaction model | **Justified** — FR-03/AC-03 require raw persistence on every path |
| `/api/results` with 10 filters | **Mild over-build** — implemented for FR-08, superseded by M8.4's overview, now dead. Not creep at the time; **dead weight now** |
| `unverified_passthrough` policy | **Justified** — required to test the clinical path; correctly opt-in |
| Instrument listener/server mode | **Correctly refused** — `SUPPORTED_INSTRUMENT_MODES = {"client"}` rejects it explicitly |
| Refresh tokens / external IdP / 3rd role | **Correctly avoided** in the M9.1 design |

**Premature generalisation to all instruments:** *not* present — `instruments.json` holds only the verified BC-5150, and §18.1 forbids extension by analogy. That is the right posture.

### **Missing MVP scope — the real problem**

| Missing | Requirement | Assigned to |
| ----- | ----- | ----- |
| Fresh-database provisioning | Deployment prerequisite | **nothing** |
| Automatic dashboard update | **FR-07, AC-09** | M9.6 (mislabelled) |
| User identity in workflow audit | **NFR-08** | **nothing** |
| Authentication / authorisation | **NFR-09**, AC-12, TC-SEC-\* | M9.1 |
| Instrument rollout beyond BC-5150 | **FR-01, AC-01, AC-13**, QA §21.6 | **nothing** |
| SIMRS end-to-end verification | **AC-11**, QA §21.7 | **nothing** (blocked on external spec) |
| Frontend test tooling | QA plan, M9.4 | M9.4 (no concrete step) |

---

## **13\. MVP readiness criteria**

The project **already has a documented release gate** — `docs/06_QA_TEST_PLAN.md` §18 (QA baseline checklist) and §21 (sign-off criteria). I am not inventing criteria; I am scoring the existing ones.

### **A. MUST HAVE (blocks MVP; no external dependency)**

| \# | Item | Now |
| ----- | ----- | ----- |
| A1 | Reproducible fresh-database provisioning | ❌ **F-1** |
| A2 | Authentication \+ RBAC on all data endpoints (NFR-09, TC-SEC-01/03, TC-HIST-03) | ❌ |
| A3 | User attribution on finalize / unfinalize / delivery (NFR-08, QA §19) | ❌ |
| A4 | Automatic dashboard update (FR-07, AC-09, QA §18) | ❌ |
| A5 | API tests for the 4 untested endpoints, incl. AC-11 and AC-12 paths | ❌ |
| A6 | No `print`\-based logging; CORS restricted (M9.5) | ❌ |
| A7 | Clinical immutability, one-final-per-order, no overwrite | ✅ (tested) |
| A8 | Raw message traceability on every path | ✅ (M8.2) |
| A9 | Malformed message does not crash the service | ✅ (UNPARSEABLE path \+ tests) |

### **B. SHOULD HAVE**

* B1 Frontend component test tooling and a first suite  
* B2 Committed redacted regression fixtures from the session-1 corpus (`docs/09` §16 step 4\) — **time-sensitive: those frames exist only in the dev DB**  
* B3 Dead-code removal (`MainLayout`, `StickyStatusBar`, `useResults`, and a decision on `/api/results`)  
* B4 Structured audit log for instrument connect/disconnect/parse errors (NFR-08 second half)  
* B5 Task-list and `docs/09` reconciliation

### **C. BLOCKED BY FIELD / EXTERNAL ACCESS**

* C1 **Multi-instrument isolation (AC-01, AC-13, QA §21.6)** — needs a 2nd physical instrument. **This is an MVP acceptance criterion that no amount of software work can satisfy.**  
* C2 **SIMRS end-to-end delivery (AC-11, QA §21.7)** — needs the SIMRS Integration Specification from the hospital  
* C3 QC/calibration classification (M9.3) — needs T-BC-K ×2  
* C4 Dedup algorithm selection (M9.2) — needs T-BC-B et al.  
* C5 `PATIENT_RESULT` enablement — needs C3 **and** T-ID-02/Q4

### **D. FUTURE / POST-MVP**

ASTM parsers; RS-232 group (Q7 procurement); instruments 3–9 beyond the second; refresh tokens; inbound SIMRS service accounts; connection pooling tuning.

> **The honest summary:** with zero analyzer access the project can reach **A1–A9 \+ B1–B5 complete**. It still could not be signed off under QA §21, because items 6 (multi-instrument isolation), 7 (SIMRS delivery) and 8 (historical API, partly) depend on access the project does not currently have. **That gap should be surfaced to the project owner now, not discovered at sign-off.**

---

## **14\. Recommended next 5–10 tasks**

| \# | Task | Blocked? | Files / modules | Why here |
| ----- | ----- | ----- | ----- | ----- |
| **1** | **Reconcile task list \+ `docs/09` §15** — M9 status, M9.3 split, "165 passing", `env.py:14` | No | `docs/07_TASK_LIST.md`, `docs/09` | \~30 min; every later decision is made against a tracker that currently misreports reality |
| **2** | **Investigate F-1** — confirm on a scratch DB that `alembic upgrade head` fails from empty; design the fresh-install migration (a real baseline creating all 11 tables, or a documented legacy-only path). **Investigation \+ design first, no schema change** | No | `alembic/versions/`, `docs/04` | **Highest-severity finding.** It also gates M9.1's `users` migration — the first migration whose fresh-install correctness will matter |
| **3** | **M9.1a — Auth / RBAC** per the previous design, **with Option B roles** | No | `core/security.py`, `models/user.py`, `api/deps.py`, `routers/auth.py`, all 4 routers, `main.py`, frontend `client.ts` \+ `AuthContext` \+ `LoginPage` | Largest unblocked contractual item (NFR-09). Must precede M9.4 or the API tests are written twice |
| **4** | **M9.1b — Audit attribution** (NFR-08): `id_user` on finalize/unfinalize/delivery/sync | After 3 | new migration, `test_run_service.py`, `routers/test_runs.py` | **Mandatory under Option B** — with ADMIN inheriting clinical rights, attribution is the only remaining control |
| **5** | **M9.4a — Close the 4 API test gaps**, incl. `sync-simrs` (AC-11, `SimrsClient` mocked) and `patients/history` (AC-12), plus SIMRS module unit tests | Partly after 3 | `tests/api/`, `tests/conftest.py` (new) | Two PRD acceptance criteria currently have **zero** automated evidence |
| **6** | **M9.6 — Auto-refresh (FR-07 / AC-09)** — polling over the M8.4 overview API, race-safe against the M7 mutation lock | No | `hooks/`, `OrderOverviewView.tsx` | Contractual and unblocked. Reclassify out of "hardening" |
| **7** | **Preserve the field corpus** — promote redacted session-1 frames to committed fixtures (`docs/09` §16 step 4). Redaction required: `tests/test_ingestion.py:95,485` already carry a real patient name | No | `tests/fixtures/` | Time-sensitive: one dev-DB loss destroys the project's only verbatim field corpus |
| **8** | **M9.5 — Hardening**: replace 9 `print()` with structured logging; finalise CORS; standardise error handling | Partly with 3 | `integration/client.py`, `integration/instruments.py`, `main.py` | Pairs naturally with the CORS work in task 3 |
| **9** | **Dead-code removal \+ `/api/results` decision** (keep and test, or delete) | No | `MainLayout.tsx`, `StickyStatusBar.tsx`, `useResults.ts`, `routers/results.py` | Removes \~200 lines of untested, unreachable surface before auth is applied to it |
| **10** | **Frontend test tooling \+ first suite** (M9.4b) | After 3, 6 | `frontend/package.json`, `src/**/*.test.tsx` | Last because auth and auto-refresh change what the components look like |

**In parallel, not on the critical path:** schedule BC-5150 session 2 (T-BC-K ×2 — needs Q1 answered by lab management) and the second-instrument survey (T-SURVEY-01, needs Q5).

---

## **15\. Blockers**

| Class | Blocker | Blocks |
| ----- | ----- | ----- |
| **Internal — actionable now** | F-1 fresh-DB path | Any new deployment; MVP A1 |
| **Internal — sequential** | No user model | NFR-08 attribution, all auth tests |
| **Analyzer access** | T-BC-K ×2 (different days), L, M, N, H | M9.3 QC rules; positive rule |
| **Analyzer access** | T-BC-B, D, E, F, I, R | M9.2 algorithm |
| **Analyzer access** | T-ID-02 | Specimen identity; stop condition S1 |
| **Analyzer access** | Both of the above | `PATIENT_RESULT` enablement (§9.6) |
| **Physical instrument access** | 2nd instrument | **AC-01, AC-13, QA §21.6** |
| **Lab management** | Q1 (QC on demand), Q3 (ACK withholding), Q5 (instruments in routine use), Q7 (serial converter budget) | Scheduling of the above |
| **External system** | SIMRS Integration Specification | **AC-11, QA §21.7**; inbound auth for AC-12 |

---

## **16\. Decisions requiring owner confirmation**

1. **RBAC: Option A or Option B?** I now recommend **B** (ADMIN inherits ANALYST), reversing my prior advice — the PRD defines only one human actor and SysDesign §11.2 is explicitly an example. **If B, audit attribution (task 4\) is mandatory, not optional.**  
2. **F-1 remediation strategy** — a true baseline migration creating all 11 tables, or an officially documented "legacy database required" deployment model? This determines whether a greenfield hospital deployment is even possible.  
3. **`/api/results` — keep or delete?** Implemented, untested, unconsumed. Testing it costs effort; deleting it removes an FR-08 fallback.  
4. **QA §21.6 (multi-instrument isolation) is unsatisfiable with one instrument.** Does MVP sign-off wait for a second instrument, or is the criterion formally scoped down? This is a scope decision, not an engineering one.  
5. **SIMRS specification availability** — AC-11 cannot be verified without it. Is MVP sign-off gated on it, or does SIMRS delivery ship "implemented, unverified"?  
6. **Interim BC-5150 posture (Q9 in `docs/09`)** — the system is currently *safe but inert*: no patient result reaches the clinical tables. Is that acceptable for an MVP demonstration, or must `PATIENT_RESULT` be enabled (which requires C3 **and** C5)?  
7. **Login body format, token storage, deployment shape** — carried forward from the M9.1 design (§13 there).

---

## **17\. Recommended documentation updates**

| Doc | Update |
| ----- | ----- |
| `07_TASK_LIST.md` | M9 status; split M9.3; correct M5/M6/M7 completion claims; add the three unassigned items (F-1, NFR-08, instrument rollout) |
| `09_PHYSICAL_INSTRUMENT_VALIDATION.md` | §15 "165 passing" → 176 |
| `04_DATABASE_DESIGN.md` | Add a **provisioning** section stating the fresh-install path and the legacy-upgrade path explicitly (currently neither is documented) |
| `03_SYSTEM_DESIGN.md` | §11.2 — replace the "Contoh" role tree with the decided contract once §16.1 is answered; add the CORS/deployment shape |
| `02_PRD.md` | FR-16 — note that `Success` is realised as `delivered` (or align the token) |
| `06_QA_TEST_PLAN.md` | Note that §18 "Instrument status terlihat" is now served by `Sidebar`, not `StickyStatusBar` |
| **New** | A short `DEPLOYMENT.md`: secret generation, first-admin bootstrap, DB provisioning, CORS origin, `VITE_API_BASE_URL` |

---

## **18\. Recommended task-list restructuring**

Recommendation only — no edits made.

M9 — QA, Security & Release Readiness

  M9.0  Deployment Foundation            ← NEW (F-1)  
        fresh-DB provisioning; migration chain verified from empty;  
        migrations exercised in CI (not only Base.metadata.create\_all)

  M9.1a Security Foundation               (auth, RBAC, CORS)  
  M9.1b Audit Attribution                 (NFR-08 — mandatory under Option B)

  M9.2  Deduplication Refinement          \[BLOCKED — analyzer\]  
  M9.3a Fail-Closed Classification        ✅ COMPLETE (28ad9b3)   ← split  
  M9.3b QC / Calibration Rules            \[BLOCKED — T-BC-K\]      ← split

  M9.4  Test Completion  
        a) backend/API gap closure (4 endpoints \+ SIMRS module)  
        b) frontend tooling \+ first suite  
        c) field-corpus regression fixtures

  M9.5  Production Hardening              (logging, CORS, errors, pooling)

  M10 — Functional Completion             ← NEW milestone  
  M10.1 Automatic Dashboard Update        (FR-07 / AC-09 — moved out of M9.6)  
  M10.2 Second Instrument Integration     (AC-01 / AC-13)  \[BLOCKED — hardware\]  
  M10.3 SIMRS End-to-End Verification     (AC-11)          \[BLOCKED — external spec\]

Four structural changes, each with a stated reason:

1. **Add M9.0.** F-1 is currently owned by nobody and blocks deployment.  
2. **Split M9.3 into a/b.** One checkbox cannot represent "safe half shipped, evidence half blocked" — which is exactly why the tracker is misleading today.  
3. **Move auto-refresh out of M9.** FR-07 is a functional requirement, not hardening; filing it under "QA & Hardening" is what let M7 close without it.  
4. **Create M10 for the contractual items that remain after M9.** It makes the externally-blocked MVP criteria visible on the roadmap instead of surfacing them at sign-off.

---

**Read-only constraint honoured: no files modified, nothing staged, committed or pushed; no database data touched; no analyzer communication performed.** The `.env` inspection printed key names only, with values redacted.

If it would help to have this as a shareable page for the project owner rather than terminal scrollback, say the word and I'll publish it as an artifact — that would create one HTML file, so I've held off given the read-only instruction.

