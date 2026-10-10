# Rencana fokus: Polymarket · IDX · GMGN (dibaca pemilik dulu)

Tanggal: 2026-10-10 · Status: **menunggu persetujuan pemilik** — belum ada yang diubah

## Ringkas kondisi nyata (hasil audit, bukan asumsi)

Semua fakta di bawah segar (11 menit lalu), kecuali yang disebut lain.

### Polymarket
- **Mesin jalan**, mode **paper**, equity $200, `total_trade: 0` (belum ada trade nyata tercatat).
- Uji kertas 4 lengan: **A momentum −10,34** (1 menang/9 kalah), **B kandidat −18,59**
  (174/42 — win-rate tinggi tapi **rugi** karena payoff), **C fade 0** (0 trade),
  **D favorit +12,01** (28/6 — **satu-satunya untung**).
- Narasi mesin: *"masih terbelah… belum ada kesimpulan yang bisa dipakai."*
- **Masalahnya:** menang banyak ≠ untung. B kandidat menang 80,79% dari 203 trade tapi
  rugi $12,33 — artinya ukuran taruhan/payoff salah, bukan sinyalnya.

### IDX
- **Mesin BEKU** — cron IDX Tencent (`idx616`) **di-pause sejak 6 Okt** (epoch beku).
- Ledger beku: **350 sinyal terbuka, 102 di antaranya ≥10 hari** dan **tidak akan pernah ditutup**.
- Akurasi dari 278 trade tuntas: **BSJP_STRONG win-rate 80,77%** (26 trade, bagus),
  **ARA_HUNTER 38,38%** dari 198 trade dengan rata-rata **−0,70 R** (jelek & mendominasi volume).
- Pakem per-setup: **INSUFFICIENT** (sampel < 10 hari) — belum bisa dipakai untuk promosi.
- **Masalahnya:** mesin mati → data beku; dan setup yang paling banyak dipakai (ARA Hunter)
  justru yang paling rugi.

### GMGN / Memecoin
- **Kering.** `gmgn_ledger: trade 0`. Sampel paper hanya **4** (1 menang/3 kalah, PF 0,38).
- Log terakhir: ***"SKIP: siklus lain sedang jalan (cycle.lock tertahan)"*** — mesin
  **macet karena kunci siklus** (bukan karena pasar sepi).
- `paper/signals.jsonl` berstatus **rusak**; `positions.json` **tidak ada**.
- LP (likuiditas) punya jalur terukur sendiri: `lp_mark` n=5, `lp_verifikasi` 2 pool,
  `lp_paper` 1 posisi (UBI) — **untung kecil/rugi** ($−1,68 pada $30), pakem juga INSUFFICIENT.
- **Masalahnya:** bukan "tidak ada peluang", tapi **mesinnya tidak jalan** (lock tertahan +
  berkas rusak).

## Pola bersama (ini inti rencananya)

Ketiganya **belum gagal karena strateginya** — gagal karena **pipa datanya**:
| Pasar | Hambatan utama | Bukan masalah |
|---|---|---|
| Polymarket | Ukuran taruhan (payoff), bukan sinyal | sinyal sudah ada |
| IDX | Mesin beku (cron pause) | bukti historis sudah ada |
| GMGN | Lock macet + berkas rusak | LP sudah ada jalurnya |

Maka urutannya: **hidupkan pipa dulu → ukur jujur → baru nilai layak-tidaknya**.
Tidak ada promosi live untuk pasar mana pun sebelum angkanya lolos gate.

---

## Rencana — 3 gelombang

### Gelombang 1 — "Buka sumbatan" (tanpa kredensial, risiko rendah)
Tujuan: data mengalir lagi, apa adanya.
1. **GMGN:** bersihkan `cycle.lock` yang tertahan + perbaiki `signals.jsonl` yang rusak.
   Target: `gmgn_ledger.trade` kembali bertambah. *Tidak menyentuh dana.*
2. **IDX:** putuskan sumber data — hidupkan kembali mesin idx616, **atau** akui ledger beku
   dan tandai jelas di UI (sudah sebagian dilakukan). Tidak ada angka baru sampai sumber hidup.
3. **Polymarket:** tidak ada sumbatan mesin — langsung ke Gelombang 2.

### Gelombang 2 — "Ukur jujur" (murni analitik, tanpa mengubah mesin)
Tujuan: tahu **apa** yang sebenarnya bekerja, angka apa adanya.
4. **Polymarket:** bedah 4 lengan — **kenapa menang banyak tapi rugi?** Ukur payoff &
   ukuran taruhan; uji apakah "D favorit" (+12) nyata atau kebetulan (n=34 → masih tipis).
5. **IDX:** pisahkan **BSJP_STRONG** (bagus) dari **ARA_HUNTER** (rugi). Uji apakah
   membuang ARA Hunter menaikkan ekspektasi total secara nyata.
6. **GMGN:** setelah catatan mengalir, ulangi jalur memecoin **arah** (bukan cuma LP) dengan
   metode benar: klaim disembunyikan, cocokkan pair+arah+waktu.

### Gelombang 3 — "Putuskan" (hak pemilik)
7. Untuk tiap pasar: **layak dijalankan** / **perlu diubah** / **distop** — berdasarkan angka
   Gelombang 2, ambang gate yang ada (n≥30, ci=0,90, ci_low>BE). Keputusan = pemilik.

---

## Yang saya butuhkan dari Anda (pilih, jawab nomor)

- **A.** Sumber IDX: **(1)** hidupkan lagi mesin idx616 di Tencent (baca-saja → butuh izin Anda
  untuk menyalakan), **atau (2)** biarkan beku & fokus ke Polymarket+GMGN dulu?
- **B.** GMGN: boleh saya **bersihkan lock + perbaiki berkas rusak** (Gelombang 1 poin 1)?
- **C.** Urutan: **(1)** kerjakan berurutan Poly→IDX→GMGN, atau **(2)** GMGN dulu (paling cepat
  membuka), baru Poly, lalu IDX?

Tidak ada yang saya ubah sampai Anda jawab. Aturan tetap: gate tidak disentuh, live NO-GO,
angka selalu dari fakta, mesin Tencent baca-saja.
