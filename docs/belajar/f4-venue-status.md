# F4 — Venue: ternyata hampir semuanya SUDAH jalan (4 Okt 2026)

Rencana `08` mengira F4 = "bangun 4 venue baru". Verifikasi membantahnya: **3 area venue sudah
terhubung dan menyajikan data nyata hari ini**, dan GMGN LP Robinhood chain sudah berjalan.

---

## 1. Bukti per venue (dibaca dari fakta yang sedang hidup)

Sumber: fakta `bagian` di Postgres `warroom`, ditulis ulang `publish-facts` tiap 300 s
(penulisan terakhir **2026-10-04 06:11:40**, tepat setelah cutover F3).

| Area | Status | Bukti nyata |
|---|---|---|
| **IDX (Arjum)** | ✅ **LIVE** | `bagian.idx` berisi saham riil: **SAPX** (WR Event 69,0% · potensi +16% · DD −5% · bucket 🩸 RISIKO PANTULAN), **WOOD**, **DSSA** — lengkap dengan `cross_check` gabungan *Asing + Teknikal* |
| **Crypto** | ✅ **LIVE** | `bagian.crypto`: BTCUSDT harga **84.883,3** · OI 97.484,79 · taker 0,983 · funding 0,0038; ETHUSDT ikut |
| **Forex** | ✅ **LIVE** | `bagian.forex`: **TVC:GOLD** close **4.142,71** · bias *bearish* · EMA20 4.162,25 / EMA50 4.167,89 · ATR14 22,78 |
| **Polymarket** | ✅ LIVE | kind `poly.arm` 1.536 · `poly.agent` 384 · `poly.verdict` 94 · `poly.money` 37 |
| **GMGN** | ✅ LIVE | kind `gmgn` 394 · job `gmgn-sync` (600 s) aktif |

**Arsitekturnya sudah benar sejak awal:** `live-trading` punya `collectors/{idx,idx_check,idx616,idx_stockbit,idx_tv,crypto,forex,hyperliquid,dexscreen,depth}.py`,
snapshot domain menggabungkannya ke `bagian.*`, lalu `publish-facts` menuliskannya sebagai fakta,
dan `services/api/src/warroom_api/areas.py` sudah mengenal area `crypto/idx/forex/gmgn/polymarket`.
**Tidak ada satu venue pun yang perlu dibangun dari nol.**

---

## 2. GMGN LP **Robinhood chain** — sudah dikonfigurasi DAN berjalan

| Bukti | Isi |
|---|---|
| `gmgn_paper/config.py` | `lp_chain = "robinhood"` · `lp_rpc_url = "https://rpc.mainnet.chain.robinhood.com"` |
| `state/lp_pools.jsonl` (8 pool) | contoh pertama: `{"chain":"robinhood","symbol":"NVDA","exchange":"uniswap_v3","fee_pct":0.05,"liquidity_usd":7949580,"volume_24h_usd":41697500}` |
| `state/lp_ledger.jsonl` | **1.112 baris**, field: `ts, address, symbol, liquidity_usd, volume_24h_usd, price_usd, fee_pct, turnover` |
| `ALL_CHAINS` | `("sol","bsc","base","eth","robinhood","arc","stable")` — robinhood sudah jadi anggota resmi |

→ Permintaan owner *"GMGN LP Robinhood chain"* **sudah terpenuhi**. Yang tersisa hanya memperluas
cakupan/pemantauan, bukan membangun.

---

## 3. Celah nyata yang tersisa (2, dan hanya 1 yang butuh owner)

### 🔴 A. MEXC — butuh API key owner
Klien futures **sudah ada dan pernah live-test**: `mexc_client.py` (Tencent, referensi) dengan
`price`, `balance_usdt`, `open_position(symbol, vol, direction, leverage, open_type)`,
`close_position`, `positions`; tanda tangan `HMAC(API_KEY + Request-Time + raw_json_body)`.
Kunci di Tencent **milik orang lain → tidak dipakai**. **Dibutuhkan: API key MEXC milik owner.**
Sampai itu ada, crypto tetap **sinyal-saja** (dan itu memang aman).

⚠️ Catatan disiplin: klien ini **order nyata dengan leverage**. Saat diaktifkan nanti wajib:
di balik gate + izin eksplisit + batas ukuran, pola sama seperti Polymarket.

### 🟡 B. Chain tanpa filter keamanan (`robinhood`, `arc`, `stable`)
`engine.py:146` → `filters = CHAIN_FILTERS.get(chain, ())`, sementara `CHAIN_FILTERS` cuma punya
**sol, bsc, base, eth**. Ditambah `safety_filters` dari env `PAPER_SAFETY_FILTERS` yang default-nya
**kosong** (`()`). Artinya sweep `trending` untuk **robinhood berjalan tanpa filter honeypot/renounced**.

**Perbaikan yang benar (belum dijalankan — perlu verifikasi dulu, jangan menebak):**
tentukan filter apa yang **benar-benar didukung GMGN untuk chain robinhood**, uji satu panggilan
nyata, baru tambahkan ke `CHAIN_FILTERS`. Menebak filter = bisa menyaring habis kandidat atau
error senyap. Ini kerja F4-T2 lanjutan yang kecil tapi harus diukur, bukan diasumsikan.

---

## 4. Dampak ke rencana `08`

| Fase | Rencana awal | Kenyataan |
|---|---|---|
| F4-T3 IDX-Arjum | "bangun collector + UI" | ✅ **sudah ada & live** — tidak dikerjakan ulang |
| F4-T2 GMGN Robinhood | "adapter + tes" | ✅ **sudah ada & berjalan** (1.112 baris ledger) |
| F4 area crypto/forex | "collector + UI" | ✅ **sudah live** |
| F4-T1 MEXC | "adapter + tes" | 🔴 **butuh API key owner** |
| — | — | 🟡 **baru:** filter keamanan robinhood/arc/stable |

**Kesimpulan: F4 mengecil dari "bangun 4 venue" menjadi "1 kunci + 1 perbaikan kecil yang harus diukur".**
