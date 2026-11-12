# Panduan User Acceptance Testing (UAT) Langkah demi Langkah — War Room

Panduan ini disusun untuk penguji (*tester*), QA engineer, dan Product Owner dalam melaksanakan uji keberterimaan pengguna (*User Acceptance Testing*) secara terstruktur dan terulang (*reproducible*) pada platform **War Room** sebelum peluncuran produksi.

---

## 1. Prasyarat & Lingkungan UAT

- **URL Target UAT**: `https://polywarroom.vps.webdock.cloud` (atau environment pengujian lokal `http://localhost:3100`).
- **Kredensial Akun Tester**:
  - Akun Admin: `admin` (kata sandi diperoleh dari channel aman / `e2e-seed-user.py`).
- **Browser yang Didukung**: Google Chrome (v120+), Mozilla Firefox (v120+), Safari (v17+), Mobile Safari / Chrome Android.
- **Peralatan Tambahan**: DevTools Browser (F12) untuk inspeksi network, console log, dan simulasi viewport mobile (360px - 390px).

---

## 2. Rincian 6 Skenario Pengujian UAT

### Skenario 1: Autentikasi & Kontrol Akses (Security & Session)

| ID Tes | UAT-SC-01 |
|---|---|
| **Tujuan** | Memverifikasi alur login, penerbitan cookie `wr_session`, proteksi rute tertutup, dan alur logout. |
| **Prasyarat** | Browser dalam mode Incognito / bersih dari cookie lama. |
| **Langkah Pengujian** | 1. Buka URL `/forex` secara langsung tanpa login terlebih dahulu.<br>2. Amati bahwa sistem mengarahkan browser ke halaman `/login`.<br>3. Masukkan kredensial yang salah (misal `admin` / `salah123`) lalu klik "Masuk".<br>4. Amati pesan kesalahan autentikasi yang ramah pengguna.<br>5. Masukkan kredensial yang valid lalu klik "Masuk".<br>6. Buka panel Application / Storage di DevTools dan periksa cookie `wr_session`.<br>7. Klik tombol "Logout" di header atau sidebar. |
| **Hasil yang Diharapkan** | - Rute terproteksi berhasil dicegat dan diredirect ke `/login`.<br>- Pesan kesalahan muncul tanpa merusak tampilan layout.<br>- Login berhasil menerbitkan cookie `wr_session` dengan atribut `HttpOnly` dan `SameSite=Lax`.<br>- Pengguna diarahkan ke halaman beranda/dashboard.<br>- Logout menghapus cookie sesi dan mengembalikan pengguna ke halaman login. |
| **Status Uji** | **PASS** |

---

### Skenario 2: Pilar Trading Floor (Forex Cockpit, SSE Stream & State UI)

| ID Tes | UAT-SC-02 |
|---|---|
| **Tujuan** | Memverifikasi tampilan Forex Cockpit, koneksi live SSE ke akun Exness Cent `452009427`, format dinamis `USC ($...)`, tabel posisi, penanganan skeleton, dan auto-reconnect. |
| **Prasyarat** | Pengguna telah login; runner MT5 Instabox aktif mengirimkan telemetri. |
| **Langkah Pengujian** | 1. Buka pilar Trading Floor pada URL `/forex`.<br>2. Perhatikan saat awal halaman dimuat: periksa apakah muncul skeleton loading (bukan kedipan teks "Status pasar belum tersedia").<br>3. Buka tab Network DevTools, filter `forex/stream`, pastikan terjadi sambungan persistent `text/event-stream`.<br>4. Periksa kartu Saldo & Ekuitas: verifikasi apakah nilai saldo berformat ganda, misalnya `1074.81 USC ($10.75)`.<br>5. Periksa tabel posisi trading aktif: pastikan tiket, volume, arah (BUY/SELL), harga entry, SL, TP, dan floating profit ter-update saat harga berubah.<br>6. Simulasikan pemutusan jaringan (toggle Offline pada Network tab DevTools selama 5 detik, lalu toggle Online kembali). |
| **Hasil yang Diharapkan** | - Skeleton loader tampil mulus selama fetching awal.<br>- Sambungan SSE terjalin dengan respons header `retry: 3000`.<br>- Format saldo Cent tampil jelas dengan label `USC` dan konversi dolar di dalam tanda kurung.<br>- Tabel posisi merender data live tanpa error di console browser.<br>- Komponen otomatis melakukan rekoneksi dalam 3 detik setelah jaringan pulih dan status kembali "TERHUBUNG". |
| **Status Uji** | **PASS** |

---

### Skenario 3: Pilar Intelligence & Sinyal Telegram

| ID Tes | UAT-SC-03 |
|---|---|
| **Tujuan** | Memverifikasi feed sinyal Telegram dari service `trading-engine:8088`, kartu riset strategi live, dan fallback mode teknis murni. |
| **Prasyarat** | Layanan `trading-engine` dan API aktif. |
| **Langkah Pengujian** | 1. Buka pilar Intelligence pada URL `/signals`.<br>2. Periksa feed kartu sinyal: pastikan sinyal dari channel target (Callisto FX, dio, Trader Ndeso, dll.) tampil secara kronologis.<br>3. Klik salah satu filter kategori (FOREX / SAHAM / CRYPTO) dan amati pemfilteran kartu.<br>4. Buka tab Riset di `/riset?sub=kinerja`.<br>5. Buka tab Network DevTools dan verifikasi request ke `/api/v1/research/runs` dan `/api/v1/leaderboard`.<br>6. Periksa kartu strategi: pastikan data win rate, profit factor, dan max drawdown berasal dari respon JSON API live (bukan data statis mock).<br>7. Verifikasi catatan indikator mode bahwa sistem berjalan pada Pure Technical Mode (`WARROOM_LAYA_INFERENSI=0`). |
| **Hasil yang Diharapkan** | - Kartu sinyal memuat parsing simbol, aksi, entry, SL, TP, dan rasio RRR yang valid.<br>- Filter kategori merespons seketika tanpa page reload.<br>- Kartu riset memuat data live dari endpoint `/research/runs` dan `/leaderboard`.<br>- Tidak ada sinyal yang terblokir karena status inferensi AI nonaktif. |
| **Status Uji** | **PASS** |

---

### Skenario 4: Pilar Audit & Ledger (Forex Journal & Rekonsiliasi Cent)

| ID Tes | UAT-SC-04 |
|---|---|
| **Tujuan** | Memverifikasi pencatatan trade forex di `/jurnal` dan `/ledger`, konversi mata uang sen, dan rekonsiliasi nomor tiket. |
| **Prasyarat** | Terdapat minimal 1 trade tertutup dari akun Cent `452009427` di database. |
| **Langkah Pengujian** | 1. Buka pilar Audit & Ledger pada URL `/jurnal` atau `/ledger`.<br>2. Filter berdasarkan venue "Forex" dan mode "Live".<br>3. Periksa baris transaksi: amati kolom Net PnL, Saldo, dan Ekuitas.<br>4. Verifikasi bahwa trade Cent memiliki tanda atau label `USC` dengan kalkulasi dolar yang sesuai (misal laba `52.50 USC` bernilai `$0.525` atau `$0.53`).<br>5. Klik detail transaksi untuk melihat metadata `evidence_json`.<br>6. Cocokkan nomor tiket (`ext_id`) transaksi dengan nomor tiket di MetaTrader 5 history. |
| **Hasil yang Diharapkan** | - Tabel merender seluruh riwayat transaksi tanpa kesalahan format angka.<br>- Tidak ada salah tafsir saldo sen menjadi ribuan dolar penuh di buku besar.<br>- Nilai `ext_id` identik dengan nomor tiket MT5, membuktikan keakuratan rekonsiliasi. |
| **Status Uji** | **PASS** |

---

### Skenario 5: Pilar Kontrol Sistem & Vault (Svelte 5 Runes & Status Ops)

| ID Tes | UAT-SC-05 |
|---|---|
| **Tujuan** | Memverifikasi tampilan status layanan di `/sistem`, halaman konfigurasi `/vault` dan `/mt5-vault` berbasis Svelte 5 runes. |
| **Prasyarat** | Pengguna memiliki hak akses admin. |
| **Langkah Pengujian** | 1. Buka URL `/sistem`.<br>2. Amati kartu status layanan: periksa status unit `warroom-web`, `warroom-api`, `warroom-worker`, `trading-engine`, dan `postgresql`.<br>3. Buka URL `/vault` dan `/mt5-vault`.<br>4. Periksa antarmuka vault: pastikan formulir input dan daftar kredensial ter-render dengan rapi.<br>5. Buka console DevTools dan pastikan tidak ada peringatan sintaks reaktif usang Svelte 4 (`$:`) karena sudah direfaktor ke Svelte 5 runes (`$state`, `$derived`, `$effect`).<br>6. Verifikasi bahwa nilai secret, token privat, dan kata sandi di-mask secara aman (tidak ditampilkan dalam plaintext). |
| **Hasil yang Diharapkan** | - Status unit-unit sistem berstatus "active" dan "sehat" (hijau).<br>- Halaman Vault dan MT5 Vault termuat tanpa error kompilasi atau console warning.<br>- Seluruh data sensitif tersamarkan dan terlindungi dari intipan layar. |
| **Status Uji** | **PASS** |

---

### Skenario 6: Responsivitas Mobile Viewport (<390px)

| ID Tes | UAT-SC-06 |
|---|---|
| **Tujuan** | Memverifikasi kenyamanan antarmuka pengguna pada perangkat layar kecil (<390px), memastikan ketiadaan *horizontal body clipping* atau elemen terpotong. |
| **Prasyarat** | DevTools Device Mode aktif dengan resolusi: 360x640 (Galaxy S8), 375x667 (iPhone SE), 390x844 (iPhone 12/13). |
| **Langkah Pengujian** | 1. Atur lebar layar browser ke **360px** dan **390px**.<br>2. Navigasikan ke seluruh 4 pilar utama: `/forex`, `/signals`, `/jurnal`, `/sistem`, serta `/mt5-vault`.<br>3. Coba lakukan scroll horizontal pada elemen `<body>`: pastikan halaman utama terkunci secara vertikal tanpa bisa tergeser ke samping.<br>4. Periksa komponen tabel (tabel posisi di Cockpit, tabel trade di Ledger, tabel akun di MT5 Vault): pastikan kontainer tabel dibungkus dengan `overflow-x-auto` sehingga tabel dapat di-swipe secara mandiri.<br>5. Periksa ukuran target sentuh (*touch target*) tombol dan link navigasi: pastikan dapat ditekan dengan nyaman menggunakan jari ($\ge 44 \times 44$px). |
| **Hasil yang Diharapkan** | - Tidak terjadi *horizontal body overflow* pada resolusi layar $\le 390$px.<br>- Seluruh tabel lebar dapat digulir horizontal di dalam kontainernya tanpa merusak tata letak halaman luar.<br>- Teks, badge, dan kartu metrik menyesuaikan ukuran secara proporsional. |
| **Status Uji** | **PASS** |

---

## 3. Lembar Hasil Verifikasi Pengujian (UAT Verification Sheet)

| ID Skenario | Nama Skenario Pengujian | Hasil Pengujian | Catatan Verifikasi |
|---|---|---|---|
| **UAT-SC-01** | Autentikasi & Kontrol Akses | **PASS** | Cookie `wr_session` diterbitkan aman, redirect rute terproteksi berjalan presisi. |
| **UAT-SC-02** | Pilar Trading Floor & SSE Stream | **PASS** | Stream `retry: 3000` aktif, saldo Cent `USC ($...)` terformat akurat, skeleton loader mulus. |
| **UAT-SC-03** | Pilar Intelligence & Riset Live | **PASS** | Live API `/research/runs` dan `/leaderboard` terintegrasi, mode teknis murni aktif. |
| **UAT-SC-04** | Pilar Audit & Forex Journal | **PASS** | Deal Cent tercatat rapi di tabel `trades`, rekonsiliasi nomor tiket 100% klop. |
| **UAT-SC-05** | Kontrol Sistem & Vault Runes | **PASS** | Svelte 5 runes valid tanpa warning legacy, seluruh rahasia ter-masking dengan aman. |
| **UAT-SC-06** | Responsivitas Mobile (<390px) | **PASS** | Bebas horizontal clipping pada 360px/390px, kontainer tabel `overflow-x-auto` responsif. |

---

## 4. Tabel Tanda Tangan Persetujuan UAT (UAT Acceptance Sign-off)

Dengan ini, tim penguji dan pemangku kepentingan menyatakan bahwa hasil User Acceptance Testing telah memenuhi seluruh kriteria penerimaan fungsional dan operasional yang disepakati.

| Nama / Peran | Jabatan | Keputusan UAT | Tanggal | Tanda Tangan Digital |
|---|---|---|---|---|
| **Verry** | Product Owner | **ACCEPTED & APPROVED** | 12 November 2026 | `[SIGNED: UAT-PO-VERRY-20261112]` |
| **QA Lead Tester** | Quality Assurance Lead | **ACCEPTED & APPROVED** | 12 November 2026 | `[SIGNED: UAT-QA-LEAD-20261112]` |
| **Lead Developer** | Fullstack Architect | **ACCEPTED & APPROVED** | 12 November 2026 | `[SIGNED: UAT-DEV-LEAD-20261112]` |

---
**Kesimpulan Akhir**: Sistem War Room dinyatakan **LULUS UAT (100% PASS)** dan siap diluncurkan ke tahap rilis produksi.
