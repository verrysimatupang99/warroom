#!/bin/bash
set -u
PROJ=/home/admin/live-trading/crypto
H=/home/admin/.hermes

echo "=== 1. cek dulu: apa yang sudah ada di ~/.hermes ==="
ls -d $H/state $H/crypto-journal $H/crypto-watchlist.json 2>/dev/null || echo "  (belum ada, aman dibuat)"
ls $H/state 2>/dev/null | head -5

echo; echo "=== 2. pasang symlink ke project (satu sumber data, bukan duplikat) ==="
mkdir -p $H/state
ln -sfn $PROJ/state/crypto-watchlist.json $H/crypto-watchlist.json
ln -sfn $PROJ/state/crypto_equity.jsonl   $H/state/crypto_equity.jsonl
mkdir -p $H/crypto-journal
ln -sfn $PROJ/journal/crypto_journal.xlsx $H/crypto-journal/crypto_journal.xlsx

ls -la $H/crypto-watchlist.json $H/state/crypto_equity.jsonl $H/crypto-journal/crypto_journal.xlsx

echo; echo "=== 3. ulang tes equity (harusnya 5 trade, +3.844R) ==="
cd $PROJ/scripts
timeout 90 python3 crypto_equity.py 2>&1 | head -14

echo; echo "=== 4. crypto_pipeline_collect.py (pakai watchlist) ==="
timeout 180 python3 crypto_pipeline_collect.py > /tmp/pipe.txt 2>/tmp/pipe.err
echo "exit: $?  | baris: $(wc -l < /tmp/pipe.txt)"
head -12 /tmp/pipe.txt
echo "--- err (3 baris) ---"; tail -3 /tmp/pipe.err
