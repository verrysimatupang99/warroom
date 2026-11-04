# TEMUAN KRITIS: API pakai harga FUTURES, EA trading SPOT (23 Okt 2026)

## Ringkasan
Filter spread sudah diperbaiki (40 -> 350 pts) dan sekarang lolos. Tetapi EA tetap
menolak semua sinyal, dan penyebabnya jauh lebih mendasar:

```
API  /forex/levels : price 4008.1   (sumber: Yahoo GC=F = GOLD FUTURES)
MT5  XAUUSDm bid   : 3996.057       (sumber: Exness SPOT)
selisih            : $12.04
```

Jarak SL strategi hanya **$2.53**. Artinya selisih sumber harga **~4,8x lebih besar
dari jarak SL**. SL/TP dari API tidak ada artinya untuk simbol yang dieksekusi EA.

## Bukti

1. Engine mengambil data dari futures:
   ```
   GET https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=5m&range=1d
   ```
   `GC=F` adalah kontrak berjangka emas, bukan XAUUSD spot.

2. EA memakai bid/ask broker (XAUUSDm). Log EA:
   ```
   Sinyal SHORT dilewati: Harga pasar saat ini (3996.057) sudah berada di bawah
   target TP (4003.55).
   ```
   Bid **3996.057 identik dari 20:58 sampai 21:04** -> pasar tutup (Jumat 21:00 UTC).

3. API tetap mengeluarkan sinyal OK dengan harga 4008.1 dari futures yang masih
   punya harga terakhir, sementara broker sudah tidak mengirim tick.

## Konsekuensi terhadap insiden 21 Okt (6 trade, -$43.02)

Ini menjelaskan trade #6 secara utuh:
- API mengirim `entry 4126.98 sl 4122.98 tp1 4132.38` (dari futures)
- EA mengeksekusi pada `ask 4132.146` (spot broker)
- Selisih ~$5 membuat `risk` melebar 3.00 -> 9.17 dan `reward` menyusut
  5.40 -> 0.23 (R:R 1:0.026) lalu rugi $91.52

Selama sumber harga berbeda, R1 (penjaga R:R) akan **terus menolak** sinyal —
itu perilaku benar, tetapi berarti EA tidak akan pernah trading secara sehat.

## Rekomendasi: R4 — satu sumber kebenaran (harga broker)

**API tidak lagi mengirim harga absolut.** API mengirim niat + jarak:

```json
{
  "status": "OK",
  "side": "SHORT",
  "risk": 2.53,          // jarak SL dalam satuan harga
  "reward": 4.55,        // jarak TP
  "generated_at": 1792786235
}
```

**EA menghitung sendiri dari harga fill broker:**

```cpp
double entry = (side == "LONG") ? ask : bid;
double sl    = (side == "LONG") ? entry - risk : entry + risk;
double tp1   = (side == "LONG") ? entry + reward : entry - reward;
```

Keuntungan:
- selisih futures vs spot tidak lagi merusak SL/TP
- R:R selalu sesuai desain (1.8) pada harga yang benar-benar dieksekusi
- penjaga R1 menjadi lapis kedua, bukan satu-satunya penahan

Catatan: ATR yang dipakai menghitung `risk` masih dari futures. Untuk jarak relatif
ini jauh lebih toleran daripada harga absolut, tetapi idealnya ATR juga dari broker.

## Status operasional saat ini

| Item | Status |
|---|---|
| Filter spread (350 pts) | ✅ diperbaiki, sinyal lolos filter |
| Pasar XAUUSD | ⛔ TUTUP (Jumat 21:00 UTC) — bid beku 3996.057 |
| EA | aktif, menerima sinyal, menolak karena TP salah sisi |
| Laya (job terjadwal) | aktif, verdict segar tiap 60 detik |
| `/forex/levels` | 0,14 detik |

Tidak ada trading yang mungkin terjadi sampai pasar buka (Senin). Ini waktu yang
tepat untuk mengerjakan R4 tanpa risiko posisi terbuka.

## Sisa pekerjaan
- **R4** satu sumber kebenaran harga (rekomendasi utama, lihat di atas)
- R5 Laya belum menerima konteks akun
- R7 `min_rrr` belum penjaga keras
- ATR sebaiknya juga dari feed broker
