# Runbook — MetaTrader 5 di Webdock (read-only)

Dibuat 1 Nov 2026. Tujuan: menjalankan MT5 di server tanpa menyentuh VM2 dan tanpa
memberi War Room kemampuan eksekusi.

## Catatan resmi MetaQuotes

MetaQuotes menjalankan MT5 di Linux lewat Wine. Instruksi resminya:

```
wget https://download.terminal.free/cdn/web/metaquotes.software.corp/mt5/mt5linux.sh
chmod +x mt5linux.sh
./mt5linux.sh
```

Skrip itu menambahkan repo WineHQ, menginstal `winehq-staging`, mengunduh
`mt5setup.exe` dan WebView2, lalu menjalankan installer dengan `WINEPREFIX=~/.mt5`.
Sumber: `metatrader5.com/en/terminal/help/start_advanced/install_linux`.

Yang tidak cocok untuk server ini:

- Skrip menjalankan `apt upgrade -y` seluruh sistem. Tidak dijalankan di produksi.
- Installer dan login butuh tampilan grafis.
- Di host, WineHQ dan Wine distro gagal dipasang karena `libgphoto2-6t64:i386`
  menuntut `libgd3:i386`, sementara `libgd3` amd64 berasal dari PPA sury dengan versi
  berbeda. Konflik multiarch ini bukan berasal dari War Room.

## Metode yang dipakai: container Webtop

`ops/docker-mt5/docker-compose.yml` menjalankan `linuxserver/webtop:ubuntu-xfce`
(akses lokal `127.0.0.1:3300`). Di dalam container:

- Ubuntu 26.04, WineHQ staging 11.12 (repo questing + libavcodec61 questing). Wine 10 distro gagal: MT5 menampilkan "A debugger has been found running" walau `SYS_PTRACE` sudah dihapus.
- MT5 dipasang portable di
  `/config/.wine/drive_c/Program Files/MetaTrader 5`.
- Desktop launcher: `config/Desktop/metatrader5.desktop`.
- Data MT5 ada di prefix `/config/.wine`; dari host terlihat di
  `ops/docker-mt5/config/.wine`.

Perintah yang dipakai:

```bash
cd ops/docker-mt5
docker compose up -d
docker exec -u root warroom-mt5-node bash -c \
  'dpkg --add-architecture i386; apt-get update; \
   apt-get install -y --install-recommends wine wine64 wine32:i386'
docker exec -u abc -e WINEPREFIX=/config/.wine -e WINEDLLOVERRIDES=mscoree,mshtml= \
  -e XDG_RUNTIME_DIR=/tmp/runtime-abc warroom-mt5-node \
  xvfb-run -a wine /config/mt5setup.exe /auto
```

Verifikasi: `terminal64.exe` ada (117 MB), folder `Config`, `Profiles`, dan
`AppData/Roaming/MetaQuotes/Terminal` terbentuk setelah terminal dijalankan.

## Cara masuk

1. Di laptop: `ssh -L 3300:127.0.0.1:3300 admin@<webdock>`.
2. Buka `http://127.0.0.1:3300`.
3. Klik launcher **MetaTrader 5**.
4. Login memakai akun demo, atau akun live dengan **investor password**.
   Jangan memakai master password akun live.

## Batas dan risiko

- War Room tetap read-only. Container ini tidak dipakai untuk mengirim order.
- WebView2 tidak dipasang. Berita/komunitas di dalam terminal mungkin tidak tampil;
  chart dan data akun tetap jalan.
- Disk host 93% (3,5 GiB bebas) setelah image dan prefix Wine. Jangan menambah image
  besar sebelum ruang dibersihkan.
- Container memakai memori sekitar 350 MiB saat idle.
- Instalasi Wine berada di layer container, bukan volume. `docker compose up --force-recreate` menghapus Wine; prefix MT5 di `/config/.wine` tetap ada. Untuk produksi, Wine harus dipindah ke Dockerfile.
- Disk host 95% (2,7 GiB bebas). Ini risiko produksi; jangan menambah image/instalasi besar sebelum ruang dibebaskan.
- Jangan menyalin EA ke container ini tanpa keputusan owner; tujuannya pemantauan.

## Rollback

```bash
cd ops/docker-mt5 && docker compose down
```

Image dan prefix tetap ada sampai `docker image rm` dan folder `config/.wine` dihapus.

## Hasil uji 1 Nov 2026 — login belum selesai

- MT5 build 6295 berjalan di Wine 11.12 (screenshot terminal terbuka).
- Login akun `452009427` gagal: server `Exness-MT5Real48` tidak ada di daftar
  perusahaan yang tersedia. Daftar Exness SC hanya memuat `ExnessSC-MT5Real0..12`;
  daftar UK memuat `ExnessUK-*`. Pesan: `authorization on Exness-MT5Real failed
  (invalid account)`.
- Artinya entitas Exness yang dipilih belum benar, atau server itu milik entitas lain.
  Perlu entitas yang tepat dari layar login MT5 pengguna.
- File `startup.ini` berisi kredensial sudah dihapus setelah uji. Jangan menyimpan
  master password di server; gunakan investor password.
