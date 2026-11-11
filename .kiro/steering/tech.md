# Tech Steering — War Room (MaximaLabs)

## Stack

- **Backend**: Python 3.12 + FastAPI (`services/api`), domain logic in
  `packages/core` (`warroom_core`), live-trading domain in
  `packages/live-trading`.
- **Frontend**: SvelteKit + Svelte 5 runes (`apps/web`), adapter-node, served
  by `warroom-web.service` on :3100 behind nginx.
- **Database**: PostgreSQL (SQLAlchemy + Alembic migrations). Facts, trades,
  events, users.
- **Live trading**: MetaTrader 5 under Wine on an instabox box, driven by an
  Expert Advisor (`GOLD_Reaper_Hexa`) that pushes telemetry over HTTP.
- **Notifications**: Telegram via a `notify-hq` wrapper.

## Architecture rules

1. **Domain is separated from transport.** `packages/core` and
   `packages/live-trading` hold pure domain logic; `services/api` is the HTTP
   layer. Routers stay thin and delegate to domain packages.
2. **Strategy is config, not code.** A strategy is a YAML file (variables +
   formula conditions) in `strategi/`. One definition drives backtest,
   screener, and paper bot. Formula evaluation is sandboxed (AST-walked
   whitelist) — never `eval()`.
3. **Money is separated by (venue, mode).** `trades.venue` and `trades.mode`
   distinguish live / paper / warisan. Never mix them.
4. **Every fact has a TTL and a source.** A fact without `observed_at` and
   `source` is not trustworthy and the UI must not present it as fresh.

## Testing

- Backend: pytest (`packages/core/tests`, `services/api/tests`). 455+ tests.
- Frontend: vitest (`apps/web`). 123+ tests.
- E2E: Playwright (`apps/web/e2e`).
- Gates before merge: `ruff`, `knip` (no dead files), `vulture` (no dead
  code), OpenAPI contract check, svelte-check (0 errors), full test suites.

## Security

- Secrets live in root-only env files (`/etc/warroom/*.env`, mode 600) and are
  never committed. `.gitignore` excludes `*.env` and `secrets/`.
- Auth: session cookie (`wr_session`, HttpOnly, Secure) for browsers;
  `X-Warroom-Token` for internal services. Roles: viewer < operator < owner.
- The WebRequest allowlist for MT5 is set via the terminal GUI (MT5 build 6286
  ignores `common.ini`), so a self-healing helper re-applies it after restart.
