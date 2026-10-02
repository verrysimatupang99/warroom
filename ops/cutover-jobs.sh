#!/usr/bin/env bash
# Cutover jadwal: timer systemd domain → worker War Room (P1-T4 lanjutan).
#
# Kenapa: dua penulis untuk berkas yang sama = berkas ditulis dua kali, kuota dobel, dan
# tidak ada satu tempat untuk melihat "apa yang akan jalan". Setelah cutover, SATU penulis
# saja: `warroom-worker.service` (tabel `jobs`).
#
# Aman & bisa dibalik: timer hanya di-stop+disable (bukan dihapus), unit-nya tetap ada.
# Rollback: `sudo systemctl enable --now live-trading-{snapshot,collect,backup}.timer`
#           dan matikan job yang sama di tabel `jobs` (enabled=false).
set -uo pipefail
WARROOM=/home/admin/warroom
TIMER=(live-trading-snapshot.timer live-trading-collect.timer live-trading-backup.timer)

echo "=== 0. keadaan sebelum ==="
for t in "${TIMER[@]}"; do printf "  %-32s %s\n" "$t" "$(systemctl is-active "$t")"; done

echo "=== 1. hentikan timer domain (watchdog dibiarkan: ia hanya membaca) ==="
for t in "${TIMER[@]}"; do
  sudo systemctl stop "$t" 2>/dev/null
  sudo systemctl disable "$t" 2>&1 | grep -q "Removed" && echo "  dimatikan: $t" || echo "  sudah nonaktif: $t"
done

echo "=== 2. siapkan job worker (hapus baris 'snapshot' lama, daftarkan refresh-snapshot) ==="
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; P=\"\${WARROOM_DB_URL#*://warroom:}\"; P=\"\${P%%@*}\"
PGPASSWORD=\"\$P\" psql -h 127.0.0.1 -U warroom -d warroom -tAc \"delete from jobs where name='snapshot'\"" | sed 's/^/  /'
sudo systemctl restart warroom-worker.service
sleep 6

echo "=== 2b. aktifkan job pindahan secara eksplisit (enabled bukan urusan kode) ==="
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; P=\"\${WARROOM_DB_URL#*://warroom:}\"; P=\"\${P%%@*}\"
PGPASSWORD=\"\$P\" psql -h 127.0.0.1 -U warroom -d warroom -tAc \"update jobs set enabled=true, next_run_at=now() where name in ('refresh-snapshot','collect','backup')\"" | sed 's/^/  /'

echo "=== 3. jalankan satu siklus penuh (job berat dipaksa jatuh tempo) ==="
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; P=\"\${WARROOM_DB_URL#*://warroom:}\"; P=\"\${P%%@*}\"
PGPASSWORD=\"\$P\" psql -h 127.0.0.1 -U warroom -d warroom -tAc 'update jobs set next_run_at=now() where enabled'" >/dev/null
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; export HOME=/home/admin; cd $WARROOM
.venv/bin/python -m warroom_worker.run --once" | sed 's/^/  /'

echo "=== 4. keadaan sesudah ==="
for t in "${TIMER[@]}"; do printf "  %-32s %s\n" "$t" "$(systemctl is-active "$t")"; done
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; P=\"\${WARROOM_DB_URL#*://warroom:}\"; P=\"\${P%%@*}\"
PGPASSWORD=\"\$P\" psql -h 127.0.0.1 -U warroom -d warroom -c \"select name, enabled, interval_s, last_status, left(last_detail,52) as detail from jobs order by name\""

echo "=== 5. kesegaran berkas domain (bukti penulis baru bekerja) ==="
for f in /home/admin/live-trading/state/snapshot.json; do
  printf "  %s\n    mtime %s (umur %s mnt)\n" "$f" "$(date -r "$f" '+%F %T %Z')" "$(( ($(date +%s) - $(stat -c %Y "$f")) / 60 ))"
done
ls -1t /home/admin/live-trading/backups/state-*.tar.gz 2>/dev/null | head -2 | sed 's/^/  arsip: /'