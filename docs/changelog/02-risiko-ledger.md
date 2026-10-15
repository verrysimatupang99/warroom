# Changelog Sektor 02 — Manajemen Risiko & Ledger

Catatan perubahan pada sistem proteksi modal, perhitungan drawdown, dan rekonsiliasi saldo ledger.

## Perkembangan Terkini

### Ditambahkan
- **Pengawasan Kuota Risiko Harian (`risk.py`)**: Pembatasan batas rugi harian per pasar (misal max daily drawdown) dengan pelacakan R-loss harian aktual terhadap batas maksimum.
- **Circuit Breaker Otomatis**: Penghentian sementara sinyal entri saat kerugian menyentuh ambang batas risiko terdefinisi.
- **Pemeriksaan Rekonsiliasi Saldo**: Validasi keseimbangan matematis saldo dompet paper: `Saldo = Modal Awal + Realized PnL - Total Biaya/Fee`. Status dinyatakan jujur: `SEIMBANG`, `SELISIH`, atau `BELUM DIVERIFIKASI`.

### Diperbaiki
- Sinkronisasi pelacakan ekuitas (`equity.py`) dan ledger transaksi (`dompet.py`) memastikan tidak ada entri ganda pada perhitungan profit bersih.
