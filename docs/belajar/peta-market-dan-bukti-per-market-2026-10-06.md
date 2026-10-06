# Peta Market & Bukti per Market (6 Okt 2026)
*Cara membaca dashboard baru: sinyal, akurasi, PnL, entry setup — per market.*

## Empat pertanyaan yang dijawab tiap market

1. **Sinyal terbaru** — apa yang mesin barusan katakan, termasuk yang DITOLAK.
2. **Entry setup per sinyal** — kolom khas marketnya, bukan kolom seragam yang tidak berarti.
3. **Akurasi sinyal** — angka dari ledger nyata + tingkat pakem (INSUFFICIENT → TUNING).
4. **PnL per market** — R untuk seri R; P&L USD untuk LP; entri menang/kalah untuk Polymarket.

## Keunikan yang sengaja ditampilkan

| Market | Kolom khas | Kenapa begitu |
|---|---|---|
| Crypto | Skor gate % (aturan lolos), tier, POI SMC, daftar aturan gagal, dimensi gerbang | Gate adalah inti prosesnya — memperlihatkan mana yang menggagalkan setup jauh lebih berguna daripada skor kosong |
| Forex | Zona (FVG/OB), time-frame, konfluensi, R | Entry forex selalu zona+temporal; "harga entry" saja tidak menggambarkan setupnya |
| IDX | Setup (ARA_HUNTER/BSJP/INTRADAY), zona, net R | Setup adalah unit analisis yang sudah dipakai grader v3; mencampurnya akan menghapus makna |
| GMGN/LP | P&L USD, IL, fee, umur posisi | LP tidak punya R; memaksa R = mengarang angka |
| Polymarket | Menang/kalah, win-rate, PnL per arm, skips | Unitnya entri biner; skips adalah cerita sebenarnya dari mesin yang disiplin |

## Bacaan angka hari ini (6 Okt)

- **Crypto**: 400 verdict tersimpan, 178 lolos gate. Trade tuntas masih 5 (4 hari) → INSUFFICIENT.
- **IDX**: BSJP satu-satunya positif (+0,608R / 45 trade / 9 hari) tapi belum 10 hari; ARA_HUNTER negatif berat (−0,702R).
- **Forex**: 4 trade tuntas → INSUFFICIENT. NO FILL ditampilkan, tidak dihitung.
- **LP**: 5 posisi dinilai, PnL −3,24 USD → INSUFFICIENT.
- **Polymarket**: arm B +6,40 USD (n=169, TUNING), D +12,01 USD (n=34, PRELIMINARY), A −10,34 USD (n=10).

## Di mana mesin sinyal hidup (penting!)

- **Crypto & Forex & IDX**: mesin sinyal ada di **Tencent** (cron Hermes). War Room
  menyimpan buktinya (import/salin). Kalau Tencent mati → sinyal tidak bertambah.
- **GMGN/LP & radar**: sudah pindah **lokal Webdock** (Azure dimatikan).
- **Polymarket**: mesin paper berjalan lokal; livetrade pernah jalan (fase pilot).

Aturan: **jangan pernah menyamarkan epoch beku sebagai "live"**. Ledger yang berhenti
bertambah ditandai; itu kejujuran inti proyek ini.

## Narasi LLM per market (6 Okt)

Job `llm-brief-<market>` (crypto/forex/idx/gmgn/polymarket), 6 jam sekali:
- Fakta diringkas **angka-utuh** untuk narator (bukan 80 karakter pertama JSON, yang dulu
  membuat LLM bercerita tentang checksum).
- Output wajib menyertakan `fact_ids`; kartu UI menampilkan provider + versi prompt + jumlah fakta.
- Narasi **tidak pernah** menggantikan angka; kartu menyatakan "deskriptif, bukan rekomendasi".
- Ambang gate & keputusan tetap milik manusia — LLM hanya menjelaskan.

## Timestamp sinyal (6 Okt, permintaan owner)

Setiap sinyal kini menyebut **kapan ia digenerate** — di verdikt Home
("Sinyal digenerate: 07 Okt 2026, 03.16 WIB (55m lalu)") dan sebagai kolom
**DIBUAT** di tabel Sinyal & Entry Setup (crypto/forex/IDX).

Bedanya dengan `umur_s` lama (penting):
- `umur_s` = umur **fakta** di DB (kapan terakhir dipublikasikan ulang).
- `umur_sinyal_s` = umur **sinyal** sejak mesinnya menghasilkan (field `ts` gate,
  `waktu` jurnal, `diambil_epoch` radar).
Yang kedua ini yang menjawab "masih segar atau sisa kemarin".

Sumber waktu per market: crypto `ts` kandidat terbaru · forex `waktu` jurnal ·
IDX `dibuat` ledger · GMGN `diambil_epoch` radar · Polymarket & LP waktu terbit fakta.
Kalau sumber tidak punya waktu → ditulis "waktu sinyal tidak tercatat", tidak dikarang.

## Temuan yang ikut diperbaiki (kelas bug "kartu kosong palsu")

1. Home menyatakan **IDX/Forex "TIDAK ADA"** padahal ledger sinyalnya berisi — Home
   hanya membaca `*_posisi` (kosong). Kini membaca `*_sinyal` (entry teratas + waktu).
2. **GMGN selalu "TIDAK ADA"**: radar ditulis kind `gmgn` (bukan `snapshot`) dan
   daftarnya bernama `chains` (bukan `state`). Setelah diperbaiki: robinhood V/L 18.82
   (34/60 pool layak) tampil dengan waktunya.
