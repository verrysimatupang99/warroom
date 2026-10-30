# Laporan sinyal terkirim — 16–30 Okt 2026

**Pertanyaan:** dari sinyal yang benar-benar dikirim ke Telegram, mana yang bagus dan mana
yang tidak? **Jawaban singkat:** catatannya ada di tiga tempat, dan setelah digabungkan:
**54,7% TP1, expectancy +0,173R per trade terisi (gross), +56,93R total** — positif, tetapi
hanya tier PREMIUM yang punya edge yang terlihat; STANDAR mendekati break-even sebelum biaya.

## Sumber catatan

| Sumber | Isi | Lokasi |
|---|---|---|
| `alerts` (Postgres) | 451 alert `sinyal/<PAIR>/<SIDE>` yang dikirim, 16–30 Okt; subjek, pesan, waktu, status kirim | tabel `alerts` |
| `verdicts.jsonl` | 787 keputusan mesin: pair, arah, tier, entry/SL/TP1, `allowed`, aturan gagal | `/home/admin/live-trading/state/verdicts.jsonl` |
| `outcomes.jsonl` | 784 hasil maju per verdict: `tp1`/`sl`/`tidak_terisi`/`kedaluwarsa`/`terbuka` + R | `/home/admin/live-trading/state/outcomes.jsonl` |
| Laporan agregat | `lt measure` — gate berguna atau tidak, termasuk kandidat ditolak | `.venv/bin/lt measure` |

Jurnal tergabung permanen sudah ada: job `jurnal-sinyal` (tiap 6 jam) menjalankan
`lt measure` lalu menghitung ulang setiap alert dari candle Binance sejak jam setelah
kirim. Hasilnya ditulis ke `/var/lib/warroom/jurnal_sinyal.json`, dibaca
`/api/v1/journal/signals`, dan tampil di `/crypto?sub=sinyal` panel **Jurnal sinyal
terkirim**. Angka di bawah berasal dari jurnal itu (`dihitung_at` 30 Okt 21:06 UTC).

## Hasil sinyal yang terkirim — divalidasi ulang dengan data asli saat kirim

451 alert → **450 verdict unik** (1 alert duplikat). Angka di bawah **bukan cache**:
setiap alert diuji ulang dengan candle 1H Binance mulai dari **jam penuh setelah alert
dikirim** (penerima tidak bisa mengisi sebelum pesan sampai). Aturan sama: entry limit,
TP1=1R, SL swing, isi maks 8 jam, tahan 24 jam, SL didahulukan bila kena di candle sama.

| Hasil | n | Arti |
|---|---:|---|
| TP1 | 182 | kena target 1R |
| SL | 129 | kena stop |
| Tidak terisi | 116 | harga tidak menyentuh entry dalam 8 jam (0R, bukan rugi) |
| Kedaluwarsa | 17 | tahan 24 jam tanpa TP/SL |
| Terbuka | 6 | belum selesai saat laporan |

**Dihitung dari yang terisi (n=334):**
- Win rate TP1: **54,5%**
- Total: **+54,51R**
- Expectancy: **+0,163R/trade**
- Median: **+1,00R**

**Kalau yang tidak terisi dihitung 0R (n=450):** expectancy **+0,122R**.
25,8% sinyal yang dikirim tidak pernah bisa dimasuki.

### Per tier (data asli saat kirim)

| Tier | n terkirim | n terisi | TP1 | SL | Win rate | Expectancy |
|---|---:|---:|---:|---:|---:|---:|
| PREMIUM | 213 | 157 | 92 | 48 | **58,6%** | **+0,286R** |
| STANDAR | 237 | 177 | 90 | 81 | 50,8% | +0,054R |

PREMIUM adalah satu-satunya tier dengan edge yang cukup jelas. STANDAR **negatif setelah
biaya** (lihat di bawah).

### Setelah biaya (fee taker Binance 0,05%/sisi)

Biaya per trade dalam R = `(2 × fee × entry) / jarak SL`. Rata-rata biaya di jurnal ini
**0,061R/trade** (SL sekitar 1–2% dari harga).

| Kelompok | Gross | Net | Expectancy net |
|---|---:|---:|---:|
| Semua (n=334) | +54,51R | **+34,01R** | **+0,102R** |
| PREMIUM (n=157) | +44,93R | +36,08R | **+0,230R** |
| STANDAR (n=177) | +9,59R | **−2,07R** | **−0,012R** |

Kalau yang tidak terisi dihitung 0R: expectancy net **+0,076R**.
Uji stres 0,10%/sisi: semua **+0,042R**, PREMIUM **+0,177R**, STANDAR **−0,078R**.

Artinya: **PREMIUM tetap positif setelah biaya; STANDAR tidak.** Rekomendasi keras:
hentikan pengiriman tier STANDAR atau naikkan syaratnya sampai gross expectancy-nya
lebih dari biaya.

### Cache vs data asli saat kirim

`outcomes.jsonl` lama dihitung dari **waktu verdict**, bukan waktu pesan dikirim.
Hasilnya **97,8% sama** (440/450), tetapi 10 kasus berbeda dan arahnya masuk akal:

| Kasus | Cache (dari verdict) | Asli (mulai setelah kirim) | Penyebab |
|---|---|---|---|
| CRVUSDT, INJUSDT 18 Okt | TP1 | **SL** | TP1 kena sebelum pesan terkirim |
| INJUSDT 20 Okt | kedaluwarsa −0,249R | **SL** | pergerakan setelah kirim berbeda |
| FILUSDT 21 Okt | tidak terisi | **SL** | entry baru terisi setelah pesan dikirim |
| 1000PEPEUSDT 21 Okt | tidak terisi | **TP1** | fill terjadi setelah kirim |
| TIAUSDT 24 Okt, SKHYNIXUSDT 28 Okt, SUIUSDT 30 Okt | tidak terisi | **TP1** | idem |

Kesimpulan validasi: angka cache **tidak bohong secara agregat** (selisih expectancy
+0,173R → +0,163R), tetapi untuk menilai satu sinyal tertentu, waktu kirim harus dipakai.
Sinyal yang telat dikirim bisa kehilangan TP1 yang sudah terjadi lebih dulu.

## Pembanding: seluruh kandidat (bukan hanya yang dikirim)

`lt measure` pada 787 kandidat:
…
| Kelompok | n | TP1 | SL | Win rate | Expectancy | Total |
|---|---:|---:|---:|---:|---:|---:|
| Lolos gate | 381 | 203 | 150 | 53,3% | +0,142R | +54,00R |
| Ditolak (bayangan) | 201 | 77 | 85 | 38,3% | −0,040R | −8,10R |

Gate menyaring ke arah yang benar: kandidat ditolak memang lebih buruk. Tetapi per aturan
belum ada yang terbukti:
- `atr_min` menolak 210 kandidat dengan expectancy +0,03R (t=0,48) — tidak bisa dibedakan
  dari derau.
- `sl_distance` n=25, −0,27R, t=−1,63 — belum cukup bukti.
- `freshness`/`exposure` sampelnya terlalu kecil.

## Observasi per pair (jangan dijadikan patokan tunggal)

Kuat (n≥13): FILUSDT n=22 +0,545R; ORDIUSDT n=13 +0,421R; SEIUSDT n=27 +0,363R;
CRVUSDT n=28 +0,324R.

Lemah (n≥10): LINKUSDT n=10 −0,485R; TIAUSDT n=13 −0,128R; ENAUSDT n=30 −0,067R;
AAVEUSDT n=20 −0,049R.

Pair dengan n kecil dan beberapa perbandingan sekaligus mudah terlihat “bagus” karena
kebetulan. Jangan memilih pair hanya dari tabel ini.

## Batas kejujuran

1. **Ini hasil bayangan, bukan trade nyata.** Entry di POI, TP1 = 1R, SL = swing,
   expired 8 jam, tahan maksimum 24 jam; jika TP dan SL kena di candle yang sama,
   dihitung SL (konservatif).
2. **Biaya sudah dihitung** dengan fee taker 0,05%/sisi; kolom net ada di jurnal.
   Uji stres 0,10%/sisi juga dicatat. Slippage nyata dari `fills.csv` belum ada karena
   belum ada trade.
3. **Sampel 15 hari / 334 hasil terisi.** Cukup untuk sinyal awal, belum untuk mengunci
   strategi.
4. **Sinyal tetap kandidat**, bukan rekomendasi. Label ini sudah ikut di setiap pesan.
5. `jurnal-sinyal` menyegarkan `outcomes.jsonl` lewat `lt measure` setiap 6 jam; kalau
   Binance gagal, jurnal memakai cache lama dan mencatat `catatan` di berkasnya.

## Cara melihat ulang

```bash
# 1. Jurnal permanen (API, butuh cookie sesi)
curl -sS -b /tmp/wr.cookie https://0xgunsl1ng3r.xyz/api/v1/journal/signals | jq .ringkas

# 2. Tampilan: /crypto?sub=sinyal → panel "Jurnal sinyal terkirim"

# 3. Ringkasan gate: lolos vs ditolak, per aturan
cd /home/admin/warroom && .venv/bin/lt measure

# 4. Alert sinyal yang benar-benar dikirim
sudo -u postgres psql -d warroom -c \
 "select created_at, subject, left(message,80)
  from alerts where subject like 'sinyal/%' order by id desc limit 20;"

# 5. Hasil per verdict
jq -c 'select(.allowed) | {ts,pair,direction,tier,hasil,r}' \
 /home/admin/live-trading/state/outcomes.jsonl | tail -20
```

## Rekomendasi

1. ~~Jadwalkan `lt measure`~~ **sudah**: job `jurnal-sinyal` menjalankannya tiap 6 jam.
2. ~~Buat jurnal sinyal permanen~~ **sudah**: JSON + API + panel UI + e2e.
3. **Hentikan/naikkan syarat tier STANDAR** — net expectancy −0,012R pada fee 5 bps/sisi,
   dan −0,078R pada 0,10%/sisi. Ini keputusan strategi; perlu persetujuan owner.
4. **Kurangi sinyal yang tidak terisi** — 25,8% tidak pernah masuk; filter jarak entry
   atau kirim hanya saat harga dekat POI.
5. **Ganti fee asumsi dengan slippage nyata** dari `fills.csv` setelah trade pertama.
