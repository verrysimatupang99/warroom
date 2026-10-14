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
| P0-2 | `SAWarning` teardown `test_schedule.py:23` (DELETE 27 baris, 0 cocok) | belum | Bikin teardown eksplisit; aman terhadap `-W error` |
| P0-3 | `ci-local.sh` uji repo luar `~/live-trading` → merah-palsu 7 tes | **SELESAI** (PR lanjutan) | Sudah diarahkan ke `packages/live-trading`; SEMUA HIJAU |

**Definisi selesai P0:** PR #3 merged ✓, `ops/ci-local.sh` hijau ✓, sisa: warning teardown.

---

## P1 — Minggu ini (biaya perubahan nyata)

| # | Item | Alasan | Ukuran keberhasilan |
|---|------|--------|---------------------|
| P1-1 | **Satu kontrak gate/sinyal.** `signal.py` (5,5 KB) + `sinyal.py` (39,6 KB) + `verdict.py` + `live_trading/signals/gates.py` — dua nama (EN/ID) untuk konsep nyaris sama | "Siapa pemilik runutan sinyal per pasar?" tak punya satu jawaban | Satu modul kanonik; sisanya shim terdokumentasi |
| P1-2 | **Pecah 3 file raksasa** (bertahap, satu per PR) | `dashboard.py` 2.371 baris / 46 def, `app.py` 1.449 / 46 rute, `jobs.py` 1.325 / 37 def | Tiap file < ~600 baris; 30 `type: ignore` di dashboard turun |
| P1-3 | **`idx616/` keluar dari pengecualian lint** | 137 format legacy; satu-satunya mesin tanpa linter | `ruff` mencakup `idx616/`; exclusion dihapus |

**Urutan disarankan:** P1-2 dulu untuk `app.py` (paling sering disentuh, pemisahan per-router jelas), baru P1-1, baru P1-3.

---

## P2 — Bisa dicicil (kebersihan & dokumen)

| # | Item | Catatan |
|---|------|---------|
| P2-1 | AGENTS.md: "761 tes" → **815** | Dokumennya sendiri bilang "sumber kebenaran = output perintah" |
| P2-2 | AGENTS.md: Caddy → **nginx** di bagian "Perintah harian" | Sudah kontradiksi internal dgn bagian Deploy |
| P2-3 | `.venv-merge/` (216 MB) — env uji F3, vestigial | Hapus setelah F3 tuntas; sudah di `.gitignore` |
| P2-4 | `.git` 141 MB | Setelah PNG keluar (PR #3), pantau; jangan `filter-branch` sembarangan |

---

## P3 — Opsional

- Rapikan `docs/` yang menumpuk (banyak file bertanggal 08 Okt 2026 — arsipkan ke `docs/arsip/`).
- Pertimbangkan `budget` baris per file di CI (mis. warn bila file > 800 baris) agar P1-2 tidak kambuh.

---

## Yang TIDAK masuk peta (bukan utang — kredit tim)

Ruff bersih di 51k LOC · 0 SQL f-string mentah · 0 `console.log` · 0 file `.bak`
· CI least-privilege + timeout + gitleaks · disiplin "kejujuran angka" nyata di kode.

---

## Pertanyaan terbuka untuk owner (belum dijawab)

1. `fix/sprint-6-pemblokir-live` = rilis pemblokir-live, atau branch kerja eksploratif?
2. Urutan P1: setuju "pecah `app.py` dulu", atau utamakan P1-1 (kontrak gate)?
3. PNG `docs/bukti-p2/` — cukup keluar dari git (PR #3), atau perlu arsip terpusat?
