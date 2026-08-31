# Quality Assurance (QA) & Test Plan

## 1. Purpose

Dokumen ini mendefinisikan strategi dan skenario pengujian untuk memvalidasi kualitas **Laboratory Information System (LIS) Middleware MVP**.

Pengujian mencakup:

1. Resilience dan connection recovery.
2. Message reception dan parsing.
3. Data integrity.
4. Re-run dan Test Run management.
5. Database business rules.
6. Strictly view-only UI.
7. SIMRS integration.
8. Historical Result API.
9. Multi-instrument concurrency.
10. Traceability dan auditability.

Tujuan utama QA adalah memastikan:

> **Data laboratorium dapat diterima, disimpan, ditampilkan, dan dikirim tanpa kehilangan, pencampuran, atau perubahan terhadap nilai klinis asli.**

---

# 2. Test Strategy & Scope

Pengujian LIS dilakukan pada beberapa level:

```text
Instrument
    ↓
Integration Service
    ↓
Parser
    ↓
PostgreSQL
    ↓
FastAPI
    ↓
React Dashboard
    ↓
SIMRS
```

### Test Levels

| Level | Fokus |
|---|---|
| Unit Test | Parser, validator, business logic |
| Integration Test | Instrument ↔ Integration Service ↔ Database |
| API Test | FastAPI endpoint dan business rules |
| Database Test | Constraint dan referential integrity |
| UI Test | Dashboard, read-only behavior, workflow |
| End-to-End Test | Instrument → LIS → SIMRS |
| Resilience Test | Network drop, reboot, reconnect |
| Concurrency Test | Multi-instrument dan batch transmission |

---

# 3. Test Environment

Environment pengujian minimal terdiri dari:

### Application

```text
Python
FastAPI
React
TypeScript
PostgreSQL
```

### Integration

```text
Laboratory Instrument
TCP/IP
ASTM / HL7
Integration Service
```

### Network

```text
Laboratory LAN
LIS Server
Instrument Network
```

Jika instrumen fisik belum tersedia, pengujian komunikasi dapat dilakukan menggunakan simulator ASTM/HL7 atau mock TCP server.

---

# 4. Resilience & Recovery Testing

## TC-RES-01 — Cable Unplug / Network Drop

**Given:**

- Integration Service berjalan.
- Instrumen terhubung melalui jaringan LAN.
- Listener berada dalam kondisi aktif.

**When:**

Kabel jaringan dicabut selama kurang lebih satu menit kemudian dipasang kembali.

**Then:**

- Integration Service tidak mengalami fatal crash.
- Connection error ditangani oleh listener.
- Status instrumen berubah menjadi `reconnecting` atau `disconnected`.
- Sistem melakukan reconnect sesuai konfigurasi.
- Setelah koneksi kembali, listener dapat menerima pesan baru.

**Expected Result:**

```text
Connected
    ↓
Disconnected / Reconnecting
    ↓
Connected
```

---

## TC-RES-02 — Instrument Reboot

**Given:**

Instrumen sedang terhubung dengan LIS.

**When:**

Instrumen dimatikan kemudian dihidupkan kembali.

**Then:**

- Listener mendeteksi connection loss.
- Application process tetap berjalan.
- Instrumen tidak memengaruhi koneksi instrumen lainnya.
- Listener kembali siap menerima data setelah instrumen online.

---

## TC-RES-03 — Single Instrument Failure Isolation

**Given:**

Beberapa instrumen terhubung secara bersamaan.

**When:**

Satu instrumen mengalami network failure.

**Then:**

- Status instrumen tersebut berubah menjadi `disconnected/reconnecting`.
- Instrumen lain tetap dapat mengirim data.
- Dashboard tetap dapat digunakan.
- Tidak terjadi global service failure.

**Acceptance:**

> Failure pada satu instrument connection tidak boleh menghentikan komunikasi instrumen lainnya.

---

# 5. Message Reception & Parsing Testing

## TC-INT-01 — Single Message Processing

**Given:**

Instrumen mengirim satu pesan pemeriksaan valid.

**When:**

Integration Service menerima pesan.

**Then:**

- Pesan diterima secara utuh.
- Raw message disimpan di `instrument_messages`.
- Parser menghasilkan data yang sesuai.
- `test_run` dibuat.
- Result dibuat berdasarkan parameter yang diterima.

---

## TC-INT-02 — Batch Transmission Handling

**Given:**

Instrumen memiliki banyak hasil yang siap dikirim.

**When:**

Instrumen mengirim beberapa pesan secara berurutan dalam satu sesi komunikasi.

**Then:**

- Setiap pesan dapat dipisahkan berdasarkan framing/terminator protokol yang sesuai.
- Setiap pesan diproses secara independen.
- Tidak ada pesan yang tercampur.
- Tidak ada pesan yang terpotong.
- Tidak ada hasil yang hilang.

Pengujian harus menggunakan framing sesuai protokol instrumen.

> Pengujian tidak boleh mengasumsikan satu karakter terminator tertentu berlaku untuk seluruh ASTM dan HL7.

---

## TC-INT-03 — Malformed Message

**Given:**

Integration Service menerima pesan yang tidak lengkap atau memiliki format invalid.

**When:**

Parser mencoba memproses pesan tersebut.

**Then:**

- Application tidak crash.
- Raw message tetap dapat dicatat.
- `parse_status` menunjukkan kegagalan.
- Data invalid tidak menghasilkan clinical result yang salah.

Contoh:

```text
parse_status = Failed
```

---

## TC-INT-04 — Ghost / Background Parameter Injection

**Given:**

Instrumen mengirimkan data kalibrasi, blank test, QC, atau background test yang bukan pemeriksaan pasien.

**When:**

Integration Service menerima data tersebut.

**Then:**

- Raw message tetap dapat disimpan untuk traceability.
- Sistem tidak membuat order/result pasien secara salah.
- Pesan dapat diberi status atau klasifikasi yang sesuai.

Filtering harus berdasarkan aturan yang terdefinisi pada instrument integration specification, bukan hanya mengandalkan string tertentu seperti `"Background"`.

---

## TC-INT-05 — Duplicate / Replayed Message

**Given:**

Instrumen atau jaringan mengirimkan kembali pesan yang sama.

**When:**

Integration Service menerima pesan tersebut.

**Then:**

- Sistem tidak menghasilkan duplicate clinical result secara tidak terkendali.
- Mekanisme deduplication/idempotency yang telah ditentukan dapat mengidentifikasi pesan yang sama.
- Raw communication tetap dapat dipertahankan untuk audit apabila diperlukan.

> Mekanisme deduplication final ditentukan pada System Design berdasarkan karakteristik protokol masing-masing instrumen.

---

# 6. Data Integrity Testing

## TC-DATA-01 — Clinical Value Preservation

**Given:**

Instrumen mengirim:

```text
Parameter: WBC
Value: 18.4
Unit: 10^3/uL
Flag: H
```

**When:**

Data:

```text
Instrument
→ Parser
→ Database
→ API
→ Dashboard
```

**Then:**

Nilai yang ditampilkan tetap:

```text
18.4
```

Tidak boleh berubah menjadi:

```text
18
18.40
17.4
```

tanpa alasan yang berasal dari data sumber.

---

## TC-DATA-02 — Result Immutability

**Given:**

Sebuah `result` telah tersimpan.

**When:**

Client/API mencoba mengubah:

```text
parameter_tes
nilai_hasil
satuan
flag_abnormalitas
reference_range_snapshot
waktu_hasil
```

**Then:**

Request harus ditolak atau field tersebut diabaikan sesuai enforcement yang diterapkan.

Tidak boleh terdapat endpoint normal yang memungkinkan perubahan clinical value.

---

## TC-DATA-03 — Reference Range Snapshot

**Given:**

Hasil pemeriksaan disimpan bersama reference range.

**When:**

Konfigurasi reference range berubah setelah pemeriksaan.

**Then:**

`reference_range_snapshot` pada hasil lama tetap sama.

---

# 7. Test Run & Re-run Testing

## TC-RUN-01 — Initial Test Run

**Given:**

Satu order menerima hasil pemeriksaan pertama.

**When:**

Pesan berhasil diproses.

**Then:**

Satu `test_run` dibuat dan seluruh parameter hasil terkait disimpan pada run tersebut.

---

## TC-RUN-02 — Re-run Override Prevention

**Given:**

Order `#1001` memiliki:

```text
Test Run #1
```

**When:**

Instrumen mengirim hasil pemeriksaan ulang.

**Then:**

Sistem membuat:

```text
Test Run #2
```

dan:

```text
Test Run #1
```

tetap utuh.

Tidak boleh terjadi overwrite terhadap result sebelumnya.

---

## TC-RUN-03 — Multiple Re-run

**Given:**

Satu order menerima tiga pengujian:

```text
Run 1
Run 2
Run 3
```

**Then:**

Ketiga Test Run tersimpan secara independen.

```text
Order
 ├── Run 1
 ├── Run 2
 └── Run 3
```

---

## TC-RUN-04 — Duplicate Parameter Within Same Run

**Given:**

Parser mencoba menyimpan parameter yang sama dua kali dalam satu `test_run`.

**When:**

Database menerima insert kedua.

**Then:**

Database menolak duplicate berdasarkan:

```sql
UNIQUE (id_run, parameter_tes)
```

Hal tersebut tidak boleh menghalangi parameter yang sama pada Test Run berbeda.

Contoh:

```text
Run 1 + WBC → Valid
Run 2 + WBC → Valid
Run 3 + WBC → Valid
```

---

# 8. Final Run Workflow Testing

## TC-WF-01 — Set First Final Run

**Given:**

Order memiliki satu Test Run.

**When:**

Analis memilih `Set as Final Run`.

**Then:**

```text
is_final = TRUE
```

Test Run tersebut menjadi final.

---

## TC-WF-02 — Switch Final Run

**Given:**

```text
Run 1 → is_final = TRUE
Run 2 → is_final = FALSE
```

**When:**

Analis memilih Run 2 sebagai final.

**Then:**

Dalam satu atomic transaction:

```text
Run 1 → FALSE
Run 2 → TRUE
```

Pada akhirnya hanya terdapat satu final run.

---

## TC-WF-03 — Database Final Run Constraint

**Given:**

```text
Run 1 → TRUE
Run 2 → TRUE
```

**When:**

Keduanya dipaksa menjadi final dalam kondisi yang melanggar constraint.

**Then:**

Partial Unique Index menolak keadaan tersebut.

```sql
UNIQUE (id_order)
WHERE is_final = TRUE
```

Database tidak boleh berada pada keadaan dua final run untuk satu order.

---

## TC-WF-04 — Final Run Does Not Modify Clinical Data

**Given:**

Run 1 memiliki nilai:

```text
WBC = 10.5
```

Run 2 memiliki:

```text
WBC = 12.7
```

**When:**

Run 2 ditetapkan sebagai final.

**Then:**

Nilai Run 1 tetap:

```text
10.5
```

Nilai Run 2 tetap:

```text
12.7
```

Pemilihan final hanya mengubah workflow metadata.

---

# 9. Referential Integrity Testing

## TC-DB-01 — Patient Visit Relationship

**Given:**

Satu pasien memiliki beberapa kunjungan.

**Then:**

Semua kunjungan dapat dikaitkan ke pasien yang benar melalui:

```text
patients
   ↓
visits
```

---

## TC-DB-02 — Visit Order Relationship

Satu visit dapat memiliki beberapa order.

```text
Visit
 ├── Order 1
 ├── Order 2
 └── Order 3
```

Database harus mempertahankan seluruh relasi tersebut.

---

## TC-DB-03 — Result Traceability

Setiap result harus dapat ditelusuri:

```text
Result
 ↓
Test Run
 ↓
Order
 ↓
Visit
 ↓
Patient
```

dan:

```text
Test Run
 ↓
Instrument
 ↓
Instrument Message
 ↓
Raw Message
```

---

# 10. Instrument Traceability Testing

## TC-TRACE-01 — Raw Message Preservation

**Given:**

Instrumen mengirim raw ASTM/HL7 message.

**When:**

Pesan berhasil diterima.

**Then:**

Raw message tersimpan di:

```text
instrument_messages.raw_message
```

bersama:

```text
id_instrument
received_at
parse_status
```

---

## TC-TRACE-02 — Result to Source Message

**Given:**

Sebuah result telah dibuat.

**When:**

Developer/analis melakukan investigasi terhadap result tersebut.

**Then:**

Result dapat ditelusuri kembali ke:

```text
Test Run
→ Instrument Message
→ Raw Message
```

Tanpa perlu meminta instrumen mengirim ulang pesan.

---

# 11. Frontend & UI Testing

## TC-UI-01 — Instrument Connection Status

**Given:**

Dashboard sedang terbuka.

**When:**

Satu instrumen kehilangan koneksi.

**Then:**

Status instrumen berubah menjadi:

```text
Connected
→ Reconnecting / Disconnected
```

UI tetap dapat digunakan untuk instrumen lainnya.

---

## TC-UI-02 — Strictly View-Only Result

**Given:**

Analis membuka Result Table.

**When:**

Analis mencoba memilih atau mengklik clinical value.

**Then:**

Nilai hanya dapat dilihat.

Tidak tersedia:

```text
<input>
<textarea>
contenteditable
```

atau komponen editing lainnya.

Tidak tersedia tombol:

```text
Edit Result
Edit Value
Edit Unit
Edit Flag
```

---

## TC-UI-03 — Test Run Selector

**Given:**

Satu order memiliki beberapa Test Run.

**When:**

Analis memilih tab Run 2.

**Then:**

Result Table menampilkan result dari Run 2.

Data Run 1 tetap tidak berubah.

---

## TC-UI-04 — Final Run Indicator

**Given:**

Run 3 memiliki:

```text
is_final = TRUE
```

**Then:**

UI menampilkan indicator:

```text
FINAL
```

atau equivalent visual yang jelas.

---

## TC-UI-05 — Clinical Flag Accessibility

**Given:**

Result memiliki flag abnormal.

**Then:**

UI menampilkan:

```text
Flag + Color + Label/Icon
```

Status tidak boleh hanya dibedakan melalui warna.

---

# 12. API Testing

## TC-API-01 — Set Final Run API

**Given:**

User memiliki permission yang sesuai.

**When:**

API dipanggil untuk menetapkan Test Run sebagai final.

**Then:**

Database melakukan perubahan secara atomic dan hanya satu run yang final.

---

## TC-API-02 — Unauthorized Final Run Modification

**Given:**

Client tidak memiliki hak untuk mengubah workflow.

**When:**

Client mencoba mengubah `is_final`.

**Then:**

API menolak request.

---

## TC-API-03 — Clinical Result Modification Prevention

**Given:**

Client mencoba mengirim request untuk mengubah:

```text
nilai_hasil
satuan
flag_abnormalitas
```

**Then:**

API menolak perubahan tersebut.

---

# 13. SIMRS Integration Testing

## TC-API-04 — Successful SIMRS Delivery

**Given:**

```text
is_final = TRUE
delivery_status = pending
```

**When:**

Analis memilih:

```text
Sync to SIMRS
```

**Then:**

FastAPI mengirim HTTP POST ke endpoint SIMRS.

Jika SIMRS mengonfirmasi keberhasilan:

```text
delivery_status = delivered
delivered_at = <timestamp>
```

Clinical result tidak berubah.

---

## TC-API-05 — SIMRS Sending State

**Given:**

Pengiriman sedang berlangsung.

**Then:**

Status sementara:

```text
sending
```

UI menampilkan:

```text
Sending...
```

User tidak boleh memicu pengiriman yang sama secara tidak terkendali secara bersamaan.

---

## TC-API-06 — Failed SIMRS Delivery

**Given:**

SIMRS mengalami:

- Timeout.
- Connection failure.
- HTTP error.

**When:**

LIS mencoba mengirim hasil.

**Then:**

```text
delivery_status = failed
```

dan nilai klinis tetap utuh.

UI menampilkan:

```text
Failed
[Retry]
```

---

## TC-API-07 — SIMRS Retry

**Given:**

```text
delivery_status = failed
```

**When:**

Analis memilih `Retry`.

**Then:**

LIS mencoba mengirim ulang tanpa membuat atau mengubah clinical result.

---

# 14. Historical Result API Testing

## TC-HIST-01 — Retrieve History by No. RM

**Given:**

Pasien memiliki beberapa historical laboratory results.

**When:**

SIMRS mengirim request menggunakan Nomor RM yang valid.

**Then:**

API mengembalikan historical result yang terkait dengan pasien tersebut.

Data harus dapat ditelusuri:

```text
No. RM
 ↓
Visit
 ↓
Order
 ↓
Test Run
 ↓
Result
```

---

## TC-HIST-02 — Unknown No. RM

**Given:**

SIMRS meminta Nomor RM yang tidak terdapat pada database.

**Then:**

API mengembalikan response yang sesuai tanpa error server yang tidak terkontrol.

---

## TC-HIST-03 — Unauthorized Historical Access

**Given:**

Client tidak memiliki authorization.

**When:**

Client mencoba mengakses historical result.

**Then:**

API menolak request.

---

# 15. Concurrency Testing

## TC-CON-01 — Multiple Instrument Messages

**Given:**

Beberapa instrumen mengirim pesan pada waktu yang berdekatan.

**When:**

Integration Service menerima pesan secara bersamaan.

**Then:**

- Setiap pesan dikaitkan dengan instrumen yang benar.
- Tidak terjadi data mixing.
- Tidak terjadi kehilangan data.
- Database tetap konsisten.

---

## TC-CON-02 — Concurrent Final Run Selection

**Given:**

Dua request mencoba menetapkan Test Run berbeda sebagai final untuk order yang sama pada waktu hampir bersamaan.

**Then:**

Database tetap menjamin:

```text
Maximum 1 final Test Run / Order
```

Sistem tidak boleh menghasilkan dua final run.

---

# 16. Data Loss & Recovery Testing

## TC-REC-01 — Application Restart

**Given:**

Integration Service telah menerima dan menyimpan beberapa result.

**When:**

Service dihentikan dan dijalankan kembali.

**Then:**

Data yang sudah committed tetap tersedia di PostgreSQL.

---

## TC-REC-02 — Database Restart

**Given:**

PostgreSQL mengalami restart.

**When:**

Database kembali online.

**Then:**

Data yang telah committed tetap tersedia.

Integration Service harus dapat kembali terhubung setelah mekanisme recovery berjalan.

---

# 17. Security Testing

## TC-SEC-01 — Unauthorized API Access

API yang memerlukan authentication tidak dapat diakses tanpa credential yang valid.

---

## TC-SEC-02 — Unauthorized Clinical Data Modification

User/client tanpa permission tidak dapat:

```text
Modify Result
Delete Result
Modify Test Run Clinical Data
```

---

## TC-SEC-03 — Patient Data Exposure

API hanya mengembalikan data pasien sesuai scope dan authorization request.

Data pasien tidak boleh terekspos melalui endpoint yang tidak memerlukan akses tersebut.

---

# 18. Acceptance Criteria

LIS MVP dapat dianggap memenuhi QA baseline apabila:

### Integration

- [ ] Instrumen dapat mengirim data ke LIS.
- [ ] ASTM/HL7 dapat diproses sesuai spesifikasi instrumen.
- [ ] Batch transmission tidak menyebabkan data loss.
- [ ] Malformed message tidak menyebabkan service crash.
- [ ] Gangguan satu instrumen tidak menghentikan instrumen lain.

### Data Integrity

- [ ] Clinical value tetap sama dari instrument hingga dashboard.
- [ ] Clinical result tidak dapat diedit melalui API normal.
- [ ] Reference range snapshot tetap historis.
- [ ] Raw message dapat ditelusuri.

### Test Run

- [ ] Re-run menghasilkan Test Run baru.
- [ ] Test Run sebelumnya tidak tertimpa.
- [ ] Parameter tidak duplicate dalam satu Test Run.
- [ ] Satu Order maksimal memiliki satu final Test Run.
- [ ] Pemindahan final dilakukan secara atomic.

### UI

- [ ] Dashboard bersifat view-only terhadap clinical data.
- [ ] Instrument status terlihat.
- [ ] Test Run dapat dipilih.
- [ ] Final Run dapat diidentifikasi.
- [ ] Abnormal flag tidak hanya menggunakan warna.

### SIMRS

- [ ] Final Run dapat dikirim.
- [ ] Status `pending → sending → delivered/failed` bekerja.
- [ ] Retry bekerja.
- [ ] Clinical result tidak berubah akibat delivery.
- [ ] Historical Result API dapat mengambil data berdasarkan Nomor RM.
- [ ] Authorization diterapkan.

---

# 19. Test Evidence

Setiap test case yang dijalankan harus menghasilkan evidence yang sesuai.

Contoh evidence:

```text
Screenshot
API Response
Database Record
Raw Instrument Message
Application Log
Timestamp
Test Result
```

Untuk integration test, minimal simpan:

```text
Raw Message
       ↓
Parsed Data
       ↓
Database Record
       ↓
API Response
       ↓
UI Result
```

Hal ini memungkinkan validasi end-to-end terhadap data yang sama.

---

# 20. Defect Classification

Defect dikategorikan sebagai:

| Severity | Definition |
|---|---|
| Critical | Data klinis hilang, berubah, tercampur, atau service utama tidak dapat digunakan |
| High | Fungsi utama LIS gagal atau menyebabkan workflow klinis terganggu |
| Medium | Fungsi berjalan tetapi terdapat incorrect behavior yang tidak menyebabkan clinical data corruption |
| Low | Cosmetic issue atau minor usability problem |

### Critical Examples

```text
Instrument value berubah
Result pasien A masuk ke pasien B
Result hilang
Test Run sebelumnya tertimpa
Dua final run pada satu order
```

Defect kategori **Critical** harus diselesaikan sebelum MVP dianggap siap digunakan untuk operasional.

---

# 21. QA Sign-off Criteria

MVP dapat memasuki tahap deployment setelah:

1. Seluruh Critical test case berhasil.
2. Tidak terdapat Critical/High unresolved defect.
3. Data integrity test berhasil.
4. Re-run test berhasil.
5. Final Run constraint berhasil.
6. Multi-instrument isolation berhasil.
7. SIMRS delivery berhasil.
8. Historical Result API berhasil.
9. Strictly View-Only UI berhasil.
10. Evidence pengujian terdokumentasi.

---

# 22. Final QA Principle

> **The LIS must fail safely: communication failures may interrupt delivery, but they must never corrupt, overwrite, or silently alter laboratory results.**

Alur yang harus dipastikan melalui pengujian:

```text
Instrument
    ↓
Raw Message
    ↓
Parser
    ↓
Test Run
    ↓
Immutable Results
    ↓
Analyst Review
    ↓
Final Run
    ↓
SIMRS Delivery
```

Setiap tahap harus memiliki mekanisme untuk mendeteksi error, mempertahankan data yang telah berhasil disimpan, dan menyediakan traceability yang cukup untuk investigasi.