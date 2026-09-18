# Boditech ichroma™ II — Field-Validation Plan

> **FIELD-VALIDATION PLAN — NOT AN IMPLEMENTATION CONTRACT.**
> This document plans **one** controlled laboratory session. It defines no parser, no schema, no transport code, no API and no frontend, and it authorises no implementation. Its only purpose is to turn the secondary, conditional material in [`SURVEY_EVIDENCE.md`](SURVEY_EVIDENCE.md) into primary evidence.

| Item | Value |
|---|---|
| Date written | 2026-09-18 |
| Instrument | Boditech Med Inc. ichroma II, `id_instrument = 6` (`docs/08_MASTER_DATA.md`, `docs/09` §4) |
| Prerequisite reading | [`SURVEY_EVIDENCE.md`](SURVEY_EVIDENCE.md) — in particular §3 (why nothing is VERIFIED) and §10 (minimum work) |
| Methodology reference | `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md`; the Sysmex XN-550 sessions in `docs/instruments/sysmex_xn550/` are the worked example |
| Physical testing performed by this document | **None.** No instrument was contacted. This is preparation only |
| PHI | This plan contains no payload, no patient data and no specimen value. It refers to field *positions* only |

---

## 1. Purpose and evidence classes

The ichroma II currently has **no primary field evidence**. Everything known comes from two HL7 messages transcribed by hand into a research note, with no capture, no hash, no manifest and no operator ground truth (`SURVEY_EVIDENCE.md` §2–§3). One short session closes that gap.

Every observation recorded during the session is assigned exactly one class:

| Class | Meaning |
|---|---|
| **A — PRIMARY OBSERVED** | Captured from the wire in this session, with a capture file, a byte-exact receive log and a SHA-256 |
| **B — OPERATOR-CONFIRMED** | Semantics stated by the laboratory operator, declared **before** the action, and recorded in the ground-truth notes |
| **C — SECONDARY / TRANSCRIPTION** | Everything inherited from the existing research note. Never promoted to A or B without a capture |
| **D — UNRESOLVED / UNKNOWN** | No evidence either way |

A class-C item **never** becomes a fact by repetition. If the session does not capture it, it stays C or D.

Status vocabulary for every matrix in this document is restricted to: **VERIFIED · PARTIALLY VERIFIED · UNKNOWN · NOT OBSERVED.** `PASS`, `FAIL`, `IMPLEMENTED` and `PRODUCTION READY` are not used — this is evidence collection, not acceptance testing.

---

## 2. Current knowledge and gaps (pre-session baseline)

**There are zero VERIFIED rows.** Everything marked PARTIALLY VERIFIED rests on the transcription (class C) and is conditional on that transcription being faithful.

| # | Aspect | Current status | Basis / gap | Test that closes it |
|---|---|---|---|---|
| 1 | Transport direction | PARTIALLY VERIFIED | Instrument appears to dial the LIS; corroborated only by the survey receiver being a listening socket | T-IC-A, T-IC-B |
| 2 | TCP endpoint / IP | UNKNOWN | Note names LIS `172.17.31.201` / instrument `.202`; no capture confirms either was in use | T-IC-A, T-IC-H |
| 3 | TCP port | UNKNOWN | `8000` is a script default and the note calls it an example | T-IC-A, T-IC-H |
| 4 | MLLP framing | PARTIALLY VERIFIED | Both transcribed frames start `0x0B` and end `0x1C 0x0D`; never seen on the wire | T-IC-A |
| 5 | HL7 version | PARTIALLY VERIFIED | `MSH-12 = 2.6` in both transcriptions | T-IC-A |
| 6 | Message type | PARTIALLY VERIFIED | `MSH-9 = OUL^R24^OUL_R24` in both | T-IC-A |
| 7 | Segment order | PARTIALLY VERIFIED | `MSH PID OBR ORC SPM OBX+`; two structures only | T-IC-A, T-IC-D |
| 8 | ACK / NAK behaviour | NOT OBSERVED | The survey receiver never wrote to the socket. Whether an ACK is required, and whether withholding one blocks later messages, is untested | T-IC-C |
| 9 | Message correlation / control ID | PARTIALLY VERIFIED | `MSH-10 = "1"` in **both** messages — constant, so unusable as a correlation key | T-IC-D, T-IC-E |
| 10 | Resend behaviour | UNKNOWN | Never tested | T-IC-E |
| 11 | `MSH-10` behaviour across sends | UNKNOWN | Constant across two messages from different days; behaviour on an actual resend unknown | T-IC-E |
| 12 | Multi-select / bulk behaviour | UNKNOWN | The note claims one connection per patient; narrative only, no connection log | T-IC-D |
| 13 | `PID-2` semantics | UNKNOWN | Holds name-like text, but `PID-2` is HL7 *Patient ID*, not *Patient Name*. Could be an operator free-text label | T-IC-F |
| 14 | `SPM-2` semantics | UNKNOWN | 8–9 character uppercase code; the trailing `SPM` field carries a **2027 date**, so this may be a **reagent-cartridge lot**, not a specimen ID | T-IC-F |
| 15 | Patient-result semantics | UNKNOWN | `OBX-2 = TX` on numeric values; `OBX-11 = R` ("not verified"); `OBX-8 = 0`, not an HL7 table 0078 flag | T-IC-A, T-IC-F |
| 16 | QC traffic | NOT OBSERVED | Zero captures | T-IC-G |
| 17 | Calibration traffic | NOT OBSERVED | Zero captures | T-IC-G |
| 18 | Maintenance traffic | NOT OBSERVED | Zero captures | T-IC-G |
| 19 | Startup / status traffic | NOT OBSERVED | Zero captures | T-IC-G |
| 20 | Reconnect behaviour | UNKNOWN | Never observed | T-IC-A (opportunistic) |
| 21 | TCP segmentation / coalescing | UNKNOWN | Both transcriptions are whole frames, implying one `recv()` each; two samples prove nothing general | T-IC-A, T-IC-D |
| 22 | Idle behaviour | UNKNOWN | No keepalive, heartbeat or idle-timeout observation exists | T-IC-A |
| 23 | Query / pull behaviour | UNKNOWN | `ichroma_client.py` exists but no result survives | T-IC-B |

Two further items are **documentation** gaps rather than instrument gaps:

- `docs/08_MASTER_DATA.md` records the ichroma II protocol as **ASTM**, which contradicts the HL7/MLLP evidence. Correct it only once T-IC-A produces a capture (`SURVEY_EVIDENCE.md` §13).
- `docs/09` row 6 and `T-CONN-01-06` / `T-CORPUS-01-06` remain **BLOCKED**; T-IC-A and T-IC-D are what unblock them.

---

## 3. Session tests

Eight tests. T-IC-A, B, D, E and F are the core and fit one session; G and H are opportunistic and configuration work.

### T-IC-A — Raw capture and provenance

**Goal.** Capture exact payload bytes with enough provenance to be class A.

**Precondition.** Packet capture running on the LIS PC before the listener starts. Byte-exact receive logging enabled. Ground-truth notes open. Tool selftest completed and recorded.

**Action.** Start the LIS-side listener, have the operator send one result, let the connection close naturally.

**Record, per connection and per message:** date and time (LIS clock); LIS hostname and IP; instrument IP; TCP port; connection direction; source and destination endpoints including ephemeral port; TCP session identifier if the tooling provides one; the raw payload bytes exactly as received; message boundaries **as observed** (not as assumed); SHA-256 of every artifact; file size; capture filename.

**Preserve the primary capture byte-exactly.** Do not redact, re-encode, pretty-print or normalise it in place. Sanitisation happens only in a separate derived copy.

**Also note, if they occur naturally:** idle time before the connection closes, any keepalive, and any reconnect. These are opportunistic — do not provoke them.

### T-IC-B — Reverse-direction probe

**Goal.** Establish which endpoint initiates TCP and whether communication is one-way or bidirectional.

**Action.** With capture running, attempt a connection from the LIS to the instrument's configured communication port, using only the intended LIS↔instrument communication path. Record the outcome exactly: accepted, refused (RST), or silently dropped (no SYN-ACK, no RST). The last is the XN-550 "S7" outcome and would make listener mode mandatory here too.

**Prohibited.** No port scanning. No probing of any other port. No arbitrary or crafted payloads. One attempt on the configured port only.

### T-IC-C — ACK / NAK requirement

**Goal.** Determine whether an application-layer acknowledgement is required, without assuming HL7 defaults.

**Action, in order.** (1) Receive at least three consecutive messages while sending **no** ACK, and record whether every message still arrives. (2) If laboratory procedure permits, repeat while sending a standard MLLP ACK, and record any difference in behaviour or timing.

**Prohibited.** Do not deliberately inject a NAK. Record NAK behaviour only if it occurs naturally. **Do not infer ACK requirements from the HL7 standard** — the finding is whatever the wire shows.

### T-IC-D — Bulk / multi-select

**Goal.** Establish the session model, which determines the whole ingestion shape.

**Action.** With the operator selecting a safe group of at least three existing results, trigger one send.

**Record.** Whether one operator action produces one message or several; whether each message opens its own TCP connection or shares one; message order relative to selection order; timing between messages and between connections; and whether any **unselected** record was transmitted. Preserve every raw message separately.

### T-IC-E — Resend and `MSH-10`

**Goal.** Establish whether a repeat transmission is distinguishable from the original.

**Precondition.** Only if the instrument workflow supports re-sending a stored result safely.

**Action.** Send the same stored result twice.

**Compare.** Raw bytes (byte-identical or not); `MSH-10`; `MSH-7` and `OBR-7`; segment structure; result content; and any other field that changes. Note explicitly whether **anything** distinguishes the two.

**Do not infer deduplication semantics from a single observation.** One resend establishes one data point; it does not establish a rule.

### T-IC-F — Identity semantics

**Goal.** Replace positional inference with operator-confirmed meaning. This is the highest-value test in the session.

**Action.** Before sending, the operator declares in writing what they entered and where: the patient-facing label, any sample or accession number, the reagent cartridge lot, and the operator ID. Then send, and match the declared values against the received fields.

**Confirm specifically:** what `PID-2` actually contains and who types it; whether `SPM-2` is a **specimen identifier or a reagent-cartridge lot**; what the trailing `SPM` date field means; what `OBR-2`, `OBR-4` and the constant token in `MSH-5` / `ORC-18` represent.

**Do not conclude that a field is a specimen identifier because its value looks like one.** Record the operator's exact words and who said them.

### T-IC-G — Non-patient categories

**Goal.** Observe QC, calibration, maintenance and startup/status traffic **if they arise naturally** in the laboratory's normal workflow during the session window.

**Prohibited.** Do not force, simulate or provoke any instrument operation to generate these categories. Do not alter instrument state for evidence.

If a category does not occur, record it as **NOT OBSERVED**. That is a valid and expected result.

### T-IC-H — Configuration provenance

**Goal.** Record the *configured* label, separately from observed behaviour.

**Action.** With laboratory permission, document the instrument's communication configuration: protocol setting, port, IP configuration, communication mode, and any LIS-side settings. Photograph the configuration screens if permitted.

**Keep these apart.** Configuration evidence says what the instrument was *told* to do; capture evidence says what it *did*. Where they disagree, both are recorded and neither is discarded.

---

## 4. Evidence capture structure

Primary evidence stays **outside the repository**, mirroring the XN-550 layout already in use:

```
D:\SurveyLIS\evidence\<YYYY-MM-DD>\ichroma2\
    GROUND_TRUTH_operator_notes.md          operator declarations, made BEFORE each action
    session_<YYYY-MM-DD>_ichroma2_run<NN>.pcapng
    selftest\
        selftest_conn99_rx.bin
        selftest_conn99_events.jsonl
        selftest_manifest.jsonl
    run<NN>_<testid>\
        <testid>_run<NN>_conn<NN>_rx.bin            byte-exact receive log
        <testid>_run<NN>_conn<NN>_events.jsonl      connection/timing events
        <testid>_run<NN>_conn<NN>_msg<NN>.hl7       one extracted message, bytes preserved
        <testid>_run<NN>_manifest.jsonl             one line per message
        <testid>_run<NN>_final_hashes.sha256        SHA-256 of every file above
        CONFIG_<subject>.md | .png                  T-IC-H only
```

Example: `run01_tica\tica_run01_conn01_msg01.hl7`.

The name encodes test ID, run, connection and sequence; the parent directories encode date and instrument. Direction is recorded as `inbound` (instrument → LIS) or `outbound` (LIS → instrument) in the manifest, and in the filename only where a test produces both.

**Manifest fields (one JSON object per message):** test id, run, connection, message index, direction, received-at (LIS clock), source and destination endpoint, byte length, SHA-256, MLLP frame complete (true/false), segment count, segment order, and a free-text note. **No patient identifier, specimen value or result value goes in the manifest** — structure only.

**Naming and path rules.** No patient name, sample number, accession, specimen code or result value may appear in any filename or directory name, in either the external tree or the repository. Sequence numbers only.

**What may enter the repository.** Nothing from the primary capture directly. Only a **sanitised or synthetic derivative** may later be committed, and only after explicit approval, following the XN-550 precedent of a redacted committed fixture. The primary capture and the ground-truth notes remain in `D:\SurveyLIS`.

---

## 5. Validation matrix

To be completed **during** the session. Status is restricted to VERIFIED · PARTIALLY VERIFIED · UNKNOWN · NOT OBSERVED.

| Test ID | Purpose | Precondition | Action | Expected observation | Actual observation | Evidence file | SHA-256 | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| T-IC-A | Primary raw capture with provenance | Capture + byte-exact logging running; selftest recorded | Operator sends one result | An inbound TCP connection carrying one MLLP-framed HL7 message | | | | | |
| T-IC-B | Which endpoint initiates; one-way or two-way | Capture running | One LIS→instrument connection attempt on the configured port | Accepted, refused, or silently dropped — record which | | | | | |
| T-IC-C | Is an application ACK required | ≥3 messages available to send | Receive 3 messages with no ACK; then, if permitted, with ACK | Whether all messages still arrive when no ACK is sent | | | | | |
| T-IC-D | Session model for bulk send | ≥3 existing results selectable | One operator send of a multi-result selection | Message count, connection count, order, timing, no unselected records | | | | | |
| T-IC-E | Is a resend distinguishable | Workflow permits safe re-send | Send the same stored result twice | Whether bytes, `MSH-10` or any field differ | | | | | |
| T-IC-F | Operator-confirmed identity semantics | Operator declares entries in writing first | Send after declaration; match declared values to fields | What `PID-2` and `SPM-2` actually are | | | | | |
| T-IC-G | Non-patient categories | Occur naturally only | Observe QC / calibration / maintenance / startup if they arise | Category messages, or none | | | | | |
| T-IC-H | Configuration provenance | Laboratory permission | Read and photograph the communication configuration | Configured protocol, port, IP, mode | | | | | |

---

## 6. Session rules

- **Every observation carries its class (A/B/C/D) and its evidence file.** An observation without an artifact is a note, not evidence.
- **Ground truth is declared before the action, never reconstructed afterwards.**
- **Do not normalise the primary capture.** Sanitise only in a derived copy.
- **Do not port scan, craft payloads, inject NAKs, or alter instrument state for evidence.**
- **Do not generalise from the XN-550.** Different vendor, different protocol family, different message type. No XN-550 finding transfers.
- **Do not promote a class-C transcription to a fact** because the session "confirmed the general shape". Each item needs its own capture.
- **NOT OBSERVED is a valid result** and must be recorded as such rather than left blank or filled by inference.
- If the session cannot be completed safely, stop and record what was and was not captured. A partial session with honest labels is worth more than a complete one with inferred entries.

---

## 7. What would make this session sufficient

The ichroma II becomes ready for an implementation contract when, at minimum:

1. **T-IC-A** yields at least one class-A capture with pcapng, byte-exact receive log, manifest and SHA-256 — converting rows 1 and 4–7 of §2 to VERIFIED;
2. **T-IC-B** settles transport direction and whether listener mode is mandatory;
3. **T-IC-C** settles whether an ACK is required — the open data-loss risk;
4. **T-IC-D** settles the session model;
5. **T-IC-F** yields operator-confirmed meanings for `PID-2` and `SPM-2`.

T-IC-E, G and H strengthen the record but do not block a contract. QC, calibration and maintenance remaining NOT OBSERVED constrains the *scope* of any future contract; it does not prevent one, exactly as with the XN-550.

---

## 8. What this plan is not

It is not an implementation contract, not a design, and not authorisation to write a parser, a listener, a simulator, a migration, an API or a frontend. It makes no claim that any instrument has been connected or tested. The protocol of the ichroma II is **not** established by this document — it remains what `SURVEY_EVIDENCE.md` says it is, which is unconfirmed.

**Evidence first. Contract second. Implementation third.**
