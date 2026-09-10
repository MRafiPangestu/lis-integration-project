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

Sejak M9.0, database LIS dapat di-*provision* sepenuhnya melalui Alembic. *Migration chain* memiliki **satu root** (`8e973e84a9d7`, disebut **R0**) dan **satu head** (`4aff9e134f16`):

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
4aff9e134f16   M8.4 — index untuk order overview          ← HEAD
```

Bagian ini menggantikan asumsi lama bahwa "SQL awal" harus dieksekusi manual sebelum migrasi. R0 kini merepresentasikan skema legacy tersebut di dalam *migration graph* yang dikelola versi (commit `d273e7f`), dan `alembic upgrade head` dari database kosong menghasilkan skema final tanpa langkah manual.

## 29.1. Instalasi baru (database kosong)

Jalur *fresh-install* yang otoritatif:

1. Buat database PostgreSQL kosong.
2. Arahkan konfigurasi koneksi aplikasi ke database tersebut (`DB_HOST=<host>`, `DB_PORT=<port>`, `DB_NAME=<database>`, `DB_USER=<user>`, dan kredensial melalui mekanisme `.env` proyek).
3. Jalankan:

   ```bash
   alembic upgrade head
   ```

4. Hasil: seluruh chain `R0 → b1f9dbe772fa → 4a24240f8c32 → 621889e316b5 → c5465739f048 → 4aff9e134f16` diterapkan; tabel `alembic_version` berisi `4aff9e134f16`.

Database PostgreSQL yang benar-benar kosong kini dapat di-*provision* **sepenuhnya melalui Alembic**. Operator **tidak** perlu — dan tidak boleh diinstruksikan — menjalankan `backend/schema/legacy_schema.sql` secara manual sebagai bagian dari *fresh-install* normal. File tersebut adalah artefak *evidence*, bukan perintah provisioning (lihat Bagian 29.5).

Verifikasi otomatis: `backend/tests/test_migration_chain.py` (commit `b7c3d0e`) menjalankan `alembic upgrade head` terhadap database sekali-pakai dan memeriksa revisi akhir serta invariant struktural skema (jumlah tabel/constraint/index, keberadaan objek M1/M8.2/M8.4, dan absennya objek yang belum di-remediasi).

> **Catatan F-2.** *Fresh-install chain* saat ini menghasilkan `patients.nomor_rm` sebagai `NOT NULL` tetapi **belum** `UNIQUE`. Constraint `UNIQUE(nomor_rm)` pada Bagian 18.2 adalah desain target; migration untuk menambahkannya adalah **remediasi terpisah yang belum ada di chain**. M9.0 tidak menyelesaikan item ini.

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

**Mengapa *stamp*, bukan *upgrade*:** R0 berisi statement `CREATE TABLE` / `CREATE SEQUENCE` / `ADD CONSTRAINT` untuk skema yang **sudah ada** di database legacy. Menjalankan `upgrade` R0 akan mencoba membuat ulang objek tersebut dan gagal. `alembic stamp` hanya menulis revisi awal yang diketahui ke `alembic_version` **tanpa mengeksekusi DDL R0**, sehingga `alembic upgrade head` berikutnya melanjutkan dari `b1f9dbe772fa` (transformasi M1) di atas skema legacy yang nyata.

> **Peringatan.**
> - `alembic stamp` **tidak** memverifikasi kompatibilitas skema secara otomatis. *Stamp* hanya benar setelah operator memastikan database memang cocok dengan skema R0 / pra-M1.
> - *Stamp* yang salah menyebabkan migrasi berjalan dari *state* skema yang keliru dan dapat merusak data.
> - Backup **wajib** sebelum migrasi lingkungan yang sudah berisi data.

## 29.3. Database development yang sudah ada

`lis_marina_permata_dev` sudah berada pada `4aff9e134f16`. R0 adalah **leluhur** revisi tersebut, bukan migrasi yang perlu diputar ulang. **Jangan** menjalankan R0 langsung terhadap database ini. Jika ada revisi baru di masa depan, `alembic upgrade head` biasa akan melanjutkan dari revisi saat ini.

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
| `4aff9e134f16` (HEAD) | empat index query untuk M8.4 order overview |

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

**Status dokumen:** Final untuk menjadi acuan database architecture LIS MVP.

**Catatan implementasi:** SQL awal yang diberikan sebelumnya merupakan baseline/schema awal dan **belum sepenuhnya sama dengan desain final ini**. Implementasi PostgreSQL harus mengikuti desain final di atas, terutama penambahan `visits` dan `test_runs`, penghapusan `UNIQUE(id_order, parameter_tes)`, serta penerapan Partial Unique Index untuk `is_final`. Sejak M9.0, "SQL awal" tersebut terpreservasi sebagai *evidence* R0 (`backend/schema/legacy_schema.sql`) dan **tidak** dijalankan manual pada instalasi baru — prosedur *provisioning* yang otoritatif (fresh-install dan *upgrade* dari legacy) ada di **Bagian 29**.
