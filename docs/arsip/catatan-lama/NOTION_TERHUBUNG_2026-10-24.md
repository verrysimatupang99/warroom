# Notion terhubung — hasil & temuan (24 Okt 2026)

## Status
- Connector `notion`: **connected** (akun user, satu workspace).
- Halaman **Planetx Trading Journal TIDAK bisa diakses** lewat connector:
  pencarian "Planetx" mengembalikan 0 hasil. Halaman itu situs publik milik pihak
  lain, bukan bagian workspace user, jadi integrasi tidak punya izin membacanya.

## Yang ADA di workspace user (jauh lebih relevan)
Sistem trading crypto pribadi dengan 4 database:

| Database | Isi (properti) |
|---|---|
| **Trades** | Trade, Koin, Arah, P/L ($), R, SL %, Leverage, Panel, Versi, Hasil, Menang, Buka, Tutup |
| **Snapshots** | Snapshot, Panel, Waktu, Ekuitas ($), Realized ($), Floating ($), Posisi terbuka, Trade ditutup, Win rate |
| **Positions** | Posisi, Entry (USDT), SL (USDT), TP kena, Leverage, Arah, Panel, Dibuka, Floating ($) |
| **Skip decisions** | Keputusan, Koin, Arah, Alasan skip, Panel, Status risk, Versi, Waktu |

### Nilai unik yang terlihat
- **Panel** (strategi): `Break&Retest`, `Squeeze`, `Fib GP`, `SMC`
- **Versi**: `v4` (versi strategi dilacak)
- **Alasan skip**: `btc_killswitch`, `sl>2.5%` -> ada kill-switch berbasis BTC!
- **R multiple** dicatat per trade (-1.1, -1.2, +0.25) -> konsisten dengan
  framework risk-based, bukan sekadar P/L
- **SL %** per trade (1.0%-2.4%) -> sizing berbasis jarak SL
- **Status risk**: Normal
- Leverage 2-5x

### Sampel 5 trade terbaru (22 Okt 2026)
| Trade | Panel | Hasil | P/L ($) | R | SL % | Lev |
|---|---|---|---|---|---|---|
| ZEN Long | Fib GP | SL | -111.23 | -1.10 | 1.96% | 3 |
| HYPE Long | SMC | SL | -114.54 | -1.10 | 1.93% | 3 |
| SUI Long | Fib GP | SL | -120.91 | -1.20 | 1.01% | 5 |
| WLD Long | Fib GP | BE | +25.13 | +0.25 | 2.36% | 2 |
| GRAM Long | SMC | SL | -119.93 | -1.14 | 1.38% | 4 |

Catatan: R negatif konsisten di sekitar -1.1 s/d -1.2 (bukan -1.0) -> ada
biaya/slippage di luar jarak SL murni. Ini penting untuk kalibrasi risk.

### Snapshots (per panel, per waktu)
Contoh 22 Okt 12:04:
| Panel | Ekuitas | Realized | Win rate | Trade ditutup |
|---|---|---|---|---|
| Break&Retest | 8.911,12 | -1.088,88 | 53,1% | 32 |
| Squeeze | 9.542,53 | -457,47 | 54,6% | 22 |
| Fib GP | 9.797,54 | -202,46 | 58,3% | 36 |
| SMC | 10.173,10 | +174,93 | 56,4% | 55 |

-> SMC satu-satunya panel dengan realized positif pada snapshot itu; tiga panel
lain negatif. Total realized keempat panel = -1.573,88.

## Kesimpulan
1. Untuk materi Planetx, perlu **ekspor dari pemilik** (PDF/Markdown) atau
   pemilik membagikan halaman ke integrasi.
2. Yang lebih berharga justru ada di workspace user sendiri: schema journal crypto
   sudah bagus (R multiple, SL %, panel, versi, alasan skip, kill-switch BTC).
3. Skema ini bisa dipetakan ke War Room untuk memperkaya journal forex/crypto:
   `panel` (strategi), `versi`, `R`, `sl_pct`, `alasan_skip`, `status_risk`.
