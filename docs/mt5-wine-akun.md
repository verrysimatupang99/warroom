# MT5 di Webdock (Wine) — Inventaris & Cara Pakai

> Status: **read-only/pemantauan saja**. Dilarang mengirim order dari server.
> Login akun live di server hanya boleh **investor password** (read-only),
> BUKAN master password. Master password tidak disimpan di server.
> VM2 (`mt5-trader-vm2`, akun live cent 36525553) — JANGAN disentuh:
> lihat `HOLD_DO_NOT_TOUCH_AZURE_VM.md`.

## 1. Setup saat ini

- Container: `warroom-mt5-node` (image `linuxserver/webtop:ubuntu-xfce`), compose di
  `ops/docker-mt5/docker-compose.yml`. Web UI di `127.0.0.1:3300`.
- Wine prefix dipersist di host: `ops/docker-mt5/config/.wine` — **terminal64.exe
  ada di layer container**, jadi `docker compose up --force-recreate` atau build ulang
  image MENGHAPUS instalasi MT5 (prefix data tetap aman, harus install ulang programnya).
- Mode portable: ada `portable.txt` → data di `<install>/config`, bukan AppData.

## 2. Status cepat (satu perintah)

```bash
ops/docker-mt5/mt5-status.sh
```

Menampilkan: container, apakah terminal64.exe jalan, daftar akun tersimpan
(server + login + LIVE/demo + waktu terakhir), dan baris log login terakhir.
Script ini **read-only**.

## 3. Hasil inventaris akun (2026-11-02)

`accounts.dat` terenkripsi machine-key (tidak bisa dibaca offline). Sumber akun
yang terbaca: folder `Bases/<Server>/symbols/symbols-<login>.dat`:

| Login | Server | Jenis | Terakhir dipakai (UTC) |
|---|---|---|---|
| 452009427 | Exness-MT5Real25 | **LIVE** | 2026-11-01 14:30 |
| 452009427 | Exness-MT5Real6 | **LIVE** | 2026-11-01 15:09 |
| 452009427 | ExnessSC-MT5Real | **LIVE** | 2026-11-01 14:30 |

Kesimpulan: **ADA akun live Exness tersimpan** (login sama, 3 server Real).
Simbol yang pernah dibuka: major forex (EURUSD, GBPUSD, USDJPY, dll), indeks
(SP500m), saham US (AMD, MSFT, INTC). Tidak ada bukti akun demo tersimpan.

Catatan: percobaan login otomatis 2026-10-30 dengan password ini gagal
(authorization failed) — kemungkinan password berubah; jangan menebak,
minta investor password ke owner.

## 4. Alur PnP strategi eksternal → MT5 (rencana)

Prinsip: strategi dari `~/.warroom/strategies/` (plugin PnP, sudah terbukti)
menghasilkan sinyal → MT5 hanya **eksekusi/pemantauan**, platform inti tidak
berubah. Langkah aman:

1. Sinyal dari plugin (mis. `demo_breakout_retest`) diverifikasi gate statistik.
2. Untuk mode paper: sinyal dicatat, TIDAK diteruskan ke MT5.
3. Untuk pemantauan live: login ke MT5 via web UI dengan **investor password**,
   server sesuai tabel di atas. Baca posisi/balance saja.
4. EA `.ex5` TIDAK boleh disalin ke container tanpa keputusan owner
   (lihat `DIRECTIVE_FROM_OWNER.md`).

## 5. Operasi harian

```bash
cd ops/docker-mt5
docker compose up -d          # start (container lama tetap, prefix aman)
./mt5-status.sh               # cek status & akun
```

Akses UI dari laptop:

```bash
ssh -L 3300:127.0.0.1:3300 admin@<host-webdock>
# lalu buka http://localhost:3300
```

Peringatan:
- `docker compose up --force-recreate` / build ulang image → Wine & terminal64
  hilang (harus install ulang via `install_wine.sh` + `init_prefix.sh`).
- Disk host sempit — jangan tambah image baru.
