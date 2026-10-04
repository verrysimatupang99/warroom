#!/bin/bash
# Backup state + deteksi snapshot basi.
#
# Kenapa ini P0: ledger hanya ada SATU salinan. Berkas itu hilang = seluruh riwayat
# keputusan hilang, dan tidak ada cara menghitungnya ulang. Backup menyalin ke lokal
# dan menggili 14 arsip terakhir.
#
# BATAS: Tencent tidak dipakai sebagai tujuan apa pun. Ia read-only — hanya untuk
# membaca/mengambil data (perintah user, 27 Sep 2026). Proyek ini standalone di Webdock.
set -uo pipefail

ROOT=/home/admin/live-trading
DEST="$ROOT/backups"
STAMP=$(date +%Y%m%d-%H%M)
KEEP=14
SNAPSHOT_MAX_AGE=1800   # 30 menit

mkdir -p "$DEST"

echo "=== 1. arsipkan state yang tidak bisa dihitung ulang ==="
ARCHIVE="$DEST/state-$STAMP.tar.gz"
tar -czf "$ARCHIVE" \
  -C /home/admin live-trading/state gmgn-paper/state \
  --exclude='*.pyc' --exclude='__pycache__' 2>/dev/null
if [ -s "$ARCHIVE" ]; then
  echo "  arsip: $(du -h "$ARCHIVE" | cut -f1) -> $ARCHIVE"
else
  echo "  GAGAL membuat arsip"; exit 1
fi

echo "=== 2. gilir arsip lokal (simpan $KEEP terakhir) ==="
ls -1t "$DEST"/state-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old"; echo "  hapus lama: $(basename "$old")"
done

echo "=== 3. kirim ke lokasi cadangan luar-server ==="
# BATAS: Tencent TIDAK diganggu (perintah user, 27 Sep 2026) — tidak ada tulis,
# kirim, atau ubah apa pun di sana. Backup luar-server menunggu tujuan lain
# (mis. object storage) sebelum diaktifkan. Backup lokal di atas sudah cukup
# untuk melindungi dari kehilangan berkas di mesin ini.
echo "  dilewati: belum ada tujuan luar-server yang disetujui"

echo "=== 4. deteksi snapshot basi (dashboard bisa menyajikan angka lama) ==="
SNAP="$ROOT/state/snapshot.json"
if [ -f "$SNAP" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$SNAP") ))
  MINS=$((AGE / 60))
  if [ "$AGE" -gt "$SNAPSHOT_MAX_AGE" ]; then
    echo "  PERINGATAN: snapshot berumur ${MINS} menit (> $((SNAPSHOT_MAX_AGE / 60)) menit)"
    echo "  dashboard mungkin menampilkan angka lama."
    exit 2
  fi
  echo "  snapshot segar (${MINS} menit)"
else
  echo "  PERINGATAN: snapshot belum ada"
  exit 2
fi
exit 0
