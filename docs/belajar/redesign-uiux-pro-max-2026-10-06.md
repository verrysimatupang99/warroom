# Redesign UI/UX via ui-ux-pro-max + backend/fullstack — 6 Okt 2026

Pemilik meminta redesign total memakai `nextlevelbuilder/ui-ux-pro-max-skill`, termasuk
sisi backend/fullstack. Keputusan pemilik: **font dipertahankan** (Space Grotesk + Inter +
JetBrains Mono), **backend disentuh penuh**.

## 0. Apa yang skill rekomendasikan (dijalankan, bukan dikutip)

`search.py "trading dashboard multi-market" --design-system` + pencarian domain:

| Aspek | Rekomendasi skill | Yang dilakukan |
|---|---|---|
| Produk | Fintech/Crypto + Financial Dashboard | cocok |
| Style | **Dark Mode (OLED) + Data-Dense Dashboard** | sudah ini; diperkuat |
| Tipografi | "Dashboard Data" (mono+sans) | **dipertahankan** pilihan pemilik (Space Grotesk/Inter/JetBrains) |
| Arsitektur token | **3 lapis: primitive → semantic → component** | **diterapkan** |
| Chart | line + a11y: jangan andalkan warna saja, sediakan tabel fallback | **diterapkan** |
| UX | empty state harus memandu; cursor-pointer; focus terlihat; target ≥44px | **diterapkan** |
| Checklist | tanpa emoji sbg ikon, reduced-motion, responsif 375/768/1024/1440 | diverifikasi |

Skill dipasang di `~/.agents/skills/{ui-ux-pro-max,design-system}` (dibaca Hermes).

## 1. Fase 1 — Token 3 lapis

`apps/web/src/app.css` direstruktur:
- **PRIMITIVE** `--p-*`: nilai mentah (navy, aksen, skala teks).
- **SEMANTIC** `--color-*` / `--bg`,`--surface`,`--text-*`: peran; **tema berganti di sini**.
- **COMPONENT** `--card-*`, `--rail-w`, `--row-h`, `--focus-ring`.

Nama semantic lama dipertahankan (menunjuk ke primitive) → ratusan pemakaian tidak putus.
Tema terang kini hanya menimpa lapisan semantic. **Dibuktikan live**: `--color-accent`
#00c8ff→#066a8c saat tema berganti, sementara `--p-cyan-400` tetap.

**Linter token** `apps/web/scripts/lint-tokens.mjs` + wire ke CI & `ci-local.sh`:
melarang hex/ukuran hardcoded di `.svelte` (komponen/rute); `app.css` dikecualikan karena
di situlah primitive memang ditulis. 3 nilai inline hardcoded diperbaiki ke token.

## 2. Fase 2 — Komponen & a11y

- **EmptyState**: parameter aksi opsional (panduan ux: memandu, bukan layar kosong).
- **EquityCurve**: **fallback tabel aksesibilitas** (`<details>` berisi R per trade) —
  panduan chart: kurva yang hanya bisa dibaca lewat hover/warna tidak cukup.
- **app.css**: `cursor: pointer` untuk semua elemen interaktif; `:disabled` → not-allowed;
  focus memakai token `--focus-ring`.

## 3. Fase 3 — Backend/fullstack

- **`GET /api/v1/design/tokens`** — token dari SATU sumber (`app.css`), **dibaca** bukan
  disalin (mencegah sumber kedua menyimpang). Tak terbaca → `ada:false` + alasan, bukan
  karangan. Live: 79 token.
- **Penjaga drift kontrak** `packages/core/tests/test_kontrak_ui.py`: field `SinyalPasar`
  Python harus SAMA dengan interface TS — tanpa ini field hilang hanya jadi `undefined`
  saat runtime tanpa error kompilasi.
- **Regresi fallback SSE** `live.svelte.test.ts`: fetch gagal → status `polling`, bukan
  tetap terlihat `live` padahal data berhenti.
- Tipe TS `DesignTokens`.

## 4. Fase 4 — Verifikasi (semua dijalankan)

| Uji | Hasil |
|---|---|
| Responsif 4 lebar × 7 rute | **0 overflow** (28 kombinasi) |
| Kontras 2 tema (gelap + terang) | **0 gagal** AA |
| a11y (nama aksesibel, h1, lang) | 0 elemen tanpa nama · 1 `<h1>`/rute · `lang=id-ID` |
| Detektor impeccable | **0 pelanggaran** |
| Linter token | bersih (43 berkas) |
| svelte-check | **0 error** |
| vitest | **45 lulus** (dari 44) |
| ruff | bersih |
| pytest | **663 lulus** (dari 660) |

## 5. Commit

`547b4fa` token 3 lapis + linter · `e30a91c` state/chart/cursor · `1b99389` endpoint
design-tokens + penjaga kontrak · `1a30ff4` regresi SSE · `3422bab` perbaikan impor tipe.

## 6. Yang belum / catatan jujur

- **Font tidak diganti** ke rekomendasi skill — keputusan pemilik, dan tetap konsisten
  dengan preferensi visualnya (beebots/ihgscreener/algentis).
- **Endpoint `design-tokens` belum dikonsumsi frontend** dan itu disengaja: arahnya
  terbalik (CSS sumbernya, API membacanya), jadi FE tidak perlu memanggilnya untuk render.
  Ia berguna untuk alat non-browser.
- 1 warning svelte-check di `EventFeed` = pola lama yang sudah ada di HEAD (props dibaca
  sekali saat mount), bukan regresi.
