# P2 & P3 — status pelaksanaan (frontend + lapisan AI)

Diperbarui: **2026-10-03 05:30 WIB** (2026-10-02 22:30 UTC) · Pelaksana: Hermes

## Ringkas

| Bagian | Status | Bukti nyata |
|---|---|---|
| P2 frontend (SvelteKit 2 + Svelte 5 runes + TS + Tailwind v4) | **selesai, terverifikasi** | `npm run build` ✔ adapter-node · `npm run test` **27/27 lulus** (6 berkas) · 7 area + sub-nav · screenshot full-page desktop & mobile di `docs/bukti-p2/` |
| P2 data nyata dari API | **selesai setelah 2 bug diperbaiki** | halaman menampilkan fakta asli (`PAPER SEGAR 3,84R`, `IDX > KUOTA > LIMIT 6.000,00`, badge segar 8–11 m) |
| P3 gateway LLM (nutaraline → qonek) | **selesai, terverifikasi** | panggilan **sungguhan** 6,2 s / 5,4 s, `llm_calls` mencatat provider, token, latensi, hash |
| P3 failover nyata | **terbukti** | kunci nutaraline dirusak → `qonek ok=True fallback_from=nutaraline` (HTTP nyata, bukan mock) |
| P3 anti-injeksi & tanpa-fakta | **terbukti** | dokumen "abaikan instruksi…" tidak dipatuhi; tanpa fakta → `insufficient`, nol angka baru |
| P3 registry prompt | **selesai** | `prompts-sync`: 3 berkas → tabel `prompts` (narrator/verifier/anomaly 1.0.0) |
| P3-T5 pindah `pods/nilai.py` | **selesai (opt-in)** | jalur War Room dulu, fallback lokal; 5 tes baru di domain (gagal-jaringan → lokal) |

## Bug nyata yang ditemukan & diperbaiki saat integrasi

1. **UI → API 404.** UI membaca `import.meta.env.PUBLIC_API_BASE`, padahal Vite hanya
   menyuntik variabel berawalan `VITE_` → nilai kosong → fetch relatif ke origin web →
   `/api/v1/...` 404 dan tiap blok menampilkan "GAGAL MEMUAT". Diperbaiki memakai
   `$env/dynamic/public` (dibaca saat runtime) + helper `urlApi()`.
2. **SSE 404.** `live.svelte.ts` menyusun jalur stream tanpa base (`/api/v1/stream?...`)
   sehingga mengenai origin web. Sekarang lewat `urlApi()` → status live tersambung.
3. **Endpoint per-area tidak ada.** UI memanggil `/api/v1/{area}`, API hanya punya
   `/api/v1/areas`. Ditambahkan `GET /api/v1/areas/{area}` (+ opsi `riwayat`).
4. **Tabel nilai panjang terpotong di mobile.** `DataTable` kini membatasi lebar kolom
   (`max-w-[38ch]`, `break-words`) dan memotong teks > 90 karakter dengan `title` (nilai utuh
   tetap bisa dibuka lewat drawer "Lihat nilai mentah").
5. **Kunci qonek 401 dari gateway.** Config efektif memakai `keyEnv=QONEK_API_KEY`, sedangkan
   `llm.env` hanya memuat `HERMES_CUSTOM_QONEK_WEB_ID_API_KEY` → tanpa header Authorization.
   Ditambahkan alias `QONEK_API_KEY`; setelah itu failover terbukti melayani.

## Catatan jujur

- **Provider utama tidak selalu sehat.** Dari panggilan nyata, nutaraline beberapa kali lambat
  (38,6 s) atau gagal (401/5xx) sehingga qonek melayani. Rantai fallback bekerja, tetapi kalau
  ini berlanjut, biaya/latensi akan ditanggung provider kedua.
- **`/metrics` publik-terbatas** dan endpoint AI tetap butuh sesi; `/api/v1/ai/verifier`
  menerima pemanggil lokal atau token layanan (`WARROOM_SERVICE_TOKEN`), bukan terbuka.
- **Uji end-to-end browser** memakai pengecualian sementara `WARROOM_COOKIE_SECURE=0` +
  `WARROOM_CORS_ORIGINS` di drop-in systemd; **berkas itu sudah dihapus**, `cookie_secure()`
  kembali `True`, dan header CORS tidak lagi dikirim (diverifikasi setelah restart).
- Angka "N/A" pada kartu NYATA/WARISAN/REALTIME **bukan bug**: memang belum ada dana
  terverifikasi on-chain (butuh `WARROOM_POLYGON_RPC`), angka UI lama belum diimpor, dan
  realtime belum dipasang. Sesuai aturan: tidak ada angka karangan.

## Perintah pembuktian

```bash
cd ~/warroom && uv run ruff check . && uv run pytest -q            # 182 lulus
cd ~/warroom/apps/web && npm run build && npm run test             # 27/27 lulus
cd ~/live-trading && .venv/bin/python -m ruff check . && .venv/bin/python -m pytest --tb=no   # 224 lulus
sudo bash -c 'set -a; . /etc/warroom/db.env; . /etc/warroom/llm.env; set +a; \
  export HOME=/home/admin; ~/warroom/.venv/bin/python ~/warroom/ops/verify-p3-llm.py'
```

## Berkas bukti

- `docs/bukti-p2/{desktop,mobile}-{polymarket,crypto,sistem}.png` — full-page (CDP
  `captureBeyondViewport`), lebar 1440 px dan 390 px; tidak ada overflow horizontal.
- `ops/verify-p3-llm.py` — skrip bukti P3 (panggilan nyata + failover + insufficient).