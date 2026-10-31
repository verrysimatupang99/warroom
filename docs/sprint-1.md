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
  - Tes: `packages/live-trading` hijau; full suite saat itu **882 collected**, rc=0
    (angka kini 889 — lihat entri regresi di bawah).
  - Deploy: `warroom-worker` restart (job `collect` memakai kode baru).

### Selesai (lanjutan sesi 30 Okt, setelah US1.1)
- **US1.2 — Runbook trade pertama + bukti (3 SP).**
  - `docs/runbook-trade-pertama.md`: checklist T-30, syarat lanjut, alert watchdog,
    verifikasi `deals.csv`/API/DoD, template bukti, rollback.
  - Jujur: **belum diuji pasar** — belum ada trade nyata; bagian "Setelah deal" menunggu
    eksekusi pertama.
- **US1.3 — Panel status Reaper (3 SP).**
  - Panel sudah ada sejak `b85b7a6` (sesi, ATR, spread, RSI, EMA21/55, tren, alasan,
    umur evaluasi). Diverifikasi ulang lewat e2e baru
    `apps/web/e2e/cek_panel_reaper.spec.ts` → **1 passed (3,1 s)** terhadap produksi.
- **US1.4 — Watchdog telemetri & deal (3 SP).**
  - Job `forwardtest-watchdog` (60 s), handler membaca fakta `mt5_snapshot` +
    `deals.csv`. Alert `forwardtest/telemetri` bila umur > 120 s di sesi 08–09 hari
    kerja; `forwardtest/deal-hilang` bila `total_trades_today` EA > baris `deals.csv`
    selama > 5 menit. Pulih otomatis saat kondisi membaik.
  - Bukti live setelah restart worker 14:02:58:
    `last_status=ok`, `last_detail=umur=20s sesi=tidak total_hari_ini=0 deal_csv=0 selisih=0`.
  - Tes: 7 kasus di `services/worker/tests/test_forwardtest_watchdog.py` (stale di
    sesi/luar sesi, pemulihan, trade pertama hari itu, deal telat, tanpa telemetri).
- **US1.5 — Tracker DoD 20 trade/30 hari (2 SP).**
  - `warroom_core.forwardtest` + CLI `tools/forwardtest_status.py` (`--json`).
  - Output live 30 Okt: `Trade tertutup 0/20`, `hari 1/30`, `Fill belum deal 0`,
    `Deal tanpa fill 0`, catatan `deals.csv belum ada`.
  - Tes: 7 kasus di `packages/core/tests/test_forwardtest.py`.
- **Regresi & deploy.**
  - `pytest` root: **1077 terkumpul, 100% lulus**; perintah AGENTS
    (`services/*/tests packages/live-trading`): **889 terkumpul, lulus**.
  - `ruff check` pada semua berkas yang disentuh: bersih.
  - `warroom-worker` restart; job baru terdaftar (`jobs.didaftarkan: forwardtest-watchdog`).

### Berikutnya
- **Tunggu pasar:** trade pertama (US1.2 bagian eksekusi) — sesi 08–09 server berikutnya.
- Sprint 2 (6–12 Nov): US2.1 rekonsiliasi deal vs statement, US2.2 edge dari fills,
  US2.3 ADR sumber jurnal, US2.4 marker trade di kurva.

### Blocker
- Belum ada trade nyata; bukti trade pertama tidak bisa dibuat tanpa pasar.
- Keputusan owner masih terbuka: gate 90% vs 95%+deff, saldo demo $1.000 vs $10.000,
  jadwal rotasi kredensial.
