# Bedah Polymarket: kenapa "menang 80%" tapi rugi (Gelombang 2)

Tanggal: 2026-10-10 · Sumber: `/var/lib/poly-paper*/execution-paper-shadow-summary.json` (mentah)
· Status: temuan, **belum ada perubahan mesin** — keputusan tetap milik pemilik

## Angka nyata (10 Okt 03:04 UTC)

| Lengan | Band masuk | Mode | n | Menang/Kalah | WR | PnL | PnL/trade | **BE-WR** | Lolos |
|---|---|---|---|---|---|---|---|---|---|
| A momentum | 0,15–0,25 | momentum | 10 | 1 / 9 | 10,0% | −10,34 | −1,034 | 20,0% | ❌ |
| B kandidat | 0,70–0,95 | ahead | 216 | 174 / 42 | 80,6% | −18,59 | −0,086 | 82,5% | ❌ |
| C fade | 0,70–0,95 | momentum·invert | 0 | 0 / 0 | — | 0 | — | 82,5% | (tak pernah kena) |
| D favorit | 0,70–0,95 | ahead | 34 | 28 / 6 | 82,4% | +12,01 | +0,353 | 82,5% | ❌ (me pet!) |

Kunci lain: `budget` 5 per trade (A: 2) · `feeMode: receipt` · semua `execution: false` (paper murni).

## Sebabnya: harga beli mahal → ambang impas tinggi

Di band **0,70–0,95** (rata-rata ≈0,82), hadiah kemenangan hanya **+0,22× stake**, sedangkan
kekalahan **−1,00× stake**. Jadi butuh **win-rate > 82,5%** hanya untuk balik modal:

- entry 0,75 → menang +0,333× → BE-WR 75,0%
- entry 0,82 → menang +0,220× → **BE-WR 82,5%**
- entry 0,90 → menang +0,111× → BE-WR 90,0%

**B paling mendekati & paling tragis:** 80,6% — kurang **1,9 poin** dari ambang. Maka 174
menang dari 216 tetap berakhir −18,59. Bukan sinyalnya yang salah; **payoff-nya** yang tak cukup.

## B vs D: bedanya cuma satu setelan

Config keduanya nyaris identik (`ahead`, band 0,70–0,95, budget 5). Yang berbeda:
- **B:** `decideWindowSeconds 45–240` → ambil **216** trade
- **D:** `decideWindowSeconds 45–119` → ambil **34** trade

D berjendela lebih sempit = lebih pemilih → WR naik 1,8 poin (80,6% → 82,4%) → **tepat di ambang**,
jadi untung tipis. B mengejar volume → kualitas turun sedikit → jatuh ke sisi rugi.
`skips` membuktikan bedanya: B `outside_window 6754`/`loss_budget 6494`, D `outside_window 524`/`loss_budget 335`.

## Kejujuran: D belum "terbukti"

**D pun hanya +0,353/trade dari n=34, dan WR 82,4% masih DI BAWAH BE-WR 82,5%.** Artinya
keuntungannya sangat rapuh (bisa berbalik dengan beberapa trade). Cakupan: `C fade` 0 trade →
`invert` belum pernah diuji. Semua lengan `execution:false` → ini kertas, bukan uang nyata.

## Arah perbaikan (usulan, bukan keputusan)

1. **Turunkan harga masuk** (band lebih rendah, mis. 0,55–0,75) → BE-WR turun → win-rate sama
   bisa untung. Perlu sampel, karena likuiditas di harga rendah biasanya lebih tipis.
2. **Uji hipotesis jendela:** jalankan D dengan jendela lebih sempit lagi (mis. 45–90) — apakah
   WR naik cukup untuk melewati BE? Kalau ya, "kesabaran" itu nyata, bukan kebetulan.
3. **Ukur payoff nyata:** tarik distribusi harga entry per-trade (bukan hanya band) untuk hitung
   BE-WR sesungguhnya, bukan taksiran rata-rata band.
4. **C fade:** beri jendela/band agar benar-benar kena trade, supaya `invert` teruji.

## Rumus (dipakai di atas, agar bisa diaudit)

stake S di harga p: menang → laba = S·(1−p)/p ; kalah → −S.
BE-WR = 1 / (1 + (1−p)/p) = p. (Jadi di pasar biner adil, win-rate impas ≈ harga beli.)
Fee mode `receipt` menambah friksi kecil → BE nyata sedikit di atas harga.
