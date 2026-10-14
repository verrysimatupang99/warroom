#!/usr/bin/env bash
# CI lokal — menjalankan pemeriksaan yang SAMA dengan .github/workflows/ci.yml,
# supaya "CI hijau" bisa dibuktikan tanpa menunggu runner (dan tanpa push).
#
# F3/ADR-002: domain KINI anggota workspace di packages/live-trading/ (bukan lagi
# repo luar $HOME/live-trading). Sebelumnya skrip ini menguji repo luar, sehingga
# memberi merah-palsu (mis. tests/test_ambil.py butuh /home/admin/gmgn-scan/lp_paper.py
# yang tak ada di host ini) padahal CI hijau. Kini keduanya menguji tree yang sama.
#
# Catatan: ~/live-trading MASIH hidup sebagai state runtime (WARROOM_DOMAIN_HOME di
# warroom-{worker,api}.service, backup, timer) sampai cutover diputuskan owner —
# JANGAN dihapus. Yang berubah di sini hanya lokasi sumber kode yang diuji.
#
# Pakai: bash ops/ci-local.sh
# Keluar 0 hanya bila semua tahap hijau. Tidak menyentuh /opt/polymarket, Tencent, atau Azure.
set -uo pipefail

WARROOM="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GITLEAKS="${GITLEAKS:-$HOME/.local/bin/gitleaks}"

fail=0
step() { printf '\n=== %s ===\n' "$1"; }
check() { if [ "$1" -eq 0 ]; then echo "  OK   $2"; else echo "  GAGAL $2"; fail=1; fi; }

step "1/4 domain: ruff + pytest (packages/live-trading, anggota workspace)"
( cd "$WARROOM" \
  && uv run ruff check packages/live-trading/src packages/live-trading/tests \
  && uv run pytest packages/live-trading -q )
check $? "domain ruff + pytest (dalam repo)"

step "2/4 platform: sync --frozen + ruff + impor domain"
( cd "$WARROOM" && uv sync --frozen && uv run ruff check . \
 && uv run python -c "import live_trading, warroom_core; print('domain', live_trading.__version__, '| core ok')" \
 && uv run python ops/check-openapi-contract.py \
 && uv run python ops/check-file-size.py )
check $? "platform sync + ruff + import"

step "3/4 secrets: gitleaks (git history, repo warroom)"
if [ -x "$GITLEAKS" ]; then
  ( cd "$WARROOM" && "$GITLEAKS" git . --redact --no-banner )
  check $? "gitleaks warroom"
else
  echo "  LEWAT gitleaks tidak ada di $GITLEAKS"
  fail=1
fi

step "4/4 web: npm ci + lint token + check + test + build (apps/web)"
( cd "$WARROOM/apps/web" && npm ci --no-audit --no-fund \
  && node scripts/lint-tokens.mjs src && npm run check && npm run test && npm run build )
check $? "web lint token + check + test + build"

printf '\n=== ringkasan ===\n'
if [ "$fail" -eq 0 ]; then echo "SEMUA HIJAU"; else echo "ADA YANG GAGAL"; fi
exit "$fail"