# Analisa Per-Trade Penuh — Sistem Crypto Sendiri (133 trade)

Tanggal: 24 Okt 2026
Sumber: database Notion `Trades` (133 baris, 13 kolom) — diekstrak via browser
Data mentah: `~/wr_notes/trades_133.csv`

---

## 1. Gambaran umum

| Metrik | Nilai |
|---|---|
| Trade | 133 |
| Total R | **−9,44 R** |
| Rata-rata per trade | **−0,071 R** |
| Total P/L | **−$988,10** |
| Win rate | **57,1%** (76 menang / 57 kalah) |
| Rata-rata menang | +0,678 R |
| Rata-rata kalah | −1,069 R |
| **Win rate impas (breakeven)** | **61,2%** |
| **Selisih** | **−4,1 poin persentase** |

Sistem **tidak impas** — butuh 61,2% untuk balik modal, hanya dapat 57,1%.

## 2. Sebaran hasil keluar

| Hasil | n | Rata-rata R | Total R |
|---|---|---|---|
| TP3 | 9 | **+1,85** | +16,63 |
| SLTP1 | 8 | +1,25 | +9,98 |
| TRAIL | 9 | +1,20 | +10,79 |
| TIME | 8 | +0,66 | +5,31 |
| **BE** | **45** | **+0,19** | **+8,34** |
| **SL** | **54** | **−1,12** | **−60,49** |

Dua temuan langsung:
- **SL rata-rata −1,12 R, bukan −1,00 R** → slippage/biaya 12% per loss
- **BE 45 trade (34% dari semua) hanya menghasilkan +0,19 R** → kunci profit terlalu dini

## 3. Panel — siapa yang sebenarnya membuang uang

| Panel | n | Win% | P/L $ | Total R | Rata-rata R |
|---|---|---|---|---|---|
| **SMC** | 52 | 57,7% | **+395** | **+4,37** | +0,08 |
| Fib GP | 33 | 60,6% | +20 | +0,50 | +0,02 |
| Squeeze | 20 | 55,0% | −369 | −3,55 | −0,18 |
| **Break&Retest** | 28 | 53,6% | **−1.034** | **−10,76** | **−0,38** |

**Break&Retest = 21% trade, tapi 114% dari total kerugian R.**
Tanpa panel ini sistem sudah positif.

## 4. Versi — strategi justru memburuk

| Versi | n | Win% | Total R | Rata-rata R |
|---|---|---|---|---|
| v1 | 26 | 53,8% | **+1,63** | +0,06 |
| v2 | 3 | — | — | — |
| v3 | 36 | 61,1% | +0,04 | 0,00 |
| **v4** | **68** | 55,9% | **−11,77** | **−0,17** |

**v4 menyerap 51% trade dan menyumbang seluruh kerugian.**
Tren: v1 positif → v3 netral → v4 negatif. Iterasi **memperburuk**, bukan memperbaiki.

Per panel:
| Panel | v1 | v3 | v4 |
|---|---|---|---|
| SMC | **+5,64** | +1,46 | **−2,73** |
| Fib GP | −3,67 | — | +4,60 |
| Squeeze | — | +4,40 | **−7,61** |
| Break&Retest | — | −4,73 | −6,03 |

SMC turun monoton tiap versi. Squeeze anjlok di v4. Hanya Fib GP yang membaik.

## 5. Leverage — 4x adalah lubang

| Leverage | n | Win% | Total R |
|---|---|---|---|
| 6x | 13 | 76,9% | **+3,07** |
| 5x | 18 | 61,1% | +2,71 |
| 2x | 21 | 61,9% | +1,91 |
| 7x | 6 | 50,0% | +0,25 |
| 8x | 6 | 66,7% | −0,67 |
| 3x | 40 | 55,0% | −6,11 |
| **4x** | **25** | **48,0%** | **−11,06** |

4x = 19% trade, 117% kerugian R. Pola ini **tidak masuk akal secara teori**
(leverage tidak mengubah R kalau sizing benar) → indikasi **sizing tidak konsisten**:
trade 4x kemungkinan memakai modal lebih besar per R.

## 6. Jarak SL — yang lebar merugi

| SL% | n | Win% | Total R |
|---|---|---|---|
| <1% | 35 | 62,9% | +3,78 |
| 2-2,5% | 29 | 62,1% | +2,24 |
| 1-1,5% | 37 | 51,4% | **−8,07** |
| 1,5-2% | 23 | 60,9% | −3,38 |
| **≥2,5%** | 9 | **33,3%** | **−4,01** |

Dua ekstrem buruk: **SL terlalu rapat (1-1,5%)** kena noise, dan **SL terlalu lebar (≥2,5%)**
risiko per trade terlalu besar.

## 7. Slippage — kebocoran terbesar yang tak terlihat

- 54 trade SL, rata-rata **−1,12 R**
- 41 dari 54 (76%) lebih buruk dari −1,00 R
- Kelebihan di luar −1,00 R: **−6,49 R**

**−6,49 R itu = 69% dari seluruh defisit −9,44 R.**

Artinya: kalau eksekusi presisi (SL kena tepat di −1,00 R), sistem hampir impas
tanpa mengubah strategi sama sekali.

## 8. BE terlalu dini — kebocoran kedua

45 trade berakhir BE dengan rata-rata hanya **+0,19 R**.
Kalau BE rata-rata 0,50 R saja: **+14,16 R** tambahan.
Kalau 0,80 R: **+27,66 R** tambahan.

Hanya 29 trade (22%) yang mencapai >1 R. Sementara 44 trade (33%) menang ≤0,35 R.
**Distribusi menang terlalu pipih** — pemenang dipotong, pecundang dibiarkan sampai −1,12 R.

## 9. Skenario perbaikan (dihitung dari data nyata)

| Skenario | n | Total R | Rata-rata R |
|---|---|---|---|
| Baseline | 133 | −9,44 | −0,071 |
| Tanpa Break&Retest | 105 | **+1,32** | +0,013 |
| Tanpa B&R + tanpa Squeeze v4 | 95 | **+8,93** | +0,094 |
| Hanya SMC + Fib GP | 85 | +4,87 | +0,057 |
| Tanpa leverage 4x | 108 | +1,62 | +0,015 |
| SL dibatasi −1,00 R | 133 | −2,95 | −0,022 |
| **Tanpa B&R + SL dibatasi −1,00 R** | 105 | **+5,25** | +0,050 |
| **Tanpa B&R − Squeeze v4 + SL −1,00 R** | 95 | **+11,76** | **+0,124** |

Kombinasi terakhir: **+11,76 R dari 95 trade** vs baseline −9,44 R.
Selisih **+21,2 R** hanya dari tiga tindakan: matikan satu panel, matikan satu versi,
perbaiki eksekusi SL.

## 10. Inkonsistensi data — perlu dibereskan

| Panel | Snapshot (Realized) | Database (sum P/L) | Selisih |
|---|---|---|---|
| SMC | +174,93 (55) | **+394,68** (52) | **−219,75** |
| Fib GP | −202,46 (36) | **+20,27** (33) | **−222,73** |
| Squeeze | −457,47 (22) | −368,93 (20) | −88,54 |
| Break&Retest | −1.088,88 (32) | −1.034,12 (28) | −54,76 |

Dua masalah:
1. **12 trade ada di snapshot tapi tidak ada di database** (145 vs 133)
2. **SMC dan Fib GP selisih >$200** — database menunjukkan lebih untung dengan trade
   lebih sedikit. Ini tidak mungkin kecuali ada baris yang diedit/dihapus setelah
   snapshot diambil, atau snapshot menghitung hal lain.

**Jangan ambil keputusan modal sebelum angka mana yang benar ditentukan.**

---

## Kesimpulan

Sistem ini **tidak rusak karena strateginya salah**, tapi karena tiga hal yang bisa diperbaiki:

1. **Break&Retest** — 21% trade, 114% kerugian. Matikan dulu.
2. **Slippage SL** — 69% defisit berasal dari SL yang kena 12% lebih dalam dari rencana.
3. **BE terlalu dini** — 45 trade dikunci di +0,19 R padahal potensinya jauh lebih besar.

Kalau ketiganya diperbaiki: **+11,76 R** dari 95 trade, bukan −9,44 R dari 133.

Yang **jangan** dilakukan: menambah versi baru (v4 sudah terbukti lebih buruk dari v1),
atau menaikkan leverage (4x sudah jadi lubang terbesar per trade).

## Keterbatasan
- R dihitung dari kolom `R` yang sudah ada di Notion (bukan hitung ulang dari harga)
- 133 baris; 12 trade yang ada di snapshot tidak tertangkap
- Penyebab slippage (spread/slatency/fill) tidak bisa dipisahkan dari data ini
- Belum ada data jam entry pada database ini (kolom `Buka` ada, tapi belum dianalisa per jam)
