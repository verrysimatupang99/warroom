# packages/live-trading — Mesin Trading & Analisis Multi-Pasar

Domain engine utama yang menangani pengumpulan sinyal, backtest, paper trading, evaluasi risiko, dan grader akurasi untuk pasar crypto, Polymarket, IDX, Forex, dan GMGN.

## Prinsip Kerja

1. **Jalur Eksekusi Berbasis Fakta**: Seluruh perhitungan diterbitkan ke tabel `facts`. Antarmuka UI hanya membaca fakta yang ada.
2. **Pakem Bukti Transparan**: Menghitung metrik performa (win rate, mean R, expectancy) hanya dari trade yang sudah tuntas. Sampel yang belum cukup diberi tanda terbuka, bukan angka nol.
3. **Pemisahan Risiko Harian**: Mengontrol batas rugi harian per venue (`risk.py`) dan status kuota modal (`dompet.py`).
4. **Alat CLI Mandiri (`lt`)**: Menyediakan perintah command-line untuk pembaruan radar lokal, pengukuran forward, grader transaksi, dan rekonsiliasi posisi.

## Peta Modul

| Modul | Deskripsi |
|---|---|
| `cli.py` | Antarmuka CLI `lt` (`radar-update`, `measure`, `grade`, `reconcile`) |
| `pasar.py` | Penyusun ringkasan fakta, akurasi, dan bukti per pasar |
| `measure.py` | Pengukuran forward-testing: performa lolos vs ditolak gate |
| `backtest.py` | Simulasi friksi dan pengujian aturan strategi historis |
| `risk.py` | Manajemen risiko, batas drawdown, dan circuit breaker |
| `dompet.py` | Pelacakan saldo dompet paper, modal awal, dan kurva ekuitas |
| `bandarmologi_skor.py` | Penilaian aliran broker IDX (ATS, frekuensi, no-sell) skor 0–100 |
| `lp_mark.py` / `lp_mark_run.py` | Perhitungan fee, impermanent loss, dan mark LP Uniswap/Meteora |
| `collectors/` | Pengumpul data pasar dari bursa dan feed penyedia |
| `crypto/` | Logika pengumpul dan filter sinyal strategi crypto |

## Pengujian

```bash
uv run pytest packages/live-trading -q
```
