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
