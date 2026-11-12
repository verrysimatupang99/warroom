# Rencana Optimasi Server `polywarroom` — MOP

> **For agentic workers:** Rencana ini dieksekusi oleh Claude (Cowork, native host) via SSH ke
> `polywarroom`. Setiap langkah punya perintah verifikasi + nilai yang berarti lolos.

**Goal:** Turunkan biaya server dari $13,70 → $6,50/bulan tanpa kehilangan data, dengan
pembersihan layanan yang tidak dipakai dan verifikasi di setiap tahap.

**Architecture:** Urutan aman — arsip → hentikan → verifikasi → disable. Tidak ada
penghapusan data. Semua tindakan destruktif di tahap akhir dan bisa di-rollback dari
snapshot Webdock (5 snapshot, terbaru 2026-11-06 05:18).

**Tech Stack:** systemd, bash, SSH, Webdock MCP (read-only), snapshot Webdock.

**Spec:** [[Status Server polywarroom - 6 Nov 2026]] (Obsidian) + audit repo
`docs/audit-offsite-backup-20261103.md`.

---

## Global Constraints

- **Snapshot terbaru:** `2026-11-06 05:18` (ID 9294398), status `completed`. Semua
  penghapusan boleh karena bisa rollback.
- **Layanan inti yang HARUS tetap `active`:** `warroom-api`, `warroom-worker`,
  `warroom-web`, `trading-engine`, `postgresql@16-main`, `nginx`.
- **Pasar fokus:** FOREX, IDX, CRYPTO. **Skip:** Polymarket, GMGN, Meteora, LPagent.
- **Data Polymarket TIDAK boleh dihapus** — hanya `disable` (berhenti ambil data baru).
- **Hemat target:** ~440 MB RAM dari `poly-agent` + `9router`.
- **Disk KVM tidak bisa dikecilkan.** Downgrade hanya core/RAM.
- **`sudo` NOPASSWD hanya `/usr/bin/systemctl`** (di `/etc/sudoers.d/warroom-agent`).
  Perintah lain butuh password — jalankan manual oleh owner.
- **Jangan sentuh VM Azure `20.212.109.170`** (`HOLD_DO_NOT_TOUCH_AZURE_VM.md`).

## Review Focus

| Kondisi | Perilaku yang diharapkan | Diuji di |
|---|---|---|
| `poly-agent` mati tapi recorder masih jalan | Dataset tetap terisi; tidak error | Task 2 Step 4 |
| `9router` dimatikan lalu ada yang memanggil port 20128 | Gagal tegas, bukan hang | Task 3 Step 4 |
| `warroom-api` restart setelah pembersihan | `/api/v1/build` = 200 | Task 4 Step 3 |
| Disk naik lagi setelah backup | Alert `slo/disk` bukan kejutan | Task 5 |
| Downgrade 2 core → beban puncak | Load tetap < 2.0, tidak swap thrash | Task 6 Step 4 |

---

## Task 1: Arsip konfigurasi sebelum perubahan

**Files:**
- Create: `/home/admin/warroom-arsip/polymarket/` (di server)

- [ ] **Step 1: Salin unit file yang akan diubah**

```bash
ssh -i ~/.ssh/polywarroom_rsa admin@217.78.237.133 '
mkdir -p /home/admin/warroom-arsip/polymarket
for u in poly-agent polymarket-research-recorder; do
  systemctl cat $u.service > /home/admin/warroom-arsip/polymarket/$u.service.txt
done
systemctl --user list-timers --all --no-pager > /home/admin/warroom-arsip/polymarket/user-timers.txt
'
```

Expected: 3 file terbuat.

- [ ] **Step 2: Verifikasi arsip lengkap**

Run: `ssh ... 'ls -la /home/admin/warroom-arsip/polymarket/'`
Expected: `poly-agent.service.txt`, `polymarket-research-recorder.service.txt`,
`user-timers.txt` semuanya ada dan > 0 byte.

- [ ] **Step 3: Catat ukuran data Polymarket (tidak dihapus, hanya dicatat)**

Run: `ssh ... 'du -sh /var/lib/poly-research /opt/polymarket 2>/dev/null'`
Expected: angka tercatat (perlu sudo — catat sebagai "perlu owner" bila gagal).

---

## Task 2: Skip Polymarket — `disable`, arsip tetap

**Files:**
- Modify: state systemd di server (bukan repo)

- [ ] **Step 1: Stop dulu (bukan disable)**

```bash
ssh ... 'sudo -n systemctl stop poly-agent.service polymarket-research-recorder.service'
```

Expected: tanpa error.

- [ ] **Step 2: Verifikasi proses mati**

Run: `ssh ... 'pgrep -fc "poly-agent|research-recorder" || echo 0'`
Expected: `0`

- [ ] **Step 3: Verifikasi layanan inti tidak terganggu**

Run:
```bash
ssh ... 'for s in warroom-api warroom-worker warroom-web trading-engine postgresql@16-main; do
  printf "%s=%s " $s $(systemctl is-active $s); done; echo'
```
Expected: semuanya `active`.

- [ ] **Step 4: Disable (tidak akan nyala saat reboot)**

```bash
ssh ... 'sudo -n systemctl disable poly-agent.service polymarket-research-recorder.service'
```

Expected: `Removed .../multi-user.target.wants/...`

- [ ] **Step 5: Verifikasi RAM turun**

Run: `ssh ... 'free -m | awk "/^Mem:/{print \$7}"'`
Expected: **≥ 12.760 + 260 = ~13.020 MB** (toleransi ±100 MB).

- [ ] **Step 6: Verifikasi data Polymarket MASIH ADA (tidak terhapus)**

Run: `ssh ... 'ls /var/lib/poly-research/paired 2>/dev/null | head -3'`
Expected: direktori & file masih ada.

---

## Task 3: Matikan `9router` — 177 MB, nol klien

**Files:** none (proses manual, bukan systemd unit)

- [ ] **Step 1: Konfirmasi nol klien sekali lagi**

Run: `ssh ... 'ss -tn | grep -c ":20128" || echo 0'`
Expected: `0`. **Kalau bukan 0 → HENTI, laporkan ke owner.**

- [ ] **Step 2: Catat PID & perintah (untuk hidupkan lagi)**

Run: `ssh ... 'ps -o pid,args -p 909506 --no-headers'`
Expected: PID + `node /home/admin/.npm-global/bin/9router -p 20128 -H 0.0.0.0 --skip-update -n`

- [ ] **Step 3: Kill proses**

```bash
ssh ... 'kill 909506'
```

- [ ] **Step 4: Verifikasi mati & port bebas**

Run: `ssh ... 'pgrep -f 9router >/dev/null && echo MASIH_HIDUP || echo MATI; ss -tln | grep -c 20128 || echo 0'`
Expected: `MATI` dan `0`.

- [ ] **Step 5: Verifikasi RAM turun**

Run: `ssh ... 'free -m | awk "/^Mem:/{print \$7}"'`
Expected: **≥ 13.020 + 177 = ~13.200 MB**

- [ ] **Step 6: Verifikasi tidak ada autostart yang menghidupkannya lagi**

Run: `ssh ... 'crontab -l | grep -c 9router; ls /etc/systemd/system/ | grep -c 9router'`
Expected: `0` dan `0`. (Baris cron yang ada sudah berstatus `#` = dikomentari.)

---

## Task 4: Verifikasi kesehatan War Room setelah pembersihan

**Files:** none

- [ ] **Step 1: Semua layanan inti active**

Run:
```bash
ssh ... 'for s in warroom-api warroom-worker warroom-web trading-engine postgresql@16-main nginx; do
  printf "%-24s %s\n" $s $(systemctl is-active $s); done'
```
Expected: 6 baris, semuanya `active`.

- [ ] **Step 2: API menjawab**

Run: `ssh ... 'curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:8800/api/v1/build'`
Expected: `200`

- [ ] **Step 3: Web menjawab**

Run: `ssh ... 'curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1/'`
Expected: `200` atau `302` (redirect ke `/masuk`).

- [ ] **Step 4: DB menerima koneksi**

Run: `ssh ... 'ss -tn | grep -c ":5432"'`
Expected: **≥ 12** (sama seperti baseline).

- [ ] **Step 5: Load tidak naik**

Run: `ssh ... 'cat /proc/loadavg | cut -d" " -f1-3'`
Expected: load 1-menit **< 1.0** (baseline 0.43).

- [ ] **Step 6: Disk tidak berubah drastis**

Run: `ssh ... 'df -h / | awk "NR==2{print \$5}"'`
Expected: `70%` atau lebih rendah.

---

## Task 5: Turunkan retensi backup (hemat disk, bukan RAM)

**Files:**
- Modify: `/etc/warroom/backup.env` di server (perlu owner/sudo)

- [ ] **Step 1: Cek nilai sekarang**

Run: `ssh ... 'systemctl show -p Environment warroom-backup-postgres.service | tr " " "\n" | grep KEEP'`
Expected: `WARROOM_DB_BACKUP_KEEP=14` (default dari skrip).

- [ ] **Step 2: Set ke 7**

Owner jalankan di server:
```bash
sudo mkdir -p /etc/warroom
echo 'WARROOM_DB_BACKUP_KEEP=7' | sudo tee /etc/warroom/backup.env
sudo systemctl edit --full warroom-backup-postgres.service   # tambah EnvironmentFile=/etc/warroom/backup.env
```

- [ ] **Step 3: Verifikasi rotasi berikutnya menyisakan 7**

Run (setelah backup harian berikutnya): `ssh ... 'ls -1 /home/admin/backups/postgres/*.dump | wc -l'`
Expected: `7` (dari 11 sekarang).

- [ ] **Step 4: Verifikasi ukuran backup turun**

Run: `ssh ... 'du -sh /home/admin/backups/postgres'`
Expected: ~0,8 GB (dari 1,2 GB).

---

## Task 6: Downgrade Webdock 8 core/16 GB → 2 core/8 GB

**Files:** none (operasi panel Webdock oleh owner)

- [ ] **Step 1: Owner buat snapshot manual sebelum downgrade**

Panel Webdock → Snapshots → Create → nama `pre-downgrade-2026-11-06`.
Expected: snapshot baru muncul, status `completed`.

- [ ] **Step 2: Owner geser slider ke 2 core / 8 GB / 50 GB**

Expected: harga **$6,50/bulan** (terkonfirmasi owner sebelumnya).
Catatan: transfer turun 5 TB → 2 TB (pemakaian nyata ~184 GB/bulan, aman).

- [ ] **Step 3: Verifikasi spek baru via Webdock MCP (read-only)**

Di Claude Code CLI: "Tampilkan profil server polywarroom sekarang."
Expected: `2 thread` / `8 GB` / `50 GB`.

- [ ] **Step 4: Verifikasi server sehat setelah downgrade**

```bash
ssh ... 'for s in warroom-api warroom-worker warroom-web trading-engine postgresql@16-main nginx; do
  printf "%-24s %s\n" $s $(systemctl is-active $s); done
  free -m | head -2
  cat /proc/loadavg | cut -d" " -f1-3
  df -h / | tail -1'
```
Expected: 6 layanan `active`; RAM available **≥ 3.000 MB**; load 1-menit **< 2.0**; disk ≤ 75%.

- [ ] **Step 5: Verifikasi API & web tetap 200**

Run: Task 4 Step 2 & 3.
Expected: `200`.

- [ ] **Step 6: Pantau 24 jam**

Cek berkala: `slo/disk` (warn 80%), `slo/backup` (>26 jam), load, swap.
Expected: tidak ada alert baru; swap tidak tumbuh.

- [ ] **Step 7: Rollback bila bermasalah**

Panel Webdock → Snapshots → Restore `pre-downgrade-2026-11-06`.
Expected: spek kembali 8 core/16 GB.

---

## Task 7: Perbaiki `paper20-cycle` (tercatat, belum dikerjakan)

**Files:**
- Modify: `ops/paper20_cycle.py:60` (di repo)

- [ ] **Step 1: Cari pengganti `warroom_worker.jobs.llm`**

Run: `grep -rn "paper_scan\|paper_eval" --include="*.py" services/ packages/ | head`
Expected: ditemukan modul baru yang memuat handler tersebut.

- [ ] **Step 2: Perbaiki import**

Ganti baris 60 agar mengarah ke modul yang benar.

- [ ] **Step 3: Verifikasi unit tidak lagi gagal**

Run: `ssh ... 'systemctl start paper20-cycle && systemctl is-active paper20-cycle'`
Expected: `active` (bukan `failed`).

---

## Ringkasan dampak

| Tahap | RAM available | Catatan |
|---|---|---|
| Baseline | 12.760 MB | setelah Hermes mati |
| Task 2 (Polymarket) | ~13.020 MB | +260 MB |
| Task 3 (9router) | ~13.200 MB | +177 MB |
| Task 6 (downgrade) | ~3.000+ MB | dari kuota 8 GB |

| Biaya | |
|---|
| Sebelum | $13,70/bulan |
| Sesudah | **$6,50/bulan** |
| Hemat | **$7,20/bulan = $86/tahun** |

## Yang TIDAK dilakukan

- ❌ Menghapus data Polymarket/GMGN (hanya `disable`)
- ❌ Menyentuh VM Azure
- ❌ Migrasi ke provider lain
- ❌ Memasang Docker/psql di laptop
- ❌ Rotasi Telegram (keputusan owner)
