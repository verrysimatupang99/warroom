# Telemetri multi-akun MT5 — 31 Okt 2026

**Masalah.** Satu akun MT5 = satu terminal. Sebelum perubahan, `latest_mt5_telemetry`
adalah satu variabel global dan snapshot disimpan dengan key `ringkas`. Akun cent HSFX
yang mengirim ke endpoint yang sama akan **menimpa** status akun demo Reaper di UI.

**Keputusan.** Pisahkan state dan fakta per nomor akun, tanpa mengubah jalur akun utama.

## Perubahan

| Lapisan | Perubahan |
|---|---|
| API `POST /mt5/telemetry` | `latest_mt5_by_account[account]`; akun utama tetap menjadi `latest_mt5_telemetry` untuk kompatibilitas. Snapshot disimpan `key=ringkas` (akun utama) atau `ringkas:<account>`. |
| Fakta | `mt5_snapshot` per akun; kurva/scanlog akun utama tetap memakai `ringkas`. |
| API baru | `GET /mt5/accounts` (daftar + `primary`), `GET /mt5/status?account=` (default utama), `GET /journal/performance?market=forex&account=`. |
| Deal | `MT5DealPayload.account` dan kolom `account` di `deals.csv`; deal lama tanpa akun dipetakan ke akun utama di UI. |
| UI | Panel **Akun MT5** di `/forex?sub=ringkas`: kartu akun, detail posisi, kurva ekuitas per akun, deal tertutup per akun. |
| Bridge | `ops/mt5/WarRoom_TelemetryBridge.mq5` + `ops/mt5/README.md`; telemetri-saja, normalisasi akun cent (`USC`/`EUC` ÷ 100). |

Akun utama = `416510164` (`WARROOM_MT5_PRIMARY_ACCOUNT`), tetap default semua endpoint
lama. Akun lain tidak pernah menjadi default.

## Bukti

- Tes: `services/api/tests/test_api.py` **28 passed**, termasuk
  `test_telemetri_multi_akun_tidak_saling_menimpa` (akun kedua tidak mengganti
  `latest_mt5_telemetry`; endpoint akun/status memisahkan nilai).
- `services/api/tests/test_jurnal_lokal.py` **20 passed**, termasuk
  `test_performance_meneruskan_akun_mt5`.
- Web: vitest **74 passed** (17 berkas), termasuk 2 tes `AkunMT5`.
- Live setelah restart API:
  - `GET /api/v1/tencent/mt5/accounts` → `{"primary":"416510164","n":1,...}`;
  - `GET /api/v1/tencent/mt5/status` → akun utama, balance 1000, 0 posisi, `connected=true`;
  - `GET /api/v1/journal/performance?market=forex&account=416510164` → 410 titik;
  - akun `999001` → **503** "Belum ada riwayat ekuitas" (bukan nol).
- UI live: panel Akun MT5 tampil dengan `$1000.00`, `0 posisi`, umur 4 s; screenshot
  diambil di browser.

## Batas / belum

- **Bridge MQL5 belum dikompilasi** di terminal MT5. Tidak ada terminal HSFX di host ini;
  `HSFX OnePiece` belum terpasang. Jangan mengklaim eksekusi live sampai EA jalan dan
  log Expert bersih.
- Akun cent harus mengirim nilai USD yang sudah dinormalisasi (bridge melakukannya).
  API menyimpan `currency`/`cent_factor` untuk audit, bukan mengubah angka.
- `latest_mt5_by_account` hanya di memori. Setelah API restart, daftar akun kosong
  sampai EA/bridge mengirim ulang; fakta historis tetap ada di DB.
- `total_trades_today` akun kedua belum dipakai watchdog; watchdog tetap memantau akun
  utama. Jangan perluas ambang tanpa keputusan owner.
- Panel hanya tersedia untuk pengguna yang lolos auth; endpoint memakai
  `verify_mt5_or_admin` seperti endpoint MT5 lain.

## Langkah berikut

1. Pasang bridge di terminal HSFX (RDP/VM), isi token dari env, izinkan WebRequest.
2. Pastikan `GET /mt5/accounts` menampilkan dua akun dan balance akun cent ≈ $10.
3. Buka panel Akun MT5, pilih akun cent, cek posisi/kurva.
4. Setelah ada deal: jalankan `tools/rekonsiliasi_forwardtest.py` terhadap statement,
   lalu simpan bukti di `artifacts/sprint-1/trade-<ticket>/` (tanpa token).
