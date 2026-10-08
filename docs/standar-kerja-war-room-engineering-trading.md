# Standar kerja War Room: engineering production-grade + trading research

Tanggal studi: 2026-10-08 UTC
Status: dokumen belajar awal; bukan izin deploy, live trading, atau rekomendasi aset.

## Ringkasan eksekutif

War Room perlu diperlakukan sebagai dua sistem yang saling terhubung tetapi tidak boleh dicampur:

1. **Software production system** — requirement, kontrak data, UI, API, keamanan, operasi, observability, release, rollback.
2. **Research/execution system** — hipotesis, observasi, signal, keputusan, paper execution, evaluasi trade, dan promosi yang digate.

Aturan penghubungnya: software boleh menerbitkan hanya apa yang dapat dibuktikan oleh data; research boleh menggunakan hanya data dengan provenance, timestamp, populasi, dan aturan eksekusi yang eksplisit.

## Track A — Cara senior web engineer bekerja

### 1. Discovery sebelum coding

Senior engineer memulai dari:

- siapa user dan keputusan apa yang harus dibuat;
- scope in/out;
- functional requirements;
- non-functional requirements: latency, availability, security, auditability;
- data classification dan role matrix;
- acceptance criteria dan failure states;
- asumsi yang belum terbukti.

Output minimum: brief satu halaman, glossary, state machine, API/data contract, risk register, dan release gate.

### 2. Arsitektur dan kontrak

Urutan kerja:

1. domain model dan lifecycle state;
2. source of truth per field;
3. OpenAPI/schema contract;
4. ownership antar frontend/backend/worker;
5. storage dan retention;
6. sync vs async boundary;
7. observability dan rollback.

Jangan membuat microservice hanya karena terlihat senior. Mulai dari boundary domain yang jelas; pecah service ketika ownership, scaling, failure isolation, atau deployment cadence memang berbeda.

Untuk War Room, boundary yang sehat:

- **facts/source layer**: raw observation, source, observed_at, TTL, hash;
- **research layer**: hypothesis, signal, feature set, split, backtest/replay;
- **execution layer**: candidate, accepted, open, closed, expired, paper/live;
- **policy/gate layer**: risk limits, promotion verdict, owner approval;
- **presentation layer**: read-only rendering, no silent statistical recomputation.

### 3. Frontend senior

Prinsip:

- mulai dari information architecture dan user decision, bukan komponen;
- satu accent dan token system yang konsisten;
- state adalah bagian dari UI: loading, empty, stale, degraded, error, unauthorized, forbidden;
- angka selalu bersama unit, timestamp, source, population, dan status;
- keyboard/focus/semantic headings/landmarks sejak awal;
- performance diukur dari rendered user path, bukan perasaan;
- frontend tidak menjadi sumber kebenaran domain.

Checklist War Room:

- Home menjawab: kandidat, promotable, posisi paper, stale/degraded source, risk breach;
- market page memisahkan observation, candidate, open, closed, paper, historical, live;
- `—` berarti absent/unknown, bukan nol;
- `fresh/stale/degraded/unknown` terlihat di surface yang memakai data;
- setiap headline verdict berasal dari backend canonical verdict;
- mobile/tablet/desktop dan keyboard diuji;
- loading shell tidak menutupi UI bila hydration gagal.

### 4. Backend/API senior

Standar:

- kontrak versi dan OpenAPI;
- validasi request body, query, path, enum, range;
- error format konsisten tanpa membocorkan secret/internal detail;
- authn dan authz di setiap route, termasuk object-level access;
- pagination/limit/rate limit untuk list dan expensive operations;
- idempotency untuk write/retry;
- transaksi dan migration teruji;
- provenance field wajib untuk data yang memengaruhi keputusan;
- API membaca domain facts; jangan diam-diam menghitung ulang angka berbeda dari engine;
- audit log untuk perubahan policy, grants, freeze, apply, rollback.

Kontrak fakta minimum:

```text
fact_id
kind
key
value
source
observed_at
ttl_s
status
hash
verification_state: measured | assumed | absent
```

Kontrak research minimum:

```text
hypothesis_id
market
instrument_or_pool
rule_version
input_fields
lookahead_policy
cost_policy
session_timezone
entry_rule
exit_rule
stop_rule
position_sizing
baseline
train_test_or_walk_forward_split
population
verdict
```

### 5. Security dan supply chain

Pakai ASVS sebagai checklist aplikasi, NIST SSDF sebagai lifecycle, dan jangan menganggap TLS/header sebagai seluruh security.

Minimum:

- cookie Secure, HttpOnly, SameSite;
- password hashing modern dan rate limit login;
- RBAC + IDOR tests;
- CSRF strategy untuk cookie writes;
- strict input/path validation;
- SQL/command/template injection defenses;
- secrets di vault/environment, tidak di chat/repo/log;
- dependency lock + audit;
- CSP tidak boleh duplicate dengan hash berbeda;
- audit trail untuk state-changing operations;
- backups diuji restore, bukan hanya dibuat.

### 6. DevOps/SRE senior

Setiap release punya:

1. CI lint/type/test/build;
2. artifact/build identity;
3. backup atau rollback point;
4. deploy through runbook;
5. health check process + served asset;
6. smoke API/auth/security headers;
7. rollback command yang nyata;
8. post-deploy observation window.

Operasi memakai SLO/error budget, bukan sekadar `systemctl active`:

- availability;
- p95 latency;
- error rate;
- stale source rate;
- job success/failure;
- queue lag;
- DB health/backup age;
- event stream liveness;
- deploy frequency, lead time, change failure rate, recovery time.

Untuk War Room: paper/live NO-GO harus menjadi policy machine-checkable, bukan hanya label UI.

## Track B — Cara trader senior bekerja

### 1. Trader tidak memulai dari entry price

Urutannya:

1. market/regime/context;
2. thesis atau hypothesis;
3. observable trigger;
4. invalidation;
5. entry condition;
6. stop/exit/target;
7. size berdasarkan risk budget;
8. expected cost/slippage/liquidity;
9. execution path;
10. journal dan post-trade review.

Setup lengkap harus bisa ditulis sebelum trade:

```text
Jika kondisi X terukur terjadi pada waktu t,
maka entry hanya bila Y,
stop/invalidation Z,
target/exit rule Q,
size = risk_budget / loss_per_unit,
biaya maksimum C,
dan trade batal bila data stale atau liquidity tidak cukup.
```

### 2. Taxonomy metode

- **Technical/trend**: momentum, breakout, moving-average, volatility regime.
- **Mean reversion**: deviation from fair/reference range, requires regime filter.
- **Structure/price action**: support/resistance, market structure, order block/FVG; must define objectively.
- **Fundamental**: earnings, valuation, cash flow, token value capture, macro.
- **Order flow**: volume, delta/CVD, broker flow, OI/funding, book imbalance; timestamp alignment is critical.
- **On-chain**: holder flow, wallet clusters, LP changes, liquidity, contract risk; address attribution is uncertain until proven.
- **Event-driven**: announcements, resolution, earnings, unlocks, macro events; define event timestamp and information availability.
- **Market making/LP**: spread/fee income versus inventory risk, adverse selection, IL, range inactivity.
- **Discretionary**: human pattern recognition; must still journal decision and invalidation.
- **Systematic**: deterministic features/rules; must control leakage and multiple testing.

Metode berbeda tidak boleh digabung menjadi satu score tanpa menguji apakah denominator, horizon, cost model, dan objective-nya sama.

### 3. Per-market differences

#### Crypto spot/perpetual

Wajib perhatikan:

- venue/pair/contract identity;
- funding, OI, liquidation, basis;
- 24/7 session definition;
- taker/maker fee, slippage, latency, gaps/liquidation;
- token liquidity and contract risks;
- spot versus perp return basis.

#### DEX/LP

Metrik bukan cuma token price:

- pool and chain identity;
- active liquidity/range bins;
- fee income;
- inventory composition;
- impermanent loss versus hold benchmark;
- rebalancing/gas/failed transaction cost;
- oracle/price source reconciliation.

Meteora position out-of-range berarti liquidity position tidak aktif pada range itu; bukan automatic buy/hold signal.

#### Forex

Wajib bedakan:

- spot/CFD/futures/broker feed;
- session/timezone;
- spread, commission, swap/financing;
- news blackout and slippage;
- pip value and contract size;
- overnight gap and broker execution.

A journal dengan 4 trade tidak menjadi evidence edge hanya karena win rate terlihat.

#### Saham Indonesia

Wajib bedakan:

- exchange data/provider/cache;
- session open/close, auction, tick size, lot size;
- T+ settlement and corporate actions;
- broker flow attribution;
- gap risk and limit-up/limit-down;
- survivorship universe and delisted names;
- fees, taxes, slippage, partial fills.

IDX strategy yang stop tidak bisa dieksekusi pada gap harus memakai risk model yang mengakui loss tail, bukan label “maksimal 1R”.

#### Prediction market

Wajib bedakan:

- probability/price versus expected value;
- market resolution rules;
- liquidity and spread;
- complement/related markets;
- fee and settlement;
- order fill versus quoted price;
- stale odds and latency;
- frozen split and calibration.

Win rate saja tidak cukup; compare Brier/log loss, calibration, expected value net fees, and resolution correctness.

### 4. Risk and sizing

Position size bukan input tetap yang dipaksakan ke semua market.

```text
risk_amount = capital * risk_fraction
loss_per_unit = entry_to_invalidation + fees + expected_slippage + gap_buffer
size = risk_amount / loss_per_unit
```

Guardrails:

- max risk per trade;
- max correlated exposure;
- max open positions;
- max daily/weekly loss;
- liquidity/market impact cap;
- stale-data rejection;
- kill switch;
- no-trade conditions;
- tail-risk override for gaps/liquidation.

### 5. Mengubah postingan Threads menjadi hypothesis

Template:

```text
Claim verbatim:
Instrument/venue/pool:
Timestamp and timezone:
Actor/signal named:
Trigger observable at t:
Entry rule:
Exit rule:
Stop/invalidation:
Cost/slippage assumption:
Baseline:
Horizon(s):
Universe:
Required historical fields:
Falsification condition:
```

Contoh “wallet penjaga harga”:

- bukan langsung label bullish;
- define wallet cluster by repeated behavior;
- define support-like action and time window;
- compare forward returns against matched random timestamps and no-cluster tokens;
- test whether address is insider/LP/bot/wash-trade candidate;
- report event frequency and false positives;
- verdict vocabulary: `terbukti`, `tidak-terbukti`, `perlu-uji-tambahan`, `tidak-ada-sinyal`.

### 6. Research protocol

1. Freeze claim and rule version.
2. Enumerate raw records and field shapes.
3. Freeze universe and timestamps.
4. Split train/validation/test or walk-forward.
5. Use only information available at decision time.
6. Include fees, spread, slippage, latency, partial fill, gap, and rejected order rules.
7. Compare baseline and counterfactual.
8. Report all chosen horizons, not best horizon.
9. Report trigger frequency and denominator.
10. Run sensitivity analysis.
11. Record invalidation before seeing result.
12. Keep research output separate from production signal.
13. Promote only after independent holdout and owner approval.

### 7. Bias checklist

- lookahead bias;
- survivorship bias;
- selection/cherry-pick bias;
- data snooping/multiple testing;
- regime bias;
- stale quote bias;
- execution/fill bias;
- fee/slippage omission;
- timestamp/timezone mismatch;
- address attribution overconfidence;
- denominator switching;
- open trade counted as closed;
- simulated balance treated as real money.

## Combined operating model for War Room

### State machine

```text
observed
  → candidate
  → evaluated
  → accepted_for_paper
  → open_paper
  → closed_paper
  → validated
  → promotable
```

Any state can go to:

```text
stale | degraded | blocked | invalidated | expired
```

`promotable` requires evidence gate; it is never inferred from score, headline, or AI narrative.

### Definition of done for a new strategy

- strategy brief and hypothesis;
- exact feature definitions;
- dataset/source inventory;
- timestamp/session rules;
- frozen universe/split;
- baseline and counterfactual;
- cost/execution model;
- risk/sizing policy;
- replay/backtest artifact;
- test coverage;
- UI labels for evidence state;
- audit trail;
- rollback/removal path;
- owner decision.

### 30-day learning/build sequence

**Week 1 — engineering standard:**
- turn this document into ADR/checklists;
- map current War Room against requirements, contracts, security, SLO, rollback;
- fix only P0/P1 gaps.

**Week 2 — research standard:**
- create one common hypothesis schema;
- create one common trade/event schema;
- add baseline/counterfactual/cost/invalidation fields;
- keep all strategies research-only.

**Week 3 — one vertical research slice:**
- select one data-complete market and one hypothesis;
- run frozen replay + walk-forward;
- compare baseline and costs;
- publish no signal unless gate passes.

**Week 4 — verification:**
- review false positives and regime split;
- run security/UX/data QA;
- decide continue, reject, or archive;
- do not expand markets until the slice is reproducible.

## Sources studied

Engineering:

- OWASP ASVS: https://owasp.org/projects/asvs
- W3C WCAG 2.2: https://w3.org/WAI/standards-guidelines/wcag/new-in-22
- MDN Web Performance: https://developer.mozilla.org/en-US/docs/Web/Performance
- OpenAPI 3.1: https://spec.openapis.org/oas/3.1.1.html
- Google SRE Workbook: https://sre.google/workbook/monitoring/
- DORA metrics: https://dora.dev/guides/dora-metrics/
- NIST SSDF: https://csrc.nist.gov/pubs/sp/800/218/final

Markets/research:

- CFA Institute backtesting: https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/backtesting-and-simulation
- CME position/risk management: https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
- Meteora DLMM dynamic positions: https://docs.meteora.ag/core-products/dlmm/dynamic-positions
- IDX data services: https://www.idx.co.id/en/products/idx-data-services/
- IDX trading mechanism: https://www.idx.co.id/en/products-services/trading-hours-and-mechanism/
- KSEI settlement: https://www.ksei.co.id/en/service-support/service-type/settlement-of-securities-transactions-services
- Polymarket resolution: https://docs.polymarket.com/concepts/resolution
- Polymarket CLOB: https://docs.polymarket.com/developers/CLOB/introduction

## Current limits

This is an initial standards study, not a complete literature review. It does not prove any trading strategy, does not authorize live trading, and does not replace market-specific legal/compliance review. All War Room strategy outputs remain PAPER/RESEARCH until their evidence gates pass.
