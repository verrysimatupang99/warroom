# Akurasi IDX diangkat ke War Room (6 Okt 2026)

Latar: IDX punya bukti **paling matang** yang dimiliki proyek (ledger 628 sinyal, grader v3,
jurnal 1.830 baris) tapi tidak mengalir ke War Room — blok equity/ledger IDX menampilkan nol.
Arahan owner: *"semua yang dibutuhkan ditampilkan di website harus selaras dengan apa yang
ada di balik layar"*. Maka ledger mesinnya **diangkat**, bukan dihitung ulang dengan rumus baru.

## 1. Epoch beku — kenapa impor aman

Cron IDX di Tencent sudah **di-pause** (28 job off, termasuk semua watcher IDX) sejak 5–6 Okt.
Artinya ledger berhenti bertambah → impor satu kali menjadi **epoch beku**, bukan cermin
yang bisa menyimpang. Ini syarat supaya angka lama dan baru diperlakukan sama.

| | Nilai |
|---|---|
| Sumber | `tencent:43.155.219.37:~/.hermes/cron/state/idx616_signal_ledger.db` |
| Impor ke | `state/idx_ledger.db` (lokal) |
| Jejak | `state/idx_ledger_sumber.json` — sha256 + tanggal impor |
| Baris | 628 sinyal · **278 tuntas** · 350 belum tuntas |
| Grader | v3-ara-intraday (253), v2-bsjp-open-exit (25) |

## 2. Angka yang diangkat (identik dengan drift mesin Tencent)

Diverifikasi ulang di modul War Room — **selisihnya nol** terhadap `idx616_drift.json`:

| Setup | n | hari | WR | mean R | total R | pakem |
|---|---|---|---|---|---|---|
| ARA_HUNTER | 198 | 5 | 38,4% | **−0,702** | −139,08 | INSUFFICIENT |
| INTRADAY | 35 | 11 | 34,3% | **−0,011** | −0,38 | DIRECTIONAL |
| BSJP gabungan | 45 | 9 | 66,7% | **+0,608** | +27,36 | INSUFFICIENT |
| ↳ BSJP_STRONG | 26 | 8 | 80,8% | +0,789 | +20,51 | INSUFFICIENT |
| ↳ BSJP_ARA | 19 | 7 | 47,4% | +0,360 | +6,84 | INSUFFICIENT |

**Pelajaran yang ditemukan saat verifikasi:** definisi "tuntas" menentukan arah angka.
Versi pertama modul mengeluarkan `TIMEOUT` dari metrik → INTRADAY terbaca **+0,107**
(seolah menguntungkan). Padahal TIMEOUT adalah posisi yang **ditutup di pasar** dengan
`net_r` nyata (−0,6R dst). Setelah dimasukkan, angkanya kembali **−0,011** — sama dengan
drift Tencent. Dikeluarkan dari metrik = membuang kerugian nyata. Kelas bug yang harus
selalu dicurigai: "angka membaik karena definisi, bukan karena bukti".

Bacaan jujurnya: **BSJP satu-satunya yang positif**, tapi baru **9 hari bursa** — pakem
menahannya di INSUFFICIENT sampai 10 hari (DIRECTIONAL) / 30 hari (PRELIMINARY).
ARA_HUNTER negatif berat dengan 198 trade tapi cuma 5 hari (95 trade di satu hari) —
contoh sempurna kenapa koreksi klaster hari wajib.

## 3. Keputusan desain yang dipegang

1. **Metrik hanya dari baris tuntas.** Belum tuntas (350) & ambigu dilaporkan di kolom
   terpisah — jangan campur, jangan juga disembunyikan.
2. **n hari ≠ n trade.** Pakem memakai hari bursa unik (satu hari = satu event korelasi).
3. **Jejak sumber wajib tampil** di UI (sumber + tanggal impor + sha256 dipotong).
4. **Setup dengan <5 baris tuntas tidak tampil sebagai "akurasi"** — ditandai belum cukup
   sampel, bukan disembunyikan diam-diam.
5. **Impor ulang hanya bila ledger sumber berubah** (sha256 berbeda). Bila nanti mesin IDX
   dihidupkan lagi di Webdock, importer ini tidak dipakai lagi — ledger baru ditulis langsung.

## 4. Yang tampil sekarang

- Snapshot: kunci `idx_akurasi` (selalu ada, offline-safe karena murni lokal).
- API: `GET /api/v1/areas/idx` → fakta `idx_akurasi`.
- UI: blok **"Akurasi Signal per Setup"** di area IDX (semua tab) + ringkasan BSJP gabungan
  + baris sumber/jejak impor.

## 5. Belum (jujur)

- **Jurnal IDX 1.830 baris** (xlsx) belum diangkat — ledger di atas lebih rapi dan sudah
  tervalidasi; jurnal berguna untuk audit silang, bukan angka utama.
- **Forex** (5 trade XAUUSD + backtest MC) dan **Crypto** (measure.py sudah punya n/WR)
  belum memakai modul pakem yang sama — urutan berikutnya setelah ini terbukti di UI.
- **Mesin sinyal IDX-nya sendiri belum berjalan di Webdock** — yang diangkat baru buktinya.
  Menjalankan ulang watcher (SCALP/ARA/BSJP) di sini butuh keputusan owner (kuota Arjum).
