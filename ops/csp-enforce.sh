#!/usr/bin/env bash
# Pasang CSP ENFORCE dengan hash skrip bootstrap yang benar (audit QA putaran 2, 7 Okt 2026).
#
# KENAPA SKRIP INI ADA
# --------------------
# 1. Aplikasi memakai `ssr = false`, sehingga SvelteKit TIDAK menyisipkan meta CSP
#    (fitur `csp`-nya butuh render server) — sudah dicoba, tidak menghasilkan apa pun.
# 2. Skrip bootstrap inline SvelteKit memuat nama chunk yang ber-hash, jadi hash-nya
#    BERUBAH setiap build — mustahil ditulis tangan di nginx.
# 3. Tanpa hash, `script-src 'self'` akan MEMBLOKIR bootstrap → halaman mati total.
#    Terbukti lewat e2e/cek_csp_enforce.spec.ts (inline script dilaporkan dilanggar).
#
# Maka: ambil HTML yang SUDAH disajikan build baru → hitung sha256 tiap skrip inline →
# tulis snippet nginx berisi header Content-Security-Policy (enforce) → reload nginx.
# Dijalankan otomatis di akhir ops/deploy-web.sh, jadi tidak ada jendela waktu di mana
# HTML baru disajikan dengan hash lama.
set -euo pipefail

BASE="${WARROOM_CSP_BASE:-http://127.0.0.1:3100}"
SNIPPET="/etc/nginx/snippets/warroom-csp.conf"
HTML="$(curl -sf --max-time 5 "$BASE/" || true)"

if [[ -z "$HTML" ]]; then
	echo "CSP: tidak bisa mengambil HTML dari $BASE — enforce TIDAK dipasang (biarkan report-only)"
	exit 1
fi

# CATATAN: HTML ditulis ke berkas sementara, BUKAN dialirkan lewat pipa ke python3
# yang skripnya datang dari heredoc — heredoc menimpa stdin, sehingga pipa HTML hilang
# dan skrip selalu melapor "tidak menemukan skrip bootstrap" (bug nyata 7 Okt).
HTML_TMP="$(mktemp)"
printf '%s' "$HTML" > "$HTML_TMP"
HASHES="$(python3 - "$HTML_TMP" <<'PY'
import base64, hashlib, re, sys
html = open(sys.argv[1], encoding="utf-8").read()
out = []
for m in re.finditer(r"<script\s*>(.*?)</script>", html, re.S):
    h = base64.b64encode(hashlib.sha256(m.group(1).encode("utf-8")).digest()).decode()
    out.append("'sha256-" + h + "'")
print(" ".join(out))
PY
)"
rm -f "$HTML_TMP"

if [[ -z "$HASHES" ]]; then
	echo "CSP: tidak menemukan skrip bootstrap inline — enforce TIDAK dipasang (akan memblokir halaman)"
	exit 1
fi

CSP="default-src 'self'; script-src 'self' ${HASHES}; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"

TMP="$(mktemp)"
cat > "$TMP" <<EOF
# DIHASILKAN OTOMATIS oleh ops/csp-enforce.sh — jangan diedit tangan.
# Hash skrip bootstrap berubah setiap build; skrip deploy menulis ulang berkas ini.
add_header Content-Security-Policy "${CSP}" always;
EOF

sudo -n install -m 644 "$TMP" "$SNIPPET"
rm -f "$TMP"
sudo -n nginx -t >/dev/null 2>&1
sudo -n systemctl reload nginx

echo "CSP enforce dipasang (${HASHES// / } )"
