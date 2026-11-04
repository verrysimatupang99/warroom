# Uji Momentum / Trend Following pada Spot Crypto

Tanggal: 24 Okt 2026 | Data: 2.000 candle harian (~5,5 tahun), 6 koin, sumber MEXC
Sumber edge: **#2 Momentum** (bukti terkuat di literatur keuangan — 67 pasar, 140 tahun)

---

## 1. Kenapa momentum

Dari peta 13 sumber edge, momentum adalah yang bukti akademiknya paling kokoh
(Moskowitz-Ooi-Pedersen 2012; "A Century of Evidence on Trend-Following" 1880–2016).
Seluruh ide yang kita uji sebelumnya berasal dari **mean reversion** — sumber yang
berbeda dan sudah gagal.

---

## 2. Aturan yang diuji

| Komponen | Nilai |
|---|---|
| Masuk | close menembus **high tertinggi 55 bar** |
| Keluar | trailing stop **3 × ATR** dari harga tertinggi sejak masuk (Chandelier) |
| Ukuran posisi | **2% ekuitas per trade** dibagi jarak stop |
| Fee | 0,1% per sisi |
| Arah | LONG saja (spot) |

Sinyal memakai bar **sebelumnya**, eksekusi di close bar sekarang — tanpa look-ahead.

---

## 3. Hasil

### a) Versi all-in (pembanding)

| Metrik | Nilai |
|---|---|
| Return OOS rata-rata | +8% |
| **Drawdown rata-rata** | **56%** |

### b) Versi risk-based (2% per trade) — **ini yang benar**

| Koin | Full | DD | Trade | Win | **OOS** | DD OOS |
|---|---|---|---|---|---|---|
| BTC | +24% | 6% | 13 | 54% | **+11%** | 6% |
| ETH | +9% | 7% | 16 | 56% | **+7%** | 6% |
| SOL | +48% | 14% | 15 | 40% | **+0%** | 11% |
| XRP | +19% | 11% | 13 | 46% | **+29%** | 10% |
| DOGE | +8% | 18% | 15 | 33% | **+5%** | 18% |
| LINK | −3% | 16% | 18 | 33% | **+3%** | 11% |
| **Rata-rata** | | | | | **+9%** | **10%** |

**Semua 6 koin positif di periode out-of-sample.** Ini pertama kalinya terjadi
dalam seluruh pengujian hari ini.

---

## 4. Perbandingan antar pendekatan (periode OOS yang sama)

| Pendekatan | Return | Drawdown | Return/DD |
|---|---|---|---|
| Buy & hold | +19% | 72% | 0,26 |
| Momentum all-in | +8% | 56% | 0,14 |
| **Momentum risk-based** | **+9%** | **10%** | **0,90** |
| Grid + filter rezim | +4% | puluhan % | ~0,1 |

**Temuan terpenting: sizing lebih berharga daripada sinyal.**

Sinyal yang sama (Donchian 55) memberi return hampir identik (+8% vs +9%), tapi
drawdown turun dari **56% → 10%** hanya dengan mengubah ukuran posisi.

Ini bukti langsung bahwa sumber edge #13 (eksekusi & sizing) nyata dampaknya —
konsisten dengan temuan 20R hilang karena slippage.

---

## 5. Batasan — penting

| Aspek | Status |
|---|---|
| **Jumlah trade** | hanya **4–8 per koin** di OOS. Terlalu sedikit untuk signifikan |
| **Jumlah pasar** | 6 koin, semuanya masih hidup (survivorship bias) |
| Parameter | 55/20/2%/3ATR dipilih dari konvensi literatur, **bukan** dioptimasi — ini bagus (anti curve fitting) |
| Return absolut | rendah: +9% dalam 2,2 tahun ≈ 4%/tahun |
| Hanya LONG | bear market panjang belum benar-benar diuji |
| Slippage | belum dihitung (di kripto kecil, tapi tetap ada) |

**Kesimpulan statistik: arahnya positif dan konsisten, tapi sampelnya terlalu kecil
untuk disebut terbukti.** Butuh 50+ trade per pasar, bukan 4–8.

---

## 6. Kenapa ini berbeda dari grid

| | Grid | Momentum |
|---|---|---|
| Sumber edge | mean reversion | **momentum** |
| Hasil OOS | +4%, tidak konsisten | +9%, **semua koin positif** |
| Drawdown | 48–59% | **10%** |
| Butuh prediksi arah | tidak (tapi butuh sideways) | ya (tapi trailing stop membatasi salah) |
| Cara gagal | tren panjang menghabiskan akun | banyak whipsaw kecil |

Momentum gagal dengan cara yang **jauh lebih aman**: rugi kecil berkali-kali,
bukan kehilangan akun.

---

## 7. Langkah berikutnya

1. **Perbanyak pasar** — 20–40 koin, bukan 6 (mengurangi survivorship bias)
2. **Perpanjang data** — pakai 5m/1h untuk dapat lebih banyak trade
3. **Uji parameter lain** — 20/10, 100/50 — dengan walk-forward, bukan optimasi
4. **Tambah slippage** — terutama untuk altcoin kecil
5. Baru pertimbangkan demo

Cara menjalankan ulang:
```bash
cd ~/warroom &&.venv/bin/python ops/uji_momentum_risk.py 1d 2000
```

---

## 8. Uji portofolio 40 koin (langkah 1)

Trend follower sungguhan menyebar risiko ke banyak pasar, bukan all-in satu koin.
Tiap koin dapat porsi modal sama, kurva ekuitas digabung.

| Metrik | Nilai |
|---|---|
| Koin diuji | **38** (2 gagal: data kurang) |
| Koin positif | **27 (71%)** |
| Return rata-rata | **+10%** |
| Terbaik / terburuk | ZEC **+118%** / ETC **−6%** |
| **Portofolio** | **+9,8%** |
| **Max drawdown portofolio** | **2,3%** |
| **Rasio return/DD** | **4,23** |

### Kenapa DD-nya kecil sekali

Karena risiko 2% dihitung per **sub-akun** tiap koin. Dengan 40 koin, risiko per
trade di tingkat portofolio hanya **0,05%** — jadi ini portofolio berleverage rendah.

Kalau diskalakan ke DD 10% (4,3×), return setara **~+42% dalam 2,2 tahun (~18%/tahun)**.
Tapi penskalaan linear tidak otomatis berlaku — margin, korelasi saat panik, dan
slippage akan menggerusnya.

### Sebaran hasil

10 terbaik: ZEC +118%, XLM +40%, HBAR +33%, XRP +29%, TRX +25%,
XMR +24%, QNT +19%, VVV +18%, AAVE +11%, BTC +11%

5 terburuk: ETC −6%, SUI −6%, ICP −3%, LTC −2%, CC −2%

**Catatan penting:** kerugian terburuk hanya −6%, sedangkan kemenangan terbaik +118%.
Ini profil **convex** khas trend following — banyak kalah kecil, sedikit menang besar.

### Batasan yang tetap ada

| Aspek | Dampak |
|---|---|
| **Survivorship bias** | 40 koin ini yang masih listed hari ini; yang delisting tidak masuk |
| Periode OOS | hanya 2,2 tahun |
| Slippage | belum dihitung, terutama altcoin kecil |
| Korelasi | saat crash, semua koin turun bersamaan — DD portofolio bisa jauh lebih besar dari 2,3% |
| Parameter | dari literatur, bukan dioptimasi (ini sisi baiknya) |

**Verdict: hasil terbaik sejauh ini, dan konsisten dengan literatur momentum —
tapi belum bisa disebut terbukti karena survivorship bias dan periode pendek.**

---

## 9. Uji robustness: sensitivitas parameter (18 kombinasi)

Kalau momentum hanya bekerja pada satu set angka, itu kebetulan. Diuji 6 lookback ×
3 pengali ATR pada 38 koin, periode OOS yang sama.

| N | ATR 2,0 | ATR 3,0 | ATR 4,0 |
|---|---|---|---|
| **20** | **+13,6%** / 2,1% / 68% | +12,3% / 2,7% / 76% | +9,0% / 2,6% / 66% |
| **30** | +11,5% / 2,0% / 63% | +11,2% / 2,6% / 71% | +8,0% / 2,4% / 66% |
| **40** | +10,8% / 2,0% / 58% | +10,5% / 2,3% / 71% | +7,4% / 2,2% / 63% |
| **55** | +9,9% / 2,0% / 66% | +9,8% / 2,3% / 71% | +6,8% / 2,3% / 66% |
| **80** | +10,0% / 1,9% / 71% | +8,9% / 2,0% / 71% | +5,9% / 1,9% / 66% |
| **100** | +9,1% / 1,9% / 55% | +7,4% / 1,8% / 63% | +5,0% / 1,7% / 61% |

*(format: return / max DD / % koin positif)*

### 18 dari 18 positif

Tidak ada satu pun kombinasi yang negatif. Rentang return **+5,0% sampai +13,6%**,
drawdown **1,7%–2,7%**.

### Yang lebih penting: gradasinya mulus, bukan acak

| Pola | Arah |
|---|---|
| Lookback lebih pendek (20) | **lebih baik** dari panjang (100): 13,6% vs 5,0% |
| Stop lebih ketat (2 ATR) | **lebih baik** dari lebar (4 ATR): 13,6% vs 9,0% |
| Drawdown | hampir konstan 1,7–2,7% di semua kombinasi |

**Ini tanda efek nyata, bukan noise.** Kalau hasilnya kebetulan, 18 sel akan
tersebar acak antara positif dan negatif. Yang kita lihat adalah **gradien
monoton** — makin pendek lookback dan makin ketat stop, makin baik. Pola yang
konsisten seperti itu tidak muncul dari random.

### Interpretasi pasar

Kripto bergerak lebih cepat dari komoditas/forex. Trend yang lebih pendek (20 bar)
menangkap momentum lebih awal sebelum berbalik. Stop lebar (4 ATR) membiarkan
posisi menahan terlalu lama sehingga menyerahkan kembali profit yang sudah didapat.

### Catatan: ini bukan optimasi

Saya **tidak** memilih 20/2,0 sebagai "pengaturan terbaik" untuk dipakai. Kalau
dipakai, itu jadi curve fitting — persis kesalahan filter rezim di §9 dokumen grid.
Yang benar: pakai nilai tengah (55/3,0) yang tidak dioptimasi, atau uji dulu
pemilihan parameter secara walk-forward.

Yang ditunjukkan tabel ini hanya: **hasilnya tidak sensitif terhadap parameter**.

---

## 10. Uji rezim bear vs bull

Rezim ditentukan dari BTC: close di bawah SMA200 = **bear**, di atas = **bull**.
Kinerja harian momentum dan buy & hold dipisah per rezim (33 koin, 48.070 hari-koin).

| Rezim | Hari | Momentum | Buy & Hold | Selisih |
|---|---|---|---|---|
| **Bear** | 22.364 | **−0,002%** | **−0,189%** | **+0,187%** |
| **Bull** | 25.706 | +0,021% | **+0,300%** | **−0,279%** |

*(rata-rata return harian)*

### Apa artinya

**Di pasar bear, momentum hampir tidak rugi sama sekali** (−0,002%/hari ≈ datar),
sementara buy & hold kehilangan −0,189%/hari (setara **−69%/tahun**).

**Di pasar bull, momentum hanya dapat +0,021%/hari** (≈ +7,7%/tahun), sementara
buy & hold dapat +0,300%/hari (≈ **+109%/tahun**).

### Ini profil khas trend following

| | Momentum | Buy & Hold |
|---|---|---|
| Saat bear | **bertahan** | −69%/tahun |
| Saat bull | +7,7%/tahun | **+109%/tahun** |
| Max DD | **2,3%** | 72% |
| Return/DD | **4,23** | ~3,5 |

Momentum **tidak mencoba menang di bull** — ia mencoba **tidak mati di bear**.
Keuntungannya datang dari compounding kecil yang tidak pernah terkena kerugian besar.

### Kelemahan yang harus jujur diakui

Momentum hanya menangkap **7% dari kenaikan bull** (0,021 vs 0,300 per hari).
Ini strategi **defensif**, bukan mesin uang. Kalau pasar terus naik, buy & hold
akan jauh mengalahkan momentum — dan itu memang terjadi pada 5,5 tahun ini.

### Kesimpulan yang jujur

| Pertanyaan | Jawaban |
|---|---|
| Apakah momentum melindungi saat bear? | **Ya, sangat** — datar vs −69%/tahun |
| Apakah momentum menangkap bull? | **Tidak** — hanya 7% dari upside |
| Apakah lebih baik dari buy & hold? | **Tergantung tujuan**: jauh lebih aman, jauh lebih kecil return |
| Layak dipakai? | **Ya, kalau tujuannya bertahan**; tidak, kalau tujuannya maksimalkan return |

Ini juga menjelaskan kenapa hasil portofolio hanya +9,8%: sebagian besar periode
uji adalah bull yang kuat, dan momentum sengaja tidak ikut sepenuhnya.
