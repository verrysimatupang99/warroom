# Changelog Sektor 11 — Keamanan & Kepatuhan

Catatan perubahan pada perlindungan rahasia, penguncian gerbang eksekusi live, kontrol akses berbasis peran (RBAC), dan mitigasi risiko operasional.

## Perkembangan Terkini

### Ditambahkan
- **Deteksi Kebocoran Rahasia Otomatis (`gitleaks`)**: Integrasi scanning token, kunci privat, dan rahasia API pada alur CI lokal (`ops/ci-local.sh`) serta GitHub Actions workflow sebelum commit diterima.
- **Isolasi Berkas Rahasia Sistem**: Penyimpanan variabel sensitif dan token lingkungan di luar direktori repositori (`/etc/warroom/*.env` dengan izin berkas 600 milik root dan `~/.config/warroom/`).
- **Gerbang Keamanan Live Terkunci Fisik**: Penegakan aturan bahwa transaksi live di Polymarket atau broker hanya dapat dieksekusi jika file izin khusus (`/etc/poly-pilot/activation-approved`) telah disetujui secara sadar oleh owner. Tanpa grant eksplisit, sistem secara tegas menolak aksi live dengan status HTTP 409 Conflict.
- **Prinsip Least-Privilege & Read-Only**: Penerapan akses baca-saja penuh pada direktori `/opt/polymarket` dan node Tencent, mencegah perubahan konfigurasi atau modifikasi data paper dari luar alur resmi.
- **Sanitasi Prompt & Konteks LLM**: Pembersihan data masukan dari feed pihak ketiga sebelum diumpankan ke model bahasa guna memitigasi serangan prompt injection dan pembajakan instruksi agen.

### Diperbaiki
- Standarisasi autentikasi cookie HttpOnly dengan perlindungan CSRF dan pembagian peran pengguna (read-only viewer vs operator).
- `sudo stat` dihapus dari runtime infra-watchdog (f573e6f): perintah tidak ada di
  allowlist sudoers, jadi kini mtime dibaca langsung; gagal izin jatuh ke penanganan
  pemanggil ("tak-terbaca: PermissionError"), bukan angka karangan.
- Konstanta `ALLOW_SUDO_CAT` yang tak terpakai dibuang (8cd332a); sumber kebenaran
  allowlist tetap `/etc/sudoers.d/warroom-poly-readonly` (cat baca-saja, tanpa `stat`).

### Verifikasi (16 Okt 2026)
- `uv run pytest -q` (root): **952 tes, 0 gagal, 0 error, 2 skip** (junitxml, 2 run).
- Subset terdampak — `test_api::test_fakta_basi_ditandai_basi`, `services/worker/tests/test_schedule.py`,
  `services/api/tests/test_live_grants.py`, `packages/live-trading/tests/test_watchdog.py` —
  37/37 lulus.
- `uv run ruff check ops/ packages/live-trading/scripts/`: All checks passed.
- `python3 ops/ops-scripts/infra-watchdog.py`: RC=0, gate=DISARMED, tanpa galat izin
  (snipe-state terbaca; 1 staleness + beberapa unit down = temuan lingkungan, bukan regresi).
- Salinan `ops/ops-scripts/` dan `packages/live-trading/scripts/ops/` infra-watchdog identik.
- Catatan: `sudo -n stat` masih berhasil di sesi interaktif karena baris `%sudo` blanket —
  batas konteks systemd terbukti lewat auth.log (lihat komentar di allowlist); verifikasi
  ulang konteks systemd tidak bisa dijalankan dari sesi ini (bus pengguna tak tersedia).
