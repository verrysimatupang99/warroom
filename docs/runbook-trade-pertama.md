# Runbook — trade pertama & buktinya

**Berlaku:** War Room forex, EA `WarRoom_AutoTrader_v3.1`, akun demo `416510164`,
XAUUSDm M5, sesi Reaper **08–09 jam server** (Senin–Jumat).
**Tujuan:** setiap trade tertutup punya jejak yang bisa diaudit — bukan hanya "EA bilang profit".

> Status 30 Okt 2026: **belum ada trade nyata**. Prosedur ini sudah diuji bagian
> baca-sajanya (telemetri, jurnal kosong, watchdog), tetapi **eksekusi pertama belum
> pernah terjadi**. Bagian "Setelah deal" baru boleh ditandai selesai setelah ada deal nyata.

---

## 1. T-30 menit sebelum sesi

Jalankan berurutan; berhenti di baris pertama yang gagal.

```bash
# 1. Layanan hidup
systemctl is-active warroom-api warroom-worker warroom-web nginx
systemctl --failed --no-legend          # harus kosong

# 2. Build web yang tersaji = commit yang diuji
cat /home/admin/warroom/apps/web/build/build-id.txt

# 3. Telemetri masuk (max harus dekat now)
sudo -u postgres psql -d warroom -tAc \
 "select max(observed_at), now() from facts where kind='mt5_snapshot';"

# 4. Watchdog baru berjalan (setelah deploy 30 Okt)
sudo -u postgres psql -d warroom -c \
 "select name, last_run_at, last_status, last_detail from jobs
  where name='forwardtest-watchdog';"

# 5. Status mesin Reaper terakhir (butuh cookie sesi; lihat §1.1)
curl -sS -b /tmp/wr.cookie https://0xgunsl1ng3r.xyz/api/v1/tencent/mt5/status | jq \
 '{connected, account, balance, eval_sesi, eval_alasan, eval_atr, eval_spread,
   eval_rsi, eval_ema_fast, eval_ema_slow, eval_tren, server_time, eval_at}'

# 6. Tidak ada alert kritis terbuka
sudo -u postgres psql -d warroom -tAc \
 "select count(*) from alerts where ack_at is null and severity='kritis';"
```

Syarat lanjut:

| Cek | Syarat | Arti bila gagal |
|---|---|---|
| `eval_sesi` | `true` (saat 08–09) | EA di luar sesi → memang tidak akan entry |
| `eval_alasan` | memuat alasan evaluasi, bukan kosong | EA < v3.1 atau payload rusak |
| umur snapshot | ≤ 120 s | EA/terminal/koneksi mati — **jangan** menunggu |
| `spread_pts` | wajar terhadap `eval_atr` (spread ≪ ATR) | spread melebar; entry ditolak gate |
| alert kritis | 0 | selesaikan dulu, jangan menambah variabel |

### 1.1 Ambil cookie sesi (sekali per sesi browser/curl)

Kredensial ada di `~/.config/warroom/e2e.env` (600). Jangan menempel isinya ke chat/log.

```bash
set -a; . ~/.config/warroom/e2e.env; set +a
curl -sS -c /tmp/wr.cookie -X POST https://0xgunsl1ng3r.xyz/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$WARROOM_E2E_EMAIL\",\"password\":\"$WARROOM_E2E_PASSWORD\"}" | jq
```

---

## 2. Selama sesi

1. Buka `https://0xgunsl1ng3r.xyz/forex` → tab **Sinyal** → panel **Status mesin Reaper**.
   Yang dibaca: sesi, alasan evaluasi, ATR, spread, RSI, EMA21/55, tren M15, umur evaluasi.
2. Buka `https://0xgunsl1ng3r.xyz/jurnal` → tab **Trade**.
3. **Jangan menambah posisi manual** saat uji. Satu variabel berubah = satu kesimpulan.
4. Alert yang mungkin muncul (dari `forwardtest-watchdog`, interval 60 s):

| Subjek | Ambang | Arti | Tindakan |
|---|---|---|---|
| `forwardtest/telemetri` | umur snapshot > 120 s **dan** jam server 08–09 hari kerja | EA berhenti mengirim | cek terminal Azure, AutoTrading, koneksi broker; jangan restart buta |
| `forwardtest/deal-hilang` | `total_trades_today` EA > baris `deals.csv` selama > 5 menit | deal tertutup tidak tercatat | cek log EA `POST /mt5/deal`, cocokkan statement MT5 |

Alert ini **tidak** mengubah posisi dan tidak mengirim order. Kalau condition pulih,
alert ditutup otomatis dengan akhiran `PULIH otomatis` — bukan di-ack manual.

---

## 3. Setelah deal tertutup (dalam 5 menit)

### 3.1 Berkas deal

```bash
# Harus ada tepat satu baris baru per posisi tertutup (idempoten per ticket)
sudo -n tail -n 3 /var/lib/warroom/deals.csv

# Net = profit + swap + commission; bukan profit saja
sudo -n python3 - <<'PY'
import csv
from pathlib import Path
rows = list(csv.DictReader(Path('/var/lib/warroom/deals.csv').open()))
for r in rows[-3:]:
    net = float(r['profit']) + float(r['swap']) + float(r['commission'])
    print(r['ticket'], r['symbol'], r['side'], r['close_time'],
          f"profit={r['profit']} net={net:.2f}", "COCOK" if abs(net-float(r['net']))<0.011 else "SELISIH")
PY
```

### 3.2 Jurnal & API

```bash
curl -sS -b /tmp/wr.cookie 'https://0xgunsl1ng3r.xyz/api/v1/journal/trades?market=forex' | jq \
 '.closed[-1], .entries[-1]'
curl -sS -b /tmp/wr.cookie 'https://0xgunsl1ng3r.xyz/api/v1/journal/stats?market=forex' | jq
```

Yang harus benar:

- `closed[-1].ticket` = ticket deal yang baru;
- `net` di jurnal = net di `deals.csv` (selisih > $0,01 = **gagal**, bukan pembulatan);
- `entries` memuat fill order masuk (kalau EA mengirim `/mt5/fill`);
- `/journal/edge` boleh 503 **hanya** bila `fills.csv` benar-benar kosong.

### 3.3 Status DoD

```bash
cd /home/admin/warroom && .venv/bin/python tools/forwardtest_status.py
```

Angka yang diharapkan setelah trade pertama: `Trade tertutup 1/20`, `Deal hari ini 1`,
`Fill belum deal 0` (kalau fill entry tercatat), `Deal tanpa fill 0`.

### 3.4 Watchdog & alert

```bash
sudo -u postgres psql -d warroom -c \
 "select id, created_at, severity, subject, message, ack_at
  from alerts where subject like 'forwardtest/%' order by id desc limit 5;"

sudo -u postgres psql -d warroom -c \
 "select last_run_at, last_status, last_detail from jobs
  where name='forwardtest-watchdog';"
```

`last_detail` harus menunjukkan `selisih=0` setelah deal tercatat.

---

## 4. Bukti yang wajib disimpan

Simpan di `artifacts/sprint-1/trade-<ticket>/` (jangan commit berkas berisi kredensial):

| Berkas | Isi | Sumber |
|---|---|---|
| `deal.txt` | baris `deals.csv` untuk ticket itu | §3.1 |
| `jurnal.json` | keluaran `/journal/trades?market=forex` | §3.2 |
| `status.json` | keluaran `/journal/stats?market=forex` | §3.2 |
| `forwardtest.txt` | keluaran `tools/forwardtest_status.py` | §3.3 |
| `alert.sql.txt` | keluaran query alert + job | §3.4 |
| `layar.png` | tab Sinyal + tab Trade (satu tangkapan per tab) | browser |

Catat di `docs/sprint-1.md`:

```
ticket=… position=… symbol=XAUUSDm side=… volume=…
open=… close=… net=… (profit … + swap … + komisi …)
alert=… (id atau "tidak ada")   watchdog_detail=selisih=0
bukti=artifacts/sprint-1/trade-…/
```

---

## 5. Rollback / berhenti

Tidak ada perubahan kode dalam prosedur ini. Bila EA berperilaku salah:

1. Matikan **AutoTrading** di terminal (atau hapus EA dari chart) — bukan mengubah gate.
2. Biarkan `warroom-api`/`worker` hidup: telemetri dan jurnal tetap merekam.
3. Tulis temuan apa adanya di `docs/sprint-1.md`; jangan menutup alert tanpa alasan.
4. Rollback EA hanya bila perlu: `WarRoom_AutoTrader_v3.ex5.v30bak` di data folder Azure
   (lihat `HANDOVER-OMP.md` §9 untuk jebakan Strategy Tester).

---

## 6. Batas yang diketahui

- `deals.csv` hanya memuat deal yang **dilaporkan EA**. Deal yang dibuka/ditutup manual di
  terminal bisa muncul sebagai `deal_tanpa_fill`; itu label, bukan tuduhan kehilangan.
- `fills.csv` mencatat order yang dikirim War Room; entry yang belum ditutup muncul sebagai
  `fill_belum_deal`. Jangan menyimpulkan "deal hilang" dari angka itu saja.
- Watchdog menilai sesi dari `server_time` EA + umur fakta. Bila EA mati berhari-hari,
  perkiraan jam server bergeser; alert pertama tetap muncul saat perkiraan jam masuk 08–09.
- Gate statistik (90% vs 95%+deff) masih keputusan owner; runbook ini tidak mengubahnya.
