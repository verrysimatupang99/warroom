# Analisa Kepadatan Posisi vs Slippage

Tanggal: 24 Okt 2026 | Data: 145 trade, 14–21 Okt 2026

---

## 1. Kepadatan posisi

Dihitung dari pasangan waktu `Buka`/`Tutup` tiap trade.

| Metrik | Nilai |
|---|---|
| Posisi terbuka bersamaan (median) | **6** |
| Maksimum | **12** |
| Rata-rata trade/hari | 18 |

Distribusi: 0-3 posisi = 22 trade, 4-6 = 60, 7-9 = 54, 10+ = 9.

## 2. Semakin padat, semakin buruk

| Posisi bersamaan | n | Win% | Rata-rata R | Median R | Laju R < −1,0 |
|---|---|---|---|---|---|
| **0-3** | 22 | **68,2%** | **+0,369** | +0,29 | **14%** |
| 4-6 | 60 | 63,3% | −0,007 | +0,17 | 20% |
| 7-9 | 54 | 44,4% | −0,404 | −1,00 | **48%** |
| **10+** | 9 | 44,4% | −0,119 | −1,09 | **56%** |

Gradiennya monoton. Laju slippage naik dari 14% → 56% seiring kepadatan.

## 3. Tapi jam lebih menentukan daripada kepadatan

Kepadatan rata-rata di kedua jendela hampir sama (5,6 vs 6,4) — jadi efek jam
**bukan** sekadar efek kepadatan. Tabel silang membuktikannya:

### Rata-rata R per sel (n / meanR)
| | 0-3 | 4-6 | 7-9 | 10+ |
|---|---|---|---|---|
| **12-18** | 13 / **+0,38** | 27 / **+0,37** | 15 / **+0,29** | 4 / **+0,62** |
| **luar** | 9 / +0,35 | 33 / −0,31 | 39 / −0,67 | 5 / −0,71 |

Di jendela 12-18, **semua tingkat kepadatan tetap positif** — bahkan 10+ posisi.
Di luar jendela, hanya 0-3 posisi yang positif; sisanya negatif dan makin buruk.

### Laju slippage (R < −1,0)
| | 0-3 | 4-6 | 7-9 | 10+ |
|---|---|---|---|---|
| **12-18** | 15% | 15% | 20% | 25% |
| **luar** | 11% | 24% | **59%** | **80%** |

Ini bukti langsung: di luar jendela likuiditas, 7-9 posisi bersamaan membuat
**59% trade** kena slippage; 10+ posisi membuat **80%**. Di dalam jendela 12-18,
angka itu tetap 20-25% berapa pun kepadatannya.

## 4. Skenario

| Skenario | n | Total R | Rata-rata R | Win% |
|---|---|---|---|---|
| Baseline | 145 | −15,14 | −0,104 | 55,9% |
| Hanya ≤6 posisi bersamaan | 82 | +7,72 | +0,094 | 64,6% |
| **Hanya 12-18** | 59 | **+21,63** | **+0,367** | **76,3%** |
| 12-18 **dan** ≤6 bersamaan | 40 | +14,83 | +0,371 | 75,0% |
| 12-18 dan ≤3 bersamaan | 13 | +4,97 | +0,382 | 69,2% |

**Menarik:** menambah batas kepadatan ke filter jam **tidak menaikkan** rata-rata R
(0,367 → 0,371, praktis sama) — hanya memotong jumlah trade dari 59 jadi 40.

Artinya: **kalau sudah di jendela likuiditas yang benar, kepadatan tidak lagi merusak.**
Batas kepadatan baru berguna kalau Anda tetap trading di luar jendela.

## 5. Kesimpulan

1. **Hipotesis kepadatan terbukti, tapi bersyarat.** Slippage bukan akibat jumlah posisi
   per se, melainkan jumlah posisi **relatif terhadap likuiditas saat itu**.

2. **Urutan kepentingan:**
   - Pertama: **jam** (12:00–18:00 WIB) — efek terbesar, +21,63 R
   - Kedua: **batas kepadatan** — hanya relevan di luar jendela
   - Ketiga: eksekusi SL

3. **Aturan praktis yang didukung data:**
   - Trading hanya 12:00–18:00 WIB → dampak terbesar
   - Kalau terpaksa di luar jam itu, maksimal **3 posisi bersamaan**
   - 18 trade/hari saat ini terlalu padat untuk likuiditas altcoin

## Keterbatasan
- 8 hari data, satu rezim pasar
- Kepadatan dihitung dari timestamp Notion, bukan dari broker — bisa selisih beberapa menit
- Tidak ada data spread aktual per trade, jadi "likuiditas" hanya disimpulkan dari jam
- Sampel sel 10+ hanya 9 trade
