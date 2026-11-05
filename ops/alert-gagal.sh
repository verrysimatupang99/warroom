#!/usr/bin/env bash
# Alarm Telegram bila unit systemd gagal. Dipanggil `warroom-alert@.service`
# lewat `OnFailure=` pada unit yang penting.
#
# Kenapa: backup dan drill restore sudah berjalan otomatis, tetapi kegagalannya
# hanya terlihat kalau ada orang yang membuka `systemctl status`. Backup yang
# gagal diam-diam lebih buruk daripada tidak punya backup, karena ia memberi
# rasa aman yang salah.
#
# Pemakaian (dipanggil systemd, bukan manusia):
#   warroom-alert@warroom-backup-postgres.service
#
# Variabel yang dibaca: WARROOM_TELEGRAM_BOT_TOKEN, WARROOM_TELEGRAM_CHAT_ID,
# WARROOM_TELEGRAM_THREAD_ID (opsional) — dimuat unit lewat EnvironmentFile.
set -uo pipefail

UNIT="${1:-tak-dikenal}"
HOST="$(hostname -s 2>/dev/null || echo host)"
WAKTU="$(date -u '+%Y-%m-%d %H:%M:%SZ')"

TOKEN="${WARROOM_TELEGRAM_BOT_TOKEN:-}"
CHAT="${WARROOM_TELEGRAM_CHAT_ID:-}"
THREAD="${WARROOM_TELEGRAM_THREAD_ID:-}"

if [[ -z "$TOKEN" || -z "$CHAT" ]]; then
	# Jangan menelan kegagalan: tanpa kredensial, alarm tidak terkirim dan itu
	# harus terlihat di journal — bukan keluar dengan status 0 tanpa jejak.
	echo "alert-gagal: WARROOM_TELEGRAM_BOT_TOKEN/CHAT_ID kosong untuk $UNIT" >&2
	exit 1
fi

# Alasan kegagalan diambil dari systemd bila tersedia; kalau tidak, dikosongkan
# (bukan dikarang).
ALASAN="$(systemctl show "$UNIT" -p Result --value 2>/dev/null || true)"
STATUS="$(systemctl show "$UNIT" -p ExecMainStatus --value 2>/dev/null || true)"

TEKS="🚨 [${HOST}] ${UNIT} GAGAL
waktu: ${WAKTU}
result: ${ALASAN:-?} · exit: ${STATUS:-?}
cek: journalctl -u ${UNIT} -n 50"

args=(
	--silent --show-error --max-time 15
	-X POST "https://api.telegram.org/bot${TOKEN}/sendMessage"
	--data-urlencode "chat_id=${CHAT}"
	--data-urlencode "text=${TEKS}"
)
[[ -n "$THREAD" ]] && args+=(--data-urlencode "message_thread_id=${THREAD}")

if ! curl "${args[@]}" >/dev/null; then
	echo "alert-gagal: pengiriman Telegram untuk $UNIT gagal" >&2
	exit 1
fi

echo "alert-gagal: alarm terkirim untuk $UNIT"
