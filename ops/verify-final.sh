#!/usr/bin/env bash
# Verifikasi final War Room — satu perintah, keluar 0 hanya bila semua hijau.
#
# Memeriksa: tes tiga paket, metrik HTTP, readiness, job, alert, umur backup,
# dan bukti drill restore. Tidak mengubah apa pun.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${WARROOM_API_BASE:-http://127.0.0.1:8800}"
ENV_E2E="${WARROOM_E2E_ENV:-$HOME/.config/warroom/e2e.env}"
COOKIE="$(mktemp)"
trap 'rm -f "$COOKIE"' EXIT
gagal=0
cek() { if [[ "$1" -eq 0 ]]; then echo "PASS $2"; else echo "FAIL $2"; gagal=1; fi; }

echo "=== 1/6 tes ==="
( cd "$ROOT" && .venv/bin/python -m pytest services/api/tests services/worker/tests packages/live-trading -q )
cek $? "pytest api + worker + live-trading"

echo "=== 2/6 metrik HTTP ==="
teks="$(curl -s --max-time 5 "$BASE/metrics" || true)"
grep -q '^warroom_http_requests_total ' <<<"$teks" && \
grep -q '^warroom_http_errors_total ' <<<"$teks" && \
grep -q '^warroom_http_latency_p95_ms ' <<<"$teks"
cek $? "metrik http tersedia"

echo "=== 3/6 sesi ==="
if [[ -r "$ENV_E2E" ]]; then
	# shellcheck disable=SC1090
	set -a; . "$ENV_E2E"; set +a
	curl -s -c "$COOKIE" -H 'content-type: application/json' \
		-d "{\"username\":\"$WARROOM_E2E_USER\",\"password\":\"$WARROOM_E2E_PASS\"}" \
		"$BASE/api/v1/auth/login" >/dev/null
	cek $? "login e2e"
else
	echo "FAIL env e2e tidak ada: $ENV_E2E"
	gagal=1
fi

echo "=== 4/6 readiness ==="
ready="$(curl -s -b "$COOKIE" "$BASE/api/v1/ready")"
python3 - "$ready" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
raise SystemExit(0 if d.get("status") == "ready" else 1)
PY
cek $? "readiness ready"

echo "=== 5/6 job dan alert ==="
jobs="$(curl -s -b "$COOKIE" "$BASE/api/v1/cron/jobs")"
python3 - "$jobs" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
bad = [j["name"] for j in d.get("jobs", []) if j.get("last_status") not in ("ok", "belum-jalan")]
print("non-ok:", bad)
raise SystemExit(0 if not bad else 1)
PY
cek $? "tidak ada job non-ok"
alerts="$(curl -s -b "$COOKIE" "$BASE/api/v1/alerts")"
python3 - "$alerts" <<'PY'
import json, sys
d = json.loads(sys.argv[1])
raise SystemExit(0 if int(d.get("terbuka", 0)) == 0 else 1)
PY
cek $? "tidak ada alert terbuka"

echo "=== 6/6 backup dan drill ==="
dump="$(ls -1t /home/admin/backups/postgres/warroom-*.dump 2>/dev/null | head -n1)"
if [[ -n "$dump" ]]; then
	umur_jam=$(( ( $(date +%s) - $(stat -c %Y "$dump") ) / 3600 ))
	[[ "$umur_jam" -le 26 ]]
	cek $? "umur backup ${umur_jam} jam <= 26"
else
	echo "FAIL dump tidak ditemukan"; gagal=1
fi
python3 - <<'PY'
import json
from datetime import UTC, datetime
try:
    d = json.load(open("/var/lib/warroom/restore-drill/last.json"))
    umur = (datetime.now(UTC) - datetime.fromisoformat(d["selesai_at"])).days
    raise SystemExit(0 if d.get("ok") and umur <= 35 else 1)
except Exception:
    raise SystemExit(1)
PY
cek $? "bukti drill <= 35 hari"

echo
if [[ "$gagal" -eq 0 ]]; then
	echo "HASIL: SEMUA PASS"
else
	echo "HASIL: ADA YANG GAGAL"
fi
exit "$gagal"
