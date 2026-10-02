# P1 — status pelaksanaan (backend layanan baru)

Diperbarui: **2026-10-02 20:40 UTC** (03:40 WIB, 3 Okt) · Pelaksana: Hermes
Rujukan: `docs/blueprint/03-backend.md`, `05-roadmap-hermes.md` §2 (P1)

## Ringkas

| Task | Status | Bukti |
|---|---|---|
| P1-T1 Postgres 16 + Alembic + skema | **selesai** | PostgreSQL 16.15 aktif; `alembic upgrade head` bersih; **17 tabel** (16 + `alembic_version`) |
| P1-T2 `packages/core/gate.py` + `/api/v1/gate/evaluate` | **selesai** | 15 tes gate hijau; endpoint == modul (uji parity); `ci_low > be` satu-satunya jalur `lolos` |
| P1-T3 `services/api` FastAPI: auth cookie+TOTP, RBAC, skema error | **selesai** | 14 tes API hijau: 401 tanpa login, 403 peran kurang, TOTP wajib bila terdaftar, error `{error:{code,message}}` |
| P1-T4 Worker + jadwal deklaratif | **belum** | kerangka paket ada; job & unit systemd menyusul |
| P1-T5 Penulis fakta snapshot → `facts` + `events` | **selesai** | 10 tes hijau; idempoten (ON CONFLICT DO NOTHING); `observed_at` dari berkas, bukan "sekarang" |
| P1-T6 Endpoint baca area + `facts[]` per respons | **sebagian** | ada: `/health`, `/freshness`, `/gate/evaluate`, `POST /facts`. Endpoint per-area (crypto/idx/forex/gmgn/poly) menyusul |
| P1-T7 SSE `/api/v1/stream` | **belum** | — |
| P1-T8 Observability `/metrics`, log JSON, alert | **belum** | — |

Jaring pengaman tidak rusak: `live-trading` **219 tes hijau**, `ruff` bersih (dijalankan ulang
setelah semua perubahan). Platform: **39 tes hijau**, `ruff` bersih.

## Bukti yang bisa dijalankan ulang

```bash
cd ~/warroom && uv run ruff check . && uv run pytest        # 39 lulus
cd ~/live-trading && uv run ruff check . && uv run pytest   # 219 lulus
bash ~/warroom/ops/ci-local.sh                              # 4 tahap CI: SEMUA HIJAU
sudo bash -c 'set -a; . /etc/warroom/db.env; set +a; export HOME=/home/admin WARROOM_COOKIE_SECURE=0; \
  /home/admin/warroom/.venv/bin/python /home/admin/warroom/ops/verify-p1-parity.py'
```

Keluaran terakhir `verify-p1-parity.py` (potret nyata, 20:36 UTC):

```
terbit : status=ok fakta=15 observed_at=2026-10-02T20:33:44+00:00
parity : 15 fakta acak dibandingkan; beda=0
gate   : verdict=gagal ci_low=0.7696 be=0.77 required_n=1219
event  : 2 event 'snapshot.published' tercatat dari aktor 'verifikasi'
HASIL  : HIJAU
```

## Infrastruktur yang ditambahkan

| Item | Nilai |
|---|---|
| PostgreSQL | 16.15 (Ubuntu), unit `postgresql` **active**, DB `warroom` (17 tabel) + DB tes `warroom_test` |
| Kredensial produksi | `/etc/warroom/db.env` — mode **600**, owner **root** (unit systemd membacanya lewat `EnvironmentFile=`, jadi proses tetap boleh jalan sebagai `admin`) |
| Kredensial tes | `~/.config/warroom/test-db.env` — mode **600**, owner `admin`, **di luar repo**; tes DB dilewati (skip, bukan lulus) bila tidak ada |
| gitleaks | 8.30.1 di `~/.local/bin/gitleaks` |

## Temuan yang membantah / menyimpang dari rancangan (ditulis apa adanya)

1. **`required_n` di blueprint terlalu besar.** `01-studi-polymarket.md` §3 menyebut "butuh
   n≈2.587–3.400" agar `ci_low > BE` pada win rate 79,0% vs BE 77,0%. Perhitungan eksak
   (Wilson, cari-n dobel→bagi dua) memberi:
   - **CI 90%: n ≈ 1.187** (pada angka nyata n=1.175, win=928 → `required_n` = **1.219**)
   - CI 95%: n ≈ 1.664

   Artinya jarak ke lolos **lebih dekat** daripada yang tertulis (≈1,7–1,9 hari pada laju
   recorder 670 window/hari, bukan 4–5 hari) — *dengan asumsi win rate 79% bertahan dan BE
   77% tidak berubah*. Ini bukan alasan melonggarkan apa pun: gate tetap `ci_low > BE`, dan
   angka ini hanya ditampilkan sebagai meter. **Dokumen studi perlu dikoreksi** oleh owner.

2. **`gitleaks dir` pada `live-trading` menemukan 20 "kebocoran" — semuanya palsu.** Berkas
   `state/cache/dexscreen/dex.json` + `state/snapshot.json` memuat nilai 8 karakter (mis. harga
   `price_usd`) yang cocok pola `generic-api-key`. `state/` **tidak dilacak git**, jadi mode yang
   dipakai CI (`gitleaks git`, 121 commit) bersih: **no leaks found**. Tidak ada tindakan.

3. **Path sumber uv workspace relatif terhadap direktori anggota, bukan root.** `packages/core`
   harus memakai `../../../live-trading`. Salah satu level → `Distribution not found`.
   Sudah dicatat di ADR-002.

4. **Cookie sesi `secure=True` membuat uji login mustahil lewat TestClient (http).** Ditambahkan
   saklar `WARROOM_COOKIE_SECURE=0` **khusus pengujian**; produksi tetap `secure=True` di balik TLS.

5. **Kebocoran kredensial di sesi ini (ditangani).** Saat verifikasi pertama, satu perintah
   diagnostik mencetak sandi DB `warroom` ke keluaran alat. **Sandi langsung dirotasi**
   (`ALTER ROLE … PASSWORD`) sebelum pekerjaan dilanjutkan; sandi lama tidak berlaku. Tidak ada
   kredensial yang ditulis ke repo/log. Pelajaran: jangan pernah memakai pola `${VAR%%@*}` untuk
   menampilkan URL — pakai `safe_url()`.

6. **Kernel baru menunggu reboot.** `apt-get install postgresql-16` ikut memasang kernel
   `6.8.0-142`; sistem masih berjalan di `6.8.0-139`. **Tidak dilakukan reboot** — host ini
   menjalankan bot trading. Reboot adalah keputusan owner.

7. **`AGENTS.md` di `~/warroom` belum ada.** Penulisan berkas instruksi agen diblokir oleh
   kebijakan (butuh persetujuan user; prompt tidak dijawab). Aturan kerja sementara ada di
   `README.md` + `docs/adr/`. Setujui penulisannya bila diinginkan.

## Yang belum dikerjakan (jujur)

- P1-T4 worker + jadwal deklaratif (timer lama masih systemd; **belum** dipindahkan).
- P1-T6 endpoint per-area (crypto/idx/forex/gmgn/poly) — hanya fondasi yang ada.
- P1-T7 SSE, P1-T8 `/metrics` + alert.
- TOTP secret masih tersimpan apa adanya di kolom `totp_secret_enc` (DB tidak masuk repo/log);
  enkripsi-at-rest dengan kunci `/etc/warroom/` dijadwalkan P6.
- Repo `~/warroom` belum punya remote GitHub → CI (`ci.yml`) belum pernah berjalan di runner.
  Bukti "CI hijau" saat ini dari `ops/ci-local.sh` (tahap identik, dijalankan lokal).