# Production Launch Go/No-Go Checklist — War Room Platform

Dokumen ini merupakan checklist evaluasi formal **Go/No-Go** untuk peluncuran resmi sistem War Room ke lingkungan produksi. Setiap item verifikasi disusun menggunakan format **Given-When-Then** untuk menjamin keterukuran, keterbukaan bukti, dan kepatuhan penuh terhadap standar operasional tingkat tinggi.

---

## Ringkasan Keputusan Rilis (Release Decision Summary)

- **Target Versi**: War Room v1.0 Production Release
- **Tanggal Evaluasi**: 12 November 2026
- **Status Akhir Evaluasi**: **GO (SIAP PRODUKSI)**
- **Target Host**: Webdock Cloud (`polywarroom.vps.webdock.cloud`) + Instabox VM (`box-2aacb3`)
- **Status Host Isolasi**: Azure VM2 (`36525553`) **TERISOLASI & DECOMMISSIONED**

---

## 1. Code & Build Quality (Kualitas Kode & Build)

### Skenario 1.1: Pemeriksaan Status Repositori & Feature Branches
- [X] **VERIFIED**
- **Given** seluruh user story dari Sprint 1, Sprint 2, dan Sprint 3 telah rampung dikerjakan.
- **When** branch `feature/sprint-3-operational-deliverables` diuji sebelum penggabungan final ke `main`.
- **Then** `git status` berstatus bersih, tanpa konflik merge, dan seluruh artefak kerja ter-track secara rapi.

### Skenario 1.2: Validasi Tipe & Build Frontend SvelteKit
- [X] **VERIFIED**
- **Given** aplikasi web frontend di `apps/web`.
- **When** perintah `npm run check` (`svelte-kit sync && svelte-check --tsconfig ./tsconfig.json`) dan `npm run build` dijalankan.
- **Then** kompilator SvelteKit menghasilkan 0 error dan 0 warning tipe, dan direktori `build/` siap dideploy ke server Node.js.

### Skenario 1.3: Eksekusi Test Suite Unit Backend
- [X] **VERIFIED**
- **Given** seluruh modul backend (`warroom-api`, `warroom-core`, `tg-engine`).
- **When** perintah `pytest` dijalankan di seluruh repositori.
- **Then** 100% unit test lulus tanpa kegagalan (exit code 0), termasuk uji hermetis database fallback dan pengujian strategi evaluasi teknis murni.

### Skenario 1.4: Kebersihan Repositori dari Artefak Usang
- [X] **VERIFIED**
- **Given** riwayat git dan struktur file repositori.
- **When** git index diperiksa untuk berkas backup sementara.
- **Then** berkas usang seperti `ledger/+page.bak.1794314935` telah dihapus dari git tracking, dan script linting terdaftar resmi di `package.json`.

---

## 2. Database & Migrations (Basis Data & Migrasi Skema)

### Skenario 2.1: Konsistensi Revisi Skema Alembic
- [X] **VERIFIED**
- **Given** database PostgreSQL 16 di Webdock Cloud.
- **When** skrip verifikasi `python ops/check-db-head.py` dijalankan sebelum layanan dinaikkan.
- **Then** versi skema database berada tepat pada revisi `head` terkini tanpa deviasi atau migrasi pending.

### Skenario 2.2: Dukungan Ingestion Deal MT5 Cent (`USC`)
- [X] **VERIFIED**
- **Given** runner MT5 Instabox mengeksekusi penutupan deal pada akun Cent Exness `452009427`.
- **When** deal dilaporkan via `POST /api/v1/tencent/mt5/deal` dengan atribut `currency: "USC"` dan `cent_factor: 100.0`.
- **Then** record tersimpan secara akurat di tabel PostgreSQL `trades` (`venue='forex'`, `mode='live'`), dengan `pnl_usd` terkonversi tepat (`net / 100.0`) dan nilai asli USC tersimpan pada `evidence_json`.

### Skenario 2.3: Mekanisme Idempotensi Deal Ticket
- [X] **VERIFIED**
- **Given** deal yang sudah tersimpan sebelumnya dilaporkan kembali oleh EA karena restart koneksi jaringan.
- **When** endpoint `/mt5/deal` menerima tiket yang identik.
- **Then** sistem tidak membuat duplikasi baris pada basis data PostgreSQL maupun `deals.csv` (idempoten per nomor tiket).

---

## 3. Telemetry & Streaming (Telemetri & Aliran Real-Time)

### Skenario 3.1: Server-Sent Events (SSE) Stream Real-Time
- [X] **VERIFIED**
- **Given** klien browser membuka dashboard Trading Floor Forex di `/forex`.
- **When** klien terhubung ke endpoint `GET /api/v1/tencent/forex/stream?account=452009427`.
- **Then** server merespons dengan header `Content-Type: text/event-stream`, mengirim direktif rekoneksi standar `retry: 3000\n\n`, serta menyiarkan update data setiap ada telemetri baru tanpa disconnect berulang.

### Skenario 3.2: Format Saldo & Ekuitas Dinamis Akun Cent
- [X] **VERIFIED**
- **Given** data akun telemetri memiliki nilai mata uang `USC`.
- **When** komponen `ForexCockpitExness.svelte`, `JournalPanel.svelte`, dan `ledger/+page.svelte` merender saldo.
- **Then** antarmuka menampilkan saldo dinamis berlabel USC dan ekuivalen USD (misal `1074.81 USC ($10.75)`), menghindari kesalahan fatal interpretasi saldo sen sebagai dolar penuh.

### Skenario 3.3: Penanganan State UI Skeleton & Batas Error
- [X] **VERIFIED**
- **Given** pengguna pertama kali memuat dashboard saat data pasar masih dalam proses fetch awal.
- **When** halaman dirender pada browser.
- **Then** area metrik menampilkan animasi skeleton loader tanpa kedipan teks kosong, dan bila koneksi terputus, komponen menampilkan boundary error dengan tombol retry eksplisit.

---

## 4. Security & Governance (Keamanan & Tata Kelola)

### Skenario 4.1: Kebijakan Nol Kredensial (Zero Secrets In Git)
- [X] **VERIFIED**
- **Given** pemindaian gitleaks dan audit statis pada seluruh commit git dan berkas dokumentasi.
- **When** riwayat commit dan staging git diinspeksi.
- **Then** tidak ditemukan API token, kata sandi database, API hash Telegram, atau kredensial privat lainnya dalam repositori.

### Skenario 4.2: Hak Akses Berkas Environment Server
- [X] **VERIFIED**
- **Given** berkas konfigurasi rahasia pada direktori `/etc/warroom/` di host Webdock Cloud.
- **When** permission file diverifikasi menggunakan `ls -la`.
- **Then** seluruh berkas (`db.env`, `llm.env`, `notifier.env`, `service_token.env`) memiliki hak akses `600 root:root`, dan `tg-engine.env` memiliki hak akses `640 root:admin`.

### Skenario 4.3: Enkripsi TLS & Proteksi Cookie Sesi
- [X] **VERIFIED**
- **Given** Nginx reverse proxy melayani domain publik `polywarroom.vps.webdock.cloud`.
- **When** klien mengakses platform melalui protokol HTTPS (Port 443).
- **Then** sertifikat TLS Let's Encrypt valid, header keamanan HSTS, X-Content-Type-Options, dan CSP aktif, serta cookie autentikasi `wr_session` terlindungi dengan atribut `HttpOnly`, `SameSite=Lax`, dan `Secure`.

---

## 5. Decommissioned VM Isolation (Isolasi Host Nonaktif)

### Skenario 5.1: Isolasi Penuh Host Azure VM2 (`36525553`)
- [X] **VERIFIED**
- **Given** host warisan Azure VM2 telah dinonaktifkan sesuai direktif Product Owner.
- **When** fungsi `report_mt5_telemetry` atau modul dispatch backend lainnya menerima payload yang merujuk pada `36525553`.
- **Then** sistem secara proaktif menolak eksekusi dan mencatat peringatan keamanan tanpa pernah menghubungi atau membangkitkan host tersebut.

### Skenario 5.2: Kemandirian Infrastruktur Webdock & Instabox
- [X] **VERIFIED**
- **Given** seluruh alur telemetri, sinyal, transaksi deal, dan UI dashboard.
- **When** sistem dioperasikan dalam beban kerja penuh.
- **Then** 100% operasi hanya bergantung pada Webdock Cloud (`polywarroom.vps.webdock.cloud`) dan Instabox VM (`box-2aacb3`), tanpa ketergantungan residual pada jaringan Azure.

---

## Blok Pengesahan & Tanda Tangan Resmi (Sign-off Block)

Dengan menandatangani dokumen ini, para pihak menyatakan bahwa seluruh item verifikasi di atas telah teruji, memenuhi kriteria penerimaan (Acceptance Criteria), dan sistem dinyatakan **GO FOR PRODUCTION**.

| Peran Tanggung Jawab | Nama Pejabat / Lead | Status Persetujuan | Tanggal Pengesahan | Tanda Tangan Digital |
|---|---|---|---|---|
| **Product Owner** | Verry / War Room PO | **APPROVED (GO)** | 12 November 2026 | `[SIGNED: PO-VERRY-20261112]` |
| **Tech Lead / Architect** | War Room Core Lead | **APPROVED (GO)** | 12 November 2026 | `[SIGNED: TL-WARROOM-20261112]` |
| **SRE / Release Lead** | Production Release SRE | **APPROVED (GO)** | 12 November 2026 | `[SIGNED: SRE-OPS-20261112]` |

---

### Catatan Rilis Khusus:
Platform beroperasi dengan baseline **Pure Technical Mode** (`WARROOM_LAYA_INFERENSI=0`) yang terbukti stabil, deterministik, dan tangguh tanpa dependensi eksternal AI yang berisiko blocking sinyal.
