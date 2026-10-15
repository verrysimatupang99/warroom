# services/notifier — War Room Notification Transport

Layanan pengiriman pesan peringatan dan notifikasi sistem via Telegram Bot Hermes dan webhook.

## Karakteristik Layanan

1. **Kejujuran Pengiriman**: Tidak pernah mengklaim notifikasi telah terkirim sebelum menerima respon HTTP 200 dari server penyedia. Status pengiriman dicatat terbuka.
2. **Kebijakan Retry Terbatas**: Menggunakan exponential backoff dengan batas maksimal 3 kali percobaan ulang (`retry <= 3`).
3. **Transport Fleksibel**:
   - `telegram`: Pengiriman ke thread khusus Telegram (misal topik War Room) menggunakan Bot Token dan Chat ID terisolasi.
   - `webhook`: Pengiriman payload JSON ke endpoint eksternal yang ditentukan.
   - `null`: Transport pengujian yang mencatat pesan tanpa koneksi jaringan.

## Struktur Modul

| Modul | Deskripsi |
|---|---|
| `dispatch.py` | Router penentu target transport dan antrean notifikasi |
| `transport.py` | Implementasi klien HTTP untuk Telegram, Webhook, dan Null |
| `signal_alert.py` | Pemformat pesan sinyal dan peringatan keputusan gate |

## Pengujian

```bash
uv run pytest services/notifier/tests -q
```
