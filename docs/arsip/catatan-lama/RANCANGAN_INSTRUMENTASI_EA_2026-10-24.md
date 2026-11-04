# Rancangan Instrumentasi EA MT5 (desain saja — belum ada perubahan kode)

Tanggal: 24 Okt 2026
Status: **usulan untuk direview**. Tidak ada berkas EA yang diubah.

---

## 1. Tujuan

Mengukur slippage nyata per trade supaya analisa yang sama seperti data crypto
(bab: slippage −1,12 R, kepadatan posisi, jam entry) bisa dilakukan pada XAUUSD —
dengan **data gold sendiri**, bukan mengimpor kesimpulan crypto.

Saat ini EA tidak pernah membandingkan **harga yang diminta** dengan **harga yang didapat**.
Tanpa itu, slippage tidak terlihat.

---

## 2. Titik sisip di kode (2 tempat, tidak menyentuh logika trading)

### Titik A — setelah order berhasil
Lokasi saat ini: sekitar baris 827 (`trade.Buy(...)`) dan pasangan `trade.Sell(...)`.

Yang diambil saat itu juga:
| Field | Sumber MQL5 |
|---|---|
| `price_requested` | `ask` / `bid` yang dipakai saat kirim |
| `price_filled` | `trade.ResultPrice()` |
| `spread_pts` | `SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)` |
| `slippage_pts` | `(price_filled - price_requested) / _Point`, dibalik tandanya untuk SELL |
| `open_positions` | hitung `PositionsTotal()` dengan magic + `_Symbol` **sebelum** order |
| `sl_dist_pts`, `tp_dist_pts` | `(entry - sl) / _Point` |
| `risk_usd` | `sl_dist / tickSize * tickValue * lot` |
| `equity`, `balance` | `AccountInfoDouble` |
| `server_time`, `wib_time` | `TimeCurrent()` + offset |

### Titik B — saat posisi tertutup
Lokasi saat ini: handler yang sudah ada (sekitar baris 150 dan 347).

| Field | Sumber |
|---|---|
| `exit_price` | `HistoryDealGetDouble(ticket, DEAL_PRICE)` |
| `profit` | `DEAL_PROFIT` + `DEAL_SWAP` + `DEAL_COMMISSION` |
| `exit_reason` | SL / TP / partial / BE / trail / manual — disimpulkan dari `DEAL_REASON` |
| `duration_sec` | `exit_time - open_time` |
| `r_realized` | `profit / risk_usd` (risiko disimpan saat buka) |

---

## 3. Penyimpanan

**Dua jalur, sengaja redundan:**

1. **CSV lokal** — `MQL5/Files/warroom_trades.csv`, ditulis append saat trade tutup.
   Aman kalau API mati; bisa diambil lewat run-command Azure.
2. **API** — kirim ke endpoint telemetry yang sudah ada (`/api/v1/tencent/mt5/telemetry`)
   atau endpoint baru `/api/v1/tencent/mt5/trade-log`. Server menyimpan ke
   `/var/lib/warroom/trades_ea.csv`.

Format satu baris (CSV, header tetap):
```
ticket,symbol,side,open_time,close_time,duration_sec,spread_pts,
price_requested,price_filled,slippage_pts,sl_dist_pts,tp_dist_pts,
lot,risk_usd,open_positions,equity,exit_price,exit_reason,profit,r_realized
```

---

## 4. Yang TIDAK diubah

- Logika sinyal, R:R guard, drift check, dedupe sinyal
- Lot, SL/TP, partial TP, BE, trailing, daily ratchet
- Spread filter `InpMaxSpreadPts`
- Tidak ada input parameter baru yang wajib diisi

Instrumentasi murni **membaca dan mencatat**. Kalau logging gagal, trading tetap jalan
(tulis dibungkus try/catch gaya MQL5: cek `FileWrite` return, jangan `return` dari handler).

---

## 5. Analisa setelah data terkumpul (2–4 minggu)

Skrip Python yang sama seperti analisa crypto, dengan kolom pengganti:

| Analisa crypto | Padanan di EA |
|---|---|
| Rata-rata R per jam | `slippage_pts` dan `r_realized` per jam server |
| Kepadatan posisi | `open_positions` vs `slippage_pts` |
| Laju R < −1,0 | `r_realized < -1.0` |
| Jendela likuiditas | jam dengan spread & slippage terendah |

Keluaran yang dicari: **jam mana XAUUSD paling murah dieksekusi**, dan
**berapa posisi bersamaan yang mulai merusak fill**.

---

## 6. Urutan kerja yang diusulkan

| Tahap | Isi | Risiko |
|---|---|---|
| 1 | Tambah logging (Titik A + B) + CSV lokal | Nol — tidak mengubah perilaku |
| 2 | Kumpulkan 2–4 minggu (pasar buka Senin) | Nol |
| 3 | Analisa: slippage per jam / spread / kepadatan | Nol |
| 4 | Baru putuskan guard: filter jam, batas posisi, ketatkan spread | Perlu review terpisah |

---

## 7. Catatan penting

- Pasar XAUUSD tutup sampai Senin 05:00 WIB — data baru tidak ada sebelum itu.
- Sampel minimal yang layak: **30–50 trade tertutup**. Dengan frekuensi EA sekarang,
  itu bisa 2–4 minggu.
- `InpSlippage = 30` pts pada SL $2,53 setara **11,9%** — berdekatan dengan slippage
  crypto 12%. Ini yang mau dibuktikan atau dibantah dengan data.
