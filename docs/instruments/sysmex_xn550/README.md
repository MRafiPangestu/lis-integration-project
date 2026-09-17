# Sysmex XN-550 — Engineering Summary

**Status: field-verified reference instrument. No production integration exists.**

This is the developer-facing summary of what the XN-550 has been *observed* to do. The full survey record, including the parts that are superseded, is in [`FIELD_REPORT.md`](FIELD_REPORT.md).

Evidence labels follow `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md` §2 and are never collapsed: **VERIFIED** (observed on the physical instrument) · **REPO-CONFIRMED** (read from this repository's source — says what the software does, not what the instrument does) · **NOT FIELD-VERIFIED** · **UNKNOWN / NOT CONFIRMED**.

---

## 1. Overview

On **15 September 2026** a Sysmex XN-550 was physically connected to a survey PC over Ethernet, configured for ASTM output, and observed to transmit a complete patient-result message. One message was captured and is committed here as a redacted test fixture.

A **second session on 16 September 2026** performed structured physical validation with full packet capture and a byte-exact listener — see [`VALIDATION_2026-09-16.md`](VALIDATION_2026-09-16.md). It captured 7 messages (4 distinct payloads), settled the transport-role and framing questions for this configuration, and confirmed the `O`-4 identifier mapping against ground truth declared *before* transmission. **It closed no milestone and no release gate:** M9.2 and M9.3b are BC-5150-scoped and untouched, and `T-CORPUS-01-03` remains unsatisfied.

A **third session on 17 September 2026** — see [`VALIDATION_2026-09-17.md`](VALIDATION_2026-09-17.md) — used ground truth declared before every action. It showed that a same-day manual retransmission is byte-identical, recorded a same-patient / different-sequence observation (**not** a rerun), found a cross-day 4-byte difference in an image-path folder date, and observed a reconnect after a physical link interruption (**PARTIALLY VERIFIED**, cause confounded). It also corrected two statements in the 16 September record. After a break the same day, **Run03** added 8 controlled corpus messages, bringing the corpus to **20 messages / 16 distinct payloads / 10 structures** — the `T-CORPUS-01-03` message count is **met**, but the category criterion is **not** (patient results only). Again, no milestone or gate was closed.

This establishes the XN-550 as the **second instrument in this project with any field evidence at all** (after the Mindray BC-5150), and it answers the first question `docs/09` §11.3 says must be answered before parser work: *which side initiates the connection?*

**What this does not do:** it does not make the XN-550 integrable today. There is no XN-550 parser, no configuration entry, and — most consequentially — the observed transport direction is the opposite of what the current LIS supports. See §6.

---

## 2. Instrument identity

| Property | Value | Evidence |
|---|---|---|
| Manufacturer / model | Sysmex XN-550 | **VERIFIED** |
| Family | XN-L | **VERIFIED** |
| Discipline | Haematology | **VERIFIED** |
| `id_instrument` in this repository | **3** | **REPO-CONFIRMED** — `docs/08_MASTER_DATA.md`, `docs/09` §4 |
| Identifiers seen in the `H` record | `XN-550^00-29^41122^^^^BD634545` | **VERIFIED** — exact meaning of each component **UNKNOWN** |
| Master-data status before this survey | "Research Baseline", protocol `NULL`, transport `NULL` | **REPO-CONFIRMED** |

> `docs/08_MASTER_DATA.md` §6.2 rule still applies: research capability is never written into deployment configuration. This survey upgrades the XN-550 from *research baseline* to *field-evidenced* — it does **not** authorise a configuration entry.

---

## 3. Transport / protocol

| Property | Observed | Evidence |
|---|---|---|
| Transport | TCP/IP over Ethernet | **VERIFIED** |
| **Connection role** | **XN-550 = TCP client; LIS PC = TCP server** | **VERIFIED** |
| Endpoint used in the session | Survey PC `10.0.0.10`, port `5001` | **VERIFIED** — survey values, **not** deployment values |
| Instrument setting applied | IPU Settings → Host Computer → `ASTM1381-95 / ASTM1394-97` | **VERIFIED** |
| Record grammar | ASTM E1394-97 — `H` / `P` / `O` / `C` / `R` / `L` | **VERIFIED** |
| Delimiters | `|` field, `\` repeat, `^` component, `&` escape (declared in `H`-2) | **VERIFIED** |
| Record terminator | `\r` (`0x0D`); no `\n` present | **VERIFIED** |
| ASTM 1381-95 low-level framing | **NOT CONFIRMED** — absent from the recovered artefact, but the artefact passed through a hand-transcription step and no pcap was taken | **UNKNOWN** |
| ICMP ping to the instrument | Fails; ARP presence is the reliable link check | **VERIFIED** |
| Windows inbound firewall rule | Required on the listening PC | **VERIFIED** |

> **The connection role is the headline finding.** `backend/app/core/config.py` sets `SUPPORTED_INSTRUMENT_MODES = {"client"}` — the LIS dials out and cannot listen. `docs/09` §11.3 states that an instrument which expects the LIS to listen *"cannot be connected at all without implementing listener mode."*
>
> **However:** this survey shows the XN-550 *operating* as a client. It does **not** show that the XN-550 *cannot* accept an inbound connection — that was never successfully tested. Do not conclude that listener mode is mandatory until that question is answered (§7, item 1).

---

## 4. Verified capabilities

Each of these was observed on the physical instrument on 15 September 2026:

- **VERIFIED** — TCP/IP connectivity between the XN-550 and the LIS PC.
- **VERIFIED** — XN-550 → LIS transmission, initiated by the instrument.
- **VERIFIED** — ASTM message reception, complete and terminated.
- **VERIFIED** — `H` / `P` / `O` / `R` / `L` record structure observed, plus **`C` (comment) records that the survey report's own legend does not mention**.
- **VERIFIED** — raw patient-result capture: 2 824 bytes, 49 records, 42 `R` records.
- **VERIFIED** — experimental ACK handling: the prototype listener ACKed permissively on receipt and the instrument completed its transmission.
- **VERIFIED** — the instrument's output format is operator-configurable; a legacy fixed-width proprietary format is also reachable from the same device.

> **On "ACK/NACK handling":** the survey report claims the listener handles an ACK/**NACK** handshake. The script sends `ACK` (`0x06`) only and contains **no `NAK` (`0x15`) path**, and it ACKs per TCP chunk rather than per validated ASTM frame. What is verified is *permissive ACK-on-receive*, nothing more. NACK behaviour is **NOT FIELD-VERIFIED**.

---

## 5. Evidence status table

**Three sessions now exist.** Session 1 = the survey of 15 September 2026
([`FIELD_REPORT.md`](FIELD_REPORT.md)). Session 2 = the physical validation of
16 September 2026 ([`VALIDATION_2026-09-16.md`](VALIDATION_2026-09-16.md)). Session 3 =
the controlled validation of 17 September 2026
([`VALIDATION_2026-09-17.md`](VALIDATION_2026-09-17.md)). Each is the authoritative
source for the rows that cite it.

| Item | Status | Note |
|---|---|---|
| TCP/IP connectivity | **VERIFIED** | Sessions 1, 2 and 3 |
| XN-550 → LIS transmission | **VERIFIED** | Instrument-initiated; session 2 recorded the dial pattern (5 SYNs ~508 ms, ~60 s cycle) |
| ASTM message reception | **VERIFIED** | Complete messages, `L|1|N` terminator |
| `H`/`P`/`O`/`R`/`L` structure observed | **VERIFIED** | `C` records also present |
| Raw patient-result capture | **VERIFIED** | Session 1: 1 message. Session 2: 7 messages, 4 distinct payloads. Session 3: 4 messages, 3 distinct payloads (run01) + 8 messages, 8 distinct payloads (Run03). **Cumulative: 20 messages, 16 distinct payloads, 10 distinct structures** |
| Corpus size ≥ 20 (`T-CORPUS-01-03`) | **MET** | 20 messages; 13 from pre-registered controlled actions, 7 not pre-registered (survey / natural observations). The uncontrolled 1 102-byte message is excluded |
| Corpus across categories (`T-CORPUS-01-03`) | **NOT MET** | Patient results only — QC, calibration, maintenance and startup **not observed** |
| Structural range observed | **VERIFIED** (observation) | Run03: 1 860–3 126 bytes, 27–48 `R` records; with and without differential parameters; `R`-7 flags `N`/`H`/`L`/`A`/`W`/blank; `R`-9 = `F`, `R`-11 = `lab`, `R`-6/`R`-8/`R`-12 empty in every capture |
| Experimental ACK handling | **VERIFIED** | ACK-only, permissive, **per socket read** — not per ASTM message |
| ASTM 1381-95 framing in observed payloads | **VERIFIED — absent** *(this configuration only)* | Session 2, pcap + byte census across 7 messages. **Not a claim that the XN-550 never uses E1381** — other output settings untested |
| Instrument's native E1381 handshake semantics | **NOT FIELD-VERIFIED** | Our ACK is application-level only |
| NACK handling | **NOT FIELD-VERIFIED** | No NAK path exists in the tooling; never authorised |
| Whether XN-550 accepts inbound connections **on port 5001** | **VERIFIED — it does not** | Session 2: LIS SYNs silently dropped, no RST. **Scope: port 5001 only** |
| Whether XN-550 accepts inbound on any *other* port | **UNKNOWN / NOT CONFIRMED** | No port scan performed — not authorised, not appropriate |
| Multiple messages per connection | **VERIFIED** | Session 2: 7 messages over one 41-minute session, no reconnect. Session 3: 4 messages over one session |
| Persistent idle session, no heartbeat | **VERIFIED** | Sessions 2 and 3: connection held with 0 bytes exchanged; no TCP keepalive frames captured |
| Transmission/message control identifier field | **VERIFIED — none exists** | `H`-3 (control id) empty in every message; `H`-5 (sender / instrument information) **is** populated. *Corrected in session 3 — previously stated as "`H`-3 … `H`-12 empty"* |
| One selected-result transmit → one message | **VERIFIED** | Session 2 GT-2; session 3 GT-1, Seq 51, Seq 58, Run03 8/8 |
| Same-day manual retransmission | **VERIFIED — byte-identical** | Session 3 GT-1 → GT-2: 0 differing bytes. One controlled pair |
| Day-varying content (image-path folder date) | **VERIFIED — exists at day granularity** | Session 3: Seq 58 vs session-2 message A differ in 4 bytes, the image-path folder date. The folder date equals the capture day even where `R`-13 shows an earlier analysis date. **Meaning UNKNOWN — not established as a transmission date**; whether Seq 58 and message A are the same analysis is a **hypothesis** |
| On-screen Sample No. → `O`-4 component 3 | **VERIFIED** | Session 2 GT-2; session 3 GT-1/GT-2, Seq 51, Seq 58, Run03 8/8 — each against ground truth declared **before** transmission |
| Independent specimen identifier in the message | **VERIFIED — none observed** | Session 3 GT-3A: `O`-3 empty, no patient id, no control id, sequence not sent; `O`-4 is the only identity-like field that differed |
| Lab practice: Sample No. holds a personal name | **CANDIDATE** | One lab, operator-entered free text. See §5.1 and the S1 hazard |
| `R`-13 = analysis time, not transmission time | **VERIFIED** | Session 2 GT-2: ~16½ min. Session 3: ~6.6 h (Seq 68); previous-day analyses (Seq 51, 58) |
| On-screen sequence number transmitted? | **VERIFIED — it is not** | Session 2 GT-2; session 3 Seq 68, 51, 58 and all 8 Run03 messages: appears in no field |
| Exact semantics of the patient identifier field (`P`-5) | **UNKNOWN / NOT CONFIRMED** | Populated in session 1; empty in session 2; in session 3 empty in run01 and populated in 2 of 8 Run03 messages. **Cause of the variation UNKNOWN.** See §5.1 |
| Exact semantics of `O`-3 | **UNKNOWN / NOT CONFIRMED** | Empty in every message observed |
| Genuine rerun behaviour | **NOT FIELD-VERIFIED** | Never performed. Session 3 GT-3A was a same-patient / different-sequence observation, **not** a rerun |
| Pending results sent automatically on connection | **CANDIDATE — not observed** | Session 3: 0 bytes for ~25 min (run01) and ~3 min 20 s (Run03) despite analyst-reported pending results; not a rule |
| Historical host query (LIS → instrument request) | **NOT FIELD-VERIFIED** | Never attempted |
| Historical / cross-day resend behaviour | **NOT FIELD-VERIFIED** | Only a same-day manual retransmission was controlled (row above) |
| Send-all / queue-flush behaviour | **NOT FIELD-VERIFIED** | Never used |
| ACK-timeout retransmission behaviour | **NOT FIELD-VERIFIED** | ACK never withheld |
| Reconnect after disconnect | **PARTIALLY VERIFIED** | Session 3: LIS-side RST → no reconnect in 5 min 16 s; after a physical link interruption the instrument opened a new session (1 SYN, new source port), no payload. **Cause confounded.** Session-2 disconnects were cable/adapter events, not instrument behaviour |
| Instrument-initiated disconnect; idle-socket timeout; connection limits | **NOT FIELD-VERIFIED** | Never observed |
| QC message classification | **NOT FIELD-VERIFIED** | Zero QC captures — **not observed** in any session, including Run03 |
| Calibration classification | **NOT FIELD-VERIFIED** | Zero captures — not observed |
| Maintenance / startup classification | **NOT FIELD-VERIFIED** | Zero captures — not observed |
| Result-value fidelity end to end | **NOT FIELD-VERIFIED** | Never ingested by this system |
| Legacy fixed-width format layout | **UNKNOWN** | Only a truncated sample exists |

### 5.1 Identity semantics — actively contradicted by the capture

The survey report's legend states that `P` carries the patient identity and `O` carries the sample id / tube barcode. **The captured message does not support this:**

- the **patient name is in `O`-4** (instrument specimen id) — not in `P`;
- **`O`-3, the ASTM specimen-id field, is empty**;
- **`P`-5 holds a bare numeric id** whose meaning is unknown (hospital MRN? instrument-local sequence? worklist key?);
- **no barcode or specimen identifier is identifiable anywhere** in the message.
- **the Sample No. is also embedded in the four graphic-reference `R`-4 paths** (`…_<Sample No.>_<type>.PNG`), so those values are PHI in raw evidence (session 3; masked in the committed fixture).

This is the XN-550 equivalent of the identity question `docs/09` §10 raises for the BC-5150, and it is **unresolved**. Any parser that maps these fields is guessing until a corpus with known ground truth exists. Do not let the report's legend stand in for evidence.

---

## 6. Current integration boundary

**REPO-CONFIRMED — nothing about the XN-550 is integrated, and nothing in this import changes that:**

| Layer | State |
|---|---|
| Parser | **None.** `backend/app/integration/parsers/registry.py` contains exactly one entry, `bc5150_hl7`. Resolution is exact-match with no fallback; an unknown `parser_key` raises `ParserNotRegisteredError` at startup |
| ASTM support | **None anywhere in production code.** The ingestion path is HL7 v2.3.1 over MLLP |
| Transport | **Client-only.** `SUPPORTED_INSTRUMENT_MODES = {"client"}`; listener mode is explicitly deferred in `backend/app/core/config.py` |
| Configuration | **No XN-550 entry** in `instruments.example.json`; enabling one today would fail loudly at startup |
| Classification | Policies are BC-5150-specific; no XN-550 policy exists |
| Database | **Unchanged.** No migration, no schema change, no new model was introduced by this import |

**This import adds documentation and one test fixture. It changes no production behaviour.**

> Related repository artefact, for the avoidance of doubt: `docs/09` §4.2 warns that `backend/mesin_simulator.py` emits ASTM-style records labelled `Sysmex_XN-550` and **must never be cited as evidence**. That warning stands. This document — not that script — is the XN-550 evidence record. The two happen to agree that the XN-550 speaks ASTM, which is a coincidence rather than corroboration.

---

## 7. Open verification items

In the order they should be answered. Items 1 and 2 are the ones that can invalidate an integration approach, so they come before any parser work (`docs/09` §11.3).

1. ~~**Can the XN-550 accept an inbound TCP connection?**~~ **Answered for port 5001 by session 2** — it does not; the LIS's SYNs are silently dropped, so **stop condition S7 is met** and listener mode would be a prerequisite for this configuration. **Still open:** whether it accepts inbound on any *other* port. No port scan was performed.
2. ~~**Is ASTM 1381-95 framing present on the wire?**~~ **Answered for this configuration by session 2** — no `STX`/`ETX`/`ENQ`/`EOT`/`ACK`/`NAK`/checksum bytes appear in any observed payload; records are `CR`-terminated. **Still open:** behaviour under other instrument output settings, and the instrument's native E1381 handshake semantics, which our application-level ACK cannot establish.
3. **Identity semantics** — **partly answered.** `O`-4 component 3 is **VERIFIED** as the on-screen *Sample No.* (session 2 GT-2, pre-registered). **Still open:** what `P`-5 holds and why its population differs between sessions; what `O`-3 is intended for; and whether any specimen/tube barcode is transmitted at all. Requires a corpus with known ground truth.
4. **ACK dependence** — what does the instrument do when an ACK is delayed, withheld, or replaced by a NAK? *(Same class of question as BC-5150 T-BC-T, which is gated on lab-management approval to withhold an ACK on a live instrument.)*
5. **Retransmission and resend** — **partly answered:** a same-day manual retransmission is byte-identical (session 3), and a cross-day comparison shows a 4-byte image-path folder-date difference. **Still open:** genuine rerun vs retransmission, cross-day resend as a rule, reconnect resend, ACK-timeout resend. **Feeds M9.2; does not resolve it.**
6. **QC / calibration / maintenance / startup message shapes** — currently zero captures. **Feeds M9.3b; does not resolve it.**
7. **Historical host query** — whether the instrument supports a LIS-initiated request for prior results, and in what dialect. Never attempted.
8. **Message corpus** — `docs/09` T-CORPUS-01-03 requires **≥20 messages across categories**. **Count criterion met:** 20 messages (1 + 7 + 4 + 8), 16 distinct patient-result payloads, 10 distinct structures, plus one uncontrolled message of unknown class. **Category criterion not met:** zero QC / calibration / maintenance / startup captures — this is now the open part of the item (see item 6).
9. **Connection behaviour** — multiple messages per connection is **VERIFIED**; reconnect after a physical link interruption is **PARTIALLY VERIFIED** (cause confounded). **Still open:** instrument-initiated disconnect, idle-socket timeout, connection limits, ordering guarantees.

> **None of the following is solved by this survey, and no document in this directory may be cited as solving it:** host query, historical reconciliation, retransmission semantics, deduplication (M9.2), QC or calibration filtering (M9.3b), specimen identity, or Gateway/reconciliation. Vendor or report *claims* that the instrument supports a capability are **CLAIMED**, never VERIFIED.

---

## 8. Parser contract

A test-only contract pins what the capture structurally **is**, so that a future parser is written against observed evidence rather than against the survey report's prose.

**`backend/tests/test_xn550_astm_contract.py`** — 16 tests, DB-free and analyzer-free, reading only the committed fixture. It imports no ASTM production code, because none exists.

### 8.1 What the contract proves

| Area | Asserted |
|---|---|
| Artefact integrity | Byte length (2 824) and SHA-256 pinned; PHI masks present and intact |
| Line discipline | Bare `CR` terminators, **zero** `LF`, no `CRLF`; final record CR-terminated |
| Record inventory | Exactly `H`×1, `P`×1, `O`×1, `C`×3, `R`×42, `L`×1 — 49 total |
| Record ordering | The exact sequence `H P C O C R×42 C L`; H first, L last, P before O before the first R |
| Control records | All three `C` records survive as `C`, are never counted as `R`, and sit after P, after O, and after the final R |
| Delimiters | `H`-2 declares `\^&`; the repeat `\` is used in `O`-5 (the test-code list), the component `^` in `R`-2, the escape `&` inside graphic result values |
| `R` field layout | All 42 records have the same 13 fields; `R`-1 runs 1..42 contiguously |
| Extraction | Test name (`R`-2 component 5), value (`R`-3), units (`R`-4), abnormal flag (`R`-6), status (`R`-8), timestamp (`R`-12), with spot-checks across all three observed flag states |
| Uniform fields | Every result is final (`F`), same operator id (`lab`), one shared run timestamp parseable as `%Y%m%d%H%M%S` |
| Reference ranges | `R`-5 is empty on **every** result — the instrument supplied none |
| Result shapes | 28 measured · 10 interpretive flags · 4 graphic references — a parser assuming "R record = numeric measurement" mishandles 14 of 42 |
| Fail-closed guard | The registry still holds only `bc5150_hl7`; `xn550_astm`, `sysmex_xn550` and `astm_generic` all raise `ParserNotRegisteredError` |

The contract was mutation-checked: converting one `C` record to an `R` record fails 12 tests, and reintroducing PHI fails 2.

> **`R`-field numbering in this table** follows the contract test's docstrings, which count from the first field *after* the record type — one lower than ASTM numbering. ASTM equivalents: sequence `R`-2, test id `R`-3, value `R`-4, units `R`-5, reference range `R`-6, abnormal flag `R`-7, status `R`-9, operator `R`-11, timestamp `R`-13. The `H`, `P` and `O` numbers above are already ASTM numbering, as are all `R` numbers in the validation records.

### 8.2 What the contract intentionally leaves unresolved

`test_contract_does_not_assert_unverified_semantics` asserts only that `P`-5 and `O`-4 are **populated**, and that **`O`-3 is empty**, never what any of them means. It exists so the absence of a semantic claim is explicit rather than accidental, and so that a future capture carrying a populated `O`-3 registers as new evidence instead of passing unnoticed.

**Deliberately not asserted anywhere:** that `P`-5 is an MRN · that `O`-3 or `O`-4 is a specimen id or barcode · any Patient / Visit / Order mapping · any deduplication or retransmission identity · any QC, calibration or maintenance classification · any wire-level ASTM E1381 framing behaviour. Semantic patient and specimen mapping is **deferred** until a corpus with known ground truth exists (§5.1, §7).

### 8.3 Why no production parser was written

`ParserFn` is typed `Callable[[str], Optional[ParsedHL7]]`, and `ParsedHL7` requires `ParsedPatient.nomor_rm`, `ParsedPatient.nama_lengkap` and `ParsedOrder.specimen_no`. **Populating those from this message would require asserting exactly the identity semantics §5.1 records as UNKNOWN.** Writing one today would therefore encode a guess into production code, and registering it would additionally need a `parser_key` and a configuration entry.

The smallest honest next step is evidence, not code.

### 8.4 Open extension point — `C` records

All three `C` records in this capture are `C|1||`: structurally present, **payload empty**. Nothing is lost by the current model today, and nothing can be classified from them.

`ParsedHL7` has no comment representation. If a future capture carries populated comments, the smallest safe extension is an inert carrier modelled on the existing `ParsedObxMetadata` — *"retained for future evidence-based classification… never interpreted by the current pipeline"* — not a parser or registry redesign. **That extension is recorded here, not designed here.**

---

## 9. Files

| Path | Contents |
|---|---|
| [`FIELD_REPORT.md`](FIELD_REPORT.md) | Full imported survey report, with PHI redacted and superseded sections marked |
| [`VALIDATION_2026-09-16.md`](VALIDATION_2026-09-16.md) | Session 2 record — transport role, framing, `O`-4 mapping (with corrections dated 2026-09-17) |
| [`VALIDATION_2026-09-17.md`](VALIDATION_2026-09-17.md) | Session 3 record — controlled retransmission, GT-3A, cross-day comparison, RECONNECT-01/02 |
| [`../../../backend/tests/fixtures/instruments/sysmex_xn550/patient_result_001.astm`](../../../backend/tests/fixtures/instruments/sysmex_xn550/patient_result_001.astm) | Redacted raw ASTM patient-result message, 2 824 bytes, 49 records |
| [`../../../backend/tests/test_xn550_astm_contract.py`](../../../backend/tests/test_xn550_astm_contract.py) | Fixture contract — 16 tests, DB-free, no production code exercised (§8) |

### 9.1 Fixture notes

- **Redacted, per `docs/09` §12.4**, which permits only redacted or synthetic derivatives in this repository. Three PHI tokens are replaced with **length-preserving** `X` masks: patient name (5 occurrences), patient id (1), date of birth (1) — **43 bytes of 2 824**. Every delimiter, field position, record length, clinical value, unit, flag, parameter name and timestamp is **unchanged**.
- **Masking re-verified on 17 September 2026:** session 3 showed that the Sample No. is embedded in the four graphic-reference `R`-4 paths. In this fixture, `O`-4 and all four image-path name segments are masked (`XXXXXX`).
- **Line endings are bare `\r`, deliberately.** That is what the instrument sent. Read the file as **bytes**, not with universal newlines, or the record structure will be silently altered.
- SHA-256, committed fixture: `2fcc8f38de8d6903595b5e876e00de352ace7005b805739486a22106ce543ad3`
- SHA-256, unredacted original: `6f6cf24905eb0a0761f07e2ed534ea90374f039ad023afa6eb398401ec6742a8` — retained only in `D:\SurveyLIS`, outside this repository.
- **It is a record-grammar fixture, not a transport fixture.** It carries no framing bytes and must not be used to justify a framing decision (see `FIELD_REPORT.md` §3.3).
- Prototype scripts (`sysmex_xn550_tcp_listener.py`, `sysmex_parser.py`) remain in `D:\SurveyLIS` and are **not** imported.
