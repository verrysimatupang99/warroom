# Inventaris Tencent — akar proyek War Room (6 Okt 2026)

Pemilik: *"beberapa di war room itu awal mulanya ada di Tencent semua termasuk data diskusi,
cronjob, hermes, omp, etc"*. Dokumen ini **mencatat apa adanya** (baca-saja, tanpa mengubah
apa pun di Tencent) dan memisahkan mana yang sudah pindah, mana yang masih jadi akar.

Akses: `ssh -i /etc/warroom/tencent_ed25519 ubuntu@43.155.219.37` (baca-saja, mode 600).

---

## 1. Ringkasan

| Kelompok | Isi | Ukuran / jumlah | Status di Webdock |
|---|---|---|---|
| **Diskusi/chat** | `~/.hermes/state.db` — 868 sesi · 40.585 pesan (2.900 user, 19.091 asisten) · rentang 2026-08-24 → 2026-10-06 | **277 MB** | Sebagian: 42 sesi, 5.783 pesan (**pindahan sebagian**) |
| **Cronjob** | `~/.hermes/cron/jobs.json` — **46 job** (18 aktif, 28 pause) · + 28 berkas backup config | 133 KB + backup | Belum dipindah |
| **Hermes (runtime)** | `~/.hermes/` — skills, memories, scripts, shared-state, trading-journal, media | total besar (sessions 93 MB) | **Terpasang juga di sini** (`~/.hermes`, `~/.local/bin/hermes`) |
| **OMP / opencode** | Webdock: `~/.omp/agent/{history.db (135 prompt), agent.db}` + `natives/ 363 MB`, `puppeteer/ 382 MB`, `run/ 106 MB` · Tencent: `~/.config/opencode/`, `~/opencode-telegram-gateway`, `~/codex-dev-mcp-suite` | ~1 GB di Webdock | **Sudah ada di sini** (OMP "Oh My Pi" — harness di atas provider kiyara/qonek/nutaraline) |
| **Arsip tick IDX** | `~/.hermes/cron/state/arjum_trades.db` — 24.964.749 baris (22,3 juta bertanggal) | **4,94 GB** | Dipakai via mirror/salinan (`state/idx616_mirror.json`); DB penuh belum |
| **Proyek lain** | `~/polymarket-migration` (145M) · `~/projects` (384M) · `~/research` (227M) · `~/cron_fix_616/backup-20260913_052624` (skrip `.hermes/scripts` = tambang IDX-Arjum) | ~750 MB | Sebagian (Arjum collector, BSJP dari salinan) |

---

## 2. Data diskusi — yang paling tidak tergantikan

`~/.hermes/state.db` (skema: `sessions`, `messages` + FTS) berisi **seluruh riwayat percakapan
pemilik dengan Hermes** sejak 24 Agustus: keputusan desain polymarket war room, iterasi UI,
audit kuota Arjum, hingga percakapan 6 Okt. Ini "otak proyek" yang tidak ada duanya.

- Webdock punya `state.db` sendiri (37 MB, 42 sesi, rentang ~5–6 Okt) — jadi **ada benang yang
  terputus**: keputusan sebelum 5 Okt hanya ada di Tencent.
- `~/.hermes/sessions/` (93 MB, 256+ berkas `request_dump_*.json`) = dump request, bukan
  percakapan lengkap.
- `~/.omp/agent/history.db` (Webdock) = 135 prompt OMP 26 Sep–6 Okt; **awalnya proyek ini
  dikerjakan lewat OMP ini** (prompt pertama: *"cek proyek polymarket war room"*, 26 Sep).

**Rekomendasi:** sebelum VM dimatikan, tarik `state.db` + `sessions/` + `trading-journal/`
ke arsip lokal (baca-saja, tanpa kredensial). Itu satu-satunya data yang hilang permanen
kalau VM dihapus.

## 3. Cronjob — 46 job, 18 masih aktif

Yang **masih aktif** di Tencent dan tidak punya padanan penuh di War Room:

| Job | Irama | Kenapa belum pindah |
|---|---|---|
| `arjum-ws-daemon-bursa-open` | jam bursa | Menulis `arjum_trades.db` (WebSocket, tanpa kuota REST) — sumber tick IDX |
| `crypto-5agent-pipeline-653` | berkala | Pipeline 5 agen kripto (War Room punya `pod`/`pod_llm`, belum 1:1) |
| `crypto-auto-exec-653` / `crypto-auto-eval-653` | berkala | Eksekusi & evaluasi otomatis kripto (di War Room masih paper) |
| `xauusd-*` (5 job: smc-daily, journal-tracker, morning-outlook, reactive, multi-pair) | harian/berkala | Forex — keputusan owner: **forex belum diputuskan** |
| `hl-whale-accum-653` / `hl-whale-digest-653` / `whale-series-logger` | berkala | Hyperliquid whale — War Room baru baca `hl` via `lt hl` |
| `sectors-report-card-grader` | harian | IDX sektor (belum ada padanan) |
| `auto-research-weekly` | mingguan | Riset otomatis |
| `Disk Guard` / `Disk Hygiene` | berkala | Perawatan host (pindah = keputusan ops terpisah) |

Job yang **sudah di-pause** (28): hampir semua IDX (Signal, Scalp, Broker Flow, Ara Hunter,
dll) — di-pause 5–6 Okt karena pindah ke War Room + hemat kuota Arjum.

## 4. OMP ("Oh My Pi") — harness yang dulu menjalankan proyek

- Webdock: `~/.local/bin/omp`, `~/.omp/agent/config.yml` — provider `kiyara` (utama),
  fallback `qonek` → `nutaraline`; model `deepseek-v4.1-flash`. **Orkestrator asli** dari
  26 Sep–6 Okt (135 prompt).
- `~/.omp/agent/APPEND_SYSTEM.md` memuat aturan proyek (balasan Bahasa Indonesia).
- Tencent juga meninggalkan: `~/opencode-telegram-gateway`, `~/codex-dev-mcp-suite`,
  `~/.config/opencode/` — keluarga harness yang sama (era sebelum OMP).
- ⚠️ `~/.omp` menyimpan ~1 GB (puppeteer, natives, run) — bukan data proyek, aman di-prune
  terpisah bila ruang disk jadi masalah.

## 5. Yang sudah dipindah (agar tidak dihitung dua kali)

| Sudah di Webdock | Bukti |
|---|---|
| Radar rantai | **6 Okt: pindah penuh** — `lt radar-update` lokal, lihat `radar-lokal-recreate-2026-10-06.md` |
| idx616 | `collectors/idx616.py` + mirror `state/idx616_mirror.json` (commit `344e15f`) |
| BSJP + SMA10 | Filter dipindah apa adanya dari `idx_bsjp_watch.py`; SMA10 dari arsip tick (`tencent-akses-dan-bsjp-2026-10-05.md`) |
| Skrip IDX-Arjum (15 berkas) | Sudah dibaca & diserap (`docs/belajar/idx-arjum.md`, dst.) |
| Kuota Arjum | Diukur & dijaga (6.003/hari; kunci Arjum = War Room saja) |

## 6. Rekomendasi sebelum VM dimatikan

1. **Tarik arsip diskusi** (`~/.hermes/state.db` 277 MB + `sessions/` 93 MB +
   `trading-journal/` 14 MB) — baca-saja, simpan lokal, jangan pernah masuk repo (berisi
   percakapan operasional; bisa memuat nama host/angka, bukan kredensial).
2. **Putuskan nasib 18 cronjob aktif** satu per satu: pindah ke worker War Room, biarkan
   mati, atau (untuk yang hanya perawatan host) pindah ke sini.
3. **Arsip tick Arjum 4,94 GB** — kalau BSJP ke depan butuh SMA10 lebih dari mirror,
   pindahkan DB atau potong rentang yang dipakai saja.
4. **Salinan kredensial Tencent** (`~/.local/share/credential-vault/sessions/` — spaceship,
   idwebhost, alibaba): **jangan disalin**, cukup tahu ada (aturan proyek).
5. Setelah VM mati: hapus kunci/known_hosts Tencent di box ini, tutup allowlist sudo terkait,
   dan tandai dokumen ini "arsip".

---

## Lampiran — cara memeriksa ulang (baca-saja)

```bash
ssh -i /etc/warroom/tencent_ed25519 ubuntu@43.155.219.37 \
  'python3 -c "import json;d=json.load(open(\"/home/ubuntu/.hermes/cron/jobs.json\"));print(len(d[\"jobs\"]))"'
# diskusi:
ssh ... 'sqlite3 ~/.hermes/state.db "select count(*) from messages"'
# arsip tick:
ssh ... 'ls -la ~/.hermes/cron/state/arjum_trades.db'
```
