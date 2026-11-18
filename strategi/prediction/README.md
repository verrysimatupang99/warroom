# Market `prediction` — belum ada strategi

Belum ada berkas `manifest.yaml` di folder ini, dan itu memang keadaan yang jujur:
market Polymarket masih berstatus *under construction* (lihat `docs/STRATEGI-DAN-FEED.md`).

Platform sudah punya jalurnya:

| Komponen | Keadaan |
| --- | --- |
| `v1.venue` | baris `polymarket` (jenis `prediction`, provider `gamma-rest`) sudah ada |
| `v1.instrument` | 25 instrumen prediksi sudah ter-ingest |
| `v1.feed` | feed `polymarket` aktif, SLA 300 detik |
| Strategi | **belum ada** |

Kalau nanti ada strategi prediction, tambahkan
`strategi/prediction/<id>/manifest.yaml` dengan `market: prediction`,
`venue: polymarket`, `executor: python-engine`, lalu jalankan
`python3 ops/strategi-sync.py --check`.

Jangan mengisi folder ini dengan manifest kosong hanya supaya "kelihatan lengkap":
manifest = klaim strategi yang jalan.
