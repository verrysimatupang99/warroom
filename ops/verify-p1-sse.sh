#!/usr/bin/env bash
# Bukti P1-T7: SSE benar-benar mengalirkan kejadian BARU (bukan hanya header).
#
# Caranya: buka stream, lalu picu job worker sungguhan saat stream terbuka, lalu lihat
# kejadiannya tiba. Sesi uji dibuat lewat command substitution (tidak masuk transkrip).
set -uo pipefail
WARROOM=/home/admin/warroom
KELUARAN=$(mktemp /tmp/wr-sse-XXXXXX); chmod 600 "$KELUARAN"
trap 'rm -f "$KELUARAN"' EXIT

SID=$(sudo bash -c "set -a; . /etc/warroom/db.env; set +a; export HOME=/home/admin
cd $WARROOM
.venv/bin/python - <<'PY'
from warroom_core.db import User, session_scope
from warroom_api import auth
with session_scope() as s:
    s.query(User).filter_by(username='uji-sse').delete()
    u = User(username='uji-sse', role='viewer', pass_hash='')
    s.add(u); s.flush()
    print(auth.issue_session(s, u).id)
PY" 2>/dev/null)
if [ -z "$SID" ]; then echo "GAGAL: sesi uji tidak terbentuk"; exit 1; fi

echo "1. buka SSE (topics=services,facts) di latar…"
timeout 25 curl -s -N -H "Cookie: wr_session=$SID" \
  "http://127.0.0.1:8800/api/v1/stream?topics=services,facts" > "$KELUARAN" 2>&1 &
CURL_PID=$!
sleep 3

echo "2. picu job worker sungguhan (menghasilkan kejadian baru)…"
# Paksa jatuh tempo supaya job benar-benar jalan pada siklus ini (bukan menunggu jadwal).
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; P=\"\${WARROOM_DB_URL#*://warroom:}\"; P=\"\${P%%@*}\"
PGPASSWORD=\"\$P\" psql -h 127.0.0.1 -U warroom -d warroom -tAc 'update jobs set next_run_at=now() where enabled'" >/dev/null 2>&1
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; export HOME=/home/admin; cd $WARROOM
.venv/bin/python -m warroom_worker.run --once" | sed 's/^/   worker: /'
sleep 4
kill "$CURL_PID" 2>/dev/null || true

echo "3. kejadian yang diterima klien SSE:"
grep -E "^(event|id|data):" "$KELUARAN" | head -20 | sed 's/^/   /'
echo "   (jumlah baris event: $(grep -c '^event:' "$KELUARAN" || true))"

echo "4. Last-Event-ID: minta ulang dari id tertentu (resume)…"
ID_TENGAH=$(grep '^id:' "$KELUARAN" | head -1 | awk '{print $2}')
if [ -n "${ID_TENGAH:-}" ]; then
  timeout 8 curl -s -N -H "Cookie: wr_session=$SID" -H "Last-Event-ID: $((ID_TENGAH - 1))" \
    "http://127.0.0.1:8800/api/v1/stream?topics=services,facts" | head -6 | sed 's/^/   /'
else
  echo "   (tidak ada id untuk diuji resume)"
fi

echo "5. bersihkan pengguna uji…"
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; export HOME=/home/admin; cd $WARROOM
.venv/bin/python - <<'PY'
from warroom_core.db import Session as S, User, session_scope
with session_scope() as s:
    u = s.query(User).filter_by(username='uji-sse').one()
    s.query(S).filter_by(user_id=u.id).delete()
    s.query(User).filter_by(id=u.id).delete()
print('   pengguna uji dihapus')
PY"