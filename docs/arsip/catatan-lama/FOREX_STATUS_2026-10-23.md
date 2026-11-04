# Forex / XAUUSD — status & perbaikan 23 Oktober 2026

Fokus: **Exness demo akun `416510164`** + EA `WarRoom_AutoTrader.mq5` yang berjalan di
MT5. Repo lain (crypto/IDX/polymarket) tidak disentuh pada catatan ini.

## 1. Kondisi nyata saat diperiksa (live, bukan asumsi)

| Komponen | Nilai | Bukti |
|---|---|---|
| EA heartbeat | **2 detik lalu** (hidup) | `GET /api/v1/tencent/mt5/status` |
| Akun / broker | `416510164` / Exness Technologies Ltd | idem |
| Balance / equity | **$456.98** / $456.98 | idem |
| Posisi terbuka | 0 | idem |
| Laya sentinel | `HEALTHY`, confidence 0.92 | `GET /api/v1/tencent/forex/sentinel` |
| News bias | `NEUTRAL`, blackout=false, age 3 s | `GET /api/v1/tencent/forex/bias` |
| Sinyal aktif | LONG XAUUSD, entry 4024.93, SL 4019.92, TP1 4029.94 | `GET /api/v1/tencent/forex/levels` |
| Performa harian | 6 trade, WR 66.7% (4W/2L), **net −$43.02**, PF 0.63 | `mt5/status` |

Catatan: `AGENTS.md` menyebut "Azure sudah tidak dipakai lagi (sejak 6 Okt 2026)".
Itu berlaku untuk **radar rantai**, bukan untuk EA. `auth_ea.py` masih mengizinkan IP
Azure `138.91.35.65` dan telemetri EA masih mengalir, jadi EA memang masih berjalan.

## 2. Temuan utama: risiko per trade 11× terlalu besar

EA memakai **lot tetap `InpFixedLot = 0.10`**. Dengan jarak SL sinyal 5.01 (dolar/oz) dan
kontrak XAUUSD 100 oz/lot:

```
risiko per trade = 5.01 × 0.10 × 100 = $50.10
persen balance   = $50.10 / $456.98 = 11.0%
InpDailyMaxLoss  = $25.00
```

**Satu stop-loss saja (=$50.10) dua kali melebihi batas rugi harian ($25).** Ini
menjelaskan pola yang terlihat: win rate 66.7% tetapi rugi bersih −$43.02 dan profit
factor 0.63 — menang kecil, kalah besar.

## 3. Perbaikan yang diterapkan (position sizing)

Berkas: `/srv/private/WarRoom_AutoTrader.mq5`
Backup sebelum perubahan: `~/wr_notes/forex_backups/WarRoom_AutoTrader.bak-20261023.mq5`
Versi baru: `~/wr_notes/forex_backups/WarRoom_AutoTrader.risk-sizing-20261023.mq5`

Input baru (grup "PENGATURAN RISK & LOT"):

| Input | Default | Arti |
|---|---|---|
| `InpUseRiskSizing` | `true` | Hitung lot dari risiko % balance |
| `InpRiskPct` | `1.0` | Risiko per trade (% balance) |
| `InpMaxLot` | `0.10` | Batas atas lot (pengaman) |
| `InpMinLot` | `0.01` | Batas bawah lot (minimum Exness) |
| `InpFixedLot` | `0.10` | Hanya dipakai bila `InpUseRiskSizing=false` |

Fungsi baru `HitungLotRisiko(entry, sl)`:
1. jarak SL diambil dari sinyal yang benar-benar dikirim (bukan angka bulat),
2. nilai per lot dihitung dari `SYMBOL_TRADE_TICK_VALUE / SYMBOL_TRADE_TICK_SIZE`,
3. lot dibulatkan ke `SYMBOL_VOLUME_STEP` (tidak boleh jatuh ke 0),
4. dijepit di [min, max],
5. **penjaga terakhir**: risiko uang nyata tidak boleh > 1.5× target (atau target+$1),
   kalau lewat → **order dibatalkan** dengan alasan tercetak di log.

Bila `tickValue`/`tickSize` tidak terbaca atau jarak SL nol → kembalikan 0 dan order
dibatalkan. Prinsipnya: lebih baik tidak trading daripada salah ukuran.

### Hasil simulasi dengan angka nyata

| Skenario | Jarak SL | Lot | Risiko | % balance | Status |
|---|---|---|---|---|---|
| Sinyal live sekarang | 5.01 | 0.01 | $5.01 | **1.10%** | OK |
| SL sempit | 2.50 | 0.01 | $2.50 | 0.55% | OK |
| SL 2× | 10.02 | — | $10.02 | — | DITOLAK |
| SL lebar | 25.00 | — | $25.00 | — | DITOLAK |
| SL sangat lebar | 50.00 | — | $50.00 | — | DITOLAK |

Sebelum: risiko **$50.10 (11.0%)**. Sesudah: **$5.01 (1.10%)** untuk sinyal yang sama.

## 4. Konsekuensi yang harus diketahui (jujur)

Pada balance $457 dengan lot minimum Exness 0.01, **hanya setup dengan SL ≤ ~$6.85**
yang bisa dieksekusi tanpa melewati batas risiko. Setup dengan SL lebih lebar akan
ditolak — bukan dipaksa dengan risiko 11%.

Artinya EA mungkin **lebih jarang masuk** dibanding sebelumnya. Itu disengaja: tujuannya
menghentikan kerugian akibat ukuran posisi, bukan menambah frekuensi trade.

Alternatif bila ingin tetap bisa mengambil SL lebar: naikkan `InpRiskPct` (mis. 2%)
atau tambah balance. Keduanya keputusan owner.

## 5. Status aktivasi (BELUM selesai — butuh tindakan di MT5)

Source baru sudah dilayani `GET /api/v1/tencent/mt5/source` (200, isi identik).
**Tetapi EA yang berjalan di MT5 masih versi lama**, karena:
- MQL5 harus di-compile ulang di MetaEditor (tidak bisa dari server ini),
- EA harus di-attach/refresh dengan input baru (`InpUseRiskSizing=true`).

Langkah yang perlu dilakukan di mesin MT5:
1. jalankan loop sinkronisasi EA (mengunduh `/api/v1/tencent/mt5/source.raw`), atau
   salin manual `WarRoom_AutoTrader.mq5`,
2. compile di MetaEditor (F7) — pastikan 0 error,
3. pastikan input `InpUseRiskSizing = true`, `InpRiskPct = 1.0`, `InpMaxLot = 0.10`,
4. cek tab Journal MT5 untuk baris ` SIZING: balance=$... -> lot=...`.

Sampai langkah 2-3 dilakukan, EA **masih memakai lot 0.10** dan risiko 11% masih berlaku.

## 6. Temuan lain yang belum ditangani

1. **EA tidak pernah mengecek akun DEMO vs LIVE.** `AccountInfoInteger` hanya dipakai
   untuk nomor akun. Risiko: input yang sama bisa jalan di akun live. Disarankan guard
   `ACCOUNT_TRADE_MODE == ACCOUNT_TRADE_MODE_DEMO` (atau minimal mencatat mode ke telemetri).
2. **Telemetri disimpan di variabel global memori** (`latest_mt5_telemetry`), hilang saat
   API restart; riwayat trade tidak persisten.
3. **`mt5/source` melayani source EA** — dijaga token, tetapi isi source berisi alamat
   endpoint; pastikan tidak ada kredensial yang ikut.
4. Performa −$43.02 pada 6 trade terlalu kecil untuk menyimpulkan edge; setelah sizing
   benar, perlu sampel baru sebelum menilai strategi.
