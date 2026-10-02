# War Room — platform (monorepo)

Super-app War Room: satu layar untuk crypto, IDX, forex, Polymarket, GMGN, dan Sistem & AI.
Rancangan lengkap: `docs/adr/` (keputusan) + blueprint di `../live-trading/docs/blueprint/`.

## Aturan yang tidak boleh dilanggar

Lihat `AGENTS.md`. Ringkasnya: `/opt/polymarket` baca-saja, Tencent/Azure baca-saja,
gate live tidak pernah disentuh, kredensial tidak pernah masuk repo/log/percakapan,
ambang gate & rumus BE hanya boleh diubah manusia.

## Struktur

```
apps/web/        SvelteKit (adapter-node) — konsumsi API, tanpa logika domain
services/api/    FastAPI: REST + SSE, auth/RBAC
services/worker/ job runner (snapshot, collect, replay, learner, parity-drift, reconcile, freshness, backup)
services/llm/    LLM gateway (nutaraline → qonek, circuit breaker, cache, audit)
services/notifier/ alert → Telegram/email/push
packages/core/   façade ke domain `live-trading` (dependensi path, tanpa salinan kode)
ops/             systemd units, Caddyfile, skrip deploy, runbook
contracts/       OpenAPI + tipe TypeScript hasil generate
docs/adr/        Architecture Decision Records
```

## Mulai

```bash
cd ~/warroom
uv sync                                        # workspace + live-trading (editable)
uv run python -c "import live_trading; print(live_trading.__version__)"
```

Domain tetap diuji di tempatnya (jaring pengaman 219 tes):

```bash
cd ~/live-trading && uv run ruff check . && uv run pytest -q
```

## Status

Fase P0 (fondasi) selesai: struktur, workspace, CI, ADR-001..005, baseline, runbook restore.
Fase berikutnya per `docs/blueprint/05-roadmap-hermes.md`.