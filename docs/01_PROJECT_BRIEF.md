# Project Brief: Laboratory Information System (LIS) Middleware

## 1. Project Overview

Pengembangan **Laboratory Information System (LIS)** untuk RS Marina Permata yang berfokus sebagai **Middleware** dan **Device Gateway**. Sistem tidak bertindak sebagai Rekam Medis Utama (*Electronic Medical Record/EMR*), melainkan sebagai jembatan antara instrumen laboratorium dan Sistem Informasi Manajemen Rumah Sakit (SIMRS).

LIS bertugas menerima data pemeriksaan secara otomatis dari berbagai instrumen laboratorium, memproses dan menyimpannya tanpa mengubah nilai klinis yang diterima, menyediakan antarmuka terpusat bagi analis untuk memantau hasil pemeriksaan, mengelola pengujian ulang (*re-run*), serta mendistribusikan hasil yang telah dipilih sebagai final ke SIMRS.

Sistem juga mempertahankan keterlacakan (*traceability*) antara pasien, kunjungan, order pemeriksaan, instrumen, *test run*, dan hasil pemeriksaan sehingga setiap hasil dapat ditelusuri kembali ke sumbernya.

---

## 2. Core Objectives

### 2.1 Hardware Automation

Menghubungkan hingga **9 instrumen laboratorium** ke dalam jaringan terpusat untuk mengurangi dan menghilangkan entri data manual dari instrumen ke sistem.

### 2.2 Data Integrity

Mempertahankan nilai hasil pemeriksaan sesuai dengan data yang diterima dari instrumen.

LIS tidak menyediakan fitur untuk mengubah, mengedit, atau memanipulasi nilai klinis hasil pemeriksaan setelah data diterima dan disimpan.

### 2.3 Centralized Monitoring

Menyediakan satu antarmuka terpusat bagi analis laboratorium untuk memantau hasil pemeriksaan dari berbagai instrumen.

### 2.4 Re-run Management

Merekam setiap pengujian ulang (*re-run*) sebagai **Test Run** terpisah tanpa menimpa hasil pemeriksaan sebelumnya.

Satu **Order** dapat memiliki beberapa **Test Run**, sedangkan setiap *Test Run* dapat menghasilkan beberapa **Result**.

Analis dapat memilih satu *Test Run* sebagai hasil final yang menjadi acuan untuk proses pengiriman ke SIMRS.

### 2.5 Patient & Transaction History

Memisahkan identitas pasien dari riwayat transaksi pemeriksaan.

* **Patient** merepresentasikan identitas pasien berdasarkan Nomor RM.
* **Visit** merepresentasikan riwayat kunjungan atau registrasi pasien.
* **Order** merepresentasikan permintaan pemeriksaan laboratorium dalam suatu kunjungan.

Pendekatan ini memungkinkan satu pasien memiliki banyak kunjungan dan setiap kunjungan dapat memiliki beberapa order pemeriksaan.

### 2.6 Seamless Integration

Menyediakan mekanisme integrasi dengan SIMRS melalui API untuk:

* mengirim hasil *Test Run* yang telah ditetapkan sebagai final;
* menyediakan akses terhadap riwayat hasil pemeriksaan berdasarkan identitas pasien atau Nomor RM;
* mempertahankan status dan rekam jejak proses pengiriman hasil.

---

## 3. Instrument Scope

MVP mencakup integrasi dengan 9 instrumen laboratorium berikut:

| No. | Jenis Alat           | Merek          | Model/Tipe      |
| --: | -------------------- | -------------- | --------------- |
|   1 | Hematology Analyzer  | Mindray        | BC-5150         |
|   2 | Hematology Analyzer  | Sysmex         | XN-550          |
|   3 | Chemistry Analyzer   | Mindray        | BS-200E         |
|   4 | Chemistry Analyzer   | Sysmex         | BX-3010         |
|   5 | Urine Analyzer       | DFI            | R-300           |
|   6 | Urine Analyzer       | Insight Expert | U120            |
|   7 | Immunoassay Analyzer | ichroma        | ichroma II      |
|   8 | Electrolyte Analyzer | Medica         | EasyLyte PLUS   |
|   9 | Coagulation Analyzer | PRECIL         | 106-AC-57000131 |

> **Catatan:** Detail teknis masing-masing instrumen seperti protokol komunikasi, IP address, port, mode komunikasi (*listener/push* atau *query/pull*), format pesan, dan parameter hasil didefinisikan pada dokumen **System Design / Instrument Integration Specification**, bukan pada Project Brief.

---

## 4. System Boundaries & Constraints

### 4.1 In Scope

* Penerimaan data hasil pemeriksaan dari instrumen laboratorium.
* Pemrosesan pesan komunikasi instrumen.
* Parsing dan normalisasi data hasil pemeriksaan.
* Penyimpanan data hasil pemeriksaan dan riwayat transaksi.
* Monitoring hasil pemeriksaan melalui dashboard LIS.
* Pengelolaan *Test Run* dan pengujian ulang (*re-run*).
* Pemilihan satu *Test Run* sebagai hasil final.
* Pengiriman hasil final ke SIMRS melalui API.
* Penyediaan API untuk akses riwayat hasil pemeriksaan.
* Pencatatan aktivitas dan status penting untuk kebutuhan *traceability* dan audit.

### 4.2 Out of Scope

* Rekam medis utama / Electronic Medical Record (EMR).
* Billing dan administrasi pembayaran.
* Manajemen inventaris dan reagen.
* Pengubahan atau manipulasi nilai hasil pemeriksaan klinis.
* Penginputan manual nilai hasil pemeriksaan sebagai pengganti data instrumen.
* Pengelolaan proses klinis yang berada di luar lingkup pemeriksaan laboratorium.

---

## 5. Data Integrity Constraint

LIS harus mempertahankan nilai hasil pemeriksaan sebagaimana diterima dari instrumen.

Setelah hasil pemeriksaan berhasil disimpan:

* nilai klinis tidak boleh diedit atau dimanipulasi melalui aplikasi;
* nilai dari *re-run* tidak boleh menimpa nilai dari *run* sebelumnya;
* setiap *Test Run* harus tetap dapat ditelusuri ke instrumen asal dan waktu pemeriksaan;
* analis hanya dapat menentukan *Test Run* mana yang dianggap final;
* maksimal satu *Test Run* dapat berstatus final untuk satu *Order* pada suatu waktu.

Perubahan yang diperbolehkan pada data yang telah tersimpan terbatas pada **metadata workflow**, seperti status finalisasi dan status pengiriman ke SIMRS.

---

## 6. Core Data Relationship

Struktur data utama mengikuti hierarki:

`Patient → Visit → Order → Test Run → Result`

Dengan hubungan:

* Satu **Patient** dapat memiliki banyak **Visit**.
* Satu **Visit** dapat memiliki banyak **Order**.
* Satu **Order** dapat memiliki banyak **Test Run**.
* Satu **Test Run** dapat memiliki banyak **Result**.
* Setiap **Test Run** terhubung dengan satu instrumen laboratorium.
* Satu **Order** dapat memiliki banyak *Test Run*, tetapi hanya satu yang dapat ditetapkan sebagai *final* pada satu waktu.

Struktur ini memastikan riwayat pemeriksaan tetap tersimpan dan tidak hilang ketika terjadi pengujian ulang.

---

## 7. SIMRS Integration Boundary

LIS berfungsi sebagai **integration gateway** antara sistem laboratorium dan SIMRS.

### LIS → SIMRS

LIS menyediakan mekanisme **POST** untuk mengirim hasil pemeriksaan yang telah ditetapkan sebagai final ke endpoint SIMRS.

Data yang dikirim harus berasal dari *Test Run* final dan tidak boleh dimodifikasi nilainya oleh LIS sebelum dikirim.

### SIMRS → LIS

LIS menyediakan **GET API** yang dapat digunakan oleh SIMRS untuk meminta riwayat hasil pemeriksaan laboratorium berdasarkan Nomor RM atau identifier transaksi yang disepakati.

Detail endpoint, format payload, autentikasi, dan mekanisme komunikasi ditentukan pada tahap **API/Integration Specification** setelah spesifikasi SIMRS tersedia.

---

## 8. Infrastructure

Sistem akan dideploy secara **On-Premise** pada jaringan intranet rumah sakit.

Instrumen laboratorium dan LIS Server berkomunikasi melalui jaringan lokal sesuai konfigurasi dan protokol yang didukung oleh masing-masing instrumen.

Komponen utama sistem terdiri dari:

* **Laboratory Instruments** sebagai sumber data pemeriksaan.
* **Integration Service** sebagai penerima dan pemroses komunikasi instrumen.
* **PostgreSQL Database** sebagai penyimpanan data.
* **FastAPI Backend** sebagai API dan business logic.
* **React Frontend** sebagai antarmuka monitoring LIS.

---

## 9. Primary System Principles

### 9.1 Instrument as Source of Clinical Result

Instrumen laboratorium merupakan sumber nilai hasil pemeriksaan. LIS bertugas menerima, memproses, menyimpan, dan mendistribusikan data tersebut tanpa mengubah nilai klinisnya.

### 9.2 Immutable Clinical Data

Nilai hasil pemeriksaan yang telah diterima dan disimpan dianggap **immutable**.

### 9.3 Traceability

Setiap hasil pemeriksaan harus dapat ditelusuri melalui rantai:

`Patient → Visit → Order → Test Run → Result → Instrument`

### 9.4 No Data Overwrite

Pengujian ulang tidak boleh menghapus atau menimpa hasil pemeriksaan sebelumnya.

### 9.5 Controlled Finalization

Pemilihan hasil final merupakan bagian dari workflow analis dan tidak mengubah nilai hasil pemeriksaan yang berasal dari instrumen.

### 9.6 Separation of Concerns

Komunikasi dengan instrumen, business logic/API, penyimpanan data, dan antarmuka pengguna dipisahkan secara jelas untuk menjaga maintainability dan reliability sistem.

---

## 10. Project Success Criteria

MVP dianggap berhasil apabila sistem mampu:

1. menerima data pemeriksaan dari instrumen yang telah berhasil diintegrasikan;
2. memproses dan menyimpan hasil pemeriksaan tanpa kehilangan data;
3. mempertahankan hasil *re-run* tanpa menimpa hasil sebelumnya;
4. menampilkan hasil pemeriksaan pada dashboard LIS;
5. memungkinkan analis memilih *Test Run* final;
6. mempertahankan nilai klinis hasil pemeriksaan tanpa manipulasi;
7. mengirim hasil final ke SIMRS melalui API sesuai spesifikasi integrasi;
8. menyediakan akses terhadap riwayat hasil pemeriksaan;
9. menyediakan keterlacakan dari hasil pemeriksaan hingga instrumen sumbernya;
10. tetap dapat beroperasi ketika salah satu instrumen mengalami gangguan koneksi tanpa menghentikan integrasi instrumen lainnya.

---

## 11. Document Boundary

Project Brief ini mendefinisikan **tujuan, ruang lingkup, batasan, dan prinsip utama proyek**.

Detail implementasi didefinisikan pada dokumen berikutnya:

* `02_PRD.md` — Product Requirements dan Functional/Non-Functional Requirements.
* `03_SYSTEM_DESIGN.md` — Arsitektur sistem, komponen, network, data flow, dan integration architecture.
* `04_DATABASE_DESIGN.md` — ERD, tabel, relasi, constraint, dan aturan integritas database.
* `05_DESIGN_SYSTEM.md` — Standar UI/UX dan komponen antarmuka.
* `06_QA_TESTING_PLAN.md` — Strategi pengujian dan quality assurance.
* `07_TASK_LIST.md` — Breakdown pekerjaan dan implementation roadmap.
