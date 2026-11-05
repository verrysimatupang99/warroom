# Rencana upgrade War Room — disusun 5 Nov 2026

Rencana ini melanjutkan temuan [`audit-server-20261105.md`](audit-server-20261105.md).
Urutannya bukan selera: tiap fase menghapus penghalang fase berikutnya.

## Status per 5 Nov 2026

| Fase | Isi | Status |
|---|---|---|
| 0 | Hygiene server (web root, akses publik, cron) | **selesai** |
| 1 | Data trade: forex/IDX belum masuk `trades` | **selesai di sisi kode** — ingest forex & IDX aktif; menunggu data sumber |
| 2 | Kesegaran data di UI | **selesai** — strip kesehatan + badge segar/basi per kartu |
| 3 | `tg-engine` masuk ruang terkendali | **sebagian** — lint bersih, uji belum |
| 4 | DX: `.env.example`, dev one-command | **selesai** — `.env.example`, `docker-compose.dev.yml`, `scripts/dev.sh`, kecuali CI non-Linux |
| 5 | Peningkatan produk | belum mulai |

## Fase 1 — data trade (penghalang utama)

Tabel `trades` hanya berisi crypto (111 baris). Forex kosong **bukan** karena
jalur baca membuang data: `lokal.py` membaca `/var/lib/warroom/deals.csv`, dan
berkas itu tidak ada.

Selesai 5 Nov 2026 (siap menerima data):

- `warroom_core.trades_forex` — `deals.csv` (+ koreksi append-only) → model
  `Trade`; kunci `venue+mode+ext_id`, `pnl_r` None (deal tidak membawa R),
  `strategy_id` None (versi EA disimpan di evidence, bukan difabrikasi).
- `jalur_hilang()` membedakan "EA belum melapor" dari "nol trade".
- Job `trades-forex-sync` (300 dtk) + laporan `sumber=belum-ada` bila berkas
  tidak ada.
- `jurnal_forex.dari_db()` — jurnal forex membaca DB, jatuh ke `deals.csv` bila
  DB kosong.
- 6 unit test (`packages/core/tests/test_trades_forex.py`).

Langkah berikutnya (butuh data nyata):

1. Pastikan EA `WarRoom_AutoTrader` attach dan `deals.csv` bertambah.
2. Setelah `deals.csv` terisi, jalankan job dan bandingkan jumlah baris DB dengan
   berkas (idempoten, aman diulang).
3. IDX: **selesai** — `warroom_core.trades_idx` membaca `idx616_signal_ledger.db`
   (SQLite, baca-saja) dan hanya menerima baris dengan `closed_at`. Baris
   `CREATED` adalah sinyal, bukan trade; job `trades-idx-sync` melaporkan
   `terbuka=` dan `tertutup=` terpisah supaya "belum ada" tidak terbaca "nol".
4. Unifikasi jangka panjang: satu model `trades` + kolom `market`, view
   kompatibilitas untuk pembaca lama.
5. Tes regresi: setiap ledger yang masuk **wajib** muncul di jurnal Home.

## Fase 2 — kesegaran data di UI

Filosofi produk menuntut "kosong ≠ nol".

Sudah (5 Nov 2026): strip kesehatan di Home (`HealthStrip`) — db, heartbeat
worker, dan jumlah fakta basi dari `/api/v1/ready`; kegagalan baca dinyatakan
terbuka ("status sistem tidak terbaca"), bukan hijau. 4 unit test mengunci nada.

Belum:

1. ~~Umur snapshot + badge `STALE` per kartu~~ — **selesai**: `FreshnessBadge`
   dipasang di kartu pasar, membandingkan umur sinyal dengan `ttl_s` yang
   dilaporkan `/api/v1/freshness` (kind `signal`). Tanpa TTL → `n/a`.
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
