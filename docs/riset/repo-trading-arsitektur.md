# Arsitektur Repo Trading Bot — Riset & Pelajaran untuk Sistem Paper-Trading

**Tanggal:** riset berbasis web (README + dokumentasi resmi repo)
**Fokus:** beebots (repo utama) + 4 repo pembanding open-source
**Tujuan:** mengekstrak pelajaran konkret untuk sistem paper-trading yang harus (a) memilih 1–2 strategi terbaik per market dari hasil backtest, (b) memisahkan wallet per strategi, (c) memprioritaskan profit.

> ⚠️ Catatan metodologi: semua informasi di bawah diambil dari README/dokumentasi publik repo (bukan audit kode baris-per-baris). Beberapa repo menyatakan dirinya "eksperimen, bukan mesin uang" — perlakuan itu ditandai.

---

## 0. Ringkasan Perbandingan Cepat

| Repo | Bahasa/Stack | Paper vs Live | Backtest & Pemilihan Strategi | Wallet / Alokasi Modal | Scheduling |
|---|---|---|---|---|---|
| **beebots** (imikerussell) | TypeScript/Node (pnpm), Docker Compose, SQLite, dashboard React | Paper default; live butuh 4 gate manual | Tidak ada backtest klasik — "seleksi" via leaderboard + Beekeeper (LLM rewrite) + salinan rules pemenang | 1 bee = 1 wallet virtual ($333), 3 bee = 3 portofolio terpisah | Tick loop internal `TICK_MS=10000` (event loop, bukan cron) |
| **Freqtrade** | Python, SQLite, CLI + Telegram, Docker | `dry_run` flag (paper) vs live — kode sama, config beda | Backtesting + Hyperopt (Optuna) + `--strategy-list` banding multi-strategi; dry-run gate wajib | Satu wallet per instance `config.json`; multi-strategi via banyak instance/`--strategy-list` | Cron/systemd/Docker restart; bot long-running + REST API |
| **Hummingbot** | Python (Cython core), Docker, CLI + API + Dashboard | `*_paper_trade` connector vs live connector | Backtest via Dashboard (Net PNL, Sharpe, Profit Factor, Max DD); config-tagging untuk promosi | Banyak instance/container; controller parallel dalam satu bot | Hummingbot API/dashboard deploy; proses long-running |
| **justinmarkdaniel/trading-bot** | Python + FastAPI, single process, Docker ARM64 | Backtest = live "by construction"; multi-account dispatch | `POST /backtest` pakai registry + indikator identik dengan live | `accounts.json` — tiap akun ccxt + state terisolasi + allow-list strategi | Tick loop daemon di boundary 5 menit |
| **Auramaur** (DarriEy) | Python (uv), SQLite, MCP bridge | Paper default; live butuh 3 gate + KILL_SWITCH | Graduation ladder + probation; tiap trade 15 cek risiko; Kelly sizing | Treasury cross-venue; allocator + kategori exposure cap | Loop berjalan; gate keputusan, bukan cron |

---

## 1. beebots — Repo Utama (imikerussell/beebots)

- **URL:** https://github.com/imikerussell/beebots
- **Lisensi:** MIT · ~279 stars · ~129 forks · Diumumkan via video Creator Magic.

### 1.1 Bahasa / Stack
- **TypeScript / Node.js**, package manager **pnpm**.
- **Docker Compose** sebagai unit deploy (image `engine` + `dashboard` + Caddy reverse proxy).
- **SQLite** untuk ledger keputusan/order.
- Dashboard web (React/Vite, `pnpm dev` di `dashboard/`).
- Integrasi bursa: **OKX Agent Trade Kit** ([okx/agent-trade-kit](https://github.com/okx/agent-trade-kit), MIT). Data publik (tickers, candles, OI, funding) jalan in-process via REST client kit; call bertanda-tangan (order, posisi, fills, leverage) lewat CLI kit.

### 1.2 Arsitektur Berlapis
- **Strategy layer:** tiga "gaya" bawaan — **Breakout** (1 breakout volatilitas/hari, koin terbatas BTC/ETH/SOL/HYPE), **Trend** (trend-following BTC/ETH saja), **Momentum** (kejar mover 7-hari terkuat di semua koin likuid). Setiap bee dijalankan satu gaya; rules teks dari user dikirim ke model keputusan (Jev).
- **Decision layer (unik):** setiap tick setiap bee melakukan: 1) **Look** data OKX live → 2) **Summarise** snapshot numerik → 3) **Ask Jev** (model keputusan TypeSafe AI) memilih satu move dari menu yang valid sekarang + probabilitas → 4) **Check** risk layer → 5) **Record** ke SQLite sebelum bertindak → 6) **Broadcast** ke dashboard.
- **Execution layer:** order lewat kit OKX CLI; bot **tidak bisa withdraw**; live pakai sub-account OKX terpisah per bee, key Read+Trade only, IP-bound.
- **Data layer:** REST publik OKX in-process, tanpa child process per call; `pnpm parity` memverifikasi kesamaan data dengan CLI.
- **Risk layer (plain code, bukan LLM):** maks 2x leverage, stop per-bee, daily loss stop, trade caps, fee budget, cooldown, dan **hard daily cap** Jev spend (`JEV_DAILY_USD_CAP=2`). Layer ini bisa **veto, memperkecil, atau memaksa** move. Prinsip kunci: *Jev stateless dan tidak pernah melihat endpoint order*; kalau Jev down/lambat → bees hold, tidak buka apa pun.

### 1.3 Paper vs Live
- **Paper adalah default.** Harga pasar nyata + uang simulasi.
- Live butuh **empat** kondisi sekaligus: `DRY_RUN=false`, `MODE=live`, tiga key OKX EEA sub-account, dan `LIVE_ACK=I-ACCEPT-REAL-MONEY-RISK`. Kurang satu → engine **menolak start**.
- **Live ramp:** jam-jam pertama live jalan ukuran kecil (`LIVE_SIZE_MULTIPLIER`, `LIVE_RAMP_HOURS`).
- End live run: `touch /data/close-live` → engine berhenti bertanya Jev, menutup semua posisi dengan reduce-only market order.
- Ada juga `MODE=demo` (key demo OKX) sebagai tahap di antara paper dan live.
- *Pelajaran:* gate live bukan sekadar flag boolean — kombinasi environment variable + acknowledgment eksplisit + ramp sizing.

### 1.4 Backtesting & Pemilihan Strategi
- **Tidak ada backtest klasik** (tanpa historical simulation engine). Ini penting: beebots adalah *live paper race*, bukan backtest lab.
- "Seleksi" terjadi lewat tiga mekanisme:
  1. **The Hive** — leaderboard publik opsional (beebots.tech) tempat bee semua orang berlomba; menampilkan % gain/loss saja. Board bisa **verify** tiap trade dengan replay harga OKX publik → ini semacam *out-of-sample proof*.
  2. **Copy a winning bee** — setiap bee di leaderboard punya tombol **Copy** rules; paste ke Setup untuk mulai dari playbook pemenang.
  3. **The Beekeeper (opsional, Zapier)** — coach eksternal tiap beberapa jam: membaca `GET /keeper/scorecard`, Jev pilih bee, Claude menulis rules baru, Zap `POST /lab/overlay`. Rewrite = teks rules + daftar koin satu bee; **tidak pernah** leverage/stop/cap/mode. Batas **1 rewrite per bee per 20 jam**, round key sekali pakai, ada **Undo**. Overlay sudah terpasang di paper = tidak perlu restart (brain dibangun ulang di tick berikutnya).
- *Insight:* alih-alih memilih strategi via backtest statis, beebots memilih via **kecepatan iterasi rules + leaderboard yang terverifikasi + rollback yang murah**.

### 1.5 Wallet / Alokasi Modal per Strategi
- **1 bee = 1 wallet virtual terpisah** (`BEE_START_EQUITY_USD=333`). Tiga bee = tiga set portofolio, ledger, dan hasil yang terisolasi.
- Isolasi ini yang membuat leaderboard bermakna: performa antar-strategi bisa dibandingkan apple-to-apple tanpa saling mengotori equity.
- Live memakai **sub-account OKX terpisah per bee** (`BEE1_OKX_API_KEY` dst), jadi isolasi modal nyata.

### 1.6 Scheduling
- **Tick loop internal** (`TICK_MS=10000` default = tiap bee tanya Jev tiap 10 dtk). Ini event loop, **bukan cron**.
- Beekeeper pakai scheduler eksternal: engine sendiri memulai tiap round dan memanggil Catch Hook (Zapier), dengan retry 10 menit bila gagal.
- Backup: sidecar menulis copy DB tiap malam ke `/data/backups`, simpan 7 hari.

---

## 2. Freqtrade — Referensi Klasik Python

- **URL:** https://github.com/freqtrade/freqtrade · Docs: https://www.freqtrade.io/

### 2.1 Bahasa / Stack
Python; penyimpanan **SQLite**; dikendalikan via CLI + **Telegram RPC** (`/status`, `/profit`, `/performance`, `/balance`, `/daily`); deploy via Docker; config `config.json` + override environment variable `FREQTRADE__SECTION__KEY`.

### 2.2 Arsitektur Berlapis
- **Strategy layer:** satu kelas strategi Python (`populate_indicators`, `populate_entry_trend`, exit logic) dengan `stoploss`, `roi`, `trailing` sebagai atribut.
- **Data layer:** downloader candle historis (format `feather`/`parquet`) dari exchange.
- **Execution layer:** trader + `Exchange` abstract class (ccxt-style) → multi-exchange.
- **Risk layer:** ROI table, stoploss, trailing stop, `max_open_trades`, `stake_amount`, protections (cooldown, stoploss-guard).
- **Persistence layer:** SQLite menyimpan trades; dry-run pakai DB terpisah (`tradesv3.dry_run.sqlite`).

### 2.3 Paper vs Live
- Flag `--dry-run` (atau `dry_run: true`) → menghapus exchange secret & simulasi trade. **Kode strategi identik**, hanya config yang beda.
- `--dry-run-wallet / --starting-balance DRY_RUN_WALLET` = saldo awal untuk backtest/hyperopt/dry-run (**satu setting dipakai tiga mode** → konsistensi metrik).
- Praktik komunitas yang berulang: `config.json` (live) vs `config.dryrun.json` (paper, virtual wallet $10k), dengan **gate penerimaan** sebelum flip live (contoh dari repo turunan: *"Sharpe > 0.8 AND drawdown < 15% selama 2 bulan; kurang dari itu → balik tuning"*).
- Peringatan resmi komunitas: **hasil backtest tidak sama dengan dry-run** — dry-run biasanya *tidak lebih baik* dari backtest, jadi jangan harap dry-run menang.

### 2.4 Backtesting & Pemilihan Strategi
- **Backtesting:** `freqtrade backtesting --strategy X --timerange ...`; ada `--max-open-trades`, `--fee` (dikenakan dua kali), `--breakdown` (harian/mingguan/bulanan), web-server mode.
- **Hyperopt:** pakai **Optuna**; tuning `roi/stoploss/trailing` atau space penuh; loss function via `--hyperopt-loss` (mis. `SharpeHyperOptLossDaily`); jalankan N epoch, lalu `hyperopt-list` / `hyperopt-show` untuk memilih hasil terbaik/profitable. Peringatan checklist: `populate_indicators` harus membuat semua indikator yang dipakai space.
- **Pemilihan strategi:** `--strategy-list A B C` (banding beberapa strategi dalam satu backtest). Untuk keputusan "strategi mana terbaik", Freqtrade mengandalkan kamu **membandingkan metrik** dari tiap run, bukan auto-selector bawaan.
- *Pelajaran:* hyperopt = *parameter tuning*, bukan pemilihan strategi. Pemilihan strategi tetap pekerjaan komparasi lintas-run.

### 2.5 Wallet / Alokasi Modal
- Satu instance = satu config = **satu wallet** (spot/futures). Freqtrade **tidak** membagi modal per strategi di dalam satu proses.
- Pola multi-strategi: jalankan **beberapa instance** (mis. `docker-compose.dca.yml` dan `docker-compose.rebalance.yml` terpisah, masing-masing `.env` sendiri) — modal terpisah karena proses/DB terpisah.
- `stake_amount` + `max_open_trades` mengatur ukuran posisi per trade.

### 2.6 Scheduling
- Bot **long-running** (bukan cron): `freqtrade trade` atau `docker compose up -d`, di-restart oleh Docker/systemd.
- Clock sistem harus sinkron NTP (kalau tidak, komunikasi exchange bermasalah).
- Ada `--sd-notify` (integrasi systemd readiness).
- Pola umum: **cronjob** eksternal untuk *backtest/tuning periodik*, sementara *trading loop* sendiri jalan terus.

---

## 3. Hummingbot — Framework Market-Making Modular

- **URL:** https://github.com/hummingbot/hummingbot · Docs: https://hummingbot.org/

### 3.1 Bahasa / Stack
Python dengan core **Cython** (performa); CLI + **Hummingbot API** + **Dashboard** + **Gateway** (jembatan DEX). Apache-2.0. Arsitektur komponen: **Condor** (AI harness) → API → Client/Gateway.

### 3.2 Arsitektur Berlapis
- **Strategy layer** bergradasi: `Executor` (workflow diskret: place/manage/close, punya lifecycle active→closed/failed), `Scripts` (single-file, prototyping), `Controllers` (modular, production, **dapat backtest & tune live**), dan V1 strategies legacy (Pure MM, Avellaneda, XEMM).
- **Data layer:** `Market Data Provider` — satu titik akses OHLCV historis, order book, trades; dipakai baik oleh strategy decision maupun backtest.
- **Execution layer:** `Exchange Connectors` yang menstandardisasi REST + WebSocket berbagai CEX/DEX.
- **Risk layer:** di executor (mis. `position_executor` punya *triple-barrier risk controls*); plus inventory management khas market-making.
- Strategi = `TimeIterator`, method `c_tick()` dipanggil tiap detik → pola "menonton market seperti film, satu frame per detik".

### 3.3 Paper vs Live
- **Paper trading via connector khusus:** `--set exchange=binance_paper_trade` — *simulasi terhadap data pasar Binance live, tanpa API key*. Ini pola elegan: paper adalah *tipe connector*, bukan flag global.
- Deploy live vs paper hanya beda nama connector.

### 3.4 Backtesting & Pemilihan Strategi
- **Backtesting lewat Dashboard** di tiap halaman controller: pilih connector + trading pair + rentang tanggal + resolusi + trade cost → **Net PNL (quote), Max Drawdown (USD), Total Volume, Sharpe Ratio, Profit Factor**, breakdown close-type (TAKE PROFIT / TRAILING STOP / STOP LOSS / TIME LIMIT / EARLY STOP), plus chart candlestick & PNL.
- **Config tagging** (mirip version number) → config yang di-backtest dan memuaskan **di-upload** ke halaman *Deploy V2*, lalu dibuat instance dari config tersimpan itu. Ini alur **backtest → promote → deploy** yang eksplisit.
- Pemilihan strategi: banding controller via metrik backtest, lalu promote config pemenang.

### 3.5 Wallet / Alokasi Modal
- Isolasi modal lewat **banyak instance/container**, dan **banyak controller dalam satu container** untuk strategi parallel.
- Tiap controller/executor punya order lifecycle sendiri; mendukung multi-strategi simultan.

### 3.6 Scheduling
- Loop internal (`c_tick()` per detik) untuk tingkah laku; **Hummingbot API/Dashboard** untuk deploy & mengelola instance. Tidak berbasis cron — proses long-running.

---

## 4. justinmarkdaniel/trading-bot — Chassis Fokus "Backtest = Live"

- **URL:** https://github.com/justinmarkdaniel/trading-bot · MIT · Binance USDⓈ-M Futures.

### 4.1 Bahasa / Stack
Python + **FastAPI**, **single process** (FastAPI + bot loop satu interpreter), Docker ARM64 (~300 MB). Strategi, TA, dan inferensi ML berbagi satu proses.

### 4.2 Arsitektur Berlapis
- **Strategy layer:** registry `active/monitoring`; menambah strategi = drop file dengan `decide(df) -> dict`. Model = `predict(features) -> dict`. **Tanpa framework lock-in.**
- **Data layer:** `Live data engine` (klines + TA + order flow) dibagi via `StateStore` thread-safe (tanpa IPC/queue/DB).
- **Execution layer:** adaptive 4-stage order chaser: GTX post-only @bid → GTC limit inside spread → IOC limit @ask+3bps → market failsafe; klaim fill ~95%+.
- **Risk layer:** fat-finger guard (qty > N× rolling median), rate limiter, allow-list strategi per akun.

### 4.3 Paper vs Live
- Didesain **"backtest = live by construction"**: `POST /backtest` memanggil registry, kline fetcher, dan indikator **yang sama persis** dengan bot live. Tidak ada implementasi kedua logika strategi. Mengubah strategi → backtest berikutnya otomatis mencerminkan.
- Klaimnya: backtest realistis karena jalur kode identik.

### 4.4 Backtesting & Pemilihan Strategi
- Endpoint `POST /backtest` melakukan walk-forward terhadap pipeline yang sama. Pemilihan strategi dilakukan dengan membandingkan hasil endpoint ini (registry `active` vs `monitoring` — strategi dapat "dipromosikan/didemosikan" antar dua status itu).

### 4.5 Wallet / Alokasi Modal
- **Multi-account dispatch eksplisit:** setiap entry di `accounts.json` = satu **ccxt client sendiri**, **state terisolasi**, dan **allow-list strategi** yang boleh ditembak akun itu. Tick loop berjalan akun demi akun dalam urutan registrasi; strategi monitoring bersifat account-agnostic.
- Ini pola paling langsung untuk "wallet per strategi/akun": akun → allow-list strategi.

### 4.6 Scheduling
- Tick loop daemon-thread **bangun di boundary 5 menit** (bukan cron), plus HTTP surface untuk introspeksi (`/health`, `/state`, `/trade/...`).

---

## 5. Auramaur — Bot Prediction Market dengan Graduation Ladder

- **URL:** https://github.com/DarriEy/Auramaur · MIT · Polymarket & Kalshi.

### 5.1 Bahasa / Stack
Python (`uv`), **SQLite**, MCP bridge (`agentmcp/`) untuk mengekspos plumbing ke agen eksternal. Modular: `exchange/`, `data_sources/`, `nlp/`, `risk/`, `strategy/`, `broker/`, `monitoring/`, `db/`.

### 5.2 Arsitektur Berlapis
- **Strategy layer:** engine + signal detection + **market selector** + resolution tracking.
- **Data layer:** news/RSS/Reddit/FRED/Manifold/Metaculus + CLOB order book.
- **NLP layer:** Claude analyzer, kalibrasi probabilitas (Platt scaling dari feedback resolusi), second opinion adversarial.
- **Risk layer:** **15 cek independen per trade** (tak bisa di-bypass), **geometric Kelly sizing**, limit drawdown, cap exposure per kategori.
- **Execution layer:** **satu gateway** `ExecutionGateway` / `exchange/client.py`; paper interception di `exchange/paper.py`; `broker/` = allocator, syncer, reconciler, redeemer, PnL tracker.
- **Treasury layer:** modal cross-venue + transfer.

### 5.3 Paper vs Live
- **Paper default.** Live butuh **tiga gate** sekaligus: `AURAMAUR_LIVE=true`, `execution.live=true`, dan per-order `dry_run=False`.
- **KILL_SWITCH** file di root/working dir → menghentikan semua trading.
- **Graduation ladder:** modal live digated bertingkat; sebagian besar strategi tetap **probation**.

### 5.4 Backtesting & Pemilihan Strategi
- Tidak menekankan backtest klasik; penekanan pada **calibration loop** (resolusi → kalibrasi Probabilitas) dan **graduation ladder + probation** sebagai mekanisme seleksi berbasis performa nyata.
- Risiko di-enforce *independen dari model* — mencegah perilaku "gambling".

### 5.5 Wallet / Alokasi Modal
- **Treasury cross-venue** + **allocator**; geometric Kelly sebagai ukuran posisi; cap per kategori sebagai diversifikasi modal. Modal live hanya mengalir ke strategi yang lulus ladder.

### 5.6 Scheduling
- Loop berjalan terus; keputusan berbasis gate, bukan cron. Reconciliation posisi terhadap riwayat trade CLOB on-chain.

---

## 6. Pelajaran Konkret & Transferable

Dipetakan ke tiga kebutuhan sistem paper-trading kamu.

### A. Memilih 1–2 strategi terbaik per market dari backtest

1. **Backtest = jalur kode yang sama dengan live (bukan reimplementasi).** Ambil pola justinmarkdaniel ("backtest = live by construction") dan Freqtrade (satu `dry_run_wallet` untuk backtest/hyperopt/dry-run). Kalau logika strategi punya dua implementasi, metrik backtest bohong.
2. **Simpan hasil backtest ke media persisten, agregasi di kode, bukan di kepala.** Freqtrade menyimpan trades di SQLite & `hyperopt-list/show`; Hummingbot mengekspor metrik backtest. Untuk "1–2 terbaik per market": tulis tiap run (market × strategi × metrik) ke JSON/CSV di workspace, lalu **rank with Python**.
3. **Metrik seleksi harus multi-faktor, bukan cuma net profit.** Pakai set Hummingbot/Jesse/Freqtrade: **Net PNL, Max Drawdown, Sharpe, Profit Factor** (+ win rate, jumlah trade). Repo skylar93 menambahkan gate keras: OOS Sharpe konsisten antar-fold, **bootstrap 95% CI Sharpe lower-bound > 0**, **permutation p < 0.05**, Deflated Sharpe, dan Sharpe kondisional-regime tak boleh katastrofik. Karena target kamu *memprioritaskan profit*, tapi profit tanpa Drawdown/Sharpe = overfit.
4. **Bedakan tuning-parameter vs pemilihan-strategi.** Hyperopt (Optuna) hanya men-tuning parameter; keputusan strategi adalah komparasi lintas-run (`--strategy-list`). Jangan campur.
5. **Walk-forward + out-of-sample, jangan single split.** Gunakan walk-forward; dan tiru mekanisme verifikasi beebots (Hive me-replay trade terhadap harga publik) sebagai *proof* out-of-sample.
6. **Anti-overfit eksplisit.** AlphaPipeline memakai **CPCV/KCV/walk-forward**; jaga Deflated Sharpe untuk menghitung jumlah trial hyperopt.
7. **Sediakan jalur promote/demote.** justinmarkdaniel: registry `active` vs `monitoring`; Hummingbot: config-tag → Deploy V2; beebots: salin rules pemenang. Sistem kamu harus punya flag: strategi lolos gate → `active` (pakai modal), gagal → `monitoring` (paper only).
8. **Gate paper sebelum "live" (bahkan live-paper).** Pola komunitas Freqtrade: *Sharpe > 0.8 AND drawdown < 15% selama 2 bulan* sebelum promosi. Formal-kan sebagai ambang numerik.

### B. Memisahkan wallet per strategi

9. **1 strategi = 1 wallet/ledger terisolasi (pola beebots `BEE_START_EQUITY_USD=333`).** Equity, fill, fee, dan PnL tidak boleh tercampur, supaya perbandingan antar-strategi sah.
10. **Implementasikan sebagai proses/akun terpisah, bukan cuma kolom di satu tabel.** justinmarkdaniel `accounts.json`: tiap akun punya ccxt client sendiri + **state terisolasi** + allow-list strategi. Freqtrade memisahkan lewat instance/DB terpisah.
11. **Dukung banyak strategi di satu market tanpa tabrakan.** justinmarkdaniel memakai **allow-list strategi per akun**; Hummingbot menjalankan banyak controller parallel dengan order lifecycle masing-masing. Batasi siapa boleh menembak wallet mana.
12. **Pusatkan alokasi modal di satu tempat.** Auramaur: satu `ExecutionGateway` + `allocator` + treasury. Semua order lewat satu gerbang → mudah audit & cap.
13. **Pisahkan "risk capital" dari "operational capital".** beebots: bot tak bisa withdraw; key Read+Trade only, IP-bound; live di sub-account terpisah. Untuk paper, ini berarti: wallet simulasi terpisah dari apa pun yang menyentuh kredensial nyata.

### C. Memprioritaskan profit (dengan aman)

14. **Risk layer dalam plain code, independen dari LLM/sinyal.** beebots: Jev tak pernah melihat endpoint order; risk layer dapat veto/shrink/force. Auramaur: 15 cek + Kelly, tak bisa di-bypass. **Keuntungan datang dari sinyal; kelangsungan hidup datang dari risk layer terpisah.**
15. **Position sizing berbasis risiko, bukan all-in.** Auramaur: geometric Kelly + cap exposure per kategori. Freqtrade: `stake_amount` + `max_open_trades`. beebots: `LIVE_SIZE_MULTIPLIER` + ramp awal.
16. **Ramp sizing saat naik dari paper ke uang nyata.** beebots: `LIVE_SIZE_MULTIPLIER` + `LIVE_RAMP_HOURS` untuk jam-jam pertama. Auramaur: graduation ladder. Terapkan juga saat live-paper → mikro-live.
17. **Kill switch & cooldown sebagai warga kelas satu.** Auramaur `KILL_SWITCH` file; freqtrade protections (cooldown, stoploss-guard); HarrierOnChain circuit breaker (auto-halt setelah N trade besar) + Depth Guard.
18. **Cap biaya non-trading.** beebots `JEV_DAILY_USD_CAP=2` — cap keras biaya inferensi/API per hari, saat kena → semua hold sampai 00:00 UTC. **Profit bersih = profit kotor − fee − biaya data/inferensi.** Freqtrade kenakan `--fee` dua kali (entry+exit) — jangan lupakan fee.
19. **Isolasi kegagalan (fail safe).** saat sinyal/LLM down → hold, jangan buka posisi (beebots). Auramaur: paper default & tiga gate. Freqtrade: dry-run default disarankan sebelum uang.
20. **Umpan-balik belajar, tapi dengan ladder & rollback.** Auramaur: resolusi → kalibrasi. beebots: Beekeeper menulis ulang rules tapi **tak pernah** menyentuh leverage/stop/cap/mode, dan **selalu ada Undo**, 1 rewrite/20 jam. Kalau sistem kamu menyesuaikan strategi otomatis, batasi blast radius: hanya rules/coin list, dengan rollback dan rate-limit.

### D. Scheduling (pola yang terbukti)

21. **Loop internal untuk trading, cron untuk housekeeping.** beebots `TICK_MS` (event loop), justinmarkdaniel tick di boundary 5 menit — *bukan* cron untuk trading. Cron/`systemd`/Docker restart dipakai untuk **menjalankan ulang proses**, backtest/tuning periodik, dan **backup** (beebots: sidecar backup DB tiap malam, retensi 7 hari).
22. **Idempotensi & batas per-round.** Beekeeper: round key sekali pakai, one round at a time, retry 10 menit bila gagal. Untuk pipeline backtest/paper terjadwal: pastikan job aman diulang dan punya batas waktu.
23. **Sinkronkan jam.** Freqtrade menuntut clock NTP akurat; penting untuk timestamp candle & verifikasi.

---

## 7. Rekomendasi Blueprint (ringkas) untuk Sistem Paper-Trading Kamu

```
┌─ Data layer ─────────────────────────────────────────────────┐
│ OHLCV + indikator; satu pipeline dipakai backtest DAN paper  │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌─ Backtest & Selection ───────────────────────────────────────┐
│ walk-forward; simpan hasil tiap (market×strategi) ke JSON;   │
│ rank via: NetProfit, MaxDD, Sharpe, ProfitFactor (+CI>0,     │
│ permutation p<0.05) → pilih top 1–2 per market → label       │
│ active / monitoring, dengan gate ambang (mis. Sharpe>0.8,    │
│ DD<15%)                                                      │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌─ Wallet layer (per strategi) ────────────────────────────────┐
│ wallets[strategy_id] = {equity, ledger, allow_list, market}  │
│ order HANYA lewat satu ExecutionGateway + Allocator          │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌─ Risk layer (plain code, LLM tak bisa bypass) ───────────────┐
│ cap per-trade, max leverage, daily loss stop,          │
│ drawdown ladder, KILL_SWITCH, fee+inference daily cap,       │
│ position sizing (Kelly/fractional), cooldown                 │
└───────────────┬──────────────────────────────────────────────┘
                ▼
┌─ Scheduling ─────────────────────────────────────────────────┐
│ tick loop internal untuk trading; cron untuk backtest ulang, │
│ retraining/re-selection, dan backup harian                   │
└──────────────────────────────────────────────────────────────┘
```

**Aturan emas (dari repos):**
- *Satu jalur kode* backtest↔paper (justinmarkdaniel, Freqtrade).
- *Satu wallet per strategi* (beebots).
- *Risk layer di luar model/LLM* (beebots, Auramaur).
- *Seleksi berbasis metrik risiko-terkoreksi*, bukan net profit mentah (Hummingbot, Jesse, skylar93).
- *Gate & ramp sebelum modal nyata* (beebots 4-gate + ramp; Auramaur 3-gate + ladder; Freqtrade dry-run gate).
- *Rollback murah untuk perubahan strategi otomatis* (beebots Beekeeper + Undo).

---

## 8. Sumber (URL)

**Repo utama**
- beebots (imikerussell): https://github.com/imikerussell/beebots
- Leaderboard/dashboard: https://beebots.tech/ · OKX Agent Trade Kit: https://github.com/okx/agent-trade-kit

**Pembanding**
- Freqtrade: https://github.com/freqtrade/freqtrade · Docs: https://www.freqtrade.io/
  - Backtesting: https://www.freqtrade.io/en/stable/backtesting/
  - Hyperopt: https://www.freqtrade.io/en/stable/hyperopt/
  - Configuration: https://www.freqtrade.io/en/stable/configuration/
  - Start the bot: https://docs.freqtrade.io/en/2026.6/bot-usage
- Hummingbot: https://github.com/hummingbot/hummingbot · Docs: https://hummingbot.org/
  - Strategi V2/arsitektur: https://hummingbot.org/strategies/v2-strategies
  - Backtesting (Dashboard): https://hummingbot.org/dashboard/backtest/
  - Blog arsitektur: https://hummingbot.org/blog/hummingbot-architecture---part-2
- justinmarkdaniel/trading-bot: https://github.com/justinmarkdaniel/trading-bot
- Auramaur (DarriEy): https://github.com/DarriEy/Auramaur

**Repo pendukung (pola yang dikutip)**
- Jesse (backtest engine): https://docs.jesse.trade/docs/backtest.html
- skylar93/trading_bot (RL paper-trading + gate Sharpe): https://github.com/skylar93/trading_bot
- AlphaPipeline (CPCV/walk-forward, risk layer bersama): https://github.com/xsa-dev/AlphaPipeline
- HarrierOnChain Prediction-Markets-Toolkits (circuit breaker, dry-run): https://github.com/HarrierOnChain/Prediction-Markets-Trading-Bot-Toolkits
- Samvid Trading Core (drawdown ladder, multi-broker paper): https://github.com/AshishTalpada/samvid-trading-core
- StratForge trading-bot-open-source (microservices, sandbox router): https://github.com/decarvalhoe/trading-bot-open-source
- Contoh gate dry-run→live Freqtrade: https://github.com/almprmg/freqtrade_btc_bot
- Solana trading-bot-architecture (pola lapisan & config): https://github.com/sanctifiedops/solana-skills/blob/main/skills/bots/trading-bot-architecture/SKILL.md

> **Disclaimer:** Repo-repo ini mayoritas menyatakan diri sebagai eksperimen/edukasi, "not financial advice," tanpa jaminan. Perlakuan performa aktual sebagai hasil riset, bukan janji profit.
