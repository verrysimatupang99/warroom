# Overnight production-readiness and research-gate audit

**Audit date:** 2026-10-08 UTC  
**Overnight target:** 2026-10-09 06:00 WIB  
**Scope:** read-only audit of the local War Room repository; no deployment, restart, live order, Tencent access, or `/opt/polymarket` write.

## Decision

**Research/paper gate: GREEN for local code and contract checks; NOT A LIVE-READINESS APPROVAL.**

The repository has a fail-closed research contract, frozen-split/sample gates, paper-only execution validation, API authorization tests, and CI checks for Python, web, OpenAPI drift, and secrets. The overnight run may proceed only with sanctioned read-only data and a frozen manifest. A missing or insufficient dataset must produce `blocked_data_access`/`not_auditable`, not a fabricated result.

**Live trading remains NO-GO.** Passing tests do not provide an owner grant, production activation, venue authorization, or evidence of profitable execution. No live promotion is justified by this audit.

## Evidence executed

| Check | Result |
|---|---|
| Full Python suite: `.venv/bin/pytest -q` | PASS — 761 tests, 1 existing Starlette/httpx deprecation warning |
| Research/gate/readiness targeted tests | PASS — 43 tests |
| Ruff on research/gate/API audit surface | PASS — `All checks passed!` |
| OpenAPI contract: `.venv/bin/python ops/check-openapi-contract.py` | PASS — `OpenAPI contract matches (50 paths)` |
| Web type/check: `npm run check` | PASS — 0 errors, 0 warnings |
| Web tests: `npm run test` | PASS — 9 files, 35 tests |
| Web production build: `npm run build` | PASS — Vite/SvelteKit build completed |

The targeted surface included `build_research_run_preview`, hypothesis/execution gate behavior, live-grant/arming fail-closed behavior, and the dry-run allowlist audit tests.

## Research-gate findings

- `HypothesisSpec` and `ExecutionSpec` require explicit rules, costs, timing, split, population, invalidation, and paper/shadow execution details.
- `build_research_run_preview` is local and side-effect free; it rejects empty keys/provenance, malformed artifact SHA-256 values, and `mode="live"`.
- Research previews bind versioned hypothesis/execution JSON to SHA-256 hashes and preserve artifact provenance.
- Gate tests cover frozen splits, minimum sample size, Wilson intervals, break-even comparison, exploration exclusion, and cluster-design-effect corrections.
- Live action tests require owner/grant/arming conditions and verify that the successful test path still performs no action (`"tidak ada aksi yang dijalankan"`).
- Dry-run tests reject state-changing subcommands (`snapshot`, `dedupe`, `dashboard`) before subprocess invocation.

## Production-readiness findings

- CI declares domain, platform, secrets, and web jobs. Platform CI checks editable domain import and OpenAPI drift; secrets CI runs gitleaks over history.
- Local CI script is explicitly non-deploying and states it does not touch `/opt/polymarket`, Tencent, or Azure.
- The local tree already contained unrelated modified evidence PNGs and multiple untracked research/audit documents before this audit. They were not altered.
- One non-blocking warning remains: Starlette reports that its current TestClient/httpx integration is deprecated and recommends `httpx2`. This is technical debt, not a failed gate.
- This audit did not validate external data access, dataset completeness, fresh market outcomes, systemd health, network reachability, or a live public deployment. Those require separate authorized evidence and were intentionally not attempted.

## Overnight operating gate

1. Use only sanctioned read-only data access.
2. Record schema, timestamps/timezone, resolution, quote/fill fields, fee/slippage/latency policy, outcomes, and source provenance.
3. Freeze and hash the dataset manifest and split before replay.
4. Run replay plus baseline and all-in cost model.
5. Publish denominator, confidence interval/gate inputs, invalidations, and evidence status.
6. If required fields are absent, publish `blocked_data_access` or `not_auditable`.
7. Do not create live grants, activation files, orders, or production changes as part of the overnight R&D run.

## Files changed by this audit

- Created: `docs/overnight-production-readiness-audit-2026-10-08.md`
- No source code, CI, production configuration, live-trading controls, Tencent resources, or `/opt/polymarket` paths were modified.
