# Changelog Sektor 12 — Dokumentasi & Kerapian

Catatan perubahan pada standarisasi dokumentasi kode, pembersihan komentar historis, dan pemeliharaan arsip proyek.

## Perkembangan Terkini

### Ditambahkan
- **Dokumentasi Terpadu per Paket & Layanan**:
  - `packages/core/README.md`: Arsitektur model basis data, mesin evaluasi StatisticalEdge, tata kelola data split, dan sistem ledger.
  - `packages/live-trading/README.md`: Spesifikasi mesin domain, manajemen risiko portofolio, modul pasar multi-aset, dan perkakas CLI `lt`.
  - `services/api/README.md`: Dokumentasi endpoint REST, otentikasi sesi cookie, otorisasi RBAC, rate limiting, dan stream SSE real-time.
  - `services/worker/README.md`: Penjadwalan deklaratif tabel `jobs`, siklus publikasi fakta pasar, dan adapter worker background.
  - `services/notifier/README.md`: Mekanisme pengiriman notifikasi Telegram/webhook/null, kebijakan retry <= 3, dan penanganan kegagalan transparan.
  - `apps/web/README.md`: Struktur aplikasi frontend SvelteKit 2, penggunaan Svelte 5 runes, adapter-node port 3100, dan integrasi stream SSE.
- **Sistem Changelog Terdistribusi (`docs/changelog/`)**: Pembagian log perubahan menjadi 12 modul sektor otonom serta tautan terpusat pada dokumen induk `CHANGELOG.md`.

### Diperbaiki
- **Pembersihan Komentar Historis (Aturan Anti-Slop)**:
  - `apps/web/src/lib/components/AreaView.svelte`: Pembersihan seluruh banner ASCII dekoratif, komentar bertanggal ("3 Okt", "6 Okt", "7 Okt"), dan catatan naratif historis pada ~3750 baris kode. Seluruh komentar disederhanakan menjadi catatan teknis ringkas 1-2 baris yang hanya menjelaskan "kenapa", tanpa mengubah logika pemrograman sedikit pun.
  - `packages/live-trading/src/live_trading/pasar.py`: Pembersihan komentar bertanggal pada docstring modul pasar dan verifikasi bukti hash pakem.
  - `services/api/src/warroom_api/routers/pasar.py`: Pembersihan komentar bertanggal pada router status pasar dan audit QA.
  - `packages/live-trading/crypto/scripts/crypto_signal_collect.py`: Penghapusan banner ASCII dan komentar bertanggal pada skrip pengumpulan sinyal kripto.
- **Penyelarasan Tautan Dokumentasi Induk**: Penambahan indeks "Dokumentasi Paket & Layanan" pada berkas root `README.md`.
