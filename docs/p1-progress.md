# P1 — status pelaksanaan (backend layanan baru)

Diperbarui: **2026-10-02 21:00 UTC** (04:00 WIB, 3 Okt) · Pelaksana: Hermes
Rujukan: `docs/blueprint/03-backend.md`, `05-roadmap-hermes.md` §2 (P1)

## Ringkas

| Task | Status | Bukti |
|---|---|---|
| P1-T1 Postgres 16 + Alembic + skema | **selesai** | PostgreSQL 16.15 aktif; 2 migrasi bersih; **18 tabel** (17 + `alembic_version`) |
| P1-T2 `packages/core/gate.py` + `/api/v1/gate/evaluate` | **selesai** | 15 tes gate; endpoint == modul; `ci_low > be` satu-satunya jalur `lolos` |
| P1-T3 API + auth cookie/TOTP + RBAC + skema error | **selesai** | 401 tanpa login, 403 peran kurang, TOTP wajib bila terdaftar |
| P1-T4 Worker + jadwal deklaratif | **selesai + cutover** | tabel `jobs` (11 job); unit `warroom-worker.service` aktif; **cutover 3 Okt**: timer domain `snapshot`/`collect`/`backup` dimatikan, worker jadi penulis tunggal (`lt snapshot`, `lt scan`, backup — semua `ok`) |
| P1-T5 Penulis fakta snapshot → `facts` + `events` | **selesai** | idempoten (ON CONFLICT DO NOTHING); `observed_at` dari berkas |
| P1-T6 Endpoint baca per-area + `facts[]` | **selesai** | 5 area + `/areas` + `/facts/{kind}/{key}`; tiap angka bawa `fact_id/source/observed_at/ttl_s/status` |
| P1-T7 SSE `/api/v1/stream` + `Last-Event-ID` | **selesai** | 5 kejadian mengalir nyata saat stream terbuka; resume dari id bekerja |
| P1-T8 `/metrics`, log JSON, alert | **selesai** (transport belum diarahkan) | `/metrics` Prometheus + log JSON; jalur alert DB→transport terbukti dengan POST nyata ke server lokal |

Platform: **76 tes hijau**, `ruff` bersih. Jaring pengaman domain: **219 tes hijau** (dijalankan ulang
setelah semua perubahan). Layanan aktif: `warroom-api.service` (127.0.0.1:8800), `warroom-worker.service`.

## Bukti yang bisa dijalankan ulang

```bash
cd ~/warroom && uv run ruff check . && uv run pytest          # 76 lulus
cd ~/live-trading && uv run ruff check . && uv run pytest     # 219 lulus
bash ~/warroom/ops/ci-local.sh                                # 4 tahap CI
bash ~/warroom/ops/verify-p1-live.sh                          # API nyata: 401 → area → gate → metrics
bash ~/warroom/ops/verify-p1-sse.sh                           # SSE: kejadian nyata + resume
sudo bash -c 'set -a; . /etc/warroom/db.env; set +a; export HOME=/home/admin WARROOM_COOKIE_SECURE=0; \
  /home/admin/warroom/.venv/bin/python /home/admin/warroom/ops/verify-p1-parity.py'   # parity fakta
```

Potongan bukti nyata (21:00 UTC, server sungguhan):

```
/api/v1/crypto -> 401                          (tanpa login)
jumlah fakta: 15 | basi: 0
crypto fakta=9  idx fakta=3  forex fakta=1  gmgn fakta=4  polymarket fakta=5
gate: verdict=gagal ci_low=0.7696 be=0.77 required_n=1219
SSE : id 16 freshness.checked | id 17 job.ran | id 18 snapshot.published | id 19-20 job.ran
      resume Last-Event-ID=15 → id 16 terkirim ulang
metrics: warroom_facts_total 30 | warroom_facts_basi 0 | warroom_alerts_open 0
         warroom_job_enabled{job="notify"} 1 ...
```

## Job yang terdaftar (semua punya alasan; yang nonaktif berlabel NONAKTIF)

| Job | Interval | Aktif | Alasan |
|---|---|---|---|
| `publish-facts` | 300 s | ✅ | baca snapshot domain → facts + event (tanpa kuota) |
| `freshness` | 300 s | ✅ | umur fakta vs TTL; basi → alert (dedupe 1 jam) |
| `notify` | 300 s | ✅ | kirim alert terbuka; default tanpa transport → dicatat gagal, **tidak** diklaim terkirim |
| `snapshot` | 900 s | ❌ | timer domain masih penulis tunggal; dua penulis = berkas sama ditulis dua kali |
| `collect` | 1800 s | ❌ | `lt scan` memakai kuota Arjum; dua penulis = kuota dobel |
| `backup` | 21600 s | ❌ | timer domain sudah jalan + restore sudah teruji |

Cutover `snapshot`/`collect`/`backup` = **keputusan owner** (butuh jendela + verifikasi parity).

## Temuan yang membantah / menyimpang dari rancangan (ditulis apa adanya)

1. **`required_n` di blueprint terlalu besar.** Ditulis n≈2.587–3.400; hitungan eksak Wilson =
   **1.219** pada angka nyata (n=1.175, win=928, BE 77%, CI 90%), ≈1.187 pada p=79%.
   Jarak ke lolos lebih dekat daripada yang tertulis. Gate tetap `ci_low > BE`.

2. **KOREKSI (3 Okt): temuan TTL saya kemarin salah separuh.** `snapshot_ttl_s=600` di
   `config.py` **bukan** ambang badge "basi" — ia hanya penjaga cache di `load_snapshot()`
   (`dashboard.py:593`: bangun ulang bila berkas lebih tua dari 600 s). Ambang badge radar
   adalah `_RADAR_SEGAR_MNT = 45` menit. Jadi **tidak ada masalah** di domain, dan tidak ada
   perubahan yang perlu dilakukan di `live-trading`.
   Yang tetap benar: pilihan TTL **saya** untuk fakta snapshot (600 s) bertabrakan dengan irama
   tulis 15 menit (900 s) dan menghasilkan 15 alert palsu. TTL fakta kini **1800 s**
   (= 2× irama tulis, sama dengan `SNAPSHOT_MAX_AGE` di skrip backup domain).

3. **`Path.exists()` melempar `PermissionError`, bukan `False`, untuk berkas di direktori 700
   milik root.** Job `notify` sempat berstatus gagal karena ini. Semua akses berkas kredensial
   sekarang dibungkus `OSError`; transport hanya boleh berakhir "tidak dikonfigurasi".

4. **`fs.protected_regular=2` memblokir root menulis ke berkas milik user di `/tmp`.** Skrip
   verifikasi awal gagal karena ini; sesi uji sekarang ditangkap lewat command substitution
   (tidak pernah masuk transkrip, tidak menyentuh berkas).

5. **`facts` bertambah per `observed_at`** (15 kunci × tiap penerbitan). Itu memang desain
   (versi + `hash` untuk deteksi perubahan sunyi), tapi berarti retensi harus benar-benar
   dijalankan di P1 lanjutan — snapshot 90 hari seperti tertulis di `03-backend.md` §5.

6. **`gitleaks dir` (bukan `git`) menandai 20 false positive** di `live-trading/state/`
   (nilai harga 8 karakter). `state/` tidak dilacak git; mode `git` yang dipakai CI bersih.

7. **Cookie `secure=True` mematikan uji login lewat TestClient (http)** → saklar
   `WARROOM_COOKIE_SECURE=0` khusus pengujian; produksi tetap `secure=True`.

8. **`AGENTS.md` di `~/warroom` belum ada** (penulisan berkas instruksi agen diblokir kebijakan;
   butuh persetujuan user). Aturan kerja sementara ada di `README.md` + `docs/adr/`.

9. **Kernel `6.8.0-142` menunggu reboot** (ikutan `apt install postgresql-16`). Tidak dilakukan —
   host ini menjalankan bot trading; reboot = keputusan owner.

## Yang belum dikerjakan

- Transport alert belum diarahkan ke webhook nyata (Telegram bridge) → perlu URL dari owner.
  Jalur kirimnya sudah terbukti dengan POST ke server lokal sungguhan (uji otomatis).
- Enkripsi-at-rest TOTP secret (kolom `totp_secret_enc`) — dijadwalkan P6.
- Caddy/domain (03-backend.md §10) — belum; API masih 127.0.0.1:8800. P2/P3.
- Repo `~/warroom` belum punya remote GitHub → CI runner belum pernah jalan; bukti "CI hijau"
  dari `ops/ci-local.sh` (tahap identik, lokal).