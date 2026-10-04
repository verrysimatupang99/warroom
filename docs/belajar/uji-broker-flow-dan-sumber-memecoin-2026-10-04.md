# Uji broker-flow ke riwayat + sumber memecoin empat venue — 4 Okt 2026

Lanjutan dari dua permintaan pemilik: **(1)** uji apakah skor broker-flow benar-benar berguna,
**(2)** sambungkan sumber kanal `@awsnumsignal` (Pumpfun · Jup · Robinhood · Stonkfun).

---

## 1. Apakah broker-flow berguna? Diuji ke riwayat, bukan diklaim

### Apa yang bisa dan tidak bisa diuji

| Data | Tersedia? |
|---|---|
| `broker_summary` **historis** (skor harian) | ❌ endpoint tidak menerima tanggal — skor harian **tidak bisa direkonstruksi** |
| `broker_accumulation(code, days)` | ✅ deret harian per broker, ~4 bulan (`nval`, `cum_nval`, `bavg`, `savg`) |
| `history(code, frame)` | ✅ harga harian, tersedia sejak 2020-01-02 |

Karena skor harian tidak bisa diambil ulang, yang diuji adalah **arah net broker** yang bisa
direkonstruksi dari `broker_accumulation`: hari dengan **total net broker positif** dibanding
**semua hari lain** pada periode yang sama (dasar pembanding).

### Hasil (120 hari, 7 Apr – 2 Okt 2026)

| Emiten | 5 hari | 10 hari | 20 hari | Verdict |
|---|---|---|---|---|
| **DSSA** | +1,52% vs −2,24% (**+3,76pp**) | +2,43% vs −4,30% (**+6,73pp**) | +10,47% vs −3,90% (**+14,37pp**, menang 79%) | **ada-keunggulan** |
| **BBCA** | −0,28% vs −0,16% (−0,11pp) | +0,07% vs −0,33% (+0,41pp) | +0,30% vs +0,17% (+0,13pp) | **ada-keunggulan** (tipis) |
| **SAPX** | +3,80% vs +2,92% | +10,88% vs +5,88% | +28,08% vs +11,55% | **perlu-uji-tambahan** |
| **WOOD** | −2,01% vs −1,67% | −4,67% vs −3,63% | −5,78% vs −7,55% | **tidak-terbukti** |

**Baca yang jujur:**

- **2 dari 4 menunjukkan keunggulan**, 1 tidak bisa dinilai, 1 tidak terbukti. Itu **bukan**
  bukti kuat — n=4 emiten, satu periode 6 bulan, satu rezim pasar.
- **SAPX ditandai `perlu-uji-tambahan` dengan benar**: sinyalnya menang di ketiga horizon, tapi
  dasar pembandingnya juga positif di ketiga horizon (saham itu naik kuat). Modul menolak
  menyebutnya keunggulan karena tidak bisa memisahkan sinyal dari pasar yang naik. Itu perilaku
  yang diinginkan.
- **DSSA** paling kuat dan paling meyakinkan: dasar pembandingnya **negatif** (saham turun),
  sementara hari-hari sinyalnya positif. Itu pemisahan yang sebenarnya.
- **BBCA** secara statistik "menang" tapi besarnya cuma +0,13 s/d +0,41 poin — praktis nol
  setelah biaya. Verdict `ada-keunggulan` di sini menyesatkan kalau dibaca tanpa angkanya; itu
  kelemahan ambang yang saya biarkan terbuka dan catat di sini.

### Putusan

**Cukup menjanjikan untuk diuji lebih lanjut, belum cukup untuk dipakai sebagai sinyal.**
Langkah berikutnya yang benar: uji ke **lebih banyak emiten dan beberapa periode**, dan
tambahkan **biaya transaksi** ke ambangnya — supaya `ada-keunggulan` tidak bisa muncul dari
selisih 0,13 poin.

### Yang dibangun

`bandarmologi.seri_broker()` — gabungkan deret per-broker jadi deret harian (total net, jumlah
broker akumulasi).
`bandarmologi.uji_riwayat()` — uji aturan ke seluruh riwayat + dasar pembanding, dengan standar
bukti yang sama seperti `overextended` (perlu ≥2 horizon; `perlu-uji-tambahan` saat seluruh
periode searah).

---

## 2. Sumber memecoin empat venue

Kanal `@awsnumsignal` menyebut empat sumber. Diperiksa satu per satu ke data nyata:

| Venue klaim | Bisa diambil? | Bagaimana |
|---|---|---|
| 🌊 **Pumpfun** | ✅ | chain `solana`, dexId `pumpfun`/`pumpswap` |
| 🪐 **Jup** | ⚠️ | **Jup itu agregator, bukan venue.** Likuiditasnya ada di `meteora`/`raydium`/`orca` — itu yang diambil, dan itu dinyatakan di keluaran |
| 🟢 **Robinhood** | ✅ | chain **`robinhood`**, dexId `uniswap`/`flapsh` — rantai ini **di-index DexScreener** |
| 📈 **Stonkfun** | ❌ | **tidak ditemukan** di DexScreener. Dinyatakan tidak tersedia, **tidak ditebak** |

### Keluaran nyata (dari snapshot, 5 kandidat per venue)

```
--- pumpfun (3 teratas) ---
   ACM/SOL       solana    pumpfun   vol24 $196.260  liq —        turn —
   CRAFT/SOL     solana    pumpfun   vol24 $137.163  liq —        turn —
--- jup -> DEX Solana (3 teratas) ---
   JUP/SOL       solana    orca      vol24 $2.590.970 liq $837.574 turn 3,093
   JUP/SOL       solana    meteora   vol24 $1.149.108 liq $2.319.679 turn 0,495
--- robinhood (3 teratas) ---
   Robinhood/ETH robinhood uniswap   vol24 $  34.550 liq $ 30.299 turn 1,14
   ROBINHOOD/ETH robinhood uniswap   vol24 $  33.859 liq $124.073 turn 0,273
```

### Temuan data: pumpfun tidak melaporkan likuiditas

Semua pool pumpfun menunjukkan `liq: None`. Dicurigai jebakan payload-terpotong seperti kasus
BONK sebelumnya — jadi **diperiksa**: endpoint **cari** dan endpoint **detail** sama-sama
mengembalikan `None`. **Bukan payload terpotong; memang tidak dilaporkan.**

Konsekuensinya: di pumpfun **turnover tidak bisa dihitung**. Itu dinyatakan lewat
`liq_tersedia: false` alih-alih diam-diam menampilkan "—". Urutannya tetap pakai volume, jadi
penyaringan masih berguna.

### Bug nyata yang ketemu lewat tes

`pumpswap` semula saya masukkan ke **dua** venue (pumpfun **dan** jup). Akibatnya peta jadi
**ambigu** dan hasil klasifikasi bergantung urutan kamus — `pumpswap` bisa terbaca `jup` hanya
karena kebetulan urutannya. Diperbaiki: `pumpswap` adalah AMM milik Pump, jadi **hanya** pumpfun.
Ditambah tes invarian: **himpunan dexId antar-venue harus saling lepas.**

### Aturan kejujuran

Modul ini **memindahkan label asli kanal sumbernya**: *"data mentah, bukan rekomendasi — tidak
ada track record yang bisa diverifikasi."* Label itu ada di setiap keluaran, tidak dihapus.

### Yang dibangun

`collectors/memecoin.py` — `klasifikasi_venue()` (chain+dexId → venue), `pilih_venue()`
(urut volume, bukan likuiditas), `skrining()` (cache 15 menit, satu venue gagal tidak
menjatuhkan sisanya). Tersedia di snapshot sebagai **`bagian.memecoin`** dan di kunci area GMGN.

---

## Status jujur: apa yang SUDAH dan BELUM tersambung

| | Status |
|---|---|
| Sumber venue tersedia sebagai data | ✅ `bagian.memecoin` di snapshot (12 bagian) |
| Tersaji ke API & UI | ✅ kunci area `gmgn` |
| **Dipancarkan sebagai sinyal oleh job `signal-sync`** | ❌ **belum** |

Saya **tidak** mengklaim poin terakhir sudah selesai. `signal-sync` sekarang membaca
`state/verdicts.jsonl` (sinyal yang sudah lolos gate). Menyalurkan kandidat venue ke sana
menuntut keputusan desain yang belum diambil: apakah kandidat mentah boleh masuk aliran sinyal
(yang selama ini berarti "lolos gate"), atau harus jadi aliran terpisah. **Pilihan itu milik
pemilik**, karena menyampurkan keduanya justru melemahkan pembeda utama kita: label jujur.

---

## Verifikasi

| Uji | Hasil |
|---|---|
| Suite | **551 lulus** · ruff **All checks passed** |
| Snapshot dari **job** | ✅ **12 bagian** — `memecoin` masuk |
| Halaman | ✅ semua 200 · 0 unit failed |
| Uji riwayat | 4 emiten × 3 horizon, dijalankan ke data Arjum nyata |
| Uji venue | live ke DexScreener: 9 kandidat, 0 galat |
