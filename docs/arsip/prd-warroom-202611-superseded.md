# PRD — War Room Overhaul (v2026.11)

Dokumen ini mendahului desain teknis. ERD ada di `erd-warroom-202611.md`.
Rencana fase ada di `overhaul-plan-202611.md` dan tidak diulang di sini.

---

## 1. Masalah yang diselesaikan

War Room saat ini tumbuh dari kebutuhan yang berbeda-beda, sehingga:

1. **Satu mesin memikul empat peran.** Webdock 2 vCPU menjalankan UI, API, database,
   pengumpulan data, dan dua terminal MT5 sekaligus.
2. **Tidak ada halaman yang menjawab "ini kenapa kosong?"** Kalau dashboard diam, tidak
   ada cara membedakan "tidak ada sinyal" dari "collector mati sejak 3 jam lalu".
3. **Angka tersebar.** PnL dihitung di beberapa tempat (EA, API, frontend, skrip cron),
   jadi angkanya bisa berbeda untuk hal yang sama.
4. **Market tidak setara.** Forex punya status EA, crypto punya engine paper, Polymarket
   dan IDX menempel sebagai halaman tanpa pola yang sama.
5. **Tidak ada jejak.** Tabel `audit` kosong padahal ada akun live dengan uang nyata.

## 2. Tujuan produk

| # | Tujuan | Ukuran keberhasilan |
|---|---|---|
| T1 | Satu layar menjawab "hari ini bagaimana" untuk semua market | Home + halaman market memuat equity, PnL hari ini, posisi, freshness di viewport HP tanpa scroll horizontal |
| T2 | Penyebab data kosong selalu bisa dijawab dari UI | 100% halaman data punya indikator freshness + tautan ke `/sumber-data` |
| T3 | Satu sumber kebenaran angka | PnL & biaya dihitung di satu modul; nol perhitungan PnL di frontend |
| T4 | Beban data keluar dari mesin trading | Webdock tidak menjalankan collector; CPU rata-rata < 40% |
| T5 | Setiap aksi yang menyentuh uang/parameter tercatat | 100% aksi tulis menghasilkan baris di `audit_log` |

### Bukan tujuan (out of scope)
- Menambah market baru sebelum P1 selesai.
- Mengaktifkan strategi yang belum lolos uji (mis. SMC Gold v3.08).
- Auto-trading oleh AI tanpa konfirmasi manusia.
- Aplikasi mobile native (web responsif sudah cukup).

## 3. Pengguna & peran

| Peran | Yang dia lakukan | Yang tidak boleh |
|---|---|---|
| **Operator** (pemilik) | lihat semua, arm/confirm, ubah batas risiko, restart service | melihat plaintext kredensial setelah disimpan |
| **Peneliti** | jalankan riset, ajukan proposal parameter, baca dataset | mengubah parameter langsung |
| **Penonton** (opsional, publik) | lihat halaman read-only: leaderboard, kurs, ringkasan market | melihat akun, posisi, PnL, jurnal |

Aturan: halaman publik **tidak** boleh memuat data akun, nomor login, saldo, atau jurnal.

## 4. Prinsip produk

1. **Read-only by default.** Semua halaman market hanya membaca. Aksi tulis wajib lewat
   `Arm → Confirm` dan menghasilkan audit.
2. **Freshness terlihat.** Data lebih tua dari SLA ditampilkan kuning (warning) atau merah
   (stale) — bukan angka lama yang terlihat normal.
3. **Satu mesin hitung.** PnL, fee, swap, funding dihitung sekali di `packages/core`.
4. **Market setara.** Semua market memakai pola halaman yang sama: Ringkasan → Posisi →
   Sinyal → Jurnal → Riset → Pengaturan.
5. **Data di luar, kontrol di dalam.** Collector, backtest, ML di host lain; webdock
   menyimpan ringkasan dan menyajikan.
6. **Bisa dipulihkan.** Setiap angka bisa ditelusuri ke deal/tick asal; backup harian teruji.

## 5. Kebutuhan per market

Pola wajib tiap market: **Ringkasan, Posisi, Sinyal, Jurnal, Riset, Pengaturan.**

### 5.1 FOREX (MT5 — live `452009427`, demo `464202979`)

| Kebutuhan | User story | Kriteria terima |
|---|---|---|
| Ringkasan akun | Sebagai operator, saya ingin melihat equity live & demo berdampingan | Dua kartu akun: equity, PnL hari ini, posisi terbuka, umur data < 15 s |
| Status EA | Saya ingin tahu EA mana yang jalan, versi, magic, dan kapan terakhir kirim data | Tabel per EA: loaded, versi, magic, simbol, heartbeat, tombol "buka `/operasi`" |
| Sinyal & alasan | Saya ingin tahu kenapa EA tidak entry | Daftar evaluasi terakhir: alasan (`DI_LUAR_SESI`, `SPREAD_TINGGI`, `RR_KURANG`), nilai ATR/RSI/spread |
| Posisi | Saya ingin melihat jarak ke SL/TP dan R berjalan | Per posisi: entry, SL, TP, jarak SL (poin), R berjalan, umur posisi |
| Jurnal | Saya ingin riwayat deal per akun & magic | Filter akun/magic/tanggal; kolom PnL, R, durasi |
| Pengaturan | Saya ingin tahu preset yang aktif | Menampilkan preset aktif; perubahan lewat proposal, bukan edit langsung |

### 5.2 CRYPTO (paper engine + akun OKX)

| Kebutuhan | User story | Kriteria terima |
|---|---|---|
| Ringkasan | Saya ingin lihat bias pasar dan hasil hari ini | Kartu: equity paper vs OKX, sinyal hari ini, trade terbuka, freshness < 30 s |
| Sinyal | Saya ingin lihat koin yang lolos/tidak dan alasannya | Tabel 20 koin: bias, RR, gate (approve/reject), alasan |
| Posisi | Saya ingin lihat TP1/TP2 dan status BE | Per posisi: qty, entry, TP1, TP2, BE aktif/tidak, R |
| On-chain | Saya ingin pantau token baru tanpa keluar dashboard | Daftar token + likuiditas/holder/umur; label risiko jelas |
| Jurnal | Saya ingin bandingkan paper vs live | Dua kolom; selisih slippage & fee ditampilkan |

### 5.3 POLYMARKET

| Kebutuhan | Kriteria terima |
|---|---|
| Daftar pasar + odds | Pasar aktif dengan harga ya/tidak dan perubahan 24 jam |
| Posisi & exposure | Exposure per event, potensi payout, tanggal settlement |
| Jurnal | Settlement tercatat, PnL dihitung oleh mesin yang sama |

### 5.4 IDX (saham Indonesia)

| Kebutuhan | Kriteria terima |
|---|---|
| Ringkasan | IHSG + watchlist, perubahan harian, freshness ≤ 15 menit |
| Per emiten | Harga, volume, fundamental ringkas, sinyal terakhir |
| Sinyal & jurnal | Sama polanya dengan market lain |

### 5.5 GMGN / on-chain memecoin

| Kebutuhan | Kriteria terima |
|---|---|
| Feed token | Token baru + likuiditas + holder, umur data < 60 s |
| Detail token | Harga, likuiditas, top holder, risiko (LP lock/burn) |
| Peringatan | Setiap halaman memberi label "risiko tinggi" dan tidak menampilkan tombol beli |

## 6. Kebutuhan halaman non-market

| Halaman | Kebutuhan minimum | Kriteria terima |
|---|---|---|
| `/` Home | Kartu per market + status sistem | Satu layar: 5 kartu market + banner hijau/kuning/merah |
| `/akun` | Daftar koneksi: broker, exchange, wallet, prediksi | Status per koneksi (OK/expired/error + umur), tombol rotasi kredensial |
| `/risiko` | Batas global & per market | Tabel batas aktif; perubahan wajib konfirmasi + audit |
| `/jurnal` | Jurnal lintas market | Filter market/tanggal/tag; bisa diekspor CSV |
| `/ledger` | PnL, fee, swap, funding, transfer | Saldo awal + mutasi = saldo akhir, selisih 0,00 |
| `/sumber-data` | Registry feed + freshness | Tiap feed: pemilik host, SLA, umur data sekarang, error terakhir |
| `/operasi` | Service, job, MT5, bridge, disk | Status + aksi restart dengan konfirmasi, hasil aksi tampil |
| `/bukti` | Audit trail | Filter aktor/aksi/waktu; menampilkan before/after |
| `/riset` | Hypothesis → run → verdict → proposal | Satu alur terlihat utuh, tidak terpotong di beberapa halaman |
| `/sistem` | User, peran, retensi, token | Perubahan peran & retensi tercatat di audit |
| `/vault`, `/masuk` | Kredensial & auth | Tidak ada plaintext kredensial di UI/log |
| `/bantuan`, `/cara-kerja`, `/info` | Dokumentasi & status publik | Tidak memuat data akun |

**Aturan navigasi:** setiap halaman market wajib menautkan `/sumber-data` (kalau angka
mencurigakan) dan `/operasi` (kalau data berhenti).

## 7. Kebutuhan data

- Setiap sumber data terdaftar di `data_sources` dengan: kode, market, provider, host pemilik,
  endpoint, SLA detik, status, `last_ok_at`, `last_error`.
- Data yang melewati SLA ditandai `stale` di API (bukan di frontend saja).
- Collector **tidak boleh** berjalan di webdock, kecuali yang butuh sesi lokal
  (Telethon) dan bridge MT5.
- Tick mentah tidak masuk Postgres webdock; disimpan di R2 atau host collector.
- Retensi: `facts` (staging) 30 hari, `events` 180 hari, `candles` 2 tahun, `trades`/`ledger`
  permanen.

## 8. Kebutuhan tata kelola parameter

Alur wajib (sudah ada di skema, harus dipakai):

```
hypothesis → research_run → verdict → proposal → (approve) → parameter baru → audit
```

- Tidak ada perubahan parameter yang boleh sampai ke EA tanpa `proposal` berstatus approved.
- Proposal wajib membawa bukti (`evidence_json`) dan verdict gate.
- Parameter yang `locked=true` tidak bisa diubah lewat UI, hanya lewat migrasi.

## 9. Non-fungsional

| Aspek | Target |
|---|---|
| Performa | P95 render halaman market < 1,5 s di 4G; API P95 < 400 ms |
| Beban | CPU webdock rata-rata < 40%; tidak ada collector di webdock |
| Keamanan | Session cookie HttpOnly; token EA rotatable; kredensial hanya di vault |
| Audit | Semua aksi tulis tercatat; retensi audit ≥ 2 tahun |
| Backup | Postgres harian ke R2, RPO 24 jam, RTO 2 jam, restore diuji tiap kuartal |
| Observability | Tiap job punya heartbeat; tidak ada job tanpa alert saat mati |
| Aksesibilitas | Kontras AA, navigasi keyboard, angka terbaca di layar 360 px |

## 10. Metrik keberhasilan

**Produk:** waktu menjawab "kenapa tidak ada trade hari ini" < 30 detik (sekarang: cek SSH).
**Teknis:** jumlah insiden "dashboard basi" per minggu = 0 tanpa terdeteksi di `/operasi`.
**Tata kelola:** 100% perubahan parameter punya proposal + verdict.

## 11. Pertanyaan terbuka (butuh keputusan pemilik)

1. **Akses publik:** halaman mana yang boleh dilihat tanpa login? (usul: leaderboard, kurs,
   ringkasan market — tanpa akun/PnL.)
2. **Retensi tick:** 2 tahun candle cukup, atau butuh tick untuk riset?
3. **Akun live:** tetap pakai master password atau pindah ke investor password
   (read-only) sampai EA terbukti stabil?
4. **Azure VM:** dipakai untuk backtest/ML, atau dimatikan saja?
5. **Instabox:** di-appeal atau ditinggalkan (sandbox pindah ke VM sendiri)?
