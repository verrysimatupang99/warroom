#!/usr/bin/env bash
# Verifikasi CSP yang SUDAH disajikan (bukan sekadar "ada header") dan sinkronkan
# hash bootstrap ke header Report-Only nginx.
#
# Latar (R1, 9 Okt 2026):
#   - CSP ENFORCE berasal dari SvelteKit adapter-node; hash bootstrap dihitung per build.
#   - nginx menambahkan header Content-Security-Policy-Report-Only sebagai jaring
#     observasi. Dulu header itu memakai `script-src 'self'` TANPA hash bootstrap ->
#     browser mencatat pelanggaran PALSU setiap kali halaman memuat skrip inline
#     SvelteKit ("Executing inline script violates ... 'script-src self'"). Konsol kotor
#     itu menggagalkan tes E2E (cek_csp_enforce + rute/sub via galatKonsol) dan
#     menyamarkan masalah nyata.
#
# Skrip ini:
#   1. Ambil hash bootstrap yang BENAR-BENAR disajikan SvelteKit (dari header enforce).
#   2. Ganti placeholder __BOOTSTRAP_HASH__ di config nginx dengan hash itu, lalu reload.
#   3. Verifikasi ulang: header enforce dan Report-Only harus memuat hash yang sama.
# Bila langkah mana pun gagal, keluar non-nol supaya deploy tidak melaporkan "ok".
set -euo pipefail

OPS_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE="${WARROOM_CSP_BASE:-http://127.0.0.1:3100}"
NGINX_CONF_TMPL="$OPS_DIR/nginx-warroom.conf"
NGINX_CONF_AVAIL="/etc/nginx/sites-available/warroom"
NGINX_CONF_ENABLED="/etc/nginx/sites-enabled/warroom"

# nginx menyajikan berkas di sites-enabled. Di host ini entri itu SALINAN biasa, bukan
# symlink ke sites-available (temuan 31 Okt 2026: hash baru ditulis ke available tetapi
# report-only yang disajikan tetap hash lama). Jadi tulis ke semua target yang ada,
# bukan hanya available.
NGINX_CONF_TARGETS=("$NGINX_CONF_AVAIL")
if sudo -n test -e "$NGINX_CONF_ENABLED"; then
	ENABLED_REAL="$(sudo -n readlink -f "$NGINX_CONF_ENABLED")"
	if [[ "$ENABLED_REAL" != "$NGINX_CONF_AVAIL" ]]; then
		NGINX_CONF_TARGETS+=("$ENABLED_REAL")
	fi
fi

HEADERS="$(mktemp)"
trap 'rm -f "$HEADERS"' EXIT

# 1) Tunggu web hidup lalu ambil header CSP enforce.
for _ in 1 2 3 4 5; do
	if curl -sfI --max-time 5 "$BASE/" >"$HEADERS"; then break; fi
	sleep 2
done

if ! grep -qi '^content-security-policy:' "$HEADERS"; then
	echo "CSP: SvelteKit tidak mengirim policy enforce" >&2
	exit 1
fi

HASH="$(grep -i '^content-security-policy:' "$HEADERS" \
	| grep -oiE "sha256-[A-Za-z0-9+/=]+" | head -n1 || true)"

if [[ -z "$HASH" ]]; then
	echo "CSP: policy enforce tidak memuat hash bootstrap (sha256-...)" >&2
	exit 1
fi

echo "CSP: hash bootstrap yang disajikan -> $HASH"

# 2) Sinkronkan hash ke config nginx (ganti placeholder), hanya bila perlu.
if grep -q '__BOOTSTRAP_HASH__' "$NGINX_CONF_TMPL"; then
	# Tulis config dengan placeholder diganti hash nyata.
	RENDERED="$(mktemp)"
	sed "s|__BOOTSTRAP_HASH__|'$HASH'|g" "$NGINX_CONF_TMPL" >"$RENDERED"
	berubah=0
	for target in "${NGINX_CONF_TARGETS[@]}"; do
		if ! sudo -n test -w "$target"; then
			echo "CSP: tidak bisa menulis $target (butuh sudo -n)" >&2
			rm -f "$RENDERED"
			exit 1
		fi
		if ! diff -q "$RENDERED" "$target" >/dev/null 2>&1; then
			sudo -n install -m 0644 "$RENDERED" "$target"
			berubah=1
		fi
	done
	if (( berubah == 1 )); then
		if ! sudo -n nginx -t >/dev/null 2>&1; then
			echo "CSP: nginx -t GAGAL setelah menulis config — tidak di-reload" >&2
			rm -f "$RENDERED"
			exit 1
		fi
		sudo -n systemctl reload nginx
		echo "CSP: config nginx diperbarui (${#NGINX_CONF_TARGETS[@]} berkas) + reload"
	else
		echo "CSP: config nginx sudah sinkron (hash cocok)"
	fi
	rm -f "$RENDERED"
else
	echo "CSP: placeholder __BOOTSTRAP_HASH__ tidak ditemukan di template — dilewati"
fi

# 3) Verifikasi ulang lewat produksi (nginx): enforce & report-only harus memuat hash.
#    Retry singkat: setelah `nginx -s reload` ada jeda propagasi — sekali baca bisa
#    masih melihat konfigurasi lama. Kegagalan palsu di sini dulu membuat deploy
#    mencetak "CSP enforce gagal" walau enforce sudah benar-benar terpasang.
PUBLIC="${WARROOM_CSP_PUBLIC:-https://0xgunsl1ng3r.xyz}"
PH="$(mktemp)"
ok=0
for _ in 1 2 3 4 5; do
	if curl -sS -D "$PH" -o /dev/null --max-time 8 "$PUBLIC/" 2>/dev/null; then
		# NB: baris enforce dimulai 'content-security-policy:' dan TIDAK memuat 'report-only'.
		# Baris report-only memuat 'Report-Only'. Ambil hash dari masing-masing baris secara tepat.
		enf="$(grep -i '^content-security-policy:' "$PH" | grep -vi 'report-only' | grep -oiE 'sha256-[A-Za-z0-9+/=]+' | head -n1 || true)"
		rep="$(grep -i 'content-security-policy-report-only' "$PH" | grep -oiE 'sha256-[A-Za-z0-9+/=]+' | head -n1 || true)"
		if [[ "$enf" == "$HASH" && "$rep" == "$HASH" ]]; then
			ok=1
			break
		fi
	fi
	sleep 1
done
if (( ok == 1 )); then
	printf 'CSP: OK — enforce & report-only memuat hash yang sama (%s)\n' "$HASH"
else
	printf 'CSP: PERINGATAN — enforce=%s report-only=%s (harus %s)\n' "${enf:-none}" "${rep:-none}" "$HASH" >&2
	rm -f "$PH"
	exit 1
fi
rm -f "$PH"
