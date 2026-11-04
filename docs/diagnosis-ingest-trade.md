# Kenapa 106 trade tidak muncul di dashboard (4 Nov 2026)

Lanjutan dari `diagnosis-gate-nol-trade.md` §9. Pertanyaan: **mengapa ledger
berisi 106 trade, tetapi platform menampilkan nol?**

Semua angka dari perintah nyata pada 4 Nov 2026 pukul 11.40–12.00 UTC.

---

## 0. Ringkas

Ada **tiga sistem ledger terpisah** yang tidak saling terhubung, dan **tabel
`trades` di PostgreSQL sama sekali tidak dipakai** — didefinisikan, dibuat oleh
migrasi, tetapi **tidak pernah ditulis maupun dibaca kode mana pun**.

Akibatnya angka yang dilihat owner di dashboard berasal dari berkas yang
berbeda dari yang dipakai `paper-scan`, dan ledger yang paling kaya
(`crypto_equity.jsonl`, 106 trade, +54 R) tidak pernah tampil di mana pun.

## 1. Tabel `trades` = yatim

```
grep "Trade(" packages/ services/ | grep -v tests
  -> packages/core/src/warroom_core/db/models.py:142: class Trade(Base)   # hanya definisi

grep "s.add(Trade" | "select(Trade"
  -> (kosong)
```

- Model `Trade` ada (`models.py:142`), tabelnya dibuat migrasi awal.
- **Tidak ada satu pun kode yang meng-insert ke tabel ini.**
- **Tidak ada satu pun kode yang membacanya.**

Jadi `select count(*) from trades` = 0 bukan karena data gagal masuk — **tidak
ada yang pernah mencoba memasukkannya**.

## 2. Tiga ledger yang berjalan sendiri-sendiri

| Ledger | Isi | Dipakai oleh |
|---|---|---|
| `~/live-trading/state/crypto_equity.jsonl` | **106 trade, +54 R** | `paper-scan` (baca posisi), `crypto_equity.sync()`, `crypto_dashboard.py` |
| `/var/lib/warroom/momentum_trades.csv` | **19 baris** (28 Okt–3 Nov), BUY-only, `alasan=breakout_55` | API `/journal/trades` untuk market crypto |
| `/var/lib/warroom/momentum_paper.json` | 8 koin, snapshot harga | UI crypto |

Ketiganya **berbeda isi dan berbeda pemilik**. Yang dianggap "trade crypto" oleh
dashboard adalah `momentum_trades.csv` (19 baris terakhir 3 Nov), sementara
sistem paper yang sebenarnya berjalan menulis ke `crypto_equity.jsonl`
(106 trade, sampai 4 Nov 11:00).

## 3. Endpoint jurnal crypto mengambil dari Tencent

`services/api/src/warroom_api/routers/journal.py`:

```python
_FILTER = ("/forex/journal/stats", "/forex/journal/trades", ...)

async def _ambil(path, market=None, account=None):
    if market is not None and path in _FILTER:
        return await _fetch_tencent(path, params=params)   # <- selalu ke Tencent
    return await _fetch_tencent(path)
```

`/api/v1/journal/trades?market=crypto` **tetap** diteruskan ke `_fetch_tencent`
(`routers/tencent.py:86`). Jadi permintaan crypto dilayani servis Tencent/MT5,
bukan ledger crypto lokal. Itu sebabnya statistik crypto terlihat kosong atau
tidak cocok: sumbernya bukan tempat paper trader menulis.

`tencent.py:653` lalu membaca `MOMENTUM_TRADES = /var/lib/warroom/momentum_trades.csv`
(19 baris) — bukan `crypto_equity.jsonl` (106 trade).

## 4. Kenapa ini penting

- **106 trade dan +54 R tidak pernah terlihat owner.** Angka itu ada, tapi
  tersimpan di berkas yang tidak dibaca UI.
- **`trades`=0 dan `verdicts`=0 di DB** membuat setiap pertanyaan "apakah sistem
  ini berguna?" tidak bisa dijawab dari platform — padahal datanya lengkap.
- **Dua sistem paper berjalan paralel** (`crypto_equity.jsonl` vs
  `momentum_trades.csv`) dengan strategi berbeda, tanpa satu pun penanda mana
  yang otoritatif. Ini sumber kebingungan berikutnya kalau dibiarkan.

## 5. Yang dibuktikan BUKAN penyebab

- Gate `exposure` — sudah diuji, `ok=True` dengan data nyata (§9 dokumen sebelumnya).
- Worker mati — semua job `ok`, 0 error 24 jam.
- Data berhenti — `facts` 111.103 baris, terakhir 11:18.
- `scan()` mengakumulasi posisi — `posisi_paper` dipanggil sekali di `engine.py:564`.

## 6. Pilihan perbaikan (butuh keputusan owner)

**A. Ingest `crypto_equity.jsonl` → tabel `trades` (disarankan).**
Isi tabel yatim itu dari ledger paper, lalu arahkan `/journal/trades?market=crypto`
ke DB. Kelebihan: satu sumber kebenaran, 106 trade langsung terlihat, riwayat
lengkap. Risiko: perlu backfill + migrasi data, dan harus jelas mana baris paper
vs live.

**B. Arahkan API langsung ke `crypto_equity.jsonl` (paling cepat).**
Ubah `_ambil` supaya `market=crypto` membaca ledger lokal, bukan Tencent.
Kelebihan: kecil, cepat, tanpa migrasi. Kekurangan: tabel `trades` tetap yatim,
dan data tetap di berkas (bukan DB).

**C. Dokumentasikan saja.**
Tandai `momentum_trades.csv` sebagai sumber resmi crypto dan `crypto_equity.jsonl`
sebagai catatan internal. Termurah, tapi 106 trade tetap tidak terlihat.

**Rekomendasi: A**, dengan B sebagai langkah antara bila ingin hasil cepat.

## 7. Jangan lakukan

- Jangan menghapus salah satu ledger sebelum dipastikan mana yang otoritatif —
  keduanya berisi riwayat nyata yang tidak bisa direkonstruksi.
- Jangan mengubah gate untuk "membuat trade muncul" — gate sudah terbukti benar.
