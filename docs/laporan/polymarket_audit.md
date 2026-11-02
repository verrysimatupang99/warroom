# Laporan Audit: Peluang Mispricing Odds Pasar Biner Polymarket & Integritas Codebase

**Tanggal Audit:** 2026-10-23T04:58:00Z  
**Domain:** Prediction & Binary Options Markets (Polymarket CLOB & Local Collectors)  
**Workspace:** `/home/admin/warroom-agents/polymarket`  
**Agen Pemeriksa:** Polymarket Event Specialist  
**Status Audit:** Komprehensif Selesai · Terverifikasi Empiris & Unit Test

---

## 1. Executive Summary

Audit teknis dan kuantitatif pada pasar biner Polymarket serta modul pendukungnya di workspace `/home/admin/warroom-agents/polymarket` mencakup dua mandat utama:

1. **Audit Peluang Mispricing Odds pada Pasar Biner Polymarket:**
   - Evaluasi matematis struktur payoff biner, probabilitas tersirat (*implied probability*), dan *Break-Even Win Rate* ($\text{BE-WR}$).
   - Verifikasi langsung hasil *live verdict* empiris QA (`/opt/polymarket/current/qa/favorite-live-verdict.py --json`): $n=4133$, wins=$3234$ (Win Rate **78.25%**), ask rata-rata $0.7666$, $\text{BE-WR} = 76.66\%$, EV per stake $+2.07\%$, $d_{\text{eff}} = 1.342$, $\rho = 0.408$, $n_{\text{eff}} = 3080$, $N_{\text{needed}} = 7392$, status operasional `EDGE`.
   - Evaluasi disparitas performa eksekusi *paper mirror*:
     - **Arm B Kandidat** (`/var/lib/poly-paper-candidate`): $n=445$, wins=$364$ (Win Rate **81.80%**), PnL **$-6.4032$ USD** ($-6.40\%$) dari modal 100 USD. Menunjukkan paradoks nyata di mana Win Rate $\approx 81.8\%$ tetap merugi karena *loss full stake* ($-1.0\times$) melampaui rasio keuntungan pada ask tinggi ($0.70\text{--}0.95$) ditambah friksi fee taker (`receipt`).
     - **Arm D Favorit** (`/var/lib/poly-paper-favorite`): $n=11$, wins=$6$ (Win Rate **54.55%**), PnL **$-15.48$ USD** dari modal 20 USD.
2. **Audit Integritas Codebase Workspace:**
   - **Modul Radar ([`radar.py`](file:///home/admin/warroom-agents/polymarket/packages/live-trading/src/live_trading/collectors/radar.py)):** Verifikasi transisi arsitektur radar rantai dari Azure VM (`20.212.52.5`, dipensiunkan sejak 6 Okt 2026) menjadi eksekutor lokal Webdock. Memantau metrik likuiditas dan volume DEX publik via `gmgn-cli`. Lolos 7 unit test (`test_radar.py`) dan 100% ruff clean.
   - **Modul Dompet ([`dompet.py`](file:///home/admin/warroom-agents/polymarket/packages/live-trading/src/live_trading/dompet.py)):** Verifikasi integrasi `_dompet_polymarket` terhadap virtual paper balance Rp 10.000.000 secara proporsional dari shadow summary Arm B. Memenuhi aturan proteksi kurs offline (`kurs is None` $\implies$ `"tersedia": false`), lolos 7 unit test (`test_dompet.py`), 2 invarian test (`test_dompet_invariant.py`), dan ruff clean.
3. **Kepatuhan Terhadap Garis Batas Platform (AGENTS.md):**
   - Direktori `/opt/polymarket` diperlakukan sebagai **baca-saja** (hanya menjalankan tool allowlist `favorite-live-verdict.py`).
   - Tidak ada modifikasi atau intervensi pada live gate `/etc/poly-pilot/activation-approved`.
   - Tidak ada kredensial atau private key yang ditulis ke dalam berkas atau log.

---

## 2. Analisis Kuantitatif Mispricing Odds Pasar Biner

### 2.1 Teori Payoff Biner & Ambang Batas Impas ($\text{BE-WR}$)

Pada instrumen biner Polymarket (seperti event 5-minute Up/Down), satu unit share yang menang bernilai $1.00$ USDC:
- Apabila membeli pada harga ask $p \in (0, 1)$ dengan ukuran modal $S$:
  - **Kondisi Menang:** Payout $= S/p$, menghasilkan laba bersih:
    $$\Delta_{\text{win}} = S \cdot \left(\frac{1 - p}{p}\right)$$
  - **Kondisi Kalah:** Payout $= 0$, menghasilkan kerugian:
    $$\Delta_{\text{loss}} = -S$$
- **Nilai Harapan ($\mathbb{E}[\text{PnL}]$) & Break-Even Win Rate:**
  $$\mathbb{E}[\text{PnL}] = \text{WR} \cdot \left(S \frac{1 - p}{p}\right) - (1 - \text{WR}) \cdot S = 0 \iff \text{BE-WR} = p$$
- **Dampak Biaya Transaksi (`feeMode: receipt`):**
  Polymarket membebankan taker fee pada fills CLOB. Biaya ini menggeser ambang batas impas ke atas:
  $$\text{BE-WR}_{\text{net}} = \frac{p + \text{fee}}{1 + \text{fee}} > p$$
  Pada band favorit $0.70\text{--}0.95$ (rata-rata ask $\approx 0.77\text{--}0.82$):
  - Entry $0.75 \implies \text{Reward} = +0.333\times \text{stake} \implies \text{BE-WR} = 75.0\%$
  - Entry $0.82 \implies \text{Reward} = +0.220\times \text{stake} \implies \text{BE-WR} = 82.5\%$
  - Entry $0.90 \implies \text{Reward} = +0.111\times \text{stake} \implies \text{BE-WR} = 90.0\%$

### 2.2 Uji Empiris Live Verdict QA (`favorite-live-verdict.py`)

Pengujian empiris langsung pada allowlist sudo mengembalikan metrik berikut:

```json
{
  "coins": ["btc", "eth"],
  "windows": 5125,
  "n": 4133,
  "wins": 3234,
  "winRate": 78.25,
  "ask": 0.7666,
  "breakEven": 76.66,
  "evPerStake": 2.07,
  "ci95": [76.75, 79.67],
  "deff": 1.342,
  "rho": 0.408,
  "nEff": 3080,
  "verdict": "EDGE",
  "nNeeded": 7392
}
```

| Metrik | Nilai | Evaluasi Teknis |
|---|---|---|
| **Total Windows Terpantau** | 5,125 | Populasi jendela pasar biner 5m BTC & ETH |
| **Trade Memenuhi Syarat ($n$)** | 4,133 | Sampel eksekusi yang lolos filter likuiditas dan ask band |
| **Menang / Kalah** | 3,234 / 899 | Win rate aktual **78.25%** |
| **Rata-rata Ask** | 0.7666 | Ambang breakeven teoritis $76.66\%$ |
| **EV per Stake** | **+2.07%** | Terdapat *edge* bruto tipis sebelum friksi slippage mikro |
| **95% Confidence Interval** | [76.75%, 79.67%] | Batas bawah CI ($76.75\%$) berada sedikit di atas BE ($76.66\%$) |
| **Design Effect ($d_{\text{eff}}$)** | 1.342 | Faktor koreksi autokorelasi serial intrawindow ($\rho = 0.408$) |
| **Sampel Efektif ($n_{\text{eff}}$)** | 3,080 | Ukuran sampel independen aktual setelah disesuaikan kluster |
| **Sampel Wajib ($N_{\text{needed}}$)** | 7,392 | Jumlah sampel yang dibutuhkan untuk verifikasi holdout definitif |

### 2.3 Evaluasi Paradoks Paper Shadow Execution (Arm B vs D)

Data aktual per 23 Oktober 2026:

#### A. Arm B Kandidat (`/var/lib/poly-paper-candidate/execution-paper-shadow-summary.json`)
- **Konfigurasi:** Band $0.70\text{--}0.95$, `sideMode: ahead`, `decideWindowSeconds: 45-240`, `budget: 5`, `feeMode: receipt`.
- **Hasil:**
  - $n = 445$ trade ($364$ Wins / $81$ Losses).
  - **Win Rate:** **81.80%**.
  - **PnL:** **$-6.4032$ USD** (Modal 100 USD $\to$ Saldo akhir $93.60$ USD, $-6.40\%$).
  - **Fees Reserved:** $26.86$ USD.
  - **Skips Breakdown:** `outside_price_band`: 13,506; `outside_window`: 13,430; `loss_budget`: 12,921; `empty_book`: 6,575; `insufficient_depth`: 5,656.

#### B. Arm D Favorit (`/var/lib/poly-paper-favorite/execution-paper-shadow-summary.json`)
- **Konfigurasi:** Band $0.70\text{--}0.95$, `sideMode: ahead`, `decideWindowSeconds: 45-119` (jendela lebih selektif), `budget: 5`.
- **Hasil:**
  - $n = 11$ trade ($6$ Wins / $5$ Losses).
  - **Win Rate:** **54.55%**.
  - **PnL:** **$-15.4796$ USD** (Modal 20 USD $\to$ Saldo akhir $4.52$ USD).
  - **Skips Breakdown:** `insufficient_balance`: 2,069 (terhenti karena draw-down modal kecil).

#### C. Mengapa Win Rate 81.80% Tetap Merugi?
1. **Asimetri Rasio Keuntungan-Kerugian:**
   Pada ask rata-rata $0.82$, payout kemenangan hanya $+0.22\times \text{stake}$, sedangkan kekalahan menghilangkan $-1.00\times \text{stake}$. Rasio payoff adalah $1 : 0.22$. Untuk menutup 1 kekalahan, diperlukan minimal 5 kemenangan berturut-turut.
2. **Friksi Fee Taker:**
   Biaya *receipt taker fee* di CLOB Polymarket membebani saldo sekitar $\approx 1\text{--}2$ sen per trade ($26.86$ USD pada Arm B), menaikkan BE-WR efektif melampaui $82.5\%$.
3. **Efek Jendela Eksekusi:**
   Arm B menggunakan jendela lebar (45–240 detik). Pada detik 150–240, harga ask favorit sering kali sudah mencapai batas atas band ($0.88\text{--}0.94$), memberikan margin reward sangat minim dengan eksposur pembalikan arah menit terakhir (*reversal risk*).

---

## 3. Audit Integritas Codebase

### 3.1 Modul [`radar.py`](file:///home/admin/warroom-agents/polymarket/packages/live-trading/src/live_trading/collectors/radar.py)
- **Path:** `packages/live-trading/src/live_trading/collectors/radar.py`
- **Fungsi:** Mengambil data trending dan gas price dari feed pasar publik via `gmgn-cli` untuk rantai `robinhood,arc,hyperevm,stable,base`.
- **Status Migrasi:** Mengonfirmasi penonaktifan total SSH ke Azure (`20.212.52.5`) sejak 6 Okt 2026. Seluruh proses pengumpulan radar dijalankan lokal di host Webdock (`state/radar_state.json`).
- **Verifikasi Integritas & Kepatuhan:**
  - Bersifat *read-only* murni, tidak memerlukan private key, wallet, atau posting order.
  - Penanganan error jaringan dan limit rate API dilakukan secara non-blokir (`_run` dengan backoff dan safe fallback).
  - **Uji Unit:** Suite [`packages/live-trading/tests/test_radar.py`](file:///home/admin/warroom-agents/polymarket/packages/live-trading/tests/test_radar.py) lulus 100% (7 passed).
  - **Linter:** `ruff check packages/live-trading/src/live_trading/collectors/radar.py` lulus tanpa peringatan.

### 3.2 Modul [`dompet.py`](file:///home/admin/warroom-agents/polymarket/packages/live-trading/src/live_trading/dompet.py) (`_dompet_polymarket`)
- **Path:** `packages/live-trading/src/live_trading/dompet.py`
- **Fungsi:** Mengintegrasikan neraca paper dompet Rp 10.000.000 untuk pasar Polymarket berdasarkan arm aktif (Arm B Kandidat).
- **Aturan Arsitektur:**
  - Persentase PnL diambil apa adanya dari berkas ringkasan shadow `/var/lib/poly-paper-candidate/execution-paper-shadow-summary.json` tanpa penulisan balik ke state eksekusi (menghilangkan *state drift*).
  - Mematuhi Garis Batas #5: Ketika kurs USD $\to$ IDR tidak tersedia (koneksi offline), sistem mengembalikan `tersedia: False` dengan alasan `"kurs USD→IDR tidak tersedia"`, tanpa mengarang angka nol atau saldo fiktif.
  - Simulasi dengan kurs acuan Rp 16.000 menghasilkan saldo akhir USD 584.98 dengan PnL $-6.403\%$, mencerminkan performa Arm B secara proporsional.
- **Verifikasi Integritas:**
  - **Uji Unit:** Suite [`packages/live-trading/tests/test_dompet.py`](file:///home/admin/warroom-agents/polymarket/packages/live-trading/tests/test_dompet.py) lulus 100% (7 passed).
  - **Uji Invarian:** Suite [`packages/live-trading/tests/test_dompet_invariant.py`](file:///home/admin/warroom-agents/polymarket/packages/live-trading/tests/test_dompet_invariant.py) lulus 100% (2 passed).
  - **Linter:** `ruff check packages/live-trading/src/live_trading/dompet.py` lulus tanpa peringatan.

---

## 4. Rekomendasi Taktikal & Strategis

1. **Eksplorasi Mid-Band Odds (0.55–0.72):**
   Alih-alih bersaing pada ask band mahal ($0.70\text{--}0.95$) yang memiliki ambang impas sangat tinggi ($>82.5\%$), rekomendasikan riset eksplorasi pada kisaran harga $0.55\text{--}0.72$. Pada kisaran ini, payout rasio jauh lebih simetris ($+0.39\times$ hingga $+0.81\times$) dengan BE-WR yang lebih toleran terhadap friksi fee.
2. **Kalkulasi EV Real-Time Pasca-Fee:**
   Tambahkan evaluasi fee rate dinamis sebelum order virtual dipasang:
   $$\text{Expected Net Profit} = p_{\text{pred}} \cdot (1 - \text{ask} - \text{fee}) - (1 - p_{\text{pred}}) \cdot (\text{ask} + \text{fee})$$
   Abaikan entri jika perkiraan *Net EV* $\le +2.5\%$.
3. **Akumulasi Sampel Replay Menuju $N = 7,392$:**
   Pertahankan pencatatan paper shadow hingga batas sampel efektif terpenuhi guna memastikan ketahanan statistik sebelum mempertimbangkan usulan perubahan kebijakan gate ke pemilik (*owner*).
4. **Isolasi Lingkungan Live:**
   Tetap pertahankan status gerbang live `/etc/poly-pilot/activation-approved` tidak tersentuh. Seluruh pengujian wajib tetap berjalan dalam mode `paper-mirror`.
