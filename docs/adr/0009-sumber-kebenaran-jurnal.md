# ADR-009 — Sumber kebenaran jurnal forex: `deals.csv`, bukan tabel `trades`

Status: **diterima** · Tanggal: 2026-10-30 · Fase: Sprint 2

## Konteks

Ada dua tempat yang bisa menyimpan trade forex:

1. **`/var/lib/warroom/deals.csv`** — ditulis `POST /api/v1/tencent/mt5/deal` saat EA
   melaporkan deal tertutup. Idempoten per `ticket`. Dibaca `/journal/trades`,
   `/journal/stats`, `tools/forwardtest_status.py`, dan
   `tools/rekonsiliasi_forwardtest.py`.
2. **Tabel `trades` di Postgres** — model `Trade` sudah ada sejak P1, tetapi
   **0 baris** dan tidak dibaca/ditulis kode mana pun (hanya diekspor dari
   `warroom_core.db`).

DoD forward test menuntut "0 fill/deal hilang" dan net yang cocok dengan broker.
Dua sumber angka tanpa aturan = dua kebenaran; itu yang harus dicegah.

## Keputusan

1. **`deals.csv` adalah sumber kebenaran jurnal forex** untuk forward test.
   Angka `closed`, `net`, dan rekonsiliasi statement berasal dari berkas ini.
2. **Tabel `trades` tidak dipakai untuk forex.** Tidak ada dual-write. Model
   dipertahankan untuk venue lain (Polymarket/Binance/paper) sampai ada penulis nyata;
   selama kosong, ia bukan sumber angka apa pun.
3. **`fills.csv` tetap sumber terpisah untuk kualitas eksekusi** (slippage, latensi,
   retcode). Fill bukan deal; entry yang belum ditutup tidak dihitung sebagai trade.
4. Bila kelak jurnal dipindah ke DB, arah impor wajib **CSV → DB**, dengan CSV tetap
   ditulis EA. Tidak boleh ada dua penulis untuk fakta yang sama.

## Konsekuensi

- Backup/restore wajib menyertakan `/var/lib/warroom/{deals,fills}.csv`; keduanya
  sudah masuk lingkup backup host.
- `tools/rekonsiliasi_forwardtest.py` menjadi penjaga drift: statement broker vs CSV,
  selisih net > $0,01 = temuan.
- Retensi CSV belum diotomasi; berkas tumbuh satu baris per deal (kecil). Ditinjau
  bila sudah > 10.000 baris.
- Kueri SQL ad-hoc atas trade forex tidak tersedia; gunakan CLI tracker/rekonsiliasi
  atau impor sekali ke DB bila benar-benar diperlukan.

## Alternatif yang ditolak

- **DB sebagai sumber utama sekarang**: butuh importer + migrasi + pembaca baru,
  sementara belum ada satu pun pembaca DB. Menambah jalur gagal tanpa manfaat.
- **Dual-write CSV + DB**: dua penulis, dua urutan commit, dan risiko selisih yang
  justru ingin dihilangkan.
- **Menggabungkan fills dan deals**: fills tidak punya harga deal keluar; nol slippage
  akan terbaca "eksekusi sempurna" — menyesatkan.

## Bukti/penjaga

- `services/api/tests/test_jurnal_lokal.py::test_trade_forex_dibentuk_dari_deals`
  mengunci bahwa jurnal forex dibentuk dari `deals.csv`.
- `packages/core/tests/test_rekonsiliasi_deal.py` mengunci pencocokan net vs statement.
- `tools/forwardtest_status.py` menghitung DoD dari berkas yang sama.
