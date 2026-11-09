#!/usr/bin/env bash
# talk — papan diskusi asinkron lintas agent & lintas komputer.
#
# Pakai:
#   talk post "catatan"                  kirim ke topik default
#   talk post -t warroom -k keputusan "…"
#   talk read                            pesan baru sejak terakhir dibaca
#   talk read -n 20                      20 pesan terakhir
#   talk watch                           terus ikut (poll 15 dtk)
#   talk topics / agents / unread / whoami
#
# Topik default dari BUS_TOPIC (default: warroom).
# Nama agent dari BUS_AGENT (default: nama host).
set -uo pipefail

BASE="${BUS_URL:-https://polywarroom.vps.webdock.cloud/bus}"
TOKEN="${BUS_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -r /etc/warroom/bus_token.env ]; then
  TOKEN=$(sed -n 's/^BUS_TOKEN=//p' /etc/warroom/bus_token.env | tr -d '"')
fi
if [ -z "$TOKEN" ] && [ -r "$HOME/.config/warroom/bus_token.env" ]; then
  TOKEN=$(sed -n 's/^BUS_TOKEN=//p' "$HOME/.config/warroom/bus_token.env" | tr -d '"')
fi
[ -z "$TOKEN" ] && { echo "talk: BUS_TOKEN belum diset" >&2; exit 2; }

AGENT="${BUS_AGENT:-$(hostname -s 2>/dev/null || echo agent)}"
TOPIC="${BUS_TOPIC:-warroom}"
STATE="${BUS_STATE:-$HOME/.cache/warroom-bus}"
mkdir -p "$STATE" 2>/dev/null

api() {
  local m="$1" p="$2" d="${3:-}"
  if [ -n "$d" ]; then
    curl -sS -m 30 -X "$m" "$BASE$p" -H "X-Bus-Token: $TOKEN" \
         -H "Content-Type: application/json" --data-binary "$d"
  else
    curl -sS -m 30 -X "$m" "$BASE$p" -H "X-Bus-Token: $TOKEN"
  fi
}

json_esc() { python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'; }

cmd="${1:-read}"; shift 2>/dev/null || true
kind="note"; topic="$TOPIC"; n=""; since=""

case "$cmd" in
  post)
    while getopts "t:k:" o; do case $o in t) topic=$OPTARG;; k) kind=$OPTARG;; esac; done
    shift $((OPTIND-1))
    text="${*:-}"
    [ -z "$text" ] && { echo "talk post: butuh teks" >&2; exit 2; }
    body=$(printf '{"agent":"%s","host":"%s","topic":"%s","kind":"%s","text":%s}' \
      "$AGENT" "$(hostname 2>/dev/null || echo '?')" "$topic" "$kind" "$(printf '%s' "$text" | json_esc)")
    r=$(api POST /post "$body")
    echo "$r" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
    print("terkirim #%s (%s)" % (d["seq"], d["topic"]) if d.get("ok") else "GAGAL: %s" % d)
except Exception:
    print("GAGAL: respons tidak valid")'
    ;;

  read)
    while getopts "t:n:s:" o; do case $o in t) topic=$OPTARG;; n) n=$OPTARG;; s) since=$OPTARG;; esac; done
    shift $((OPTIND-1))
    curf="$STATE/$topic.$AGENT"
    [ -z "$since" ] && [ -r "$curf" ] && since=$(cat "$curf")
    if [ -n "$n" ]; then
      q="?topic=$topic&limit=$n"
    else
      q="?topic=$topic&since=${since:-0}&agent=$AGENT"
    fi
    out=$(api GET "/messages$q")
    printf '%s' "$out" | python3 -c '
import json,sys,time
d=json.load(sys.stdin)
ms=d.get("messages",[])
if not ms:
    print("(tidak ada pesan baru)")
for m in ms:
    jam=time.strftime("%d %b %H:%M", time.localtime(m["ts"]))
    print("[%s] %s %s@%s (%s)" % (m["seq"], jam, m["agent"], m["host"], m["kind"]))
    for line in m["text"].splitlines():
        print("    "+line)
if ms: print("--- %d pesan, s/d #%s" % (len(ms), ms[-1]["seq"]))
'
    if [ -z "$n" ] && [ -n "$out" ]; then
      last=$(printf '%s' "$out" | python3 -c 'import json,sys;d=json.load(sys.stdin);m=d.get("messages") or [];print(m[-1]["seq"] if m else "")' 2>/dev/null)
      [ -n "$last" ] && echo "$last" > "$curf"
    fi
    ;;

  watch)
    while getopts "t:" o; do case $o in t) topic=$OPTARG;; esac; done
    shift $((OPTIND-1))
    curf="$STATE/$topic.$AGENT"
    [ -r "$curf" ] || echo 0 > "$curf"
    echo "memantau topik '$topic' sebagai '$AGENT' (Ctrl-C berhenti)"
    while :; do
      since=$(cat "$curf")
      out=$(api GET "/messages?topic=$topic&since=$since&agent=$AGENT")
      printf '%s' "$out" | python3 -c '
import json,sys,time
d=json.load(sys.stdin)
for m in d.get("messages",[]):
    jam=time.strftime("%H:%M", time.localtime(m["ts"]))
    print("[%s] %s %s (%s): %s" % (m["seq"], jam, m["agent"], m["kind"], m["text"][:300]))
last=(d.get("messages") or [{}])[-1].get("seq")
if last: print("__LAST__ %s" % last)
' | tee /tmp/.talkwatch | grep -v '^__LAST__'
      l=$(grep '^__LAST__' /tmp/.talkwatch | tail -1 | awk '{print $2}')
      [ -n "${l:-}" ] && echo "$l" > "$curf"
      sleep "${BUS_POLL:-15}"
    done
    ;;

  topics) api GET /topics | python3 -m json.tool ;;
  agents) api GET /agents | python3 -m json.tool ;;
  unread) api GET "/unread?agent=$AGENT" | python3 -m json.tool ;;
  whoami) echo "agent=$AGENT host=$(hostname) topic=$TOPIC base=$BASE" ;;
  *) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//' ;;
esac