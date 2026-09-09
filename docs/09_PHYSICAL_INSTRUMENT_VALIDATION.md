# Physical Instrument Validation

**Status:** Field-validation plan and evidence record. Living document.
**Created against:** `e8c401a docs: finalize task list consistency` (branch `refactor/orm-architecture`)
**Last evidence update:** BC-5150 field session 1 — first successful live integration, recorded against `19d333e fix(integration): handle BC-5150 heartbeat framing`.
**Milestone position:** After M8.6 (released), before M9.2 / M9.3 implementation.
**Nature:** Investigation and planning only. No source, schema, migration, test or task-list change is authorised by this document.

> **Session-1 summary (VERIFIED).** BC-5150 transport, MLLP framing, `0x02` idle-heartbeat behaviour, normal-patient and Background message shapes, manual retransmission semantics, and live ingestion with a positive `MSA|AA` ACK are all now field-verified. **Positive patient classification remains NOT APPROVED** — see §9.5. The next physical priority is **T-BC-K (QC / control)**.

---

## 1. Purpose

M9.2 (Message Deduplication Refinement) and M9.3 (QC / Calibration Filtering Refinement) both encode rules about **how a physical instrument actually behaves**. Neither can be implemented safely from research capability, vendor datasheets, or reasoning about HL7 in the abstract.

This document exists to:

1. record, precisely and durably, what instrument behaviour the project has **actually observed**;
2. separate that from what the repository merely **implements**, what has been **inferred**, and what is **unknown**;
3. define the physical tests that must be run, and the evidence that must be captured, before each dependent engineering decision;
4. identify which parts of M9 can proceed **now**, in parallel, without waiting for a lab session.

It is the project's authoritative physical-instrument validation record. It is intended to be updated after every field session — §18 is the running completion record.

### Governing principle

> **Real instrument behaviour must be verified before implementing rules that depend on that behaviour.**

The codebase already enforces this principle structurally: the classification layer fails closed, the parser registry refuses unknown keys rather than guessing, and `docs/08_MASTER_DATA.md` §6.2 mandates `protokol = NULL` for every instrument whose actual configuration is unverified. This document extends that discipline to the field.

---

## 2. Scope

**In scope:** transport and connectivity observation; protocol and framing confirmation; message-level behaviour (identity, timestamps, retransmission, ACK); non-patient message categories; specimen → visit/order identity evidence; evidence-capture standards; a test matrix across all nine instrument identities.

**Out of scope:** implementing M9.2 or M9.3; changing parsers, classification, schema, API or frontend; selecting a deduplication algorithm; declaring any instrument's protocol.

**Explicitly forbidden by this document:** generalising the BC-5150 Background rule to any other instrument; recording a research capability as an actual configuration; introducing a date-derived or otherwise synthetic identity key.

### Evidence labels used throughout

| Label | Meaning |
|---|---|
| **VERIFIED** | Observed on the physical instrument and recorded as evidence |
| **REPO-CONFIRMED** | Read directly from this repository's source; describes what the software does, **not** what the instrument does |
| **INFERRED** | A reasoned conclusion from VERIFIED or REPO-CONFIRMED facts; not itself observed |
| **UNKNOWN** | No evidence either way |

These four are never collapsed. In particular, REPO-CONFIRMED is **not** evidence about an instrument: the software's ability to parse a field says nothing about whether the instrument emits it.

---

## 3. Safety / Data Handling

1. **Use synthetic or control material wherever the instrument permits it.** Quality-control material, background runs, and manufacturer control samples generate real protocol traffic without real patient data, and are sufficient for most transport, framing, ACK, retransmission and identity tests.
2. **Where a genuine patient sample is unavoidable** (e.g. to observe how a real accession/barcode populates PID-3 and OBR-3), record only the fields technically necessary for the identity investigation.
3. **Pseudonymise in the evidence record.** Replace the patient name with a token (`PT-01`) in the written record. Where a real identifier's *shape* is the object of study, record its **structure** (length, character classes, prefix) rather than its value where that is sufficient — e.g. `MRN shape: 7 digits, no prefix` rather than the MRN itself.
4. **Raw captures containing real identifiers are working evidence, not repository content.** See §12.4 for the storage rule: they are held in the controlled evidence store, and only redacted or synthetic derivatives are committed.
5. **Never run validation against the production database.** `lis_marina_permata` must never be touched. Field sessions run against `lis_marina_permata_dev`.
6. **Do not alter instrument calibration, QC schedules or reagent state to force a test.** Where a scenario requires an instrument state the lab cannot safely produce, mark it `NOT APPLICABLE` rather than manufacturing it.

---

## 4. Current Instrument Inventory

Nine instrument identities are seeded. `id_instrument` values are **2–10**; there is no id 1.

| id | `nama_mesin` | `protokol` (DB) | `tipe_koneksi` (DB) | Master-data status |
|---|---|---|---|---|
| 2 | Mindray BC-5150 | `HL7` | `TCP/IP` | **Field-Confirmed** |
| 3 | Sysmex XN-550 | `NULL` | `NULL` | Research Baseline |
| 4 | Mindray BS-200E | `NULL` | `NULL` | Research Baseline |
| 5 | Sysmex BX-3010 | `NULL` | `NULL` | Research Baseline |
| 6 | Boditech Med Inc. — ichroma II | `NULL` | `NULL` | Research Baseline |
| 7 | Medica — EasyLyte PLUS | `NULL` | `NULL` | Research Baseline |
| 8 | DFI — R-300 | `NULL` | `NULL` | Configuration Dependent |
| 9 | ACON / Mission — Insight Expert U120 | `NULL` | `NULL` | Configuration Dependent |
| 10 | Precil — 106-AC-57000131 (Reported ID) | `NULL` | `NULL` | **Identity Unverified** |

*Source: live `GET /api/instruments/status` against `lis_marina_permata_dev`, and `docs/08_MASTER_DATA.md` §5, §6, §7.*

`docs/08_MASTER_DATA.md` §7 records a **technical reference** (vendor capability) for each instrument. That table is a development reference only. Per §6.2 of that document, research capability must never be written into actual deployment configuration — "Research says ASTM supported" does not mean "actual protocol = ASTM". This document adopts that rule without exception.

### 4.1 Configuration state — REPO-CONFIRMED

- Per-instrument deployment configuration lives in a JSON file (`backend/instruments.json`, path from `Settings.INSTRUMENTS_CONFIG_FILE`), **not** in the database. The `instruments` table carries identity, master-data attributes and runtime status only; it has no host or port column (`backend/app/models/instrument.py`).
- `backend/instruments.json` is **git-ignored** (`.gitignore:5`); only `instruments.example.json` is tracked. It is deployment configuration, not repository content, so its presence cannot be established by reading the repository alone.
- **Session 1 created it** (T-CONFIG-01, complete). The active BC-5150 entry differs from the tracked example in exactly one field — `host` — and is otherwise the example verbatim: `port 5100`, `mode "client"`, `parser_key "bc5150_hl7"`, `identity_prefix "BC5150-"`, `enabled true`, `classification_policy "bc5150_field_verified"`.
- Configuration never contains a numeric database id; identity is resolved at startup by matching `instrument_name` against `instruments.nama_mesin`, failing loudly on zero or ambiguous matches (`backend/app/integration/instruments.py`). Session 1 confirmed this resolves `Mindray BC-5150` → `id_instrument = 2` unambiguously.

### 4.3 BC-5150 physical configuration — VERIFIED (session 1)

Read from the analyzer's own communication settings and the test laptop, on a direct point-to-point Ethernet link. **No production LIS and no production network were involved.**

| Property | Value |
|---|---|
| Analyzer IP | `10.0.0.2` |
| Subnet mask | `255.255.255.0` |
| Gateway | `10.0.0.254` |
| Port | `5100` |
| Protocol | HL7 |
| Transport | TCP/IP |
| Laptop (LIS) IP | `10.0.0.10/24` |
| Link | Direct P2P Ethernet |
| Auto Communicate | **ON** |
| Auto Retransmit | **OFF** |
| ACK Overtime | 10 s |
| ACK Sync | **OFF** |

Two of these settings bound the interpretation of every other test in this document and must be cited whenever ACK or duplicate behaviour is discussed:

- **Auto Retransmit is OFF.** The instrument will not resend on its own. Every duplicate observed in session 1 was **operator-initiated**, and no conclusion about automatic retry behaviour can be drawn from this session (T-BC-T remains open).
- **ACK Sync is OFF**, with a 10 s ACK Overtime. Whether the instrument's behaviour changes when an ACK is late or absent is therefore **UNKNOWN**; the 10 s value is a configured setting, not an observed timeout.

### 4.2 A hazard that must not be mistaken for evidence

`backend/mesin_simulator.py` is a developer-authored script that emits **ASTM-style records** (`H|`, `P|`, `R|`, ENQ/EOT framing) under the label `Sysmex_XN-550`, and connects **to** the LIS on port 5000 as if the LIS were a server.

This file is **not field evidence**. It contradicts the current architecture in two ways: the supported transport mode is client-only (§11.1), and no ASTM parser exists (§5.2). It appears to be an artefact of an earlier design.

> **Rule:** `mesin_simulator.py` must never be cited as evidence that the XN-550 uses ASTM, or that any instrument connects inbound. Its existence is recorded here so that a future reader does not mistake it for a capture.

`backend/tests/simulate_bc5150.py` is a legitimate **test harness** that emits field-shaped BC-5150 HL7 over MLLP. It is a simulator, not a capture; it exercises the software, and proves nothing about the instrument.

---

## 5. Known vs Unverified Behaviour

This is the Phase 1 baseline: what the software implements, mapped against what the field has confirmed.

### 5.1 Behaviour matrix

| # | Area | Current implementation (REPO-CONFIRMED) | Field-verified? | Required validation |
|---|---|---|---|---|
| 1 | **Transport role** | LIS is a **TCP client**; it dials out to `host:port`. `SUPPORTED_INSTRUMENT_MODES = {"client"}`; listener/server mode raises a validation error (`core/config.py`) | **VERIFIED for BC-5150** — session 1: LIS at `10.0.0.10` connected outbound to `10.0.0.2:5100` and received data. The instrument does **not** require the LIS to listen | T-CONN-01 per instrument: confirm which side initiates |
| 2 | **Protocol** | Only HL7 v2 is parsed. `protokol = HL7` seeded for BC-5150 only | **VERIFIED for BC-5150** — `ORU^R01`, HL7 `2.3.1`, observed on the wire | T-PROTO-01 per instrument |
| 3 | **Framing** | MLLP: `0x0B` … `0x1C 0x0D`. Frames are anchored on the start block; bytes preceding it are discarded (`integration/mllp.extract_frames`, `client.py`) | **VERIFIED for BC-5150** — MLLP confirmed by packet capture and by live ingestion. See row 22 for the `0x02` heartbeat finding that this framing had to absorb | T-FRAME-01 per instrument; partial/split-frame delivery still to confirm on-device (T-BC-S) |
| 4 | **ACK behaviour** | LIS sends `MSA\|AA\|{MSH-10}` on success, `MSA\|AE\|{MSH-10}\|{error[:50]}` on failure. ACK MSH receiving application is **hardcoded `MINDRAY`** (`client.py:33,41`) | **VERIFIED that the ACK is sent and the exchange completes** — session 1 packet capture shows instrument → LIS `ORU^R01` and LIS → instrument HL7 ACK carrying `MSA\|AA`. **Still UNKNOWN:** whether the instrument *requires* an ACK, its real timeout, its reaction to `AE`, and whether the hardcoded receiving-app value matters. `ACK Sync` was OFF and `Auto Retransmit` OFF (§4.3), so none of those was exercised | T-BC-T: ACK dependence, timeout, and `AE` handling |
| 5 | **Message Control ID (MSH-10)** | Parsed for ACK correlation (`mllp.extract_control_id`, and `parsers/hl7.py`). An **empty MSH-10 makes the message UNPARSEABLE** (parser returns `None`). **Not persisted as a column** — recoverable only by re-parsing `instrument_messages.raw_message` | **VERIFIED (strong observation, not a universal guarantee):** MSH-10 **changes on manual retransmission** (T-BC-C, T-BC-C-P), and **repeated values were observed across separate messages** in the session corpus. It is a transmission/message control id, **not** a stable logical-result identifier, and is **not safe as a sole dedup key** | Whether MSH-10 ever repeats *within* a single uninterrupted session, and its reset/rollover behaviour, remain UNKNOWN (T-BC-E) |
| 6 | **Timestamps** | OBR-7 → `TestRun.waktu_run`, parsed as `%Y%m%d%H%M%S` from the first 14 characters. `InstrumentMessage.received_at` is server-local receipt time | **VERIFIED:** OBR-7 is the **original measurement timestamp and remained invariant** across both observed manual retransmissions, while MSH-7 (transmission timestamp) changed. Observed OBR-7 values are historical (2023), i.e. stored records replayed from instrument memory | T-BC-D: does OBR-7 ever change on an automatic resend? (`Auto Retransmit` was OFF, so untested) |
| 7 | **Patient identifier** | PID-3.1 → `nomor_rm`. If empty, a **synthetic patient** is created with `nomor_rm = no_registrasi` and the message flagged `SIMRS_IDENTITY_NOT_RESOLVED` (`repository.py:144-158`) | **VERIFIED, and narrower than previously recorded:** the PID-3 **field is present as the literal `^^^^MR` in both patient and Background messages** — its components are empty, so `nomor_rm` parses to `""` in **both**. PID-3 therefore does **not** discriminate, and the synthetic-patient path would fire for **every** message observed so far | **T-BC-O / T-ID-01 — does PID-3 ever carry a real MRN in routine work?** Escalated: see §10.2 |
| 8 | **Specimen / order identifier** | OBR-3 → `specimen_no`; `no_registrasi = identity_prefix + OBR-3`. Missing OBR-3 **or** OBR-7 → `Failed` + `AE` | **VERIFIED:** BC-5150 emits a short integer sample number (session 1 observed `42`; earlier captures 30, 31, 359) and the literal `Background`. Reset/rollover behaviour of the counter remains **UNKNOWN** | **T-ID-02 — see §10, the largest open architectural question** |
| 9 | **Repeat run** | `run_sequence = MAX(run_sequence)+1` per order (`repository._next_run_sequence`) | **UNKNOWN** — no field observation of a genuine repeat run | T-BC-B |
| 10 | **Retransmission** | Exact-retransmission guard: a `TestRun` matching `(id_instrument, Visit.no_registrasi, waktu_run)` short-circuits to `Success` + `AA` with `error_detail = "Retransmission: Source measurement already exists"` | **VERIFIED for manual retransmission only** (T-BC-C, T-BC-C-P): OBR-3 and OBR-7 both invariant, payload unchanged, MSH-7 and MSH-10 changed. The existing key's two components therefore both survive an operator-initiated resend. **Not exercised:** the guard itself, because under `bc5150_field_verified` patient messages return as `UNCLASSIFIED` before reaching it (§8.1) | T-BC-D, T-BC-I: resend after reconnect/timeout, and any automatic resend |
| 11 | **Disconnect / reconnect** | Client retries every 5s indefinitely; status transitions `CONNECTED` → `RECONNECTING` → `DISCONNECTED` | **UNKNOWN** — instrument-side behaviour on LIS disappearance | T-CONN-04 |
| 12 | **Buffered / offline results** | No buffering logic exists in the LIS. Whether the instrument buffers is an instrument property | **UNKNOWN** | T-BC-I |
| 13 | **Malformed messages** | Fails closed: `UNPARSEABLE` → `Failed` + `AE`; ingestion exception → T3 records failure, raw row survives, `AE` sent | **PARTIAL** — proven in simulation (`simulate_bc5150.py` has `missing_obr3`, `missing_obr7`, `missing_msh10`, `split`, `multi` modes); never provoked on the physical device | T-BC-Q (only if safely producible) |
| 14 | **Background / QC / calibration / maintenance** | Only `Background` is encoded. `bc5150_field_verified`: OBR-3 (casefolded, stripped) `== "background"` → `NON_PATIENT`; **everything else → `UNCLASSIFIED`** | **VERIFIED — Background only, re-confirmed live** (T-BC-J): OBR-3 `Background`, classified `NON_PATIENT` / `OBR3_BACKGROUND` in `lis_marina_permata_dev`. QC, calibration, maintenance, control, blank, startup: **UNKNOWN — zero captures** | **T-BC-K / L / M / N — the M9.3 blocker** |
| 15 | **Result encoding** | OBX `NM`/`ST` → results. OBX-3 `^`-split, index 1 → parameter name; OBX-5 value; OBX-6 units; OBX-7 reference range; OBX-8 flag (`~`-split, first element; `N` → `None`). `HISTOGRAM` / `SCATTERGRAM` / `BASE64` payloads skipped | **VERIFIED for BC-5150 shape** | T-BC-A: confirm the full parameter panel and units in routine operation |
| 16 | **Status / flag semantics** | Only the first `~`-separated flag element is kept; literal `N` becomes `None` | **PARTIAL** — `H~N` observed in captures; full flag vocabulary UNKNOWN | T-BC-A: collect the complete observed flag set |
| 17 | **OBX `IS` metadata** | Parsed into `ParsedHL7.is_metadata` "for future evidence-based classification" — but **never consumed or persisted anywhere**. Verified: `is_metadata` appears only in `parsers/hl7.py` and `parsers/__init__.py` | **VERIFIED, and it differs by category:** the session-1 patient frame carried four `IS` entries — `08001^Take Mode^99MRC`, `08002^Blood Mode^99MRC`, `08003^Test Mode^99MRC`, `01002^Ref Group^99MRC` — while the Background frame carried **none**. Earlier captures also show `12002^Leucocytosis^99MRC`. Whether a QC run carries `IS` metadata is **UNKNOWN** | **T-BC-K** — capture every `IS` field seen. This is a §9.5 candidate, not a rule |
| 22 | **Idle heartbeat (`0x02`)** | No `0x02` handling existed after the M8 transport rewrite; `extract_frames` now discards any bytes preceding the MLLP start block (`integration/mllp.py`, commit `19d333e`) | **VERIFIED:** the BC-5150 emits **single-byte `0x02` while idle**. Accumulated heartbeats were prepended to the next frame, pushing `MSH` off the front and making otherwise-valid messages `UNPARSEABLE`. Confirmed in live rows (2–9 leading `0x02` bytes) and by a same-session control frame with none, which parsed correctly | Heartbeat **interval** is UNKNOWN and not required by any current decision. Whether other instruments emit an equivalent is UNKNOWN |
| 18 | **Message ordering** | No sequencing logic. Messages are processed in arrival order; `run_sequence` is assigned at ingestion time, not from the message | **UNKNOWN** | T-BC-R |
| 19 | **Multiple messages per connection** | Supported: the receive buffer drains every complete frame in a loop before reading again (`client.py:92-98`) | **UNKNOWN** on the physical device | T-BC-S |
| 20 | **Duplicate messages** | Only the exact-retransmission guard (row 10) exists | **UNKNOWN** | §8 |
| 21 | **Instrument startup / shutdown** | No handling. The supervisor restarts only a **dead worker thread**; it never inspects sockets or message timing (`supervisor.py`) | **UNKNOWN** — does the instrument emit anything at power-on/self-test? | T-BC-H, T-QC-06 |

### 5.2 Parser readiness — REPO-CONFIRMED

The parser registry (`integration/parsers/registry.py`) is a static dictionary containing **exactly one** entry:

```
_PARSERS = { "bc5150_hl7": parse_hl7_bc5150 }
```

Resolution is an exact-match lookup. An unknown `parser_key` raises `ParserNotRegisteredError` with **no fallback and no fuzzy matching**, because binding a message to the wrong parser can produce plausible-but-incorrect clinical data.

**Consequence:** eight of the nine instruments have **no parser**. Enabling any of them today fails loudly at startup. This is correct behaviour, and it means every non-BC-5150 instrument needs a captured message corpus **before** a parser can even be written — not merely before it can be trusted.

### 5.3 Classification readiness — REPO-CONFIRMED

Three policies exist (`integration/classification.py`):

| Policy | Behaviour |
|---|---|
| `strict` (default; also the fallback for an unknown name) | Everything parseable → `UNCLASSIFIED`. Nothing reaches clinical persistence |
| `unverified_passthrough` | Everything parseable → `PATIENT_RESULT`. **Not evidence-based**; an explicit owner risk decision |
| `bc5150_field_verified` | OBR-3 normalised `== "background"` → `NON_PATIENT` / `OBR3_BACKGROUND`; **everything else** → `UNCLASSIFIED` / `BC5150_BACKGROUND_ONLY` |

The source documents, and the test suite enforces, that the following are **deliberately not** discriminators because no field evidence supports them: PID-3 emptiness, low or zero numeric values, histogram/scattergram presence, Take/Blood/Test Mode, `99MRC` identifiers, and the `ORU^R01` trigger itself.

`test_bc5150_field_verified_never_emits_patient_result` asserts this structurally against OBR-3 values `QC`, `Calibration`, `Control`, `Maintenance`, `""` and `Backgroundish`.

**Session 1 vindicates two of those exclusions directly.** PID-3 was the literal `^^^^MR` in *both* the patient and the Background frame, and both frames carried the same `ORU^R01` trigger and the same `OBR-4` — so had either been used as a discriminator, it would have been wrong. This is evidence that the narrowness of the M8.2b rule was correct, not merely cautious.

> **The BC-5150 policy is deliberately incomplete.** It classifies exactly one thing and quarantines everything else. Real patient samples from a BC-5150 running this policy are `UNCLASSIFIED` and do **not** produce clinical rows. Making patient ingestion work is a separate decision requiring separate evidence (§9.4).

### 5.4 Existing BC-5150 field evidence — VERIFIED

Recorded in `backend/tests/test_ingestion.py` §K:

- **Patient samples 28, 29, 30, 31** — PID metadata present, numeric results.
- **Background run** — OBR-3 literally `Background`, PID-3 components empty, WBC ≈ 0.05–0.06, RBC 0.00, HCT 0.0, PLT 0–1, histogram/scattergram segments present. *(Session 1 refines this: the PID-3 **field** is present as the literal `^^^^MR`, and the same is true of the patient frame — see §5.1 row 7.)*
- Message shape: `ORU^R01`, HL7 `2.3.1`, `UNICODE` charset, `OBR-4 = 00001^Automated Count^99MRC`, `OBR-24 = HM`, `OBX IS 08001^Take Mode^99MRC`.

**Limitation as it now stands.** The repository still holds only **field-shaped fixtures**, not a committed raw corpus. However, session 1 produced a **verbatim raw corpus in `lis_marina_permata_dev`**: `instrument_messages.raw_message` retains every frame byte-exactly, including the failed and unclassified ones. That table is now the authoritative session-1 evidence store (§12.4). Promoting redacted derivatives of it into committed M9.4 fixtures remains outstanding.

### 5.5 BC-5150 field session 1 — VERIFIED

The first controlled live integration test. Physical configuration in §4.3.

**Two defects were found and are recorded here because both were live-blocking:**

1. **Schema drift — dev database two Alembic revisions behind head.** Ingestion failed at the first `INSERT` with `UndefinedColumn: column "message_class" ... does not exist`. Pending were `c5465739f048` (M8.2 classification columns) and `4aff9e134f16` (M8.4 indexes). `py -m alembic upgrade head` was run; the database is now at **`4aff9e134f16 (head)`**. The database was *behind*, not drifted — no unexpected columns existed. **Because the failure occurred in T1, no raw audit row was written and those frames were lost to the LIS.**
2. **Transport regression — `0x02` heartbeats.** See §5.1 row 22. Fixed in `19d333e`; 31 focused framing tests plus the full backend suite (**165 passed**) verified it, and the fix was replay-tested against **four real previously-failed frames**, all of which recovered and parsed.

**Outcome after the fix — VERIFIED:**

| Observation | Evidence |
|---|---|
| LIS `10.0.0.10` → analyzer `10.0.0.2:5100`, outbound TCP | Live connection; packet capture |
| Instrument → LIS `ORU^R01` over MLLP | Packet capture |
| LIS → instrument HL7 ACK containing **`MSA\|AA`** | Packet capture |
| Successful ingestion into `lis_marina_permata_dev` | `id_message=152`, `id_instrument=2`, `parse_status=Success`, `message_class=UNCLASSIFIED`, `classification_rule=BC5150_BACKGROUND_ONLY` |
| Background correctly classified | `NON_PATIENT` / `OBR3_BACKGROUND` rows present |
| **Production database untouched** | All work against `lis_marina_permata_dev` |

**What the session did not establish.** Because `bc5150_field_verified` is fail-closed, **patient messages remained `UNCLASSIFIED` and created no `Patient` / `Visit` / `Order` / `TestRun` / `Result` rows.** The clinical persistence path is therefore still unexercised against the physical device, and the exact-retransmission guard was never reached (§8.1).

### 5.6 Session-1 corpus — a limitation that governs every conclusion

| Category | Messages captured | **Distinct events** |
|---|---|---|
| Patient | 10 | **1** — every frame carries OBR-3 `42` and the same OBR-7 |
| Background | 2 | **1** — both carry the same OBR-7 |
| QC / control / calibration / maintenance / blank / startup | **0** | **0** |

Ten patient messages are **one specimen retransmitted**, not a corpus. Within session 1 the effective sample size is **n = 1 per observed category**, and every category a positive patient rule must *exclude* has **n = 0**. This is why §9.5 approves nothing.

*Session 1 is not the whole evidence base — see §5.7 for the larger historical corpus, which broadens the Background evidence but does not supply the missing categories.*

### 5.7 Historical "Comm. All" corpus — VERIFIED shape, UNKNOWN ground truth

A bulk historical transmission of **360 messages** exists in addition to the session-1 captures. Its composition is:

| Group | Count | Shape | Status |
|---|---|---|---|
| Background | **27** | OBR-3 `Background`; PID-5 empty; `count_IS = 0`; `total_OBX = 22` | **VERIFIED — consistent, no exceptions** |
| Patient-like (named) | **313** | PID-5 populated | **Shape VERIFIED; clinical class NOT ESTABLISHED** |
| **Unidentified** | **20** | PID-5 empty **and** numeric OBR-3 | **UNKNOWN** |
| *Total* | *360* | | |

**What this strengthens.** All 27 Background messages carry OBR-3 `Background`, with no counter-example. Together with the two live session-1 captures (T-BC-J), this is the strongest evidence in the project for any classification rule. It remains **BC-5150 field evidence scoped to this instrument**, and is not transferable to any other instrument (§18.1).

**What this does not establish.** The 20 unidentified messages have **no ground truth**. They are consistent with at least three mutually exclusive explanations:

1. unlabelled patient specimens (run without an operator-entered name),
2. QC / control material,
3. another non-patient workflow not yet observed.

> **The 20 must not be called QC.** Nothing in the corpus distinguishes those three cases, and the corpus carries no operator log tying any message to an action. Treating "PID-5 empty" as a QC marker would be exactly the inference §9.5 rejects — it would also reclassify any genuine patient sample run without a name.

**Why 313 named messages still do not authorise a positive patient rule.** They establish that named messages are *common*, not that naming is *sufficient*. The corpus contains no confirmed QC message against which "PID-5 populated" could be falsified, so the candidate's failure mode — QC labelled with a control name reaching PID-5 — remains untested. Volume is not ground truth.

---

## 6. Validation Priorities

### 6.1 Prioritisation criteria

1. Existing field evidence (a partially-known instrument yields faster, safer results)
2. Clinical importance and routine throughput
3. Protocol uncertainty (unknown protocol blocks all downstream work)
4. Architectural impact (does it force a transport or parser change?)
5. Likelihood of changing an M9 decision

### 6.2 Priority matrix

Confidence labels: **VERIFIED / PARTIALLY VERIFIED / UNVERIFIED / UNKNOWN**.

| # | Instrument | Identity confidence | Protocol confidence | Transport confidence | Parser readiness | Config readiness | Priority | Blocking unknowns |
|---|---|---|---|---|---|---|---|---|
| 2 | Mindray BC-5150 | VERIFIED | VERIFIED (HL7 2.3.1) | **VERIFIED** (TCP/IP, LIS=client, `10.0.0.2:5100`) | **Ready** (`bc5150_hl7`) | **Configured and live** (`instruments.json` present) | **P1** | **QC / calibration / control / maintenance categories (zero captures); positive patient rule; specimen-counter reset; ACK dependence** |
| 3 | Sysmex XN-550 | VERIFIED (nameplate) | UNVERIFIED | UNVERIFIED | **None** | Not configured | **P2** | Actual protocol; actual transport; whether LIS may be client |
| 4 | Mindray BS-200E | VERIFIED (nameplate) | UNVERIFIED | UNVERIFIED | **None** | Not configured | **P2** | Same. Same vendor as BC-5150 — HL7 dialect similarity is INFERRED, not known |
| 6 | Boditech ichroma II | VERIFIED (nameplate) | UNVERIFIED | UNVERIFIED | **None** | Not configured | **P3** | Protocol; transport |
| 9 | ACON / Mission Insight Expert U120 | VERIFIED (nameplate) | UNVERIFIED | UNVERIFIED | **None** | Not configured | **P3** | Protocol; transport; reference lists proprietary **and** ASTM |
| 5 | Sysmex BX-3010 | VERIFIED (nameplate) | UNVERIFIED | UNVERIFIED | **None** | Not configured | **P4** | Reference lists **RS-232 only** — see §11.4 |
| 7 | Medica EasyLyte PLUS | VERIFIED (nameplate) | UNVERIFIED | UNVERIFIED | **None** | Not configured | **P4** | Reference lists proprietary ASCII over RS-232 |
| 8 | DFI R-300 | VERIFIED (nameplate) | UNVERIFIED | UNVERIFIED | **None** | Not configured | **P4** | Reference lists proprietary over RS-232 |
| 10 | Precil 106-AC-57000131 | **UNVERIFIED** | UNKNOWN | UNKNOWN | **None** | Not configured | **P5** | **Instrument identity itself is unverified** — the stored name is a reported ID, not a confirmed model |

**Rationale for the ordering.** BC-5150 is P1 because it is the only instrument that can produce evidence *today*, and because it must establish the methodology every other instrument will follow. XN-550 and BS-200E are P2 because both are plausibly TCP/IP-capable, so they are the cheapest tests of whether the current client-only transport generalises. The RS-232 group is P4 not because it is unimportant but because it likely requires hardware (§11.4) that must be procured before any software question can be asked. Precil is P5 because **identity must be established before protocol is even a meaningful question**.

---

## 7. BC-5150 Validation Plan

BC-5150 is the reference instrument. These tests establish both its behaviour and the methodology.

**Common preconditions for every test below:** `instruments.json` contains a BC-5150 entry (`mode: "client"`, correct `host`/`port`, `parser_key: "bc5150_hl7"`, `identity_prefix`, `enabled: true`); the integration service runs against `lis_marina_permata_dev`; a packet capture (§12.3) runs for the whole session; the operator log is open.

**Classification policy note.** Run the primary corpus-collection tests under `bc5150_field_verified` (the production-candidate policy) so the fail-closed behaviour is observed as it will ship. Only if the owner explicitly accepts the risk should any test run under `unverified_passthrough`, and that must be recorded on the evidence record.

| ID | Scenario | Objective | Operator action | Expected observable | Evidence to capture | Question answered | Blocks M9? |
|---|---|---|---|---|---|---|---|
| **T-BC-A** | Normal patient sample — **PASS (session 1)** | Establish the routine message shape | Run one ordinary sample end to end | One `ORU^R01`; `AA` returned | Raw frame; MSH-10; PID-3 population and shape; OBR-3; OBR-7; full OBX list with units, ranges, flags | **Answered for one specimen:** `ORU^R01` / HL7 2.3.1 / MLLP; PID-3 = `^^^^MR`; PID-5 populated; OBR-3 numeric (`42`); OBR-7 populated; clinical OBX and `IS` metadata present. **Still needs ≥3 distinct patients** (§5.6) | Yes — feeds §10 and M9.3 |
| **T-BC-B** | Repeat run, same patient/order | Distinguish a genuine rerun from a retransmission | Re-aspirate the same sample as a new run | Second message | Both raw frames; **whether OBR-3 changes**; whether MSH-10 changes; whether OBR-7 changes | Does a rerun reuse the sample number? | **Yes — M9.2 + §10** |
| **T-BC-C** | **Background manual retransmission** — **PASS (session 1)** | Observe true duplicate delivery | Manual resend of a Background run | Duplicate message | Both frames compared | **Answered:** MSH-7 and MSH-10 change; OBR-3 stays `Background`; OBR-7 and payload unchanged | **Yes — M9.2** |
| **T-BC-C-P** | **Patient manual retransmission** — **PASS (session 1)** | Confirm the same invariants hold for a patient message | Manual resend of a patient sample | Duplicate message | Both frames compared | **Answered:** MSH-7 and MSH-10 change; PID-3 stays `^^^^MR`; PID-5 stays populated; OBR-3 stays `42`; OBR-7 and clinical payload unchanged | **Yes — M9.2** |
| **T-BC-D** | Retransmission, changed timestamp | Test the current guard's weak point | Resend after a delay | Duplicate with possibly-new OBR-7 | Both frames; diff | Does the existing `(instrument, no_registrasi, waktu_run)` key still hold? | **Yes — M9.2** |
| **T-BC-E** | New Message Control ID | Determine MSH-10 semantics | Compare MSH-10 across all captures | — | MSH-10 of every message in the session | Is MSH-10 unique per transmission or per sample? | **Yes — M9.2** |
| **T-BC-F** | Same Message Control ID | Determine whether MSH-10 is stable across a resend | Resend and compare | — | MSH-10 pair | Can MSH-10 serve as a dedup key at all? | **Yes — M9.2** |
| **T-BC-G** | Disconnect / reconnect | Observe instrument-side behaviour when the LIS vanishes | Stop the integration service mid-session, restart after 60 s | Instrument may retry, buffer, error, or discard | Instrument UI state; any error shown; whether the message arrives after reconnect and whether it is altered | Does the instrument retry? | Yes — M9.2 + M9.5 |
| **T-BC-H** | Instrument restart | Observe power-cycle traffic | Power-cycle per lab procedure | Possible startup/self-test traffic | Any message emitted before the first patient sample | Does startup produce classifiable traffic? | Yes — M9.3 |
| **T-BC-I** | Buffered / offline results | Determine whether results survive an outage | With the LIS down, run a sample; bring the LIS up | Message may arrive late or never | Arrival timing; OBR-7 vs `received_at` skew | Can a message arrive long after its OBR-7? | Yes — M9.2 |
| **T-BC-J** | **Background** — **PASS (session 1)** | Re-confirm the one verified rule against a live device | Trigger a background count | OBR-3 `Background`; PID-3 empty; near-zero counts | Full raw frame | **Confirmed on the physical device.** PID-3 = `^^^^MR`; PID-5 absent; OBR-3 `Background`; OBR-7 populated. **Note:** the frame *does* carry clinical-style `NM` OBX values (WBC 0.05, RBC 0.00, HGB `*****`, HCT 0.0, PLT 0) and **no `IS` metadata** | No — already VERIFIED, now re-confirmed live |
| **T-BC-K** | **QC / control** | **Discover the QC indicator** | Run a QC / control material per lab procedure | UNKNOWN | Full raw frame; **every OBX `IS` field**; OBR-3, OBR-4, OBR-24; instrument UI label | **How is QC distinguishable?** | **Yes — M9.3 blocker** |
| **T-BC-L** | Calibration | Discover the calibration indicator | Run calibration if lab procedure permits | UNKNOWN | As above | How is calibration distinguishable? | **Yes — M9.3** |
| **T-BC-M** | Maintenance | Discover maintenance traffic | Run a maintenance cycle | UNKNOWN — may emit nothing | As above, or explicit "no message" | Does maintenance emit anything? | Yes — M9.3 |
| **T-BC-N** | Control material | Distinguish "control" from "QC" if the instrument separates them | Run control material | UNKNOWN | As above | Are these one category or two? | Yes — M9.3 |
| **T-BC-O** | Missing patient identifier — **priority raised by session 1** | Determine whether PID-3 is **ever** populated with a real MRN | Run a sample with a patient/barcode assigned per normal lab workflow, and one without | PID-3 components populated vs `^^^^MR` | Raw frame; resulting `SIMRS_IDENTITY_NOT_RESOLVED` flag | Session 1 found `^^^^MR` in **both** patient and Background frames, so on current evidence the synthetic path fires for every message. **Is that routine, or an artefact of how session-1 samples were run?** | **Yes — §9.6, §10, S5** |
| **T-BC-P** | Missing specimen / order identifier | Determine whether OBR-3 can ever be empty | Only if producible without forcing an abnormal state | OBR-3 empty → `Failed` + `AE` | Raw frame | Is the current hard rejection correct? | Yes — §10 |
| **T-BC-Q** | Unexpected / empty fields | Observe real-world field sparsity | Passive: review the whole captured corpus | — | Field-population census across all captures | Which fields are reliably present? | Yes — M9.4 |
| **T-BC-R** | Message sequencing | Determine ordering guarantees | Run several samples in quick succession | — | Arrival order vs OBR-7 order | Can messages arrive out of chronological order? | Yes — M9.2 |
| **T-BC-S** | Multiple messages per connection | Confirm the multi-frame buffer path against the device | Run samples back to back | Several frames on one TCP connection | Packet capture showing frame boundaries | Does the instrument reuse the connection? | Yes — M9.5 |
| **T-BC-T** | ACK / retry behaviour | Determine ACK dependence | Observe normal ACK; then, if safe, delay or withhold one | UNKNOWN | Instrument UI; whether it retries; timing | Does the instrument require an ACK, and on what timeout? | **Yes — M9.5, and gates any ACK change** |

**Not every scenario is guaranteed producible.** T-BC-C, T-BC-I, T-BC-L, T-BC-M, T-BC-N and T-BC-T depend on instrument features and lab policy that may not exist or may not be safely exercisable. Any such test is recorded `NOT APPLICABLE` with the reason — which is itself evidence, and must not be silently skipped.

---

## 8. Deduplication Evidence Plan (M9.2)

### 8.1 What already exists, stated precisely

`docs/07_TASK_LIST.md` M9.2 states that "foundational exact-retransmission handling stays in M8.2". The M8.2 mechanism is, verbatim from `integration/repository.py:126-141`:

```
existing_run = SELECT TestRun.id_run
  JOIN Order ON TestRun.id_order = Order.id_order
  JOIN Visit ON Order.id_visit = Visit.id_visit
  WHERE TestRun.id_instrument = <instrument>
    AND Visit.no_registrasi   = <identity_prefix + OBR-3>
    AND TestRun.waktu_run     = <OBR-7>
```

If a row matches, ingestion short-circuits: `parse_status = "Success"`, `error_detail = "Retransmission: Source measurement already exists"`, and an `AA` is returned.

**The existing key is therefore `(id_instrument, identity_prefix + OBR-3, OBR-7)`. MSH-10 plays no part in it.**

Two consequences follow directly (INFERRED from the code, and to be confirmed in the field):

1. A retransmission whose **OBR-7 differs by even one second** does not match the guard, and will create a **new `TestRun` with `run_sequence = MAX+1`** — i.e. a duplicate clinical run. This is the specific defect M9.2 exists to address.
2. A genuine repeat run that reuses the same OBR-3 **and** reports the same OBR-7 would be silently swallowed as a retransmission. Whether the instrument can produce that pair is UNKNOWN.

### 8.2 The MSH-10 storage gap — REPO-CONFIRMED

`InstrumentMessage` columns are: `id_message`, `id_instrument`, `raw_message`, `parse_status`, `error_detail`, `message_class`, `classification_rule`, `received_at`.

**There is no control-ID column.** MSH-10 exists only inside `raw_message` text. Any dedup strategy keyed on MSH-10 therefore requires either a schema addition or a text extraction over raw messages. This is a design consequence to be weighed **after** the evidence, not a reason to prefer or avoid MSH-10.

### 8.3 Evidence required before choosing an algorithm

For each captured message pair, record and compare:

| Dimension | What to measure | Why it matters |
|---|---|---|
| **MSH-10** | Value on original and on resend | Whether it is a transmission id or a sample id — the single most decisive fact |
| **OBR-7** | Value on original and on resend | Whether the existing key survives a resend |
| **OBR-3** | Value on original, resend, and repeat run | Whether specimen id is stable, and whether it distinguishes rerun from resend |
| **PID-3** | Presence and value | Whether patient identity can participate in a key at all |
| **Instrument identity** | `id_instrument` | Whether a key must be per-instrument (the current one is) |
| **Connection / session** | Same TCP connection or new? | Whether session boundaries correlate with resends |
| **Byte-identity** | Full-frame hash of both | Distinguishes byte-identical from logically-identical-but-byte-different |
| **Reconnect resend** | Whether a resend follows reconnection | Whether outage recovery produces duplicates |
| **Timeout resend** | Whether withholding an ACK triggers a resend | Whether the LIS's own latency can create duplicates |
| **Manual resend / reprint** | Whether the function exists; what it emits | The most likely operator-driven duplicate source |

### 8.4 Decision matrix this evidence must resolve

The evidence must let the project answer, without guessing:

- If MSH-10 is unique per transmission → it identifies transmissions, not measurements, and **cannot alone** distinguish a resend from a rerun.
- If MSH-10 is stable across a resend → it is a strong dedup key candidate.
- If OBR-7 is stable across a resend → the existing M8.2 key already covers the case and M9.2 shrinks to per-instrument tuning.
- If OBR-7 changes across a resend → the existing key is insufficient and M9.2 must add a supplementary key.
- If OBR-3 is reused for a genuine rerun → dedup and rerun are **not separable by identity alone**, and §10 becomes the harder blocker.

### 8.5 What session 1 answered — VERIFIED (manual retransmission only)

| Dimension | Observation | Consequence |
|---|---|---|
| **MSH-7** | **Changes** on manual retransmission | It is a transmission timestamp, not a measurement timestamp |
| **MSH-10** | **Changes** on manual retransmission; **repeated values observed across separate messages** in the session corpus | MSH-10 is a transmission/message control id. It is **not safe as a sole logical-result dedup key**, and it must **not** be described as globally unique |
| **OBR-3** | **Invariant** — `Background` stayed `Background`; `42` stayed `42` | Both components of the existing key survive an operator-initiated resend |
| **OBR-7** | **Invariant** across both retransmissions | The M8.2 key `(instrument, prefix + OBR-3, OBR-7)` is **not invalidated** by manual retransmission. Stop condition **S2 did not trigger** |
| **Payload** | Unchanged | Logically identical resends are byte-comparable on the clinical portion |

**Scope of this finding, stated precisely.** It covers **operator-initiated manual retransmission only**, on a device with `Auto Retransmit OFF` and `ACK Sync OFF` (§4.3). It is **strong observed evidence, not an absolute universal guarantee.** These remain UNKNOWN and are *not* settled by session 1:

- resend triggered by reconnection (T-BC-I) or by ACK timeout (T-BC-T);
- any automatic retransmission (never enabled);
- whether a **genuine repeat run** reuses OBR-3 and/or OBR-7 (T-BC-B) — the case that separates a rerun from a resend;
- whether the specimen counter recycles (T-ID-02).

**The guard itself was never exercised.** Under `bc5150_field_verified` a patient message returns as `UNCLASSIFIED` at `repository.py:101-106`, before the dedup query at `:126`. Every retransmission in session 1 therefore produced a **new raw `instrument_messages` row** — correct audit behaviour, and not evidence that dedup works.

> **No deduplication algorithm is proposed here, and none should be chosen before T-BC-B, D, E, F and I are complete.** The task-list wording — "supplementary keys such as HL7 Control ID **where justified**" — is the correct posture; session 1 in fact makes the "HL7 Control ID" option *less* attractive, since MSH-10 was observed to repeat.

---

## 9. QC / Calibration Evidence Plan (M9.3)

### 9.1 Current state

Exactly one non-patient rule is field-verified, and it applies to exactly one instrument:

> **VERIFIED RULE (BC-5150 only):** OBR-3, whitespace-stripped and casefolded, equal to `background` → `NON_PATIENT`.

Everything else is `UNCLASSIFIED`. There are **no** verified rules for QC, calibration, maintenance, control material, blank runs, startup self-test, or reagent/system checks — on any instrument, including the BC-5150.

### 9.2 Observation targets

For each instrument, and for each category the lab can safely produce:

| Category | Observable? | Evidence to capture |
|---|---|---|
| Normal patient | Yes | Baseline for comparison |
| QC / control | Lab-dependent | Full raw frame + operator-visible label |
| Calibration | Lab-dependent | Full raw frame |
| Maintenance | Lab-dependent | Full raw frame, **or an explicit record that nothing was emitted** |
| Background | Yes — **BC-5150 VERIFIED, re-confirmed live in session 1** | Complete for BC-5150; still required for every other instrument |
| Startup / self-test | Yes (T-BC-H) | Any traffic before the first sample |
| Blank | Lab-dependent | Full raw frame |
| Reagent / system check | Lab-dependent | Full raw frame |

For **every** non-patient message captured, record: raw message; message timestamp (OBR-7) and `received_at`; MSH-10; OBR-2/3/4/24; **every OBX `IS` segment** (identifier and value); OBX `NM`/`ST` values; instrument state; and the exact operator action that generated it.

The OBX `IS` capture is emphasised because `ParsedHL7.is_metadata` already exists as the parser's hook "for future evidence-based classification" and is **currently discarded** (§5.1 row 17). If a QC indicator exists, `IS` metadata is where it most plausibly lives — but that is INFERRED, and must not be treated as a plan until observed.

### 9.3 Classification of findings

Every candidate rule produced by a field session must be labelled:

- **VERIFIED RULE** — observed repeatedly, unambiguous, and safe to encode. Requires **at least two independent captures** of the same category, ideally on different days.
- **CANDIDATE RULE** — observed once, or observed with ambiguity. Recorded, **not implemented**.
- **UNKNOWN** — category not observed. Stays `UNCLASSIFIED` by the fail-closed default.

A single observation never becomes a production rule. The Background rule qualified because it was observed in multiple captures with a consistent, structurally unambiguous marker.

### 9.4 The inverse problem — do not overlook it

M9.3's task-list text includes: "Validate that the conservative fail-closed mechanism does not incorrectly quarantine genuine patient results."

Under `bc5150_field_verified`, **every genuine patient sample is `UNCLASSIFIED` and produces no clinical rows.** The instrument is safe but not yet useful. Making patient results flow requires a **positive** patient-identification rule, which needs its own evidence — the same standard as any QC rule.

T-BC-A and T-BC-Q are therefore not merely descriptive; they are the evidence base for whichever positive rule is eventually proposed. This is a distinct engineering decision from QC filtering and should be tracked separately.

### 9.5 Positive patient rule — candidate assessment — **NOT APPROVED**

Session 1 produced the first side-by-side field comparison of a patient frame against a Background frame. It is recorded here because it **eliminates one candidate outright** and sharpens the rest — but **no positive `PATIENT_RESULT` rule is approved, and none may be implemented on this evidence.**

**Field-level comparison — VERIFIED (session 1, n = 1 per category):**

| Field | Patient | Background | Discriminates? |
|---|---|---|---|
| MSH-9 trigger | `ORU^R01` | `ORU^R01` | **No — identical** |
| PID-3 | `^^^^MR` | `^^^^MR` | **No — identical** |
| PID-5 | populated | absent | Yes |
| OBR-3 | numeric (`42`) | `Background` | Yes (already the verified rule) |
| **OBR-4** | `00001^Automated Count^99MRC` | `00001^Automated Count^99MRC` | **No — identical** |
| OBR-24 | `HM` | `HM` | **No — identical** |
| Clinical `NM`/`ST` OBX | present | **also present** (0.05 WBC, 0.00 RBC, `*****` HGB, 0.0 HCT, 0 PLT) | **No** |
| `IS` metadata | 4 entries | none | Yes |

**Candidates — all CANDIDATE or REJECTED:**

| Candidate | Status | Supporting evidence | What it would misclassify if the assumption is wrong | Falsifying test |
|---|---|---|---|---|
| Presence of clinical OBX | **REJECTED — falsified** | — | Background itself emits accepted clinical values, including a non-zero WBC. The rule is disproved by session-1 data | Already falsified |
| OBR-3 ≠ `Background` (negation of the verified rule) | **REJECTED** | Only the inverse of a known rule | Turns **every unobserved category** into a patient result. `classification.py` explicitly refuses this reasoning | Excluded by design |
| OBR-3 numeric | **CANDIDATE** | Patient `42`; Background is a word | A QC run plausibly uses the **same sample counter**, and would then be classified as a patient result | **T-BC-K** |
| PID-5 populated | **CANDIDATE** | Patient populated; Background absent | QC / control material is routinely **labelled** by operators. If that label reaches PID-5, QC becomes a patient result and control values enter the clinical record | **T-BC-K** |
| `IS` metadata present | **CANDIDATE** | Patient 4 entries; Background none | Take / Blood / Test Mode are **physical aspiration parameters**; a QC run is physically aspirated and would plausibly carry them | **T-BC-K** |
| Conjunction of the three above | **CANDIDATE (strongest)** | All three hold for patient, all fail for Background | Safe only if **at least one conjunct reliably fails for QC**. No evidence any of them does | **T-BC-K** |

**Why more patient samples cannot settle this.** Every candidate already separates patient from Background — but Background is *already handled*. The rule's actual job is to exclude **QC, calibration, control and maintenance**, and those have **zero captures**. Collecting more patient samples cannot reduce that risk; only a QC capture can.

**The 360-message historical corpus does not change this conclusion** (§5.7). Its 313 named messages raise confidence that naming is *common*, not that it is *sufficient* — no confirmed QC message exists in that corpus to falsify the candidate against. Its **20 PID-5-empty numeric messages are UNKNOWN, not QC**, and are the clearest illustration of the problem: under the "PID-5 populated → PATIENT" candidate they would be quarantined, and under a "PID-5 empty → QC" rule they would be silently discarded — and on current evidence either could be wrong.

The failure mode is asymmetric and clinical: a false `PATIENT_RESULT` on a QC run writes control-material values into a patient record. Under `bc5150_field_verified` the system is currently inert but safe; a premature positive rule would be neither.

> **Decision: positive patient classification is NOT APPROVED.** Minimum evidence to revisit — **T-BC-K ×2 on different days** (§9.3 repetition rule), plus **T-BC-A across ≥3 distinct patients** and **T-BC-H**. See §16 step 6.

### 9.6 A second, independent blocker on enabling `PATIENT_RESULT`

Even a *correct* classification rule would not by itself make patient ingestion safe, because of what happens **after** classification.

`nomor_rm` parses to `""` for every message observed so far (PID-3 = `^^^^MR` in both categories, §5.1 row 7). Every patient message would therefore take the **synthetic-patient path**: `nomor_rm = no_registrasi = "BC5150-<OBR-3>"`, flagged `SIMRS_IDENTITY_NOT_RESOLVED`, with the **specimen counter as the Visit key** (§10.1).

If that counter recycles, two different real patients become the same `no_registrasi` → the same Visit → the same Order, and the M8.2 guard would **not** catch it because `waktu_run` differs. This is stop condition **S1**, and it is gated on **T-ID-02** and **Q4**, not on M9.3.

> **M9.3 and the §10 specimen-identity question must both clear before `PATIENT_RESULT` is enabled for the BC-5150.** Neither alone is sufficient.

---

## 10. Specimen / Visit / Order Identity Evidence

This is the largest unresolved architectural question, and it is a prerequisite for production multi-instrument ingestion.

### 10.1 Current behaviour — REPO-CONFIRMED

From `integration/repository.py:123-174`:

1. `no_registrasi = identity_prefix + OBR-3`
2. `Visit` is looked up by `no_registrasi`; created if absent, with `waktu_kunjungan = OBR-7`
3. `Order` is looked up by `SELECT ... WHERE Order.id_visit == visit.id_visit` — **one Order per Visit**
4. Patient: `nomor_rm = PID-3.1`; if empty, `nomor_rm = no_registrasi` and the message is flagged `SIMRS_IDENTITY_NOT_RESOLVED`
5. `TestRun.run_sequence = MAX+1` for that Order

**Therefore the instrument's specimen number is the visit key, and specimen → visit → order is 1 : 1 : 1.** The `identity_prefix` is the only thing preventing collisions between instruments that both emit sample number `30`.

### 10.2 What this implies, and why it needs evidence

Two properties follow directly, and both are risks:

- **Sample-number reuse.** BC-5150 captures show short integer sample numbers (session 1: `42`; earlier: 30, 31, 359). If the instrument's counter resets — daily, on power cycle, or at a rollover — then the same `no_registrasi` will recur for a **different specimen**, and the second specimen will be attached to the **first patient's Visit**. Whether the counter resets is **UNKNOWN** and is the single most important identity question.
- **Synthetic patients — escalated by session 1.** Previously recorded as observed "in Background captures" with routine behaviour unknown. Session 1 shows the PID-3 field is the literal **`^^^^MR` in the patient frame as well**, so `nomor_rm` parses to `""` in **both** categories. On the evidence available, the synthetic-patient path would fire for **every** BC-5150 message, not just Background. Whether PID-3 is *ever* populated in routine clinical work — via barcode, host worklist or manual entry — is **UNKNOWN** and is now a higher-priority question (T-BC-O, Q8, stop condition **S5**).

### 10.3 Evidence required

| Field | What to determine |
|---|---|
| Patient identifier (PID-3) | Populated in routine use? Source — barcode, host worklist, manual entry? Format and stability? |
| Specimen identifier (OBR-3) | Format; monotonic or resetting; **does it reset daily / on restart / at rollover?**; reused across patients? |
| Accession number | Does a separate accession concept exist on the instrument? |
| Order number | Does the instrument carry any order concept distinct from the sample? |
| Sample ID | Same as OBR-3, or a distinct field? |
| Rack / position | Emitted anywhere? Does it disambiguate a reused sample number? |
| Barcode | Read by the instrument? Does it reach PID-3 or OBR-3? |
| Instrument-generated ids | Any identifier the instrument mints itself |
| Re-run identifiers | Does a rerun carry any marker distinguishing it from the original? |
| Timestamps | OBR-7 granularity; does it change on rerun and on resend? |
| Duplicate identifiers | **Directly observe whether two different specimens can share an OBR-3** |

### 10.4 Distinctions the evidence must make separable

The eventual rule must distinguish, using only observed fields:

1. same patient, same order, **repeat run**
2. same specimen, **retransmission**
3. **new specimen**, same patient
4. same specimen, **new order**
5. **non-patient** material (QC, control, calibration)
6. **instrument/background** material

Cases 1 and 2 are currently indistinguishable if OBR-7 differs (§8.1). Case 3 depends entirely on whether OBR-3 is unique per specimen. Case 4 is not representable at all under the current one-Order-per-Visit model.

### 10.5 Constraints on any future solution

- **Do not invent a replacement key.** The key must be derived from fields the instrument demonstrably emits.
- **Do not use date-based or otherwise arbitrary keys.** A date-scoped identity such as `{instrument}-{YYYYMMDD}-{specimen}` was previously considered and withdrawn for lack of evidence; it must not reappear without direct observation of counter-reset behaviour.
- **Do not implement anything** on the basis of this section. It defines the questions.

---

## 11. Transport / Connectivity Validation

### 11.1 Current transport — REPO-CONFIRMED

| Property | Value | Source |
|---|---|---|
| Role | **LIS is the TCP client**; it dials the instrument | `client.py` `s.connect((host, port))` |
| Supported modes | `{"client"}` only; any other value is a config validation error | `core/config.py:13,38-47` |
| Framing | MLLP `0x0B` … `0x1C 0x0D` | `client.py:65-66` |
| Connect timeout | 5 s | `client.py:72` |
| Read timeout | 1 s (stop-event responsiveness) | `client.py:79` |
| Reconnect delay | Fixed 5 s, unlimited retries | `client.py:116` |
| Multi-frame per read | Supported — drains all complete frames per buffer | `client.py:92-98` |
| ACK direction | LIS → instrument, after DB commit on success paths | `repository.py` |
| ACK receiving app | **Hardcoded `MINDRAY`** | `client.py:33,41` |
| Supervision | Restarts a **dead thread** only; never inspects sockets, status, or message timing | `supervisor.py` |
| Ordering guarantees | None implemented | — |
| Connection limits | None implemented; one thread per enabled instrument | `supervisor.py` |

### 11.2 Per-instrument validation required

For every instrument intended for concurrent operation:

| Property | Must be established as |
|---|---|
| TCP client/server role | **field-confirmed** — which side initiates? |
| IP address | field-confirmed |
| Port | field-confirmed |
| Protocol | field-confirmed |
| Framing | field-confirmed |
| ACK direction and format | field-confirmed |
| ACK timeout | field-confirmed |
| Reconnect behaviour | field-confirmed |
| Idle-connection behaviour | field-confirmed (does either side drop an idle socket?) |
| Multiple messages per connection | field-confirmed |
| Instrument retry behaviour | field-confirmed |
| Connection limits | field-confirmed (does the instrument accept only one session?) |
| Ordering guarantees | field-confirmed |

**Separation rule.** Every row above is currently *configuration-only* or *assumed* for all instruments except BC-5150.

**BC-5150 status after session 1:**

| Property | Status |
|---|---|
| TCP client/server role — LIS dials out | **field-confirmed** |
| IP `10.0.0.2`, port `5100` | **field-confirmed** |
| Protocol HL7 2.3.1 | **field-confirmed** |
| Framing MLLP `0x0B` … `0x1C 0x0D` | **field-confirmed** |
| Idle `0x02` heartbeat between frames | **field-confirmed** (§5.1 row 22) |
| ACK direction LIS → instrument, `MSA\|AA` accepted end-to-end | **field-confirmed** |
| Multiple messages per connection | *assumed* — buffer path proven in unit tests, not yet on-device (T-BC-S) |
| ACK timeout / ACK dependence / reaction to `AE` | *configuration-only* — `ACK Overtime 10 s`, `ACK Sync OFF` read from the analyzer UI, never exercised (T-BC-T) |
| Instrument retry behaviour | *configuration-only* — `Auto Retransmit OFF`; automatic retry never observed |
| Reconnect behaviour, idle-connection behaviour, connection limits, ordering | **not established** (T-BC-G, T-BC-I, T-BC-R) |

### 11.3 The client-only constraint is a rollout blocker

The LIS can only **dial out**. If any instrument acts solely as a TCP client — i.e. it expects the LIS to listen — that instrument **cannot be connected at all** without implementing listener mode, which `core/config.py` explicitly defers.

This must be determined **before** any parser work for that instrument, because it can invalidate the entire integration approach for it. It is the first question of every T-CONN-01.

### 11.4 The RS-232 group

`docs/08_MASTER_DATA.md` §7 records BX-3010, EasyLyte PLUS and R-300 as RS-232 in the technical reference. That is capability, not actual configuration — but if field inspection confirms serial-only operation, then:

- the current TCP transport cannot reach them at all;
- a serial-to-Ethernet converter, or a serial transport, becomes a **procurement and architecture** decision, not a software task;
- this must be discovered by physical inspection of the instrument's ports and settings, which requires **no software** and can be done in the very first site visit.

**Recommendation:** perform a purely physical port-and-settings survey of all nine instruments before any software field session. It is cheap, requires no integration service, and may reclassify several instruments from P2/P3 to "blocked on hardware".

---

## 12. Evidence Capture Standard

### 12.1 Evidence record

One record per test execution. Suggested filename: `EV-<TESTID>-<YYYYMMDD>-<seq>.md`.

```
TEST ID:            T-BC-K-01
DATE / TIME:        2026-__-__ HH:MM (site local)
OPERATOR:           <initials>
INSTRUMENT:         Mindray BC-5150   (id_instrument=2)
FIRMWARE / VERSION: <as displayed>
NETWORK ENDPOINT:   <ip>:<port>   role: LIS=client / LIS=server
PROTOCOL / FRAMING: HL7 v2.3.1 / MLLP 0x0B..0x1C0D
CLASSIFICATION POLICY IN EFFECT: bc5150_field_verified

OPERATOR ACTION:    <exact button/menu sequence>
INSTRUMENT STATE:   <idle / running / QC mode / error>
SAMPLE CONTEXT:     <synthetic | control material | patient PT-01>

RAW MESSAGE:        <file reference — see 12.4>   sha256: <hash>
MSH-10:             <value>
KEY IDENTITY:       PID-3=<value|EMPTY>  OBR-3=<value>  OBR-7=<value>
OBR FIELDS:         OBR-2/-4/-24 = <values>
OBX IS SEGMENTS:    <identifier=value, ...>          (capture ALL)
OBX NM/ST SAMPLE:   <first few, with units/range/flag>
OBSERVED ACK:       <MSA code + control id, or NONE>  latency: <ms>

EXPECTED RESULT:    <from the test definition>
ACTUAL RESULT:      <what happened>
DB OUTCOME:         parse_status=<> message_class=<> classification_rule=<>
INTERPRETATION:     <what this does and does not prove>
CONFIDENCE:         VERIFIED | CANDIDATE | INCONCLUSIVE
REFERENCES:         <screenshot / pcap file ids>
```

The `INTERPRETATION` field must state what the observation **does not** prove. That discipline is what kept the M8.2b rule narrow and correct.

### 12.2 Minimum repetition

- A **VERIFIED RULE** requires ≥ 2 independent observations, preferably on different days.
- A single observation yields at most a **CANDIDATE RULE**.
- Contradictory observations trigger a stop condition (§14).

### 12.3 Network capture

Run a packet capture for the entire session, filtered to the instrument endpoint. It is the only way to answer framing, connection-reuse, ACK-timing and ordering questions, and it captures messages the application may reject before persisting anything useful. Store the pcap alongside the evidence records.

### 12.4 Raw message preservation

- Preserve every raw frame **byte-exactly**, including control characters, one file per message, named by test id and sequence. Record a SHA-256 for each — this is what makes byte-identity comparisons in §8.3 possible.
- Store the raw corpus in a controlled evidence store **outside the repository** while it may contain real identifiers.
- Commit to the repository only **redacted or synthetic derivatives**, and only once reviewed. These become the M9.4 regression fixtures.
- The application already retains every frame in `instrument_messages.raw_message`, including for failed and unclassified messages — that table is a reliable secondary source for anything the manual capture misses.

---

## 13. Master Field-Test Matrix

Statuses: **NOT STARTED / READY / FIELD TESTED / VERIFIED / BLOCKED / NOT APPLICABLE**.

`READY` means the test can be executed as soon as a session is scheduled. Everything for instruments 3–10 is `BLOCKED` on the physical survey (T-SURVEY-01), because protocol and transport are unknown and no parser exists.

### 13.1 Cross-cutting

| Test ID | Instrument | Scenario | Priority | Status | Evidence required | Dependency | M9.2 | M9.3 | M9.4 | Rollout |
|---|---|---|---|---|---|---|---|---|---|---|
| T-SURVEY-01 | All 9 | Physical port / settings / protocol survey | **P0** | NOT STARTED | Port types, cabling, network settings, protocol menu | Site access only | No | No | No | **Yes** |
| T-CONFIG-01 | BC-5150 | Create `instruments.json` | P0 | **VERIFIED** | Working config file | — | No | No | No | Yes |

### 13.2 BC-5150 (id 2) — P1

| Test ID | Scenario | Priority | Status | Evidence required | Dependency | M9.2 | M9.3 | M9.4 | Rollout |
|---|---|---|---|---|---|---|---|---|---|
| T-BC-A | Normal patient sample | P1 | **FIELD TESTED** (n=1 specimen; needs >=3 distinct patients) | Full message shape, field census | T-CONFIG-01 | No | **Yes** | **Yes** | No |
| T-BC-B | Repeat run | P1 | READY | OBR-3/OBR-7/MSH-10 across reruns | T-BC-A | **Yes** | No | Yes | No |
| T-BC-C | Background manual retransmission | P1 | **VERIFIED** | Both frames compared | T-BC-A | **Yes** | No | Yes | No |
| T-BC-C-P | Patient manual retransmission | P1 | **VERIFIED** | Both frames compared | T-BC-A | **Yes** | No | Yes | No |
| T-BC-D | Retransmission, changed timestamp | P1 | READY | OBR-7 diff | T-BC-C | **Yes** | No | Yes | No |
| T-BC-E | New Message Control ID | P1 | READY | MSH-10 census | T-BC-A | **Yes** | No | Yes | No |
| T-BC-F | Same Message Control ID | P1 | READY | MSH-10 across resend | T-BC-C | **Yes** | No | Yes | No |
| T-BC-G | Disconnect / reconnect | P2 | READY | Instrument-side reaction | T-BC-A | **Yes** | No | No | Yes |
| T-BC-H | Instrument restart | P2 | READY | Startup traffic | Lab schedule | No | **Yes** | No | Yes |
| T-BC-I | Buffered / offline results | P2 | READY | Late arrival, timestamp skew | T-BC-G | **Yes** | No | No | Yes |
| T-BC-J | Background | P1 | **VERIFIED** (re-confirmed live, session 1) | Raw frame on current firmware | — | No | **Yes** | Yes | No |
| T-BC-K | QC / control | **P1** | READY | Raw frame, all OBX IS | Lab QC schedule | No | **Yes** | Yes | No |
| T-BC-L | Calibration | P2 | READY | Raw frame | Lab policy | No | **Yes** | Yes | No |
| T-BC-M | Maintenance | P3 | READY | Raw frame or explicit "none" | Lab policy | No | Yes | No | No |
| T-BC-N | Control material | P2 | READY | Raw frame | Lab policy | No | **Yes** | Yes | No |
| T-BC-O | Missing patient identifier | P1 | READY | PID-3 empty in routine use | T-BC-A | No | No | Yes | **Yes** |
| T-BC-P | Missing specimen identifier | P3 | READY | OBR-3 empty (if producible) | — | No | No | Yes | Yes |
| T-BC-Q | Unexpected / empty fields | P2 | READY | Field-population census | T-BC-A | No | Yes | **Yes** | No |
| T-BC-R | Message sequencing | P2 | READY | Arrival vs OBR-7 order | T-BC-A | **Yes** | No | No | Yes |
| T-BC-S | Multiple messages per connection | P2 | READY | pcap frame boundaries | T-BC-A | No | No | No | **Yes** |
| T-BC-T | ACK / retry behaviour | P1 | READY | ACK dependence and timeout | T-BC-A | Yes | No | No | **Yes** |
| T-ID-02 | **Specimen counter reset** | **P1** | READY | OBR-3 across days / power cycles | T-BC-A, multi-day | **Yes** | No | Yes | **Yes** |

### 13.3 Instruments 3–10

Every instrument below carries the same initial test set. Until T-SURVEY-01 and T-CONN-01 complete, no protocol-level test is meaningful.

| Test ID | Instrument | Scenario | Priority | Status | Evidence required | M9.2 | M9.3 | M9.4 | Rollout |
|---|---|---|---|---|---|---|---|---|---|
| T-CONN-01-03 | Sysmex XN-550 | Role / IP / port / protocol / framing | P2 | BLOCKED (T-SURVEY-01) | Endpoint + protocol confirmation | No | No | No | **Yes** |
| T-CORPUS-01-03 | Sysmex XN-550 | Raw message corpus | P2 | BLOCKED (T-CONN-01-03) | ≥20 raw messages across categories | Yes | Yes | Yes | **Yes** |
| T-CONN-01-04 | Mindray BS-200E | Role / IP / port / protocol / framing | P2 | BLOCKED | As above | No | No | No | **Yes** |
| T-CORPUS-01-04 | Mindray BS-200E | Raw message corpus | P2 | BLOCKED | As above | Yes | Yes | Yes | **Yes** |
| T-CONN-01-06 | ichroma II | Role / IP / port / protocol / framing | P3 | BLOCKED | As above | No | No | No | **Yes** |
| T-CORPUS-01-06 | ichroma II | Raw message corpus | P3 | BLOCKED | As above | Yes | Yes | Yes | **Yes** |
| T-CONN-01-09 | Insight Expert U120 | Role / IP / port / protocol / framing | P3 | BLOCKED | As above | No | No | No | **Yes** |
| T-CORPUS-01-09 | Insight Expert U120 | Raw message corpus | P3 | BLOCKED | As above | Yes | Yes | Yes | **Yes** |
| T-CONN-01-05 | Sysmex BX-3010 | Physical interface determination | P4 | BLOCKED | Port type; serial settings if applicable | No | No | No | **Yes** |
| T-CONN-01-07 | Medica EasyLyte PLUS | Physical interface determination | P4 | BLOCKED | As above | No | No | No | **Yes** |
| T-CONN-01-08 | DFI R-300 | Physical interface determination | P4 | BLOCKED | As above | No | No | No | **Yes** |
| T-ID-01-10 | Precil 106-AC-… | **Establish instrument identity** | P5 | BLOCKED | Nameplate, model, vendor documentation | No | No | No | **Yes** |

---

## 14. Stop Conditions

Engineering **must stop and gather more field evidence** when any of the following occurs. Each is grounded in a specific repository or business risk, not hypothesised.

| # | Condition | Why it stops work |
|---|---|---|
| **S1** | **Two different specimens observed sharing one OBR-3** | `no_registrasi` is derived from OBR-3 and keys the Visit. Collision attaches a specimen to the wrong patient's Visit — a clinical safety issue. Stop all ingestion work for that instrument (§10.2) |
| **S2** | **OBR-7 observed changing across a retransmission** | The M8.2 exact-retransmission key is invalidated; duplicate `TestRun` rows will be created. Stop M9.2 design until the substitute key is evidence-backed (§8.1). **Session 1: did NOT trigger** for manual retransmission — OBR-7 was invariant. Remains live for reconnect-, timeout- and automatic-resend paths, which are untested |
| **S3** | **MSH-10 observed to be non-unique in a way that conflicts with S2's finding** | Contradictory identity signals mean no safe dedup key exists yet. Stop and widen the capture set. **Session 1: MSH-10 was observed to repeat across separate messages, but this does not conflict with S2** — OBR-7 held, so the existing key is unaffected. The finding removes MSH-10 as a *sole* key candidate rather than creating a contradiction. No stop |
| **S4** | **A QC / calibration message observed that is structurally indistinguishable from a patient result** | No fail-closed rule can separate them; encoding one would risk either releasing QC as clinical data or quarantining real results. Stop M9.3 for that instrument |
| **S5** | **PID-3 observed to be inconsistently populated for genuine patient work** | The synthetic-patient path would fire during routine use, creating specimen-keyed patients in production (§10.2). Stop production ingestion enablement. **Session 1 raises this from hypothetical to likely:** PID-3 was `^^^^MR` — components empty — in the patient frame as well as Background, so on current evidence the synthetic path would fire for *every* message. Enabling `PATIENT_RESULT` is blocked until T-BC-O / Q8 resolve this |
| **S6** | **The instrument does not accept, or actively rejects, the current ACK** | The ACK's receiving application is hardcoded `MINDRAY`. If any instrument requires a correct value, ingestion is unreliable. Stop rollout for that instrument |
| **S7** | **An instrument requires the LIS to listen (server mode)** | Unsupported by `SUPPORTED_INSTRUMENT_MODES`. Stop; this is an architecture decision, not a configuration change (§11.3) |
| **S8** | **An instrument is confirmed serial-only** | Out of reach of the current transport. Stop software work; escalate to procurement/architecture (§11.4) |
| **S9** | **Observed protocol contradicts `docs/08_MASTER_DATA.md` §7 technical reference** | The reference is capability, not configuration. Trust the field, record the contradiction, and stop before writing any parser against the reference |
| **S10** | **Two field sessions produce conflicting observations of the same behaviour** | Never average or pick one. Stop, and design a discriminating test |
| **S11** | **Undocumented vendor behaviour appears** (unexpected segment, non-standard framing, unsolicited traffic) | Stop; capture exhaustively before interpreting |
| **S12** | **A rule is about to be implemented from a single observation** | Violates §9.3. Stop and obtain a second independent capture |

---

## 15. M9 Dependency Mapping

Verified against the actual M9 task list (`docs/07_TASK_LIST.md` lines 524–566) and the repository.

| M9 item | Evidence prerequisite | Can proceed independently? | Verdict |
|---|---|---|---|
| **M9.1 — Authentication / RBAC** | None. JWT, roles (Analyst / Administrator), endpoint protection and action protection are entirely internal to the API and frontend; no instrument behaviour is involved | **Yes — fully** | **PROCEED NOW** |
| **M9.2 — Message Deduplication Refinement** | T-BC-B, D, E, F, I, R, T-ID-02. Session 1 showed the existing key `(instrument, prefix+OBR-3, OBR-7)` **survives manual retransmission**, and that **MSH-10 is unsafe as a sole key** (§8.5). Repeat-run, reconnect-resend and timeout-resend behaviour remain unobserved | **Partially** — the evidence base has started | **STILL BLOCKED**, but materially narrowed |
| **M9.3 — QC / Calibration Filtering Refinement** | T-BC-K/L/M/N, T-BC-H. `Background` is now re-confirmed live; every other category still has **zero captures**. The separate positive-patient decision is **NOT APPROVED** (§9.5) and additionally gated by §9.6 | **No** | **BLOCKED on field evidence** |
| **M9.4 — Test suite** | **Split.** Backend unit tests, API integration tests, DB constraint tests and frontend component tests need no instrument evidence — the current suite (**165 passing** as of `19d333e`, including 31 new MLLP framing tests) already covers parser, ingestion, supervisor, config, identity, overview and transport framing. **Instrument-behaviour regression fixtures** need a real captured corpus (§12.4) | **Partially — the majority can proceed** | **PROCEED with the non-fixture portion** |
| **M9.5 — Production hardening** | **Split.** Structured logging (replacing the `print` calls in `client.py` / `instruments.py`), connection pooling, CORS restriction, error-handling standardisation and input validation are all internal. **ACK-timeout and reconnect-interval tuning** need T-BC-T and T-BC-G, since the 5 s reconnect and 5 s connect timeout are currently unvalidated constants | **Mostly** | **PROCEED with the non-timing portion** |
| **M9.6 — UI Auto-Refresh** | None. Polling/refresh over the existing M8.4 API with race-safety during mutations is a frontend concern | **Yes — fully** | **PROCEED NOW** |
| *Specimen identity work (§10)* | T-BC-A, T-BC-O, T-ID-02. Not a numbered M9 item, but a prerequisite for production multi-instrument ingestion | **No** | **BLOCKED on field evidence** |

**Conclusion: M9 is not globally blocked.** M9.1 and M9.6 are fully unblocked, and the larger parts of M9.4 and M9.5 are unblocked. Only M9.2, M9.3 and the specimen-identity work genuinely require a lab session.

---

## 16. Recommended Execution Order

Adjusted from the generic sequence to reflect what the repository actually shows — notably that no `instruments.json` exists, that eight instruments have no parser, and that the RS-232 group may be blocked on hardware.

| Step | Action | Why here |
|---|---|---|
| **0** | **Start M9.1 and M9.6 immediately, in parallel with everything below** | Fully unblocked; no reason to serialise them behind a lab visit |
| **1** | **T-SURVEY-01 — physical port/settings survey of all nine instruments** | Needs no software, no config, no service. May immediately reclassify several instruments as hardware-blocked (S8) and reshape the whole plan |
| **2** | ~~Prepare the field environment~~ — **DONE (session 1)** | `instruments.json` created; `lis_marina_permata_dev` confirmed; database brought to Alembic head `4aff9e134f16`; packet capture in place |
| **3** | **BC-5150 session 1 — T-BC-A, J** — **DONE**; **T-BC-C and T-BC-C-P also completed** | Routine shape and the Background rule confirmed live; first successful ingestion and `MSA\|AA`. **T-BC-O, Q, S, T were not completed and roll forward** |
| **4** | **Preserve the raw corpus** (§12.4) — **partially done** | Session-1 frames are retained verbatim in `instrument_messages.raw_message` in the dev database. Promoting redacted derivatives into committed fixtures is still outstanding |
| **5** | **BC-5150 session 2 — T-BC-B, D, E, F, R, plus the rolled-forward T-BC-O, Q, S, T** | The dedup and ACK set. T-BC-B (genuine repeat run) is now the most valuable of these, since manual retransmission is already characterised (§8.5) |
| **6** | **BC-5150 QC set — T-BC-K (×2, different days), L, M, N, H** — **now the top physical priority** | The **only** evidence that can advance §9.5. Must be scheduled against the lab's real QC/calibration calendar (Q1) rather than forced. Pair with **T-BC-A across ≥3 distinct patients** to close the n=1 limitation in §5.6 |
| **7** | **T-ID-02 — specimen counter behaviour across days and a power cycle** | Inherently multi-day; start the observation window early and close it here |
| **8** | Update §5, §13 and §18; label every finding VERIFIED / CANDIDATE / UNKNOWN | The evidence base becomes citable |
| **9** | **Begin M9.2 and M9.3 investigations** using the evidence — algorithm and rule selection, still not implementation | Only now is "where justified" answerable |
| **10** | Convert redacted captures into M9.4 regression fixtures | Closes the M9.4 split from §15 |
| **11** | **Second instrument (XN-550 or BS-200E): T-CONN-01, then T-CORPUS-01** | First test of whether the client-only transport generalises (S7) |
| **12** | Write and register the second parser; extend the registry | Only after a real corpus exists |
| **13** | Repeat 11–12 for remaining TCP-capable instruments; escalate the serial group per S8 | — |
| **14** | Multi-instrument concurrent QA | Requires ≥2 instruments actually connected |

**Sessions 3, 5 and 6 are deliberately separate.** Combining exploratory shape-discovery with deliberate duplicate generation makes it hard to attribute a message to an action — and attribution is the entire value of the evidence record.

---

## 17. Open Questions

Questions for the project owner or lab management. None can be resolved from the repository.

| ID | Question | Why it matters | Owner |
|---|---|---|---|
| **Q1** | Can QC / control material be run on demand for T-BC-K, or only on the lab's QC schedule? | Determines whether the M9.3 blocker clears in days or weeks | Lab management |
| ~~**Q2**~~ | ~~Does the BC-5150 expose a manual resend / reprint function?~~ | **ANSWERED — YES (session 1).** Manual retransmission was performed for both a Background run and a patient sample, and is the basis of §8.5 | *Closed* |
| **Q3** | Is withholding an ACK (T-BC-T) acceptable on a production instrument? | If not, ACK-timeout behaviour stays UNKNOWN and M9.5 timing constants stay unvalidated | Lab management |
| **Q4** | Does the BC-5150 sample counter reset daily, on power cycle, or at rollover? | **The single highest-risk unknown** (S1). May be answerable from vendor documentation without a multi-day observation | Vendor docs / lab |
| **Q5** | Which of the nine instruments are actually in routine clinical use today? | Priorities in §6.2 assume all are in scope; clinical throughput should outrank protocol convenience | Lab management |
| **Q6** | Is the Precil unit's true model identifiable from its nameplate? | Identity precedes protocol; it may not be integrable at all | Lab / vendor |
| **Q7** | Is a serial-to-Ethernet converter budgeted for the RS-232 group? | Determines whether P4 instruments are a software or procurement question (S8) | Project owner |
| **Q8** | For a BC-5150 patient sample, what populates PID-3 — barcode, host worklist, or manual entry? | Determines whether the synthetic-patient path fires in routine use (S5) | Lab workflow |
| **Q9** | Is `unverified_passthrough` acceptable for BC-5150 in the interim, or must patient ingestion wait for a positive evidence-based rule? | Under `bc5150_field_verified` no patient result reaches clinical persistence (§9.4). **Session 1 sharpens this:** §9.6 shows that enabling patient ingestion today would also route every message through the synthetic-patient path with the specimen counter as the Visit key. The interim option therefore carries **two** risks, not one | Project owner |
| **Q10** | Can a QC / control run be labelled by the operator in a way that reaches **PID-5**? | Decides candidate "PID-5 populated" in §9.5. If QC carries an operator label in PID-5, that candidate is falsified outright | Lab workflow / vendor docs |
| **Q11** | Does a QC run carry OBX `IS` metadata (Take / Blood / Test Mode)? | Decides the `IS`-metadata candidate in §9.5. Answerable in the same capture as Q10 | Observable in T-BC-K |
| **Q12** | Does a QC run reuse the numeric sample counter that patient samples use? | Decides the "OBR-3 numeric" candidate in §9.5 | Observable in T-BC-K |

---

## 18. Validation Completion Record

Append one row per completed test. This table is the project's authoritative record of what has actually been observed.

| Test ID | Instrument | Date | Operator | Outcome | Confidence | Evidence ref | Notes |
|---|---|---|---|---|---|---|---|
| *(M8.2b)* | Mindray BC-5150 | pre-2026-09 | — | OBR-3 `Background` → NON_PATIENT | **VERIFIED** | `test_ingestion.py` §K fixtures; physical UI screenshots | Field-shaped fixtures only; **no verbatim raw corpus preserved** |
| *(M8.2b)* | Mindray BC-5150 | pre-2026-09 | — | Patient samples 28/29/30/31 observed with PID metadata and numeric results | **VERIFIED** | `test_ingestion.py` §K | Not sufficient to positively classify as PATIENT_RESULT |
| *(M8.1)* | Mindray BC-5150 | pre-2026-09 | — | HL7 over TCP/IP; IP reported 10.0.0.2 | **VERIFIED** | `docs/08_MASTER_DATA.md` §5 "Field-Confirmed" | Port not recorded at that time; now confirmed as 5100 (§4.3) |
| **T-CONFIG-01** | Mindray BC-5150 | 2026-09-09 | — | `instruments.json` created; identity resolved to `id_instrument=2` | **VERIFIED** | §4.1, §4.3 | Differs from the tracked example in `host` only |
| **T-CONN-01** | Mindray BC-5150 | 2026-09-09 | — | LIS `10.0.0.10` → analyzer `10.0.0.2:5100`, **LIS is TCP client**; HL7 2.3.1 over MLLP | **VERIFIED** | §4.3, §5.5; packet capture | Direct P2P Ethernet; no production network |
| **T-FRAME-01** | Mindray BC-5150 | 2026-09-09 | — | MLLP `0x0B` … `0x1C 0x0D` confirmed; **instrument emits single-byte `0x02` while idle** | **VERIFIED** | §5.1 row 22; live rows with 2–9 leading `0x02`; fix `19d333e` | Regression found and fixed; 31 framing tests, 165 backend tests pass; 4 real failed frames replayed and recovered |
| **T-BC-A** | Mindray BC-5150 | 2026-09-09 | — | Normal patient shape: PID-3 `^^^^MR`, PID-5 populated, OBR-3 numeric (`42`), OBR-7 populated, clinical OBX and 4 `IS` entries present | **VERIFIED (shape)** / **INSUFFICIENT (diversity)** | §5.5, §9.5 | **n = 1 distinct specimen.** Not a basis for a positive rule |
| **T-BC-J** | Mindray BC-5150 | 2026-09-09 | — | Background: OBR-3 `Background`, PID-5 absent, **clinical-style NM OBX present**, **no `IS` metadata** | **VERIFIED** | §5.5; `NON_PATIENT` / `OBR3_BACKGROUND` rows | Re-confirms the M8.2b rule on the physical device |
| **T-BC-C** | Mindray BC-5150 | 2026-09-09 | — | Background manual retransmission: MSH-7 and MSH-10 change; OBR-3, OBR-7 and payload invariant | **VERIFIED** | §8.5 | Operator-initiated only; `Auto Retransmit` was OFF |
| **T-BC-C-P** | Mindray BC-5150 | 2026-09-09 | — | Patient manual retransmission: MSH-7 and MSH-10 change; PID-3, PID-5, OBR-3, OBR-7 and clinical payload invariant | **VERIFIED** | §8.5 | Same scope limitation as T-BC-C |
| **(live ingestion)** | Mindray BC-5150 | 2026-09-09 | — | First successful live ingestion + `MSA\|AA`; `id_message=152`, `parse_status=Success`, `message_class=UNCLASSIFIED`, `classification_rule=BC5150_BACKGROUND_ONLY` | **VERIFIED** | §5.5 | Dev DB only. Patient messages create **no** clinical rows under the fail-closed policy |
| **(MSH-10 census)** | Mindray BC-5150 | 2026-09-09 | — | **MSH-10 values repeat across separate messages**; MSH-10 changes on retransmission | **VERIFIED (strong observation, not a universal guarantee)** | §8.5 | Removes MSH-10 as a *sole* dedup key candidate |

### 18.1 Verified-rule register

The authoritative list of rules the project has earned the right to implement. Adding a row requires ≥2 independent captures (§9.2) and a completed evidence record.

| Rule | Instrument | Scope | Status | Encoded in |
|---|---|---|---|---|
| OBR-3 (stripped, casefolded) `== "background"` → `NON_PATIENT` | Mindray BC-5150 **only** | Background runs | **VERIFIED** — 27 consistent historical captures (§5.7) plus 2 live session-1 captures, no counter-example | `classification._bc5150_field_verified` |
| *(none yet)* | — | QC | **UNKNOWN — zero captures** | — |
| *(none yet)* | — | Calibration | **UNKNOWN — zero captures** | — |
| *(none yet)* | — | Maintenance | **UNKNOWN — zero captures** | — |
| *(none yet)* | — | Control material | **UNKNOWN — zero captures** | — |
| *(none yet)* | Mindray BC-5150 | **Positive patient identification** | **NOT APPROVED** — candidates assessed in §9.5; one candidate (presence of clinical OBX) is **falsified**. Additionally gated by §9.6 | — |
| *(none yet)* | Any instrument other than BC-5150 | All categories | **UNKNOWN** | — |

**Non-classification facts earned in session 1** — recorded here so they are not mistaken for classification rules:

| Fact | Instrument | Status | Bears on |
|---|---|---|---|
| LIS is the TCP client; endpoint `10.0.0.2:5100`; HL7 2.3.1 over MLLP | BC-5150 | **VERIFIED** | §11, rollout |
| Instrument emits single-byte `0x02` while idle; framing must anchor on `0x0B` | BC-5150 | **VERIFIED** | Transport (`19d333e`) |
| Manual retransmission: MSH-7 and MSH-10 change; OBR-3, OBR-7 and payload invariant | BC-5150 | **VERIFIED** (manual resend only) | **M9.2 only** — not a classification signal |
| MSH-10 repeats across separate messages | BC-5150 | **VERIFIED** | **M9.2 only** |

> **Do not conflate M9.2 evidence with M9.3 evidence.** Retransmission and MSH-10 findings constrain the *deduplication key*. They say nothing about whether a message is a patient result, and must never be cited in support of a classification rule.

> **This register must never be extended by analogy.** A rule verified on the BC-5150 applies to the BC-5150. A second Mindray instrument (BS-200E) requires its own evidence, even for the same vendor and the same nominal protocol.

---

*This document plans and records physical validation. It authorises no source, schema, migration, test or task-list change. No source code was modified in producing it.*
