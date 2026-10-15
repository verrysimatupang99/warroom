# Changelog Sektor 07 — Notifikasi & Komunikasi

Catatan perubahan pada layanan pengiriman sinyal, alert operasional, dan integrasi kanal komunikasi.

## Perkembangan Terkini

### Ditambahkan
- **Layanan Notifikasi Mandiri (`services/notifier`)**: Komponen terisolasi untuk mendistribusikan notifikasi tanpa menggantung proses caller.
- **Transport Multi-Kanal**: Dukungan transport `telegram`, `webhook`, dan `null` (untuk pengujian/lingkungan tanpa jaringan eksternal).
- **Integrasi Telegram Hermes**: Pengiriman pesan terformat markdown ke thread topik khusus War Room (`t.me/c/4383844873/237`).
- **Kebijakan Retry Eksponensial**: Pengulangan otomatis maksimal 3 kali dengan backoff bertingkat saat terjadi gangguan koneksi atau rate limit Telegram.
- **Audit Pengiriman Anti-Klaim Palsu**: Status pengiriman hanya ditandai sukses jika transport mengembalikan respons 200 OK eksplisit. Jika gagal, status kesalahan dan alasan terakhir disimpan di database dan ditampilkan pada UI tanpa menutupi kegagalan.

### Diperbaiki
- Penanganan payload notifikasi panjang kini memotong teks berlebih sesuai batas kuota Telegram (4096 karakter) tanpa memutus struktur tag markdown.
