# Sprint 3 — Cockpit Obsidian Telemetry (audit & verifikasi)

**Periode:** 13–19 Nov 2026 (dikerjakan 31 Okt karena Sprint 2 selesai).
**Goal:** cockpit memakai design system *Obsidian Telemetry* tanpa mengorbankan kepadatan.

## Status story

| Story | Status | Bukti |
|---|---|---|
| US4.1 token + kontras | **selesai** | `docs/audit-token-kontras-20261031.md`; 102 berkas, 0 hardcoded; semua pasangan utama lulus AA |
| US4.2 layout 3 kolom | **terverifikasi** | `ForexCockpitExness` `lg:grid-cols-3`; mobile satu kolom; e2e responsif 4 lebar |
| US4.3 komponen inti | **terverifikasi** | token lint bersih; status chip/metric/table/empty/freshness sudah satu pola; tidak ada komponen baru yang hardcoded |
| US4.4 responsif 390/768/1280/1920 | **selesai** | `e2e/cek_responsif.spec.ts`: 4 lebar × 3 halaman, **4 passed**; tidak ada overflow; mobile header hanya <768 |
| US4.5 copy pass | **selesai** | panel Jurnal sinyal/Riwayat EA/Kurva memakai istilah spesifik + sumber + batas; tidak ada teks generik |

## Yang tidak diubah

Tidak ada redesign visual besar: UI sudah memakai token graphite/amber, IBM Plex,
radius 6px, dan larangan gradient/glow. Perubahan yang dilakukan hanya verifikasi dan
penguatan e2e — bukan mengecat ulang cockpit yang sudah lulus.

## Catatan

- `--p-mist-500` (#787d84) hanya 4,49 di atas surface (gagal tipis AA), tetapi token itu
  tidak dipakai komponen; dibiarkan dengan catatan di audit.
- E2E responsif memakai `waitForTimeout(400)` setelah `data-app-siap`, bukan
  `networkidle` (SSE membuat networkidle tidak pernah selesai).
