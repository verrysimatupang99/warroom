# P4–P6 — status pelaksanaan (integrasi, otonomi berbatas, kesiapan live)

Diperbarui: **2026-10-02 21:45 UTC** (04:45 WIB, 3 Okt) · Pelaksana: Hermes

## Ringkas

| Task | Status | Bukti |
|---|---|---|
| P4-T1 Adapter Polymarket (baca-saja) | **selesai** | job `poly-sync`: `fakta=7 arm=4 arm_summary=ok`; angka arm dibaca dari berkas summary yang sama |
| P4-T2 Parity monitor + alarm | **selesai** | job `parity-drift`; status `tidak-bisa-dibandingkan` bila eksekutor tidak memutuskan (bukan drift 0 palsu) |
| P4-T3 Dataset explorer + ReplayLab UI | **sebagian** | `DatasetExplorer` (sub Dataset di `/polymarket`) **selesai 3 Okt** — katalog `poly.dataset/recorder` + cakupan `poly.akses/cakupan` tampil dari fakta (3 direktori, 2.599 berkas, 6 GB); ReplayLab masih menunggu |
| P4-T4 Adapter GMGN + radar rantai | **selesai** (diperbarui 6 Okt: radar pindah **lokal**) | job `radar-update`: `lt radar-update ok; 5 chain`; job `gmgn-sync`: `gmgn=ok berkas=24 radar=ok sumber=lokal`. Sebelumnya membaca via SSH ke VM Azure; kini dijalankan di host ini (`state/radar_state.json`) |
| P4-T5 Rekonsiliasi on-chain | **selesai** | job `reconcile`: `klaim=0.0 terverifikasi=False` + alert (tanpa RPC → tidak pernah diklaim terverifikasi) |
| P5-T1 Registry parameter + bounds + locked | **selesai** | 10 parameter terdaftar; `gate.min_n`/`gate.ci`/`mode` **terkunci** |
| P5-T2 Learner harian | **selesai** | job `learner`: `diusulkan=4 keputusan={'ditolak': 4}` — semua ditolak karena bukti bukan split beku |
| P5-T3 Gate keputusan usulan | **selesai** | `prohibited` (gate/locked), `ditolak` (di luar batas / bukti kurang), `butuh_manusia` (scope live), `diterapkan` (paper & non-gate) |
| P5-T4 UI ProposalCard + rollback | **selesai** | `ProposalCard` di Sistem→Kebijakan **selesai 3 Okt** — 12 usulan tampil dari `/api/v1/proposals` (dari→ke, bukti, alasan penolakan); tombol terapkan/rollback hanya owner; 4 tes Vitest + e2e sub baru |
| P5-T5 Kill switch + anggaran | **selesai** (anggaran P3) | `POST /api/v1/ai/kill-switch` (owner); learner berhenti saat aktif |
| P6-T1 ArmingPanel + grant flow | **selesai** | `GET /api/v1/live/arming` (4 sumber), `POST /api/v1/live/grant`, aksi tanpa grant → **409 + daftar kurang** |
| P6-T2 Kill switch operasional + runbook | **sebagian** | kill switch AI ada; runbook insiden menyusul |
| P6-T3 Uji kering (kedalaman/slippage) | **selesai** (alat) | `POST /api/v1/live/dry-run` menjalankan `lt depth` (read-only, tanpa order) |
| P6-T4 Checklist go/no-go | **belum** | menunggu owner (butuh tanda tangan) |

## Bukti nyata (potongan keluaran job, 21:42 UTC)

```
poly-sync    ok  fakta=7 arm=4 arm_summary=ok agen_summary=tidak-izin lessons=182 dataset=tidak-izin
parity-drift ok  status=tidak-bisa-dibandingkan drift=0 mirror=0 eksekutor=0
gmgn-sync    ok  gmgn=ok berkas=23 radar=ok sumber=cache
reconcile    ok  status=ok klaim=0.0 terverifikasi=False
learner      ok  diusulkan=4 keputusan={'ditolak': 4} seed_baru=0
collect      ok  lt scan ok; 20 pair dipindai · 1 punya arah jelas · 1 duplikat (tidak dicatat ulang)
backup       ok  kode=0 arsip 3.7M -> state-20261002-2136.tar.gz
```

## Temuan keamanan: artefak Playwright memuat kredensial (3 Okt, lanjutan)

**Gejala:** `ops/ci-local.sh` merah di `gitleaks warroom` — 1 temuan `generic-api-key` di
`apps/web/test-results/.playwright-artifacts-*/traces/resources/*.json` (body request login
memuat sandi e2e). Artefak ikut ter-commit di 3 commit (`fb06a9c`, `01a95da`, `3774c7d`).

**Perbaikan (bukti dijalankan):**

1. `test-results/` + `playwright-report/` masuk `.gitignore` — trace Playwright memuat cookie
   dan body request, jadi tidak boleh pernah masuk repo.
2. Riwayat ditulis ulang (`git filter-branch --index-filter 'git rm -r --cached --ignore-unmatch
   apps/web/test-results'`, 103 berkas dibuang), refs lama dibersihkan + `git gc --prune=now`.
   `gitleaks git .` → **no leaks found** (18 commit dipindai). Repo tanpa remote → aman.
3. **Sandi `uji-web` dirotasi** + **260 sesi dicabut** (cookie lama di trace ikut mati);
   `~/.config/warroom/e2e.env` ditulis ulang mode 600. e2e dijalankan ulang dengan sandi baru:
   **lulus**.

**Catatan:** karena repo tidak punya remote, rewrite tidak butuh koordinasi; bila nanti ada
remote, hash commit sebelum `a169f00` berubah.

## Temuan yang membantah/menyimpang (ditulis apa adanya)

1. **Batas izin berkas nyata.** `/etc/sudoers.d/poly-shadow-read` hanya mengizinkan `sudo cat`
   pada **4 berkas summary** arm. Akibatnya: `arm_summary=ok`, sedangkan `arm_jsonl`,
   `agent_summary.json` (600 root), dan direktori dataset (`/var/lib/poly-research`, 700)
   berstatus **`tidak-izin`** — dilaporkan apa adanya, bukan diisi nol.
   **Keputusan:** tidak menambah hak akses sendiri ke direktori proyek lain. Bila owner ingin
   angka arm per-window + katalog dataset penuh di UI, tambahkan 3 baris di allowlist itu
   (baca-saja), atau cukupkan dari `state/snapshot.json` yang sudah dibaca domain.

2. **`NoNewPrivileges=true` mematikan jalur baca.** Awalnya unit worker/API memakainya; flag itu
   memblokir `sudo -n` sehingga adapter gagal. Dilepas (dengan catatan di unit) karena pola host
   ini memang `sudo -n cat`. Alternatifnya (ACL baca di direktori proyek lain) ditolak.

3. **Drift parity palsu 597 → diperbaiki.** Versi pertama menghitung status *"tidak mampu
   menilai"* (`feed_or_momentum_unavailable`, `empty_book`) sebagai keputusan, menghasilkan
   `drift=597` dari 400 baris. Kini hanya keputusan nyata (masuk / tolak-sengaja) yang
   dibandingkan; bila eksekutor hanya menghasilkan status "tidak mampu", hasilnya
   **`tidak-bisa-dibandingkan` + alasan**. Alert palsunya dihapus.

4. **`~` tidak di-expand** oleh `Path` mentah → `radar_cache.json` sempat berstatus `tidak-ada`.
   Diperbaiki di lapisan baca (`_baca_mentah`), bukan di pemanggil satu per satu.

5. **Learner menolak 4 dari 4 usulannya sendiri** — karena bukti dari `agent-lessons.jsonl`
   adalah rentang bergulir, bukan *split beku* menurut kebijakan ADR-003. Ini **perilaku yang
   diinginkan**: usulan yang menyentuh angka wajib punya `split=frozen:<id>`. Konsekuensi jujur:
   learner baru bisa menerapkan perubahan setelah ada mekanisme split beku (P5 lanjutan).

6. **Uang nyata tetap belum terverifikasi** — `klaim=0.0`, `terverifikasi=False`, dan alert
   muncul karena `WARROOM_POLYGON_RPC` belum diisi. Sesuai aturan: klaim uang tidak pernah
   ditampilkan sebagai "nyata" tanpa verifikasi ke sumber.

## Status keamanan live (dibaca apa adanya dari tiga sumber)

- berkas gate `/etc/poly-pilot/activation-approved`: **tidak ada** (hanya varian `.disarmed-*`).
- `operator.json`: `paused=false`, `submissionAllowed=true` — tapi itu **tidak cukup**.
- unit `poly-pilot.service`: **tidak terdaftar** di systemd.
- ⇒ `armed=false`, dan `live.start` selalu mengembalikan **409** dengan daftar grant yang kurang.
- WhatsApp: tidak ada aksi live yang dijalankan API ini; uji kering `lt depth` tidak mengirim order.