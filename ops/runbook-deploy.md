# Runbook Deploy — War Room Web & API

Dibuat: **2026-10-09** (R0, revisi total) · Kursi: SRE · Alasan: insiden 2026-10-08/09.

---

## Kenapa runbook ini ada (insiden yang melatarbelakangi)

**8 Okt 20:58** — proses `warroom-web` (node) mulai berjalan.
**8 Okt 21:00** — `npm run build` selesai dan **menimpa** folder `build/` dengan chunk baru.
Proses lama **tidak di-restart**, jadi ia memegang `manifest.js` lama di memori sementara
chunk di disk sudah diganti:

```
ERR_MODULE_NOT_FOUND: Cannot find module
'.../build/server/chunks/nodes/0.js-DjEETD9C.js'
```

**Akibatnya: SEMUA halaman web → HTTP 500** (root, /masuk, /crypto, dst) sampai ketahuan
kebetulan keesokan paginya. Pemulihan: `systemctl restart warroom-web` (~2 detik).

**Pelajaran:** perubahan kode **wajib** diikuti restart + verifikasi. Mengandalkan ingatan
tidak cukup. Itulah kenapa ada mekanisme `build_id` di bawah.

---

## Aturan utama (jangan dilanggar)

> **Deploy = build + restart + VERIFIKASI, sebagai satu unit.**
> Bukan tiga langkah terpisah yang bisa terlupa.

> **`build_id` proses HARUS sama dengan `build_id` disk.**
> Kalau beda → proses lama masih jalan → restart belum terjadi.

---

## Cara deploy web (dipakai sehari-hari)

```bash
cd /home/admin/warroom
bash ops/set-build-id.sh          # tulis build_id ke /etc/warroom/build.env
bash ops/deploy-web.sh            # build + restart web + health gate + verifikasi build_id
```

Skrip `deploy-web.sh` melakukan, berurutan:
1. Backup `build/` lama (untuk rollback).
2. `npm run build` — **sekaligus menulis `build/build-id.txt` + `build-id.js`**.
3. `systemctl restart warroom-web`.
4. **Health gate**: tunggu `/` = 200 **dan** satu aset `/_app/*.js` benar-benar tersedia
   (membuktikan proses menyajikan build baru, bukan sekadar 200).
5. **Verifikasi build↔proses**: bandingkan `build_id` disk dengan `build_id` API
   (`/api/v1/build`). Bila beda → **peringatan** (API perlu restart).
6. Bila health gate gagal → **rollback otomatis** ke build sebelumnya + restart.

---

## Cara deploy / restart API

Setelah mengubah kode API, **selalu** sinkronkan `build_id` lalu restart:

### Migrasi DB (otomatis sejak 15 Okt 2026)

Unit `warroom-api` dan `warroom-worker` menjalankan
`ExecStartPre=ops/check-db-head.py --upgrade` sebelum proses naik: skema DB
dipastikan di head alembic, dan kalau tertinggal migrasinya diterapkan dulu.
Bila unit gagal start, periksa `journalctl -u warroom-api -n 50` — kegagalan
migrasi muncul di situ dan **tidak boleh** diatasi dengan menghapus ExecStartPre.
Cek manual:

```bash
sudo bash -c 'set -a; source /etc/warroom/db.env; set +a; \
  /home/admin/warroom/.venv/bin/python /home/admin/warroom/ops/check-db-head.py'
```

```bash
cd /home/admin/warroom
bash ops/set-build-id.sh                 # samakan build_id
sudo systemctl restart warroom-api
curl -sS http://127.0.0.1:8800/api/v1/build   # verifikasi
```

**Kenapa `set-build-id.sh` penting:** kalau API di-restart tanpa memperbarui
`WARROOM_BUILD_ID`, endpoint `/api/v1/build` akan melaporkan build lama → verifikasi
deploy web akan memberi **peringatan palsu**.

---

## Verifikasi manual (kapan saja)

```bash
# 1. build_id yang dilaporkan proses API (publik, tanpa auth)
curl -sS https://0xgunsl1ng3r.xyz/api/v1/build

# 2. build_id hasil build terakhir di disk
cat /home/admin/warroom/apps/web/build/build-id.txt

# 3. keduanya harus SAMA. Kalau beda:
#    - API? -> sudo systemctl restart warroom-api
#    - Web? -> bash ops/deploy-web.sh

# 4. semua halaman harus 200
for p in / /masuk /crypto /idx /forex /polymarket /gmgn /sistem /riset; do
  printf "%-14s %s\n" "$p" "$(curl -sS -o /dev/null -w '%{http_code}' https://0xgunsl1ng3r.xyz$p)"
done
```

---

## Kalau web 500 lagi (langkah pemulihan cepat)

```bash
# 1. Konfirmasi gejalanya & cari akar di log
sudo journalctl -u warroom-web -n 50 --no-pager | grep -iE 'error|500|MODULE_NOT_FOUND'

# 2. Kasus paling umum: build baru, proses lama -> restart saja
sudo systemctl restart warroom-web
sleep 3
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3100/

# 3. Kalau masih 500, deploy ulang (ada rollback otomatis)
bash ops/deploy-web.sh
```

**Diagnosis cepat:**
- `ERR_MODULE_NOT_FOUND ... chunks/nodes/*.js` → **build≠proses** → restart (kasus insiden).
- `build_id` disk ≠ `build_id` API → salah satu proses belum di-restart.

---

## Yang TIDAK boleh dilakukan

- ❌ **Jangan** `npm run build` tanpa restart web setelahnya.
- ❌ **Jangan** mengubah `build/` manual.
- ❌ **Jangan** mengubah ambang gate / rumus BE lewat jalur deploy ini.
- ❌ **Jangan** melewati verifikasi hanya karena "biasanya aman".

---

## Endpoint terkait

| Endpoint | Auth | Isi |
|---|---|---|
| `GET /api/v1/build` | **tidak** | `build_id`, `domain_version`, `time` |
| `GET /api/v1/health` | sesi | status, db, `build_id`, user |
| `GET /api/v1/ready` | sesi | readiness checks |

## Kesiapan uang nyata (15 Okt 2026)

Cek status kedua pasar kapan pun (baca-saja):

    .venv/bin/python ops/persiapan-live.py            # kedua pasar
    sudo -n .venv/bin/python ops/persiapan-live.py    # penuh (termasuk /etc)

Status 15 Okt: Polymarket verdict EDGE (n=4133, EV +2,07%/stake, CI95 di atas BE)
tapi gerbang DISARMED; crypto gerbang pun belum ada (file izin + kredensial MEXC).
Langkah owner, berurutan:

1. Polymarket: buat `/etc/poly-pilot/activation-approved` (tangan owner), top-up USDC,
   jalankan SATU order uji kecil, cek `poly.money`/state setelahnya.
2. Crypto: pasang `MEXC_API_KEY`/`MEXC_API_SECRET` di `/etc/warroom/crypto.env` (600),
   buat `/etc/warroom/crypto-live-approved`, lalu satu order uji ≤ $2 via
   `kirim_ke_live` — baca output `ops/persiapan-live.py` sampai tiap blokir hilang.
3. Sejarah hidup: 29 Sep 2026 live Polymarket rugi −13,12 USDC (1W/10L) sebelum disarm —
   baca `snipe-live-v1-state.json` sebelum menghidupkan ulang.
