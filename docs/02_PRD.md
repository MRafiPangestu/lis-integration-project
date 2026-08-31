# Product Requirements Document (PRD)

# Laboratory Information System (LIS) Middleware

---

## 1. Product Vision

Menciptakan antarmuka pantau terpusat (*Centralized Monitoring Interface*) yang mempercepat alur kerja analis laboratorium dan mengurangi *human error* dalam proses transkripsi data ke SIMRS, dengan tetap menjaga integritas data klinis dan tidak menyediakan fitur untuk memanipulasi nilai hasil pemeriksaan.

LIS berperan sebagai **Middleware** dan **Device Gateway** yang menjembatani instrumen laboratorium dengan SIMRS, bukan sebagai sistem Rekam Medis Utama (*Electronic Medical Record / EMR*).

Sistem dirancang untuk menerima hasil pemeriksaan dari instrumen secara otomatis, menyimpan setiap pengujian secara terstruktur dan dapat ditelusuri, menampilkan hasil kepada analis, mengelola pengujian ulang (*re-run*), serta mendistribusikan *Test Run* yang telah ditetapkan sebagai final ke SIMRS.

---

# 2. System Boundaries & Constraints

## 2.1. Clinical Data Integrity

LIS tidak menyediakan fitur untuk mengubah, mengedit, atau memanipulasi nilai hasil pemeriksaan klinis yang diterima dari instrumen.

Nilai hasil yang diterima dari instrumen harus dipertahankan selama proses:

**Instrument → LIS → Database → Dashboard → SIMRS**

Analis dapat melakukan tindakan administratif terhadap *workflow*, seperti memilih *Test Run* sebagai hasil final atau mengirim hasil ke SIMRS, tetapi tidak dapat mengubah nilai klinis yang terdapat di dalam *Test Run*.

Data klinis hasil pemeriksaan dianggap **immutable setelah berhasil disimpan**.

---

## 2.2. Middleware & Device Gateway Boundary

LIS berfungsi sebagai perantara antara instrumen laboratorium dan SIMRS dengan tanggung jawab utama:

1. Menerima data pemeriksaan dari instrumen.
2. Menyimpan pesan yang diterima untuk kebutuhan audit dan penelusuran.
3. Memproses dan menormalisasi data yang diperlukan.
4. Menyimpan hasil pemeriksaan secara terstruktur.
5. Menampilkan hasil kepada analis.
6. Merekam setiap *Test Run*, termasuk pengujian ulang.
7. Memungkinkan analis memilih *Test Run* final.
8. Mengirim *Test Run* final ke SIMRS melalui API.
9. Menyediakan API untuk akses riwayat hasil pemeriksaan laboratorium.

LIS tidak menggantikan fungsi utama SIMRS atau sistem Rekam Medis.

---

## 2.3. Patient & Transaction Boundary

LIS membedakan antara:

* **Patient** — identitas dasar pasien yang memiliki Nomor RM.
* **Visit** — riwayat kunjungan/transaksi pasien.
* **Order** — permintaan pemeriksaan laboratorium dalam suatu kunjungan.
* **Test Run** — satu sesi pengujian fisik terhadap sampel.
* **Result** — hasil parameter yang dihasilkan oleh suatu *Test Run*.

Hubungan konseptual utama:

**Patient → Visit → Order → Test Run → Result**

Satu pasien dapat memiliki banyak kunjungan, satu kunjungan dapat memiliki banyak *order*, satu *order* dapat memiliki beberapa *Test Run*, dan satu *Test Run* dapat menghasilkan banyak *Result*.

---

## 2.4. Infrastructure Constraint

Sistem akan dideploy secara **On-Premise** pada jaringan intranet rumah sakit.

Instrumen laboratorium dan LIS Server berkomunikasi melalui jaringan lokal sesuai dengan protokol dan mekanisme komunikasi yang didukung oleh masing-masing instrumen.

Fungsi utama penerimaan data instrumen tidak bergantung pada koneksi internet publik.

---

# 3. Actors & User Roles

## 3.1. Laboratory Analyst

Analis laboratorium merupakan pengguna utama LIS.

Analis dapat:

* Memantau hasil pemeriksaan dari berbagai instrumen.
* Memfilter hasil berdasarkan instrumen.
* Melihat detail hasil pemeriksaan.
* Melihat beberapa *Test Run* untuk pemeriksaan yang sama.
* Membandingkan hasil antar-*Test Run*.
* Memilih satu *Test Run* sebagai hasil final.
* Mengirim *Test Run* final ke SIMRS.
* Melihat status pengiriman hasil ke SIMRS.

Analis **tidak dapat**:

* Mengubah nilai hasil pemeriksaan.
* Mengedit parameter hasil.
* Mengubah satuan hasil.
* Mengubah flag hasil.
* Mengubah *reference range* hasil yang diterima dari instrumen.
* Memasukkan nilai klinis pengganti secara manual melalui LIS.

---

## 3.2. SIMRS

SIMRS merupakan sistem eksternal yang berintegrasi dengan LIS.

SIMRS dapat:

* Menerima hasil pemeriksaan final dari LIS melalui API.
* Meminta riwayat hasil pemeriksaan laboratorium pasien melalui API LIS.
* Mengakses data hanya melalui mekanisme integrasi yang telah diotorisasi.

SIMRS merupakan sistem yang bertanggung jawab sebagai sistem informasi rumah sakit utama, sedangkan LIS hanya menyediakan data dan layanan yang berada dalam ruang lingkup laboratorium.

---

## 3.3. Laboratory Instruments

Instrumen laboratorium merupakan sumber data pemeriksaan.

Instrumen dapat mengirimkan atau menyediakan data hasil pemeriksaan kepada LIS melalui mekanisme komunikasi yang didukung oleh masing-masing perangkat.

Instrumen merupakan **source of clinical result data** pada sisi LIS.

---

# 4. Functional Requirements

# 4.1. Instrument Connectivity & Message Processing

## FR-01 — Multi-Instrument Connectivity

Sistem harus mampu menangani komunikasi data dengan hingga **9 instrumen laboratorium secara bersamaan** tanpa kegagalan atau gangguan pada satu instrumen menyebabkan komunikasi dengan instrumen lainnya terhenti.

Setiap koneksi instrumen harus diproses secara terisolasi sehingga kegagalan pada satu perangkat tidak menghentikan layanan instrumen lainnya.

---

## FR-02 — Protocol Support

Sistem harus mampu memproses pesan pemeriksaan menggunakan protokol komunikasi yang dibutuhkan oleh instrumen dalam ruang lingkup proyek, termasuk **ASTM dan HL7** sesuai implementasi dan spesifikasi masing-masing instrumen.

Detail protokol, mode komunikasi, IP address, port, framing, dan format pesan masing-masing instrumen ditentukan pada dokumen **System Design / Instrument Integration Specification**.

---

## FR-03 — Message Reception & Raw Message Traceability

Sistem harus dapat menerima pesan mentah (*raw message*) dari instrumen dan menyimpan informasi yang diperlukan untuk kebutuhan audit serta penelusuran proses integrasi.

Informasi minimal yang dapat ditelusuri meliputi:

* Instrumen sumber.
* Isi pesan yang diterima atau representasi raw message yang diperlukan.
* Waktu penerimaan.
* Status pemrosesan pesan.
* Informasi error apabila proses parsing gagal.

Pesan mentah dapat digunakan untuk membantu proses debugging, audit, dan investigasi apabila terjadi masalah integrasi.

---

## FR-04 — Message Processing & Data Filtering

Sistem harus mampu mengidentifikasi dan memproses bagian pesan yang diperlukan untuk menghasilkan data pemeriksaan.

Payload non-esensial, seperti data visualisasi instrumen berupa Histogram atau Scattergram, dapat dikecualikan dari penyimpanan hasil utama selama tidak menghilangkan data dan metadata yang diperlukan untuk:

* Identifikasi pasien.
* Identifikasi pemeriksaan.
* Identifikasi instrumen.
* Integritas hasil.
* Penelusuran data.
* Integrasi dengan SIMRS.

---

## FR-05 — Data Validation & Normalization

Sistem harus melakukan validasi teknis terhadap data yang diterima sebelum disimpan sebagai hasil pemeriksaan terstruktur.

Validasi sekurang-kurangnya mencakup informasi yang diperlukan untuk:

* Identifikasi pasien.
* Identifikasi order atau pemeriksaan.
* Identifikasi instrumen.
* Identifikasi parameter.
* Nilai hasil.
* Satuan apabila tersedia.
* Flag hasil apabila tersedia.

Data dapat dinormalisasi ke dalam struktur internal LIS tanpa mengubah makna atau nilai klinis yang diterima dari instrumen.

---

# 4.2. View-Only LIS Dashboard

## FR-06 — Device Filtering

Sistem harus menyediakan mekanisme bagi analis untuk memfilter hasil pemeriksaan berdasarkan instrumen sumber.

Analis harus dapat menampilkan:

* Semua instrumen.
* Satu instrumen tertentu.
* Instrumen tertentu sesuai kebutuhan monitoring.

---

## FR-07 — Automatic Result Update

Sistem harus memperbarui tampilan hasil pemeriksaan secara otomatis setelah data baru berhasil diterima dan diproses, tanpa mengharuskan analis melakukan *manual page refresh*.

Mekanisme teknis untuk pembaruan otomatis ditentukan pada tahap implementasi.

---

## FR-08 — Result Display

Dashboard harus menampilkan informasi hasil pemeriksaan yang relevan, sekurang-kurangnya:

* Nomor RM.
* Nama pasien.
* Parameter pemeriksaan.
* Nilai hasil.
* Satuan.
* Flag abnormalitas.
* Instrumen sumber.
* Waktu pemeriksaan/penerimaan.
* Informasi *Test Run* apabila terdapat lebih dari satu pengujian.

---

## FR-09 — Abnormality Highlighting

Sistem harus menampilkan status atau *flag* abnormalitas yang diterima dari instrumen dan memberikan penanda visual yang membedakan hasil abnormal dari hasil normal.

Klasifikasi abnormalitas harus mengikuti informasi atau konfigurasi yang berlaku pada masing-masing instrumen.

Sistem tidak boleh mengubah nilai hasil hanya untuk menentukan tampilan abnormalitas.

---

# 4.3. Patient, Visit & Order Management

## FR-10 — Patient Identification

Sistem harus dapat mengidentifikasi pasien menggunakan **Nomor RM** sebagai identifier utama pasien dalam LIS.

Nomor RM harus dapat digunakan untuk menelusuri seluruh riwayat hasil pemeriksaan laboratorium yang tersimpan di LIS.

---

## FR-11 — Visit / Transaction History

Sistem harus mampu membedakan identitas pasien dengan riwayat kunjungan/transaksi.

Satu pasien dapat memiliki banyak kunjungan atau registrasi.

Setiap kunjungan dapat memiliki satu atau lebih *Order* pemeriksaan laboratorium.

Informasi kunjungan harus dapat ditelusuri melalui identifier transaksi/registrasi yang tersedia dari sistem rumah sakit.

---

## FR-12 — Laboratory Order

Sistem harus mampu mengaitkan hasil pemeriksaan dengan *Order* yang menjadi konteks permintaan pemeriksaan.

Satu *Order* harus dapat memiliki beberapa *Test Run* untuk mengakomodasi pengujian ulang terhadap pemeriksaan yang sama.

---

# 4.4. Re-run Management & Data Integrity

## FR-13 — Multiple Test Run Handling

Sistem harus merekam setiap pengujian (*run*) sebagai **Test Run terpisah** dan tidak boleh menimpa data dari pengujian sebelumnya.

Jika satu *Order* menghasilkan beberapa pengujian, seluruh *Test Run* harus tetap tersimpan.

Setiap *Test Run* harus dapat ditelusuri sekurang-kurangnya berdasarkan:

* Order terkait.
* Instrumen sumber.
* Waktu pengujian atau waktu penerimaan.
* Data hasil yang diterima.
* Urutan *run* apabila tersedia.

---

## FR-14 — Result per Test Run

Setiap *Test Run* dapat menghasilkan banyak parameter pemeriksaan.

Struktur hubungan harus memungkinkan:

**1 Order → N Test Runs → N Results**

Dalam satu *Test Run*, parameter hasil yang sama tidak boleh disimpan lebih dari satu kali apabila berasal dari satu pesan/pengujian yang sama, kecuali terdapat kebutuhan khusus yang ditentukan oleh spesifikasi instrumen.

---

## FR-15 — Final Test Run Selection

Sistem harus menyediakan mekanisme bagi analis untuk memilih satu *Test Run* sebagai hasil final yang menjadi acuan proses pengiriman ke SIMRS.

Pemilihan *Test Run* final:

* Tidak mengubah nilai klinis.
* Tidak menggabungkan nilai dari beberapa *Test Run*.
* Tidak menghapus *Test Run* sebelumnya.
* Tidak mengubah isi hasil yang berasal dari instrumen.

Untuk setiap *Order*, sistem hanya boleh memiliki **satu Test Run yang berstatus final pada satu waktu**.

Jika analis memilih *Test Run* lain sebagai final, status final sebelumnya harus dicabut atau digantikan tanpa mengubah data hasil di dalam *Test Run* tersebut.

---

# 4.5. SIMRS Integration Gateway

## FR-16 — Push Result to SIMRS

Sistem harus menyediakan mekanisme **POST Gateway** untuk mengirim hasil pemeriksaan final ke endpoint SIMRS yang telah dikonfigurasi.

Pengiriman harus menggunakan data yang berasal dari **satu Test Run final**.

Sistem harus:

1. Mengirim data hasil dari *Test Run* final.
2. Tidak mengubah nilai klinis sebelum pengiriman.
3. Menampilkan status proses pengiriman.
4. Mencatat status pengiriman.
5. Mencatat waktu pengiriman.
6. Mencatat informasi respons dari SIMRS apabila tersedia.

Status pengiriman minimal harus dapat membedakan:

* `Pending`
* `Sending`
* `Success`
* `Failed`

Mekanisme pemicu pengiriman dapat berupa aksi analis atau mekanisme *request-based* lain yang disepakati dengan integrasi SIMRS.

---

## FR-17 — Historical Result API

Sistem harus menyediakan API yang memungkinkan sistem yang berwenang, termasuk SIMRS, mengambil **riwayat hasil pemeriksaan laboratorium pasien berdasarkan Nomor RM**.

Data yang diberikan harus berasal dari hasil pemeriksaan yang tersimpan di LIS dan tidak boleh mengubah data yang tersimpan.

API harus mengembalikan konteks yang diperlukan untuk membedakan hasil pemeriksaan berdasarkan:

* Pasien.
* Kunjungan/registrasi apabila tersedia.
* Order.
* Test Run.
* Instrumen.
* Waktu pemeriksaan.
* Parameter hasil.

API ini menyediakan **riwayat hasil laboratorium**, bukan keseluruhan rekam medis pasien.

---

# 4.6. Workflow & Delivery Status

## FR-18 — Test Run Workflow Status

Sistem harus dapat menyimpan metadata workflow yang berkaitan dengan *Test Run*, termasuk status finalisasi dan status pengiriman ke SIMRS.

Metadata workflow dapat berubah sesuai aktivitas pengguna atau proses integrasi.

Perubahan metadata workflow tidak boleh mengubah nilai klinis yang tersimpan.

---

# 5. Non-Functional Requirements

## NFR-01 — Data Integrity

Nilai hasil pemeriksaan yang diterima dari instrumen harus dipertahankan tanpa perubahan selama proses:

**Instrument → LIS → Database → Dashboard → SIMRS**

Data klinis hasil pemeriksaan yang telah tersimpan tidak boleh dimodifikasi melalui fungsi aplikasi.

---

## NFR-02 — Clinical Data Immutability

Data klinis yang berasal dari instrumen, termasuk sekurang-kurangnya:

* Nilai hasil.
* Parameter.
* Satuan.
* Flag abnormalitas.
* Reference range yang diterima dari instrumen.
* Waktu pemeriksaan yang berasal dari instrumen apabila tersedia.

harus diperlakukan sebagai **immutable** setelah berhasil disimpan.

Perubahan hanya diperbolehkan pada metadata workflow yang tidak mengubah substansi hasil klinis.

---

## NFR-03 — Reliability

Kegagalan komunikasi atau gangguan pada satu instrumen tidak boleh menyebabkan seluruh layanan LIS berhenti atau mengganggu komunikasi dengan instrumen lainnya.

---

## NFR-04 — Connection Recovery

Sistem harus mampu menangani kondisi kegagalan koneksi instrumen dan melakukan proses pemulihan komunikasi sesuai mekanisme yang ditentukan pada System Design.

Kegagalan koneksi tidak boleh menyebabkan data yang sudah berhasil diterima dan diproses menjadi hilang.

---

## NFR-05 — Concurrency

Sistem harus dapat menangani data yang diterima secara bersamaan dari beberapa instrumen tanpa menyebabkan:

* Kehilangan data.
* Pencampuran data antar-instrumen.
* Duplikasi transaksi yang tidak disengaja.
* Korupsi data.

---

## NFR-06 — Performance

Data hasil pemeriksaan yang berhasil diterima dan diproses harus tersedia pada dashboard dalam waktu yang cukup cepat untuk mendukung kebutuhan monitoring operasional laboratorium.

Target waktu aktual untuk penerimaan, pemrosesan, dan tampilan data ditentukan pada tahap System Design dan Performance Testing.

---

## NFR-07 — Auditability & Traceability

Sistem harus menyimpan informasi yang memungkinkan penelusuran hasil pemeriksaan dari data klinis kembali ke sumbernya.

Penelusuran minimal harus mencakup:

**Patient → Visit → Order → Test Run → Instrument → Result**

Sistem juga harus dapat mengaitkan hasil dengan pesan instrumen yang menjadi sumber penerimaannya apabila diperlukan untuk audit atau troubleshooting.

---

## NFR-08 — Workflow Auditability

Sistem harus mencatat aktivitas penting yang berkaitan dengan workflow, termasuk:

* Pemilihan *Test Run* final.
* Perubahan status final.
* Proses pengiriman ke SIMRS.
* Status dan waktu pengiriman.
* Error parsing.
* Gangguan koneksi instrumen.

Informasi audit harus mencakup timestamp dan identitas pengguna apabila aktivitas dilakukan oleh pengguna.

---

## NFR-09 — Security

Akses terhadap fungsi LIS dan API harus dibatasi berdasarkan kebutuhan dan hak akses yang ditentukan.

Data pasien dan hasil pemeriksaan hanya boleh dapat diakses oleh pengguna atau sistem yang berwenang.

API integrasi eksternal harus memiliki mekanisme autentikasi/otorisasi yang ditentukan pada tahap System Design dan Integration Specification.

---

## NFR-10 — Deployment

Sistem harus dapat dijalankan pada lingkungan **On-Premise** dan jaringan intranet rumah sakit tanpa ketergantungan terhadap koneksi internet untuk fungsi utama komunikasi antara instrumen dan LIS.

---

# 6. Acceptance Criteria

## AC-01 — Multi-Instrument Connectivity

**Given** beberapa instrumen aktif secara bersamaan.

**When** masing-masing instrumen mengirimkan data ke LIS.

**Then** LIS harus dapat menerima dan memproses data dari setiap instrumen tanpa satu koneksi menghambat koneksi lainnya.

---

## AC-02 — Protocol Processing

**Given** instrumen mengirim pesan menggunakan protokol yang telah ditentukan untuk instrumen tersebut.

**When** LIS menerima pesan.

**Then** LIS harus dapat memproses bagian pesan yang diperlukan dan menghasilkan data pemeriksaan yang dapat disimpan.

---

## AC-03 — Raw Message Traceability

**Given** LIS menerima pesan dari instrumen.

**When** pesan berhasil atau gagal diproses.

**Then** sistem harus dapat mencatat instrumen sumber, waktu penerimaan, dan status pemrosesan pesan.

---

## AC-04 — Data Integrity

**Given** instrumen mengirimkan suatu nilai hasil pemeriksaan.

**When** data diterima, diproses, disimpan, dan ditampilkan.

**Then** nilai yang ditampilkan harus sama dengan nilai yang diterima dari instrumen.

---

## AC-05 — Patient Transaction History

**Given** satu pasien dengan Nomor RM yang sama melakukan beberapa kunjungan.

**When** setiap kunjungan memiliki pemeriksaan laboratorium.

**Then** LIS harus dapat mempertahankan hubungan antara pasien, kunjungan, order, dan hasil pemeriksaan secara terpisah.

---

## AC-06 — Multiple Test Run

**Given** satu order menghasilkan dua atau lebih pengujian dari instrumen.

**When** seluruh pengujian diterima oleh LIS.

**Then** LIS harus menyimpan setiap pengujian sebagai *Test Run* yang berbeda tanpa menimpa data pengujian sebelumnya.

---

## AC-07 — Final Test Run

**Given** terdapat beberapa *Test Run* untuk satu order.

**When** analis memilih salah satu *Test Run* sebagai final.

**Then** hanya *Test Run* tersebut yang berstatus final dan menjadi sumber data untuk pengiriman ke SIMRS.

Nilai klinis di dalam seluruh *Test Run* tidak boleh berubah.

---

## AC-08 — Final Run Constraint

**Given** satu *Order* telah memiliki satu *Test Run* berstatus final.

**When** analis memilih *Test Run* lainnya sebagai final.

**Then** sistem harus mengganti status final tanpa menghasilkan lebih dari satu *Test Run* final pada *Order* yang sama.

---

## AC-09 — Dashboard Update

**Given** hasil baru berhasil diproses oleh LIS.

**When** analis sedang membuka dashboard.

**Then** hasil tersebut harus muncul secara otomatis tanpa analis melakukan *manual page refresh*.

---

## AC-10 — Abnormality Highlighting

**Given** instrumen mengirimkan hasil dengan status atau flag abnormal.

**When** hasil ditampilkan pada dashboard.

**Then** hasil tersebut harus memiliki penanda visual yang membedakannya dari hasil normal sesuai informasi instrumen.

Nilai klinis tidak boleh diubah untuk menghasilkan penanda tersebut.

---

## AC-11 — SIMRS Push

**Given** sebuah *Test Run* telah ditetapkan sebagai final.

**When** analis atau mekanisme pengiriman yang disepakati menjalankan proses pengiriman ke SIMRS.

**Then** LIS harus mengirim data dari *Test Run* tersebut dan mencatat status serta waktu pengiriman.

Jika pengiriman gagal, LIS harus menampilkan status kegagalan tanpa mengubah nilai hasil pemeriksaan.

---

## AC-12 — Historical Result API

**Given** SIMRS mengirimkan permintaan riwayat hasil berdasarkan Nomor RM yang valid dan terotorisasi.

**When** LIS menerima permintaan.

**Then** LIS harus mengembalikan riwayat hasil pemeriksaan laboratorium yang tersedia untuk pasien tersebut tanpa mengubah data yang tersimpan.

---

## AC-13 — Instrument Failure Isolation

**Given** salah satu instrumen mengalami gangguan koneksi.

**When** instrumen lain tetap aktif dan mengirimkan data.

**Then** LIS harus tetap dapat menerima dan memproses data dari instrumen lain.

---

# 7. Out of Scope

## 7.1. Rekam Medis Utama

LIS bukan pengganti SIMRS atau sistem Electronic Medical Record.

LIS hanya menyimpan dan menyediakan data yang berkaitan dengan pemeriksaan laboratorium dalam ruang lingkup sistem.

---

## 7.2. Clinical Result Editing

Tidak terdapat fitur untuk:

* Mengubah nilai hasil.
* Mengedit hasil pemeriksaan.
* Mengubah parameter hasil.
* Mengubah satuan.
* Mengubah flag hasil.
* Mengubah reference range hasil.
* Memasukkan nilai klinis pengganti secara manual.

---

## 7.3. Billing

Sistem tidak mencakup:

* Penagihan pasien.
* Pembayaran.
* Invoice.
* Manajemen tarif pemeriksaan.

---

## 7.4. Reagent & Inventory Management

Sistem tidak mencakup:

* Manajemen stok reagen.
* Pengadaan reagen.
* Monitoring inventaris laboratorium.
* Expired-date management reagen.

---

## 7.5. Clinical Interpretation

LIS tidak melakukan diagnosis atau interpretasi klinis terhadap hasil pemeriksaan.

Validasi operasional terhadap hasil dilakukan melalui pemilihan *Test Run* yang dianggap final oleh analis, tanpa mengubah nilai hasil pemeriksaan.

---

## 7.6. Manual Result Entry

LIS tidak menyediakan mekanisme untuk memasukkan hasil pemeriksaan secara manual sebagai pengganti hasil yang berasal dari instrumen.

---

# 8. Instrument Scope

MVP mencakup integrasi dengan hingga **9 instrumen laboratorium** berikut:

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

Detail teknis masing-masing instrumen seperti:

* Protokol komunikasi.
* IP address.
* Port.
* Mode komunikasi (*listener/push* atau *query/pull*).
* Framing/message structure.
* Parameter hasil.
* Mapping parameter.

ditentukan pada dokumen **System Design / Instrument Integration Specification**.

---

# 9. Project Success Criteria

Proyek dianggap berhasil apabila:

1. Instrumen yang termasuk dalam scope dapat terhubung dan mengirimkan data ke LIS sesuai protokol masing-masing.
2. Data pesan instrumen dapat diterima dan ditelusuri.
3. Data hasil pemeriksaan dapat diproses dan disimpan tanpa kehilangan atau perubahan nilai klinis.
4. Identitas pasien dapat ditelusuri berdasarkan Nomor RM.
5. Riwayat kunjungan/transaksi pasien dapat dibedakan.
6. Satu *Order* dapat memiliki beberapa *Test Run* tanpa menimpa pengujian sebelumnya.
7. Setiap *Test Run* dapat memiliki banyak *Result*.
8. Analis dapat memilih satu *Test Run* sebagai hasil final tanpa mengubah nilai klinis.
9. Hanya satu *Test Run* yang dapat berstatus final untuk satu *Order* pada satu waktu.
10. Hasil pemeriksaan dapat dipantau secara terpusat melalui dashboard.
11. Dashboard dapat memperbarui hasil secara otomatis tanpa *manual page refresh*.
12. Hasil final dapat dikirim ke SIMRS melalui mekanisme API yang disepakati.
13. SIMRS dapat mengambil riwayat hasil pemeriksaan melalui API LIS.
14. Gangguan pada satu instrumen tidak menyebabkan keseluruhan layanan LIS berhenti.
15. Aktivitas penting dan status integrasi dapat ditelusuri melalui audit/logging.

---

# 10. Requirement Traceability

| Requirement | Tujuan / Komponen Utama                          |
| ----------- | ------------------------------------------------ |
| FR-01       | Multi-instrument connectivity                    |
| FR-02       | ASTM / HL7 processing                            |
| FR-03       | Raw message & integration traceability           |
| FR-04       | Message filtering                                |
| FR-05       | Validation & normalization                       |
| FR-06–09    | Dashboard & monitoring                           |
| FR-10–12    | Patient, Visit & Order                           |
| FR-13–15    | Test Run, Re-run & Final Selection               |
| FR-16–17    | SIMRS Integration Gateway                        |
| FR-18       | Workflow metadata                                |
| NFR-01–02   | Clinical data integrity & immutability           |
| NFR-03–06   | Reliability, recovery, concurrency & performance |
| NFR-07–08   | Auditability & traceability                      |
| NFR-09–10   | Security & deployment                            |

---

# 11. Requirement Boundary with Other Documents

PRD ini mendefinisikan **apa yang harus dilakukan sistem** dan batasan fungsionalnya.

Dokumen lain memiliki tanggung jawab sebagai berikut:

* **`01_PROJECT_BRIEF.md`** — tujuan proyek, scope, konteks bisnis, dan batasan tingkat tinggi.
* **`02_PRD.md`** — kebutuhan fungsional, non-fungsional, aktor, acceptance criteria, dan batasan sistem.
* **`03_SYSTEM_DESIGN.md`** — bagaimana kebutuhan tersebut diwujudkan secara arsitektural dan teknis.
* **`04_DATABASE_DESIGN.md`** — bagaimana data dan hubungan antar-entitas direpresentasikan di PostgreSQL.
* **Instrument Integration Specification** — detail komunikasi masing-masing instrumen, termasuk protokol, koneksi, framing, message structure, dan mapping parameter.
