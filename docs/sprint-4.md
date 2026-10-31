# Sprint 4 — Aman untuk ditinggal (audit & drill)

**Periode:** 20–26 Nov 2026 (dikerjakan 31 Okt).
**Goal:** operasi bisa ditinggal tanpa kejutan.

| Story | Status | Bukti |
|---|---|---|
| US5.1 rotasi kredensial | **dilewati owner** | keputusan 31 Okt; catatan OKX tetap ada di `docs/audit-ops-20261031.md` |
| US5.2 sudoers/allowlist | **terverifikasi** | allowlist eksplisit per perintah di `/etc/sudoers.d/warroom-poly-readonly`; `%sudo` tidak diandalkan; tidak diubah untuk menghindari lockout |
| US5.3 drill restore | **lulus** | restore `warroom-20261031-004000.dump` ke DB uji: facts=93.099, alerts=685, jobs=34; DB dihapus |
| US5.4 CI + commit | **sebagian** | CI hijau; PR #61/#62 menunggu review owner |
| US5.5 audit dependensi | **selesai (laporan)** | npm prod 0 vuln; OSV Python 88 advisory pada 86 paket, terbanyak pillow/filelock/cryptography; belum upgrade buta |

Laporan lengkap: `docs/audit-ops-20261031.md`.
