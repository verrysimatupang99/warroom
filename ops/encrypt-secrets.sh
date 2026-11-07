#!/usr/bin/env bash
# encrypt-secrets.sh — Bungkus /etc/warroom (rahasia) jadi satu arsip terenkripsi
# yang AMAN dikirim keluar server (Drive/offsite). Tanpa ini, dump Postgres tidak
# bisa dihidupkan di host lain — audit 2026-11-03 §2.4.
#
# Prinsip:
#  - Simetris (gpg -c) dengan passphrase dari FILE atau STDIN, tidak pernah argv
#    (argv terlihat di `ps` oleh semua user).
#  - Plaintext TIDAK PERNAH menyentuh disk: tar -> gpg lewat pipe.
#  - Rotasi menjaga maks KEEP arsip; arsip lama dihapus bersama sha256-nya.
#  - Gagal = keluar non-zero, tidak meninggalkan .part yang tampak sah.
#
# Pemakaian (lewat unit systemd, passphrase dari file 600 root):
#   WARROOM_SECRETS_PASSPHRASE_FILE=/root/.warroom-secrets.pass bash encrypt-secrets.sh
# Atau interaktif:
#   bash encrypt-secrets.sh            # akan meminta passphrase dua kali
set -euo pipefail

SRC="${WARROOM_SECRETS_SRC:-/etc/warroom}"
OUT_DIR="${WARROOM_SECRETS_OUT_DIR:-/home/admin/backups/secrets}"
KEEP="${WARROOM_SECRETS_KEEP:-14}"
PASS_FILE="${WARROOM_SECRETS_PASSPHRASE_FILE:-}"

[[ -d "$SRC" ]] || { echo "GAGAL: $SRC tidak ada"; exit 1; }
command -v gpg >/dev/null || { echo "GAGAL: gpg tidak ditemukan"; exit 1; }
command -v tar >/dev/null || { echo "GAGAL: tar tidak ditemukan"; exit 1; }

umask 077
mkdir -p "$OUT_DIR"
stamp="$(date -u +%Y%m%d-%H%M%S)"
out="$OUT_DIR/warroom-secrets-$stamp.tar.gz.gpg"
part="$out.part"
trap 'rm -f "$part"' EXIT

# Passphrase: file (unit systemd) atau prompt interaktif. Tidak pernah lewat argv.
gpg_opt+=( --batch --yes --symmetric --cipher-algo AES256 --pinentry-mode loopback )
if [[ -n "$PASS_FILE" ]]; then
	[[ -r "$PASS_FILE" ]] || { echo "GAGAL: passphrase file tidak terbaca: $PASS_FILE"; exit 1; }
	gpg_opt+=( --passphrase-file "$PASS_FILE" )
else
	[[ -t 0 ]] || { echo "GAGAL: tidak ada TTY dan tidak ada passphrase file"; exit 1; }
	read -rsp "Passphrase: " P1; echo
	read -rsp "Ulangi    : " P2; echo
	[[ "$P1" == "$P2" && -n "$P1" ]] || { echo "GAGAL: passphrase kosong/tidak sama"; exit 1; }
	PASS_FILE_TMP="$(mktemp)"; printf '%s' "$P1" > "$PASS_FILE_TMP"
	chmod 600 "$PASS_FILE_TMP"; trap 'rm -f "$part" "$PASS_FILE_TMP"' EXIT
	gpg_opt+=( --passphrase-file "$PASS_FILE_TMP" )
	unset P1 P2
fi

# tar -> gpg lewat pipe: plaintext tidak pernah ditulis ke disk.
tar -C "$(dirname "$SRC")" -czf - "$(basename "$SRC")" | gpg "${gpg_opt[@]}" -o "$part"

[[ -s "$part" ]] || { echo "GAGAL: hasil enkripsi kosong"; exit 1; }
# Sanity: cek magic OpenPGP (0x8c 0x0d 0x04 = symmetric encrypted packet).
# JANGAN pakai `gpg --list-packets` di sini: tanpa passphrase ia memanggil gpg-agent,
# gagal dgn "Inappropriate ioctl for device" di unit non-TTY, dan exit code-nya tetap 0
# sehingga validasi salah tempat. Cek byte tidak butuh agent sama sekali.
magic="$(head -c 3 "$part" | od -An -tx1 | tr -d " \n")"
[[ "$magic" == "8c0d04" ]] || { echo "GAGAL: arsip bukan OpenPGP symmetric (magic=$magic)"; exit 1; }

mv -f "$part" "$out"
trap - EXIT
( cd "$OUT_DIR" && sha256sum "$(basename "$out")" > "$(basename "$out").sha256" )
echo "rahasia: $out ($(du -h "$out" | cut -f1)) + .sha256"

# Rotasi
ls -1t "$OUT_DIR"/warroom-secrets-*.tar.gz.gpg 2>/dev/null | tail -n "+$((KEEP + 1))" | while read -r f; do
	rm -f "$f" "$f.sha256"
	echo "rotasi: hapus $(basename "$f")"
done
rm -f "$OUT_DIR"/warroom-secrets-*.tar.gz.gpg.part 2>/dev/null || true
