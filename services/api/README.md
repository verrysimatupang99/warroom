# services/api — War Room FastAPI Backend

Layanan REST API dan real-time stream SSE berbasis FastAPI (berjalan pada port 8800 di balik proxy reverse nginx).

## Fitur Utama

1. **REST API (`/api/v1/*`)**: Menyediakan endpoint terstruktur untuk area pasar, fakta, proposal, alert, metrik sistem, dan autentikasi.
2. **Server-Sent Events (`/api/v1/stream`)**: Streaming kejadian sistem secara real-time dengan dukungan reconnection dan buffer deduplikasi.
3. **Autentikasi & RBAC**: Sesi berbasis cookie aman dengan pembagian peran bertingkat:
   - `viewer`: Akses baca ke data pasar dan status sistem.
   - `operator`: Manajemen operasional paper trading dan acknowledgment alert.
   - `owner`: Akses penuh konfigurasi sensitif dan otorisasi gate.
4. **Proteksi & Observabilitas**: Rate limiting terisolasi per alamat IP/token, logging terstruktur, dan metrik Prometheus (`/metrics`).

## Peta Endpoint

| Router | Jalur | Keterangan |
|---|---|---|
| `auth` | `/api/v1/auth/*` | Login, logout, status sesi pengguna |
| `areas` | `/api/v1/areas/*` | Fakta teragregasi per area/instrumen pasar |
| `pasar` | `/api/v1/pasar/*` | Sinyal aktif, ringkasan akurasi, dan bukti performa |
| `stream` | `/api/v1/stream` | Aliran event SSE terfilter topik |
| `proposals` | `/api/v1/proposals/*` | Daftar proposal aksi dan status approval |
| `alerts` | `/api/v1/alerts/*` | Antrean peringatan sistem dan ack log |
| `metrics` | `/metrics` | Metrik Prometheus untuk scraping infrastruktur |

## Menjalankan & Pengujian

```bash
# Menjalankan secara lokal
uv run uvicorn warroom_api.app:app --host 127.0.0.1 --port 8800 --reload

# Menjalankan test suite
uv run pytest services/api/tests -q
```
