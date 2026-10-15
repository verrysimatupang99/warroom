# apps/web — War Room SvelteKit Frontend

Aplikasi antarmuka pengguna War Room yang dibangun menggunakan SvelteKit 2, Svelte 5 (runes), Tailwind CSS, dan adapter-node (berjalan pada port 3100).

## Arsitektur & Prinsip Desain

1. **Konsumsi Murni Tanpa Logika Domain**: Antarmuka hanya menampilkan fakta (`facts`) dan bukti dari API. Tidak ada kalkulasi angka atau inferensi trading di sisi UI.
2. **Sinkronisasi SSOT (Single Source of Truth)**: State navigasi dan tab dikontrol langsung oleh URL query parameter (`?sub=...`), mencegah inkonsistensi status pada riwayat peramban.
3. **Pembaruan Reaktif Real-Time**:
   - `src/lib/api/live.svelte.ts`: Mengelola sambungan Server-Sent Events (SSE) dengan mekanisme fallback otomatis ke REST polling saat jaringan terganggu.
4. **Desain Serene Capital**: Palet warna kontras gelap bernuansa terminal profesional dengan tipografi proporsional untuk kemudahan membaca cepat metrik risiko dan performa.

## Struktur Komponen Utama

| Direktori / Komponen | Fungsi |
|---|---|
| `src/routes/` | Rute halaman (`/`, `/areas/[kunci]`, `/masuk`, `/sistem`, dll.) |
| `src/lib/components/AreaView.svelte` | Tampilan instrumen pasar multi-tab |
| `src/lib/components/AreaLoader.svelte` | Wrapper pemuatan data fakta dan indikator kesegaran |
| `src/lib/components/DecisionFeed.svelte` | Kronologi keputusan entri dan exit trade |
| `src/lib/components/FreshnessBadge.svelte` | Lencana status kesegaran data (online/stale/error) |
| `src/lib/components/SubNav.svelte` | Navigasi sub-tab instrumen pasar |
| `src/lib/api/` | Klien REST API dan live state reactive |

## Menjalankan & Pengujian

```bash
# Menjalankan dev server
npm run dev

# Memeriksa tipe data TypeScript dan template Svelte
npm run check

# Menjalankan unit test Vitest
npm test

# Menjalankan end-to-end test Playwright (membutuhkan instance aktif)
npx playwright test
```
