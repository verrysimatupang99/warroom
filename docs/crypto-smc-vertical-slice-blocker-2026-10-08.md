# Crypto SMC vertical slice — evidence availability audit

Date: 2026-10-08 UTC  
Scope: Crypto SMC paper/research vertical slice only. No live, deployment, Tencent, or Polymarket writes.

## Verdict

**`blocked_evidence` — do not run a replay or claim an SMC result.**

The repository contains SMC implementation code and paper/operational outcome ledgers, but not a joinable, frozen historical evidence set with raw candles/features, candidate identity, executable entry evidence, and outcomes for the same rows. The available files are useful for schema discovery and contract preparation, not for an auditable replay.

## Evidence inspected

| Artifact | Observed coverage | Fields present | Decision use |
|---|---:|---|---|
| `packages/live-trading/crypto/journal/crypto_journal.xlsx` | 40 non-empty rows: 33 `SIGNAL`, 7 no-trade (`NO TRADE`/`NO_TRADE`); dates 2026-08-25 through 2026-09-27 | `Tanggal`, `Jam WIB`, `Status`, `Pair`, `Arah`, `Entry Est.`, `SL Est.`, `TP1 Est.`, `TP2 Est.`, `Funding %`, free-text `Alasan / Bias MTF`, `Hasil`, `P/L %`, `Skor Disiplin` | Candidate journal only. `Hasil`, `P/L %`, and `Skor Disiplin` are populated on 8/40 rows; 32/40 lack outcomes. No raw candles, quote timestamps, depth, fills, fees, slippage, or deterministic candidate IDs. Pair naming is inconsistent (`BTC_USDT`, `BTCUSDT`, `LINK`, `MULTI`, etc.). |
| `packages/live-trading/crypto/state/crypto_equity.jsonl` | 30 closed/expired rows; 2026-09-22 through 2026-10-09 | `signal_id`, `pair`, `direction`, `closed_at`, `status`, `r`, `note`, `source`, `logged_at` | Outcome ledger only. 28/30 have an `r`; 2/30 have missing/null `r`. It has no entry, stop, target, candidate feature snapshot, decision timestamp, quote, fee, slippage, or source-row join key. Notes can contain manually described outcomes and fallback status-derived R. |
| `packages/live-trading/src/live_trading/signals/smc.py` | deterministic implementation | candle shape `{t,o,h,l,c,v}`; swing points, EMA/structural bias, order blocks, FVGs, liquidity sweeps, POIs | Code/schema evidence only. No persisted historical input dataset is bundled. |
| `packages/live-trading/crypto/scripts/crypto_signal_collect.py` and `crypto_pipeline_collect.py` | live/public fetchers | Binance perp price, 24h ticker, book ticker, funding, OI, 1h/4h/1d klines, order-flow and positioning fields | Current-fetch pipeline, not a frozen historical export. Running it would create a new observation, not recover historical evidence, and is outside this audit's research-only scope. |
| `packages/live-trading/src/live_trading/execution/paper.py` | contract/schema | paper position fields include entry/SL/TP/size, timestamps, optional cost bps; closed ledger emits signal/pair/direction/close/status/R/source | Paper execution contract exists, but the existing ledger rows do not preserve the SMC candidate snapshot or all-in cost evidence needed for replay. |
| `packages/core/src/warroom_core/specs.py` and `docs/research-contracts.md` | contract definitions | required hypothesis and execution fields, explicit baseline/split/cost/lookahead policies | Research contract is available and should gate the next export. |

## Exact availability findings

### Available

- SMC feature vocabulary and deterministic implementation: candle timestamp/open/high/low/close/volume, swing points, structural/EMA bias, order blocks, FVGs, sweeps, and POIs.
- Candidate-journal fields for estimated entry/SL/TP1/TP2, direction, funding, and free-text MTF rationale on 37/40 rows.
- A paper outcome ledger with 30 rows and stable `signal_id` values.
- Outcome status and close timestamp on all 30 ledger rows; source labels on all 30 rows.

### Not available or not joinable

- **Raw historical candles:** no persisted OHLCV series with timestamps for the journal or ledger rows.
- **Feature snapshots:** no structured SMC features (bias per timeframe, POI type/zone/freshness, sweep/FVG/OB evidence) per candidate; rationale is unstructured text only.
- **Candidate identity join:** journal has no `signal_id`; ledger has no journal row/source-row reference. Pair spelling also differs.
- **Executable entry evidence:** no quote timestamp, bid/ask, selected price, depth, fill/no-fill rule, or latency for accepted candidates.
- **Cost evidence:** no fee rate/amount or slippage per row; `cost_bps` is optional in code but absent from the inspected ledger rows.
- **Outcome completeness:** journal outcomes are present for only 8/40 rows; ledger has 2/30 missing R values and does not identify the corresponding candidate inputs.
- **Frozen provenance:** no manifest binding files, row counts, hashes, schema version, freeze cutoff, or train/validation/holdout membership for a replay dataset.
- **Baseline inputs:** no row-level no-trade or market-implied counterfactual using the same timestamps and costs.

## Why the slice is blocked

A replay would require inventing joins, reconstructing candles from current APIs, treating free-text/manual statuses as structured labels, or assuming costs and fills. That would not be evidence-locked and could manufacture an SMC edge. Existing paper R totals are not a replay result and must not be promoted as one.

## Required next gate

Create a **read-only staging export** (no raw production access required) containing:

1. `manifest.json`
   - `dataset_id`, `schema_version`, `generated_at`, `freeze_epoch`;
   - source files with `path`, `rows`, `bytes`, `sha256`;
   - explicit `splits` for `train`, `validation`, and `holdout`.
2. `crypto_smc_candidates.jsonl`, one row per candidate/no-trade decision, with:

```text
candidate_id, signal_id, pair, venue, timeframe_set,
decision_ts, candle_cutoff_ts, entry_ts, exit_ts,
partition, direction, status, entry, stop, tp1, tp2,
smc_bias_1d, smc_bias_4h, smc_bias_1h,
poi_kind, poi_low, poi_high, poi_fresh,
sweep_kind, fvg_state, ob_state,
price_at_decision, bid, ask, depth, quote_ts,
fill_status, latency_ms, fee_rate, fee_usd, slippage_bps,
gross_r, net_r, outcome, outcome_ts,
baseline_net_r, source_file, source_row, parser_version
```

3. `crypto_smc_candles.jsonl` (or a content-addressed parquet/CSV equivalent), keyed by `candidate_id` or `(pair, timeframe, candle_ts)`, with:

```text
pair, venue, timeframe, candle_ts, open, high, low, close, volume,
source_file, source_row, parser_version
```

The aggregator must print, without raw payloads or secrets: total rows, unique IDs, duplicate count, timestamp range, split counts, missing counts for every required field, candidate-to-outcome join coverage, gross/net/baseline totals, and fee/slippage coverage.

## Admission criteria after export

Do not enter replay until all are true:

- manifest hashes validate and the split/cutoff are frozen;
- candidate IDs are unique and join coverage is reported;
- raw candle coverage is complete through the decision cutoff, with no lookahead;
- accepted candidates have executable quote/fill and all-in-cost fields, or are explicitly excluded by a deterministic no-trade rule;
- outcomes are resolved from a documented source and linked to candidate IDs;
- baseline and paper execution rules are represented on the same rows;
- no required field is silently imputed.

Then run the paper replay on the frozen holdout only, report denominator/coverage/missingness/gross-vs-net/baseline delta/CI, and keep promotion and live status **NO-GO**.

## Registration state

```json
{
  "vertical": "crypto",
  "strategy": "smc",
  "status": "blocked_evidence",
  "research_only": true,
  "raw_historical_fields_available": false,
  "outcomes_available": "partial_unjoinable",
  "replay": "blocked",
  "promotion": "blocked",
  "live": "NO-GO",
  "next_gate": "frozen_read_only_crypto_smc_export"
}
```
