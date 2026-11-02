# Runbook Operator — War Room

Panduan operasional harian: restart layanan, membaca log, memahami gate
statistik yang blocking, serta backup/restore Postgres. Untuk arsitektur
lihat [`arsitektur.md`](arsitektur.md); untuk aturan kerja lihat [`../AGENTS.md`](../AGENTS.md).

> Prinsip: **jangan mengarang angka**. Kalau data kosong, tulis kosong.
> Gate live & ambang statistik hanya boleh diubah manusia (owner).

## 1. Peta layanan (systemd)

| Unit | Fungsi | Cara jalan |
|---|---|---|
| `warroom-api.service` | FastAPI :8800 (REST + SSE) | always |
| `warroom-web.service` | SvelteKit (node adapter) | always |
| `warroom-worker.service` | Job runner: ingest, hitung, terbitkan fakta | always |
| `warroom-laya-verdict.timer` | Hitung verdict Laya AI | timer ~tiap jam |
| `warroom-panel-sim.timer` | Simulator panel A/B/C + daily ratchet | timer 5 menit |
| `warroom-momentum-paper.timer` | Paper trader momentum | timer 1 jam |
| `warroom-alert-push.timer` | Teruskan alert watchdog ke Telegram | timer 5 menit |
| `warroom-pantau-tick.timer` | Pantauan tick/kesegaran feed | timer |
| `warroom-backup-postgres.timer` | `pg_dump` custom + sha256 + rotasi | harian 00:40 UTC |
| `warroom-restore-drill.timer` | Drill restore ke DB uji (hapus setelah verifikasi) | bulanan |

Status cepat:

```bash
systemctl list-timers 'warroom-*'          # semua timer + jadwal berikutnya
systemctl status warroom-api warroom-web warroom-worker
```

## 2. Restart & diagnosa

```bash
sudo systemctl restart warroom-api.service
sudo systemctl restart warroom-worker.service
sudo systemctl restart warroom-web.service
systemctl --failed                    # ada unit gagal?
```

Kalau unit loop-restart (`activating auto-restart`), cek log dulu (bagian 3)
sebelum restart lagi — restart buta menutupi penyebab.

## 3. Membaca log

Log worker/API berformat JSON satu baris (`ts`, `svc`, `event`, `job`,
`status`, `detail`):

```bash
journalctl -u warroom-worker.service -n 50 --no-pager
journalctl -u warroom-worker.service --since "1 hour ago" | grep '"status": "error"'
journalctl -u warroom-api.service -f                 # ikuti langsung
journalctl -u warroom-laya-verdict.service -n 30
```

Yang perlu dicurigai:

- `status: "error"` atau `status: "timeout"` berulang pada job yang sama.
- `svc: "warroom-worker"` hilang > 5 menit → worker mati; cek `systemctl status`.
- LLM verdict gagal beruntun → gateway `services/llm` punya circuit breaker;
  lihat log `services/llm` sebelum restart.

## 4. Gate statistik blocking — apa artinya

Sinyal tidak otomatis jadi order. Alur gate (detail: [`arsitektur.md`](arsitektur.md)):

1. **Gate statistik** (`packages/core`) — membandingkan performa strategi
   terhadap ambang minimum (win rate, sample size, drawdown). Kalau blocking,
   worker tetap mencatat sinyal tapi menandai **tidak layak eksekusi**.
2. **Gate risiko & biaya** (`packages/live-trading`) — break-even spread/komisi,
   sizing dompet.
3. **Gate izin owner** — allowlist dry-run; live hanya setelah paper trade.

Kalau sinyal diblok:

```bash
# lihat alasan gate terakhir
grep -r "gate" /home/admin/live-trading/state/ | tail -20
# atau lewat API
curl -s localhost:8800/api/v1/health | python3 -m json.tool
```

**Jangan pernah** menaikkan/menurunkan ambang gate agar sinyal lolos —
ambang hanya boleh diubah owner dengan alasan tertulis.

## 5. Backup Postgres (harian, otomatis)

Timer `warroom-backup-postgres.timer` jalan 00:40 UTC: `pg_dump -Fc`
(custom format) + sha256 + rotasi.

```bash
systemctl list-timers warroom-backup-postgres.timer    # jadwal & status
sudo systemctl start warroom-backup-postgres.service   # backup manual kapan pun
ls -lht /var/backups/warroom/ | head                   # arsip terbaru (sesuai unit)
```

Verifikasi cepat integritas dump:

```bash
f=$(ls -t /var/backups/warroom/*.dump 2>/dev/null | head -1)
sha256sum -c "$f.sha256"     # nama file .sha256 mengikuti konvensi unit
pg_restore --list "$f" >/dev/null && echo "dump valid"
```

## 6. Restore & drill bulanan

Drill otomatis (`warroom-restore-drill.timer`, bulanan) me-restore dump
terbaru ke **DB uji**, memverifikasi, lalu menghapus DB uji. Jalankan manual:

```bash
sudo systemctl start warroom-restore-drill.service
journalctl -u warroom-restore-drill.service -n 50 --no-pager
```

Restore darurat (owner saja):

```bash
sudo systemctl stop warroom-api.service warroom-worker.service
pg_restore --clean --if-exists -d "$DATABASE_URL" /var/backups/warroom/<dump>.dump
sudo systemctl start warroom-api.service warroom-worker.service
```

Selalu `pg_restore --list` dulu untuk memastikan dump bisa dibaca
sebelum menimpa DB hidup.

## 7. Checklist insiden cepat

1. `systemctl --failed` → catat unit gagal.
2. `journalctl -u <unit> --since "30 min ago" | grep error` → catat penyebab.
3. Data basi? cek `warroom-pantau-tick.timer` & job `signal-sync` di worker.
4. DB penuh / lambat? cek retensi (`packages/core`) & ukuran WAL arsip.
5. Semua aman tapi UI kosong → cek `warroom-web.service` & health API :8800.
6. Setelah pulih: tulis catatan insiden di `docs/` (apa, kenapa, cara cegah).
