# ADR: Cutover `~/live-trading` — kode mati, data hidup

Status: **SELESAI** (dijalankan owner 14 Okt 2026 18:35).
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

## Hasil (14 Okt 2026 18:35)

- `infra-watchdog.service` → venv warroom (`ops/ops-scripts/infra-watchdog.py`),
  jalan exit 0. ✓
- `.venv.lama`, `.venv`, `src` dihapus; arsip 114 MB di
  `~/arsip/live-trading-kode-20261014.tar.gz`. ✓
- `~/live-trading`: 1,7 GB → **104 MB**; `state/` (63 berkas data) utuh. ✓
- Tak ada unit menyentuh venv lama lagi. ✓

## Temuan ikutan (penting): migrasi DB produksi tertunda 3 revisi

Saat verifikasi pasca-cutover, ditemukan **DB produksi masih di revisi
`a1f2c3d4e5b6`** — padahal head `c3d5e7f9a1b2`. Tiga migrasi BELUM diterapkan:

1. `f1a2b3c4d5e6` — research contracts (P1).
2. `d2c4e6f8a0b1` — **kolom `users.totp_last_counter` (anti-replay TOTP, PR #3)**.
3. `c3d5e7f9a1b2` — rename job (PR #23).

Akibatnya PR #3 (kode anti-replay TOTP) **aktif di kode tapi tak punya kolomnya
di DB** selama ini; dan setelah PR #23 handler job mati (diperbaiki di PR #25
dengan alias nama lama).

Karena itu `alembic upgrade head` dijalankan 14 Okt 18:44 (backup dulu:
`~/arsip/db-pre-migrasi-20261014-1842.sql`, 200 MB). DB kini di `c3d5e7f9a1b2`.

**Akar masalah proses:** migrasi DB dijalankan MANUAL; tidak ada `ExecStartPre`
dan tidak ada di CI. Setiap PR yang menyentuh skema berisiko merge tanpa pernah
menerapkannya. → dicatat sebagai utang (lihat peta).

