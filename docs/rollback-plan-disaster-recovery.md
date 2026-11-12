# Rencana Rollback & Pemulihan Bencana (Disaster Recovery Plan) — War Room

Dokumen ini menetapkan prosedur operasional standar (SOP) untuk pemulihan bencana (*Disaster Recovery*) dan pengembalian versi (*Rollback*) pada platform **War Room**, guna memastikan kelangsungan operasional sistem dengan target metrik yang ketat.

---

## 1. Target Metrik & Sasaran Pemulihan (SLO)

Platform War Room menetapkan batas ambang toleransi kegagalan sebagai berikut:

- **RTO (Recovery Time Objective)**: **< 15 Menit**  
  Durasi maksimal yang diperbolehkan sejak insiden dinyatakan kritis hingga sistem kembali beroperasi normal melayani pengguna dan menerima telemetri.
- **RPO (Recovery Point Objective)**: **< 24 Jam**  
  Batas maksimal kehilangan data transaksi atau metrik. Dijamin oleh jadwal dump harian pukul 00:40 UTC serta audit trail persisten pada berkas `deals.csv` dan log telemetri lokal.

---

## 2. Matriks Keputusan Rollback & Kriteria Pemicu

Eksekusi rencana rollback wajib dipicu apabila salah satu kondisi kritis berikut terpenuhi:

1. **Kegagalan Peluncuran Kode (Application Crash)**: Layanan `warroom-api` atau `warroom-web` mengalami *crash-loop* (exit code non-zero) pasca deploy dan tidak dapat pulih dalam waktu 3 menit.
2. **Korupsi Skema Basis Data**: Migrasi Alembic menyebabkan inkonsistensi tabel, data hilang, atau transaksi deal terhenti karena *database deadlocks*.
3. **Anomali Telemetri & Order**: Sistem keliru mengeksekusi deal, kesalahan fatal konversi mata uang sen (`USC` dianggap `USD` penuh), atau hilangnya aliran telemetri secara menyeluruh.

---

## 3. Prosedur Rollback Aplikasi (Git & Layanan)

Target waktu eksekusi: **3 - 5 Menit**.

```
[ IDENTIFIKASI ERROR ] ---> [ STOP TRAFFIC SEMENTARA ] ---> [ GIT ROLLBACK ] ---> [ REBUILD & RESTART ] ---> [ VERIFIKASI ]
```

### Langkah 3.1: Masuk ke Host Produksi Webdock
```bash
ssh admin@polywarroom.vps.webdock.cloud
cd /home/admin/warroom
```

### Langkah 3.2: Identifikasi Commit Stabil Sebelumnya
```bash
# Periksa 5 commit terakhir pada branch main
git log -n 5 --oneline
```
Pilih commit ID yang terverifikasi sehat (misalnya commit `TAG_SEBELUMNYA` atau `HEAD~1`).

### Langkah 3.3: Eksekusi Rollback Kode
Terdapat dua opsi rollback tergantung pada kebijakan rilis git:

**Opsi A (Git Revert — Disukai untuk audit git)**:
```bash
git revert --no-edit HEAD
```

**Opsi B (Git Reset Hard — Bila darurat pemulihan instan)**:
```bash
git reset --hard <STABLE_COMMIT_SHA>
```

### Langkah 3.4: Rebuild Frontend Web
```bash
cd /home/admin/warroom/apps/web
npm ci
npm run build
```

### Langkah 3.5: Restart Layanan Terkait
```bash
sudo systemctl restart warroom-api warroom-worker warroom-web
```

### Langkah 3.6: Verifikasi Status Layanan Pasca Rollback
```bash
curl -f http://127.0.0.1:8800/api/v1/health || echo "API GAGAL"
curl -f http://127.0.0.1:3100/ || echo "WEB GAGAL"
```

---

## 4. Prosedur Pemulihan Basis Data (PostgreSQL Restore)

Target waktu eksekusi: **7 - 10 Menit**.

Prosedur ini dijalankan jika terjadi kerusakan data, tabel terhapus, atau kegagalan migrasi skema yang tidak dapat diselesaikan dengan `alembic downgrade`.

### Langkah 4.1: Hentikan Layanan yang Menulis ke Database
Untuk mencegah *race condition* dan data kotor saat pemulihan berlangsung:
```bash
sudo systemctl stop warroom-worker warroom-api trading-engine
```

### Langkah 4.2: Pilih Berkas Backup & Validasi Checksum SHA-256
Direktori backup berada di `/var/backups/postgresql/` (atau `/home/admin/backups/postgres/`).
```bash
cd /var/backups/postgresql/

# Cari berkas dump terbaru yang valid
BACKUP_FILE=$(ls -1t warroom-*.dump | head -n 1)
echo "Menggunakan berkas backup: $BACKUP_FILE"

# Verifikasi integritas berkas menggunakan checksum relatif
sha256sum -c "${BACKUP_FILE}.sha256"
```
> **PERINGATAN**: Jika status verifikasi checksum bukan `OK`, JANGAN gunakan berkas tersebut! Periksa berkas dump sebelumnya (`head -n 2 | tail -n 1`).

### Langkah 4.3: Periksa Header / Daftar Isi Dump
Pastikan berkas dump bukan berkas kosong (0 byte) dan format kustom dapat dibaca:
```bash
pg_restore --list "$BACKUP_FILE" > /dev/null
echo "Daftar isi dump valid."
```

### Langkah 4.4: Eksekusi Restorasi Database
Ambil connection string dari `/etc/warroom/db.env` (bersihkan driver `+psycopg` untuk kompatibilitas `pg_restore`):
```bash
source /etc/warroom/db.env
PG_URL=$(echo "$WARROOM_DB_URL" | sed -E 's#^(postgresql|postgres)\+[A-Za-z0-9_]+://#\1://#')

# Jalankan restorasi dengan pembersihan tabel yang ada (--clean --if-exists)
pg_restore --clean --if-exists --no-owner --no-privileges -d "$PG_URL" "$BACKUP_FILE"
```

### Langkah 4.5: Validasi Skema Pasca Restorasi
```bash
cd /home/admin/warroom
/home/admin/warroom/.venv/bin/python /home/admin/warroom/ops/check-db-head.py
```

### Langkah 4.6: Nyalakan Kembali Layanan
```bash
sudo systemctl start warroom-api warroom-worker trading-engine
systemctl is-active warroom-api warroom-worker trading-engine
```

---

## 5. Prosedur Pemulihan Telemetri & Runner Instabox

Target waktu eksekusi: **2 - 4 Menit**.

### 5.1. Restart Runner MT5 di Instabox VM (`box-2aacb3`)

Jika telemetri dari Instabox berhenti mengalir:
1. Akses Instabox VM:
   ```bash
   ssh box-2aacb3
   ```
2. Jalankan skrip pemulihan terstandarisasi:
   ```bash
   /data/home/warroom-telemetry-ensure.sh
   ```
   *Skrip ini secara otomatis memverifikasi keberadaan proses Wine MT5, menjalankan ulang jika mati, dan memulihkan URL allowlist WebRequest via xdotool.*
3. Verifikasi pengiriman:
   ```bash
   /data/home/warroom-telemetry-ensure.sh --check
   tail -n 10 /data/home/.../MQL5/Files/warroom_debug.txt
   ```

### 5.2. Fallback Operasional ke Mode Teknis Murni (Pure Technical Mode)

Apabila layanan pemrosesan AI eksternal atau inferensi Laya mengalami down atau latensi ekstrem:
1. Pastikan variabel environment pada `/etc/warroom/llm.env` di Webdock tersetting:
   ```ini
   WARROOM_LAYA_INFERENSI=0
   ```
2. Dalam mode ini, strategi `MultiSessionLayaScalperStrategy` akan menggunakan aturan evaluasi teknis deterministik:
   - Evaluasi filter sesi trading (London / NY / Tokyo).
   - Validasi rasio Risk-Reward minimum (RRR $\ge 1.6$).
   - Validasi toleransi spread dan jarak Stop Loss.
3. Reload konfigurasi:
   ```bash
   sudo systemctl restart warroom-worker warroom-api
   ```
   *Sistem tetap melakukan eksekusi perdagangan dan pencatatan deal tanpa terhambat oleh inferensi AI.*

---

## 6. Prosedur Drill & Latihan Pemulihan Rutin

Untuk memastikan keandalan SOP ini, tim SRE wajib menjalankan simulasi restorasi secara terjadwal:
- **Jadwal Drill**: Setiap awal bulan (minggu pertama hari kerja).
- **Unit Pelaksana**: `warroom-restore-drill.service` / skrip `ops/restore-drill.sh`.
- **Target Drill**: Restorasi dump ke database sementara `warroom_restore_drill` dan verifikasi integritas tabel transaksi `trades`.

---

## 7. Templat Post-Mortem Insiden (Incident Post-Mortem Template)

Setiap insiden dengan tingkat keparahan **P1 / P2** wajib didokumentasikan selambat-lambatnya 24 jam setelah insiden teratasi.

```markdown
# 📋 LAPORAN POST-MORTEM INSIDEN WAR ROOM

## 1. Ringkasan Insiden
- **Nomor Tiket Insiden**: INC-YYYYMMDD-XX
- **Tingkat Keparahan**: P1 (Kritis) / P2 (Tinggi) / P3 (Sedang)
- **Waktu Mulai Insiden**: YYYY-MM-DD HH:MM UTC
- **Waktu Deteksi**: YYYY-MM-DD HH:MM UTC
- **Waktu Pemulihan (Mitigasi)**: YYYY-MM-DD HH:MM UTC
- **Total Durasi Dampak (Downtime)**: XX Menit (Target RTO < 15 Min: [TERPENUHI/TERLAMPAUI])
- **Lead Insiden / On-Call SRE**: Nama / ID Operator

## 2. Dampak terhadap Layanan & Pengguna
- **Layanan Terdampak**: (Contoh: Forex Cockpit SSE, Deal Ingestion, Web UI)
- **Dampak Finansial / Transaksi**: (Contoh: XX transaksi tertunda, nol deal terduplikasi)
- **Jumlah Pengguna Terpengaruh**: XX sesi pengguna aktif

## 3. Garis Waktu Peristiwa (Chronological Timeline)
- **HH:MM UTC** - Anomali pertama terjadi (deskripsi singkat).
- **HH:MM UTC** - Alert PagerDuty / SRE mendeteksi anomali.
- **HH:MM UTC** - Investigasi awal dilakukan (pemeriksaan log journalctl).
- **HH:MM UTC** - Keputusan rollback / failover diambil oleh Lead.
- **HH:MM UTC** - Prosedur rollback dieksekusi (git revert / restore db).
- **HH:MM UTC** - Layanan kembali online dan aliran telemetri terverifikasi.

## 4. Analisis Akar Masalah (Root Cause Analysis — 5 Whys)
1. *Mengapa sistem gagal?*
2. *Mengapa kondisi tersebut terjadi?*
3. *Mengapa proteksi awal tidak menangkapnya?*
4. *Mengapa pengujian pra-rilis melewatkannya?*
5. *Akar Masalah Fundamental*: (Deskripsi akar penyebab teknis atau prosedural)

## 5. Yang Berjalan Baik vs. Yang Perlu Diperbaiki
- **Yang Berjalan Baik**:
  - Respon tim cepat (< 3 menit setelah alert).
  - Skrip backup dan checksum terbukti valid dan memulihkan data tanpa kendala.
- **Yang Perlu Diperbaiki**:
  - Deteksi awal masih memerlukan observasi manual pada SSE stream.

## 6. Tindakan Korektif & Preventif (Action Items)
| No | Tindakan Korektif | Tipe (Preventif/Mitigatif) | Penanggung Jawab | Target Tanggal | Status |
|---|---|---|---|---|---|
| 1 | Tambahkan alert otomatis jika telemetri stale > 30s | Preventif | SRE Lead | YYYY-MM-DD | OPEN |
| 2 | Perbaiki test case boundary pada parser | Korektif | Backend Dev | YYYY-MM-DD | OPEN |
```
