# Sysmex XN-550 — Field Integration Report

| Field | Value |
|---|---|
| **Manufacturer** | Sysmex |
| **Model** | XN-550 |
| **Family** | XN-L |
| **Survey date** | 15 September 2026 |
| **Evidence type** | Physical field verification + raw ASTM capture |
| **Repository status** | Field evidence |
| **Source document** | `D:\SurveyLIS\Laporan_Investigasi_LIS_Sysmex.md` |
| **Imported** | 15 September 2026, unchanged except for the redaction and annotations declared in §0.2 |

---

## 0. How to read this document

> **A second session has since taken place.** This document records **session 1**
> (15 September 2026) and is left as the historical record of that survey. Several
> questions it leaves open — the transport role, the presence of ASTM 1381-95
> framing, and the meaning of `O`-4 — were addressed on **16 September 2026**; see
> [`VALIDATION_2026-09-16.md`](VALIDATION_2026-09-16.md), which supersedes this
> document wherever the two speak to the same question. A **third session** on
> **17 September 2026** ([`VALIDATION_2026-09-17.md`](VALIDATION_2026-09-17.md)) added
> controlled retransmission, identifier and reconnect evidence, corrected two
> statements in the 16 September record, and — in a corpus-expansion run (Run03) — brought
> the raw corpus to 20 messages, all patient results; it also recorded one controlled normal
> instrument restart (POWER-CYCLE-01) and one controlled multi-select/batch transmit
> observation (MULTI-SELECT-01). The single message this report
> describes is therefore no longer the whole corpus. Nothing below has been rewritten to
> match either.

### 0.1 ⚠ This is a historical field-survey report, not an architecture decision

> **The exploratory backend and database recommendations inside this report PRE-DATE the current `LIS_Project` architecture and are NOT authoritative for this repository.**
>
> In particular, **§5 "Rekomendasi Arsitektur Database & Backend" must not be implemented.** It proposes a three-table schema (`pasien` / `pemeriksaan` / `hasil_detail`) and direct `INSERT` / `requests.post` calls from a listener script. The current repository already has a governed clinical hierarchy (`Patient → Visit → Order → TestRun → Result`, `docs/04_DATABASE_DESIGN.md`), a migration chain with a single root and head, a three-stage ingestion transaction model, and a fail-closed classification layer. **None of that is reopened by this report.**
>
> What *is* authoritative here is the **field evidence**: what the instrument was observed to do on 15 September 2026. Recommendations, opinions and vendor claims in this report carry no more weight than the evidence label attached to them.
>
> Governing documents remain `docs/03_SYSTEM_DESIGN.md`, `docs/04_DATABASE_DESIGN.md`, `docs/07_TASK_LIST.md` and `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md`. Where this report and those documents disagree, **those documents win** and the disagreement is recorded as an open item, not silently resolved.

### 0.2 Editorial changes made during import

Exactly two kinds of change were made. Nothing else was altered, reordered, corrected or paraphrased.

1. **PHI redaction (required).** `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md` §12.4 requires that only *redacted or synthetic derivatives* of a raw corpus be committed to this repository, and that anything carrying real identifiers stay in a controlled store outside it. The captured message contains a real patient name, patient id and date of birth. Every occurrence is replaced with a **length-preserving** `X` mask, so field positions, delimiters and record lengths are unchanged:

   | Original | Mask | Occurrences |
   |---|---|---|
   | patient name (ASTM `O`-4, and 4 embedded PNG filenames) | `XXXXXX` | 5 |
   | patient id (ASTM `P`-5) | `XXXXX` | 1 |
   | date of birth (ASTM `P`-8) | `XXXXXXXX` | 1 |
   | patient name in the §3.1 legacy-format sample | `XX. XXX` | 2 |

   **No clinical value, unit, flag, parameter name, timestamp, instrument identifier or serial number was altered.**

2. **Annotations.** Editorial notes are added in clearly-marked `> **Repository note:**` blocks. They never replace the original text; the original statement always remains directly above them.

### 0.3 Evidence labels

This document uses the labels defined in `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md` §2, without exception:

| Label | Meaning |
|---|---|
| **VERIFIED** | Observed on the physical instrument on 15 September 2026 |
| **REPO-CONFIRMED** | Read from this repository's source; says what the software does, not what the instrument does |
| **INFERRED** | Reasoned from VERIFIED or REPO-CONFIRMED facts; not itself observed |
| **CLAIMED** | Asserted by the survey report or a vendor document, not independently observed in this session |
| **UNKNOWN** | No evidence either way |

A single session yields at most a **CANDIDATE** rule, never a VERIFIED rule (§12.2 requires ≥2 independent observations, preferably on different days). **This survey is one session.**

---

## 1. Topologi Jaringan & Pengaturan TCP/IP

*(Preserved from the source report, §1.)*

Dalam pengembangan *bridging* LIS dengan mesin Sysmex (khususnya seri XN-L dan BX-3010), komunikasi dilakukan melalui protokol jaringan TCP/IP.

### 1.1 Peran Klien & Server

Secara arsitektur, sangat direkomendasikan PC LIS bertindak sebagai **TCP Server**, sedangkan alat Sysmex bertindak sebagai **TCP Client**.

- **LIS (Server):** Diam membuka port, mendengarkan di IP `0.0.0.0` (mewakili seluruh antarmuka jaringan di komputer LIS).
- **Sysmex (Client):** Melakukan inisiasi pengiriman data ke `IP_LIS:PORT_LIS` setiap kali ada hasil (Auto-Output) atau ketika tombol Transmit ditekan oleh analis.

> **Repository note — this is the single most consequential finding, and it conflicts with the current transport.**
>
> - **VERIFIED:** in this session the XN-550 acted as **TCP client** and the survey PC acted as **TCP server** on port `5001`. The instrument initiated the connection and delivered data.
> - **REPO-CONFIRMED:** the current LIS supports **client mode only** — `backend/app/core/config.py` defines `SUPPORTED_INSTRUMENT_MODES = {"client"}` and rejects any other value as a configuration error; `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md` §11.1 records that the LIS dials out.
> - `docs/09` §11.3 anticipated exactly this case: *"If any instrument acts solely as a TCP client — i.e. it expects the LIS to listen — that instrument cannot be connected at all without implementing listener mode."* It also states this must be determined **before** any parser work for that instrument.
> - **UNKNOWN:** whether the XN-550 can *also* accept an inbound connection. `sysmex_xn550_tcp_listener.py` contains a client mode that dials `10.0.0.11:5001`, but this report records no successful result from it. **"XN-550 works as a client" does not establish "XN-550 cannot be a server."**
> - **No architecture change is made or implied by this import.** Whether to implement listener mode is an open engineering decision, not a conclusion of this survey. See `README.md` §7.

### 1.2 Resolusi Masalah Jaringan (Troubleshooting)

Selama sesi riset, kami menemukan 2 hambatan standar industri:

1. **Windows Firewall (WinError 10049 / 10054):**
   Secara bawaan, OS Windows pada PC LIS memblokir koneksi masuk ke port sembarang (misal: `5000` atau `5001`). *Firewall Inbound Rules* **wajib** dibuka melalui CMD Administrator.

2. **Ping Request Timed Out (RTO) pada Sysmex:**
   PC LIS seringkali tidak bisa me-`ping` IP Sysmex meskipun kabel tersambung baik. Hal ini dikarenakan OS Windows Embedded bawaan monitor Sysmex memiliki *firewall internal* yang memblokir ICMP (Ping).
   - **Solusi:** Selama MAC Address Sysmex terdeteksi di tabel ARP (`arp -a` di CMD Windows LIS), maka jalur fisik kabel LAN dipastikan **100% aman**, dan status RTO Ping pada alat medis dapat diabaikan.

> **Repository note.** Both items are **VERIFIED** operational observations from the session and are useful deployment knowledge. The explanation offered for the ping failure (an internal firewall in the Sysmex embedded OS blocking ICMP) is **INFERRED**, not confirmed against vendor documentation. The practical rule — ARP presence is sufficient evidence of a healthy physical link — holds regardless of the cause.

---

## 2. Pengaturan Parameter pada Alat Sysmex XN-550

*(Preserved from the source report, §2.)*

Untuk mendapatkan data yang terstruktur dan mudah di-*parsing*, alat Sysmex **WAJIB** diatur menggunakan format komunikasi standar industri.

**Langkah Pengaturan (IPU Settings > Host Computer):**

- **Connection Type:** TCP/IP
- **Host IP:** `10.0.0.10` (Sesuaikan dengan IP PC LIS saat itu)
- **Port:** `5001` (Port yang sedang di-listen oleh PC LIS)
- **Format / Protocol:** `ASTM1381-95 / ASTM1394-97`
  > **Catatan Krusial:** Jangan gunakan format "Sysmex" atau "TCP/IP" standar bawaan alat, karena akan mengirimkan format data *Fixed-width* yang kuno dan rentan bergeser (sangat sulit di-parsing tanpa dokumen mapping khusus dari pabrikan).

> **Repository note.** **VERIFIED:** these settings were applied on the instrument and produced the ASTM output in §3.2. The endpoint (`10.0.0.10:5001`) was the survey PC, **not** a production LIS host — it must not be copied into `backend/instruments.json` as a deployment value.
>
> **VERIFIED, and important:** the instrument's output format is **operator-configurable**, and the legacy (§3.1) and ASTM (§3.2) formats are both reachable from the same device. Any future XN-550 integration therefore depends on an instrument-side setting that is **not** under LIS control and is **not** currently recorded in any deployment configuration.
>
> The instrument menu advertises `ASTM1381-95 / ASTM1394-97` as one selection. **1381-95 is the low-level framing layer** (`STX` … `ETX`, frame numbers, checksums, `ENQ`/`ACK`/`EOT` handshake); **1394-97 is the record grammar** (`H`/`P`/`O`/`R`/`L`). The captured payload contains the 1394-97 records but **no 1381-95 framing characters** — see §3.3.

---

## 3. Analisis Raw Data

### 3.1 Raw Data Gagal (Format Sysmex Legacy)

*(Preserved from the source report, §3.1. Patient name redacted per §0.2.)*

Saat alat belum diubah ke ASTM, tangkapan pesannya terlihat seperti ini:

```text
\x02D1U    XN-550^411220000000052000               XX. XXX202609142336000000000001                000000...
\x02D2U    XN-550^411220000000052000               XX. XXX01603103910011200330008442028600339002130...
```

*(Nilai hasil darah menyatu menjadi rentetan angka `0160310391...` yang harus dihitung digit per digit).*

> **Repository note.** **VERIFIED** that the instrument emits this fixed-width proprietary format when not configured for ASTM. The sample is **truncated in the source report** (`...`) and **no complete legacy-format capture exists** anywhere in the survey workspace. This format is therefore **not** represented by any fixture and its field layout remains **UNKNOWN**. Note the `\x02` (`STX`) prefix, absent from the ASTM capture.

### 3.2 Raw Data Sukses (Format ASTM 1394-97)

*(Preserved from the source report, §3.2. Identifiers redacted per §0.2.)*

Setelah alat diatur ke mode ASTM, data dikirim dengan separator *Pipe* `|` dan *Caret* `^`. Format ini mendukung relasi *Key-Value* yang jelas:

```text
H|\^&|||    XN-550^00-29^41122^^^^BD634545||||||||E1394-97
P|1|||XXXXX|^^||XXXXXXXX|F|||||^||||||||||||^^^
O|1||^^                XXXXXX^M|^^^^WBC\^^^^RBC\^^^^HGB...
R|1|^^^^WBC^1|11.30|10*3/uL||N||F||lab||20260915023225
R|2|^^^^RBC^1|4.75|10*6/uL||N||F||lab||20260915023225
R|3|^^^^HGB^1|12.9|g/dL||N||F||lab||20260915023225
...
L|1|N
```

**Struktur ASTM Utama:**

- **H** = Header (Sesi dimulai)
- **P** = Patient (Identitas pasien/ID Rekam Medis)
- **O** = Order (Sample ID/Barcode tabung darah)
- **R** = Result (Nama parameter, Nilai, Satuan, dan Flag Abnormalitas)
- **L** = Last / Terminator (Tanda paket selesai)

> **Repository note — the excerpt above is truncated; the complete message was recovered separately.**
>
> The snippet in the source report is abbreviated with `...` and is **not** a usable fixture. The complete payload was recovered from `D:\SurveyLIS\scratch_test.py`, where it is embedded verbatim as a Python string literal, and every line the report *does* show matches it byte-for-byte. It is committed (redacted) as:
>
> `backend/tests/fixtures/instruments/sysmex_xn550/patient_result_001.astm`
>
> **The record-type legend above is the report's interpretation, and two parts of it are not supported by the capture:**
>
> - The report labels **P** as *"Identitas pasien / ID Rekam Medis"* and **O** as *"Sample ID / Barcode tabung darah"*. In the actual message, the **patient name appears in `O`-4** (instrument specimen id), not in `P`; `P`-5 carries a bare numeric id whose meaning (hospital MRN? instrument-local sequence? worklist key?) is **UNKNOWN**; and **`O`-3 — the ASTM specimen-id field itself — is empty.** No barcode or specimen id is identifiable anywhere in the message.
> - This is exactly the "patient identifier semantics" and "specimen identifier semantics" gap listed as open in `README.md` §7. **It is not resolved by this survey, and the report's legend must not be used to resolve it.**

### 3.3 Structure actually present in the captured message

> **Repository note — this subsection is editorial. It records measurements of the committed fixture, not text from the source report.**

| Property | Value | Label |
|---|---|---|
| Total size | 2 824 bytes | VERIFIED (measured) |
| Record count | 49 | VERIFIED |
| Record types | `H`×1, `P`×1, `O`×1, `C`×3, `R`×42, `L`×1 | VERIFIED |
| Record terminator | `\r` (`0x0D`) only; no `\n` anywhere | VERIFIED |
| Field / repeat / component / escape delimiters | `|` `\` `^` `&` — declared in `H`-2 as `\^&` | VERIFIED |
| ASTM 1381-95 framing | **Absent** — no `STX`, `ETX`, `ENQ`, `ACK`, `EOT`, frame numbers or checksums | VERIFIED (of this artefact — see the caveat below) |
| `C` (comment) records | Present, 3× — **not mentioned anywhere in the source report's legend** | VERIFIED |
| `R` record content | 28 numeric results with units and flags, 10 interpretive flags (`Blasts/Abn_Lympho?` etc.), 4 PNG filename references | VERIFIED |
| SHA-256, unredacted original | `6f6cf24905eb0a0761f07e2ed534ea90374f039ad023afa6eb398401ec6742a8` | VERIFIED |
| SHA-256, committed fixture | `2fcc8f38de8d6903595b5e876e00de352ace7005b805739486a22106ce543ad3` | VERIFIED |

> **Caveat on the framing row — read this before designing a transport.**
>
> The recovered payload is a **de-framed record stream**, and it is *not* established that the instrument sent no framing. `sysmex_xn550_tcp_listener.py` accumulates `data.decode('ascii', errors='ignore')` and does not strip control characters, so `STX`/`ETX`/`ENQ`/`EOT` would have survived into its buffer had they arrived. But the string in `scratch_test.py` was pasted into a scratch script by hand, and whether it was cleaned before pasting is **UNKNOWN**.
>
> **Therefore: "the XN-550 sends no ASTM 1381-95 framing" is NOT a verified conclusion.** It is unresolved, and it must be settled by a byte-level capture (`docs/09` §12.3 requires a pcap for exactly this class of question) before any transport is written. Treat the fixture as a **record-grammar fixture**, valid for parser work, and **not** as a transport/framing fixture.

---

## 4. Modul Kode (Siap Pakai untuk Development)

*(Preserved from the source report, §4.)*

Telah disediakan dua buah modul *script* Python inti di direktori *workspace* `D:\SurveyLIS\` yang bertindak sebagai jembatan (*bridger*).

1. **`sysmex_xn550_tcp_listener.py`**
   Sebagai penangkap koneksi. Menangani ACK/NACK *handshake* dan mendeteksi terminator pesan.
2. **`sysmex_parser.py`**
   Mesin pemotong string ASTM yang mengubah teks murni menjadi variabel JSON/Dictionary agar mudah didistribusikan.

> **Repository note — these scripts stay in `D:\SurveyLIS` and are deliberately NOT imported.**
>
> They are field-investigation and prototyping tools. Only documentation, evidence and redacted fixtures enter this repository; a production adapter is a separate, later task governed by the current architecture (`docs/09` §5.2: the parser registry is an exact-match dictionary with **no fallback**, and today contains exactly one entry, `bc5150_hl7`).
>
> **One claim in this section is not supported by the code.** The listener is described as handling an *"ACK/NACK handshake"*. The script sends `ACK` (`0x06`) only — it contains no `NAK` (`0x15`) path at all, and it ACKs on receipt of a TCP chunk rather than on a validated ASTM frame. So:
> - **VERIFIED:** an experimental, permissive ACK-on-receive behaviour was exercised and the instrument completed its transmission under it.
> - **CLAIMED, not supported:** NACK handling. It does not exist in the script.
> - **UNKNOWN:** how the instrument reacts to a withheld ACK, to a NAK, or to an ACK timeout. None was tested.
>
> This mirrors a known gap for the BC-5150 (`docs/09` T-BC-T, blocked on lab-management question Q3) and is listed as open in `README.md` §7.

---

## 5. Rekomendasi Arsitektur Database & Backend

> ## ⚠ SUPERSEDED — DO NOT IMPLEMENT
>
> **This section is preserved verbatim for the historical record only. It pre-dates the current architecture and is overridden in full by `docs/04_DATABASE_DESIGN.md`, `docs/03_SYSTEM_DESIGN.md` and the M1–M9 milestone record in `docs/07_TASK_LIST.md`.**
>
> Specifically: the proposed `pasien` / `pemeriksaan` / `hasil_detail` schema does not exist and will not be created; the repository's clinical hierarchy is `Patient → Visit → Order → TestRun → Result` across a governed migration chain rooted at `8e973e84a9d7`. Direct `INSERT` or `requests.post` from a listener script bypasses the three-stage ingestion transaction model, the fail-closed classification layer, the raw-message audit trail in `instrument_messages`, and the M9.1b actor-attribution model. **None of that is negotiable on the strength of this report.**

*(Preserved from the source report, §5.)*

Untuk implementasi akhir pada LIS sesungguhnya, kami merekomendasikan:

1. **Skema Database (RDBMS):**
   Siapkan minimal 3 tabel (sebaiknya PostgreSQL/MySQL):
   - `pasien` (Menampung Patient_ID dari record P).
   - `pemeriksaan` (Menampung Sample_ID dari record O).
   - `hasil_detail` (Menampung setiap Record R: `parameter`, `value`, `unit`, dan `flag`).

2. **Integrasi Polling / Push API:**
   Ubah baris kode pencetak *console* (bagian `print("DATA PASIEN...")`) di dalam file Listener menjadi fungsi HTTP POST (`requests.post('http://localhost/api/save_hasil')`), atau lakukan `INSERT` SQL secara langsung ke *database* LIS Anda pada momen tersebut.

**- END OF REPORT -**

---

## 6. Provenance

| Item | Value |
|---|---|
| Primary source | `D:\SurveyLIS\Laporan_Investigasi_LIS_Sysmex.md` (4 858 bytes, dated 15 September 2026) |
| Complete raw payload recovered from | `D:\SurveyLIS\scratch_test.py`, variable `raw` |
| Listener used in the session | `D:\SurveyLIS\sysmex_xn550_tcp_listener.py` (**not imported**) |
| Prototype parser | `D:\SurveyLIS\sysmex_parser.py` (**not imported**) |
| Committed fixture | `backend/tests/fixtures/instruments/sysmex_xn550/patient_result_001.astm` |
| Unredacted original | Retained **only** in `D:\SurveyLIS`, outside this repository, per `docs/09` §12.4 |

### 6.1 Capture-standard compliance

Measured against `docs/09_PHYSICAL_INSTRUMENT_VALIDATION.md` §12, so that the shortfalls are visible rather than assumed:

| §12 requirement | Status |
|---|---|
| §12.1 Structured evidence record (`EV-<TESTID>-…`) | **Not produced.** This survey pre-dates that template; this document is the substitute record |
| §12.2 ≥2 observations on different days for a VERIFIED rule | **Not met — one session.** Every behavioural conclusion here is at most CANDIDATE |
| §12.3 Packet capture for the session | **Not performed.** This is why the framing question in §3.3 is unresolved |
| §12.4 Byte-exact preservation, one file per message, SHA-256 | **Partially met.** One message, hashed; byte-exactness is limited by the hand-transcription path described in §3.3 |
| §12.4 Raw corpus with real identifiers kept outside the repository | **Met** — unredacted original stays in `D:\SurveyLIS` |
| §12.4 Only redacted or synthetic derivatives committed | **Met** — see §0.2 |

The session also did not produce the ≥20-message corpus that `docs/09` T-CORPUS-01-03 requires. **One patient-result message is a starting point for a parser contract, not a validated corpus.**
