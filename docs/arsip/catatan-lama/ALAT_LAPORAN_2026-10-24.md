# Alat bantu: riwayat verdict + laporan kesiapan (24 Okt 2026)

Dua alat supaya keputusan ambang Laya tidak lagi berdasarkan cuplikan, dan
pemantauan harian tidak perlu perintah manual berlapis.

## 1. Riwayat verdict (`ops/laya_verdict_job.py`)

Setiap siklus job menambah 2 baris ke
`/var/lib/warroom/laya_verdict_log.csv`:

```
ts,session,price,atr,side,choice,confidence
1792847006,NEW_YORK,4007.9,2.37,LONG,SKIP,0.1493
1792847006,NEW_YORK,4007.9,2.37,SHORT,SKIP,0.1967
```

- header ditulis sekali
- rotasi: menyisakan 2000 baris bila melewati 5000
- kegagalan tulis tidak menggagalkan job (hanya warning)

Alasan: ambang `laya_min_confidence` hanya bisa dinilai dengan **sebaran**
confidence nyata selama beberapa hari, bukan satu pembacaan.

## 2. Laporan kesiapan (`ops/laporan-forex.py`)

Satu perintah, hanya membaca:

```bash
cd ~/warroom && .venv/bin/python ops/laporan-forex.py
```

Isi laporan:
1. **EA/MT5** — heartbeat, akun, ekuitas, posisi, bid/ask/spread, `atr_m5`/`ema*_m5`
2. **Sinyal** — status, `indicator_source` (`broker:mt5` vs `yahoo:GC=F`),
   `blocked_reason`
3. **Sebaran verdict** — per arah: n, min, median, max, berapa yang >= ambang
4. **Simulasi ambang** 0,50 / 0,55 / 0,60 / 0,65 / 0,70 — persen sinyal lolos

Contoh keluaran nyata (24 Okt, pasar tutup, sampel masih kecil):
```
terhubung : True (heartbeat 5 detik)
bid/ask   : 3996.057 / 3996.317 | spread 260 pts
atr_m5    : 2.452 | ema9 3996.104 | ema21 3996.771
status    : WAITING_SETUP | sumber indikator: broker:mt5
blokir    : Laya SKIP p=0.197 (ambang 0.60)
sebaran   : LONG median 0.149 | SHORT median 0.197
simulasi  : ambang 0.50 -> 0.0% (0/4) ... 0.70 -> 0.0%
```

Catatan kejujuran: sampel 4 baris ini **belum cukup** untuk memutuskan ambang.
Perlu data saat pasar buka (Senin) minimal beberapa jam agar sebarannya berarti.

## Verifikasi
| Cek | Hasil |
|---|---|
| `test_laya_akun.py` | **7 lulus** (2 kasus baru: header sekali + append, gagal tulis aman) |
| pytest core + api | **272 lulus** |
| ruff | bersih |
| commit / push | `976848f` / `5cf67f4..976848f` |

## Cara pakai Senin
1. Jalankan laporan setelah pasar buka beberapa jam:
   `.venv/bin/python ops/laporan-forex.py`
2. Lihat baris `sumber indikator` — harus `broker:mt5`.
3. Lihat simulasi ambang: pilih nilai yang memberi peluang sinyal wajar
   **tanpa** mengorbankan arti gerbang.
4. Bila EA mulai trading, cek log EA di VM untuk baris
   `Level relatif dihitung dari broker` sebagai bukti jalur R4 aktif.
