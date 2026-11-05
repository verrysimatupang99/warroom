#!/usr/bin/env bash
# verify-server.sh — bukti runtime War Room, jalankan DI SERVER (bukan sandbox agent).
#
# Pakai:
#   ssh -i ~/.ssh/polywarroom_rsa admin@217.78.237.133 'bash -s' < ops/verify-server.sh
# atau salin ke server lalu:  bash verify-server.sh 2>&1 | tee verify-server.out
#
# Skrip ini READ-ONLY: tidak menulis DB, tidak restart unit, tidak menyentuh MT5/VM.
# Semua keluaran adalah bukti yang bisa dibandingkan dengan analisis repo lokal.
set -uo pipefail

hr() { printf '\n===== %s =====\n' "$1"; }

hr "0. IDENTITAS & REPO"
hostname; date -u '+%Y-%m-%dT%H:%M:%SZ'
echo "host IP: $(hostname -I 2>/dev/null | awk '{print $1}')"
cd /home/admin/warroom 2>/dev/null && {
  echo "HEAD   : $(git rev-parse --short HEAD) $(git log -1 --format=%s)"
  echo "origin : $(git rev-parse --short origin/main 2>/dev/null || echo '?')"
  echo "hitung : $(git rev-list --count HEAD) commit"
} || echo "BUKAN di /home/admin/warroom — sesuaikan path"

hr "1. LAYANAN (harus: api/worker/web/nginx active)"
systemctl is-active warroom-api warroom-worker warroom-web nginx 2>&1

hr "2. DISK (konteks: 48G, 33G terpakai per laporan 5 Nov)"
df -h / | tail -1
echo "var/lib/warroom:"; du -sh /var/lib/warroom/* 2>/dev/null | sort -rh | head -6

hr "3. TRADES: ingest ledger->DB benar-benar jalan? (bukti angka)"
if [ -n "${WARROOM_DB_URL:-}" ]; then
  psql "$WARROOM_DB_URL" -At -c \
    "select 'trades total='||count(*) from trades;
     select 'trades by mode: '||mode||'='||count(*) from trades group by mode;
     select 'verdicts='||count(*) from verdicts;" 2>&1
else
  echo "(WARROOM_DB_URL tidak di env shell — jalankan: source /etc/warroom/db.env)"
fi
# Baris job terakhir (ingest + scan)
psql "$WARROOM_DB_URL" -At -c \
  "select name||' | '||coalesce(last_status,'?')||' | '||coalesce(last_detail,'')
   from jobs where name in ('trades-crypto-sync','paper-scan') order by name;" 2>&1

hr "4. SQLITE/STATE LEDGER (kebenaran sumber)"
ls -la /home/admin/live-trading/state/crypto_equity.jsonl 2>/dev/null && \
  echo "baris ledger: $(wc -l < /home/admin/live-trading/state/crypto_equity.jsonl)"
tail -1 /home/admin/live-trading/state/crypto_equity.jsonl 2>/dev/null

hr "5. LIVE GATE (harus TIDAK ada = fail-closed)"
for f in /etc/polymarket/activation-approved /etc/warroom/crypto-live-approved; do
  if [ -e "$f" ]; then echo "ADA (perlu perhatian!): $f"; else echo "tidak ada (aman): $f"; fi
done

hr "6. TELEMETRI MT5: bridge terpasang? endpoint hidup?"
find / -iname '*TelemetryBridge*' 2>/dev/null | head
# bridge EA kirim ke /tencent/mt5/telemetry (bukan /telemetry/push)
curl -s -o /dev/null -w "POST /api/v1/tencent/mt5/telemetry -> HTTP %{http_code}\n" \
  -X POST -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8800/api/v1/tencent/mt5/telemetry 2>&1

hr "7. P0 TELEGRAM: sesi masih aktif? (risiko hash bocor)"
systemctl list-units --type=service --all 2>/dev/null | grep -iE 'tg|trading-engine' | head
pgrep -af 'telethon|tg-engine' 2>/dev/null | head
ls -la /home/admin/tg-trading-engine/*.session 2>/dev/null
echo "--- apakah engine.py masih hardcode hash? ---"
grep -nE 'api_hash|API_HASH|ea452b7e' /home/admin/tg-trading-engine/engine.py 2>/dev/null | sed 's/ea452[0-9a-f]*/<REDACTED>/'

hr "8. BACKUP: tujuan offsite ada?"
ls -la /home/admin/backups/postgres/ 2>/dev/null | tail -3
systemctl list-timers --all 2>/dev/null | grep -iE 'backup|restore' | head

hr "9. TAG: konfirmasi 3 item sisa"
echo "branch lokal :"; git branch 2>/dev/null | head
echo "--- remote branch yang tertinggal (kandidat hapus, verifikasi 0 commit unik) ---"
git fetch --prune origin >/dev/null 2>&1
for b in feat/sumber-okx-idx-mt5 docs/backtest-reaper-1k; do
  [ -n "$(git branch -r --list origin/$b)" ] && \
    echo "$b : $(git rev-list --count HEAD..origin/$b) commit di luar main"
done

hr "SELESAI — tempel seluruh keluaran ini untuk dianalisis"
