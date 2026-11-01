# Roadmap profit live — re-prioritas 1 Nov 2026

Keputusan owner: tujuan enam bulan adalah **profit live**, dengan batas **read-only**,
tanpa biaya infrastruktur baru, dan tanpa rewrite. Dokumen ini menggantikan urutan
prioritas sebelumnya.

## Arti batas read-only

War Room boleh membaca saldo, posisi, fill, dan ekuitas. War Room **tidak** mengirim
order, menutup posisi, atau menyentuh VM/EA. Semua penghentian tetap manual oleh owner.

## Urutan prioritas

### P0 — visibilitas akun live (2 minggu)

Saat ini akun `36525553` tidak terlihat sama sekali: `fills.csv` hanya header, dan
`/api/v1/telemetry/push` belum ada. Tanpa data, "profit live" tidak bisa diukur.

Dua jalur tanpa biaya baru, pilih salah satu:

1. **Terminal read-only di Webdock.** `ops/docker-mt5` sudah berisi compose Wine/Webtop.
   Login dengan **investor password** ke akun `36525553`, tanpa EA, lalu ekspor
   equity/posisi/deals ke direktori yang dibaca worker. Tidak menyentuh VM2.
2. **Impor statement harian.** Anda mengekspor statement Vantage (CSV/HTML) ke
   `/var/lib/warroom/statements/`, lalu job membaca berkas terbaru. Tidak real-time,
   tetapi nol proses baru dan nol kredensial tambahan.

Kriteria selesai: equity, floating P/L, posisi terbuka, dan pending order terlihat di
API/fakta dengan umur data < 15 menit (jalur 1) atau < 24 jam (jalur 2).

### P0 — disiplin risiko

- Hitung drawdown harian dan total terhadap batas 3% dan 5%.
- Alert Telegram: warning 2,4% harian dan 4,0% total; critical 3% dan 5%.
- Alert bila feed mati > 15 menit atau EA tidak heartbeat.
- Tampilkan posisi/pending dengan risiko per posisi bila tersedia.

Kriteria selesai: alert diuji dengan nilai sintetis, bukan hanya ada di kode.

### P1 — laporan dan evaluasi

- Laporan harian 23:55 WIB: equity, P/L, trade, DD, posisi tersisa.
- Laporan mingguan: win rate, expectancy, biaya, slippage, jumlah trade per hari.
- Catatan keputusan: setiap perubahan parameter EA dicatat dengan alasan.

### P1 — ketahanan lokal tanpa biaya baru

- Verifikasi checksum dump harian (sudah), drill restore bulanan (sudah).
- Alert umur backup > 26 jam (sudah), disk 80/90 (sudah).
- Offsite ditunda sesuai keputusan; risiko kehilangan host diterima dan dicatat.

### Ditunda atau dibuang

- Offsite cloud: tanpa anggaran.
- p95/5xx API: bukan pengungkit profit; perlu perubahan format log.
- Auto-execution dan gate live: di luar batas read-only.
- Pasar baru dan polesan UI: setelah P0 terbukti.

## Yang saya butuhkan untuk mulai

- Jalur P0: investor password (untuk jalur 1) atau satu contoh statement (jalur 2).
- Konfirmasi bahwa container Docker boleh dipakai di Webdock (RAM tersedia 10 GiB).
- Jam reset harian DD: waktu broker atau WIB.

Tanpa salah satu jalur itu, saya hanya bisa menyiapkan kontrak data dan uji sintetis,
bukan menampilkan angka akun live.
