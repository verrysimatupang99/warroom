# Riset Gold Reaper — Laporan G1 (Walk-Forward Layer)

**Tanggal:** 2026-11-02
**Status:** ❌ **NO-GO untuk uang nyata.** Strategi Golden Pullback tidak punya edge.
**Data mentah:** `docs/riset-reaper-hasil.json` (bisa diaudit ulang kapan saja)

---

## 1. Pertanyaan

Apakah Golden Pullback di `signals/golden_pullback.py` menghasilkan profit **setelah
biaya Exness**, di luar kebetulan?

**Jawaban: tidak.**

---

## 2. Data & metode

| Aspek | Nilai |
|---|---|
| Sumber | Binance `PAXGUSDT` 1h (proxy emas) |
| Periode | 2021-01-01 → 2026-11-02 (**5,8 tahun**) |
| Bar setelah QC | 51.133 |
| Biaya | spread **0,35 USD/oz** (Exness Standard Cent) |
| Risiko/trade | 1% ekuitas |
| Aturan ragu | SL & TP kena di candle sama → **hitung SL** |
| Overlap | tidak ada posisi ganda |

**Kenapa PAXG, bukan XAUUSD?** `data/hist/XAUUSD_15m.csv` hanya **30 hari** — tidak
cukup untuk walk-forward. PAXG adalah token emas LPPM bersertifikat, mengikuti harga
spot, likuiditas 24/7. Keterbatasan ini dibahas di §5.

### QC data
- Gap timestamp diperiksa; tidak ada gap struktural.
- **1 bar anomali dibuang:** 2024-04-13 (spike +19,8% / −13,8% dalam 2 jam) — artefak
  likuiditas PAXG saat serangan Iran–Israel, bukan pergerakan emas. Setelah dibuang,
  max move 1 jam turun ke 4,9% (normal untuk emas).

### Model biaya (penting)
Candle dianggap berisi harga **bid**. Long dieksekusi di ask = bid + spread, sehingga
entry efektif digeser satu spread penuh. Konsekuensinya R lebih kecil dan jarak ke
stop lebih sempit — keduanya merugikan strategi.

> Catatan riset: model biaya awal gw **salah** — spread sempat membuat posisi lebih
> mudah selamat, bukan lebih mudah rugi. Bug ini ketahuan lewat unit test yang
> sengaja menuntut sifat "spread selalu merugikan". Setelah diperbaiki, hasil memburuk
> dari −0,067 R menjadi **−0,308 R**. Artinya angka sebelum perbaikan terlalu optimis.

---

## 3. Hasil

### Backtest penuh (5,8 tahun)

| Metrik | Nilai | Arti |
|---|---|---|
| Jumlah trade | 15 | sampel sangat tipis |
| Win rate | **26,7%** | |
| Expectancy | **−0,308 R** | rugi signifikan per trade |
| Profit factor | **0,608** | jauh di bawah 1 |
| R kotor total | **−3,61 R** | rugi **bahkan sebelum biaya** |
| Biaya rata-rata | 0,067 R | |
| R bersih total | −4,62 R | |
| Max drawdown | 6,36% | (pada risiko 1%) |
| t-statistik | **−0,94** | tidak signifikan → "nol", bukan "negatif pasti" |
| Sharpe/trade | −0,243 | |

**Bacaan kunci:** R kotor sudah −3,61 R. Berbeda dari dugaan awal, kelemahannya
**bukan** sekadar biaya — arahnya memang salah. Biaya hanya memperlebar kerugian.

### Monte Carlo (bootstrap 2.000×)

| Persentil | Expectancy |
|---|---|
| p05 | −0,875 |
| p50 | −0,309 |
| p95 | +0,266 |

**Probabilitas expectancy > 0 hanya 20,1%.** Satu dari lima.

### Walk-forward (5 blok kronologis)

| Blok | Periode | n | Expectancy | PF |
|---|---|---|---|---|
| 1 | 2021-01 → 2022-03 | 1 | −1,06 | 0,00 |
| 2 | 2022-03 → 2023-05 | 4 | −1,10 | 0,00 |
| 3 | 2023-05 → 2024-07 | 3 | −0,16 | 0,78 |
| 4 | 2024-07 → 2025-09 | 2 | +0,43 | 1,84 |
| 5 | 2025-09 → 2026-11 | 5 | +0,09 | 1,14 |

Tiga blok pertama rugi, dua terakhir tipis positif — semuanya dengan **n ≤ 5**.
Ini pola derau, bukan rezim yang bisa diprediksi. Tertentu tidak konsisten.

### Skenario spread buruk berita (0,50 USD/oz)

Expectancy **−0,353 R**, PF 0,564. Makin buruk, sesuai ekspektasi.

### Sensitivitas 16 kombinasi (lookback × RR)

Hanya **4 dari 16** yang positif, dan t-stat semuanya < 0,5:

| lookback | RR 1.5 | RR 2.0 | RR 2.5 | RR 3.0 |
|---|---|---|---|---|
| **30** | **+0,016** (t=0,07) | **+0,011** (t=0,04) | −0,051 | −0,051 |
| **40** | −0,279 | **−0,308** ← default | −0,182 | −0,055 |
| **50** | −0,122 | **+0,062** (t=0,12) | −0,182 | −0,059 |
| **60** | −0,212 | −0,049 | **+0,114** (t=0,17) | **+0,278** (t=0,37) |

Bentuknya **bukan plateau**. Nilai positif muncul berserak dan tidak bertetangga.
Edge yang nyata akan menghasilkan area hijau berdekatan; ini derau.

### Diagnostik: apa yang membunuhnya?

Buka filter zona Fibonacci untuk menambah sampel:

| Konfigurasi | n | PF | Expectancy | Max DD |
|---|---|---|---|---|
| Default (0,618–0,786) | 15 | 0,608 | −0,308 | 6,4% |
| Longgar 0,5–0,786 | 32 | 0,838 | −0,118 | 8,1% |
| Lebar 0,382–0,786 | 57 | 0,793 | −0,152 | 12,7% |
| Tanpa filter zona | **81** | **0,735** | **−0,200** | **20,2%** |

Semua negatif. Sampel yang lebih besar tidak menyelamatkannya.

---

## 4. Diagnosis

Interpretasi sinyal memicu entry **di candle sweep**, sementara `build_pullback_setup()`
mensyaratkan harga di **zona retracement**. Keduanya bertentangan secara struktural:
saat sweep, harga berada di ekstrem — bukan di 61,8–78,6%.

Itulah sebabnya **83% kondisi mentah tersaring** (89 → 15 trade). Ini menjelaskan
sampel kecil, tetapi **tidak** menyelamatkan strategi: setelah filter dibuka, hasilnya
tetap negatif.

---

## 5. Keterbatasan (jujur)

1. **PAXG ≠ XAUUSD.** Spread, gap weekend, dan perilaku sesi berbeda. Ini alasan kuat
   untuk tidak memakai hasil ini sebagai lampu hijau; bukan alasan berharap XAUUSD
   lebih baik, karena biaya XAUUSD umumnya lebih mahal.
2. **15 trade terlalu tipis** untuk membuktikan profit. Cukup untuk **menolak** membawa
   strategi ini ke uang nyata.
3. Belum ada model slippage selain spread; realita lebih buruk, bukan lebih baik.
4. Interpretasi sinyal adalah buatan gw, bukan milik penulis strategi.

---

## 6. Keputusan

❌ **NO-GO.** Golden Pullback tidak dijalankan, termasuk di akun cent.

Alasannya bukan "belum terbukti", tapi **sudah diuji dan hasilnya negatif**:
- rugi bahkan sebelum biaya (−3,61 R kotor)
- probabilitas profit 20,1%
- tidak ada plateau parameter
- konsisten rugi saat sampel diperbesar

---

## 7. Nilai yang tetap didapat

1. **Data emas 5,8 tahun** yang bersih & ber-QC — kini bisa dipakai untuk kandidat apa pun.
2. **Runner backtest jujur** dengan aturan pesimistis **yang dikunci oleh 19 unit test**
   (SL diutamakan saat ragu, spread selalu merugikan, tanpa look-ahead).
3. **Kemampuan menolak ide dengan bukti** — aset yang lebih berharga daripada menerima
   ide dengan harapan.
4. **Bukti bahwa arah entry-nya salah**, bukan cuma biaya — mengarahkan riset berikutnya
   ke hipotesis yang benar-benar berbeda.

## 8. Langkah berikutnya

Jangan cari parameter lain untuk Golden Pullback. Uji **hipotesis berbeda**:
- berbasis **sesi** (Asia vs London vs NY) — volatilitas emas sangat berbeda per sesi;
- **momentum harian** dengan trade sedikit tapi R besar, agar biaya per R kecil.

Setiap kandidat wajib lewat `riset_reaper.py` dengan ambang yang sama.
