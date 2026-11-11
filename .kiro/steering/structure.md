# Structure Steering — War Room (MaximaLabs)

## Repository layout

```
apps/web/                  SvelteKit frontend (routes, components, e2e)
  src/routes/<slug>/       one page per market/system (crypto, forex, idx, ...)
  src/lib/components/      shared + per-market components
  src/lib/nav.ts           navigation + per-market tab definition (TAB_DASAR)
  e2e/                     Playwright specs (encode the rendered DOM)
packages/core/             domain: models, db, strategy-config, mt5 crypto
  src/warroom_core/strategi_config/   strategy-as-config (YAML -> backtest/screener/bot)
packages/live-trading/     live-trading domain (MT5 bridge, forward-test)
services/api/              FastAPI app + routers (HTTP layer)
  src/warroom_api/routers/ one router per concern (journal, tencent, auth, ...)
services/worker/           background workers
ops/                       operational scripts (backfill, watchdog, sync)
strategi/                  strategy YAML definitions
contracts/openapi.json     committed OpenAPI contract (CI checks drift)
docs/                      architecture decisions (ADR), audits
```

## Conventions

- **Pages** are thin: they fetch via `urlApi()` and render four states
  (memuat / kosong / galat / ada). Rich logic lives in components.
- **One page per market** follows `MarketShell` + the tabs from `nav.ts`
  (`TAB_DASAR` = Ringkas / Sinyal / Uji / Eksekusi). A market page that
  diverges from this skeleton is a consistency bug.
- **Components** use Svelte 5 runes (`$props`, `$derived`, `$state`). Semantic
  tokens only — never hardcode hex in a component.
- **Routers** are thin; domain logic lives in `packages/`. A router that
  grows business logic is a smell.
- **Migrations** are Alembic, one per schema change, never edited after merge.
- **Backups** of edited files (`*.bak.*`) are deleted before committing — they
  are untracked noise, not history.

## What does not belong

- No secrets in the repo (env files are gitignored; only `*.env.example`).
- No dead files/components (knip + vulture gate this).
- No fabricated data to fill an empty screen — show an honest empty state.
