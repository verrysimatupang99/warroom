# Laporan Audit & Perbaikan — 9 November 2026

**Sasaran:** PolyWarRoom (`polywarroom.vps.webdock.cloud`, 217.78.237.133) dan proyek War Room.
**Dikerjakan:** 9 Nov 2026, 00.20–04.50 WIB (8 Nov 17.20–21.50 UTC), atas mandat penuh owner.

---

## Ringkasan: 1 temuan kritis, 7 perbaikan, 4 unit bermasalah dibereskan

| # | Temuan | Tingkat | Status |
|---|---|---|---|
| 1 | `/term/` = shell browser **tanpa autentikasi**, siapa pun dapat shell sebagai `admin` | **KRITIS** | Ditutup |
| 2 | `ufw` mati padahal `ENABLED=yes` — semua port baru langsung publik | Tinggi | Diaktifkan |
| 3 | `0xgunsl1ng3r.xyz` mati (526), War Room tidak punya domainhidup | Tinggi | Pindah domain |
| 4 | `paper20-cycle` gagal tiap 15 menit (import modul yang sudah dihapus) | Sedang | Diperbaiki |
| 5 | `war-room-git-sync` gagal tiap 6 jam, dan menyasar repo yang salah | Sedang | Diperbaiki |
| 6 | `watchdog` berteriak "mt5_telemetri basi ~11.800 mnt" tiap 30 menit selamanya | Sedang | Digerbang |
| 7 | Permukaan PHP (`filemanager.php`) hidup di balik basic-auth | Sedang | Ditutup |
| 8 | `/9router/`, `/agent/` 502 permanen | Rendah | Dinonaktifkan |
| 9 | Wine prefix 2,1 GB menganggur di dalam repo | Rendah | Dihapus |
| 10 | 19 branch di remote (desain: 1) | Rendah | 12 dihapus, 6 dipertahankan |

---

## 1. KRITIS — `/term/` shell terbuka

`location ^~ /term/` memakai `auth_basic off` dan meneruskan ke `ttyd -p 7681 -i 127.0.0.1` yang
**tidak punya kredensial sendiri**. Artinya:

```
curl https://polywarroom.vps.webdock.cloud/term/     -> 200, halaman xterm
curl -X POST .../term/token                           -> 200, {"token": ""}
```

Siapa pun yang tahu URL-nya dapat shell sebagai `admin`. Ini terbuka **karena** domain
bawaan diaktifkan untuk app (sebelumnya `/term/` hanya hidup di vhost mati).

**Perbaikan:** wajib basic auth memakai `/etc/nginx/.htpasswd-warroom`.
Sekarang `/term/` → **401** dengan `WWW-Authenticate: Basic realm="War Room"`.

---

## 2. Firewall mati

`/etc/ufw/ufw.conf` berisi `ENABLED=yes` dan service `enabled`, tapi `ufw status` → **inactive**.
Yang aktif hanya aturan Tailscale. Konsekuensi: setiap proses yang bind `0.0.0.0`
otomatis terbuka ke internet tanpa persetujuan.

**Perbaikan:** `ufw --force enable`. Aturan lama dipertahankan (22, 80, 443, 50443,
50000:50099, 8055 hanya 172.16/12). Verifikasi dari luar:

| Port | Sebelum | Sesudah |
|---|---|---|
| 3100, 8800, 5432, 7681, 20128 | terbuka (bind lokal, tapi tanpa filter) | **tertutup** |
| 22, 80, 443, 50443 | jalan | jalan |

---

## 3. Migrasi domain

`0xgunsl1ng3r.xyz` → 526 karena symlink `sites-enabled/warroom` tidak ada, sehingga nginx
menyajikan cert `maximalabs.ai.id` untuk SNI itu (dibuktikan `openssl s_client`).

**Keputusan owner:** domain dipensiunkan (langganan Spaceship tetap jalan), War Room pindah
ke domain bawaan Webdock.

Script: `ops/aktifkan-domain-bawaan.py` — idempotent, backup ke `/var/backups/nginx/`,
`nginx -t`, rollback otomatis.

> **Pelajaran:** backup config **tidak boleh** ditaruh di `sites-enabled/`. Nginx memuat
> `include sites-enabled/*`, jadi `webdock.bak-*` ikut terbaca dan memicu
> `duplicate listen options for [::]:443`. Percobaan pertama gagal karena ini dan
> otomatis rollback; percobaan kedua sukses setelah backup dipindah.

Hasil routing domain bawaan:

| Path | Tujuan |
|---|---|
| `/` | app SvelteKit `:3100` (login di aplikasi, bukan basic-auth proxy) |
| `/api/v1/` | FastAPI `:8800`, `auth_basic off` (EA pakai `X-Warroom-Token`) |
| `/signals` | trading-engine `:8088` |
| `/komuter/`, `/komuter-api/` | statis `/srv/komuter/` + API `api-01:20272` |
| `/pratinjau/` | statis `/srv/pratinjau/` + unduhan EA |
| `/legacy/` | snapshot statis lama `/var/www/html` **ber-basic-auth** |
| `/term/` | ttyd `:7681` **ber-basic-auth** |
| `/maxxy/`, `/maxxy.apk`, `/hermes-mobile.apk` | aset aplikasi mobile |

`/9router/` dan `/agent/` dinonaktifkan (dikomentari): upstream `:20128` dan `:8790`
sudah tidak listen sejak audit 6 Nov → 502 permanen.

---

## 4. Permukaan PHP ditutup

Fakta yang ditemukan:
- `php8.3-fpm` **inactive + disabled**, `/var/run/php/` kosong → setiap `.php` **sudah 502**;
  angka 401 yang terlihat selama ini hanya basic-auth yang menutupinya lebih dulu.
- `/var/www/html/index.php` = halaman selamat datang Webdock, isinya
  *"YOU SHOULD DELETE THIS FILE"*.
- `/var/www/html/filemanager.php` (230 KB): **1 hit** dalam 39 hari log
  (`access.log` + semua `.gz`), dan itu bot memindai
  `/wp-content/plugins/hellopress/wp_filemanager.php` → 404.

**Perbaikan:** `location ~ \.php$` dan `error_page 404 /index.php` dibuang. Berkas
**diparkir** ke `/var/backups/www-html-php-parked/` (bukan dihapus).

**Renew cert tidak rusak** — dibuktikan, bukan diasumsikan:
`certbot renew --cert-name polywarroom.vps.webdock.cloud --dry-run` →
`all simulated renewals succeeded`, dan setelah certbot menulis ulang config,
kedua marker perubahan tetap utuh + `nginx -t` bersih.

---

## 5. Unit yang tadinya gagal

### `paper20-cycle` (gagal tiap 15 menit)
`ModuleNotFoundError: No module named 'warroom_worker.jobs.llm'` — modul itu dihapus di
commit `208de76` ("Buang LLM worker"). Handler-nya pindah ke `jobs.formula`.
Perbaikan: import diarahkan ke `warroom_worker.jobs.formula`.
Hasil: siklus pertama langsung menutup posisi **TP2 +1.00R**, dan fakta
`paper20/dompet` terbit (equity $20.0).

### `war-room-git-sync` (gagal tiap 6 jam)
Tiga masalah sekaligus:
1. Daftar `REPOS` salah total — 5 dari 6 entri **hilang atau bukan repo git**, dan
   repo yang sebenarnya (`/home/admin/warroom`) **tidak pernah ikut disinkronkan**.
2. `/opt/polymarket/...` butuh `sudo -n git`, tapi tidak ada entri sudoers untuk git →
   `a password is required`.
3. 8 berkas di `.git/` milik `root`, membuat operasi git gagal
   (`cannot lock ref ... Permission denied`).

Perbaikan: `REPOS=(/home/admin/warroom)`, polymarket dilepas dengan catatan (proyek
pensiun), `chown -R admin:admin .git`. Hasil log: `semua sinkron`.

### `live-trading-watchdog` (AWAS permanen)
Selalu `AWAS 3/4` dengan `mt5_telemetri basi ~11.800 mnt` (berkas terakhir disentuh
31 Okt 12:27 UTC). Penyebab: EA `WarRoom_AutoTrader` di Azure `mt5-trader-vm` berhenti
melapor karena **subscription Azure di-disable** — bukan gangguan server.

Perbaikan: gerbang `live-trading/state/mt5_ea_offline`. Alasannya sama dengan gerbang
`gmgn_siklus`/`lp_mark` yang sudah ada di kode: AWAS permanen menyamarkan kegagalan
nyata. Hapus berkas penanda itu begitu EA dinyalakan lagi → cek otomatis aktif kembali.
Hasil: `SEHAT 3/3`.

---

## 6. Kebersihan

- **Network disk:** wine prefix `ops/docker-mt5/config` (2,1 GB, gitignored, uid `ubuntu`)
  dihapus. EA di dalamnya (`WarRoom_AutoTrader.mq5`) **identik md5** dengan yang
  terlacak di git dan di `/srv/pratinjau/` (`6680306b…`), dan resep pembuatnya
  (`init_prefix.sh`, `install_wine.sh`, `docker-compose.yml`) tetap disimpan.
  Symlink `/var/www/html/phpmyadmin` dicabut (MariaDB + php-fpm mati).
  **Disk 48% → 44%** (bebas 2,1 GB).
- **Branch remote:** 19 → 7. Yang dihapus hanya branch yang **sudah merge** ke `main`
  (12 buah). Enam branch berisi commit yang belum masuk main **dipertahankan**:
  `docs/audit-server-20261105`, `docs/backtest-reaper-1k`, `feat/sumber-okx-idx-mt5`,
  `feat/tg-engine-ekspor-dialog-dan-filter-dm`, `fix/auth-ea-bypass-gitleaks`,
  `ops/paper20-import-fix`.
- **Proses yatim:** `cloudflared tunnel --url http://127.0.0.1:20128` berjalan 2 hari
  5 jam tanpa supervisor, menembak port yang tidak ada listener-nya (9Router sudah
  dimatikan saat audit 6 Nov). Dihentikan.

---

## 7. Yang sengaja TIDAK disentuh

| Hal | Alasan |
|---|---|
| `ai.maximalabs.tech` → 502 | Vhost yatim (upstream `:20129` mati). Server block wajib tetap ada karena certbot memakai `authenticator = nginx` untuk renew domain ini. 502 tidak memakan resource. |
| `poly-dashboard-sync.timer` | Masih menulis `/var/www/html` tiap 2 menit. Sekarang tidak sia-sia karena `/legacy/` menyajikan hasilnya. Overhead ~25 KB/2 menit. |
| Permission PHP-fpm package | Service dibiarkan `disabled`; kalau suatu saat butuh PHP, blok nginx harus dipasang ulang dari `/var/backups/nginx/`. |
| Box `instabox-box-2aacb3` | Menjalankan **akun MT5 REAL** (`452009427`). Tidak disentuh sama sekali. |
| Password sudo `admin` | Dikirim lewat chat; **sebaiknya diganti**. Tidak diubah diam-diam karena berisiko mengunci owner. |

---

## 8. Verifikasi akhir (dari jaringan luar)

```
/                        200   app War Room
/masuk                   200   halaman login
/forex, /jurnal          200
/api/v1/health           401   {"error":{"code":"unauthenticated"}}
POST /api/v1/auth/login  401   "kredensial tidak sah"  (jalur tulis + JSON tembus)
/signals                 200
/komuter/                200
/komuter-api/health      200
/pratinjau/              302 -> opsi-tampilan.html
/legacy/                 401   basic auth
/term/                   401   basic auth
/9router/, /agent/       404
/maxxy/, /hermes-mobile.apk 200
0xgunsl1ng3r.xyz         526   dipensiunkan (sesuai keputusan)
```

- `nginx -t` bersih; `systemctl` tanpa unit gagal.
- Sertifikat: `polywarroom` 14 Des 2026, `maximalabs.ai.id` 19 Jan 2027,
  `ai.maximalabs.tech` 17 Jan 2027, `0xgunsl1ng3r.xyz` 1 Jan 2027.
- Backup Postgres harian jalan (118 MB + `.sha256` + rotasi); SLO job melaporkan
  `disk=44% api=True alert=0`.
- Worker: 10 job terakhir semua `ok` (publish-facts, freshness, job-health,
  strategi-alert, poly-sync, slo-check, okx-sync, paper-eval, forwardtest-watchdog,
  source-health).
- Semua script ops **idempotent** — dijalankan ulang menghasilkan "sudah diterapkan".

## 9. Kalau mau mengulang / memulihkan

```bash
# semua script aman diulang, lihat dulu dengan --dry-run
sudo python3 ops/aktifkan-domain-bawaan.py --dry-run
sudo python3 ops/tutup-term.py --dry-run
sudo python3 ops/tutup-php-webdock.py --dry-run
sudo python3 ops/rapikan-sisa-vhost.py --dry-run
sudo python3 ops/kembalikan-path-statis.py --dry-run

# rollback config nginx ke kondisi sebelum perubahan apa pun
sudo cp /var/backups/nginx/webdock.bak-20261108-192808 /etc/nginx/sites-enabled/webdock
sudo nginx -t && sudo systemctl reload nginx

# hidupkan lagi cek telemetri EA
rm /home/admin/live-trading/state/mt5_ea_offline
```