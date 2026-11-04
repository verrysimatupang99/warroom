# Forex — Laya middleware & insiden API beku (23 Okt 2026)

## 1. Permintaan owner
1. Laya middleware berjalan **di server ini** (bukan Azure).
2. `InpUseRiskSizing` dikembalikan ke **false** (lot tetap 0.1 sesuai kebijakan owner).

Keduanya sudah dikerjakan.

## 2. EA: sizing dikembalikan ke lot tetap
`/srv/private/WarRoom_AutoTrader.mq5`:
`input bool InpUseRiskSizing = false;` — risk-sizing tetap ADA sebagai opsi, tetapi
default OFF sehingga perilaku kembali ke lot tetap 0.10 seperti keputusan owner.
(Catatan: EA tetap perlu di-compile ulang di MT5 agar perubahan ini aktif.)

## 3. `laya_sentinel.py` diperbaiki: berhenti menampilkan angka karangan
Sebelumnya: `last_verdict="STANDBY"`, `laya_confidence=0.92`, `bias_score=0.0`,
`active_headlines_count=6` — semuanya konstanta yang disajikan lewat
`/forex/sentinel` dan `/forex/bias` seolah hasil analisis AI.

Sekarang:
- `last_verdict="BELUM_DIANALISIS"`
- `laya_confidence=None` (tidak diukur, bukan 0)
- `bias_status="TAK_DIKETAHUI"`, `bias_score=None`
- `active_headlines_count=0`
- `get_bias()` menambah `dinilai: bool` + `catatan` dan TIDAK lagi menyamarkan
  `None` menjadi `0.0`.
- Blackout **tetap nyata** (dibaca dari kalender event di `blackout.txt`).

## 4. Middleware Laya nyata
- `services/api/src/warroom_api/laya_forex.py` — menyusun konteks dari telemetri EA
  (balance/equity/floating/posisi) + sinyal level (entry/sl/tp/atr/tren), lalu menilai
  dengan model.
- `services/api/src/warroom_api/laya_cli.py` — proses terpisah untuk inferensi.
- Endpoint (dijaga token EA/admin):
  - `GET /api/v1/tencent/forex/laya`
  - `GET /api/v1/tencent/forex/laya/status`
- `packages/core/pyproject.toml`: `laya` didaftarkan sebagai extra `forex`.
  Sebelumnya TIDAK terdaftar, sehingga `uv sync` menghapusnya dari venv.

### Bukti inferensi nyata (sebelum dimatikan)
```
konteks -> LONG, tren BULLISH, entry 4029.90, SL 4023.27, jarak 6.63, ATR 5.17
verdict -> tersedia=True, SKIP, keyakinan 0.2455 (ambang 0.60) -> tidak layak
```
Model benar-benar dipanggil dan memberi verdict berbeda dari klaim "HEALTHY 0.92".

## 5. INSIDEN: Laya menjatuhkan seluruh API (dan perbaikannya)

### Gejala
Setelah endpoint `/forex/laya` dipanggil:
- `GET /api/v1/build` balas **000** (tidak merespons) selama berjalan,
- listen backlog uvicorn penuh (13),
- `laya_cli` memakai **RSS 1,1 GB**, API 34 MB.

### Penyebab (dua lapis)
1. **Model terlalu besar untuk server ini.** Total RAM 14,8 GB tetapi swap 2 GB
   **penuh 100%**; model 421M + torch mendorong sistem ke swap sehingga semua proses
   tersendat. `asyncio.to_thread` tidak menolong (beban CPU+memori, bukan I/O).
2. **Bukan hanya Laya.** Ditemukan bug terpisah: `/forex/levels` menerima
   `status="WAITING_SETUP"` dari engine lokal — itu **jawaban sah** ("belum ada setup")
   — tetapi kode hanya menerima `status == "OK"`, sehingga jatuh ke fallback Tencent
   yang menggantung. Akibatnya endpoint levels sendiri bisa membekukan API
   (terukur: hang >25 s, lalu API balas 000).

### Perbaikan
1. `/forex/levels` mengembalikan status apa pun dari engine lokal (termasuk
   `WAITING_SETUP`). Hasil: **HTTP 200 dalam 0,49 s** (sebelumnya hang 25 s+).
2. Inferensi Laya dipindah ke subprocess + timeout, DAN **dimatikan secara default**
   lewat saklar `WARROOM_LAYA_ENABLE`. Tanpa saklar itu endpoint menjawab
   `tersedia:false` + alasan — bukan menjalankan model yang bisa menjatuhkan layanan.

### Verifikasi setelah perbaikan
```
/forex/levels  -> 200 dalam 0,49 s
/forex/laya    -> tersedia:false, "inferensi dimatikan demi kestabilan layanan..."
/api/v1/build  -> 200
RAM available  -> 8,3 GB (swap tidak lagi penuh)
```

## 6. Rekomendasi (butuh keputusan owner)

Model Laya **tidak aman dijalankan di dalam proses layanan** pada mesin ini. Pilihan:

1. **Batas memori** — jalankan `laya_cli` dengan `systemd-run`/cgroup ber-limit RAM
   (mis. 2 GB) supaya kegagalan model tidak menyeret sistem.
2. **Jadwalkan, jangan on-demand** — jalankan verdict tiap N menit lewat timer,
   simpan hasilnya ke state, endpoint hanya membaca (pola yang sama dengan snapshot).
3. **Server terpisah** — host khusus inferensi (atau GPU) supaya RAM terisolasi.
4. **Model lebih kecil** — `laya` 421M memang paling ringan yang tersedia; bila masih
   terlalu berat, middleware bisa memakai model lain yang lebih kecil.

Sampai salah satu dipilih, `/forex/laya` akan terus menjawab `tersedia:false`.

## 7. Yang masih menggantung (belum diverifikasi)
- EA di MT5 belum di-compile ulang, jadi `InpUseRiskSizing=false` belum aktif di sana.
- Akses Azure: `az` terautentikasi, VM `mt5-trader-vm` running, tetapi
  `az vm run-command invoke` masih macet (`Conflict: execution is in progress`)
  dan SSH:22 timeout.
- Sinyal Telegram masuk: belum ada konsumen di server ini (yang ada hanya notifier
  keluar). Bila Laya memang mengolah sinyal Telegram, sumbernya perlu ditunjukkan.
