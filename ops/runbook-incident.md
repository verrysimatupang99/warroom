# Runbook — insiden & hentikan semua eksekusi (P6-T2)

Tujuan: menghentikan seluruh pekerjaan otomatis dan semua kemungkinan eksekusi **di bawah 60
detik**, lalu mengembalikannya dengan sadar. Tidak ada langkah di sini yang menyalakan live.

## 0. Kapan dipakai

- Anomali uang/posisi (saldo turun tak terduga, posisi tak dikenal, drift parity > 0).
- Data basi yang membuat keputusan bisa salah (feed mati > 2× TTL).
- Permintaan owner: "stop semuanya".

## 1. Urutan henti (total < 60 detik)

```bash
# 1) semua job otomatis (snapshot, collect, publish-facts, poly-sync, parity, reconcile, learner, backup)
sudo systemctl stop warroom-worker.service

# 2) peran tulis AI (usulan/otomatis) — peran baca tetap jalan
curl -s -X POST localhost:8800/api/v1/ai/kill-switch \
  -H 'Content-Type: application/json' -H "Cookie: wr_session=<sesi owner>" -d '{"aktif": true}'

# 3) verifikasi tidak ada eksekusi yang mungkin berjalan
systemctl is-active poly-pilot.service poly-agent.service
sudo test -e /etc/poly-pilot/activation-approved && echo "GATE TERBUKA" || echo "gate tertutup"
```

Atau jalankan latihannya sekaligus (mengukur durasi + membuktikan tidak ada job baru):

```bash
bash ~/warroom/ops/drill-stop.sh
```

## 2. Yang TIDAK boleh dilakukan saat insiden

- Jangan membuat/menghapus `/etc/poly-pilot/activation-approved` (itu keputusan owner).
- Jangan mengubah ambang gate atau rumus BE untuk "menyelamatkan" angka.
- Jangan menyalakan ulang unit eksekusi "untuk melihat apakah sudah normal".
- Jangan memakai `gate.edit` atau mengubah `operator.json`.

## 3. Diagnosis setelah aman

```bash
cd ~/warroom
uv run python -c "import json;from warroom_core.db import session_scope;from warroom_core.db import Fact" 2>/dev/null || true
curl -s localhost:8800/api/v1/freshness -H "Cookie: wr_session=<sesi>" | head -40   # apa yang basi
curl -s localhost:8800/metrics | grep -E "warroom_facts_basi|warroom_alerts_open"
sudo journalctl -u warroom-worker.service -n 80 --no-pager | grep -E "gagal|status"
```

Pertanyaan yang harus dijawab sebelum memulihkan:
1. Sumber mana yang berhenti, dan sejak kapan (`observed_at` fakta terakhir)?
2. Apakah ada angka uang yang berubah? Kalau ya — apakah sudah diverifikasi ke sumber
   (on-chain/venue)? Kalau belum: tampilkan sebagai **belum terverifikasi**.
3. Apakah keputusan diambil dari data basi? Bila ya, catat sebagai temuan (bukan dihapus).

## 4. Pemulihan

```bash
sudo systemctl start warroom-worker.service          # job kembali
curl -s -X POST localhost:8800/api/v1/ai/kill-switch -d '{"aktif": false}' ...   # AI kembali (opsional)
```

Live **tetap mati** setelah pemulihan. Menyalakannya kembali = keputusan owner, dan gate harus
dibuka owner secara manual (tidak pernah oleh agen).

## 5. Bukti latihan (dijalankan 2026-10-02)

Lihat `docs/p4-p6-progress.md` §P6 dan keluaran `ops/drill-stop.sh`: worker berhenti seketika,
jumlah event `job.ran` **tidak bertambah** selama worker mati, kill switch aktif, gate live
tertutup, dan semua dipulihkan di akhir latihan.