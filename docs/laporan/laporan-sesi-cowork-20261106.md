# Laporan sesi agent — 5–6 Nov 2026 (Cowork)

Ringkasan kerja otomatis selama sesi, dari repo clone lokal + verifikasi nyata
(gitleaks biner, pytest, gh CLI). Semua klaim di bawah punya bukti perintah.

---

## 0. Konteks awal vs koreksi

Sesi dimulai dengan analisis read-only. Beberapa dugaan awal **dikoreksi oleh data
server** yang dilaporkan owner:

| Dugaan awal | Fakta server | Status |
|---|---|---|
| Disk krisis 92–96% | 68.6% (33/48 GB, sisa 15 GB) | dokumen 1 Nov basi |
| Trade belum masuk DB | ledger=114 db=114, sync 300s | ingest bekerja |
| Layanan tak terverifikasi | 4 unit active | sehat |

**Pelajaran:** pisahkan "kebenaran kode" (bisa diverifikasi offline) dari "kebenaran
runtime" (perlu server). Laporan ini menandai keduanya secara eksplisit.

## 1. Infrastruktur: egress & GitHub CLI

- **Egress sandbox:** semula 403 (`proxy after CONNECT`) ke semua domain. Hermes
  membuka `vmEgressPolicy`→unrestricted. Terverifikasi: `github.com` 200,
  `api.github.com` 200, `api.github.com/zen` mengembalikan teks.
- **GitHub CLI:** `gh` v2.103.3 dipasang di `~/.local/bin`. Awalnya belum login.
  Setelah owner menyediakan token, `gh auth status` → **logged in
  verrysimatupang99** (scope: gist, read:org, repo, workflow).
- **Rekonsiliasi repo:** `git fetch` berhasil. **GitHub `main` = `3549d57`**,
  clone lokal semula `2384c6f` → tertinggal 4 commit (#99–#102). Working tree
  disinkronkan ke upstream lalu patch lokal diterapkan ulang (lihat §3).

> Catatan: `git commit`/`checkout` di sandbox terhalang mount `.git` read-only
> (`index.lock` tak bisa dihapus). Isi file benar (disinkronkan per-file dari
> `origin/main`); **commit harus dilakukan di sisi owner/agent lain.**

## 2. Temuan keamanan

### 2.1 P0 — API hash Telegram bocor (sudah dikomunikasikan)
`services/tg-engine/README.md` memuat API ID + API hash + sesi. **Upstream #101
sudah menghapus nilainya** (pakai env `TG_API_ID`/`TG_API_HASH`) dan #100 memindahkan
rahasia `engine.py` ke env. Yang **belum** ada di upstream: **rule gitleaks** untuk
mendeteksi pola ini. Itu ditambahkan di patch ini (§3.1).

### 2.2 P0 — Bypass autentikasi `auth_ea.py` (BELUM diperbaiki upstream)
`verify_mt5_or_admin` memilih `CF-Connecting-IP` lebih dulu. Header itu **tidak**
di-set nginx (`ops/nginx-warroom.conf` hanya menyetel `X-Real-IP` + `X-Forwarded-For`),
jadi penyerang cukup mengirim `CF-Connecting-IP: 138.91.35.65` untuk lolos ke seluruh
endpoint `/mt5/*` (telemetry, deal, fill, accounts, panels, …).

Dibuktikan dengan simulasi logika lama: skenario "klien kirim CF-Connecting-IP palsu"
→ **LULUS**.

### 2.3 IP VM live tidak ada di allowlist
`auth_ea.AZURE_MT5_IP` hanya `138.91.35.65` (Azure lama). VM trader live
`mt5-trader-vm2` = **`20.212.109.170`** (AGENTS.md/HOLD) tidak diizinkan.

## 3. Perubahan yang dikerjakan (working tree, belum commit)

### 3.1 `.gitleaks.toml` — rule Telegram
Tambah `telegram-api-hash` & `telegram-api-id` (regex teruji menangkap format README
nyata: `API HASH: \`…\``, `**API HASH:**`, `TelegramClient(..., 'hash')`). Plus
allowlist path untuk `gh_token.txt`/`.gh-config/` (token sesi agent, tak ter-track).

**Bukti (gitleaks v8.30.1, checksum CI):**
- `2384c6f:services/tg-engine/README.md` → `leaks found: 1` (DITANGKAP).
- Working tree (upstream+parch) → `no leaks found`.
- Upload config ke `2384c6f` → masih menangkap (allowlist tidak menutupi).

### 3.2 `services/api/src/warroom_api/auth_ea.py` — tutup bypass
- IP asal hanya dipercaya dari proxy/loopback tepercaya; header diabaikan bila koneksi
  langsung.
- Urutan: `X-Real-IP` (di-set nginx) > `CF-Connecting-IP` (opt-in `WARROOM_TRUST_CF=1`)
  > `X-Forwarded-For` **elemen terakhir**.
- Allowlist: `20.212.109.170` + `138.91.35.65` + override `WARROOM_MT5_IPS`.
- Jalur service-token & cookie-admin tidak berubah.

### 3.3 `services/api/tests/test_auth_ea.py` — 10 tes
Murni, tanpa DB. Bukti tes bukan kosong: **terhadap versi lama 6 gagal** (termasuk
dua tes bypass), terhadap versi baru **10/10 lulus**.

### 3.4 `ops/verify-server.sh` — skrip bukti server (read-only)
Mengumpulkan: HEAD vs origin, unit systemd, disk, jumlah `trades`/`verdicts`, job
`trades-crypto-sync`/`paper-scan`, ledger, gate live, telemetri bridge, sesi Telegram
(P0), backup, branch. Tidak menulis DB / restart unit / menyentuh MT5.

### 3.5 `SECURITY-telegram-hash.md`
Langkah rotasi API hash + cabut sesi + bersihkan history untuk owner.

## 4. Bukti kualitas (semua dijalankan nyata)

| Perintah | Hasil |
|---|---|
| `pytest services/api/tests/test_auth_ea.py` | **10 passed** |
| `ruff check auth_ea.py test_auth_ea.py` | All checks passed |
| `pytest packages/core/tests` | **190 passed, 49 skipped** |
| `pytest core/tests/test_trades_{forex,idx}.py` | **12 passed** |
| `pytest services/tg-engine/tests` | **24 passed** (risk_gate 14, engine 10) |
| `pytest services/worker/tests` (murni) | **29 passed, 1 gagal-lingkungan** (`lt` binary absen di sandbox, bukan regresi) |
| `gitleaks dir .` | no leaks (working tree) |
| `bash -n ops/verify-server.sh` | OK |

## 5. Temuan deep-dive lain (verifikasi kode, bukan asumsi)

- **`trades-crypto-sync`:** jalur lengkap & idempoten (kunci venue+mode+ext_id),
  ledger rusak menahan ingest, `pnl` `None` bila bahan hilang (bukan 0). Sesuai fakta
  server (114=114).
- **`risk_gate.py` (tg-engine):** fail-closed (RR<1.5, umur>12 jam, data kurang, SL=entry,
  arah tak koheren). Ukuran lot dari saldo, bukan hardcode. Tidak membuka order.
- **`WarRoom_TelemetryBridge.mq5`:** read-only ("Tidak membuka order"), kirim ke
  `/api/v1/tencent/mt5/telemetry` & `/deal` (terdaftar di OpenAPI). Belum dikompilasi
  di terminal (docs multi-akun) — pekerjaan pemasangan, bukan pembangunan.

## 6. Yang perlu dilakukan owner (di luar kemampuan sandbox)

1. **Commit patch ini** dari sisi yang punya akses tulis `.git`. Patch ada di
   working tree; file baru: `test_auth_ea.py`, `ops/verify-server.sh`,
   `SECURITY-telegram-hash.md`. Perubahan: `.gitleaks.toml`, `auth_ea.py`, `.gitignore`.
2. **Rotasi API hash Telegram** (`SECURITY-telegram-hash.md`) — hapus aplikasi di
   `my.telegram.org`, cabut sesi lain. Ini wajib; hapus README saja tidak cukup.
3. **Instal bridge telemetri** (compile `WarRoom_TelemetryBridge.mq5`, isi `InpToken`
   = `WARROOM_EA_SYNC_TOKEN`, isi `InpApiBase`). Read-only, tidak menyentuh VM2.
4. **Backup offsite** — tunggu keputusan kredensial (audit 3 Nov sudah mendesain).
5. **Hapus branch usang** setelah verifikasi 0 commit unik:
   `feat/sumber-okx-idx-mt5` (snapshot pra-#88, jangan di-merge — akan mengembalikan
   LLM yang sengaja dibuang), `docs/backtest-reaper-1k` (file sudah di main).

## 7. Sisa risiko / belum diverifikasi

- **Runtime server** (status systemd, isi DB, sesi Telegram aktif) belum diverifikasi
  dari sesi ini — jalankan `ops/verify-server.sh` di server.
- **Commit** belum dilakukan (mount read-only). CI belum dijalankan (butuh push).
- Tes API `/mt5/*` (test_api.py) butuh Postgres; belum dijalankan di sandbox.
