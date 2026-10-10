# Pengembangan War Room (teknis)

> Dokumen ini untuk kontributor/agen yang mengubah kode. Untuk pemakaian sehari-hari
> sebagai pengguna, lihat [`../README.md`](../README.md).
> Sumber kebenaran tetap **output perintah**, bukan angka di dokumen ini.
> Terakhir disegarkan 10 Okt 2026.

## Isi

- [Alamat produksi](#alamat-produksi)
- [Stack](#stack)
- [Struktur folder](#struktur-folder)
- [Kanonis](#kanonis)
- [Mulai (setup)](#mulai-setup)
- [Perintah harian](#perintah-harian)
- [Angka tes](#angka-tes-kondisi-per-10-okt-2026)
- [Environment & kredensial](#environment--kredensial)
- [Deploy web](#deploy-web)
- [API & systemd](#api--systemd)
- [nginx, TLS, DNS](#nginx-tls-dns)
- [Batas keselamatan](#batas-keselamatan-tidak-boleh-dilanggar)
- [Alur kerja branch–PR](#alur-kerja-branchpr)
- [Status](#status)
- [Perintah balik (reversibel)](#perintah-balik-reversibel)

## Alamat produksi

**https://0xgunsl1ng3r.xyz** — nginx (TLS Let's Encrypt) → web `:3100` + API `:8800`, same-origin.
Login di `/masuk`; `/api/*` butuh sesi (401 tanpa cookie). `/metrics` sengaja tidak diekspos publik.
`:8799` = dashboard diagnostik domain, localhost saja.

## Stack

| Lapis | Teknologi | Jalan di |
|---|---|---|
| Web (publik) | SvelteKit, adapter-node | `:3100`, via nginx `/` |
| API | FastAPI, REST `/api/v1/*` + SSE `/api/v1/stream`, auth cookie + RBAC | `:8800`, via nginx `/api/` |
| Worker | job runner (jadwal deklaratif di tabel `jobs`, `--every 30`) | systemd |
| LLM gateway | nutaraline → qonek, circuit breaker, cache, audit `llm_calls` | systemd |
| Notifier | Telegram/webhook/null + retry ≤3 (tidak pernah klaim terkirim) | systemd |
| Core | façade domain: gate, autonomy, db models, prompts, db/session | impor |
| Domain | `live-trading` (dependensi path, tanpa salinan kode) | — |
| Proxy | nginx (Caddy terpasang tapi **disabled**) | host |
| Paket Python | `uv` (`uv sync --frozen`); web `npm ci` | — |

## Struktur folder

```
apps/web/           SvelteKit (adapter-node, port 3100) — frontend KANONIS publik, tanpa logika domain
services/api/       FastAPI :8800 — REST /api/v1/*, SSE /api/v1/stream, auth cookie+RBAC
services/worker/    job runner (snapshot, collect, replay, learner, parity-drift, reconcile, freshness, backup)
services/llm/       gateway LLM (nutaraline → qonek, breaker, cache, audit `llm_calls`)
services/notifier/  transport Telegram/webhook/null + retry ≤3
packages/core/      façade ke domain `live-trading` (dependensi path, tanpa salinan kode)
packages/live-trading/ domain trading: kolektor, ledger, dashboard diagnostik internal (:8799, localhost saja)
  ├─ idx616/scripts/  mesin IDX 616 KANONIS (arjum_client/pool, BSJP/ARA watcher, grader v3, ledger)
  ├─ frontend/        dashboard HTML statis internal/diagnostik — BUKAN frontend publik
  └─ vendor/forex/    salinan baca-saja skrip forex Tencent (rujukan, bukan dependensi impor)
ops/                systemd units, vhost nginx sumber, skrip deploy, runbook
contracts/          OpenAPI hasil generate (`curl :8800/api/openapi.json`); tipe TS menyusul
docs/               ADR, progres P0–P6/W1–W10, bukti, dokumen ini
```

Aliran: **domain (`live-trading`) → worker publish fakta → API baca fakta → web render +
label kebijakan**. Angka hanya dari tabel `facts`; tidak ada perhitungan di UI.

Peta struktur lebih rinci (termasuk tabel "kanonis vs arsip") ada di
[`struktur-repo.md`](struktur-repo.md).

## Kanonis

Kanonis yang ditetapkan 10 Okt 2026 (audit kerapian):

- Frontend publik = `apps/web` (SvelteKit). `packages/live-trading/frontend` tetap ada
  untuk dashboard diagnostik `:8799` (localhost) + dikunci `test_multipage`/`test_sinkron`.
- Mesin IDX = `packages/live-trading/idx616/scripts` (duplikat `vendor/idx` + grader v2
  + `idx_bsjp_exit.py` dihapus 10 Okt, commit `6ff1b10`).
- State LP paper mati `~/gmgn-scan/` dilepas 10 Okt → `~/live-trading/state/lp_paper_state.json`
  + jejak mark `lp_mark_terakhir.json` (commit `b73d74b`).

## Mulai (setup)

```bash
cd ~/warroom
uv sync                                        # workspace + live-trading (editable)
uv run python -c "import live_trading; print(live_trading.__version__)"
```

Domain tetap diuji di tempatnya (jaring pengaman 227 tes):

```bash
cd ~/live-trading && uv run ruff check . && uv run pytest -q
```

## Perintah harian

```bash
# layanan
sudo systemctl status warroom-api warroom-worker warroom-web nginx
journalctl -u warroom-worker -n 30 --no-pager

# kualitas (dari ~/warroom)
uv run ruff check . && uv run pytest -q                # suite penuh: 806 tes (10 Okt 2026)
cd apps/web && npm run test                            # 9 berkas, 36 vitest
npx playwright test                                    # 47 berkas spec, 79 test() (butuh web+nginx hidup + e2e.env)
bash ops/ci-local.sh                                   # versi CI yang sama, termasuk gitleaks

# domain (dari ~/live-trading)
uv run ruff check . && uv run pytest                   # 227 tes domain
```

Jika menyentuh tes, perbarui angka ini di dokumen yang sama beserta bukti perintahnya.
Sumber kebenaran tetap output perintah, bukan angka di dokumen ini.

## Angka tes (kondisi per 10 Okt 2026)

Diverifikasi 10 Okt 2026 lewat `pytest --collect-only` dan `grep -r "test(" apps/web/e2e`
(lihat juga `../PRODUCT.md` bagian *Evidence on Hand*):

| Suite | Jumlah |
|---|---|
| Python (`.venv/bin/pytest -q`) | **806 tes** |
| Web (`npm run test`) | **9 berkas, 36 tes** |
| E2E (`npx playwright test`) | **47 berkas spec, 79 panggilan `test()`** |
| Domain (`~/live-trading`) | **227 tes** |
| OpenAPI contract | **50 path cocok** |

E2E **wajib** dijalankan lewat `https://0xgunsl1ng3r.xyz` (nginx mem-proxy `/api/` → API
`:8800`). Menjalankan langsung ke `127.0.0.1:3100` akan gagal login `/api/v1/auth/login`
(404, tanpa proxy) sehingga tes ber-sesi jatuh ke form login dengan gejala menyesatkan.

E2E + a11y + screenshot (butuh sesi):

```bash
cd apps/web
printf 'WARROOM_E2E_USER=uji-web\nWARROOM_E2E_PASS=…\n' > ~/.config/warroom/e2e.env  # mode 600
npx playwright test                     # login, SSE, a11y, screenshot
```

## Environment & kredensial

Aturan: **kredensial tidak pernah masuk repo, log, atau percakapan.** Jalankan `gitleaks`
sebelum commit bila menyentuh berkas contoh.

| Berkas | Isi | Mode |
|---|---|---|
| `/etc/warroom/*.env` | rahasia runtime, di-inject systemd | `600` root |
| `/etc/warroom/notifier.env` | transport alert (Telegram/webhook) | `600` root |
| `~/.config/warroom/e2e.env` | kredensial e2e | `600` |
| `~/.config/warroom/spaceship.env` | API DNS Spaceship | `600` |
| `~/.config/warroom/dns-backup-*.json` | backup record DNS | — |

Dari repo: `ops/notifier.env.example` (dan `ops/mexc.env.example`, sisa arsip) sebagai
contoh tanpa nilai — salin lalu isi di luar repo:

```bash
sudo install -m 600 -o root -g root ops/notifier.env.example /etc/warroom/notifier.env
sudo systemctl restart warroom-worker.service warroom-api.service
```

Notifier Telegram: topik War Room `t.me/c/4383844873/237` (thread 237); terbukti kirim
`telegram 200`. Tanpa isi yang sah, transport = `null` dan alert tetap di DB — status itu
ditampilkan apa adanya di UI, bukan diklaim "terkirim".

## Deploy web

**Deploy = build + restart + verifikasi, sebagai satu unit.** Membangun tanpa restart →
proses lama memegang manifest lama → 500 (`Cannot find module …/nodes/0.js-*.js`).

```bash
cd /home/admin/warroom
bash ops/set-build-id.sh          # tulis build_id ke /etc/warroom/build.env
bash ops/deploy-web.sh            # build + restart web + health gate + verifikasi build_id
```

`ops/deploy-web.sh` berurutan: backup `build/` lama → `npm run build` (menulis
`build/build-id.txt`) → `systemctl restart warroom-web` → health gate (`/` = 200 **dan** satu
aset `/_app/*.js` tersedia) → verifikasi `build_id` disk = `build_id` API
(`/api/v1/build`) → rollback otomatis bila health gate gagal.

Detail lengkap + pemulihan saat web 500: [`../ops/runbook-deploy.md`](../ops/runbook-deploy.md).

## API & systemd

```bash
cd /home/admin/warroom
bash ops/set-build-id.sh                 # samakan build_id sebelum restart API
sudo systemctl restart warroom-api
curl -sS http://127.0.0.1:8800/api/v1/build   # verifikasi
```

Unit: `ops/warroom-api.service`, `ops/warroom-worker.service`, `ops/warroom-web.service`.
Endpoint terkait:

| Endpoint | Auth | Isi |
|---|---|---|
| `GET /api/v1/build` | **tidak** | `build_id`, `domain_version`, `time` |
| `GET /api/v1/health` | sesi | status, db, `build_id`, user |
| `GET /api/v1/ready` | sesi | readiness checks |

## nginx, TLS, DNS

- **Proxy**: nginx (bukan Caddy) karena nginx sudah memegang 80/443 untuk situs lain.
  Vhost: `/etc/nginx/sites-available/warroom` (salinan repo: `ops/nginx-warroom.conf`).
  SSE wajib `proxy_buffering off` di lokasi `/api/`.
- **TLS**: certbot (plugin nginx), perpanjangan otomatis via timer.
- **Caddy**: terpasang tetapi **disabled**; `ops/Caddyfile*` disimpan sebagai alternatif host bersih.
- **DNS**: Spaceship, record `A @ → 217.78.237.133`; backup di `~/.config/warroom/dns-backup-*.json`.

```bash
sudo nginx -t && sudo systemctl reload nginx     # setelah ubah vhost
sudo certbot renew --dry-run                     # uji perpanjangan otomatis
```

## Batas keselamatan (tidak boleh dilanggar)

Lihat [`../AGENTS.md`](../AGENTS.md). Ringkasnya:

1. `/opt/polymarket` = **baca-saja** (tidak menulis, tidak restart unit, tidak ubah config).
2. Tencent = **baca-saja**. Azure sudah dilepas 6 Okt — radar rantai kini lokal di host ini.
3. Gate live tidak pernah disentuh (`/etc/poly-pilot/activation-approved`); aksi live butuh izin owner.
4. Kredensial tidak pernah masuk repo/log/percakapan.
5. **Jangan mengarang angka.** Sumber tak terbaca → `tidak-izin`/`n/a` + alasan, bukan nol.
6. Ambang gate & rumus BE hanya boleh diubah owner (`gate.min_n`, `gate.ci`, `mode` terkunci).

## Alur kerja branch–PR

Detil di [`../AGENTS.md`](../AGENTS.md). Ringkas: **dilarang push langsung ke `main`.**
Perubahan lewat branch → PR (pakai `.github/pull_request_template.md`) → CI hijau
(`.github/workflows/ci.yml`) → review → merge.

## Status

- **P0–P6 selesai** (fondasi → integrasi → otonomi berbatas → kesiapan live).
- **W1–W10 (perbaikan pasca-periksa, 3 Okt)** — lihat [`w10-perbaikan-2026-10-03.md`](w10-perbaikan-2026-10-03.md).
- **Live tetap NO-GO**: split beku belum ada; keputusan kebijakan gate (90% vs 95%+deff) di owner.
- Rujukan rancangan: `../live-trading/docs/blueprint/` (00–07).

## Perintah balik (reversibel)

```bash
git log --oneline -5                                   # lihat komit terakhir
git revert <sha>                                       # kembalikan perubahan tertentu
.venv/bin/python -m pytest -p no:cacheprovider --collect-only -q | tail -1   # hitung ulang tes
```
