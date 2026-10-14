# Tencent (previous system) — Cronjob Trading Architecture: Crypto / IDX / Forex

**Source of truth:** `/tmp/tencent-src` (3 files) and `/tmp/tencent_arsip` (23 files).
All findings below are read directly from the staged files; journal JSON/XLSX/SQLite contents
were parsed. Nothing in the staged tree was modified.

**Scope:** how the previous system ("Tencent") structured its trading crons and pipelines for
three markets — **crypto (Binance perp / MEXC exec)**, **IDX (Indonesian equities)** and
**forex (XAUUSD + NAS100/EURUSD multi-pair)** — covering pipeline stages, cron cadence,
signal→entry→exit→journal flow, data files written, key parameters, and design lessons.

---

## 0. System-wide facts that apply to all three markets

- **Timezone is WIB (UTC+7)** everywhere. Cron windows, session filters, and cutoffs are all WIB.
  Host clock note: `idx_scalp_watch.py` line 53: `# Host CST (UTC+8); WIB = UTC+7` → WIB derived as `utcnow() + 7h`.
- **"Silent cron" / watchdog pattern** is used everywhere: a collector prints to **stdout only when there is
  something to say**; empty stdout = no Telegram post. Examples:
  - `crypto_watch_eval.py:6` *"prints alert lines ONLY when a level is hit (empty stdout = silent, watchdog pattern). No LLM involved."*
  - `idx_flow_collect.py:14` *"no_agent cron, stdout kosong = SILENT"*
  - `idx_scalp_watch.py:9` *"[SILENT] ... no scalping setups found"*
- **Two-layer architecture**: a *deterministic Python data/collect/score layer* (fapi curl, TradingView feed,
  arjum, yfinance, sqlite) + an *LLM composing layer* that turns a JSON/text "packet" into a Telegram post.
  The pipeline scripts themselves explicitly **never post**:
  - `xauusd_pipeline.py:10` *"Final message ... is composed by the calling cron LLM from this JSON — pipeline itself never posts."*
  - `crypto_pipeline_collect.py:15` *"The composing LLM (Agent 2 setups + Agent 3 news interpretation) turns this digest into the Telegram post."*
- **Common SMC vocabulary** across crypto/forex: OB (order block), FVG/iFVG (fair-value gap / inversion FVG),
  EQH/EQL (equal highs/lows = liquidity), premium/discount on dealing range, BOS/CHoCH, CISD, ATR, `TP1=1R`, `TP2=2R`.
- **Common exit rule v3**: **TP1 hit → close 50% (partial) + move SL to break-even (BE)**, runner targets TP2.
  Stated in many places, e.g. `crypto_watch_eval.py:66`, `trade_journal.py:22-25`, `xauusd_journal.json meta`.
- **Journals are the cross-system source of truth.** `xauusd_reactive.py:100-107`:
  *"The journal is the source of truth across the whole system."*

---

## 1. CRYPTO

### 1.1 Pipeline stages

The crypto stack is a **5-agent (actually 6-agent with add-ons) signal pipeline** plus a separate
**execution + watchdog** track. Defined in `crypto_pipeline_collect.py` (docstring lines 2-17):

| Stage | Agent | What it does | Source file |
|---|---|---|---|
| FASE 0 | A1 (partial) | Order-flow scan: buy pressure, vol Δ6h, funding, L/S ratio, classify_flow | `crypto_signal_collect` + `crypto_pipeline_collect.py` |
| FASE 1 | A1 | SMC structure 1D/4H/1H (EMA50, premium/discount, BOS) | same |
| FASE 2 | A4 | Whale & positioning: taker buy/sell ratio, OI Δ24h, whale aggTrades >$100k, funding extremes | `whale_scan.py` |
| FASE 3 | A3 | Sentiment: Fear & Greed (alternative.me), BTC dominance (CoinGecko) | `crypto_pipeline_collect.py` |
| FASE 4 | A5 | Risk & exposure: spread, ATR(14) 1H, open positions, BTC regime | same |
| A6 | A6 | On-chain (DefiLlama) + positioning — **confirmation only, not a gate** | `onchain_enrich.py` |
| A6b | — | Hyperliquid whale-wallet accumulation (read-only from state; refreshed by separate cron) | `hl_whale_accum.py` |

Agent 2 (setups) and Agent 3 (news interpretation) are explicitly **LLM tasks**, not in the collector.

**Morning outlook variant:** `crypto_outlook_collect.py` (thread 648) — MEXC perp digest (BTC/ETH focus) +
CoinGecko global + "OTHERS proxy" (total mcap − top10) for a two-scenario morning outlook.

### 1.2 Cron / schedule cadence

Derived from job IDs/thread IDs in the code (exact crontab not in the staged files, but cadence is stated/embedded):

| Job | Cadence | Evidence |
|---|---|---|
| Crypto signal pipeline (thread 653) | docstring: *"crypto-signal-653 cron job"* | `crypto_signal_journal.py:3` |
| Crypto outlook (thread 648) | morning, pre-market | `crypto_outlook_collect.py:1` *"Morning outlook collector for thread 648"* |
| `crypto_watch_eval.py` | **hourly** — *"Silent watchdog: hourly evaluation of crypto watchlist (topic 653)"* | line 2; prints `⏱ CRYPTO AUTO-EVAL (hourly)` |
| `crypto_auto_exec.py` | driven per signal (reads watchlist, execs `still_open`), not its own timer in-file | docstring line 4 |
| HL whale accumulation | **every 10 minutes** — *"state only (cron hl-whale-accum-653 that refreshes every 10 minutes)"* | `crypto_pipeline_collect.py:341-342` |
| `crypto_fill_monitor.py` | spawned as a daemon on fill (`subprocess.Popen`) to arm SL/TP | `crypto_auto_exec.py:199-202` |

### 1.3 Signal → entry → exit → journal flow

1. **Scan** — pipeline builds digest, candidates = pairs whose `classify_flow` is Mild/AGGRESSIVE/Strong (`crypto_pipeline_collect.py:185-187`).
2. **Signal** — LLM composes Telegram post; then `crypto_signal_journal.py` appends a row (`SIGNAL` or `NO_TRADE`) to XLSX with entry/SL/TP1/TP2 estimates.
3. **Watchlist** — open ideas live in `~/.hermes/crypto-watchlist.json` as items with `status="still_open"`, `entry_zone` (e.g. `"4.795-4.845"`), `sl/tp1/tp2`, `direction`.
4. **Entry (auto-exec)** — `crypto_auto_exec.py` reads the watchlist, applies guardrails, then places a **MEXC LIMIT order at the mid of the entry zone**:
   - `mid = (entry_lo + entry_hi) / 2` (line 132), `limit_order(pair, lots, direction, price_str)` (line 191).
   - On success sets `it["auto_executed"]=True`, writes state, and **spawns `mexc_fill_monitor.py`** to arm SL/TP at fill (lines 195-202).
5. **Exit / management** — `crypto_watch_eval.py` (hourly) evaluates TP1/TP2/SL using **intrabar 1H high/low**, not spot:
   - TP gate helper line 225-235 (*"TP itu limit order yang MENGGANTUNG ... touch = hit"*).
   - TP2 → `closed_TP2`; TP1 → `manage_tp1()` (partial 50% + SL→BE); SL → `closed_SL`.
   - `manage_tp1()` (lines 65-158) cancels old stop orders, closes half if `hold >= 2`, moves SL to BE, **verifies on exchange** (`stoporder/list/orders`, line 151).
6. **Journal / equity** — after eval, `crypto_equity.sync()` appends newly closed trades to the equity ledger (lines 293-301). XLSX journal manually filled for `Hasil/P-L/Skor Disiplin`.

### 1.4 Data files written

| File | Writer | Content |
|---|---|---|
| `~/.hermes/crypto-journal/crypto_journal.xlsx` | `crypto_signal_journal.py` | Sheet **"Jurnal Crypto"**, 14 cols (Tanggal, Jam WIB, Status, Pair, Arah, Entry Est., SL Est., TP1 Est., TP2 Est., Funding %, Alasan/Bias MTF, Hasil, P/L %, Skor Disiplin) |
| `~/.hermes/crypto-watchlist.json` | signal job / auto-exec | Open ideas, `status`, `entry_zone`, `sl/tp1/tp2`, `auto_executed`, `exec_skip` |
| `~/.hermes/crypto-auto-exec-state.json` | `crypto_auto_exec.py` | Per-signal exec result `{ts, ok, resp, lots}` |
| `~/.hermes/state/onchain_enrich.jsonl` | `onchain_enrich.py` | On-chain enrichment datalog (for edge evaluation) |
| Equity ledger (via `crypto_equity.sync()`) | `crypto_watch_eval.py` | Closed trades appended |

`crypto_journal.xlsx` parsed: header row confirmed + real rows, e.g. `2026-08-25 10:25 SIGNAL BTC_USDT Long entry 78200 SL 76900 TP1 80500 TP2 82500 funding 0.0100 … Hasil CLOSED MANUAL, P/L 0.63, Skor A`.

### 1.5 Key parameters

| Parameter | Value | Where |
|---|---|---|
| Risk per trade (cap) | `RISK_PCT_MAX = 2.0` % of balance | `crypto_auto_exec.py:28` |
| Risk per trade (abs cap) | `RISK_PER_TRADE_USDT = 1.5` | line 29 |
| **Hard risk reject** | `RISK_PCT_HARD = 5.0` % (skip if 1 lot risks more) | line 30 |
| Max open positions | `MAX_OPEN = 2` | line 33 |
| Min balance to trade | `MIN_BALANCE = 10.0` USDT | line 34 |
| Sizing formula | `notional = risk_budget / sl_pct`; `lots = notional/(mid*csize)`, round-down if `vol_scale==0` | lines 161-171 |
| Whale print threshold | `WHALE_NOTIONAL_USD = 100_000` | `crypto_pipeline_collect.py:34` |
| SMC TFs | 1D(100), 4H(100), 1H(60) | line 206 |
| Hold / TP rule | intraday 4-12h (max 24h), TP1=1R, TP2=2R; **POI gate relaxed to 2-of-4 POI + 1 confirmation (CISD or iFVG)** | `crypto_signal_journal.py:16-20` |
| ATR risk-of-thumb | SL structure 1H ideal 0.5–2× ATR1H; TP2=2R realistic if ATR ≥ TP2-dist/12h | `crypto_pipeline_collect.py:326` |

### 1.6 Design lessons / pitfalls in comments

- **Sizing must be risk-based, not notional-based** (`crypto_auto_exec.py:23-27`): *"Sebelumnya: target $1.5 NOTIONAL … risiko antar koin beda 64x (OP $0.014 = 0.07% balance vs DOGE $0.90 = 4.4%)"*. Now unify risk.
- **Zone guard (bug 28 Sep, `crypto_auto_exec.py:134-158`)**: auto-exec used to place a limit at mid *without* checking current price; if price already broke the zone the limit filled instantly into a falling market. LIT #SIGAE6D3926: zone 4.795-4.845, price 4.707 → filled instantly, SL 7 min later. Guard now blocks LONG if `px_now < entry_lo`.
- **Symbol conversion to Binance fails silently** — `binance_price("LIT_USDT")` fails silently and the guard is skipped; must strip `_` (lines 142-143).
- **MEXC contract spec gotchas** (`crypto_auto_exec.py:60-84`): `contractSize` = coin per lot (LINK 0.1, DOGE 100); `volUnit` returns 1.0 for all → using it makes sizing wildly wrong; `volScale==0` ⇒ integer volume; **`priceScale` bug 29 Sep**: formatting price to 6 sig figs (XRP 1.49675) → MEXC error 2015 precision → limit never placed (XRP #SIG6D313137 failed 2×).
- **Only success should block re-exec** (lines 110-115): *"Dulu state apa pun (termasuk ok=False) ikut ngeblokir -> satu kegagalan 6002 bikin sinyal itu nggak pernah dicoba lagi"*.
- **Stale position dict after partial** (`crypto_watch_eval.py:112-119`): after partial close, the cached `holdVol` is stale (still 10 while actual 5); sending stop order with stale data → MEXC rejects → **position left WITHOUT SL (XRP 29 Sep)**. Fix: re-read position from exchange before each retry.
- **Fallback ladder: SL is more important than TP** (lines 121-125): *"BE itu proteksi modal; TP itu bonus"* — if combined SL+TP order rejected, place SL alone.
- **TP touch = hit, not "price still at level"** (`crypto_watch_eval.py:225-231`): old guard wrong for TP because the limit is resting on exchange.
- **Watchlist direction field name** (lines 180-182): watchlist writes `direction`, not `arah`; reading `arah` alone → all comparisons fail → **watchdog blind**.
- **Lookback since signal, not last 2 candles** (lines 199-210): missed crons / pullbacks make touches vanish; limit = hours since signal (clamped 2..120).
- **Deprecated whale fetcher** (`crypto_pipeline_collect.py:82-96`): the old `?startTime&endTime&limit=1000` only covered ~0.7-3 min of the "4 hours" claim (~1-5% of tape) and was biased to the start of the hour → replaced by `whale_scan.whale_scan()`.
- **Budget-aware whale scan** (lines 239-260): Binance rate limit 2400 weight/min, aggTrades limit=1000 = 20 weight; dynamic per-pair budget, coverage reported honestly instead of claiming full.
- **`exec_skip` = user's decision** (lines 104-109): signal still tracked + counted as PAPER trade, never retried.

---

## 2. IDX (Indonesian Stocks)

### 2.1 Pipeline stages & strategies

IDX is organized as **several independent strategy cron jobs** feeding a shared ledger + journal:

| Strategy | Script | Setup logic |
|---|---|---|
| **ARA Hunter** (auto-reject-up) | `idx_ara_collect.py` → `ara_hunter.py` | recipe `chg>=5% · rel_vol>=3x · ADX>15 · value>=Rp1B`; exit = open T+1; backtest walk-forward 11 Sep: +1.00% net/trade |
| **BSJP** (Beli Sore Jual Pagi) | `idx_bsjp_watch.py` | Entry=close T with `6%<=chg<=12%` (STRONG) / `2-25%` (ARA), `close>=1.03-1.05*SMA10`, `vol>=1.5x avg10`, price>100, value>=5B/1B; **exit = open T+1** at 08:55-09:05 WIB |
| **INTRADAY scalping** | `idx_scalp_watch.py` | breakout/rejection/momentum on 5-min WS or yfinance; verified edge `chg>=3% + price<=SMA10 + vol>=2x + value>=1B` |
| **Broker flow** (arjum) | `idx_flow_collect.py` + `arjum_pool.py` | per-ticker broker summary, foreign flow (f_buy/f_sell/n_foreign), bandar accumulation 4-month |
| **Track record** | `idx_track_record.py` | pairs SIGNAL rows ↔ first EVAL row in `idx_journal.xlsx` |

**Data source layer:** `arjum_pool.py` is a caching+quota wrapper over `arjum_client` (Arjum REST).
Key config `arjum_pool.py`:
- TTLs (lines 28-39): screener 30m, broker_summary 1h, history 4h, analysis 1d, seasonal 7d, financial_statements 7d, insiders 6h, market_cap 6h.
- `MIN_REMAINING = 500` — skip live fetch if quota below (line 40).
- `HISTORY_SOURCE = os.environ.get("ARJUM_HISTORY_SOURCE", "yfinance")` (line 49): OHLCV-only jobs served by **yfinance** to save Arjum quota; falls back to Arjum on failure (line 283-287).
- Audit JSONL: `~/.hermes/cron/logs/arjum_audit_<YYYY-MM-DD>.jsonl` (lines 72-88).

### 2.2 Cron / schedule cadence

| Job | Cadence / window | Evidence |
|---|---|---|
| `idx_scalp_watch.py` | **every 20 min, Mon-Fri 09:00-14:40** | line 10 *"Run by cron every 20 min during market hours (Mon-Fri 09:00-14:40)"* |
| `idx_bsjp_watch.py` | **15:40 WIB, Mon-Thu** (Fri off — weekend gap) | line 12; guard `now.weekday() >= 4` → silent (line 169); window 15:40-16:00 (line 173) |
| `idx_ara_collect.py` | cron LLM job, silent when no hits | docstring |
| `idx_flow_collect.py` | no_agent cron, ~10 watchlist × 3 req + 1 screener = 31/run | lines 14-16 |
| `idx_track_record.py` | on-demand (--days N), posts to topic 616 | line 9 |

**Market clock** is centralized in `idx_clock` (`market_status`, `trading_day`, `now_wib`) — reused by scalp/BSJP.

### 2.3 Signal → entry → exit → journal flow

1. **Scan** — `idx_scalp_watch.scan_setups()` returns `(setups, ws_hits, yf_fallbacks)` and is explicitly *"Pure scan — TIDAK kirim, TIDAK dedup-mark, TIDAK journal"* (line 222-224).
2. **Coordinator** — before posting, `idx_coordinator.py --check-only` monitors open scalps & logs TP/SL hits (lines 371-382); `_dedup_filter()` skips recently-posted symbols (`--dedup`).
3. **Post** — `idx_delivery.send_confirmed(msg)` to Telegram `topic 616`.
4. **Journal + ledger** — `_mark_posted_and_journal()` runs **after send**: `idx_coordinator.py --mark-posted`, then `idx616_ledger.record_event(...)` (SQLite) and `idx_signal_journal.py` (XLSX, `--mode SCALPING`) (lines 313-351).
5. **Exit** — strategies exit differently: BSJP/ARA **at next-session open**; INTRADAY at TP1/TP2/SL/**TIMEOUT** (grader logs e.g. `[ws1m 69b] intraday timeout 15:49 @ 625 = -0.62R`).
6. **Grade** — `grader v3-ara-intraday` resolves outcomes; `idx616_grader_last.json` shows `{"events":401,"graded":{"bsjp":1,"ara":50,"intraday":0},"pending_wait_session":104,"ara_dup_suppressed":236}`.

### 2.4 Data files written

| File | Writer | Notes |
|---|---|---|
| `~/.hermes/idx-journal/idx_journal.xlsx` | `idx_signal_journal.py` | Sheet **"Jurnal IDX"**, 18 cols (Tanggal, Jam WIB, Session, Status, Emiten, Arah, Entry, SL, TP1, TP2, Size, Estim Modal, Alasan, Hasil, P/L%, Skor Disiplin, Catatan, **Mode**) |
| `/home/ubuntu/.hermes/cron/state/arjum_trades.db` | WS trade feed | `trades(price, lot, value_idr, ts, ticker)` read by scalp watcher |
| `idx616_signal_ledger.db` | `idx616_ledger.record_event` | Tables `signals` (628 rows), `candidates`, `evidence`, `schema_meta` |
| `~/.hermes/scripts/data/flow/<date>/<T>.json` | `idx_flow_collect.py` | Per-ticker broker + hist + accumulation |
| `…/data/flow/flow_latest.json` | `idx_flow_collect.py` | Combined snapshot |
| `…/data/flow/screener_latest.json` | `idx_flow_collect.py` | V5.2 screener snapshot (1 req, for dashboard, 0 req/view) |
| `~/.hermes/cron/logs/arjum_audit_<date>.jsonl` | `arjum_pool.py` | Per-call audit (hit/fetch/skip_low_quota/err) |
| `~/.hermes/cron/cache/arjum/*.json` | `arjum_pool.py` | Disk cache with `saved_at` TTL |
| `idx_universe.json` | (universe input) | Tickers list |

**`idx616_signal_ledger.db` schema (signals)** — the IDX analog of a trade ledger:
```
event_id TEXT PRIMARY KEY, job_id, created_at, ticker, setup, source, direction,
entry_low, entry_high, sl, tp1, tp2, status DEFAULT 'CREATED', filled_at, closed_at,
result, net_r, costs_r DEFAULT 0, data_source, freshness_s, duplicate_of, note,
producer, source_timestamp, graded_at, grader_version,
UNIQUE(job_id, created_at, ticker, setup)   <- idempotency
```
Parsed: producers `ara_hunter_ledger.py` (533), `idx_bsjp_watch.py` (50), `idx_scalp_watch.py` (45);
results mix `LOSS(122)/SL(31)/TIMEOUT(7)/TP1(35)/TP2(7)/WIN(76)`.

### 2.5 Key parameters

| Parameter | Value | Where |
|---|---|---|
| Scalp liquidity floor | `LIQUIDITY_MIN_IDR = 50_000_000_000` (50B) | `idx_scalp_watch.py:43` |
| Scalp ATR band | `ATR_MIN_PCT=0.8`, `ATR_MAX_PCT=6.0` | lines 44-45 |
| Vol / ATR spike | `VOL_SPIKE=1.5`, `ATR_SPIKE=1.5` | lines 46-47 |
| WS minimum trades | `WS_MIN_TRADES_PER_SYMBOL=5` (else yf fallback) | line 49 |
| Anti-blow-off | skip if `vol_ratio>=5.0 and atr_pct>4.0` (journal: vol≥5x WR 18%) | lines 261-265 |
| Scalp SL / TP | `sl = low_last*0.998`; `tp1 = entry+1R`, `tp2 = entry+2R` | lines 267-279 |
| BSJP filters | `CHG_MIN,CHG_MAX=2,25`; `VOL_VS_AVG=1.5`; `PRICE_MIN=100`; `VALUE_MIN=1e9`; `EXT_SMA10=1.03`; `STRONG_CHG=(6,12)` | `idx_bsjp_watch.py:28-33` |
| BSJP cost | `COST_PCT=0.40` %/round-trip | line 34 |
| BSJP exit levels | entry=close; `sl=e*0.975` (-2.5% kill-switch); `tp1=e*1.01`; `tp2=e*1.02` | lines 143-158 |
| ARA exit levels | `sl=c*0.975`; `tp1=c*1.01`; `tp2=c*1.02` | `idx_ara_collect.py:38-40` |
| Flow watchlist | 10 tickers: BBCA, BBRI, BMRI, BBNI, TLKM, ASII, ADRO, ANTM, UNTR, GOTO | `idx_flow_collect.py:34` |
| Arjum quota | `MIN_REMAINING=500` | `arjum_pool.py:40` |

### 2.6 Design lessons / pitfalls in comments

- **BSJP exit ≠ TP/SL** (`idx_bsjp_watch.py:142-143`): *"Exit BSJP = open T+1, bukan TP1/TP2"* — tp set to a +1% gap target, sl a −2.5% kill-switch before 09:00 (anti black-swan).
- **Friday off for BSJP** (lines 12, 169): *"Jumat libur BSJP — hindari gap weekend"*.
- **"Kingdom WR 79%" debunked** (`idx_bsjp_watch.py:7-9`): raw BSJP only +0.28% net; claimed 79% is a high-touch metric, not real profit. Filtered recipe nets +0.89%/trade @ ~48% WR across 3 walk-forward folds.
- **Baseline expectancy gate** (`idx616_drift.json`): per-strategy cluster gate requires `independen days>=20`, `expectancy>0.6R`, `WR>55%`, `max DD<4R`. At snapshot: BSJP passed 3/4 (mean_r 0.608), SCALP failed all, **ARA failed with mean_r −1.144, max_dd 206.34R → alerts "ARA: rolling-20 expectancy −0.75R (NEGATIF — edge mati?)"** and "CI95 cluster seluruhnya < 0".
- **Effective-N cluster correction** (`idx616_drift.json` note): *"efektif N=11 hari (bukan 35 trade — 1 hari = 1 event korelasi)"* — same-day trades are one correlated event, not independent samples.
- **Idempotent ledger** (`idx_ara_collect.py:8-9`): *"Ledger 616 ditulis DI SINI (setelah hits valid, sebelum LLM) — sinyal = event, grader v3 yang resolve outcome-nya. Idempotent via UNIQUE ledger."*
- **Dirty PnL recomputed deterministically** (`idx_track_record.py:112-113`): *"recompute pnl deterministically dari level (kolom pnl journal kotor)"*.
- **1-signal-1-outcome pairing** to survive duplicated EVAL rows from an old monitor bug (`idx_track_record.py:3-7`).
- **Suspense/IPO guard** (`idx_bsjp_watch.py:78`): consecutive zero volume = invalid → fallback to yfinance.
- **WS-first, yf-fallback** (scalp): real-time from `arjum_trades.db` (quota-free) with 5-min bucketing; yfinance only if <5 trades or stale >600s.

---

## 3. FOREX (XAUUSD + multi-pair)

### 3.1 Pipeline stages

**XAUUSD** is the primary forex/FX-commodity line. It has both a **daily 4-agent pipeline** and a **reactive 30-min watcher** that share the same SMC detectors.

`xauusd_pipeline.py` — **4-agent sequential orchestrator** (docstring lines 3-8):

| Agent | Function | Role |
|---|---|---|
| 1 SCANNER | `agent1_scanner()` | runs `xauusd_smc_data.py` packet (deterministic, no LLM); capped to 9000 chars for token budget |
| 2 SETUP | `agent2_setup()` | builds confluence-scored candidates from scanner + watchlist zones via `xauusd_reactive` engine |
| 3 NEWS | `agent3_news()` | hard veto rules: cutoff 19:30 WIB, weekend, Friday late session |
| 4 RISK | `agent4_risk()` | open positions, daily loss limit, sizing verdict |

**Reactive watcher** `xauusd_reactive.py`:
- Pulls live 1H + 15M from `tv_feed.py` (TVC:GOLD spot).
- For each watchlist zone, checks `candle_reaction_to_zone()` (body-in-zone + ≥40% rejection wick).
- Scores via `confluence_score()` → **6-point checklist** (lines 222-323): (1) top-down bias, (2) MTF structure, (3) POI OB/FVG/iFVG/trendline overlap, (3b) CISD bonus, (4) liquidity pool direction, (5) discount/premium on 4H range, (6) 1H volatility.
- `build_signal()` → LIMIT-only policy (never stop-entry), SL behind far side + 1×ATR, TP1=1R, TP2=2R (lines 404-446).

**Multi-pair** `multi_pair_signal.py` covers **XAUUSD (no-op, covered elsewhere), NAS100 (`CAPITALCOM:NAS100`), EURUSD (`OANDA:EURUSD`)**, reusing the same engine (`import xauusd_reactive as rx`).

**Data collector** `xauusd_smc_data.py` is the SMC packet builder (1W/1D/4H/1H/15M), including FVG, order blocks, liquidity levels, premium/discount, session ranges (Asia/London/NY), econ calendar, and blackout status.

### 3.2 Cron / schedule cadence

| Job | Cadence / window | Evidence |
|---|---|---|
| `xauusd_reactive.py` | **every 30 min, Mon-Fri 06:00-22:00 WIB** | line 9 *"Schedule: every 30 minutes during market hours (Mon-Fri 06:00-22:00 WIB)"* |
| Daily 4-agent signal | daily ~13:30 WIB (gate reference "daily 13:30") | `xauusd_reactive.py:155`, `xauusd_journal.json` entries at 13:32-13:35 |
| `multi_pair_signal.py` | per-pair session windows: XAU 13-19 (no-op), NAS100 21-03 (NY, crosses midnight), EURUSD 14-21 (London+NY) | `PAIRS` dict lines 53-57 |
| Blackout gate | ±30 min High / ±15 min Medium news window | `xauusd_reactive.py:575-589`, `multi_pair_signal.py:266-279` |

**Session discipline (rule v2, `xauusd_reactive.py:156-161`)**: no new entries in thin Asia hours; `SESSION_START_HOUR_WIB=13` (London open ~14:00, start 13:00), `SESSION_END_HOUR_WIB=19` with cutoff 19:30. Rationale: *"3 dari 4 signal jelek lama terjadi di jam Asia (00:00-13:00 WIB saat likuiditas tipis)."*

### 3.3 Signal → entry → exit → journal flow

1. **Scan** — morning outlook writes `xauusd_watchlist.json`; scanner emits SMC packet including blackout status.
2. **Reactive trigger** — watcher detects a candle reacting to a zone → `confluence_score` → must be `>= MIN_CONFLUENCE` (else SKIP + `scan_log` GATE_REJECT).
3. **Guards before signal**: (a) session filter, (b) **news blackout gate** (`news_calendar.blackout_status()`), (c) zone state (`in_zone` / `retest` / `mitigated`), (d) **failed-zone flip** — a zone price broke through this day gets `mark_zone_broken()` and same-side entry is blocked; it's `flip_zone()`'d to the opposite side (lines 344-401).
4. **Signal compose + send** — `build_signal()` (LIMIT-only), chart via `plot_signal.py`, Telegram photo to `topic 144` with entry/SL/TP1/TP2/BE caption. WATCH vs LIMIT vs in-zone captions differ (lines 486-498).
5. **Journaling** — signals go to `xauusd_journal.json` via `trade_journal.py add`; per-zone dedup uses **age-based** not calendar-date keys.
6. **Exit tracking** — `trade_journal.py track` resolves PENDING→ACTIVE→CLOSED against 15m TV candles.
7. **Stats** — `trade_stats.py` aggregates sessions, MAE/MFE excursions, backtest-vs-live drift, risk aggregator, and TTL expiry countdown.

### 3.4 Data files written

| File | Writer | Content |
|---|---|---|
| `~/.hermes/trading-journal/xauusd_journal.json` | `trade_journal.py` | `{"trades":[...]}` — schema below |
| `~/.hermes/trading-journal/multipair_journal.json` | `multipair_journal.py` | list of MP trade dicts (pair, entry, sl, confluence, status, notes) |
| `~/.hermes/state/xauusd_watchlist.json` | morning outlook / `--set-watchlist` | Zone list with `added`/`updated` stamps (persist across regen) |
| `~/.hermes/state/zone_state.json` | `xauusd_reactive.py` | Zone broken/mitigated state (`broken`, `broken_px`, `broken_at`) |
| `~/.hermes/trading-journal/charts/reactive_YYYYMMDD_HHMM.png` | `plot_signal.py` | Signal chart image |
| `~/.hermes/state/multi_pair_signals.json` | `multi_pair_signal.py` | Dedupe state (age-based) + daily flip quota |
| `~/.hermes/state/trade_excursions.json` | `trade_stats.py` | Cached MAE/MFE in R per trade |
| `~/.hermes/cache/ff_calendar_thisweek.json` | `xauusd_smc_data.py` | Forexfactory weekly calendar (cache ≤6h) |
| scan_log (via `scan_log` module) | watchers | Structured per-scan reason for dashboard |

**XAUUSD journal trade schema** (from `xauusd_journal.json`): `id`, `created_utc`, `date_wib`, `side`,
`entry`, `sl`, `tp1`, `tp2`, `be`, `price_at_signal`, `risk_points`, `rr_tp1`, `rr_tp2`, `bias`, `poi`,
`session`, `style`, `status` (PENDING/ACTIVE/CLOSED/CANCELLED), `filled_utc`, `resolved_utc`, `outcome`
(TP2/TP1/SL/BE/NO FILL/EXPIRED), `r_multiple`, `max_favorable_r`, `be_armed`, `notes[]`.

**Real journal contents parsed**: 5 trades, outcomes `SL (−1.0R)`, `TP2 (+2.0R, be_armed true)`, `NO FILL (0.0R)`,
`SL (−1.0R)`, `SL (−1.0R)`. `meta` confirms *"Strategy reset v2 (21 Sep 2026). Rule: gate 5/6, BE trigger 1.2R, TP1 partial 50%, sesi 13:00-19:30 WIB"* and `previous_stats` = 9 signals, 20% WR, +0.32R, buy 0W/4L.

**`multipair_journal.json` parsed**: 11 records; outcomes `INVALID/CANCELLED`, `SL (−1.0R)`, `MANUAL (+1.5R)`, etc. Documents the **dedupe bug** ("Baris duplikat 28 Sep 00:00 dihapus — sinyal sama terkirim 2x karena bug dedupe (key bertanggal + datetime.datetime AttributeError)") and the **outside-active-hours problem** (signals at 23:00/01:00 WIB missed while user asleep, e.g. NAS100 +2R not taken).

### 3.5 Key parameters

| Parameter | Value | Where |
|---|---|---|
| Min confluence gate | `MIN_CONFLUENCE = 2` (rule v2.1, 22 Sep — lowered from 5/6→4/6→2/6) | `xauusd_reactive.py:155` |
| Max risk mult | `max_risk_mult = 1.5` × ATR (zone too wide → reject) | lines 404, 432 |
| SL buffer | 1 × ATR(1H) behind far side of zone | lines 429, 437 |
| TP rule | TP1 = 1R, TP2 = 2R; BE at entry | lines 434-435 |
| BE trigger | **at TP1** (rule v3, 26 Sep; was 1.2R in v2) | `trade_journal.py:22-25,48` |
| Pending TTL | `PENDING_TTL_HOURS = 24` (no fill → CANCELLED) | `trade_journal.py:42` |
| Active TTL | `ACTIVE_TTL_HOURS = 48` (neither level → EXPIRED) | line 43 |
| Risk per trade | 1% normal / 0.5% event-caution; `RISK_PER_TRADE_PCT = 0.5` for stats | `xauusd_pipeline.py:126`, `trade_stats.py:35` |
| Daily loss stop | `daily_r <= -1.5` → no new entries | `xauusd_pipeline.py:124` |
| Max exposure | `MAX_OPEN_TOTAL=2`, `MAX_OPEN_PER_PAIR=1` | `trade_stats.py:36-37` |
| Multi-pair dedupe | `DEDUPE_HOURS = 12` (age-based, not calendar) | `multi_pair_signal.py:41` |
| Multi-pair ATR floor | `MIN_ATR_PCT = 0.0015` (0.15% of price) | line 47 |
| Flip-zone guards | `MIN_CONFLUENCE_FLIP = 4`; `MAX_FLIP_PER_PAIR_PER_DAY = 1` | lines 50-51 |
| Blackout | High ±30 min, Medium ±15 min | `xauusd_smc_data.py:483` |
| Calendar cache | `CAL_MAX_AGE = 6*3600` | line 254 |
| Backtest ref | XAUUSD 15tr/73%/+11.1R; NAS100 10tr/60%/+8.0R; EURUSD 10tr/90%/+8.4R | `trade_stats.py:42-49` |

### 3.6 Design lessons / pitfalls in comments

- **Two standards for the same setup (1 Sep 2026, `xauusd_reactive.py:100-107,149-155`)**: the 09:00 reactive watcher fired a **2/6** setup; the 13:30 daily run scored the same entry 2/6 and called it weak. Fix: both runs share the SAME `confluence_score` and the SAME `MIN_CONFLUENCE` bar.
- **BE must equal entry, armed at TP1** (v3, lines 22-25 of `trade_journal.py`): v2 waited for 1.2R; changed to arm BE exactly at TP1. Consistent caption fix 28 Sep (`multi_pair_signal.py:187-189`: *"caption lama nulis 'TP1 -> BE arm' yang kebaca seolah BE aktif tepat di TP1 — sumber kontradiksi"*).
- **LIMIT-only policy (25 Sep 2026, `xauusd_reactive.py:406-417`)**: *"TIDAK ADA stop-entry. Buy stop / sell stop keisi tepat di ujung ekstrem breakout — kalau breakout-nya palsu, harga round-trip langsung ke SL."*
- **Failed-zone flip** (`xauusd_reactive.py:361-386`): *"jangan dipaksa untuk entry searah dengan zona yang sudah ditembus; takutnya cuma retest lalu lanjut -> kena SL"* (user, 25 Sep).
- **Conservative outcome model** (`trade_journal.py:18-26`): if a single candle contains both SL and a TP, **assume SL hit first** — *"assuming the good outcome would inflate the win rate."*
- **BE accounting bug** (`trade_journal.py:218-224, 245-259`): old code always used the original SL then labelled "BE"; trades that reversed to entry but hadn't hit original SL stayed ACTIVE, and trades that hit original SL reported 0R despite locked TP1 partial. Fixed: effective stop follows BE state; runner stopped at BE after TP1 = **+0.5R**, not 0R.
- **TP2 partial-accounting fix** (lines 271-276): old code wrote full `rr_tp2` (2.0R) → inflated results by 0.5R per TP1; correct effective TP2 = `(rr_tp1 + rr_tp2)/2`.
- **NO FILL ≠ trade** (`trade_journal.py:391-397`): *"Bug: outcome NO FILL (r=0.0) ikut masuk daftar BE -> WR jadi 33% padahal dari trade nyata 1W/1L = 50%."*
- **`fromisoformat(None)` crash** (lines 306-311): filled_utc can be NULL for manual entries → TypeError killed the whole tracker (bug 25 Sep).
- **Dedupe bug (28 Sep, `multi_pair_signal.py:242-255, 350-354`)**: `from datetime import datetime` makes `datetime` a CLASS; `datetime.datetime.fromisoformat` → AttributeError swallowed → dedupe silently dead. Also date-keyed dedupe let identical signals through at midnight → switched to age-based.
- **ATR-min filter (28 Sep, lines 42-47)**: EURUSD 28 Sep ATR 1H = 0.104% of price → two signals, both SL. Threshold 0.15% filters both losers without dropping XAU/NAS100 winners.
- **Weekly/Daily basis lesson** (`xauusd_smc_data.py:14-16`): originally used COMEX GC=F futures sitting 50-60 pts above spot (contango) needing error-prone basis subtraction → switched to TVC:GOLD spot, *"every level printed here is directly usable on the broker chart."*
- **TradingView scanner needs `curl_cffi` impersonate** (`idx_bsjp_watch.py:52-53`) — TV blocks plain requests.
- **`tv_feed` returns only the LAST bar, not a range** (`trade_stats.py:178-182`): so bar counts must cover the span from now to fill time; >10 days of 15m data unavailable.

---

## 4. Cross-market comparison

| Dimension | Crypto | IDX | Forex (XAUUSD) |
|---|---|---|---|
| Primary data source | Binance fapi (curl) + whale_scan | Arjum REST (pooled) + TradingView scanner + yfinance | TradingView TVC:GOLD via `tv_feed.py` |
| Execution | **Real** (MEXC limit + fill-monitor daemon) | Signal-only (manual) | Signal-only (manual) |
| Journal | `crypto_journal.xlsx` + watchlist JSON + equity ledger | `idx_journal.xlsx` + `idx616_signal_ledger.db` + flow JSON | `xauusd_journal.json` + `multipair_journal.json` |
| Earliest cadence | hourly eval + 10-min HL whale | 20-min scalp | 30-min reactive |
| Gate | 2-of-4 POI + 1 confirmation | Strategy filters (chg/vol/ADX) + drift gate | confluence ≥ 2/6 |
| TP model | TP1=1R, TP2=2R intraday | BSJP/ARA: next-open exit; INTRADAY: 1R/2R | TP1=1R, TP2=2R |
| Partial/BE | TP1 → 50% + BE | INTRADAY: BE; BSJP: −2.5% kill-switch | TP1 → 50% + BE (v3) |
| Timeouts | PENDING TTL folded into hourly eval | intraday TIMEOUT | PENDING 24h, ACTIVE 48h |
| Idempotency | `auto_executed` flag + state JSON | UNIQUE ledger constraint | age-based dedupe |

---

## 5. Top cross-cutting lessons (for a successor system)

1. **Silent-cron + explicit alerts**: collectors stay quiet unless actionable; every state change or failure that
   touches money (no-SL position, BE failure) is *forced* to print — *"APA PUN hasilnya harus dilaporkan"* (`crypto_watch_eval.py:70-77`).
2. **Journal = single source of truth** across sub-systems; dedupe, exposure, and conflict checks all read it.
3. **Risk first, sizing derived from stop distance** — never from a fixed notional that collapses to lot granularity.
4. **Validate every order on the exchange**, re-read position before each retry (stale-state bug cost a naked XAU/XRP position).
5. **Conservative outcome accounting** — same-candle SL+TP ⇒ SL; partial fills accounted at half weight; NO FILL excluded from WR.
6. **Correlation-aware statistics** — cluster by day; effective N << trade count; gate on expectancy + drawdown, not raw WR.
7. **Age-based dedupe, not calendar-date**, and never let a swallowed exception silently disable a dedupe/watchdog (`datetime.datetime` bug).
8. **Guard the entry geometry** — never place a limit into a zone price has already broken ("limit keisi instan ke pasar yang jatuh"); flag it WATCH instead.
9. **Zone lifecycle tracking** — mitigated/broken zones flip side; same-side re-entry into a failed zone is blocked.
10. **Session + news blackout filters** remove the majority of bad trades (thin Asia hours, ±30 min high-impact releases).
