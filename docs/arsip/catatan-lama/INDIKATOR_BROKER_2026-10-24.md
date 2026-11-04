# Indikator dari broker, Yahoo jadi cadangan (24 Okt 2026)

## Masalah yang ditutup
Engine **selalu** mengambil indikator dari Yahoo `GC=F` (kontrak berjangka emas),
padahal EA mengeksekusi `XAUUSDm` (spot). Selisih harga terukur $11-12 sementara
jarak SL strategi hanya ~$2,5 — akar trade #6 (21 Okt, rugi $91,52).

## Perubahan

### 1. `engine.generate_forex_levels(symbol, mode, snapshot=None)`
Urutan sumber:
1. **snapshot broker** (bila lengkap) -> `indicator_source = "broker:mt5"`
2. Yahoo `GC=F` -> `indicator_source = "yahoo:GC=F"`

`_indikator_dari_snapshot()` memetakan:
| Snapshot broker | Indikator |
|---|---|
| `bid` | `price` |
| `atr_m5` | `atr14` |
| `ema9_m5` / `ema21_m5` | `ema9` / `ema21` |
| `high_12` / `low_12` | `recent_high` / `recent_low` |

Snapshot ditolak (jatuh ke Yahoo) bila field wajib hilang atau nilainya `<= 0`.
Tidak ada nilai default: ATR nol akan menghasilkan jarak SL nol.

### 2. `multi_session_laya.py`
Menerima `recent_high`/`recent_low` dari snapshot. Daftar candle hanya wajib bila
keduanya tidak ada. Ini menghapus ketergantungan pada 15 candle Yahoo saat data
broker tersedia.

### 3. `routers/tencent.py`
Snapshot hanya dipakai bila telemetri **<= 60 detik** dan `atr_m5` terisi.
EA mengirim tiap ~5 detik, jadi normalnya selalu segar; bila EA mati/pasar tutup
panjang, otomatis kembali ke Yahoo dan itu terlihat di `indicator_source`.

## Bukti

### Endpoint produksi (sekarang)
```
status WAITING_SETUP | sumber broker:mt5 | price 3996.057 | trend BEARISH
blocked: Laya SKIP p=0.197 (ambang 0.60)
```
Harga 3996.057 = bid broker (bukan 4008 dari futures).

### Jalur OK dengan snapshot nyata
```
snapshot        : bid 3996.057  atr 2.452
status          : OK
side            : SHORT
indicator_source: broker:mt5
price           : 3996.057
atr             : 2.452
trend           : BEARISH
risk            : 2.7
reward          : 4.86
levels_mode     : relative
R:R             : 1.8
```

## Verifikasi
| Cek | Hasil |
|---|---|
| `test_indikator_broker.py` | **9 lulus** |
| pytest core + api | **270 lulus** |
| ruff | bersih |
| deploy | build `5cf67f4-20261024T125317Z` |
| commit / push | `5cf67f4` / `4d0c26a..5cf67f4` |

## Dampak
- Harga acuan kini **instrumen yang benar-benar dieksekusi**.
- Jarak `risk`/`reward` dihitung dari ATR broker (2,452) — bukan futures (2,371).
- Ketergantungan pada Yahoo turun menjadi cadangan saja.
- Setiap respons menyebut sumbernya, sehingga tidak ada lagi "data dari mana?"
  yang tak terjawab saat post-mortem.

## Sisa
1. **Ambang Laya** (0,60 vs verdict 0,10-0,20) - keputusan owner setelah pasar buka.
2. **Verifikasi live jalur EA relatif** ("Level relatif dihitung dari broker") -
   belum muncul karena belum ada sinyal OK dari produksi (Laya memblokir).
3. `exec_powershell` pada respons telemetri masih ada (mati, tidak dieksekusi EA)
   dan berisiko bila kelak dipakai komponen lain.
