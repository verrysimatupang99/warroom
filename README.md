# War Room — platform (monorepo)

Super-app War Room: satu layar untuk crypto, IDX, forex, Polymarket, GMGN, dan Sistem & AI.
Rancangan lengkap: `docs/adr/` (keputusan) + blueprint di `../live-trading/docs/blueprint/`.

## Aturan yang tidak boleh dilanggar

Lihat `AGENTS.md`. Ringkasnya: `/opt/polymarket` baca-saja, Tencent baca-saja
(Azure sudah dilepas 6 Okt — radar rantai kini lokal di Webdock),
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
contracts/       OpenAPI hasil generate (`curl :8800/api/openapi.json`); tipe TS menyusul
docs/adr/        Architecture Decision Records
```

## Mulai

```bash
cd ~/warroom
uv sync                                        # workspace + live-trading (editable)
uv run python -c "import live_trading; print(live_trading.__version__)"
```

Domain tetap diuji di tempatnya (jaring pengaman 227 tes):

```bash
cd ~/live-trading && uv run ruff check . && uv run pytest -q
```

## Alamat produksi

**https://0xgunsl1ng3r.xyz** — nginx (TLS Let's Encrypt) → web `:3100` + API `:8800`, same-origin.
Login di `/masuk`; `/api/*` butuh sesi (401 tanpa cookie). `/metrics` sengaja tidak diekspos publik.

```bash
sudo systemctl status warroom-api warroom-worker warroom-web nginx
sudo nginx -t && sudo systemctl reload nginx     # setelah ubah vhost
sudo certbot renew --dry-run                     # perpanjangan otomatis (timer certbot)
```

DNS dikelola di Spaceship (record `A @ → 217.78.237.133`); backup record ada di
`~/.config/warroom/dns-backup-*.json`. Vhost sumber: `ops/nginx-warroom.conf`.

Kredensial notifier (opsional, agar alert terkirim): `ops/notifier.env.example` → `/etc/warroom/notifier.env`.

E2E + a11y + screenshot (butuh sesi):

```bash
cd apps/web
printf 'WARROOM_E2E_USER=uji-web\nWARROOM_E2E_PASS=…\n' > ~/.config/warroom/e2e.env  # mode 600
npx playwright test                     # 106 tes: 8 rute, login, SSE, a11y, screenshot
```

## Angka tes (kondisi per 9 Okt 2026)

Selalu jadikan output perintah sebagai sumber kebenaran; angka di bawah hanya rujukan
terakhir yang tercatat. Diverifikasi 9 Okt 2026 lewat `pytest --collect-only -q` dan
`npx playwright test --list` (lihat catatan R2 di `docs/`):

| Suite | Jumlah |
|---|---|
| Python (`.venv/bin/pytest -q`) | **806 tes** |
| Web (`npm run test`) | **9 berkas, 36 tes** |
| E2E (`npx playwright test`) | **106 tes** |
| Domain (`~/live-trading`) | **227 tes** |
| OpenAPI contract | **50 path cocok** |

E2E **wajib** dijalankan lewat `https://0xgunsl1ng3r.xyz` (nginx mem-proxy `/api/` → API
`:8800`). Menjalankan langsung ke `127.0.0.1:3100` akan gagal login `/api/v1/auth/login`
(404, tanpa proxy) sehingga tes ber-sesi jatuh ke form login dengan gejala menyesatkan.

## Status

- **P0–P6 selesai** (fondasi → integrasi → otonomi berbatas → kesiapan live).
- **W1–W10 (perbaikan pasca-periksa, 3 Okt)** — lihat `docs/w10-perbaikan-2026-10-03.md`:
  CI gitleaks, fakta `verdict` (GateMeter hidup), gate `deff`, metrik basi, alert + ack/snooze,
  kesehatan provider, deploy web+Caddy+login, e2e/a11y/screenshot, kebersihan dokumen.
- **Live tetap NO-GO**: split beku belum ada; keputusan kebijakan gate (90% vs 95%+deff) di owner.
- Rujukan rancangan: `../live-trading/docs/blueprint/` (00–07).