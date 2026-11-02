# Investigasi: Fungsi Laya AI di Server
Tanggal: 2026-11-02 | Status: investigasi selesai, temuan + rekomendasi

## Ringkasan Satu Paragraf
Laya AI **bukan** asisten chat terpisah — dia adalah **middleware keputusan trading + gate risiko** di dalam War Room, yang memanggil model HuggingFace `convaiinnovations/laya` untuk menilai sinyal forex/gold (BIAS) dan menjalankan sentinel latar (bias, blackout berita, gate keselamatan). Ada tiga peran: (1) **penilai sinyal** (`laya_forex`), (2) **sentinel latar** (`laya_sentinel`), (3) **gate data segar** (`laya_verdict` + timer systemd). Untuk Gold Reaper, Laya berperan sebagai lapisan konfirmasi/veto — penting untuk Wave 1-3.

## Komponen yang Ditemukan

| Komponen | Path | Fungsi |
|---|---|---|
| Penilai sinyal | `services/api/src/warroom_api/laya_forex.py` | Middleware panggil model `convaiinnovations/laya`, output verdict BIAS BULLISH/BEARISH/NEUTRAL + confidence, timeout & fallback |
| Sentinel latar | `services/api/src/warroom_api/laya_sentinel.py` | Loop background (startup app.py:79), status + bias global |
| Pemberitaan makro | `services/api/src/warroom_api/laya_news_fetcher.py` | RSS Fed press releases, keyword gold bull/bear, hitung skor sentimen |
| Blackout berita | `services/api/src/warroom_api/blackout.txt` | Daftar window blackout event makro |
| Gate verdict | `packages/core/src/warroom_core/forex/laya_verdict.py` | **FAIL-CLOSED**: jika verdict tidak segar → tolak eksekusi |
| Job verdict | `ops/laya_verdict_job.py` | Refresh cache verdict |
| Timer | `warroom-laya-verdict.service/.timer` (systemd) | Jadwal refresh verdict otomatis |

## Endpoint API (router tencent.py)
- `GET /forex/laya` — verdict lengkap (panggil model langsung) — `verify_mt5_or_admin`
- `GET /forex/laya/status` — status middleware (up/down, timeout, model)
- `GET /forex/laya/sentinel` — status sentinel (line 731)
- `GET /forex/laya/bias` — bias global (line 743)
- Middleware juga dites di test suite (grep "laya" → 7 file di `warroom_api/`)

## Arsitektur Laya (dari dokumen internal `arsitektur_laya_middleware_dan_strategi_scalper.md`)
- Laya = **filter/veto**, bukan generator sinyal. Strategi (scalper/gold reaper) menghasilkan sinyal → Laya menilai kondisi pasar → jika bias konflik/confidence rendah → sinyal ditolak.
- Model: `convaiinnovations/laya` (HuggingFace), dipanggil via ringkasan data MT5 mentah + telemetri.
- Timeout 120 detik; saat gagal/timeout → `tersedia: False, verdict: TAK_DIKETAHUI` (bukan BULLISH) ✅ fail-safe benar, tapi artinya **sinyal diblokir** karena gate fail-closed.

## Hubungan dengan Gold Reaper (Wave 1-3)
1. **Wave 1 (riset)**: verdict Laya bisa dipakai sebagai fitur tambahan di backtest — tapi harus ada **rekaman historis verdict**. Cek: apakah ada tabel/log historis verdict? Jika tidak ada, overlay Laya **tidak bisa di-backtest** dan hanya bisa dipakai forward (Wave 3).
2. **Wave 2**: integrasi eksplisit di interface `Strategy`: `signal → laya_veto → risk_check → order_intent`.
3. **Gate**: `laya_verdict` fail-closed = temuan **bagus** untuk disiplin risiko, tapi harus dipastikan tidak menyebabkan sistem mati total ketika cache basi (perilaku bisa menolak semua eksekusi).

## Temuan Berisiko (perlu tindakan)
1. **Cache verdict**: timer aktif tiap 60 detik, TTL 180 detik (margin 3x), cache terakhir 2026-11-02 → sehat. **Risiko**: bila job macet >180 detik, gate menolak semua eksekusi tanpa alarm.
2. **Fail-closed tanpa alert** = trade silently blocked. Butuh notifikasi ke Telegram owner.
3. **Tidak ada historisasi verdict** → tidak bisa backtest overlay Laya. Rekomendasi: mulai log verdict ke DB sejak Wave 1 (murah, berdampak besar).
4. **Model tunggal** (`convaiinnovations/laya`) — tidak ada fallback model. Nectere bisa jadi fallback jika Laya down.

## Rekomendasi (masuk rencana Wave 1-2)
- [ ] A2/B7: tambah tabel `laya_verdict_history` (symbol, ts, bias, confidence, source) — mulai dari sekarang
- [ ] A5: alert Telegram bila verdict basi / model gagal
- [ ] B2: evaluasi backtest **dengan** dan **tanpa** overlay Laya (setelah data historis terkumpul cukup; sementara pakai proxy news-sentiment dari `laya_news_fetcher`)
- [ ] Dokumentasi: Laya masuk dokumen arsitektur Quant Trading System sebagai "Risk & Macro Overlay Layer"

---

## UJI KAPABILITAS (probe langsung, 2026-11-02) — BUKTI EMPIRIS

Skenario probe: muat model di venv produksi (RAM 10 GB tersedia, 8 core), panggil
`laya.LayaEvaluator.invoke()` dengan konteks yang sama bentuknya dengan `susun_konteks()`.

### Hasil

| Input | Output | Catatan |
|---|---|---|
| Konteks kosong `{"symbol": None}` | SKIP, p(EXECUTE)=0.4908 | — |
| XAUUSD BUY bersih (tren selaras, SL 10, akun sehat) | SKIP, 0.2596 | 3x diulang → **identik** (0.2596) |
| XAUUSD SELL bersih (tren selaras) | SKIP, 0.2117 | — |
| XAUUSD BUY bodoh (floating −180, 3 posisi, free margin 40, ATR 20) | SKIP, 0.2710 | **lebih tinggi** dari BUY bersih |
| Replay 12 sinyal XAU asli dari DB Telegram | **12/12 SKIP** | 8 BUY → 0.2596 identik; 4 SELL → 0.195–0.212. Output hanya fungsi arah. |
| Input `"APEL"` | SKIP, 0.3034 | — |
| Input `"BUAH"` | SKIP, 0.1768 | — |

### Interpretasi
1. **Tidak pernah EXECUTE.** Bahkan untuk setup ideal. Ambang gate 0.60 tidak pernah tercapai (maks 0.49 di input kosong).
2. **Tidak membedakan sinyal buruk dari sinyal baik** — malah memberi skor lebih tinggi untuk kondisi berbahaya.
3. **Output deterministik per arah** → model pada dasarnya hanya membaca `sinyal_arah`, bukan kualitas setup, risiko, atau kondisi akun. Fitur lain (tren, SL, margin, ATR) **tidak terpakai** oleh model.
4. Model ini (ModernBERT 395M di subfolder `multilingual/`) adalah **classifier pemahaman, bukan model penalaran**: tak dilatih untuk menilai kualitas trade.

### Kesimpulan
**Laya (dalam bentuk sekarang) TIDAK layak jadi gate keputusan trading.** Sebagai gate, ia hanya menambah penolakan tanpa diskriminasi, dan menonaktifkan seluruh eksekusi. Bila diaktifkan dan dipakai di jalur eksekusi, sistem akan dead-lock secara permanen.

### Rekomendasi
1. **Jangan hidupkan `WARROOM_LAYA_ENABLE=1` sampai teruji.** Tetap OFF (sekarang memang OFF).
2. **Turunkan status Laya**: dari "gate" → "observability/telemetry" (mencatat; tidak mengosongkan).
3. **Bila tetap ingin ada lapisan penilai**: ganti dengan LLM reasoning nyata (Nectere) yang bisa dibandingkan A/B terhadap baseline deterministik. Ukur dengan metrik: apakah prediksi EXECUTE berkorelasi positif dengan PnL forward. Tanpa itu, lapisan ini menambah risiko, bukan mengurangi.
4. Jangan masukin Laya ke arsitektur Gold Reaper sebagai gate. **Engine risk (Wave 2, DD 10%) tetap jadi satu-satunya penentu eksekusi.**

**Catatan jujur**: probe dijalankan dengan 10 GB RAM bebas & 8 core — model (395M param) termuat normal tanpa OOM, jadi hasil konsisten ini mencerminkan kapabilitas asli model.
