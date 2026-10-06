# Keputusan Arah & Temuan Malam 7 Okt 2026

*Ditulis untuk dibaca pemilik saat bangun. Ringkas, angka nyata, tanpa hiasan.*

## Jawaban langsung untuk 8 poin

1. **Crypto pakai SMC/Fib GP/yang ada di Tencent** — SMC aktif dari Tencent; Fib Golden
   Pocket tetap **"rencana"** (jujur: belum diuji, jangan dipakai dulu).
2. **Kurva Ekuitas Crypto** — jalan, sumbernya **ledger trade tertutup** (satuan R),
   **bukan** kandidat setup. Kandidat baru jadi titik setelah dibuka & ditutup. Order yang
   tak terisi ditandai `expired` dan tidak dihitung. Penjelasan ini kini tertulis di halaman.
3. **Cockpit & Setup dirapikan** — Cockpit: dompet + kurva + risiko. Setup: kandidat +
   sinyal/entry + akurasi (RiskMeter dipindah ke Cockpit agar tidak kosong-menggantung).
4. **Polymarket → Setup B** — tab utama sekarang `Setup B`; A/C/D dibekukan ke `Arsip`.
5. **IDX → tab "Sinyal"** (bandarmologi + BSJP + ARA), "Aliran" kembali jadi tab sendiri.
6. **Forex dirombak** — ringkas per-pair, kalender dengan hitung mundur, kalkulator posisi.
7. **GMGN: "Robinhood Chain" dijelaskan** — lihat bagian riset di bawah.
8. **Sistem/Riset/Info** — Riset dapat panel Dompet Lintas Market; Info membaca 25 catatan
   repo (dokumen malam ini sudah terbaca dari UI).

## Temuan terpenting: dompet Rp 10 juta membongkar kebenaran IDX

| Setup | n | mean R | Hasil dompet Rp 10 jt |
|---|---|---|---|
| **BSJP_STRONG** | 26 | +0,789 | **+Rp 2.051.420 (+20,5%)** |
| **BSJP_ARA** | 19 | +0,360 | **+Rp 684.220 (+6,8%)** |
| INTRADAY | 35 | −0,011 | −Rp 37.820 (−0,4%) |
| **ARA_HUNTER** | 198 | −0,702 | **−Rp 13.908.020 (−139%)** |

**Pelajaran:** pertanyaan yang benar bukan "IDX untung/rugi", tapi **"setup mana yang
dipakai"**. ARA_HUNTER menghabiskan dompet sendirian sementara BSJP menghasilkan.
Keputusan yang tersedia: matikan ARA_HUNTER, atau kecilkan risikonya.

## Temuan kedua: 2R hilang di ledger crypto

OP_USDT & LIT_USDT menggantung "still_open" sejak 27 Sep padahal SL terjadi 27–28 Sep.
Ledger melaporkan **+3,844R → sebenarnya +1,844R** (winrate 66,7% → 50%).
Sudah ditutup lewat `rekonsiliasi.py` + job `rekonsiliasi-crypto` (tiap jam) supaya tidak
terjadi lagi.

## Temuan ketiga: akurasi crypto mandek karena mesin tidak pernah eksekusi

`paper-scan` memindai 6 pair warisan, bukan `verdicts.jsonl` (192 izin dari 68 pair).
Akibatnya trade tidak pernah terbuka → akurasi mustahil membaik. Sudah diperbaiki:
**3 posisi pertama terbuka** (WIF/INJ/AAVE) dengan biaya depth terukur 10–12 bps.

## Riset LP: "Robinhood Chain" vs Meteora (jawaban poin 7)

- **Robinhood Chain NYATA**: L2 Arbitrum Orbit, chain ID **4663**, gas ETH, mainnet 1 Jul 2026.
- LP di sana = **Uniswap v2/v3/v4**, **bukan Meteora**. Ada Stock Token (TSLA dll).
- **Meteora murni Solana** (DLMM/DAMM v2); **tidak ada** kaitan terverifikasi dengan Robinhood.
- Data kita diverifikasi hidup: MET-USDC → Meteora vs DexScreener vs GeckoTerminal
  **sepakat dalam 0,06%**. Halaman GMGN menampilkan perbandingan ini langsung.

## "Apakah data kita sama dengan internet live?"

Sekarang bisa dijawab dengan alat: `/gmgn?sub=radar` → panel **Verifikasi Harga vs API
Publik** memanggil 3 sumber keyless untuk pool yang sama dan menampilkan selisihnya.
Ambang 1%; di atas itu ditandai "SELISIH", bukan disembunyikan.

## Yang masih terbuka (jujur)

- Mesin sinyal Crypto/Forex/IDX **masih di Tencent**; mati = sinyal berhenti (bukti tetap).
  350 sinyal IDX terbuka tidak akan tertutup selama mesin beku — itu ditampilkan apa adanya.
- Forex sampel masih 4 trade (INSUFFICIENT). Jangan jadikan dasar keputusan besar.
- Fib Golden Pocket: spesifikasi uji belum dibuat (butuh walk-forward, bukan cerita).
