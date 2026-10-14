# Keputusan: Kanonik Kode Domain = packages/live-trading

Status: ditetapkan 14 Okt 2026 (audit cutover `~/live-trading`).
Pengambil keputusan: owner (delegasi ke agen), berbasis bukti mtime + git log.

## Pertanyaan

Dua salinan kode domain beredar dan berbeda (37 berkas divergen):

- `~/live-trading/src/live_trading/` — dipakai `.venv/bin/lt` di sana (`.pth`
  menunjuk ke sini). **Ini yang benar-benar dijalankan watchdog produksi.**
- `packages/live-trading/src/live_trading/` — diuji CI, anggota workspace (ADR-002/F3).

Mana yang kanonik?

## Bukti

| Berkas | LUAR (mtime) | DALAM (mtime) | Pemenang |
|---|---|---|---|
| `cli.py` | 7 Okt 18:31 (42 KB) | 10 Okt 11:37 (45 KB) | DALAM |
| `config.py` | 4 Okt 19:26 (4,9 KB) | 10 Okt 07:09 (5,6 KB) | DALAM |
| `dashboard.py` | 4 Okt 19:28 (94 KB) | 11 Okt 11:57 (99 KB) | DALAM |
| `lp_positions.py` | 4 Okt 10:40 (9,7 KB) | 11 Okt 11:54 (10 KB) | DALAM |
| `__init__.py` | 4 Okt 05:39 | 10 Okt 07:09 | DALAM |

- Repo luar berhenti di `e3331e5` (7 Okt). Repo dalam memuat komit keputusan owner:
  `refactor(crypto): ganti MEXC -> OKX total (keputusan owner 10 Okt)`,
  `feat(lp): mark LP terukur + pakem bukti`.
- Berkas hanya-ada-di-DALAM: `dompet.py`, `lp_mark.py`, `pasar.py`,
  `bandarmologi_skor.py`, `golden_pullback.py`, `idx_akurasi.py`, dll.
- `config.py` DALAM: `home: Path = ~/live-trading` — **dirancang** agar kode
  (packages) dan data (`~/live-trading`) hidup terpisah.

## Keputusan

1. **KODE kanonik = `packages/live-trading/src/live_trading/`.** Repo luar
   `~/live-trading/src` adalah salinan lama; ia tidak boleh lagi jadi sumber kode.
2. **DATA runtime tetap di `~/live-trading`** (state/, secrets/, backups/,
   index-cache/, logs/) — ini LT_HOME yang dirancang `config.py`, bukan utang.
3. **Koreksi penting (audit lanjutan):** produksi **sudah** memakai kode DALAM.
   Semua unit system `live-trading-{snapshot,collect,watchdog,dashboard}.service`
   memakai `ExecStart=/home/admin/warroom/.venv/bin/lt`, dan venv warroom menunjuk
   `packages/live-trading/src/live_trading` (editable). Yang menunjuk kode LUAR
   hanyalah `.venv/bin/lt` di `~/live-trading` — **venv lama yang tidak dipakai
   unit mana pun** (sisa 6 Okt; `_editable_impl_live_trading.pth` -> `~/live-trading/src`).

### Uji banding watchdog (bukti kode DALAM lebih benar)

| Cek | LUAR (venv lama) | DALAM (kanonik) |
|---|---|---|
| lp_mark | `basi inf` (path salah) | `basi 6443 mnt` (benar) |
| radar | `radar_azure` (usang, Azure dilepas 6 Okt) | `radar_lokal` (benar) |

`lt doctor` dijalankan dari venv warroom + `LT_HOME=~/live-trading`:
**7/7 jalur data hidup, mode PAPER** — kode kanonik kompatibel dengan data lama.

## Konsekuensi

- `ops/warroom-worker.service` & `warroom-api.service`: `WARROOM_DOMAIN_HOME`
  tetap `~/live-trading` (untuk state) — **tidak berubah**.
- **`~/live-trading/src` + `.venv` lama = sisa mati**, bukan jalur produksi.
  Boleh diarsipkan (jangan langsung hapus) setelah cek terakhir unit user.
- Satu unit user masih menyentuh kode luar: `~/.config/systemd/user/infra-watchdog.service`
  (`~/live-trading/.venv/bin/python ~/live-trading/scripts/ops/infra-watchdog.py`).
  Perlu dipindah ke venv warroom — **belum dieksekusi**; `systemctl --user`
  tidak dapat diakses dari sesi ini, jadi butuh verifikasi terpisah.

## Catatan kejujuran

Klaim awal audit ("kode produksi yang berjalan justru lebih TUA") ternyata
**salah** — saya menyimpulkan terlalu cepat dari `.pth` venv luar, tanpa dulu
memeriksa unit systemd mana yang sebenarnya dijalankan. Setelah dicek: produksi
sudah memakai kode kanonik. `~/live-trading/.venv` adalah sisa yang menyesatkan.

