# Analisa Akun Threads — @johnnnlenon

Tanggal: 24 Okt 2026 | Sumber: threads.com/@johnnnlenon + lynk.id/cuanwithaiotrade

---

## 1. Profil

| Field | Isi |
|---|---|
| Nama tampilan | **John Lenon, S.H.** |
| Handle | `@johnnnlenon` |
| Bio | "Membantu lebih dari **+5000 member** trading menggunakan sistem Automated crypto" |
| Tautan | `lynk.id/cuanwithaiotrade` |
| Pengikut | 120 |

**Produk yang dijual:**

> "Segera Bergabung di VIP Group member untuk belajar menghasilkan dollar dengan
> AI Crypto Automated Trading"
>
> "Passive Income dari belajar Crypto Automated Trading"
> **IDR 100.000** (dari IDR 999.000)

Model bisnisnya jelas: **keanggotaan grup berbayar**, bukan pengelolaan dana.

---

## 2. Isi postingan (yang terbaca publik)

| Umur | Isi ringkas |
|---|---|
| 10 jam | "hanya dalam 10 jam perjalanan, crypto automated mampu eksekusi disaat kita tidur" |
| 3 hari | "Trading sekarang tidak perlu menebak, **beli dibawah jual diatas** konsisten, automate 24 jam" |
| 4 hari | "TF 1 & 2 jam **terlalu padat transaksi buy n sell** dengan settingan memadai sehingga bisa maksimalkan profit" |
| 17 Okt | "gw ikutin engine ini dari 2024 buat trade di market spot dengan **metode avg+grid**, dengan perhitungan drawdown sistematis, **udah dibacktest dan ini real trade**" (107 suka) |

---

## 3. Temuan kunci: **avg + grid**

Satu frasa di postingan 17 Oktober mengubah seluruh penilaian:

> "metode **avg+grid**"

Ini persis kategori yang masuk **daftar hitam** dalam riset EA gratis kita:

| Pola | Kenapa berbahaya |
|---|---|
| **Averaging** | menambah posisi saat rugi → risiko membesar saat salah |
| **Grid** | memasang order berjenjang → semua level terisi saat tren melawan |
| Gabungan | kurva ekuitas **mulus sampai tidak** — kerugian tersembunyi di floating |

Ciri khas sistem grid:
- **Terlihat hebat dalam jendela pendek** (10 jam, 3 hari, 4 hari — persis yang diposting)
- **Win rate tinggi** karena hampir semua posisi akhirnya tertutup profit kecil
- **Kerugian jarang, tapi fatal** — satu tren panjang menghabiskan akun
- **Backtest terlihat bagus** kalau periode ujinya kebetulan sideways

Postingan "10 jam perjalanan" bukan kebetulan — itu jendela di mana grid selalu tampak
sempurna.

---

## 4. Yang diklaim vs yang bisa diverifikasi

| Klaim | Bisa diverifikasi? |
|---|---|
| "+5000 member" | ❌ tidak ada bukti |
| "udah dibacktest" | ❌ tidak ada tautan backtest |
| "ini real trade" | ❌ tidak ada tautan statement (Myfxbook/FTMO/explorer) |
| "drawdown sistematis" | ❌ tidak ada angka drawdown |
| "AI Crypto Automated" | ⚠️ tidak jelas AI-nya di mana; metode intinya grid |

Pola umum: **klaim kuantitatif tanpa satu pun angka yang bisa dicek.**
Tidak ada alamat wallet on-chain, tidak ada akun verifikasi pihak ketiga.

Gelar "S.H." (Sarjana Hukum) ditampilkan di nama — relevansinya nol untuk kompetensi
trading, tapi berfungsi sebagai *authority bias*.

---

## 5. Steel-man: kapan grid benar-benar masuk akal

Supaya adil, grid **bukan** otomatis penipuan. Grid bisa bekerja bila:

1. **Pasar sideways** dan ada filter rezim yang mendeteksi itu
2. **Batas drawdown keras** — berhenti di N level, bukan terus menambah
3. **Sizing yang tahan** skenario terburuk (semua level terisi + tren lanjut)
4. **Modal cukup** untuk menahan floating tanpa margin call

Tanpa empat itu, grid = martingale dengan nama lain.

Yang tidak terlihat dari postingan: apakah empat syarat itu ada. Dan klaim
"drawdown sistematis" tanpa angka tidak menjawabnya.

---

## 6. Hubungan dengan pekerjaan kita

**Ini cermin dari apa yang justru kita hindari.**

| | Akun ini | War Room kita |
|---|---|---|
| Metode | avg + grid | sinyal + guard berlapis |
| Validasi | klaim "sudah backtest" | 1.046 tes otomatis + uji walk-forward |
| Bukti | tidak ada tautan | `trades_all.csv`, `fills.csv`, `panels.json` |
| Metrik risiko | "sistematis" (tanpa angka) | R, SL%, drawdown terukur |
| Sumber pendapatan | iuran member | hasil trading |
| Uji hipotesis | tidak ada | 2 hipotesis **ditolak** hari ini karena data |

Hari ini kita membuang dua ide (SNR, filter jam) karena tidak lolos uji statistik.
Akun ini menjual ide yang **tidak bisa diuji dengan sampel pendek** justru karena
kerugiannya tersembunyi di floating.

---

## 7. Kalau tetap ingin mempelajari

Yang **layak** dipelajari dari akun seperti ini:
- Cara mereka memasarkan (bukan strateginya)
- Struktur funnel: konten pendek → bio → lynk.id → VIP group berbayar

Yang **jangan** diadopsi:
- Metode avg+grid tanpa batas drawdown keras
- Klaim performa dari jendela 10 jam
- "Passive income" sebagai kerangka berpikir

**Kalau ingin menguji klaim mereka secara adil:** minta tautan statement
(Myfxbook, FXBlue, atau explorer on-chain) dengan riwayat **minimal 12 bulan**
yang mencakup satu tren besar. Sistem grid yang jujur akan punya jawabannya;
yang tidak, akan menghindar.

---

## 8. Kesimpulan

Akun ini menjual sistem **avg+grid** lewat grup berbayar, dengan klaim performa
tanpa bukti yang bisa diverifikasi. Itu bukan bukti penipuan — tapi juga bukan
bukti kompetensi.

Untuk tujuan kita, nilainya **negatif**: mempelajari metodenya berisiko menanamkan
kebiasaan yang justru sedang kita buang (menambah posisi saat salah, menyembunyikan
rugi di floating).

Yang bisa diambil hanya pelajaran pemasaran, bukan trading.
