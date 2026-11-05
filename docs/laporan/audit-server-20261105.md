# Audit server &amp; kondisi data — 5 Nov 2026

Audit dilakukan langsung di VPS `polywarroom` (217.78.237.133, Webdock, Ubuntu 24.04
Noble, 14 GiB RAM, disk 69% terpakai). Semua klaim di bawah berasal dari perintah
yang dijalankan di host, bukan perkiraan.

## 1. Kebersihan web root

`/var/www/html` menyimpan artefak yang tidak lagi dilayani aplikasi mana pun.
Dihapus 36 berkas:

- `rakazo.apk` + 18 screenshot pengujian `rakazo_*.png`
- 4 screenshot ad-hoc (`create_menu.png`, `deepseek_success.png`,
  `emulator_now.png`, `home_screen.png`)
- 13 cadangan lama `*.bak-*` (`index.html`, `live-ops.js`, `war-room.js`,
  `war-room.css`)

Sisa 82 MB, semuanya masih relevan: berkas web aktif, data snapshot
(`data.json`, `analytics.json`, `quant-backtest.json`, `wallet-info.json`),
`hermes-mobile.apk`, `maxxy.apk`, `ea_files`, `filemanager.php`, `phpmyadmin`.

## 2. Akses publik

| Temuan | Bukti | Tindakan |
|---|---|---|
| `filemanager.php` & `phpmyadmin` **sudah** di balik basic auth | blok `auth_basic "War Room"` di vhost `webdock` berlaku untuk semua `location` | tidak ada perubahan |
| `rakazo.conf` membuka `/rpc/`, `/api/`, `/novnc/` tanpa auth | snippet di-include vhost `webdock`, semua `auth_basic off` | include di-comment; nginx `-t` ok, reload sukses. `/rpc/` kini 401 |
| Port **20128** (next-server 9router) terbuka ke internet | `ufw status` memuat `20128/tcp ALLOW Anywhere` | aturan dihapus; dari jaringan luar `curl` timeout (`000`), dari `127.0.0.1` tetap 307 |
| Port 5173 (rakazo) | tidak listen | snippet ikut dilepas (lihat baris di atas) |

Port 20128 sengaja tetap dijangkau lewat nginx `/9router/`, bukan langsung ke
port-nya. UFW sekarang hanya membuka 22, 80, 443, 50000:50099, 50443.

## 3. Cron: lima dari enam sudah mati

`crontab -l` sebelum audit memuat enam job farm. Direktori kerjanya sudah tidak
ada, sehingga tiap jadwal hanya menulis log error:

| Job | Direktori | Status |
|---|---|---|
| `n33-farm.sh` (*/3) | `~/0xgetz-repos/n33-bulk-9router` | hilang → di-comment |
| `pool-live/gen.py` (tiap menit) | `~/pool-live` | hilang → di-comment |
| `opensatan-farm.sh` (*/5) | `~/0xgetz-repos/opensatan-bulk-9router` | hilang → di-comment |
| `nanomuse-farm/farm.py` (*/15) | `~/nanomuse-farm` | hilang → di-comment |
| `pool-live/monitor.py` (*/5) | `~/pool-live` | hilang → di-comment |
| `overchat/refarm.py` (*/20) | `~/0xgetz-repos/overchat-bulk-9router` | hilang → di-comment |
| `ops/telegram_bridge.py` (*/15) | `~/warroom` | **hidup** — satu-satunya yang tersisa |

Baris asli di-comment, bukan dihapus. Cadangan penuh: `/tmp/crontab-backup-20261105.txt`.

## 4. Kondisi data `trades` — gap forex/IDX terkonfirmasi

```
venue|mode|count|min       |max
crypto|paper|111 |2026-10-14|2026-11-05
```

Hanya crypto yang masuk tabel `trades`. Penyebabnya **bukan** ketiadaan kode
ingest, melainkan ketiadaan sumber:

- `services/api/src/warroom_api/lokal.py` membaca forex dari
  `/var/lib/warroom/deals.csv` (EA MetaTrader yang menulis).
- Berkas itu **tidak ada** di host, dan `fills.csv` hanya berisi 149 byte
  sisa 24 Okt.

Artinya jurnal forex kosong karena EA tidak pernah mengirim deal, bukan karena
API membuangnya. Langkah berikutnya adalah memastikan EA terpasang & melapor,
bukan menulis ulang jalur baca.

## 5. Temuan lain (belum ditindak)

1. `agent/poly-agent.mjs` berjalan sebagai **root** sejak 16 Okt
   (`/usr/bin/node agent/poly-agent.mjs`). Ini proses web yang punya hak penuh
   atas host; sebaiknya dipindah ke systemd dengan `User=admin`.
2. `/home/admin/.hermes` memakan **4,9 GiB** (toolchain + repositori agen) —
   kandidat pembersihan berikutnya, tapi bukan bagian War Room.
3. `warroom-panel-sim.service` terlihat `activating start` saat pertama
   diambil, tetapi itu transien: unit ini oneshot yang dipicu timer 30 detik
   dan keluar dengan status 0 (`telemetri tidak tersedia; lewati`). Bukan
   gangguan.
4. Kredensial VPS/MySQL/FTP/SSH yang beredar di percakapan **wajib dirotasi**
   lewat panel Webdock. Ini tidak bisa dikerjakan dari dalam host.
