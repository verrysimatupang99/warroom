# Audit Kesiapan Backup War Room untuk Offsite
### + Rancangan Konkret yang Siap Dieksekusi Owner

| | |
|---|---|
| **Tanggal audit** | 3 November 2026, 00:03 UTC (07:03 WIB) |
| **Host** | `polywarroom` (Webdock VPS, `100.69.157.63`) |
| **Metode** | Audit baca-saja (read-only). **Tidak ada sistem yang diubah.** |
| **Sifat** | Audit + rancangan. **Belum ada yang dipasang/dijalankan.** |

---

## 0. Ringkasan untuk Owner (baca ini dulu)

**Kesimpulan satu baris:** backup lokal War Room **sehat dan terbukti bisa di-restore**, tetapi **belum ada satu pun salinan yang keluar dari host ini**. Jika VPS Webdock hilang (hangus, ransomware, akun Webdock terkunci), War Room **tidak bisa dipulihkan** — bukan karena backupnya rusak, tapi karena backupnya berada di mesin yang ikut hilang.

**Skor kesiapan offsite: 1,5 / 5 — BELUM SIAP.**

| Aspek | Status | Bukti |
|---|---|---|
| Backup Postgres harian jalan | ✅ **Sehat** | 7 dump, 27 Okt–2 Nov, 98 MB/dump |
| Integritas dump terakhir | ✅ **Valid** | sha256 `OK`, TOC terbaca, 22 tabel |
| Backup state (ledger/posisi) | ✅ **Sehat** | 5 arsip 6-jaman, terbaru 2 Nov 22:24 |
| Drill restore terbukti | ✅ **Ada bukti nyata** | 96.326 `facts`, 669 `alerts`, 34 `jobs` dipulihkan |
| Monitoring umur backup | ✅ **Aktif** | `slo-check` tiap 60 dtk: `backup_h=23.4 drill_d=1.75` |
| **Salinan offsite (luar host)** | ❌ **TIDAK ADA** | Tidak ada rclone/restic/borg/aws/s3cmd; unit "ke Tencent" menunjuk skrip yang **sudah tidak ada** |
| **Restore tanpa host asli** | ❌ **Tidak mungkin** | Rahasia (`.env`) hanya ada di `/etc/warroom` host ini, tanpa salinan terenkripsi mana pun |

**Tiga temuan yang paling perlu keputusan owner:**

1. **Offsite = nol.** Unit `war-room-backup.timer` ("to Tencent archive") **disabled**, dan skrip yang dipanggilnya `/usr/local/sbin/war-room-backup-to-tencent` **tidak ada di host** (dikonfirmasi `cat`: *No such file or directory*). Jadi offsite **tidak pernah benar-benar berjalan**, bukan "sedang bermasalah".
2. **`.sha256` tidak bisa dipakai memverifikasi salinan offsite.** Checksum menyimpan **path absolut**. Sudah saya buktikan: salinan yang saya rusak (`093aa757…`) tetap dilaporkan **`OK`**, karena `sha256sum -c` memeriksa file **asli**, bukan salinannya. Verifikasi offsite yang dibangun di atas format ini akan **hijau palsu**.
3. **Rahasia tidak punya salinan apa pun.** `/etc/warroom/*.env` (db, llm, crypto, okx, idx, notifier, token service) tidak terlacak git, tidak ada arsip terenkripsi, tidak ada password manager. **Tanpa ini, dump terbaik pun tidak bisa dihidupkan kembali.**

**Kabar baiknya:** semua bahan sudah ada. Azure CLI **sudah login** (`Azure for Students`, state `Enabled`), git remote **sudah bisa push**, dan kuota gratis 125 GB cukup untuk retensi 90 hari (hanya terpakai ~18%). Rancangan di §5 bisa dijalankan **hari ini** dalam ~2 jam.

---

## 1. Ruang lingkup & batasan audit

**Yang diaudit:** kesiapan *backup* War Room untuk skenario **offsite** (host utama hilang seluruhnya) — bukan hanya "file backup ada".

**Yang TIDAK saya lakukan** (sesuai instruksi "jangan mengubah sistem apa pun"):
- Tidak membuat/mengubah/menghapus file backup.
- Tidak meng-enable/disable/start/stop unit systemd mana pun.
- Tidak membuat storage account, container, atau kredensial Azure.
- Tidak melakukan `git push`, commit, atau perubahan repo.
- Tidak membaca **isi** rahasia (hanya nama file, permission, dan pemilik).

Semua perintah bersifat pembacaan (`ls`, `cat` konfigurasi unit, `sha256sum -c`, `pg_restore --list`, `systemctl show/list-timers`, `az ... list/show`). Satu-satunya penulisan terjadi di `/tmp` untuk **membuktikan** cacat checksum, lalu langsung dihapus.

---

## 2. Kondisi aktual (temuan berbukti)

### 2.1 Backup Postgres — sehat

```
/home/admin/backups/postgres/   (616 MB total, mode 600, owner admin)
warroom-20261027-004000.dump   79M
warroom-20261028-004000.dump   82M
warroom-20261029-004000.dump   85M
warroom-20261030-004000.dump   88M
warroom-20261031-004000.dump   92M
warroom-20261101-004000.dump   95M
warroom-20261102-004000.dump   98M   ← terbaru, 23,4 jam
```
- Timer `warroom-backup-postgres.timer`: harian **00:40 UTC**, `Persistent=true`, jadwal berikutnya 3 Nov 00:40 UTC.
- Dump terbaru: `sha256sum -c` → **OK**; `pg_restore --list` → **OK**; **22 tabel**.
- Rotasi `KEEP=14` **terverifikasi benar** (uji batas 15 file → hapus tepat 1, file tertua).
- Skrip sudah menangani dua kegagalan historis: `+psycopg` pada URL (guest 17–18 Okt) dan dump 0-byte (tulis `.part` lalu `mv`).

### 2.2 Backup state — sehat, tapi unit systemd-nya sudah basi

- Arsip `state-*.tar.gz` (15 MB, tiap 6 jam) di `/home/admin/live-trading/backups/`, terbaru **2 Nov 22:24**.
- **Produsennya bukan** `live-trading-backup.timer` (unit itu **disabled**), melainkan **job `backup` di worker**:
  `{"job":"backup","status":"ok","detail":"kode=0 arsip: 15M -> .../state-20261102-2224.tar.gz"}`
- `live-trading-backup.service` masih menunjuk `/home/admin/live-trading/scripts/ops/backup-state.sh` yang **tidak ada** (skrip asli ada di `warroom/packages/live-trading/scripts/ops/`). Unit mati = aman hari ini, **tapi** `docs/baseline-p0.md` dan `ops/runbook-restore.md` masih menyebut timer itu sebagai mekanisme aktif → **dokumen menyesatkan operator**.
- `ops/runbook-restore.md` menyebut "rotasi 14 arsip", **faktanya hanya 5 arsip** yang ada. Jangan mengarang: jumlah sebenarnya 5, dan rotasinya tidak terverifikasi.

### 2.3 Bukti drill restore — kuat

`/var/lib/warroom/restore-drill/last.json` (1 Nov 2026 05:56):
```json
{ "ok": true, "dump": ".../warroom-20261101-004000.dump",
  "facts": 96326, "alerts": 669, "jobs": 34,
  "durasi_detik": 31, "catatan": "DB uji dihapus setelah verifikasi; produksi tidak disentuh" }
```
Drill bulanan (`*-*-01 03:30 UTC`) berikutnya **1 Des 2026**. Batas SLO owner: drill ≤ 35 hari — saat ini 1,75 hari. **Bagus.** Catatan: drill memverifikasi `facts`/`alerts`/`jobs` saja, bukan seluruh 22 tabel.

### 2.4 Monitoring — aktif dan jujur

`slo-check` tiap 60 detik, ambang owner 1 Nov 2026: `disk 80/90`, `backup_max_h=26`, `drill_max_d=35`.
```
disk=83.4% backup_h=23.31 drill_d=1.75 api=True alert=0 pulih=0
```
Artinya: umur backup **sudah diukur** dan akan berbunyi bila > 26 jam. **Yang tidak diukur: apakah salinan offsite ada dan bisa dipulihkan** — karena memang tidak ada.

### 2.5 Celah utama: offsite

| Yang dicari | Hasil |
|---|---|
| `rclone`, `restic`, `borg`, `aws`, `s3cmd`, `gsutil`, `mc` | **Tidak ada satu pun** |
| `~/.config/rclone/rclone.conf` | Tidak ada |
| Remote/copy di skrip ops | **Tidak ada** (hanya `rsync` lokal antar folder) |
| `war-room-backup.timer` (Tencent) | **disabled**, `LastTriggerUSec` kosong, skrip target **tidak ada** |
| Arsip terenkripsi rahasia (`.age`/`.gpg`) | **Tidak ada** |
| Password manager (`pass`/`bw`) | **Tidak ada** |
| Salinan repo di GitHub | ⚠️ Ada, tapi **1 commit tertinggal** (`e17c0b5`, memuat `ingest_mt5.py` + `WarRoom_HistoryExporter.mq5`) |

Komentar di `ops/ops-scripts/infra-watchdog.py:43-46` mengonfirmasi: unit backup Tencent "disabled sejak 17 Sep 2026" dan skripnya "sudah tidak ada di host". **Jadi ini kondisi permanen, bukan insiden sesaat.**

### 2.6 Cacat yang terbukti: checksum menunjuk path absolut

`.sha256` berisi:
```
1ce23342d9250ac2416479be07fd9c65213d2093ef26ef710144c92c8455a6f0  /home/admin/backups/postgres/warroom-20261102-004000.dump
```
Uji kontrol yang saya jalankan: salin dump ke `/tmp`, **rusak 7 byte di offset 1000**, lalu `sha256sum -c`:
```
hash salinan   : 093aa757b9e7da22ae970afa9512974a3730f4443208370f893079825633569a
hash tercatat  : 1ce23342d9250ac2416479be07fd9c65213d2093ef26ef710144c92c8455a6f0
sha256sum -c   : /home/admin/backups/postgres/warroom-20261102-004000.dump: OK   ← SALAH
```
**Dampak:** verifikasi di sisi offsite (yang wajib ada di rancangan mana pun) akan **selalu hijau** walau salinannya rusak — karena ia memeriksa file **asli di host**. Ini harus diperbaiki **sebelum** offsite dipasang, kalau tidak offsite-nya jadi "backup teater".

### 2.7 Sumber daya host

```
/dev/sda1  48G  40G  7.6G  85%  /
```
Sisa **7,6 GB** (85%). Ini **membatasi** desain: staging di host harus hemat (<= ~110 MB per siklus, bukan menyalin 616 MB), dan retensi lokal tidak boleh ditambah. Owner punya target disk < 70% / > 18 GB kosong (`DIRECTIVE_FROM_OWNER.md`) — **belum tercapai**, dan offsite harus **tidak memperburuk**.

### 2.8 Sisa-sisa yang perlu dibereskan

- `warroom-20261017-004000.dump.invalid` & `...20261018...invalid` (0 byte, dari kegagalan 17–18 Okt) — tidak pernah dibersihkan, tidak cocok glob rotasi sehingga **tidak akan pernah** terhapus otomatis.

---

## 3. Matriks risiko

| # | Risiko | Kemungkinan | Dampak | Status sekarang |
|---|---|---|---|---|
| R1 | VPS Webdock hilang / akun terkunci | Rendah | **Bencana: total loss** | ❌ Tidak termitigasi |
| R2 | Ransomware / host ter-rootkit | Rendah–Sedang | **Total loss** (backup lokal ikut terenkripsi) | ❌ Tidak termitigasi |
| R3 | Disk penuh (85%, naik) → backup gagal diam-diam | **Sedang–Tinggi** | Kehilangan jendela pemulihan | ⚠️ Terpantau SLO, tapi tren buruk |
| R4 | Offsite "ada" tapi tidak pernah diverifikasi | **Tinggi (pasti terjadi** tanpa §5.4**)** | Pemulihan gagal di hari-H | ❌ Cacat checksum §2.6 menjaminnya |
| R5 | Rahasia hilang → dump tak bisa dihidupkan | Tinggi (jika host hilang) | Pemulihan mustahil | ❌ Tanpa salinan |
| R6 | Operator salah paham dokumen (timer "aktif") | Sedang | Drill/restore salah langkah | ⚠️ `runbook-restore.md` & `baseline-p0.md` basi |
| R7 | Kode 1 commit tertinggal di GitHub | **Pasti** (sudah terjadi) | Kehilangan `ingest_mt5.py`/EA exporter | ⚠️ Perlu push |

---

## 4. Sasaran yang diusulkan (minta persetujuan owner)

Angka ini diturunkan dari bukti: **tulis DB ~4.718 fakta/24 jam**, dump 98 MB naik **3,2 MB/hari**, state 15 MB/6 jam.

| Parameter | Usulan | Alasan |
|---|---|---|
| **RPO** (data boleh hilang) | **≤ 24 jam** | Dump harian sudah memberi ini; state 6-jaman memperbaiki berkas non-DB |
| **RTO** (waktu pulih) | **≤ 4 jam** | Drill tercatat **31 detik** untuk restore+verifikasi; 4 jam memberi ruang provisi VM + pasang Postgres |
| **Retensi offsite** | Postgres **90 hari**, state **30 hari**, repo **mingguan 12** | Muat di kuota gratis (§5.2) |
| **Frekuensi uji** | Metadata **harian**, restore penuh **bulanan** (bersama drill) | Menangkap kerusakan cepat, tanpa membebani host 85% |

---

## 5. Rancangan konkret

Prinsip desain: **push (bukan pull)**, **append-only + immutable (WORM)**, **enkripsi di sisi klien**, **verifikasi di sisi offsite**, dan **hemat disk host**.

```
  ┌─ Webdock VPS (polywarroom) ─────────────┐        ┌─ Azure Blob (offsite) ──────────┐
  │                                          │        │                                  │
  │  worker job `backup`  ──► state-*.tar.gz │        │  container: warroom-offsite      │
  │  warroom-backup-postgres ──► *.dump      │        │   ├─ postgres/2026/11/*.dump     │
  │           │                              │  TLS   │   ├─ state/2026/11/*.tar.gz      │
  │           ▼                              │ ─────► │   ├─ configs/*.tar.gz.enc        │
  │  rz-offsite.sh (baru)                    │  SAS   │   ├─ repo/warroom-*.bundle       │
  │   enkripsi → unggah → verifikasi         │        │   └─ manifests/YYYY-MM-DD.json   │
  │                                          │        │                                  │
  │  TIDAK menyimpan state lokal jangka      │        │  Immutability policy: 90 hari    │
  │  panjang (staging dihapus tiap selesai)  │        │  (tidak bisa dihapus/ditimpa)    │
  └──────────────────────────────────────────┘        └──────────────────────────────────┘
                                                              ▲
                                                     verifikasi independen (§5.4)
                                                     dari mesin/CI lain
```

### 5.1 Langkah 0 — perbaiki cacat checksum (WAJIB, mendahului semua)

Ubah `ops/backup-postgres.sh:45` agar checksum memakai **path relatif**:
```bash
# SEBELUM (baris 45) — menulis path absolut, tidak bisa diverifikasi dari salinan
sha256sum "$pas" > "$pas.sha256"
# SESUDAH — path relatif, bisa diverifikasi di mana pun file itu berada
( cd "$OUT_DIR" && sha256sum "$(basename "$pas")" > "$(basename "$pas").sha256" )
```
Dampak: hanya isi `.sha256` untuk dump **berikutnya**; dump lama tetap jalan (checksum mereka diverifikasi lokal, bukan offsite). Tambahan: hapus dua file `.invalid` 0-byte, dan tambahkan pola `warroom-*.dump.invalid` ke pembersihan rotasi.

### 5.2 Langkah 1 — siapkan tujuan offsite (Azure, sudah login)

Azure CLI **terbukti** login: `Azure for Students`, subscription `26bb0358-…`, state `Enabled`. Provider `Microsoft.Storage` **Registered**. Belum ada storage account — jadi kita buat yang khusus, **tanpa menyentuh VM `mt5-trader-vm`** dan **tanpa mengubah NSG** (patuh pada `COORDINATION_NOTE_WARROOM_HERMES.md`).

```bash
RG=warroom-dr-rg; LOC=southeastasia; SA=warroomoffsite$RANDOM
az group create -n "$RG" -l "$LOC"
# StorageV2 + LRS (cukup: sumber & tujuan beda benua, LRS melindungi dari kehilangan host)
az storage account create -n "$SA" -g "$RG" -l "$LOC" \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 \
  --allow-blob-public-access false --https-only true
az storage container create -n warroom-offsite --account-name "$SA" \
  --auth-mode login
# Kunci append-only: tidak bisa dihapus/ditimpa selama 90 hari
az storage container immutability-policy create \
  --account-name "$SA" -c warroom-offsite -g "$RG" \
  --period 90 --allow-protected-append-writes true
```
Sasaran container: `postgres/`, `state/`, `configs/`, `repo/`, `manifests/`.

**Anggaran (dihitung dari ukuran nyata, bukan karangan):**
| Retensi | Terpakai | % dari 125 GB gratis |
|---|---|---|
| 30 hari | 4,7 GB | 3,7% |
| **90 hari** | **22,3 GB** | **17,9%** |
| 90 hari + semua 4 arsip state/hari | 26,3 GB | 21,0% |

Aman dari kredit $100 / 12 bulan. Tanpa perlu kartu kredit (Azure for Students).

### 5.3 Langkah 2 — skrip unggah (`ops/offsite-upload.sh`, baru)

Sifat wajib: **idempoten, hemat disk, fail-closed, dan memverifikasi hasil unggahan.**

```bash
#!/usr/bin/env bash
# Unggah artefak War Room terbaru ke Azure Blob (offsite). Idempoten + terverifikasi.
# TIDAK menyimpan staging di host (disk 85%). Rahasia dienkripsi SEBELUM meninggalkan host.
set -euo pipefail

STAGE="$(mktemp -d)"; trap 'rm -rf "$STAGE"' EXIT          # staging dihapus selalu
SA="${WARROOM_OFFSITE_SA:?}"; C=warroom-offsite
HARI="$(date -u +%Y/%m/%d)"
fail() { echo "OFFSITE GAGAL: $*" >&2; exit 1; }

# 1) Postgres: dump terbaru saja per hari (hemat kuota)
DUMP="$(ls -1t /home/admin/backups/postgres/warroom-*.dump | head -1)"
[[ -s "$DUMP" ]] || fail "dump terbaru kosong/hilang"
( cd "$(dirname "$DUMP")" && sha256sum -c "$(basename "$DUMP").sha256" ) \
  || fail "checksum dump lokal tidak cocok"
cp "$DUMP" "$STAGE/"
az storage blob upload --account-name "$SA" --auth-mode login \
  --container-name "$C" --name "postgres/$HARI/$(basename "$DUMP")" \
  --file "$STAGE/$(basename "$DUMP")" --overwrite false   # immutable: tidak bisa timpa

# 2) State terbaru
ST="$(ls -1t /home/admin/live-trading/backups/state-*.tar.gz | head -1)"
az storage blob upload --account-name "$SA" --auth-mode login \
  --container-name "$C" --name "state/$HARI/$(basename "$ST")" --file "$ST" --overwrite false

# 3) Config/rahasia — ENKRIPSI DULU, baru keluar host
tar -C /etc -czf "$STAGE/warroom-etc.tar.gz" warroom
age -R /home/admin/.config/warroom/offsite.pub -o "$STAGE/warroom-etc.tar.gz.age" \
    "$STAGE/warroom-etc.tar.gz"
shred -u "$STAGE/warroom-etc.tar.gz"                       # plaintext tidak boleh tersisa
az storage blob upload --account-name "$SA" --auth-mode login \
  --container-name "$C" --name "configs/$HARI/warroom-etc.tar.gz.age" \
  --file "$STAGE/warroom-etc.tar.gz.age" --overwrite false

# 4) Repo mingguan (Senin) — git bundle, bukan tarball .git
if [[ "$(date -u +%u)" == "1" ]]; then
  git -C /home/admin/warroom bundle create "$STAGE/warroom-$(date -u +%Y%m%d).bundle" --all
  az storage blob upload --account-name "$SA" --auth-mode login --container-name "$C" \
    --name "repo/$(date -u +%Y%m%d).bundle" --file "$STAGE/"*.bundle --overwrite false
fi

# 5) Manifest: bukti apa yang diunggah hari ini
python3 - "$STAGE" "$DUMP" "$ST" <<'PY'
import hashlib, json, os, sys
from datetime import UTC, datetime
stage, dump, st = sys.argv[1:4]
def h(p):
    d = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): d.update(b)
    return d.hexdigest()
json.dump({"selesai_at": datetime.now(UTC).isoformat(),
           "dump": {"nama": os.path.basename(dump), "sha256": h(dump)},
           "state": {"nama": os.path.basename(st), "sha256": h(st)}},
          open(os.path.join(stage, "manifest.json"), "w"), indent=2)
PY
az storage blob upload --account-name "$SA" --auth-mode login --container-name "$C" \
  --name "manifests/$(date -u +%F).json" --file "$STAGE/manifest.json" --overwrite true
echo "OFFSITE OK: $(date -u +%F)"
```

**Kenapa begini:**
- `mktemp -d` + `trap rm -rf` → **nol** jejak di disk 85%.
- `--overwrite false` + immutability 90 hari → ransomware tidak bisa menimpa/menghapus.
- Enkripsi `age` **sebelum** upload → rahasia tidak pernah ada di cloud sebagai plaintext.
- `set -euo pipefail` + `fail()` → **fail-closed**: gagal = alarm, bukan diam.
- Manifest harian → bukti mandiri bahwa hari itu benar-benar terkirim.

### 5.4 Langkah 3 — verifikasi offsite (bagian yang paling sering dilupakan)

Ini yang membedakan "backup" dari "backup teater". Jalankan dari **mesin lain / CI**, bukan dari host produksi:

```bash
# 1) Unduh manifest hari ini + dump, HITUNG ULANG hash dari salinan
./ops/offsite-verify.sh 2026-11-03
```
Aturan skrip verifikasi (wajib):
- `sha256` dihitung dari **byte salinan yang baru diunduh**, bukan dari path lokal (menghindari jebakan §2.6).
- Bandingkan dengan `manifest.json` **hari itu**.
- `pg_restore --list` pada salinan unduhan harus sukses.
- **Bulanan:** restore salinan offsite ke DB uji, lalu bandingkan jumlah baris `facts` (baseline terakhir: **96.326** saat 1 Nov; saat ini DB hidup 103.760).

Bila salah satu gagal → **alarm ke Telegram** via `warroom-alert-push` yang sudah ada.

### 5.5 Langkah 4 — jadwalkan (systemd, *jalankan setelah owner setuju*)

`ops/warroom-offsite-upload.timer` — **01:15 UTC** (35 menit setelah backup Postgres 00:40, memberi ruang selesai):
```ini
[Timer]
OnCalendar=*-*-* 01:15:00 UTC
Persistent=true
RandomizedDelaySec=300
```
Service: `Type=oneshot`, `User=admin`, `EnvironmentFile=/etc/warroom/offsite.env` (600 root, isi `WARROOM_OFFSITE_SA` + kunci `age`), `TimeoutStartSec=1800`.

Tambahkan pemeriksaan ke `slo-check` (payload baru): `offsite_max_h=26`. Ini **menutup** celah bahwa SLO sekarang hanya mengukur backup **lokal** — bukan yang offsite.

### 5.6 Langkah 5 — tutup celah rahasia & dokumen

1. **Rahasia:** buat kunci `age`, simpan **private key HANYA di luar host** (password manager owner / kertas di safe). Berkas `/etc/warroom/*.env` masuk arsip terenkripsi §5.3. **Tanpa langkah ini, seluruh rancangan tidak berguna** — dump tanpa `db.env`/`llm.env` tidak bisa dihidupkan.
2. **Dokumen (cegah R6):**
   - `ops/runbook-restore.md`: ganti klaim "timer tiap 6 jam / rotasi 14" → **faktanya job `backup` di worker, 5 arsip**. Tambahkan bahwa `live-trading-backup.timer` **disabled** dan skrip lamanya **tidak ada**.
   - `docs/baseline-p0.md:74-76`: koreksi baris `live-trading-backup.timer` & `war-room-backup.timer` (keduanya **disabled**).
3. **Repo (cegah R7):** `git -C /home/admin/warroom push origin main` → membawa `e17c0b5` (`ingest_mt5.py`, `WarRoom_HistoryExporter.mq5`) ke GitHub. Kredensial git **terbukti bekerja** (`git ls-remote` exit 0).
4. **Disk (R3):** hapus 2 file `.invalid`, dan **jangan** menambah retensi lokal. Catatan: target owner < 70% **belum tercapai** (sekarang 85%) — offsite dirancang agar **tidak menambah** beban disk.

---

## 6. Rencana eksekusi

| Fase | Isi | Waktu | Risiko | Butuh owner? |
|---|---|---|---|---|
| **P0** | §5.1 fix checksum + hapus `.invalid` + §5.6 push repo & koreksi dokumen | ~30 mnt | Sangat rendah (tanpa downtime) | Push repo: **ya** |
| **P1** | §5.2 storage account + immutability + §5.3 skrip | ~60 mnt | Rendah (resource baru, host tak tersentuh) | **Ya** (biaya/resource) |
| **P2** | §5.5 timer + probe `slo-check` | ~30 mnt | Rendah | **Ya** (unit baru) |
| **P3** | §5.4 verifikasi dari mesin kedua + latihan restore penuh **dari offsite** | ~60 mnt | Rendah (DB uji) | **Ya** (jadwal latihan) |
| **P4** | Dokumentasikan bukti + perbarui runbook | ~20 mnt | Nol | Tidak |

**Gate "SIAP OFFSITE"** — baru boleh disebut siap bila **keenam** ini benar:
1. Minimal 1 dump + 1 state + 1 configs terenkripsi ada **di luar host**.
2. `sha256` diverifikasi **dari salinan unduhan**, bukan dari host asli.
3. `pg_restore --list` sukses pada salinan unduhan.
4. **Restore penuh dari offsite** ke DB uji berhasil, jumlah baris `facts` wajar.
5. Rahasia bisa didekripsi kunci di luar host → service bisa start.
6. `slo-check` melaporkan `offsite_h` dan alarm menyala bila > 26 jam.

---

## 7. Yang harus diputuskan owner

1. **Setuju RPO ≤ 24 jam / RTO ≤ 4 jam / retensi 90 hari?** (§4)
2. **Setuju pakai Azure Blob** (sudah login, kuota gratis, ~18% terpakai)? Alternatif: **Backblaze B2** atau **Cloudflare R2** — perlu kredensial baru, jadi lebih lama.
3. **Siapa pemegang private key `age`** dan di mana disimpan? **(tanpa ini P1 sia-sia)**
4. **Boleh `git push`** commit `e17c0b5` ke GitHub?
5. **Boleh membuat resource Azure baru** (storage account + RG), dengan catatan **tidak menyentuh `mt5-trader-vm`/NSG**?
6. **Jadwal latihan restore dari offsite** — usul: tanggal 1 tiap bulan, menyatu dengan `warroom-restore-drill` yang sudah ada.

---

## 8. Lampiran — perintah reproduksi (semua baca-saja)

```bash
# Backup & integritas
systemctl list-timers 'warroom-*' --all
f=$(ls -1t /home/admin/backups/postgres/warroom-*.dump | head -1)
sha256sum -c "$f.sha256" && pg_restore --list "$f" | grep -c 'TABLE DATA'
cat /var/lib/warroom/restore-drill/last.json

# Bukti offsite tidak ada
command -v rclone restic borg aws s3cmd || echo "tidak ada alat offsite"
systemctl show war-room-backup.timer -p UnitFileState -p LastTriggerUSec
ls /usr/local/sbin/war-room-backup-to-tencent   # No such file or directory

# Cacat checksum (uji kontrol)
cd /tmp && cp -a /home/admin/backups/postgres/warroom-*.dump* . \
  && printf 'CORRUPT' | dd of=warroom-20261102-004000.dump bs=1 seek=1000 conv=notrunc \
  && sha256sum -c warroom-20261102-004000.dump.sha256   # tetap "OK" → cacat terbukti
```

---

*Audit ini tidak mengubah sistem apa pun. Seluruh angka diambil dari keluaran perintah nyata pada 3 Nov 2026 00:03 UTC; tidak ada angka yang dikarang. Bagian yang tidak dapat diverifikasi ditandai eksplisit (mis. jumlah arsip state = 5, bukan 14 seperti klaim runbook).*
