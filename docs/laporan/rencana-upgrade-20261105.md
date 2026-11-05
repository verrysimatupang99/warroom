# Rencana upgrade War Room — disusun 5 Nov 2026

Rencana ini melanjutkan temuan [`audit-server-20261105.md`](audit-server-20261105.md).
Urutannya bukan selera: tiap fase menghapus penghalang fase berikutnya.

## Status per 5 Nov 2026

| Fase | Isi | Status |
|---|---|---|
| 0 | Hygiene server (web root, akses publik, cron) | **selesai** |
| 1 | Data trade: forex/IDX belum masuk `trades` | terhambat — sumbernya tidak ada |
| 2 | Kesegaran data di UI | **sebagian** — strip kesehatan Home selesai |
| 3 | `tg-engine` masuk ruang terkendali | **sebagian** — lint bersih, uji belum |
| 4 | DX: `.env.example`, dev one-command | **selesai** — `.env.example`, `docker-compose.dev.yml`, `scripts/dev.sh` |
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

Filosofi produk menuntut "kosong ≠ nol".

Sudah (5 Nov 2026): strip kesehatan di Home (`HealthStrip`) — db, heartbeat
worker, dan jumlah fakta basi dari `/api/v1/ready`; kegagalan baca dinyatakan
terbuka ("status sistem tidak terbaca"), bukan hijau. 4 unit test mengunci nada.

Belum:

1. Umur snapshot + badge `STALE` per kartu pasar (badge komponen `FreshnessBadge`
   sudah ada; belum dipasang di Home).
2. E2E Playwright: matikan worker → UI harus menampilkan stale, bukan kosong.
   Butuh kredensial e2e + API uji, jadi tidak dikerjakan di mesin tanpa DB.

## Fase 3 — `tg-engine`

Sudah: 52 temuan lint → 0, unit kembali masuk cakupan `ruff check .`.
Belum: unit uji untuk jalur eksekusi order, dan masuk uv workspace.

Syarat sebelum deploy ulang: jalankan di mode paper, bandingkan keputusan gate
sebelum/sesudah refactor gaya (perubahan hanya typing/format, tetapi kode ini
mengeksekusi order — verifikasi bukan formalitas).

## Fase 4 — developer experience

Selesai 5 Nov 2026:

- `.env.example` — semua variabel, nilai placeholder.
- `docker-compose.dev.yml` — Postgres 16 + migrasi + API + worker + web; migrasi
  dijalankan sekali sebagai langkah terpisah supaya dua proses tidak saling
  mengunci.
- `scripts/dev.sh` — satu perintah untuk API + worker + web.

Berikutnya: smoke test CI di luar Linux (saat ini seluruh pipeline Linux).

## Fase 5 — produk

1. Kontrak test API ↔ Web di CI.
2. Alert Telegram untuk worker stale / gate nol / freshness breach.
3. Riwayat perubahan sinyal ("kenapa BUY jadi HOLD").
4. Alert bila drill restore gagal (drill sudah terbukti lulus 5 Nov 2026).
