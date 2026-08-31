# System Design & Architecture

## 1. Architecture Overview

### 1.1 Architectural Pattern

Sistem menggunakan **Layered Client-Server Architecture with a Dedicated Integration Service** dengan pendekatan **Modular Monolith**.

Arsitektur ini memisahkan tanggung jawab utama antara *frontend* (React), *backend/API* (FastAPI), *database* (PostgreSQL), serta *background service* mandiri (*Integration Service*) yang bertugas menangani komunikasi jaringan TCP/IP dengan instrumen laboratorium.

Pemisahan ini bertujuan untuk memastikan bahwa gangguan pada komunikasi instrumen tidak secara langsung mengganggu layanan API atau antarmuka pengguna.

### 1.2 Component Relationship Diagram

```text
                         ┌──────────────────────┐
                         │   9 Lab Instruments  │
                         │  Mindray, Sysmex,    │
                         │  DFI, Medica, etc.   │
                         └──────────┬───────────┘
                                    │
                              ASTM / HL7
                                TCP/IP
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Integration Service  │
                         │   Python Background  │
                         │                      │
                         │ • TCP Communication  │
                         │ • Parsing            │
                         │ • Validation         │
                         │ • Normalization      │
                         └──────────┬───────────┘
                                    │
                                Persist
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      PostgreSQL      │
                         │       Database       │
                         └──────────▲───────────┘
                                    │
                            Query / Workflow
                                    │
                         ┌──────────┴───────────┐
                         │  FastAPI Application │
                         │      API Layer       │
                         └──────────▲───────────┘
                                    │
                              REST API / HTTP
                                    │
                         ┌──────────┴───────────┐
                         │      React SPA       │
                         │    LIS Dashboard     │
                         └──────────────────────┘

             ┌──────────────────────────────────────┐
             │          SIMRS Eksternal             │
             └──────────────────┬───────────────────┘
                                │
                          HTTP POST / GET
                                │
                                ▼
                       ┌──────────────────────┐
                       │   FastAPI / SIMRS    │
                       │ Integration Module   │
                       └──────────────────────┘
```

### 1.3 Architectural Responsibilities

| Component | Responsibility |
|---|---|
| Lab Instruments | Menghasilkan dan mengirim data hasil pemeriksaan |
| Integration Service | Menerima, memproses, memvalidasi, menormalisasi, dan menyimpan data instrumen |
| PostgreSQL | Menyimpan data master, transaksi, test run, dan hasil pemeriksaan |
| FastAPI | Menyediakan API untuk dashboard dan integrasi SIMRS |
| React SPA | Menampilkan dan mengelola workflow pengguna |
| SIMRS Integration Module | Menangani pertukaran data hasil laboratorium dengan SIMRS |

### 1.4 Traceability with PRD

Arsitektur dirancang untuk memenuhi kebutuhan utama pada PRD:

- **FR-01 (Multi-Connection Handling):** Ditangani oleh *Integration Service* dengan mekanisme koneksi instrumen secara terisolasi.
- **FR-02 (Protocol Support):** Parsing protokol ASTM/HL7 dilakukan pada *Integration Service*.
- **FR-03 (Data Filtering):** Data non-esensial dapat disaring pada tahap parsing sebelum disimpan.
- **FR-04–FR-06 (Dashboard):** Disediakan melalui React SPA dan FastAPI.
- **FR-07 (Multiple Run Handling):** Didukung oleh hierarki `Order → Test Run → Result`.
- **FR-08 (Final Run Selection):** Dikelola melalui workflow `is_final`.
- **FR-09–FR-10 (SIMRS Integration):** Ditangani melalui API dan modul integrasi SIMRS.

---

## 2. System Components

### 2.1 Presentation Layer — React SPA

Frontend menggunakan **React dengan Vite dan TypeScript**.

Tanggung jawab utama:

- Menampilkan hasil pemeriksaan laboratorium.
- Memfilter hasil berdasarkan instrumen.
- Menampilkan status abnormalitas.
- Memantau data yang masuk secara berkala/*real-time*.
- Menampilkan beberapa *Test Run* untuk kebutuhan review.
- Memungkinkan analis menetapkan *Test Run* final.
- Menyediakan aksi sinkronisasi hasil final ke SIMRS.

Frontend **tidak menyediakan fitur untuk mengedit nilai klinis**.

### 2.2 API Layer — FastAPI

FastAPI bertindak sebagai lapisan API dan logika aplikasi.

Tanggung jawab utama:

- Menyediakan REST API untuk React.
- Mengambil data dari PostgreSQL.
- Menyediakan informasi status instrumen.
- Mengelola workflow pemilihan `Test Run` final.
- Menyediakan endpoint integrasi dengan SIMRS.
- Mengelola status pengiriman hasil ke SIMRS.

FastAPI tidak menyediakan endpoint untuk mengubah nilai klinis yang berasal dari instrumen.

### 2.3 Integration Service — Python

*Integration Service* merupakan layanan background yang bertanggung jawab terhadap komunikasi dengan instrumen.

Tanggung jawab utama:

- Membuka dan mempertahankan koneksi TCP/IP.
- Menangani koneksi beberapa instrumen secara bersamaan.
- Menerima data ASTM/HL7.
- Menangani fragmentasi dan *batch transmission*.
- Melakukan parsing pesan.
- Melakukan validasi struktur dan data.
- Melakukan normalisasi data.
- Menyaring payload non-esensial.
- Menyimpan hasil ke PostgreSQL.
- Menangani kegagalan koneksi dan *automatic reconnect*.

### 2.4 Database Layer — PostgreSQL

PostgreSQL digunakan sebagai database utama sistem.

Database menyimpan:

- Master pasien.
- Riwayat kunjungan.
- Order pemeriksaan.
- Test Run.
- Hasil pemeriksaan.
- Master instrumen.
- Master unit, dokter, tes, dan kelompok tes.
- Metadata workflow dan status integrasi.

---

## 3. Network Architecture

### 3.1 Network Topology

Sistem berjalan pada jaringan lokal (*On-Premise*) di lingkungan laboratorium.

Secara umum:

```text
[Instrument 1] ─┐
[Instrument 2] ─┤
[Instrument 3] ─┤
      ...       ├──► [LAN Switch] ───► [LIS Server]
[Instrument 9] ─┘
```

Seluruh instrumen dan LIS Server berkomunikasi melalui jaringan LAN laboratorium.

### 3.2 IP Addressing

Masing-masing instrumen dan LIS Server menggunakan alamat IP yang ditentukan oleh konfigurasi jaringan rumah sakit.

Contoh alamat:

```text
LIS Server      : 10.0.0.10
Instrument 01   : 10.0.0.2
Instrument 02   : 10.0.0.3
...
```

Alamat tersebut merupakan contoh dan harus disesuaikan dengan konfigurasi jaringan aktual.

---

## 4. Instrument Integration Architecture

### 4.1 Instrument Configuration Matrix

Ruang lingkup MVP mencakup 9 instrumen laboratorium berikut:

| No | Model Alat | Jenis Analisis | Protokol | Transport | Status R&D |
|---:|---|---|---|---|---|
| 1 | Mindray BC-5150 | Hematology Analyzer | TBD | TCP/IP | Active / Verified |
| 2 | Sysmex XN-550 | Hematology Analyzer | TBD | TCP/IP | Planned |
| 3 | Mindray BS-200E | Chemistry Analyzer | TBD | TCP/IP | Planned |
| 4 | Sysmex BX-3010 | Chemistry Analyzer | TBD | TCP/IP | Planned |
| 5 | DFI R-300 | Urine Analyzer | TBD | TCP/IP | Planned |
| 6 | Insight Expert U120 | Urine Analyzer | TBD | TCP/IP | Planned |
| 7 | ichroma II | Immunoassay Analyzer | TBD | TCP/IP | Planned |
| 8 | Medica EasyLyte PLUS | Electrolyte Analyzer | TBD | TCP/IP | Planned |
| 9 | PRECIL 106-AC-57000131 | Coagulation Analyzer | TBD | TCP/IP | Planned |

> Detail protokol, port, mode komunikasi, dan konfigurasi jaringan setiap instrumen akan ditentukan setelah proses R&D dan verifikasi teknis masing-masing alat.

### 4.2 Integration Strategy

Setiap instrumen diperlakukan sebagai koneksi yang terisolasi pada *Integration Service*.

Dengan pendekatan tersebut:

```text
Instrument A ──► Connection Handler A
Instrument B ──► Connection Handler B
Instrument C ──► Connection Handler C
       ...
Instrument I ──► Connection Handler I
```

Kegagalan komunikasi pada satu instrumen tidak boleh menghentikan proses komunikasi instrumen lainnya.

---

## 5. Data Flow

### 5.1 Instrument → LIS

```text
Instrument
    ↓
TCP/IP
    ↓
Integration Service
    ↓
Receive
    ↓
Parse
    ↓
Validate
    ↓
Normalize
    ↓
Persist
    ↓
PostgreSQL
```

Data klinis yang telah diterima dan disimpan tidak boleh dimodifikasi melalui aplikasi.

### 5.2 LIS → Dashboard

```text
PostgreSQL
    ↓
FastAPI
    ↓
REST API
    ↓
React Dashboard
    ↓
Analis Laboratorium
```

Dashboard menampilkan data hasil pemeriksaan dan metadata yang diperlukan untuk workflow.

### 5.3 LIS → SIMRS

```text
Analis
   ↓
Select Final Test Run
   ↓
FastAPI
   ↓
SIMRS Integration Module
   ↓
HTTP POST
   ↓
SIMRS
```

Hanya hasil dari *Test Run* yang ditetapkan sebagai final yang dapat digunakan sebagai sumber pengiriman hasil ke SIMRS.

### 5.4 SIMRS → LIS

```text
SIMRS
   ↓
HTTP GET
   ↓
FastAPI
   ↓
PostgreSQL
   ↓
Historical Laboratory Results
```

Data yang dikembalikan merupakan **riwayat hasil laboratorium**, bukan keseluruhan rekam medis pasien.

---

## 6. Message Processing Pipeline

Setiap pesan yang diterima dari instrumen diproses melalui tahapan berikut:

### 6.1 Receive

*Integration Service* menerima aliran *byte* melalui koneksi TCP/IP.

Sistem harus mampu menangani:

- Fragmentasi paket.
- Pesan yang dikirim bertahap.
- *Batch transmission*.
- Beberapa pesan dalam satu koneksi.

### 6.2 Parse

Pesan diproses berdasarkan protokol instrumen yang digunakan.

Parser bertanggung jawab mengekstraksi informasi seperti:

- Nomor RM.
- Identitas sampel.
- Waktu pemeriksaan.
- Parameter pemeriksaan.
- Nilai hasil.
- Satuan.
- Flag abnormalitas.
- Informasi instrumen.

Payload non-esensial seperti grafik atau data Base64 yang tidak diperlukan oleh MVP dapat disaring pada tahap ini.

### 6.3 Validate

Sistem melakukan validasi terhadap struktur dan isi data sebelum disimpan.

Validasi minimal mencakup:

- Struktur pesan.
- Identitas pasien/sampel.
- Nomor RM.
- Parameter pemeriksaan.
- Nilai hasil.
- Informasi instrumen.

Data yang gagal diproses harus dicatat pada log error dan tidak boleh menyebabkan *Integration Service* berhenti.

### 6.4 Normalize

Data dari berbagai instrumen dinormalisasi ke struktur internal LIS yang seragam.

Contoh:

```text
Instrument-specific format
          ↓
LIS Standard Data Model
```

Dengan demikian, frontend dan API tidak perlu memahami format spesifik setiap instrumen.

### 6.5 Persist

Data yang telah lolos proses validasi dan normalisasi disimpan ke PostgreSQL melalui transaksi database.

---

## 7. Result & Re-run Architecture

### 7.1 Data Hierarchy

Struktur utama hasil pemeriksaan:

```text
Patient
   ↓
Visit
   ↓
Order
   ↓
Test Run
   ↓
Result
```

### 7.2 Immutability Rule

Nilai klinis yang diterima dari instrumen bersifat **immutable** setelah berhasil disimpan.

Contoh data klinis yang tidak boleh diubah:

```text
nilai_hasil
satuan
flag_abnormalitas
parameter_tes
```

Aplikasi tidak menyediakan mekanisme untuk mengubah data tersebut.

Sebaliknya, metadata workflow dapat berubah sesuai kebutuhan sistem, misalnya:

```text
is_final
delivery_status
delivery_timestamp
```

### 7.3 Re-run Handling

Apabila sampel yang sama diperiksa kembali, sistem membuat *Test Run* baru.

Contoh:

```text
Order #1001
│
├── Test Run #1
│     ├── WBC
│     ├── RBC
│     └── HGB
│
└── Test Run #2 (Re-run)
      ├── WBC
      ├── RBC
      └── HGB
```

Test Run sebelumnya tidak ditimpa.

### 7.4 Final Run Selection

Analis dapat memilih satu *Test Run* sebagai hasil final.

Untuk setiap `Order`, sistem harus memastikan:

> **Maksimal hanya satu Test Run yang memiliki `is_final = true` pada satu waktu.**

Contoh valid:

```text
Test Run #1 → false
Test Run #2 → true
Test Run #3 → false
```

Pemilihan *Test Run* final merupakan workflow metadata dan **tidak mengubah nilai klinis hasil pemeriksaan**.

---

## 8. Reliability & Failure Handling

### 8.1 Automatic Connection Recovery

*Integration Service* harus mampu menangani kegagalan seperti:

- Connection reset.
- TCP timeout.
- Instrumen dimatikan.
- Instrumen direstart.
- Koneksi jaringan terputus sementara.

Setelah koneksi gagal, sistem melakukan proses pemulihan dan mencoba melakukan koneksi kembali secara berkala.

### 8.2 Fault Isolation

Setiap koneksi instrumen harus berjalan secara terisolasi.

Contoh:

```text
BC-5150       → Connected
XN-550        → Connected
BS-200E       → Connection Lost
BX-3010       → Connected
```

Kegagalan `BS-200E` tidak boleh menghentikan koneksi `BC-5150`, `XN-550`, atau instrumen lainnya.

### 8.3 Batch Transmission

Sistem dirancang untuk menangani pengiriman beberapa hasil secara berurutan dalam satu sesi komunikasi.

Pipeline harus memastikan setiap pesan dapat dipisahkan, diproses, dan disimpan tanpa kehilangan urutan atau data.

---

## 9. API Architecture & SIMRS Integration

### 9.1 Internal REST API

FastAPI menyediakan API internal untuk frontend.

Kebutuhan utama meliputi:

- Mengambil hasil laboratorium.
- Mengambil status instrumen.
- Memfilter hasil berdasarkan instrumen.
- Mengambil Test Run.
- Menetapkan Test Run final.
- Mengambil status sinkronisasi.

### 9.2 SIMRS Integration

Modul integrasi SIMRS bertanggung jawab terhadap:

- Penyusunan payload.
- Authentication sesuai spesifikasi SIMRS.
- HTTP POST hasil final.
- Penanganan response SIMRS.
- Pencatatan status pengiriman.
- Penyediaan endpoint GET untuk riwayat hasil laboratorium.

Detail endpoint, format payload, metode autentikasi, dan kontrak API akan ditentukan setelah spesifikasi API SIMRS diperoleh.

---

## 10. Data Persistence & Transaction Integrity

PostgreSQL digunakan sebagai database utama dengan dukungan transaksi **ACID**.

Transaksi digunakan untuk memastikan proses penyimpanan data tidak meninggalkan kondisi parsial.

Contoh:

```text
Receive Message
      ↓
Parse
      ↓
Validate
      ↓
Create Test Run
      ↓
Create Results
      ↓
COMMIT
```

Apabila proses gagal sebelum *commit*, transaksi harus dapat dibatalkan (*rollback*) sesuai kebutuhan.

Data klinis yang telah berhasil disimpan tidak boleh dimodifikasi melalui workflow aplikasi.

---

## 11. Security

Sistem menerapkan prinsip keamanan yang sesuai dengan lingkungan *on-premise*.

### 11.1 Network Restriction

Akses sistem dibatasi pada jaringan internal rumah sakit sesuai kebutuhan operasional.

### 11.2 Role-Based Access Control

Akses pengguna dibatasi berdasarkan peran.

Contoh:

```text
Analis
 ├── View Results
 ├── Review Test Runs
 └── Select Final Run

Administrator
 └── System / Configuration Management
```

Hak akses aktual dapat disesuaikan dengan kebutuhan rumah sakit.

### 11.3 Clinical Data Protection

Tidak tersedia endpoint atau antarmuka aplikasi untuk mengubah nilai klinis yang berasal dari instrumen.

---

## 12. Audit & Logging

Sistem menyediakan logging untuk membantu troubleshooting dan memastikan traceability.

Log utama meliputi:

- Koneksi dan pemutusan instrumen.
- Percobaan reconnect.
- Error parsing.
- Error validasi.
- Error penyimpanan.
- Aktivitas pemilihan Test Run final.
- Timestamp aktivitas workflow.
- Status pengiriman ke SIMRS.
- Response dari SIMRS.

Audit log digunakan untuk menelusuri aktivitas penting tanpa mengubah data klinis yang telah diterima dari instrumen.

---

## 13. Deployment Architecture

Sistem dideploy secara **On-Premise** pada server lokal laboratorium.

Komponen utama berjalan pada lingkungan server:

```text
LIS Server
│
├── Integration Service
│
├── FastAPI
│
├── PostgreSQL
│
└── React Application
```

Frontend dapat diakses melalui browser pada komputer yang berada di jaringan internal dan memiliki hak akses ke LIS.

*Integration Service* berjalan sebagai background service agar komunikasi instrumen tetap aktif tanpa bergantung pada browser pengguna.

---

## 14. Scalability & Performance Principles

Sistem dirancang untuk mendukung hingga **9 instrumen laboratorium aktif secara bersamaan** sesuai ruang lingkup MVP.

Arsitektur mempertimbangkan:

- Koneksi instrumen secara paralel.
- Fault isolation antar-instrumen.
- Batch transmission.
- Pemrosesan pesan tanpa blocking terhadap koneksi lain.
- Penyimpanan data secara transaksional.
- API yang responsif untuk kebutuhan dashboard.

Target numerik untuk latency, throughput, dan kapasitas akan ditentukan berdasarkan hasil **performance testing** pada lingkungan laboratorium dan karakteristik komunikasi instrumen yang sebenarnya.

---

## 15. Architectural Principles

### 15.1 Separation of Concerns

Setiap komponen memiliki tanggung jawab yang jelas:

```text
Instrument
    → Data Source

Integration Service
    → Communication & Processing

PostgreSQL
    → Data Persistence

FastAPI
    → Business Logic & API

React
    → Presentation & User Workflow
```

### 15.2 Data Integrity

Data klinis yang diterima dari instrumen diperlakukan sebagai sumber data yang immutable pada level aplikasi.

### 15.3 Data Traceability

Setiap hasil pemeriksaan harus dapat ditelusuri ke:

- Pasien.
- Visit.
- Order.
- Test Run.
- Instrumen asal.
- Waktu pemeriksaan.

### 15.4 Fault Isolation

Kegagalan satu instrumen tidak boleh menyebabkan kegagalan keseluruhan sistem integrasi.

### 15.5 Simplicity for MVP

Arsitektur mempertahankan pendekatan **Modular Monolith** dan tidak memecah sistem menjadi microservices terpisah selama belum ada kebutuhan operasional yang membenarkannya.

---

## 16. Traceability to PRD

System Design ini merupakan penerjemahan teknis dari kebutuhan pada `02_PRD.md`.

| PRD Requirement | Architectural Component |
|---|---|
| FR-01 Multi-Connection Handling | Integration Service |
| FR-02 ASTM / HL7 Support | Protocol Parser |
| FR-03 Data Filtering | Message Processing Pipeline |
| FR-04 Device Filtering | React + FastAPI |
| FR-05 Auto-Refresh / Real-Time Data | React + FastAPI |
| FR-06 Abnormality Highlighting | React Dashboard |
| FR-07 Multiple Run Handling | Order → Test Run → Result |
| FR-08 Final Run Selection | `is_final` Workflow |
| FR-09 Push to SIMRS | SIMRS Integration Module |
| FR-10 Pull Historical Results | FastAPI GET API |

Seluruh implementasi teknis berikutnya harus mengacu pada arsitektur ini dan tidak boleh bertentangan dengan prinsip **Strictly View-Only** serta **Clinical Result Immutability** yang telah ditetapkan dalam PRD.