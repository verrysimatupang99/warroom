# Rencana Pembaharuan Fullstack End-to-End — Pendekatan Per Market
**Tanggal:** 6 Okt 2026 · **Dasar:** arahan owner + riset sumber (Tencent, Webdock, acuan produk)

> Aturan main yang tidak berubah: `/opt/polymarket` baca-saja, Tencent/Azure baca-saja,
> gate live tidak disentuh, kredensial tidak pernah masuk repo. War Room = **mesin bukti**;
> mesin sinyal boleh hidup di mana saja (Tencent/Webdock), bukti selalu di sini.

---

## 0. Temuan riset (yang mengubah arah)

| Temuan | Bukti | Implikasi |
|---|---|---|
| Server Azure dimatikan → radar dipindah ke Webdock | `_radar_panel` komentar 6 Okt; `radar_state.json` lokal | Tidak ada SSH di jalur tampil; semua panel lokal |
| Mesin sinyal Crypto & Forex hidup di **Tencent** (cron Hermes "Dumbledore") | `crypto-5agent-pipeline-653`, `xauusd-smc-daily-signal`, `multi-pair-signal` | Sub-tab **Suplai** + catatan "server mati = sinyal berhenti" wajib ada |
| Ledger IDX sudah beku (cron di-pause) tapi paling matang | `idx_ledger.db` 628 sinyal, grader v3 | Akurasi IDX jadi tolok ukur standar ("pakem") |
| Polymarket punya livetrade + 4 arm paper | `poly-paper*` shadow summary; total PnL +8,07 USD | Halaman per-arm: win-rate + PnL + skips |
| Acuan produk: **algentis.xyz** & **ihsgscreener** | riset web | Yang diadopsi: algentis = "signal or silence" + track record + alasan skip; ihsgscreener = score/faktor + bandarmologi + modul per fitur |
| Strategi baru yang diminta owner: Fib Golden Pocket | arahan 6 Okt | Status **rencana** (jujur), diuji walk-forward dulu — bukan dipromosikan |

---

## 1. Kontrak data per market (SUDAH JADI)

Satu modul: `packages/live-trading/src/live_trading/pasar.py` → snapshot →
`publish-facts` → fakta `crypto_sinyal`, `forex_sinyal`, `idx_sinyal`, `pasar_akurasi`.

Setiap market menjawab 4 pertanyaan owner:

1. **Sinyal** — daftar terbaru lengkap dengan status (lolos/ditolak/tuntas).
2. **Entry setup per sinyal** — kolom khas market (crypto: POI+skor gate; forex: zona FVG/OB+TF+konfluensi; IDX: setup+zona+net R).
3. **Akurasi sinyal** — pakem bukti satu standar (n efektif per hari).
4. **PnL per market** — R untuk yang berseri R; P&L USD untuk LP; entri menang/kalah untuk Polymarket. Tidak ada yang dipaksa jadi R.

## 2. Racangan menu per market (jujur via registry)

Registry `STRATEGI_PASAR` menandai status **aktif / paper / rencana** — UI menampilkan
perbedaan itu terang-terangan (pelajaran dari algentis: "skip with reasons").

| Market | Strategi terdaftar | Bukti saat ini | Pakem |
|---|---|---|---|
| **Crypto** | SMC MTF (aktif) · Fib Golden Pocket (rencana) | 400 verdict, 178 lolos, 5 trade tuntas | INSUFFICIENT (4 hari) |
| **IDX** | ARA Hunter · BSJP · Scalping · Bandarmologi (semua aktif) | 628 sinyal; BSJP +0,608R/45 trade | BSJP INSUFFICIENT (9 hari), INTRADAY DIRECTIONAL |
| **Forex** | SMC XAUUSD 4-agen · SMC FVG/OB multi-pair (aktif) | 4 trade tuntas (XAUUSD 3 + NAS100 1) | INSUFFICIENT |
| **GMGN/LP** | LP Terukur (paper) · Radar (paper) · FOMO Family (rencana) | 5 posisi dinilai, PnL −3,24 USD | INSUFFICIENT |
| **Polymarket** | 4 arm paper (A momentum −10,34 · B kandidat +6,40 · C fade 0 · D favorit +12,01) | 213 entri | B TUNING, D PRELIMINARY |

## 3. Sub-tab baru — status per 6 Okt malam

SUDAH JADI:
- ✅ **Sinyal & Entry Setup** (crypto/forex/IDX) — kolom khas market, dari `*_sinyal`.
- ✅ **Akurasi per Strategi** (semua market) + dimensi gerbang crypto.
- ✅ **Papan Akurasi & PnL per Market** di Home (`/api/v1/pasar/ringkas`).
- ✅ **Narasi LLM per market** (kartu ✳) + ringkas fakta angka-utuh (bukan 80 char JSON).
- ✅ **Skor Bandarmologi 0–100** (adopsi ihsgscreener) dengan komponen diaudit.
- ✅ Registry strategi jujur aktif/paper/rencana (Fib Golden Pocket = rencana).

BELUM (jangan diklaim sudah):
- **Suplai** tiap market: umur sinyal terakhir + efek server mati (baru berupa catatan teks).
- **Entry Plan** (crypto): kalkulator ukuran posisi dari risiko % (angka gate sudah tersedia).
- **Skips & alasan** (crypto/Poly) sebagai panel tersendiri — data sudah terkumpul
  (`aturan_gagal`, `skips`) tetapi belum dirender.
- **Fib Golden Pocket**: spesifikasi uji → backtest → keputusan owner (aturan: tidak ada tuning dari cerita; harus walk-forward).

## 4. LLM yang benar-benar membantu (bukan hiasan)

Yang sudah ada: gateway LLM (`services/llm`) dengan prompt berversi + narrator 6 jam sekali.

Rencana berurutan:
1. **Narator per market** (bukan hanya crypto): fakta `*_sinyal` + `pasar_akurasi` jadi `FactRef`; output wajib menyebut angka & `fact_ids`.
2. **Verifier pra-eksekusi**: sebelum sinyal ditandai "siap", LLM memeriksa konflik (mis. BSJP long vs bandarmologi distribusi) — keputusan tetap manusia.
3. **Analis pasca-trade**: membaca note hasil + konteks, mengusulkan hipotesis perbaikan; hipotesis harus diuji walk-forward sebelum dipakai (aturan: tidak ada tuning dari cerita).
4. **Kurator strategi baru** (Fib Golden Pocket): LLM menyusun spesifikasi uji (parameter, jendela, kriteria batal) — bukan menebak arah.

Batas keras: LLM **tidak pernah** mengubah ambang gate, memicu live order, atau menulis ulang angka bukti.

## 5. Urutan eksekusi yang disarankan

1. ✅ Mesin per-market + UI (ini).
2. Publish otomatis + test kontrak bentuk fakta (penjaga drift seperti `SinyalPasar`).
3. Sub-tab Suplai + panel LLM per market.
4. Skor bandarmologi IDX (adopsi ihsgscreener) — data sudah ada di `bagian.bandarmologi`.
5. Fib Golden Pocket: spesifikasi uji → backtest → keputusan owner.
6. Rekonsiliasi PnL: jumlahkan per market dalam satu halaman "Portofolio" (tanpa mencampur satuan R/USD — dipisah kolomnya).

## 6. Risiko yang harus selalu tampil

- Sampel kecil (<10 hari) → **INSUFFICIENT**; JANGAN promosikan angka.
- Mesin Tencent mati → sinyal berhenti; ledger jadi beku (seperti IDX sekarang).
- Perbedaan satuan (R vs USD vs entri) → kolom terpisah, tidak dijumlahkan buta.
- Data demo/paper diberi label "DEMO/PAPER" di mana pun angkanya muncul.
