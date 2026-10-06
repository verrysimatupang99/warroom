# Riset LP: "Robinhood Chain" vs Meteora (7 Okt 2026)

*Jawaban untuk pertanyaan owner: "yang LP Robinhood Chain seperti di meteora itu maksudnya gimana?"*

## Kesimpulan utama (satu paragraf)

**Robinhood Chain itu NYATA** — L2 Arbitrum Orbit, chain ID **4663**, gas pakai ETH, mainnet
1 Juli 2026. LP di sana adalah **Uniswap v2/v3/v4** (bukan Meteora). **Meteora murni Solana**
(DLMM + DAMM v1/v2) dan **tidak punya kaitan terverifikasi** dengan Robinhood Chain —
menyamakan keduanya adalah miskonsepsi yang wajar muncul karena istilah "concentrated
liquidity" dan "dynamic AMM" dipakai keduanya.

## Fakta terverifikasi

| Klaim | Status | Bukti |
|---|---|---|
| Robinhood Chain ada (chain ID 4663, gas ETH) | ✅ | docs.robinhood.com/chain/connecting |
| AMM utama = Uniswap v2/v3/v4 | ✅ | blog.uniswap.org (2 Jul 2026) + DexScreener `chainId:"robinhood"`, `dexId:"uniswap"` |
| Stock Token (TSLA dll) benar ada | ✅ | pool TSLA/WETH v3 → priceUsd ~$380,67, liq $342.014 |
| Meteora ↔ Robinhood Chain | ❌ tidak ada bukti | Meteora Solana-only; program DAMM v2 `cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG` |
| "AI-native" Robinhood Chain | 🟡 pemasaran | tidak ada metrik independen |
| Token native Robinhood | ❌ tidak ada | gas ETH; semua "coin Robinhood" = meme |
| GeckoTerminal dukung Robinhood | ❌ 404 | dipanggil live saat riset |

## Yang dipakai proyek ini (dan apa artinya untuk radar kita)

Radar kita menampilkan chain **robinhood** dengan label window/avg V/L — itu **benar**:
chain-nya ada dan DexScreener mengindeksnya. Yang perlu diubah hanya **penamaan**:
LP di Robinhood = **Uniswap v3/v4**, sedangkan LP Solana (Meteora) = **DLMM/DAMM v2**.
Dua hal berbeda; jangan dicampur dalam satu baris "LP" tanpa keterangan protokol.

## API gratis tanpa kunci (untuk verifikasi harga/data kita vs internet)

| Sumber | Kegunaan | Catatan |
|---|---|---|
| DexScreener `api.dexscreener.com` | discovery lintas chain (termasuk robinhood) | **tidak ada** field `fees` |
| GeckoTerminal `api.geckoterminal.com/api/v2` | OHLCV, likuiditas terkunci | 30 call/menit; robinhood tidak ada |
| Meteora DAMM v2 `damm-v2.datapi.meteora.ag` | kebenaran pool Meteora (fee, config, TVL) | 10 RPS |
| Meteora DLMM `dlmm.datapi.meteora.ag` | idem untuk DLMM + PnL posisi | 30 RPS |
| Raydium `api-v3.raydium.io` | pool Raydium (feeRate, feeApr) | gratis |

**Contoh angka live (6 Okt):** MET-USDC DAMM v2 → TVL $3.062.595 (Meteora) vs $3.612.994
(DexScreener) — beda metodologi ±18%, itu **normal**. Volume konsisten ±0,7%.
→ Aturan proyek: **cross-check minimal 2 sumber**, dan sebutkan sumbernya.

## Cross-check: apakah data kita sama dengan internet live?

Fitur `lp_verifikasi.py` memanggil DexScreener + Meteora DAMM v2 + GeckoTerminal untuk
pool yang sama dan menampilkan selisih harga antar sumber. Kalau selisih > 1%, itu alarm
(mis. cache kita basi atau pool-nya tipis). Semua request keyless; gagal = ditandai,
bukan dikarang.
