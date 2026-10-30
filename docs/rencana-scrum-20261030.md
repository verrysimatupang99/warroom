# Rencana Scrum — War Room

**Tanggal:** 30 Okt 2026  
**Product Owner:** owner  
**Scrum Master:** OMP  
**Tim:** 2 agen (A: domain/API/EA, B: web/QA/desain)  
**Sprint:** 1 minggu, mulai 30 Okt 2026  
**Kapasitas:** 10 agent-day/sprint; komitmen **16 SP** (buffer 20%)

---

## 1. Product Goal

> Setiap sinyal, eksekusi, dan P&L War Room punya bukti yang bisa diaudit — dan UI-nya
> mengikuti design system *Obsidian Telemetry* tanpa mengorbankan kepadatan data.

**Sprint Goal 1:** *Tidak ada trade tanpa bukti.* Gate exposure membaca posisi nyata,
cockpit menampilkan status mesin, dan runbook trade pertama siap dipakai.

**Definition of Done forward test (disepakati owner):**
- **20 trade tertutup** atau **30 hari**, mana yang lebih dulu.
- **0 fill/deal hilang** dari `deals.csv` dan `/journal/trades`.
- Telemetri hidup ≥ 99% selama sesi 08–09 server.
- Setiap trade punya jejak: ticket, entry, exit, net (profit+swap+commission), alert.

---

## 2. Baseline terverifikasi (30 Okt 2026)

| Area | Keadaan |
|---|---|
Repo | `/home/admin/warroom`, branch `feat/visibilitas-jurnal-deal` (`b85b7a6`), main `8e00176`; 75 commit di depan `origin/main`
Situs | `https://0xgunsl1ng3r.xyz`, build `8e00176-20261030T114631Z`, nginx → web `:3100`, API `:8800`
Layanan | `warroom-api`, `warroom-web`, `warroom-worker`, nginx active; 0 unit gagal; 31 job `ok`
Tes | Python **878 passed, 3 skipped, 1 xfailed** (882 collected); web **65**; svelte-check **0 error**
EA | `WarRoom_AutoTrader_v3.1` live di Azure, akun demo `416510164`, XAUUSDm M5, Reaper 08–09, balance $1.000
Telemetri | `mt5_snapshot` segar ~14 detik; field `eval_alasan`, `eval_sesi`, `eval_atr`, `eval_rsi`, `eval_ema_*`, `server_time` aktif
Jurnal | `deals.csv` → `/journal/trades.closed`; `fills.csv` → `entries` + `/journal/edge`; **0 trade nyata**
Backtest | Reaper $1k: +13,48%, PF 1,13, DD 9,11%, 436 trade; $10k: +38,73%, PF 1,25, DD 6,01%, 772 trade
Vendor EA | Galaxius +$7.348, GoldenBall +$3.709 (3 tahun, lot tetap 0,01); trial, tanpa track record live
REA | 6.8.0 + **Ghidra 12.1.4** (`available`, JDK 21); 229 tool MCP
Stitch | Proyek `War Room Modern Financial Terminal`; design system *Obsidian Telemetry*; `list_screens` kosong (design system, belum ada screen)

### Cacat/risiko yang sudah terbukti

1. **Exposure gate tidak melihat posisi paper.** Verdict OPUSDT 10:56:25 menulis
   `0/2 posisi` padahal `paper_positions.json` berisi 2 SHORT (SOL, ETH). Penyebab:
   `engine.scan()` tidak mengoper `open_positions` ke `evaluate()` → `gates.exposure`
   menerima `[]`. Batas pun tidak konsisten: gate `MAX_OPEN_POSITIONS=2`, executor
   `max_concurrent_positions=3` + `maks_posisi_searah=2`.
2. **Belum ada trade nyata** — pipeline deal sudah diuji sintetis, belum oleh pasar.
3. **`trades` DB 0 baris**; sumber jurnal sekarang `deals.csv`. Perlu ADR: DB atau CSV.
4. **75 commit belum di remote**; PR #61 masih terbuka.
5. **Kredensial belum dirotasi** (MEXC, IDX, Stitch, MT5).
6. **Real-tick backtest gagal** (Model 3 → 0 tick).
7. **Keputusan owner menggantung**: batas exposure, gate 90% vs 95%+deff, saldo demo.

---

## 3. Mekanika Scrum

| Artefak | Isi | Lokasi |
|---|---|---|
Product Backlog | Epics + stories + estimasi | `docs/rencana-scrum-20261030.md` §4 |
Sprint Backlog | Story yang dikomit + task | `docs/sprint-<n>.md` |
Increment | Kode + tes + deploy + bukti | branch + `artifacts/sprint-<n>/` |
Definition of Ready | AC jelas, dependensi diketahui, tes bisa ditulis | checklist §3.2 |
Definition of Done | kode, tes, docs, deploy, rollback, bukti | checklist §3.2 |

**Upacara (WIB):**
- Planning: Senin 09:00, 60 menit.
- Daily async: 09:30, tiga baris (kemarin / hari ini / blocker).
- Refinement: Rabu 30 menit.
- Review: Jumat 15:00, demo pakai bukti.
- Retro: Jumat 16:00, maks 3 aksi.

**Aturan main:**
- WIP maks 2 story aktif per agen.
- Satu story = satu branch + satu PR.
- Tidak ada deploy Jumat setelah 15:00 kecuali perbaikan insiden.
- Perubahan strategi/gate/EA butuh persetujuan owner; API/web non-strategi boleh
  deploy otonom setelah tes hijau + rollback tersedia.

### 3.1 Definition of Ready
- AC bisa diuji (Given/When/Then) dan tidak ambigu.
- File/komponen yang disentuh diketahui.
- Dependensi (data, kredensial, izin) tersedia atau ada mock.
- Estimasi ≤ 8 SP; kalau lebih, dipecah.

### 3.2 Definition of Done
- Kode + tes baru yang gagal sebelum & lulus sesudah.
- `pytest` penuh hijau; web `check` + `test` hijau bila menyentuh UI.
- Dokumentasi/ADR diperbarui bila mengubah kontrak.
- Deploy + health gate + rollback path dicatat.
- Bukti perintah ditempel di PR/`artifacts/`.
- Tidak ada kredensial di repo/log/chat.

---

## 4. Product Backlog

### Ringkasan epics

| ID | Epic | Prioritas | Sprint |
|---|---|---|---|
E1 | Stabilisasi forward test & bukti | P0 | 1 |
E2 | Jurnal & metrik yang bisa diaudit | P0 | 2 |
E3 | Visibilitas & kontrol | P1 | 2, 4 |
E4 | UI *Obsidian Telemetry* (Stitch) | P1 | 3, 4 |
E5 | Keamanan & operasi | P1 | 4 |
E6 | Backtest & tata kelola strategi | P2 | 5 |
E7 | Dokumentasi & serah-terima | P2 | 5 |

### E1 — Stabilisasi forward test

| ID | Story | SP | AC ringkas |
|---|---|---|---|
US1.1 | Gate exposure membaca posisi paper nyata | 5 | 2 SHORT terbuka → kandidat SHORT ke-3 ditolak dengan alasan `2/2 searah`; 3 posisi total → `3/3 penuh` |
US1.2 | Runbook trade pertama + bukti | 3 | Checklist pre/during/post sesi; trade pertama punya ticket, deal, alert, screenshot, query SQL |
US1.3 | Panel status Reaper di cockpit | 3 | Ringkas menampilkan sesi, ATR, spread, RSI, EMA, tren, alasan evaluasi, umur data |
US1.4 | Watchdog deal & telemetri | 3 | Alert bila snapshot >120s saat sesi atau deal tertutup tidak muncul di `deals.csv` dalam 5 menit |
US1.5 | Tracker DoD 20 trade/30 hari | 2 | Skrip menghitung trade tertutup, hari berjalan, fill hilang; tampil di web/CLI |

### E2 — Jurnal & metrik

| ID | Story | SP | AC ringkas |
|---|---|---|---|
US2.1 | Rekonsiliasi `deals.csv` vs statement MT5 | 3 | Net per trade cocok dengan profit+swap+commission; selisih > $0,01 diberi flag |
US2.2 | Edge eksekusi dari fills | 3 | `/journal/edge` menampilkan slippage/latensi per jam dan per simbol; 503 hanya bila benar-benar kosong |
US2.3 | ADR: `trades` DB vs `deals.csv` | 5 | Satu sumber kebenaran ditetapkan; importer atau deprecation dieksekusi |
US2.4 | Marker trade di kurva ekuitas | 3 | Grafik performa menandai entry/exit dan drawdown |

### E3 — Visibilitas & kontrol

| ID | Story | SP | AC ringkas |
|---|---|---|---|
US3.1 | Pusat alert (ack/snooze) | 3 | Daftar alert terbaru + aksi; tautan ke fact |
US3.2 | Scanlog forex vs crypto terpisah | 3 | Tab Sinyal menampilkan alasan EA; verdict crypto tidak tercampur |
US3.3 | Empty/error/stale state konsisten | 3 | Semua tab forex punya state jelas, bukan spinner abadi |

### E4 — UI *Obsidian Telemetry*

| ID | Story | SP | AC ringkas |
|---|---|---|---|
US4.1 | Audit token + kontras | 3 | Token DESIGN.md dipetakan ke `app.css`; semua pasangan teks/latar lulus AA atau diberi alasan |
US4.2 | Layout cockpit 3 kolom | 5 | Desktop 1280–1920 padat; mobile 390 satu kolom; tanpa overlap `.mobile-header` |
US4.3 | Komponen inti | 5 | Status chip, metric tile, data table, empty state, freshness badge konsisten |
US4.4 | Responsif 390/768/1280/1920 | 3 | Screenshot tiap breakpoint; tidak ada horizontal scroll tak sengaja |
US4.5 | Copy pass antislop | 2 | Tidak ada teks generik/AI-slop; istilah konsisten |

### E5 — Keamanan & operasi

| ID | Story | SP | AC ringkas |
|---|---|---|---|
US5.1 | Rotasi kredensial | 3 | MEXC, IDX, Stitch, MT5 baru; lama dicabut; gitleaks bersih |
US5.2 | Perbaiki sudoers/allowlist | 3 | `%sudo` tidak diandalkan; perintah operasi masuk allowlist eksplisit |
US5.3 | Drill restore backup | 3 | Restore Postgres ke DB uji + rollback web terbukti |
US5.4 | CI + 75 commit ke remote | 5 | PR besar dipecah/merge; CI hijau; tidak ada push ke main |
US5.5 | Audit dependensi | 2 | `npm audit`/`pip-audit`; temuan high ditindak atau dicatat |

### E6 — Backtest & tata kelola

| ID | Story | SP | AC ringkas |
|---|---|---|---|
US6.1 | Real-tick backtest (Model 3) | 5 | 0-tick diperbaiki; laporan 3 tahun tersimpan; biaya realistis |
US6.2 | Matriks keputusan vendor EA | 3 | Galaxius/GoldenBall: trial, lot tetap, jalur $100, rekomendasi paper/nyata |
US6.3 | Registry parameter EA | 3 | `MaxLot`, partial gate 0,04, risiko, sesi terdokumentasi + tes regresi |
US6.4 | Keputusan gate (owner) | 2 | 90% vs 95%+deff dan `split=frozen` diputuskan |

### E7 — Dokumentasi

| ID | Story | SP | AC ringkas |
|---|---|---|---|
US7.1 | ADR: exposure, deals/fills, EA v3.1 | 2 | Tiga ADR pendek, berbasis bukti |
US7.2 | Runbook deploy/rollback/insiden | 3 | Bisa diikuti tanpa bertanya |
US7.3 | Segarkan AGENTS/HANDOVER | 2 | Angka tes, build, commit, EA v3.1 akurat |

---

## 5. Rencana Sprint

### Sprint 1 — 30 Okt–5 Nov 2026
**Goal:** *Tidak ada trade tanpa bukti.*

| Story | SP | Pemilik | Hasil yang bisa didemokan |
|---|---|---|---|
US1.1 Exposure gate | 5 | A | Scan dengan 2 SHORT → kandidat SHORT ditolak, alasan tercatat |
US1.2 Runbook trade pertama | 3 | B | Dokumen + checklist + query SQL siap |
US1.3 Panel cockpit | 3 | B | Ringkas menampilkan status Reaper |
US1.4 Watchdog | 3 | A | Uji matikan telemetri → alert muncul |
US1.5 Tracker DoD | 2 | B | `tools/forwardtest_status.py` mencetak 0/20, hari ke-1 |

**Status 30 Okt:** US1.1 selesai — gate exposure membaca `paper_positions.json`
(2 SHORT → `2/2 searah` ditolak; LONG → `2/3, 0/2 aman`), tes 882 collected, worker restart.

**Sprint Review 5 Nov:** demo scan yang menolak SHORT ke-3, panel cockpit, alert watchdog,
dan tracker DoD.

### Sprint 2 — 6–12 Nov 2026
**Goal:** *Jurnal bisa diaudit.*

US2.1 rekonsiliasi (3) · US2.2 edge chart (3) · US2.3 ADR trades DB (5) · US3.2 scanlog forex (3) · US2.4 marker ekuitas (2) = 16 SP.

### Sprint 3 — 13–19 Nov 2026
**Goal:** *Cockpit Obsidian Telemetry.*

US4.1 token+kontras (3) · US4.2 layout (5) · US4.3 komponen (5) · US4.5 copy (3) = 16 SP.

### Sprint 4 — 20–26 Nov 2026
**Goal:** *Aman untuk ditinggal.*

US4.4 responsif (3) · US5.1 rotasi (3) · US5.2 sudoers (3) · US5.3 restore drill (3) · US5.5 dependency audit (2) · US3.1 alert center (2) = 16 SP.

### Sprint 5 — 27 Nov–3 Des 2026
**Goal:** *Strategi punya batas yang jelas.*

US6.1 real-tick (5) · US6.2 vendor matrix (3) · US6.3 registry parameter (3) · US7.1 ADR (2) · US7.2 runbook (3) = 16 SP.

---

## 6. Langkah implementasi — Sprint 1

### US1.1 — Gate exposure membaca posisi paper (A, 5 SP)

**Reproduksi**
1. `jq '.positions | length' /home/admin/live-trading/state/paper_positions.json` → 2.
2. Verdict OPUSDT 10:56:25: `rules[exposure].reason = "0/2 posisi, korelasi aman"`.
3. `engine.scan()` memanggil `evaluate()` tanpa `open_positions`; `gates.exposure` menerima `[]`.

**Perubahan**
- `packages/live-trading/src/live_trading/signals/engine.py`
  - Di `scan()`, muat posisi paper sekali per siklus:
    `PaperBroker(settings, venue="crypto").positions()` atau baca state yang sama.
  - Oper `open_positions=[p.to_dict() ...]` ke `evaluate()`.
- `packages/live-trading/src/live_trading/signals/gates.py`
  - Ganti `MAX_OPEN_POSITIONS=2` hardcoded dengan batas dari settings:
    total `max_concurrent_positions` (3) dan searah `maks_posisi_searah` (2).
  - Alasan harus menyebut angka: `2/2 searah` atau `3/3 penuh`.
- Tes:
  - `packages/live-trading/tests/test_gates.py`: 2 SHORT → SHORT gagal; 2 SHORT → LONG lolos;
    3 posisi total → gagal.
  - `packages/live-trading/tests/test_engine_scan.py` (baru): monkeypatch posisi paper,
    panggil `scan`, pastikan verdict memakai posisi tersebut.

**Verifikasi**
```bash
.venv/bin/python -m pytest packages/live-trading/tests -q
# replay: satu pair, 2 posisi SHORT sintetis
.venv/bin/python - <<'PY'
from live_trading.signals import gates
print(gates.exposure("SHORT", [{"direction":"SHORT"},{"direction":"SHORT"}], None))
PY
```
**Deploy/rollback:** worker restart (`sudo systemctl restart warroom-worker`) agar job
`collect` memakai kode baru; rollback `git revert`.

### US1.2 — Runbook trade pertama (B, 3 SP)

Buat `docs/runbook-trade-pertama.md`:
- **Pre-sesi:** status API (`connected`, `eval_sesi`, `eval_atr`, `spread`), posisi 0,
  balance/equity, `deals.csv` header, EA log v3.1.
- **Sesi 08–09:** cek snapshot tiap 60 detik; jika entry, catat ticket.
- **Post-close:** query `deals.csv`, `/journal/trades`, bandingkan statement MT5;
  simpan screenshot + output SQL di `artifacts/sprint-1/trade-<ticket>/`.
- **Jika deal hilang:** cek log EA `PERINGATAN laporan deal`, respons API, lalu insiden.

AC: dry-run dengan deal sintetis (sudah terbukti) + checklist ditandatangani saat trade nyata.

### US1.3 — Panel status Reaper di cockpit (B, 3 SP)

- Pindahkan/kopikan kartu `Status mesin Reaper` dari `ForexSinyal.svelte` ke
  `ForexCockpitExness.svelte` (atau komponen `StatusReaper.svelte` reusable).
- Tampilkan: sesi aktif/tidak, `eval_alasan`, `eval_atr`, `eval_spread`, `eval_rsi`,
  `eval_ema_fast/slow`, `eval_tren`, umur evaluasi.
- Tambah tautan “Lihat detail” ke tab Sinyal.

Verifikasi: `npm run check`, `npm run test`, screenshot 1280 dan 390.

### US1.4 — Watchdog deal & telemetri (A, 3 SP)

- Perluas job `pantau-tick`/`source-health`:
  - snapshot `mt5_snapshot` > 120s saat `eval_sesi=true` → alert `mt5_telemetri`;
  - `deals.csv` tidak bertambah 5 menit setelah posisi tertutup (posisi 0 dan
    `net_pnl_today_usd` berubah) → alert `deal_hilang`.
- Uji dengan mematikan telemetri di klon; alert muncul di tabel `alerts` dan Telegram.

### US1.5 — Tracker DoD (B, 2 SP)

`tools/forwardtest_status.py`:
- Baca `deals.csv`, hitung trade tertutup, hari sejak trade pertama, fill tanpa deal.
- Output JSON + baris ringkas; tambahkan ke `publish-facts` atau tampilkan di cockpit.
- Tes unit untuk CSV kosong, 1 trade, trade dengan net negatif.

---

## 7. Langkah implementasi — sprint berikutnya (ringkas)

**Sprint 2**
- `tools/rekonsiliasi_deals.py`: bandingkan `deals.csv` dengan statement MT5 (CSV/HTML),
  toleransi $0,01; jalankan harian.
- `/journal/edge`: chart slippage/latency; tes 503 vs data.
- ADR-001: `deals.csv` sumber closed trade; `trades` DB diisi importer atau dihapus.
- Scanlog forex: pisahkan `verdicts.jsonl` crypto dari `eval_alasan` EA.

**Sprint 3**
- Token map: `DESIGN.md` → `apps/web/src/app.css`; cek kontras dengan MCP
  `check_contrast` untuk pasangan `on-surface/surface`, `text-3/surface`, `accent/surface`.
- Layout 3 kolom; tabel 24/30px; `font-variant-numeric: tabular-nums`.
- Komponen: `StatusChip`, `MetricTile`, `DataTable`, `EmptyState`, `FreshnessBadge`.
- Copy pass antislop; hapus teks generik.

**Sprint 4**
- Rotasi kredensial satu per satu; simpan di `/etc/warroom/*.env` (600); gitleaks.
- Sudoers: allowlist eksplisit untuk perintah operasi; dokumentasikan.
- Restore drill: `pg_dump` → DB uji; rollback web dari `backups/web-*`.
- CI: pecah PR 75 commit menjadi rangkaian PR kecil; `ops/ci-local.sh`.

**Sprint 5**
- Real-tick: perbaiki Model 3 0 tick; jalankan 3 tahun; simpan laporan.
- Matriks vendor: trial, lot tetap, $100 path; rekomendasi paper.
- Registry parameter: `docs/ea-parameters.md` + tes regresi nilai default.

---

## 8. Peta tooling (skill & MCP)

| Pekerjaan | Skill/MCP |
|---|---|
Perencanaan & task breakdown | `agents/planning-and-task-breakdown`, `agents/spec-driven-development`, `execplan` |
Scrum & flow | `sprint-planning`, `flow-metrics-interpreter`, `sprint-retro-facilitator` |
Debug exposure | `agents/debugging-and-error-recovery`, `agents/test-driven-development` |
API/journal | `agents/api-and-interface-design`, `agents/security-and-hardening` |
UI & token | `stitch::*`, Stitch MCP (`list_projects`, `get_project`), `antislop`, `antislop-ui`, `design-tokens`, `agents/frontend-ui-engineering` |
Kontras | MCP `antislop-contrast` (`check_contrast`) |
EA/binary audit | REA MCP + Ghidra 12.1.4 (`open_binary`, `inspect_pe_imports`, `analyze_function`) |
Backtest | `agents/performance-optimization`, `backtest-*` |
Docs/ADR | `agents/documentation-and-adrs`, `technical-documentation` |
Keamanan | `agents/security-and-hardening`, `dependency-audit`, `hipaa` tidak relevan |
Review | `code-review-and-quality`, `receiving-code-review`, `verification-before-completion` |

---

## 9. Risiko & keputusan owner

| Risiko/Keputusan | Dampak | Usulan |
|---|---|---|
Batas exposure: gate 2 total vs executor 3 total/2 searah | Scan dan eksekusi tidak sepakat | Samakan ke **3 total, 2 searah**; gate baca settings |
Gate 90% vs 95%+deff | Menentukan kapan strategi boleh live | Owner putuskan; tulis ADR |
Saldo demo $1.000 vs $10.000 | Partial TP mati di $1k; statistik berbeda | Isi $10k atau terima varian tanpa partial |
Rotasi kredensial | Integrasi bisa putus | Jadwalkan Sprint 4; satu per satu + smoke test |
Real-tick backtest | 0 tick; hasil belum terbukti | Sprint 5; jangan naikkan modal sebelum ada |
Vendor EA trial | Tidak boleh live | Paper-only; keputusan di Sprint 5 |
75 commit belum di remote | Risiko kehilangan | Sprint 4; PR bertahap |
REA Ghidra | OMP perlu reload untuk memuat env | Reload sekali; Hermes sudah memakai env baru |

---

## 10. Metrik & laporan

- **Velocity:** SP selesai / sprint (target 16).
- **Fill completeness:** `deals.csv` vs statement (target 100%).
- **Telemetry uptime:** snapshot <120s selama sesi (target ≥99%).
- **Deal lag:** waktu close → baris `deals.csv` (target <60 detik).
- **Escaped defects:** bug yang lolos ke produksi (target 0).
- **MTTD/MTTR** alert (target <5 menit / <30 menit).
- Laporan harian async; review Jumat dengan bukti perintah, bukan klaim.

---

## 11. Artefak

```
docs/rencana-scrum-20261030.md   # dokumen ini
docs/sprint-1.md                 # log harian + keputusan
docs/runbook-trade-pertama.md    # US1.2
docs/adr/                        # ADR-001..003
artifacts/sprint-1/              # bukti: scan, screenshot, SQL, log
tools/forwardtest_status.py      # US1.5
```

**Aturan bukti:** setiap demo menyertakan perintah + output ringkas; angka tanpa
sumber dianggap belum ada.
