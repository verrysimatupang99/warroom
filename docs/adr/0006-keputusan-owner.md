# ADR-006 — Keputusan owner yang mengikat (ambang, promosi, target uji)

Status: **diterima** · Tanggal: 2026-10-09 · Fase: R4 (revisi total)

## Konteks

Beberapa keputusan di sistem ini **bukan** keputusan teknis agen, melainkan keputusan pemilik
produk. Bila keputusan-keputusan itu hanya hidup di kepala owner atau di percakapan, tiap agen
baru akan mengarang tafsir sendiri — persis kelas kesalahan yang proyek ini coba hindari
("jangan mengarang angka"). ADR ini merekamnya sebagai aturan tetap.

## Keputusan

1. **Ambang & rumus gate = hak owner.** Angka `n ≥ 30`, `ci = 0.90`, `ci_low > BE`, dan rumus
   BE **hanya boleh diubah manusia**. Agen/LLM tidak pernah mengubahnya (memperjelas ADR-003).
   Hasil eksplorasi tetap tidak bisa dipromosikan tanpa sampel baru + split beku.

2. **Promosi live = NO-GO sampai owner memutuskan.** Selama split beku belum ada, gate
   mengembalikan `insufficient` (dengan alasan), bukan `lolos`. Keputusan kebijakan
   (90% vs 95%+deff) ada di owner, bukan di agen.

3. **Tidak ada angka di UI/AI tanpa baris `facts`.** Setiap angka yang tampil harus dapat
   dilacak ke baris `facts`; `events` append-only menautkan `fact_ids` sebagai bukti (ADR-005).
   Sumber tak terbaca → `tidak-izin`/`n/a`, bukan angka tebakan.

4. **E2E wajib lewat origin produksi (`https://0xgunsl1ng3r.xyz`).** nginx yang mem-proxy
   `/api/` → API `:8800`. Menjalankan Playwright langsung ke `127.0.0.1:3100` (node mentah,
   tanpa nginx) membuat `/api/v1/auth/login` → 404 → sesi gagal → semua tes ber-sesi jatuh ke
   form login dengan gejala menyesatkan ("timeout", bukan "belum login"). *(R1 membuktikan ini:
   run salah target melaporkan 14 gagal; run di origin benar menyisakan 2 tes.)*

5. **Gate live tidak pernah disentuh agen.** Agen tidak menyalakan unit eksekusi dari API dan
   tidak membuat/menghapus `/etc/poly-pilot/activation-approved`. Perubahan produksi
   (restart, deploy) hanya setelah persetujuan eksplisit owner.

6. **Ubah produksi butuh approval eksplisit.** Restart unit, menimpa `build/`, mengubah vhost —
   semuanya menunggu kata owner. Setiap `build/` baru **wajib** diikuti restart unit yang
   memegang manifest lama (temuan insiden 9 Okt: proses node lama bertahan memegang chunk yang
   sudah hilang → HTTP 500 di semua rute).

## Konsekuensi

- ADR ini menjadi rujukan tunggal saat ada keraguan "siapa yang berhak memutuskan X".
- Setiap agen yang menyentuh gate/ambang/promosi **wajib** berhenti dan bertanya ke owner.
- Runbook E2E (R0) memakai origin produksi sebagai default — lihat `docs/revisi-total/`.

## Alternatif yang ditolak

- **Biarkan keputusan di kepala owner saja**: tiap agen baru menafsir ulang → risiko mengubah
  ambang yang seharusnya tetap.
- **Serahkan ambang ke agen/LLM**: melanggar ADR-003 dan membuat "lolos" bisa bergeser tanpa
  jejak audit.
