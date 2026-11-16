# Riset A/B Strategi 2 Akun Demo Exness Standard USD ($1.000)

**Tanggal:** 16 November 2026
**Modul Simulator:** `packages/live-trading/src/live_trading/demo_ab_backtest.py`
**Tes Unit:** `packages/live-trading/tests/test_demo_ab_backtest.py` (4 passed)

## 1. Konteks Akun
- **Akun Live Real:** `#452009427` — Exness Real Cent (`USC`, saldo `1.084,84 USC` / `$10,85`).
- **Akun Demo 1 (`#434446792`):** Exness Demo **Standard USD** (`$1.005,00`, akun biasa bukan Cent).
- **Akun Demo 2 (`#464202979`):** Exness Demo **Standard USD** (`$1.000,00`, akun biasa bukan Cent).

Pada akun Standard USD (`1 lot = 100 oz`), **`0,01 lot XAUUSD = $1 per $1 gerak harga`**.

## 2. Hasil Simulasi Empiris ($1.000, Spread $0,30/oz, Hari Kerja Saja, SL-Dulu)

### A. Proxy Multi-Tahun `PAXGUSDT_15m.csv` (2021-01-01 s.d. 2026-11-02 · 146.027 bar)
| Metode | Final Ekuitas | Return % | Trade | Win % | PF | Max DD % | Status |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `martingale_2x` (grid `$6`, lot `2x`, tanpa SL) | `$150,00` | `-85,00%` | `1.832` | `99,95%` | `0,93` | `105,32%` | **BLOWUP (MC)** |
| `bounded_avg_counter` (counter-trend RSI, SL `-$60`) | `$108,00` | `-89,20%` | `883` | `86,75%` | `0,87` | `92,78%` | **BLOWUP (MC)** |
| `trend_twin_order` (M15 breakout + Twin `0.01+0.01`) | `$149,26` | `-85,07%` | `263` | `42,59%` | `0,53` | `88,26%` | **BLOWUP** *(mikrostruktur PAXG ≠ XAUUSDm M5)* |
| **`trend_bounded_avg`** (`EMA200` + pullback RSI, flat `0.01`, step `max($15, 2.2×ATR)`, maks 4 layer, TP `+$12` / **Hard SL `-$45`**) | **`$1.138,00`** | **`+13,80%`** | **`154`** | **`80,52%`** | **`1,10`** | **`24,28%`** | **SURVIVAL & PROFIT** |

### B. Data XAUUSD Aktual 30 Hari `XAUUSD_15m.csv` (2026-09-21 s.d. 2026-10-21 · 1.990 bar)
| Metode | Final Ekuitas | Return % | Trade | Win % | PF | Max DD % | Status |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `martingale_2x` | `$150,00` | `-79,51%` / MC | `62` | `98,39%` | `0,30` | `126,39%` | **BLOWUP (MC)** (`-$1.216` dalam 1 tren 6 layer) |
| `bounded_avg_counter` | `$800,00` | `-20,00%` | `26` | `76,92%` | `0,44` | `30,00%` | Negatif |
| **`trend_twin_order`** | **`$1.007,44`** | **`+0,74%`** | **`18`** | **`55,56%`** | **`1,06`** | **`10,15%`** | **Positif** |
| **`trend_bounded_avg`** | **`$1.036,00`** | **`+3,60%`** | **`3`** | **`100,00%`** | **`99,00`** | **`3,54%`** | **Positif** |

*(Catatan tambahan dari uji terpisah: menambahkan pyramiding layer tambahan pada XAUUSD justru menurunkan PF `trend_twin_order` karena whipsaw mengenai SL sebelum tren berlanjut — lihat `docs/backtest-reaper-1k-20261030.md` sebagai pembanding MT5 Strategy Tester `XAUUSDm M5` `+13,48% / 3 thn, PF 1,13, DD 9,41%`).*

## 3. Artefak Implementasi MT5 (`ops/mt5/`)
1. **Demo-1 (`#434446792`) — Trend Twin-Order Layering:**
   - Source: `ops/mt5/WarRoom_DemoA_TwinLayering.mq5`
   - Preset: `ops/mt5/Demo1_434446792_TwinLayering.set` (Magic `434446`, `0.01 + 0.01`, BE Lock saat Scalp TP, ATR Trailing, Daily Max Loss `$30`)
2. **Demo-2 (`#464202979`) — Trend-Filtered Bounded Averaging:**
   - Source: `ops/mt5/WarRoom_DemoB_TrendBoundedAvg.mq5`
   - Preset: `ops/mt5/Demo2_464202979_TrendBoundedAvg.set` (Magic `464202`, Flat `0.01`, `EMA200` + `RSI`, spacing `max($15, 2.2×ATR)`, maks 4 layer, TP `+$12`, **Hard Basket SL `-$45`**)

Keduanya sudah membawa integrasi telemetri (`POST /api/v1/tencent/mt5/telemetry` & `/deal`). Saat memasang di chart MT5 `XAUUSD` TF `M15`, isi input `InpToken` dengan token EA (`WARROOM_EA_SYNC_TOKEN`) dan izinkan URL `https://0xgunsl1ng3r.xyz` pada *Tools → Options → Expert Advisors*.
