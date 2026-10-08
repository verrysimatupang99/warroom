# Crypto/MEXC SMC + Fibonacci Smart Golden Pullback v1

Status: deterministic implementation, paper-only.

## Pipeline

```text
MEXC/Binance public candles
→ SMC structure
→ liquidity sweep
→ Fibonacci retracement zone
→ confirmation
→ unified Signal
→ shared Risk Gate
→ PaperExecutor
```

## Defaults

- Golden zone: `0.618` through `0.786` of the impulse retracement.
- Minimum reward/risk: `2.0R`.
- Long: bullish structure, bullish liquidity sweep, confirmation, price inside zone.
- Short: bearish structure, bearish liquidity sweep, confirmation, price inside zone.
- Stop: opposite impulse swing.
- Target: entry ± `minimum_rr × risk`.
- No setup is emitted when any required deterministic gate is missing.

The zone and R multiple are configuration defaults, not a performance claim. They must be
recorded with each signal once the strategy is wired into the worker ledger.

## Inputs

The strategy needs:

- confirmed swing low/high;
- current price;
- structural bias;
- direction-specific liquidity sweep;
- deterministic candle confirmation;
- venue timestamp/freshness.

## Outputs

A setup contains:

- direction;
- entry;
- stop;
- target;
- risk/reward;
- golden zone bounds;
- reason string naming the exact gates.

## Not yet promotion evidence

This module does not claim an edge. It still requires worker wiring, live candle freshness,
paper fills with conservative fee/slippage, and the agreed 30-day forward validation before
any staged-live decision.
