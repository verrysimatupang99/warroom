# Runbook — backup & restore Postgres War Room

Dump dihasilkan `ops/backup-postgres.sh` (format custom `pg_dump`) via unit
`warroom-backup-postgres.timer`. Tujuan: `~/backups/postgres/warroom-*.dump` +
`.sha256`, mode 600, retensi 14 dump terakhir.

Pasangan state berkas (ledger/verdict/state GMGN) ada di
`ops/runbook-restore.md` — keduanya wajib; backup yang satu tidak menutupi yang lain.

## 1. Pasang (sekali, butuh root)

```bash
cd /home/admin/warroom
sudo -n install -m 644 ops/warroom-backup-postgres.service ops/warroom-backup-postgres.timer /etc/systemd/system/
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now warroom-backup-postgres.timer
```

Jadwal 00:40 UTC, setelah siklus harian (00:20) selesai menulis. `Persistent=true`
berarti backup yang tertunda karena host mati tetap jalan saat boot.

## 2. Cek harian

```bash
systemctl --no-pager status warroom-backup-postgres.service
journalctl -u warroom-backup-postgres -n 20 --no-pager
ls -lh ~/backups/postgres | head
```

Skrip mengharuskan `WARROOM_DB_URL` (dari `/etc/warroom/db.env`, 600 root), jadi
jalur sahnya lewat unit. Uji manual satu kali sebagai root:

```bash
sudo -n bash -c 'set -a; source /etc/warroom/db.env; set +a; bash /home/admin/warroom/ops/backup-postgres.sh'
```

## 3. Verify dump (level 1)

```bash
LATEST=$(ls -1t ~/backups/postgres/warroom-*.dump | head -1)
sha256sum -c "$LATEST.sha256"
pg_restore --list "$LATEST" | head
```

## 4. Drill restore (level 2, bulanan — butuh root)

Restore ke database sementara `warroom_drill` — tidak pernah menyentuh DB `warroom` hidup:

```bash
sudo -n bash -c 'set -a; source /etc/warroom/db.env; set +a
  LATEST=$(ls -1t /home/admin/backups/postgres/warroom-*.dump | head -1)
  DRILL="${WARROOM_DB_URL%/*}/warroom_drill"
  psql "$WARROOM_DB_URL" -c "DROP DATABASE IF EXISTS warroom_drill" -c "CREATE DATABASE warroom_drill"
  pg_restore -d "$DRILL" "$LATEST"
  psql "$DRILL" -c "\dt"
  psql "$DRILL" -Atc "SELECT count(*) FROM facts" | head -1
  psql "$DRILL" -c "DROP DATABASE warroom_drill"'
```

Kriteria lolos: `\dt` menampilkan tabel inti (`facts`, `users`, `alerts`, `jobs`)
dan `SELECT count(*) FROM facts` menghitung baris. Catat bukti drill di
laporan ops — backup yang tidak pernah diuji bukan backup.

## 5. Jangan dilakukan

- Jangan mengubah `/etc/warroom/db.env` atau menyalin isinya ke repo/log/output.
- Jangan memutar rotasi dengan `rm` acak — biarkan skrip mengurus (retensi 14).
- Jangan menjadwalkan backup bersamaan dengan siklus harian (00:20) — risiko menangkap
  penulisan setengah jalan.
