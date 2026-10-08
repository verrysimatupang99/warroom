#!/usr/bin/env bash
# CI lokal — menjalankan pemeriksaan yang SAMA dengan .github/workflows/ci.yml,
# supaya "CI hijau" bisa dibuktikan tanpa menunggu runner (dan tanpa push).
#
# Pakai: bash ops/ci-local.sh
# Keluar 0 hanya bila semua tahap hijau. Tidak menyentuh /opt/polymarket, Tencent, atau Azure.
set -uo pipefail

WARROOM="${WARROOM:-$HOME/warroom}"
DOMAIN="${DOMAIN:-$HOME/live-trading}"
GITLEAKS="${GITLEAKS:-$HOME/.local/bin/gitleaks}"

fail=0
step() { printf '\n=== %s ===\n' "$1"; }
check() { if [ "$1" -eq 0 ]; then echo "  OK   $2"; else echo "  GAGAL $2"; fail=1; fi; }

step "1/4 domain: sync --frozen + ruff + pytest (live-trading)"
( cd "$DOMAIN" && uv sync --frozen --extra dev && uv run ruff check . && uv run pytest -q )
check $? "domain sync + ruff + pytest"

step "2/4 platform: sync --frozen + ruff + impor domain"
( cd "$WARROOM" && uv sync --frozen && uv run ruff check . \
 && uv run python -c "import live_trading, warroom_core; print('domain', live_trading.__version__, '| core ok')" \
 && uv run python ops/check-openapi-contract.py )
check $? "platform sync + ruff + import"

step "3/4 secrets: gitleaks (git history, dua repo)"
if [ -x "$GITLEAKS" ]; then
  ( cd "$WARROOM" && "$GITLEAKS" git . --redact --no-banner )
  check $? "gitleaks warroom"
  ( cd "$DOMAIN" && "$GITLEAKS" git . --redact --no-banner )
  check $? "gitleaks live-trading"
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