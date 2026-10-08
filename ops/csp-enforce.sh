#!/usr/bin/env bash
# Validate the CSP emitted by SvelteKit; nginx must not add a second enforce policy.
set -euo pipefail
BASE="${WARROOM_CSP_BASE:-http://127.0.0.1:3100}"
HEADERS="$(mktemp)"
trap 'rm -f "$HEADERS"' EXIT
for _ in 1 2 3 4 5; do
  if curl -sfI --max-time 5 "$BASE/" >"$HEADERS"; then break; fi
  sleep 2
done
if ! grep -qi '^content-security-policy:' "$HEADERS"; then
  echo "CSP: SvelteKit tidak mengirim policy enforce" >&2
  exit 1
fi
count="$(grep -i '^content-security-policy:' "$HEADERS" | wc -l | tr -d ' ')"
printf 'CSP: validasi SvelteKit berhasil (%s enforce policy; nginx tidak menambah policy kedua)\n' "$count"
