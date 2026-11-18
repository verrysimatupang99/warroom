# Rencana Overhaul War Room — 2026-11

Status: **draft untuk disetujui**. Semua angka di sini hasil inventaris langsung server,
bukan asumsi.

---

## 1. Kondisi sekarang (fakta)

**Webdock** — 2 vCPU, 7,3 GB RAM (2,3 GB kepakai), disk 59% (20 GB sisa). Menjalankan
semuanya sekaligus:

| Lapis | Yang jalan |
|---|---|
| UI | SvelteKit `:3100` (25 route) |
| API | FastAPI `:8800`, worker, notifier, tg-engine (Telethon), llm |
| Data | PostgreSQL `:5432` |
| Eksekusi | MT5 live (`GOLD_Reaper_Hexa`) + MT5 demo (`MTRB_Fix`), 1 prefix Wine |
| Akses | nginx `:443`, VNC `:5900`, noVNC `:6080`, ttyd `:7681` |
| Bridge | `/mtrb/` `:8765`, `/crypto/`, `wr-bridge` (telemetri 10 s) |

Route yang sudah ada di web: `agy, bandar, bantuan, berita, bukti, cara-kerja, catatan,
crypto, forex, gmgn, idx, info, jurnal, leaderboard, ledger, lp, masuk, mt5-vault, mulai,
overextended, polymarket, riset, sistem, tencent, vault`.

**Di luar webdock**

| Host | Isi | Kondisi |
|---|---|---|
| cyber1 (`vps-q6szm4-3317`) | orchestrator muse, Hermes agent, skill, git clone | 4 vCPU / 3,9 GB, **disk 75%** |
| api-01 PakaiCloud (`31.58.103.2`) | `komuter-api :8930` publik, wstunnel | 1 GB RAM |
| R2 (Cloudflare) | storage objek | dipakai sebagian |
| Instabox | 5 box (box-2aacb3, mt5-paper-1/2, testing, sshjump) | **akun di-disable admin** |
| Azure VM | kosong | nganggur |
| Eksternal | Exness (2 akun), OKX, Polymarket, GMGN, IDX, Telegram, 9Router/LLM | — |

**Diagnosis:** webdock memikul empat peran sekaligus (UI, API, data, eksekusi) di 2 vCPU.
Itu sumber utama: dashboard lag, build lambat, dan tiap penambahan market menambah beban
ke mesin yang sama dengan terminal trading.

---

## 2. Prinsip overhaul

1. **Pisahkan bidang.** Webdock = *control plane + eksekusi*. Data ingest, backtest, ML,
   dan scraping keluar dari webdock. UI boleh berat render, tapi tidak boleh mengumpulkan data.
2. **Satu market = satu kontrak.** Tiap market punya: sumber data, skema, halaman, freshness
   SLA, dan fallback. Tidak ada market yang "menumpang" data market lain.
3. **Read-only by default.** Semua halaman market hanya membaca. Aksi yang menyentuh uang
   harus lewat `Arm → Confirm` dengan jejak audit (tabel `audit`), dan hanya dari akun yang
   punya peran `operator`.
4. **Freshness terlihat.** Kalau data lebih tua dari SLA, halaman menampilkan kuning/merah —
   bukan diam-diam menampilkan angka lama.
5. **Satu sumber kebenaran angka.** PnL, biaya, funding, swap dihitung sekali di `packages/core`
   dan dipakai semua halaman. Tidak ada rumus PnL kedua di frontend.
6. **Bisa dipulihkan.** Postgres harian ke R2 + artefak riset ke R2. Satu perintah restore.

---

## 3. Arsitektur target (3 lapis)

### A. Edge / publik
- Cloudflare → nginx webdock.
- `/api/v1/*` publik hanya **GET**, di-cache 15–60 s, tanpa data akun.
- Semua yang menyentuh akun/posisi di belakang auth (session cookie) atau token operator.

### B. Control plane (tetap di webdock)
- SvelteKit `:3100` (UI), FastAPI `:8800` (API + websocket), PostgreSQL.
- notifier (Telegram), tg-engine (Telethon), llm (opsional).
- **Eksekusi**: MT5 live `MT5-EX-Live` (Gold Reaper HEXA) + `MT5-EX-Demo` (MTRB Pro),
  masing-masing satu service systemd, watchdog 5 menit, `wr-bridge` 10 detik.

### C. Data plane (di luar webdock)
| Komponen | Host | Kenapa di situ |
|---|---|---|
| Collector harga & on-chain (OKX, GMGN, Binance) | **cyber1** | CPU ringan tapi banyak koneksi; jangan ganggu terminal trading |
| Collector Polymarket + IDX | **cyber1** | sama |
| Backtest & ML runner | **cyber1** sekarang, **Azure VM** kalau sudah berat | butuh CPU/RAM besar, tidak butuh IP publik |
| Artefak (screenshot, ekspor CSV, model) | **R2** | webdock disk 59% |
| API publik `komuter-api` | **api-01** | sudah publik, jangan dipindah |
| Sandbox / paper eksperimen | instabox (setelah appeal) atau VM kecil | jangan di webdock |

Aliran: collector → normalisasi → **Postgres di webdock** (hanya tabel ringkas: 1 baris/menit
per simbol) + artefak besar ke R2. Webdock tidak pernah menyimpan tick mentah.

---

## 4. Halaman per market

Format tiap market: **Ringkasan → Posisi → Sinyal → Jurnal → Riset → Pengaturan**.
Ringkasan wajib muat dalam satu layar HP: equity, PnL hari ini, posisi terbuka, freshness.

### FOREX (MT5)
| Route | Isi |
|---|---|
| `/forex` | ringkasan: equity live+demo, PnL hari ini, posisi, jam sesi London/NY, status EA |
| `/forex/posisi` | posisi + pending per akun, SL/TP, jarak ke SL, R multiple |
| `/forex/sinyal` | sinyal aktif per EA (Gold Reaper, MTRB), alasan terima/tolak (`eval_alasan`) |
| `/forex/ea` | status tiap EA: loaded, versi, magic, input aktif, heartbeat |
| `/forex/jurnal` | deal history per akun, filter magic/strategi |
| `/forex/riset` | backtest, banding strategi, dokumen riset |
| `/forex/pengaturan` | preset aktif, batas risiko per akun (read + ajukan perubahan) |

### CRYPTO
| Route | Isi |
|---|---|
| `/crypto` | ringkasan paper + akun OKX, bias pasar, sinyal hari ini |
| `/crypto/posisi` | posisi paper & live, TP1/TP2, status BE |
| `/crypto/sinyal` | hasil scan 20 koin, alasan approve/reject |
| `/crypto/onchain` | GMGN: token baru, likuiditas, holder — **read-only** |
| `/crypto/jurnal` | trade paper vs live, slippage, fee |
| `/crypto/riset` | parameter engine (RR, ATR, gate), hasil uji |

### POLYMARKET
`/polymarket` ringkasan pasar + posisi; `/polymarket/pasar` daftar market & odds historis;
`/polymarket/posisi` exposure per event; `/polymarket/jurnal` settlement.

### IDX
`/idx` ringkasan IHSG + watchlist; `/idx/emiten` per saham (fundamental + teknikal);
`/idx/sinyal`; `/idx/jurnal`.

### GMGN / on-chain
`/gmgn` feed token, `/gmgn/token/[addr]` detail; selalu dengan peringatan risiko likuiditas.

### Lintas market
`/leaderboard` peringkat strategi lintas market; `/bandar` aliran dana/order flow;
`/overextended` watchlist kondisi ekstrem; `/tencent` data vendor.

---

## 5. Halaman di luar market (wajib ada)

| Route | Fungsi | Kenapa wajib |
|---|---|---|
| `/` | Home: ringkasan semua market + status sistem | satu layar untuk "keadaan hari ini" |
| `/akun` | Koneksi: broker, wallet, API key, status otorisasi | tahu apa yang tersambung, kapan terakhir OK |
| `/risiko` | Limit global: exposure per market, daily loss, correlation | satu tempat mengubah batas, bukan tersebar |
| `/jurnal` | Jurnal lintas market, tag, catatan | bahan evaluasi, bukan sekadar log |
| `/ledger` | PnL, biaya, funding, swap, transfer | angka uang harus bisa ditelusuri |
| `/sumber-data` | Status tiap feed: last update, SLA, error terakhir | **halaman yang paling sering menyelamatkan** |
| `/operasi` | Service, cron, MT5 health, bridge, disk, restart | pengganti SSH untuk 90% kasus |
| `/bukti` | Audit trail: siapa mengubah apa, kapan | syarat kalau nanti ada uang sungguhan |
| `/riset` | Lab: backtest, hipotesis, hasil | tempat ide diuji sebelum menyentuh live |
| `/catatan` | Catatan bebas / changelog | konteks keputusan |
| `/sistem` | Admin: user, peran, token, retensi data | kontrol akses |
| `/masuk`, `/vault` | Auth & penyimpanan kredensial | jangan pernah taruh kredensial di kode |
| `/bantuan`, `/cara-kerja`, `/info` | Dokumentasi & status publik | mengurangi pertanyaan berulang |
| `/buat`/`/mulai` | Onboarding alur kerja | biar konsisten |

Aturan: **setiap halaman market wajib punya tautan ke `/sumber-data` dan `/operasi`** —
kalau angka aneh, penyebabnya hampir selalu salah satu dari dua itu.

---

## 6. Sumber data & pemiliknya

| Sumber | Dipakai untuk | Pemilik (host) | Protokol | SLA | Fallback |
|---|---|---|---|---|---|
| Exness MT5 live `452009427` | eksekusi forex | webdock | status JSON + `wr-bridge` | 10 s | baca langsung `MQL5/Files` |
| Exness MT5 demo `464202979` | MTRB Pro | webdock | `MTRB_Pro_status.json` | 5 s | sama |
| OKX | harga & saldo crypto | cyber1 | REST | 15 s | cache Postgres |
| Binance / GMGN | on-chain & memecoin | cyber1 | REST | 60 s | skip dengan flag "stale" |
| Polymarket | pasar prediksi | cyber1 | REST | 5 mnt | cache |
| IDX/Yahoo | saham | cyber1 | REST | 15 mnt | cache |
| Telegram (Telethon) | notifikasi & sinyal | webdock (perlu sesi) | MTProto | realtime | notifier fallback |
| 9Router/LLM | analisa naratif | cyber1 | HTTP | on-demand | nonaktifkan fitur |
| R2 | artefak | Cloudflare | S3 | — | disk lokal 7 hari |
| Cloudflare | TLS/DNS/WAF | — | — | — | — |

Semua kredensial di vault terenkripsi (`/vault`), **tidak pernah** di file repo atau chat.

---

## 7. Fase kerja

**P0 — Stabilkan & pisahkan (3–5 hari)**
1. `/sumber-data` + `/operasi` hidup dengan data nyata (baca dari service & file status).
2. Pindahkan collector crypto/polymarket/idx dari webdock ke cyber1; webdock hanya menerima
   ringkasan 1 baris/menit.
3. Backup Postgres harian → R2 + uji restore sekali.
4. Bersihkan disk cyber1 (75%) sebelum menambah beban; pasang alert disk > 80%.
5. Semua job punya heartbeat; kalau mati, muncul merah di `/operasi`.

**P1 — Halaman per market (1–2 minggu)**
6. FOREX: `/forex` + `/forex/posisi` + `/forex/ea` (data sudah ada: status JSON + API).
7. CRYPTO: `/crypto` + `/crypto/posisi` dari engine paper yang sudah jalan.
8. `/jurnal` & `/ledger` lintas market dengan satu mesin hitung di `packages/core`.
9. `/risiko` global: batas per market, per akun, max exposure.

**P2 — Riset & kepercayaan (2–3 minggu)**
10. `/riset` + runner backtest di cyber1 (atau Azure bila perlu), hasil ke R2.
11. `/bukti` audit trail untuk semua aksi tulis.
12. `/akun`: status koneksi broker/wallet + rotasi kredensial dari vault.
13. Polymarket & IDX dirapikan ke pola yang sama.

**P3 — Otomasi (setelah P2 stabil)**
14. Auto-tuning parameter per market dengan laporan, bukan auto-deploy.
15. Multi-broker forex (akun kedua) memakai kerangka yang sama.

---

## 8. Kriteria selesai (per fase)

- P0: webdock CPU idle < 40% rata-rata, tidak ada collector yang jalan di webdock,
  restore backup terbukti, `/operasi` menampilkan semua service dengan status benar.
- P1: tiap market bisa dijawab dalam 1 layar HP: equity, PnL hari ini, posisi, freshness.
- P2: setiap angka PnL bisa ditelusuri ke deal/tick asalnya; setiap aksi punya audit.
- P3: tidak ada perubahan parameter yang masuk produksi tanpa laporan tertulis.

---

## 9. Risiko & penanganan

| Risiko | Dampak | Penanganan |
|---|---|---|
| Webdock 2 vCPU kehabisan tenaga | dashboard mati saat market ramai | data plane keluar + cache + render statis |
| cyber1 disk 75% | collector berhenti | bersihkan + alert + artefak ke R2 |
| Instabox disabled | kehilangan sandbox | appeal; sementara pakai demo MT5 di webdock |
| Akun live tanpa investor password | EA bisa trading penuh | batas keras di preset + audit; saran pindah ke investor password |
| Satu Postgres untuk semua | satu query berat bikin semua lambat | read replica/cache, query timeout, index |
| Kredensial tersebar | kebocoran | vault tunggal + rotasi + audit akses |

---

## 10. Yang **tidak** dilakukan

- Tidak menambah market baru sebelum P1 selesai.
- Tidak mengaktifkan mesin yang belum terbukti (contoh: SMC Gold v3.08 — simulasi 30 hari rugi).
- Tidak menaruh tick mentah di webdock.
- Tidak membuat AI yang bisa mengirim order tanpa konfirmasi manusia.
