# Changelog Sektor 05 — Frontend & Visualisasi

Catatan perubahan pada antarmuka pengguna SvelteKit, komponen reaktif, dan visualisasi metrik.

## Perkembangan Terkini

### Ditambahkan
- **Halaman Leaderboard Antar-Strategi (`/leaderboard`)**: Tampilan perbandingan metrik kinerja lintas instrumen dengan filter pasar, status operasional (`AKTIF`, `BENCHED`, `HALTED`), dan rincian buku rekonsiliasi saldo.
- **Badge Status Daur Hidup Setup**: Visualisasi status setup strategi (`WAITING`, `IN_AREA`, `RUNNING`, `TP`, `SL`) pada komponen `StrategyLeaderboard.svelte`.
- **Badge Rekonsiliasi Saldo**: Label visual transparan (`SEIMBANG`, `SELISIH`, `BELUM DIVERIFIKASI`) untuk memverifikasi integritas ledger dompet paper.
- **Navigasi Tab Berbasis SSOT**: Pengendalian sub-tab sepenuhnya lewat parameter URL query (`?sub=...`) untuk menjamin sinkronisasi state peramban.

### Diperbaiki
- Komponen `AreaView.svelte` dibersihkan dari komentar historis/bertanggal dan kode usang, mengembalikan kejelasan arsitektur tampilan.
- Penanganan fallback stream SSE ke polling REST pada klien `live.svelte.ts` saat koneksi socket terputus.
