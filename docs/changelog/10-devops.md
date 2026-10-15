# Changelog Sektor 10 — DevOps & Infrastruktur

Catatan perubahan pada manajemen unit systemd, konfigurasi reverse proxy web, pipeline deployment, dan otomatisasi host.

## Perkembangan Terkini

### Ditambahkan
- **Konfigurasi Unit Systemd Terpadu (`ops/*.service`)**: Unit mandiri untuk `warroom-api`, `warroom-worker`, dan `warroom-web` dengan isolasi hak akses user `admin` dan restart otomatis saat crash.
- **Reverse Proxy Nginx Teroptimasi (`ops/nginx-warroom.conf`)**: Konfigurasi vhost produksi dengan pengalihan otomatis HTTP ke HTTPS, dukungan TLS Let's Encrypt (Certbot), dan penonaktifan buffer proxy (`proxy_buffering off`) khusus endpoint SSE (`/api/v1/stream`).
- **Skrip Deploy Frontend Aman (`ops/deploy-web.sh`)**: Skrip build yang menjamin proses kompilasi bundler Vite/SvelteKit selesai sepenuhnya sebelum me-restart unit systemd `warroom-web`, mencegah insiden node manifest mismatch 500.
- **Migrasi Radar Rantai Lokal**: Pemindahan parser radar blockchain ke host lokal (`lt radar-update`) yang menyimpan state ke `state/radar_state.json`, menghapus ketergantungan pada VM Azure.

### Diperbaiki
- Sinkronisasi lingkungan eksekusi worktree Git menggunakan symlink dependensi `node_modules` untuk efisiensi ruang disk dan keandalan tooling.
- Manajemen hak akses sudo terbatas melalui allowlist eksplisit di `/etc/sudoers.d/warroom-poly-readonly` untuk eksekusi skrip audit read-only.
