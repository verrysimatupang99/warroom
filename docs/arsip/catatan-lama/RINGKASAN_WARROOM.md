# RINGKASAN LINTAS-AGENT: WAR ROOM
Dibaca: 2026-10-23 ~09:50-10:05 WIB oleh Hermes (qonek/deepseek-v4.1-flash)

## 0. Di mana sesi tiap agent disimpan
| Agent | Lokasi | Bentuk | Jumlah |
|---|---|---|---|
| Hermes | `~/.hermes/state.db` (tabel sessions/messages + FTS) | SQLite | 127 sesi, 33.461 pesan |
| AGY (Antigravity CLI) | `~/.gemini/antigravity-cli/conversations/*.db` + `conversation_summaries.db` | SQLite per-conversation, payload protobuf di `steps` | 49 konversasi |
| OMP | `~/.omp/agent/sessions/**/*.jsonl`, `~/.omp/agent/history.db` | JSONL + SQLite (judul/recap) | 15 jsonl, 46 prompt, 7 judul |
| War Room agents | `~/warroom-agents/{orchestrator,crypto,forex,idx,polymarket}/.agent_chat_history.json` + `ORCHESTRATOR_DIRECTIVE.json` | JSON | 5 agen |

Sesi Hermes yang menyentuh War Room: 57 dari 127 (kata kunci war room/warroom/polymarket/ledger/bandarmologi).

## 1. Kronologi War Room
- 02-03 Okt: pondasi (gate, ADR-003), checklist go/no-go live -> NO-GO oleh owner.
- 04-05 Okt: serangan pertama AGY: "Redesign UI/UX War Room" (2.573 step) -> asesmen + blueprint "Trader Cockpit".
- 07 Okt: Hermes audit QA portal login & data market (495 pesan).
- 11-12 Okt: OMP audit kesiapan (QA/dev/quant/UX) -> verdict NO-GO live, 7 task selesai, branch perlu merge.
- 14-16 Okt: 12 sektor paralel (`~/orchestrator/sectors.json`) -> mayoritas `merged`.
- 18-22 Okt: hardening, audit menyeluruh Hermes (KRITIS/TINGGI/SEDANG), perbaikan Blok 0-3.
- 23 Okt 04:28-05:05: "Trading Floor": Chief Orchestrator + 4 spesialis pasar (model campur Qonek/Kiyara/Nutaraline) -> audit pasar + codebase + CONSENSUS_RECOMMENDATIONS.md.

## 2. Arsitektur War Room (yang dipakai bersama)
- `~/warroom` (SvelteKit `apps/web` :3100 + FastAPI `services/api` :8800 + `services/worker`) -> Postgres, `state/snapshot.json`.
- `~/live-trading` = mesin trading/paper + `state/snapshot.json` (sumber fakta, stamp "WIB").
- `~/polymarket-warroom` + `/opt/polymarket` (read-only), `poly-agent`, arm B/C/D/E services.
- Service aktif sekarang: warroom-api, warroom-worker, warroom-web, nginx, poly-agent, 9router-tools, 4 paper-arm polymarket, live-trading-dashboard.
- `~/warroom-wt/*` (worktree 12 sektor) SUDAH TIDAK ADA; worktree tersisa hanya `~/warroom-agents/*` di branch `agent-*` (semua di c6bf539).

## 3. Node AGY: asesmen UX + bug riil
Sesi utama `2d02098d` (2.573 step, 15 Okt).
Temuan: mental model "database inspector" vs "trading cockpit"; 11 menu root terfragmentasi (GMGN punya sub LP tapi ada rute /lp; IDX punya sub Bandarmologi tapi ada /bandar; /overextended hanya untuk 1 postingan); sub-tab kosong; tanpa chart; copy defensif; search global belum ada endpoint.
Bug yang ditemukan & diperbaiki:
1. `/idx` menampilkan crypto -> `AREA_KEYS["idx"]` menarik `kandidat`/`pengukuran` (milik crypto) -> diubah jadi `("bagian",)`.
2. Halaman bandar/lp/overextended cek `f.kind !== 'bagian'` padahal fakta ber-kind `snapshot` -> selalu kosong.
3. Bug zona waktu WIB: `facts_publish.py` mem-parse "… WIB" sebagai UTC -> observed_at 7 jam di masa depan; `Math.abs()` di format.ts menyamarkan jadi badge "segar 7j"; 495 baris dibersihkan.
4. ORDIUSDT: `SignalCard.svelte` baca `setup.arah` padahal snapshot punya `direction` -> default LONG, TP terlihat di bawah entry. Ditambah guard anomali + vitest.
5. Gate paper-scan tidak meneruskan `fee_buffer_pct=0.0013`.
Hasil akhir: 3 kategori nav (Overview/Sinyal/Kelayakan dst), 38/38 vitest, 523/523 pytest, build SvelteKit OK, semua rute 200.

## 4. Node OMP
- 11 Okt: minta bertindak senior QA + fullstack + quant untuk menilai War Room; 6 sub-task (QaAudit, QuantReview, UxBenchmark, HomeJujur, PaperSim, FixVerified, FixGateCI...) -> recap: semua 7 task selesai, verdict **NO-GO live**, sisa: review/merge branch + rotasi password `qa_viewer`.
- 15 Okt: 3 sesi sektor (02-risiko-ledger, 04-api, 01/08 pendek) -> hasil sektor 02 (fee 0,1%/sisi, bench harian, rekonsiliasi ledger) dan 04 (leaderboard strategi) masuk ke branch sektor.
- 22 Okt: sesi "Principal Systems Architect" (98 KB) - audit live repo.

## 5. Node Hermes
### 5a. 12 sektor (`~/orchestrator/sectors.json`)
Status tercatat: 10 `merged` + 07-notifikasi `done` + 10-devops `done`.
Verifikasi git: semua `sektor/*` sudah ancestor `main` KECUALI `sektor/07-notifikasi` (belum merge).
Isi sektor: strategi (heat score, filter funding/OI, lifecycle), risiko-ledger (fee seragam, benched, rekonsiliasi), data (TTL/freshness), api (leaderboard), frontend (halaman leaderboard), llm (routing + Beekeeper), notifikasi (alert entry/exit/benched/kill-switch), database (skema+indeks), qa, devops, keamanan (hapus sudo, .env gmgn-paper), dokumentasi.
Catatan jujur dari agen: flaky test `test_schedule`/`test_facts_publish` sudah ada di base; `AGENTS.md` angka tes 824 -> 913 diblokir sebagai file terlindungi.

### 5b. Audit menyeluruh 22 Okt (`20261022_145804_e87f6f` + 3 subagent)
- KRITIS-1: `POST /api/v1/MiniMax/mt5/telemetry` menulis state akun MT5 live tanpa auth (poisoning; EA menimpanya ~25 detik kemudian).
- KRITIS-2/3: endpoint yang dibaca EA untuk buka order, dan 5-8 router (40+ endpoint) live tanpa auth.
- TINGGI: path traversal `market=` ke 44 endpoint node MiniMax; rate-limit bisa dilewati via X-Forwarded-For; `/pratinjau/` menyajikan 65 MB APK + source EA; OpenAPI menyimpang & job report "ok" padahal gagal; `build_id` label basi (bukan sidik jari kode berjalan); `events` tumbuh tanpa batas (96.569 baris, 87% `job.ran`, 35 MB); `sessions` tumbuh tanpa batas (`purge_expired()` dead code).
- SEDANG: klaim job non-atomik (3 writer paralel), API tanpa graceful shutdown, tak ada rate limit nginx, `/api/v1/ai/verifier` dari localhost tanpa auth (membakar kuota), angka fallback karangan di `quant-backtest` + order hardcoded, web tanpa gate auth, TOCTOU executor lock tak pernah dipanggil, dua penulis `snapshot.json` non-atomik, SSE `after_id` tidak maju.
- Remediasi: commit `f0c8e02` (Blok 0) dan `c6bf539` (Blok 1-3) ada di main.

## 6. Trading Floor 23 Okt (warroom-agents)
Chief Orchestrator + 4 spesialis, model divariasikan (kebijakan NON-INHERIT):
- Crypto: qonek/grok-4.7 (validator kiyara/deepseek-v4.1-flash)
- Forex: kiyara/z-ai/glm-5.3-flash (validator qonek/ling-3.1-flash)
- IDX: kiyara/qwen3.8-flash (validator nutaraline/mimo-v2.6-flash)
- Polymarket: nutaraline/nemotron-3.5-lightning (validator kiyara/kimi-k3)
Tesis: **"Alpha-Execution Divergence"** - deteksi sinyal bagus, tapi edge habis di lapisan eksekusi.
- Polymarket: WR 81,8% tapi PnL -$6,40 (payoff biner asimetris + taker fee); dataset n=4.133 WR 78,25% EV +2,07% d_eff 1,342.
- Forex XAUUSD: H1 bearish kuat (4004,39 < EMA20 4039,93 < EMA50 4075,61), tetapi buffer BE $0,30 vs spread rollover Exness 12-25 (kadang 40-80) pts -> risiko phantom stop.
- Crypto: fail-closed terkunci (izin=False, kunci=False, siap=False), OI BTC $7,74B; perlu Z-score adaptif taker ratio + filter likuiditas DEX.
- IDX: bandarmologi + foreign flow Arjum lulus 39 unit test; tetap Cap Fase 2 (eksekusi manual).
Kesiapan live: Crypto 80%, Forex 75%, Polymarket 75%, IDX SIAP FASE 2 (manual) -> **NO-GO live penuh**.

## 7. Isu lintas-agent yang berulang
1. UI = penampil fakta mentah; setiap agent yang diminta "cek UI" menemukan hal yang sama (AGY, OMP, Hermes).
2. Kebocoran domain: `AREA_KEYS` mencampur kunci crypto ke area lain.
3. Waktu: stempel WIB diperlakukan sebagai UTC + `Math.abs()` -> data "basi 7j".
4. Skema field backend vs frontend tidak sinkron (`arah` vs `direction`).
5. Angka "karangan"/fallback diam-diam, dan status "ok" padahal job gagal.
6. Gate live: berulang kali ditegaskan tidak boleh disentuh; tetap fail-closed.
7. `build_id` tidak bisa dipercaya untuk mendeteksi drift deploy.

## 8. Kondisi live saat pembacaan (verifikasi sendiri)
- `warroom-api` :8800 `/api/v1/build` -> `f0c8e02-20261022T163914Z`, domain_version 0.1.0.
- `git -C ~/warroom` HEAD = `b861549` (perf retention) -> **build_id tertinggal 2 commit dari HEAD** (persis kelas masalah TINGGI-4: build_id bukan identitas kode berjalan).
- `warroom-web` :3100 -> HTTP 200; nginx, worker, poly-agent aktif.
- File untracked di repo: `packages/core/src/warroom_core/retention.py.bak-noisy`.
- `sektor/07-notifikasi` belum di-merge (8 butir patch masih rencana: subjek entry/exit, gate kill-switch, kirim_tertunda, field strategi, benched/hari WIB, retensi fact_ids, job stale -> gagal, alert_tp1).

## 9. Yang belum selesai / perlu keputusan
1. Merge `sektor/07-notifikasi` + 8 butir patch notifikasi.
2. Resync deploy (`ops/deploy-service.sh api`) supaya build_id = HEAD.
3. Perbaiki mekanisme build_id (sidik jari per-restart) agar gate drift benar-benar menangkap.
4. Hapus `retention.py.bak-noisy`, lalu commit/bersihkan worktree.
5. Gate live: butuh tanda tangan owner (A3/A4/A5 masih ❌).
6. Rotasi password `qa_viewer` (dari recap OMP 11 Okt).
7. Hardening lanjutan: auth untuk endpoint telemetri/order EA, indeks `events(id,type)`, retensi `events` & `sessions`.
8. Keputusan arsitektur: `~/warroom-agents/*` masih branch `agent-*` di c6bf539, belum punya remote/merge path yang jelas.

## 10. Berkas bukti
- Ekstraksi sesi AGY: `~/wr_notes/agy_*.txt` (22 konversasi)
- Daftar sesi Hermes War Room: `~/wr_notes/hermes_war_sessions.json`
- Dokumen kanonik: `~/warroom-agents/orchestrator/CONSENSUS_RECOMMENDATIONS.md`, `docs/MARKET_SPECIALISTS_AUDIT.md`, `docs/MACRO_ORCHESTRATION_DIRECTIVE.md`, `~/warroom-agents/*/\*_audit.md`
- `~/warroom/docs/checklist-go-nogo-live.md`, `~/warroom/AGENTS.md`


---

# CATATAN EKSEKUSI 2026-10-23 10:00-10:15 WIB

## Yang dikerjakan
1. **Deploy drift ditutup.** API/worker/web tadinya jalan di `f0c8e02` sementara HEAD `b861549`
   (4 commit tertinggal, termasuk Blok 1-3 hardening audit + modular forex/MT5 + retensi events).
   Sekarang ketiganya di HEAD, `build_id` identik di `/etc/warroom/build.env`, `build/build-id.txt`, dan `/api/v1/build`.
2. **Bug nginx ditemukan & diperbaiki (akar "CSP enforce gagal").**
   `sites-enabled/warroom` adalah **file salinan**, bukan symlink ke `sites-available`.
   `ops/csp-enforce.sh` menulis hash bootstrap baru ke `sites-available` -> tidak pernah dibaca nginx
   -> header Report-Only terus memuat hash build lama -> setiap deploy mencetak peringatan palsu.
   Perbaikan: symlink dipasang + 3 blok yang hanya ada di config aktif (unduhan EA `/srv/pratinjau`,
   include snippet KOMUTER, include snippet Telegram Trading Signals) dimasukkan ke template repo.
   Commit `6d640c9`. Sesudah itu gate CSP lulus tanpa peringatan.
3. **Tes migrasi diperbaiki.** `test_rantai_migrasi_alembic_tunggal_dan_valid` mengunci head
   `a7b8c9d0e1f2` sehingga merah setiap ada migrasi baru (2 migrasi remediasi audit). Sekarang
   memverifikasi rantai tunggal + tertelusur head->base. Commit `e2d9e3e`. 158 tes notifier+core lulus.

## Koreksi terhadap analisis awal
- **`sektor/07-notifikasi` SUDAH di-merge** lewat `67fa127 merge(sektor/07-notifikasi)`; branch-nya
  sudah dihapus setelah merge. Semua 8 perbaikan (subjek entry/exit, gate kill-switch, kirim_tertunda,
  field strategi, benched per hari WIB, retensi `alerts.fact_ids`, job stale -> gagal, `alert_tp1`)
  terverifikasi ada di `main`. Tidak ada pekerjaan notifikasi yang tertinggal.

## Sisa yang masih terbuka
1. `ruff check .` = 56 error, semuanya di berkas baru dari `5862e00` (agents_hub, tencent, agy,
   laya_sentinel, laya_news_fetcher, forex/strategies). **Sudah ada sebelum sesi ini**, bukan regresi;
   CI platform kemungkinan merah karenanya.
2. `build_id` masih berupa label (commit + stempel), belum sidik jari kode yang berjalan -> temuan
   TINGGI-4 Hermes belum tertutup secara desain, baru tertutup kasusnya.
3. Gate live A3/A4/A5 masih ❌ (butuh keputusan + tanda tangan owner).
4. Rotasi password `qa_viewer` belum dilakukan.
5. `~/warroom-agents/*` masih branch `agent-*` di c6bf539, belum ada jalur merge/remote yang jelas.
6. Backup config nginx & repo ada di `~/wr_notes/sys_backups/` dan `~/wr_notes/repo_backups/`.


## CATATAN EKSEKUSI 2 (2026-10-23 10:20-10:40 WIB) - berurutan kecuali rotasi password

### 1. Ruff: 56 -> 0 (All checks passed)
- **Bug nyata 1**: `strategies/multi_session_laya.py` anotasi `lot_size: double` (tipe tidak ada).
  Tertutup oleh `from __future__ import annotations`, tapi meledak `NameError` saat
  `typing.get_type_hints()` -> diganti `float`.
- **Bug nyata 2 (penting)**: `evaluate_laya()` SELALU `return True, 0.88` tanpa memanggil model.
  `market_state` + dict `questions` disusun lalu ditinggalkan; setiap sinyal diloloskan dan
  dilabeli "Laya AI Confirmed". Kini `LayaEvaluator` dibangun sekali di `__init__` dan
  di-`invoke()`; verdict + probabilitas dipakai dengan ambang `laya_min_confidence` (0.60).
  Diuji nyata: model `convaiinnovations/laya` ter-cache 647 MB, inferensi 19,6 detik dingin,
  hasil p-EXECUTE 0.960 / 0.934. Kegagalan model -> baseline + alasan jujur (fail-open).
- **Bug nyata 3**: `strategies/laya_judge.py` menyiapkan `market_state`/`is_safe` tapi tidak
  dipakai, sementara `reason` berbunyi "Laya Confirmed". Diganti label baseline + catatan.
- **B904** `raise HTTPException` tanpa `from exc` di routers/agy.py.
- Sisanya gaya: 27 auto-fix + 28 baris >110 char. Diverifikasi AST: AGENT_REGISTRY 5 agen
  IDENTIK, SUPPORTED_MODELS 21 entri IDENTIK, string `update_cmd` PowerShell IDENTIK.

### 2. Token EA bocor - TEMUAN KRITIS, sudah ditangani
- `routers/tencent.py` menyimpan `X-Warroom-Token=022ee87b...` sebagai literal di dalam
  perintah PowerShell. Nilainya SAMA dengan `WARROOM_SERVICE_TOKEN` aktif di
  `/etc/warroom/service_token.env`.
- Bukti dampak: `GET /api/v1/agents/list` -> 403 tanpa token, **200 dengan token bocor**
  dari internet. Token itu membuka `/api/v1/agents/*`, `/api/v1/agy/*` (termasuk
  `POST /dispatch`), dan endpoint MT5/EA.
- Token **sudah dirotasi** (`service_token.env`, backup `.bak-20261023`); API direstart;
  diuji: token lama 403, token baru 200.
- Kode kini membaca `$env:WARROOM_EA_SYNC_TOKEN`; tidak ada lagi kredensial di repo.
- Token belum pernah ter-push (7 commit masih lokal), jadi history lokal dibersihkan:
  `git filter-branch` + hapus `refs/original` + `reflog expire` + `gc --prune=now`.
  Verifikasi: 0 commit, 0 blob, `gitleaks: no leaks found`. Backup: 
  `~/wr_notes/repo_backups/warroom-before-scrub-20261023.bundle`.

### 3. OpenAPI drift
- 14 endpoint baru tidak pernah tercatat (agents, agy, komuter, tencent forex/mt5);
  0 endpoint hilang. `contracts/openapi.json` disinkronkan -> 107 paths, gate lulus.

### 4. Verifikasi akhir
- `ops/ci-local.sh` -> **SEMUA HIJAU** (domain pytest, platform ruff+import+openapi,
  gitleaks, web lint+check+test+build).
- Deploy: api/worker/web semua di `eec3f5a`; `build_id` identik di env, web, dan API.
- Rute publik `/`, `/komuter/`, `/signals`, `/api/v1/build` -> 200. Token lama -> 403.

### Sisa terbuka (belum dikerjakan)
1. `build_id` masih label commit+stempel, belum sidik jari kode berjalan (temuan TINGGI-4).
2. Gate live A3/A4/A5 masih perlu keputusan + tanda tangan owner.
3. `~/warroom-agents/*` masih branch `agent-*` di c6bf539, belum ada jalur merge.
4. Rotasi password `qa_viewer` - sengaja dilewati sesuai instruksi.
5. Perlu keputusan: 7 commit lokal belum di-push ke origin.


## CATATAN EKSEKUSI 3 (2026-10-23 10:40-10:50 WIB) - build_id jadi sidik jari kode

### Masalah yang ditutup (temuan audit TINGGI-4)
`/api/v1/build` hanya mengembalikan `WARROOM_BUILD_ID` dari `/etc/warroom/build.env`, dan
`gate_identity_api()` membandingkannya dengan nilai yang dihitung di sesi deploy yang sama.
Artinya gate membandingkan nilai dengan dirinya sendiri -> tidak pernah menangkap drift.
Kasus nyata 23 Okt: API melaporkan `f0c8e02` sementara HEAD `b861549` (4 commit di depan),
termasuk endpoint yang tidak ada di commit yang dilaporkan.

### Perbaikan
1. `packages/core/src/warroom_core/fingerprint.py` (baru): SHA-256 atas isi 136 berkas
   sumber (`.py/.json/.toml/.txt/.j2`) dari paket `warroom_core`, `warroom_api`,
   `live_trading`; direktori cache & tests dilewati. 12 heksadesimal, di-cache
   (`lru_cache`) karena tidak boleh berubah selama proses hidup. Biaya: 11 ms saat start.
   Berkas yang tak terbaca ditandai `UNREADABLE:` — tidak dilewati diam-diam.
2. `/api/v1/build` kini melaporkan `kode_fingerprint` + `berkas_dihitung` di samping
   `build_id` (label tetap ada untuk kompatibilitas).
3. `ops/deploy-lib.sh`: `fingeprint_disk()` menghitung sidik jari dari BERKAS DI DISK;
   `gate_identity_api()` sekarang menuntut (a) build_id cocok DAN (b) fingerprint proses ==
   fingerprint disk. Bila proses belum melaporkan fingerprint (build lama), gate tidak
   digagalkan supaya rollback tetap mungkin.
4. `packages/core/tests/test_fingerprint.py`: 5 tes termasuk bentuk hash, kestabilan,
   jumlah berkas > 0, dan kunci yang dibaca gate.

### Bukti gate bekerja (diuji langsung)
- Kondisi sehat: proses `35926898c2c3` == disk `35926898c2c3`.
- Uji drift: satu baris ditambahkan ke `specs.py` tanpa restart ->
  disk `6e9dcda35d9d` vs proses `5eab0f77caa3` -> gate akan GAGAL (sebelumnya lolos).
- Berkas dipulihkan; tree bersih.

### Status akhir
- `ops/ci-local.sh` -> SEMUA HIJAU. `ruff check .` -> All checks passed.
- Deploy: api/worker/web semua `4b78718`; `build_id` identik di env/web/API, dan
  `kode_fingerprint` identik antara proses dan disk.
- Rute publik 200; token lama tetap 403.


## CATATAN EKSEKUSI 4 (2026-10-23 10:50-10:55 WIB) - push ke origin

### main
9 commit di-push `c6bf539..4b78718` (fast-forward, origin tidak bergerak).
Sebelum push: gitleaks 411 commit -> no leaks; token lama 0 jejak di history.
Verifikasi: `origin/main` == `main` == 4b78718, selisih 0.

### Branch agent-* (sebelumnya risiko hilang)
- Kelima branch (`agent-crypto/forex/idx/orchestrator/polymarket`) ternyata SEMUA persis di
  `c6bf539` - nol commit unik, jadi tidak ada pekerjaan kode yang menggantung.
- Namun ada hasil Trading Floor 23 Okt yang belum pernah di-commit (untracked):
  `.agent_chat_history.json`, `ORCHESTRATOR_DIRECTIVE.json`, `<pasar>_market_audit.md`,
  `CONSENSUS_RECOMMENDATIONS.md`, `docs/MACRO_ORCHESTRATION_DIRECTIVE.md`,
  `docs/MARKET_SPECIALISTS_AUDIT.md`, `proof_of_crud.json`.
- Sudah di-commit di masing-masing worktree lalu di-push sebagai branch baru:
  agent-crypto 1156805, agent-forex 61dad49, agent-idx 8664c22,
  agent-orchestrator 98fde71, agent-polymarket 2a8ae18 (semua cocok lokal==origin).
- Catatan gitleaks `--no-git` di folder warroom-agents: 25 temuan, SEMUANYA dari fixture
  sintetis `services/llm/{golden,tools,tests}` (pola sama yang sudah di-allowlist di repo
  utama, mis. `secret=abcdef123456`). File baru Trading Floor bersih.

### Status akhir seluruh sesi kerja
- main + 5 branch agent-* tersimpan di GitHub (verrysimatupang99/warroom).
- Layanan: warroom-api/worker/web, nginx, poly-agent semua active.
- Rute publik /, /komuter/, /signals, /api/v1/build -> 200.
- Token lama tetap 403 (rotasi berlaku).

### Sisa terbuka (butuh keputusan owner, bukan agen)
1. Gate live A3/A4/A5 (split beku, fee terukur saat order, dana terverifikasi) masih kurang.
2. Rotasi password `qa_viewer` - sengaja dilewati atas instruksi.
3. Branch agent-* masih tanpa jalur merge ke main; isinya dokumen audit, jadi keputusan
   apakah di-merge, diarsipkan, atau dibiarkan sebagai branch laporan.


## CATATAN EKSEKUSI 5 (2026-10-23 10:55-11:05 WIB) - gate live A3 + nasib branch agent-*

### 1. A3 (split beku) - BUG GATE DITEMUKAN & DIPERBAIKI
- Mekanisme ternyata SUDAH ada lengkap (`warroom_core/splits.py`: bekukan/verifikasi/daftar),
  bukan "belum ada mekanisme" seperti tertulis di checklist.
- Split `poly-paired-131d1ab4aed5` terdaftar (411 berkas, manifest_hash ca88aabc...), tetapi
  verifikasi menemukan **411 berkas HILANG**: sumbernya
  `/var/lib/poly-research/paired/auto-20261005t000115z` sudah tidak ada di disk.
- Bug: `split_untuk_gate()` hanya cek "id terdaftar" dan tetap mengembalikan
  `frozen:poly-paired-131d1ab4aed5` -> gate menerima bukti dari dataset yang tidak ada.
  Tiga pemanggil terdampak (autonomy, areas, pasar); hanya worker yang memakai versi aman
  (`split_terverifikasi_terbaru`).
- Perbaikan: `split_untuk_gate` kini memanggil `verifikasi()`; dataset hilang/berubah -> `None`.
  Biaya 0,009 s (dataset hilang). Tes regresi ditambahkan di `test_splits.py`.
  Diperiksa di produksi: `split_untuk_gate(...) -> None`.
- Status A3 tetap **❌** karena dataset sumbernya memang tidak ada; yang berubah adalah gate
  sekarang JUJUR menolak, bukan diam-diam meloloskan.

### 2. A4 (fee & slippage saat order) - alat ADA dan berjalan
`run_dry_depth()` (lewat `/api/v1/live/dry-run`) mengukur kedalaman buku LIVE 8 pair Binance
futures. Contoh 23 Okt: BTCUSDT mid 81.659,9 dengan notional terlihat $1,98 jt pada ≤20 bps;
ETH $3,21 jt; SOL $6,99 jt; LINK $426 rb. Status tetap **❌** karena belum ada order nyata
yang memakai angka ini saat eksekusi.

### 3. A5 (dana terverifikasi) - blocker sah, bukan bug
Job `reconcile` berjalan dan jujur: klaim `0.0` pUSD, `terverifikasi=false`, mode `manual`,
sumber `/var/lib/poly-pilot/snipe-live-v1-state.json`. Tidak ada dana nyata untuk
diverifikasi; agen TIDAK boleh "menyelesaikannya" dengan mengarang angka.

### 4. Branch agent-* -> sudah merge ke main
- Isi: 4 audit pasar + CONSENSUS_RECOMMENDATIONS + direktif + riwayat chat (~1.147 baris dokumen).
- Konflik yang muncul saat merge (tidak terdeteksi `merge-tree`, muncul saat benar-benar merge):
  - `.agent_chat_history.json` (add/add): digabung sebagai JSON list, dedupe, urut waktu
    (17 -> 22 -> 25 -> 28 pesan). Tidak ada riwayat hilang.
  - `ORCHESTRATOR_DIRECTIVE.json` (add/add): keempat worktree menaruh berkas bernama sama di
    root repo yang sama, padahal isinya direktif BERBEDA per pasar. Dipindah ke
    `docs/trading-floor/directive-<pasar>.json` (crypto/forex/idx/polymarket) + README.
- Checklist `docs/checklist-go-nogo-live.md` diperbarui: A3/A4/A5 kini menyebut status
  sebenarnya, bukan "belum ada mekanisme". Keputusan NO-GO tidak diubah.

### 5. Verifikasi
- `ruff check .` bersih; `packages/core` 133 tes lulus; `ops/ci-local.sh` SEMUA HIJAU.
- Deploy api/worker/web = `7ce2dd5`; build_id identik; fingerprint `50ae2d4b902a`.
- Rute publik 200 semua. Push `4b78718..7ce2dd5`; `main` == `origin/main`.

### Sisa terbuka
1. A3: dataset `poly-paired` harus direkam ulang lalu dibekukan lagi (butuh keputusan owner;
   recorder read-only, agen tidak boleh mengarang dataset).
2. A4: perlu order nyata (micro-live) yang memakai angka kedalaman saat eksekusi.
3. A5: perlu dana nyata + verifikasi on-chain.
4. `qa_viewer` belum dirotasi (dilewati atas instruksi).


## CATATAN EKSEKUSI 6 (2026-10-23 11:05-11:35 WIB) - A3 diverifikasi, A4 naik, A6 naik

### A3 - penyebab sebenarnya DITEMUKAN (bukan bug lagi)
Recorder aktif dan memproduksi data baru: `/var/lib/poly-research/paired/auto-20261023t085947z`
(420 berkas, 1,1 GB). Tetapi `splits._scan_outcome()` -> **0 penanda outcome**. Artinya
recorder memang menulis INPUT pasar (order book, quote) dan TIDAK menulis hasil/resolusi.
Persis batas jujur yang sudah didokumentasikan di `splits.py` sendiri. Konsekuensi:
- Split tidak bisa dibekukan secara sah dari data yang ada -> A3 tetap NO-GO.
- Agen TIDAK boleh mengarang outcome untuk memaksa split. Itu akan membuat gate menerima
  bukti palsu - persis yang dicegah ADR-003.
- Gate sudah diperketat (commit sebelumnya) sehingga split rusak ditolak, bukan diloloskan.

### A4 - NAIK dari "alat ada" menjadi TERUKUR & BISA DIPANGGIL
- Ditambah `live.ukur_biaya_eksekusi()`: DepthCollector.report() -> biaya_dari_depth(),
  jadi keluarannya langsung fee + slippage untuk ukuran posisi nyata.
- Endpoint baru `POST /api/v1/live/biaya` (role operator, read-only, tidak menyentuh gate live).
- Diuji di produksi (sesi operator asli): 200 ->
  `sumber=depth:BTCUSDT, fee_bps=5.0, slippage_bps_masuk=0.005, total_bps=5.005`.
  Tanpa auth -> 401 (terlindungi).
- 3 tes: validasi sisi/size tanpa jaringan + pengukuran nyata (skip bila buku tak terbaca).
- Status tetap NO-GO: belum ada ORDER nyata yang memakai angka ini saat eksekusi.

### A6 - NAIK ke OK
`lt risk`: mode paper, R hari ini +0.000, batas -3.0R, sisa ruang 3.0, 48 trade,
posisi 1/3, executor bebas. Penegakan di `risk.py:186`. 14 tes batas/limit lulus.
Sebelumnya berstatus "perlu bukti ulang" - sekarang dibuktikan dengan angka nyata.

### Verifikasi
- `ruff check .` bersih; `ops/ci-local.sh` SEMUA HIJAU (setelah openapi disinkronkan ke 108 paths).
- Deploy api/worker/web = `a9d191d`; build_id identik; fingerprint `8a270dd577ff`.
- Push `7ce2dd5..a9d191d`; main == origin/main. Rute publik 200 semua.

### Ringkasan gate live sekarang
A1 OK, A2 OK, A6 OK, A7 OK, A8 OK, A9 OK, A10 OK.
A3 NO-GO (recorder tak menulis outcome), A4 NO-GO (belum ada order nyata),
A5 NO-GO (klaim dana 0.0, terverifikasi=false).
=> Keputusan owner tetap NO-GO. Tiga yang tersisa semuanya butuh dana/dataset nyata,
bukan kode.


## CATATAN EKSEKUSI 7 (2026-10-23 11:35-12:50 WIB) - A3 SELESAI (bukan sekadar "blocker")

### Koreksi besar terhadap kesimpulan saya sendiri
Di catatan sebelumnya saya menulis: "recorder memang TIDAK menulis outcome". **Itu SALAH.**
Saya menyimpulkannya dari `market_state` saja, yang memang selalu `closed:false`
(0 dari 160). Padahal body Gamma API di rekaman yang SAMA memuat resolusi final.

Bukti terukur pada run `auto-20261023t105826z`:
- 168 slug 5-menit, **152 di antaranya `"closed": true`**.
- 602 baris `closed:true` di seluruh run.
- `_scan_outcome` per berkas: 125 dari 321 berkas kini True (sebelumnya 0).

### Akar masalah sebenarnya
`OUTCOME_MARKERS = (outcome, resolved, resolution, result, won, payout)` tidak memuat
`closed` - padahal itulah nama field resolusi di Gamma API. Jadi deteksi buta, `bekukan()`
menolak, dan A3 mustahil lulus meski datanya lengkap.

### Perbaikan
- `closed` masuk daftar penanda, TAPI hanya dihitung bila nilainya **true**.
  `"closed": false` = market belum selesai, tidak boleh meloloskan split.
- Format rapat `{"closed":true}` juga dikenali.
- 2 tes regresi ditambahkan (closed:true diterima, closed:false ditolak, format rapat).
- Recorder di `/opt/polymarket` **TIDAK disentuh** (read-only, AGENTS.md aturan #1).

### Hasil nyata
- Split dibekukan: **`frozen:poly-paired-a3081eaa0d1b`**, 348 berkas, `ada_outcome=True`.
- `verifikasi` -> **cocok=True**, 0 berkas hilang.
- `split_untuk_gate` -> **menerima** `frozen:poly-paired-a3081eaa0d1b`.
- Split lama `131d1ab4aed5` (dataset hilang) tetap DITOLAK.
- Checklist A3 -> **OK**.

### Status gate live sekarang
A1 OK, A2 OK, **A3 OK**, A6 OK, A7 OK, A8 OK, A9 OK, A10 OK.
Tersisa: A4 (belum ada order nyata), A5 (klaim dana 0.0).
=> 8 dari 10 hijau. Dua sisanya butuh ORDER dan DANA nyata, bukan kode.

### Verifikasi
ruff bersih; ci-local SEMUA HIJAU; deploy api/worker/web = `38ee8fd`;
fingerprint `7ccea284b247`; push `a9d191d..38ee8fd`; rute publik 200.
