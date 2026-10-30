# Backtest Reaper: saldo demo $1.000 vs $10.000

30 Okt 2026. Semua angka di bawah hasil eksekusi Strategy Tester, bukan perkiraan.

## Tujuan

Menjawab satu pertanyaan: berapa hasil `WarRoom_AutoTrader_v3` (varian A yang
terpasang) bila modal awal disamakan dengan saldo akun demo — **$1.000**, bukan
$10.000 seperti backtest sebelumnya.

## Metode

- MT5 build 6274, salinan **portable** di `C:\mt5test` supaya terminal produksi
  (session 2, EA live) tidak diganggu dan tidak di-restart.
- Akun demo `416510164` (Exness-MT5Trial14), leverage 1:500.
- XAUUSDm M5, Model 2 (1 minute OHLC), 2023.10.27–2026.10.27, `UseLocal=1`,
  history quality **98%**.
- Input identik dengan `Tester/reaper_A.ini`: sesi 08–09, skip Senin, risiko 0,5%,
  SL 1,6×ATR, TP 3,5×ATR, BE/trailing default. **Hanya `Deposit` dan `Report`
  yang berbeda** antara dua run.
- Dijalankan lewat scheduled task interaktif sebagai `traderadmin` (session 2),
  bukan `az vm run-command` yang berjalan sebagai SYSTEM (§9 serah-terima).
- Durasi tiap run ±4 menit.

## Hasil

| Metrik | Deposit $1.000 | Deposit $10.000 |
|---|---|---|
| Total net profit | **+134,75** (+13,48%) | **+3.873,36** (+38,73%) |
| Profit factor | **1,13** | **1,25** |
| Total trades | **436** | **772** |
| Win rate | 43,58% (190/436) | 61,66% (476/772) |
| Average profit trade | 6,23 | 41,32 |
| Average loss trade | −4,26 | −53,36 |
| Expected payoff | 0,31 | 5,02 |
| Balance drawdown maks | **103,71 (9,11%)** | **717,18 (6,01%)** |
| Equity drawdown maks | 107,18 (9,41%) | 800,47 (6,68%) |
| Recovery factor | 1,26 | 4,84 |
| Sharpe ratio | 2,66 | 5,08 |
| Gross profit / loss | 1.183,31 / −1.048,56 | 19.666,64 / −15.793,28 |

## Per tahun

| Tahun | $1.000 | $10.000 |
|---|---|---|
| 2023 (Okt–Des) | −11,33 (−1,13%) | −377,18 (−3,77%) |
| 2024 | +99,13 (+9,91%) | +907,49 (+9,07%) |
| 2025 | +84,10 (+8,41%) | +1.967,59 (+19,68%) |
| 2026 (s.d. Okt) | **−37,15 (−3,72%)** | +1.375,46 (+13,75%) |

## Penyebab perbedaan — bukan sekadar compounding

1. **Partial take profit tidak pernah jalan di $1.000.** EA memasang pagar
   `volume >= 0.04` sebelum partial 50% di +1,0R (baris 703). Di $1.000 lot yang
   dihitung 0,02–0,03, jadi cabang partial tidak pernah dieksekusi.
   - Bukti log tester: partial pertama (baris 30.476) muncul **setelah** init run
     kedua (baris 30.454). Run $1.000: **0 partial**. Run $10.000: **234 partial**.
2. **Win rate berbeda karena exit-nya berbeda**, bukan karena sinyal masuknya
   berbeda: 43,58% vs 61,66%, dengan average win $6,23 vs $41,32.
3. **Penjaga risiko lot tidak menolak order**: 0 pesan `SIZING DITOLAK` di kedua
   run. Jadi bukan pagar risiko yang mengurangi trade.

Kesimpulan: di saldo $1.000, EA berjalan sebagai **varian tanpa partial TP**,
bukan varian A yang dilaporkan di serah-terima. BE dan trailing tetap aktif.

## Validasi ulang angka lama

Rerun $10.000 di build yang sama mereproduksi serah-terima:

- net **+3.873,36** vs +3.923 (selisih −1,3%),
- PF **1,25** (sama),
- trade **772** vs 771,
- balance DD **6,01%** (sama).

Selisih kecil wajar karena history quality 98% dan data M1 diunduh ulang.

## Implikasi

- Ekspektasi realistis untuk demo $1.000: **+13,5% / 3 tahun, PF 1,13, DD ~9%**,
  dan 2026 berjalan negatif.
- Statistik varian A (PF 1,25, DD 6%) hanya berlaku bila lot cukup besar untuk
  memicu partial, kira-kira saldo ≥ $2.000–4.000 tergantung lebar SL.
- Opsi: (a) isi saldo demo ke $10.000 agar identik dengan backtest, (b) ubah pagar
  partial dan backtest ulang, atau (c) terima varian tanpa partial sebagai baseline
  live.

## Bonus: deposit $100 — nol trade

Satu run tambahan dengan `Deposit=100`, input identik:

- **0 trade**, net 0,00, DD 0,00 sepanjang 3 tahun.
- Sebabnya bukan pasar: jalur Reaper menghitung
  `lot = ekuitas × 0,5% / (SL × 100)`, dibulatkan ke bawah 2 desimal, lalu
  **menolak order bila lot < 0,01** (baris 160). Di $100 risiko hanya $0,50;
  dengan SL minimum 1,28 (ATR min 0,80 × 1,6) lot = 0,0039 → semua sinyal ditolak.
- Ambang kasar agar bisa trading: `ekuitas ≥ 200 × SL`. Dengan SL $1,3–3,2
  berarti butuh **$260–640**; $1.000 baru memberi ruang lot 0,02–0,03.
- Pesan penolakan tidak muncul di log console run ini, jadi "0 trade" bukan bukti
  tidak ada sinyal — sinyalnya ada, sizing-nya yang tidak sah.

## Artefak

- Laporan: `C:\mt5test\reaper_A_100.htm`, `reaper_A_1k.htm`, `reaper_A_10k.htm`
  (+ PNG) di VM `mt5-trader-vm`. Tidak disalin ke repo.
- Config: `C:\mt5test\Tester\reaper_A_100.ini`, `reaper_A_1k.ini`, `reaper_A_10k.ini`.
- Klon portable `C:\mt5test` disimpan untuk rerun; scheduled task uji sudah dihapus.
- EA live tidak disentuh; telemetri tetap masuk selama pengujian.
