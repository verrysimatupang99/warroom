# 03 — Rencana Implementasi

Disusun: 2026-10-09 · Status: **DRAF untuk disetujui owner**

> Menutup rangkaian dok revisi total: **00** (arah) → **01** (model data) →
> **02** (tim & framework) → **03** (rencana, dokumen ini).
> Setiap pekerjaan di sini punya **Definisi Selesai + bukti**, sesuai aturan repo.

---

## 1. Prinsip penyusunan rencana

1. **Kerjakan yang sudah terbukti merugikan dulu.** Kejadian 8–9 Okt bukan hipotesis —
   War Room benar-benar down. Itu jadi R0.
2. **Satu pekerjaan = satu pitch kecil.** Tidak ada "lalu dst".
3. **Tidak ada pekerjaan yang menyentuh ambang gate / rumus BE.** Itu domain owner.
4. **Setiap pekerjaan punya jalur rollback.**

---

## 2. Urutan pekerjaan (R0–R6)

### 🔴 R0 — Runbook deploy + verifikasi wajib (PALING MENDESAK)

- **Masalah:** build web (8 Okt 21:00) tidak diikuti restart (proses dari 20:58) →
  War Room 500 sampai ketahuan kebetulan. **Tidak ada jejak versi build↔proses.**
- **Kursi:** SRE.
- **Kerja:** (a) `ops/deploy.md`; (b) `/api/v1/health` kembalikan `build_id`;
  (c) skrip deploy yang **gagal** kalau build_id ≠ proses.
- **Definisi Selesai + bukti:** jalankan skrip di staging; tunjukkan output saat
  build_id cocok (hijau) dan saat tidak cocok (merah). Tautkan ke insiden 8–9 Okt.
- **Rollback:** skrip opsional; endpoint `/health` tambah field, tak hapus yang ada.
- **Risiko kalau salah:** minimal — perubahan aditif.

### 🟠 R1 — Perbaiki & jalankan E2E War Room

- **Masalah:** "E2E 27 hijau" ternyata gagal total. Akar hari ini: **produksi 500**
  (sudah diperbaiki via restart) — tapi **mekanisme sesi tetap rapuh** (sesi mati,
  storageState basi).
- **Kursi:** QA.
- **Kerja:** jalankan E2E **bertahap** (`--workers=1`, subset dulu — run penuh OOM);
  perbaiki `globalSetup` supaya sesi di-refresh otomatis tiap run.
- **DoD + bukti:** output Playwright yang bisa dibaca; hijau ATAU kegagalan nyata
  terdokumentasi. Tidak ada lagi "gagal karena sesi".
- **Rollback:** perubahan hanya di `e2e/`, tak menyentuh produksi.
- **Catatan:** jangan jalankan suite penuh bersama worker produksi (OOM).

### 🟡 R2 — Koreksi angka README War Room

- **Masalah:** README bilang **761** (Python), **219** (domain), **35** (web).
  Kenyataan terverifikasi: **806 / 227 / 36**.
- **Kursi:** QA.
- **DoD + bukti:** README cocok dengan `pytest --collect-only` & `vitest run`.
- **Rollback:** trivial.
- **Bonus:** tambahkan catatan **jujur** soal E2E (jangan klaim 27 hijau kalau belum).

### 🟢 R3 — Perluas status kesehatan sumber (celah C1)

- **Masalah:** `services.status` belum punya state halus
  (`paused/frozen/degraded/unreachable`) — P1 backlog.
- **Kursi:** Backend + SRE.
- **Kerja:** **perluas tabel `services`** (bukan tabel baru) + endpoint + tampilan.
- **DoD + bukti:** migrasi Alembic + tes; tunjukkan state baru muncul saat sumber
  di-set paused.
- **Rollback:** migrasi reversibel.

### 🟢 R4 — Rekam keputusan owner pada perubahan ambang (celah C3)

- **Masalah:** `parameters` berversi, tapi tidak ada tautan
  **perubahan → tanda tangan owner + alasan**.
- **Kursi:** Owner + Backend.
- **DoD + bukti:** perubahan ambang mustahil tanpa jejak keputusan.
- **Batas keras:** **mekanisme ini tidak boleh menyentuh nilai ambang/BE itu sendiri.**

### 🔵 R5 — CI War Room (bukan hanya Komuter)

- **Masalah:** Komuter kini punya CI (commit `ce75e02`); **War Room belum.**
- **Kursi:** QA + SRE.
- **Kerja:** GitHub Actions: 806 + 36 tes + lint + build web + verifikasi `build_id`
  (nyambung ke R0).
- **DoD + bukti:** PR pertama yang gagal karena tes merah, dan lulus saat hijau.

### 🔵 R6 — SOP postmortem tanpa menyalahkan

- **Masalah:** kejadian 8–9 Okt belum jadi pelajaran permanen.
- **Kursi:** SRE + Owner.
- **Kerja:** dokumen SOP + **1 postmortem nyata** (kejadian 8–9 Okt) sebagai contoh.
- **DoD + bukti:** dokumen ada dan insiden pertama tercatat.

---

## 3. Peta ketergantungan

```
R0 (deploy+verifikasi) ──► R5 (CI War Room, pakai build_id)
R1 (E2E) ──► R2 (angka tes jujur)
R3 (source_health) ─┐
R4 (keputusan owner)┘─► (keduanya independen)
R6 (postmortem) ── berdiri sendiri; sebaiknya setelah R0
```

**Urutan usul:** R0 → R1 → R2 → R6 → R3 → R4 → R5.
Alasan: R0 menyelamatkan (baru kena); R1/R2 mengoreksi kebohongan dokumen;
R6 mengabadikan pelajaran; R3–R5 perbaikan lebih besar.

---

## 4. Yang TIDAK ada di rencana ini (sengaja)

- **Tidak** menyentuh `gate.py`, rumus BE, ambang, atau status live (NO-GO tetap).
- **Tidak** membuat/menghapus `/etc/poly-pilot/activation-approved`.
- **Tidak** menyalakan unit eksekusi.
- **Tidak** menambah infrastruktur (K8s, queue) — 1 server cukup.
- **Tidak** memorting domain ke bahasa lain (melanggar ADR-001).
- **Tidak** "destroy & rebuild" — 193 commit + data non-git tidak layak dibuang.

---

## 5. Ringkasan & permintaan keputusan

| # | Pekerjaan | Kursi | Prioritas |
|---|---|---|---|
| R0 | Runbook deploy + verifikasi `build_id` | SRE | 🔴 |
| R1 | Perbaiki & jalankan E2E | QA | 🟠 |
| R2 | Koreksi angka README | QA | 🟡 |
| R3 | Perluas `services` (source health) | Backend+SRE | 🟢 |
| R4 | Rekam keputusan owner | Owner+Backend | 🟢 |
| R5 | CI War Room | QA+SRE | 🔵 |
| R6 | SOP postmortem | SRE+Owner | 🔵 |

**Saya minta darimu:**
1. **Setujui/tolak arah revisi total ini** (dok 00–03).
2. **Setujui R0** sebagai pekerjaan pertama? (paling terbukti dibutuhkan)
3. Kalau setuju, apakah saya **kerjakan R0 sekarang** (bikin runbook + `build_id`),
   atau kamu mau tinjau dokumennya dulu?

> **Catatan kejujuran:** dokumen ini **draf**. Nol kode produksi diubah untuk
> menyusunnya. Saya menunggu persetujuan sebelum mengerjakan R0 dan seterusnya.
