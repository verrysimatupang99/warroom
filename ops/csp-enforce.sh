#!/usr/bin/env bash
# Validate the CSP emitted by SvelteKit; nginx must not add a second enforce policy.
# SvelteKit hashes its per-build bootstrap and emits the enforce header itself. Adding
# another nginx policy with a stale hash combines policies with AND and can brick hydration.
set -euo pipefail
BASE="${WARROOM_CSP_BASE:-http://127.0.0.1:3100}"
for _ in 1 2 3 4 5; do
  HTML="$(curl -sf --max-time 5 "$BASE/" || true)"
  [[ -n "$HTML" ]] && break
  sleep 2
done
if [[ -z "${HTML:-}" ]]; then
  echo "CSP: tidak bisa mengambil HTML dari $BASE" >&2
  exit 1
fi
count="$(printf '%s' "$HTML" | grep -oi 'content-security-policy' | wc -l | tr -d ' ')"
if (( count < 1 )); then
  echo "CSP: SvelteKit tidak mengirim policy enforce" >&2
  exit 1
fi
printf 'CSP: validasi SvelteKit berhasil (%s policy di HTML)\n' "$count"
