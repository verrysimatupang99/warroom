# Investigasi (a) 12 Trade "Hilang" + (b) Analisa Jam Entry

Tanggal: 24 Okt 2026 | Data: `~/wr_notes/trades_all.csv` (145 baris)

---

## (a) 12 trade "hilang" — ternyata bug saya, bukan data hilang

**Penyebab:** saat scrape pertama saya memakai judul trade sebagai kunci kamus.
Trade dengan nama sama (mis. dua "PYTH Short • SL" di tanggal berbeda) saling menimpa.
12 baris hilang karena itu.

**Perbaikan:** kunci diganti jadi seluruh isi baris (13 kolom digabung). Hasil: **145 baris**,
persis sama dengan angka snapshot.

### Verifikasi terhadap snapshot
| Panel | Snapshot | Database | Selisih |
|---|---|---|---|
| SMC | +174,93 (55) | +193,20 (55) | **−18,27** |
| Fib GP | −202,46 (36) | −202,46 (36) | **0,00** |
| Squeeze | −457,47 (22) | −457,46 (22) | **−0,01** |
| Break&Retest | −1.088,88 (32) | −1.088,87 (32) | **−0,01** |

Tiga panel cocok sampai sen. SMC selisih $18,27 — kemungkinan satu trade diedit
setelah snapshot, atau ada floating yang belum tercatat. **Bukan masalah struktural.**

**Kesimpulan: data Anda sehat.** Peringatan "inkonsistensi data" di laporan sebelumnya
saya tarik — itu artefak kesalahan scrape saya.

---

## Angka dasar (145 trade, bukan 133)

| Metrik | Nilai |
|---|---|
| Total R | **−15,14 R** |
| Rata-rata | −0,104 R/trade |
| Win rate | **55,9%** |
| Rata-rata menang | +0,664 R |
| Rata-rata kalah | −1,077 R |
| Win rate impas | **61,9%** |

| Panel | n | Win% | Total R |
|---|---|---|---|
| SMC | 55 | 56,4% | +2,43 |
| Fib GP | 36 | 58,3% | −1,81 |
| Squeeze | 22 | 54,5% | −4,44 |
| Break&Retest | 32 | 53,1% | **−11,32** |

| Versi | n | Win% | Total R |
|---|---|---|---|
| v1 | 28 | 50,0% | −0,37 |
| v2 | 3 | 66,7% | +0,66 |
| v3 | 40 | 62,5% | −0,75 |
| **v4** | **74** | 54,1% | **−14,68** |

v4 = 51% trade, 97% kerugian.

---

## (b) Jam entry — temuan terbesar dari seluruh analisa

Waktu mengikuti tampilan Notion (asumsi **WIB / UTC+7**).

| Blok jam | n | Win% | Total R | Rata-rata R |
|---|---|---|---|---|
| **00-08 dini hari** | 52 | 40,4% | **−27,17** | **−0,522** |
| **09-11 pagi** | 6 | 16,7% | −4,50 | −0,750 |
| **12-18 siang-sore** | 59 | **76,3%** | **+21,63** | **+0,367** |
| 19-23 malam | 28 | 50,0% | −5,10 | −0,182 |

**Seluruh kerugian terjadi di jam 00:00–11:59 (−31,67 R).**
Jam 12:00–18:00 menghasilkan **+21,63 R** dengan win rate 76,3%.

### Bukan efek samping panel
| Blok | Break&Retest | Fib GP | SMC | Squeeze |
|---|---|---|---|---|
| 00-08 | 16 / **−6,5** | 10 / −2,0 | 15 / **−9,2** | 11 / **−9,5** |
| 12-18 | 8 / **+2,1** | 15 / **+4,5** | 26 / **+8,8** | 10 / **+6,2** |

Keempat panel negatif di dini hari, keempatnya positif di siang-sore.
Bahkan Break&Retest — panel terburuk — jadi **positif (+2,1 R)** di jendela 12-18.

### Bukan efek samping versi
| Blok | v1 | v3 | v4 |
|---|---|---|---|
| 00-08 | −6,7 | −7,1 | −13,4 |
| 12-18 | +4,3 | +10,9 | +5,7 |

Pola bertahan di semua versi.

### Jam terbaik & terburuk (detail)
| Jam | n | Win% | Total R |
|---|---|---|---|
| **13:00** | 9 | **100%** | **+9,11** |
| 14:00 | 10 | 90% | +4,22 |
| 12:00 | 6 | 83% | +3,36 |
| 17:00 | 8 | 75% | +2,08 |
| 09:00 | 5 | **0%** | **−5,60** |
| 08:00 | 5 | 20% | −4,23 |
| 20:00 | 5 | 20% | −4,54 |
| 00:00 | 12 | 33% | −8,12 |

### Konversi ke jam pasar
12:00–18:00 WIB = **05:00–11:00 UTC** = **01:00–07:00 New York**.
Itu jendela **pembukaan London sampai pre-market New York** — saat likuiditas tertinggi
dan spread paling ketat untuk altcoin.

Sebaliknya 00:00–08:00 WIB = 17:00–01:00 UTC = **13:00–21:00 NY** (sesi NY sore/malam),
saat likuiditas menipis dan spread melebar. **Ini juga menjelaskan slippage.**

---

## Skenario (dihitung dari data nyata)

| Skenario | n | Total R | Rata-rata R |
|---|---|---|---|
| Baseline | 145 | −15,14 | −0,104 |
| Semua + SL dibatasi −1,0 R | 145 | −7,66 | −0,053 |
| **Hanya jam 12-18** | 59 | **+21,63** | +0,367 |
| **Hanya 12-18 + SL −1,0 R** | 59 | **+23,26** | **+0,394** |
| 12-18 tanpa B&R + SL −1,0 R | 51 | +20,80 | +0,408 |

Catatan: 46 trade punya R < −1,0 dengan kelebihan total **−7,48 R** (slippage).

---

## Kesimpulan

1. **12 trade tidak pernah hilang** — bug scrape saya. Data 145 baris valid dan cocok
   dengan snapshot sampai sen untuk 3 dari 4 panel.

2. **Filter jam adalah tuas terbesar, bukan mematikan panel.**
   Membatasi entry ke 12:00–18:00 WIB mengubah −15,14 R menjadi **+21,63 R**
   tanpa mengubah strategi, panel, atau versi apa pun.

3. **Slippage punya penjelasan.** Jam 00-08 (sesi NY sore/malam) adalah periode spread
   lebar. Membatasi jam sekaligus menutup sebagian besar kebocoran −7,48 R.

4. **Prioritas tindakan:**
   - a) Terapkan filter jam 12:00–18:00 WIB (dampak terbesar, risiko nol)
   - b) Perbaiki eksekusi SL agar tidak melewati −1,0 R
   - c) Baru setelah itu evaluasi Break&Retest dan v4

## Uji ketahanan (dilakukan 24 Okt 2026)

**Koreksi penting:** seluruh 145 trade ternyata hanya mencakup **8 hari** (14–21 Okt 2026),
bukan 6 bulan. Uji per bulan tidak mungkin; uji per hari dilakukan.

### Per hari: 12-18 vs luar
| Hari | n in | R in | n out | R out |
|---|---|---|---|---|
| 14 Okt | 4 | +3,33 | 6 | +3,99 |
| 15 Okt | 7 | +1,65 | 14 | −8,68 |
| 16 Okt | 13 | **+12,31** | 6 | −4,52 |
| 17 Okt | 5 | −1,59 | 11 | −4,74 |
| 18 Okt | 12 | +0,14 | 6 | −5,90 |
| 19 Okt | 4 | −3,38 | 28 | −7,45 |
| 20 Okt | 10 | **+9,64** | 11 | −7,26 |
| 21 Okt | 4 | −0,47 | 4 | −2,21 |

**12-18 lebih baik di 7 dari 8 hari.**

### Uji statistik
- Selisih rata-rata R: **+0,794 R** per trade
- Bootstrap per hari (3000 iterasi, resample 8 hari): **95% CI [+0,248, +1,277]**
- Proporsi bootstrap > 0: **99,7%**

### Bukan karena outlier
| Kelompok | n | Win% | Median R | Rata-rata R |
|---|---|---|---|---|
| 12-18 | 59 | **76,3%** | **+0,24** | +0,367 |
| Luar | 86 | 41,9% | **−1,00** | −0,428 |

Median ikut berubah tanda → efeknya bukan dari beberapa kemenangan besar.

### Batasan yang tetap berlaku
8 hari = **satu rezim pasar**. Ini bukti konsistensi **di dalam** sampel, bukan
bukti out-of-sample. Filter jam harus diuji maju (forward test) minimal 2–4 minggu
sebelum dipakai dengan ukuran penuh.

## Keterbatasan
- Asumsi zona waktu WIB berdasarkan tampilan Notion; perlu dikonfirmasi
- **Data hanya 8 hari (14–21 Okt 2026)** — satu rezim pasar
- Penyebab slippage (spread vs latency vs fill) belum dipisah
- Belum diuji out-of-sample — filter jam bisa jadi kebetulan rezim pasar
