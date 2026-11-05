# Insiden: API hash Telegram bocor di repo (ditemukan 5 Nov 2026)

## Ringkasan

API ID + API hash Telethon akun Telegram pribadi bocor di `services/tg-engine/README.md`
dan masuk ke git history lewat commit **`7cd6b09`** ("chore(repo): lebur proyek War Room ke
repo + tg-engine pindah lokasi (#93)", 4 Nov 2026).

- **Terkena:** akun Telegram `Sasc / +6285754257413`, sesi `trading_session.session`
  di `/home/admin/tg-trading-engine/`.
- **Celah:** gitleaks CI **tidak menangkapnya** — pola API hash Telethon (32 hex polos)
  tidak dikenali gitleaks bawaan. Sudah ditutup: aturan `telegram-api-hash` &
  `telegram-api-id` di `.gitleaks.toml`.
- **Mengapa serius:** dengan API ID + API hash + file `.session` yang valid, pihak lain
  dapat **membajak sesi** (baca/balas atas nama akun). File `.session` **tidak** bocor
  (di-gitignore), tetapi pasangan ID+hash adalah separuh kunci; `.session` ada di server
  yang sama.

## Status: BELUM DIPULIHKAN sampai rotasi dilakukan owner

Redaksi README + aturan gitleaks **mencegah kebocoran baru**, tetapi **tidak** menghapus
nilai dari history dan **tidak** membatalkan sesi yang mungkin sudah disalin.

## Langkah pemulihan (wajib, urut)

### 1. Rotasi API hash (owner, di my.telegram.org)
1. Buka <https://my.telegram.org> → *API development tools*.
2. **Hapus** aplikasi yang memakai API ID lama (nilainya tidak ditulis di sini — lihat commit
   `7cd6b09` bila perlu; atau langsung buat aplikasi baru).
3. Catat API ID + API hash **baru**. Jangan tempel di repo/percakapan.

### 2. Cabut sesi lama (owner)
Di dalam aplikasi Telegram → *Settings → Devices* → **Terminate all other sessions**.
Ini mematikan sesi `trading_session` yang mungkin sudah disalin.

### 3. Pasang kredensial baru di server (bukan di repo)
```bash
# di server, sebagai admin — buat berkas 600, isi manual oleh owner
install -d -m 700 ~/.config/tg-engine
install -m 600 /dev/null ~/.config/tg-engine/creds.env
# lalu isi dua baris ini (owner mengetik sendiri, jangan lewat agen/chat):
#   TG_API_ID=<id-baru>
#   TG_API_HASH=<hash-baru>
```
`engine.py` (di-gitignore, di server) harus membaca `TG_API_ID`/`TG_API_HASH` dari env,
bukan hardcode. Generate ulang `trading_session.session` dengan kredensial baru.

### 4. Bersihkan history (setelah rotasi, opsional tapi disarankan)
Karena nilai **sudah tidak valid** setelah langkah 1, penghapusan history bersifat
higienis, bukan penyelamatan. Gunakan `git filter-repo` (bukan `filter-branch`):
```bash
# salinan cadangan dulu
git clone --mirror https://github.com/verrysimatupang99/warroom.git warroom-backup.git
cd warroom
git filter-repo --replace-text <(printf '%s==>ROTATED\n' '<HASH-LAMA>')
git push --force --all && git push --force --tags
```
> `--force` ke `main` melanggar aturan repo. Jalankan hanya setelah owner menyetujui,
> dan umumkan ke semua clone agar `git reset --hard origin/main`.

### 5. Verifikasi
```bash
# tidak ada lagi temuan di HEAD
git grep -nE '(api[ _-]?hash)[^0-9a-f]*[0-9a-f]{32}' || echo "bersih"
# gitleaks pada working tree (bila biner tersedia)
gitleaks dir . --redact --no-banner
```

## Pencegahan (sudah dilakukan di repo)
- `.gitleaks.toml`: aturan `telegram-api-hash` + `telegram-api-id` (teruji menangkap
  format README nyata: `API HASH: \`…\``, `**API HASH:**`, `TelegramClient(...)`).
- README `services/tg-engine/`: nilai kredensial **dihapus**, diganti instruksi env.

## Catatan jujur
- Aturan gitleaks hanya memindai perubahan **baru** (push/PR). Nilai lama di history
  tetap ada sampai langkah 4.
- Rotasi adalah **satu-satunya** tindakan yang benar-benar mematikan risiko; hapus
  README saja tidak cukup.
