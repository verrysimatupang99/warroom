# KUNCI EKSEKUSI LIVE — War Room

**Status: TERKUNCI.** Jangan dibuka tanpa persetujuan pemilik.

- Bendera: `WR_EXEC_LIVE=0` di `/etc/warroom/v1-executor.env`
- Efek: aksi apa pun yang menarget `gold_reaper_hexa` / `live` **DITOLAK** oleh executor,
  walau sudah di-arm + di-confirm. EA live tetap jalan, tidak bisa dihentikan dari web.
- Demo (`mtrb_pro` / `mt5-ex-demo`) **aktif** dan bisa dieksekusi.

## Rencana pemilik
Live nanti memakai **key berbeda** (bukan master password). Sampai itu:
- Jangan set `WR_EXEC_LIVE=1`.
- Jangan hapus gerbang di `v1/jobs/executor.py` (`LIVE_TARGETS` + `LIVE_ENABLED`).

## Cara membuka (HANYA bila pemilik minta + key live sudah dipasang)
1. Pasang kredensial live baru di vault, bukan master password.
2. `WR_EXEC_LIVE=1` di `/etc/warroom/v1-executor.env`, lalu `systemctl restart warroom-v1-executor.timer`.
3. Uji dulu di demo, baru live.

Dibuat: 2026-11-18. Pemilik memutuskan live tetap terkunci.
