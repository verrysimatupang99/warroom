# Finalisasi produksi — 1 Nov 2026

Snapshot setelah rangkaian PR #61–#70 dan deploy `b6bcaad`.
Semua angka di bawah hasil perintah pada 1 Nov 2026, 06:20–06:30 UTC.

## Yang sudah selesai dan terbukti

| Area | Bukti |
|---|---|
| Build produksi | API, web, dan disk sama: `b6bcaad-20261101T062307Z` |
| Layanan | `warroom-api`, `warroom-worker`, `warroom-web`, `nginx` aktif |
| Halaman | `/`, `/masuk`, `/crypto`, `/idx`, `/forex`, `/polymarket`, `/gmgn`, `/sistem`, `/riset`, `/jurnal` = 200 |
| Readiness | `ready`, `freshness={stale, count:24}`, 4 heartbeat ok |
| Job | 35 job, **0 non-ok**; `reconcile-crypto` ok setelah perbaikan timestamp OKX |
| Alert | `job/reconcile-crypto` auto-ack saat job pulih (`pulih=1`) |
| CSP | enforce == report-only; hash ditulis ke 2 vhost |
| Restore drill | Timer bulanan aktif; run 1 Nov: facts 96.326, alerts 669, jobs 34, 32 detik, DB uji dihapus |
| OKX read-only | Job `okx-sync` 5 menit; run 06:23: `equity_usd=104.7364`, `posisi=2`, `upl_usd=-1.3944` |
| Area crypto | Fakta `okx.account/ringkas` dan `okx.positions/ringkas` muncul di `/api/v1/areas/crypto` |
| Provider gateway | Urutan efektif nutaraline → qonek → kiyara |
| Model CLI | default/smol: `bluesminds-2/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`; subagent `scout` terbukti jalan |

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
4. **MT5 demo `416510164`**: dua snapshot basi karena sumbernya sudah tidak aktif. Pilih: pensiunkan faktanya atau sambungkan ulang.
5. **SLO formal**: metric dasar sudah ada (`warroom_up`, `facts_basi`, readiness), tetapi ambang error-budget/p95/disk belum ditetapkan owner.
6. **Disk 75%**: tren naik; belum ada alert ambang.

## Verifikasi cepat

```bash
curl -s http://127.0.0.1:8800/api/v1/build
curl -s -b <cookie> http://127.0.0.1:8800/api/v1/ready
curl -s -b <cookie> http://127.0.0.1:8800/api/v1/cron/jobs | jq '[.jobs[]|select(.last_status!="ok")]'
cat /var/lib/warroom/restore-drill/last.json
```
