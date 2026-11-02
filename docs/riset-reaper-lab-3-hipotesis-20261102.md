# Riset Reaper — Lab 3 Hipotesis (Putaran 2)

Tanggal: 2026-11-02
Status: **NO-GO** untuk ketiga hipotesis. Tidak ada yang layak masuk uang nyata.
Data: `data/hist/PAXGUSDT_15m.csv` (proxy emas 24/7), 2021–2026.
Biaya: spread + komisi disimulasikan per trade (2,5–6,6% dari R).

## Ringkasan hasil (hari kerja saja)

| Hipotesis | n | Win % | Ekspektansi | PF | t-stat | Max DD |
|---|---|---|---|---|---|---|
| A. Momentum antar-sesi | 1530 | 37,1 | −0,054R | 0,91 | −1,45 | 80,0% |
| B. Opening range NY | 827 | 53,0 | −0,003R | 0,99 | −0,09 | 26,2% |
| C. Trend sesi | 4640 | 32,5 | −0,117R | 0,84 | −5,76 | 99,8% |

Tidak satu pun lolos gate. B adalah yang paling dekat ke titik impas, tetapi
"dekat nol" bukan edge — itu hanya strategi yang belum terbukti merugi.

## Yang ditemukan di tengah jalan (dan mengubah kesimpulan)

### 1. PAXG tidak punya padanan weekend di XAUUSD

PAXG diperdagangkan 7 hari; XAUUSD tutup Jumat 22:00 – Minggu 22:00 UTC.
Hasil awal yang dicampur weekend tidak transferable. Semua angka di atas
sudah difilter ke hari kerja.

### 2. Dua bug di kode sendiri, bukan di pasar

- **Filter range pembukaan 0,7× ATR** menghasilkan nol sinyal. Setelah dicek,
  range jam 13:00–14:00 UTC wajar bernilai 1,4–2,2× ATR harian karena itu jam
  paling volatil emas. Ambang awalnya salah tulis, bukan temuannya.
- **Cek breakout pada candle terakhir range** tidak akan pernah terpicu: close
  sebuah candle selalu berada di dalam [low, high] miliknya sendiri. Diperbaiki
  jadi dua tahap — simpan level, lalu cari penembusan pada candle berikutnya.

Kedua hal ini bukan detail. Tanpa ditemukan, "nol trade" akan terbaca sebagai
"strategi bagus tapi tidak pernah kena", dan bug breakout akan terbaca sebagai
"NO-GO" padahal kodenya belum pernah jalan.

### 3. Uji cermin (arah dibalik)

| | Ekspektansi kotor | Ekspektansi bersih |
|---|---|---|
| A asli | −167R | — |
| A cermin | −126,8R | −242,7R |
| C asli | −675R | — |
| C cermin | −240,1R | −739,0R |

Versi cermin juga negatif. Artinya kerugian **bukan** karena arah sinyal
terbalik — biaya transaksi sendirian sudah lebih besar dari selisihnya. Ini
mengeliminasi satu penjelasan yang tampak meyakinkan, bukan menawarkan yang baru.

### 4. Bias bull market pada emas — dan mengapa bukan itu penyebabnya

Emas naik 2,05× selama periode uji. Kecurigaan pertama: long B menang hanya
karena tren naik (beta), bukan karena strukturnya.

Diuji dengan korelasi hasil strategi harian terhadap return harian emas:

**r = −0,026** (praktis nol).

Jadi B **tidak** mengambil eksposur arah pasar. Ia tidak menumpang bull market —
tetapi juga tidak menang karena strukturnya. Nol di dua sisi tetap nol.
Catatan: ini mengoreksi dugaan awal bahwa long = beta; koreksinya tidak
menyelamatkan strategi.

### 5. Asimetri long/short tidak bertahan pada grid

Titik `rr=1.5, jendela=24` memperlihatkan long +0,046R (PF 1,11) lawan short
−0,050R. Karena parameter itu dipilih sebelum melihat hasil, dilakukan grid
4×4 (rr × jendela):

- Long bergerak dari **−0,05R sampai +0,05R** tergantung sel.
- Short bergerak di rentang serupa.
- **Tidak ada satu pun sel dengan |t| > 2.**

Asimetri yang tampak adalah artefak pemilihan satu titik. Ini persis jenis
kesalahan yang akan lolos kalau grid tidak dijalankan.

## Keputusan

**NO-GO.** Tidak ada hipotesis yang diusulkan untuk uang nyata, dan tidak ada
pelonggaran gate untuk memaksakannya lolos.

Yang *tidak* boleh dilakukan ke depan: menurunkan ambang gate, memperketat
filter setelah melihat hasil, atau memilih parameter terbaik dari grid lalu
melaporkannya sebagai temuan.

## Langkah berikut

1. Uji data XAUUSD asli (bukan PAXG) — biaya dan jam sesi berbeda, dan itu
   variabel yang benar-benar relevan untuk Gold Reaper.
2. Hipotesis baru harus datang dari mekanisme pasar yang bisa dijelaskan lebih
   dulu (misal perilaku likuiditas di sekitar fixing London), bukan dari
   pencarian parameter.
3. Wave 4 (uang nyata) tetap tertahan sampai ada satu hipotesis yang lolos gate
   tanpa disentuh setelah hasilnya terlihat.
