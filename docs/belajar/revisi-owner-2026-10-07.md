# Revisi pemilik 7 Okt 2026 — Home, Crypto, GMGN (apa yang berubah & mengapa)

Dokumen ini mencatat revisi yang diminta pemilik pada 7 Okt 2026, apa yang dikerjakan,
dan **bukti** bahwa pekerjaan itu benar-benar sampai ke layar (bukan hanya di kode).
Ditulis dari kode & hasil uji, bukan dari rencana.

## Sumber data (ditetapkan pemilik)

| Pasar | Sumber | Catatan |
|---|---|---|
| Crypto | **MEXC** | harga & depth venue paper; sinyal SMC multi-timeframe |
| IDX | **Stock Arjum** | bandarmologi/BSJP; mesin lama (Tencent) beku |
| Forex | **TVC** (TradingView) | bias & struktur |
| Polymarket | **Dokumentasi PM** | aturan arm B favorit 0,70–0,95 |
| Meme | **GMGN / FOMO** | memecoin baru + safety gate |
| LP | **Meteora (Solana) · Uniswap (Robinhood Chain)** | dua protokol **berbeda**, tidak saling terhubung |

Sekarang tertulis di halaman: endpoint `/api/v1/sumber` + strip "Sumber data" di Home.

---

## Home — 4 revisi

### 1. Card status + akurasi digabung; sinyal pindah ke bawah
`STATUS HARI INI` dan `Akurasi & PnL per Market` kini satu card (`.kartu-gabung`); daftar
sinyal menjadi bagian **3. Sinyal per Market** di bawahnya. Alasan yang dikodekan: keduanya
menjawab pertanyaan yang sama ("hari ini bagaimana?").

### 2. Maks 3 sinyal per market + tombol ke halaman market
Endpoint `/api/v1/sinyal/per-pasar` kini mengembalikan `pasar[]` (bentuk baru) berisi:
`status_data`, `alasan`, `rute`, `jumlah`, `sinyal[]` (maks 3). Tombol **Lihat semua (N)**
muncul hanya bila `jumlah > 3`.

> Bug yang tertangkap saat mengerjakan ini: `facts` menyimpan **satu baris per pengamatan**,
> sehingga 6 kandidat aktif terbaca sebagai **53**. Dedupe per pair ditambahkan.

### 3. "Tidak ada sinyal" ≠ "gagal sistem"
`status_data` tegas: `ada` · `kosong` (mesin hidup, tak ada setup cocok) · `gagal`
(sumber/job tak terbaca). Hanya yang `gagal` berbunyi sebagai kegagalan sistem.

### 4. Ticker berjalan & realtime
Dua salinan identik dalam satu jalur, animasi geser 45 dtk (mulus, tanpa lompat), berhenti
saat hover/fokus, menghormati `prefers-reduced-motion`. Data tetap di-refresh 15 dtk.

---

## Crypto

### Cockpit
- **Dompet → Kurva → Risiko/Posisi: SUDAH BENAR, tidak diubah.** (Pemilik menegaskannya;
  percobaan menyusun ulang dibatalkan dan susunan asli dipulihkan — ada komentar di kode.)
- **Posisi terbuka diperbaiki.** Ada 2 posisi nyata (SUIUSDT, 1000PEPEUSDT) tetapi UI
  menulis "Tidak ada posisi (0/3)" karena membaca `risiko.posisi_terbuka` yang tidak lagi
  ditulis collector. Kini jumlah diambil dari **daftar posisi itu sendiri**.
- **Harga mikro.** 1000PEPE (0,00414775) tidak lagi dibulatkan jadi "0,00" — format adaptif.
- **Narasi LLM** (5 tempat): gaya "kesimpulan dulu" — kalimat pertama besar, bukti menyusul
  dengan garis kutipan, mesin (provider/ms) di kaki. Prompt narrator naik ke `1.1.0`
  (kalimat pertama = kesimpulan, bukan pengulangan angka; grounding `fact_ids` tetap mutlak).
- **Kejadian Area di-collapse** + akar masalah tombol "tidak berfungsi" diperbaiki:
  filter hanya dirender bila ada >1 tipe, dan **panel selalu kosong** karena SSE tanpa
  `Last-Event-ID` mulai dari "sekarang" → kini ada backfill `/api/v1/events`.

### Setup / Ukur / Eksekusi — "gw ga ngeh"
Panel **Cara membaca** di ketiga tab, berisi hal yang selama ini tidak terlihat:

- **Metode:** SMC multi-timeframe (1D, 4H, 1H) — cari POI (FVG/order block), tunggu harga
  kembali ke area, susun entry/SL/TP. Enam aturan gate disebut namanya:
  `mtf_alignment`, `poi_valid` (keras), `freshness` (keras), `sl_distance` (keras),
  `atr_min`, `exposure` (keras).
- **Ukur:** apa itu pengukuran forward (shadow), backtest walk-forward, dan **pakem**
  (INSUFFICIENT → DIRECTIONAL → PRELIMINARY → TUNING).
- **Eksekusi:** arti paper, arti **R**, dan apa yang **tidak** akan terlihat (angka yang
  dibulatkan menjadi bagus / trade yang dihilangkan).

---

## GMGN — target baru

Peta **"Tiga target & sumbernya"** di semua tab GMGN:

1. **Memecoin** — GMGN/FOMO, safety gate (bundler, dev hold, entrapment), konfigurasi bot
   paper **nyata** dari folder state; peringatan `signals.jsonl` **rusak** ditulis apa adanya.
2. **LP Robinhood Chain** — Uniswap v2/v3/v4 (L2 Robinhood, chain ID 4663).
3. **LP Solana** — Meteora DLMM/DAMM v2.

Kind `gmgn` (paper/radar) yang sebelumnya **tidak pernah sampai ke UI** kini disajikan
lewat `AREA_KIND` — itu sumber semua angka memecoin.

---

## Bukti (bukan klaim)

- `pytest packages services` hijau; `ruff` bersih; `lint-tokens` bersih (53 berkas).
- E2E baru: `cek_home_revisi.spec.ts` (card gabungan, susunan, maks 3, ticker beranimasi,
  6 aturan gate), `cek_penjelasan.spec.ts` (3 tab), `cek_kandidat_aktif.spec.ts`.
- Penjaga kontrak `test_kontrak_ui.py` **menangkap** drift `SinyalPasar` saat field
  `status_data` ditambahkan — lalu disinkronkan. Penjaga itu bekerja.

## Yang masih terbuka (jujur)

- **Narasi LLM: 0 kalimat** — `insufficient · semua_provider_gagal` (semua penyedia LLM
  gagal). Fakta tetap sah; status penyedia ada di Sistem → AI. Ini **gagal sistem**, bukan
  "tidak ada sinyal".
- **LP Robinhood baru "PANTAU"** — belum ada posisi paper; yang ada baru verifikasi harga.
- **Bot memecoin:** `positions.json` belum ada & `signals.jsonl` rusak → belum ada hasil
  yang bisa dinilai, hanya konfigurasi.
