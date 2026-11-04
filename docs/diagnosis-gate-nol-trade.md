# Diagnosis: gate selalu menolak, 0 trade (4 Nov 2026)

Dokumen ini menjawab satu pertanyaan yang diajukan owner: **kenapa War Room belum
pernah membuka trade?** Sampai awal penelusuran, `trades` = 0, `verdicts` = 0,
dan `paper-scan` melaporkan `kandidat=0 dibuka=0` setiap siklus.

Semua angka di bawah dari perintah nyata pada 4 Nov 2026 pukul 11.15–11.30 UTC.
Tidak ada angka yang dikira-kira.

---

## 0. Ringkas untuk owner

**War Room tidak "rusak". Sinyal memang diproduksi — 572 dari 1.014 verdict
berstatus `allowed=true`.** Yang terjadi ialah **gate risiko `exposure`
menolak kandidat dengan alasan yang salah**, dan itu berlangsung sejak
**30 Oktober 2026**.

Rantainya:

```
sumber data → sinyal → verdict ALLOWED=True  →  gate exposure: "2/2 searah"  →  SKIP
                          (572 sinyal sah)        (padahal posisi cuma 1)
```

Jadi bukan gate-nya terlalu ketat, dan bukan datanya mati. Gate menilai
jumlah posisi terbuka lebih besar dari kenyataan.

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

## 8. Langkah berikut yang disarankan

1. Telusuri jalur `paper-scan` sampai pemanggilan `assess()`/`evaluate()` untuk
   menemukan dari mana entri posisi kedua berasal (hipotesis §5.1–5.2).
2. Tambahkan uji regresi: bila `paper_positions.json` berisi N posisi,
   `exposure` **wajib** melihat tepat N — bukan N+1.
3. Setelah diperbaiki, jalankan satu siklus `paper-scan` dan pastikan ada
   kandidat yang benar-benar dibuka, lalu periksa `trades` bertambah.

**Jangan longgarkan `MAX_SAME_DIRECTION`** untuk "menghijaukan" hasil. Itu arah
melonggarkan risiko, dan dilarang AGENTS.md §6.
