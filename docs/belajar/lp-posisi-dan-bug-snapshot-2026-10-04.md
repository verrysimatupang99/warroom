# LP: pencatat posisi + panel + 3 bug jalur snapshot — 4 Okt 2026

Lanjutan dari `analisa-klaim-lp-solana-2026-10-04.md`. Dua tugas yang diminta dikerjakan.

---

## Tugas 1 — Pencatat posisi LP (`lp_positions.py`)

Menjawab tepat satu pertanyaan yang **tidak bisa** dijawab klaim LP mana pun di media sosial:
*posisi LP saya lebih baik daripada cuma memegang tokennya?*

| Kemampuan | Cara |
|---|---|
| Catat masuk/keluar | `catat_masuk()` / `catat_keluar()` — **wajib kedua kaki** (>0), kalau tidak ditolak |
| IL == hold tanpa harga | Saat kenaikan **proporsi** kedua kaki sama → tidak ada rugi vs memegang |
| IL vs hold tanpa harga | Lewat imbal hasil **tertimbang modal awal** (bukan 50/50, bukan jumlah token yang selalu terlihat naik) |
| IL vs hold dengan harga | `return_lp_pct` vs `return_hold_pct` + `lp_vs_hold_usd`, putusan `LP/hold/seri` |
| Yang tidak diketahui | Ditulis `belum diketahui` — fee APR & USD apa pun tidak pernah ditebak |

Penyimpanan: `state/lp_positions.json`, append-only supaya bisa diaudit.

### Uji dengan angka PERSIS dari klaim poster

```
masuk : 5.710 BAGSPAY + 0,035 SOL
keluar: 6.230 BAGSPAY + 0,077 SOL
```

| Hasil | Nilai |
|---|---|
| Kenaikan kaki base | **+9,11%** |
| Kenaikan kaki quote | **+120,00%** |
| Kedua kaki naik (= tanda fee masuk) | **ya** |
| Imbal hasil tertimbang | **+9,11%** |
| Imbal hasil hold | **+64,55%** |
| **IL vs hold** | **−55,45 poin** |
| Putusan | **hold menang** |
| Ketidakseimbangan komposisi | **2,02×** |

Jadi: menambah kuantitas di kedua kaki memang tanda fee nyata — **tapi itu bukan ukuran
keuntungan.** Karena modal awal 98,8% ada di kaki SOL, dan SOL naik +120% sementara BAGSPAY cuma
+9,1%, **memegang jauh lebih untung**. Itulah kalimat yang tidak ada di post itu.

---

## Tugas 2 — Panel `/lp`

`apps/web/src/routes/lp/+page.svelte` + entri nav `≋ LP` (sebelum Bukti).

Pemisahan yang sengaja tegas:

- **Posisi LP (uang nyata)** — hanya dari sini IL vs hold bisa dihitung. Kosong → dinyatakan
  `0 posisi` + penjelasan bahwa itu keputusan sadar (ukur dulu sebelum menyetor).
- **Kandidat pool** — hasil pencarian, **belum ada uang**. Diurutkan **berdasarkan volume**,
  bukan likuiditas, dengan label kualitas.

---

## 3 bug jalur snapshot yang ditemukan sambil mengerjakan ini

Ketiganya nyata, semuanya membuat `bagian.lp` **tidak pernah** sampai ke UI, dan tidak satu pun
memunculkan error.

### Bug 1 — `dibuat` berformat WIB dianggap UTC (`facts_publish._observed_at`)

`state/snapshot.json` menyimpan `"dibuat": "2026-10-04 18:43:19 WIB"` — waktu lokal (UTC+7),
**tanpa penanda zona**. Diumpankan apa adanya ke `datetime.fromisoformat`, jamnya dianggap UTC.
Dua akibat sekaligus:

1. Setiap fakta snapshot **selalu terlihat 7 jam lebih tua** dari kenyataan → badge kesegaran salah.
2. `on_conflict_do_nothing` pada `(kind, key, observed_at)` terus **menabrak baris lama**, sehingga
   **fakta baru tidak pernah masuk** — padahal job melaporkan `ok` dan `fakta=15`.

Perbaikan: stempel berzona (`Z` / `±HH:MM`) dipakai apa adanya; `dibuat` lokal dicek terhadap
mtime berkas supaya waktu observasi **tidak pernah lebih akurat daripada kenyataan**.
Dikunci dengan 4 tes regresi.

### Bug 2 — `timeout_s` 300 detik di-seed ulang setiap restart worker (`schedule.py`)

`payload={"timeout_s": 300}` di `JobSpec`. Nilai ini **di-seed ulang ke DB setiap worker
restart**, jadi menyunting DB (`update jobs set payload_json=...`) **selalu ditimpa** — termasuk
suntingan yang baru saja melaporkan `UPDATE 1`.

Sejak `bagian` bertambah (macro, lp, …) satu siklus snapshot bisa menembus 5 menit saat jaringan
lambat. Proses yang dibunuh di tengah tulis meninggalkan `snapshot.json` **separuh**.

Perbaikan: `900` detik di sumbernya (`schedule.py`), sama dengan anggaran job `collect`.

### Bug 3 — tidak ada penjaga snapshot separuh (`jobs._jalankan_lt`)

Sebuah bagian bisa hilang sementara prosesnya keluar kode 0 — tanpa jejak. Sekarang: bagian yang
dilaporkan `ok` di stdout **tetapi tidak ada di berkas** membuat job **GAGAL dengan pesan jelas**,
bukan lolos berstatus `ok`.

---

## Verifikasi

| Uji | Hasil |
|---|---|
| Suite | **479 lulus** · ruff **All checks passed** |
| `bagian.lp` di berkas | ✅ ada (`dibuat 19:33:35 WIB`) |
| `bagian.lp` di `facts` | ✅ ada |
| API `/api/v1/crypto` | ✅ `bagian.lp ADA: True` → `0 posisi · 5 kandidat` |
| Halaman `/lp` | ✅ **200** |
| Layanan | 4 `active` · publik 200 · api 401 · **0 unit failed** |

Contoh keluaran nyata (dan alatnya memang menolak yang buruk):

```
SOL/SOL     pumpfun  –      vol24 $223.252  turn 0x  belum-cukup-data
SOL/USDC    raydium  CLMM   vol24 $141.025  turn 0x  pool-mati
SOL/USDC    raydium  CLMM   vol24 $108.229  turn 0x  pool-mati
SOL/USDC    raydium  CLMM   vol24 $    282  turn 0x  pool-mati
```

Empat dari lima kandidat ditandai **pool-mati** — likuiditas ada, transaksi tidak. Itu jawaban
jujur untuk pertanyaan "boleh masuk LP di sini?" — dan persis yang tidak akan pernah dikatakan
postingan "+122%".

---

## Pelajaran yang layak diingat

1. **Nilai di DB bisa di-seed ulang oleh kode.** Kalau `update` di DB hilang tanpa jejak, periksa
   `schedule.py` / seeder sebelum menuduh psql.
2. **Stempel waktu lokal tanpa penanda zona adalah ranjau.** Bukan cuma salah tampil — ia merusak
   idempotensi penulisan (`on_conflict`) sehingga data baru **diam-diam tidak masuk**.
3. **Jangan pernah mempercayai "ok" saja.** Bandingkan yang dilaporkan dengan yang benar-benar
   ada di berkas.
4. **Urutkan peluang LP pakai volume, bukan likuiditas.** Likuiditas besar tanpa transaksi = uang
   diparkir tanpa fee.
