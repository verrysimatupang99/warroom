# Finalisasi produksi — 1 Nov 2026

Snapshot setelah rangkaian PR #61–#72 dan deploy `abad66b`.
Semua angka di bawah hasil perintah pada 1 Nov 2026, 06:20–06:30 UTC.

## Yang sudah selesai dan terbukti

| Area | Bukti |
|---|---|
| Build produksi | API, web, dan disk sama: `abad66b-20261101T105935Z` |
| Layanan | `warroom-api`, `warroom-worker`, `warroom-web`, `nginx` aktif |
| Halaman | `/`, `/masuk`, `/crypto`, `/idx`, `/forex`, `/polymarket`, `/gmgn`, `/sistem`, `/riset`, `/jurnal` = 200 |
| Readiness | `ready`, `freshness={stale, count:24}`, 4 heartbeat ok |
| Job | 36 job, **0 non-ok**; `reconcile-crypto` ok, `slo-check` ok |
| Alert | 0 terbuka; `job/reconcile-crypto` auto-ack, alert MT5 demo di-ack setelah pensiun |
| CSP | enforce == report-only; hash ditulis ke 2 vhost |
| Restore drill | Timer bulanan aktif; run 1 Nov: facts 96.326, alerts 669, jobs 34, 32 detik, DB uji dihapus |
| OKX read-only | Job `okx-sync` 5 menit; run 06:23: `equity_usd=104.7364`, `posisi=2`, `upl_usd=-1.3944` |
| Area crypto | Fakta `okx.account/ringkas` dan `okx.positions/ringkas` muncul di `/api/v1/areas/crypto` |
| Provider gateway | Urutan efektif nutaraline → qonek → kiyara |
| Model CLI | `nectere/deepseek-v4.1-flash` untuk default dan smol; subagent `scout` terbukti jalan |


## Perubahan kode utama

- `services/api/.../routers/cron.py`: panel cron lokal dari `jobs`/`events`, bukan proxy Tencent.
- `services/api/.../routers/sistem.py`: readiness tidak diblokir fakta basi; freshness terpisah.
- `services/worker/.../jobs/domain.py`: kegagalan rekonsiliasi menjadi `status: gagal`.
- `packages/live-trading/.../rekonsiliasi.py`: timestamp OKX ms → detik.
- `packages/live-trading/.../okx_account.py` + job `okx-sync`: saldo/posisi read-only.
- `ops/restore-drill.sh` + unit/timer: bukti restore berulang.
- `ops/csp-enforce.sh`: menulis hash ke vhost yang benar-benar disajikan.

## Pending — butuh keputusan atau kredensial owner

1. **Akun live `36525553` (VM2)** masih di luar telemetri War Room. Larangan menyentuh VM tetap berlaku. Opsi: investor password/statement read-only untuk pemantau eksternal.
2. **Backup offsite**: belum ada tujuan terukur (tanpa rclone/restic/borg, tanpa bucket). Backup harian tetap lokal.
3. **Kunci provider**: qonek `401 Key expired`; kiyara `429` (maks 6 bersamaan); nutaraline menolak probe pendek. Perbaikan kunci/limit di sisi owner.
4. **p95/5xx**: belum diukur karena access log nginx tidak memuat `request_time`. Ambang lain (disk, backup, drill, API up) sudah berjalan di job `slo-check`.
5. **Disk 74–76%**: alert warn 80% dan crit 90% sudah aktif; belum ada tindakan pemangkasan.

## Verifikasi cepat

```bash
curl -s http://127.0.0.1:8800/api/v1/build
curl -s -b <cookie> http://127.0.0.1:8800/api/v1/ready
curl -s -b <cookie> http://127.0.0.1:8800/api/v1/cron/jobs | jq '[.jobs[]|select(.last_status!="ok")]'
cat /var/lib/warroom/restore-drill/last.json
```
