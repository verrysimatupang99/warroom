# Runbook — restore state War Room (P0-T5)

Tujuan: mengembalikan state yang **tidak bisa dihitung ulang** (ledger `crypto_equity.jsonl`,
watchlist, kandidat/verdict, state GMGN) dari arsip lokal, dan membuktikan hasilnya dengan `sha256`.

PRASYARAT: akses SSH ke Webdock sebagai `admin`. Tidak ada langkah yang menyentuh Tencent,
Azure, atau `/opt/polymarket` — restore murni lokal.

## 0. Kapan dipakai

- Berkas state rusak/kosong (ledger hilang, `snapshot.json` korup, state GMGN terhapus).
- Sebelum percobaan berisiko (migrasi P1, ubah skema) — ambil arsip baru dulu.
- Uji restore rutin (bulanan) — **backup yang tidak pernah diuji bukan backup**.

## 1. Lihat arsip yang ada

```bash
ls -1t ~/live-trading/backups/state-*.tar.gz | head -3
LATEST=$(ls -1t ~/live-trading/backups/state-*.tar.gz | head -1)
sha256sum "$LATEST"                      # catat hash arsip yang dipakai
stat -c '%s byte  %y' "$LATEST"
```

Irama backup: `live-trading-backup.timer` tiap 6 jam, rotasi 14 arsip terakhir
(`scripts/ops/backup-state.sh`). Isi arsip: `live-trading/state` + `gmgn-paper/state`,
relatif terhadap `/home/admin`.

## 2. Restore ke lokasi sementara DULU (jangan langsung menimpa)

```bash
DRILL=/tmp/warroom-restore-drill
rm -rf "$DRILL" && mkdir -p "$DRILL"
LATEST=$(ls -1t ~/live-trading/backups/state-*.tar.gz | head -1)
tar -xzf "$LATEST" -C "$DRILL"
find "$DRILL" -type f | wc -l        # jumlah berkas terekstrak
du -sh "$DRILL"
```

## 3. Verifikasi sebelum menimpa

Bandingkan berkas yang **tidak bisa dihitung ulang** (harus identik):

```bash
for f in live-trading/state/crypto_equity.jsonl live-trading/state/crypto-watchlist.json; do
  echo "$(sha256sum "$DRILL/$f" | cut -d' ' -f1)  arsip  $f"
  echo "$(sha256sum "/home/admin/$f" | cut -d' ' -f1)  live   $f"
done
```

Berkas yang **memang berubah** dan tidak perlu identik: `snapshot.json`, `verdicts.jsonl`,
`outcomes.jsonl`, `arjum_quota.json`, `*cache*`, `*.lock`, `idx616_mirror.json`, `run_config.json`.
Kalau berkas kritis **BEDA** → jangan timpa; selidiki dulu (mungkin arsip lebih tua dari
perubahan sah terakhir).

## 4. Menimpa (hanya bila langkah 3 lolos)

```bash
BACKUP_SEBELUM=/tmp/pre-restore-$(date +%Y%m%d-%H%M).tar.gz
tar -czf "$BACKUP_SEBELUM" -C /home/admin live-trading/state gmgn-paper/state
# hentikan penulis state supaya tidak ada tulisan saat restore
systemctl --user stop live-trading-snapshot.timer 2>/dev/null || true
sudo systemctl stop live-trading-snapshot.timer live-trading-collect.timer live-trading-watchdog.timer
rsync -a --delete "$DRILL/live-trading/state/" /home/admin/live-trading/state/
rsync -a "$DRILL/gmgn-paper/state/" /home/admin/gmgn-paper/state/
sudo systemctl start live-trading-snapshot.timer live-trading-collect.timer live-trading-watchdog.timer
```

Catatan: hentikan **dan** jalankan kembali timer hanya lewat perintah di atas. Jangan pernah
menyalakan unit eksekusi live — gate live tidak disentuh di runbook ini.

## 5. Buktikan hasilnya

```bash
cd ~/live-trading && uv run lt doctor          # 7 jalur data
uv run lt ledger                               # ledger terbaca, 5 trade +3.844R (harapan)
uv run lt snapshot                             # snapshot baru terbentuk (~36 s)
```

## 6. Bukti latihan (dijalankan 2026-10-02)

| Item | Nilai |
|---|---|
| Arsip dipakai | `state-20261002-1547.tar.gz` (3.774.761 byte) |
| `sha256` arsip | `12dbd539f052524f681bc0e26a194389f589fe8e94ed3df14bf320a89549089f` |
| Terekstrak ke | `/tmp/warroom-restore-drill` (69 berkas, 30 MB) |
| Cocok dengan live | **35 berkas** |
| Berbeda (wajar, memang berubah tiap siklus) | 8 berkas: `snapshot.json`, `verdicts.jsonl`, `outcomes.jsonl`, `arjum_quota.json`, `idx616_mirror.json`, `cache/dexscreen/dex.json`, `gmgn-paper/state/cycle.lock`, `gmgn-paper/state/run_config.json` |
| Hilang di live | 0 |
| **Kritis — ledger** `crypto_equity.jsonl` | **COCOK** `5aefeca4…6760` (arsip == live) |
| **Kritis — watchlist** `crypto-watchlist.json` | **COCOK** `8d9dfcf1…894c` (arsip == live) |

Kesimpulan latihan: arsip dapat dipulihkan dan berkas kritis identik dengan state hidup.
Belum ada langkah 4 (penimpaan) yang dijalankan — memang tidak diperlukan saat uji.

## 7. Jangan dilakukan

- Jangan menyimpan arsip/kredensial ke Tencent (read-only) atau repo.
- Jangan menyalin `secrets/` (token Stockbit, kunci API) ke mana pun; restore ini hanya state.
- Jangan menganggap backup sukses hanya karena berkasnya ada — uji ekstrak + `sha256` seperti di atas.