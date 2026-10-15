# Changelog Sektor 04 — Layanan API & SSE

Catatan perubahan pada antarmuka REST API, streaming Server-Sent Events, dan kontrol otorisasi.

## Perkembangan Terkini

### Ditambahkan
- **Streaming SSE Real-Time (`/api/v1/stream`)**: Penyaluran event bus langsung ke antarmuka web dengan dukungan filter topik per pasar dan deduplikasi ID kejadian.
- **Role-Based Access Control (RBAC)**: Pembatasan akses berbasis cookie sesi dengan level izin berjenjang (`viewer`, `operator`, `owner`).
- **Endpoint Agregasi Performa (`/api/v1/pasar/*`)**: Penyediaan ringkasan statistik, akurasi trade tuntas, dan bukti transaksi tanpa manipulasi di sisi perantara.
- **Dukungan Kontrak Leaderboard**: Penyiapan rute endpoint untuk data pemeringkatan strategi antar-pasar.

### Diperbaiki
- Penanganan SSE disconnection dan buffer event backfill memastikan riwayat kejadian lokal segera tersedia saat halaman dimuat.
