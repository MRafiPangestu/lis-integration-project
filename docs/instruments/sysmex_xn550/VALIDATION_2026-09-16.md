# Sysmex XN-550 Physical Validation — 2026-09-16

Session record for the second XN-550 field session. The first was the survey of
15 September 2026, recorded in [`FIELD_REPORT.md`](FIELD_REPORT.md); the standing
engineering summary is [`README.md`](README.md).

Evidence labels are those defined in `../../09_PHYSICAL_INSTRUMENT_VALIDATION.md` §2
and are used here without extension: **VERIFIED · CANDIDATE · UNVERIFIED · UNKNOWN**.
Capture, repetition and redaction rules are §12 of that document and are not restated here.

---

## 1. Session metadata

| Item | Value |
|---|---|
| Session date | **2026-09-16** (site local, UTC+08:00) |
| Instrument | Sysmex XN-550 (`id_instrument = 3`) |
| Instrument endpoint observed | `10.0.0.11`, MAC `74:fe:48:a9:dc:34` (Advantech OUI) |
| LIS host endpoint observed | `10.0.0.10`, MAC `00:e0:4c:14:41:48` (Realtek), interface `Ethernet` |
| TCP port | **5001** |
| Repository branch | `refactor/orm-architecture` |
| Starting commit | `2852961` — *test(xn550): add field-verified ASTM contract* |
| Evidence root | `D:\SurveyLIS\evidence\2026-09-16\` |
| PHI | **All raw evidence is PHI-bearing and remains outside the repository.** No raw capture, payload or identifier value is reproduced in this document |

Capture tooling: `tshark` (Wireshark) for the wire layer, and a purpose-built
byte-exact listener `D:\SurveyLIS\astm_raw_capture.py` (outside the repository) for
the application layer. The listener's byte fidelity was proven by loopback self-test
before use — 1 044 bytes covering all 256 byte values, SHA-256 identical, NUL and
high bytes preserved.

---

## 2. Scope and objective

The session set out to validate: transport role; TCP session behaviour; wire and
application framing; normal ASTM message structure; identifier and timestamp
behaviour; multiple messages per connection; controlled transmission behaviour;
retransmission-related observations; disconnect/reconnect where a valid observation
could be made; ACK behaviour; and QC/calibration/startup traffic if naturally
available.

### 2.1 Relationship to the BC-5150 blockers — read this before citing anything below

**This session does not close any M9.2 or M9.3b blocker.** Those blockers are
defined in `../../07_TASK_LIST.md` by **BC-5150 test IDs** — M9.2 on T-BC-B, D, E,
F, I, R and T-ID-02; M9.3b on T-BC-K (×2, different days), L, M, N and H. Each is by
definition an observation of the **Mindray BC-5150**. No amount of XN-550 evidence
can discharge them.

XN-550 work is tracked separately as **T-CONN-01-03** and **T-CORPUS-01-03** (§17).
What this session produces is a second-instrument evidence base that may later
*inform* M9.2 and M9.3 design, exactly as the §13 matrix anticipates — not evidence
that closes them.

### 2.2 Explicitly not performed

No ACK was withheld; no NAK was sent; no reconnect, disconnect or timeout experiment
was initiated; no protocol interference of any kind occurred. No production parser
was written or registered, no schema, migration, transport or frontend code was
touched, and no database was contacted.

---

## 3. Evidence inventory

Every artefact below is **PHI-bearing unless marked otherwise** and therefore lives
outside the repository, under the evidence root in §1.

| File (relative to evidence root) | Description | Size | SHA-256 | Role | PHI |
|---|---|---|---|---|---|
| `session_2026-09-16_xn550.pcapng` | run01 wire capture | 4 984 | `04bf6a27d699f52b462d96aa3c3c907d7d36e3c72a9184d2344c839d459de12f` | Transport-role evidence; instrument dial pattern; LIS dial attempt | No — no payload captured |
| `session_2026-09-16_xn550_run02.pcapng` | run02 wire capture | 2 076 | `6d363651cafe6ead4f5ed3bb53df9ce7a5f2369b0e7fac0c40e1866815252492` | Contains the uncontrolled transmission and its RST | **Yes** |
| `session_2026-09-16_xn550_run03.pcapng` | run03 wire capture (frozen) | 22 644 | `46c44b5426e029b8794ed30ccc6af7ee77755df10093371ee1fc4b3bfc91a3f5` | Main session: TCP behaviour, segmentation, ACK timing | **Yes** |
| `P1a_lis_dials_instrument_manifest.jsonl` | LIS→instrument dial result | 172 | `bc57854334dff2ba07b2e491183b60f71f8abced5ad152fc5b7601c66f5150ff` | Transport-role evidence | No |
| `P1b_P2_normal_tx_manifest.jsonl` | run01 connection record | 368 | `2fbfd26968a5053b7258f3e5328f7c746ed7f4e1c1c34c119431051249aaf36f` | Idle-session evidence; 0 bytes exchanged | No |
| `P1b_P2_normal_tx_conn01_events.jsonl` | run01 connection events | 572 | `737f1c63b4ca15c032caec1a1146b9ce2af9c5342755513f2c73e96f8ec701a7` | Timing of connection open/close | No |
| `selftest_conn99_rx.bin` | Loopback fidelity payload | 1 044 | `e4f408a4229126f9314efc8a573ccfa66a82e6d358c73ef25e75d7f2afc9e48f` | Proves listener byte fidelity | No — synthetic |
| `selftest_conn99_events.jsonl` | Loopback self-test events | 920 | `e4a9adc15eb49fe926d26483faaf83237fbc74cf1b14fb17f9d87486143e6877` | Self-test record | No |
| `selftest_manifest.jsonl` | Loopback self-test manifest | 338 | `7d17f4c967480a806af5ddb95cbe135848490aa0365535cd37b19fdcca01b89a` | Self-test record | No |
| `run02/run02_conn01_rx.bin` | **Byte-exact application stream, run03 window** | 17 817 | `faae28bbdaa962d050944e66237f74ee90a74d5185ba8d925def4ed63e64c0f3` | Authoritative payload record — all 7 messages | **Yes** |
| `run02/run02_conn01_events.jsonl` | Per-read rx/tx events with hashes | 5 886 | `640561798a6e3f24bab7b44ff1f1302f142aa575e4f665cf5326d5f858b86b29` | ACK timing, message chronology | No — metadata only |
| `run02/rst_lost_transmission_001.astm` | **Uncontrolled natural observation** | 1 102 | `f610615e7212667e47c6d42db7964a5a97add3ae886c1ef697a66eb4037593f6` | Recovered from run02 pcap after RST | **Yes** |
| `run02/payload_hex.txt` | Hex form of the above | 2 205 | `fcc1eaa3c3a9342a27e569b67070f2b4ccebb1fc3d32feace37d9ac20416b271` | Extraction intermediate | **Yes** |
| `run02/run03_msg_A.astm` | Distinct message A | 2 841 | `11ae7c0cdc552ce1a88646b77601540a7df959ccedcbb56df0d6ab794ef36383` | Received 4× byte-identically | **Yes** |
| `run02/run03_msg_B.astm` | Distinct message B | 1 766 | `9deeb8ce54727345943e54c0150147b8b914dcbc070a399bef2498327f15f52a` | Received once | **Yes** |
| `run02/run03_msg_C.astm` | Distinct message C | 1 864 | `55007a54bf0bbfba049c0387540184b4174b7a77ec484e29795a8a361957da8e` | Received once | **Yes** |
| `run02/run03_msg_D_gt2.astm` | **Controlled observation GT-2** | 2 823 | `d22e0d552790b466cfbe05ef94604d4e7031a947e056d2d22c0e2bdb6cca5bd6` | The pre-registered controlled transmission | **Yes** |
| `run02/run03_messages_manifest.json` | Sequence → distinct-id → hash map | 921 | `df3ee0be7fa4d3f3ef77f924b30ece0106c3415237c4df5a4c4c268792f0afe5` | Message ordering record | No |
| `run02/GROUND_TRUTH_operator_notes.md` | Operator ground truth GT-1, GT-2 | 5 690 | `6586ac481bae51e9ebfce122fe20f4f6ea8b87659c2f44244d7b63ac649d25fa` | Pre-registered declarations | **Yes** |
| `run02/selftest_*` (3 files) | Second loopback self-test, run03 window | 1 044 / 1 616 / 338 | `e4f408a4…` / `8074fb28…` / `70574b20…` | Re-proves fidelity before run03 | No — synthetic |

**Filename note.** The GT-2 artefact was originally written with the operator-entered
Sample No. embedded in its filename. It was **renamed** to `run03_msg_D_gt2.astm` to
keep that identifier out of any path this document references. **Content is unchanged
and verified byte-identical** — SHA-256 `d22e0d5527…` before and after.

---

## 4. Session chronology

All times site local (UTC+08:00), taken from the preserved artefacts.

| Time | Event | Classification |
|---|---|---|
| 14:55 | Evidence directory created | Pre-flight |
| 14:56:02 | Byte-exact listener authored | Pre-flight |
| 14:56 | Loopback self-test **PASSED** — all 256 byte values preserved | Pre-flight |
| 14:56:38 | **run01 capture started — before any instrument contact** | Pre-flight |
| 14:57:14.153 | First packet: instrument SYN to `10.0.0.10:5001`, refused (nothing listening) | **Uncontrolled — passive** |
| 14:57–15:00 | Instrument dial pattern recorded: 5 SYNs at ~508 ms, source port incrementing, cycle repeating ~60 s | **Uncontrolled — passive** |
| 14:59:03.838 | **LIS→instrument dial on port 5001: `TimeoutError`** — no SYN-ACK, no RST | **Controlled** |
| 15:00:14.166 | Listener opened; instrument connected immediately; **0 payload bytes** | Controlled |
| ~15:00:14 | **Ethernet adapter removed from the system; run01 capture stopped** (49 packets) | Environmental |
| 15:01:55.046 | Listener socket closed, `WinError 10054`, rx 0 / tx 0 bytes | Environmental artefact |
| 15:49:58 | run02 capture started | Pre-flight |
| 15:51 | run01 listener stopped to rotate to a clean session | Operator/engineering |
| 15:56:21.714 | **Instrument pushed 1 102 bytes onto the now-closed socket; host replied RST** | **UNCONTROLLED NATURAL OBSERVATION** |
| ~15:56:26 | Adapter removed again (LAN cable handling); run02 capture stopped (6 packets) | Environmental |
| ~15:58 | Ethernet restored, `10.0.0.10` and ARP to `10.0.0.11` healthy | Pre-flight |
| 15:59:14.258 | Instrument reconnected; session `10.0.0.11:50257` established | — |
| 16:03:19 | **run03 capture started** | Pre-flight |
| 16:11:45.258 | Message **A** received (2 841 B) | **Uncontrolled — operator action undeclared** |
| 16:12:13.350 | Message **A** received again, as 2 TCP segments | **Uncontrolled** |
| 16:12:33.844 | Message **A** received again | **Uncontrolled** |
| 16:13:44.716 | Message **A** received again, as 2 TCP segments | **Uncontrolled** |
| 16:13:48.396 | Message **B** received (1 766 B) | **Uncontrolled** |
| 16:13:52.049 | Message **C** received (1 864 B) | **Uncontrolled** |
| ~16:24:02 | Specimen for GT-2 analysed on the instrument (from its own `R`-13 timestamp) | — |
| before 16:40 | **GT-2 pre-registered**: sequence, Sample No., "transmit this selected result once", explicitly not send-all | **Controlled — declared in advance** |
| 16:40:45.551 | Message **D** received (2 823 B) — exactly one message | **CONTROLLED OBSERVATION GT-2** |
| 16:40:50.215 | Last packet in run03; capture frozen for documentation (51 packets) | — |

The environmental adapter losses were caused by physical LAN cable/adapter handling
at the site, confirmed by Windows reporting the `Ethernet` adapter absent entirely
rather than merely disconnected. They were **not** instrument behaviour and are not
treated as reconnect evidence (§5.5).

---

## 5. Transport validation

### 5.1 Instrument initiates the connection — VERIFIED

The XN-550 autonomously dials `10.0.0.10:5001` with no prompting. When the port is
closed it emits **5 SYNs at ~508 ms spacing**, then backs off and repeats the cycle
approximately every **60 s**, incrementing its source port each cycle
(50252 → 50253 → 50254 → 50255). *Evidence:* `session_2026-09-16_xn550.pcapng`,
frames 1–24, 35–44; reproduced at 15:59:14 after the cable was restored.

### 5.2 LIS cannot dial the instrument on port 5001 — VERIFIED, scope-limited

Four SYNs from `10.0.0.10:51714` to `10.0.0.11:5001` at t = 101.7 / 102.7 / 104.7 /
108.7 s (standard 1 s / 2 s / 4 s backoff) received **no response of any kind** —
neither SYN-ACK nor RST. The SYN is silently dropped. *Evidence:*
`session_2026-09-16_xn550.pcapng` frames 29–34; `P1a_lis_dials_instrument_manifest.jsonl`.

**Scope limitation, stated explicitly.** This establishes only that the instrument
does not accept inbound TCP **on port 5001**, in **this configuration**. It does
**not** establish that the XN-550 is client-only, nor that it refuses inbound
connections on any other port. **No port scan was performed** — it was neither
authorised nor appropriate on a clinical device. Whether the instrument can act as a
server on some other port is **UNKNOWN**.

### 5.3 Stop condition S7

`../../09_PHYSICAL_INSTRUMENT_VALIDATION.md` §14 **S7** — *"An instrument requires
the LIS to listen (server mode). Stop; this is an architecture decision, not a
configuration change."*

**S7 is met for this instrument in this configuration.** The XN-550 connects
outbound and does not answer inbound on the configured port; the LIS supports
`SUPPORTED_INSTRUMENT_MODES = {"client"}` only. **Recorded, and stopped there** — no
listener-mode design, transport change or configuration change was made or is
proposed by this document.

### 5.4 Persistent session and multiple messages per connection — VERIFIED

A single TCP session `10.0.0.11:50257 ↔ 10.0.0.10:5001`, established **15:59:14**,
carried **all seven ASTM messages** and was still open when the capture was frozen at
16:40:50 — **41 minutes**, with no SYN, FIN or RST in between. *Evidence:*
`session_2026-09-16_xn550_run03.pcapng` (51 packets, no SYN after 15:59:14);
`run02/run02_conn01_events.jsonl`.

The instrument also holds the session **idle indefinitely with zero payload** and no
observed heartbeat: at 15:00:14 it connected and exchanged 0 bytes before the
environmental disconnect (`P1b_P2_normal_tx_manifest.jsonl`, `rx_bytes: 0`,
`tx_bytes: 0`). This differs from the BC-5150, which emits `0x02` idle heartbeats
(`../../09_PHYSICAL_INSTRUMENT_VALIDATION.md` §11.2).

### 5.5 Reconnect was NOT tested — UNVERIFIED

The instrument did reconnect after each cable event, but **those events were caused
by physical cable/adapter handling at the site, not by a controlled instrument
disconnect**. The `WinError 10054` at 15:01:55 is an artefact of the adapter
disappearing beneath an open socket, **not** an observation of instrument behaviour.

No controlled disconnect/reconnect experiment was performed. Buffering across an
outage, resend-on-reconnect and idle-socket timeout all remain **UNVERIFIED**.

---

## 6. Wire and application framing

### 6.1 What the payloads contained — VERIFIED for this configuration

Across **all seven messages** captured today, plus the uncontrolled 1 102-byte
message and the September fixture:

- Records are terminated by **bare `CR` (`0x0D`)**. No `LF` appears anywhere.
- Field `|`, repeat `\`, component `^`, escape `&` — as declared in `H`-2.
- **No `STX`, `ETX`, `ENQ`, `EOT`, `ACK`, `NAK`, `ETB`, frame numbers or checksums
  appear in any observed application payload.**

*Evidence:* `run02/run02_conn01_rx.bin` and the four extracted message artefacts;
byte census recorded per read in `run02/run02_conn01_events.jsonl`.

**Scope limitation.** This is observed behaviour for **this instrument, in this ASTM
output configuration, in these two sessions**. It must not be generalised into
"the XN-550 never uses ASTM E1381 framing". The instrument menu presents
`ASTM1381-95 / ASTM1394-97` as a single selection, and other configurations were not
tested. The absence of framing under a different setting is **UNKNOWN**.

### 6.2 TCP segmentation is not message structure — VERIFIED

Message boundaries and TCP segment boundaries are independent. The same 2 841-byte
message arrived once as a single read and, on other occasions, as two segments
(1 460 + 1 381). The 2 823-byte GT-2 message arrived on the wire as two segments
(1 460 + 1 363) which the receiver coalesced into **one** `recv()`.

Any future parser must reassemble on the **ASTM record/terminator layer**, never on
socket-read boundaries.

### 6.3 The observed ACK is application-level only — important limitation

The listener replied with a single `0x06` byte per **socket read**, replicating the
September prototype's behaviour. This is **not** ASTM E1381 handshake semantics: a
real E1381 exchange acknowledges validated *frames* with checksums, within an
`ENQ`/`ACK`/`EOT` session.

Consequently the ACK timings in §11 characterise **our listener**, not the
instrument's native protocol handling. Nothing in this session establishes how the
XN-550 implements or depends on E1381 acknowledgement.

---

## 7. Observed message structure

All messages share the record grammar `H → P → C → O → C → R… → C → L`, with `C`
(comment) records positioned after `P`, after `O`, and after the final `R`.

| Message | Bytes | Records | H | P | C | O | R | L | Note |
|---|---|---|---|---|---|---|---|---|---|
| **A** | 2 841 | 49 | 1 | 1 | 3 | 1 | 42 | 1 | Received 4× byte-identically |
| **B** | 1 766 | 32 | 1 | 1 | 3 | 1 | 25 | 1 | Received once |
| **C** | 1 864 | 34 | 1 | 1 | 3 | 1 | 27 | 1 | Received once |
| **D** (GT-2) | 2 823 | 49 | 1 | 1 | 3 | 1 | 42 | 1 | Controlled observation |
| *Uncontrolled* | 1 102 | 20 | 1 | 1 | **0** | 1 | **16** | 1 | See §7.1 |
| September fixture | 2 824 | 49 | 1 | 1 | 3 | 1 | 42 | 1 | For comparison |

`R` counts vary by specimen (16, 25, 27, 42). A, B, C and D are **byte-distinct from
one another** and from the uncontrolled message.

### 7.1 The uncontrolled 1 102-byte message differs structurally

Two differences set it apart from every other message observed:

- it contains **no `C` records at all**, where all others contain exactly three;
- its `P` record has **only 2 fields** (`P|1`), against 26 fields elsewhere.

It is nonetheless a complete, well-formed message: it begins `H` and ends `L|1|N\r`.
**What it represents is UNKNOWN.** It may be a different message class, a different
instrument state, or a different output path. Nothing here classifies it, and it must
not be treated as a patient-result exemplar without further evidence.

### 7.2 `R` record shape

In message D: all 42 `R` records carry a uniform 13 fields; `R`-1 runs 1…42
contiguously; `R`-8 (status) is `F` for every record; `R`-10 is a constant operator
string. `R`-5 (reference range) is empty on every result — consistent with the
September fixture. A future parser must not fabricate a reference range for this
instrument.

---

## 8. Identifier and ground-truth findings

Field numbering below is **ASTM 1-based**, consistent with
[`README.md`](README.md) §5.1 and [`FIELD_REPORT.md`](FIELD_REPORT.md) §3.2.

### 8.1 No transmission or message control identifier — VERIFIED

`H`-3 through `H`-12 are **empty in every message observed**: the four run03
messages, the uncontrolled message, and the September fixture — **seven independent
messages**. Only `H`-1, `H`-2, `H`-5 (instrument identification) and `H`-13 (version)
carry values.

The instrument transmits **no message control id, no transmission id and no sample
sequence number**. There is no MSH-10 analogue.

### 8.2 `O`-3 empty; `O`-4 carries the operator-entered Sample No. — VERIFIED

`O`-3 — the ASTM specimen-identifier field — is **empty in every message observed**.
`O`-4 is populated in every message.

**GT-1 → GT-2 confirmation.** Before transmission, the operator declared the
on-screen **Sample No.** value for the GT-2 specimen. In the resulting message,
**`O`-4 component 3, after stripping its space padding, matched that declared value
exactly.** Because the value was registered *before* the bytes arrived, this is a
genuine confirmation rather than a post-hoc fit.

The mapping **on-screen "Sample No." → ASTM `O`-4, component 3** is therefore
**VERIFIED** for this instrument and configuration. `O`-4 also carries a trailing
component whose meaning is **UNKNOWN** (present in September too).

### 8.3 Operator practice: Sample No. holds a personal name — CANDIDATE

The site operator reported that this laboratory's habit is to type a **patient name**
into the instrument's Sample No. field rather than a specimen number, and the GT-2
capture is consistent with that. The September capture likewise carried a personal
name in `O`-4.

**Status CANDIDATE, deliberately.** One laboratory, one operator, one reported habit,
two sessions. Whether the practice is universal, permanent or applied by every
analyst is **UNKNOWN**.

**Why it matters — potential S1 hazard, not a conclusion.** If the specimen field
carries a patient name, two different specimens from the same patient would present
identical `O`-4 values, and no other distinguishing identifier exists in the message
(`O`-3 empty, `P`-5 empty, no control id). The current ingestion path derives
`no_registrasi` from the specimen field and keys the **Visit** on it, which is the
condition `../../09_PHYSICAL_INSTRUMENT_VALIDATION.md` §14 **S1** describes as a
clinical-safety stop. **No collision has actually been observed**, so S1 is recorded
here as a hazard to test, not as a triggered stop condition. It is a mandatory
consideration for any future XN-550 parser or identity mapping.

### 8.4 `P`-field population is inconsistent across sessions — VERIFIED observation

| Capture | `P`-5 (patient id) | `P`-8 |
|---|---|---|
| September fixture | populated | populated |
| Messages A, B, C, D (today) | **empty** | **empty** |
| Uncontrolled 1 102-byte | field absent — 2-field `P` record | — |

This is the condition §14 **S5** concerns (identifier inconsistently populated for
genuine patient work). Recorded as an observation; the *cause* — configuration
change, operator workflow, or message class — is **UNKNOWN**.

### 8.5 The pre-registered sequence identifier is not transmitted — VERIFIED

GT-2 pre-registered the sequence number shown on the instrument screen. **That value
appears nowhere in the transmitted message as a field.** The two-character substring
occurs only incidentally inside the `R`-13 timestamp; no field anywhere holds it as a
value. `O`-2 and `P`-2 are both `1` — ASTM intra-message sequence numbers, unrelated
to the instrument's on-screen sample sequence.

This is a significant **negative** finding: an on-screen sequence number would have
been the dedup-key candidate the message otherwise lacks, and it is not sent.

### 8.6 Observed population versus semantic meaning

Everything in §8 records **which fields are populated** and, for `O`-4 alone, a
**confirmed mapping to an on-screen field**. No clinical semantics are assigned. It
remains **UNKNOWN** what `P`-5 would contain if the laboratory used it, what `O`-3 is
intended to hold, and what the trailing `O`-4 component means.

---

## 9. Timestamp findings

### 9.1 One shared timestamp per message — VERIFIED

In message D all 42 `R` records carry an identical 14-character `R`-13 value. The
same single-value behaviour holds for A, B, C and the September fixture.

### 9.2 `R`-13 is analysis time, not transmission time — VERIFIED

Message D's `R`-13 corresponds to **16:24:02**. The message was received at
**16:40:45** — a gap of approximately **16½ minutes**. `R`-13 therefore records when
the specimen was analysed, and is unaffected by when the result is transmitted.

*Evidence:* `run02/run03_msg_D_gt2.astm` `R`-13 value; arrival time in
`run02/run02_conn01_events.jsonl` and `session_2026-09-16_xn550_run03.pcapng`.

### 9.3 Limitation

Because `R`-13 is fixed at analysis time, a resend of the same result carries an
identical timestamp — consistent with message A arriving four times byte-identically.
Whether a **genuine repeat run** of the same specimen produces a *different* `R`-13
is **UNVERIFIED**: no rerun was performed. That distinction must not be assumed.

---

## 10. Multiple-message and session findings

- **One persistent TCP session carried seven ASTM messages** over 41 minutes with no
  reconnection — VERIFIED (§5.4).
- In the uncontrolled portion of run03, **six complete messages** were received,
  comprising **three distinct payloads**: A (×4), B (×1), C (×1).
- **Message A was received four times, byte-identical every time** — same SHA-256
  `11ae7c0cdc55…`, no field differing anywhere.
- The controlled GT-2 action — **one transmit of one selected result** — produced
  **exactly one** ASTM message.

### 10.1 The four deliveries of A are *repeated byte-identical deliveries*

They are **not** labelled retransmissions, reruns or duplicates. No operator action
was declared for them at the time, so their cause is **UNVERIFIED**. Candidate
explanations — four separate operator transmit actions, instrument-side retry, or a
queue/batch behaviour — are not distinguishable from the bytes alone.

What GT-2 *does* establish is a constraint: since one selected-result transmit
produces exactly one message, the four deliveries of A were **four distinct delivery
events**, not one action amplified by the instrument into four. What triggered each
of those four remains unknown.

Inter-arrival gaps were 28.1 s, 20.5 s and 70.9 s, with B and C following 3.7 s apart
— recorded as fact, interpreted as nothing.

---

## 11. ACK observations

- **Baseline used:** ACK-on-receive, a single `0x06` byte, replicating the September
  prototype. This was chosen deliberately as the behaviour empirically known not to
  disrupt this instrument.
- **Observed:** every receive was followed by one `0x06`. Latencies ranged
  **0.34 – 1.71 ms** (mean ≈ 0.93 ms) across the uncontrolled messages; the GT-2
  message was acknowledged in **1.05 ms**.
- **The listener ACKs per socket read, not per complete ASTM message.** Where a
  message arrived as two reads it received **two** ACKs, the first while the message
  was still incomplete; where it arrived coalesced it received **one**. ACK count
  therefore tracks TCP delivery, not message boundaries.
- **Consequently, the observed timings cannot establish native instrument E1381
  semantics** (§6.3). They characterise our listener.
- **No NAK was ever sent** — the capture tool has no NAK path at all.
- **No ACK was withheld** — the tool hard-refuses that mode; it was not authorised.
- **No ACK-timeout evidence exists.** Instrument retry behaviour, ACK dependence and
  reaction to a withheld or negative acknowledgement are all **UNVERIFIED**.

---

## 12. Controlled observation GT-2

The only fully controlled transmission of the session. Ground truth was recorded in
`run02/GROUND_TRUTH_operator_notes.md` **before** the transmission occurred.

**Pre-registered:** a specific selected result identified by its on-screen sequence
number and Sample No.; operator action = *transmit this selected result once*;
explicitly **not** a send-all or queue operation.

**Observed:**

| Check | Result |
|---|---|
| Messages produced | **Exactly one** |
| Size | 2 823 bytes |
| SHA-256 | `d22e0d552790b466cfbe05ef94604d4e7031a947e056d2d22c0e2bdb6cca5bd6` |
| Structure | 49 records — `H`×1, `P`×1, `C`×3, `O`×1, `R`×42, `L`×1 |
| `O`-4 vs pre-registered Sample No. | **Exact match** on component 3 after padding removal |
| `O`-3 | **Empty** |
| `P`-5, `P`-8 | **Empty** |
| Pre-registered sequence identifier | **Not transmitted as any field** |
| `R`-13 | Single shared value = analysis time, ~16½ min before transmission |
| TCP session | **Reused** — no new connection; delivered as 2 segments, coalesced into 1 read |
| Application ACK | 1 ACK, 1.05 ms |
| Byte-identical to A / B / C / uncontrolled | **No** to all four |

**Classification:** a **first transmission of a distinct result**. It is not a
retransmission, rerun or duplicate — the declared action and the byte evidence agree
on that, and no other reading is supported.

*No patient name, patient identifier, date of birth or other PHI value appears in
this document; all such values remain in the evidence root only.*

---

## 13. Retransmission and deduplication evidence

### Observed

- The message format contains **no transmission-varying field whatsoever** (§8.1,
  §8.5, §9.2). An exact resend is therefore byte-identical, which is precisely what
  message A demonstrated four times over.
- `R`-13 is fixed at analysis time and does not change when a result is re-sent.
- No message control id, no sample sequence number, no per-transmission timestamp.

### Not observed

- **No genuine repeat run** of a specimen was performed. Whether a rerun yields a
  different `R`-13, a different `O`-4, or an otherwise distinguishable message is
  **UNVERIFIED**.
- **No cause** was established for the four deliveries of message A.
- **No reconnect- or timeout-driven resend** was observed (§5.5, §11).

### Why no deduplication algorithm follows from this

Distinguishing a resend from a genuine rerun is the entire problem, and this session
supplies only one half of the pair. `../../09_PHYSICAL_INSTRUMENT_VALIDATION.md` §14
**S12** forbids implementing a rule from a single observation, and §8.5 of the same
document already records that no dedup algorithm should be chosen before the relevant
evidence is complete.

Additionally, the candidate identifier that *is* present — `O`-4 — may carry a
patient name rather than a specimen number (§8.3), which would make it unusable as a
dedup key and actively hazardous as a Visit key.

**No dedup design, key selection or algorithm is proposed by this document.** M9.2
remains blocked on its own BC-5150 evidence (§2.1).

---

## 14. QC, calibration, maintenance and startup

**Nothing was captured in any of these categories.**

Every message observed today arrived during routine patient work. No QC run, control
material, calibration, maintenance cycle or instrument startup occurred during the
session, and none was requested — the session was explicitly limited to naturally
available traffic.

**No QC or calibration semantics may be inferred from patient-result messages.** The
XN-550's QC/control message shape is **UNKNOWN — zero captures**, exactly as it was
before this session. Stop condition **S4** cannot be evaluated without such captures,
and M9.3b is unaffected (§2.1).

---

## 15. Evidence confidence matrix

| Finding | Status | Evidence | Scope / limitation |
|---|---|---|---|
| Instrument initiates TCP to LIS `:5001`; 5 SYNs ~508 ms, ~60 s cycle | **VERIFIED** | run01 pcap frames 1–44 | This configuration |
| LIS cannot dial instrument **on port 5001** | **VERIFIED** | run01 frames 29–34; P1a manifest | **Port 5001 only; no port scan performed** |
| Instrument accepts inbound on some other port | **UNKNOWN** | — | Not tested, deliberately |
| S7 met (instrument requires LIS to listen) | **VERIFIED** | §5.2, §5.3 | This configuration; recorded, not acted on |
| Persistent session, 7 messages, 41 min, no reconnect | **VERIFIED** | run03 pcap; rx events | — |
| Instrument holds idle session with 0 bytes, no heartbeat | **VERIFIED** | P1b manifest (rx 0 / tx 0) | — |
| CR-only record termination, no LF | **VERIFIED** | rx.bin; all 7 messages | This configuration |
| No E1381 framing bytes in observed payloads | **VERIFIED** | Byte census per read | **This ASTM configuration only — not "never"** |
| TCP segmentation independent of message boundaries | **VERIFIED** | run03 pcap vs rx events | — |
| Instrument's native E1381 handshake semantics | **UNVERIFIED** | — | Our ACK is application-level (§6.3) |
| `H`-3 … `H`-12 empty; no control id | **VERIFIED** | 7 independent messages | — |
| `O`-3 empty in all messages | **VERIFIED** | 7 independent messages | — |
| On-screen Sample No. → `O`-4 component 3 | **VERIFIED** | GT-2 pre-registered match | This instrument/configuration |
| Lab enters a personal name as Sample No. | **CANDIDATE** | Operator report + 2 sessions | One lab, one operator; §12.2 needs more |
| S1 specimen-collision hazard | **CANDIDATE** (hazard) | §8.3 reasoning | **No collision observed** — hazard, not a triggered stop |
| `P`-5 populated Sept, empty today (S5 condition) | **VERIFIED** observation | Field census | Cause UNKNOWN |
| On-screen sequence number not transmitted | **VERIFIED** | GT-2 message field scan | — |
| `R`-13 single value per message | **VERIFIED** | A, B, C, D, September | — |
| `R`-13 = analysis time, not transmission time | **VERIFIED** | GT-2: 16:24:02 vs 16:40:45 | — |
| One selected-result transmit → exactly one message | **VERIFIED** | GT-2 | Selected-result action only |
| Message A delivered 4× byte-identically | **VERIFIED** | 4 hashes identical | — |
| **Cause** of those 4 deliveries | **UNVERIFIED** | — | No operator action declared |
| Genuine rerun behaviour | **UNVERIFIED** | — | Not performed |
| Reconnect / buffering / resend-on-reconnect | **UNVERIFIED** | — | Cable events ≠ instrument behaviour |
| ACK timeout / NAK / retry behaviour | **UNVERIFIED** | — | Not authorised; not attempted |
| Identity of the uncontrolled 1 102-byte message | **UNKNOWN** | Structure differs (§7.1) | — |
| QC / calibration / maintenance / startup shapes | **UNKNOWN** | Zero captures | — |
| Multi-day identifier/counter behaviour | **UNKNOWN** | Single-day session | — |

---

## 16. XN-550 nine-task status

| # | Task | Status | Evidence obtained | Remaining gap |
|---|---|---|---|---|
| 1 | Transport role / IP / port | **Largely complete, scope-limited** | Outbound dial pattern; inbound refused on 5001; S7 met | Inbound on other ports untested; single configuration |
| 2 | Normal transmission + framing | **Substantially complete** | 7 messages; record grammar; no E1381 bytes; segmentation behaviour | Other output configurations; corpus size |
| 3 | Identifier + timestamp behaviour | **Substantially complete** | No control id; `O`-3 empty; `O`-4 mapping VERIFIED; `R`-13 = analysis time | Semantics of `P`-5, `O`-3, trailing `O`-4 component; multi-day counters |
| 4 | Multiple messages / session | **Complete for this session** | 7 messages, one 41-minute session, no reconnect | Idle-timeout limits; connection limits; ordering guarantees |
| 5 | Retransmission behaviour | **Partial** | 4× byte-identical deliveries of A; no transmission-varying field | **Cause undetermined**; no declared retransmission action |
| 6 | Genuine rerun | **NOT STARTED** | None | Requires a specimen re-run with declared ground truth |
| 7 | Disconnect / reconnect | **NOT VALIDLY TESTED** | Cable-induced events only | Controlled instrument-side disconnect needed |
| 8 | ACK / retry behaviour | **Baseline only** | ACK-on-receive accepted; latencies recorded | Timeout, NAK, withheld-ACK — all require authorisation |
| 9 | QC / calibration / startup / maintenance | **NOT STARTED** | Zero captures | Requires the lab's QC/calibration schedule |

**No task is marked complete.** Tasks 1–4 are substantially advanced within the
tested configuration; 5 is partial; 6, 7, 9 are outstanding; 8 has a baseline only.

---

## 17. Relation to T-CONN-01-03 and T-CORPUS-01-03

### T-CONN-01-03 — Role / IP / port / protocol / framing

Today's session contributes: confirmed endpoint and port; **confirmed connection role**
(instrument dials out, does not answer inbound on 5001); protocol confirmed as ASTM
E1394-97 record grammar; framing characterised for this configuration; and the S7
determination that §11.3 identifies as the first question of every T-CONN-01.

This materially advances T-CONN-01-03. **It is not marked complete here** — that is a
status change to `../../09_PHYSICAL_INSTRUMENT_VALIDATION.md` §13.3, and the inbound
scope limitation in §5.2 is a genuine remaining gap.

### T-CORPUS-01-03 — Raw message corpus

**Target: ≥20 raw messages across categories.**

Obtained today: **7 messages, 4 distinct payloads**, all patient-result work, plus
one uncontrolled message of unknown class. Together with the September capture that
is **5 distinct payloads across two sessions**, with **zero** QC, calibration,
maintenance or startup captures.

**T-CORPUS-01-03 is NOT satisfied and is not marked complete.** Neither the message
count nor the category spread meets the gate.

---

## 18. Safety, privacy and repository boundary

- **All raw PHI-bearing evidence remains outside the repository**, under
  `D:\SurveyLIS\evidence\2026-09-16\`, per
  `../../09_PHYSICAL_INSTRUMENT_VALIDATION.md` §12.4. No raw capture, payload, hex
  dump or identifier value was copied into the repository.
- **Only redacted or synthetic derivatives may enter the repository.** None was
  created by this session; the existing committed fixture remains the redacted
  September message.
- **No production parser was written or registered.** The registry remains
  `{bc5150_hl7}`; `xn550_astm` is unregistered and any ASTM key still fails closed.
- **No schema, migration, transport implementation, configuration or frontend change**
  was made.
- **No database was contacted** at any point — not the stable PoC
  `lis_marina_permata`, not `_dev`, not `_test`. No migration, stamp, reset, drop or
  truncate occurred.
- **No instrument behaviour was altered**: no ACK withheld, no NAK sent, no
  disconnect, no protocol-interference experiment.

---

## 19. Unresolved questions and next evidence needed

1. **Genuine repeat run** of a specimen, with declared ground truth — the single
   highest-value missing capture. It is the only thing that can separate a rerun from
   a resend, and it directly determines whether `R`-13 can distinguish them.
2. **Causality of the four byte-identical deliveries of A** — requires the operator to
   declare each transmit action as it is performed.
3. **Controlled disconnect/reconnect**, initiated at the instrument rather than by
   cable handling: buffering, resend-on-reconnect, idle-socket timeout.
4. **ACK timeout, withheld ACK and NAK** — if and only if lab management authorises
   interference on a clinical device. This is the XN-550 analogue of the BC-5150's
   T-BC-T, which is itself gated on that question.
5. **QC, control material, calibration, maintenance and startup captures** — zero
   exist; required before any classification work, and scheduled against the lab's
   real calendar.
6. **A broader corpus** toward T-CORPUS-01-03's ≥20 messages across categories.
7. **Multi-day identifier behaviour** — whether the on-screen sequence resets, and
   whether `O`-4 values recur across days, which bears directly on the §8.3 hazard.
8. **The 1 102-byte message class** — what it is, and whether its missing `C` records
   and minimal `P` record indicate a distinct message type.
9. **Whether the Sample No. practice is universal** across analysts and shifts.

---

## 20. Conclusion

This session established, with byte evidence, that the XN-550 **initiates** its
connection to the LIS and does not answer inbound TCP on the configured port; that it
maintains a single long-lived session carrying many messages; that its output in this
configuration is ASTM E1394-97 records terminated by bare `CR` with **no E1381
framing bytes present in the payload**; and that the message carries **no
transmission identifier, no sample sequence number and no transmission timestamp**.

The session's strongest single result is the **GT-2 controlled observation**: a
pre-registered transmit of one selected result produced exactly one message, and the
on-screen Sample No. matched ASTM `O`-4 component 3 exactly. That confirms an
identifier mapping which had been unresolved since September, and it surfaces a
clinical-safety hazard worth taking seriously — if this laboratory's Sample No. holds
a patient name, the only specimen identifier the message carries cannot distinguish
two specimens from the same patient.

What remains blocked is unchanged. No genuine rerun was performed, so retransmission
versus rerun is unresolved and **no deduplication design follows from this evidence**.
No QC, calibration, maintenance or startup traffic was captured, so QC classification
is exactly where it was. Reconnect behaviour was never validly tested, and ACK
dependence was not explored because it was not authorised.

**Stop condition S7 is met and recorded**: the XN-550 requires the LIS to listen,
which the current client-only transport does not support. That is an architecture
decision, deliberately left open rather than resolved here.

**M9.2 and M9.3b are untouched by this session**, and **T-CORPUS-01-03 remains
unsatisfied**. No milestone, gate or test-matrix status is advanced to complete by
this document.
