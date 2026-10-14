# Uji backtest peran LLM `verifier` — hasil & pelajaran (3b)

**Tanggal:** 9 Okt 2026 · **Status:** uji selesai (bahan sudah diperbaiki) · **Alat:** `tools/uji_backtest_verifier.py`

> Ini catatan **jujur** jalannya uji. Termasuk **dua koreksi** atas analisis saya sendiri.
> Tujuannya: siapa pun yang melanjutkan tidak mengulang kesalahan yang sama.

---

## 0. Ringkas hasil

| Putaran | Bahan uji | Hasil | Sah? |
|---|---|---|---|
| **1** | `fact_id` palsu (1,2,3) | `fact_id_tidak_ada` — semua gagal | ❌ bahan cacat |
| **2** | agregat `idx_akurasi` + parameter trade | 6/6 ditolak | ❌ bahan tidak memuat kelayakan |
| **3** | riwayat kinerja setup (fakta tepat) | 12/12 ditolak | ✅ ke-4 putaran sah |
| **3b** | + sebar lintas-setup | 12/12 ditolak | ✅ sah, tapi sampel kecil |

**Verdict sementara:** uji **cenderung NO-GO**, **tetapi belum final** — lihat bagian 3.

---

## 1. Dua koreksi analisis saya (ditulis apa adanya)

### Koreksi A — "kredensial LLM mati" → SALAH

Saat uji pertama, `llm_calls` mencatat `http_401` + `circuit_open` untuk ketiga provider.
Saya menyimpulkan **kredensial mati**. **Itu keliru.**

**Penyebab sebenarnya:** skrip uji saya **tidak memuat `/etc/warroom/llm.env`**, sehingga
gateway membaca **kunci kosong** → semua provider 401 → circuit terbuka.

**Bukti koreksi:** setelah env dimuat, gateway **`ok` 3× berturut** (provider `nutaraline`),
dan curl langsung ke ketiga endpoint (nutaraline/kiyara/qonek) → **HTTP 200**.

**Pelajaran:** jangan menyimpulkan "kredensial mati" dari log tanpa memeriksa **cara env dimuat**.
Di sistem ini, `llm.env` **wajib** di-`source` sebelum memanggil gateway.

### Koreksi B — "LLM menolak semua → tidak berguna" → SALAH

Uji ke-2 menolak **semua**. Saya hampir menyimpulkan LLM tidak menambah nilai. **Itu keliru**
karena **bahan ujinya cacat**: blok FAKTA berisi **statistik agregat** + parameter trade,
padahal `verifier` diminta menilai **kelayakan**. `verifier` **benar** menolak
("blok fakta tidak memuat data kelayakan") — sesuai ADR-004 butir 5.

**Pelajaran:** menolak ≠ tidak berguna. Bila fakta tidak mendukung, **menolak itu benar**.
Bahan harus memuat **bukti kelayakan** (riwayat kinerja setup).

---

## 2. Mekanisme yang terbukti bekerja

| Hal | Bukti | Status |
|---|---|---|
| `verifier` menolak `fact_id` tidak ada | `error_code=fact_id_tidak_ada:[1,2,3]` | ✅ **benar** (ADR-004 butir 5) |
| `verifier` menolak klaim tanpa bukti | "blok fakta tidak memuat data kelayakan" | ✅ **benar** |
| `verifier` merujuk `fact_id` saat menilai | "F1 (fact_id=73252) …" | ✅ **benar** |
| Gateway hidup (env benar) | 3× `ok`, curl 200 | ✅ **terbukti** |
| Skrip backtest jalan | 12 baris hasil | ✅ **terbukti** |

**Kesimpulan:** `verifier` **bekerja sesuai desain**. Ia **jujur & ketat**.

---

## 3. Temuan paling penting (dan kenapa hasilnya belum final)

**`verifier` menolak SEMUA (12/12) — tetapi bukan acak.** Alasannya konsisten:

| Setup | mean_r | pakem | Verifier | Benar? |
|---|---|---|---|---|
| ARA_HUNTER | −0,7024 | INSUFFICIENT | TOLAK | ✅ mean_r negatif |
| INTRADAY | −0,0108 | DIRECTIONAL | TOLAK | ✅ mean_r negatif |
| BSJP_ARA | **+0,3601** | INSUFFICIENT | TOLAK | ❌ tapi pakem kurang |
| BSJP_STRONG | **+0,789** | INSUFFICIENT | TOLAK | ❌ tapi pakem kurang |

**Ini inti persoalannya:** `verifier` menolak **BSJP_ARA & BSJP_STRONG** — yang **RUGI-nya belum terbukti**
(mean_r positif) — hanya karena **`pakem=INSUFFICIENT`** (sampel kurang, 5–8 hari efektif < 10).

**Artinya:** keputusan `verifier` di uji ini **didikte oleh ambang pakem**, bukan oleh penilaian
konteks pasar. Ini persis kekhawatiran dokumen usul: *"LLM hanya bisa mempersempit"* — dan di sini
ia mempersempit **terlalu banyak**, termasuk yang sebenarnya untung.

**Kenapa hasil ini BELUM final:**
- **Semua** setup di ledah IDX ber-`pakem=INSUFFICIENT` (kecuali INTRADAY=DIRECTIONAL) → akibatnya
  uji tak bisa membedakan "menolak karena rugi" vs "menolak karena sampel kurang".
- **Jumlah trade per setup kecil** (BSJP_STRONG n=26; BSJP_ARA n=19; INTRADAY n=35).
- **`n_uji` hanya 12** — tidak cukup untuk klaim statistik.

**Jadi:** hasil ini menunjukkan **`verifier` ketat**, **bukan** bahwa "LLM tidak menambah nilai".
Klaim yang sah: **pada sampel ini, `verifier` menolak semuanya, dan penolakannya didominasi
ambang pakem.** Kriteria GO (tambah_nilai ≥60% DAN false_negatif ≤20%) → **NO-GO pada sampel ini**.

---

## 4. Yang TIDAK boleh disimpulkan

- ❌ "LLM tidak berguna" — **tidak sah** dari uji ini (penolakan didominasi pakem, bukan hasil).
- ❌ "Kredensial mati" — **salah**, sudah dikoreksi (bagian 1A).
- ❌ "Verifier rusak" — **salah**, ia bekerja sesuai desain.
- ❌ "Peran LLM layak dipasang" — **belum**, kriteria GO belum terpenuhi.

## 5. Yang BISA disimpulkan

- ✅ `verifier` **jujur & ketat** — ia menolak bila fakta tak mendukung.
- ✅ **Bahan uji menentukan hasil** — beri fakta kelayakan, bukan agregat.
- ✅ **Ambang pakem sangat menentukan** — `verifier` menaatinya, bahkan untuk setup untung.
- ✅ Untuk uji yang **sah**, perlu: **lebih banyak trade per setup**, dan **setup yang pakem-nya
  sudah memadai** (mis. TUNING/PRELIMINARY), supaya perbedaan "rugi vs untung" terlihat.

---

## 6. Langkah lanjut (bila owner mau)

1. **Perbesar sampel** — uji setup yang pakem-nya lebih matang (polymarket B/D, crypto SMC n=30)
   supaya `verifier` tidak otomatis menolak karena pakem.
2. **Pisahkan variabel** — uji dua keranjang: (a) setup untung yang pakem-nya cukup,
   (b) setup rugi yang pakem-nya cukup. Baru perbedaan penolakan bermakna.
3. **Putuskan berdasarkan kriteria owner** — bukan dari satu putaran uji.

**Selama itu belum dikerjakan, tidak ada rekomendasi "pasang LLM".**
