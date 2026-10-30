# Serah-terima War Room untuk OMP

Ditulis 30 Okt 2026 oleh Hermes. Pengganti saya memegang repo ini dan mulai bekerja
dari sini. Semua angka di bawah adalah hasil eksekusi nyata, bukan perkiraan.

---

## 1. Status satu layar

| Hal | Keadaan |
|---|---|
Repo | `/home/admin/warroom`, branch `main`, commit `8e00176`, tree **bersih** |
Situs | `https://0xgunsl1ng3r.xyz`, build `8e00176-20261030T114631Z` |
Layanan | `warroom-api` `warroom-web` `warroom-worker` **running**, 0 unit gagal |
Database | PostgreSQL 16, db `warroom` |
EA produksi | `WarRoom_AutoTrader_v3` (logika Reaper) di VM Azure, akun demo `416510164` |
Telemetri | hidup, snapshot tiap 60 detik, terverifikasi masuk tabel `facts` |
Trade forex tercatat | **0** — belum pernah ada satu pun |

---

## 2. Arsitektur

```
Pengguna ──HTTPS──> nginx ──> warroom-web (SvelteKit, :3100)
                        └──> warroom-api (FastAPI) ──> PostgreSQL `warroom`
                                     ^
                                     │ HTTPS: telemetry / fill / sinyal
                                     │
                          MT5 di Azure (mt5-trader-vm)
                          WarRoom_AutoTrader_v3, XAUUSDm M5
```

Tiga layanan systemd: `warroom-api`, `warroom-web`, `warroom-worker`.
Timer penting: `warroom-alert-push` (10 mnt), `warroom-momentum-paper`,
`warroom-panel-sim`, `warroom-laya-verdict`, `warroom-pantau-tick`,
`warroom-backup-postgres`.

### Tabel `facts` — jantung data

```
id, kind, key, value_json, source, observed_at, ttl_s, hash, created_at
```

Kind yang dipakai: `mt5_snapshot` (telemetri EA), ditambah kind lain per modul.
Data lama dipangkas, jadi `count(*)` kecil itu **normal** — yang penting
`max(observed_at)` dekat dengan `now()`.

```bash
sudo -u postgres psql -d warroom -tAc \
 "select count(*), max(observed_at), now() from facts where kind='mt5_snapshot';"
```

---

## 3. Yang benar-benar dikerjakan sesi lalu

### 3.1 Reaper diadopsi ke AutoTrader

Sebelumnya `WarRoom_AutoTrader` v2.0 hanya menerima sinyal dari server War Room.
Sekarang v3.0 punya **dua sumber sinyal** lewat satu input:

```
InpSumberSinyal = SUMBER_SERVER | SUMBER_REAPER
InpUjiDuaSumber = false   // true = Reaper dulu, server jadi cadangan
```

Logika Reaper yang masuk: EMA21/55 + tren EMA200 (M15) + RSI14 (batas 25–75),
filter ATR 0,80–20,0 USD, spread maks 0,40, sesi jam server, skip Senin,
risiko 0,5%/trade, SL 1,6×ATR, TP 3,5×ATR, maks 6 trade/hari,
stop rugi harian 3%, stop profit harian 6%.

**Yang tidak disentuh:** telemetri, `ManageOpenPositions()`, `CheckDailyProtections()`.
Itu rantai bukti War Room — jangan diubah tanpa alasan kuat.

Berkas:
```
MQL5/Experts/WarRoom_AutoTrader_v3.mq5   51.059 byte
MQL5/Experts/WarRoom_AutoTrader_v3.ex5   81.806 byte   (0 errors, 0 warnings)
config/startup.ini                       137 byte, Expert=WarRoom_AutoTrader_v3
config/startup.ini.v2bak                 untuk rollback
MQL5/Experts/WarRoom_AutoTrader.ex5      64.412 byte (v2, pembanding)
```

### 3.2 Hasil backtest — angka yang harus lu percaya

3 tahun (27 Okt 2023 – 27 Okt 2026), XAUUSDm M5, Model 2, modal $10.000.

| Varian | Net | PF | Trade | DD | Titik putus slippage |
|---|---|---|---|---|---|
**A — sesi 08–09** | **+$3.923** | **1,25** | 771 | **6,01%** | **0,48** |
B — sesi 08–17 | −$1.787 | 0,95 | 1.846 | 25,48% | 0,00 |
A pure (tanpa partial/BE/trailing) | +$4.697 | 1,24 | 525 | 7,55% | 0,56 |
Reaper H08 asli (pembanding) | +$1.640 | 1,07 | 1.017 | 9,7% | 0,11 |

Spread terukur akun demo: **$0,240** (240 point, digits 3). Artinya A punya margin 2×,
Reaper asli sudah melewati batas.

**Yang dipasang di Azure: varian A.** Net/DD 5,44 vs 4,72 milik pure — lebih baik
imbal-risikonya meski profit absolut lebih rendah $774.

Rincian per tahun (bukti bukan satu tahun keberuntungan):

```
A     : 2023 −378 · 2024 +960 · 2025 +1.990 · 2026 +1.352
Pure  : 2023 −273 · 2024 +1.475 · 2025 +2.149 · 2026 +1.346
B     : negatif di keempat tahun
```

Uji ketahanan: SL/TP 2,0/4,0 → PF turun ke 1,14. **Jangan optimasi lebih jauh** —
sudah di tepi curve-fitting.

### 3.3 Perbaikan web

- Bar mobile 48px (`fixed`) tidak pernah disembunyikan di `@media (min-width: 768px)`,
  sementara `.main-canvas` padding-top turun ke 24px → 24px awal konten tertimpa.
  Diperbaiki dengan `.mobile-header { display: none }` di media query desktop.
  Diukur: desktop konten mulai y=24 tanpa bar; mobile bar 48px, konten y=60.
- Deskripsi halaman forex masih menyebut "Sinyal dari Laya Sentinel" padahal v3
  menghitung sinyal lokal. Sudah diganti.

---

### 3.4 EA v3.1 + jurnal deal (30 Okt 2026)

- Telemetri EA membawa `server_time`, `eval_at`, `eval_alasan`, `eval_sesi`, `eval_atr`,
  `eval_spread`, `eval_rsi`, `eval_ema_fast`, `eval_ema_slow`, `eval_tren`. Panel
  **Status mesin Reaper** tampil di tab Sinyal halaman forex.
- Deal tertutup dilaporkan ke `POST /api/v1/tencent/mt5/deal` →
  `/var/lib/warroom/deals.csv` (idempoten per ticket). `/journal/trades` membaca
  `deals.csv` untuk `closed` dan `fills.csv` untuk `entries`; fills tetap sumber
  slippage/latensi.
- Uji end-to-end: deal sintetis ticket `999999` muncul di jurnal dengan net $8,50,
  lalu berkas uji dihapus.
- Exposure gate kini membaca posisi paper nyata (3 total/2 searah dari settings);
  verdict tidak lagi menulis `0/2` saat dua SHORT terbuka.
- **Sprint 1 sisa selesai 30 Okt:** job `forwardtest-watchdog` (60 s) mengawasi
  telemetri mati saat sesi dan deal yang tidak masuk `deals.csv`;
  `tools/forwardtest_status.py` mencetak DoD 20 trade/30 hari; runbook trade pertama
  ada di `docs/runbook-trade-pertama.md`; panel Reaper dijaga e2e
  `apps/web/e2e/cek_panel_reaper.spec.ts`.
- Suite terkini: **900** tes (perintah AGENTS), **1099** root `pytest`; 70 vitest, 49 spec e2e.
- Rollback EA: `WarRoom_AutoTrader_v3.ex5.v30bak` / `.mq5.v30bak` di data folder Azure;
  source v3.1 juga ada di `MQL5/Experts/WarRoom_AutoTrader_v31.mq5`.

---

## 4. Halaman & API — apa yang nyata

Rute publik: `/mulai` (satu-satunya tanpa sesi). Sisanya butuh cookie `wr_session`.

```
GET /api/v1/journal/stats?market=all|forex|crypto     200
GET /api/v1/journal/trades?market=...                 200  (kosong: n=0)
GET /api/v1/journal/performance?market=...            200  (deret ekuitas)
GET /api/v1/journal/edge?market=...                   503  "Belum ada fill forex"
GET /api/v1/journal/multipair?market=...              200  (kosong)
GET /api/v1/tencent/forex/levels?symbol=XAUUSD        200  (sinyal Laya)
POST /api/v1/tencent/mt5/telemetry                    butuh token EA
```

Halaman forex punya 5 tab: `ringkas · sinyal · uji · eksekusi · alat`.
Semuanya render. Yang kosong hanya `eksekusi`, karena memang belum ada trade.

**Untuk memeriksa halaman ber-sesi tanpa password user:** buat baris di tabel
`sessions` (kolom: `id`, `user_id`, `created_at`, `expires_at`, `revoked_at`),
pakai cookie `wr_session=<id>`, lalu **revoke** setelah selesai.

```sql
insert into sessions (id,user_id,created_at,expires_at)
select 'aud-'||substr(md5(random()::text),1,6), min(id), now(), now()+interval '20 minutes' from users returning id;
-- setelah selesai:
update sessions set revoked_at=now() where id like 'aud-%' and revoked_at is null;
```

---

## 5. Infrastruktur di luar VPS

### VM Azure — `mt5-trader-vm`
```
RG            FOREX-MT5-RG
IP            138.91.35.65
Ukuran        Standard_B2ats_v2 (2 core, 1.019 MB RAM)
MT5 build     6274
Akun          416510164 @ Exness-MT5Trial14 (demo), ping ~2,4 ms
Proses        terminal64.exe, dijalankan task LaunchMT5GUI sebagai user traderadmin
Data folder   C:\Users\traderadmin\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075
NSG allowlist 138.91.35.65, 20.212.52.5, 32.186.94.41, 34.215.27.177,
              125.165.155.166, 114.4.100.6   (jangan pernah '*')
```
RAM sisa ~139 MB. **Jangan pasang EA kedua** — `startup.ini` hanya mendukung satu
`[StartUp] Expert=` dan RAM tidak cukup.

### Instabox
```
box-2aacb3     MT5 Wine (akun 434434290 @ Exness-MT5Trial7), autoSuspend 1800s
testing        Telethon: scanner.py, 19 channel, 108 sinyal ter-ekstrak
sshjump        jumphost port 2222 — JANGAN disentuh
```
Akses dari laptop: `~/bin/via-jump poly|api01 [cmd]`.

---

## 6. Kredensial — di mana, bukan apa

| Rahasia | Lokasi |
|---|---|
DB, LLM, notifier, IDX, instabox | `/etc/warroom/*.env` |
Password MT5 demo | `~/.hermes/secrets/mt5_434434290.env` (600) |
Token Telegram bot | `/etc/warroom/notifier.env` |

**Semua ini belum dirotasi** dan sebagian pernah lewat chat: MEXC API key+secret,
kunci IDX (`stock.arjum.com`), kunci Stitch, password MT5. Rotasi masih terbuka.
`/etc/warroom/tailscale.env` sudah tidak dipakai — kandidat dihapus.

---

## 7. Yang masih rusak atau menggantung — jujur

1. **`fills.csv` hanya header** → tabel `trades` 0 baris → `/journal/edge` 503,
   `multipair` kosong. Ini bukan bug kode: memang belum ada trade yang tereksekusi
   sejak pipeline dicatat.
2. **Belum ada trade nyata dari v3.** EA hidup dan mengirim telemetri, tapi sesi
   Reaper jam 08:00–09:00 waktu server dan v3 baru dipasang 19:30. Sampai satu trade
   benar-benar tercatat, "bisa trading di akun" masih **belum terbukti**.
3. **Tab tipis:** `/riset?sub=leaderboard` (butuh ≥2 strategi lulus Gate B),
   `/crypto?sub=sinyal` (level SMC tanpa padanan lokal), `/sistem?sub=event`.
4. **`gmgn_siklus` dan `lp_mark` = `inf`** — berkas state tidak ada.
5. **Backtest real-tick gagal** — `Model=3` menghasilkan 0 tick dan tidak menulis laporan.
6. **API crypto/IDX `not_configured`** — parkir sampai Gate B atau node data lokal.
7. **Kuota IDX** — `ANGGARAN_HARIAN = 1000`, penghitung harian append-only di
   `~/.panggilan-<YYYYMMDD>.log`, guard menolak dengan `IdxTidakSiap` saat habis
   (tanpa retry, karena berbayar).
8. **Watchdog** ambang: snapshot 1200s, verdicts 2400s, gmgn_siklus 4200s,
   lp_mark 93600s, radar_lokal 3600s, mt5_telemetri 600s.

---

## 8. Keputusan yang menunggu user

- **Varian A atau pure** untuk EA produksi. Sekarang A. Pure butuh
  `InpUsePartialTP=false` dan menghasilkan +$774 lebih dengan DD 7,55%.
- **Model default omp** belum diset; `~/.omp/agent/config.yml` hanya `setupVersion: 2`.

---

## 9. Jebakan yang sudah memakan waktu — jangan diulang

**Strategy Tester MT5 menuntut akun tersimpan.** Tanpa itu:
`tester not started because the account is not specified`, `exit -1000012353`
(Wine: `rc=191`). Menaruh `[Common] Login=` di config **tidak menolong**.
Build 6286 menyimpan akun di **`config/accounts.dat`**, bukan `accounts.ini` —
kalau mencari `accounts.ini` dan tidak menemukannya, jangan simpulkan akun tidak ada.
Hanya pemilik akun yang bisa membuatnya lewat `File → Login to Trade Account`
dengan "Save password". **Jangan pernah meminta atau mengetik password user.**

**Jangan jalankan tester lewat `az vm run-command`.** Perintah itu jalan sebagai
SYSTEM, dan MT5 memakai `%APPDATA%` user yang menjalankannya → membaca data folder
SYSTEM yang kosong, keluar diam-diam tanpa laporan. Scheduled task `LogonType S4U`
juga gagal (profil tidak dimuat, selesai 10 detik tanpa log). Jalur yang bekerja:
sesi interaktif RDP, atau Wine lokal di mesin yang akunnya sudah login.

**MT5 wajib `/portable`.** Tanpa itu ia membuka profil kosong di AppData — tanpa akun,
tanpa EA, tanpa laporan.

**Laporan MT5 adalah UTF-16LE dengan BOM.** Dibaca sebagai UTF-8 → nol baris, dan itu
mudah disalahartikan sebagai "EA tidak trading". Parse berbasis header, dan hanya deal
`Direction == "out"` yang merealisasi profit; `in` selalu 0,00.

**Input yang tidak dipakai.** Setelah menyisipkan blok input baru, cek tiap input
direferensikan: `grep -c InpNama file.mq5` harus ≥ 2. Input yang muncul sekali adalah
input mati — EA kompilasi bersih, tester jalan, tapi nilainya tidak berefek. Tandanya:
dua laporan **identik byte-per-byte** dengan nilai input berbeda. Ini pernah terjadi
pada enam input BE/trailing di v3 dan sudah dibuang.

**Dua manajemen posisi bertabrakan.** `InpUsePartialTP=true` menutup 50% lot di +1,0R
sehingga rasio untung-rugi jatuh ke 0,77:1 meski TP 3,5×ATR. Uji manajemen lama
hidup vs mati sebelum menyimpulkan strateginya lemah.

**`az vm run-command` memotong keluaran di ~4.096 byte.** Untuk menarik berkas besar,
potong base64 per 3.500 karakter; untuk mengunggah, kirim per ~16.000 karakter per
panggilan (batas keluaran, bukan batas skrip).

**`instabox exec` memotong perintah di 60 detik.** Untuk pekerjaan lebih lama, jalankan
`nohup ... &` di dalam perintah lalu baca berkas hasilnya di panggilan berikutnya.

---

## 10. Cara memverifikasi semuanya masih sehat

```bash
# 1. layanan
systemctl --failed --no-legend                      # harus kosong
systemctl is-active warroom-api warroom-web warroom-worker

# 2. build yang benar-benar tersaji
cat /home/admin/warroom/apps/web/build/build-id.txt

# 3. telemetri hidup (max harus dekat now)
sudo -u postgres psql -d warroom -tAc \
 "select max(observed_at), now() from facts where kind='mt5_snapshot';"

# 4. EA di Azure memuat v3 + Reaper
az vm run-command invoke -g FOREX-MT5-RG -n mt5-trader-vm \
  --command-id RunPowerShellScript --scripts \
  'Get-Content "C:\Users\traderadmin\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Logs\$(Get-Date -Format yyyyMMdd).log" -Tail 12' \
  --query "value[0].message" -o tsv
# harapan: "...AutoTrader v3.0 siap berjalan" + "REAPER siap: sesi 08-09" + "sumber sinyal: REAPER"

# 5. uji
cd /home/admin/warroom && .venv/bin/python -m pytest services/*/tests -q
```

---

## 11. Aturan kerja user

- Bahasa Indonesia santai. Panggil asisten **"Mes"**.
- Suka didelegasikan penuh, tapi **menuntut angka nyata**. Koreksi diri terbuka kalau
  hasil membantah dugaan — dan tulis koreksinya di dokumen yang sama, jangan hapus.
- Minta "rumusan besar" (P0/P1/P2 + estimasi waktu) sebelum eksekusi besar.
- **Jangan sentuh kredensial/RDP** kecuali diminta eksplisit. Jangan pernah mencetak
  password ke chat.
- Tema tidak boleh diubah. Snapshot Azure tidak perlu. Tailscale tidak dipakai.
