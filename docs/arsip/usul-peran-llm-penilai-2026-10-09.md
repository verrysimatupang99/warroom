# Usul — Peran LLM sebagai Penilai Kedua Signal (veto, bukan pengganti gate)

**Tanggal:** 9 Okt 2026 · **Status:** USUL (belum dipasang) · **Dasar:** analisis A (data nyata) + ADR-004 (LLM gateway) + ADR-006 (keputusan owner)

> Ini **dokumen usul**, bukan keputusan. Belum ada kode yang dipasang. Nomor ADR belum
> dialokasikan — kalau owner menyetujui arahnya, baru dinaikkan ke ADR.

---

## 0. Pertanyaan yang dijawab

Owner bertanya: *"LLM untuk membantu proses pemilihan dari data deterministik yang lolos —
apakah memang pantas dijadikan signal dan di paper/live trade kan, atau masih belum sama sekali?"*

Dokumen ini menjawab **"apakah pantas"** — dan **tidak** menjawab "ya, pasang". Alasan di
bagian 1 menunjukkan masalahnya nyata; bagian 4 menunjukkan **bahwa LLM memperbaikinya
belum terbukti** dan harus diuji lebih dulu.

---

## 1. Kenapa ini diusulkan: buktinya (dari analisis A, data nyata)

Fakta dari fakta `idx_akurasi` dan `pasar_akurasi` (9 Okt 2026):

| Market | Aturan | n | WR | mean R / PnL | Catatan |
|---|---|---|---|---|---|
| IDX | BSJP_STRONG | 26 | 80,8% | **+0,789 R** | untung |
| IDX | ARA_HUNTER | 198 | 38,4% | **−0,702 R** | rugi besar, sampel besar |
| Crypto | SMC multi-tf | 30 | 83,3% | **+0,695 R** | untung |
| Polymarket | D favorit | 34 | 82,4% | +12,01 USD | untung |
| Polymarket | B kandidat | 203 | 80,8% | **−12,33 USD** | WR tinggi tapi rugi |
| GMGN | LP Terukur | 72 | 30,6% | −37,38 USD | rugi |

**Masalah yang terbukti:** ada aturan yang **lolos penilaian kuantitatif** (sampel cukup, bahkan
win-rate tinggi) tetapi **rugi**. Contoh paling tajam: `B kandidat` **WR 80,8%** tapi
**−12,33 USD** (n=203). Angka kuantitatif saja **tidak menangkap konteks** — regime pasar,
korelasi antar-trade, biaya, atau kualitas momen masuk.

Ini **bukan** hipotesis. Ini hasil hitung dari data yang sudah ada.

## 1b. Kenapa gate tidak bisa menambal ini sendiri

Gate (ADR-003/0006) memakai ambang tetap: `n ≥ 30`, `ci = 0.90`, `ci_low > BE`. Ambang itu
**hak owner**, bukan tempat agen menambal. Menaikkan `n` atau mengubah rumus = melanggar
ADR-006. Jadi bila masalahnya "kuantitatif lolos tapi kualitatif buruk", solusinya **bukan**
menyetel ulang gate — melainkan menambah **penilai** yang membaca konteks, di **lapisan
antara "lolos gate" dan "masuk paper"**.

---

## 2. Yang sudah ada (jangan bikin ulang)

Rancangan ini **menyambung** infrastruktur yang sudah dibangun, bukan peran baru dari nol:

| Sudah ada | Di mana | Dipakai untuk |
|---|---|---|
| Gateway LLM (primary nutaraline, fallback qonek) | `services/llm`, ADR-004 | panggilan LLM tercatat |
| Peran `verifier` **sudah diizinkan** | ADR-004 butir 7 | kontrak `{setuju, catatan}` |
| Endpoint verifier **sudah ada** | `app.py:1380` (`role="verifier"`) | menguji klaim pod |
| Pencatatan `llm_calls` | ADR-004 butir 3 | peran, provider, `fact_ids[]`, `ok` |
| Aturan "angka tidak lahir dari LLM" | ADR-004 butir 5 | fakta diinjeksi blok `FAKTA` bernomor |

Jadi usul ini **tidak** menambah provider, tidak menambah gateway, tidak menyentuh gate.
Ia **memakai ulang** `verifier` yang sudah ada, dengan **kontrak peran** yang diperjelas
(bagian 3).

---

## 3. Usul peran: "penilai kedua" (veto-only)

### 3.1 Aturan wewenang (yang membuat ini aman)

| Boleh | Tidak boleh |
|---|---|
| **Menolak** signal yang lolos gate (veto → paper) | **Meloloskan** signal yang ditolak gate |
| Memberi alasan (+ skor keyakinan) | Mengubah ambang gate/rumus BE |
| Menandai "perlu tinjauan manusia" | Menulis ke gate, live, atau `activation-approved` |

**Ini kunci keselamatannya:** LLM hanya bisa **mempersempit** (menolak), tak pernah
**melebarkan** (meloloskan). Kalau LLM salah, kerugiannya = **kehilangan peluang**, bukan
**trade buruk masuk**. Itu sesuai prinsip ADR-004 alternatif yang ditolak: *"LLM sebagai
pengambil keputusan gate"* tetap **ditolak** — di sini LLM bukan pengambil keputusan gate,
ia **penyaring setelah gate**.

### 3.2 Kontrak keluaran (sama dengan `verifier` yang sudah ada)

```json
{
  "setuju": true | false,
  "catatan": "satu-dua kalimat: kenapa setuju/tidak, dirujuk ke fact_id",
  "keyakinan": "tinggi | sedang | rendah",
  "perlu_manusia": true | false
}
```

Angka **tidak boleh** lahir dari LLM (ADR-004 butir 5): LLM menilai **konteks**, bukan
menghitung ulang. Setiap angka yang ia sebut harus punya `fact_id`.

### 3.3 Bahan yang diinjeksi (blok `FAKTA` bernomor)

Dari fakta nyata yang sudah ada — **bukan data baru**:

- Hasil aturan yang lolos gate: `n`, `winrate_pct`, `mean_r`, `total_r` (fact `idx_akurasi`/`pasar_akurasi`)
- Kondisi risiko hari itu: `hari_ini_r`, `batas_rugi_r` (fact `risiko`)
- Kesegaran & status sumber: umur sinyal, `status_data`
- Catatan biaya: tercatat (net) atau **BRUTO**

LLM **membaca**, tidak menambah.

### 3.4 Di mana ia duduk (alur)

```
data mentah → gate deterministik → [LOLOS] → LLM penilai → [SETUJU] → paper
                                  → [TOLAK]                     → [TOLAK] → arsip + alasan
                                     ↓
                            (LLM TIDAK BISA masuk sini)
```

Titik masuknya **setelah** gate, **sebelum** paper. Gate tetap satu-satunya pintu keras.

---

## 4. Yang WAJIB diuji sebelum dipasang (jujur: belum terbukti)

**Peringatan penting:** saya membuktikan **masalahnya ada** (lolos gate tapi rugi). Saya
**belum** membuktikan LLM memperbaikinya. Menyatakan "LLM akan memperbaiki" tanpa uji =
klaim tanpa bukti. Karena itu, sebelum dipasang:

1. **Uji mundur (backtest keputusan LLM).** Ambil trade lampau yang **lolos gate lalu rugi**
   (mis. `B kandidat`, `ARA_HUNTER`). Tanya: dari fakta yang tersedia **saat itu**, apakah
   `verifier` akan **menolaknya**? Kalau ya → ada nilai. Kalau tidak → LLM tidak menambah apa pun.
2. **Uji false-negative.** Ambil trade yang **lolos gate lalu UNTUNG** (`BSJP_STRONG`,
   `D favorit`). Apakah LLM keliru **menolaknya**? Bila sering → LLM **merugikan** (membuang
   peluang baik).
3. **Ukur tambahan nilai.** Bandingkan dua keranjang:
   - **A:** semua yang lolos gate, apa adanya
   - **B:** semua yang lolos gate **DAN** disetujui LLM
   Kalau `mean R` keranjang B **tidak lebih baik** dari A → **jangan pasang**. Titik.
4. **Ukur biaya.** Berapa panggilan LLM per hari? Latensi? Anggaran (ADR-004) cukup?

**Kriteria GO (usulan, untuk didiskusikan owner):**
- B menolak ≥ 60% dari trade rugi diuji **DAN**
- B tidak menolak > 20% trade untung diuji **DAN**
- B `mean R` > A `mean R` secara berarti

**Kriteria NO-GO:** salah satu di atas gagal → LLM tidak dipasang; masalahnya diselesaikan
dengan cara lain (mis. dataset lebih besar, biaya dicatat, atau aturan merugi diarsipkan).

---

## 5. Alternatif yang ditolak (dan kenapa)

| Ditolak | Alasan |
|---|---|
| LLM **mengganti** gate | Melanggar ADR-004 (alternatif ditolak), ADR-006 (ambang hak owner) |
| LLM **meloloskan** yang ditolak gate | Bila LLM salah → trade buruk masuk. Vetо-only mencegah ini |
| LLM **menghitung ulang** angka | Melanggar ADR-004 butir 5 ("angka tidak lahir dari LLM") |
| Pasang **sekarang** tanpa uji | Klaim tanpa bukti — melanggar semangat "no fabricated evidence" |
| Naikkan ambang gate agar rugi tertolak | Ambang = hak owner; menyetelnya untuk memburu hasil = overfit |

---

## 6. Konsekuensi bila disetujui

- **Peran `verifier` diperjelas** kontraknya untuk kasus ini (sudah ada di `app.py:1380`).
- **Tidak** mengubah gate, `live-trading`, ambang, atau rumus BE.
- **Tidak** ada trade yang dijalankan dari LLM — ia hanya **menyaring** langkah paper.
- Setiap keputusan tercatat di `llm_calls` (peran, provider, `fact_ids[]`, `ok`) —
  dapat diaudit, sesuai ADR-004/005.
- Bila uji **NO-GO**, dokumen ini jadi catatan **"sudah dipertimbangkan & ditolak dengan
  bukti"** — itu berharga juga, karena menghentikan usul yang sama muncul lagi.

---

## 7. Yang dibutuhkan dari owner (keputusan, bukan kerja agen)

1. **Setuju arahnya?** (LLM = penilai kedua, veto-only, setelah gate) — ya/tidak.
2. **Setuju diadakan uji dulu** (bagian 4) sebelum dipasang? — ya/tidak.
3. **Kriteria GO/NO-GO** di bagian 4: pakai usulan itu, atau owner punya angka lain?

Selama tiga ini belum dijawab, **tidak ada yang dipasang**. Dokumen ini berhenti di sini
dengan sengaja.
