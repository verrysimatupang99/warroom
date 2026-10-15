# Changelog Sektor 08 — Basis Data & Skema

Catatan perubahan pada model basis data, migrasi Alembic, integritas referensial, dan optimasi query.

## Perkembangan Terkini

### Ditambahkan
- **Model Frozen Split Data (`FrozenSplit`)**: Tabel skema untuk mencatat hash integritas sample holdout data uji, mencegah data leakage saat kalibrasi strategi.
- **Indeks Komposit Leaderboard**: Penambahan indeks pada tabel `trades(strategy_id, created_at)` dan `facts(area, timestamp)` untuk menjamin query agregasi dashboard cepat tanpa full-table scan.
- **Skema Audit Terpadu**: Tabel `llm_calls` dan `notification_logs` dengan kolom waktu presisi mikrodetik untuk menunjang kebutuhan audit kepatuhan.
- **Migrasi Bertahap Alembic**: Skrip migrasi teruji untuk peningkatan skema tanpa kehilangan data paper trading atau riwayat eksekusi historis.

### Diperbaiki
- Retensi data otomatis pada fakta historis dan event log mencegah pembengkakan ukuran basis data tanpa menghapus ringkasan agregat harian.
- Pengaturan koneksi engine SQLAlchemy dengan pool pre-ping untuk mencegah pemutusan koneksi idle dari PostgreSQL/SQLite.
