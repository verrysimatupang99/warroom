# Sprint 2 — log harian

**Goal:** *Jurnal bisa diaudit.*
**Periode resmi:** 6–12 Nov 2026.
**Catatan:** US2.1 dan US2.2 ditarik maju **30 Okt 2026** karena seluruh Sprint 1
selesai kecuali bukti trade pertama yang menunggu pasar. Sprint 2 tetap dievaluasi
pada jendela resminya.

---

## 30 Okt 2026 — ditarik maju

### Selesai

- **US2.2 — Edge eksekusi dari fills (3 SP).**
  - Implementasi sudah ada di `warroom_api.lokal.journal_edge`: slippage per jam dan
    per simbol, latensi rata-rata, dan `503` hanya bila `fills.csv` benar-benar kosong.
  - Yang ditambahkan: 3 tes yang mengunci perilaku itu
    (`services/api/tests/test_jurnal_lokal.py`): pengelompokan jam/simbol, kasus kosong,
    dan penolakan market crypto dengan alasan.
  - Bukti: `pytest services/api/tests/test_jurnal_lokal.py` → **9 passed**.
  - Tidak ada perubahan perilaku; ini verifikasi, bukan fitur baru.

- **US2.1 — Rekonsiliasi `deals.csv` vs statement MT5 (3 SP).**
  - Modul `warroom_core.rekonsiliasi_deal`:
    - parser statement MT5 (UTF-16LE/BOM atau UTF-8), hanya baris `Direction=out`;
    - net = profit + swap + commission;
    - cocokkan per tiket deal, selisih > toleransi (default $0,01) = temuan;
    - laporkan deal yang hanya ada di statement / hanya di `deals.csv`, duplikat,
      dan filter periode `--sejak/--sampai`.
  - CLI `tools/rekonsiliasi_forwardtest.py` — exit `0` cocok, `1` selisih,
    `2` statement tidak terbaca / tidak ada deal `out`.
  - `tools/ea_jurnal.py` sekarang memakai parser yang sama (tidak ada dua aturan).
  - Tes: `packages/core/tests/test_rekonsiliasi_deal.py` → **11 passed**.
  - Bukti sintetis: statement 2 deal (net $12,00) vs `deals.csv` (net $11,90) →
    `SELISIH ticket=102 … diff=-0.10`, exit 1. Sesuai harapan.
  - Batas jujur: **belum ada statement nyata** untuk periode demo; angka nyata baru
    bisa direkonsiliasi setelah trade pertama.

### Berikutnya

- **US2.3 — ADR sumber kebenaran jurnal** (`trades` DB vs `deals.csv`).
- **US3.2 — scanlog forex vs crypto terpisah** di tab Sinyal.
- **US2.4 — marker trade di kurva ekuitas** (butuh deal nyata).

### Blocker

- Trade/statement nyata belum ada; US2.1 baru terbukti pada data sintetis.
- PR #61 (Sprint 1) menunggu review/merge. Branch Sprint 2
  (`feat/rekonsiliasi-jurnal`) di atas branch itu; PR-nya di-retarget ke `main`
  setelah #61 merge.
