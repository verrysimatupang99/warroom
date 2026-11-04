# Riset: sumber harga & ATR untuk XAUUSD (24 Okt 2026)

Status: **riset saja — tidak ada kode yang diubah.**
Pertanyaan: setelah R4 (jarak relatif), apakah ATR dari `GC=F` masih layak, atau
harus diganti sumber spot/broker?

---

## 1. Bukti: harga spot vs futures vs broker

Diukur bersamaan (Sabtu, pasar tutup):

| Sumber | Harga | Selisih vs MT5 bid |
|---|---|---|
| MT5 XAUUSDm (broker) | 3996,057 | — |
| xaus.com spot XAU | **3996,90** | **+0,84** |
| Yahoo `GC=F` (futures) | 4007,90 | **+11,84** |

Kesimpulan kuat: untuk **level harga**, spot benar dan futures salah. Ini
memperkuat keputusan R4 (jarak relatif) dan menunjukkan bahwa bila kelak level
absolut dipakai lagi, sumbernya harus spot/broker, bukan `GC=F`.

## 2. Apakah Yahoo punya spot XAU?

| Simbol | Hasil |
|---|---|
| `GC=F` | 200 (futures) |
| `XAUUSD=X` | **404** |
| `XAU=X` | **404** |
| `XAUUSD` | **404** |
| `GLD` | 200 (ETF, bukan spot 1:1) |

Yahoo **tidak menyediakan** spot XAUUSD. Jadi mengganti `SYMBOL_MAP` saja tidak cukup.

## 3. Kandidat sumber spot (gratis, tanpa key)

| Layanan | Endpoint | Isi | Batasan |
|---|---|---|---|
| xaus.com | `/api/v1/spot` | spot XAU + perak + rasio | cache 60 s, "indicative", **bukan quote tradable** |
| xaus.com | `/api/v1/intraday` | **24 jam titik 5 menit**, hanya `{t, p}` | **tanpa high/low** |
| xaus.com | `/api/v1/history` | harian OHLC sejak 2021 | tidak untuk M5 |
| api.gold-api.com | `/price/XAU` | spot saja | tanpa OHLC |

Implikasi penting: **tidak ada OHLC 5 menit** dari sumber gratis ini. ATR sejati
butuh high/low. Yang tersedia hanya close → ATR tidak bisa dihitung murni.

## 4. Percobaan mengukur beda volatilitas — TIDAK KONKLUSIF

Pengukuran dilakukan saat pasar tutup:

```
ATR14 GC=F (true range)      : 2.371
ATR14 xaus (proxy close-only): 0.371   <- bukan pembanding setara
MAD close GC=F               : 1.164
MAD close xaus               : 0.371   <- rasio 0.32, mencurigakan
bar/titik                    : GC=F 204 | xaus 154
```

Angka ini **tidak boleh dipakai mengambil keputusan**: pasar tutup, sehingga
sebagian besar titik adalah harga beku dan jumlah bar tidak lengkap. Perbandingan
volatilitas yang sah harus diulang **saat pasar buka**.

Yang bisa disimpulkan sekarang hanya: **level harga** spot benar (bagian 1),
sedangkan **skala volatilitas** belum terbukti berbeda atau sama.

## 5. Tiga opsi

### Opsi A — EA mengirim snapshot broker (rekomendasi)
EA menambah field ke telemetri yang sudah ada:
```
bid, ask, spread_pts, digits,
atr_m5   (iATR handle M5, 14),
ema9_m5, ema21_m5 (iMA),
high_12, low_12  (dari 12 bar M5 terakhir)
```
API memakai snapshot itu selama umurnya < N detik; bila basi → jatuh ke perilaku
sekarang (fail-closed/Laya). 

- (+) Instrumen **persis** yang dieksekusi; tidak ada selisih futures/spot
- (+) Tanpa dependensi pihak ketiga baru
- (+) ATR sejati (high/low tersedia di MT5)
- (−) Perlu ubah EA + compile + reload (prosedur yang sudah terbukti lancar)
- (−) Bila EA mati, API kehilangan sumber (harus ada fallback eksplisit)

### Opsi B — xaus untuk harga + close untuk EMA/ATR-proxy
- (+) Tanpa ubah EA; bisa dipakai sekarang
- (−) **Tanpa high/low** → ATR hanya bisa didekati, bukan ATR sejati
- (−) Dependensi jaringan baru; cache 60 s; status "indicative"
- (−) Perlu cek `price_as_of` untuk staleness

### Opsi C — biarkan `GC=F` untuk ATR
- (+) Nol perubahan
- (−) Volatilitas instrumen berbeda (belum terukur dengan benar)
- (−) Risiko: jarak SL bisa terlalu sempit/lebar relatif ke broker

## 6. Rekomendasi

**Opsi A**, dikerjakan bertahap:
1. Tambah field broker ke telemetri EA (tanpa mengubah logika keputusan).
2. Verifikasi nilainya cocok dengan MT5 (bandingkan bid EA vs log EA).
3. Baru setelah data cocok, API memakai ATR broker untuk menghitung `risk`/`reward`.
4. `GC=F` tetap sebagai fallback bila telemetri basi.

Sebelum itu, **ukur dulu saat pasar buka (Senin)**: bandingkan ATR14 GC=F dengan
ATR14 broker. Kalau selisihnya < ~10%, prioritasnya turun dan R-berikutnya bisa
dialihkan ke hal lain.

## 7. Catatan tambahan
- xaus menyatakan harganya "indicative mid-market, **not tradable quotes**" —
  layak untuk sinyal, tidak layak untuk settlement/klaim eksekusi.
- MT5 di VM membuka MCP di `127.0.0.1:22346` (terlihat di log). Itu jalur
  alternatif untuk membaca data broker langsung, tetapi butuh tunnel dari server
  ini ke VM Azure — lebih rumit dan menambah permukaan risiko dibanding Opsi A.
