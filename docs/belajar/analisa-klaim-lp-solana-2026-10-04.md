# Analisis klaim LP Solana dari media sosial — 4 Okt 2026

Sumber: 9 tautan yang dikirim pemilik (Threads ×7, Instagram ×2) + repo `omkarcloud/botasaurus`.
Semua diambil dari **permukaan publik saja**. Label keyakinan:
**[verified]** = gue cek langsung & bertanggal · **[reported]** = pihak ketiga · **[assumed]** = inferensi.

---

## 1. Klaim utama: +122,36% dari BAGSPAY-SOL lewat DAMM v2

**Poster:** `@christoper_alexander_` (Threads, ~4 hari, 731 tayangan) **[verified]**

> Modal masuk: 5,71K BAGSPAY + 0,035 SOL
> Hasil keluar: 6,23K BAGSPAY + 0,077 SOL

### Pool-nya nyata — dan memang DAMM v2

| Data pool (DexScreener, 4 Okt) | Nilai |
|---|---|
| Pasangan | BAGSPAY/SOL |
| DEX + label | `meteora`, label **`DYN2`** = Dynamic AMM v2 (DAMM v2) ✓ |
| Alamat pool | `DxSBgaYreFNFxGu9TEC17n4Usq5jjy4Zf9djT7RBLrGf` |
| Harga | $0,0003271 (0,000002696 SOL) — SOL ≈ $121,33 |
| Likuiditas | $81.137 |
| Volume 24 j | $104.689 → **turnover 1,29×/hari** |
| Perubahan harga | **+58,28% /24 jam** · +8,52% /6 jam |
| Umur pool | **5,4 hari** |

### Angkanya tidak menutup

Menilai kuantitas yang dia tulis dengan harga pasar sekarang:

| | Nilai |
|---|---|
| Masuk | 5.710 × $0,0003271 + 0,035 SOL = **$6,11** (0,050394 SOL) |
| Keluar | 6.230 × $0,0003271 + 0,077 SOL = **$11,38** (0,093796 SOL) |
| **Return dari angka dia sendiri** | **+86,12%** |
| Klaim poster | **+122,36%** → selisih **36,2 poin**, tidak reproducible |

Dari mana 122%? Lihat kenaikan per kaki:

- BAGSPAY: 5.710 → 6.230 = **+9,1%**
- SOL: 0,035 → 0,077 = **+120,0%**  ← **persis di sekitar angka 122%**

Jadi angka besar itu **pertumbuhan kaki SOL**, bukan return posisi. Menambah kuantitas di **kedua**
kaki memang tanda fee masuk (bagus), tapi menyebut "+122%" seolah itu hasil keseluruhan posisi
adalah framing yang menyesatkan.

### Yang tidak disebutkan (dan justru itu yang menentukan)

1. **Jendela waktu** — tidak ada. Tanpa itu, % tidak berarti apa-apa.
2. **Harga masuk & keluar posisi** — hanya kuantitas. Tanpa harga, IL tidak bisa dihitung.
3. **Pembanding hold** — wajib untuk LP. Kalau cuma **memegang** token yang naik +58%/24 jam, bisa
   jadi hasilnya lebih baik daripada LP. Itu impermanent loss; tidak disebut sama sekali.
4. **Fee tier & porsi posisi dalam range** — tanpa ini, fee APR tidak bisa diverifikasi.
5. **Ukuran modal** — masuk ~$6. "+122%" dari $6 = **~$7**. Ini demo, bukan bukti edge.
6. **n = 1**, satu pool berumur 5 hari, di token yang sedang pump — kondisi **paling menguntungkan**
   bagi LP (volume tinggi + kedua kaki naik).

### Putusan

**Konsisten dengan pendapatan fee yang nyata pada posisi sangat kecil saat pump — tetapi
BUKAN bukti edge yang bisa diulang, dan angka +122,36%-nya tidak reproducible dari data yang
dia tulis sendiri.** Menurut disiplin proyek: n=1, tanpa jendela waktu, tanpa CI → **belum terbukti.**
Post itu juga berpola ajakan engagement ("ceritain di komentar ya") — bukan laporan audit.

---

## 2. Sisa tautan — semuanya konten retail, bukan data

| Sumber | Isi | Nilai |
|---|---|---|
| `@zonacryptocoin` (Threads, 2,2K tayangan) | *"aku LP di 2 chain Solana, RH. Bismillah $1k pertama bulan Oktober"* | **[verified]** — sinyal tren: **LP di Solana + Robinhood chain**, sama persis dengan probe LP War Room. Target $1k = kecil, jujur. |
| `@stravonlab` (Minvon) | Promosi grup Telegram internal, posisi long BTW/HYPE | **[reported]** — pemasaran grup sinyal. Belum ada bukti hasil. |
| `@harsky.amsyah` | Sedang mencoba `@copyfomo` (copy trading: Adinerosol, Orangie) | **[reported]** — copy-trading; arah TrenchOps. |
| `@napel.trades` | *"My 82% Win Rate Strategy"* (H/L Asia-London, sweep likuiditas, FVG 1M) | **[reported]** — win rate tanpa R:R, tanpa BE, tanpa n → **tidak bermakna**. Persis pelajaran gate kita (`be=0,7666`). |
| `@gamma.sniper` | MA Cross 9/20 scalping + "pelajaran gratis" Google Drive | **[reported]** — corong funnel. |
| `@captivequant` (Threads) | *"This content isn't available to everyone"* | **[verified]** — tidak bisa diakses. Tidak ditebak isinya. |
| Instagram `cryptoforgeid` | Daftar "TOOLS WAJIB PARA DEGEN": DEX Screener, Fomo, GMGN, Bubblemaps, RugCheck | **[verified]** — dari 5 alat, **2 sudah kita pakai** (DEX Screener, GMGN). Bubblemaps/RugCheck = kandidat. |
| Instagram `robbiekurniawan` | Isi post tidak tampil (hanya komentar) | **[verified]** — tidak bisa dibaca. |
| `omkarcloud/botasaurus` | Framework scraping anti-deteksi bot | **[verified]** — **sudah terpasang** di box ini (`~/.hermes/skills/botasaurus`, `~/tools/botasaurus`). |

---

## 3. Dua jebakan data yang ditemukan saat menguji klaim ini

Keduanya nyata, ditemukan dari data pasar — bukan teori:

### Jebakan 1 — likuiditas besar ≠ ada fee

Ada pool **BONK/USDC di Raydium dengan likuiditas $50.394.585 tetapi volume $0,31/hari.**
Dikonfirmasi dua endpoint (cari dan detail) — bukan payload terpotong.

Kalau LP menaruh modal di situ: **fee nol**, modal terparkir. Kalau penyaringan mengurutkan
berdasarkan **likuiditas**, justru pool mati inilah yang terpilih.

→ **Aturan: urutkan berdasarkan volume, bukan likuiditas.** Fee datang dari transaksi.

### Jebakan 2 — menyebut % tanpa jendela waktu & pembanding hold

Persis kelemahan klaim di bagian 1. Setiap ukuran LP yang kita terbitkan **wajib** menyatakan
apa yang belum diketahui, bukan menebaknya.

---

## 4. Yang dibangun dari pelajaran ini

Ditambahkan ke kolektor `dexscreen.py` (sudah ada di pipeline, gratis, tanpa key):

| Fungsi | Guna |
|---|---|
| `ukur_lp(pool)` | Turnover (vol ÷ likuiditas), tekanan IL dari perubahan harga, umur pool → kelas: `layak-ditinjau` / `tipis` / `pool-mati` / `terlalu-baru` / `belum-cukup-data` |
| `pilih_pool(pools, limit)` | Buang volume nol, urutkan **berdasarkan volume** |
| `lp_cari(kata, limit)` | Cari pool + ukur, siap tampil |

**Setiap hasil selalu membawa dua baris jujur:**
- `fee APR nyata: belum diketahui (butuh fee tier + porsi posisi di dalam range)`
- `LP vs hold: belum diketahui (butuh harga masuk & keluar posisi, bukan kuantitas)`

`enrich()` (dipakai snapshot tiap 15 menit) kini juga menyertakan `lp` per kandidat, jadi data LP
mengalir ke War Room otomatis **untuk semua rantai termasuk `sol` → `solana`**.

**Uji:** 15 tes baru (`test_lp_ukur.py`) · **462 tes lulus** · ruff bersih.

### Contoh hasil nyata (live, 4 Okt)

```
BAGSPAY/SOL      meteora DYN2  vol24 $   104.468  liq $  80.858  turnover 1,29x   layak-ditinjau
Bonk/SOL         orca    wp    vol24 $   541.025  liq $ 430.098  turnover 1,26x   layak-ditinjau
Bonk/USDC        meteora DLMM  vol24 $   209.270  liq $ 267.482  turnover 0,78x   layak-ditinjau
SPEC/SOL         meteora DYN2  vol24 $11.131.119  liq $ 158.586  turnover 70,2x   terlalu-baru
STONK/SOL        meteora DLMM  vol24 $10.403.365  liq $2.801.041 turnover 3,71x   layak-ditinjau
BONK/ETH         uniswap v4    vol24 $ 1.487.979  liq $   2.433  turnover 611x     tipis
```

Perhatikan baris terakhir: turnover 611× **tetap `tipis`** karena likuiditasnya cuma $2.433 —
fee besar tapi keluar-masuknya akan menghabisi modal lewat slippage. Alat ini menolak godaan itu.

---

## 5. Kesimpulan operasional

1. **Klaim +122% itu tidak lolos uji** → jangan dijadikan alasan menaikkan alokasi LP.
2. **Arah LP-nya tetap masuk akal** dan didukung sinyal independen (`@zonacryptocoin`: LP di
   Solana + RH) — tapi harus diukur, bukan dari tangkapan layar.
3. Probe LP yang sudah jalan (Robinhood chain, 1.112 baris ledger) kini punya **jalan ke Solana**
   lewat kolektor yang sudah ada, tanpa API key dan tanpa biaya.
4. **Yang masih kurang untuk memutuskan:** fee tier pool, ripian posisi, dan pencatat **harga masuk
   & keluar** supaya IL vs hold bisa dihitung. Tanpa itu, semua angka LP tetap "belum diketahui".
