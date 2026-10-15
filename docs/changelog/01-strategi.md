# Changelog Sektor 01 — Strategi & Sinyal

Catatan perubahan pada domain strategi trading, grading sinyal, dan status siklus hidup setup.

## Perkembangan Terkini

### Ditambahkan
- **Kontrak Siklus Hidup Setup (`strategy_lifecycle.py`)**: Definisi status mengikat `WAITING` → `IN_AREA` → `RUNNING` → `TP`/`SL` (+ `EXPIRED`). Transisi status bersifat satu arah dan konservatif (jika TP dan SL tersentuh di jendela candle yang sama, dicatat sebagai SL).
- **Skor Heat Terukur (`heat_score.py`)**: Kalkulasi skor 0–100 dari metrik volume 24 jam, deviasi taker, dan volatilitas rentang. Jika komponen tidak terbaca, menghasilkan status `None` (bukan 0 karangan).
- **Filter Funding & OI Terpisah (`signals/heat.py`)**: Deteksi kondisi pasar ekstrem berdasarkan ambang funding rate dan penurunan tajam Open Interest (OI). Penolakan menghasilkan tier `SKIP` secara transparan.
- **CLI Pelacakan Setup (`lt lifecycle`)**: Perintah inspeksi status setup per strategi dari baris `verdicts.jsonl` dan data candle 1H.

### Diperbaiki
- Evaluasi sinyal pada `signals/engine.py` kini menerima konteks agen dan mencatat alasan penolakan filter secara eksplisit di log audit.
