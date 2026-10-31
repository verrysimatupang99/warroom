# AGENTS.md — War Room platform (Webdock)

Panduan kerja untuk agen/sesi berikutnya. Baca ini dulu sebelum mengubah apa pun.
Rancangan lengkap: `../live-trading/docs/blueprint/` (00–07).

## Garis yang tidak boleh dilewati

1. **`/opt/polymarket` = baca-saja.** Tidak menulis, tidak me-restart unit, tidak mengubah
   config. Menjalankan alat read-only miliknya (mis. `qa/favorite-live-verdict.py --json`)
   hanya lewat allowlist sudo yang ada.
2. **Tencent = baca-saja.** Sama seperti domain `live-trading`.
   **Azure: radar rantai tetap lokal** di host ini (`lt radar-update` → `state/radar_state.json`);
   VM `20.212.52.5` tidak dipakai untuk itu dan boleh mati. **Pengecualian:** VM
   `mt5-trader-vm` (`FOREX-MT5-RG`, 138.91.35.65) **dipakai aktif** untuk eksekusi demo
   XAUUSD lewat `WarRoom_AutoTrader_v3`. Jangan matikan; lihat `HANDOVER-OMP.md` §5.
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
systemctl status warroom-api warroom-worker warroom-web nginx
journalctl -u warroom-worker -n 30 --no-pager

# kualitas (dari ~/warroom)
.venv/bin/python -m pytest services/*/tests packages/live-trading -q   # angka terkini: lihat catatan di bawah
cd apps/web && npm run test                            # 16 berkas, 72 vitest
npx playwright test                                    # 52 berkas spec e2e (butuh web+nginx hidup + e2e.env)
bash ops/ci-local.sh                                   # versi CI yang sama, termasuk gitleaks

# domain (anggota workspace: packages/live-trading/)
.venv/bin/python -m pytest packages/live-trading -q    # tes domain, dari root repo
```

**`uv` sudah tidak terpasang** di host ini; pakai `.venv/bin/python -m pytest`.
Jumlah tes per **30 Okt 2026**: **912** (`--collect-only`, perintah
`pytest services/*/tests packages/live-trading`), dan run penuh sampai 100%
tanpa kegagalan. Root `pytest` (testpaths `packages` + `services`, termasuk
`packages/core/tests`) mengoleksi **1126**. Web: **72** vitest, **52** berkas spec e2e.
Angka lama 882/889/892/900/906/908/909 sudah tidak berlaku. Kalau menyentuh tes, perbarui
angka ini beserta bukti perintahnya — sumber kebenaran tetap output, bukan dokumen.

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

## Alur kerja branch–PR (dilarang push langsung ke `main`)

**`main` = cabang terproteksi. Jangan pernah `git push` langsung ke `main`.**
Semua perubahan lewat pull request, bukan push ke cabang utama.

1. **Branch** dari `main` yang mutakhir. Nama: `<tipe>/<ringkas-dengan-dash>`,
   mis. `docs/pisah-readme-pengembangan`, `fix/gate-deff-basi`. Tipe = daftar di bawah.
2. **Commit** kecil dan bermakna (lihat format di bawah). Satu perubahan = satu alasan.
3. **Push** branch itu, lalu buka **Pull Request** ke `main` dan isi
   `.github/pull_request_template.md` (Apa yang berubah / Kenapa / Sudah dicek / Selanjutnya).
4. **CI harus hijau** (`.github/workflows/ci.yml`: domain, platform, secrets/gitleaks, web).
   Bukti perintah lokal (`bash ops/ci-local.sh`) lebih dihargai daripada klaim.
5. **Review** minimal satu mata lain (atau owner) sebelum **merge**. Jangan merge CI merah,
   jangan merge tanpa mengisi bagian *Sudah dicek*.

Dilarang juga: `git push --force` ke `main`, menulis riwayat ulang (`rebase`/`amend`) pada
cabang bersama, dan mem-bypass CI. Untuk perubahan darurat, tetap buka PR — kerjakan cepat,
biarkan jejaknya ada.

### Format commit (Conventional Commits, Bahasa Indonesia)

```
<tife>(<lingkup>): <ringkas imperatif, maks 72 karakter>

<body opsional: alasan + bukti perintah>
```

- **Tipe:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`.
- **Lingkup:** area yang disentuh, mis. `crypto`, `idx`, `api`, `web`, `docs`.
- **Ringkas** maks **72 karakter**, imperatif, Bahasa Indonesia, tanpa titik di akhir.
- **Tanpa atribusi AI** (jangan tulis "Generated by …", "Co-Authored-By: AI", dsb.).
- Badan commit menampung alasan dan bukti; ringkas jangan dipakai untuk cerita panjang.

Contoh yang sah (dari riwayat repo ini):

```
feat(crypto): header dompet + log aksi/skip di sub eksekusi
docs(rapi): segarkan README/PRODUCT + peta struktur-repo
refactor(idx): satukan duplikasi arjum + hapus skrip mati
```

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

## Tambahan 30 Okt 2026 — adopsi Reaper & serah-terima

Rincian lengkap: `HANDOVER-OMP.md`. Yang berubah sejak catatan di atas:

- **AutoTrader v3** di VM Azure (`WarRoom_AutoTrader_v3`) kini menghitung sinyal sendiri
  dengan logika Reaper (EMA21/55 + EMA200 M15 + RSI14, filter ATR/spread/sesi), bukan
  hanya menerima sinyal server. Telemetri v2 tidak diubah. Rollback:
  `config/startup.ini.v2bak` + `WarRoom_AutoTrader.ex5`.
- Backtest 3 tahun, XAUUSDm M5, Model 2: sesi 08–09 → net +$3.923, PF 1,25, DD 6,01%
  (**dipasang**); sesi 08–17 → net −$1.787 (rugi tiap tahun, jangan dipakai);
  varian tanpa partial TP → +$4.697, PF 1,24, DD 7,55%. Titik putus slippage 0,48 vs
  spread terukur 0,24.
- `.mobile-header` disembunyikan di `@media (min-width: 768px)`; sebelumnya bar 48px
  menimpa 24px awal konten di desktop.
- `fills.csv` masih header saja → `/journal/edge` 503. Sejak v3.1, deal tertutup
  dilaporkan ke `/mt5/deal` → `deals.csv` dan tampil di `/journal/trades`; fills
  tetap dipakai untuk kualitas eksekusi (slippage/latensi).
- EA v3.1 (30 Okt): telemetri menyertakan `eval_alasan`/`eval_sesi`/`eval_atr`/
  `eval_rsi`/`eval_ema_*`/`server_time`; panel "Status mesin Reaper" di tab Sinyal.
  Rollback: `WarRoom_AutoTrader_v3.ex5.v30bak` + `WarRoom_AutoTrader_v3.mq5.v30bak`.
- Password MT5 demo pindah ke `~/.hermes/secrets/mt5_434434290.env` (600); `.ini` di
  instabox sudah dikosongkan. Rotasi kunci lama (MEXC, IDX, Stitch, MT5) masih terbuka.
- Jebakan yang memakan waktu ada di `HANDOVER-OMP.md` §9 — terutama: Strategy Tester
  menuntut akun tersimpan (`accounts.dat` di build 6286), dan `az vm run-command`
  berjalan sebagai SYSTEM sehingga MT5 membaca data folder yang salah.
