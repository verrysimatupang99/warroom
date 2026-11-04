# R5 deployed — Laya kini menilai akun, bukan hanya pasar (24 Okt 2026)

## Masalah
`market_state` yang dikirim ke Laya hanya berisi:
```
symbol, side, session, price, atr, setup
```
Tidak ada balance, equity, floating PnL, atau jumlah posisi. Model menilai
"apakah PASAR aman", bukan "apakah trade ini pantas untuk UKURAN AKUN".

## Perubahan (`ops/laya_verdict_job.py`)

1. `ambil_akun()` — GET `/api/v1/tencent/mt5/status`, timeout 5 detik.
   Kegagalan tidak fatal: job tetap menulis verdict dan menandainya jujur.
2. `susun_konteks_akun()` — meringkas telemetri:
   | Field | Isi |
   |---|---|
   | `akun_tersedia` | EA terhubung atau tidak |
   | `balance_usd`, `equity_usd` | saldo |
   | `floating_pnl_usd` | PnL mengambang |
   | `floating_pct_balance` | floating / balance (%), None bila balance 0 |
   | `posisi_terbuka` | jumlah posisi |
   | `free_margin_usd`, `win_rate_pct`, `net_pnl_usd` | konteks tambahan |
3. Konteks digabung ke `market_state` yang dinilai model, dan ditulis ke berkas
   verdict sebagai blok `akun` supaya keputusan bisa diaudit.
4. Pertanyaan & kriteria diperluas:
   - EXECUTE: risiko terhadap balance wajar **dan** tidak ada posisi yang menahan risiko
   - SKIP: termasuk floating loss besar, margin tipis, sudah ada posisi terbuka

## Bukti jalankan job nyata
```
konteks akun: {'akun_tersedia': True, 'balance_usd': 456.98, 'equity_usd': 456.98,
               'floating_pnl_usd': 0.0, 'floating_pct_balance': 0.0,
               'posisi_terbuka': 0, 'free_margin_usd': 456.98,
               'win_rate_pct': 66.7, 'net_pnl_usd': -43.02}
LONG  -> SKIP p=0.1007
SHORT -> SKIP p=0.1437
```

API membaca hasilnya pada permintaan berikutnya:
```
WAITING_SETUP | Laya SKIP p=0.144 (ambang 0.60, umur 37s/180s) side=SHORT sesi=LONDON
```

## Perubahan perilaku yang perlu diperhatikan
Sebelum konteks akun masuk: `EXECUTE p=0.546`.
Setelah konteks akun masuk: `SKIP p=0.10-0.14`.

Model sekarang melihat akun sudah **-43,02** dari 6 trade. Lebih konservatif —
sesuai maksud R5 — tetapi pergeseran sebesar ini perlu diamati setelah pasar buka,
karena bisa berarti verdict lama (tanpa konteks akun) memang terlalu permisif.

## Verifikasi
| Cek | Hasil |
|---|---|
| `test_laya_akun.py` | **5 lulus** (lengkap, tanpa telemetri, EA putus, balance 0, positions bukan list) |
| pytest core | **153 lulus** |
| ruff | bersih |
| timer memakai kode baru | `akun` hadir, `ts` bergerak dalam 75 detik |
| commit / push | `897c64a` / `5aecb3b..897c64a` |

## Sisa pekerjaan
- **R7** — `min_rrr` belum jadi penjaga keras di sisi strategi
- ATR masih dari `GC=F`; jarak relatif lebih toleran, tetapi idealnya dari broker
- Ambang `laya_min_confidence = 0.60` vs verdict saat ini 0.14 — keputusan owner
  setelah pasar buka (Senin)
