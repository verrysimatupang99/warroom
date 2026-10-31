# Sprint 5 — Backtest & tata kelola (status 31 Okt)

**Periode:** 27 Nov–3 Des 2026 (dikerjakan sebagian 31 Okt).

| Story | Status | Bukti / alasan |
|---|---|---|
| US6.1 real-tick Model 3 | **blocked** | Model 3 sebelumnya menghasilkan 0 tick. Strategy Tester build 6286 menuntut akun tersimpan (`config/accounts.dat`), dan `az vm run-command` berjalan sebagai SYSTEM sehingga MT5 membaca data folder yang salah. Perbaikan butuh sesi RDP/interaktif atau Wine dengan akun login. Tidak dijalankan ulang tanpa akses itu. |
| US6.2 matriks vendor EA | **selesai** | `docs/matriks-vendor-ea-20261031.md`; Galaxius/GoldenBall trial, backtest 3 tahun, tanpa track record live → paper only |
| US6.3 registry parameter | **terverifikasi** | tabel `parameters`: 10 baris, `bounds_json`, `locked`, unique name; perubahan lewat `proposals`; API `/api/v1/params` ber-auth (401 tanpa sesi). `strategy_version` (fingerprint) ditambahkan ke verdict/outcome. |
| US6.4 keputusan gate | **menunggu owner** | `docs/keputusan-gate-20261031.md`: 90% vs 95%+deff; PREMIUM 157 sampel (butuh 99 di 90%, 210 di 95%+deff 1,5) |
| US7.3 segarkan AGENTS/HANDOVER | **selesai** | angka tes 912/1126, 72 vitest, 51 e2e; status job-health/jurnal |

## Catatan real-tick

Yang sudah dicoba dan gagal:
- Model 3 (real tick) → 0 tick, bukan hasil strategi.
- `az vm run-command` → SYSTEM profile, MT5 tidak membaca akun/EA.
- Scheduled task S4U → profil tidak dimuat, selesai 10 detik tanpa log.

Yang dibutuhkan: sesi RDP interaktif (atau Wine lokal dengan akun sudah login), lalu
jalankan tester dari terminal yang sama. Setelah itu simpan laporan HTML + set biaya
(spread/komisi) dan masukkan ke matriks keputusan.

## Tambahan 31 Okt — telemetri multi-akun (di luar backlog)

**Latar.** Akun cent HSFX (`HSFX OnePiece`, saldo $10) akan memakai terminal MT5
terpisah. Sebelumnya state telemetri hanya satu variabel global, sehingga akun kedua
menimpa status akun Reaper.

**Selesai.**

- API: state per akun (`latest_mt5_by_account`), snapshot `ringkas:<account>`,
  `GET /mt5/accounts`, `GET /mt5/status?account=`, kurva
  `/journal/performance?account=`, kolom `account` di deal.
- UI: panel **Akun MT5** di `/forex?sub=ringkas` (kartu akun, posisi, kurva, deal).
- Bridge telemetri-saja `ops/mt5/WarRoom_TelemetryBridge.mq5` + README; normalisasi
  akun cent. **Belum dikompilasi/diuji di terminal MT5** — jangan diklaim live.
- Tracker DoD: berkas tidak terbaca karena izin sekarang dilaporkan
  `status=tidak-izin` + angka `n/a`, bukan nol (temuan dari eksekusi sebagai `admin`).

Rincian + bukti: `docs/multi-akun-mt5-20261031.md`.

**Menunggu owner.** Pemasangan bridge di terminal HSFX (RDP/VM), lalu trade pertama
untuk bukti runbook US1.2. Watchdog masih hanya memantau akun utama.
