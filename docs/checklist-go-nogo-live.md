# Checklist go/no-go live (P6-T4) — **untuk ditandatangani owner**

Disusun: 2026-10-02 · Diperbarui: **2026-10-03** · Status saat ini: **NO-GO** — keputusan owner
3 Okt 2026. Angka gate sudah **lolos** (A1/A2 ✅ sejak sampel naik ke n=4.133), tetapi A3/A4/A5
dan pendanaan belum terpenuhi. Tidak ada izin yang terbuka karena keputusan ini.
Aturan: setiap baris wajib punya bukti yang bisa dijalankan ulang. Tanpa tanda tangan owner,
live tidak dinyalakan — gate live juga tidak pernah dibuat oleh agen.

## A. Syarat keras (harus semua ✅)

| # | Syarat | Ambang | Nilai sekarang | Bukti | Status |
|---|---|---|---|---|---|
| A1 | Gate lolos: `ci_low > BE` | ci_low > 76,66 % | **`ci_low 0.7675` > BE 0.7666** @ **95% + deff 1.342** (n=4.133, win=3.234) — **lolos** | `POST /api/v1/gate/evaluate` | ✅ 3 Okt |
| A2 | Sampel cukup | n ≥ required_n | **4.133 ≥ 3.713** (95% + deff) — cukup | idem (`required_n`) | ✅ 3 Okt |
| A3 | Split beku sebelum melihat hasil | `split=frozen:<id>` | Mekanisme ADA (`warroom_core.splits`), split `poly-paired-131d1ab4aed5` terdaftar (411 berkas). Tetapi **dataset sumbernya hilang** (`/var/lib/poly-research/paired/auto-20261005t000115z` tidak ada), jadi split itu TIDAK sah. 23 Okt: `split_untuk_gate` diperketat agar menolak split yang berkasnya hilang/berubah. | `warroom_core.splits.verifikasi` | ❌ |
| A4 | Fee & slippage terukur pada saat order | ≥ 5 share, kedalaman nyata | Alat ADA dan berjalan: `run_dry_depth()` mengukur kedalaman buku live 8 pair (BTC ≤20bps $1,98 jt; ETH $3,21 jt; SOL $6,99 jt). Belum ada order nyata yang memakai angka ini saat eksekusi. | `POST /api/v1/live/dry-run` | ❌ |
| A5 | Dana nyata terverifikasi | saldo on-chain == klaim | Job `reconcile` berjalan dan jujur: klaim `0.0` pUSD, `terverifikasi=false`, mode `manual`. Tidak ada dana nyata untuk diverifikasi — tidak bisa "diselesaikan" oleh agen. | job `reconcile` | ❌ |
| A6 | Batas kerugian harian diset dan diuji | ada + diuji | ada di domain (`daily_loss_limit_r`) | `lt risk` | ⚠️ perlu bukti ulang |
| A7 | Kill switch teruji < 60 dtk | < 60 s | **10,7 s** | `ops/drill-stop.sh` | ✅ |
| A8 | Tidak ada kredensial di repo/log | gitleaks bersih | bersih (git mode, 2 repo) | `ops/ci-local.sh` | ✅ |
| A9 | Backup + uji restore | sha256 cocok | 35 berkas cocok, ledger identik | `ops/runbook-restore.md` | ✅ |
| A10 | Grant flow menolak aksi tanpa izin | 409 + daftar kurang | teruji | `POST /api/v1/live/action` | ✅ |

## A-bis. **Keputusan owner yang memblokir A1/A2**: kebijakan gate mana yang otoritatif?

| Kebijakan | ci_low (n=4.133) | vs BE 76,66% | required_n | Putusan |
|---|---|---|---|---|
| **95% + koreksi klaster (alat Poly — rekomendasi)** | **0.7675** | **di atas** | **3.713** | **lolos** (diverifikasi 3 Okt) |
| 90% tanpa koreksi klaster (baku platform) | 0.7703 * | di atas | 2.131 * | lolos (angka n=3.977) |
| 95% tanpa koreksi | 0.7681 * | di atas | 3.027 * | lolos (angka n=3.977) |
| 90% + koreksi klaster (deff 1.345) | 0.7685 * | di atas | 2.882 * | lolos (angka n=3.977) |

\* Baris ini masih dari sampel n=3.977 (2 Okt) dan belum dihitung ulang; hanya baris
rekomendasi yang diverifikasi ulang pada 3 Okt. Selisihnya tipis (0,1–0,4 pp di atas BE),
jadi keputusan owner tetap NO-GO sampai A3/A4/A5 selesai — bukan karena angkanya.

Alat Poly (`qa/favorite-live-verdict.py --json`) memakai baris terakhir; angkanya kini mengalir
ke UI sebagai fakta `verdict` (job `verdict-sync`, kebijakan 95% + deff). Sampai owner memilih,
checklist ini memakai **yang paling konservatif** — tidak ada pendanaan yang dibuka oleh kenaikan sampel.

Data di atas diperbarui 2026-10-03 06:5x UTC. Jalankan `POST /api/v1/gate/evaluate` dengan
`{"n":…,"win":…,"be":…,"ci":0.95,"deff":…}` untuk angka terbaru.

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
| Owner | (owner) | 2026-10-03 | ☐ GO  ☒ **NO-GO** |

Catatan keputusan 3 Okt 2026: gate lolos, tetapi **A3 (split beku), A4 (fee/slippage saat
order), A5 (dana terverifikasi)** belum selesai, dan saldo funder ($0,87 pUSD) belum cukup
untuk pilot $5/entry. Keputusan ditinjau ulang setelah syarat itu beres.

Catatan: dokumen ini **tidak** memberi izin apa pun. Izin live selalu lewat grant eksplisit
(`grantedBy`/`messageId`/`scope`/`at`) dan gate fisik yang dibuat owner.