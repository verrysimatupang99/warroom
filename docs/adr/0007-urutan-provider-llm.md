# ADR-007 — Urutan provider LLM: qonek → kiyara → nutaraline (hemat biaya)

Status: **diterima** · Fase: sektor LLM & Agent

## Konteks

Bentuk baku `default_config()` lama hanya tahu dua provider (`nutaraline` → `qonek`) padahal
armada nyata punya tiga: `kiyararouter.web.id` dipakai sebagai provider utama orkestrator OMP
(135 prompt, 26 Sep–6 Okt) dengan fallback `qonek` → `nutaraline` — lihat
`docs/belajar/inventaris-tencent-2026-10-06.md`. Catatan kesehatan terbaru (AGENTS.md, item
menunggu owner; `docs/belajar/revisi-owner-2026-10-07.md`): `nutaraline` sempat 401 dan lambat
dengan `qonek` menyelamatkan; `kiyara` sempat sering `schema_invalid`; sembilan Okt semua
endpoint kembali HTTP 200. Harga per provider belum pernah diukur, jadi urutan mata uang tidak
bisa dibuktikan — yang bisa dibuktikan adalah kesehatan dan latensi.

## Keputusan

1. Bentuk baku (tanpa `/etc/warroom/llm.json`) memakai rantai **qonek → kiyara → nutaraline**.
2. Alasan "hemat biaya" yang bisa dipertanggungjawabkan tanpa data harga: provider yang
   sehat dan tanggap ditaruh depan agar generasi berbayar yang berakhir gagal/retry minimum,
   dan kedalaman fallback (ADR-004) tetap tiga. Urutan sebenarnya di produksi tetap milik
   `/etc/warroom/llm.json` (root-only) — berkas itu adalah sumber kebenaran.
3. `pricing` ketiga provider tetap nilai placeholder konservatif dan wajib ada untuk SEMUA
   anggota rantai karena budget fail-closed memblokir seluruh panggilan bila satu saja
   tak berharga. Tarif riil menunggu konfirmasi owner.
4. `kiyara` ditambahkan ke bentuk baku dengan `keyEnv: KIYARA_API_KEY` dan model
   `deepseek-ai/deepseek-v4.1-flash` (dari config OMP). Nama env var di produksi mengikuti
   berkas root.

## Konsekuensi

- Tes `test_config.py` mengunci urutan baku dan menuntut `pricing` menutup seluruh rantai.
- Mengaktifkan urutan ini di live butuh penyuntingan `/etc/warroom/llm.json` (root-only,
  dilarang untuk agen) — sisa tanggung jawab owner.
- Setelah tarif riil tercatat, urutan boleh dihitung ulang dari biaya per 1k token, bukan
  dari selera.

## Alternatif yang ditolak

- **Biarkan urutan lama (nutaraline depan)**: provider yang lambat/sering 401 memakan
  latensi dan menghasilkan panggilan berbayar yang gagal sebelum fallback jalan.
- **Pesan urutan berdasarkan harga placeholder**: semua diberi harga sama, jadi tidak
  membedakan apa pun — pembandingnya palsu, bukan hemat biaya.
- **Hapus satu provider dari rantai**: merusak kedalaman fallback ADR-004.
