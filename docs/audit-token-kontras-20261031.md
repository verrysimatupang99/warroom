# Audit token & kontras — 31 Okt 2026

**Lingkup:** `apps/web/src/app.css` (3 lapis token) + komponen yang dipakai cockpit.
**Alat:** `node scripts/lint-tokens.mjs src` dan perhitungan WCAG 2.1 kontras.

## Hasil token

- **102 berkas `.svelte`**, **0 nilai warna/ukuran hardcoded** di komponen.
- Token primitif → semantic → component konsisten; tidak ada hex mentah di komponen.
- `--color-text-3` memakai `--p-mist-300`, bukan `--p-mist-500`; `--p-mist-500`
  tidak dipakai di komponen mana pun.

## Kontras pasangan utama (WCAG 2.1)

| Pasangan | Rasio | AA normal (4.5) |
|---|---:|---|
| `text` #ededec / `surface` #121314 | 15,88 | lulus |
| `text-2` #a6aab0 / `surface` #121314 | 7,97 | lulus |
| `accent` #f5b83d / `surface` #121314 | 10,46 | lulus |
| `pos` #3cc76b / `surface` #121314 | 8,48 | lulus |
| `neg` #f2604f / `surface` #121314 | 5,81 | lulus |
| `on-accent` #0c0d0e / `accent` #f5b83d | 10,94 | lulus |
| `text-2` #a6aab0 / `surface-2` #16181a | 7,63 | lulus |
| `neg` #f2604f / `surface-2` #16181a | 5,56 | lulus |

Tidak ada pasangan teks/latar yang gagal AA untuk teks normal. `--p-mist-500` (#787d84)
di atas surface hanya 4,49 (gagal tipis), tetapi token itu **tidak dipakai** di komponen;
tidak perlu diubah. Jika kelak dipakai, ganti ke `#7d8289` atau `--p-mist-300`.

## Temuan & tindakan

1. **Tidak ada pelanggaran token** — tidak ada perubahan warna.
2. **Bar mobile** sudah disembunyikan di `min-width: 768px`; diverifikasi e2e.
3. **Kepadatan**: kartu 12px, grid 8px, baris 36px; cockpit forex memakai 3 kolom
   desktop (`lg:grid-cols-3`) dan satu kolom di mobile.
4. **Copy panel baru** (Jurnal sinyal, Riwayat evaluasi EA, Kurva ekuitas) sudah
   spesifik: menyebut sumber, waktu, dan batas; tidak ada kalimat generik.

**Status US4.1:** selesai (audit + bukti). Tidak ada perubahan visual yang diperlukan.
