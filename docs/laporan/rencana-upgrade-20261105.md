# Rencana upgrade War Room — disusun 5 Nov 2026

Rencana ini melanjutkan temuan [`audit-server-20261105.md`](audit-server-20261105.md).
Urutannya bukan selera: tiap fase menghapus penghalang fase berikutnya.

## Status per 5 Nov 2026

| Fase | Isi | Status |
|---|---|---|
| 0 | Hygiene server (web root, akses publik, cron) | **selesai** |
| 1 | Data trade: forex/IDX belum masuk `trades` | terhambat — sumbernya tidak ada |
| 2 | Kesegaran data di UI | belum mulai |
| 3 | `tg-engine` masuk ruang terkendali | **sebagian** — lint bersih, uji belum |
| 4 | DX: `.env.example`, dev one-command | **sebagian** — `.env.example` ada |
| 5 | Peningkatan produk | belum mulai |

## Fase 1 — data trade (penghalang utama)

Tabel `trades` hanya berisi crypto (111 baris). Forex kosong **bukan** karena
jalur baca membuang data: `lokal.py` membaca `/var/lib/warroom/deals.csv`, dan
berkas itu tidak ada. Langkah:

1. Pastikan EA `WarRoom_AutoTrader` attach dan mengirim deal (cek
   `fills.csv`/`deals.csv` bertambah). Tanpa ini, tidak ada yang bisa di-ingest.
2. Setelah ada data, tulis `warroom_core.trades_forex` mengikuti pola
   `trades_crypto` (kunci `venue+mode+ext_id`, `pnl_usd` None bila bahan
   kurang, jangan fabrikasi `strategy_id`).
3. IDX: `idx_ledger.db` (SQLite) → `trades` dengan `venue="idx"`.
4. Unifikasi jangka panjang: satu model `trades` + kolom `market`, view
   kompatibilitas untuk pembaca lama.
5. Tes regresi: setiap ledger yang masuk **wajib** muncul di jurnal Home.

## Fase 2 — kesegaran data di UI

Filosofi produk menuntut "kosong ≠ nol". Sekarang kosong dan "worker mati"
tampil sama. Yang dibutuhkan:

1. Umur snapshot per kartu + badge `STALE` bila melewati ambang.
2. Health strip: API, worker, umur fakta terakhir.
3. E2E Playwright: matikan worker → UI harus menampilkan stale, bukan kosong.

## Fase 3 — `tg-engine`

Sudah: 52 temuan lint → 0, unit kembali masuk cakupan `ruff check .`.
Belum: unit uji untuk jalur eksekusi order, dan masuk uv workspace.

Syarat sebelum deploy ulang: jalankan di mode paper, bandingkan keputusan gate
sebelum/sesudah refactor gaya (perubahan hanya typing/format, tetapi kode ini
mengeksekusi order — verifikasi bukan formalitas).

## Fase 4 — developer experience

Sudah: `.env.example`.
Berikutnya: `docker-compose.dev.yml` (Postgres 16 + API + worker + web),
`scripts/dev.sh`, dan smoke test CI di luar Linux.

## Fase 5 — produk

1. Kontrak test API ↔ Web di CI.
2. Alert Telegram untuk worker stale / gate nol / freshness breach.
3. Riwayat perubahan sinyal ("kenapa BUY jadi HOLD").
4. Alert bila drill restore gagal (drill sudah terbukti lulus 5 Nov 2026).
