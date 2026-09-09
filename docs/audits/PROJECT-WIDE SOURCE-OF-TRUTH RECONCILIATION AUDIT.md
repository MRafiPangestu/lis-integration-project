> Status: READ-ONLY AUDIT RECORD
> Authority: NON-AUTHORITATIVE
> Purpose: Project audit / reconciliation
> Audited commit: 28ad9b3
> Date: 2026-09-XX
> Supersession: This document does not override PRD, System Design,
> Database Design, QA Plan, Physical Validation, or milestone decision records.

This document is an audit of the project's source-of-truth structure; it is not itself a source of truth for product requirements, architecture, schema, physical behaviour, or milestone implementation decisions.

The three M8 investigation documents are the main sources I haven't read in depth. Let me locate and read them, then reconcile.

No files modified. Full reconciliation below.

*(Note: a stray background-task notification — "Update master test matrix statuses" — arrived mid-audit and was already stopped. I did not start it and it made no changes.)*

---

# **SOURCE-OF-TRUTH RECONCILIATION AUDIT**

**LIS Middleware — RS Marina Permata** · `refactor/orm-architecture` @ `28ad9b3` · tree clean · local \== origin (`git rev-parse` verified)

---

## **1\. Executive conclusion**

**The project's documentation discipline is working better than the previous audit credited, and one of that audit's recommendations was wrong.**

Reading M8.4/M8.5/M8.6 as first-class decision records changes three conclusions:

|  | Previous audit said | Reconciled finding |
| ----- | ----- | ----- |
| `MainLayout.tsx`, `StickyStatusBar.tsx` | "dead code — remove" | **Deliberately retained under a frozen decision.** M8.5 §20 D1: *"Retire it from the shell, **keep the file**"*; M8.6 §10 lists both under **"Must NOT change"**; M8.6 §11 forbids *"deleting retained files"*. **My prior task 9 would have violated a frozen decision.** — FACT |
| M8.4/M8.5/M8.6 compliance | not assessed | **All three implementations follow their decision records with near-perfect fidelity.** 14 of 15 frozen decisions verified in code; one (M8.4 D4 `total_runs`) is documented-but-unimplemented — FACT |
| Frontend test tooling absence | "gap" | **A documented, permitted fallback.** M8.5 §20 D4 offered "add vitest **or** accept Tier 1 \+ manual checklist and move §17 to M9.4". The fallback was taken legitimately — FACT |

**What does not change** — the five structural findings stand and are now better evidenced:

* **F-1 provisioning gap is confirmed and deeper than reported.** There is **no `.sql` file anywhere in the repository**, `04_DATABASE_DESIGN.md` contains **zero `CREATE TABLE` statements** (it is a column-specification document), and `4a24240f8c32_legacy_baseline.py` is a **no-op stamp** whose name is the only hint that a legacy database is assumed. — FACT  
* **FR-07/AC-09 auto-refresh** remains contractual and unimplemented.  
* **NFR-08 user attribution** remains contractual and unassigned.  
* **4 endpoints \+ the entire SIMRS module remain untested.**  
* **8 of 9 instruments remain unintegrated.**

**The single most important structural insight:** the project has an excellent authority hierarchy for *requirements* (PRD §11), *evidence* (doc 09 §1), and *milestone decisions* (M8.x investigations) — and **no declared authority at all for milestone status or deployment configuration.** That is precisely where the drift lives.

---

## **2\. Source-of-truth hierarchy**

**This hierarchy is not invented — it is assembled from self-declarations in the documents themselves.**

| Rank | Authority | Self-declaration (FACT) |
| ----- | ----- | ----- |
| 1 | **`01_PROJECT_BRIEF.md`** — goals, scope boundaries, success criteria | §11 *"Project Brief ini mendefinisikan tujuan, ruang lingkup, batasan, dan prinsip utama proyek"* |
| 2 | **`02_PRD.md`** — *what* the system must do; actors; acceptance criteria | §11 *"PRD ini mendefinisikan **apa yang harus dilakukan sistem** dan batasan fungsionalnya"* |
| 3 | **`03_SYSTEM_DESIGN.md`** — *how*, architecturally | PRD §11: *"bagaimana kebutuhan tersebut diwujudkan secara arsitektural dan teknis"* |
| 4 | **`04_DATABASE_DESIGN.md`** — data representation | PRD §11: *"bagaimana data … direpresentasikan di PostgreSQL"*; §1554: *"Implementasi PostgreSQL harus mengikuti desain final di atas"* |
| 5 | **`M8.x_Investigation.md`** — milestone-scoped frozen decisions | M8.6 closing: *"This document is the source of truth for the M8.6 implementation"* |
| 6 | **`09_PHYSICAL_INSTRUMENT_VALIDATION.md`** — physical truth **only** | §1: *"It is the project's authoritative physical-instrument validation record"* **and** *"No source, schema, migration, test or task-list change is authorised by this document"* |
| 7 | **`06_QA_TEST_PLAN.md`** — verification method and release gate | §18, §21 constitute the sign-off criteria |
| — | **`07_TASK_LIST.md`** | **Declares no authority.** Header is only *"Task List — LIS Middleware MVP / Implementation Roadmap"* |
| — | **Repository** | Ground truth for *what exists*, never for *what should exist* |

### **Precedence rule (derived, FACT-based)**

> **Requirement conflicts → PRD wins. Architecture conflicts → System Design wins. Data-representation conflicts → Database Design wins. Milestone-implementation conflicts → that milestone's investigation doc wins, but only within its own scope. Physical-behaviour conflicts → doc 09 wins absolutely and overrides vendor capability, simulators, and the task list.**

### **The two gaps — RECOMMENDATION**

**Gap 1 — nothing is authoritative for milestone status.** The task list is used as if it were, but declares nothing, and is demonstrably stale (`:612` `M9 | Not Started` vs `28ad9b3`).

**Gap 2 — nothing is authoritative for deployment configuration.** `instruments.json` is gitignored; `.env` is gitignored; CORS lives in `main.py`; the DB provisioning assumption lives nowhere.

*Minimal recommended rule* (two sentences to add to `07_TASK_LIST.md`, and one new document):

> `07_TASK_LIST.md` is authoritative for milestone status and for nothing else. A milestone may be marked complete only when its acceptance criteria are demonstrated by an automated test, a cited investigation-document verification, or a dated entry in `09_PHYSICAL_INSTRUMENT_VALIDATION.md` §18.

---

## **3\. Full document authority matrix**

| Source | Primary authority for | Secondary authority for | Must not override |
| ----- | ----- | ----- | ----- |
| **01 Project Brief** | Business goals; in/out of scope (§4.1/4.2); MVP success criteria (§10); instrument scope (§3) | Data hierarchy (§6); integration boundary (§7) | PRD functional detail; any technical decision |
| **02 PRD** | Functional \+ non-functional requirements; **actors (§3)**; acceptance criteria (§6); out-of-scope (§7) | Delivery-state vocabulary (FR-16) | Architecture; schema; **field evidence**; milestone sequencing |
| **03 System Design** | Architecture; layering; network topology (§3); deployment (§13); security posture (§11) | Role illustration (§11.2 — **explicitly "Contoh:"**) | PRD requirements; **doc 09 physical facts**; DB column definitions |
| **04 Database Design** | Table/column/constraint definitions; traceability rules (§16); finality rule (§13.1) | Delivery-status literals | PRD *requirements*; migration mechanics |
| **06 QA Test Plan** | Test cases (46 TC-\*); QA baseline (§18); **sign-off criteria (§21)**; defect severity (§20) | Evidence format (§19) | What the system must *do*; physical evidence classification |
| **07 Task List** | **(declares nothing — de facto milestone status)** | Implementation sequencing; per-milestone acceptance criteria | Everything above it; **must not assert completion the repo contradicts** |
| **08 Master Data** | Instrument identity/seed eligibility; the `protokol = NULL`\-if-unverified rule (§6.2) | Field-confirmed instrument config | Physical protocol truth (defers to doc 09\) |
| **09 Physical Validation** | **Physical instrument behaviour, absolutely**; evidence labels; the verified-rule register (§18.1) | M9.2/M9.3 readiness; execution order (§16) | **Authorises no code, schema, migration, test or task-list change** (self-declared, §1) |
| **M8.4 Investigation** | M8.4 API semantics: grain, effective run, finality, delivery, abnormal count, dates, pagination, indexes | Endpoint naming; timezone convention (D1) | Anything outside M8.4 (§16 enumerates) |
| **M8.5 Investigation** | M8.5 navigation, sidebar, detail reuse, state architecture, **file-retention decisions (D1)** | Frontend test posture (D4) | Backend, API contract, clinical components (§16) |
| **M8.6 Investigation** | M8.6 visual system; frozen decisions F1–F7; allowed file scope (§10); forbidden changes (§11) | Brand strings (R2) | Business rules, contracts, data grain (§11); **its prohibitions are milestone-scoped, not permanent** |

**Nine questions answered:** business requirements → PRD · architecture → System Design · schema → Database Design · acceptance criteria → PRD §6 \+ QA §18/§21 · milestone status → **nobody (Gap 1\)** · field truth → doc 09 · frozen milestone decisions → M8.x investigations · deployment config → **nobody (Gap 2\)** · precedence → as stated in §2.

---

## **4\. M8.4 reconciliation**

**Objective (§1):** instrument-scoped operational Order worklist. Verdict was *"ready for implementation, but the task definition is inaccurate in four places."*

| Frozen decision | Where | Implementation | Status |
| ----- | ----- | ----- | ----- |
| Row grain \= **one Order** (Patient/Visit/TestRun rejected, §3) | §3 | `overview_service.py` docstring \+ `func.count(Order.id_order)` | **CURRENT / BINDING** ✅ |
| Effective run \= `is_final DESC, run_sequence DESC, id_run DESC` (**correctness requirement**, must match `App.tsx`) | §4 | `_effective_run_lateral()` — exact ordering | **CURRENT / BINDING** ✅ |
| No final run is a **normal state**, not an error | §5 | `is_final = bool(row.effective_is_final)` | **CURRENT** ✅ |
| `delivery_status = NULL` when not final; **no synthetic value** | §6, D5 | `row.effective_delivery_status if is_final else None` | **CURRENT** ✅ |
| Abnormal count over the **effective run only** | §7 | `Result.id_run == er.c.id_run` | **CURRENT** ✅ (R3 mitigated) |
| Instrument scope via **EXISTS semi-join** on `test_runs` | §8 | `_exists_run_for_instrument()` | **CURRENT** ✅ (R4 mitigated) |
| Filter `Order.waktu_order`, **half-open** `[from, to)` | §9 | `>= date_from`, `< date_to` | **CURRENT** ✅ |
| **D1** timezone \= server-local naive | §19 | Documented in service docstring \+ router `Query` description | **RESOLVED as proposed** ✅ |
| **D2** endpoint \= `/instruments/{id}/orders` | §19 | `instruments.py:43` | **RESOLVED as proposed** ✅ |
| **D3** lateral filtered by `id_instrument` | §19 | `TestRun.id_instrument == instrument_id` inside the lateral | **RESOLVED as proposed** ✅ |
| Offset pagination, `page_size` 1–100, `{items,page,page_size,total}`, tie-break `id_order DESC` | §10 | Router \+ `PaginatedOrderOverviewResponse` | **CURRENT** ✅ |
| 4 indexes; 5th deliberately omitted | §12 | `4aff9e134f16` — 4 created, omission documented in the migration docstring | **CURRENT** ✅ |
| **D4 — include `total_runs`** | §19 | **Absent** from `overview.py`, service, frontend | **DOCUMENTED BUT UNIMPLEMENTED** |

**Deviations:** one (D4). It is a proposed default, not a frozen decision, and its absence harms nothing — M8.5 D5 instead surfaces re-runs via `effective_run_sequence > 1` → "Run N", which is implemented (`OrderOverviewRow.tsx:49,125-126`). **RECOMMENDATION: record D4 as consciously dropped rather than leaving it as an unexplained gap.**

**Contradictions with other sources:** none. §16 forbids frontend work — honoured; the frontend arrived in M8.5.

---

## **5\. M8.5 reconciliation**

**Objective (§1):** dashboard integration with **no backend change**; one mandatory refactor (extract detail from `App.tsx`).

| Frozen decision | Implementation | Status |
| ----- | ----- | ----- |
| **No React Router** | `package.json` runtime deps \= `react`, `react-dom` only | **CURRENT / STILL BINDING** ✅ |
| Sidebar **replaces** `StickyStatusBar` in the shell; **keep the file** (D1) | `Sidebar.tsx` in shell; `StickyStatusBar.tsx` present, unreferenced, cited in a comment at `Sidebar.tsx:15-16` | **CURRENT — intentional retention** ✅ |
| Instrument identity from `/api/instruments/status`; **no hardcoded PoC ids** | `useInstruments` → `Sidebar`; no `INSTRUMENTS` array | **CURRENT** ✅ (R4 mitigated) |
| Drill-down preselects `id_visit` **and** `id_order` | `detailTarget = {nomorRm, idVisit, idOrder}` (`App.tsx`) | **CURRENT** ✅ (R2 mitigated) |
| Overview \= compact Order rows, not a clinical grid | `OrderOverviewTable` / `OrderOverviewRow` | **CURRENT** ✅ |
| PoC palette **not** adopted | enterprise tokens retained in `index.css` | **CURRENT** ✅ |
| Detail extracted to `OrderDetailView`, clinical logic unchanged | `components/detail/OrderDetailView.tsx` | **CURRENT** ✅ (R1 mitigated) |
| **D2** `page_size = 25` | `useInstrumentOrders.ts:6 OVERVIEW_PAGE_SIZE = 25` | **CURRENT** ✅ |
| **D3** no overview search box; MRN search stays on the search/detail path | Search relocated by M8.6 to the overview *toolbar*, but still drives the **patient-history detail path**, not overview filtering | **SUPERSEDED IN PLACEMENT, SUBSTANCE PRESERVED** — no client-side filtering was introduced |
| **D5** show "Run N" only when `> 1` | `OrderOverviewRow.tsx:49` | **CURRENT** ✅ |
| **D4** add vitest \+ testing-library in M8.5 | Not added; Tier-1 (build \+ lint \+ manual checklist) taken | **DEFERRED — via the document's own permitted fallback**, not a violation |
| Date strings sent verbatim, never `toISOString()` | 3 `toISOString` occurrences in `src/` are **all comments forbidding it**; zero actual calls | **CURRENT** ✅ (R3 mitigated) |
| `MainLayout` shell replaced | `MainLayout.tsx` present, 0 importers | **CURRENT** — retention implied by M8.6 §10 |

**Deviations:** D4 (permitted fallback) and D3's placement (superseded by a later milestone that explicitly reasoned about it). Both legitimate.

---

## **6\. M8.6 reconciliation**

**Objective (§1):** PoC visual language *"without changing a business rule, contract or data grain established in M8.1–M8.5."* Revision 2 explicitly **overturns** four Revision-1 constraints and records each (§15).

| Frozen decision | Implementation | Status |
| ----- | ----- | ----- |
| **F1** sidebar expanded on load, manual collapse to 64px, **no persistence** | `App.tsx: useState(true)` with the comment *"No persistence — a reload always returns to expanded"*; `localStorage`/`sessionStorage` count in `src/` \= **0** | **CURRENT** ✅ |
| **F2** collapsed \= 64px rail, not full hide | `Sidebar` `expanded` prop | **CURRENT** ✅ |
| **F3** search → overview toolbar; **availability narrows** (behavioural, accepted) | `searchProps` passed to `OrderOverviewView`; `handleSearchSubmit` body unchanged | **CURRENT — but see O8 below** |
| **F4** `All` \= sentinel `1900-01-01T00:00` → `2999-12-31T23:59`, server-paginated | `dateRange.ts:45-46 ALL_DATE_FROM / ALL_DATE_TO` | **CURRENT** ✅ |
| **F5** custom inputs replaced by a muted "All dates" line under `All` | per spec | **CURRENT** ✅ |
| **F6** centred five-button window, inert ellipses | `Pagination.tsx` | **CURRENT** ✅ |
| **F7** detail buttons: logic protected, `className` \+ radius only | `.lis-btn` system | **CURRENT** ✅ |
| **R2** brand `LIS Server` / `Marina Permata`; *"LIS Middleware" stays the system term in docs* | Sidebar brand block | **CURRENT** ✅ |
| §11 no polling / `setInterval` / `setTimeout` | count in `src/` \= **0** | **CURRENT — but milestone-scoped** ⚠ |
| §11 no new dependencies, no test framework | `package.json` unchanged | **CURRENT — but milestone-scoped** ⚠ |
| §10 **Must NOT change**: `MainLayout.tsx`, `StickyStatusBar.tsx`, `hooks/*`, `api/*`, `types/*`, `package.json`, all of `backend/` | all unmodified | **STILL BINDING within M8.6** ✅ |
| §11 *"deleting retained files"* forbidden | both files present | **STILL BINDING** ✅ |

### **Two scope-lifetime clarifications — RECOMMENDATION, high importance**

1. **M8.6 §11's prohibitions on polling and on new dependencies are milestone-scoped, not permanent.** They exist because M8.6 was a *visual polish* milestone. A future reader could reasonably misread them as project-wide bans that block **M9.6 (auto-refresh, which requires polling)** and **M9.4 (frontend tests, which require a test framework)**. This should be stated explicitly when the task list is next touched.  
2. **O8 was never answered by the owner.** M8.6 §15 lists it as an open question with a recommended default (*"No — accept the extra click"*), and the default was applied. That is procedurally correct, but the owner should now confirm or reverse it, because **F3 is the one genuinely behavioural change M8.6 made** and the document itself says *"If preserving search on the detail screen matters, that must be raised before implementation."*

**No M8.4/M8.5/M8.6 decision is CONTRADICTED by the repository.** One is SUPERSEDED (M8.5 D3 placement, by M8.6 F3), one is DOCUMENTED BUT UNIMPLEMENTED (M8.4 D4), one is DEFERRED via its own permitted fallback (M8.5 D4).

---

## **7\. PRD ↔ System Design ↔ QA consistency, and requirement traceability**

### **Consistency findings**

| \# | Issue | Verdict |
| ----- | ----- | ----- |
| 1 | **PRD §3 defines exactly one human actor (Laboratory Analyst).** System Design §11.2's `Analis`/`Administrator` tree is prefixed **"Contoh:"** and followed by *"Hak akses aktual dapat disesuaikan dengan kebutuhan rumah sakit"* | **Not a contradiction — a gap.** No document contractually defines an Administrator. Decisive for §10 — FACT |
| 2 | PRD FR-16 delivery vocabulary `Pending/Sending/**Success**/Failed` vs DB Design `:472` \+ code `pending/sending/**delivered**/failed` | **Cosmetic.** FR-16 requires four *distinguishable* states; QA §18 itself writes `pending → sending → delivered/failed`. **QA and DB Design agree with the code; only the PRD's literal differs** — FACT |
| 3 | PRD §3.1 grants the Analyst both finalize **and** SIMRS send; SysDesign §11.2 example lists only "Select Final Run" | PRD wins (owns *what*) — FACT |
| 4 | Brief §7 / FR-17 / AC-12 require an **authorised** SIMRS→LIS history API; `SIMRS_API_KEY` is **outbound only** (`simrs_client.py:33`) and no inbound auth exists | **Genuine gap** — FACT |
| 5 | FR-04 permits excluding histogram/scattergram payloads | Parser behaviour is **compliant, not lossy-by-accident** — FACT |

### **Requirement traceability matrix**

| Requirement | Source | Milestone | Implementation | Test | Evidence | Status |
| ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| Multi-instrument connectivity | FR-01, AC-01 | M8.1 | supervisor \+ config; **1 of 9 configured** | 13 supervisor \+ 11 config | doc 09 §4.1 | **PARTIAL** |
| Instrument isolation | AC-13, QA §21.6 | M8.1 | thread-per-instrument | supervisor tests (simulated) | none physical | **IMPLEMENTED \+ UNVERIFIED** |
| HL7 processing | FR-02, AC-02 | M8.3 | `bc5150_hl7` parser \+ registry | 10 registry \+ 48 ingestion | doc 09 T-CONN-01 | **IMPLEMENTED \+ VERIFIED** |
| ASTM | FR-02 | M8.3 | none | — | — | **DEFERRED (documented)** |
| Raw message persistence | FR-03, AC-03 | M8.2 | T1/T2/T3 | ingestion tests | live rows | **IMPLEMENTED \+ VERIFIED** |
| Classification / filtering | FR-04 | M8.2/M8.2b/M9.3a | fail-closed, Background only | 28 bc5150 tests | doc 09 §5.7, §18.1 | **IMPLEMENTED \+ VERIFIED (Background only)** |
| Patient/Visit/Order hierarchy | §2.5, NFR-07 | M1/M2 | 11 models | ingestion \+ overview | — | **IMPLEMENTED \+ VERIFIED** |
| Test Run semantics (no overwrite) | FR-13/14, AC-06 | M4 | `run_sequence` MAX+1 \+ UNIQUE | ingestion \+ API | — | **IMPLEMENTED \+ VERIFIED** |
| Final run \+ one-per-order | FR-15, AC-07/08 | M4 | service \+ partial unique index | 20 API tests | — | **IMPLEMENTED \+ VERIFIED** |
| Delivery workflow | FR-18, AC-11 partial | M4/M6 | 4-state machine | API tests | — | **IMPLEMENTED \+ VERIFIED** |
| **SIMRS push** | **FR-16, AC-11** | M6 | `SimrsClient` \+ orchestration | **ZERO** | `SIMRS_BASE_URL` unset | **IMPLEMENTED \+ UNVERIFIED / BLOCKED (external)** |
| **Historical retrieval** | **FR-17, AC-12** | M5.3 | `/api/patients/{rm}/history` | **ZERO** | — | **IMPLEMENTED \+ UNVERIFIED** |
| Result display \+ abnormal flags | FR-08/09, AC-10 | M7 | full component set | none automated | manual checklist | **IMPLEMENTED \+ UNVERIFIED** |
| **Authentication / authorisation** | **NFR-09, AC-12, TC-SEC-01/03, TC-HIST-03** | M9.1 | **none** | none | — | **MISSING** |
| **Workflow audit incl. user identity** | **NFR-08** | **unassigned** | timestamps only, no actor | none | — | **MISSING** |
| **Auto-refresh** | **FR-07, AC-09, QA §18** | M9.6 | **none** | none | — | **MISSING** |
| Deployment on-prem, no internet | NFR-10 | M8.1 | client-mode TCP, local DB | — | doc 09 §4.3 | **IMPLEMENTED \+ VERIFIED** |
| Production hardening | NFR-03/05/09 | M9.5 | 9 `print()`, CORS `*` | — | — | **MISSING** |
| EMR / billing / inventory / manual entry / value editing | Brief §4.2, PRD §7 | — | absent by design | TC-SEC-02 satisfied architecturally | — | **OUT OF SCOPE** ✅ |

---

## **8\. M1–M8 exit integrity**

| MS | A. Scope implemented | B. AC tested | C. Deviations | D. "Complete" honest? | E. Work leaked forward | F. Impl ✔ / Verif ✘ |
| ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| **M1** | Partly — DDL \+ dev migration \+ seed | On the **dev DB**, not via migrations | **F-1**: no fresh-install path | **NO** | Provisioning leaked to nobody | **Yes** |
| **M2** | Yes — 11 models, session, Alembic | Structural, verified | none | **YES** | — | No |
| **M3** | Yes | Via ingestion tests | superseded by M8.1/8.2 | **YES** | — | No |
| **M4** | Yes | 20 API tests | none | **YES** | — | No |
| **M5** | Yes (5 endpoints) | **3 of 5 untested** | AC *"All specified endpoints return correct data"* asserted, not demonstrated | **NO — verification incomplete** | Testing leaked to M9.4 | **Yes** |
| **M6** | Yes | **ZERO tests**; unconfigured | AC-11 never exercised end-to-end | **NO — verification incomplete** | Testing → M9.4; E2E → blocked | **Yes** |
| **M7** | **No — FR-07/AC-09 missing** | Manual only | M7's AC list (`:341-348`) **omits auto-refresh entirely** | **NO** | **FR-07 leaked to M9.6** | Yes |
| **M8.1** | Yes | 24 tests | 1 of 9 instruments configured | **YES** (capability) | Rollout unassigned | Partly |
| **M8.2** | Yes | 48 tests | specimen identity **DEFERRED (documented)** | **YES** | Identity → M9/§10 (documented) | No |
| **M8.2b** | Yes | included | QC extension **BLOCKED (documented)** | **YES** | → M9.3b (documented) | No |
| **M8.3** | Yes | 10 tests | ASTM **DEFERRED (documented)** | **YES** | — | No |
| **M8.4** | Yes | 27 tests | **D4 `total_runs` unimplemented** | **YES** | — | No |
| **M8.5** | Yes | Build+lint+manual (Tier 1, permitted) | D4 test deps deferred **per the doc's own fallback** | **YES** | Tests → M9.4 (documented) | Partly |
| **M8.6** | Yes | V1–V27 manual \+ independent audit | **F3 behavioural narrowing; O8 unconfirmed** | **YES** | — | Partly |

**Answer to E, precisely:** three milestones leaked work forward. Two did so **with documentation** (M8.2 identity, M8.3 ASTM — legitimate deferrals). **M7 leaked FR-07 silently** — its acceptance criteria simply never listed it. That is the only genuine milestone-boundary error.

**No already-validated M8 decision is reopened by this audit.**

---

## **9\. M9 / M10 recommended structure**

| Proposed | Why it exists | Source requirement | Depends on | Impl | Verif | Release impact |
| ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| **M9.0 Deployment Foundation** | No fresh-DB path; migrations never tested | Brief §8, NFR-10, DB Design §1554 | — | ✘ | ✘ | **HARD GATE** — nothing deployable without it |
| **M9.1a Security Foundation** | 11 open endpoints; PHI exposed | NFR-09, AC-12, TC-SEC-01/03, TC-HIST-03 | M9.0 (its migration) | ✘ | ✘ | **HARD GATE** |
| **M9.1b Audit Attribution** | No actor on any workflow mutation | **NFR-08**, QA §19 | M9.1a | ✘ | ✘ | **HARD GATE** (mandatory under Option B) |
| **M9.2 Dedup Refinement** | Guard unreachable for BC-5150 | M9.2 task text; doc 09 §8 | T-BC-B/D/E/F/I/R | ✘ | ✘ | **Not a gate** — fail-closed is safe today |
| **M9.3a Fail-Closed Classification** | Already shipped | FR-04; doc 09 §9 | — | **✔ `28ad9b3`** | **✔ 28 tests** | **Already met** |
| **M9.3b QC / Calibration** | Zero QC captures | doc 09 §9.5 | T-BC-K ×2 | ✘ | ✘ | **Not a gate** for a fail-closed MVP |
| **M9.4 QA Gap Closure** | 4 endpoints \+ SIMRS module untested; no FE tooling | QA §18/§21; M8.5 §17 Tier 2 | M9.1a | ✘ | ✘ | **HARD GATE** |
| **M9.5 Production Hardening** | 9 `print()`, CORS `*` | NFR-03/05/09 | M9.1a (CORS) | ✘ | ✘ | **Gate** (partial) |
| **M10.1 Auto-Refresh** | **Contractual, not hardening** | **FR-07, AC-09, QA §18** | — | ✘ | ✘ | **HARD GATE** |
| **M10.2 Second Instrument** | 1 of 9 configured | FR-01, AC-01, AC-13, QA §21.6 | physical access | ✘ | ✘ | **HARD GATE — externally blocked** |
| **M10.3 SIMRS E2E** | Never sent a real request | FR-16, AC-11, QA §21.7 | SIMRS spec | ✔ code | ✘ | **HARD GATE — externally blocked** |

### **Answers to the placement questions**

* **Auto-refresh in M10?** It belongs in **neither M9 nor M10 as a "functional completion" bucket** — it is unfinished **M7** work. Placing it in M10.1 is acceptable *provided* the task list records that it discharges FR-07/AC-09 and closes M7's gap. Filing it under "QA & Hardening" (today's M9.6) is what let it go unnoticed. — RECOMMENDATION  
* **Second instrument in M10?** **No — it is a release gate, not a development milestone.** No code is required; `instruments.json` plus a parser plus a field session. Modelling it as a milestone implies engineering effort that does not exist and hides the fact that it is externally blocked. — RECOMMENDATION  
* **SIMRS E2E in M10?** **Also a release gate, not a milestone.** The code is written (M6); what is missing is the counterparty specification. — RECOMMENDATION  
* **Therefore:** M10 should contain **only M10.1 (auto-refresh)**. M10.2 and M10.3 become entries in a **release-gate register** (§15) with explicit external owners.

---

## **10\. RBAC recommendation — Option B**

This confirms the reversal made in the previous audit, now with the full document set.

**Evidence:**

1. **`02_PRD.md` §3 — the authoritative actors document — defines exactly one human actor: Laboratory Analyst** (§3.1). §3.2 is SIMRS (a system), §3.3 is instruments. There is **no Administrator actor in the PRD**. — FACT  
2. **`03_SYSTEM_DESIGN.md` §11.2 prefixes its role tree with "Contoh:"** and states *"Hak akses aktual dapat disesuaikan dengan kebutuhan rumah sakit"* — illustrative, explicitly adjustable. — FACT  
3. **`TC-SEC-02` ("user without permission cannot Modify Result / Delete Result / Modify Test Run Clinical Data") is satisfied architecturally, not by RBAC** — no such endpoint exists across the 11-endpoint surface, and PRD §2.1 / NFR-02 / Brief §4.2 forbid one. — FACT

**Conclusion (RECOMMENDATION):** separation of duties is **not** the primary control in this system. The primary control is **architectural immutability** — the absence of any clinical-mutation endpoint. Option A would therefore restrict ADMIN from actions that carry no clinical-corruption risk, at real operational cost.

### **Option B, stated explicitly**

* **ADMIN inherits these clinical actions:** `finalize`, `unfinalize`, `delivery/start`, `delivery/success`, `delivery/fail`, `sync-simrs`, plus all reads.  
* **ADMIN additionally holds:** user creation/deactivation, role assignment, system configuration.  
* **Why separation of duties is not the primary control:** the risk PRD §2.1 and QA §20 classify as *Critical* is clinical value corruption — architecturally impossible. Finalization is reversible (`unfinalize` exists, `test_run_service.py:63`). SIMRS delivery is idempotent-guarded (`nowait` row lock, 409 on concurrent delivery).  
* **Audit attribution becomes MANDATORY.** With role no longer distinguishing actors, `id_user` on every workflow mutation is the **only** remaining mechanism satisfying **NFR-08** (*"Informasi audit harus mencakup timestamp dan identitas pengguna"*) and QA §19. **M9.1b is a hard gate, shipped with M9.1a.**  
* **A third role remains unnecessary.** Two roles cover all 11 endpoints plus user management.

**Operational consequence of NOT choosing B (i.e. choosing A):** every supervisor needs two accounts. In a lab of this size the predictable outcome is credential sharing, which destroys attribution — making NFR-08 compliance *worse* than Option B with attribution.

---

## **11\. Database / migration / provisioning assessment**

### **FACT**

1. **No `.sql` file exists anywhere** in the repository (`find -name "*.sql"` → empty).  
2. **`04_DATABASE_DESIGN.md` contains zero `CREATE TABLE` statements** — the schema is specified as markdown column tables (§4.1–§10.1).  
3. **`04_DATABASE_DESIGN.md:1554`** states an earlier *"SQL awal … merupakan baseline/schema awal dan **belum sepenuhnya sama dengan desain final ini**"* — an external baseline is acknowledged but **not in the repo**.  
4. **`b1f9dbe772fa_M1_initial_schema.py` creates only `visits` and `test_runs`.** It then `add_column`s on `instrument_messages`, `alter_column`/`drop_constraint`/`drop_column`s on `orders` and `results`, and `create_table('visits')` carries `ForeignKeyConstraint(['id_pasien'], ['patients.id_pasien'])`.  
5. **`4a24240f8c32_legacy_baseline.py` has `upgrade(): pass` and `downgrade(): pass`** — a no-op stamp, created 2026-09-02, positioned *after* the transformation, with no explanatory docstring.  
6. `621889e316b5`, `c5465739f048`, `4aff9e134f16` are genuine additive migrations. Single head, linear chain.  
7. **Both API test files call `Base.metadata.create_all(bind=engine)`** (`test_test_runs_api.py:22-23`, `test_order_overview.py:32-33`). **No test executes a migration.**  
8. `alembic/env.py:29` sets `target_metadata = Base.metadata`; ORM tablenames match `04_DATABASE_DESIGN` 1:1 (11 tables verified).  
9. M1.2's checklist includes *"Back up existing database (if data exists)"* — the only place the legacy assumption surfaces, and it is phrased as optional.

### **DETERMINISTIC INFERENCE**

* **`alembic upgrade head` cannot succeed on an empty database.** `create_table('visits')` requires `patients`; `add_column('instrument_messages', …)` requires that table. Both are absent from every migration.  
* **The project has a legacy-baseline assumption**: it presumes a PostgreSQL database pre-created from the external "SQL awal" of `04:1554`. `4a24240f8c32`'s *name* is the only artefact expressing it.  
* **M1's acceptance criteria were verified against the dev database, not against the migration chain** — which is why F-1 survived undetected through eight milestones.  
* **There are two divergent schema sources**: tests/CI use ORM metadata; dev uses legacy \+ migrations. Nothing verifies they agree.

### **UNVERIFIED**

* The exact first failing statement and its error text (not executed — read-only).  
* Whether the external "SQL awal" still exists in the owner's possession.  
* Whether `lis_marina_permata_dev` currently matches `Base.metadata` exactly.

### **Is a new baseline migration appropriate? — RECOMMENDATION**

**Yes.** Two viable shapes; the choice is the owner's (§19 D2):

| Option | Shape | Trade-off |
| ----- | ----- | ----- |
| **B1 — True baseline (recommended)** | New revision **before** `b1f9dbe772fa` creating all 11 tables in their *pre-M1* legacy form, then let the existing chain transform them. Existing deployments `alembic stamp` past it | Migration chain becomes self-sufficient and testable end-to-end; preserves the historical record; existing DB untouched |
| **B2 — Squashed baseline** | New head creating the 11 tables in *final* form; old chain retired to an archive branch label | Simpler for new installs; loses upgrade continuity for the existing dev DB; higher risk |

**Migration testing must become a release criterion** — RECOMMENDATION: one CI job that runs `alembic upgrade head` against a scratch database and then asserts `Base.metadata` matches, so the two schema sources can never silently diverge again. This is the control that would have caught F-1 at M1.

---

## **12\. Test / QA traceability**

| QA §18 / §21 criterion | Where tested | Automated | Manual | Physical | Status |
| ----- | ----- | ----- | ----- | ----- | ----- |
| Instrument can send data to LIS | doc 09 §18 live ingestion | — | — | ✔ | **VERIFIED** |
| HL7 processed per instrument spec | 48+19 tests | ✔ | — | ✔ | **VERIFIED** |
| Batch transmission, no data loss | `test_multiple_frames_in_one_receive`, `test_three_frames_with_leading_heartbeats` | ✔ | — | ✘ | **IMPL \+ PARTLY VERIFIED** |
| Malformed message → no crash | UNPARSEABLE path \+ noise tests | ✔ | — | ✘ | **VERIFIED (simulated)** |
| **One instrument's failure doesn't stop others** | supervisor tests | ✔ (simulated) | — | **✘ 1 instrument only** | **BLOCKED — QA §21.6** |
| Clinical value identical instrument→dashboard | ingestion tests | ✔ partial | ✔ | ✔ (n=1) | **PARTIAL** |
| Clinical result not editable via API | **no endpoint exists** | architectural | — | — | **VERIFIED by construction** |
| Reference range snapshot historical | ingestion tests | ✔ | — | — | **VERIFIED** |
| Raw message traceable | T1/T2/T3 tests \+ live rows | ✔ | — | ✔ | **VERIFIED** |
| Re-run → new Test Run, no overwrite | ingestion \+ API | ✔ | — | ✘ | **VERIFIED (simulated)** |
| One final run per order, atomic switch | partial unique index \+ 20 tests | ✔ | — | — | **VERIFIED** |
| Dashboard view-only; status visible; run selectable; final identifiable; flags not colour-only | **manual checklist only** | ✘ | ✔ | — | **IMPL \+ UNVERIFIED** |
| **Final Run can be sent to SIMRS** | **nothing** | ✘ | ✘ | ✘ | **UNVERIFIED / BLOCKED** |
| **`pending→sending→delivered/failed` works** | API tests on the transitions | ✔ | — | ✘ | **PARTIAL** (state machine yes; real delivery no) |
| **Retry works** | `start_delivery` accepts `failed` | ✔ unit | ✘ E2E | ✘ | **PARTIAL** |
| **Historical Result API by Nomor RM** | **nothing** | ✘ | ✘ | — | **UNVERIFIED** |
| **Authorization applied** | **nothing** | ✘ | ✘ | — | **MISSING** |

### **False-confidence patterns (FACT)**

1. **`Base.metadata.create_all()` implies "the schema works"** while never executing a migration — the direct cause of F-1 surviving eight milestones.  
2. **M5/M6 marked ✅ against the criterion *"All specified endpoints return correct data"*** while 3 of 5 M5 endpoints and the whole of M6 have zero tests.  
3. **"176 passed" reads as broad coverage** but covers **7 of 11 endpoints, 0% of the frontend, and 0% of SIMRS**.  
4. **M8.6's V1–V27 manual checklist produced real verification** — but it is not repeatable, so any future change silently re-opens every one of those 27 checks.

### **Should M9.4 remain a standalone milestone? — RECOMMENDATION**

**No.** It should become a **cross-cutting release-quality gate**, for a causal reason visible in the evidence: M5 and M6 were marked Complete precisely *because* "tests" lived in a later milestone. Keeping M9.4 standalone reproduces the failure. Replace it with: (a) a per-milestone exit criterion — *"acceptance criteria demonstrated by an automated test or a cited verification record"* — and (b) a one-time **QA Gap Closure** task covering the existing backlog (4 endpoints, SIMRS module, frontend tooling, corpus fixtures).

---

## **13\. Physical evidence matrix**

Labels exactly as `docs/09` defines them. **doc 09 is authoritative here and overrides vendor capability, `08_MASTER_DATA.md`, simulators and the task list** (doc 09 §1).

| Question | Status | Source |
| ----- | ----- | ----- |
| BC-5150 transport role — LIS is TCP **client** | **VERIFIED** | §18 T-CONN-01; packet capture |
| Endpoint `10.0.0.2:5100`, direct P2P | **VERIFIED** | §4.3 |
| Protocol HL7 2.3.1 over MLLP | **VERIFIED** | §18 T-CONN-01 |
| Framing `0x0B` … `0x1C 0x0D` | **VERIFIED** | §18 T-FRAME-01 |
| `0x02` single-byte idle heartbeat | **VERIFIED** | §18 T-FRAME-01; fix `19d333e`; 19 tests |
| ACK `MSA|AA` accepted by device | **VERIFIED** | §5.5; `id_message=152` |
| **OBR-3 `Background` → NON\_PATIENT** | **VERIFIED** | 27 historical (§5.7) \+ 2 live (T-BC-J), no counter-example |
| Patient message shape | **VERIFIED (shape)** / **INSUFFICIENT (diversity, n=1)** | §18 T-BC-A |
| **Positive PATIENT\_RESULT rule** | **NOT APPROVED** | §9.5 |
| PID-5 populated as discriminator | **CANDIDATE** | §9.5 — falsifiable only by T-BC-K |
| OBR-3 numeric as discriminator | **CANDIDATE** | §9.5 |
| `IS` metadata present as discriminator | **CANDIDATE** | §9.5 |
| Clinical OBX present as discriminator | **REJECTED — falsified** | §9.5 (Background emits clinical OBX) |
| **The 20 PID-5-empty numeric messages** | **UNKNOWN — not proven QC** | §5.7 |
| QC / control | **UNKNOWN — zero captures** | §18.1 |
| Calibration | **UNKNOWN — zero captures** | §18.1 |
| Maintenance | **UNKNOWN — zero captures** | §18.1 |
| Startup / self-test | **UNKNOWN** | T-BC-H outstanding |
| Manual retransmission: MSH-7/MSH-10 change | **VERIFIED** (manual resend only) | §8.5 |
| OBR-3 / OBR-7 invariant across manual resend | **VERIFIED** (same scope) | §8.5 — S2 did not trigger |
| MSH-10 globally unique | **VERIFIED FALSE** (repeats observed) | §18 MSH-10 census |
| Reconnect-resend / ACK-timeout resend | **UNKNOWN** | T-BC-I, T-BC-T |
| Genuine repeat run reuses OBR-3/OBR-7 | **UNKNOWN** | T-BC-B — decisive for dedup |
| Dedup guard ever exercised | **REPO-CONFIRMED: never** | §8.5; `repository.py:101-106` precedes `:126` |
| Specimen counter recycling | **UNKNOWN** | T-ID-02, Q4 — stop condition S1 |
| Instruments 2–9, all categories | **UNKNOWN** | §18.1 final row |

**Blocking map:** M9.2 ← T-BC-B/D/E/F/I/R \+ T-ID-02 · M9.3b ← T-BC-K ×2 \+ L/M/N/H · production `PATIENT_RESULT` ← **both** M9.3b **and** the §10 identity question (§9.6: *"Neither alone is sufficient"*).

---

## **14\. Scope creep / missing scope**

### **Scope creep — essentially none, and two prior "findings" retracted**

| Candidate | Verdict |
| ----- | ----- |
| `MainLayout.tsx`, `StickyStatusBar.tsx` | **NOT creep, NOT dead code — deliberately retained** (M8.5 D1 "keep the file"; M8.6 §10 "Must NOT change"; §11 forbids deleting retained files). **Prior "remove" recommendation retracted** |
| Parser registry abstraction | **Justified** — FR-01 (9 instruments), FR-02 (2 protocol families) |
| Classification mechanism/policy split | **Justified** — FR-04 is generic; keeps the vendor rule opt-in |
| T1/T2/T3 transaction model | **Justified** — FR-03/AC-03 |
| `/api/results` \+ `useResults` | **Genuine dead weight** — 0 consumers, 0 tests. But `hooks/*` and `api/*` are under M8.6 §10 "Must NOT change" (milestone-scoped), so removal is a *decision*, not cleanup |
| M8.4 D4 `total_runs` | Correctly **not** built; M8.5 D5 "Run N" covers the need |
| `unverified_passthrough` policy | **Justified** — needed to test the clinical path; correctly opt-in |
| Listener/server instrument mode | **Correctly refused** — `SUPPORTED_INSTRUMENT_MODES = {"client"}` |
| Refresh tokens / external IdP / third role | **Correctly avoided** in the M9.1 design |
| Premature generalisation to 9 instruments | **Absent** — `instruments.json` holds only the verified BC-5150; doc 09 §18.1 forbids extension by analogy |

### **Missing scope**

| Missing | Requirement | Currently assigned to |
| ----- | ----- | ----- |
| Fresh-database provisioning | Brief §8, NFR-10 | **nothing** |
| Migration testing | implied by DB Design §1554 | **nothing** |
| **Auto-refresh** | **FR-07, AC-09, QA §18** | M9.6, mislabelled as hardening |
| **User attribution in audit** | **NFR-08, QA §19** | **nothing** |
| Authentication | NFR-09, AC-12, TC-SEC-\* | M9.1 |
| Instrument rollout beyond BC-5150 | FR-01, AC-01, AC-13, QA §21.6 | **nothing** |
| SIMRS E2E verification | FR-16, AC-11, QA §21.7 | **nothing** (external) |
| Inbound SIMRS authorisation | FR-17, AC-12, TC-HIST-03 | **nothing** |
| Frontend test tooling | M8.5 §17 Tier 2, QA plan | M9.4 (no concrete step) |
| Field-corpus regression fixtures | doc 09 §16 step 4, §12.4 | M9.4 (marked "partially done") |

**Implemented but undocumented:** the fail-closed M9.3 behaviour (`28ad9b3`) is absent from the task list. **Documented but unimplemented:** M8.4 D4; doc 09 §16 step 4; every M9 item.

---

## **15\. Implementation vs verification vs release readiness**

Three distinct concepts, deliberately not conflated:

> **IMPLEMENTATION COMPLETE** — the code exists and does what its milestone specified.  
>  **VERIFICATION COMPLETE** — an automated test, cited investigation verification, or dated doc-09 §18 record demonstrates it.  
>  **MVP RELEASE READY** — QA §21 sign-off is honestly achievable.

### **Release-gate matrix**

| Requirement | Implementation | Verification | External blocker | Release gate |
| ----- | ----- | ----- | ----- | ----- |
| Clinical immutability / no overwrite | ✔ | ✔ automated | — | **MET** |
| One final run per order | ✔ | ✔ automated \+ DB index | — | **MET** |
| Raw message traceability | ✔ | ✔ automated \+ live | — | **MET** |
| HL7 ingestion \+ framing \+ ACK | ✔ | ✔ automated \+ physical | — | **MET** |
| Fail-closed classification | ✔ | ✔ 28 tests \+ field evidence | — | **MET** |
| Malformed input safety | ✔ | ✔ automated | — | **MET** |
| **Fresh-DB provisioning** | ✘ | ✘ | — | **GATE — unblocked** |
| **Authentication / RBAC** | ✘ | ✘ | — | **GATE — unblocked** |
| **User attribution (NFR-08)** | ✘ | ✘ | — | **GATE — unblocked** |
| **Auto-refresh (FR-07/AC-09)** | ✘ | ✘ | — | **GATE — unblocked** |
| **SIMRS push (AC-11)** | ✔ | ✘ | **SIMRS spec** | **GATE — blocked** |
| **Historical API (AC-12)** | ✔ | ✘ | needs auth | **GATE — unblocked once auth lands** |
| **Multi-instrument isolation (AC-13, QA §21.6)** | ✔ capability | ✘ | **2nd instrument** | **GATE — blocked** |
| Dashboard view-only / flags / selectors | ✔ | ✘ automated (manual only) | — | **GATE — unblocked** |
| Production hardening | ✘ | ✘ | — | **GATE — unblocked** |
| QC / calibration filtering | ✘ | ✘ | **T-BC-K** | **NOT a gate** — fail-closed is safe |
| Dedup refinement | ✘ | ✘ | **T-BC-B** | **NOT a gate** — no clinical rows are created |

### **Minimum set for honest MVP sign-off**

**Unblocked and required:** fresh-DB provisioning \+ migration test · auth/RBAC · user attribution · auto-refresh · API tests for the 4 untested endpoints \+ SIMRS module · hardening · a repeatable UI verification.

**Externally blocked and required:** one additional instrument (QA §21.6) · the SIMRS specification (QA §21.7).

> **The honest statement the owner needs:** with zero analyzer access the project can complete every unblocked gate. It still **cannot** be signed off under QA §21, because items 6 and 7 depend on a second instrument and a SIMRS specification. **Surface that now, not at sign-off.**

---

## **16\. Consolidated project map**

LAYER              AUTHORITY                 CURRENT STATE                    UNRESOLVED CONFLICT  
─────────────────────────────────────────────────────────────────────────────────────────────  
REQUIREMENTS       01 Brief → 02 PRD         Stable, coherent                 PRD defines 1 human  
                   (PRD §11 rule)            18 FR, 10 NFR, 13 AC             actor; SysDesign §11.2  
                                                                              "Contoh" adds a 2nd  
                                                                              → RBAC (§10)  
        ↓  
ARCHITECTURE       03 System Design          Modular monolith as designed     §11.2 roles are an  
                   04 Database Design        11 tables ↔ ORM 1:1 ✔            example, not a contract  
        ↓  
MILESTONE          M8.4/M8.5/M8.6 docs       Frozen decisions honoured        M8.4 D4 unimplemented;  
DECISIONS          (self-declared SoT)       14/15 verified in code           M8.6 O8 unanswered  
        ↓  
MILESTONE          ✗ NOBODY (Gap 1\)          07\_TASK\_LIST stale:              M9 "Not Started" vs  
STATUS             de facto 07\_TASK\_LIST     M9.3a shipped, unchecked         28ad9b3; M5/M6/M7  
                                                                              ✅ but unverified  
        ↓  
IMPLEMENTATION     Repository                Backend solid; 11 endpoints,     8/9 instruments  
                                             0 authenticated; FE complete     unconfigured;  
                                             except FR-07                     SIMRS unconfigured  
        ↓  
TESTS              06 QA Test Plan           176 backend passed               7/11 endpoints;  
                   (46 TC-\*, §18, §21)       0 frontend, 0 SIMRS,             0% frontend;  
                                             0 migration                      migrations untested  
        ↓  
PHYSICAL           09 Physical Validation    BC-5150 transport/framing/       QC, calibration,  
EVIDENCE           (absolute for behaviour)  ACK/Background VERIFIED          maintenance, dedup,  
                                             Positive rule NOT APPROVED       counter \= UNKNOWN  
        ↓  
DEPLOYMENT         ✗ NOBODY (Gap 2\)          .env \+ instruments.json          F-1: no fresh-DB path;  
CONFIG             gitignored, undocumented  gitignored; CORS in main.py      legacy assumption  
                                                                              expressed only by a  
                                                                              no-op migration's name  
        ↓  
RELEASE GATE       06 QA §18 \+ §21           2 of 10 sign-off items blocked   Blockers are external,  
                                             by external dependencies         not engineering

---

## **17\. Recommended next 10 tasks**

| \# | Task | Milestone | Depends on | Blocked? | Files / modules | Why next | Release impact | Model | Design review first? |
| ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| **1** | **Reconcile task list \+ doc 09 §15**; add the milestone-status authority rule; note M8.6 §11's prohibitions are milestone-scoped | M9.0 prep | — | No | `docs/07_TASK_LIST.md`, `docs/09` | Every later decision is made against a tracker that misreports reality; \~30 min | Enables honest tracking | **Sonnet 5** | No |
| **2** | **F-1 investigation \+ baseline design.** Confirm on a scratch DB that `upgrade head` fails from empty; choose B1 vs B2; design the migration-test CI job. **Design only** | **M9.0** | 1 | No | `alembic/versions/`, `docs/04` | Highest-severity finding; gates every deployment **and** M9.1's `users` migration | **HARD GATE** | **Opus 5** | **Yes — mandatory** |
| **3** | **Implement M9.0** — baseline migration \+ migration test in CI | M9.0 | 2 | No | `alembic/`, `tests/test_migrations.py` (new) | Makes the chain self-sufficient and permanently prevents recurrence | **HARD GATE** | Opus 5 | No (design done in 2\) |
| **4** | **M9.1a — Auth / RBAC**, Option B roles, argon2-cffi \+ PyJWT/HS256, 8h token, per-request DB check | **M9.1a** | 3 | No | `core/security.py`, `models/user.py`, `api/deps.py`, `routers/auth.py`, 4 routers, `main.py`; FE `client.ts`, `AuthContext`, `LoginPage` | Largest unblocked contractual item (NFR-09); must precede M9.4 or API tests are written twice | **HARD GATE** | **Opus 5** | **Yes** — §19 D1/D3/D4 |
| **5** | **M9.1b — Audit attribution** (NFR-08): `id_user` on finalize/unfinalize/delivery/sync | **M9.1b** | 4 | No | new migration, `test_run_service.py`, `routers/test_runs.py` | **Mandatory under Option B** — the only remaining NFR-08 control | **HARD GATE** | Opus 5 | Yes — brief |
| **6** | **QA gap closure** — API tests for `results`, `patients/history` (AC-12), `instruments/status`, `sync-simrs` (AC-11); SIMRS module unit tests; `conftest.py` | M9.4 | 4 | No | `tests/api/`, `tests/conftest.py` | Two PRD acceptance criteria have **zero** automated evidence | **HARD GATE** | **Sonnet 5** | No |
| **7** | **M10.1 — Auto-refresh (FR-07/AC-09)**, race-safe against the M7 mutation lock. **Note: M8.6 §11's polling ban was milestone-scoped and does not apply** | **M10.1** | — | No | `hooks/`, `OrderOverviewView.tsx` | Contractual, unblocked, closes M7's only gap | **HARD GATE** | Opus 5 | **Yes** — polling vs SSE; interaction with pagination drift (M8.4 §10 flagged this) |
| **8** | **Preserve the field corpus** — redacted session-1 fixtures (doc 09 §16 step 4). Redaction required: `tests/test_ingestion.py:95,485` carry a real patient name | M9.4 | — | No | `tests/fixtures/` | **Time-sensitive** — the only verbatim field corpus lives solely in the dev DB | Supports QA §19 evidence | Sonnet 5 | No |
| **9** | **M9.5 — Hardening**: 9 `print()` → structured logging; finalise CORS; standardise errors | M9.5 | 4 | No | `integration/client.py`, `integration/instruments.py`, `main.py` | Pairs with the CORS work in task 4 | **GATE** (partial) | Sonnet 5 | No |
| **10** | **Frontend test tooling \+ first suite** — M8.5 §17 Tier-2 scenarios 1–16 | M9.4 | 4, 7 | No | `frontend/package.json`, `src/**/*.test.tsx` | M8.5 §17 already specifies the 16 scenarios; converts M8.6's one-shot V1–V27 into repeatable checks | **GATE** | Sonnet 5 | No |

**In parallel, owner-driven (not engineering):** answer Q1/Q3/Q5 to schedule BC-5150 session 2 (T-BC-K ×2); request the SIMRS Integration Specification; identify a second instrument for T-CONN-01.

**Deliberately not listed:** dead-code removal of `MainLayout`/`StickyStatusBar` — **retracted**, they are protected by frozen decisions.

---

## **18\. Documentation updates required**

| Doc | Update | Class |
| ----- | ----- | ----- |
| `07_TASK_LIST.md` | M9 status; split M9.3 → a/b; correct M5/M6/M7 completion claims; add M9.0, M9.1b, M10.1; add the three unassigned requirements; **add the milestone-status authority sentence** | **MUST** |
| `04_DATABASE_DESIGN.md` | New **Provisioning** section: fresh-install path, legacy-upgrade path, and what `4a24240f8c32` actually means | **MUST** |
| **New `DEPLOYMENT.md`** | Closes Gap 2: DB provisioning, JWT secret generation, first-admin bootstrap, CORS origins, `VITE_API_BASE_URL`, `instruments.json` location | **MUST** |
| `09_PHYSICAL_INSTRUMENT_VALIDATION.md` | §15 "165 passing" → 176 | **MUST** |
| `03_SYSTEM_DESIGN.md` | §11.2 — replace the "Contoh" role tree with the decided RBAC contract once §19 D1 is answered; add deployment shape / CORS | **SHOULD** |
| `06_QA_TEST_PLAN.md` | §18 "Instrument status terlihat" now served by `Sidebar`, not `StickyStatusBar`; add TC entries for auto-refresh and migration provisioning | **SHOULD** |
| `M8.4_Investigation.md` | Record D4 (`total_runs`) as consciously dropped | **SHOULD** |
| `M8.6_Investigation.md` | Record the O8 answer once the owner confirms; note §11's prohibitions were milestone-scoped | **SHOULD** |
| `02_PRD.md` | FR-16: note `Success` is realised as `delivered` | **OPTIONAL** |
| `08_MASTER_DATA.md` | Cross-reference doc 09 §4.3 for BC-5150 port 5100 | **OPTIONAL** |

---

## **19\. Decisions requiring owner confirmation**

| ID | Decision | Recommendation | Consequence if deferred |
| ----- | ----- | ----- | ----- |
| **D1** | **RBAC Option A or B?** | **B** — PRD defines one human actor; SysDesign §11.2 is explicitly an example; TC-SEC-02 is satisfied architecturally | Blocks M9.1a. If B, **M9.1b becomes mandatory** |
| **D2** | **F-1 remediation: B1 true baseline or B2 squashed?** | **B1** — preserves upgrade continuity for the existing dev DB | Blocks M9.0 and therefore M9.1's migration |
| **D3** | **Login body: JSON or `OAuth2PasswordRequestForm`?** | **JSON** — matches the whole API, no new dependency; Swagger "Authorize" is the cost | Minor; decide before task 4 |
| **D4** | **Token storage: `sessionStorage` or httpOnly cookie?** | **`sessionStorage`** — shared-workstation risk dominates; cookie needs CSRF \+ `SameSite` | Retrofitting later touches CORS, client wrapper and every auth test |
| **D5** | **M8.6 O8 — should MRN search remain reachable from the detail screen?** | **No** (the applied default). **The owner has never confirmed this**, and it is the one behavioural change M8.6 made | Currently in production behaviour unconfirmed |
| **D6** | **`/api/results` \+ `useResults` — keep and test, or retire?** | Owner's call; note `hooks/*` and `api/*` were M8.6-protected (milestone-scoped only) | Adds untested surface to the auth work in task 4 |
| **D7** | **QA §21.6 (multi-instrument isolation) is unsatisfiable with one instrument.** Wait for a second instrument, or formally scope the criterion down? | **Raise now** — it is a scope decision, not engineering | Discovered at sign-off instead of now |
| **D8** | **SIMRS specification availability** — is MVP sign-off gated on AC-11, or does SIMRS ship "implemented, unverified"? | **Raise now** | QA §21.7 unachievable |
| **D9** | **Interim BC-5150 posture (doc 09 Q9)** — the system is safe but inert; no patient result reaches clinical tables. Acceptable for MVP demo? | Owner's call; enabling requires **both** M9.3b and T-ID-02 (§9.6) | Determines whether MVP demonstrates end-to-end clinical flow |

---

## **20\. Overall confidence**

| Conclusion | Confidence | Basis |
| ----- | ----- | ----- |
| Authority hierarchy as stated in §2/§3 | **High** | Assembled from explicit self-declarations (PRD §11, doc 09 §1, M8.6 closing) — quoted, not inferred |
| M8.4/M8.5/M8.6 decisions honoured in code | **High** | 14 of 15 frozen decisions verified directly against source this session |
| **`MainLayout`/`StickyStatusBar` are deliberately retained, not dead code** | **High** | M8.5 §20 D1 "keep the file"; M8.6 §10 "Must NOT change"; §11 "deleting retained files" forbidden — three independent citations |
| F-1: migration chain cannot provision an empty DB | **High** (deterministic inference) | Migration contents are fact; failure follows deterministically. **Not empirically executed** — read-only |
| The project has an undocumented legacy-baseline assumption | **High** | No `.sql` in repo; 0 `CREATE TABLE` in DB design; `04:1554` references an external "SQL awal"; `4a24240f8c32` is a no-op named "Legacy baseline" |
| FR-07/AC-09 and NFR-08 are contractual and unmet | **High** | Direct quotation from PRD §4.2, §6, §5 |
| RBAC Option B is the better fit | **Medium-High** | Document evidence is strong; the operational premise (lab supervisor is both roles) is an inference the owner should confirm |
| M1–M8 status classifications | **High** | Each cross-checked against implementation, tests and the milestone's own doc |
| M9/M10 restructuring | **Medium-High** | Follows from the evidence; the M10 boundary is a judgement call |
| Effort sizing for tasks 2–4 | **Medium** | No auth or baseline-migration precedent in this codebase to calibrate against |

---

**Read-only constraint fully honoured:** no file modified, nothing staged/committed/pushed/reset/cleaned, no database read or written, no migration executed, no analyzer communication. The `.env` inspection printed key names with values redacted.

Two things I'd flag for your attention above all: **F-1 blocks any deployment and also gates M9.1's migration**, and **my earlier "remove dead code" recommendation was wrong** — `MainLayout.tsx` and `StickyStatusBar.tsx` are protected by frozen decisions in M8.5 and M8.6.

If you'd like this as a shareable page for the project record rather than terminal scrollback, I can publish it as an artifact — that creates one HTML file, so I've held off given the read-only instruction.

