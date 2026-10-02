#!/usr/bin/env bash
# Bukti P1 lewat API yang benar-benar berjalan (127.0.0.1:8800).
#
# Sesi uji dibuat langsung di DB lalu ditulis ke berkas mode 600 — token tidak pernah
# masuk ke transkrip/terminal. Pengguna uji dihapus lagi di akhir.
set -uo pipefail
WARROOM=/home/admin/warroom
# Sesi uji dibuat di DB dan ditangkap lewat command substitution — token tidak pernah
# masuk ke transkrip maupun ke berkas. (Root TIDAK boleh menulis ke berkas milik admin di
# /tmp: `fs.protected_regular=2` menolaknya.)
SID=$(sudo bash -c "set -a; . /etc/warroom/db.env; set +a; export HOME=/home/admin
cd $WARROOM
.venv/bin/python - <<'PY'
from warroom_core.db import User, session_scope
from warroom_api import auth
with session_scope() as s:
    s.query(User).filter_by(username='uji-live-p1').delete()
    u = User(username='uji-live-p1', role='viewer', pass_hash='')
    s.add(u); s.flush()
    print(auth.issue_session(s, u).id)
PY" 2>/dev/null)
if [ -z "$SID" ]; then echo "GAGAL: sesi uji tidak terbentuk"; exit 1; fi
C="Cookie: wr_session=$SID"

echo "=== 1. 401 tanpa login (data) ==="
curl -s -m 5 -o /dev/null -w "  /api/v1/crypto -> %{http_code}\n" http://127.0.0.1:8800/api/v1/crypto

echo "=== 2. /api/v1/freshness (dengan sesi) ==="
curl -s -m 8 -H "$C" http://127.0.0.1:8800/api/v1/freshness | .venv/bin/python -c "
import json,sys
d=json.load(sys.stdin)
print('  jumlah fakta:', d['count'])
for f in d['facts'][:3]:
    print(f\"    {f['kind']}/{f['key']}: {f['status']} umur {f['age_s']}s ttl {f['ttl_s']}s sumber={f['source']}\")
basi=[f for f in d['facts'] if f['status']=='basi']
print('  basi:', len(basi))
"

echo "=== 3. baca per-area ==="
for A in crypto idx forex gmgn polymarket; do
  curl -s -m 8 -H "$C" "http://127.0.0.1:8800/api/v1/$A" | $WARROOM/.venv/bin/python -c "
import json,sys
d=json.load(sys.stdin)
print(f\"  {d['area']:11s} fakta={len(d['facts'])} hilang={len(d['kunci_hilang'])} kunci={sorted(d['data'])[:4]}\")
"
done

echo "=== 4. gate lewat API (angka nyata studi) ==="
curl -s -m 8 -H "$C" -H 'Content-Type: application/json' \
  -d '{"n":1175,"win":928,"be":0.77,"ci":0.90,"split":"frozen:studi-2026-09"}' \
  http://127.0.0.1:8800/api/v1/gate/evaluate | $WARROOM/.venv/bin/python -c "
import json,sys
d=json.load(sys.stdin)
print(f\"  verdict={d['verdict']} ci_low={d['ci_low']:.4f} be={d['be']} required_n={d['required_n']}\")
print('  alasan:', d['reason'])
print('  catatan:', d['notes'])
"

echo "=== 5. SSE: 2 kejadian pertama lalu keluar ==="
timeout 12 curl -s -N -H "$C" "http://127.0.0.1:8800/api/v1/stream?topics=services,facts" | head -12 | sed 's/^/  /'

echo "=== 6. /metrics (scraper lokal) ==="
curl -s -m 5 http://127.0.0.1:8800/metrics | grep -E "^(warroom_facts_total|warroom_facts_basi|warroom_alerts_open|warroom_job_enabled|warroom_job_last_run_seconds)" | sed 's/^/  /'

echo "=== 7. bersihkan pengguna uji ==="
sudo bash -c "set -a; . /etc/warroom/db.env; set +a; export HOME=/home/admin
cd $WARROOM
.venv/bin/python - <<'PY'
from warroom_core.db import Session as S, User, session_scope
with session_scope() as s:
    u = s.query(User).filter_by(username='uji-live-p1').one()
    s.query(S).filter_by(user_id=u.id).delete()
    s.query(User).filter_by(id=u.id).delete()
print('  pengguna uji dihapus')
PY"