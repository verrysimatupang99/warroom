# Changelog War Room

Catatan perubahan terpadu platform War Room (super-app paper trading multi-pasar). Log perubahan dikelola secara terdistribusi per sektor spesialisasi untuk menjaga ketelusuran dan kepemilikan kode.

## Indeks Sektor

| Sektor | Lingkup Fokus | Berkas Detail |
|---|---|---|
| **01** | Strategi & Sinyal | [01-strategi.md](docs/changelog/01-strategi.md) |
| **02** | Risiko & Ledger | [02-risiko-ledger.md](docs/changelog/02-risiko-ledger.md) |
| **03** | Data & Pipeline | [03-data.md](docs/changelog/03-data.md) |
| **04** | API & Backend | [04-api.md](docs/changelog/04-api.md) |
| **05** | Frontend & Antarmuka | [05-frontend.md](docs/changelog/05-frontend.md) |
| **06** | LLM & Kecerdasan Buatan | [06-llm.md](docs/changelog/06-llm.md) |
| **07** | Notifikasi & Komunikasi | [07-notifikasi.md](docs/changelog/07-notifikasi.md) |
| **08** | Basis Data & Skema | [08-database.md](docs/changelog/08-database.md) |
| **09** | QA & Pengujian | [09-qa.md](docs/changelog/09-qa.md) |
| **10** | DevOps & Infrastruktur | [10-devops.md](docs/changelog/10-devops.md) |
| **11** | Keamanan & Kepatuhan | [11-keamanan.md](docs/changelog/11-keamanan.md) |
| **12** | Dokumentasi & Kerapian | [12-dokumentasi.md](docs/changelog/12-dokumentasi.md) |

## Ringkasan Inisiatif Terkini

- **Kerapian Kode & Pembersihan Anti-Slop**: Penghapusan banner dekoratif, komentar bertanggal, dan narasi historis pada komponen inti (`AreaView.svelte`, `pasar.py`, skrip sinyal kripto). Semua komentar kini ringkas (1-2 baris) dan hanya menjelaskan rasional teknis ("kenapa").
- **Standarisasi Dokumentasi Arsitektur**: Penyusunan dokumentasi komprehensif untuk seluruh komponen (`packages/core`, `packages/live-trading`, `services/api`, `services/worker`, `services/notifier`, `apps/web`).
- **Pemisahan Log Perubahan Sektor**: Pembuatan repositori catatan perubahan independen di bawah `docs/changelog/` untuk mempermudah audit kolaboratif antar agen worktree.
- **Integritas Pengujian**: Menjaga 100% kelulusan pengujian pada seluruh lapisan platform (pytest backend, vitest frontend, svelte-check, dan audit lint ruff).
