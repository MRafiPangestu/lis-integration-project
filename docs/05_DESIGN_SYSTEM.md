# Design System & UI Guidelines

## 1. Purpose

Dokumen ini mendefinisikan prinsip visual, komponen antarmuka, state, dan pola interaksi untuk **Laboratory Information System (LIS) Middleware**.

Design System dirancang untuk mendukung kebutuhan utama analis laboratorium:

- Monitoring hasil pemeriksaan secara cepat.
- Monitoring status konektivitas instrumen.
- Review beberapa `Test Run` dalam satu `Order`.
- Pemilihan `Test Run` sebagai hasil final.
- Monitoring status pengiriman hasil ke SIMRS.
- Mempertahankan sifat **strictly view-only** terhadap nilai klinis.

Prioritas desain:

> **Clarity → Readability → Operational Efficiency → Visual Consistency**

UI tidak boleh mengorbankan keterbacaan data klinis hanya untuk mencapai tampilan visual yang menarik.

---

# 2. Global Design Principles

## 2.1. Function Over Form

UI harus mengutamakan fungsi operasional dibandingkan dekorasi visual.

Hindari:

- Animasi berlebihan.
- Ilustrasi dekoratif yang tidak memiliki fungsi.
- Gradien atau efek visual yang mengganggu.
- Excessive whitespace.
- Komponen yang memperlambat akses terhadap data.

Visual hierarchy harus membuat analis dapat memahami kondisi sistem dalam waktu singkat.

---

## 2.2. Data-Dense Layout

Dashboard LIS menggunakan layout yang relatif padat karena hasil laboratorium terdiri dari banyak parameter.

Gunakan:

- Padding dan margin yang efisien.
- Table row yang compact.
- Informasi penting tetap terlihat tanpa scrolling horizontal/vertikal yang tidak diperlukan.
- Sticky header pada tabel jika diperlukan.
- Sticky status bar untuk informasi instrumen.

Namun, density tidak boleh mengurangi readability.

Target prinsip:

> **Compact, but not cramped.**

---

## 2.3. Strictly View-Only Clinical Data

Nilai klinis yang berasal dari instrumen tidak boleh tampil sebagai komponen editable.

Tidak diperbolehkan:

- Editable table cell.
- Input field untuk `nilai_hasil`.
- Input field untuk `satuan`.
- Input field untuk `flag_abnormalitas`.
- Tombol edit hasil.
- Inline editing hasil laboratorium.

Contoh:

```text
WBC     12.4    10^3/uL    H
HGB     13.2    g/dL
PLT     245     10^3/uL
```

Data ditampilkan sebagai teks statis.

Aksi yang diperbolehkan terhadap hasil adalah aksi workflow, misalnya:

```text
Review Test Run
Set as Final
Sync to SIMRS
Retry Delivery
```

Aksi tersebut tidak mengubah nilai klinis.

---

## 2.4. Always-on Monitoring

Status instrumen harus selalu dapat diketahui tanpa analis harus membuka halaman konfigurasi khusus.

Status konektivitas sembilan instrumen ditampilkan melalui:

**Instrument Connection Status Bar**

Status minimal:

```text
CONNECTED
RECONNECTING
DISCONNECTED
```

Komponen dapat ditempatkan pada bagian atas dashboard dan bersifat sticky/persistent.

---

# 3. Theme

## 3.1. Default Theme: High-Contrast Light Mode

**Light Mode menjadi tema default untuk MVP.**

Pertimbangannya adalah:

- Mendukung keterbacaan tabel data dalam penggunaan operasional.
- Memiliki kontras yang jelas antara teks dan background.
- Sesuai dengan karakteristik aplikasi administrasi/klinis.
- Memudahkan pembacaan data numerik dalam jumlah besar.
- Memudahkan penggunaan warna semantic untuk clinical flags.

Dark Mode tidak menjadi requirement MVP.

Dark Mode dapat dipertimbangkan sebagai:

> **Future Enhancement**

jika terdapat kebutuhan operasional nyata dari pengguna.

---

# 4. Color System

## 4.1. Base Colors

| Token | Value | Usage |
|---|---|---|
| `background` | `#F5F7FA` | Background utama aplikasi |
| `surface` | `#FFFFFF` | Card, table, panel |
| `surface-hover` | `#F0F4F8` | Hover state |
| `border` | `#D1D5DB` | Border dan divider |

---

## 4.2. Text Colors

| Token | Value | Usage |
|---|---|---|
| `text-primary` | `#111827` | Data utama dan heading |
| `text-secondary` | `#6B7280` | Label, metadata, timestamp |
| `text-disabled` | `#9CA3AF` | Disabled state |

Text harus memiliki kontras yang cukup terhadap background.

---

## 4.3. Primary Action

| Token | Value | Usage |
|---|---|---|
| `primary` | `#2563EB` | Primary button |
| `primary-hover` | `#1D4ED8` | Hover |
| `primary-disabled` | `#D1D5DB` | Disabled |

Contoh penggunaan:

```text
Set as Final Run
Sync to SIMRS
```

---

# 5. Semantic Colors

Warna digunakan sebagai **indikator tambahan**, bukan satu-satunya cara untuk memahami status.

Setiap status penting harus tetap memiliki:

- Text label.
- Icon atau indicator.
- Color.

---

## 5.1. Clinical Result Flags

| Flag | Color | Meaning |
|---|---|---|
| High / Critical | `#DC2626` | Hasil tinggi / critical sesuai data instrumen |
| Low / Warning | `#D97706` | Hasil rendah / warning sesuai data instrumen |
| Normal | `#059669` | Normal jika informasi tersedia |

Contoh:

```text
HGB   8.2 g/dL   [L]
WBC   18.4       [H]
PLT   250        [N]
```

Sistem tidak membuat klasifikasi klinis baru apabila informasi tersebut tidak berasal dari instrumen atau konfigurasi yang telah ditentukan.

---

# 6. Typography

## 6.1. Font Family

### UI

Gunakan:

```text
Inter
```

Fallback:

```text
Roboto
Sans-serif
```

Digunakan untuk:

- Navigation.
- Button.
- Label.
- Heading.
- Status.
- Filter.
- Metadata.

### Clinical Data

Gunakan:

```text
Roboto Mono
```

atau:

```text
Fira Code
```

Digunakan terutama untuk:

- Nilai hasil.
- Reference range.
- Kode parameter.
- Timestamp tertentu jika diperlukan.

Tujuannya adalah menjaga alignment angka dan meningkatkan scanability tabel.

---

# 7. Spacing System

Menggunakan basis:

```text
4px
```

Recommended spacing:

```text
4px
8px
12px
16px
24px
32px
```

Untuk data table:

- Cell padding: sekitar `8px`.
- Row height: compact.
- Header table: sedikit lebih tinggi daripada data row.
- Jangan menggunakan padding besar yang mengurangi jumlah data yang dapat terlihat.

---

# 8. Layout Structure

Struktur dashboard utama:

```text
┌───────────────────────────────────────────────────────────────┐
│ LIS Header                                                    │
├───────────────────────────────────────────────────────────────┤
│ Instrument Connection Status                                 │
├───────────────────────────────────────────────────────────────┤
│ Filters / Search                                             │
├───────────────────────────────────────────────────────────────┤
│ Order / Patient Information                                  │
├───────────────────────────────────────────────────────────────┤
│ Test Run Selector                                            │
├───────────────────────────────────────────────────────────────┤
│ Result Table                                                 │
│                                                             │
│ Parameter | Result | Unit | Reference | Flag | Status       │
│                                                             │
├───────────────────────────────────────────────────────────────┤
│ Test Run / SIMRS Actions                                     │
└───────────────────────────────────────────────────────────────┘
```

Dashboard harus memprioritaskan:

```text
Patient
   ↓
Order
   ↓
Test Run
   ↓
Results
   ↓
Workflow Action
```

---

# 9. Instrument Connection Status

## 9.1. Purpose

Menampilkan kondisi komunikasi seluruh instrumen secara persistent.

Contoh:

```text
● BC-5150       Connected
● XN-550        Connected
● BS-200E       Connected
● BX-3010       Connected
● DFI R-300     Connected
● U120          Reconnecting
● ichroma II    Connected
● EasyLyte      Connected
● PRECIL        Disconnected
```

---

## 9.2. Connection States

### Connected

Indicator:

```text
● Connected
```

Warna semantic: hijau.

### Reconnecting

Indicator:

```text
● Reconnecting
```

Warna semantic: orange/amber.

Dapat menggunakan animasi ringan untuk menunjukkan proses reconnect.

### Disconnected

Indicator:

```text
● Disconnected
```

Warna semantic: merah.

Status harus tetap terlihat sampai koneksi kembali atau kondisi ditangani oleh sistem.

---

# 10. Filters & Search

Dashboard harus menyediakan filter yang membantu analis menemukan data dengan cepat.

Minimal:

- Instrument.
- Status order.
- Status delivery.
- Date/time.
- Patient / Nomor RM jika diperlukan.
- Final/non-final Test Run.

Contoh:

```text
[ All Instruments ▼ ]
[ All Status ▼ ]
[ Date ▼ ]
[ Search Patient / RM ]
```

Filter tidak boleh mengubah data database.

---

# 11. Patient & Order Information

Informasi pasien harus ditampilkan secara jelas tetapi tidak mengambil ruang berlebihan.

Minimal informasi:

```text
Patient
Nama Lengkap

No. RM
RM-000123

Tanggal Lahir
01-01-1990

Jenis Kelamin
L
```

Informasi order:

```text
Registration
REG-2026-00123

Order
ORD-000123

Unit
IGD

Doctor
dr. Example

Order Time
08:31
```

Nomor RM merupakan identifier penting untuk pencarian dan historical result.

---

# 12. Test Run / Re-run Selector

## 12.1. Purpose

Komponen digunakan untuk menampilkan seluruh `Test Run` yang berkaitan dengan satu `Order`.

Struktur data:

```text
Order
 ├── Test Run 1
 ├── Test Run 2
 └── Test Run 3
```

---

## 12.2. UI Pattern

Gunakan:

- Segmented control, atau
- Compact tabs.

Contoh:

```text
[ Run 1  10:15 ] [ Run 2  10:20 ] [ Run 3  10:25 ★ FINAL ]
```

---

## 12.3. Active Run

Test Run yang sedang dilihat harus memiliki visual distinction yang jelas.

Contoh:

```text
Run 2
────────────
Active
```

Perubahan tab hanya mengubah data yang ditampilkan.

Tidak ada perubahan terhadap data klinis.

---

## 12.4. Final Run

Test Run yang ditetapkan sebagai final harus memiliki indicator:

```text
★ FINAL
```

atau:

```text
FINAL
```

Status final berasal dari:

```text
test_runs.is_final
```

Untuk satu order hanya boleh terdapat satu final run.

---

# 13. Result Table

## 13.1. Table Structure

Minimal:

| Parameter | Result | Unit | Reference | Flag | Status |
|---|---:|---|---|---|---|

Contoh:

```text
WBC       12.4      10^3/uL      4.0–10.0      H
HGB       13.2      g/dL         12–16
PLT       245       10^3/uL      150–400
```

---

## 13.2. Result Immutability

Result harus dirender sebagai static display.

Tidak ada:

```text
<input value="12.4">
```

untuk nilai klinis.

UI hanya membaca data dari API.

---

## 13.3. Abnormality Highlighting

Abnormal result dapat menggunakan kombinasi:

- Color.
- Flag.
- Icon atau visual marker.

Contoh:

```text
WBC   18.4   [H]
```

Jangan hanya menggunakan warna merah tanpa label `H`, karena pengguna dengan gangguan persepsi warna tetap harus dapat memahami status.

---

# 14. Final Run Action

Button:

```text
Set as Final Run
```

Action hanya tersedia apabila:

- Test Run belum menjadi final.
- User memiliki permission yang sesuai.
- Data Test Run tersedia.

Sebelum perubahan dilakukan, sistem dapat menampilkan confirmation:

```text
Set Run 3 as final?

The current final run, if any, will no longer be marked
as final.

The laboratory values will not be modified.

[Cancel] [Set as Final]
```

Aksi ini hanya mengubah workflow metadata:

```text
is_final
```

Tidak mengubah:

```text
nilai_hasil
satuan
flag_abnormalitas
reference_range_snapshot
```

---

# 15. SIMRS Delivery Indicator

Status delivery ditampilkan pada level `Test Run`.

Database field:

```text
delivery_status
delivered_at
```

---

## 15.1. Pending

Display:

```text
○ Pending
```

Meaning:

> Test Run belum berhasil dikirim ke SIMRS.

---

## 15.2. Sending

Display:

```text
◌ Sending...
```

Meaning:

> Proses pengiriman sedang berlangsung.

---

## 15.3. Delivered

Display:

```text
✓ Delivered
08:45:12
```

Timestamp berasal dari:

```text
delivered_at
```

---

## 15.4. Failed

Display:

```text
✕ Failed
[Retry]
```

Retry dapat menjalankan proses pengiriman kembali tanpa mengubah nilai klinis.

---

# 16. Primary Actions

Primary actions:

```text
Set as Final Run
Sync to SIMRS
```

Karakteristik:

- Jelas.
- Tidak ambigu.
- Tidak menggunakan istilah teknis yang tidak diperlukan pengguna.
- Memiliki confirmation untuk aksi yang mengubah workflow penting.

---

# 17. Button States

Setiap button memiliki minimal:

```text
Default
Hover
Active
Disabled
Loading
```

Contoh:

### Default

```text
[ Set as Final Run ]
```

### Loading

```text
[ ◌ Setting Final... ]
```

### Disabled

```text
[ Set as Final Run ]
```

Disabled state digunakan apabila aksi tidak valid.

---

# 18. Notification & Feedback

Setiap operasi penting harus memberikan feedback.

Contoh success:

```text
✓ Test Run 3 is now the final run.
```

Contoh delivery success:

```text
✓ Result successfully sent to SIMRS.
```

Contoh failure:

```text
✕ Failed to send result to SIMRS.
   Please retry or check the integration status.
```

Error message harus menjelaskan:

1. Apa yang gagal.
2. Apakah data klinis berubah atau tidak.
3. Apa tindakan yang dapat dilakukan pengguna.

---

# 19. Loading States

Hindari blank screen saat data sedang dimuat.

Gunakan:

- Skeleton.
- Spinner.
- Loading indicator pada button.
- Table loading state.

Contoh:

```text
Loading laboratory results...
```

Untuk operasi yang tidak boleh dilakukan bersamaan, button dapat disabled selama proses berlangsung.

---

# 20. Empty States

Jika tidak ada hasil:

```text
No laboratory results found.
```

Jika filter menghasilkan data kosong:

```text
No results match the selected filters.
```

Jika belum ada Test Run:

```text
No Test Run available for this Order.
```

Empty state harus berbeda dari error state.

---

# 21. Error States

Contoh:

```text
Unable to load laboratory results.

[Retry]
```

Untuk masalah koneksi instrumen:

```text
XN-550
Disconnected
Last connection: 08:32
```

Error pada satu instrumen tidak boleh membuat seluruh dashboard menjadi tidak dapat digunakan.

---

# 22. Responsive & Display Considerations

Dashboard terutama ditujukan untuk workstation laboratorium.

Prioritas:

1. Desktop.
2. Large desktop monitor.
3. Laptop workstation.

Mobile layout bukan prioritas MVP.

Untuk layar lebar:

- Gunakan full available width.
- Hindari excessive whitespace.
- Result table dapat menggunakan horizontal scrolling jika memang diperlukan.
- Header table dapat dibuat sticky.

---

# 23. Accessibility

UI harus tetap dapat digunakan ketika pengguna tidak dapat membedakan warna dengan sempurna.

Karena itu:

**Jangan:**

```text
Merah = abnormal
Hijau = normal
```

saja.

Gunakan:

```text
🔴 H
🟠 L
✓ N
```

atau kombinasi icon + label + color.

Interactive element juga harus memiliki:

- Clear focus state.
- Readable label.
- Sufficient contrast.
- Tidak hanya mengandalkan tooltip.

---

# 24. Audit & Data Transparency

UI harus membedakan antara:

### Clinical Data

Contoh:

```text
nilai_hasil
satuan
flag_abnormalitas
reference_range_snapshot
```

Data tersebut bersifat view-only.

### Workflow Metadata

Contoh:

```text
is_final
delivery_status
delivered_at
status_hasil
waktu_validasi
```

Data workflow dapat berubah berdasarkan aksi yang diizinkan.

UI tidak boleh memberikan kesan bahwa perubahan workflow berarti perubahan terhadap hasil klinis.

---

# 25. Information Hierarchy

Prioritas informasi pada halaman hasil:

```text
1. Patient Identity
2. Order
3. Test Run
4. Clinical Results
5. Abnormal Flags
6. Final Status
7. SIMRS Delivery Status
8. Supporting Metadata
```

Informasi dengan prioritas lebih tinggi harus lebih mudah dipindai daripada metadata teknis.

---

# 26. Component Naming Convention

Komponen frontend direkomendasikan menggunakan nama berdasarkan domain:

```text
InstrumentStatusBar
InstrumentStatusItem

OrderSummary
PatientSummary

TestRunSelector
TestRunTab

ResultTable
ResultRow
ResultFlag

FinalRunButton
SimrsDeliveryStatus
SimrsSyncButton

FilterBar
SearchInput

LoadingState
EmptyState
ErrorState
```

Nama komponen harus merepresentasikan fungsi bisnis, bukan hanya bentuk visual.

---

# 27. MVP UI Scope

Komponen yang wajib tersedia pada MVP:

### Dashboard

- Instrument Status Bar.
- Filter Bar.
- Patient/Order Summary.
- Test Run Selector.
- Result Table.
- Final Run Action.
- SIMRS Delivery Status.
- SIMRS Sync Action.

### Supporting States

- Loading.
- Empty.
- Error.
- Success notification.
- Confirmation dialog.

Dark Mode, advanced customization, dan personalization tidak termasuk requirement MVP.

---

# 28. Design System Principles Summary

Design System LIS mengikuti prinsip:

```text
High Contrast
      ↓
Readable Data
      ↓
Compact Layout
      ↓
Fast Monitoring
      ↓
Clear Workflow
      ↓
Immutable Clinical Result
```

Tujuan akhirnya bukan membuat UI yang paling dekoratif, tetapi membuat analis dapat:

```text
SEE
  ↓
UNDERSTAND
  ↓
REVIEW
  ↓
SELECT FINAL
  ↓
SYNC TO SIMRS
```

dengan cepat dan tanpa risiko salah memahami atau mengubah nilai klinis.

---

# 29. Final Design Principle

> **The LIS interface must make clinical data easy to read, workflow actions easy to understand, and clinical values impossible to accidentally modify.**

Design System ini menjadi acuan implementasi UI React/TypeScript dan harus konsisten dengan:

```text
01_PROJECT_BRIEF.md
        ↓
02_PRD.md
        ↓
03_SYSTEM_DESIGN.md
        ↓
04_DATABASE_DESIGN.md
        ↓
05_DESIGN_SYSTEM.md
```

Perubahan terhadap struktur data atau workflow harus terlebih dahulu diselaraskan dengan dokumen arsitektur dan database sebelum diterapkan pada UI.