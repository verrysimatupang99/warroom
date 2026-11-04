# Laya keluar dari jalur panas + timeout EA (23 Okt 2026)

## 1. Timeout WebRequest EA jadi parameter
```
InpHttpTimeoutMs = 15000   (sebelumnya hardcode 3000)
```
Compile: `0 errors, 0 warnings`, `.ex5` 56.148 B.

## 2. Inferensi Laya dipindah ke job terjadwal

### Arsitektur baru
```
systemd timer (60s)
   └─> warroom-laya-verdict.service (proses terpisah, MemoryMax=2G, CPUQuota=200%)
         └─> ops/laya_verdict_job.py
               ├─ ambil candle M5 + indikator
               ├─ nilai LONG dan SHORT untuk sesi berjalan
               └─ tulis atomik -> /var/lib/warroom/laya_verdict.json

API /forex/levels
   └─> multi_session_laya.evaluate_laya()
         └─> laya_verdict.ambil(side, session, min_confidence)   [baca berkas, mikrodetik]
```

### Semantik fail-closed (`laya_verdict.ambil`)
| Kondisi | Hasil |
|---|---|
| berkas belum ada | BLOKIR |
| umur > TTL 180s | BLOKIR |
| sesi cache != sesi berjalan | BLOKIR |
| arah tidak ada di cache | BLOKIR |
| verdict tak dikenali | BLOKIR |
| EXECUTE p < ambang 0.60 | BLOKIR |
| EXECUTE p >= ambang, segar, sesi cocok | LOLOS |

### Hasil terukur
| | Sebelum | Sesudah |
|---|---|---|
| `/forex/levels` cold | **30 detik** | **0,14 detik** |
| `/forex/levels` warm | 1,5–2,2 detik | **0,14–0,21 detik** |
| RSS model di proses API | ~1 GB | **0** (di proses terpisah) |
| Timeout EA | 3 detik (selalu gagal saat cold) | 15 detik (parameter) |

Job terverifikasi berjalan: verdict `ts` bergerak 1792786193 -> 1792786333 dalam
100 detik, `systemctl show -p Result` = `success`, timer `active`.

Verdict nyata: `LONG EXECUTE p=0.8092`, `SHORT EXECUTE p=0.8120` (20,8 detik/proses).

Sinyal yang dihasilkan API setelah perubahan:
```json
{"status":"OK","side":"LONG","generated_at":1792786235,
 "levels":{"entry":4012.7,"sl":4010.17,"tp1":4017.25,"tp2":4020.89,
           "risk":2.53,"reward":4.55},"rrr":1.8,"confidence":0.8092}
```

Tes: 148 lulus, `test_laya_fail_closed.py` 11 kasus. ruff bersih.
Commit `4b6a84a`, deploy build `4b6a84a-20261023T201017Z`, push `1de2873..4b6a84a`.

---

## 3. TEMUAN BARU: EA tidak bisa trading karena filter spread

EA **sudah menerima sinyal OK** setiap 5 detik, tetapi menolak semuanya:

```
Sinyal dilewati: Spread pasar saat ini (240 pts) melebihi batas toleransi
(40 pts). Melindungi dari slippage.
```

### Analisis unit
- Harga XAUUSDm di riwayat: `4132.146` -> **3 desimal** -> `digits=3` -> `point=0.001`
- Spread 240 pts = 240 x 0.001 = **$0,240**
- Batas `InpMaxSpreadPts = 40` = **$0,040**

Spread normal XAUUSD di Exness berada di kisaran $0,15–$0,35 (150–350 pts).
Artinya batas 40 pts **tidak mungkin tercapai** dan EA akan **selalu** menolak.

### Mengapa 6 trade 21 Okt bisa terjadi?
EA yang dipakai saat itu adalah build lama (20.573 B, tanpa `InpUseRiskSizing`).
Nilai `InpMaxSpreadPts` pada build lama tidak diketahui karena berkasnya sudah
tertimpa; kemungkinan besar nilainya jauh lebih longgar.

### Rekomendasi
Naikkan `InpMaxSpreadPts` ke nilai realistis untuk gold 3-desimal, mis.
**350 pts ($0,35)** — cukup menahan spread pelebaran saat rollover/news tetapi
tidak memblokir pasar normal.

**Belum diubah** — ini parameter risiko, jadi menunggu keputusan owner.
Selama nilainya 40, EA akan terus menolak semua sinyal (aman, tapi tidak trading).

## Sisa yang belum dikerjakan
- R4 satu sumber kebenaran SL/TP
- R5 Laya belum menerima konteks akun
- R7 `min_rrr` belum penjaga keras
- `InpMaxSpreadPts` (lihat di atas)
