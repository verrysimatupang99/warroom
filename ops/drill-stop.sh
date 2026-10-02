#!/usr/bin/env bash
# Latihan P6-T2: hentikan SEMUA eksekusi & pekerjaan otomatis, ukur waktunya.
#
# Target blueprint: < 60 detik. Aman dijalankan: live memang sedang tidak aktif, dan skrip
# ini hanya menghentikan layanan MILIK WAR ROOM (worker/API) — tidak menyentuh unit domain
# lain kecuali memverifikasi statusnya.
set -uo pipefail
WARROOM=/home/admin/warroom
PSQL_ENV=/etc/warroom/db.env

t0=$(date +%s.%N)
echo "=== 1. matikan worker (semua job otomatis berhenti) ==="
sudo systemctl stop warroom-worker.service
systemctl is-active warroom-worker.service | sed 's/^/  worker: /'

echo "=== 2. matikan peran tulis AI (kill switch) ==="
sudo bash -c "set -a; . $PSQL_ENV; set +a; export HOME=/home/admin; cd $WARROOM
.venv/bin/python - <<'PY'
from warroom_core import autonomy
from warroom_core.db import session_scope
with session_scope() as s:
    autonomy.seed_parameters(s)
    autonomy.set_kill_switch(s, True, actor='drill')
    print('  kill_switch:', autonomy.kill_switch_aktif(s))
PY"

echo "=== 3. verifikasi tidak ada eksekusi yang mungkin berjalan ==="
for u in poly-pilot.service poly-agent.service; do
  printf "  %-24s %s\n" "$u" "$(systemctl is-active "$u" 2>/dev/null)"
done
sudo -n test -e /etc/poly-pilot/activation-approved \
  && echo "  gate live: ADA (perhatian!)" \
  || echo "  gate live: tidak ada (benar)"

echo "=== 4. bukti tidak ada job baru setelah worker mati ==="
before=$(sudo bash -c "set -a; . $PSQL_ENV; set +a; P=\"\${WARROOM_DB_URL#*://warroom:}\"; P=\"\${P%%@*}\"
PGPASSWORD=\"\$P\" psql -h 127.0.0.1 -U warroom -d warroom -tAc \"select count(*) from events where type='job.ran'\"" 2>/dev/null)
sleep 8
after=$(sudo bash -c "set -a; . $PSQL_ENV; set +a; P=\"\${WARROOM_DB_URL#*://warroom:}\"; P=\"\${P%%@*}\"
PGPASSWORD=\"\$P\" psql -h 127.0.0.1 -U warroom -d warroom -tAc \"select count(*) from events where type='job.ran'\"" 2>/dev/null)
echo "  event job.ran sebelum=$before sesudah=$after (harus sama)"

t1=$(date +%s.%N)
echo "=== hasil ==="
echo "  durasi henti: $(printf '%.1f' "$(echo "$t1 - $t0" | bc)") detik (target < 60)"

echo "=== 5. kembalikan ke keadaan normal (worker hidup, kill switch mati) ==="
sudo systemctl start warroom-worker.service
sudo bash -c "set -a; . $PSQL_ENV; set +a; export HOME=/home/admin; cd $WARROOM
.venv/bin/python - <<'PY'
from warroom_core import autonomy
from warroom_core.db import session_scope
with session_scope() as s:
    autonomy.set_kill_switch(s, False, actor='drill-selesai')
    print('  kill_switch:', autonomy.kill_switch_aktif(s))
PY"
systemctl is-active warroom-worker.service | sed 's/^/  worker: /'