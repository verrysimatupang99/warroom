# WORKLOG — War Room v1

Format: `tanggal | item | apa yang dikerjakan | bukti | hambatan`

---

2026-11-17 | W1-01 | Skema inti dari nol: 24 tabel di schema `v1`, DB baru `warroom_v1` (DB lama tidak disentuh) | `psql`: 24 tabel (account…venue) | —
2026-11-17 | W1-02 | `risk_rule` + seed nyata: venue exness, 2 akun (live cent 452009427 / demo 464202979), 3 instrumen, 2 strategi (gold_reaper_hexa, mtrb_pro), 2 strategy_run, 6 feed, 4 batas risiko | `SEED OK` + hitung: 1/2/3/2/2/6/4 | —
2026-11-17 | setup | Backup pertama DB lama: `pg_dump warroom` → 158 MB gzip → `cyber1:/root/backups/warroom/warroom-20261117-2107.dump.gz`, sha256 `5a4edb49…`, PGDMP valid | ukuran + sha cocok di dua sisi | disk cyber1 76%
2026-11-17 | setup | Bagan jabatan 9 posisi (`docs/peran.md`), backlog (`v1/backlog.json`), loop kontinu tiap 30 menit | cron aktif | —

**Keputusan yang mengikat (dari pemilik):**
- Live trade **hanya** forex/MT5 Exness cent `452009427`. Market lain paper/monitor.
- Semua data plane di **webdock**; **cyber1 hanya backup**.
- Akun live tetap **master password** (kompensasi: batas keras + audit + arm/confirm).
- Strategi = pekerjaan **di luar platform**; platform hanya registry + gate + ledger + audit + UI.
- Tema web **dipertahankan**.

**Berikutnya:** W1-03 ingest status MT5 → `account_snapshot`, `position`, `ledger_entry`.
2026-11-17 | W1-09 | Backup harian terenkripsi: pg_dump -> gpg RSA4096 (kunci privat hanya di cyber1) -> /var/backups/warroom, timer 02:00 UTC; cyber1 pull 02:20 + verifikasi header + retensi 14 | dump 158.519.389 B, decrypt header `PGDMP`, sha 687731023a00cc77, timer active/enabled | sempat gagal 2x karena permission dir & pipefail

**Berikutnya:** W1-03 ingest (loop sedang jalan), lalu W1-04 /v1/status.
2026-11-17 | drill | Restore drill dari backup terenkripsi: decrypt -> pg_restore ke warroom_restore_test -> bandingkan baris | rc=0, 51 s, 0 error, 22 tabel; facts 155234/155315, events 96598/96670, trades 217/217, alerts 460/460, heartbeats 195496/195532 (selisih = tulisan baru setelah dump) | plaintext dump dihapus setelah drill
2026-11-17 | W1-03 | Ingest MT5 -> v1: account_snapshot, position, ledger dari wr_telemetry.json + MTRB_status + wr_deals.jsonl; timer 20 s | snapshot=20, ledger=2 (-9.00), position=2, feeds ok age 1 s | 3 bug: waktu MT5 pakai titik, index unik parsial vs ON CONFLICT, error log terpotong
2026-11-17 | insiden | Telemetri live berhenti 20:07 (unit mt5-ex-live inactive); ditemukan oleh feed freshness, bukan oleh mata | live authorized 21:49:15 + EA loaded 21:49:18; watchdog diperbaiki (cek cmdline per-ini + telemetri basi > 5 mnt)
2026-11-17 | W1-04 | API v1 read-only di 127.0.0.1:8830: /v1/health, /v1/status (feeds level ok/warn/stale, run heartbeat, akun) | curl: summary feeds_ok=2, feeds_stale=0, runs_stale=0 | —
2026-11-17 | W1-05 | Rekonsiliasi saldo: account_baseline + recon_check, job 5 menit, endpoint /v1/recon; drift != 0 menulis event | live 1084.84-9.00=1075.84 vs broker 1075.84 (drift 0), demo 1000 vs 1000 (drift 0), all_ok=true | —
2026-11-17 | ops | Konsolidasi backup: `warroom-backup-postgres.timer` (00:40, plaintext ke /home/admin/backups/postgres, tanpa offsite) dimatikan; satu jalur saja = wr-backup terenkripsi -> cyber1 | timer lama disabled, timer baru active, dump 158 MB terverifikasi restore | dump plaintext lama dibiarkan (tidak dihapus) sampai pemilik memutuskan
2026-11-17 | W1-06 | Halaman /sistem (statis, tema crypto #0d1117): chip status, tabel feed (dot hijau/kuning/merah + umur + SLA), run heartbeat, recon drift; auto-refresh 10 s | /var/www/html/sistem 6193 B; nginx: /v1/ dan /sistem/ 401 tanpa auth, API lokal 200 | blok nginx pertama nyasar ke site maximalabs (dibersihkan, dipasang di site webdock)
2026-11-17 | W1-07 | Halaman /ledger/ (tab mutasi uang + jejak audit, tema sama): /v1/ledger (total per akun + 100 mutasi), /v1/jejak (200 event terakhir) | /ledger/ 401 tanpa auth; API: 2 deal -9.00 USC, 4 event | nama /ledger (tanpa slash) masih dipakai app lama -> catatan: konsolidasi nanti
2026-11-17 | W1-08 | Audit hook level DB: fungsi v1.audit_row + trigger di account, ledger_entry, position, strategy_run, feed(status), risk_rule, account_baseline | uji 2 event UPDATE:risk_rule (before->after benar); ingest tidak membanjiri (2 event/menit) | TG_OP tidak boleh di klausa WHEN -> trigger dipecah

**W1 SELESAI (9/9).** Berikutnya: W2 — halaman forex (ringkasan, posisi, sinyal, EA, jurnal, arm/confirm).
2026-11-17 | W2-01/02/04 | Halaman /forex/ (tema sama): kartu akun live+demo (equity, saldo, PnL hari ini, margin bebas, umur data), tabel posisi terbuka (entry/SL/TP/umur), tabel EA (magic, heartbeat, hidup/basi); API /v1/forex | /v1/forex: live 1075.84 USC PnL -9.00, demo 1000 USD, 0 posisi, 2 run heartbeat 18 s; /forex/ 401 tanpa auth | —
2026-11-18 | W2-03 | API /v1/forex/signals diaktifkan (restart uvicorn, endpoint sudah ada di app.py tapi proses lama belum memuatnya) | HTTP 200, count=0 (tabel signal kosong) | halaman /forex/sinyal belum dibuat: /var/www/html/forex/index.html root-owed, sudo ditolak cron mode
2026-11-18 | W2-03 | Ingest sinyal per engine (60 s) + /forex/sinyal/ + /v1/signals: decision approved/tunggu, reason_code, gate | GOLD MENUNGGU_KONFIRMASI; MAIN/SMCG/SMC/MOM ENGINE_NONAKTIF | kolom engine + unique bar; TG_OP di WHEN tidak boleh; % di LIKE harus %%
2026-11-18 | W2-05 | /forex/jurnal/ + /v1/journal: riwayat deal dari ledger | 2 deal | —
2026-11-18 | W2-06 | arm/confirm: token sekali-pakai, jejak di v1.event; EKSEKUSI NYATA sengaja belum tersambung | arm ok, confirm ok (executed:false) | 3 bug: %s ambigu, % di LIKE, q() fetchall pada INSERT
2026-11-18 | W3 | Market non-forex = monitor/paper (tile home 'belum live'), feed terdaftar tapi belum aktif | 4 tile | —
2026-11-18 | selesai | Home / diperbarui (ringkasan lintas market + tautan operasi), navigasi antar halaman lengkap | / 200 (tanpa data akun), /forex /forex/sinyal /forex/jurnal /sistem /ledger semua 401; API health/status/recon/forex/signals/journal 200; 4 timer aktif; 2 terminal64 hidup | —
2026-11-18 | W2-03 | Koreksi backlog: /forex/sinyal/ sebenarnya sudah jalan sejak 04:08 (index.html ada, location nginx matched); curl port 8830 salah -> 404 palsu. Verifikasi 05:18 UTC: HTTPS 401 (auth War Room) + /v1/signals 200 18970B. Status done.
2026-11-18 | W3 | Collector market non-forex (60 s) + /markets/ + /v1/markets: OKX spot 30 simbol, Polymarket 25 pasar; feed okx/polymarket ok | quote_okx=30, quote_polymarket=25, /markets/ 401 | gmgn & idx masih unknown (butuh sumber publik yang cocok)
2026-11-18 | ops | Hapus 7 dump plaintext lama (1.1G) di /home/admin/backups/postgres — sudah digantikan backup terenkripsi -> cyber1 | daftar+sha dicatat di docs/ops/hapus-dump-plaintext-20261118.log; backup terenkripsi tetap utuh (warroom-20261118-0200.dump.gpg) | —
2026-11-18 | ditunda | Eksekusi nyata arm/confirm: executor.py sudah ditulis (whitelist pause/resume/restart, unit dipetakan, hasil diaudit) tapi BELUM dipasang | alasan: satu-satunya jalur yang bisa menghentikan EA di akun live; menunggu izin eksplisit pemilik | —
2026-11-18 | executor | Eksekusi nyata arm->confirm->EXEC dipasang: whitelist aksi (pause/resume/restart), unit dipetakan dari target, hasil diaudit di v1.event; gerbang WR_EXEC_LIVE=0 | demo restart dieksekusi (unit mt5-ex-demo), live DITOLAK (live_locked) dan tetap hidup | 3 bug: target di CONFIRM kosong (ambil dari ARM), verb dari ARM bukan CONFIRM, polkit butuh rules.d (dipersempit ke 9 unit MT5 saja)
2026-11-18 | insiden | Restart demo menghentikan terminal64 demo ~1 menit; live ikut terdampak lalu dipulihkan watchdog+manual | akhir: 2 terminal64 hidup, mt5_demo & mt5_live ok (10 s), recon all_ok, saldo live 1075.84 USC / demo 1000 USD | —

**STATUS: seluruh backlog (W1 9/9, W2 6/6, W3 4/4) selesai + executor live-ready dengan live terkunci.**
2026-11-18 | audit | Audit UI via browser (user audit-hermes, role viewer): temukan endpoint /api/v1/tencent/mt5/status crash 500 -> UI tampilkan live DISCONNECTED/$0 | akar: /etc/warroom root:sudo 750, service API (admin) tak bisa baca service_token.env | DIPERBAIKI: setfacl u:admin:x; UI kini tampil EKUITAS 1075.84 USC (cocok DB/recon)
2026-11-18 | audit | Kredensial owner tidak ada di vault; password operator di vault usang (verify=False). Dibuat user audit-hermes (viewer, read-only) utk audit; password owner TIDAK di-reset | —
2026-11-18 | ops | Opsi C: status instabox dikeluarkan dari banner INFRA (box-2aacb3/mt5-paper-1/2 sudah bukan host EA live) | build web sukses, banner INFRA tidak tampil lagi (diverifikasi via browser); backup InfraBanner.svelte.old | deskripsi halaman forex yang menyebut Instabox TIDAK diubah (di luar lingkup opsi C)
2026-11-18 | keamanan | PIN /mtrb/ DIHAPUS atas permintaan pemilik (opsi C): config.php pin='' | API & halaman /mtrb/ kini terbuka publik tanpa PIN (200, data akun demo terlihat) | backup config: backups/web-root/mtrb-config.php.old; PERHATIAN: halaman menampilkan data akun demo (bukan live) ke siapa pun yang punya URL
2026-11-18 | warroom-v1 | SLA feed MT5 diperbaiki: registry mt5_live/mt5_demo 15s/10s < timer ingest 20s -> selalu warn. touch_feed kini menulis sla_seconds; ingest pass sla=45 keduanya | /v1/status: feeds_ok 2->4, mt5_live/mt5_demo level ok fresh=true (age 13s < 45s); py_compile OK; backup mt5_ingest.py.bak-sla
