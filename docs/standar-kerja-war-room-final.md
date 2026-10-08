# Standar Kerja War Room — Engineering Production + Trading Research

**Status:** hasil studi gabungan enam track paralel  
**Tanggal:** 2026-10-08 UTC  
**Scope:** engineering website production-grade dan research/execution lintas market.  
**Batas:** bukan izin live trading, bukan rekomendasi aset, dan bukan klaim bahwa strategi tertentu profitable.

## 1. Prinsip inti

War Room adalah dua sistem yang terhubung tetapi tidak boleh dicampur:

1. **Software production system:** requirements, contracts, UI, API, security, deployment, observability, recovery.
2. **Research/execution system:** hypothesis, data, signal, decision, execution, outcome, validation, promotion.

Aturan penghubung:

> Software hanya boleh menerbitkan apa yang dibuktikan datanya. Research hanya boleh memakai data dengan provenance, timestamp, populasi, aturan biaya, dan execution model yang eksplisit.

Pemisahan wajib:

```text
observed      = fakta yang diambil dari sumber
interpreted   = transformasi/analisis
simulated     = paper/replay
validated     = lolos gate statistik dan robustness
promotable    = boleh dipertimbangkan untuk tahap berikutnya
live          = capability terpisah, tetap NO-GO tanpa owner grant
```

## 2. Senior engineering workflow

### Fase A — Discovery

Sebelum coding, tulis:

- problem statement;
- user dan keputusan yang dibuat;
- scope in/out;
- functional dan non-functional requirements;
- sumber data dan trust level;
- role/permission matrix;
- failure states;
- security/privacy impact;
- acceptance criteria;
- assumptions/open questions;
- Definition of Ready dan Definition of Done.

Requirement harus dapat diuji. Contoh:

> Jika fakta melewati TTL, UI menampilkan stale, observed_at, age, dan tidak menghasilkan signal baru.

### Fase B — Architecture

Output minimum:

- context/component diagram;
- data flow;
- domain lifecycle;
- API/event contract;
- ownership antarkomponen;
- threat model;
- capacity estimate;
- failure modes;
- deployment/rollback plan.

Untuk War Room, modular monolith + worker tetap lebih tepat daripada memecah microservice tanpa kebutuhan scaling/failure isolation yang nyata.

Boundary yang dipertahankan:

```text
source/raw facts
  → ingestion/normalization
  → research/features
  → candidate/verdict
  → paper execution
  → evidence/performance
  → UI/API/audit
```

### Fase C — Contract-first

OpenAPI/JSON Schema harus memuat:

- request/response schema;
- error schema;
- auth requirement;
- pagination/limits;
- nullable semantics;
- timestamp/freshness meaning;
- rate limit;
- idempotency;
- compatibility/versioning.

Tambahkan CI contract diff dan consumer/provider tests. Frontend types idealnya digenerate dari contract, bukan diketik ulang manual.

### Fase D — Implement dan test

Piramida test:

- unit: invariant, formula, state transition, freshness, permission;
- integration: DB, migration, worker, SSE, provider adapter;
- contract: OpenAPI, status/error/provenance;
- security: IDOR, role escalation, CSRF, SSRF, injection, rate limit;
- E2E: login, evidence, paper flow, stale state, SSE reconnect, deploy smoke.

Setiap mutating endpoint minimal diuji untuk:

1. happy path;
2. malformed input;
3. anonymous;
4. insufficient role;
5. wrong object/IDOR;
6. duplicate request;
7. concurrent request;
8. provider timeout;
9. DB conflict;
10. audit event read-back.

## 3. Frontend standard

### Information architecture

Urutan dashboard:

```text
ringkasan 10 detik
→ keputusan/status
→ uang dan risiko
→ evidence
→ market context
→ raw facts/ledger
```

Setiap halaman menjawab:

- apa yang terjadi;
- seberapa yakin/valid;
- datanya kapan;
- apa tindakan berikutnya;
- apa yang tidak diketahui.

### State wajib

- loading/skeleton;
- success;
- empty/no signal;
- stale;
- degraded/partial;
- error/retry;
- unauthorized;
- forbidden;
- simulated/paper;
- unverified.

Jangan membuat `0` sebagai pengganti data hilang. Jangan mengandalkan warna saja. Status harus punya label, angka/ikon bila relevan, dan text explanation.

### Accessibility

Target WCAG 2.2 AA:

- keyboard/focus visible;
- semantic headings/landmarks;
- `aria-current` untuk navigasi;
- label/error association;
- chart punya ringkasan tekstual/tabel;
- contrast dihitung pada rendered background;
- reduced motion;
- target interaksi cukup besar;
- sticky element tidak menutup focus.

### Performance

- budget initial load/API/chart;
- batasi payload dan tabel besar;
- pagination/virtualisasi;
- cache sesuai freshness tolerance;
- retry backoff;
- fragmen independen agar satu source gagal tidak merusak halaman;
- browser tidak langsung bergantung pada vendor eksternal untuk data kritis bila backend proxy lebih stabil.

## 4. Backend/API standard

### Domain invariant

State penting memakai enum/lifecycle, bukan boolean yang ambigu. Setiap transition punya actor, waktu, alasan, event audit, dan read-back.

Invariant contoh:

```text
promotable hanya jika frozen split valid + n minimum + CI gate + policy_version
fresh hanya jika observed_at + ttl >= now
live hanya jika owner grant + scope + expiry + activation gate
ext_id unik untuk (venue, mode, ext_id)
```

### Fact/provenance contract

```text
fact_id
kind
key
value
source
source_record_id
observed_at
received_at
timezone
ttl_s
hash/raw_payload_hash
parser_version
schema_version
verification_state: measured | assumed | absent
quality/correction_status
```

Aggregation wajib membawa denominator, filter populasi, source facts, policy version, dan computed_at.

### Auth/security

Pisahkan:

```text
authenticate      → siapa?
authorize_action  → boleh operasi?
authorize_object  → boleh resource ini?
```

Wajib:

- cookie Secure/HttpOnly/SameSite;
- session rotation setelah login/privilege change;
- CSRF protection untuk cookie writes;
- TOTP secret benar-benar encrypted, bukan hanya nama kolom `*_enc`;
- IDOR matrix untuk own/other/missing object;
- input/path/JSON size limits;
- secret tidak ada di repo/log/bundle/URL;
- audit login, role, grant, freeze, apply, rollback;
- CSP tidak duplicate.

### Idempotency/concurrency

Semua command penting memakai `Idempotency-Key` dan request hash:

- same key + same payload → hasil pertama;
- same key + payload berbeda → 409;
- unique DB constraint tetap wajib;
- transaksi pendek, network call di luar transaksi;
- optimistic version atau row lock untuk state penting.

### Worker/queue

Command berat mengikuti:

```text
validate → authorize → durable command/outbox → 202 command_id
→ worker claim → retry/dead-letter → facts/events → read-back
```

Job state:

```text
queued | running | succeeded | failed | retryable | dead_letter | cancelled
```

Metrics: queue depth, oldest age, retry count, dead-letter, heartbeat, latency.

## 5. DevOps/SRE standard

### Environments

- local: synthetic data, no production secret;
- staging: production-like, DB/secret terpisah;
- production: immutable reviewed artifact, bukan edit source manual.

### Release gate

```text
lint/type/test
→ integration/contract/security
→ migration validation
→ secret scan/dependency scan
→ build artifact + commit SHA
→ staging smoke
→ backup verified
→ production deploy
→ health/readiness/auth/SSE smoke
→ observation window
→ rollback if needed
```

### Deployment

Prefer release directory immutable + atomic `current` symlink. Simpan 3–5 known-good release. Code rollback dan database rollback adalah dua hal berbeda; migration gunakan expand → backfill → switch → contract.

### SLO/error budget

Mulai ukur:

- availability;
- p95/p99 API latency;
- 5xx/401/403/409/429;
- source freshness/stale rate;
- worker success/lag;
- SSE liveness/lag;
- DB health/backup age;
- deployment change-failure/recovery time.

Target angka harus berasal dari baseline aktual. Jangan menyebut target sebagai jaminan sebelum diukur.

### Backup/recovery

Backup dianggap valid hanya setelah restore test. Minimum:

- PostgreSQL dump otomatis;
- off-site/immutable copy;
- retention;
- restore ke instance sementara;
- query/integrity/smoke test;
- catat restore duration dan recovery point.

### Incident

Setiap incident menghasilkan impact, timeline, detection gap, contributing causes, mitigation, owner/deadline, dan regression control. Prioritaskan mitigasi dan rollback sebelum root cause mendalam.

## 6. Trader/research workflow

Trader profesional memisahkan:

1. forecast/signal;
2. decision;
3. execution.

Setup bukan hanya entry:

```text
regime/context
→ hypothesis/mechanism
→ observable trigger
→ entry executable
→ invalidation/stop
→ exit/time-stop
→ risk budget/size
→ cost/slippage/fill model
→ journal/review
```

Hypothesis template:

> Pada universe X, jika kondisi Y terjadi pada timestamp t, maka return/probability Z dalam horizon H mengungguli baseline B setelah biaya C, selama regime R; hipotesis gugur bila I.

### Taxonomy

- technical/price action;
- fundamental/valuation;
- order flow/microstructure;
- on-chain;
- event-driven;
- market making;
- AMM/LP;
- discretionary;
- systematic;
- hybrid human + machine.

Jika keputusan penting tidak dapat ditulis sebelum melihat outcome, itu masih thesis discretionary, bukan strategi reproducible.

## 7. Perbedaan per market

### Crypto spot/perpetual

Identitas venue/pair/contract, funding, OI, liquidation, 24/7 sessions, fee, slippage, latency, custody, dan liquidation cascade wajib ada.

### DEX/LP

Yang diuji adalah total economic return:

```text
fee income
- divergence/impermanent loss
- gas/rebalance/hedge
- price impact/MEV
- token/contract/oracle risk
```

Baseline minimal: hold token A, hold token B, 50/50 hold, passive LP, active LP. Out-of-range berarti LP tidak aktif di range itu; bukan sinyal hold otomatis.

### Forex

Bedakan broker/feed, spot/CFD/futures, session, spread, commission, swap, event blackout, pip value, leverage, gap, dan execution. Jurnal kecil tidak boleh diklaim edge.

### Saham Indonesia

Masukkan lot/tick, session/auction, T+2, broker fee/levy/tax, corporate action, auto-rejection/halt, partial fill, gap, survivorship universe. Stop 1R tidak valid bila gap membuat exit jauh lebih buruk; risk tail harus diakui.

### Prediction market

Bedakan probability forecast dari trade EV. Masukkan resolution rules, CLOB bid/ask/depth, fee, fill, collateral, time-to-expiry, settlement/oracle. Gunakan calibration/Brier/log loss dan ask-adjusted EV, bukan win rate saja.

## 8. Protocol mengaudit klaim Threads

1. Simpan klaim literal, URL, author, timestamp.
2. Pisahkan observasi, mekanisme, prediksi, keputusan, hasil.
3. Identifikasi instrument/venue/pool.
4. Tulis feature availability `feature_time <= decision_time`.
5. Definisikan entry/exit/stop/size/cost/fill.
6. Freeze universe, horizon, baseline, invalidation.
7. Enumerate semua signal, bukan screenshot terbaik.
8. Bandingkan random/base-rate/buy-hold/market benchmark.
9. Jalankan chronological walk-forward dan frozen test.
10. Laporkan semua trial, termasuk gagal.
11. Stress fee, spread, latency, fill, regime, start date, best/worst trade.
12. Pisahkan signal quality, paper execution, operational feasibility.
13. Beri verdict yang tidak melebihi evidence.

Label evidence:

```text
[verified]    dicek dengan data primer/perhitungan ulang
[reported]    klaim pihak ketiga
[assumed]     asumsi untuk menjalankan test
[unverifiable] detail hilang/tidak dapat direkonstruksi
```

Verdict vocabulary:

```text
terbukti secara historis
menjanjikan, perlu validasi tambahan
tidak-terbukti
tidak-ada-sinyal
tidak-dapat-diaudit
```

## 9. Bias wajib

- lookahead/label leakage;
- survivorship/universe bias;
- selection/cherry-pick;
- multiple testing/data snooping;
- regime bias;
- execution/fill/touch bias;
- stale quote/timezone mismatch;
- cancellation bias;
- capacity/market impact bias;
- benchmark bias;
- wallet attribution overconfidence;
- open trade dianggap closed;
- paper PnL dianggap uang nyata.

## 10. Research card wajib

```text
hypothesis_id
source_claim/url/author/date
evidence_label
market/venue/instrument
mechanism
regime
features + available_at
entry/exit/stop/time-stop
cost/slippage/fill model
risk/sizing
baseline/counterfactual
universe/population
train-validation-frozen-test or walk-forward
trial_count/multiple-testing note
invalidation
results per horizon/regime
robustness/stress tests
verdict
```

## 11. Promotion gates

Strategi tidak boleh naik level sebelum:

- specification lengkap;
- raw data dan point-in-time integrity tervalidasi;
- baseline relevan tersedia;
- net edge bukan hanya gross edge;
- frozen out-of-sample/walk-forward ada;
- execution model defensible;
- robustness tidak bergantung pada outlier/satu regime;
- drawdown/tail/concentration masih masuk risk budget;
- replay reproducible;
- semua trial tercatat;
- owner menyetujui tahap berikutnya.

Status `promotable` berasal dari gate backend, bukan skor UI, AI narrative, atau postingan sosial.

## 12. Prioritas War Room

### P0

1. Rotate/revoke Google Stitch key yang sudah terekspos.
2. Pastikan TOTP secret benar-benar encrypted.
3. Tambahkan CSRF untuk cookie writes.
4. Tetap pertahankan Tencent dan live activation read-only/NO-GO.

### P1 engineering

1. Canonical `HypothesisSpec` + `ExecutionSpec` lintas market.
2. OpenAPI contract diff dan generated frontend types.
3. Idempotency untuk mutating commands.
4. DB constraints/triggers untuk invariant dan append-only events.
5. Negative IDOR/concurrency matrix.
6. request_id/correlation ID lintas API-worker-provider-SSE.
7. SLO dashboard + alert runbooks.
8. PostgreSQL off-site backup + verified restore.
9. Keyboard/focus/responsive automated QA.
10. `health`/`ready` + authenticated deploy smoke.

### P1 research

1. Pilih satu market data-complete.
2. Register satu hypothesis.
3. Jalankan frozen replay + walk-forward.
4. Bandingkan baseline/counterfactual.
5. Sertakan all-in cost dan fill/no-fill.
6. Stress test dan publish denominator.
7. Archive hasil gagal; jangan hapus.

### P2

- shared rate limiter bila multi-process;
- durable outbox/queue bila workload meningkat;
- OpenTelemetry tracing penuh;
- generated typed client;
- partition/retention facts/events;
- property-based invariant tests;
- VPS rebuild/game day berkala;
- canary/blue-green setelah staging matang.

## 13. Kesimpulan akhir studi

War Room sudah memiliki fondasi production dan evidence yang lebih baik daripada dashboard signal biasa: CI, auth/RBAC dasar, source freshness, canonical verdict, paper/live separation, deploy gate, rollback, dan evidence surface.

Namun standar senior penuh belum tercapai pada:

1. research contract belum seragam lintas market;
2. idempotency/CSRF/TOTP encryption/DB invariants belum seluruhnya menjadi gate;
3. SLO, restore drill, OpenAPI diff, responsive/accessibility automation, dan negative authorization matrix belum lengkap;
4. beberapa market belum punya baseline, cost model, frozen split, atau sample independen yang cukup.

**Keputusan:** studi ini selesai. War Room layak dilanjutkan sebagai evidence dashboard dan paper research platform. Tetap belum layak sebagai live-trading control plane.

## Sumber utama

- OWASP ASVS/API Security: https://owasp.org/projects/asvs/ dan https://owasp.org/API-Security/
- NIST SSDF: https://csrc.nist.gov/pubs/sp/800/218/final
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
- OpenAPI 3.1: https://spec.openapis.org/oas/3.1.0.html
- OpenTelemetry: https://opentelemetry.io/docs/
- Google SRE Workbook: https://sre.google/workbook/
- DORA metrics: https://dora.dev/guides/dora-metrics/
- CFA Institute backtesting: https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/backtesting-and-simulation
- CME risk management: https://www.cmegroup.com/education/courses/trade-and-risk-management
- Meteora DLMM: https://docs.meteora.ag/core-products/dlmm/dynamic-positions
- IDX trading/data services: https://www.idx.co.id/en/products-services/trading-hours-and-mechanism/ dan https://www.idx.co.id/en/products/idx-data-services/
- KSEI settlement: https://www.ksei.co.id/en/service-support/service-type/settlement-of-securities-transactions-services
- Polymarket CLOB/resolution: https://docs.polymarket.com/developers/CLOB/introduction dan https://docs.polymarket.com/concepts/resolution
