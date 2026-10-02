# ADR-001 — Stack: SvelteKit (web) + FastAPI (API), domain tetap Python

Status: **diterima** (dikunci user 2 Okt 2026) · Tanggal: 2026-10-02 · Fase: P0

## Konteks

UI sekarang adalah satu berkas Python 2.070 baris (`live-trading/src/live_trading/dashboard.py`)
yang menyusun string HTML, tanpa state, tanpa kontrak data, dan memakai `meta refresh` 60 detik.
Tidak ada API: tidak ada klien lain (HP, bot Telegram, Hermes) yang bisa memakai angka yang sama.
Di sisi lain, domain (collectors, signals, risk, execution, measure, backtest, equity) sudah
matang dan dijaga 219 tes — menulis ulang ke bahasa lain berarti membuang jaring pengaman itu.

## Keputusan

1. Frontend baru: **SvelteKit 2 + Svelte 5 (runes) + TypeScript + Tailwind v4**, `adapter-node`.
2. Backend baru: **FastAPI** (REST `/api/v1/*` + SSE `/api/v1/stream`), auth cookie + TOTP, RBAC.
3. **Domain tetap Python dan tidak diporting.** `packages/core` hanya façade ke paket `live-trading`.
4. Chart: ECharts (kanvas) untuk chart berat, SVG inline untuk sparkline. Tanpa framework UI berat.

## Konsekuensi

- Satu bahasa per lapisan: Python untuk hitungan, TypeScript untuk tampilan. Tidak ada dua
  implementasi rumus (mis. BE/gate) — rumus hidup di satu tempat (ADR-003).
- 219 tes domain tetap berlaku sepanjang migrasi; CI menjalankannya tiap PR.
- Perlu menjalankan dua runtime (Node + Python) di satu host — diterima, keduanya sudah ada di Webdock.
- Bug tampilan tidak bisa lagi "diperbaiki" dengan mengubah logika snapshot.

## Alternatif yang ditolak

- **Porting domain ke Node/TypeScript**: membuang 219 tes dan menciptakan dua definisi rumus. Ditolak.
- **HTMX + Jinja di atas FastAPI**: lebih dekat ke UI lama, tetap tanpa state/komponen, dan tetap
  menyatukan tampilan dengan logika. Ditolak — akar masalahnya ada di situ.
- **Next.js/React**: ekosistem lebih besar, tetapi menambah runtime RSC + dua bahasa UI untuk
  kebutuhan yang sebenarnya satu dashboard internal. SvelteKit lebih ringan untuk satu layar operasi.
- **Tetap `dashboard.py` + perbaikan bertahap**: plafon UI rendah; blueprint ini justru hasil
  diagnosis bahwa akarnya struktural.