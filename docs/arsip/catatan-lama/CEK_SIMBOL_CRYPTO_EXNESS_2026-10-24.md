# Cek Paralel: Simbol Crypto di Exness MT5 + Rancangan Adapter

Tanggal: 24 Okt 2026

---

## A. Hasil cek simbol di VM (run-command Azure, read-only)

`C:\Users\traderadmin\AppData\Roaming\MetaQuotes\Terminal\*\bases\*\history`

| Server | Simbol yang punya riwayat |
|---|---|
| Custom | (kosong) |
| Default | EURUSD, GBPUSD, USDCHF, USDJPY |
| **Exness-MT5Trial14** | EURUSD, GBPUSD, USDCHF, USDJPY, **XAUUSDm** |

**Tidak konklusif** — folder `history` hanya berisi simbol yang pernah di-chart.
Crypto tidak pernah dibuka di terminal ini, jadi tidak muncul. Ini **bukan** bukti
crypto tidak tersedia.

`symbols.sel` (daftar Market Watch) tidak terbaca — berkas tidak ditemukan di jalur itu.

## B. Daftar resmi Exness (Help Center)

Sumber: `get.exness.help/hc/en-us/articles/17854191888540-Cryptocurrencies`

Isi artikel hanya tiga bagian: **Bitcoin, Ethereum, Bitcoin crosspairs**.

| Simbol | Contract size | Pip size | Min volume | Catatan |
|---|---|---|---|---|
| **BTCUSD** | 1 BTC | 0.1 | 0.01 lot | 24/7, triple swap Jumat |
| **BTCUSDT** | 1 BTC | 0.1 | 0.01 lot | **nama sama dengan universe DeepSeek** |
| BTCJPY | 1 BTC | 10 | 0.01 lot | |
| **ETHUSD** | 1 ETH | 0.1 | **0.1 lot** | min volume tidak bisa 0.01 |
| ETHBTC | 100 ETH | 0.00001 | 0.1 lot | |
| BTCXAU / BTCXAG / BTCTHB / BTCAUD / BTCCNH / BTCZAR | 1 BTC | variasi | 0.5 lot | **close-only** |

### Kesimpulan penting
**Exness hanya menyediakan BTC dan ETH** (plus pasangan silang BTC). **Tidak ada altcoin.**
Klaim review site soal "30 crypto CFD" tidak cocok dengan halaman resmi ini.

> Catatan kejujuran: halaman itu menampilkan banner "we're hard at work updating this content".
> Verifikasi terakhir tetap harus dari **Market Watch di terminal** (klik kanan → Show All).

## C. Implikasi terhadap rencana EA crypto

| | |
|---|---|
| Universe sinyal DeepSeek | **40 koin** |
| Bisa dieksekusi di Exness MT5 | **2 koin** (BTC, ETH) |
| Yang benar-benar cocok nama | **BTCUSDT** (persis sama) |
| Perlu pemetaan | ETHUSDT → ETHUSD |

Jadi dari 40 koin, **38 tidak bisa ditradingkan** lewat MT5 Exness — termasuk HYPE, ZEC,
ASTER, WLD, WLFI, MORPHO yang mendominasi journal crypto Anda.

Artinya: memindahkan sistem crypto ke MT5 Exness **hanya mungkin untuk BTC dan ETH**.
Untuk altcoin, jalurnya tetap exchange (seperti sekarang).

## D. Rancangan adapter `/crypto/ea` (tetap relevan untuk BTC & ETH)

Masalah: EA mengharapkan kontrak berbeda dari yang dikirim node DeepSeek.

**Output DeepSeek sekarang:**
```json
{"symbol":"BTCUSDT","side":"LONG","price":80220.1,"atr":107.14,
 "status":"OK","levels":{"entry":80220.1,"sl":80000.0,"tp1":80440.0,
 "risk":220.1,"rr1":1.0,...}}
```
Tidak ada `levels_mode`, tidak ada `generated_at`.

**Kontrak yang diharapkan EA:**
```json
{"status":"OK","side":"LONG","levels_mode":"relative",
 "risk":220.1,"reward":220.1,"generated_at":1792847006}
```

**Adapter yang diusulkan** — endpoint baru di `routers/tencent.py`:

```
GET /api/v1/tencent/crypto/ea?symbol=BTCUSDT&play=scalping
```

Yang dilakukan:
1. Panggil `/crypto/levels` di node DeepSeek (sudah ada)
2. Petakan simbol: `ETHUSDT` → `ETHUSD`, `BTCUSDT` → `BTCUSDT` (tetap)
3. Ubah level absolut jadi **jarak relatif**: `risk = entry - sl`, `reward = tp1 - entry`
4. Tambahkan `generated_at = time.time()`
5. Teruskan `status` apa adanya (REJECTED/OK), termasuk `reason`
6. Tolak simbol yang tidak ada di Exness (kembalikan `status: "UNSUPPORTED"`)

**Kenapa relatif, bukan absolut:** harga spot (80220) dan harga CFD Exness bisa beda.
Mode relatif membuat EA menghitung level dari harga broker sendiri — persis perbaikan R4
yang sudah terbukti menyelesaikan masalah selisih futures/spot di XAUUSD.

**Yang masih harus diubah di EA (bukan di adapter):**
- `InpApiUrl` harus bisa diarahkan ke endpoint crypto (atau tambah input kedua)
- `InpMaxSpreadPts`, `InpBEBufferPts`, `InpSlippage` harus jadi relatif ATR
- Lot: BTCUSDT contract 1 BTC, `0.01 lot` = 0.01 BTC ≈ $800 notional pada harga 80.000

## E. Kesimpulan

1. **Altcoin tidak bisa** di Exness MT5. Hanya BTC & ETH.
2. Nama simbol **BTCUSDT identik** antara DeepSeek dan Exness — tidak perlu pemetaan.
3. ETHUSD perlu pemetaan + min volume 0.1 lot (bukan 0.01).
4. Adapter tetap layak dibuat, tapi cakupannya hanya 2 instrumen.
5. Untuk altcoin, sistem crypto Anda tetap harus jalan di exchange.
