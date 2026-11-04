# Uji Grid + Averaging pada SPOT CRYPTO

Tanggal: 24 Okt 2026 | Data: 2.000 candle harian (~5,5 tahun), sumber MEXC via node Tencent
Commit: `uji_grid_crypto.py`

---

## 1. Koreksi atas uji sebelumnya

Uji pertama saya memakai **XAUUSD** dan menyimpulkan grid = bangkrut. Itu **pasar yang salah**:
grid+avg adalah metode **spot crypto**, dan crypto punya karakter berbeda (drift naik
jangka panjang, volatilitas tinggi, tanpa margin call di spot).

Uji ulang di crypto memberi hasil yang **berlawanan**.

---

## 2. Setup

| Parameter | Nilai |
|---|---|
| Modal | $500 |
| Alokasi per level | $62,5 (modal ÷ 8 level) |
| Maks level | 8 |
| Jarak antar level | 0,5 × ATR |
| TP per posisi | 0,5 × ATR |
| Fee | **0,1% per sisi** (khas spot) |
| Arah | LONG saja (beli saat turun) |

---

## 3. Hasil — 5,5 tahun, sudah termasuk fee

| Koin | Buy & Hold | DD B&H | **Grid (tanpa stop)** | DD Grid | Grid + stop 10% |
|---|---|---|---|---|---|
| BTCUSDT | +40% | 77% | **+59%** | 51% | +31% |
| ETHUSDT | −34% | 79% | **+35%** | 50% | −8% |
| SOLUSDT | **+123%** | 96% | +62% | 59% | **−77%** |
| XRPUSDT | −20% | 81% | **+44%** | 48% | −8% |
| DOGEUSDT | **−88%** | 92% | −10% | 53% | −65% |
| LINKUSDT | −77% | 90% | **+41%** | 48% | −4% |

---

## 4. Tiga temuan penting

### a) Grid mengalahkan buy & hold di 5 dari 6 koin — dengan drawdown lebih kecil

Drawdown grid 48–59% vs B&H 77–96%. Grid memotong risiko hampir separuh.

### b) Grid adalah strategi panen volatilitas, bukan strategi arah

| Kondisi pasar | Pemenang |
|---|---|
| Tren naik kuat (SOL +123%) | **B&H** |
| Sideways / turun (ETH −34%, XRP −20%, LINK −77%, DOGE −88%) | **Grid** |

Grid tidak menebak arah. Ia mengambil profit dari setiap pantulan dan memegang kas
saat harga jatuh — itu sebabnya ia unggul justru ketika pasar memburuk.

### c) Hard stop justru MERUSAK grid

| Koin | Tanpa stop | Dengan stop 10% |
|---|---|---|
| SOL | +62% | **−77%** |
| DOGE | −10% | **−65%** |
| LINK | +41% | −4% |

Alasannya: grid bertahan karena **menunggu pantulan**. Stop memaksa realisasi rugi
di dasar, lalu grid dibuka ulang dan kena lagi. Semakin ketat stop, semakin cepat
modal habis.

**Ini kebalikan dari sistem tren** — pada sistem tren, stop menyelamatkan; pada grid,
stop membunuh.

---

## 5. Batasan yang harus disadari

| Aspek | Dampak |
|---|---|
| **Drawdown ~50%** | separuh akun pernah hilang sementara — psikologis berat |
| **Survivorship bias** | 6 koin ini masih ada hari ini; koin yang mati tidak masuk hitungan |
| **Hanya LONG** | versi dua arah belum diuji |
| **Data harian** | grid intraday (5m/15m) punya karakter berbeda |
| **Likuiditas** | altcoin kecil bisa tidak terisi saat dibutuhkan |
| **Fee 0,1%** | sudah dihitung; exchange dengan fee lebih tinggi menekan hasil |

Return grid ~35–62% dalam 5,5 tahun ≈ **6–9% per tahun** dengan DD 50%.
Risk-adjusted-nya sederhana, tapi **lebih baik dari B&H** pada 5 dari 6 koin.

---

## 6. Kesimpulan jujur

**Saya salah menilai lebih dulu.** Grid+avg di spot crypto bukan penipuan — ia punya
dasar nyata: memanen volatilitas dari pasar yang cenderung mean-reverting.

Tapi klaim pemasaran tetap menyesatkan, karena:

1. **Screenshot 10 jam** menyembunyikan drawdown 50%
2. **"Passive income"** menyembunyikan bahwa ia kalah di tren kuat (SOL: kalah 61 poin dari B&H)
3. **"Drawdown sistematis"** tanpa angka — padahal DD-nya separuh akun
4. Menambahkan stop (yang terdengar aman) justru **menghancurkan** strateginya

Yang benar: grid adalah **strategi bertahan** yang butuh modal tahan banting dan
perut kuat — bukan mesin uang pasif.

---

## 7. Kalau mau dilanjutkan

Urutan uji yang masuk akal:
1. Versi **dua arah** (grid beli + grid jual) di pasar sideways
2. **Filter rezim** — hanya aktif saat volatilitas rendah
3. Uji di **15m/1h** dengan fee realistis
4. Baru demo terpisah dengan modal yang siap hilang 50%

Cara menjalankan ulang:
```bash
cd ~/warroom &&.venv/bin/python ops/uji_grid_crypto.py 1d 2000
```

---

## 8. Hasil uji filter rezim (langkah 2)

Filter: hanya jalankan grid bila `|EMA50 − EMA200| / ATR ≤ ambang`.
Semua kolom memakai jendela yang sama (mulai bar ke-200), jadi bisa dibandingkan
satu sama lain — tapi **tidak** langsung dibandingkan dengan tabel §3 yang mulai
bar ke-15.

| Koin | tanpa filter | ≤4,0 | ≤2,0 | ≤1,0 |
|---|---|---|---|---|
| BTC | +44% / 57% | +37% / 56% | +24% / 54% | +21% / 37% |
| ETH | +10% / 62% | +20% / 62% | **+53% / 55%** | +40% / 52% |
| SOL | +24% / 88% | +65% / 73% | +46% / 74% | +44% / 57% |
| XRP | +44% / 50% | +40% / 50% | **+63% / 50%** | +51% / 26% |
| DOGE | +7% / 48% | −1% / 51% | +32% / 41% | +25% / 28% |
| LINK | +28% / 62% | +26% / 64% | **+44% / 51%** | **+60% / 42%** |
| **Rata-rata** | **+26%** | **+31%** | **+44%** | **+40%** |

*(format: return / max drawdown)*

### Yang membaik
- Rata-rata return **+26% → +44%** (ambang 2,0)
- Drawdown turun di 4 dari 6 koin: SOL 88→74%, LINK 62→51%, DOGE 48→41%, BTC 57→54%

### Yang memburuk
- **BTC justru turun** (+44% → +24%): filter memotong profit di tren naik terkuat
- ETH pada ambang 4,0 hampir tidak berubah

### Peringatan metodologis
Memilih ambang 2,0 karena ia menang **di data ini** adalah *curve fitting*.
Klaim yang jujur: **filter rezim membantu secara umum** (+26% → +31…44%),
bukan "2,0 adalah nilai optimal". Untuk menentukan ambang yang benar perlu
walk-forward out-of-sample, bukan satu kali jalan.

### Kesimpulan tambahan
Filter rezim **mengurangi** kelemahan utama grid (drawdown di pasar tren) tanpa
membunuh sisi positifnya. Ini kandidat yang layak diuji lebih lanjut — berbeda
dengan hard stop yang terbukti merusak.

---

## 9. Walk-forward: UJIAN PENENTU — hasilnya GAGAL

Latih di 60% data awal, pilih ambang terbaik **hanya dari data latih**, lalu
terapkan ke 40% data terakhir yang belum pernah dilihat.

| Koin | ambang dipilih | latih | **uji (OOS)** | uji tanpa filter | selisih |
|---|---|---|---|---|---|
| BTC | ≤4,0 | +27% | +4% | +10% | **−6%** |
| ETH | ≤1,0 | +19% | +21% | +4% | +17% |
| SOL | ≤4,0 | +48% | +6% | +6% | 0% |
| XRP | ≤1,0 | +32% | +4% | +7% | **−3%** |
| DOGE | ≤1,5 | +25% | −22% | −47% | +25% |
| LINK | ≤0,5 | +6% | +9% | +14% | **−5%** |
| **Rata-rata** | — | — | **+4%** | **−1%** | **+5%** |

### Kenapa ini gagal

1. **Tidak konsisten** — 3 koin membaik, 3 koin memburuk. Rata-rata +5 poin
   didorong hampir seluruhnya oleh DOGE (yang tetap rugi, hanya lebih sedikit).
2. **Ambang yang dipilih kacau** — ≤4,0 / ≤1,0 / ≤1,5 / ≤0,5. Kalau ada optimum
   yang nyata, pilihan antar koin akan mengumpul di sekitar nilai yang sama.
   Sebaran acak ini tanda khas **overfitting**.
3. **Latih jauh lebih baik dari uji** — latih +6…+48%, uji −22…+21%. Performa
   masa lalu tidak berlanjut.
4. **Tanpa filter pun rugi** di periode uji (rata-rata −1%).

### Artinya

Angka **+44%** di §8 sebagian besar adalah **curve fitting**. Ekspektasi
out-of-sample yang jujur: **sekitar +4% dalam 2,2 tahun** — praktis nol, dengan
drawdown yang tetap puluhan persen.

---

## 10. VERDICT AKHIR: grid+avg TIDAK lolos

| Tahap uji | Hasil |
|---|---|
| Grid crypto tanpa filter | +26% rata-rata (in-sample) |
| + filter rezim | +44% (in-sample) |
| **Walk-forward out-of-sample** | **+4%, tidak konsisten, ambang tak stabil** |

**Keputusan: tidak dilanjutkan ke akun nyata.** Bukan karena grid itu penipuan —
mekanismenya nyata — tapi karena **tidak ada edge yang bisa diandalkan** setelah
diuji dengan benar.

Yang tetap benar dari analisa awal: klaim pemasaran "passive income" dari grid
tidak berdasar, karena hasil in-sample-nya pun tidak bertahan di data baru.
