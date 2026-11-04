# Verifikasi Eksekusi XAUUSDm + Penerjemahan Aturan Harian

Tanggal: 24 Okt 2026

---

## 1. Tipe eksekusi XAUUSD — TERVERIFIKASI

Sumber: Exness Help Center, artikel Commodities (XAUUSD).

| Properti | Nilai |
|---|---|
| **Execution type** | **Market execution** (Instant execution hanya untuk akun Pro) |
| Contract size | 100 troy ounces |
| **Pip size** | **0.01** |
| Min volume | 0.01 lot |
| Max volume | 200 lot |
| Swap | Triple swap **Rabu** |
| Komisi | 3,5 USD/lot/sisi (Raw Spread), 5,5 (Zero) |

Akun demo kita `Exness-MT5Trial14` bukan Pro, jadi **Market Execution**.

### Konsekuensinya
Dokumentasi MQL5 `MqlTradeRequest`:
> `deviation` — required field for **Instant and Request Execution only**;
> Market and Exchange requests need no price or deviation.

**`InpSlippage = 30` tidak berfungsi.** Broker mengabaikannya.
EA kita saat ini **tidak punya batas slippage**.

---

## 2. Temuan lebih serius: `InpMaxSpreadPts = 350`

Dengan pip size 0.01, 350 point = **$3,50**.

Jarak SL yang terukur pada sinyal nyata: **$2,53 = 253 point**.

Artinya: EA **mengizinkan spread lebih besar daripada seluruh jarak SL**.
Entry bisa lolos saat spread $3,40 padahal SL cuma $2,53 — risiko langsung
melebihi 100% dari yang direncanakan sebelum harga bergerak sedikit pun.

Ambang yang wajar untuk XAUUSD Standard: **40–60 point ($0,40–$0,60)**.
Nilai 350 kemungkinan dinaikkan saat pasar tutup/rollover (spread terukur 240 point
pada kondisi itu) — tapi konsekuensinya terbawa ke jam normal.

---

## 3. Kabar baik: telemetri sudah mengirim spread

Payload telemetri EA (baris 199–213) sudah berisi:

```
account, broker, balance, equity, margin, free_margin, floating_pnl, positions,
total_trades_today, wins_today, losses_today, win_rate_today_pct,
net_pnl_today_usd, bid, ask, spread_pts, digits,
atr_m5, ema9_m5, ema21_m5, high_12, low_12
```

**`spread_pts` dikirim setiap poll (~1–5 detik).**

### Masalahnya
Di `routers/tencent.py`, telemetri disimpan **hanya di memori**:
```python
latest_mt5_telemetry = { ... }   # ditimpa setiap poll
```
Tidak ada histori. Jadi data spread per jam **hilang** setiap kali poll baru masuk.

### Solusi termurah
Tambahkan append ke berkas di endpoint telemetri:

```
/var/lib/warroom/telemetry_log.csv
kolom: ts, spread_pts, bid, ask, atr_m5, positions, net_pnl_today_usd
```

- **Tidak menyentuh EA sama sekali**
- Tidak perlu compile, tidak perlu deploy ke VM
- Perubahan server ~10 baris, mudah dibatalkan
- Data langsung terkumpul sejak pasar buka Senin

Dengan data ini, jendela likuiditas XAUUSD ditentukan **dari pengukuran sendiri**,
bukan dari jam crypto atau teori sesi.

---

## 4. Penerjemahan aturan harian ke parameter EA

Aturan yang diminta:
- **1–5 trade per hari** (kualitas di atas kuantitas)
- **Stop harian di −$30**

### Kondisi sekarang
| Parameter | Nilai sekarang |
|---|---|
| `InpDailyMaxLoss` | $25 |
| `InpDailyTargetLock` | $40 |
| `InpDailyFloorLock` | $30 |
| `InpMaxTradesPerDay` | **tidak ada** |
| `InpFixedLot` di VM | 0.05 (0.10 di repo) |

### Hitungan penting

XAUUSD, contract 100 oz:
- **0,10 lot** → pergerakan $1 = **$10**
- **0,05 lot** → pergerakan $1 = **$5**

Dengan SL $2,53:
| Lot | Risiko per trade | Arti stop −$30 |
|---|---|---|
| 0,10 | **$25,30** | **1,2 SL** → satu loss hampir menutup hari |
| 0,05 | **$12,65** | **2,4 SL** → wajar |

**Kesimpulan:** stop −$30 hanya masuk akal dengan **lot 0,05**.
Kalau lot tetap 0,10, stop −$30 berarti EA berhenti setelah **satu** trade rugi —
tidak sesuai dengan target 1–5 trade/hari.

Pilihan:
- **A. Lot 0,05 + stop −$30** → 2–3 loss per hari masih tertampung ✅ disarankan
- **B. Lot 0,10 + stop −$50** → setara 2 SL
- **C. Lot 0,10 + stop −$30** → hanya 1 SL, sisanya harus menang

### Parameter yang perlu ditambah
| Input baru | Nilai usul | Alasan |
|---|---|---|
| `InpMaxTradesPerDay` | 5 | batas atas sesuai catatan |
| `InpMinTradesBeforeStop` | — | tidak perlu; biarkan alami |
| `InpMaxSpreadPts` | **60** (dari 350) | spread tidak boleh > 24% jarak SL |
| `InpDailyMaxLoss` | **30** (dari 25) | sesuai permintaan |

---

## 5. Soal klaim "modal $100 jadi $1.000+ dalam sebulan"

Perlu dipisahkan dua hal:

**Yang layak ditiru: disiplinnya.**
Batas trade per hari + stop harian memang terbukti membantu. Data crypto kita
mendukung: win rate turun dari 68% (0–3 posisi) ke 44% (7–9 posisi).

**Yang tidak layak dijadikan target: angkanya.**
$100 → $1.000+ = **10x dalam <30 hari**. Dengan aturan 1–5 trade/hari dan stop ketat,
itu **mustahil secara aritmetika** kecuali risiko per trade sangat besar (20–50% akun),
yang justru bertentangan dengan aturan ketat yang sama.

Kemungkinan besar: leverage ekstrem, martingale, atau keberuntungan satu kali.
Orang yang rugi tidak memposting — ini survivorship bias klasik.

**Saran:** jangan pakai angka itu sebagai target. Pakai aturannya, bukan hasilnya.
Target yang sehat untuk demo $500: **+2–5% per bulan** dengan drawdown <10%.

---

## 6. Urutan tindakan

| # | Tindakan | Menyentuh EA? | Status |
|---|---|---|---|
| 1 | Simpan telemetri ke CSV (server) | ❌ tidak | menunggu izin |
| 2 | Kumpulkan spread per jam sampai pasar buka Senin | ❌ tidak | — |
| 3 | Turunkan `InpMaxSpreadPts` 350 → 60 | ✅ ya | setelah data |
| 4 | Tambah `InpMaxTradesPerDay = 5` | ✅ ya | setelah data |
| 5 | `InpDailyMaxLoss` 25 → 30 (+ lot 0,05) | ✅ ya | setelah data |
| 6 | Instrumentasi fill (requested vs filled, latensi) | ✅ ya | fase 2 |
