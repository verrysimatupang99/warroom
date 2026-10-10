# Gelombang 3 — Keputusan Per Pasar (layak / ubah / stop)

Tanggal: 2026-10-10 · Status: **menunggu keputusan pemilik** — agen tidak memilih sendiri.
Bukti: seluruh dokumen `docs/belajar/bedah-*-2026-10-10.md` + ledger mesin (baca-saja).

---

## Ringkas: tiga pasar, tiga vonis berbeda

| Pasar | Setup | n | Hasil | Vonis bukti | Usulan |
|---|---|---|---|---|---|
| **IDX** | BSJP_STRONG | 30 | **+0,682R** (CI90 bawah +0,254) | **LOLOS pakem** | **LAYAK** (kecil, jaga) |
| IDX | ARA_HUNTER | 346 | **−0,442R** | merugikan, dominan volume | **STOP** |
| **Polymarket** | B kandidat | 216 | −18,59 (WR 80,6% < BE-WR 82,5%) | payoff tak cukup | **UBAH** (turunkan band) |
| Polymarket | D favorit | 34 | +12,01 (WR 82,4% < BE-WR 82,5%) | untung **rapuh** | **UBAH** (perlebar sampel) |
| Polymarket | A momentum | 10 | −10,34 | rugi | **STOP** |
| Polymarket | C fade | 0 | — | belum pernah kena | UBAH (beri jendela) |
| **GMGN** | jalur arah (semua grup) | 283 | −6% s/d −20% | **semua negatif** | **STOP** (jangan promosikan) |
| GMGN | LP terukur | 75 | jalur terpisah | belum dinilai penuh | UBAH (kumpulkan sampel) |
| **CRYPTO** | intraday (30 tuntas) | 30 | **+0,672R**, WR 80,6% | untung | **LAYAK** (kecil, jaga) |
| **FOREX** | XAUUSD | — | kolom R masih kosong | belum bisa dinilai | TUNGGU (butuh data) |

---

## 1. IDX — **UBAH** (matikan ARA, pertahankan BSJP)

**Bukti tegas:** membuang ARA_HUNTER membalik total **−126,08R → +26,77R**
(ekspektasi −0,293 → **+0,315** per trade). ARA = 80% volume, 100% kerugian.

- **LAYAK:** `BSJP_STRONG` (+0,682R, CI90 bawah +0,254, n=30) — satu-satunya yang lolos pakem.
- **STOP:** `ARA_HUNTER` (−0,442R, n=346) — n besar justru mempertegas kerugian.
- **TUNGGU:** `BSJP_ARA` (+0,334R, n=20) — kumpulkan sampai n≥30, lalu uji ulang.

**Keputusan diminta:** matikan `ARA_HUNTER` dari komposisi, atau kurangi ukurannya?

---

## 2. Polymarket — **UBAH** (payoff, bukan sinyal)

**Bukti:** 174 menang dari 216 tetap −18,59, karena harga beli ≈0,82 → butuh WR > 82,5%
hanya untuk balik modal. B paling tragis: 80,6% (kurang **1,9 poin**).

- **UBAH:** turunkan band masuk (mis. 0,55–0,75) → BE-WR turun → win-rate sama bisa untung.
- **UBAH:** jalankan D dengan jendela lebih sempit (45–90) — uji hipotesis "kesabaran".
- **STOP:** arm A momentum (WR 10%, −10,34).
- **Catatan jujur:** D (+0,353/trade, n=34) masih **DI BAWAH** BE-WR 82,5% → rapuh, bukan bukti.

**Keputusan diminta:** izinkan uji band lebih rendah (paper) untuk melihat apakah BE-WR turun?

---

## 3. GMGN — **STOP** (jalur arah), LP tetap

**Bukti:** semua grup negatif (admitted −19,59, signal −15,71, control −11,31). Gate
**tidak terbukti menambah nilai** (3 dari 4 geometri: admitted lebih buruk dari control).

- **STOP:** jangan promosikan jalur arah memecoin ke live atas dasar apa pun sekarang.
- **UBAH (uji):** kalau mau lanjut, uji geometri scalp kecil (tp50/sl30 — satu-satunya mendekati
  netral) dan tumbuhkan `admitted` sampai n≥30 sebelum vonis.
- **Catatan jujur:** ini bukan "gate buruk", ini "belum ada dasar memakai gate ini".

**Keputusan diminta:** matikan jalur arah, atau beri satu putaran uji di geometri scalp?

---

## 4. CRYPTO — **LAYAK** (kecil, jaga)

**Bukti:** `crypto_equity.jsonl` 30 trade tuntas, 25 menang / 4 kalah, WR 80,6%,
expectancy **+0,672R**, total **+20,844R**.

- **LAYAK:** pertahankan apa adanya. Ini pasar paling sehat yang kita punya.
- **Catatan:** crypto Tencent (12 baris) beda — total +1,5R. Eksekusi otomatis (`crypto-auto-exec-653`)
  jalan via MEXC, tapi **kunci MEXC di Tencent tidak boleh diambil**.

**Keputusan diminta:** tidak ada — usul: jaga, jangan promosikan live.

---

## 5. FOREX (XAU/USD) — **TUNGGU**

**Bukti:** kategori FOREX (bukan pasar baru). Kolom R masih kosong di jurnal Tencent →
**belum bisa dinilai** apa pun. Bukan "layak", bukan "stop" — datanya belum ada.

**Keputusan diminta:** tunggu jurnal terisi, atau minta saya siapkan pengukur?

---

## Rekomendasi agen (bukan keputusan)

1. **IDX:** matikan `ARA_HUNTER` (bukti paling tegas: membalik −126R → +27R).
2. **GMGN:** stop jalur arah; LP jalan terus.
3. **Polymarket:** izinkan uji band 0,55–0,75 (paper) — murah, langsung menguji akar masalah.
4. **CRYPTO:** jaga apa adanya.
5. **FOREX:** tunggu data.

**Semua tetap NO-GO untuk uang nyata** sampai pemilik memutuskan. `live.start` tetap 409,
`armed=false` — tidak ada yang saya ubah tanpa persetujuan.
