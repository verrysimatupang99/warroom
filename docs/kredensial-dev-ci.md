# Kredensial dev, CI, dan e2e — aturan pakai

Dokumen ini menutup TODO 2 November #7: memberi catatan tegas bahwa ada
kredensial di repo/CI yang **hanya untuk dev, tes, dan CI**, dan tidak boleh
dipakai di produksi.

## Garis keras

1. **Tidak ada kredensial produksi di repo.** Rahasia produksi hidup di
   `/etc/warroom/*.env` (mode 600, milik root) dan tidak pernah masuk git.
   Diverifikasi `gitleaks detect` atas 611 commit: **0 temuan**.
2. **Kredensial di CI bersifat sementara.** Setiap kali job berjalan, Postgres
   dibuat dari nol lalu dibuang. Nilainya tidak membuka apa pun di luar job itu.
3. **Jangan menyalin nilai dari CI/dev ke server.** Kalau sebuah nilai kebetulan
   sama dengan produksi, itu bug — ganti, jangan dipertahankan.

## Daftar kredensial non-produksi

| Di mana | Nilai / nama | Untuk apa | Batas |
|---|---|---|---|
| `.github/workflows/ci.yml` (job `platform`, `e2e`) | Postgres `warroom` / `warroom`, DB `warroom_ci` | Tes ber-DB & cek head alembic | Postgres ephemeral per job, port hanya di runner |
| `.github/workflows/ci.yml` (job `e2e`) | `WARROOM_E2E_USER=uji-web`, `WARROOM_E2E_PASS=ci-e2e-bukan-rahasia` | Login suite Playwright | Disemai oleh `ops/e2e-seed-user.py` ke DB sementara; TOTP dimatikan |
| `~/.config/warroom/e2e.env` (lokal, mode 600, **tidak** di git) | `WARROOM_E2E_USER`, `WARROOM_E2E_PASS` | Menjalankan e2e di host dev | Hanya mesin operator |
| `~/.config/warroom/test-db.env` (lokal) | `WARROOM_TEST_DB_URL` | pytest yang menyentuh DB | DB tes lokal |

## Pengaman yang sudah terpasang

- `ops/e2e-seed-user.py` **menolak jalan** bila `WARROOM_DB_URL` menunjuk host
  bukan loopback — mencegah penyemaian user ke DB produksi secara tidak sengaja.
- Skrip itu tidak pernah mencetak sandi ke log.
- Sandi e2e disimpan sebagai hash `scrypt` (`warroom_api.auth.hash_password`),
  bukan teks biasa.
- Job `secrets — gitleaks` berjalan di setiap push/PR dan akan gagal bila ada
  pola rahasia baru yang ikut ter-commit.

## Yang masih terbuka (butuh owner, bukan agent)

Rotasi kunci lama di `/etc/warroom/` belum dilakukan. Daftar & umurnya:

| Berkas | Kunci | Terakhir diubah |
|---|---|---|
| `llm.env` | 4 | 2026-10-03 |
| `notifier.env` | 1 | 2026-10-03 |
| `axynode.env` | 1 | 2026-10-15 |
| `crypto.env` | 2 | 2026-10-16 |
| `tailscale.env` | 2 | 2026-10-16 |
| `service_token.env` | 1 | 2026-10-23 |
| `idx.env` | 1 | 2026-10-29 |
| `instabox.env` | 1 | 2026-10-29 |
| `okx.env` | 4 | 2026-11-01 |

Rotasi butuh akses ke dashboard tiap penyedia, jadi hanya owner yang bisa.
Karena `gitleaks` bersih, ini **rutin**, bukan darurat.
