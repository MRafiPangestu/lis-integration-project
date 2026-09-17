# Sysmex XN-550 Physical Validation — 2026-09-17

Session record for the third XN-550 field session. The first was the survey of
15 September 2026 ([`FIELD_REPORT.md`](FIELD_REPORT.md)); the second was the validation
of 16 September 2026 ([`VALIDATION_2026-09-16.md`](VALIDATION_2026-09-16.md)); the
standing engineering summary is [`README.md`](README.md).

The same day also produced **Run03**, a corpus-expansion run after a break, with a fresh
capture and listener (§15), and the cumulative corpus status that follows from it (§16).

Evidence labels are those of `../../09_PHYSICAL_INSTRUMENT_VALIDATION.md` §2, as used
in the 2026-09-16 record: **VERIFIED · CANDIDATE · UNVERIFIED · UNKNOWN**, plus the
§6.2 confidence label **PARTIALLY VERIFIED** where a behaviour was observed but its
cause could not be isolated. Every finding keeps three things apart:

- **Observed fact** — what the bytes, packets or logs show;
- **Interpretation** — a reading of those facts, labelled as such;
- **Hypothesis** — a possible explanation that the evidence does not establish.

**This document proposes no production design.** No parser rule, identity or
specimen mapping, deduplication key or schema change follows from anything below.

---

## 1. Session metadata

| Item | Value |
|---|---|
| Session date | **2026-09-17** (site local, UTC+08:00) |
| Instrument | Sysmex XN-550 (`id_instrument = 3`), `10.0.0.11`, MAC `74:fe:48:a9:dc:34` |
| LIS host | `10.0.0.10`, MAC `00:e0:4c:14:41:48`, interface `Ethernet` (same USB adapter as 2026-09-16) |
| TCP port | **5001** |
| Runs | **run01** 10:02–12:25 (first connection, GT-1, GT-2, GT-3A; RECONNECT-01/02 inside the same capture, listener output in `run02_reconnect/`) · **run03_corpus** 14:20–14:52 (fresh capture, listener and self-test after a break) |
| Repository | `refactor/orm-architecture` at `c1c41e2` during run01/run02, `af2196b` during run03; **unchanged during every capture phase** |
| Evidence root | `D:\SurveyLIS\evidence\2026-09-17\` — outside the repository |
| PHI | **All raw payloads, the byte stream, the pcaps carrying payload and the ground-truth notes are PHI-bearing** and stay in the evidence root. No patient name, Sample No. value or other identifier appears in this document |
| Listener | `D:\SurveyLIS\astm_raw_capture.py`, SHA-256 `4cb47218…aa710ed` (same tool as 2026-09-16); loopback self-test **passed** before use (1 044 bytes, all 256 values, SHA-256 identical) |
| ACK policy | ACK-on-receive (one `0x06` per socket read), the 2026-09-16 baseline. **No NAK was sent and no ACK was withheld at any point** |

**Field numbering is ASTM 1-based throughout**, with field 1 being the record type:
`R`-2 sequence, `R`-3 test id, `R`-4 value, `R`-5 units, `R`-6 reference range,
`R`-7 abnormal flag, `R`-8 nature of abnormality, `R`-9 status, `R`-11 operator,
`R`-13 completion timestamp. See §13 for a numbering inconsistency this reconciliation
found in earlier documents.

**Ground-truth labels are per session.** "GT-1" and "GT-2" below are the
2026-09-17 controlled actions; they are unrelated to "GT-1"/"GT-2" in the
2026-09-16 record.

---

## 2. Scope and boundaries

**Objective:** close evidence gaps left open on 2026-09-16 — controlled retransmission,
identifier behaviour across different sequences, and controlled disconnect/reconnect —
using pre-registered operator ground truth rather than inference from payloads.

**Relationship to blockers.** Unchanged from 2026-09-16 §2.1: **M9.2 and M9.3b are
defined by BC-5150 test IDs and are not closed or advanced by XN-550 evidence.** This
session contributes to **T-CONN-01-03** and **T-CORPUS-01-03** only (§12).

**Explicitly not performed:** ACK withholding; NAK; packet modification; malformed
messages; instrument configuration change; send-all/batch transmission; genuine
re-analysis of a specimen; port scanning; any database contact; any parser, registry,
schema, migration, transport or frontend change.

**Ground-truth discipline.** Every controlled action was written to the external
ground-truth notes **before** the analyst acted, with a byte-offset baseline, and every
outcome was appended afterwards without editing the declaration.

---

## 3. Evidence inventory

Paths relative to `D:\SurveyLIS\evidence\2026-09-17\`. PHI column: **Yes** = must never
enter the repository.

| File | Bytes | SHA-256 | Role | PHI |
|---|---|---|---|---|
| `selftest/selftest_conn99_rx.bin` | 1 044 | `e4f408a4229126f9314efc8a573ccfa66a82e6d358c73ef25e75d7f2afc9e48f` | Listener fidelity proof | No — synthetic |
| `session_2026-09-17_xn550_run01_prelistener_snapshot.pcapng` | 6 744 | `e82f0029350b13acf84153a29fc124ff04834bca76d88dd05bd54c79d9c3c9c7` | Dial pattern before any listener; 70 frames, 0 payload | No |
| `run01/day18_run01_conn01_rx.bin` | 11 994 | `49fc8d8c290c94e4bb198c29c72a8f811abd995c6c22745c975ef4b6e7d3154d` | **Authoritative byte stream** — all four messages on session 49706 | **Yes** |
| `run01/day18_run01_conn01_events.jsonl` | 3 970 | `9a0c680ddd1f6999759e869a327d8d5884a74d89e351e1df58afd4acf7de1ce7` | Per-read rx/tx events with hashes | No — metadata |
| `run01/day18_gt1_msg_01.astm` | 3 133 | `349703441b9cfb4fa32e17a4227bb34c845c2a140cc0dff46b12f8cc2f0fca9f` | GT-1 message (stream offset 0–3132) | **Yes** |
| `run01/day18_gt2_msg_02.astm` | 3 133 | `349703441b9cfb4fa32e17a4227bb34c845c2a140cc0dff46b12f8cc2f0fca9f` | GT-2 message (offset 3133–6265) | **Yes** |
| `run01/day18_gt3a1_msg_03.astm` | 2 887 | `59bee91d9c31f4afc6e9090dd95fda2369601db6b83b433d38e9847e59d7def7` | GT-3A-1 message, Seq 51 (offset 6266–9152) | **Yes** |
| `run01/day18_gt3a2_msg_04.astm` | 2 841 | `24dd58f51db689ac5b61de6b09bd4f6c12a78e20e4e1f80b90bde0158524fd23` | GT-3A-2 message, Seq 58 (offset 9153–11993) | **Yes** |
| `run01/day18_gt1_manifest.json` | 1 471 | `bda385485bb62e7a8ba396ad9c1c40f70e868c38b952cd7f5947ad13859b5aec` | GT-1 wire/ACK record | No |
| `run01/day18_gt2_manifest.json` | 1 765 | `d44d6d5137b2a33ce79d1f2db1d641d94cddbb070e6e2d34d99130086cfb187f` | GT-2 wire/ACK record | No |
| `run01/day18_gt3a_manifest.json` | 4 012 | `72c04041e13c5261d36078d037d907800b5bdaf9b239d4c71ba5c2110f1f6fbf` | GT-3A wire/ACK/comparison record | No |
| `run01/phase1_first_connection_observation.md` | 2 229 | `38c4d61fc477ac71ef93bdc6d30cc46e0342b47a8ccf985e8028ca1129f7cf6b` | First-connection observation | No |
| `session_2026-09-17_xn550_run01_post_gt1_snapshot.pcapng` | 10 612 | `4608d008578160157ed3e1a6d85a4222f9201c2b84e5cbf070566628b04d0d4a` | Frozen wire evidence after GT-1 | **Yes** |
| `session_2026-09-17_xn550_run01_post_gt2_snapshot.pcapng` | 14 524 | `e61d90354a7b5b31a424251a974b3ccd626a32079a08abb0b90edc6b7c94de89` | After GT-2 | **Yes** |
| `session_2026-09-17_xn550_run01_post_gt3a1_snapshot.pcapng` | 18 372 | `7bc26523cca3c7846f2065a064197a3a2dd0e7e5a7542bea6c9789501ba2742b` | After GT-3A-1 | **Yes** |
| `session_2026-09-17_xn550_run01_post_gt3a2_snapshot.pcapng` | 22 172 | `2141a10c276e9feba0d7bdb6e99398b01f859f30295f4a41a2035a14aef9b580` | After GT-3A-2 = pre-disconnect checkpoint | **Yes** |
| `run02_reconnect/reconnect_window_frames_110-145.pcapng` | 4 436 | `7e89ecbb7d22dcb45054419d80966ea93497f8742e06c99bc2241811fb2860fb` | RECONNECT-01/02 packets only (36 frames, 0 payload) | No |
| `run02_reconnect/post_reconnect02_snapshot.pcapng` | 26 244 | `0612751ef852a6d8b64e979b8c0981145bc1f554be0c1aa83b72c0f3f64550c5` | Full capture after RECONNECT-02 (145 frames) | **Yes** |
| `run02_reconnect/reconnect02_linkstate_log.jsonl` | 868 | `4cd7785f67fb9bd045cdef3310a887fee95a4fd56e968088389d9cf2673854a7` | Adapter link state / process health log | No |
| `run02_reconnect/reconnect_manifest.json` | 2 724 | `df76c880cd4b1de3c1b79927a9bb46fcf261a07a0e89ae1b72539b08f10a0f1d` | Reconnect timeline and hashes | No |
| `run02_reconnect/pre_disconnect_run01_hashes.txt` | 1 788 | `8901afffd2ce5c918c5a7c149803a105901b7e5ac5d9944ffa970b72380583a1` | Integrity baseline for run01; re-verified 16/16 after the tests | No |
| `session_2026-09-17_xn550_run01.pcapng` | 26 500 | `6d1b45c2e255f384c76ffeef449aa96111f38bb2b562f58f317ae1dd1dd6f18a` | Continuous run01 capture, frozen at session close (148 frames; frames 146–148 are shutdown teardown) | **Yes** |
| `run03_corpus/corpus03_conn01_rx.bin` | 22 547 | `240ee105a4d4e79642f50516221fc8772af157ca692de116961384e1059afa01` | **Authoritative Run03 byte stream** — all eight corpus messages; identical to the payload reassembled from the pcap | **Yes** |
| `run03_corpus/corpus_d18_01.astm` … `corpus_d18_08.astm` | 1 860 – 3 126 | see §15.3 | The eight Run03 messages | **Yes** |
| `run03_corpus/session_2026-09-17_xn550_run03_corpus.pcapng` | 34 200 | `813a5b7ecde8ac7bffaa7d2989484b62ca28f4d92ae1322e0c9ea8d55d58e5a1` | Run03 capture, frozen (119 frames; frames 117–119 are shutdown teardown) | **Yes** |
| `run03_corpus/corpus_manifest.jsonl` | 18 860 | `d015b1b62b8a599b3da95c766cbf9a13b683aa4342a7412a889af0ae5f089ae5` | Per-message pre-registration, structure and wire records (includes two appended corrections and one repaired line) | No |
| `run03_corpus/run03_corpus_summary.json` | 2 344 | `fe6c21f2db072907f29ba6f4ff674b6e4f7acf2fe81358cb8327520e97035c7c` | Run03 non-PHI summary | No |
| `run03_corpus/run03_corpus_final_hashes.sha256` | 2 312 | `9a5816b46a0c4b308428e7d353ba26d5813dd44581fd749bcff20d6036469763` | Hash list of all 24 Run03 files; re-verified 24/24 | No |
| `GROUND_TRUTH_operator_notes.md` | — | append-only; not pinned | Pre-registered declarations and outcomes | **Yes** |

The per-message pcap snapshots of Run03 (`run03_corpus/post_corpus_d18_NN_snapshot.pcapng`)
are listed with their hashes in `run03_corpus_final_hashes.sha256`.

---

## 4. Session chronology

| Time | Event | Classification |
|---|---|---|
| 09:33 | Evidence directory created; loopback self-test **passed** | Pre-flight |
| 10:02:46 | Capture started (filter `host 10.0.0.11 or port 5001 or arp`) | Pre-flight |
| 10:02:49.97 – 10:06:49 | Instrument dial cycles: 5 SYNs ~510 ms apart, every ~60 s, source ports 49701 → 49705; each SYN answered by host RST (no listener) | Uncontrolled — passive |
| 10:07:15 | Listener started on TCP 5001 | Controlled |
| 10:07:49.977 | Session `10.0.0.11:49706` established on the first SYN of the next cycle | — |
| 10:07:49 – 10:33:12 | **0 payload bytes** on the session (~25 min) | Observation (§5) |
| 10:32:42 | GT-1 identifiers pre-registered (Sequence 68, Sample No.) | Controlled — declared |
| 10:33:12.922 | **GT-1 message** (3 133 B) | **Controlled** |
| 10:56:35 | GT-2 pre-registered: retransmit Sequence 68 once | Controlled — declared |
| 10:57:01.606 | **GT-2 message** (3 133 B) | **Controlled** |
| 11:19:23 | GT-3A and GT-3A-1 pre-registered (Seq 51) | Controlled — declared |
| 11:20:18.792 | **GT-3A-1 message** (2 887 B) | **Controlled** |
| 11:21:36 | GT-3A-2 pre-registered (Seq 58), after GT-3A-1 was frozen | Controlled — declared |
| 11:22:17.663 | **GT-3A-2 message** (2 841 B) | **Controlled** |
| 11:31:06 | RECONNECT-01 pre-registered | Controlled — declared |
| 11:31:16.088 | LIS listener process terminated → one LIS→instrument `RST, ACK` | **RECONNECT-01** |
| 11:31:16.270 | New listener instance listening (gap ~0.18 s) | Controlled |
| 11:36:32 | RECONNECT-01 wait closed — no SYN in 5 min 16 s | Observation |
| 11:38:30.08 | Ethernet link down (network cable unplugged; adapter stayed attached) | **RECONNECT-02** |
| 11:41:38.82 | Ethernet link up (same cable, same ports) | RECONNECT-02 |
| 11:46:49.990 | Instrument SYN from port 49707; new session established | Observation |
| 11:56:57 | Post-reconnect window closed — 0 payload bytes in 10 min 7 s | Observation |
| 12:25:45 – 12:25:54 | Session close: listener then capture stopped; one LIS-side `RST, ACK` on 49707 | Operator shutdown — not evidence |
| 14:20:03 – 14:20:31 | **Run03** fresh setup: self-test passed, capture started (before cable reconnection), listener started | Pre-flight |
| 14:23:04 | Ethernet link restored (cable reconnected by operator) | Operator setup |
| 14:23:49.927 | Session `10.0.0.11:49737` established (one SYN) | Operator setup — not reconnect evidence |
| 14:27:10 – 14:50:47 | **CORPUS-D18-01 … 08**: eight pre-registered single transmits, eight messages (§15) | **Controlled** |
| 14:52:33 – 14:52:41 | Run03 close: listener then capture stopped; one LIS-side `RST, ACK` on 49737 | Operator shutdown — not evidence |

---

## 5. First connection of the day

**Observed fact.** Before the listener started, the analyst reported that completed
results were pending on the analyzer since the previous day's cable removal (at least
one from the previous day plus six newer, by recollection). The session opened at
10:07:49.977 and carried **no payload for ~25 minutes**, until the first manual
transmit (GT-1). No TCP keepalive frames were observed on the idle session.

**Limitation.** The analyst's values reached the capture operator ~2 minutes after the
listener started (the user stated they were recorded beforehand); 0 bytes had arrived
at that time. The declaration is therefore recorded as *declared before, relayed after*.

**Interpretation — CANDIDATE** (single observation here; Run03 later added a second, shorter
one, §15.1). In this configuration the XN-550
did not transmit analyst-reported pending results automatically when a connection was
established. **Not established:** whether "pending" on the analyzer corresponds to an
instrument transmission queue; whether a longer wait, a new analysis or any other event
would release them; send-all behaviour.

---

## 6. GT-1 and GT-2 — controlled transmission and same-day retransmission

### 6.1 GT-1 — one selected result transmitted once (Sequence 68)

| Check | Observed |
|---|---|
| Messages produced | **Exactly one** |
| Size / SHA-256 | **3 133 B** / `349703441b9cfb4fa32e17a4227bb34c845c2a140cc0dff46b12f8cc2f0fca9f` |
| Wire vs listener | Payload reassembled from the pcap has the identical SHA-256 |
| Records | 55 — `H`×1 `P`×1 `C`×3 `O`×1 `R`×48 `L`×1, order `H P C O C R×48 C L` |
| Line discipline | Bare `CR`, no `LF`, no E1381 control bytes, no bytes ≥ 0x80 |
| `O`-3 | Empty |
| `O`-4 component 3 | Matches the on-screen Sample No. — see note below |
| `P` fields | Content only in `P`-2 (`1`) and `P`-9 (`U`); `P`-6, `P`-14, `P`-26 delimiters only; `P`-3, `P`-4, `P`-5, `P`-8 empty |
| `R`-13 | `20260917035625` on all 48 records — analysis ~6 h 37 min before transmission |
| Sequence number | **Not transmitted.** The string `68` occurs only incidentally inside one measured `R`-4 value |
| `R` records | 48 = the 42 codes of the 2026-09-16 GT-2 message plus 6 flag records (`Neutrophilia`, `Lymphopenia`, `IG_Present`, `Positive_Diff`, `Positive_Morph`, `Positive_Count`) |
| TCP | Session 49706 reused; 2 segments (2 920 + 213) coalesced into 1 read |
| ACK | 1 × `0x06` |
| Byte-identical to any 2026-09-16 message | No |

**Note on the `O`-4 check — recorded, not reinterpreted.** The Sample No. relayed before
GT-1 omitted a 3-character honorific prefix that is present on screen and in the bytes.
Against that relayed value the pre-registered exact-match check **failed as stated**.
The analyst's character-level re-reading, declared **before GT-2**, matches `O`-4
component 3 exactly — in GT-2's bytes and therefore in GT-1's, which are identical.

### 6.2 GT-2 — the same result retransmitted once

| Comparison with GT-1 | Result |
|---|---|
| Messages produced | **Exactly one** |
| Size / SHA-256 | 3 133 B / **identical** |
| Byte-for-byte | **0 differing bytes** (`cmp` equal) |
| Records, `H`/`P`/`C`/`O`/`L`, every `R` field incl. `R`-13 | Identical |
| TCP | Same session 49706; same segmentation (2 920 + 213); 1 read, 1 ACK |

**Observed fact — VERIFIED (one controlled pair).** A declared manual retransmission of
a completed result, **on the same day** as its first transmission, produced a message
**byte-identical** to the first.

**Classification.** A controlled retransmission, satisfying the pre-registered rule:
declared single action **and** exactly one message whose `O`-4 matched. Byte identity
alone was not used as the criterion.

**What this does not establish:** whether a retransmission on a *different* day is
byte-identical (it is not in the one cross-day comparison available — §8); any
instrument-initiated resend; ACK-timeout resend; send-all behaviour; the cause of the
four byte-identical deliveries of 2026-09-16 message A (consistent with manual same-day
resends, but no action was declared for them).

---

## 7. GT-3A — same-patient / different-sequence observation

### 7.1 What this test is, and is not

The analyst selected two results already on the analyzer, **Seq 51** and **Seq 58**, whose
Sample No. values differ only by an operator-added suffix. Each was pre-registered and
transmitted **once**, Seq 58 only after Seq 51 had been captured and frozen.

**This is a same-patient / different-sequence observation only.** It is **not** a
genuine-rerun test, and nothing in it establishes that the two results come from the
same specimen, that one is a rerun or resend of the other, that similar names denote one
patient in any system-level sense, or that the on-screen sequence number is a specimen
identifier. **Genuine same-specimen rerun was not testable in this session and remains
UNVERIFIED.**

### 7.2 Observed facts

| | Seq 51 (GT-3A-1) | Seq 58 (GT-3A-2) |
|---|---|---|
| Messages produced | **Exactly one** | **Exactly one** |
| Size | **2 887 B** | **2 841 B** |
| SHA-256 | `59bee91d9c31f4afc6e9090dd95fda2369601db6b83b433d38e9847e59d7def7` | `24dd58f51db689ac5b61de6b09bd4f6c12a78e20e4e1f80b90bde0158524fd23` |
| Records / order | 50 — `H P C O C R×43 C L` | 49 — `H P C O C R×42 C L` |
| `H` | Identical (sender = instrument model/serial in `H`-5; `H`-3 control id empty) | Identical |
| `P`-2 … `P`-9 | `P`-2 `1`; `P`-6 delimiters only; `P`-9 `U`; others empty | Identical |
| `C` ×3, `L` | Identical | Identical |
| `O`-2 / `O`-3 | `1` / **empty** | `1` / **empty** |
| `O`-4 component 3 | Exact match to its pre-registered Sample No. | Exact match to its pre-registered Sample No. |
| `R`-3 codes | 43 | 42 (= Seq 51's codes minus `Positive_Count`) |
| `R`-4 values | — | Differ in **30** of 42 shared codes |
| `R`-7 flags | — | Differ in **10** shared codes |
| `R`-5, `R`-6, `R`-8, `R`-9 (`F`), `R`-11 (`lab`), `R`-12 | — | No difference |
| `R`-13 | `20260916140903` | `20260916155935` |
| Sequence number in message | Not present in any field | Not present in any field |
| TCP | Session 49706 reused; 1 460 + 1 427 bytes; **2 reads → 2 ACKs** | Session 49706 reused; 1 460 + 1 381; **2 reads → 2 ACKs** |
| Byte-identical to any earlier message | No | No (but see §8) |

### 7.3 Identifiers

- **`O`-4 is the only observed field that distinguishes these two messages as to identity.**
  It is operator-entered free text; here the two values differ only by a manually added
  suffix. `H`, `P`, `C`, `L`, `O`-2 and `O`-3 are identical.
- **No independent specimen identifier was observed**: `O`-3 is empty, no patient id is
  populated, there is no message control id, and the on-screen sequence number is not
  transmitted.
- `R`-13 and the result values differ, but they are **results, not identifiers**.
- **The Sample No. also appears outside `O`-4.** Four graphic-reference `R`-4 values
  (`SCAT_WDF`, `SCAT_WDF-CBC`, `DIST_RBC`, `DIST_PLT`) have the form
  `PNG&R&<YYYYMMDD>&R&<YYYY_MM_DD_HH_MM>_<Sample No.>_<type>.PNG`. In raw evidence these
  paths are therefore **PHI**.
- **Committed fixture re-verified:** in `patient_result_001.astm` all four image-path
  name segments are masked (`XXXXXX`), as declared in `FIELD_REPORT.md` §0.2. No unmasking.

---

## 8. Cross-day comparison — a day-granularity varying field

### 8.1 Observed fact — VERIFIED

Seq 58 (captured 2026-09-17) and 2026-09-16 message A (2 841 B, received four times) are
the same length and differ in **exactly 4 bytes**, at message offsets 2444, 2550, 2656 and
2758. **All four lie in the folder-date component of the four image-path `R`-4 values:
`20260916` in message A, `20260917` in Seq 58.** Every other byte is identical,
including `O`-4, every result value and flag, and `R`-13.

Across every captured message that carries image paths, the folder date equals the
**capture day**, including where the analysis was on an earlier day:

| Message | Analysis date (`R`-13) | Folder date in image paths |
|---|---|---|
| September fixture | 2026-09-15 | `20260915` |
| 2026-09-16 A, B, C, D | 2026-09-16 | `20260916` |
| 2026-09-17 GT-1 / GT-2 (Seq 68) | 2026-09-17 | `20260917` |
| 2026-09-17 Seq 51 | **2026-09-16** | `20260917` |
| 2026-09-17 Seq 58 | **2026-09-16** | `20260917` |
| 2026-09-17 Run03 CORPUS-D18-01, -02 | 2026-09-17 | `20260917` |
| 2026-09-17 Run03 CORPUS-D18-03 … -08 | **2026-09-16** | `20260917` |

**Consequence for earlier documentation.** The 2026-09-16 record stated that the
message format contains "no transmission-varying field whatsoever". **That is
incorrect** and has been corrected there (§8.1, §13, §15, §20 of that record):

- there is **no dedicated** message control id, transmission id, sequence number or
  transmission timestamp field;
- **same-day** controlled retransmission was byte-identical (§6.2);
- a **cross-day** comparison shows a 4-byte difference in the image-path folder date.

### 8.2 Interpretation

**Observed:** in every image-bearing message the folder date equals the day the message
was captured, and in eight messages captured on 2026-09-17 it differs from the analysis
date in `R`-13. It is therefore **not** the analysis date.

**Its semantic meaning is UNKNOWN.** It must **not** be called a transmission date: the
observations are equally consistent with an export, image-storage or other folder date,
and no observation separates these. This record assigns no meaning.

### 8.3 Hypotheses — not facts

- **Message A (2026-09-16) and Seq 58 may be two transmissions of the same analysis
  result.** The shared `R`-13, `O`-4 and result values are consistent with that, but
  message A had no declared operator action and the sequence number is not transmitted.
  **This relationship is a hypothesis and must not be cited as established.**
- The uncontrolled 1 102-byte message of 2026-09-16 carries the same `R`-13 value as
  message A and Seq 58, but has a different record set (no `C`, different result codes,
  no image paths) and an `O`-4 of different length. **Its relationship to either is
  UNKNOWN.**

### 8.4 Constraint recorded, not a design

Exact byte comparison would treat a same-day resend as identical and a cross-day resend
of the same analysis (if the §8.3 hypothesis is true) as different. This is recorded as
an observed constraint on any future identity work. **No deduplication rule, key or
algorithm is proposed**; M9.2 remains blocked on its own BC-5150 evidence.

---

## 9. RECONNECT-01 and RECONNECT-02 — transport session behaviour

Both tests were pre-registered with the statement: *"This is a transport reconnect test;
no inference about ASTM resend/query semantics will be made from absence or presence of
payload unless directly observed."* No result was transmitted during either test.

### 9.1 RECONNECT-01 — LIS-side abortive close

- **Condition.** Session 49706 idle for ~8.5 min. Shell not elevated, so single-connection
  TCB deletion was unavailable; the listener process was force-terminated and a new
  listener instance started ~0.18 s later (no SYN arrived in the gap). The run01 evidence
  files were re-hashed afterwards: unchanged.
- **Observed.** Exactly **one LIS→instrument `RST, ACK`** (11:31:16.088). No FIN from
  either side; no reply frame from the instrument. **No SYN and no new connection for
  5 min 16 s**; no payload. One ARP exchange at 11:31:20.
- **Contrast, not conclusion.** Earlier the same day, with no listener present, the
  instrument dialled every ~60 s.
- **Not established.** Whether the instrument processed the RST; how it detects a dead
  session (no TCP keepalive frames appear in the 2026-09-16 run03 or 2026-09-17
  captures); whether it would reconnect
  after a longer delay or on its next transmission attempt. **This is not evidence that
  the XN-550 cannot reconnect after an RST.**

### 9.2 RECONNECT-02 — physical link interruption

- **Condition.** The network cable (only) was unplugged and the same cable replugged into
  the same ports. The USB-Ethernet adapter stayed attached; Windows settings were not
  changed; capture and listener survived without restart.
- **Observed.**
  - Link down 11:38:30.08, link up 11:41:38.82 — **≈3 min 8.7 s** (500 ms polling of
    Windows adapter state; link changes are not packets).
  - Within ~5 s of link-up the instrument host re-announced itself on the segment (ARP
    probes and announcement, IGMP joins, mDNS/LLMNR, NetBIOS registration).
  - **11:46:49.990: one SYN from `10.0.0.11:49707`**, accepted; handshake complete in
    0.53 ms; **new TCP session established** on the new listener.
  - Source port **49706 → 49707**.
  - **0 application bytes** in the 10 min 7 s after reconnect; session still established
    at the end of observation.

### 9.3 Attribution and status

The reconnect is the **first after both events**: 15 min 34 s after the RST, 8 min 20 s
after link-down, 5 min 11 s after link-up. **It cannot be attributed to either event
alone**, and no reconnect timer or trigger is inferred.

**Hypothesis only:** the source port advanced by exactly one, while earlier dial cycles
advanced it by one per cycle, which would be consistent with no connection attempt
between 10:07:49 and 11:46:49. This depends on the instrument allocating source ports
sequentially and is not established.

**Absence of payload after reconnect is not evidence** about retransmission, buffering,
queue flush, ACK dependence or query capability.

**Status: PARTIALLY VERIFIED** — a reconnect after physical link interruption was
directly observed; its cause is confounded and application-level behaviour after
reconnect remains unknown.

---

## 10. ACK observations

- One `0x06` per **listener read**, never per ASTM message: GT-1 and GT-2 arrived as one
  read each (1 ACK); Seq 51 and Seq 58 arrived as two reads each (2 ACKs, the first sent
  before the message was complete). The instrument showed no visible reaction to either
  pattern.
- Listener-internal receive→ACK latency 0.16–1.03 ms. Wire latency from last data
  segment to the `0x06` frame: 52.15 ms (GT-1), 2.56 ms (GT-2) — host/listener scheduling,
  **not** instrument behaviour, and not interpreted.
- As on 2026-09-16, these timings characterise the listener; **native E1381 handshake
  semantics, ACK-timeout retry and NAK behaviour remain UNVERIFIED**.

---

## 11. Evidence status after this session

| Finding | Label | Evidence | Scope / limitation |
|---|---|---|---|
| One declared selected-result transmit → exactly one message | **VERIFIED** | GT-1, GT-3A-1, GT-3A-2, Run03 8/8 (and 2026-09-16 GT-2) | Selected-result action only |
| Same-day manual retransmission is byte-identical | **VERIFIED** | GT-1 vs GT-2, 0 differing bytes | One controlled pair |
| A day-granularity varying component exists (image-path folder date) | **VERIFIED** | Seq 58 vs 2026-09-16 A: 4 bytes | Semantic meaning **UNKNOWN** |
| 2026-09-16 message A and Seq 58 are the same analysis | **Hypothesis** | Shared `R`-13, `O`-4, results | No declared action for A |
| No dedicated message control id / sequence / transmission timestamp field | **VERIFIED** | `H`-3 empty; sequence absent in 68, 51, 58 | — |
| `H`-5 sender (instrument model/serial) populated | **VERIFIED** | All 9 raw messages across three sessions carry one identical `H` record; populated fields `H`-1, `H`-2, `H`-5, `H`-13 | — |
| `O`-3 empty; `O`-4 = on-screen Sample No. (component 3) | **VERIFIED** | GT-2 (2026-09-16), GT-1/GT-2, GT-3A, Run03 8/8 | — |
| No independent specimen identifier in the message | **VERIFIED** (observation) | GT-3A; Run03 | These captures only |
| `P`-5 population varies between messages | **VERIFIED** (observation) | Run03: populated in 2 of 8, empty in 6; empty or absent in every other 2026-09-16/17 message; populated in the September fixture | **Cause UNKNOWN**; content not characterised |
| `R`-9 = `F`, `R`-11 = `lab`; `R`-6, `R`-8, `R`-12 empty | **VERIFIED** (observation) | Every raw message captured to date | These observations only |
| Sample No. embedded in image-path `R`-4 values | **VERIFIED** | All image-bearing messages | PHI in raw evidence |
| `R`-13 = analysis time | **VERIFIED** (corroborated) | Seq 68: ~6.6 h; Seq 51/58: previous day | — |
| Pending results not auto-transmitted on connection | **CANDIDATE** | run01: ~25 min, 0 bytes; Run03: ~3 min 20 s, 0 bytes, with results still pending | Two observations, the second short; not a rule |
| Corpus message count ≥ 20 (T-CORPUS-01-03) | **MET** | 20 messages across three sessions (§16) | Count criterion only |
| Corpus across categories (T-CORPUS-01-03) | **NOT MET** | Patient results only | QC / calibration / maintenance / startup **not observed** |
| LIS-side RST → no reconnect within 5 min 16 s | **VERIFIED** (observation) | RECONNECT-01 | Not a claim that it cannot reconnect |
| Reconnect after physical link interruption | **PARTIALLY VERIFIED** | RECONNECT-02 | Cause confounded with RECONNECT-01 |
| Application payload after reconnect | **UNKNOWN** | 0 bytes in 10 min 7 s | Absence ≠ capability |

### 11.1 Explicitly UNVERIFIED or NOT OBSERVED after this session (including Run03)

- **Genuine same-specimen rerun** — UNVERIFIED (not testable; GT-3A and Run03 are not reruns).
- **Instrument-initiated disconnect** behaviour — UNVERIFIED.
- **ACK-timeout retry** and **NAK** behaviour — UNVERIFIED.
- **Query / pull semantics** (LIS-initiated request for results) — UNVERIFIED.
- **Queue flush / send-all** behaviour — UNVERIFIED.
- **QC, calibration, maintenance and startup message classes** — **NOT OBSERVED** (zero captures).
- Cross-day retransmission identity as a rule; meaning of the image-path folder date — UNKNOWN.
- Cause of `P`-5 population differences — UNKNOWN.

---

## 12. Relation to T-CONN-01-03 and T-CORPUS-01-03

**T-CONN-01-03.** Adds controlled reconnect observations (§9, PARTIALLY VERIFIED) and a
second session confirming role, endpoint, framing and persistent-session behaviour. The
inbound-on-other-ports gap from 2026-09-16 §5.2 is unchanged. **Not marked complete.**

**T-CORPUS-01-03 — target ≥20 raw messages across categories.** The test has two
separate criteria, and they are recorded separately:

| Criterion | Status | Basis |
|---|---|---|
| Message count ≥ 20 | **MET** | 20 messages: 1 (2026-09-15) + 7 (2026-09-16) + 4 (run01) + 8 (Run03) — §16 |
| Across relevant categories | **NOT MET** | Patient results only; QC, calibration, maintenance and startup **not observed** |

**T-CORPUS-01-03 is therefore NOT satisfied.** Before Run03 the count was 12 messages and
8 distinct patient-result payloads.

---

## 13. Documentation corrections made with this record

1. **2026-09-16 record §8.1, §13, §15, §16, §20** — the "no transmission-varying field
   whatsoever" statement is replaced by the §8.1 wording above.
2. **`H`-field wording** — "`H`-3 … `H`-12 empty" is corrected in the 2026-09-16 record
   and `README.md`: `H`-3 (message control id) is empty; `H`-5 (sender / instrument
   information) is populated; `H`-4 and `H`-6 … `H`-12 are empty.
3. **`R`-field numbering.** The 2026-09-16 record §7.2 and `README.md` §8.1 numbered `R`
   fields from the first field *after* the record type (one lower than ASTM), while §9 of
   the same record used ASTM numbering for `R`-13. The 2026-09-16 record §7.2 is corrected
   to ASTM numbering. `README.md` §8.1 keeps the contract test's convention, now stated
   explicitly with ASTM equivalents, because the test module's docstrings use it and this
   reconciliation changes documentation only.

---

## 14. Safety, privacy and repository boundary

- All raw PHI-bearing evidence remains in `D:\SurveyLIS\evidence\2026-09-17\`. No payload,
  hex dump, name, Sample No. value or patient identifier was copied into the repository.
- No redacted derivative was created; the committed fixture is unchanged and its masking
  was re-verified (§7.3).
- No production parser was written or registered; the registry remains `{bc5150_hl7}`.
- No schema, migration, transport, configuration or frontend change; no database was
  contacted — `lis_marina_permata` was not touched.
- No ACK withheld, no NAK sent, no instrument configuration changed, no send-all used.
- Run03 followed the same boundary: raw messages, notes and pcaps stay in the evidence
  root; the repository was not modified during capture.

---

## 15. Run03 — corpus expansion after the break

### 15.1 Purpose and setup

**Purpose:** expand the raw XN-550 corpus toward T-CORPUS-01-03's ≥20 messages, preferring
genuine variation. **Not** a rerun, retransmission, reconnect, QC, calibration, ACK-timeout
or NAK test. No synthetic, modified or replayed payload was used.

| Item | Observed |
|---|---|
| Evidence directory | `run03_corpus/` — new; run01 and run02_reconnect untouched (re-verified by hash) |
| Self-test | Passed 14:20:03 (1 044 B, all 256 values, SHA-256 identical) |
| Capture | Started 14:20:11 with the cable still disconnected, so the link-up was captured |
| Listener | Fresh instance on `0.0.0.0:5001`, 14:20:31, ACK-on-receive, never NAK |
| Link / session | Cable reconnected by the operator; link 14:23:04; one SYN from `10.0.0.11:49737` at 14:23:49.927. **One TCP session carried all eight messages**; no reconnect during the run |
| Adapter | Same USB-Ethernet adapter, stable for the whole run |
| Before the first transmit | 0 payload bytes from session establishment (14:23:49.927) to CORPUS-D18-01 (14:27:10.546), ~3 min 20 s, while the analyst's earlier-listed pending results were still untransmitted |
| Uncontrolled payload | None during the run |

The session after cable reconnection is **operator setup, not reconnect evidence**. Recorded
as facts only: link-up to SYN ≈ 46 s (versus 5 min 11 s in RECONNECT-02), and a source port
30 higher than the previous session's. This does not change the §9.3 hypothesis status.

### 15.2 Ground-truth procedure

- **Operator ground truth:** before each transmit, the on-screen Sequence and Sample No.
  were relayed and written to the external notes, with the action "transmit selected result
  exactly once" and "normal transmission, not a rerun or retransmission test". Values are PHI
  and stay in the evidence root.
- One message was armed at a time; the next was armed only after the previous message had
  been captured, hashed and recorded, and after a 45 s quiet window.
- **Pre-arm check:** each proposal was compared against every earlier raw message. **Two
  proposals were not armed:** Seq 61, whose Sequence and Sample No. match the 2026-09-16
  controlled observation GT-2; and Seq 60, whose relayed Sample No. is contained in the `O`-4
  of 2026-09-16 uncontrolled message C behind a 3-character prefix. **That Seq 60 corresponds
  to message C is a hypothesis only.** Neither was transmitted.

### 15.3 Messages captured — observed facts

All eight are **controlled**: one declared action, exactly one message, `O`-4 component 3
exactly equal to the declared Sample No., and not byte-identical to any earlier capture.

| Corpus ID | Seq | Arrival | Bytes | SHA-256 | Records / `R` | Image paths | `R`-13 date | Reads / ACKs |
|---|---|---|---|---|---|---|---|---|
| CORPUS-D18-01 | 67 | 14:27:10.546 | 2 822 | `b122b9060b9fa0f36dd27639b303be3673867c9863e217831232668313c199ed` | 49 / 42 | 4 | 2026-09-17 | 1 / 1 |
| CORPUS-D18-02 | 66 | 14:31:11.385 | 2 924 | `8de477467ed29aa6683fb1c7e9fba7d7bbf384cd7240fe2a1bb312dc746c8e33` | 50 / 44 | 4 | 2026-09-17 | 2 / 2 |
| CORPUS-D18-03 | 65 | 14:33:37.009 | 2 922 | `c90a4444efcf8d80bf117a48a92188e3830825223e5142bf9cf314f3467cd790` | 50 / 44 | 4 | 2026-09-16 | 1 / 1 |
| CORPUS-D18-04 | 64 | 14:36:42.702 | 3 126 | `2375e9e7d9b47cfa23f6fb6ebf428a15cca5fd2b1d23a1dec5b3f2388f868942` | 55 / 48 | 4 | 2026-09-16 | 2 / 2 |
| CORPUS-D18-05 | 63 | 14:38:48.191 | 2 978 | `e51e6cf37b6de4c1ce5db81d230019d6842b50266f57cecbe0a3e9f3232c14a4` | 51 / 45 | 4 | 2026-09-16 | 2 / 2 |
| CORPUS-D18-06 | 62 | 14:40:47.705 | 2 871 | `7d122297e9b831f33d7b6c5977fef6fb1f35f2d80dd4ba583987babeb011d97a` | 50 / 43 | 4 | 2026-09-16 | 2 / 2 |
| CORPUS-D18-07 | 57 | 14:47:52.123 | 1 860 | `d114317c716eee49cc9bbdb07fce41d30fb3fd4fc93c4ce9fe41822b8d2ee755` | 33 / 27 | 3 | 2026-09-16 | 1 / 1 |
| CORPUS-D18-08 | 56 | 14:50:46.846 | 3 044 | `eef24ff22ca33068f3f1f43492c203fdfe3d8ce95696d9ad5b71e370d4f07207` | 52 / 46 | 4 | 2026-09-16 | 2 / 2 |

Every message has the order `H P C O C R… C L`, bare `CR` terminators, no `LF`, no E1381
control bytes, and the payload reassembled from the pcap equals the listener's bytes.

### 15.4 Field variation — observed facts

| Aspect | Observed across the eight messages |
|---|---|
| Size | 1 860 – 3 126 B |
| `R` count | 27 – 48 |
| Panel | 7 with differential parameters (38 numeric `R`-4 values, 4 image paths); 1 without (22 numeric values, 3 image paths, no `SCAT_WDF`) |
| Interpretive flag records | Vary by message; codes new to the corpus: `Monocytosis`, `Lymphocytosis`, `Anisocytosis`, `Microcytosis`, `Anemia`, `PLT_Abn_Distribution` |
| `R`-7 abnormal flag values | `N`, `H`, `L`, `A`, `W`, blank |
| `R`-4 shapes | Numeric values, image paths, and empty values on some flag records |
| `P` | `P`-2 = `1`, `P`-9 = `U` in all; **`P`-5 populated in 2 of 8 (Seq 67, 66), empty in 6 — cause UNKNOWN** |
| `O` | `O`-3 empty in all; `O`-4 component 3 padded with 12–16 leading spaces; `O`-4 component 4 = `M` in all |
| `R`-9 / `R`-11 | `F` / `lab` in all |
| `R`-6, `R`-8, `R`-12 | Empty in all |
| `R`-13 | One value per message; 6 analysed 2026-09-16, 2 analysed 2026-09-17 |
| Image-path folder date | `20260917` in all eight, including the six analysed on 2026-09-16 (§8.2: meaning UNKNOWN) |
| Sequence number | Not present as any field in any of the eight |
| `H` record | Identical to every earlier capture |
| TCP | 2–3 segments per message; 1–2 listener reads; one ACK per read |

### 15.5 Comparison with earlier captures

- **Byte identity:** none of the eight equals any earlier raw message.
- **Structure** (record order plus `R` test-code list) is shared with earlier captures for three
  of them: CORPUS-D18-01 with 2026-09-16 A and D, 2026-09-17 Seq 58 and the September fixture;
  CORPUS-D18-06 with 2026-09-17 Seq 51; CORPUS-D18-07 with 2026-09-16 message C. The other five
  structures are new.

### 15.6 Interpretation limits

Run03 is corpus evidence only. It establishes **nothing** about genuine rerun behaviour,
specimen identity (Sample No. and patient name are operator-entered text), deduplication keys,
query/pull capability, queue flush or send-all, or ACK dependence. The sequence number is not
treated as a specimen identifier. No production design follows.

### 15.7 Close

Listener terminated at 14:52:33.409 while idle, producing one LIS-side `RST, ACK` on 49737
(frame 117); capture stopped by 14:52:41.266. The teardown frames are operator shutdown, not
evidence. All 24 Run03 files were hashed (`run03_corpus_final_hashes.sha256`) and re-verified.

---

## 16. Cumulative XN-550 corpus status

| Measure | Value | Composition |
|---|---|---|
| Raw patient-result messages | **20** | 1 (2026-09-15 survey) + 7 (2026-09-16: A ×4, B, C, D) + 4 (2026-09-17 run01: GT-1, GT-2, Seq 51, Seq 58) + 8 (Run03) |
| — from pre-registered controlled actions | 13 | 2026-09-16 GT-2 (D); run01 4; Run03 8 |
| — not pre-registered (survey / natural observations) | 7 | 2026-09-15 survey message; 2026-09-16 A ×4, B, C |
| Distinct patient-result payloads | **16** | Repeated deliveries (A ×4) and the same-day retransmission (GT-2 = GT-1) counted once |
| Distinct structures | **10** | Record order plus `R` test-code list |
| Outside the corpus | 1 | The uncontrolled 1 102-byte message of 2026-09-16, class UNKNOWN |
| QC / calibration / maintenance / startup | **0** | **Not observed** |

Seq 58 and 2026-09-16 message A differ by only 4 bytes (§8) and are counted as distinct
payloads by bytes; whether they are the same analysis remains a hypothesis.

**T-CORPUS-01-03:** message-count criterion **MET**; category criterion **NOT MET**;
test **not satisfied** (§12).
