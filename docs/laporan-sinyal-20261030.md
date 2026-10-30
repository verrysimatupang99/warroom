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

Belum ada satu jurnal tergabung permanen. Angka di bawah dihasilkan dengan mencocokkan
alert terkirim ke verdict `allowed=true` dalam ±120 detik, dedupe per `(ts, pair, arah)`.

## Hasil sinyal yang terkirim

451 alert → **450 verdict unik** (1 alert duplikat). Rincian hasil:

| Hasil | n | Arti |
|---|---:|---|
| TP1 | 180 | kena target 1R |
| SL | 124 | kena stop |
| Tidak terisi | 121 | harga tidak menyentuh entry dalam 8 jam (0R, bukan rugi) |
| Kedaluwarsa | 19 | tahan 24 jam tanpa TP/SL |
| Terbuka | 6 | belum selesai saat laporan |

**Dihitung dari yang terisi (n=329):**
- Win rate TP1: **54,7%**
- Total: **+56,93R**
- Expectancy: **+0,173R/trade**
- Median: **+1,00R**

**Kalau yang tidak terisi dihitung 0R (n=450):** expectancy **+0,127R**.
Angka ini penting: 26,9% sinyal yang dikirim tidak pernah bisa dimasuki.

### Per tier

| Tier | n final | TP1 | SL | Win rate | Expectancy |
|---|---:|---:|---:|---:|---:|
| PREMIUM | 156 | 91 | 46 | **58,3%** | **+0,299R** |
| STANDAR | 173 | 89 | 78 | 51,4% | +0,059R |

PREMIUM adalah satu-satunya tier dengan edge yang cukup jelas. STANDAR praktis
break-even sebelum biaya; setelah fee/slippage kemungkinan negatif.

## Pembanding: seluruh kandidat (bukan hanya yang dikirim)

`lt measure` pada 787 kandidat:

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
2. **Belum dikurangi biaya.** R di atas gross. Fee + slippage 0,1%/sisi dapat memakan
   sebagian besar edge STANDAR.
3. **Sampel 15 hari / 329 hasil terisi.** Cukup untuk sinyal awal, belum untuk mengunci
   strategi.
4. **Sinyal tetap kandidat**, bukan rekomendasi. Label ini sudah ikut di setiap pesan.
5. `outcomes.jsonl` hanya segar setelah `lt measure` dijalankan; belum ada job terjadwal.

## Cara melihat ulang

```bash
# 1. Ringkasan gate: lolos vs ditolak, per aturan
cd /home/admin/warroom && .venv/bin/lt measure

# 2. Alert sinyal yang benar-benar dikirim
sudo -u postgres psql -d warroom -c \
 "select created_at, subject, left(message,80)
  from alerts where subject like 'sinyal/%' order by id desc limit 20;"

# 3. Hasil per verdict
jq -c 'select(.allowed) | {ts,pair,direction,tier,hasil,r}' \
 /home/admin/live-trading/state/outcomes.jsonl | tail -20
```

## Rekomendasi

1. **Jadwalkan `lt measure`** (harian) agar `outcomes.jsonl` tidak basi.
2. **Buat jurnal sinyal permanen** yang menggabungkan alert + outcome + status kirim,
   supaya angka di atas bisa dibuka tanpa skrip ad-hoc.
3. **Pertimbangkan tier STANDAR** — kalau setelah biaya tetap ≤0, kurangi/hentikan
   pengirimannya, atau naikkan syaratnya.
4. **Kurangi sinyal yang tidak terisi** — 26,9% tidak pernah masuk; filter jarak entry
   atau kirim hanya saat harga dekat POI.
