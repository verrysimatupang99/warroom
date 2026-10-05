# Catatan: memindahkan BSJP + SMA10 dari Tencent (5 Okt 2026)

Dokumen ini mencatat **jalur akses, temuan kuota, dan pelajaran** dari kerja hari ini.
Ditulis di repo supaya tidak hilang bersama sesi.

---

## 1. Jalur masuk ke Hermes Tencent

```
Host      : 43.155.219.37  (VM-0-10-ubuntu, Ubuntu)
User      : ubuntu
Kunci     : /etc/warroom/tencent_ed25519     (mode 600, milik user `admin`)
Sumber    : disalin dari /etc/poly-pilot/backup_ed25519
```

**Kenapa perlu disalin:** kunci aslinya `root:root 600`, sementara `warroom-worker` berjalan
sebagai user `admin` — jadi worker tidak bisa membacanya. Perbaikannya **bukan** melonggarkan
izin kunci asli, melainkan:

1. salin ke path milik `admin` dengan mode tetap **600**, dan
2. beri grup `sudo` akses ke direktorinya (`/etc/warroom`, `root:sudo 750`).

Catatan jebakan: grup bernama `admin` di sistem ini (**gid 110**) **bukan** grup dari user
`admin` (user itu ada di `sudo`, gid 27). Memakai `chgrp admin` akan gagal dengan cara yang
membingungkan — izin terlihat benar tapi tetap "Permission denied".

Uji: `ssh -i /etc/warroom/tencent_ed25519 ubuntu@43.155.219.37 'hostname'` → `VM-0-10-ubuntu`.

---

## 2. Kuota Arjum: siapa yang sebenarnya memakainya

Angka mengalahkan dugaan. Dari audit di Tencent untuk 5 Okt:

| Sumber | Panggilan | Catatan |
|---|---|---|
| `history_yf` | 1.740 | |
| `history` | 1.447 | |
| `financial_statements` | 20 | |
| `screener` | 4 | |
| `broker_accumulation` | 2 | |
| **Total** | **3.214** | 0 cache hit |

Dan `~/.hermes/scripts/.arjum_rate_state.json` mencatat `{"date":"2026-10-05","used":967}` —
angka **967 itu persis** yang muncul di dashboard Arjum. Jadi pemakainya memang **Tencent**,
bukan box warroom (warroom hanya ~29 panggilan hari itu).

**Yang penting: `history` + `history_yf` = 3.187 dari 3.214 = 99%.** Jadi 22 job IDX yang
di-pause menghemat sedikit; yang menguras kuota adalah dua endpoint riwayat itu.

**Cara menghitung yang benar** (dari skill `trading-api-platform-selection`):
> *"Count the scripts that import the client, not the jobs that look related.
> Job counts overstate demand badly."*

Diterapkan: dari 122 berkas `.py` di `scripts/`, hanya **1** yang benar-benar
`import arjum_client` (`idx_flow_collect.py`). Menghitung "job yang menyentuh IDX" (6) —
seperti yang saya lakukan pertama kali — membuat angka terlihat 6× lebih besar dari kenyataan.

---

## 3. Aset tak terduga: arsip tick running-trade

```
Berkas : /home/ubuntu/.hermes/cron/state/arjum_trades.db
Ukuran : 5,0 GB
Tabel  : trades        24.964.749 baris   (ts, ticker, action, price, lot, value_idr, change_pct, tn)
         top5             281.543 baris
         market               246 baris
         daemon_state           6 baris
Indeks : idx_trades_ticker_ts, idx_trades_ts
Sumber : wss://stock.arjum.com/ws/running-trade  (WebSocket — TIDAK memakai kuota REST)
```

Dua hal yang menyelamatkan waktu:

1. **Pakai indeks.** `ts LIKE '2026-09%'` → **0,5 detik**. `substr(ts,1,10) >= '2026-09-01'`
   → **50+ detik** (memindai 24,9 juta baris, indeks tidak terpakai). Perbedaan frasa kueri =
   100× waktu.
2. **Pecah per ±15 emiten.** Satu kueri `ticker IN (...)` dengan puluhan emiten timeout.

Cacat data yang harus disaring: **2,6 juta tick (~10%) tidak punya tanggal**
(`length(ts) <= 8`). Memakainya akan mencampur hari secara acak. 22,3 juta sisanya bertanggal
lengkap (16.889 hari bursa).

**Batas:** tick ini cukup untuk BSJP (open/close/high/low/volume/tekanan beli-jual), **tidak**
untuk bandarmologi — identitas broker tidak ada di tick.

---

## 4. Pelajaran yang paling mahal

**Baca skill dulu sebelum mendiagnosis.** Bug "kuota beku" yang saya temukan dari nol hari ini
sudah tertulis di skill `finance/trading-api-platform-selection`:

> *"A sibling client that books usage only on the success path goes blind exactly when it
> matters. After a 429 the state file freezes and later status calls report a healthy balance.
> Read the recorded date before trusting a local count: stale makes it a floor, not a total."*

Itu `_kuota_basi()` yang saya tulis, kata per kata. Tiga kesalahan hari ini berasal dari satu
kebiasaan yang sama — melompat ke diagnosis sebelum membaca:

1. Menduga QuantDinger yang memakai kuota → salah, Tencent yang memakai.
2. Menghitung "6 job menyentuh IDX" → salah, yang benar 1 script yang `import`.
3. Menduga "BSJP butuh 24 juta tick" → salah, BSJP tidak menyentuh Arjum sama sekali untuk
   harga (pakai TradingView); yang diperlukan cuma SMA10.

---

## 5. Hasil: BSJP kini terukur

Filter dipindah apa adanya dari `idx_bsjp_watch.py` (Tencent):

```
ARA    : chg 2–25%, harga > Rp100, nilai ≥ Rp1 M, rel-vol ≥ 1,5×   → net +1,06%/trade
STRONG : subset ARA + close ≥ 1,03× SMA10 + chg 6–12%              → net +0,86%/trade
COST   : 0,40% round-trip (sudah dikurangkan di sumber)
```

Sebelum: mode `proksi`, `edge_rata_pct=None` — fitur yang jujur tapi tidak berguna.
Sesudah: mode `bersumber`, 17 lolos (1 STRONG) dari 40, **dari nol panggilan kuota Arjum**.

Batasan yang tetap dikodekan: `net_est_pct` berasal dari walk-forward **di sumbernya**, jadi
`terverifikasi_di_warroom=False` dan mode `terukur` hanya muncul bila edge dihitung ulang di
sini. Kandidat tanpa SMA10 **ditolak**, bukan diloloskan — tier STRONG tidak punya dasar tanpa itu.
