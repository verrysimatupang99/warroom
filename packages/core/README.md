# packages/core — War Room Core Domain Façade

Paket inti yang mendefinisikan model basis data, façade domain, evaluasi gate statistik, pemisahan dataset, dan aturan retensi platform.

## Peran & Tanggung Jawab

1. **Façade Domain SSOT**: Menyediakan antarmuka konsisten untuk entitas sistem (`Signal`, `MarketSignal`, `Outcome`, `Verdict`, `Paper`).
2. **Evaluasi Gate Statistik (`gate.py`)**: Menghitung batas bawah Confidence Interval (CI95) terhadap break-even (BE) dengan ambang sampel minimum (`min_n`) dan koreksi design effect (`deff`). Rumus BE dan ambang gate hanya diubah oleh manusia.
3. **Pemisahan Dataset (`splits.py`)**: Mengunci isolasi data latihan vs data uji beku (`split=frozen:<id>`) untuk mencegah kebocoran lookahead bias.
4. **Model Basis Data & Migrasi (`db/`, `alembic/`)**: Definisi skema SQLAlchemy untuk tabel fakta (`facts`), ledger (`ledgers`), metrik (`metrics`), alert (`alerts`), panggilan LLM (`llm_calls`), dan migrasi versi.
5. **Kebijakan Retensi Data (`retention.py`)**: Menghapus data transien sesuai TTL tanpa merusak jejak audit keputusan.

## Struktur Modul

| Modul | Deskripsi |
|---|---|
| `gate.py` | Evaluasi `StatisticalEdge`, CI95, batas BE, dan putusan gate |
| `autonomy.py` | Tingkat otonomi operasional (L0–L3) dan verifikasi izin |
| `splits.py` | Partisi dataset (train, test, holdout beku) dan validasi hash |
| `market_signal.py` | Skema representasi sinyal lintas instrumen pasar |
| `verdict.py` | Penyusunan kesimpulan formal berbasis statistik |
| `retention.py` | Pembersihan data berumur lewat batas retensi |
| `db/models.py` | Definisi tabel database SSOT |
| `db/session.py` | Pengelola koneksi dan sesi basis data |

## Pengujian

```bash
uv run pytest packages/core/tests -q
```
