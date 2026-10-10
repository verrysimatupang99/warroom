# Peta struktur repo warroom

> Diverifikasi 10 Okt 2026. Sumber kebenaran = output perintah, bukan teks ini.
> Kanonis ditetapkan saat audit kerapian 10 Okt (komit `b73d74b`, `6ff1b10`).

## Ringkas

```
apps/web/              SvelteKit — frontend KANONIS publik (:3100 via nginx /)
services/api/          FastAPI REST + SSE, auth/RBAC (:8800 via nginx /api/)
services/worker/       job runner (snapshot, collect, replay, reconcile, freshness, backup)
services/llm/          gateway LLM (nutaraline → qonek, circuit breaker, cache, audit)
services/notifier/     alert → Telegram/email/push
packages/core/         façade ke domain live-trading (dependensi path, tanpa salinan)
packages/live-trading/ domain trading: kolektor, ledger, dashboard diagnostik (:8799, localhost)
ops/                   systemd units, vhost nginx sumber, skrip deploy, runbook
contracts/             OpenAPI hasil generate (curl :8800/api/openapi.json)
docs/                  ADR, progres P0–P6/W1–W10, bukti, peta ini
```

## Kanonis yang ditetapkan 10 Okt 2026

| Area | Kanonis | Bukan kanonis / arsip | Bukti |
|---|---|---|---|
| Frontend publik | `apps/web` (SvelteKit) | `packages/live-trading/frontend` = dashboard diagnostik `:8799` (localhost, dikunci `test_multipage`/`test_sinkron`) | nginx `/` → `:3100` |
| Mesin IDX 616 | `packages/live-trading/idx616/scripts` (arjum_client/pool, BSJP/ARA watcher, grader v3, ledger) | `vendor/idx` dihapus; grader v2 + `idx_bsjp_exit.py` dihapus | komit `6ff1b10`, grep bersih |
| State LP paper | `~/live-trading/state/lp_paper_state.json` + jejak `lp_mark_terakhir.json` | `~/gmgn-scan/` dilepas (folder hilang) | komit `b73d74b` |
| Kolektor forex | `collectors/forex.py` + `collectors/tv_feed.py` | `vendor/forex/` = salinan baca-saja Tencent, bukan dependensi impor | grep impor bersih |
| Harga crypto | OKX swap + Binance (pengganti MEXC total, 10 Okt) | `ops/mexc.env.example` = sisa arsip, tak dipakai kode | grep `MEXC_API` bersih |

## Alamat produksi

- Publik `https://0xgunsl1ng3r.xyz`: `/` → `127.0.0.1:3100` (web), `/api/` → `127.0.0.1:8800` (API).
- Internal (localhost saja): `:8799` dashboard diagnostik (`live-trading-dashboard.service`).
- `/metrics` tidak diekspos publik.

## Perintah balik (reversibel)

```bash
git log --oneline -5                                   # lihat komit kerapian
git revert 6ff1b10                                     # kembalikan duplikat IDX bila perlu
git revert b73d74b                                     # kembalikan rujukan gmgn-scan bila perlu
.venv/bin/python -m pytest -p no:cacheprovider --collect-only -q | tail -1
grep -rn "gmgn-scan" --include="*.py" packages/ services/ | grep -v ".venv"
```
