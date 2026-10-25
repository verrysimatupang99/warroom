# Peta Seluruh Sumber Edge di Dunia Trading

Tanggal: 24 Okt 2026 | Pelengkap `docs/register-ide.md`

---

## 0. Kenapa "semua ide" bisa dipetakan

Jumlah strategi yang pernah ditulis orang tak terbatas, tapi **sumber keuntungannya
terbatas**. Setiap strategi — dari grid retail sampai HFT Citadel — mengambil uang
dari salah satu dari 13 sumber di bawah. Sisanya adalah kombinasi, variasi parameter,
atau ilusi.

Pertanyaan yang benar bukan "strategi apa yang bagus", tapi **"dari mana uangnya
datang, dan kenapa orang lain belum mengambilnya"**.

---

## 1. Tiga belas sumber edge

| # | Sumber | Mekanisme | Bukti akademik | Akses retail $500 |
|---|---|---|---|---|
| 1 | **Risk premium** | dibayar karena menanggung risiko yang orang lain hindari | kuat | sebagian |
| 2 | **Momentum / tren** | harga yang naik cenderung lanjut naik (1–12 bulan) | **sangat kuat** | **ya** |
| 3 | **Mean reversion** | harga menyimpang lalu kembali | kuat (horizon pendek) | ya |
| 4 | **Carry / yield** | dibayar karena memegang aset ber-yield | kuat | ya (kripto) |
| 5 | **Value** | beli murah, jual mahal (fundamental) | kuat (ekuitas) | lemah |
| 6 | **Volatility risk premium** | jual asuransi (opsi) lebih mahal dari risiko nyata | **sangat kuat** | tidak |
| 7 | **Market making** | dapat spread dari yang butuh likuiditas | kuat | tidak |
| 8 | **Latency / microstructure** | lebih cepat dari orang lain | kuat | tidak |
| 9 | **Event / flow** | reaksi atas berita, likuidasi, unlock, rebalancing | sedang | sebagian |
| 10 | **Behavioral** | orang salah sistematis (overreact, anchoring) | sedang | sebagian |
| 11 | **Struktural** | aturan yang memaksa orang bertransaksi | kuat | sebagian (kripto) |
| 12 | **Informasi** | tahu lebih dulu | kuat | tidak |
| 13 | **Eksekusi & sizing** | bukan alpha, tapi mengurangi kebocoran | kuat | **ya** |

---

## 2. Rincian per sumber

### 1. Risk premium
Dibayar karena menanggung sesuatu yang tak nyaman: risiko ekuitas, kredit, likuiditas,
atau volatilitas. Contoh: beli saham dan tahan 10 tahun; jual opsi; beri pinjaman.
**Untuk kita:** butuh modal besar dan horizon panjang. Tidak cocok untuk akun $500.

### 2. Momentum / tren
Harga yang sedang naik cenderung lanjut naik dalam 1–12 bulan. Salah satu temuan
paling kokoh di keuangan (Moskowitz-Ooi-Pedersen 2012; "A Century of Evidence on
Trend-Following" — 1880–2016, 67 pasar).
**Untuk kita:** ✅ paling mudah diakses. Cukup MA/breakout, bisa otomatis, bekerja
di forex & kripto. **Ini yang paling aneh karena belum kita uji sama sekali.**

### 3. Mean reversion
Harga menyimpang dari rata-rata lalu kembali. Kuat di horizon menit–jam (stat arb),
lemah di horizon panjang.
**Untuk kita:** ✅ inilah keluarga grid/Bollinger/RSI. Sudah kita uji — mekanismenya
nyata, tapi tanpa edge stabil setelah walk-forward.

### 4. Carry / yield
Dibayar karena memegang aset yang menghasilkan. Di kripto: **funding rate** perp,
staking, basis futures-spot.
**Untuk kita:** ✅ **paling belum tergarap.** Funding rate perp kripto bisa 10–50%
tahunan, dan bisa di-hedge (long spot + short perp = delta netral). Ini sumber edge
nyata yang belum kita sentuh.

### 5. Value
Beli aset murah relatif fundamentalnya. Kuat di ekuitas (Fama-French).
**Untuk kita:** ❌ butuh data fundamental & horizon tahunan. Tidak realistis.

### 6. Volatility risk premium
Opsi secara sistematis lebih mahal dari nilai wajarnya — penjual opsi dipaid
premium. Salah satu premium paling stabil yang diketahui.
**Untuk kita:** ❌ butuh akses opsi & margin besar. Exness punya opsi? Terbatas.

### 7. Market making
Dapat spread dengan memasang order dua sisi.
**Untuk kita:** ❌ butuh infrastruktur, modal, dan manajemen inventori. Bukan untuk retail.

### 8. Latency / microstructure
Menang karena lebih cepat melihat/mengeksekusi.
**Untuk kita:** ❌ butuh colocation. Mustahil dari Azure ke broker retail.

### 9. Event / flow
Reaksi atas kejadian: berita makro, likuidasi paksa, token unlock, rebalancing indeks.
**Untuk kita:** ⚠️ sebagian. Likuidasi berantai di kripto bisa dipantau (funding +
open interest), tapi butuh data real-time yang mahal.

### 10. Behavioral
Orang salah secara sistematis: terlalu reaktif, jangkar ke harga lama, takut rugi
lebih dari senang untung.
**Untuk kita:** ⚠️ sebagian — dan ini yang sebenarnya kita manfaatkan kalau trading
melawan kepanikan. Tapi sulit diukur tanpa data positioning.

### 11. Struktural
Aturan yang memaksa transaksi: rebalancing indeks, expiry futures, unlock token.
**Untuk kita:** ⚠️ kripto punya banyak (unlock, listing, halving), tapi butuh
kalender event yang rapi.

### 12. Informasi
Tahu lebih dulu dari pasar.
**Untuk kita:** ❌ ilegal atau tidak etis. Tidak dipertimbangkan.

### 13. Eksekusi & sizing
Bukan sumber alpha, tapi **mengurangi kebocoran**. Slippage, spread, lot sizing,
korelasi antar posisi.
**Untuk kita:** ✅ **inilah C1 di register** — 20R hilang dari 145 trade karena SL
kena 14% lebih dalam. Ini bukan alpha, tapi dampaknya sebesar alpha.

---

## 3. Yang tampak seperti edge tapi bukan

| Ide | Kenapa bukan edge |
|---|---|
| **Martingale** | memindahkan risiko ke ekor; bangkrut cepat atau lambat |
| **Grid tanpa filter** | kita uji: OOS +4%, tidak konsisten |
| **Support/resistance** | kita uji: p=0,741 |
| **Pola candlestick** | tak ada bukti setelah biaya |
| **RSI/MACD crossover** | dieksploitasi sejak 1980-an; edge habis oleh biaya |
| **Elliott wave** | tak bisa difalsifikasi |
| **"AI trading bot"** | LLM tidak punya informasi yang belum ada di harga |
| **Sinyal grup berbayar** | kalau benar-benar untung, tak perlu jual langganan |
| **Copy trading** | biaya + keterlambatan; yang disalin sudah kadung masuk |
| **Backtest cantik** | curve fitting — 3 dari 4 hasil positif kita gugur OOS |

---

## 4. Yang realistis untuk kita

Filter: modal $500, Exness MT5 (forex/CFD), spot crypto, otomatis, tanpa colocation.

| Peringkat | Sumber | Alasan |
|---|---|---|
| **1** | **Eksekusi (13)** | terbukti bocor 20R; murni perbaikan, bukan spekulasi |
| **2** | **Carry/funding (4)** | belum digarap; bisa delta-netral; hasil relatif stabil |
| **3** | **Momentum/tren (2)** | bukti terkuat di dunia; belum kita uji sama sekali |
| 4 | Mean reversion (3) | sudah diuji, gagal OOS — tapi bisa dicoba dengan filter berbeda |
| 5 | Event/struktural (9/11) | butuh data & kalender; layak nanti |
| — | Sisanya | tidak realistis atau tidak etis |

---

## 5. Posisi ide-ide kita di peta

| Ide kita | Sumber | Status |
|---|---|---|
| SNR | mean reversion | ❌ p=0,741 |
| Filter jam | timing (bukan edge) | ❌ tidak transfer |
| Grid + avg | mean reversion | ❌ OOS +4% |
| Hard stop grid | manajemen risiko | ❌ merusak |
| Filter rezim | regime timing | ❌ overfitting |
| Slippage/SL | **eksekusi (13)** | ✅ terukur, belum diperbaiki penuh |
| Panel A/B/C | sizing (13) | 🟡 berjalan |
| Daily ratchet | sizing (13) | 🟡 berjalan |
| Breakeven/trailing | manajemen risiko | ✅ terpasang |

**Pola yang terlihat:** semua yang kita uji berasal dari **sumber #3 (mean reversion)**
dan **timing**. Yang belum kita sentuh justru sumber dengan bukti terkuat:
**#2 momentum** dan **#4 carry**.

---

## 6. Tiga hal yang belum kita coba dan paling menjanjikan

### a) Trend following (sumber #2)
Bukti terkuat di seluruh literatur keuangan, berlaku di 67 pasar selama 140 tahun.
Implementasi sederhana: breakout Donchian, MA cross, atau ATR channel — dengan
trailing stop, bukan TP tetap.

**Kenapa cocok:** bekerja di forex & kripto, otomatis, tidak butuh data mahal.
**Kenapa belum dicoba:** kita terlalu fokus membenahi sistem mean-reversion yang ada.

### b) Funding rate / carry (sumber #4)
Di perp kripto, funding dibayar tiap 8 jam. Bisa di-hedge: long spot + short perp →
delta netral, dapat funding tanpa risiko arah.
**Kenapa cocok:** hasilnya tidak bergantung pada tebakan arah.
**Risiko:** risiko exchange, likuidasi pada leg short, dan funding bisa berbalik.

### c) Eksekusi (sumber #13)
Sudah terbukti bocor. Bukan ide baru — tapi **paling cepat menghasilkan perbaikan
terukur** dan tidak butuh hipotesis baru.

---

## 7. Kesimpulan

Ada 13 sumber edge di dunia. Kita sudah menguji **satu** di antaranya secara serius
(mean reversion) dan gagal. Kita belum pernah menyentuh **momentum** — sumber dengan
bukti terkuat — maupun **carry**, yang paling cocok untuk kripto.

Artinya: bukan "tidak ada ide lagi". Justru **dua sumber terbaik belum dicoba**.

Tapi urutannya tetap: **perbaiki eksekusi dulu** (C1), karena alpha apa pun akan
bocor lewat slippage 14%.
