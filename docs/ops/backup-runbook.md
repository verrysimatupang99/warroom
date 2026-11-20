# Runbook — Backup & Restore War Room

## Alur

```
webdock 02:00 UTC  pg_dump -Fc warroom | gpg RSA4096 (kunci PUBLIK di admin)
                   → /var/backups/warroom/warroom-<stamp>.dump.gpg   (retensi 7)
cyber1  02:20 UTC  ssh pull file terbaru → /root/backups/warroom/      (retensi 14, verifikasi header)
```

Kunci privat GPG **hanya ada di cyber1** (`/root/.gnupg`, `backup@warroom.local`,
fpr `BC8871CB…`). Webdock hanya punya kunci publik, jadi dump di webdock tidak bisa dibuka
bahkan oleh root webdock.

Perintah:
- Backup manual: `sudo systemctl start wr-backup.service` (webdock)
- Pull manual: `/root/scripts/pull-warroom-backup.sh` (cyber1)
- Log: `/var/log/wr-backup.log` (webdock), `/var/log/wr-pull.log` (cyber1)

## Restore (uji kuartalan)

1. Ambil dump terbaru di cyber1:
   `ls -1t /root/backups/warroom/*.dump.gpg | head -1`
2. Dekripsi dan kirim ke webdock (plaintext hanya di /tmp, umask 077):
   `gpg --batch --decrypt <file> | ssh admin@webdock 'umask 077; cat > /tmp/wr_restore.dump'`
3. Jalankan restore ke DB uji (jangan ke DB produksi):
   ```
   chown postgres:postgres /tmp/wr_restore.dump
   sudo -u postgres dropdb --if-exists warroom_restore_test
   sudo -u postgres createdb warroom_restore_test
   sudo -u postgres pg_restore -d warroom_restore_test --no-owner --no-privileges /tmp/wr_restore.dump
   ```
4. Bandingkan jumlah baris tabel kunci (`facts`, `events`, `trades`, `alerts`) dengan sumber.
5. Hapus `/tmp/wr_restore.dump` segera.
6. Kalau restore ke produksi: hentikan `warroom-api` + `warroom-worker` dulu, restore ke DB baru,
   lalu `ALTER DATABASE` ganti nama — jangan menimpa DB yang sedang dipakai.

## Jebakan yang sudah kena (jangan diulang)

- **`pg_restore` berjalan sebagai `postgres`** → file dump harus dimiliki/readable oleh postgres.
  `cat > file` sebagai user `admin` menghasilkan `600 admin` → error "Permission denied".
- **`pipefail` + `gpg | head`** membuat verifikasi gagal padahal header benar (gpg kena SIGPIPE).
  Pakai `HDR=$( { set +o pipefail; gpg -d file | head -c 5; } )`.
- **`sudo -S` di dalam pipe** akan memakan stdin dump. Jalankan restore lewat skrip yang
  dipanggil dengan `sudo bash script`, bukan `sudo` di tengah pipeline.
- Direktori `/var/backups/warroom` harus bisa dibaca user `admin` supaya cyber1 bisa pull
  (grup `sudo`, mode 750; file 640).
