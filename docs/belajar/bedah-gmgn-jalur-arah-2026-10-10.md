# Bedah GMGN: uji jalur arah memecoin dgn metode benar (Gelombang 2, poin 6)

Tanggal: 2026-10-10 · Sumber: `~/gmgn-paper/state/sim_ledger.jsonl` (298 baris; 283 `done`)
· Status: temuan jujur, **belum ada perubahan mesin** — keputusan milik pemilik

## Apa yang diuji

Ledger simulasi mencatat **semua kandidat** (bukan hanya yang lolos) dalam 3 grup:
- **`admitted`** (n=9) — lolos gate
- **`signal`** (n=223) — sinyal mentah
- **`control`** (n=51) — ditolak sebagai pembanding

Tiap kandidat diuji pada 4 geometri exit. Pertanyaannya: **apakah gate menambah nilai?**
Artinya `admitted` harus **lebih untung** dari `control`.

## Hasil (net% per trade)

Geometri bawaan (tp100/sl65):

| Grup | n | net% |
|---|---|---|
| `admitted` (lolos gate) | 9 | **−19,59** |
| `signal` (mentah) | 223 | −15,71 |
| `control` (ditolak) | 51 | **−11,31** |

Semua geometri, `admitted` vs `control`:

| Geometri | admitted | control | beda |
|---|---|---|---|
| tp50/sl30 | −6,78 | −12,54 | **+5,76** |
| tp100/sl65 | −19,59 | −11,31 | −8,28 |
| tp150/sl50 | −11,67 | −10,16 | −1,50 |
| tp200/sl40 | −16,67 | −8,56 | −8,11 |

## Vonis (jujur)

1. **SEMUA grup negatif.** Tidak ada satu pun yang untung di geometri bawaan. Jalur arah
   memecoin, apa adanya, **merugi** pada sampel ini.
2. **Gate TIDAK terbukti menambah nilai.** Di 3 dari 4 geometri, `admitted` justru **lebih buruk**
   dari `control`. Hanya di tp50/sl30 ia sedikit lebih baik (+5,76) — tapi itu geometri
   scalp kecil, dan **admitted n=9** jauh di bawah ambang (n≥30) untuk diuji pakem.
3. **Jangan menyimpulkan dari n=9.** Yang bisa dikatakan: arahnya **bukan positif**, dan gate
   belum menunjukkan keunggulan. Ini **bukan** bukti "gate buruk" — ini bukti "belum ada dasar
   untuk memakai gate ini".

## Kenapa ini penting

Meniru pola yang sama dengan crypto & IDX: **LLM/narasi ≠ sumber alfa.** Di sini bahkan gate
arsitekturnya belum terbukti. Angka apa adanya: -6% s/d -20% per trade.

## Langkah berikutnya (usulan)

1. **Ubah geometri:** tp50/sl30 satu-satunya yang mendekati netral — uji lebih banyak sampel di
   geometri scalp kecil, bukan tp100/sl65.
2. **Tumbuhkan `admitted`** sampai n≥30 baru uji pakem (jangan vonis dari 9).
3. **Jangan promosikan** jalur arah memecoin ke live atas dasar apa pun sekarang.
4. Bila tetap negatif setelah n cukup: **matikan** jalur arah, sisakan LP (yang punya jalur terukur sendiri).
