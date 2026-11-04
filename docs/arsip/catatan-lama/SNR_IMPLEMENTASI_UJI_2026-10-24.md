# SNR MAP — Implementasi & Uji Awal

Tanggal: 24 Okt 2026 | Commit: `8f155e1`

---

## 1. Yang dibangun

**`packages/core/src/warroom_core/forex/snr.py`** — murni perhitungan, tanpa I/O,
tanpa mengubah keputusan apa pun:

| Fungsi | Kegunaan |
|---|---|
| `deteksi_swing(candles, kiri, kanan)` | cari swing high/low dengan aturan fraktal |
| `bangun_zona(levels, toleransi, jenis)` | kelompokkan level berdekatan jadi zona |
| `peta_snr(candles, atr, toleransi_atr)` | peta lengkap support + resistance |
| `zona_mengandung(zona, harga, buffer)` | apakah harga ada di dalam zona |
| `sl_terlindungi(entry, sl, zonas, buffer)` | apakah SL di sisi aman zona |

**`packages/core/tests/test_snr.py`** — 11 tes, semua lulus.

**`ops/uji_snr.py`** — studi walk-forward pada candle nyata.

---

## 2. Hasil uji pada data nyata

Data: **1.308 candle M5 XAUUSD** (5 hari, rentang 3.989–4.211).

Metode: untuk setiap bar, peta zona dibangun **hanya dari candle sebelumnya**
(tanpa look-ahead). Posisi hipotetis dibuka di close, SL 1,5 ATR, TP 2,0 ATR,
disimulasikan sampai 60 bar ke depan.

| Kelompok | n | Win rate | Expectancy |
|---|---|---|---|
| **SL terlindungi** (di luar zona) | 1.744 | **43,1%** | +0,009 ATR (**+0,006 R**) |
| **SL rentan** (di dalam zona) | 466 | **38,6%** | −0,149 ATR (**−0,099 R**) |

**Selisih: +4,4 poin persentase.**

### Uji signifikansi
```
z = 1,748   p-value = 0,081
```
**Tidak signifikan pada ambang 5%.** Marginal.

### Konteks penting
Breakeven win rate untuk RR 1,33 adalah **42,9%**:
- SL terlindungi 43,1% → **tepat di breakeven**
- SL rentan 38,6% → **di bawah breakeven**

Jadi temuannya bukan "SNR bikin profit", tapi **"SL di dalam zona membuat sistem
kehilangan expectancy"** — sekitar 0,1R per trade.

---

## 3. Penilaian jujur

**Yang didukung data:**
- Arahnya benar — SL di dalam zona memang lebih buruk
- Besaran efeknya masuk akal (0,1R/trade) dan konsisten dengan temuan crypto
  (`sl-placement` win rate 3,1%, SL rata-rata −1,12R)

**Yang belum terbukti:**
- **p = 0,081** — belum cukup bukti untuk menyatakan ini bukan kebetulan
- Hanya **5 hari** data, satu rezim pasar
- Uji ini memakai entry sintetis (setiap bar, SL/TP ATR tetap), **bukan sinyal
  War Room yang sebenarnya**

**Kesimpulan:** hipotesis **layak dilanjutkan**, belum layak dijadikan filter wajib.

---

## 4. Langkah berikutnya (berurutan)

| # | Langkah | Alasan |
|---|---|---|
| 1 | Ulangi uji dengan **30–60 hari** data M5 | n naik ~6–12×, p-value bisa turun di bawah 0,05 |
| 2 | Kalau konsisten, pasang SNR sebagai **metadata** di output sinyal (tidak memblokir) | mengukur pada sinyal nyata, bukan sintetis |
| 3 | Setelah 30–50 trade nyata, bandingkan `sl_placement` sebelum vs sesudah | baru boleh jadi filter |

**Yang TIDAK dilakukan:** memblokir sinyal berdasarkan SNR sekarang. Dengan p=0,081,
memblokir berarti membuang trade berdasarkan sinyal statistik yang belum pasti.

---

## 5. Berkas

| Berkas | Isi |
|---|---|
| `packages/core/src/warroom_core/forex/snr.py` | modul SNR |
| `packages/core/tests/test_snr.py` | 11 tes |
| `ops/uji_snr.py` | studi walk-forward |

Cara menjalankan ulang:
```bash
cd ~/warroom &&.venv/bin/python ops/uji_snr.py
```
