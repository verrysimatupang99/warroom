# Peta market × bukti — arah "satu layar, teruji hasil" (6 Okt 2026)

Recon untuk permintaan owner: *"tiap market punya keunikan; tugas utama = bangun yang
bagus tampilannya DAN teruji hasilnya (akurasi sinyal, PnL paper per market); UI wajib
selaras dengan yang ada di balik layar"*. Acuan tampilan/produk: algentis + ihsgscreener.

Sumber: cronjob & skrip Tencent (baca-saja), ledger/jurnal yang ditarik ke
`/tmp/tencent_arsip/`, kode War Room, DB `warroom`, teardown ihsgscreener.

---

## 1. Kondisi nyata per market (6 Okt)

| Market | Sinyal (mesin) | Yang sudah terukur | Yang tampil di War Room |
|---|---|---|---|
| **Crypto** | `lt scan` (SMC 4H+1H), 463 verdict; Tencent `crypto-5agent-pipeline` (order flow + whale + F&G) | **Measurement gate kuat**: lolos n=145 WR 51,7% **+10,97R**; ditolak-bayangan n=204 WR 38,7% **−26,16R** → gate terbukti berguna | Equity **6 trade** +3,84R; pod & kandidat ✅ |
| **IDX** | Tencent: SCALP/INTRADAY/ARA/BSJP (5 watcher, semua **pause**) + `lt idx-tv` | **Terkuat**: ledger 628 sinyal (schema+grader v3, dedupe, cluster days) + jurnal 1.830 baris (1.158 EVAL); BSJP **+0,608R** (CI 0,12–1,06; 9 hari < 20), SCALP −0,011R, ARA −0,702R | Equity/ledger **0** (kosong) |
| **Forex** | Tencent: `xauusd-reactive`, `multi-pair-signal` (NAS100/EURUSD), journal-tracker | Tipis tapi serius: XAUUSD 5 trade (SL 3, TP2 1, NO FILL 1; reset v2 21 Sep, sebelumnya 9 sinyal WR 20%); multipair 11 tiket (8 closed, 1 SL) | Equity/ledger **0** (kosong) |
| **Polymarket** | `verdict-sync` (gate PM: NOT_PROVEN, deff 1,34) | Gate + parity + dataset (5,1 GB recorder) | Arm A–D, gate ✅ (n=4.133) |
| **GMGN / Meteora / Robinhood** | `lt radar-update` (baru, lokal); pool LP paper | LP paper 1 posisi (UBI, fee $1,31/hari est, IL −5,6%); radar V/L per chain | Radar ✅; LP posisi ✅; memecoin ✅ |

**Temuan kunci:** mesin ukur terbaik justru ada di Tencent (IDX ledger/grader, BSJP
walk-forward, jurnal XAUUSD + backtest MC 20 tahun), tapi **tidak mengalir ke War Room**.
Sebaliknya, blok equity/ledger per market di UI menampilkan **nol** padahal di Tencent
ada ribuan baris bukti. Ini pelanggaran prinsip "UI selaras dengan balik layar".

## 2. Keunikan tiap market (yang membedakan aturan, bukan selera)

| Market | Edge khas | Aturan yang wajib beda | Sumber data |
|---|---|---|---|
| Crypto | SMC POI + gate struktural; whale/OI/funding sebagai konteks | 24/7, funding, expiry 8 jam, klaster candle; gate lolos-vs-ditolak | Binance fapi, MEXC, Hyperliquid |
| IDX | BSJP (beli sore jual pagi, walk-forward), ARA, bandarmologi (aliran broker) | Jam bursa, ARA/ARB, T+2, lot 100, foreign flow; sampel per **hari** (klaster) | Arjum (kuota 6.003/hari), TradingView, tick WS |
| Forex | SMC multi-TF XAUUSD; sesi London/NY; backtest MC 20 tahun | Sesi & DST, spread, per-pair pip value, max 2 posisi total | TradingView TVC:GOLD/OANDA |
| Polymarket | Binary outcome, gate statistis (ci_low > BE), parity paper≡live | Probabilitas, geoblock, deff klaster | recorder 5,1 GB + verdicts |
| Meteora/LP (Solana/Robinhood) | Fee churn pool muda (V/L), IL vs hold | Fee tier + porsi in-range, umur pool, urutkan **volume** bukan likuiditas | DexScreener, gmgn-cli |

## 3. Standar bukti yang sudah terbukti (dipakai di Tencent, layak diangkat)

`signal-performance-validation` (skill Tencent) — **schema ledger + gate**:
`event_id` deterministik · level wajib (entry_low/high, sl, tp1/2) · state machine
CREATED→FILLED→TP1/TP2/SL/PENDING/**AMBIGUOUS** · metrik hanya dari **closed** ·
exclude duplikat/no-trade/ambiguous · gate: `<10` INSUFFICIENT · `10–29` DIRECTIONAL_ONLY ·
`≥30` PRELIMINARY · `≥100` TUNING (butuh uji tail/stabilitas) ·
**win rate tinggi tak pernah cukup** — wajib expectancy bersih + biaya tercatat.

Ditambah pelajaran Tencent IDX: **koreksi klaster hari** ("efektif N=11 hari, bukan 35 trade")
— sudah dipakai di drift/CI.

## 4. ihsgscreener — yang mereka tawarkan (teardown singkat)

- **Visual**: navy gelap (`#030c12`, panel `#0a1622`), cyan `#00c8ff` + hijau `#00e5a0`,
  JetBrains Mono untuk angka, Space Grotesk untuk teks — **dekat** dengan arah War Room
  (Beebots/ihsg/algentis); gap utamanya CSS `app.css` yang masih memuat sisa 3 tema.
- **Produk**: Screener 956 emiten + **AI Intelligence Score** (undervalue/fair/danger),
  fundamental (PER/PBV/ROE) + teknikal + perbandingan sektor + verdict, watchlist pribadi
  ("pantau **Akurasi Signal** IHSG Screener"), market overview & update real-time.
- **Catatan jujur**: halaman yang bisa dibaca publik menampilkan data statis (tanggal
  contoh 14 Mar 2026) — jadi belum bisa diverifikasi sebagai live. Yang bisa ditiru:
  *struktur produk* (score + reason + watchlist + akurasi), bukan klaimnya.

**Padanan untuk War Room**: satu "skor peluang + alasan + level" per emiten/pair, halaman
per market dengan daftar kandidat + status sinyal + track record akurasi, dan watchlist.
Untuk GMGN/Meteora: skor pool (V/L, HP, umur, fee APR terukur) + posisi LP + IL vs hold.

## 5. Kesenjangan terukur (gap list)

1. **IDX**: 628 sinyal + BSJP terbukti — belum ada jalur ke War Room; UI nol.
2. **Forex**: 5 trade XAUUSD + backtest MC 20 th — belum masuk; UI nol.
3. **Crypto**: gate terukur ✅ tapi paper trade tipis (6); 5-agen pipeline Tencent belum diserap.
4. **LP Meteora/Robinhood**: posisi & fee est ✅; harga mark belum otomatis (butuh keputusan sumber).
5. **UI**: blok per market kosong karena fakta tidak ada; belum ada halaman "akurasi/skor".
6. **⚠️ Risiko aktif**: `crypto-auto-exec-653` (Tencent, ON) masih eksekusi **uang nyata MEXC**
   (`limit_order` real; satu order kena restriksi akun 6002). Tidak terlihat dari War Room.

## 6. Pertanyaan terbuka untuk owner → lihat jawaban di sesi ini

Dipakai untuk memutuskan urutan kerja; semua rekomendasi default ada di pertanyaan.
