# Roadmap Peningkatan Terarah War Room (Q4 2026)

Dokumen ini memetakan inisiatif dan rencana peningkatan strategis untuk War Room, mengintegrasikan kapabilitas **Oyenza Trade**, **1001 Startup**, kesiapan prop firm (**Global4Ex / Goat Funded Trader**), dan orkestrasi bot multi-market.

---

## 1. Integrasi Prop Firm & Eksekusi Akun $5,000 (Global4Ex / GFT)
*Prioritas: TINGGI (Dukungan langsung target trading manual/semi-otomatis pengguna)*

- [ ] **Prop Firm Rule Enforcement Engine (Dashboard Guard):**
  - Monitor batas **Daily Loss (5% = $250)** dan **Max Trailing Drawdown (8% - 10% = $400 - $500)** secara real-time.
  - Pasang peringatan suara / visual merah berkedip di header War Room jika saldo akun mendekati -3% dalam sehari.
- [ ] **Modul Sizing Otomatis 0.10 Lot XAUUSD:**
  - Tambahkan kalkulator "One-Click Lot Calculator" di tab `Sinyal & Setup` Forex: langsung menghitung SL dalam pips, target profit $ (USD), dan risiko $ per trade untuk modal $5K.
- [ ] **Jembatan Notifikasi Telegram Khusus Eksekusi Mobile:**
  - Format pesan sinyal Telegram bot diperkaya dengan tombol salin cepat:
    `PAIR | SIDE | ENTRY | SL | TP1 | TP2 | LOT SIZE` agar mempermudah entri manual di TradeLocker / MT5 mobile tanpa risiko ban IP VPS.

---

## 2. Peningkatan Fitur Adopsi Model Oyenza (oyenza.trade)
*Prioritas: TINGGI (Kematangan Tooling & Visualisasi)*

- [ ] **Interactive Institutional Flow Map (Oyenza Style):**
  - Dashboard visualisasi Bubble Matrix atau Sankey Diagram untuk perpindahan likuiditas: Stablecoin -> BTC -> Large Cap -> Altcoins / Memecoins.
- [ ] **Multi-Market Unified Screener Filter:**
  - Tab filter dinamis: Pengguna dapat menyaring seluruh market berdasarkan kriteria universal (Volume Spike > 3x, RSI Divergence, Break & Retest Valid, Smart Money Accumulation).
- [ ] **Economic & Earnings Calendar Alert System:**
  - Hitung mundur rilis berita makro penting (CPI, NFP, Fed Rate Decision) dengan tombol *Auto-Stand Down* (rekomendasi tidak membuka posisi 30 menit sebelum dan sesudah rilis).

---

## 3. Peningkatan Data & Transparansi Model 1001Startup (1001startup.id)
*Prioritas: MENENGAH (Provenance & Validasi Komunitas)*

- [ ] **Public Proof-of-Execution Page / Audit Tracker:**
  - Halaman portofolio publik transparan yang menampilkan seluruh trade closed (tanpa membocorkan proprietary secret), mencantumkan timestamp, bukti hash data, dan rasio R murni.
- [ ] **Data Source Health & Latency Dashboard:**
  - Panel terpusat yang memantau uptime API (Binance, OKX, GoAPI IDX, TradingView TVC, DexScreener, Pyth Network, Polymarket CLOB).

---

## 4. Automasi Multi-Market Signal Broadcaster
*Prioritas: MENENGAH (Ekspansi Signal Engine)*

- [ ] **Cron Automasi Notifikasi Telegram Lintas Pasar:**
  - Menjalankan script `scripts/notify_all_markets_signal.py` setiap 15 menit melalui timer systemd, memfilter sinyal dengan skor konfluensi tertinggi untuk disiarkan ke Telegram.
- [ ] **Machine Learning Confluence Weighting:**
  - Integrasi evaluasi dinamis: bobot sinyal disesuaikan secara otomatis berdasarkan performa 30 hari terakhir dari masing-masing strategi.
