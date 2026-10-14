# Peta Pelunasan Tech Debt — War Room

Disusun dari audit 14 Okt 2026 (semua temuan diverifikasi lewat perintah langsung).
Prinsip: **jujur soal prioritas** — safety/kebenaran dulu, kosmetik terakhir.
Ini *usulan*, bukan rencana yang sudah disetujui.

## Legenda prioritas

- **P0** — risiko kebenaran/keselamatan; kerjakan sebelum fitur baru.
- **P1** — biaya perubahan nyata (setiap perubahan fitur memperlambat diri sendiri).
- **P2** — kebersihan & akurasi dokumen; bisa dicicil.
- **P3** — kosmetik/opsional.

---

## P0 — Segera (sudah dikerjakan sebagian lewat PR #3)

| # | Item | Status | Sisa kerja |
|---|------|--------|------------|
| P0-1 | Jejak git hilang: 30 berkas live-gate hanya di working tree | **SELESAI** (PR #3 merged 14 Okt) | — |
| P0-2 | `SAWarning` teardown `test_schedule.py:23` (DELETE 27 baris, 0 cocok) | **SELESAI** (PR #5; diverifikasi 15 tes lulus `-W error::Warning`) | — |
| P0-3 | `ci-local.sh` uji repo luar `~/live-trading` → merah-palsu 7 tes | **SELESAI** (PR lanjutan) | Sudah diarahkan ke `packages/live-trading`; SEMUA HIJAU |

**Definisi selesai P0:** PR #3 merged ✓, `ops/ci-local.sh` hijau ✓, warning teardown ✓.

---

## P1 — Minggu ini (biaya perubahan nyata)

| # | Item | Alasan | Ukuran keberhasilan | Status |
|---|------|--------|---------------------|--------|
| P1-1 | **Satu kontrak gate/sinyal.** | "Siapa pemilik runutan sinyal per pasar?" tak punya satu jawaban | Satu modul kanonik; sisanya shim terdokumentasi | **SELESAI** (docstring batas peran di `signal.py`/`market_signal.py`/`verdict.py`, PR #23) |
| P1-2 | **Pecah 3 file raksasa** | `dashboard.py` 2.371 / `app.py` 1.449 / `jobs.py` 1.325 baris | Tiap file < ~600 baris | **SELESAI** (`app.py` 373; `jobs/` & `dashboard/` jadi paket; penjaga `ops/check-file-size.py`) |
| P1-3 | **`idx616/` keluar dari pengecualian lint** | satu-satunya mesin tanpa linter | `ruff` mencakup `idx616/` | **SELESAI** (14 Okt: ruff `idx616/` All checks passed) |

---

## 🆕 P0 — Ditemukan 14 Okt (pasca-cutover)

| # | Item | Catatan |
|---|------|---------|
| **P0-4** | **Migrasi DB dijalankan MANUAL** — produksi tertinggal 3 revisi (`a1f2b3c4d5e6` → head) saat ditemukan; `users.totp_last_counter` (anti-replay TOTP, PR #3) tak pernah ada di DB walau kode aktif | Tambah mekanisme: `ExecStartPre` alembic **atau** langkah CI/deploy yang memaksa `upgrade head`, + tes "DB di head". Sudah diterapkan sekali (14 Okt 18:44); **cegah kambuh**. |

---

## P2 — Bisa dicicil (kebersihan & dokumen)

| # | Item | Status |
|---|------|--------|
| P2-1 | AGENTS.md: "761 tes" → **815** | **SELESAI** (14 Okt) |
| P2-2 | AGENTS.md: Caddy → **nginx** | **SELESAI** (14 Okt) |
| P2-3 | `.venv-merge/` (298 MB) | **SELESAI** (dihapus 14 Okt) |
| P2-4 | `.git` 141 MB | Dipantau; **tidak** `filter-branch` sembarangan (risiko riwayat bersama) |

### 🆕 Ditemukan 14 Okt (sesi lanjutan)

| # | Item | Status |
|---|------|--------|
| P2-5 | **27 import relatif rusak** di `dashboard/panels.py` pasca-pecah `dashboard/` (PR #21) — dashboard produksi rusak senyap berhari-hari, lolos CI karena tak ada tes yang memanggil `build_snapshot` | **SELESAI** (PR #28: perbaikan + `test_dashboard_smoke.py`) |
| P2-6 | **Job dobel jalan**: baris job nama lama (`retensi`/`rekonsiliasi-crypto`) tak terbersihkan saat rename — migrasi `c3d5e7f9a1b2` terlewat karena `ensure_jobs` sudah bikin baris baru | **SELESAI** (PR #27: migrasi `d4e6f8a0b2c3`) |
| P2-7 | **Disk hampir penuh** (88%, 6,2 GB) | **SELESAI** sebagian (14 Okt: cache npm/pip/uv, /tmp APK, backup web lama — bebas ~600 MB+) |

---

## P3 — Opsional

- **SELESAI** — `docs/` bertanggal lama diarsipkan ke `docs/arsip/` (8 berkas).
- **SELESAI** — anggaran baris per berkas di CI: `ops/check-file-size.py` (warn 800, gagal 1000).
- **BARU** — `ops/arsip-reset-market.py` + `ops/check-db-head.py` (pencegahan migrasi tertinggal).

---

## Yang TIDAK masuk peta (bukan utang — kredit tim)

Ruff bersih di 51k LOC · 0 SQL f-string mentah · 0 `console.log` · 0 file `.bak`
· CI least-privilege + timeout + gitleaks · disiplin "kejujuran angka" nyata di kode.

---

## Pertanyaan terbuka untuk owner (belum dijawab)

1. `fix/sprint-6-pemblokir-live` = rilis pemblokir-live, atau branch kerja eksploratif?
2. Urutan P1: setuju "pecah `app.py` dulu", atau utamakan P1-1 (kontrak gate)?
3. PNG `docs/bukti-p2/` — cukup keluar dari git (PR #3), atau perlu arsip terpusat?
