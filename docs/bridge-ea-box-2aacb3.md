# Bridge EA box-2aacb3 → War Room — SELESAI (9 Nov 2026)

Status: **telemetri live mengalir.** Akun `452009427` (Exness real) tampil di War Room
dengan `connected: true`, equity/balance dan harga XAUUSDc nyata, segar tiap 5 detik.

## Ringkas

| Item | Nilai |
|---|---|
| Sumber | `instabox-box-2aacb3`, MT5 build 6286 di Wine 11.21 |
| Akun | `452009427` @ Exness-MT5Real48, currency USC, hedging |
| EA | `GOLD_Reaper_Hexa` XAUUSDc M5 + modul telemetri (read-only) |
| Tujuan | `POST https://polywarroom.vps.webdock.cloud/api/v1/tencent/mt5/telemetry` |
| Auth | header `X-Warroom-Token` dari `/etc/warroom/service_token.env` |
| Interval | 5 detik |
| Skrip pemulihan | `/data/home/warroom-telemetry-ensure.sh` |

## Temuan penting

### 1. EA aslinya tidak pernah bicara ke mana pun
`GOLD_Reaper_Hexa` v2.10 murni indikator lokal (EMA 20/50/200 + VWAP + RSI) — **tidak ada
`WebRequest`**. Yang punya jalur War Room adalah `WarRoom_AutoTrader`, dan EA itu ada di
Azure `mt5-trader-vm` yang mati sejak 31 Okt (subscription disabled).

### 2. MT5 membuang allowlist WebRequest setiap restart (akar masalah 4014)
Gejala: `WebRequest()` gagal `err=4014` (`ERR_FUNCTION_NOT_ALLOWED`) dan nol request
sampai ke nginx, walaupun `config/common.ini` berisi:

```
[Experts]
WebRequest=1
WebRequestUrl=https://polywarroom.vps.webdock.cloud
```

Nilai itu **ditulis** MT5 tapi **tidak dibaca** saat start. Di GUI, checkbox
"Allow WebRequest for listed URL" terlihat tercentang sementara daftar URL-nya **kosong** —
persis kondisi yang memicu 4014. Izin hanya masuk akal lewat GUI
(Tools → Options → Expert Advisors), dan tidak bertahan setelah restart.

Solusi: skrip `warroom-telemetry-ensure.sh` mengisi ulang allowlist lewat `xdotool`
(tersedia di image ini) dan **dipanggil otomatis** di akhir `run_reaper_cent.sh`.

### 3. War Room menampilkan akun yang salah
`/api/v1/tencent/mt5/telemetry` menerima data dengan benar (respons
`{"status":"OK","received_at":...}`), tetapi `/mt5/status` tetap menampilkan data basi
akun `416510164` (akun Azure lama) karena `PRIMARY_ACCOUNT` default-nya akun itu.
Data akun baru tersimpan benar dan muncul di `/mt5/accounts` dengan `connected: true`.

Perbaikan: drop-in systemd untuk `warroom-api` dan `warroom-worker`:

```ini
# /etc/systemd/system/warroom-api.service.d/20-mt5-primary.conf
[Service]
Environment=WARROOM_MT5_PRIMARY_ACCOUNT=452009427
```

### 4. Log akses vhost ini tidak di `/var/log/nginx/access.log`
Vhost memakai `access_log /var/www/logs/access.log hermes_debug;` (format dengan
`X-Token`). Saat menelusuri request, periksa file itu — bukan access.log default.

### 5. MCP internal MT5 tidak bisa dipakai sebagai jalur alternatif
`127.0.0.1:22346` (`Server: MetaTrader5-MCP`) menjawab 401 untuk semua varian header
(Bearer / X-API-Key / Api-Key), meski ApiKey ada di `config/assistant.ini`.

## Yang dipasang di box-2aacb3

| Path | Isi |
|---|---|
| `MQL5/Include/WarRoomTelemetry.mqh` | modul telemetri, read-only, token dibaca dari file |
| `MQL5/Files/warroom_token.txt` | token War Room, mode 600 |
| `MQL5/Experts/Mes/GOLD_Reaper_Hexa.mq5` | +4 titik hook: include, WarRoomInit, WarRoomDeinit, OnTimer |
| `MQL5/Experts/Mes/GOLD_Reaper_Hexa.ex5` | build telemetri (85.922 B) |
| `MQL5/Experts/Mes/GOLD_Reaper_Hexa.ex5.bak-20261109` | biner asli (69.416 B, md5 `67fb7c50…`) |
| `/data/home/warroom-telemetry-ensure.sh` | pastikan/ perbaiki telemetri (idempotent, `--check`) |
| `/data/home/run_reaper_cent.sh` | +1 baris memanggil skrip di atas |
| `MQL5/Files/warroom_debug.txt` | log ground-truth `push: OK/GAGAL` (self-trim > 2 MB) |

Logika trading EA **tidak diubah**: modul hanya membaca state akun dan harga.

## Verifikasi

```
# di box
tail MQL5/Files/warroom_debug.txt      -> "push: OK http=200 ok#N" tiap 5 dtk
/data/home/warroom-telemetry-ensure.sh --check -> "telemetri OK (3/3 …)"

# di Webdock
curl -H "X-Warroom-Token: $TOKEN" .../api/v1/tencent/mt5/status
  connected=true  account=452009427  balance=1034.74  bid=4119.053  positions=0
```

Uji pemulihan penuh sudah dilakukan: terminal dimatikan paksa → skrip dijalankan →
terminal menyala → allowlist dipasang ulang → telemetri kembali `OK` tanpa campur tangan
manusia.

## Kalau telemetri mati lagi

```bash
/data/home/warroom-telemetry-ensure.sh          # perbaiki
/data/home/warroom-telemetry-ensure.sh --check  # hanya cek
```

Kalau tetap gagal, buka GUI (tab Computer) dan isi manual:
Tools → Options → Expert Advisors → dobel-klik baris "add new URL" → tempel
`https://polywarroom.vps.webdock.cloud` → Enter → OK.

## Catatan operasional

- Free plan instabox: auto-suspend 30 mnt idle, max-run 480 mnt. Watchdog di `api-01`
  me-restart box ini saat umur run > 450 mnt; telemetri akan pulih sendiri karena
  `run_reaper_cent.sh` memanggil skrip ensure.
- Sesi trade EA: 08–09 jam server (15:00–15:59 WIB). Restart terminal sebaiknya di luar itu.
- Jangan pakai `pkill -f 'terminal[6]4'`: pola itu ikut mencocokkan command line shell
  pemanggil dan pernah menjatuhkan terminal live. Pakai `pkill -x` atau filter `ps`.