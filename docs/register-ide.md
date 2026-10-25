# Register Ide — Status Semua Hipotesis

Terakhir diperbarui: 24 Okt 2026
Sumber: analisa journal crypto (145 trade), PlanetX (200 trade), riset EA, uji walk-forward

**Legenda status:**
✅ **LOLOS** — terbukti dengan data, layak dilanjutkan
🟡 **MENUNGGU** — butuh data yang belum ada (pasar tutup / sampel kurang)
⏳ **BELUM DIUJI** — ada dasarnya, belum diukur
❌ **GAGAL** — sudah diuji, tidak lolos
🚫 **DITOLAK** — bertentangan dengan prinsip, tidak akan diuji

---

## A. Filter & Sinyal

| # | Ide | Bukti | Status |
|---|---|---|---|
| A1 | **SNR**: SL di dalam zona S/R lebih sering gagal | 60 hari, 26.306 trade: 42,6% vs 42,8%, **p=0,741** | ❌ GAGAL |
| A2 | **Jam 12–18 WIB** (dari journal crypto, +21,63R / n=59) | Uji XAUUSD 60 hari: jam 05–11 UTC = 42,6%, sama dengan rata-rata | ❌ GAGAL (tidak transfer ke gold) |
| A3 | **Filter jam di crypto** (in-sample +21,63R) | n=59, 8 hari — belum out-of-sample | ⏳ BELUM DIUJI |
| A4 | **Batas kepadatan posisi ≤6** (+7,72R vs baseline −15,14R) | in-sample n=82; belum diuji forward | ⏳ BELUM UJI |
| A5 | **Buang panel Break&Retest** (22% trade, 69% kerugian, −1.088,88) | in-sample; belum diuji forward | ⏳ BELUM UJI |
| A6 | **Model 2 PlanetX** (win 79,2%, n=72 vs Model 1 74,2%) | data orang lain, satuan P/L tak konsisten | ⏳ BELUM UJI |
| A7 | **Entry window 06–09 NY** (win 84,2%, median +178) | PlanetX, n kecil, belum diverifikasi | ⏳ BELUM UJI |
| A8 | **Tag `sl-placement`** (win 3,1%, n=32) | PlanetX — indikator cacat eksekusi | ✅ LOLOS (sebagai diagnosis) |
| A9 | **Tag `revenge`** (win 0%, n=6) | PlanetX — n terlalu kecil | 🟡 MENUNGGU |
| A10 | **Laya AI verdict** | konsisten SKIP p≈0,14–0,24 vs ambang 0,60 | 🟡 MENUNGGU (menurunkan ambang tidak menolong) |

---

## B. Strategi

| # | Ide | Bukti | Status |
|---|---|---|---|
| B1 | **Grid + avg di XAUUSD** | 60 hari: semua skenario **bangkrut** (tanpa stop 31 Agu, stop 2% 28 Sep) | ❌ GAGAL |
| B2 | **Grid + avg di spot crypto** | 5,5 tahun: +35…62%, unggul dari B&H di 5/6 koin, DD ~50% | ✅ mekanisme nyata |
| B3 | **Hard stop pada grid** | SOL +62% → **−77%**, DOGE −10% → −65% | ❌ GAGAL (merusak) |
| B4 | **Filter rezim pada grid** | in-sample +26% → +44%; **walk-forward hanya +4%, tidak konsisten** | ❌ GAGAL (overfitting) |
| B5 | **Grid dua arah** (beli + jual) | belum diuji; butuh perp (spot tak bisa short) | ⏳ BELUM UJI |
| B6 | **Grid intraday 15m/1h** | hanya diuji di data harian | ⏳ BELUM UJI |
| B7 | **SNR sebagai filter** | lihat A1 | ❌ GAGAL |
| B8 | **Daily ratchet persen** (arm 8%, lock 60%, target 15%) | sudah jalan di simulator 3 panel | 🟡 MENUNGGU |
| B9 | **Panel A/B/C** (risk 2,5/5/7,5%) | simulator aktif, timer 30 s | 🟡 MENUNGGU |
| B10 | **Momentum Donchian 55 + trailing 3ATR + risiko 2%** | OOS 2,2 thn: **+9%, semua 6 koin positif, DD 10%**; sampel hanya 4–8 trade/koin | 🟡 MENUNGGU (sampel kecil) |

---

## C. Eksekusi (paling berdampak)

| # | Ide | Bukti | Status |
|---|---|---|---|
| C1 | **Slippage SL** — R tercatat −1,14 bukan −1,00 | 145 trade crypto: **~20R hilang** murni dari eksekusi; slippage 12% dari jarak SL | ✅ LOLOS (terukur) |
| C2 | **Perbaiki presisi SL** (toleransi 0,01/max(risk,1.0)) | sudah dipasang di EA | 🟡 MENUNGGU verifikasi live |
| C3 | **Ukur slippage forex** | butuh ≥30 fill; pasar tutup sampai Senin | 🟡 MENUNGGU |
| C4 | **`InpSlippage=30` no-op** | Market Execution mengabaikan parameter | ✅ LOLOS (temuan) |
| C5 | **Leverage 4x tak konsisten** | journal crypto: sizing tak seragam | ⏳ BELUM UJI |
| C6 | **Spread 350 pts = $0,35** (bukan $3,50) | digits=3; koreksi klaim sendiri | ✅ LOLOS (fakta) |

---

## D. Proteksi & Guard EA

| # | Ide | Bukti | Status |
|---|---|---|---|
| D1 | **Buffered Breakeven** (+1,2R, buffer 15 pts) | terpasang | ✅ LOLOS (desain) |
| D2 | **Partial TP 50%** di +1,0R | terpasang | ✅ LOLOS (desain) |
| D3 | **Dynamic Trailing** +1,5R | terpasang | ✅ LOLOS (desain) |
| D4 | **R3 fail-closed, R4 jarak relatif, R7 RRR guard** | terpasang & teruji | ✅ LOLOS |
| D5 | **MaxTradesPerDay** | belum ada di EA | ⏳ BELUM UJI |
| D6 | **Batas posisi terbuka** | belum ada di EA | ⏳ BELUM UJI |
| D7 | **Filter jam di EA** | lihat A2 — prior lemah | ❌ GAGAL |
| D8 | **Telemetri + pencatatan fill** | endpoint `/mt5/fill` + `/mt5/telemetry` aktif | ✅ LOLOS |

---

## E. Ide yang ditolak sejak awal (tidak akan diuji)

| # | Ide | Alasan |
|---|---|---|
| E1 | **Martingale** (lot berlipat saat rugi) | risiko tak terbatas; versi jinak grid saja sudah bangkrut |
| E2 | **Recovery mode** (balas rugi dengan lot lebih besar) | sama dengan martingale |
| E3 | **Menurunkan ambang Laya** agar lolos | SKIP adalah veto — menurunkan ambang = mengarang outcome |
| E4 | **Meniru P/L mentah PlanetX** | satuannya tak konsisten (win +13.876 vs +36.339) |
| E5 | **`perfect-entry` sebagai bukti** | bias hindsight (tag diberi setelah tahu hasil) |
| E6 | **Klaim "passive income" dari grid** | hasil in-sample pun tidak bertahan OOS |

---

## F. Ringkasan angka

**Diuji hari ini: 6 ide → 1 lolos sebagian, 5 gugur**

| Ide | Hasil akhir |
|---|---|
| SNR | p=0,741 ❌ |
| Jam XAUUSD | semua jam 42,6% ❌ |
| Grid XAUUSD | bangkrut ❌ |
| Grid crypto | mekanisme nyata ✅ tapi tanpa edge stabil |
| Hard stop grid | merusak ❌ |
| Filter rezim | OOS +4% ❌ |

**Pelajaran metodologis:** 3 dari 4 hasil "positif" hari ini ternyata **curve fitting**
saat diuji out-of-sample. Walk-forward bukan formalitas — itu satu-satunya yang
membedakan edge dari kebetulan.

---

## G. Urutan prioritas berikutnya

| Prioritas | Ide | Alasan |
|---|---|---|
| **1** | C1/C3 — ukur & perbaiki slippage | satu-satunya temuan dengan dasar kuat (20R hilang) |
| **2** | A4 — batas kepadatan posisi | efek besar in-sample, mudah diuji |
| **3** | A5 — buang panel Break&Retest | 69% kerugian dari 22% trade |
| **4** | A3 — filter jam crypto (OOS) | perlu data lebih panjang |
| **5** | D5/D6 — MaxTradesPerDay & batas posisi | guard yang belum ada |
| **6** | B5/B6 — grid dua arah / intraday | hanya kalau ingin lanjut eksplorasi grid |

**Yang TIDAK dikerjakan:** B1, B3, B4, A1, A2, D7 — sudah gagal, jangan diulang.

---

## H. Titik keputusan berikutnya

1. **Senin 05:00 WIB** — pasar buka, mulai kumpulkan fill untuk C3
2. **Setelah 30 fill** — evaluasi slippage: median ≤5 pt (lolos) / >15 pt (gagal)
3. **Setelah 60 trade panel** — evaluasi A4 & B9
4. **Sebelum tambah modal** — semua gate di `docs/roadmap-2026-Q4.md` harus lolos
