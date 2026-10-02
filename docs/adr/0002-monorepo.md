# ADR-002 — Monorepo `~/warroom` + uv workspace, tanpa menyalin kode domain

Status: **diterima** · Tanggal: 2026-10-02 · Fase: P0

## Konteks

Platform baru (api, worker, llm, notifier, web) butuh satu tempat untuk struktur, CI, ops, dan
kontrak. Domain sudah hidup di repo lain (`~/live-trading`) dengan riwayat git dan 219 tesnya.
Menyalin kode domain ke monorepo akan menciptakan dua sumber kebenaran dan membuat perbaikan
domain tidak lagi mengalir ke platform.

## Keputusan

1. Repo baru `~/warroom` (git baru, riwayat domain **tidak** dipindahkan).
2. `uv` **workspace**: anggota di `packages/*` dan `services/*`; root virtual (`package = false`)
   yang menarik seluruh anggota supaya satu `uv sync` menyiapkan env dev lengkap.
3. `packages/core` bergantung pada `live-trading` lewat **path dependency**
   (`[tool.uv.sources] live-trading = { path = "../../../live-trading", editable = true }`).
4. **Tidak ada satu baris domain yang disalin.** Butuh fungsi baru → tambah di `live-trading`,
   ekspor ulang lewat façade.

## Konsekuensi

- Satu `uv sync` di `~/warroom` menyiapkan env dengan seluruh layanan + domain editable.
- `uv run python -c "import live_trading"` jalan dari `~/warroom` (bukti acceptance P0-T1).
- CI harus checkout dua repo berdampingan (`warroom/` dan `live-trading/`) agar path relatif resolve;
  ini konsekuensi nyata dan sudah ditulis di `.github/workflows/ci.yml`.
- Path sumber relatif di `[tool.uv.sources]` diselesaikan **relatif terhadap direktori anggota**
  (bukan root workspace). Pelajaran praktis: dari `packages/core`, live-trading ada di
  `../../../live-trading`. Salah satu level → `Distribution not found`.
- Repo `live-trading` tetap bisa diuji berdiri sendiri (`uv run pytest` → 219 lulus).

## Alternatif yang ditolak

- **Monorepo dengan git subtree/submodule**: riwayat bercampur atau ada langkah sync manual yang
  mudah lupa. Path dependency lebih sederhana dan tetap satu arah.
- **Salin domain ke `packages/core`**: dua sumber kebenaran. Ditolak.
- **Publish `live-trading` ke registry privat**: menambah rilis untuk kode yang berubah tiap hari;
  berlebihan untuk satu host.