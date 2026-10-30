# AGENTS.md — War Room

Panduan kerja untuk agent yang memegang repo ini. **Baca `HANDOVER-OMP.md` lebih dulu** —
di situ ada status sistem, angka terverifikasi, dan daftar hal yang masih rusak.

## Apa ini

Platform trading multi-market (forex, crypto, IDX, polymarket) dengan backend mandiri
di satu VPS Webdock. Situs publik: `https://0xgunsl1ng3r.xyz`.

Satu-satunya komponen di luar VPS: **MetaTrader 5 di VM Azure** (`mt5-trader-vm`),
yang mengeksekusi demo XAUUSD dan mengirim telemetri ke API di sini.

## Struktur

```
apps/web            SvelteKit (adapter-node), UI + tema token
services/api        FastAPI, REST /api/v1/* + SSE
services/worker     jadwal deklaratif (publish-facts, freshness)
services/notifier   push alert (Telegram)
services/llm        jalur model bahasa
packages/live-trading
ops/                Caddyfile, systemd unit, skrip operasional
docs/               ADR, audit, catatan keputusan
```

## Perintah

```bash
# uji
cd /home/admin/warroom && .venv/bin/python -m pytest services/api/tests services/worker/tests \
  services/notifier/tests services/llm/tests -q

# web: build + deploy (wajib keduanya; build saja tidak mengubah yang disajikan)
cd apps/web && sudo -u admin npm run build
sudo systemctl restart warroom-web
cat apps/web/build/build-id.txt          # bukti build yang benar-benar terpasang

# layanan
sudo systemctl restart warroom-api warroom-web warroom-worker
systemctl --failed --no-legend           # harus kosong
```

Python: `.venv` di root repo. Node: v24 di VPS.

## Aturan keras

1. **Jangan ubah token tema** (warna, font, radius) saat merombak UI. Tema dikunci user.
2. **Label harus jujur.** Tidak boleh ada badge yang menjanjikan lebih dari kenyataan
   (`AUTO-TRADE READY` sudah diganti `DEMO · TANPA UANG NYATA`).
3. **Jangan isi data kosong dengan nol palsu.** Kalau belum ada data, kembalikan `503`
   dengan pesan jelas — jangan `0` yang terlihat seperti hasil.
4. **Tab harus ada isinya.** Navigasi hanya menampilkan tab yang punya data nyata.
5. **Jangan pernah mencetak kredensial** ke chat, log, atau commit. Nilai ada di
   `/etc/warroom/*.env` dan `~/.hermes/secrets/`.
6. **Verifikasi dengan angka nyata**, bukan klaim. Kalau hasil membantah dugaan sendiri,
   tulis koreksinya di tempat yang sama.
7. Akun MT5 adalah **demo**. Tidak ada uang nyata. Jangan mengaktifkan jalur live.

## Jangan melakukan ini

- Menjalankan Strategy Tester MT5 lewat `az vm run-command` — jalan sebagai SYSTEM dan
  membaca data folder yang salah. Lihat `HANDOVER-OMP.md` §9.
- Menyalakan Tailscale. Sudah dihapus; akses klien lewat SSH tunnel.
- Menambah snapshot Azure (diminta tidak).
