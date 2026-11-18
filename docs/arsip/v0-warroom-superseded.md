# War Room v0 — desain dari nol

Bukan migrasi. Ini cetak biru bersih: kalau hari ini kita mulai project ini tanpa warisan
apa pun, ini yang dibangun. Sistem lama tetap jalan sampai v0 terbukti.

---

## 1. Satu kalimat

**War Room adalah satu tempat untuk menjalankan strategi di beberapa market, dengan jejak
yang bisa diaudit.**

Kalau sebuah fitur tidak membantu salah satu dari dua hal itu — menjalankan, atau
membuktikan — fitur itu tidak masuk v0.

## 2. Satu lingkaran inti (7 langkah)

```
1 FEED      data masuk: harga, status akun, jam sesi
2 SIGNAL    strategi memutuskan: entry, atau menolak (dengan alasan)
3 DECISION  gate: risiko, exposure, sesi, batas harian
4 ORDER     dikirim ke venue
5 POSITION  terbuka, dikelola: SL, TP, BE, trailing
6 LEDGER    uang tercatat: PnL, fee, swap
7 REVIEW    jurnal → verdict → usul parameter
```

Semua halaman adalah jendela ke salah satu langkah ini. Tidak ada halaman ke-8.

## 3. Lingkup v0 (sengaja sempit)

| | v0 | Nanti |
|---|---|---|
| Market | **1: forex** | crypto, polymarket, idx, on-chain |
| Akun | **1 demo** | live, akun kedua |
| Strategi | **1 engine** | multi-strategi, A/B |
| Peran | **1 pengguna (owner)** | peneliti, penonton publik |
| Mode | baca + arm/confirm | otomasi penuh |

Aturan: **live tidak masuk sebelum demo jalan 14 hari tanpa intervensi manual.**

## 4. Entitas (10, bukan 28)

```
venue        — tempat: broker/exchange (code, name, tz)
account      — akun di venue (venue_id, label, currency, mode, status, cred_id)
instrument   — yang diperdagangkan (venue_id, symbol, kind, tick_size, contract_size)
strategy     — kode strategi (code, version, market, status)
signal       — keputusan (account, instrument, ts, side, decision, reason, gate_json)
order        — perintah (account, instrument, ext_id, side, qty, price, status)
position     — hasil (account, instrument, side, qty, entry, exit, sl, tp, pnl, r)
ledger_entry — uang (account, ts, kind, amount, currency, ref)
feed         — sumber data (code, provider, sla_seconds, last_ok_at, status)
event        — jejak (ts, actor, action, target, before, after)
```

Relasi:

```
venue 1—n account        venue 1—n instrument
account 1—n position     account 1—n ledger_entry
instrument 1—n signal    1—n order   1—n position
strategy 1—n signal
feed 1—n (instrument)    account 1—1 cred (vault)
```

Yang **tidak** ada di v0: `facts`, `research_*`, `verdict`, `proposal`, `dataset`,
`news`, `journal` terpisah, `services` (digabung ke `feed` sebagai status host).
Semuanya masuk v1 setelah lingkaran inti terbukti.

## 5. Halaman (6)

| Halaman | Menjawab | Isi minimum |
|---|---|---|
| `/` | "hari ini bagaimana?" | equity, PnL hari ini, posisi terbuka, status feed, tombol ke detail |
| `/pasar` | "apa yang dipantau?" | instrument + harga + spread + jam sesi + freshness |
| `/sinyal` | "kenapa entry / kenapa tidak?" | semua keputusan, `reason`, nilai gate (atr, rsi, spread, sesi) |
| `/posisi` | "apa yang terbuka?" | entry, SL, TP, jarak SL, R berjalan, umur |
| `/jejak` | "dari mana angka ini?" | tab 1 ledger (mutasi), tab 2 audit (siapa mengubah apa) |
| `/sistem` | "kalau kosong, siapa salah?" | feed (umur, SLA, error) + service (jalan/mati) |

Aturan keras:
- Setiap halaman menampilkan **umur data**. Lebih tua dari SLA → kuning, 3× SLA → merah.
- `/sinyal` dan `/sistem` wajib bisa dibuka dari halaman mana pun (satu klik).
- Tidak ada tombol yang menyentuh uang tanpa `Arm → Confirm`.

## 6. Aturan yang tidak boleh dilanggar

1. **Tabel bertipe, bukan `facts` serba bisa.** Data mentah boleh masuk tabel staging
   dengan TTL, tapi halaman hanya membaca tabel bertipe.
2. **Kredensial tidak pernah di tabel domain.** `account` menyimpan referensi vault,
   bukan password.
3. **Satu mesin hitung uang.** PnL/fee/swap dihitung di satu modul; halaman hanya menampilkan.
4. **Semua tulis → `event`.** Kalau tidak tercatat, dianggap tidak terjadi.
5. **Tidak ada strategi baru sebelum punya alasan yang bisa diuji.**

## 7. Buangan dari sistem lama

| Lama | Kenapa dibuang |
|---|---|
| `facts` 371 MB | semua hal jadi satu tabel; angka UI tidak bisa dijamin benar |
| 25 route | terlalu banyak halaman tanpa lingkaran inti |
| 4 service terpisah (api/worker/notifier/llm) | untuk v0 cukup 2: `web` + `engine` |
| password di DB | risiko kebocoran |
| heartbeat 195k baris | diganti `feed.last_ok_at` + alert |

## 8. Urutan bangun (v0, 7 langkah kecil)

1. Skema 10 tabel + seed 1 venue/akun/instrument.
2. Ingest harga (1 sumber) → `feed` + harga terakhir.
3. Baca status akun dari MT5 (file JSON) → `account` + `position`.
4. `/` dan `/sistem` hidup dengan data nyata.
5. Generator `signal` (dari EA, read-only) → `/sinyal`.
6. `ledger_entry` dari deal history → `/jejak`.
7. Arm/confirm + `event` audit untuk satu aksi (mis. pause EA).

Target: **v0 bisa dibuka dari HP dan menjawab "kenapa tidak ada trade hari ini" dalam 30 detik.**

## 9. Yang perlu diputuskan sebelum baris pertama kode

1. v0 fokus **forex** saja — setuju? (alternatif: forex + crypto sejak awal)
2. Engine v0: **baca status JSON EA** (read-only) atau langsung tulis order?
   (rekomendasi: read-only dulu, arm/confirm menyusul di langkah 7)
3. Stack v0: tetap SvelteKit + FastAPI + Postgres, atau mulai salah satu yang lebih kecil?
   (rekomendasi: tetap, tapi 2 proses saja — `web` dan `engine`)
4. Repo: project baru bersih, atau folder baru di repo War Room sekarang?
   (rekomendasi: folder `v0/` di repo yang ada, supaya riwayat keputusan tetap satu tempat)
