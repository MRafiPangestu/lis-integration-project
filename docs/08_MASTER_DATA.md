# **1\. Purpose & Scope**

Dokumen ini mendefinisikan \*\*master data\*\* dan \*\*reference data\*\* yang digunakan dalam pengembangan Laboratory Information System (LIS) Marina Permata, khususnya untuk kebutuhan \*\*M1.3 — Master Data Seed\*\*.

Dokumen ini menjadi \*\*source of truth\*\* untuk menentukan:

\- data master apa yang termasuk dalam scope M1.3;  
\- data mana yang boleh di-seed ke development database;  
\- data mana yang hanya bersifat reference/research;  
\- data mana yang masih menunggu field verification;  
\- batasan pengisian actual instrument configuration;  
\- aturan pembaruan master data.

M1.3 berfokus pada tiga kelompok data utama:

\`\`\`text  
1\. Instruments  
2\. Units  
3\. Test Groups

Laboratory test catalog, test subcategories, dan technical capability hasil research **belum menjadi data seed M1.3**.

---

# **2\. Data Sources & Authority**

Master data diklasifikasikan berdasarkan sumber dan tingkat otoritasnya.

| Data | Source | Authority |
| ----- | ----- | ----- |
| Instrument Names | Project Brief / Project Scope | Authoritative |
| Unit List | RS Marina Permata | Authoritative |
| Test Groups | Laboratory Form / RS source | RS-derived |
| Laboratory Test Catalog | Laboratory Form / RS source | RS-derived |
| Protocol Capability | Technical Research | Provisional / Research Baseline |
| Connection Capability | Technical Research | Provisional / Research Baseline |
| Actual Instrument Configuration | Field Survey / Physical Verification | Field-Verified / Pending |

### **Authority Principle**

Data actual deployment tidak boleh ditentukan hanya berdasarkan hasil research.

Urutan authority untuk actual instrument configuration:

1\. Actual physical / field-verified configuration  
2\. Official hospital/project documentation  
3\. Vendor technical documentation  
4\. Technical research / secondary source

Research dapat digunakan sebagai **technical baseline**, tetapi tidak otomatis menjadi actual deployment configuration.

---

# **3\. Data Classification**

Setiap master/reference data menggunakan salah satu klasifikasi berikut.

## **3.1 Authoritative**

Data berasal dari project scope atau sumber resmi rumah sakit dan dapat digunakan sebagai dasar master data.

Contoh:

Instrument identity  
Unit name/code  
Primary test group

## **3.2 Field-Verified**

Data telah diverifikasi terhadap kondisi aktual perangkat/deployment.

Contoh saat ini:

Mindray BC-5150  
Protocol: HL7  
Connection: TCP/IP

## **3.3 Research Baseline**

Informasi teknis yang diperoleh dari technical research dan digunakan sebagai referensi pengembangan.

Contoh:

Device may support HL7  
Device may support ASTM  
Device may support RS-232  
Device may support TCP/IP

Research baseline **tidak boleh dianggap sebagai actual deployment configuration**.

## **3.4 Pending Verification**

Data yang belum dapat dipastikan dari field survey atau sumber resmi.

Contoh:

Actual protocol  
Actual connection  
IP address  
TCP port  
Serial parameters  
Firmware version  
Exact model identity  
---

# **4\. Seed Eligibility**

Aturan eligibility untuk M1.3:

| Data | M1.3 Seed | Rule |
| ----- | ----- | ----- |
| Instrument Identity | ✅ | Seed |
| Protocol Capability | ❌ | Reference only |
| Connection Capability | ❌ | Reference only |
| Actual Protocol | ⚠️ | Hanya jika field-verified |
| Actual Connection | ⚠️ | Hanya jika field-verified |
| Unit Code & Name | ✅\* | Hanya unit dengan confirmed official code |
| Primary Test Group | ✅ | Seed |
| Test Subcategory | ❌ | Reference only |
| Laboratory Test Catalog | ❌ | Reference only |
| IP Address | ❌ | Pending field verification |
| TCP Port | ❌ | Pending field verification |
| Serial Settings | ❌ | Pending field verification |
| Firmware | ❌ | Pending field verification |

---

# **5\. Instrument Master**

M1.3 mencakup **9 instrument identities** berikut.

| \# | Manufacturer / Brand | Instrument | Protocol Capability | Connection Capability | Actual Deployment | Status |
| ----- | ----- | ----- | ----- | ----- | ----- | ----- |
| 1 | Mindray | BC-5150 | HL7, ASTM | TCP/IP, RS-232, USB | HL7 / TCP-IP | **Field-Confirmed** |
| 2 | Sysmex | XN-550 | ASTM, HL7 | TCP/IP, RS-232 | Pending | Research Baseline |
| 3 | Mindray | BS-200E | HL7 | TCP/IP | Pending | Research Baseline |
| 4 | Sysmex | BX-3010 | ASTM, HL7 | RS-232 | Pending | Research Baseline |
| 5 | Boditech Med Inc. | ichroma II | ASTM | TCP/IP, RS-232, USB | Pending | Research Baseline |
| 6 | Medica | EasyLyte PLUS | Proprietary (ASCII) | RS-232 | Pending | Research Baseline |
| 7 | DFI | R-300 | Proprietary | RS-232 | Pending | Configuration Dependent |
| 8 | ACON / Mission | Insight Expert U120 | Proprietary, ASTM | RS-232, TCP/IP, USB | Pending | Configuration Dependent |
| 9 | Precil | `106-AC-57000131 (Reported ID)` | Unverified | Unverified | Pending | Identity Unverified |

## **5.1 Instrument Identity Principle**

Untuk M1.3, yang di-seed adalah **instrument identity**.

Identity harus mengikuti project scope dan dokumentasi master data.

Jangan:

* mengarang model;  
* mengganti nama instrument berdasarkan asumsi;  
* mengubah reported identifier menjadi model yang belum diverifikasi;  
* menambahkan instrument di luar daftar 9 instrument tanpa perubahan source of truth.

Khusus:

Precil — 106-AC-57000131 (Reported ID)

harus tetap dianggap sebagai **reported/unverified identifier** sampai dilakukan physical/nameplate verification.

---

# **6\. Actual Instrument Configuration**

Kolom database berikut merepresentasikan **actual deployment configuration**:

instruments.protokol  
instruments.tipe\_koneksi

Kolom tersebut **bukan** tempat untuk menyimpan seluruh technical capability perangkat.

## **6.1 Mindray BC-5150**

BC-5150 merupakan instrument yang saat ini telah diverifikasi dalam PoC/integration testing.

Actual configuration:

Protocol:  
HL7

Connection:  
TCP/IP

Dengan demikian:

protokol \= HL7  
tipe\_koneksi \= TCP/IP

dapat disimpan sebagai actual deployment configuration.

## **6.2 Instrument Lain**

Untuk instrument selain BC-5150:

protokol \= NULL  
tipe\_koneksi \= NULL

sampai actual configuration diverifikasi.

Jangan mengisi actual configuration menggunakan research capability saja.

Contoh:

Research says ASTM supported

tidak berarti:

actual protocol \= ASTM

Contoh lain:

Research says RS-232 supported

tidak berarti:

actual connection \= RS-232  
---

# **7\. Instrument Technical Reference**

Technical capability berikut dapat digunakan sebagai **development reference**, tetapi tidak otomatis dimasukkan ke master actual deployment.

| Instrument | Technical Reference |
| ----- | ----- |
| BC-5150 | HL7 / ASTM; TCP/IP / RS-232 / USB |
| XN-550 | ASTM / HL7; TCP/IP / RS-232 |
| BS-200E | HL7; TCP/IP |
| BX-3010 | ASTM / HL7; RS-232 |
| ichroma II | ASTM; TCP/IP / RS-232 / USB |
| EasyLyte PLUS | Proprietary / ASCII; RS-232 |
| R-300 | Proprietary; RS-232 |
| Insight Expert U120 | Proprietary / ASTM; RS-232 / TCP/IP / USB |
| Precil `106-AC-57000131` | Unverified |

Technical reference di atas dapat membantu pengembangan future parser/interface, tetapi bukan bukti konfigurasi aktual.

Untuk perangkat yang secara fisik menggunakan serial interface, implementasi deployment dapat memerlukan external serial-to-LAN gateway bergantung pada topology aktual. Hal tersebut harus diverifikasi di lapangan sebelum dimasukkan ke actual configuration.

---

# **8\. Unit Master**

Daftar unit yang diperoleh dari RS Marina Permata mencakup:

* IGD — Instalasi Gawat Darurat  
* IRJA — Instalasi Rawat Jalan  
* IRNA — Instalasi Rawat Inap  
* ICU — Intensive Care Unit  
* NICU — Neonatal Intensive Care Unit  
* PICU — Pediatric Intensive Care Unit  
* PONEK — Pelayanan Obstetri Neonatal Esensial / Emergensi Komperhensif  
* VK — Verloskamer  
* Rehabilitasi Medik  
* Dialisis  
* Home Care  
* MCU — Medical Check Up  
* APS — Atas Permintaan Sendiri

## **8.1 Confirmed Unit Codes**

Untuk M1.3, hanya unit berikut yang memiliki confirmed code dan eligible untuk seed:

| \# | Kode | Nama |
| ----- | ----- | ----- |
| 1 | IGD | Instalasi Gawat Darurat |
| 2 | IRJA | Instalasi Rawat Jalan |
| 3 | IRNA | Instalasi Rawat Inap |
| 4 | ICU | Intensive Care Unit |
| 5 | NICU | Neonatal Intensive Care Unit |
| 6 | PICU | Pediatric Intensive Care Unit |
| 7 | PONEK | Pelayanan Obstetri Neonatal Esensial / Emergensi Komperhensif |
| 8 | VK | Verloskamer |
| 9 | MCU | Medical Check Up |
| 10 | APS | Atas Permintaan Sendiri |

Total eligible unit seed:

10 records

## **8.2 Units Pending Official Code**

Unit berikut **belum boleh di-seed** karena official code belum tersedia:

Rehabilitasi Medik  
Dialisis  
Home Care

Jangan membuat abbreviation/code berdasarkan asumsi.

Contoh:

REHAB  
DM  
HC

tidak boleh digunakan kecuali telah ditetapkan sebagai official code.

---

# **9\. Test Group Master**

M1.3 menggunakan enam primary laboratory test groups.

| \# | Test Group | urutan\_tampil |
| ----- | ----- | ----- |
| 1 | Hematologi | 1 |
| 2 | Urine | 2 |
| 3 | Feses | 3 |
| 4 | Kimia Darah | 4 |
| 5 | Imunoserologi | 5 |
| 6 | Lain-lain | 6 |

Total primary test groups:

6 records  
---

# **10\. Test Subcategories**

Untuk kebutuhan grouping/reference pada **Kimia Darah**, terdapat subkategori:

1\. Gula Darah  
2\. Fungsi Ginjal  
3\. Lemak  
4\. Fungsi Hati  
5\. Elektrolit

Subkategori tersebut adalah **reference/UI grouping**.

Untuk M1.3:

DO NOT seed as test\_groups

Tidak boleh membuat:

test\_group \= Gula Darah  
test\_group \= Fungsi Ginjal  
test\_group \= Lemak  
test\_group \= Fungsi Hati  
test\_group \= Elektrolit

sebagai primary `test_groups`.

---

# **11\. Laboratory Test Catalog — Reference Only**

Laboratory test catalog berasal dari laboratory form RS dan digunakan sebagai reference untuk pengembangan berikutnya.

## **11.1 Hematologi**

Darah Rutin  
Darah Lengkap  
LED  
Golongan darah  
CT  
BT  
PT  
APTT  
INR  
MDT  
DDR

## **11.2 Urine**

Urine Rutin  
Urine Lengkap (Urine rutin \+ Sedimen)  
Plano test / Tes Kehamilan  
Narkoba

## **11.3 Feses**

Feses Rutin

## **11.4 Kimia Darah**

### **Gula Darah**

Glukosa Puasa  
Glukosa 2 Jam PP  
Glukosa Sewaktu  
HbA1C

### **Fungsi Ginjal**

Ureum  
Creatinin  
Asam Urat

### **Lemak**

Cholestrol total  
Trigliserida  
HDL  
LDL

### **Fungsi Hati**

SGOT/AST  
SGPT/ALT  
Bilirubin Total  
Bilirubin Direk  
Bilirubin Indirek  
Albumin  
Total Protein

### **Elektrolit**

Natrium  
Kalium  
Klorida  
Kalsium Total  
Kalsium Ion

## **11.5 Imunoserologi**

HBsAg rapid  
Anti HB rapid  
Anti HCV rapid  
Anti HIV Screening rapid  
Sifilis rapid  
IgG / IgM Dengue rapid  
NS-1  
Malaria Rapid  
Tubex  
Widal  
Antigen SARS-CoV-2  
Antibody SARS-CoV-2  
FT4  
TSH

## **11.6 Lain-lain**

Sputum BTA S/P/S  
TCM-TB (GeneXpert)  
Analisis Sperma  
PCR SARS-CoV-2  
HBsAg Elisa  
HBeAg

### **Important**

Laboratory test catalog di atas adalah:

REFERENCE ONLY

dan **tidak termasuk M1.3 seed**.

Tabel `tests` tidak boleh di-seed pada milestone ini.

---

# **12\. Pending Field Verification**

Data berikut masih membutuhkan field verification:

## **Instrument configuration**

* actual protocol  
* actual connection type  
* IP address  
* TCP port  
* serial communication parameters  
* firmware version  
* actual enabled interface

## **Instrument identity**

Khusus perangkat Precil:

106-AC-57000131

exact manufacturer/model/nameplate masih harus diverifikasi secara fisik.

## **Unit master**

Official codes untuk:

Rehabilitasi Medik  
Dialisis  
Home Care

masih pending.

---

# **13\. Master Data Seed Scope**

## **13.1 SEED NOW — M1.3**

M1.3 seed mencakup:

9 instrument identity records  
10 confirmed unit records  
6 primary test group records

Untuk instruments:

BC-5150:  
    actual protocol \= HL7  
    actual connection \= TCP/IP

Other 8 instruments:  
    actual protocol \= NULL  
    actual connection \= NULL

## **13.2 REFERENCE ONLY**

Tidak di-seed pada M1.3:

Protocol capability  
Connection capability  
Test subcategories  
Laboratory test catalog  
Technical research metadata

## **13.3 FIELD-VERIFIED ONLY**

Actual values berikut hanya boleh dimasukkan ketika telah field-verified:

Actual protocol  
Actual connection  
IP address  
TCP port  
Serial configuration  
Firmware  
---

# **14\. Data Update Policy**

Master data harus diperbarui berdasarkan tingkat authority.

Prioritas:

1\. Actual instrument configuration verified in field  
2\. Official hospital/project documentation  
3\. Vendor technical documentation  
4\. Technical research / secondary source

## **Update Principle**

Jika information baru hanya berasal dari research:

Reference documentation may be updated  
Actual deployment fields should remain NULL

Jika information telah diverifikasi secara fisik:

Actual deployment fields may be updated

Jangan mengganti actual configuration berdasarkan asumsi.

---

# **15\. Seed Database Safety**

M1.3 seed hanya boleh dijalankan terhadap:

lis\_marina\_permata\_dev

Database berikut merupakan protected PoC/demo database:

lis\_marina\_permata

PoC database **tidak boleh diubah oleh seed process**.

Seed implementation harus melakukan exact database-name validation:

database\_name \== "lis\_marina\_permata\_dev"

Bukan substring matching.

Jika active database bukan:

lis\_marina\_permata\_dev

seed harus:

ABORT

tanpa melakukan mutation.

---

# **16\. Idempotency Policy**

Seed harus idempotent.

Repeated execution tidak boleh menghasilkan duplicate master data.

Expected behavior:

Missing record  
    → INSERT

Existing record  
    → PRESERVE

Existing BC-5150 verified field \= NULL  
    → Controlled enrichment allowed

Existing verified/non-NULL value  
    → PRESERVE

Ambiguous identity  
    → STOP AND REPORT

Jangan menggunakan destructive reset untuk memperoleh desired dataset.

---

# **17\. Existing BC-5150 Handling**

Jika `Mindray BC-5150` sudah ada:

DO NOT INSERT DUPLICATE

Identity harus dipertahankan.

Jika:

protokol \= NULL  
tipe\_koneksi \= NULL

maka controlled enrichment berikut diperbolehkan:

protokol \= HL7  
tipe\_koneksi \= TCP/IP

Jika nilai sudah terisi:

DO NOT OVERWRITE

kecuali terdapat field verification baru yang secara eksplisit mengubah source of truth.

---

# **18\. Current M1.3 Seed Snapshot**

Target master data untuk kondisi saat ini:

INSTRUMENTS  
\----------  
Total identities: 9

Field-verified actual configuration:  
\- Mindray BC-5150  
  Protocol: HL7  
  Connection: TCP/IP

Other instruments:  
\- Actual protocol: NULL  
\- Actual connection: NULL  
UNITS  
\-----  
Confirmed-code records eligible for seed: 10

Pending official code:  
\- Rehabilitasi Medik  
\- Dialisis  
\- Home Care  
TEST GROUPS  
\-----------  
Primary groups: 6  
---

# **19\. M1.3 Acceptance Baseline**

M1.3 master data dianggap sesuai dengan specification apabila:

Instrument identities \= 9  
Confirmed unit records \= 10  
Primary test groups \= 6

Dengan kondisi:

BC-5150  
    protocol \= HL7  
    connection \= TCP/IP

dan:

Other instruments  
    protocol \= NULL  
    connection \= NULL

Serta:

No invented unit codes  
No unverified actual configuration  
No test catalog seed  
No subcategory seed  
No duplicate master records  
---

# **20\. Out of Scope**

Dokumen ini tidak menetapkan implementation detail untuk:

\- Laboratory test CRUD  
\- Test master implementation  
\- Patient master implementation  
\- Doctor master implementation  
\- Order management  
\- Test Run management  
\- Result management  
\- Instrument protocol parser  
\- HL7 parser  
\- ASTM parser  
\- Delivery workflow  
\- LIS API  
\- Frontend  
\- Production deployment

Hal-hal tersebut ditangani oleh milestone dan documentation lain.

---

# **21\. Change Control**

Perubahan terhadap master data harus dapat ditelusuri.

Jangan mengubah master/reference data hanya berdasarkan asumsi.

Perubahan yang memengaruhi:

instrument identity  
actual protocol  
actual connection  
unit code  
test group

harus berasal dari sumber yang dapat dipertanggungjawabkan dan tercermin dalam dokumentasi master data.

Untuk actual instrument configuration, field verification memiliki priority tertinggi.

---

# **22\. Summary**

M1.3 saat ini memiliki scope:

9 Instruments  
10 Confirmed Units  
6 Primary Test Groups

Hanya satu instrument yang saat ini memiliki actual deployment configuration yang telah terverifikasi:

Mindray BC-5150  
HL7 / TCP-IP

Technical capability dari instrument lain tetap berada pada level:

Research Baseline

sampai dilakukan field verification.

Dengan demikian, master data database harus membedakan dengan jelas antara:

WHAT THE DEVICE MAY SUPPORT

dan:

WHAT THE CURRENT DEPLOYMENT ACTUALLY USES

Untuk M1.3, hanya informasi yang telah memenuhi authority/verification requirement yang boleh masuk ke actual master data.