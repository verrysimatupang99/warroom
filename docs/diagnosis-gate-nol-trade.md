# Diagnosis: gate selalu menolak, 0 trade (4 Nov 2026)

Dokumen ini menjawab satu pertanyaan yang diajukan owner: **kenapa War Room belum
pernah membuka trade?** Sampai awal penelusuran, `trades` = 0, `verdicts` = 0,
dan `paper-scan` melaporkan `kandidat=0 dibuka=0` setiap siklus.

Semua angka di bawah dari perintah nyata pada 4 Nov 2026 pukul 11.15–11.30 UTC.
Tidak ada angka yang dikira-kira.

---

## 0. Ringkas — dan KOREKSI atas kesimpulan awal

> **Versi pertama dokumen ini salah.** Ia menyimpulkan "gate `exposure` menghitung
> posisi salah". Setelah ditelusuri sampai ujung, kesimpulan itu **dibatalkan**.
> Ringkasan yang benar ada di §0b di bawah; §1–§8 dipertahankan apa adanya sebagai
> jejak penelusuran, dan §0b yang mengikat.

**Sinyal memang diproduksi — 572 dari 1.014 verdict berstatus `allowed=true`.**
Dalam 27 verdict enam jam terakhir, semuanya ditolak gate `exposure` dengan
alasan `2/2 posisi searah SHORT`.

## 0b. Kesimpulan yang benar (menggantikan §0)

Tiga fakta yang membalik diagnosis awal:

1. **Trade ADA dan berjalan.** `crypto_equity.jsonl` berisi **106 trade tertutup**
   (+54 R), termasuk **5 trade pada 4 Nov** (ENA +1R; TIA, AAVE, WIF, CRV masing
   −1R). Sistem tidak beku sejak 30 Okt.
2. **Gate `exposure` benar.** Dijalankan dengan posisi nyata sekarang:
   `ok=True, "1/3 posisi, 1/2 searah — aman"`. Saat verdict `2/2` ditulis
   (05:00–10:16 UTC), memang **ada 2 posisi SHORT terbuka** — empat trade ditutup
   12:46–17:30 WIB (05:46–10:30 UTC), persis jendela itu. Konfigurasi juga benar:
   `maks_posisi_searah=2`, `max_concurrent_positions=3`.
3. **Yang bermasalah: 106 trade di ledger tidak masuk DB.** `trades`=0,
   `verdicts` DB=0, `fills.csv` hanya header sejak 24 Okt — sementara ledger
   penuh. Karena itu War Room **tampak** belum pernah trading.

**Jadi masalahnya pelaporan/ingest, bukan mesin gate.** Langkah berikut ada di §9.


---

## 1. Bukti bahwa sinyal ADA

`/home/admin/live-trading/state/verdicts.jsonl` — 1.014 baris, 14 Okt s/d 4 Nov.

| Field | Sebaran |
|---|---|
| `allowed` | **True: 572**, False: 442 |
| `tier` | STANDAR: 295, PREMIUM: 277, SKIP: 442 |
| `strategy` | `legacy-smc` (tunggal) |

Verdict `allowed=true` terakhir: **2026-11-04T01:01:43Z**, pair `CRVUSDT`,
tier STANDAR. Jadi sistem pernah menyetujui sinyal — pagi ini juga.

**Ini membatalkan hipotesis awal** bahwa gate terlalu ketat atau data tidak
sampai. Datanya sampai, sinyalnya dihasilkan.

## 2. Tapi dalam 6 jam terakhir, NOL yang lolos

27 verdict terakhir (jendela yang dibaca `signal-sync`, 6 jam):

```
allowed: False 27/27
tier:    SKIP  27/27
```

Karena itu `signal-sync` melaporkan `sinyal=0`

Alasan penolakan — **satu aturan mendominasi mutlak**:

| Aturan gagal | Jumlah | Alasan |
|---|---|---|
| **`exposure`** | **27/27** | `2/2 posisi searah SHORT — korelasi terlalu tinggi` |
| `atr_min` | 3 | `ATR1H 0.94% < 1.0%` |

## 3. Kontradiksi inti: klaim gate vs kenyataan posisi

Gate bilang "2 posisi SHORT". Kenyataannya:

```
$ PaperBroker(settings, venue="crypto").positions()
posisi terbuka: 1
  SOLUSDT SHORT  entry 92.42  opened_at 2026-11-03T07:04:09+07:00
```

Venue lain kosong: forex 0, idx 0, polymarket 0.

`/home/admin/live-trading/state/paper_positions.json`:

```json
{ "updated_at": "2026-11-04T17:30:08+07:00",
  "positions": [ { "pair": "SOLUSDT", "direction": "SHORT", "status": "open" } ] }
```

**Satu posisi, bukan dua.**

Reproduksi langsung gate dengan data hidup:

```python
ps = [p.to_dict() for p in PaperBroker(s, venue="crypto").positions()]
gates.exposure("SHORT", ps, None)
# -> ok=True, reason="1/3 posisi, 1/2 searah — aman"
```

Gate **meloloskan** saat dijalankan sekarang. Artinya saat scan berjalan,
`open_positions` yang dikirim berisi dua entri — padahal hanya satu yang ada.

## 4. Kapan ini mulai

Verdict yang memakai alasan `2/2`: **107 kali**, sejak
**2026-10-30T13:01:34Z** sampai **2026-11-04T10:16:15Z** (hari ini).

Tanggal 30 Okt itu tanggal yang sama dengan catatan AGENTS.md:

> "insiden OPUSDT 30 Okt: verdict 0/2 padahal 2 SHORT terbuka"

Dan komentar di `signals/engine.py:561-563` menyebut perbaikan untuk insiden itu:
`posisi_paper_crypto()` dibuat supaya gate melihat sumber posisi yang sama
dengan executor. Perbaikan itu **membuat gate melihat posisi**, tetapi sejak itu
gate konsisten melaporkan **satu posisi lebih banyak dari yang ada**.

## 5. Hipotesis yang belum tertutup

Perlu diuji, urut dari paling mungkin:

1. **Ada pembaca kedua yang menambahkan posisi sintetis.** `engine.py:668` dan
   `:756` juga menerima `open_positions=`; jalur mana yang dipakai `paper-scan`
   belum ditelusuri sampai ujung.
2. **`scan()` memanggil `posisi_paper_crypto()` sekali di awal**, lalu menambah
   posisi baru di tengah loop tanpa membuang yang lama — sehingga kandidat
   pertama menambah, kandidat kedua melihat akumulasi.
3. ~~**Dua proses worker berjalan bersamaan**~~ — **sudah diuji, gugur.**
   `pgrep -f warroom_worker` → 1 proses (PID 47561). `paper-scan` berjalan 3×
   dalam 10 menit, tidak ada tumpang tindih proses.

## 6. Yang TIDAK menjadi penyebab

Dibuktikan agar tidak diulang mencarinya:

- **Gate terlalu ketat** — `gate.ci=0,9` / `min_n=30` tidak dipakai di jalur ini;
  penolakan datang dari `exposure`, bukan ambang statistik.
- **Data berhenti** — `facts` 111.103 baris, terakhir 11:18 (masih mengalir).
- **Worker mati** — semua job `ok`, 0 error 24 jam, 0 alert.
- **Tidak ada sinyal** — 572 verdict `allowed=true` membuktikan sebaliknya.

## 7. Dampak

- **Kripto paper trading praktis beku sejak 30 Okt** (5 hari).
- `trades` = 0 dan `verdicts` DB = 0, jadi tidak ada satu pun hasil yang bisa
  dievaluasi. Seluruh kerja platform tidak bisa dibuktikan berguna.
- `fills.csv` hanya header sejak 24 Okt — konsisten dengan tidak ada eksekusi.

## 8. Langkah yang disarankan (versi pertama — digantikan §9)

1. ~~Telusuri jalur `paper-scan` sampai `assess()`~~ — **selesai**, lihat §9.
2. ~~Uji regresi `exposure` melihat N bukan N+1~~ — **tidak diperlukan**, gate
   sudah terbukti benar dengan N=1 → `1/2 searah — aman`.
3. Pastikan kandidat dibuka & `trades` bertambah — **arah yang benar**, tapi
   sebabnya bukan gate; lihat §9.

**Jangan longgarkan `MAX_SAME_DIRECTION`** untuk "menghijaukan" hasil. Itu arah
melonggarkan risiko, dan dilarang AGENTS.md §6.

---

## 9. Penelusuran lanjutan (4 Nov, sesi yang sama) — hasil akhir

**Hipotesis §5.1–5.2 gugur semua.**

| Yang diperiksa | Hasil |
|---|---|
| `scan()` mengakumulasi posisi? | **Tidak.** `posisi_paper = posisi_paper_crypto(settings)` dipanggil sekali di `engine.py:564`, di luar loop pair. |
| Dua worker bentrok? | **Tidak.** `pgrep -f warroom_worker` → 1 proses (PID 47561). |
| Gate menghitung salah? | **Tidak.** `assess(... open_positions=[SOLUSDT])` → `exposure ok=True "1/3 posisi, 1/2 searah — aman"`. |
| Konfigurasi salah? | **Tidak.** `maks_posisi_searah=2`, `max_concurrent_positions=3`. |

**Penjelasan yang benar untuk `2/2`:** saat 27 verdict itu ditulis
(05:00–10:16 UTC), memang ada dua posisi SHORT terbuka. Ledger
`crypto_equity.jsonl` mencatat empat trade ditutup **12:46–17:30 WIB
(05:46–10:30 UTC)** — persis jendela tersebut. Setelah ditutup, posisi tinggal
satu dan gate kembali meloloskan. Tidak ada bug.

**Akar masalah sebenarnya:** `handler_paper_scan` mengambil kandidat dari
`verdicts.jsonl`. Dijalankan pada data nyata:

```
_kandidat_terbaru_dari_ledger(stg, jam_terakhir=6) -> 0 kandidat
_pair_sudah_dipakai(stg, jam=12) -> {SOLUSDT, CRVUSDT, AAVEUSDT, ENAUSDT, WIFUSDT, TIAUSDT}
```

Nol kandidat karena 6 jam terakhir tidak ada verdict `allowed=true` (sah: dua
posisi penuh), dan enam pair terkunci jeda 12 jam. `paper-scan` melaporkan
`kandidat=0` dengan benar — ia memang tidak punya pekerjaan saat itu.

**Dan trading tetap jalan** lewat jalur lain: **106 trade** di ledger,
**+54 R**, termasuk **5 trade hari ini**. Yang tidak jalan adalah **pencatatan
ke DB/platform**:

| Sumber | Jumlah |
|---|---|
| `crypto_equity.jsonl` (ledger) | **106 trade**, +54 R |
| `trades` (PostgreSQL) | **0** |
| `verdicts` (PostgreSQL) | **0** |
| `fills.csv` | 1 baris (header), sejak 24 Okt |

### Kesimpulan akhir

**Mesin trading sehat; yang rusak adalah penyampaian hasilnya ke platform.**
Selama 106 trade tidak masuk `trades`, dashboard akan selalu tampak "belum
pernah trading", dan tidak ada satu pun hasil yang bisa dievaluasi — padahal
datanya ada.

**Langkah berikut yang benar:** telusuri kenapa `crypto_equity.jsonl` tidak
di-ingest ke tabel `trades` (cek job `publish-facts`, dan apakah `trades` hanya
diisi jalur live alih-alih paper). **Bukan** mengubah gate.
