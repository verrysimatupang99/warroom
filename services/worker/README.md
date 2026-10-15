# services/worker — War Room Background Job Runner

Layanan eksekusi pekerjaan latar belakang yang berjalan terjadwal untuk menyinkronkan data pasar, menghitung snapshot akurasi, dan menerbitkan fakta ke database.

## Mekanisme Kerja

1. **Jadwal Deklaratif**: Seluruh tugas dideklarasikan di tabel `jobs` dengan ekspresi interval atau cron, dikendalikan melalui runner `warroom_worker.schedule`.
2. **Penerbitan Fakta (`facts_publish.py`)**: Hasil koleksi dari berbagai adapter dinormalisasi dan disimpan ke tabel `facts` dengan metadata sumber, timestamp, dan status kesegaran (`freshness`).
3. **Pemberian Skor & Grader**: Grader berkala mengevaluasi trade terbuka terhadap pergerakan harga real-time dan mencatatnya ke ledger.
4. **Isolasi Kegagalan**: Setiap job dieksekusi secara independen sehingga kegagalan satu provider tidak menghentikan siklus tugas lainnya.

## Peta Modul

| Modul | Deskripsi |
|---|---|
| `run.py` | Titik masuk worker background daemon |
| `schedule.py` | Engine penjadwalan berkala berbasis database |
| `facts_publish.py` | Penerbit fakta teragregasi untuk konsumsi API |
| `adapters/` | Penghubung antara script domain trading dan basis data |
| `jobs/` | Handler spesifik untuk tiap jenis pekerjaan sinkronisasi |

## Pengujian

```bash
uv run pytest services/worker/tests -q
```
