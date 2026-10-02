# Checklist go/no-go live (P6-T4) — **untuk ditandatangani owner**

Disusun: 2026-10-02 · Status saat ini: **NO-GO** (belum ada satu pun syarat keras yang terpenuhi)
Aturan: setiap baris wajib punya bukti yang bisa dijalankan ulang. Tanpa tanda tangan owner,
live tidak dinyalakan — gate live juga tidak pernah dibuat oleh agen.

## A. Syarat keras (harus semua ✅)

| # | Syarat | Ambang | Nilai sekarang | Bukti | Status |
|---|---|---|---|---|---|
| A1 | Gate lolos: `ci_low > BE` | ci_low > 77,0 % | `ci_low 0.7696` (n=1.175, win=928) | `POST /api/v1/gate/evaluate` | ❌ gagal |
| A2 | Sampel cukup | n ≥ required_n | 1.175 vs **1.219** | idem (`required_n`) | ❌ kurang 44 |
| A3 | Split beku sebelum melihat hasil | `split=frozen:<id>` | belum ada mekanisme split di jalur produksi | ADR-003 | ❌ |
| A4 | Fee & slippage terukur pada saat order | ≥ 5 share, kedalaman nyata | belum diukur saat order (hanya kutipan) | `POST /api/v1/live/dry-run` | ❌ |
| A5 | Dana nyata terverifikasi | saldo on-chain == klaim | klaim `0.0`, `terverifikasi=false` | job `reconcile` | ❌ |
| A6 | Batas kerugian harian diset dan diuji | ada + diuji | ada di domain (`daily_loss_limit_r`) | `lt risk` | ⚠️ perlu bukti ulang |
| A7 | Kill switch teruji < 60 dtk | < 60 s | **10,7 s** | `ops/drill-stop.sh` | ✅ |
| A8 | Tidak ada kredensial di repo/log | gitleaks bersih | bersih (git mode, 2 repo) | `ops/ci-local.sh` | ✅ |
| A9 | Backup + uji restore | sha256 cocok | 35 berkas cocok, ledger identik | `ops/runbook-restore.md` | ✅ |
| A10 | Grant flow menolak aksi tanpa izin | 409 + daftar kurang | teruji | `POST /api/v1/live/action` | ✅ |

## B. Konfigurasi pilot yang diusulkan (bila A terpenuhi)

| Parameter | Usulan | Alasan |
|---|---|---|
| Pasar | **btc/eth saja** | 8 coin lain: −1,97 % (zec −32,3 %); spread 1 sen ≈ 1,2 % stake menghapus edge |
| Band harga | 0,70–0,95 | satu-satunya edge terukur (+2,60 %/stake) |
| Ukuran | $5/entry, `MAX_OPEN 1` | batas kerugian harian & modal tersedia |
| Stop | 200 trade atau −10 % ekuitas | batas eksperimen |
| Fee | model **terverifikasi** (bukan 0,07·p·(1−p)) | model lama membalik kesimpulan (+1,01 % vs +2,60 %) |

## C. Yang harus disiapkan owner (di luar repo ini)

1. **Dana**: saldo `pUSD` di funder + gas POL di signer. Saldo saat ini **$0,87 pUSD** + 0,004 POL
   (tidak cukup untuk pilot $5/entry).
2. **Gate live**: berkas `/etc/poly-pilot/activation-approved` dibuat **oleh owner**, bukan agen.
3. **RPC Polygon** (opsional tapi disarankan): set `WARROOM_POLYGON_RPC` supaya rekonsiliasi uang
   berhenti berstatus "belum terverifikasi".
4. **Allowlist baca** (opsional): 3 baris tambahan di `/etc/sudoers.d/poly-shadow-read` untuk
   `state.json`/`jsonl` arm + katalog dataset, bila ingin angka per-window tampil di UI.
5. **Alert**: `WARROOM_TELEGRAM_BOT_TOKEN` + `WARROOM_TELEGRAM_CHAT_ID` di
   `/etc/warroom/notifier.env` (mode 600) agar alert sampai ke HP. Tanpa itu alert tetap di DB.
6. **Grant**: satu pesan eksplisit berisi scope (mis. `live.start`) + `message_id` pesan itu.

## D. Setelah live menyala (bila nanti diputuskan)

- Pantau: `warroom_alerts_open`, `warroom_facts_basi`, drift parity, PnL vs BE.
- Setiap anomali → `ops/runbook-incident.md` (eskalasi, bukan perbaikan otomatis).
- Live berhenti otomatis pada 200 trade / −10 % ekuitas (batas eksperimen, bukan target).

## E. Tanda tangan

| Peran | Nama | Tanggal | Keputusan |
|---|---|---|---|
| Owner | ________________ | __________ | ☐ GO  ☐ NO-GO |

Catatan: dokumen ini **tidak** memberi izin apa pun. Izin live selalu lewat grant eksplisit
(`grantedBy`/`messageId`/`scope`/`at`) dan gate fisik yang dibuat owner.