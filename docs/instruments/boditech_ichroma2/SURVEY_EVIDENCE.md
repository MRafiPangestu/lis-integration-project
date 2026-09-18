# Boditech ichroma™ II — Survey / Field Evidence

> **SURVEY / FIELD EVIDENCE — NOT AN IMPLEMENTATION CONTRACT.**
> This document records what the existing survey material actually shows about the ichroma II, and what it does not. It defines no parser, no schema, no API, no configuration and no design. Nothing here authorises implementation.

| Item | Value |
|---|---|
| Date of this audit | 2026-09-18 |
| Instrument | Boditech Med Inc. ichroma II (immunoassay analyser), `id_instrument = 6` (`docs/08_MASTER_DATA.md`, `docs/09` §4) |
| Evidence source audited | `D:\SurveyLIS` — the same survey tree that holds the Sysmex XN-550 field evidence |
| Evidence read-only | Nothing under `D:\SurveyLIS` was created, modified or deleted by this audit |
| PHI | No patient name, patient identifier, specimen/cartridge code or result value from the survey material appears in this document. Structure, field positions, test codes and units only |
| Physical testing | **None.** No instrument was connected or contacted by this audit |

---

## 1. Headline finding

**The ichroma II has no primary field evidence.** The survey tree contains a complete, provenance-controlled evidence set for the XN-550 and, for the ichroma II, **three top-level files and nothing else**. There is no packet capture, no byte-exact receive log, no manifest, no hash file, and no operator ground-truth record for this instrument.

What does exist is a research note containing **two transcribed HL7 messages**. Those transcriptions are informative and internally consistent, and they are the reason this instrument is further along than the other unsurveyed analysers — but by this project's own evidence standard they are **derived material, not primary evidence** (§3).

---

## 2. Evidence inventory (TASK 1)

Every file in `D:\SurveyLIS` (115 files) was searched by **content**, not filename, for `ichroma`, `boditech`, `i-chroma`, MLLP/HL7 markers (`MSH|`, `\x0bMSH`, `OUL^R24`, `\x1c\r`) and for the IPv4 addresses named in the scripts. Exactly three files matched.

| Artifact | Type | Date (mtime) | iChroma relevance | PHI risk | What it proves |
|---|---|---|---|---|---|
| `D:\SurveyLIS\ichroma2_lis_research.md`<br>6 710 B · sha256 `cad37f12…` | Note — derived analysis with **transcribed** raw payloads | 2026-09-15 16:30 | **Primary content source.** Connectivity, protocol claim, two byte-literal messages, parsing commentary, send-behaviour narrative | **HIGH** — contains two patient names, two specimen/cartridge codes and result values in cleartext | That two HL7/MLLP-framed messages *of this shape* were obtained from something labelled ichroma2, and what the surveyor concluded |
| `D:\SurveyLIS\ichroma_tester.py`<br>2 151 B · sha256 `f4d06585…` | Script — TCP **server** on `0.0.0.0:8000` | 2026-09-15 16:10 | The receiver that plausibly produced the transcriptions (`print(f"[DATA RAW] -> {data}")`) | None | That a listener was written. **It writes nothing to disk** — which is exactly why no capture exists |
| `D:\SurveyLIS\ichroma_client.py`<br>2 925 B · sha256 `1541b621…` | Script — TCP **client** dialling `172.17.31.202:8000` | 2026-09-15 16:15 | A reverse-direction probe (LIS dials instrument) | None | That the reverse direction was *scripted*. **No output, log or result survives**, so its outcome is unknown |

**Nothing else.** The `evidence/` tree (`2026-09-16`, `2026-09-17`, 5 runs, 34 captures/binaries) is XN-550 only. The remaining top-level files are XN-550, BX-3010 and generic scratch tools.

**Negative results, explicitly** — searched and **not found** anywhere in the tree:

- no `.pcapng`, `.bin`, `.hl7` or `.astm` file containing ichroma traffic;
- no byte sequence `MSH|`, `\x0bMSH`, `OUL^R24` or `ichroma2` in **any** of the 34 capture/binary files;
- neither `172.17.31.201` nor `172.17.31.202` appears in any capture. The XN-550 sessions run on a `10.0.0.x` segment — a different network context entirely;
- no ichroma manifest, SHA-256 file, events JSONL, selftest or `GROUND_TRUTH_operator_notes.md`.

*(Nine capture files contain the two-byte sequence `1c 0d` by chance. Since `MSH|` and `\x0bMSH` are absent from all of them, this is binary coincidence, not MLLP.)*

---

## 3. Evidence class and provenance (why nothing here is VERIFIED)

The XN-550 evidence standard, applied in this same tree, is: live packet capture (`.pcapng`) **plus** a byte-exact receive log (`*_rx.bin`) **plus** a per-message manifest **plus** a SHA-256 file **plus** a tool selftest **plus** operator ground truth declared *before* transmission. Every XN-550 run has all six.

The ichroma material has **none** of the six. The chain is:

> instrument → `ichroma_tester.py` → terminal `print()` → *(human copy/paste)* → markdown note

The two byte literals are consistent with genuine `repr(bytes)` output from that script, and they are internally coherent (§5–§6), which is meaningful corroboration. But transcription through a terminal and an editor cannot be distinguished from correction, truncation or reconstruction after the fact. There is no hash, no capture and no timestamp of receipt to check against.

**Consequence:** nothing about the ichroma II may be labelled **VERIFIED**. The strongest honest label for anything visible in the transcription is **OBSERVED (PARTIALLY VERIFIED)**, and it is *conditional on the transcription being faithful*. That condition is cheap to discharge — one short controlled session with capture turned on (§10).

---

## 4. Transport (TASK 3)

| Aspect | Finding | Label |
|---|---|---|
| Physical medium | RJ45 / Ethernet, TCP/IP; no serial converter needed | **CANDIDATE** — note assertion; no capture, no nameplate photo |
| Instrument role | Instrument acts as **TCP client** and dials the LIS | **OBSERVED** — corroborated structurally: the receiver that produced the data is a `bind()`/`listen()`/`accept()` server, so data did arrive on an inbound connection |
| LIS role | LIS must be a **TCP server / listener** | **OBSERVED**, same corroboration |
| Port | Note and both scripts default to **8000**; the note calls it an example (*"contoh: Port 8000"*) | **CANDIDATE** — not confirmed as the instrument's configured port |
| IP addressing | Note: LIS `172.17.31.201`, instrument `172.17.31.202`, same subnet required | **CANDIDATE** — no capture confirms either address was in use |
| Reverse direction (LIS dials instrument) | `ichroma_client.py` exists and targets `172.17.31.202:8000`, but no output survives | **NOT CONFIRMED** — cannot tell whether it was run, let alone whether it succeeded or was refused. **The XN-550 "S7" question is therefore open for this instrument** |
| Listener requirement | Follows from the role finding, but only as far as that finding is trusted | **OBSERVED**, inherits the same conditionality |
| Packet capture | **None exists** | **NOT TESTED** |
| Session establishment / teardown | Note: TCP 3-way handshake, one MLLP message, immediate FIN by the instrument ("hit-and-run") | **CANDIDATE** — narrative only; no handshake or FIN was captured |
| Idle behaviour | Nothing recorded (no keepalive, heartbeat or idle-timeout observation) | **UNKNOWN** |
| Reconnect behaviour | Not recorded | **UNKNOWN** |
| Message timing | Not recorded — no inter-message or inter-connection timings exist | **UNKNOWN** |
| TCP fragmentation / coalescing | Both transcriptions are complete single frames, implying each arrived in one `recv()`. Two samples establish nothing general | **UNKNOWN** |

---

## 5. Protocol and framing (TASK 4)

The three layers the audit keeps separate:

- **Configured protocol label** — none available. No instrument configuration screen, export or screenshot exists.
- **Vendor/documentation claim** — `docs/08_MASTER_DATA.md` records ichroma II as **ASTM** (Research Baseline). **This contradicts the survey material** (§13).
- **Observed wire behaviour** — from the transcriptions only:

| Aspect | Finding (measured from the two transcribed frames) | Label |
|---|---|---|
| Protocol | HL7 — `MSH` header, `\|` field separator, `^~\&` encoding characters, `MSH-12 = 2.6` | **OBSERVED** |
| Message type | `MSH-9 = OUL^R24^OUL_R24` (unsolicited observation, lab-to-LIS) | **OBSERVED** |
| Lower layer | **MLLP** — both frames begin `0x0B` and end `0x1C 0x0D` | **OBSERVED** |
| Segment terminator | **CR only.** Message 1: 6 CR / 0 LF; message 2: 8 CR / 0 LF; **zero CRLF pairs**; payload ends with CR | **OBSERVED** |
| Character set | Pure US-ASCII; 0 bytes > 127 in both | **OBSERVED** |
| Message boundary | The MLLP end block `<FS><CR>`; no length prefix | **OBSERVED** |
| ENQ / STX / ETX / EOT | Absent — none of `0x05`, `0x02`, `0x03`, `0x04` appears. This is MLLP, **not** ASTM E1381 | **OBSERVED** |
| ACK / NAK | **None sent by the LIS.** `ichroma_tester.py` never writes to the socket, yet data was obtained. Whether the instrument *requires*, *waits for* or *ignores* an MLLP ACK is untested — and whether a missing ACK affects the *next* message is unknown | **NOT TESTED** |
| Checksum | No checksum field present; MLLP has none | **OBSERVED** (absence) |
| Control / sequence number | `MSH-10 = "1"` in **both** messages — **not unique per message** | **OBSERVED**, and material: control ID cannot serve as a deduplication key |
| Processing ID | `MSH-11 = "T"`. HL7 table 0103: `P` = Production, `T` = Training, `D` = Debugging | **OBSERVED** — the instrument was emitting non-production-flagged messages. Whether this is configurable is **UNKNOWN** |

> **Do not call this "ASTM".** The evidence shows HL7 v2.6 inside MLLP. Equally, do not yet call it "HL7 v2.6-conformant": §7 shows fields used in non-standard positions.

---

## 6. Message corpus (TASK 5)

**Two messages exist, both as transcriptions.** No corpus in the XN-550 sense.

| Metric | Message 1 | Message 2 |
|---|---|---|
| Framed length | 231 B | 295 B |
| Payload (frame removed) | 228 B | 292 B |
| MLLP frame complete | yes (`0x0B` … `0x1C 0x0D`) | yes |
| Segments | 6 | 8 |
| Segment order | `MSH → PID → OBR → ORC → SPM → OBX` | `MSH → PID → OBR → ORC → SPM → OBX → OBX → OBX` |
| `OBX` count | 1 | 3 |
| Segment lengths (B) | 66, 22, 33, 30, 39, 32 | 66, 22, 35, 30, 40, 29, 32, 30 |
| `\|` count | 78 | 100 |
| `^` count | 3 (all in `MSH`) | 3 (all in `MSH`) |
| Test named in `OBR-2` | TSH | HbA1c |
| Truncated? | No — complete frame | No — complete frame |

- **Distinct messages: 2. Byte-identical pairs: 0. Distinct structures: 2** (single-result and multi-`OBX`).
- **Multi-result shape:** one ordered test yields several `OBX` segments. Only the first carries an observation identifier (`OBX-3`); the second and third carry a value and units with `OBX-3` **empty**, distinguished only by `OBX-1` set-id and their units. Any consumer must therefore treat `OBX-3` as optional and rely on ordering — a design hazard worth confirming against more samples.
- **`OBX-2 = "TX"`** (text) on every result, including plainly numeric values.
- **`OBX-11 = "R"`** on every result — HL7 table 0085: *"Results entered — not verified."*
- **`OBX-8 = "0"`** on every result. `0` is not an HL7 table 0078 abnormal-flag code. **UNKNOWN semantics.**
- **Timestamps:** `MSH-7 == OBR-7` in **both** messages. The message therefore carries **no distinct transmission timestamp** — only an analysis/observation time. Message 2's timestamp is **12 days older** than the file that records it, which is consistent with the instrument re-sending a stored historical result rather than a fresh run. **CANDIDATE**, not established.
- **Image references:** none. No `ED`/`RP` data type and no path-like value appears. (Unlike the XN-550, which references graphics.)
- **Duplicate relationships:** none observable — two different tests, two different days, and a constant `MSH-10`.
- **Multiple-message/session behaviour:** the note asserts one connection per patient even on bulk "select all". **CANDIDATE** — narrative only, no capture, no connection log.

---

## 7. Identity and ground truth (TASK 6)

**No operator ground truth exists for this instrument** — nothing was declared before transmission, and no screenshot or worksheet accompanies either message. Every mapping below is inferred from field position alone.

| Candidate | Where it appears | Assessment |
|---|---|---|
| Patient name | `PID-2` holds a lowercase human-name-like string in both messages | **RAW-ONLY.** Note that `PID-2` is HL7 *Patient ID (external)*, **not** `PID-5` *Patient Name*. The instrument is putting name-like text in an identifier field, or the field is an operator free-text label. **Semantics UNKNOWN** |
| Patient identifier | No `PID-3` patient identifier list; `PID-1` empty | **NOT PRESENT** |
| Administrative sex | `PID-8` (`Male` in one, `-` placeholder in the other) | **CANDIDATE** — positionally conformant, unverified |
| Specimen identifier | `SPM-2` holds an 8–9 character uppercase alphanumeric code | **RAW-ONLY / UNKNOWN.** The final `SPM` field carries a **2027 date**, which reads far more like a **reagent-cartridge expiry** than a specimen date. If so, `SPM-2` is a **cartridge lot code, not a specimen ID**. Must not be treated as specimen identity without ground truth |
| Sample number / accession | Not identifiable | **UNKNOWN** |
| Barcode | Not identifiable | **UNKNOWN** |
| Operator-entered label | `PID-2` is the only plausible candidate | **UNKNOWN** |
| Sequence number | `MSH-10 = "1"` (constant), `OBX-1` set-id, `SPM-1 = 1` | **RAW-ONLY** — `MSH-10` is constant and carries no sequence information |
| Order identifier | `OBR-2` holds the **test name**, not an order number; `OBR-3 = 0`; `OBR-4` differs between messages (`1` vs `0`) | **RAW-ONLY.** `OBR-4`'s meaning is **UNKNOWN** |
| Instrument-local identifier | A constant token `RF076` appears in `MSH-5` and `ORC-18` | **RAW-ONLY** — device/receiving-application configuration; meaning **UNKNOWN** |

**No identity mapping may be inferred from this material.** The single most important gap for any future integration is that nothing distinguishes a patient identity from an operator-typed label, and nothing establishes whether `SPM-2` is a specimen or a reagent lot.

---

## 8. Workflow coverage (TASK 7)

| Workflow | Status | Basis |
|---|---|---|
| One selected result | **OBSERVED** | Message 1 (single `OBX`) |
| Multiple selected results | **NOT TESTED** | Narrative claim of one connection per patient; no capture, no connection log |
| Retransmission | **NOT TESTED** | — |
| Rerun | **NOT TESTED** | — |
| Resend of a stored result | **CANDIDATE** | Message 2's 12-day-old timestamp is suggestive only |
| Reconnect resend | **NOT TESTED** | — |
| Pending-queue behaviour | **NOT TESTED** | — |
| Startup message | **NOT TESTED** | — |
| QC | **NOT TESTED** | Zero captures |
| Calibration | **NOT TESTED** | Zero captures |
| Maintenance | **NOT TESTED** | Zero captures |
| Historical query | **NOT TESTED** | — |
| Host-initiated pull | **NOT TESTED** | `ichroma_client.py` exists; no result survives |

---

## 9. Comparison with the XN-550 methodology (TASK 8)

Used as a **checklist only**. The ichroma II is a different vendor, protocol family and message type; no XN-550 behaviour transfers.

| Question | XN-550 method | ichroma existing evidence | Status |
|---|---|---|---|
| Transport role | Reverse-dial test + pcapng; SYNs silently dropped → S7 met | Inbound-only receiver script; reverse probe unconfirmed | **Open** (strong prior) |
| Port | Configured and confirmed on the wire (5001) | 8000 as a script default, called an example | **Open** |
| Listener requirement | Proven from the role test | Follows from the role finding only | **Open** (strong prior) |
| Framing | pcapng + byte-exact `rx.bin`, bare-CR records, no E1381 | MLLP `0x0B`…`0x1C 0x0D`, CR-only segments — from transcription | **Partially answered** |
| Message boundary | `H|`…`L|` record rule, proven over 20 messages | MLLP end block, 2 samples | **Partially answered** |
| ACK / NAK | Policy pinned (`ack_per_read_on_receive`, single `0x06`, no NAK) | Nothing sent, nothing tested | **Open** |
| Identity | Ground truth declared before transmission; `O`-4 mapping confirmed | No ground truth at all | **Open** |
| Timestamps | `R`-13 / `O`-based; field numbering pinned | `MSH-7 == OBR-7`; no send time | **Partially answered** |
| Retransmission | Same-day byte-identical retransmission observed | Not tested | **Open** |
| Multi-select | MULTI-SELECT-01, five messages, one session, capture | Narrative claim only | **Open** |
| Reconnect | Observed (PARTIALLY VERIFIED, confounded) | Not tested | **Open** |
| Restart / power cycle | POWER-CYCLE-01 observed | Not tested | **Open** |
| QC | Zero captures (open for XN-550 too) | Zero captures | **Open** |
| Calibration | Zero captures | Zero captures | **Open** |
| Maintenance | Zero captures | Zero captures | **Open** |
| Startup | Instrument-screen only | Not tested | **Open** |
| Query / pull | Not tested | Not tested | **Open** |
| Corpus size | 20 messages / 16 distinct payloads / 10 structures | **2 transcribed messages / 2 structures** | **Open** |
| Ground truth | Declared before every action, recorded per run | **None** | **Open** |

**Roughly 3 of 20 checklist questions are even partially addressed**, and all three rest on transcription rather than capture.

---

## 10. Is more field work required, and what is the minimum? (TASK 9)

Classification of every unresolved item:

- **A — answerable from existing `D:\SurveyLIS` evidence:** segment order, HL7 version, message type, MLLP framing, CR-only separators, ASCII-only, multi-`OBX` shape, `MSH-10` constancy, `MSH-11 = T`, `MSH-7 == OBR-7`. *All at transcription confidence — they are hypotheses to confirm, not facts to build on.*
- **B — answerable from repository/code analysis:** repository identity (§12); absence of any iChroma parser, configuration or prototype; the `docs/08` protocol contradiction (§13); and the fact that the repository already contains an MLLP frame extractor with exactly these block characters, currently used only on the **client** path.
- **C — requires a new controlled laboratory observation:** transport role confirmation, actual port, reverse-direction behaviour, ACK/NAK requirement, identity ground truth, multi-select behaviour, retransmission, reconnect, restart, corpus size and category coverage, and whether `MSH-11` can be `P`.
- **D — should remain UNKNOWN (testing risky or unnecessary):** port scanning the instrument (not authorised, same position as the XN-550); deliberately malforming messages or forcing NAK conditions on a clinical analyser; and any attempt to provoke QC/calibration/maintenance messages by altering instrument state.

### Minimal additional field work required

These experiments are planned in detail, with the capture structure and the session rules, in [`FIELD_VALIDATION_PLAN.md`](FIELD_VALIDATION_PLAN.md).

**Yes — one short, scripted session is required.** Nothing can be skipped on the grounds that it was done for the XN-550, because the XN-550 answers do not transfer. But the session can be small, because the transcription tells us what to expect.

| ID | Experiment | Answers | Why it cannot be skipped |
|---|---|---|---|
| **T-IC-A** | Run a byte-exact listener **with packet capture, manifest and SHA-256**, and receive ≥1 message | Transport role, port, framing, message boundary, first primary corpus entry | Converts every §5 finding from transcription to evidence in one step |
| **T-IC-B** | Attempt LIS→instrument connection on the configured port while capturing | Reverse-direction behaviour; whether listener mode is mandatory | The XN-550 "S7" analogue; `ichroma_client.py` left no result |
| **T-IC-C** | Send ≥3 consecutive messages with **no** ACK, then repeat **with** an MLLP ACK | Whether an ACK is required, and whether withholding one blocks later messages | MLLP normally expects an ACK; the survey receiver never sent one. Unresolved, this is a data-loss risk |
| **T-IC-D** | Bulk "select all" with ≥3 patients, capturing connections | One-connection-per-patient claim; session model | Currently narrative only, and it determines the whole ingestion shape |
| **T-IC-E** | Re-send the same stored result twice | Byte-identical or not; `MSH-10` behaviour | `MSH-10` is constant, so dedup needs another key — or none exists |
| **T-IC-F** | Operator declares name / sample / cartridge lot **before** sending, then send | `PID-2` and `SPM-2` semantics | The only way to resolve specimen-vs-lot; no mapping may be inferred |
| **T-IC-G** | Capture QC, calibration, maintenance and startup output if they occur naturally | Non-patient message categories | Zero captures; a misclassified control result is a clinical risk |
| **T-IC-H** | Read the instrument's LIS configuration screen and photograph it | Configured port, protocol label, `MSH-11` setting | Separates configured label from observed behaviour |

T-IC-A, B, D, E and F fit in a single session with the XN-550 tooling reused unchanged.

---

## 11. Field-validation status matrix (TASK 10)

| Aspect | Status | Evidence source | Confidence | Remaining gap |
|---|---|---|---|---|
| Transport | Instrument dials LIS; TCP/IP over Ethernet | Research note + receiver script shape | **Low-medium** | No capture; reverse direction unconfirmed (T-IC-A, B) |
| Protocol | HL7 v2.6, `OUL^R24` | Transcribed frames | **Medium** | Two samples, transcription only (T-IC-A) |
| Framing | MLLP `0x0B` … `0x1C 0x0D`; CR-only segments; no ASTM control bytes | Byte analysis of transcriptions | **Medium** | Not confirmed on the wire (T-IC-A) |
| Message structure | `MSH PID OBR ORC SPM OBX+`; multi-`OBX` per order | Byte analysis | **Medium** | 2 structures; `OBX-3` empty on continuation rows unconfirmed (T-IC-A) |
| Identity | `PID-2` name-like, `SPM-2` code-like | Field position only | **Very low** | No ground truth; specimen-vs-lot unresolved (T-IC-F) |
| Timestamp | `MSH-7 == OBR-7`; no send time | Byte analysis | **Medium** | Analysis-vs-send semantics unconfirmed (T-IC-A, E) |
| Retransmission | Not tested | — | **None** | T-IC-E |
| Reconnect | Not tested | — | **None** | Deferred until the session model is known |
| QC | Not tested | — | **None** | T-IC-G |
| Calibration | Not tested | — | **None** | T-IC-G |
| Maintenance | Not tested | — | **None** | T-IC-G |
| Startup | Not tested | — | **None** | T-IC-G |
| Query / pull | Not tested | — | **None** | T-IC-B |
| Corpus | 2 transcribed messages, 2 structures, 0 primary captures | Research note | **Low** | No primary corpus exists (T-IC-A) |
| Ground truth | None | — | **None** | T-IC-F |

---

## 12. Repository fit (TASK 11)

| Question | Answer |
|---|---|
| Does iChroma have a repository identity? | **Yes** — `id_instrument = 6`, `nama_mesin = "Boditech Med Inc. — ichroma II"`, seeded by `backend/scripts/seed_master_data.py`. `protokol` and `tipe_koneksi` are **NULL**, which is correct: nothing is verified |
| Parser? | **None.** No key in the parser registry |
| Configuration entry? | **None** in `instruments.example.json` or any deployment configuration |
| Simulator, prototype or experimental code? | **None in the repository.** The two scripts in `D:\SurveyLIS` are survey tools, live outside the repository, and are **not evidence of instrument behaviour** |
| Tests? | **None** |
| Anything reusable? | `app/integration/mllp.py` already extracts MLLP frames using exactly `0x0B` / `\x1c\x0d`, and the XN-550 work added a generic listener transport. **This is an observation about the codebase, not a design decision, and not a reason to start implementing** |

`ichroma_client.py`'s parser splits records on `\r\n`, while the transcribed data uses **CR only**. The script was written from assumption, not from the observed bytes — a concrete reason not to treat survey scripts as evidence.

---

## 13. Documented inconsistencies to resolve (not changed by this audit)

1. **`docs/08_MASTER_DATA.md` records ichroma II as `ASTM`** with connectivity `TCP/IP, RS-232, USB` ("Research Baseline"). The survey material shows **HL7 v2.6 over MLLP**. These cannot both be right. **Not corrected here**, because the contradicting evidence is transcription-class: correcting a documented vendor baseline needs primary evidence (T-IC-A). Raise it once T-IC-A is captured.
2. **`docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md` row 6** records Protocol and Transport as **UNVERIFIED** with Evidence **None**. That is accurate for repository-held evidence, and it stays accurate — the survey note was never imported and does not meet the bar. `T-CONN-01-06` and `T-CORPUS-01-06` remain **BLOCKED**.

---

## 14. Readiness verdict

**The ichroma II is not ready for an implementation contract.**

The XN-550 contract was written on 20 captured messages, a confirmed transport role, a settled framing question and ground truth declared before every action. The ichroma II has two transcribed messages, no capture, and no ground truth. Writing a contract now would mean pinning identity semantics — the field that decides whether a result can ever be attached to a patient — on field position alone.

The gap is small and well understood. One controlled session (§10) plausibly moves this instrument from "two transcriptions" to "contract-ready", and the existing XN-550 tooling can be reused without modification.

**Next step: collect primary evidence. Not implementation.**
