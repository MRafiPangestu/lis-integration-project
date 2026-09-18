# Database Design & Schema

## Laboratory Information System (LIS) Middleware

---

## 1. Database Overview

Database LIS menggunakan **PostgreSQL** sebagai database relasional utama untuk menyimpan data master, identitas pasien, riwayat kunjungan, permintaan pemeriksaan laboratorium, data pengujian instrumen, hasil pemeriksaan, serta rekam jejak komunikasi dengan instrumen.

Database dirancang untuk mendukung peran LIS sebagai **Middleware** dan **Device Gateway**, bukan sebagai sistem Rekam Medis Utama.

Prinsip utama desain database adalah:

* **Master Data** — menyimpan data referensi seperti unit, dokter, kelompok pemeriksaan, katalog tes, dan instrumen.
* **Patient Identity** — menyimpan identitas utama pasien berdasarkan Nomor RM.
* **Transactional History** — memisahkan identitas pasien dari riwayat kunjungan dan registrasi.
* **Order Management** — menyimpan permintaan pemeriksaan dalam suatu kunjungan.
* **Test Run Management** — menyimpan setiap sesi pengujian instrumen secara terpisah untuk mendukung *re-run*.
* **Result Immutability** — mempertahankan nilai hasil sebagaimana diterima dari instrumen.
* **Instrument Traceability** — memungkinkan setiap hasil ditelusuri kembali ke instrumen dan pesan mentah yang diterima.
* **Workflow Metadata** — menyimpan status operasional seperti pemilihan *final run* dan status pengiriman ke SIMRS tanpa mengubah data klinis asli.

Arsitektur hierarki utama:

```text
Patient
   │
   └── 1:N
       Visit
          │
          └── 1:N
              Order
                 │
                 └── 1:N
                     Test Run
                        │
                        └── 1:N
                            Result
```

---

# 2. Database Architecture

Database dibagi menjadi empat kelompok utama:

```text
MASTER DATA
├── units
├── doctors
├── test_groups
├── tests
└── instruments

PATIENT & TRANSACTION
├── patients
├── visits
└── orders

INSTRUMENT TRACEABILITY
└── instrument_messages

LABORATORY RESULT
├── test_runs
└── results
```

Relasi keseluruhan:

```text
patients
    │
    └──< visits
            │
            └──< orders
                    │
                    └──< test_runs
                            │
                            └──< results

instruments
    │
    ├──< instrument_messages
    │
    └──< test_runs

test_groups
    │
    └──< tests
```

---

# 3. Entity Relationship

## 3.1. Core Relationship

```text
patients (1)
    │
    │
    └──────────< visits (N)
                    │
                    │
                    └──────────< orders (N)
                                      │
                                      │
                                      └──────────< test_runs (N)
                                                          │
                                                          │
                                                          └──────────< results (N)
```

## 3.2. Instrument Traceability

```text
instruments (1)
    │
    ├──────────< instrument_messages (N)
    │
    └──────────< test_runs (N)

test_runs
    │
    └── id_message ──> instrument_messages
```

Dengan demikian, satu hasil dapat ditelusuri melalui dua jalur:

### Clinical / Transactional Traceability

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
  ↓
Nomor RM
```

### Technical Traceability

```text
Result
  ↓
Test Run
  ↓
Instrument Message
  ↓
Raw ASTM / HL7 Message
  ↓
Instrument
```

---

# 4. Master Data

## 4.1. `units`

Menyimpan master unit atau asal permintaan pemeriksaan.

| Column      | Type         | Constraint       | Description      |
| ----------- | ------------ | ---------------- | ---------------- |
| `id_unit`   | SERIAL       | PK               | ID internal unit |
| `kode_unit` | VARCHAR(20)  | UNIQUE, NOT NULL | Kode unit        |
| `nama_unit` | VARCHAR(100) | NOT NULL         | Nama unit        |

Contoh:

```text
IGD → Unit Gawat Darurat
IRJ → Instalasi Rawat Jalan
```

---

## 4.2. `doctors`

Menyimpan master dokter yang dapat menjadi peminta atau penanggung jawab pemeriksaan.

| Column         | Type         | Constraint | Description         |
| -------------- | ------------ | ---------- | ------------------- |
| `id_dokter`    | SERIAL       | PK         | ID internal dokter  |
| `nama_dokter`  | VARCHAR(150) | NOT NULL   | Nama dokter         |
| `spesialisasi` | VARCHAR(100) | NULL       | Spesialisasi dokter |

---

## 4.3. `test_groups`

Menyimpan kelompok pemeriksaan laboratorium.

| Column          | Type         | Constraint | Description     |
| --------------- | ------------ | ---------- | --------------- |
| `id_group`      | SERIAL       | PK         | ID kelompok     |
| `nama_group`    | VARCHAR(100) | NOT NULL   | Nama kelompok   |
| `urutan_tampil` | INT          | NULL       | Urutan tampilan |

Contoh:

```text
HEMATOLOGI
KIMIA DARAH
URINALISIS
IMUNOASSAY
ELEKTROLIT
KOAGULASI
```

---

## 4.4. `tests`

Menyimpan katalog parameter/pemeriksaan yang dikenali oleh LIS.

| Column           | Type         | Constraint                  | Description          |
| ---------------- | ------------ | --------------------------- | -------------------- |
| `id_test`        | SERIAL       | PK                          | ID pemeriksaan       |
| `id_group`       | INT          | FK → `test_groups.id_group` | Kelompok pemeriksaan |
| `kode_tes`       | VARCHAR(50)  | UNIQUE, NOT NULL            | Kode tes             |
| `nama_tes`       | VARCHAR(100) | NOT NULL                    | Nama pemeriksaan     |
| `satuan_default` | VARCHAR(20)  | NULL                        | Satuan default       |

Contoh:

```text
WBC
RBC
HGB
HCT
PLT
```

### Catatan

`tests` merupakan **master katalog internal LIS**.

Parameter aktual yang diterima dari instrumen disimpan pada:

```text
results.parameter_tes
```

LIS tidak boleh memaksa nilai aktual dari instrumen menjadi struktur master tertentu apabila mapping instrumen belum tersedia.

Mapping seperti:

```text
Sysmex WBC
      ↓
LIS WBC

Mindray WBC
      ↓
LIS WBC
```

merupakan tanggung jawab **Integration / Mapping Layer**, bukan alasan untuk mengubah nilai asli yang diterima.

---

## 4.5. `instruments`

Menyimpan identitas dan konfigurasi dasar instrumen laboratorium.

| Column          | Type         | Constraint | Description          |
| --------------- | ------------ | ---------- | -------------------- |
| `id_instrument` | SERIAL       | PK         | ID instrumen         |
| `nama_mesin`    | VARCHAR(100) | NOT NULL   | Nama/model mesin     |
| `protokol`      | VARCHAR(50)  | NULL       | ASTM / HL7 / lainnya |
| `tipe_koneksi`  | VARCHAR(50)  | NULL       | TCP/IP / lainnya     |

MVP mencakup:

| No | Instrumen              | Jenis                |
| -: | ---------------------- | -------------------- |
|  1 | Mindray BC-5150        | Hematology Analyzer  |
|  2 | Sysmex XN-550          | Hematology Analyzer  |
|  3 | Mindray BS-200E        | Chemistry Analyzer   |
|  4 | Sysmex BX-3010         | Chemistry Analyzer   |
|  5 | DFI R-300              | Urine Analyzer       |
|  6 | Insight Expert U120    | Urine Analyzer       |
|  7 | ichroma II             | Immunoassay Analyzer |
|  8 | Medica EasyLyte PLUS   | Electrolyte Analyzer |
|  9 | PRECIL 106-AC-57000131 | Coagulation Analyzer |

Detail seperti IP address, port, mode komunikasi, konfigurasi listener, format pesan, dan parameter spesifik alat tidak menjadi tanggung jawab utama database schema dan didefinisikan pada **System Design / Instrument Integration Specification**.

---

# 5. Patient Identity

## 5.1. `patients`

Menyimpan identitas utama pasien.

Nomor RM merupakan identifier pasien yang relatif permanen. Data transaksi seperti nomor registrasi dan pemeriksaan tidak disimpan langsung sebagai bagian dari identitas pasien.

| Column          | Type         | Constraint       | Description        |
| --------------- | ------------ | ---------------- | ------------------ |
| `id_pasien`     | SERIAL       | PK               | ID internal pasien |
| `nomor_rm`      | VARCHAR(50)  | UNIQUE, NOT NULL | Nomor rekam medis  |
| `nama_lengkap`  | VARCHAR(200) | NOT NULL         | Nama pasien        |
| `tanggal_lahir` | DATE         | NULL             | Tanggal lahir      |
| `jenis_kelamin` | CHAR(1)      | NULL             | Jenis kelamin      |

Relasi:

```text
patients 1 ─── N visits
```

Contoh:

```text
RM-000123
Budi Santoso

├── Visit 001
├── Visit 002
├── Visit 003
└── Visit 004
```

Dengan desain ini, riwayat pemeriksaan pasien tidak mengharuskan pembuatan record pasien baru untuk setiap kunjungan.

---

# 6. Transactional History

## 6.1. `visits`

`visits` merupakan representasi **transactional history / encounter history** pasien.

Tabel ini menjadi penghubung antara identitas pasien dan aktivitas pelayanan pada suatu kunjungan.

| Column            | Type        | Constraint                          | Description                |
| ----------------- | ----------- | ----------------------------------- | -------------------------- |
| `id_visit`        | SERIAL      | PK                                  | ID internal kunjungan      |
| `id_pasien`       | INT         | FK → `patients.id_pasien`, NOT NULL | Pasien                     |
| `no_registrasi`   | VARCHAR(50) | UNIQUE, NOT NULL                    | Nomor registrasi/encounter |
| `waktu_kunjungan` | TIMESTAMP   | NOT NULL                            | Waktu kunjungan            |
| `created_at`      | TIMESTAMP   | DEFAULT CURRENT_TIMESTAMP           | Waktu record dibuat        |

Relasi:

```text
Patient 1 ─── N Visit
```

Contoh:

```text
Patient: RM-000123

Visit #1001
No Registrasi: REG-2026-001

Visit #1023
No Registrasi: REG-2026-023

Visit #1187
No Registrasi: REG-2026-187
```

Hal ini memungkinkan LIS mempertahankan histori transaksi tanpa mengubah identitas pasien.

---

# 7. Laboratory Order

## 7.1. `orders`

`orders` merepresentasikan permintaan pemeriksaan laboratorium dalam suatu kunjungan.

| Column         | Type        | Constraint                       | Description             |
| -------------- | ----------- | -------------------------------- | ----------------------- |
| `id_order`     | SERIAL      | PK                               | ID internal order       |
| `id_visit`     | INT         | FK → `visits.id_visit`, NOT NULL | Kunjungan               |
| `id_unit`      | INT         | FK → `units.id_unit`             | Unit asal               |
| `id_dokter`    | INT         | FK → `doctors.id_dokter`         | Dokter                  |
| `diagnosa`     | TEXT        | NULL                             | Diagnosis jika tersedia |
| `waktu_order`  | TIMESTAMP   | DEFAULT CURRENT_TIMESTAMP        | Waktu order             |
| `status_order` | VARCHAR(50) | DEFAULT 'Diproses'               | Status workflow order   |

Relasi:

```text
Visit 1 ─── N Order
```

Contoh:

```text
Visit #1001

├── Order #5001 → Hematologi
├── Order #5002 → Kimia Darah
└── Order #5003 → Urinalisis
```

---

# 8. Instrument Message

## 8.1. `instrument_messages`

Menyimpan pesan mentah yang diterima dari instrumen.

Tabel ini merupakan bagian penting dari **technical traceability** dan debugging integrasi.

| Column          | Type        | Constraint                       | Description           |
| --------------- | ----------- | -------------------------------- | --------------------- |
| `id_message`    | SERIAL      | PK                               | ID pesan              |
| `id_instrument` | INT         | FK → `instruments.id_instrument` | Instrumen pengirim    |
| `raw_message`   | TEXT        | NOT NULL                         | Pesan ASTM/HL7 mentah |
| `parse_status`  | VARCHAR(50) | DEFAULT 'Success'                | Status parsing        |
| `received_at`   | TIMESTAMP   | DEFAULT CURRENT_TIMESTAMP        | Waktu pesan diterima  |

Contoh alur:

```text
Instrument
    ↓
TCP/IP
    ↓
Raw Message
    ↓
instrument_messages
    ↓
Parser
    ↓
Test Run
    ↓
Results
```

`raw_message` dipertahankan agar proses parsing dapat diinvestigasi kembali apabila terjadi masalah.

---

# 9. Test Run

## 9.1. `test_runs`

`test_runs` merupakan entitas inti untuk menangani **pengujian aktual oleh instrumen** dan **re-run**.

Satu `order` dapat menghasilkan lebih dari satu `test_run`.

```text
orders 1 ─── N test_runs
```

Setiap pengujian disimpan sebagai record terpisah.

| Column            | Type        | Constraint                                 | Description                       |
| ----------------- | ----------- | ------------------------------------------ | --------------------------------- |
| `id_run`          | SERIAL      | PK                                         | ID test run                       |
| `id_order`        | INT         | FK → `orders.id_order`, NOT NULL           | Order terkait                     |
| `id_instrument`   | INT         | FK → `instruments.id_instrument`, NOT NULL | Instrumen                         |
| `id_message`      | INT         | FK → `instrument_messages.id_message`      | Raw message sumber                |
| `run_sequence`    | INT         | NOT NULL                                   | Urutan run                        |
| `waktu_run`       | TIMESTAMP   | NULL                                       | Waktu pengujian menurut instrumen |
| `is_final`        | BOOLEAN     | DEFAULT FALSE                              | Penanda final run                 |
| `delivery_status` | VARCHAR(30) | DEFAULT 'pending'                          | Status pengiriman SIMRS           |
| `delivered_at`    | TIMESTAMP   | NULL                                       | Waktu berhasil dikirim            |
| `created_at`      | TIMESTAMP   | DEFAULT CURRENT_TIMESTAMP                  | Waktu record dibuat LIS           |

### Contoh

```text
Order #5001

Run #1
id_run = 101
is_final = FALSE

Run #2
id_run = 102
is_final = FALSE

Run #3
id_run = 103
is_final = TRUE
```

Ketiga run tetap tersimpan.

Tidak terjadi:

```text
Run #3 menggantikan Run #1 ❌
```

Melainkan:

```text
Run #1 ── preserved
Run #2 ── preserved
Run #3 ── final
```

---

# 10. Result

## 10.1. `results`

`results` menyimpan parameter individual yang dihasilkan oleh suatu `test_run`.

| Column                     | Type         | Constraint                        | Description                      |
| -------------------------- | ------------ | --------------------------------- | -------------------------------- |
| `id_hasil`                 | SERIAL       | PK                                | ID hasil                         |
| `id_run`                   | INT          | FK → `test_runs.id_run`, NOT NULL | Test run sumber                  |
| `parameter_tes`            | VARCHAR(50)  | NOT NULL                          | Parameter dari instrumen         |
| `nilai_hasil`              | VARCHAR(50)  | NOT NULL                          | Nilai hasil                      |
| `satuan`                   | VARCHAR(20)  | NULL                              | Satuan hasil                     |
| `flag_abnormalitas`        | VARCHAR(10)  | NULL                              | Flag dari instrumen              |
| `reference_range_snapshot` | VARCHAR(100) | NULL                              | Rentang referensi saat pengujian |
| `waktu_hasil`              | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP         | Waktu hasil diterima/disimpan    |

### Contoh

```text
Test Run #101

WBC → 8.40 → 10^3/uL → Normal
HGB → 13.2 → g/dL    → Normal
PLT → 450  → 10^3/uL → H
```

---

# 11. Result Immutability

Nilai klinis yang diterima dari instrumen diperlakukan sebagai **immutable data** setelah berhasil disimpan.

Field berikut tidak boleh diubah melalui aplikasi/API:

```text
parameter_tes
nilai_hasil
satuan
flag_abnormalitas
reference_range_snapshot
waktu_hasil
```

Prinsipnya:

```text
Instrument
    ↓
Original Result
    ↓
Stored Result
    ↓
Displayed Result
    ↓
SIMRS
```

Nilai klinis tidak boleh dimodifikasi pada salah satu tahap tersebut.

Analis hanya dapat melakukan tindakan workflow yang tidak mengubah nilai hasil, seperti memilih `test_run` sebagai final.

---

# 12. Re-run Management

## 12.1. One-to-Many Order → Test Run

Desain lama:

```text
Order 1 ─── 1 Result
```

tidak cukup untuk menangani pengujian ulang.

Desain final:

```text
Order 1 ─── N Test Runs
```

dan:

```text
Test Run 1 ─── N Results
```

Sehingga:

```text
Order #5001
│
├── Test Run #1
│    ├── WBC
│    ├── HGB
│    └── PLT
│
├── Test Run #2
│    ├── WBC
│    ├── HGB
│    └── PLT
│
└── Test Run #3
     ├── WBC
     ├── HGB
     └── PLT
```

Semua hasil tetap dapat ditelusuri.

---

# 13. Final Test Run

## 13.1. Finality Rule

Dalam satu `order`, hanya boleh terdapat **maksimal satu `test_run` dengan `is_final = TRUE`**.

Database memberikan perlindungan melalui **Partial Unique Index**:

```sql
CREATE UNIQUE INDEX idx_unique_final_run_per_order
ON test_runs (id_order)
WHERE is_final = TRUE;
```

Contoh:

```text
Order #5001

Run #1 → FALSE
Run #2 → TRUE
Run #3 → TRUE ❌
```

Database akan menolak kondisi tersebut.

---

## 13.2. Final Run Selection

Pemilihan final run tidak mengubah data klinis.

Contoh:

```text
Before:

Run #1 → TRUE
Run #2 → FALSE

Analyst selects Run #2

After:

Run #1 → FALSE
Run #2 → TRUE
```

Data pada:

```text
Run #1
Run #2
```

tetap sama.

Perubahan hanya terjadi pada metadata workflow:

```text
is_final
```

---

# 14. Duplicate Parameter Rule

Dalam satu `test_run`, parameter yang sama tidak boleh muncul lebih dari satu kali.

Constraint:

```sql
ALTER TABLE results
ADD CONSTRAINT uk_run_parameter
UNIQUE (id_run, parameter_tes);
```

Dengan demikian:

```text
Run #1 + WBC → valid
Run #2 + WBC → valid
Run #3 + WBC → valid
```

karena setiap run berbeda.

Namun:

```text
Run #1 + WBC
Run #1 + WBC
```

ditolak karena merupakan duplikasi dalam satu run.

Constraint lama:

```sql
UNIQUE (id_order, parameter_tes)
```

**tidak digunakan lagi** karena akan menghalangi penyimpanan hasil re-run.

---

# 15. SIMRS Delivery Metadata

Pengiriman ke SIMRS dilakukan berdasarkan **Test Run final**.

Metadata pengiriman disimpan pada `test_runs`:

```text
delivery_status
delivered_at
```

Lifecycle minimal:

```text
pending
   │
   ▼
sending
   │
   ├── success → delivered
   │
   └── failure → failed
```

Nilai pada `results` tidak berubah selama proses pengiriman.

Contoh:

```text
Test Run #103
is_final = TRUE
delivery_status = pending

        ↓

POST to SIMRS

        ↓

delivery_status = delivered
delivered_at = timestamp
```

Jika pengiriman gagal:

```text
delivery_status = failed
```

dan hasil klinis tetap tersimpan.

---

# 16. Data Traceability

Setiap hasil pemeriksaan harus dapat ditelusuri sampai ke sumbernya.

## 16.1. Clinical Traceability

```text
results
   ↓
test_runs
   ↓
orders
   ↓
visits
   ↓
patients
   ↓
nomor_rm
```

Contoh:

```text
WBC = 8.40
   ↓
Test Run #103
   ↓
Order #5001
   ↓
Visit #1001
   ↓
Patient #25
   ↓
RM-000123
```

## 16.2. Instrument Traceability

```text
results
   ↓
test_runs
   ↓
instruments
```

## 16.3. Raw Message Traceability

```text
results
   ↓
test_runs
   ↓
instrument_messages
   ↓
raw_message
```

Dengan demikian, ketika terjadi masalah parsing, sistem dapat melakukan investigasi terhadap pesan asli yang diterima.

---

# 17. Timestamp Strategy

Database membedakan waktu yang berasal dari instrumen dengan waktu yang berasal dari server LIS.

## `waktu_run`

Merepresentasikan waktu pengujian yang berasal dari instrumen atau data komunikasi instrumen.

```text
waktu_run = Instrument Time
```

## `received_at`

Merepresentasikan waktu ketika server LIS menerima raw message.

```text
received_at = LIS Reception Time
```

## `created_at`

Merepresentasikan waktu ketika record database dibuat oleh LIS.

```text
created_at = Database Record Creation Time
```

Ketiga timestamp tersebut tidak boleh dianggap sebagai hal yang sama.

Contoh:

```text
10:15:01 → Instrumen melakukan pengujian
10:15:03 → LIS menerima message
10:15:03 → LIS menyimpan record
```

Maka:

```text
waktu_run    = 10:15:01
received_at  = 10:15:03
created_at   = 10:15:03
```

Perbedaan tersebut penting untuk debugging komunikasi dan audit sistem.

---

# 18. Data Type Decisions

## 18.1. Primary Key

Primary key menggunakan `SERIAL` sebagai ID internal database.

Contoh:

```text
id_pasien
id_visit
id_order
id_run
id_hasil
id_message
```

ID internal digunakan sebagai foreign key dan tidak bergantung pada identifier eksternal SIMRS.

---

## 18.2. `nomor_rm`

`nomor_rm` menggunakan:

```sql
VARCHAR(50)
```

karena format Nomor RM merupakan identifier eksternal dan tidak seharusnya diperlakukan sebagai angka untuk operasi matematika.

Constraint:

```sql
UNIQUE
NOT NULL
```

---

## 18.3. `nilai_hasil`

`nilai_hasil` menggunakan:

```sql
VARCHAR(50)
```

karena hasil instrumen tidak selalu berupa angka murni.

Contoh:

```text
12.4
NEGATIVE
POSITIVE
>100
<0.5
TRACE
++++
```

LIS bertugas **mempertahankan representasi hasil dari instrumen**, bukan memaksa semua hasil menjadi tipe numerik.

---

## 18.4. `reference_range_snapshot`

Rentang referensi disimpan sebagai snapshot pada saat pemeriksaan.

Tujuannya agar perubahan konfigurasi referensi di masa depan tidak mengubah interpretasi historis data yang telah tersimpan.

---

# 19. Referential Integrity

Foreign key digunakan untuk mempertahankan integritas relasi.

```text
visits.id_pasien
        ↓
patients.id_pasien

orders.id_visit
        ↓
visits.id_visit

orders.id_unit
        ↓
units.id_unit

orders.id_dokter
        ↓
doctors.id_dokter

tests.id_group
        ↓
test_groups.id_group

test_runs.id_order
        ↓
orders.id_order

test_runs.id_instrument
        ↓
instruments.id_instrument

test_runs.id_message
        ↓
instrument_messages.id_message

results.id_run
        ↓
test_runs.id_run

instrument_messages.id_instrument
        ↓
instruments.id_instrument
```

Data hasil dan pesan instrumen merupakan bagian dari histori dan tidak boleh dihapus sembarangan.

Untuk MVP, penghapusan data historis secara *cascade* tidak direkomendasikan.

---

# 20. Indexing Strategy

Index tambahan direkomendasikan pada kolom yang sering digunakan untuk pencarian dan join.

```sql
CREATE INDEX idx_visits_patient
ON visits (id_pasien);

CREATE INDEX idx_orders_visit
ON orders (id_visit);

CREATE INDEX idx_test_runs_order
ON test_runs (id_order);

CREATE INDEX idx_test_runs_instrument
ON test_runs (id_instrument);

CREATE INDEX idx_results_run
ON results (id_run);

CREATE INDEX idx_instrument_messages_instrument
ON instrument_messages (id_instrument);
```

Unique constraint juga menghasilkan index secara otomatis pada:

```text
patients.nomor_rm
visits.no_registrasi
tests.kode_tes
```

Partial unique index digunakan untuk final run:

```sql
CREATE UNIQUE INDEX idx_unique_final_run_per_order
ON test_runs (id_order)
WHERE is_final = TRUE;
```

---

# 21. Database Business Rules

| Rule                                          | Enforcement                                 |
| --------------------------------------------- | ------------------------------------------- |
| Nomor RM harus unik                           | `UNIQUE patients.nomor_rm`                  |
| Nomor registrasi harus unik                   | `UNIQUE visits.no_registrasi`               |
| Kode tes harus unik                           | `UNIQUE tests.kode_tes`                     |
| Satu pasien dapat memiliki banyak visit       | FK + relationship                           |
| Satu visit dapat memiliki banyak order        | FK + relationship                           |
| Satu order dapat memiliki banyak test run     | FK + relationship                           |
| Satu test run dapat memiliki banyak result    | FK + relationship                           |
| Re-run tidak boleh menimpa run sebelumnya     | Tidak ada `UNIQUE(id_order, parameter_tes)` |
| Parameter tidak boleh duplikat dalam satu run | `UNIQUE(id_run, parameter_tes)`             |
| Satu order maksimal satu final run            | Partial Unique Index                        |
| Nilai klinis tidak boleh diedit               | Application/API rule                        |
| Raw message harus dapat ditelusuri            | `instrument_messages`                       |
| Status pengiriman dapat berubah               | `test_runs.delivery_status`                 |
| Hasil dapat ditelusuri ke pasien              | `Result → Run → Order → Visit → Patient`    |
| Hasil dapat ditelusuri ke instrumen           | `Result → Run → Instrument`                 |
| Hasil dapat ditelusuri ke raw message         | `Result → Run → Message`                    |

---

# 22. Relationship Cardinality

Cardinality final:

```text
patients
   │
   │ 1:N
   ▼
visits
   │
   │ 1:N
   ▼
orders
   │
   │ 1:N
   ▼
test_runs
   │
   │ 1:N
   ▼
results
```

Master relationship:

```text
test_groups
   │
   │ 1:N
   ▼
tests
```

```text
instruments
   │
   ├── 1:N ── instrument_messages
   │
   └── 1:N ── test_runs
```

---

# 23. Final Schema Concept

Struktur database final:

```text
┌──────────────────────┐
│      MASTER DATA     │
├──────────────────────┤
│ units                │
│ doctors              │
│ test_groups          │
│ tests                │
│ instruments          │
└──────────────────────┘

┌──────────────────────┐
│ PATIENT & TRANSACTION│
├──────────────────────┤
│ patients             │
│ visits               │
│ orders               │
└──────────────────────┘

┌──────────────────────┐
│ INSTRUMENT TRACE     │
├──────────────────────┤
│ instrument_messages  │
└──────────────────────┘

┌──────────────────────┐
│ LABORATORY RESULTS   │
├──────────────────────┤
│ test_runs            │
│ results              │
└──────────────────────┘
```

Core flow:

```text
Patient
   │
   ▼
Visit
   │
   ▼
Order
   │
   ├───────────────┐
   │               │
   ▼               ▼
Test Run #1      Test Run #2
   │               │
   ▼               ▼
Results          Results
```

---

# 24. Alignment with LIS Workflow

Database mendukung alur sistem:

```text
LAB INSTRUMENT
      │
      │ ASTM / HL7
      ▼
INSTRUMENT MESSAGE
      │
      │ Parse
      ▼
TEST RUN
      │
      ▼
RESULTS
      │
      ▼
DATABASE
      │
      ▼
LIS DASHBOARD
      │
      │ Analyst selects final run
      ▼
FINAL TEST RUN
      │
      │ POST
      ▼
SIMRS
```

Database tidak melakukan perubahan terhadap nilai klinis pada alur tersebut.

---

# 25. Separation of Clinical Data and Workflow Metadata

Desain membedakan dua jenis informasi:

## Clinical Data

Data yang berasal dari instrumen:

```text
parameter_tes
nilai_hasil
satuan
flag_abnormalitas
reference_range_snapshot
waktu_hasil
```

Data ini bersifat immutable.

## Workflow Metadata

Data yang digunakan untuk mengendalikan proses LIS:

```text
is_final
delivery_status
delivered_at
```

Metadata tersebut dapat berubah sesuai workflow tanpa mengubah data klinis.

Tabel `users` (autentikasi API, M9.1a) juga termasuk Workflow Metadata — lihat Bagian 33. Tabel ini mengendalikan *siapa* yang boleh menjalankan workflow, bukan data klinis itu sendiri, dan tidak memiliki relasi foreign key ke hierarki `patients → visits → orders → test_runs → results` di atas.

Tabel `audit_events` (atribusi aktor, M9.1b) juga termasuk Workflow Metadata — lihat Bagian 34. Tabel ini mencatat *siapa melakukan apa* pada workflow, bukan data klinis itu sendiri; `entity_id` di dalamnya menunjuk ke `test_runs` atau `users` secara polimorfik (bukan foreign key), dan `id_user` adalah satu-satunya foreign key pada tabel ini (ke `users.id_user`).

Dengan demikian:

```text
Clinical Data
     │
     └── IMMUTABLE

Workflow Metadata
     │
     └── MUTABLE
```

---

# 26. Important Design Boundary

Database LIS **tidak menjadi sumber kebenaran utama untuk identitas dan rekam medis pasien**.

LIS hanya menyimpan data yang diperlukan untuk menjalankan fungsi middleware dan menjaga traceability.

Sumber data eksternal seperti:

```text
Patient Identity
Registration
Order
```

dapat berasal dari SIMRS atau mekanisme integrasi yang disepakati.

Oleh karena itu, desain database harus memungkinkan identifier eksternal seperti:

```text
Nomor RM
Nomor Registrasi
```

tetap dipertahankan tanpa menjadikan LIS sebagai pengganti SIMRS.

---

# 27. Migration from Previous Schema

Schema sebelumnya menggunakan struktur:

```text
orders
   │
   └── results
```

dengan constraint:

```sql
UNIQUE (id_order, parameter_tes)
```

Struktur tersebut tidak dapat menangani re-run dengan benar.

Desain final mengubahnya menjadi:

```text
orders
   │
   └── test_runs
          │
          └── results
```

Selain itu, relasi pasien diubah dari:

```text
orders → patients
```

menjadi:

```text
orders → visits → patients
```

Perubahan ini memungkinkan:

```text
1 Patient
   ↓
N Visits
   ↓
N Orders
   ↓
N Test Runs
   ↓
N Results
```

---

# 28. Required Schema Changes from Initial SQL

SQL awal proyek belum sepenuhnya mencerminkan desain final.

Perubahan minimum yang diperlukan adalah:

### 1. Menambahkan `visits`

```text
patients → visits → orders
```

### 2. Menambahkan `test_runs`

```text
orders → test_runs → results
```

### 3. Memindahkan hubungan instrument dari `results` ke `test_runs`

Sebelumnya:

```text
results.id_instrument
```

menjadi:

```text
test_runs.id_instrument
```

### 4. Memindahkan traceability message ke `test_runs`

Sebelumnya:

```text
results.id_message
```

menjadi:

```text
test_runs.id_message
```

### 5. Menghapus constraint lama

```sql
UNIQUE (id_order, parameter_tes)
```

### 6. Menambahkan constraint baru

```sql
UNIQUE (id_run, parameter_tes)
```

### 7. Menambahkan finality rule

```sql
CREATE UNIQUE INDEX idx_unique_final_run_per_order
ON test_runs (id_order)
WHERE is_final = TRUE;
```

### 8. Menghapus workflow validation dari `results`

Field seperti:

```text
status_hasil
divalidasi_oleh
waktu_validasi
```

tidak digunakan sebagai sumber status final.

Pemilihan final dilakukan pada:

```text
test_runs.is_final
```

Hal ini menghindari dua sumber kebenaran antara:

```text
results.status_hasil
```

dan:

```text
test_runs.is_final
```

---

# 29. Provisioning & Migration Lifecycle

Sejak M9.0, database LIS dapat di-*provision* sepenuhnya melalui Alembic. *Migration chain* memiliki **satu root** (`8e973e84a9d7`, disebut **R0**) dan **satu head** (`8a3023944bd1`, sejak XN-550 G2):

```text
8e973e84a9d7   R0 — baseline skema legacy pra-M1 (evidence-derived)
     ↓
b1f9dbe772fa   M1 — transformasi ke desain final (visits, test_runs, dst.)
     ↓
4a24240f8c32   no-op historis (upgrade/downgrade = pass)
     ↓
621889e316b5   instrument runtime status (connection_status, last_status_at)
     ↓
c5465739f048   message classification (message_class, classification_rule)
     ↓
4aff9e134f16   M8.4 — index untuk order overview
     ↓
27e00bcff992   M9.1a — tabel users (autentikasi)
     ↓
28aa370f5dbe   M9.1b — tabel audit_events (atribusi aktor)
     ↓
5d2e8b7c41a9   XN-550 Phase 1 — instrument_sessions + provenance raw capture
     ↓
8a3023944bd1   XN-550 G2 — instrument_result_sets + instrument_result_items   ← HEAD
```

Bagian ini menggantikan asumsi lama bahwa "SQL awal" harus dieksekusi manual sebelum migrasi. R0 kini merepresentasikan skema legacy tersebut di dalam *migration graph* yang dikelola versi (commit `d273e7f`), dan `alembic upgrade head` dari database kosong menghasilkan skema final tanpa langkah manual. `27e00bcff992` (M9.1a), `28aa370f5dbe` (M9.1b) dan `5d2e8b7c41a9` (XN-550 Phase 1) ditulis manual (*hand-authored*), bukan hasil `--autogenerate` — lihat Bagian 33, 34 dan 35 untuk alasannya.

## 29.1. Instalasi baru (database kosong)

Jalur *fresh-install* yang otoritatif:

1. Buat database PostgreSQL kosong.
2. Arahkan konfigurasi koneksi aplikasi ke database tersebut (`DB_HOST=<host>`, `DB_PORT=<port>`, `DB_NAME=<database>`, `DB_USER=<user>`, dan kredensial melalui mekanisme `.env` proyek).
3. Jalankan:

   ```bash
   alembic upgrade head
   ```

4. Hasil: seluruh chain `R0 → b1f9dbe772fa → 4a24240f8c32 → 621889e316b5 → c5465739f048 → 4aff9e134f16 → 27e00bcff992 → 28aa370f5dbe → 5d2e8b7c41a9 → 8a3023944bd1` diterapkan; tabel `alembic_version` berisi `8a3023944bd1`.
5. **(M9.1a)** Buat akun ADMIN pertama secara interaktif:

   ```bash
   py scripts/create_admin.py --username <nama>
   ```

   Skrip ini **tidak** dijalankan otomatis oleh migrasi atau saat startup aplikasi (lihat Bagian 33) — tanpa langkah ini, sistem terkunci sepenuhnya (*deny-by-default* tanpa akun berarti tidak ada yang bisa login, yang merupakan mode kegagalan yang benar).

Database PostgreSQL yang benar-benar kosong kini dapat di-*provision* **sepenuhnya melalui Alembic**. Operator **tidak** perlu — dan tidak boleh diinstruksikan — menjalankan `backend/schema/legacy_schema.sql` secara manual sebagai bagian dari *fresh-install* normal. File tersebut adalah artefak *evidence*, bukan perintah provisioning (lihat Bagian 29.5).

Verifikasi otomatis: `backend/tests/test_migration_chain.py` (commit `b7c3d0e`; diperluas pada M9.1a untuk tabel `users`, pada M9.1b untuk tabel `audit_events`, pada XN-550 Phase 1 untuk `instrument_sessions` serta kolom *raw capture* `instrument_messages`, dan pada XN-550 G2 untuk kedua tabel observasi — termasuk uji paritas ORM/migrasi dan *downgrade* G2) menjalankan `alembic upgrade head` terhadap database sekali-pakai dan memeriksa revisi akhir serta invariant struktural skema (jumlah tabel/constraint/index, keberadaan objek M1/M8.2/M8.4/M9.1a/M9.1b/XN-550 Phase 1/XN-550 G2, dan absennya objek yang belum di-remediasi).

> **Catatan F-2.** *Fresh-install chain* saat ini menghasilkan `patients.nomor_rm` sebagai `NOT NULL` tetapi **belum** `UNIQUE`. Constraint `UNIQUE(nomor_rm)` pada Bagian 18.2 adalah desain target; migration untuk menambahkannya adalah **remediasi terpisah yang belum ada di chain**. M9.0 tidak menyelesaikan item ini, dan M9.1a maupun M9.1b juga tidak menyentuhnya — lihat Bagian 33 dan Bagian 34.

## 29.2. Instalasi legacy yang sudah ada

Untuk deployment legacy yang sudah berjalan dengan skema pra-M1:

- 9 tabel legacy: `doctors`, `instrument_messages`, `instruments`, `orders`, `patients`, `results`, `test_groups`, `tests`, `units`;
- **tanpa** tabel `alembic_version`;
- skema sesuai `backend/schema/legacy_schema.sql`.

Jalur migrasi:

1. **Backup** database.
2. **Verifikasi manual** bahwa skema database benar-benar cocok dengan skema R0 / pra-M1 (bandingkan dengan `backend/schema/legacy_schema.sql` atau `backend/schema/canonical_legacy_schema.sql`).
3. **Jangan** menjalankan `alembic upgrade 8e973e84a9d7` terhadap database legacy yang sudah berisi skema tersebut.
4. *Stamp* database pada R0:

   ```bash
   alembic stamp 8e973e84a9d7
   ```

5. Lalu jalankan:

   ```bash
   alembic upgrade head
   ```

6. **(M9.1a)** Buat akun ADMIN pertama — identik dengan langkah 5 pada Bagian 29.1 (`py scripts/create_admin.py --username <nama>`).

**Mengapa *stamp*, bukan *upgrade*:** R0 berisi statement `CREATE TABLE` / `CREATE SEQUENCE` / `ADD CONSTRAINT` untuk skema yang **sudah ada** di database legacy. Menjalankan `upgrade` R0 akan mencoba membuat ulang objek tersebut dan gagal. `alembic stamp` hanya menulis revisi awal yang diketahui ke `alembic_version` **tanpa mengeksekusi DDL R0**, sehingga `alembic upgrade head` berikutnya melanjutkan dari `b1f9dbe772fa` (transformasi M1) di atas skema legacy yang nyata.

> **Peringatan.**
> - `alembic stamp` **tidak** memverifikasi kompatibilitas skema secara otomatis. *Stamp* hanya benar setelah operator memastikan database memang cocok dengan skema R0 / pra-M1.
> - *Stamp* yang salah menyebabkan migrasi berjalan dari *state* skema yang keliru dan dapat merusak data.
> - Backup **wajib** sebelum migrasi lingkungan yang sudah berisi data.

## 29.3. Database development yang sudah ada

`lis_marina_permata_dev` berada pada `8a3023944bd1` (XN-550 G2 — sebelumnya `5d2e8b7c41a9` pada XN-550 Phase 1, `28aa370f5dbe` pada M9.1b, `27e00bcff992` pada M9.1a, dan `4aff9e134f16` sebelum itu). *Upgrade* ke `8a3023944bd1` dijalankan pada 2026-09-18 dengan `alembic upgrade head`: aditif saja (dua tabel baru, keduanya kosong), seluruh data yang ada tidak berubah, dan tidak ada operasi destruktif. R0 adalah **leluhur** revisi tersebut, bukan migrasi yang perlu diputar ulang. **Jangan** menjalankan R0 langsung terhadap database ini. Jika ada revisi baru di masa depan, `alembic upgrade head` biasa akan melanjutkan dari revisi saat ini.

## 29.4. Database PoC stabil / sumber evidence

`lis_marina_permata` adalah PoC stabil sekaligus sumber *evidence* untuk R0. Database ini **tidak**:

- di-migrasi;
- di-*stamp*;
- diubah

oleh alur *provisioning* M9.0. Tidak ada instruksi dalam dokumen ini yang menargetkannya. Skema legacy-nya dipreservasi sebagai `backend/schema/legacy_schema.sql`.

## 29.5. Peran R0 dan `4a24240f8c32`

**R0 (`8e973e84a9d7`)** — baseline skema legacy pra-M1 yang **diturunkan dari evidence**, bukan direkonstruksi atau ditebak. Empat artefak yang harus dibedakan:

| # | Peran | File | SHA-256 |
|---|---|---|---|
| 1 | Artefak *evidence* (`pg_dump --schema-only` dari `lis_marina_permata`) | `backend/schema/legacy_schema.sql` | `93d902f67e334c0d6b7ea0ce36a2c81cbb5292781b7d45a920b5cbc67199c81e` |
| 2 | Baseline kanonik (diturunkan deterministik dari #1) | `backend/schema/canonical_legacy_schema.sql` | `a75046a8dd9b5da4454581ffa8552c5af0e7af7bc380ace6092ddab293e7125d` |
| 3 | Migration **eksekutabel** (menjalankan DDL kanonik) | `backend/alembic/versions/8e973e84a9d7_r0_legacy_baseline.py` (commit `d273e7f`) | — |
| 4 | Revisi **no-op historis** | `backend/alembic/versions/4a24240f8c32_legacy_baseline.py` | — |

Prosedur kanonikalisasi #1 → #2 ada di `backend/schema/canonicalize_legacy_schema.py`.

R0 sengaja mempertahankan karakteristik legacy dan **tidak** menormalkannya:

- mekanisme SERIAL (`CREATE SEQUENCE` + `OWNED BY` + `DEFAULT nextval(...)`), **bukan** `IDENTITY`;
- kolom legacy yang kemudian dihapus M1 (mis. `orders.no_registrasi`, `orders.id_pasien`, `results.id_order`, `results.id_instrument`, `results.id_message`, `results.status_hasil`, `results.divalidasi_oleh`, `results.waktu_validasi`);
- nama constraint legacy yang persis (beberapa di antaranya di-*drop* by name oleh `b1f9dbe772fa`);
- `patients.nomor_rm` `NOT NULL` tetapi **NON-UNIQUE**.

R0 **bukan** skema final saat ini — R0 adalah **akar historis** yang diperlukan untuk merekonstruksi *migration chain*. Skema final adalah hasil `alembic upgrade head` (Bagian 32).

**`4a24240f8c32` (`4a24240f8c32_legacy_baseline.py`)** — revisi **no-op historis**:

- `upgrade()` = `pass`;
- `downgrade()` = `pass`;
- **tidak** membuat skema legacy;
- **tidak** berfungsi sebagai R0;
- tetap ada di *graph* untuk kontinuitas historis.

Nama lama "legacy_baseline" pada revisi ini bersifat historis dan **tidak boleh** disamakan dengan R0. Baseline legacy yang sesungguhnya (evidence-derived) adalah R0 `8e973e84a9d7`. Revisi `4a24240f8c32` **tidak** dihapus, di-*rename*, atau diubah.

## 29.6. Evolusi skema (migration chain)

| Revisi | Peran |
|---|---|
| `8e973e84a9d7` (R0) | skema legacy pra-M1 (evidence-derived) |
| `b1f9dbe772fa` | transformasi M1 — `visits`, `test_runs`, pemindahan traceability instrument/message ke `test_runs`, penghapusan `UNIQUE(id_order, parameter_tes)`, penambahan `UNIQUE(id_run, parameter_tes)` dan *finality rule* |
| `4a24240f8c32` | no-op historis (*stamp*) |
| `621889e316b5` | instrument runtime status — `instruments.connection_status`, `instruments.last_status_at` |
| `c5465739f048` | message classification — `instrument_messages.message_class`, `instrument_messages.classification_rule` |
| `4aff9e134f16` | empat index query untuk M8.4 order overview |
| `27e00bcff992` | M9.1a — tabel `users` (autentikasi API); lihat Bagian 33 |
| `28aa370f5dbe` | M9.1b — tabel `audit_events` (atribusi aktor); lihat Bagian 34 |
| `5d2e8b7c41a9` | XN-550 Phase 1 — tabel `instrument_sessions` dan kolom provenance *raw capture* (nullable) pada `instrument_messages`; lihat Bagian 35 |
| `8a3023944bd1` (HEAD) | XN-550 G2 — tabel `instrument_result_sets` dan `instrument_result_items` (observasi tak tertaut); lihat Bagian 36 |

## 29.7. Peringatan operasional

- **Downgrade penuh tidak didukung.** Bagian ini adalah dokumentasi *upgrade* / *provisioning*. `b1f9dbe772fa.downgrade()` memiliki cacat yang diketahui (menghapus *foreign key* tanpa nama) dan merupakan remediasi terpisah; jangan mengandalkan `alembic downgrade` melewati M1.
- Jangan menjalankan migrasi terhadap `lis_marina_permata`.
- Selalu *backup* lingkungan yang berisi data sebelum migrasi.
- `alembic stamp` tidak memverifikasi skema; verifikasi manual adalah tanggung jawab operator.
- `alembic check` **belum** bersih terhadap database hasil chain: empat index M8.4 belum dideklarasikan di metadata ORM, sehingga *autogenerate* mengusulkan `DROP INDEX`. Ini adalah item drift ORM yang terpisah dan belum di-remediasi — jangan jadikan `alembic check` sebagai *gate* provisioning untuk saat ini.
- `backend/schema/legacy_schema.sql` dan `backend/schema/canonical_legacy_schema.sql` adalah artefak *evidence* / baseline untuk menurunkan dan mempreservasi R0 — **bukan** perintah *provisioning* untuk instalasi baru.

---

# 30. Final Design Principle

Prinsip utama database LIS adalah:

> **Preserve the original laboratory result, preserve its history, and make every result traceable.**

Implementasinya:

```text
Original Instrument Message
          ↓
      Test Run
          ↓
       Results
          ↓
   Immutable History
          ↓
 Analyst selects Final Run
          ↓
     SIMRS Delivery
```

Database tidak menganggap hasil terbaru sebagai pengganti otomatis hasil sebelumnya.

Setiap pengujian merupakan bagian dari histori.

---

# 31. Final Database Requirements

Database final harus mendukung:

1. PostgreSQL sebagai relational database utama.
2. Identitas pasien berdasarkan Nomor RM.
3. Pemisahan `patients` dan `visits`.
4. Riwayat kunjungan/transactional history.
5. Relasi `Visit → Order`.
6. Relasi `Order → Test Run`.
7. Relasi `Test Run → Result`.
8. Penyimpanan raw ASTM/HL7 message.
9. Traceability hasil hingga instrumen dan raw message.
10. Penyimpanan seluruh re-run tanpa overwrite.
11. Pemilihan maksimal satu final run per order.
12. Perlindungan final run menggunakan Partial Unique Index.
13. Pencegahan duplikasi parameter dalam satu run.
14. Penyimpanan nilai hasil dalam bentuk yang mempertahankan representasi instrumen.
15. Penyimpanan snapshot reference range.
16. Pemisahan clinical data dan workflow metadata.
17. Metadata pengiriman hasil final ke SIMRS.
18. Dukungan terhadap integrasi hingga 9 instrumen dalam MVP.
19. Referential integrity melalui foreign key.
20. Indexing untuk kebutuhan query operasional dan integrasi.

---

# 32. Final Schema Summary

```text
                    ┌──────────────┐
                    │   patients   │
                    └──────┬───────┘
                           │
                          1:N
                           │
                    ┌──────▼───────┐
                    │    visits    │
                    └──────┬───────┘
                           │
                          1:N
                           │
                    ┌──────▼───────┐
                    │    orders    │
                    └──────┬───────┘
                           │
                          1:N
                           │
                    ┌──────▼───────┐
                    │  test_runs   │
                    └──────┬───────┘
                           │
                          1:N
                           │
                    ┌──────▼───────┐
                    │   results    │
                    └──────────────┘


instruments
     │
     ├────────────── 1:N ──────────────► instrument_messages
     │
     └────────────── 1:N ──────────────► test_runs


test_groups
     │
     └────────────── 1:N ──────────────► tests
```

**Status dokumen:** Final untuk menjadi acuan database architecture LIS MVP — diagram di atas merepresentasikan hierarki **Clinical Data** dan *master data* terkait.

**Catatan implementasi:** SQL awal yang diberikan sebelumnya merupakan baseline/schema awal dan **belum sepenuhnya sama dengan desain final ini**. Implementasi PostgreSQL harus mengikuti desain final di atas, terutama penambahan `visits` dan `test_runs`, penghapusan `UNIQUE(id_order, parameter_tes)`, serta penerapan Partial Unique Index untuk `is_final`. Sejak M9.0, "SQL awal" tersebut terpreservasi sebagai *evidence* R0 (`backend/schema/legacy_schema.sql`) dan **tidak** dijalankan manual pada instalasi baru — prosedur *provisioning* yang otoritatif (fresh-install dan *upgrade* dari legacy) ada di **Bagian 29**.

**Catatan M9.1a:** tabel `users` (autentikasi API) ditambahkan setelah head migrasi ini sebagai *Workflow Metadata* terpisah — lihat Bagian 33. Tabel tersebut sengaja **tidak** digambarkan pada diagram di atas karena tidak memiliki relasi foreign key ke hierarki klinis manapun; diagram di atas tetap final untuk data klinis.

**Catatan M9.1b:** tabel `audit_events` (atribusi aktor) ditambahkan setelah `users` sebagai *Workflow Metadata* tambahan — lihat Bagian 34. Tabel ini juga sengaja **tidak** digambarkan pada diagram di atas: satu-satunya foreign key-nya menunjuk ke `users`, bukan ke hierarki klinis, dan `entity_id`-nya bersifat polimorfik (bukan foreign key sama sekali).

---

# 33. Users Table — Authentication (M9.1a)

**Tujuan.** Tabel `users` menyimpan akun aplikasi untuk autentikasi API (JWT Bearer) yang diimplementasikan pada M9.1a. Ini adalah *Workflow Metadata* (Bagian 25) — mengendalikan siapa yang boleh menjalankan workflow LIS, bukan data klinis — dan **tidak** menjadikan LIS sebagai sumber kebenaran identitas pengguna rumah sakit di luar konteks login aplikasi ini (konsisten dengan batas desain di Bagian 26, yang berbicara tentang identitas **pasien**, bukan akun staf LIS).

**Migrasi.** `backend/alembic/versions/27e00bcff992_m9_1a_add_users_table.py`, `down_revision = "4aff9e134f16"` — revisi tunggal setelah HEAD M8.4, ditulis manual (*hand-authored*), **bukan** hasil `alembic revision --autogenerate`. Alasan: skema saat ini memiliki dua drift ORM yang diketahui dan sengaja belum diremediasi — F-2 (`patients.nomor_rm` belum `UNIQUE`) dan F-3 (empat index M8.4 ada di chain tapi tidak di model ORM manapun). `--autogenerate` pada titik ini akan mengusulkan penambahan `UNIQUE(patients.nomor_rm)` yang belum disetujui **dan** penghapusan keempat index M8.4 — keduanya di luar cakupan M9.1a. Migrasi `27e00bcff992` **hanya** membuat tabel `users`; F-2, F-3, dan defek *downgrade* `b1f9dbe772fa` (F-4) tetap menjadi remediasi terpisah, tidak disentuh, tidak diperparah.

**Kolom dan constraint yang diimplementasikan** (`app/models/user.py`):

| Kolom | Tipe | Constraint |
|---|---|---|
| `id_user` | `SERIAL` (PK, autoincrement) | Primary key. **Bukan** `IDENTITY` — mengikuti konvensi SERIAL seluruh skema (kaidah fidelitas M9.0) |
| `username` | `VARCHAR(50)` | `NOT NULL`, `UNIQUE` (`users_username_key`) |
| `nama_lengkap` | `VARCHAR(100)` | `NOT NULL` |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` — menyimpan output Argon2id yang sudah di-encode, tidak pernah plaintext |
| `role` | `VARCHAR(20)` | `NOT NULL` |
| `is_active` | `BOOLEAN` | `NOT NULL`, `server_default = true` |
| `created_at` | `TIMESTAMP` (tanpa timezone) | `NOT NULL`, `server_default = CURRENT_TIMESTAMP` |
| `last_login_at` | `TIMESTAMP` (tanpa timezone) | nullable |

Tidak ada foreign key dari atau ke `users` — diverifikasi oleh `backend/tests/test_migration_chain.py`.

**Semantik `role`.** Disimpan sebagai `VARCHAR(20)`, divalidasi di level aplikasi (`app/core/security.py:Role`), **bukan** `CHECK` constraint di database — mengikuti konvensi yang sudah ada di skema ini (nol `CHECK` constraint sebelum M9.1a; `delivery_status` dan `connection_status` memakai pola app-level-enum-sebagai-VARCHAR yang sama). Dua nilai valid: `ANALYST` dan `ADMIN`. ADMIN mewarisi seluruh kapabilitas ANALYST ditambah manajemen pengguna (OD-1 = Option B — lihat `03_SYSTEM_DESIGN.md` §11.2 dan `M9.1a_SECURITY_FOUNDATION_DESIGN.md`).

**Semantik `is_active`.** Ini adalah mekanisme *revocation* utama: `is_active = false` membuat akun ditolak pada request berikutnya, tanpa menunggu token JWT (masa berlaku 8 jam) kedaluwarsa, dan tanpa memerlukan *token blacklist*. Peran (`role`) dan status (`is_active`) selalu dibaca ulang dari baris `User` di database pada setiap request — **tidak pernah** dipercaya dari klaim token.

**Provisioning akun pertama.** Tabel `users` kosong pada instalasi baru — sesuai desain, sistem terkunci sepenuhnya (*deny-by-default* tanpa akun berarti tidak ada yang bisa login). Akun ADMIN pertama dibuat melalui `backend/scripts/create_admin.py`, sebuah CLI interaktif (lihat Bagian 29.1 langkah 5 dan Bagian 29.2 langkah 6). Skrip ini **bukan** migrasi dan **bukan** proses startup aplikasi — keduanya akan menanam kredensial yang dikenal (*known credential*) di setiap deployment. Skrip menolak dijalankan terhadap database PoC stabil `lis_marina_permata` (Bagian 29.4).

**Cakupan yang sengaja tidak termasuk.** Atribusi pengguna pada mutasi workflow klinis (kolom `id_user` pada `test_runs` atau tabel audit terpisah) **tidak** ditambahkan oleh migrasi ini — kolom `id_user` tidak pernah ditambahkan ke `test_runs` (atau tabel domain manapun); atribusi diimplementasikan sebagai tabel terpisah, `audit_events`, oleh M9.1b — lihat Bagian 34.

---

# 34. Audit Events Table — Actor Attribution (M9.1b)

**Tujuan.** Tabel `audit_events` mencatat *siapa melakukan apa* untuk mutasi workflow klinis dan aksi manajemen pengguna — separuh *human-actor* dari NFR-08 (Workflow Auditability) yang belum terpenuhi setelah M9.1a. Ini adalah *Workflow Metadata* (Bagian 25), append-only, dan sepenuhnya terpisah dari `Clinical Data` — tidak ada kolom klinis (`nilai_hasil`, dsb.) yang disentuh atau disalin ke tabel ini.

**Migrasi.** `backend/alembic/versions/28aa370f5dbe_m9_1b_add_audit_events_table.py`, `down_revision = "27e00bcff992"` — revisi tunggal setelah HEAD M9.1a, ditulis manual (*hand-authored*), **bukan** hasil `alembic revision --autogenerate`, untuk alasan yang identik dengan migrasi `users` (Bagian 33): F-2 dan F-3 masih merupakan drift ORM yang belum diremediasi, dan `--autogenerate` pada titik manapun di chain ini akan mengusulkan perubahan yang tidak disetujui pada keduanya. Migrasi `28aa370f5dbe` **hanya** membuat tabel `audit_events`; F-2, F-3, dan F-4 tetap tidak disentuh.

**Kolom dan constraint yang diimplementasikan** (`app/models/audit_event.py`):

| Kolom | Tipe | Constraint |
|---|---|---|
| `id_audit` | `SERIAL` (PK, autoincrement) | Primary key |
| `id_user` | `INTEGER` | *Nullable* di level skema; **FK** ke `users.id_user`, `ON DELETE RESTRICT` |
| `actor_username` | `VARCHAR(50)` | `NOT NULL` — snapshot `users.username` pada saat kejadian |
| `actor_role` | `VARCHAR(20)` | `NOT NULL` — snapshot `users.role` pada saat kejadian |
| `action` | `VARCHAR(50)` | `NOT NULL` — lihat daftar aksi di bawah |
| `entity_type` | `VARCHAR(50)` | `NOT NULL` — `'TEST_RUN'` atau `'USER'` |
| `entity_id` | `INTEGER` | `NOT NULL` — **bukan** foreign key (lihat di bawah) |
| `occurred_at` | `TIMESTAMP` (tanpa timezone) | `NOT NULL`, `server_default = CURRENT_TIMESTAMP` |
| `outcome` | `VARCHAR(20)` | `NOT NULL` — selalu `"SUCCESS"` pada M9.1b (lihat di bawah) |
| `state_before` | `VARCHAR(30)` | nullable — label state sebelum mutasi |
| `state_after` | `VARCHAR(30)` | nullable — label state sesudah mutasi |

Satu-satunya foreign key pada tabel ini adalah `id_user → users.id_user`, diverifikasi oleh `backend/tests/test_migration_chain.py`.

**Mengapa `id_user` nullable padahal selalu diisi.** Setiap aksi yang diatribusikan mensyaratkan pemanggil yang terautentikasi (deny-by-default, M9.1a), sehingga tidak ada kode M9.1b yang pernah menulis `NULL` pada kolom ini. Kolom dibiarkan *nullable* di level skema semata-mata untuk kemungkinan event bersumber-sistem di masa depan — bukan kebutuhan M9.1b saat ini. `ON DELETE RESTRICT` memastikan sebuah `User` dengan riwayat audit tidak dapat dihapus; diverifikasi langsung: percobaan `DELETE` pada user yang memiliki baris `audit_events` ditolak oleh database, sementara *deactivation* (`is_active = false`, satu-satunya mekanisme revocation yang ada) tetap berhasil dan mempertahankan riwayat audit tersebut.

**`entity_id` bersifat polimorfik, bukan foreign key.** Satu tabel `audit_events` mencatat aksi terhadap dua jenis entitas berbeda (`test_runs.id_run` atau `users.id_user`), dan satu kolom integer tidak dapat menjadi foreign key ke dua tabel induk berbeda sekaligus. `entity_type` menentukan tabel mana yang dimaksud `entity_id`. Integritas referensial untuk pasangan ini adalah tanggung jawab aplikasi — aman dalam praktiknya karena setiap penulisan audit terjadi dalam transaksi yang sama dengan mutasi yang menghasilkan baris yang dirujuk, dan karena tidak ada endpoint yang menghapus `TestRun` atau `User` (hanya *deactivation* untuk `User`).

**Semantik `action`.** Sembilan nilai, app-level enum (VARCHAR, tanpa `CHECK` constraint — mengikuti konvensi skema yang sama seperti `role`, `delivery_status`, `connection_status`):

*Workflow klinis (lima aksi, seluruhnya melalui `TestRunService`):* `TEST_RUN_FINALIZED`, `TEST_RUN_UNFINALIZED`, `DELIVERY_STARTED`, `DELIVERY_DELIVERED`, `DELIVERY_FAILED`.

*Manajemen pengguna (empat aksi, tiga endpoint):* `USER_CREATED` (`POST /api/users`), `USER_DISABLED` / `USER_REACTIVATED` (`PATCH /api/users/{id_user}/status`, dibedakan dari nilai `is_active` hasil), `PASSWORD_CHANGED` (`POST /api/account/change-password`).

`sync-simrs` menghasilkan **dua** baris — `DELIVERY_STARTED` lalu `DELIVERY_DELIVERED`/`DELIVERY_FAILED` — tanpa logika khusus di router: kedua baris muncul secara alami karena `sync-simrs` memanggil `start_delivery` lalu `mark_delivery_delivered`/`mark_delivery_failed`, dua method `TestRunService` yang masing-masing sudah menulis baris auditnya sendiri. Panggilan HTTP keluar ke SIMRS berada di antara kedua commit tersebut, tidak pernah di dalam transaksi database yang terbuka — diverifikasi dengan koneksi database independen yang membuktikan commit pertama sudah terlihat oleh sesi lain sebelum panggilan HTTP dimulai.

**Semantik `outcome`.** Hanya transisi state yang berhasil dan ter-commit yang dicatat — permintaan yang ditolak (`401`/`403`) atau gagal karena aturan bisnis (mis. `409 Conflict`) tidak menghasilkan baris sama sekali, sehingga `outcome` selalu bernilai `"SUCCESS"` pada M9.1b. Kolom ini ada untuk ekstensibilitas di masa depan tanpa perubahan skema, bukan karena ada jalur kode yang menulis nilai lain saat ini.

**Semantik `state_before`/`state_after`.** Label singkat yang merepresentasikan nilai domain sesungguhnya — representasi boolean literal (`"True"`/`"False"`) untuk `is_final`, atau nilai `delivery_status` yang sudah ada apa adanya (`"pending"`, `"sending"`, `"delivered"`, `"failed"`) — bukan JSON. `PASSWORD_CHANGED` selalu memiliki `state_before = NULL` dan `state_after = NULL`: kolom ini **tidak pernah** memuat `password_hash` atau password plaintext, diverifikasi oleh pemindaian field secara langsung pada test suite.

**Penulisan dalam transaksi yang sama.** Setiap baris `audit_events` di-*stage* (`session.add`) sebelum `session.commit()` yang sudah ada pada method yang melakukan mutasi bisnis terkait — tidak ada commit baru, tidak ada boundary transaksi baru. Jika penulisan audit gagal (mis. constraint violation), mutasi bisnis ikut *rollback* — tidak ada baris audit yatim, dan tidak ada mutasi bisnis yang "berhasil" tanpa audit yang menyertainya.

**Immutability.** Aplikasi-level, *append-only* — tidak ada endpoint yang meng-*update* atau menghapus baris `audit_events`; tidak ada *DB trigger* atau `REVOKE` yang menegakkannya pada milestone ini (konsisten dengan pola imutabilitas `results` yang sudah ada, Bagian 11).

**Cakupan yang sengaja tidak termasuk.** Login (`POST /api/auth/login`) — `users.last_login_at` tetap menjadi catatan yang cukup. Pembacaan (`GET`). Ingesti instrumen — Integration Service menulis langsung ke database di luar siklus request manapun dan tidak memperkenalkan identitas pengguna sintetis; diverifikasi oleh regresi khusus yang membuktikan ingesti klinis penuh menghasilkan nol baris `audit_events`. Retensi tidak terbatas — tidak ada kebijakan *expiry*/*deletion*. Tidak ada kolom *correlation ID* / *request ID*.

Rincian desain dan verifikasi lengkap: `M9.1b_AUDIT_ATTRIBUTION_DESIGN.md`.

---


# 35. Instrument Sessions & Raw Capture Provenance (XN-550 Phase 1)

**Tujuan.** Menyimpan *raw bytes* yang persis dan provenance transport untuk instrumen mode *listener* (Sysmex XN-550, G1 `raw_only`). Kontrak lengkap: `docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md` §9, §19.4 dan §19.5. Ini adalah *technical traceability* (Bagian 16.3) — **bukan** data klinis: tidak ada baris `patients` / `visits` / `orders` / `test_runs` / `results` yang dibuat dari data XN-550.

**Migrasi.** `backend/alembic/versions/5d2e8b7c41a9_xn550_phase1_raw_capture.py`, `down_revision = "28aa370f5dbe"`, ditulis manual (alasan sama dengan Bagian 33/34). Aditif saja: satu tabel baru dan 13 kolom *nullable* baru; tanpa *backfill*. Baris lama (BC-5150/MLLP) tetap `NULL` pada kolom baru. *Downgrade* menghapus tepat objek-objek ini dan diuji oleh `backend/tests/test_migration_chain.py`.

**`instrument_sessions`** (`app/models/instrument_session.py`) — satu baris per koneksi TCP yang diterima dari peer yang diizinkan: `id_instrument` (FK), `transport_mode`, `local_address`/`local_port`, `peer_address`/`peer_port`, `ack_policy`, `opened_at`, `closed_at` (NULL = terbuka), `close_reason` (app-level enum tanpa `CHECK`), serta counter `bytes_received`, `reads_count`, `acks_sent`, `messages_completed`, `fragments_count`. Index `(id_instrument, opened_at DESC)`. Tidak memuat PHI.

**Kolom baru `instrument_messages`** (semua nullable): `id_session` (FK), `session_message_index`, `stream_offset_start`/`stream_offset_end`, `raw_bytes` (`BYTEA`, **otoritatif**), `raw_sha256` (`CHAR(64)`), `raw_length`, `first_byte_at`, `read_count`, `framing`, `parser_key`, `parser_version`, `duplicate_of_message_id` (FK ke tabel yang sama). Untuk baris XN-550, `raw_message` hanya representasi ASCII non-otoritatif (NUL diganti U+FFFD karena `TEXT` PostgreSQL tidak dapat menyimpannya).

**Constraint.** Hanya keunikan teknis: `UNIQUE (id_session, stream_offset_start)`, `CHECK (raw_bytes IS NULL OR raw_length = octet_length(raw_bytes))`, `CHECK (raw_bytes IS NULL OR raw_sha256 IS NOT NULL)`. Index non-unik `(id_instrument, raw_sha256)`, `(id_instrument, received_at DESC)`, `(duplicate_of_message_id)`. **Sengaja tidak ada** `UNIQUE` pada `raw_sha256`: retransmisi manual di hari yang sama identik per byte, dan setiap pengiriman tetap disimpan.

**Status Phase 1 dan Phase 2.** T1 menyimpan pesan lengkap dengan `parse_status = 'Pending'`. Fragmen dan pesan dengan byte kontrol/LF/non-ASCII langsung disimpan `Failed` / `UNPARSEABLE` dengan token kontrak; pada baris ini `parser_key` dan `parser_version` tetap `NULL`.

Sejak Phase 2 (`app/integration/xn550_ingestion.py`, tanpa migrasi baru), tahap T2 membaca `raw_bytes` dan memverifikasi ulang `raw_sha256` / `raw_length`. Selama baris masih `Pending`, T2 memperbarui **baris yang sama**:
- `parse_status`: `Success` / `Failed`;
- `message_class`: `UNCLASSIFIED` atau `UNPARSEABLE`, tidak pernah `PATIENT_RESULT`;
- `classification_rule`: `XN550_ENVELOPE_CONFORMANT`, `XN550_DEV_*`, atau token `UNPARSEABLE`;
- `error_detail`: token, dengan indeks record/field bila ada, tanpa teks field;
- `parser_key` (`xn550_astm_e1394`) dan `parser_version` (`xn550-astm-1.0.0`).

Baris yang tertinggal `Pending` akibat crash diklasifikasikan saat listener start.

Sejak XN-550 G2 (Bagian 36), tahap T2 yang sama juga mengisi `duplicate_of_message_id` untuk pengiriman ulang yang identik per byte — pada **kedua** `ingestion_stage` — dan menulis catatan `Redelivery: byte-identical to message <id>` pada `error_detail`. Penautan hanya menunjuk ke `id_message` yang lebih kecil; baris yang sudah diklasifikasikan sebelum G2 tidak pernah di-*backfill*.


---

# 36. Instrument Result Sets & Items — Observasi Tak Tertaut (XN-550 G2)

**Tujuan.** Menyimpan hasil XN-550 yang sudah dinormalisasi sebagai **observasi tak tertaut**: satu *result set* per pengiriman yang lolos amplop (`XN550_ENVELOPE_CONFORMANT`) dan satu *item* per record `R`. Kontrak lengkap: `docs/instruments/sysmex_xn550/M9.2_IMPLEMENTATION_CONTRACT.md` §10, §11.1, §13 dan §19.8. Ini **bukan** data klinis: tidak ada baris `patients` / `visits` / `orders` / `test_runs` / `results` yang dibuat, dan tidak ada *foreign key* ke tabel klinis mana pun.

**Batas identitas.** `sample_label` (Sample No. yang diketik operator) adalah **label tampilan saja** — bukan kunci pasien, spesimen, kunjungan atau order — dan sengaja **tidak** di-index, di-*filter*, di-*sort* maupun di-*unique*-kan. `association_status` selalu `UNRESOLVED` (dijaga `CHECK`). `source_r_sequence` adalah nomor urut record `R` ASTM di dalam satu pesan, bukan nomor urut pada layar instrumen.

**Migrasi.** `backend/alembic/versions/8a3023944bd1_xn550_g2_unlinked_observations.py`, `down_revision = "5d2e8b7c41a9"`, ditulis manual (alasan sama dengan Bagian 33/34/35). Aditif saja: dua tabel baru; **tidak ada** perubahan pada tabel yang sudah ada dan tidak ada *backfill*. *Downgrade* menghapus tepat kedua tabel beserta index dan sequence-nya, dan diuji oleh `backend/tests/test_migration_chain.py` — termasuk uji paritas ORM/migrasi khusus untuk kedua tabel ini.

**`instrument_result_sets`** (`app/models/instrument_result_set.py`) — satu baris per pengiriman yang memiliki *result set*: `id_message` (FK, **UNIQUE**), `id_instrument` (FK), `received_at` (jam LIS), `analysis_at` (jam instrumen, `R`-13), `sample_label`, `association_status`, `analysis_fingerprint` (`CHAR(64)`) dan `fingerprint_version`, `duplicate_status` dengan `possible_duplicate_of` (FK ke tabel yang sama), `p5_populated` / `p8_populated` (hanya penanda keberadaan, **tidak pernah** diekspos), `item_count`, `non_n_flag_item_count`, `image_reference_count`, serta `created_at`.

**`instrument_result_items`** (`app/models/instrument_result_item.py`) — satu baris per record `R`: `id_result_set` (FK), `source_record_index`, `source_offset_start` / `source_offset_end` (offset byte relatif terhadap `raw_bytes`, tanpa CR penutup), `source_r_sequence`, `item_kind`, `test_code`, `test_code_qualifier`, `value_raw`, `units_raw`, `reference_range_raw`, `abnormal_flag_raw`, `result_status_raw`. Lebar kolom sengaja sama dengan `results`.

**Constraint.**
- `UNIQUE (id_message)` pada *set*; `UNIQUE (id_result_set, source_record_index)` dan `UNIQUE (id_result_set, test_code)` pada *item*.
- Empat *foreign key*, semuanya `ON DELETE RESTRICT` (baris bersifat *append-only*; Bagian 19 menolak *cascade*).
- Empat `CHECK` keselamatan: `association_status = 'UNRESOLVED'`; konsistensi `duplicate_status` ↔ `possible_duplicate_of` (dan penunjuk selalu ke id yang lebih kecil); domain `item_kind`; serta "referensi gambar tidak pernah menyimpan nilai" (`value_raw IS NULL`). Ini menyimpang dari konvensi "enum app-level tanpa CHECK" secara sadar: keempatnya menjaga invarian keselamatan, bukan kosakata tampilan.

**Index.** `(id_instrument, fingerprint_version, analysis_fingerprint, id_result_set)` untuk pencarian sidik jari; `(received_at DESC, id_result_set DESC)` dan `(id_instrument, received_at DESC, id_result_set DESC)` untuk daftar API. **Sengaja tidak ada** index pada `sample_label`, tidak ada index `(id_result_set)` terpisah pada *item* (sudah dilayani index bawaan `UNIQUE`), dan tidak ada `UNIQUE` pada kolom konten mana pun.

**Status.** Tabel ini hanya terisi bila `ingestion_stage = "observations"` (G2), dan saat ini hanya diisi di lingkungan pengembangan dan pengujian — di DEV melalui simulator pengembangan (`backend/tests/simulate_xn550.py`), bukan instrumen fisik. Belum ada *deployment* produksi (kontrak §19.9). Bila nanti produksi dipasang, konfigurasinya dimulai pada `raw_only` selama *soak* G1 — sehingga kedua tabel tetap kosong di produksi sampai gerbang §19.7 terpenuhi.
