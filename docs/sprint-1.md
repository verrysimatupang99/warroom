# Sprint 1 — log harian

**Goal:** *Tidak ada trade tanpa bukti.*  
**Periode:** 30 Okt–5 Nov 2026  
**Tim:** A (domain/API/EA), B (web/QA/desain)

---

## 30 Okt 2026

### Selesai
- **US1.1 — Gate exposure membaca posisi paper nyata (5 SP).**
  - `engine.scan()` kini memuat `paper_positions.json` lewat `posisi_paper_crypto()` dan
    mengoper `open_positions` ke `evaluate()`.
  - `gates.exposure` memakai batas dari settings: **3 total**, **2 searah**; alasan
    menyebut angka.
  - Bukti dengan state live:
    - `SHORT` → `2/2 posisi searah SHORT — korelasi terlalu tinggi` (ditolak).
    - `LONG` → `2/3 posisi, 0/2 searah — aman`.
  - Tes: `packages/live-trading` hijau; full suite **882 collected**, rc=0.
  - Deploy: `warroom-worker` restart (job `collect` memakai kode baru).

### Berikutnya
- US1.2 runbook trade pertama (B).
- US1.3 panel status Reaper di cockpit (B).
- US1.4 watchdog deal & telemetri (A).
- US1.5 tracker DoD 20 trade/30 hari (B).

### Blocker
- Belum ada trade nyata; US1.2 baru bisa diuji penuh saat sesi 08–09 berikutnya.
- OMP perlu reload sekali lagi agar server REA memuat `GHIDRA_INSTALL_DIR`
  (Ghidra 12.1.4 sudah `available` pada proses baru).
