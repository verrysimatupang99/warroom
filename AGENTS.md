# AGENTS.md — War Room platform (Webdock)

Panduan kerja untuk agen/sesi berikutnya. Baca ini dulu sebelum mengubah apa pun.
Rancangan lengkap: `../live-trading/docs/blueprint/` (00–07).

## Garis yang tidak boleh dilewati

1. **`/opt/polymarket` = baca-saja.** Tidak menulis, tidak me-restart unit, tidak mengubah
   config. Menjalankan alat read-only miliknya (mis. `qa/favorite-live-verdict.py --json`)
   hanya lewat allowlist sudo yang ada.
2. **Tencent = baca-saja.** Sama seperti domain `live-trading`.
   **Azure sudah tidak dipakai lagi (sejak 6 Okt 2026):** radar rantai dipindah **lokal**
   ke host ini (`lt radar-update` → `state/radar_state.json`), jadi tidak ada lagi SSH
   ke VM `20.212.52.5`. Bila VM itu dimatikan, tidak ada yang hilang.
3. **Gate live tidak pernah disentuh** (`/etc/poly-pilot/activation-approved`): jangan
   dibuat, jangan diubah. Aksi live butuh izin eksplisit owner (grant), dan API menolak
   dengan 409 tanpa itu.
4. **Kredensial tidak pernah masuk repo/log/percakapan.** Berkas rahasia: `/etc/warroom/*.env`
   (mode 600 root) di-inject systemd; `~/.config/warroom/e2e.env` untuk kredensial e2e.
   Jalankan `gitleaks` sebelum commit bila menyentuh berkas contoh.
5. **Jangan mengarang angka.** Sumber tak terbaca → `tidak-izin`/`n/a` + alasan, bukan nol.
6. **Ambang gate & rumus BE hanya boleh diubah manusia (owner).** `gate.min_n`, `gate.ci`,
   dan `mode` terkunci; `deff` < 1 ditolak (itu arah melonggarkan).

## Perintah harian

```bash
# layanan
systemctl status warroom-api warroom-worker warroom-web caddy
journalctl -u warroom-worker -n 30 --no-pager

# kualitas (dari ~/warroom)
uv run ruff check . && uv run pytest -q                # suite penuh: 761 tes (audit 8 Okt 2026)
cd apps/web && npm run test                            # 9 berkas, 35 vitest
npx playwright test                                    # 27 e2e (butuh web+caddy hidup + e2e.env)
bash ops/ci-local.sh                                   # versi CI yang sama, termasuk gitleaks

# domain (dari ~/live-trading)
uv run ruff check . && uv run pytest                   # 219 tes domain
```

Angka di atas = kondisi per 8 Okt 2026 (`docs/overnight-production-readiness-audit-2026-10-08.md`).
Jika menyentuh tes, perbarui angka ini di dokumen yang sama beserta bukti perintahnya.
Sumber kebenaran tetap output perintah, bukan angka di dokumen ini.

## Arsitektur satu layar

```
apps/web/         SvelteKit (adapter-node, port 3100) — konsumsi API, tanpa logika domain
services/api/     FastAPI :8800 — REST /api/v1/*, SSE /api/v1/stream, auth cookie+RBAC
services/worker/  job runner (jadwal deklaratif di tabel `jobs`, --every 30)
services/llm/     gateway LLM (nutaraline → qonek, breaker, cache, audit `llm_calls`)
services/notifier/ transport Telegram/webhook/null + retry ≤3 (tidak pernah klaim terkirim)
packages/core/    façade domain: gate, autonomy, db models, prompts, db/session
ops/              systemd units, Caddyfile(.lokal), runbook, skrip bukti
contracts/        openapi.json (generate dari API hidup)
```

Aliran: **domain (`live-trading`) → worker publish fakta → API baca fakta → web render +
label kebijakan**. Angka hanya dari tabel `facts`; tidak ada perhitungan di UI.

## Konvensi kerja

- Satu perubahan = satu commit dengan alasan; sertakan bukti perintah di deskripsi.
- Uji yang gagal **tidak** dihapus; kalau perilaku memang berubah, tulis alasannya.
- Temuan yang membantah dokumen/rencana: tulis apa adanya di `docs/*progress*.md`.
- Jangan memakai `pip install` manual; semua lewat `uv sync` / `npm ci`.
- Batas izin sudo platform ada di `/etc/sudoers.d/warroom-poly-readonly` (read-only).
  **Catatan penting:** baris `%sudo … NOPASSWD` di `/etc/sudoers` terlihat berlaku di
  `sudo -l` tetapi **tidak** berlaku di konteks systemd (terbukti via auth.log +
  systemd-run). Jangan mengandalkannya; tambahkan perintah ke allowlist eksplisit.

## Deploy (3 Okt 2026)

- **URL**: `https://0xgunsl1ng3r.xyz` (apex; DNS Spaceship `A @ → 217.78.237.133`).
- **Proxy**: **nginx** (bukan Caddy) karena nginx sudah memegang 80/443 untuk situs lain.
  Vhost: `/etc/nginx/sites-available/warroom` (salinan repo: `ops/nginx-warroom.conf`).
  SSE wajib `proxy_buffering off` di lokasi `/api/`.
- **TLS**: certbot (plugin nginx), perpanjangan otomatis via timer; `certbot renew --dry-run` untuk uji.
- **Caddy**: terpasang tetapi **disabled** (dulu untuk uji lokal :8081); `ops/Caddyfile*`
  disimpan sebagai alternatif untuk host bersih.
- **Kredensial**: `~/.config/warroom/{e2e.env,spaceship.env}` (600). Jangan pernah masuk repo.
- **Notifier Telegram**: topik War Room `t.me/c/4383844873/237` (thread 237) — `ops/notifier.env.example` + `/etc/warroom/notifier.env` (600). Terbukti kirim: `telegram 200`.
- **Deploy web**: pakai `ops/deploy-web.sh` (build **lalu restart**). Membangun tanpa restart → proses lama pegang manifest lama → 500 (`Cannot find module …/nodes/0.js-*.js`). Insiden nyata 3 Okt.

## Sedang menunggu (owner)

1. ~~URL webhook/Telegram~~ **selesai 3 Okt** — transport Telegram aktif (bot Hermes, topic War Room); alert macet tetap terlihat di UI dengan label & kesalahan terakhir.
2. Domain + DNS → `ops/Caddyfile` (TLS) menggantikan `Caddyfile.lokal`.
3. Keputusan kebijakan gate (90% vs 95%+deff) + `split=frozen:<id>` untuk data uji.
4. Kunci/urutan provider nutaraline (401 + lambat; qonek menyelamatkan).
5. Perbaikan baris `%sudo` di `/etc/sudoers`.

## Gaya yang diminta user

Rapi, terstruktur, terdokumentasi. Bukti dijalankan lebih berharga daripada klaim.
Kalau ada temuan yang tidak nyaman, tulis — termasuk yang membantah pekerjaan sendiri.
