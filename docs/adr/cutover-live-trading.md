# ADR: Cutover `~/live-trading` — kode mati, data hidup

Status: **rencana siap; eksekusi menunggu** (butuh akses `systemctl --user`).
Tanggal: 14 Okt 2026.

## Ringkasan

`~/live-trading` menjalankan DUA peran:

1. **DATA runtime** (`state/`, `secrets/`, `backups/`, `logs/`, `index-cache/`) —
   HIDUP, dipakai `WARROOM_DOMAIN_HOME` oleh `warroom-worker`/`warroom-api`.
   → **TIDAK disentuh.**
2. **KODE lama** (`src/`, `.venv`, `.venv.lama`) — sudah digantikan
   `packages/live-trading` (kanonik, lihat ADR kanonik-kode-domain).
   → **Diarsipkan** (bukan dihapus), setelah 1 unit dimigrasikan.

## Sisa yang menunjuk kode lama

Satu unit user masih memakai venv lama:
`~/.config/systemd/user/infra-watchdog.service`:
```
ExecStart=/home/admin/live-trading/.venv/bin/python /home/admin/live-trading/scripts/ops/infra-watchdog.py
```

Semua unit system lain (`live-trading-{snapshot,collect,watchdog,dashboard}`)
SUDAH memakai venv warroom.

## Langkah cutover (belum dieksekusi)

1. Migrasikan `infra-watchdog.service`:
   - `ExecStart` → `/home/admin/warroom/.venv/bin/python <script>.py`
   - salin `scripts/ops/infra-watchdog.py` ke `ops/` repo warroom (atau arahkan).
   - verifikasi jalan: `systemctl --user start infra-watchdog.service` + cek log.
2. Setelah itu, arsipkan kode lama:
   ```
   tar -czf ~/arsip-live-trading-kode-YYYYMMDD.tar.gz -C ~/live-trading src .venv .venv.lama
   rm -rf ~/live-trading/.venv.lama      # 146 MB, pasti mati (venv super lama)
   # .venv + src: hapus HANYA setelah langkah 1 tuntas
   ```
3. Jangan sentuh `state/`, `secrets/`, `backups/`, `logs/`, `index-cache/`.

## Kenapa butuh akses khusus

`systemctl --user` dari sesi agen gagal ("Failed to connect to bus"). Owner perlu
menjalankan langkah 1 di sesi login.

## Cara cepat

```
bash ~/warroom/ops/cutover-live-trading.sh
```

Skrip menjalankan langkah 0-4 di atas dengan **konfirmasi di tiap langkah
destruktif** dan **guard** (berhenti bila masih ada unit menyentuh venv lama).
Tidak menyentuh `state/`/`secrets/`/`backups/`. Bila dijalankan dari sesi tanpa
bus user, ia berhenti di Prakondisi (exit 1) tanpa mengubah apa pun.

## Risiko bila salah

- Menghapus `.venv` sebelum migrasi → `infra-watchdog` mati (hanya watchdog,
  bukan jalur trading). Dampak terbatas, tapi tetap dihindari.
- Menghapus `state/` → KEHILANGAN DATA. Dilarang keras.
