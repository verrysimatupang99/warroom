# Market `equity` — belum ada strategi

Belum ada `manifest.yaml` di folder ini. Market IDX saat ini hanya punya jalur
**data**, belum punya strategi yang dieksekusi.

| Komponen | Keadaan |
| --- | --- |
| `v1.venue` | baris `idx` (jenis `exchange`, provider `idx-yahoo`) sudah ada |
| `v1.instrument` | 1 instrumen (`^JKSE` / IHSG) |
| `v1.feed` | feed `idx` aktif, SLA 900 detik |
| Endpoint | `routers/idx.py` + halaman `apps/web/src/routes/idx` |
| Strategi | **belum ada** |

Kalau nanti ada strategi equity, tambahkan
`strategi/equity/<id>/manifest.yaml` dengan `market: equity`, `venue: idx`,
`executor: python-engine`, lalu jalankan `python3 ops/strategi-sync.py --check`.

Catatan: IHSG adalah indeks, bukan saham tunggal — strategi equity butuh
`v1.instrument` per emiten lebih dulu sebelum bisa diuji.
