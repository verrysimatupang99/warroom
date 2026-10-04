#!/bin/bash
# Satukan ledger & watchlist: satu file kanonik, sisanya symlink.
# Sebelum ini: crypto/state/ (warisan) dan state/ (baru) bisa berbeda isi.
set -eu
ROOT=/home/admin/live-trading
H=/home/admin/.hermes

echo "=== 1. adopsi ledger & watchlist warisan ke lokasi kanonik ==="
mkdir -p "$ROOT/state"
if [ -f "$ROOT/crypto/state/crypto_equity.jsonl" ] && [ ! -f "$ROOT/state/crypto_equity.jsonl" ]; then
  cp "$ROOT/crypto/state/crypto_equity.jsonl" "$ROOT/state/crypto_equity.jsonl"
  echo "  ledger warisan disalin ke state/"
fi
if [ -f "$ROOT/crypto/state/crypto-watchlist.json" ] && [ ! -f "$ROOT/state/crypto-watchlist.json" ]; then
  cp "$ROOT/crypto/state/crypto-watchlist.json" "$ROOT/state/crypto-watchlist.json"
  echo "  watchlist warisan disalin ke state/"
fi

echo "=== 2. jadikan lokasi lama sebagai symlink (biar script warisan ikut file yang sama) ==="
ln -sfn "$ROOT/state/crypto_equity.jsonl"   "$ROOT/crypto/state/crypto_equity.jsonl"
ln -sfn "$ROOT/state/crypto-watchlist.json" "$ROOT/crypto/state/crypto-watchlist.json"
ln -sfn "$ROOT/state/crypto_equity.jsonl"   "$H/state/crypto_equity.jsonl"
ln -sfn "$ROOT/state/crypto-watchlist.json" "$H/crypto-watchlist.json"

echo "=== 3. bukti: semua jalur menunjuk berkas yang sama ==="
for p in "$ROOT/state/crypto_equity.jsonl" "$ROOT/crypto/state/crypto_equity.jsonl" "$H/state/crypto_equity.jsonl"; do
  printf "  %-52s %s\n" "${p/#\/home\/admin/\~}" "$(readlink -f "$p")"
done
echo "  inode kanonik: $(stat -c %i "$ROOT/state/crypto_equity.jsonl")"
