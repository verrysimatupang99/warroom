# Revisi Total War Room — Draf untuk Disetujui

Disusun: **2026-10-09** · Status: **DRAF** · Sifat: dokumen pra-perencanaan (bukan kode).

> Rangkaian dokumen ini menyusun ulang fondasi War Room **dari nol secara nalar** —
> mundur sampai pra-perencanaan (model data/ERD, arsitektur) sampai rencana
> implementasi — dengan sudut pandang: *"kalau kami bikin tim kecil untuk proyek ini,
> kami hire posisi apa, dan pakai framework kerja apa."*
>
> **Nol kode produksi diubah** untuk menyusun dokumen ini. Semua klaim paham sumber
> yang bisa dijalankan ulang; klaim tanpa bukti ditandai `[asumsi]`.

## Urutan baca

1. **[00-ringkasan-dan-arah.md](00-ringkasan-dan-arah.md)** — fakta proyek (terverifikasi),
   analogi 5 kursi tim, tiga lapis framework, dan rencana R0–R6. **Baca ini dulu.**
2. **[01-model-data-erd.md](01-model-data-erd.md)** — peta **21 tabel** (dari kode) dan
   tiga celah model data yang tersisa.
3. **[02-tim-peran-framework.md](02-tim-peran-framework.md)** — detail tiap kursi
   (isi kerja, artefak, batas keras) + framework kerja (Shape Up / DORA-SRE / SDLC).
4. **[03-rencana-implementasi.md](03-rencana-implementasi.md)** — rencana R0–R6 dengan
   Definisi Selesai + bukti + rollback.

## Intisari 1 halaman

- Proyek ini **bukan startup**: 1 pengguna (owner), **uang nyata**, 7 pasar,
  **batas keselamatan sebagai fitur utama** (gate, `ci_low > BE`, paper/live terpisah).
- Kalau bikin tim: **5 kursi** — Quant/Risk · Backend/Platform · Frontend/Product ·
  SRE/Ops · QA/Verification. **Hire untuk risiko, bukan fitur.**
- Framework: **3 lapis** — Shape Up (apa yang dikerjakan), DORA/SRE (sistem hidup),
  SDLC repo (keselamatan). **SDLC yang sudah ada TIDAK diganti.**
- ERD **sudah 90% ada** di kode (**21 tabel**). Sisa: perluas `services`
  (status halus), tambah jejak **build↔proses**, perluas rekaman keputusan owner.
- **Pekerjaan paling mendesak: R0** — runbook deploy + verifikasi `build_id`.
  Ini menutup langsung penyebab War Room down 8–9 Okt.

## Yang dibutuhkan dari owner

1. Setujui/tolak arah revisi (dok 00–03).
2. Setujui **R0** sebagai pekerjaan pertama.
3. Jawab pertanyaan terbuka di akhir dok 01 dan 02.

## Catatan kejujuran

- Dokumen ini **draf**. Belum ada baris kode War Room yang diubah.
- Draf awal dok 01 sempat keliru (mengklaim tak ada `source_health`); sudah dikoreksi
  setelah verifikasi ulang — lihat §4.3 dok 01.
