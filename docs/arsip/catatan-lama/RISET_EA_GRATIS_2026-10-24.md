# Riset EA Gratis untuk Instrumentasi XAUUSD

Tanggal: 24 Okt 2026
Tujuan: mempelajari cara EA lain mengukur eksekusi, membatasi risiko, dan mencatat trade —
untuk dipakai pada instrumentasi War Room EA. **Tidak ada kode yang diambil/diubah.**

---

## 1. Peta sumber (di mana EA gratis berada)

| Sumber | Isi | Kualitas |
|---|---|---|
| **MQL5 Code Base** (`mql5.com/en/code/mt5/experts`) | Source code `.mq5` lengkap, gratis, ratusan EA | Campur — banyak edukasi, banyak juga sampah |
| **MQL5 Market → Free** (`mql5.com/en/market/mt5/expert/free`) | EA gratis **tanpa source** (hanya `.ex5`) | Tidak bisa dipelajari kodenya — hanya bisa diuji |
| **GitHub** (`topics/mql5`, `topics/mt5-ea`) | Source terbuka, ada lisensi jelas | **Terbaik untuk dipelajari** |
| **forexr.com/expert-advisors** | Indeks 2.043 EA GitHub dengan lisensi & stars | Bagus untuk navigasi |
| **Forex-Station / Forex Factory** | Arsip `.mq4/.mq5` lama | Banyak EA martingale berbahaya |

**Kesimpulan praktis:** yang layak dipelajari adalah **GitHub + MQL5 Code Base**.
MQL5 Market gratis tidak memberi source, jadi tidak bisa dipelajari — hanya bisa dites.

---

## 2. Yang paling relevan untuk instrumentasi (prioritas 1)

### a) MQL5 Article 22998 — "Measuring broker execution quality in MQL5"
**Ini yang paling penting dari seluruh riset.** Isinya persis pekerjaan yang kita rencanakan.

Dua mode pengukuran:

| Mode | Cara | Akurasi |
|---|---|---|
| **Probe (aktif)** | Catat quote **tepat sebelum** kirim order, bandingkan dengan fill | Presisi — ini request-to-fill sebenarnya |
| **Passive** | Dengar `OnTradeTransaction`, bandingkan fill dengan quote saat event diterima | Perkiraan — event datang **setelah** eksekusi |

Poin teknis yang harus kita tiru:
```mql5
// positive slippage = fill lebih buruk dari referensi
double slip = isBuy ? (fill - reference) / _Point
                    : (reference - fill) / _Point;
```
- Simpan **sampel**, laporkan **median dan p95** — bukan rata-rata (rata-rata tertarik outlier)
- Catat juga **latensi (ms)** dan **retcode** (requote 10004, price changed 10020)
- Tulis ke CSV di `MQL5\Files`

**Implikasi untuk rancangan kita:** desain "Titik A" saya sudah benar arahnya (requested vs
`trade.ResultPrice()`), tapi kurang tiga hal: **latensi**, **p95**, dan **pemisahan entry vs exit**.

### b) MQL5 Article 1683 — slippage & limit order
Temuan yang **mengubah asumsi kita**:

> "Market orders of symbols, whose execution type is 'Market Execution' … do not require
> specification of price." dan "deviation … required field for Instant and Request Execution only;
> Market and Exchange requests need no price or deviation."

Artinya: **pada simbol Market Execution, `deviation` diabaikan broker.**
`InpSlippage = 30` di EA kita kemungkinan besar **tidak melakukan apa pun** kalau XAUUSDm
bertipe Market Execution.

Ini harus diverifikasi (`SYMBOL_TRADE_EXECUTION`), dan kalau benar, satu-satunya cara
membatasi slippage adalah **limit order**, bukan `deviation`.

### c) `MT5-Automation-Labs/mt5-prop-firm-guard` (MIT)
Library `PropGuard.mqh` — penjaga risiko yang bisa dipakai EA apa pun:

- Daily loss limit (dari balance atau max(balance, equity))
- Max drawdown statis **atau trailing**
- **Max open risk**: total risiko SL semua posisi terbuka; posisi tanpa SL **memblokir entry baru**
- **Pre-trade check**: order ditolak kalau stop-out semua posisi bisa melanggar limit
- Max trade per hari
- **Filter jam** (termasuk jendela lewat tengah malam), blokir weekend, cutoff Jumat
- **Jendela berita** dengan menit sebelum/sesudah
- Auto-flatten + blokir saat limit tersentuh
- State bertahan setelah restart (global variable terminal)

**Yang layak diadopsi:** `maxOpenRiskPct` dan aturan "posisi tanpa SL memblokir entry".
Ini jawaban langsung untuk temuan kepadatan posisi di analisa crypto — dan lebih rapi
daripada menghitung jumlah posisi.

### d) MQL5 Code Base — "Order Watchdog" (read-only)
EA yang **tidak pernah trading**, hanya mengawasi: magic tak dikenal, posisi duplikat
setelah reconnect, **posisi tanpa SL**, stop out, dan apa yang terjadi saat EA mati.

**Kenapa penting:** ini pola yang aman — pengawas terpisah dari eksekutor. Kalau EA utama
bug, pengawas tetap melapor.

### e) MQL5 Code Base — "Spread Monitor"
Panel spread real-time + **rata-rata, minimum, maksimum** dari histori bergulir, plus
hitungan berapa kali melewati ambang.

**Relevan langsung:** kita butuh data spread per jam untuk menentukan jendela likuiditas
XAUUSD. EA ini pola yang tepat — dan bisa jadi alat ukur sementara tanpa menyentuh EA utama.

---

## 3. EA XAUUSD yang layak dipelajari (prioritas 2)

| EA | Sumber | Yang bisa dipelajari | Lisensi |
|---|---|---|---|
| **GOLD_ORB** (306★) | `yulz008/GOLD_ORB` | Struktur OOP bersih: kelas `Price_Action`, `new_candle_check2`, ORB H1. Contoh terbaik untuk pemula MQL5 | **tidak dinyatakan** — jangan copy kode |
| **GoldLondonBreakout** | MQL5 Code Base | Range sesi Asia → OCO BuyStop/SellStop saat London buka, SL berbasis ATR, **sizing berdasarkan % risiko**. "Range diukur, bukan ditebak" | Code Base (baca, jangan redistribusi) |
| **Stochastic Daily Breakout** | MQL5 Code Base | Backtest 2021–2026: +245%, DD 23,9%. Stop order di high/low kemarin + filter Bollinger | Code Base |
| **Gold Breakout EA H4** | MQL5 Code Base | Turtle breakout: 2 ATR stop, target 2R, PF 1,77, DD 11,38%, 6/7 tahun profit | Code Base |
| **Quantum XAUUSD Silver Trader** | MQL5 Code Base | RSI+ADX+MA, **ATR trailing adaptif**, proteksi modal bawaan | Code Base |
| **FvgGold-EA** (44★) | `foeed/FvgGold-EA` | FVG + Order Block dengan skor kualitas; 45% win rate, +48,7% 6 bulan | tidak jelas |
| **mt5-trade-split-manager** (86★) | `codedpro/...` | **REST API + EA** — arsitektur paling mirip War Room. Order splitting 60/10/10/10/10, trailing, safe shutdown, position recovery | MIT |
| **EA31337** (1.3k★) | `EA31337/EA31337` | Framework multi-strategi besar, filter berbasis metrik akun & volatilitas | **GPL-3.0** — hati-hati, bisa "menular" |
| **EarnForex PositionSizer** (594★) | `EarnForex/PositionSizer` | Perhitungan lot paling lengkap: komisi, swap, mata uang akun | Apache-2.0 ✅ |
| **geraked/metatrader5** (645★) | GitHub | Kumpulan strategi + grid | MIT, tapi isinya **high risk** |

---

## 4. Pola berbahaya — daftar hitam

Riset ini menemukan banyak EA XAUUSD gratis yang **tidak boleh ditiru**:

| Pola | Contoh di katalog | Kenapa berbahaya |
|---|---|---|
| **Grid dua arah** | "Bidirectional grid EA for Gold, ideal for ProCent accounts" | Menambah posisi rugi; satu tren panjang menghabiskan akun |
| **Recovery / martingale** | XANDER Gold Recovery ("Progressive Recovery System") | Lot berlipat setelah rugi — kurva ekuitas terlihat mulus sampai meledak |
| **Basket take profit** | Beberapa EA grid | Menutup basket di profit kecil, menyembunyikan posisi rugi besar |
| **Tanpa SL** | Banyak "scalper" gratis | Risiko tak terbatas; persis yang diperingatkan Order Watchdog |
| **Klaim tanpa bukti** | "SafeScalperPro v4.0 — #1 free gold scalper" | Itu copy marketing MQL5 Market, bukan hasil uji independen |

**Aturan:** kalau sebuah EA gratis punya kata *grid*, *recovery*, *martingale*, *basket*,
atau *averaging* — jangan dipelajari strateginya, cukup pelajari **kode manajemen ordernya**.

---

## 5. Yang perlu diubah pada rancangan instrumentasi kita

Berdasarkan riset, rancangan awal saya perlu empat tambahan:

| Tambahan | Alasan | Sumber |
|---|---|---|
| **Ukur latensi** (ms dari kirim sampai fill) | Slippage tanpa latensi tidak bisa didiagnosa | Article 22998 |
| **Median + p95**, bukan rata-rata | Rata-rata tertarik outlier | Article 22998 |
| **Pisahkan slippage entry vs exit** | Exit sering lebih buruk (SL kena saat spike) | Article 22998 |
| **Catat `SYMBOL_TRADE_EXECUTION`** | Menentukan apakah `deviation` berlaku | Article 1683 |

Dan satu temuan yang harus diverifikasi lebih dulu:

> **`InpSlippage = 30` mungkin tidak berfungsi** kalau XAUUSDm bertipe Market Execution.
> Kalau benar, EA kita saat ini **tidak punya batas slippage sama sekali** — hanya
> `InpMaxSpreadPts` yang menyaring spread awal, bukan fill.

---

## 6. Rekomendasi

1. **Jangan ambil kode dari mana pun.** Lisensi campur (GPL-3.0, MIT, tanpa lisensi).
   Ambil **polanya**, tulis sendiri. Kode kita sudah punya logika yang tidak ada di EA gratis
   (mode relatif, guard R:R, fail-closed).
2. **Instrumentasi dulu**, lalu bandingkan hasilnya dengan klaim backtest EA gratis.
   Banyak EA gratis mengklaim PF 1,7–1,8 dengan DD 11% — angka itu hanya bisa dibandingkan
   kalau kita punya pengukuran eksekusi sendiri.
3. **Adopsi `maxOpenRiskPct`** dari PropGuard — lebih tepat daripada menghitung jumlah posisi.
4. **Bangun pengawas terpisah** (pola Order Watchdog): EA read-only yang memantau posisi
   tanpa SL, duplikat, dan EA mati. Tidak mengubah EA utama.
5. **Verifikasi tipe eksekusi XAUUSDm** sebelum menyimpulkan apa pun soal slippage.

---

## Berkas terkait
- `~/wr_notes/RANCANGAN_INSTRUMENTASI_EA_2026-10-24.md` — rancangan awal (perlu diperbarui
  dengan 4 tambahan di atas)
- `~/wr_notes/CEK_SIMBOL_CRYPTO_EXNESS_2026-10-24.md`
