//+------------------------------------------------------------------+
//|                                                     MTRB_Pro.mq5 |
//|   Scalper multi-timeframe (D1..M1) + panel + monitor news        |
//|   Dirancang untuk XAUUSDc (akun cent), lot tetap 0.01            |
//|   v1.10: filter VWAP / PDH-PDL / ATR, twin order (scalper +      |
//|          runner), ratchet SL, squeeze, ekspansi TP, cooldown     |
//+------------------------------------------------------------------+
#property copyright "MTRB Pro"
#property version   "3.07"
#property description "Scalper MTF: bias D1..M1, entry pullback M1, twin order + ratchet, panel + news"

#include <Trade/Trade.mqh>

//--- input ---------------------------------------------------------
input group "=== Umum ==="
input long   InpMagic          = 772001;   // Magic number
input double InpLot            = 0.01;     // Lot tetap per tiket
input int    InpSlippagePts    = 50;       // Slippage maks (points)

input group "=== Mode ==="
input bool   InpExtremeMode    = false;    // Mode Extreme: syarat entry dilonggarkan supaya lebih sering trade (bisa diubah dari dashboard)

input group "=== Strategi yang dijalankan (bisa bersamaan) ==="
input bool   InpEnableMain     = false;    // Strategi utama (mode entry di grup Entry)
input bool   InpEnableHB       = true;     // Strategi breakout H4
input bool   InpEnableORB      = true;     // Strategi opening-range breakout
input bool   InpEnableTL       = true;     // Strategi garis tren (break - retest - close)
input bool   InpEnableHB2      = true;     // Breakout di timeframe kedua
input ENUM_TIMEFRAMES InpHbTF2 = PERIOD_H1; // Timeframe breakout kedua
input bool   InpEnableHB3      = false;    // Breakout di timeframe ketiga (menambah trade, kualitas lebih rendah)
input ENUM_TIMEFRAMES InpHbTF3 = PERIOD_M30; // Timeframe breakout ketiga
input bool   InpEnableTL2      = true;     // Garis tren di timeframe kedua
input ENUM_TIMEFRAMES InpTlTF2 = PERIOD_M30; // Timeframe garis tren kedua

input bool   InpEnableSMC      = false;    // Strategi SMC (liquidity sweep + order block + FVG)
input bool   InpEnableMOM      = false;    // Strategi momentum M30 dengan entry M5
input bool   InpEnableRSM      = false;    // Strategi RSI + Moving Average (M5)

input bool   InpEnableDIP      = true;     // Strategi scalping koreksi (M5)

input group "=== Strategi: pola candle + RSI (Dark Cloud / Piercing Line / Hanging Man / Hammer) ==="
input bool   InpEnableCDL      = true;     // Strategi pola candle + RSI
input ENUM_TIMEFRAMES InpCdlTF = PERIOD_M5; // Timeframe
input bool   InpCdlDarkPierce  = true;     // Pola Dark Cloud Cover (sell) dan Piercing Line (buy)
input bool   InpCdlHangHammer  = true;     // Pola Hanging Man (sell) dan Hammer (buy)
input int    InpCdlBodyPeriod  = 12;       // Rata-rata badan candle dari N candle
input int    InpCdlMaPeriod    = 5;        // MA tren (SMA)
input int    InpCdlRsiPeriod   = 37;       // RSI
input double InpCdlRsiBuy      = 40.0;     // Buy hanya jika RSI di bawah ini
input double InpCdlRsiSell     = 60.0;     // Sell hanya jika RSI di atas ini
input double InpCdlSL          = 2.0;      // SL (USD harga; 200 point di emas)
input double InpCdlTP          = 2.0;      // TP (USD harga)
input int    InpCdlMaxBars     = 10;       // Tutup posisi setelah N candle (0 = off)
input bool   InpCdlExitRsi     = true;     // Keluar saat RSI memotong 30 / 70
input double InpCdlMaxSpread   = 0.60;     // Spread maks (USD harga)

input group "=== Strategi: NadirAliOfficial (3 EMA + PSAR, bar 10 detik) ==="
input bool   InpEnableNAO      = true;     // Strategi NadirAliOfficial
input int    InpNaoFastEma     = 5;        // EMA cepat
input int    InpNaoMidEma      = 20;       // EMA tengah
input int    InpNaoSlowEma     = 40;       // EMA lambat
input double InpNaoSarStep     = 0.02;     // PSAR step
input double InpNaoSarMax      = 0.2;      // PSAR maksimum
input bool   InpNaoRequireM5   = true;     // M5 harus searah M1
input int    InpNaoConfirmBars = 1;        // PSAR harus bertahan N bar 10 detik setelah berbalik
input int    InpNaoExitMode    = 0;        // Keluar: 0 = PSAR 10 detik berbalik, 1 = tutup melewati EMA cepat
input double InpNaoSL          = 2.0;      // SL pengaman (USD harga; 200 point di emas)
input double InpNaoTP          = 0.0;      // TP (USD harga, 0 = tanpa TP)
input double InpNaoMaxSpread   = 0.30;     // Spread maks (USD harga; 30 point)
input int    InpNaoHourFrom    = 9;        // Entry mulai jam (waktu server)
input int    InpNaoHourTo      = 21;       // Entry sampai sebelum jam (waktu server)
input int    InpNaoMaxBars     = 800;      // Jumlah bar 10 detik yang disimpan

input group "=== Strategi: scalping koreksi searah tren ==="
input ENUM_TIMEFRAMES InpDipTF = PERIOD_M5; // Timeframe
input int    InpDipCandles     = 3;        // Jumlah candle koreksi berturut-turut
input int    InpDipTrendEma    = 2400;     // EMA tren (2400 di M5 setara EMA50 di H4)
input double InpDipVolMult     = 1.25;     // Pasar "ramai" jika ATR > N x median ATR
input int    InpDipVolBars     = 1440;     // Median ATR dihitung dari N candle (1440 = 5 hari)
input double InpDipSLAtr       = 1.0;      // SL = ATR x ini
input double InpDipMinSL       = 2.0;      // SL minimal (USD harga)
input double InpDipMaxSL       = 12.0;     // SL maksimal (USD harga)
input double InpDipTP          = 1.0;      // TP = SL x ini
input int    InpDipMaxMin      = 60;       // Tutup posisi setelah N menit (0 = off)
input int    InpDipHourFrom    = 1;        // Entry mulai jam (waktu server)
input int    InpDipHourTo      = 22;       // Entry sampai sebelum jam (waktu server)
input double InpDipMaxSpread   = 0.60;     // Spread maks (USD harga)

input group "=== Strategi: Range Hybrid (optimasi) ==="
input bool   InpEnableRangeHybrid = true;     // Strategi Range Hybrid
input ENUM_TIMEFRAMES InpRangeTF  = PERIOD_M5; // Timeframe
input int    InpRhLookback        = 40;       // Candle untuk hitung High/Low & touch
input int    InpRhAdxPeriod       = 14;       // ADX period
input double InpRhScale           = 1.0;      // Pengali SEMUA angka jarak di bawah (1 = persis spesifikasi)
input double InpAdxStrict         = 19.0;     // ADX di bawah ini = Strict
input double InpAdxDetail         = 23.5;     // ADX di bawah ini = Detail (di atas = Off)
input double InpMinWidthStrict    = 6.5;     // Minimal lebar range untuk Strict
input double InpMinWidthDetail    = 4.5;     // Minimal lebar range untuk Detail
input double InpRhForceOffWidth   = 16.0;     // Range melebar melewati ini -> Off sementara
input int    InpRhForceOffMin     = 90;       // Lama Off setelah range melebar (menit)
input double InpTouchBuffer       = 0.80;     // Jarak dianggap "menyentuh" range
input double InpSLBufferStrict    = 2.20;     // SL di luar range + ini (Strict)
input double InpSLBufferDetail    = 2.80;     // SL di luar range + ini (Detail)
input bool   InpRhUseRisk         = true;     // Lot dari % risiko (false = lot tetap InpLot)
input double InpRiskStrict        = 0.45;     // % risiko per trade mode Strict
input double InpRiskDetail        = 0.65;     // % risiko per trade mode Detail
input double InpRhMaxLot          = 0.10;     // Batas lot absolut
input int    InpMaxTradeStrict    = 4;        // Maks trade per hari saat Strict
input int    InpMaxTradeDetail    = 7;        // Maks trade per hari saat Detail
input double InpRhMaxSpread       = 0.30;     // Spread maks (USD harga)
input int    InpRhSessionStart    = 15;       // Entry mulai jam (waktu server)
input int    InpRhSessionEnd      = 23;       // Entry sampai sebelum jam (waktu server)
input bool   InpUsePartialDetail  = true;     // Partial close hanya di mode Detail
input double InpPartialPercent    = 50.0;     // Persen lot yang ditutup di tengah range
input int    InpTrailPoints       = 70;       // Trailing sisa posisi (point)
input double InpRhStrictBEAt      = 0.55;     // Strict: SL ke breakeven setelah bagian ini dari jarak ke TP
input int    InpRhLossPause       = 2;        // Loss beruntun sebelum jeda
input int    InpRhLossPauseMin    = 90;       // Lama jeda setelah loss beruntun (menit)
input int    InpRhMinRangeAge     = 12;       // Range minimal sudah bertahan X candle
input double InpRhMinDistMid      = 1.80;     // Jarak minimal entry dari tengah range
input int    InpRhPartialCooldown = 3;        // Candle tanpa entry baru setelah partial
input bool   InpRhAdaptive        = true;     // Lebar adaptif: batas lebar dari ATR, bukan angka tetap
input double InpRhAtrMinMult      = 2.8;      // Adaptif: lebar minimal = ATR(14) x ini (Strict lebih lebar sesuai rasio MinWidth)
input double InpRhAtrOffMult      = 6.5;      // Adaptif: range dianggap terlalu lebar di atas ATR(14) x ini
input double InpRhAtrRiseMax      = 1.25;     // Tidak entry jika ATR naik melebihi x kali ATR beberapa candle lalu (0 = off)
input int    InpRhAtrRiseBars     = 6;        // Pembanding ATR: N candle lalu
input int    InpRhMinTouch        = 2;        // Minimal sentuhan di tepi atas DAN tepi bawah sebelum entry (0 = off)
input int    InpMagicRange        = 772110;   // Magic number khusus Range Hybrid

input group "=== Pemisahan mesin per sesi ==="
input bool   InpSessionSplit      = true;     // Asia: Range Hybrid (+DIP). London-NY: Breakout, Momentum, Garis tren
input bool   InpSplitDip          = true;     // DIP ikut dibatasi ke sesi Asia

input group "=== Strategi: RSI + Moving Average ==="
input ENUM_TIMEFRAMES InpRsmTF = PERIOD_M5; // Timeframe
input int    InpRsmMaPeriod    = 100;      // Moving Average (close)
input int    InpRsmRsiPeriod   = 50;       // RSI
input int    InpRsmSmooth      = 50;       // Penghalus RSI (WMA) = garis sinyal
input int    InpRsmSwing       = 10;       // SL di swing low/high N candle terakhir
input double InpRsmSLBuf       = 0.20;     // Jarak tambahan SL di balik swing (USD harga)
input double InpRsmMinSL       = 1.0;      // SL minimal (USD harga)
input bool   InpRsmExitOnFlip  = true;     // Keluar saat garis sinyal balik melewati 50
input double InpRsmRR          = 0.0;      // TP = SL x ini (0 = tanpa TP)
input double InpRsmBE_R        = 0.0;      // SL ke breakeven saat profit >= N x R (0 = off)
input int    InpRsmHourFrom    = 2;        // Entry mulai jam (waktu server)
input int    InpRsmHourTo      = 23;       // Entry sampai sebelum jam (waktu server)
input double InpRsmMaxSpread   = 0.60;     // Spread maks (USD harga)

input group "=== Strategi: momentum M30 -> entry M5 ==="
input ENUM_TIMEFRAMES InpMomBiasTF  = PERIOD_M30; // Timeframe peta arah (dua candle searah)
input ENUM_TIMEFRAMES InpMomEntryTF = PERIOD_M5;  // Timeframe entry
input double InpMomImpulseAtr  = 1.0;      // Badan candle pertama (impulsif) minimal (x ATR)
input double InpMomFib         = 0.50;     // Level retrace di dalam range dua candle (0.382 / 0.5 / 0.618)
input bool   InpMomConfirm     = true;     // Tunggu candle entry menutup searah setelah menyentuh level
input double InpMomRR          = 2.0;      // TP = SL x ini (1:2 atau 1:3)
input double InpMomSLBufAtr    = 0.10;     // Jarak SL di balik high/low range (x ATR)
input int    InpMomExpiryBars  = 6;        // Setup batal jika tidak ada retrace dalam N bar
input bool   InpMomTrendFilter = false;    // Hanya searah tren D1
input double InpMomMaxSpread   = 0.60;     // Spread maks (USD harga)

input group "=== Strategi: SMC (sweep - order block - FVG - re-entry) ==="
input ENUM_TIMEFRAMES InpSmcTF = PERIOD_M15; // Timeframe eksekusi
input bool   InpSmcTrendFilter = true;     // Konteks: hanya searah tren D1
input int    InpSmcPivot       = 3;        // Swing high/low: N bar di kiri dan kanan
input int    InpSmcLookback    = 80;       // Jumlah bar untuk mencari level likuiditas
input int    InpSmcSweepBars   = 8;        // Sweep harus terjadi dalam N bar sebelum displacement
input int    InpSmcMssBars     = 5;        // Displacement harus menembus high N bar sebelum sweep
input double InpSmcDispAtr     = 0.8;      // Badan candle displacement minimal (x ATR)
input double InpSmcMinGapAtr   = 0.10;     // Lebar FVG minimal (x ATR)
input int    InpSmcEntryMode   = 0;        // Entry: 0 = tepi FVG, 1 = tengah FVG, 2 = tepi order block
input bool   InpSmcStopAtOB    = false;    // SL dirapatkan ke balik order block (bukan balik sweep)
input double InpSmcSLBufAtr    = 0.30;     // Jarak SL di balik level (x ATR)
input double InpSmcRR          = 2.0;      // TP = SL x ini
input bool   InpSmcTPatLiquidity = false;  // TP di high/low sebelumnya (likuiditas seberang)
input int    InpSmcExpiryBars  = 20;       // Setup batal jika harga tidak kembali dalam N bar
input double InpSmcBE_R        = 0.0;      // SL ke breakeven saat profit >= N x R (0 = off)
input double InpSmcMaxSpread   = 0.60;     // Spread maks (USD harga)

input group "=== Strategi: garis tren (top-down, break - retest - close) ==="
input ENUM_TIMEFRAMES InpTlTF  = PERIOD_H1; // Timeframe eksekusi
input bool   InpTlTrendFilter  = true;     // Top-down: hanya searah tren D1
input int    InpTlPivot        = 5;        // Swing high/low: N bar di kiri dan kanan
input int    InpTlLookback     = 200;      // Jumlah bar untuk mencari garis
input int    InpTlMinSpan      = 10;       // Jarak minimal dua titik garis (bar)
input int    InpTlMinTouches   = 3;        // Minimal jumlah sentuhan pada garis
input double InpTlTolAtr       = 0.25;     // Toleransi sentuhan (x ATR)
input double InpTlBreakAtr     = 0.20;     // Break sah jika menutup melewati garis sejauh ini (x ATR)
input int    InpTlRetestBars   = 12;       // Batas menunggu retest setelah break (bar)
input double InpTlMaxEntryAtr  = 0.0;      // Tolak entry jika harga sudah lebih jauh dari garis daripada ini (x ATR, 0 = off)
input double InpTlSLBufAtr     = 0.50;     // Jarak SL di balik garis / candle retest (x ATR)
input double InpTlRR           = 0.0;      // TP = SL x ini (0 = tanpa TP: keluar lewat garis tren seberang)
input bool   InpTlTPatSR       = false;    // TP di support/resistance terdekat (high/low sebelumnya)
input bool   InpTlTrailLine    = true;     // Trailing SL mengikuti garis tren seberang
input bool   InpTlExitViolation = true;    // Keluar jika candle menutup menembus garis tren seberang
input double InpTlMaxSpread    = 0.60;     // Spread maks (USD harga)
input bool   InpTlAlerts       = true;     // Alert saat break dan saat entry
input bool   InpTlDraw         = true;     // Gambar garis tren di chart

input group "=== Strategi: breakout H4 ==="
input ENUM_TIMEFRAMES InpHbTF  = PERIOD_H4; // Timeframe breakout
input int    InpHbLookback     = 55;       // Tembus high/low N bar
input double InpHbSLAtr        = 1.5;      // SL = ATR x ini
input double InpHbRR           = 3.0;      // TP = SL x ini
input double InpHbMaxSpread    = 1.0;      // Spread maks (USD harga)

input group "=== Bias multi-timeframe ==="
input int    InpEmaFast        = 21;       // EMA cepat
input int    InpEmaSlow        = 50;       // EMA lambat
input double InpW_D1           = 1.0;      // Bobot D1
input double InpW_H4           = 2.0;      // Bobot H4
input double InpW_H1           = 3.0;      // Bobot H1
input double InpW_M30          = 2.0;      // Bobot M30
input double InpW_M15          = 3.0;      // Bobot M15
input double InpW_M5           = 2.0;      // Bobot M5
input double InpW_M1           = 1.0;      // Bobot M1
input double InpMinScore       = 60.0;     // Skor minimal untuk entry (0-100)
input bool   InpRequireH1M15   = true;     // H1 dan M15 wajib searah

enum ENTRY_MODE
  {
   ENTRY_PULLBACK = 0,   // Pullback ke EMA lalu tutup searah tren
   ENTRY_BREAKOUT = 1,   // Breakout high/low N bar
   ENTRY_ZONE     = 2,   // Sentuh EMA lalu tutup melewati high/low bar sebelumnya
   ENTRY_DIP      = 3,   // RSI jenuh berlawanan tren lalu berbalik
   ENTRY_SWEEP    = 4,   // Sapu low/high N bar lalu tutup kembali di dalam
   ENTRY_BIAS     = 5,   // Tanpa pemicu (kontrol: hanya bias + filter)
   ENTRY_MAMACD   = 6,   // MA5 potong MA10, searah MA30, konfirmasi MACD
   ENTRY_ORB      = 7    // Opening-range breakout: tutup di luar range pembukaan sesi
  };

enum ORB_STOP
  {
   ORB_STOP_MID = 0,     // Tengah range
   ORB_STOP_OPP = 1,     // Sisi seberang range
   ORB_STOP_ATR = 2      // ATR (pakai setelan SL / TP)
  };

input group "=== Entry ==="
input ENTRY_MODE      InpEntryMode = ENTRY_MAMACD;   // Jenis pemicu entry
input ENUM_TIMEFRAMES InpSignalTF  = PERIOD_M15;     // Timeframe pemicu
input bool   InpUseBias        = true;     // Pakai bias multi-timeframe (false = arah dari sinyal)
input int    InpMaFast         = 5;        // Mode MA+MACD: MA cepat
input int    InpMaMid          = 10;       // Mode MA+MACD: MA tengah
input int    InpMaSlow         = 30;       // Mode MA+MACD: MA lambat
input bool   InpMaRequireSlow  = true;     // Mode MA+MACD: harga dan MA tengah harus di sisi MA lambat
input int    InpMacdFast       = 12;       // MACD cepat
input int    InpMacdSlow       = 26;       // MACD lambat
input int    InpMacdSignal     = 9;        // MACD sinyal

input group "=== Strategi: opening-range breakout ==="
input int    InpOrbHour        = 3;        // Jam buka sesi (waktu server)
input int    InpOrbMinute      = 0;        // Menit buka sesi
input int    InpOrbRangeMin    = 30;       // Lama range pembukaan (menit)
input ENUM_TIMEFRAMES InpOrbSignalTF = PERIOD_M5; // Timeframe candle penembus
input double InpOrbRR          = 2.0;      // TP = SL x ini (0 = tanpa TP)
input double InpOrbMinSL       = 1.0;      // SL minimal (USD harga)
input double InpOrbMaxSpread   = 0.60;     // Spread maks (USD harga)
input int    InpOrbWindowMin   = 120;      // Batas entry setelah range selesai (menit)
input int    InpOrbFlatMin     = 360;      // Tutup semua posisi N menit setelah sesi buka (0 = off)
input ORB_STOP InpOrbStop      = ORB_STOP_MID; // Letak stop
input bool   InpOrbLongOnly    = false;    // Hanya breakout ke atas

input group "=== Sesi pasar (waktu server) ==="
input bool   InpSessAsia       = true;     // Boleh entry di sesi Asia (00:00 sampai buka London)
input bool   InpSessLondon     = true;     // Boleh entry di sesi London
input bool   InpSessNY         = true;     // Boleh entry di sesi New York (sampai 24:00)
input int    InpSessLondonHour = 9;        // Jam buka London (waktu server)
input int    InpSessNYHour     = 15;       // Jam buka New York (waktu server)

input group "=== Risk manager portofolio (semua strategi tambahan) ==="
input double InpMaxOpenRisk    = 100.0;    // Total rugi-di-SL semua posisi terbuka + trade baru maks (mata uang akun, 0 = off)
input double InpPortDailyLossPct = 4.0;    // Stop entry baru jika equity hari ini turun >= % ini (0 = off)
input double InpSLMinPerTrade  = 0.0;      // SL minimal per trade (mata uang akun, 0 = ikut strategi)
input double InpSLMaxPerTrade  = 0.0;      // SL maksimal per trade (mata uang akun, 0 = ikut strategi)

input group "=== Ambil untung global (semua mesin, bisa diubah dari dashboard) ==="
input int    InpTpMode         = 0;        // 0 = ikut strategi, 1 = TP tetap, 2 = trailing stop, 3 = pindah SL
input double InpTpUsd          = 10.0;     // Mode 1: tutup saat profit posisi mencapai ini (mata uang akun)
input double InpTrailStartUsd  = 5.0;      // Mode 2: trailing mulai setelah profit mencapai ini
input double InpTrailDistUsd   = 3.0;      // Mode 2: jarak SL di belakang harga
input double InpBeAtUsd        = 5.0;      // Mode 3: pindah SL setelah profit mencapai ini
input double InpBeLockUsd      = 1.0;      // Mode 3: profit yang dikunci (0 = tepat di harga entry)

input group "=== Risk manager ==="
input double InpMaxLossPerTrade = 0.0;     // Tolak trade jika rugi di SL > nilai ini (mata uang akun, 0 = off)
input double InpTrailStartUSD  = 0.0;      // Trailing stop USD: mulai setelah profit sejauh ini (USD harga)
input double InpTrailDistUSD   = 0.0;      // Trailing stop USD: jarak SL dari harga (USD harga, 0 = off)
input double InpTrailStepUSD   = 0.20;     // Langkah minimal perpindahan SL
input bool   InpTrailMain      = true;     // Trailing stop USD berlaku untuk strategi utama
input bool   InpTrailHB        = true;     // Pengelolaan SL berlaku untuk breakout H4
input bool   InpTrailORB       = true;     // Pengelolaan SL berlaku untuk ORB

input group "=== Pengelolaan SL strategi tambahan (R = jarak SL awal) ==="
input double InpHbBE_R         = 0.0;      // H4: SL ke breakeven saat profit >= N x R (0 = off)
input double InpHbTrailStartR  = 1.0;      // H4: trailing mulai saat profit >= N x R
input double InpHbTrailDistR   = 1.5;      // H4: jarak trailing = N x R (0 = off)
input double InpOrbBE_R        = 0.5;      // ORB: SL ke breakeven saat profit >= N x R (0 = off)
input double InpOrbTrailStartR = 0.0;      // ORB: trailing mulai saat profit >= N x R
input double InpOrbTrailDistR  = 0.0;      // ORB: jarak trailing = N x R (0 = off)
input double InpSmHalfAtR      = 0.0;      // Pangkas risiko jadi setengah saat profit >= N x R (0 = off)
input double InpSmBE_USD       = 0.0;      // SL ke breakeven saat profit >= N USD harga (0 = off)
input double InpSmBEOffset     = 0.30;     // Breakeven + offset ini (menutup spread)
input bool   InpSmTrailCapBE   = false;    // Trailing berhenti di breakeven (hanya mengurangi rugi)
input int    InpLookback       = 20;       // Jumlah bar untuk breakout / sweep
input double InpDipRsi         = 35.0;     // Mode DIP: RSI <= ini untuk BUY (SELL: >= 100 - ini)
input int    InpAdxPeriod      = 14;       // ADX period (M15)
input double InpMinADX         = 20.0;     // ADX minimal
input int    InpRsiPeriod      = 14;       // RSI period (M5)
input double InpRsiOB          = 70.0;     // Jangan BUY jika RSI di atas ini
input double InpRsiOS          = 30.0;     // Jangan SELL jika RSI di bawah ini
input int    InpTriggerEma     = 20;       // EMA pullback di M1
input bool   InpUseVWAP        = true;     // BUY hanya di atas VWAP harian, SELL di bawah
input bool   InpUsePDGuard     = true;     // Hindari entry menempel high/low kemarin
input double InpPDGuardDist    = 1.0;      // Jarak aman dari high/low kemarin (USD)

input group "=== SL / TP ==="
input ENUM_TIMEFRAMES InpAtrTF = PERIOD_M5; // Timeframe ATR untuk SL
input int    InpAtrPeriod      = 14;       // ATR period
input double InpAtrMin         = 1.0;      // ATR M5 minimal (USD) - pasar terlalu sepi
input double InpAtrMax         = 12.0;     // ATR M5 maksimal (USD) - pasar terlalu liar
input double InpSLAtr          = 1.4;      // SL = ATR x ini
input double InpMinSL          = 4.0;      // SL minimal (jarak harga, USD)
input double InpMaxSL          = 12.0;     // SL maksimal (jarak harga, USD)
input double InpRR             = 1.5;      // TP = SL x ini (mode satu tiket)

input group "=== Twin order (butuh akun hedging) ==="
input bool   InpTwinOrder      = true;     // Buka 2 tiket: scalper + runner
input double InpScalpTpR       = 0.7;      // TP tiket scalper (x R)
input double InpRunnerTpR      = 2.0;      // TP awal tiket runner (x R)

input group "=== Pengunci profit ==="
input double InpBE_R           = 1.0;      // Breakeven di profit x R (runner: saat scalper TP)
input double InpBEOffset       = 0.30;     // Offset breakeven (USD)
input bool   InpUseRatchet     = true;     // Kerek SL bertahap
input double InpRatchetStepR   = 0.5;      // Langkah ratchet (x R)
input double InpSqueezeDistR   = 0.3;      // Rapatkan SL jika sisa ke TP <= ini (x R)
input double InpSqueezeLockR   = 0.35;     // Jarak SL dari harga saat dirapatkan (x R)
input double InpTpExpandR      = 1.5;      // Perpanjang TP runner saat momentum kuat (x R, 0 = off)
input double InpExpandRsi      = 60.0;     // RSI momentum kuat (BUY > ini, SELL < 100 - ini)

input group "=== Filter & proteksi ==="
input double InpMaxSpread      = 0.40;     // Spread maks (jarak harga, USD)
input int    InpSessStartHour  = 9;        // Jam mulai trading (waktu server)
input int    InpSessEndHour    = 22;       // Jam selesai trading (waktu server)
input bool   InpAvoidRollover  = true;     // Hindari 21:55-22:10 server (rollover)
input int    InpFridayStopHour = 21;       // Jumat: stop entry mulai jam ini
input int    InpMaxTradesDay   = 8;        // Maks setup per hari
input int    InpMaxConsecLoss  = 3;        // Stop setelah loss beruntun (per hari)
input int    InpCooldownMin    = 10;       // Jeda setelah tiket rugi (menit)
input double InpDailyLossPct   = 5.0;      // Stop jika rugi harian >= % saldo
input double InpDailyProfitPct = 8.0;      // Stop jika profit harian >= % saldo (0 = off)

input group "=== Target harian (pips) ==="
input double InpPipSize        = 0.10;     // Ukuran 1 pip dalam harga (emas: 0.10 USD)
input double InpDayTargetPips  = 100.0;    // Stop hari itu setelah profit >= pips ini (0 = off)
input double InpDayMaxLossPips = 30.0;     // Stop hari itu setelah loss >= pips ini (0 = off)
input double InpSLPips         = 0.0;      // SL tetap dalam pips (0 = pakai ATR)
input double InpTPPips         = 0.0;      // TP tetap dalam pips (0 = pakai R, mode satu tiket)

input group "=== News ==="
input bool   InpUseNews        = true;     // Pause trading saat news high impact
input string InpNewsCurrency   = "USD";    // Mata uang news
input int    InpNewsBeforeMin  = 30;       // Pause sebelum news (menit)
input int    InpNewsAfterMin   = 30;       // Pause setelah news (menit)

input group "=== Estimasi Buy/Sell volume ==="
input int    InpFlowMode       = 1;        // 0 = mati, 1 = tampil dan dicatat saja, 2 = filter entry (bisa diubah dari dashboard)
input int    InpFlowBars       = 20;       // Jumlah candle untuk CVD (delta kumulatif)
input double InpFlowTrendPct   = 55.0;     // Mesin searah: porsi volume searah entry minimal (%)
input double InpFlowRevPct     = 60.0;     // Mesin pembalikan: tolak jika dorongan lawan >= % ini
input int    InpFlowTickMaxMin = 15;       // Hitung per tick untuk timeframe <= N menit (di atasnya pakai posisi close di candle)

input group "=== Pencatat trade (bahan analisa) ==="
input bool   InpTradeLog       = true;     // Catat kondisi pasar tiap entry dan hasilnya ke CSV (Common\Files)

input group "=== Dashboard ==="
input bool   InpDashboard      = true;     // Kirim status ke dashboard dan terima perintah darinya
input int    InpStatusRefreshMin = 5;      // Perbarui status tiap strategi setiap N menit (0 = hanya saat bar baru)

input group "=== Panel ==="
input bool   InpShowPanel      = true;     // Tampilkan panel
input int    InpPanelX         = 10;       // Posisi X
input int    InpPanelY         = 20;       // Posisi Y

input group "=== Laporan backtest ==="
input string InpReportTag      = "";       // Label file laporan (opsional)

//--- global --------------------------------------------------------
#define PFX       "MTRB_"
#define NTF       7
#define CMT_ONE   "MTRB Pro"
#define CMT_SCALP "MTRB SCALP"
#define CMT_RUN   "MTRB RUN"
#define CMT_HB    "MTRB H4BO"
#define CMT_ORB   "MTRB ORB"
#define CMT_TL    "MTRB TL"
#define CMT_SMC   "MTRB SMC"

CTrade          trade;
ENUM_TIMEFRAMES g_tf[NTF]     = {PERIOD_D1, PERIOD_H4, PERIOD_H1, PERIOD_M30, PERIOD_M15, PERIOD_M5, PERIOD_M1};
string          g_tfName[NTF] = {"D1", "H4", "H1", "M30", "M15", "M5", "M1"};
double          g_w[NTF];
int             g_hFast[NTF], g_hSlow[NTF];
int             g_bias[NTF];
int             g_hAdx = INVALID_HANDLE, g_hRsi = INVALID_HANDLE, g_hAtr = INVALID_HANDLE, g_hTrig = INVALID_HANDLE;
int             g_hSigRsi = INVALID_HANDLE;
int             g_hMaF = INVALID_HANDLE, g_hMaM = INVALID_HANDLE, g_hMaS = INVALID_HANDLE, g_hMacd = INVALID_HANDLE;
int             g_hHbAtr = INVALID_HANDLE;
int             g_hTlAtr = INVALID_HANDLE;
int             g_hSmcAtr = INVALID_HANDLE;
// keadaan yang bisa diubah dari dashboard saat EA berjalan
bool            g_enMain = false, g_enORB = true, g_enSMC = false, g_enMOM = false, g_paused = false;
bool            g_enRSM = false;
bool            g_enDIP = false;
int             g_hDipEma = INVALID_HANDLE, g_hDipAtr = INVALID_HANDLE;
datetime        g_dipBar = 0;
string          g_dipStatus = "-";
bool            g_enNAO = false;
int             g_hNaoE[6], g_hNaoSar[2];           // EMA cepat/tengah/lambat di M1 lalu M5; PSAR M1, M5
double          g_naoH[], g_naoL[], g_naoC[];       // bar 10 detik yang sudah tutup (harga tengah bid/ask)
datetime        g_naoT = 0;                         // awal bar 10 detik yang sedang berjalan
double          g_naoCurH = 0, g_naoCurL = 0, g_naoCurC = 0;
string          g_naoStatus = "-";
bool            g_enCDL = false;
int             g_hCdlRsi = INVALID_HANDLE, g_hCdlMa = INVALID_HANDLE;
datetime        g_cdlBar = 0;
string          g_cdlStatus = "-";
// Range Hybrid
enum RH_MODE { RH_OFF = 0, RH_DETAIL = 1, RH_STRICT = 2 };
struct RhState
  {
   double            hi, lo, width, adx;
   int               score, touchHi, touchLo, falseBrk;
   bool              atrStable;
   RH_MODE           mode;
  };
RhState         g_rh;
bool            g_enRH = false;
int             g_hRhAdx = INVALID_HANDLE, g_hRhRsi = INVALID_HANDLE, g_hRhAtr = INVALID_HANDLE;
datetime        g_rhBar = 0, g_rhOffUntil = 0;
double          g_rhPrevWidth = 0;
ulong           g_rhPartTk = 0;
string          g_rhStatus = "-";
bool            g_extreme = false;         // mode Extreme aktif
double          m_rhAdxDetail = 0;
double          m_rhAtrMin = 0;
int             m_rhMinTouch = 0;
double          m_rhMinDistMid = 0;
int             m_rhMaxDetail = 0;
int             m_dipCandles = 0;
double          m_dipVolMult = 0;
int             m_dipHourTo = 0;
int             m_hbLookback = 0;
int             m_tlMinTouches = 0;
int             m_tlRetestBars = 0;
double          m_tlTolAtr = 0;
double          m_momImpulse = 0;
double          m_momFib = 0;
int             m_momExpiry = 0;
double          m_smcDisp = 0;
double          m_smcMinGap = 0;
double          m_rhRsiHi = 63.0, m_rhRsiLo = 37.0, m_rhPinBody = 1.6, m_rhPinRng = 0.40;   // rejection mode Detail
int             m_rhScoreDetail = 48;      // skor minimal mode Detail
int             g_tpMode = 0;              // ambil untung global: 0 ikut strategi, 1 TP tetap, 2 trailing, 3 pindah SL
double          g_tpUsd = 0, g_trStart = 0, g_trDist = 0, g_beAt = 0, g_beLock = 0;
double          g_slMin = 0, g_slMax = 0;  // SL per trade (mata uang akun), bisa diubah dari dashboard
bool            g_sessOn[3] = {true, true, true};   // 0 Asia, 1 London, 2 New York: boleh entry atau tidak
bool            g_newsOn = true;           // hindari entry di sekitar news berdampak tinggi
int             g_hRsmMa = INVALID_HANDLE, g_hRsmRsi = INVALID_HANDLE, g_hRsmSig = INVALID_HANDLE;
int             g_rsmEp = 0;               // sisi episode sinyal: +1 di atas 50, -1 di bawah
bool            g_rsmTaken = false;        // satu entry per episode
bool            g_rsmFirst = true;         // evaluasi pertama sejak EA dipasang
datetime        g_rsmBar = 0;
string          g_rsmStatus = "-";
double          g_maxOpenRisk = 0, g_dailyLossPct = 0;
bool            g_statsDirty = true;
int             g_hMomAtr = INVALID_HANDLE;
struct MomSetup
  {
   bool              ok, touched;
   int               dir;
   double            level, stop;
   datetime          created;
  };
MomSetup        g_mom;
datetime        g_momBar = 0, g_momEBar = 0;
string          g_momStatus = "-";
datetime        g_eqDay = 0;               // hari yang equity awalnya sudah dicatat
double          g_eqDayStart = 0;

// setup SMC yang sedang menunggu harga kembali ke zona
struct SmcSetup
  {
   bool              ok;
   int               dir;
   double            entry, stop, tp;
   datetime          created;
  };
SmcSetup        g_smc;
datetime        g_smcBar = 0;
string          g_smcStatus = "-";

// garis tren: dua titik jangkar (t2 lebih lama dari t1)
struct TLine
  {
   bool              ok;
   datetime          t1, t2;
   double            p1, p2;
   int               touches;
  };
TLine           g_tlBreak;                 // garis yang sudah ditembus, menunggu retest
TLine           g_tlTrail;                 // garis seberang untuk trailing
int             g_tlState = 0;             // 0 = cari garis / tunggu break, 1 = tunggu retest
int             g_tlDir = 0;
datetime        g_tlBreakTime = 0, g_tlBar = 0;
string          g_tlStatus = "-";
string          g_hbStatus = "-", g_orbStatus = "-";
datetime        g_hbBar = 0, g_orbBar = 0;

// Beberapa salinan strategi breakout / garis tren di timeframe berbeda.
// Kode strategi memakai variabel "aktif" di bawah; RunHB/RunTL memuat dan menyimpan keadaan tiap salinan.
#define N_HB 3
#define N_TL 2
struct HbInst
  {
   bool              on;
   ENUM_TIMEFRAMES   tf;
   long              magic;
   string            cmt, label;
   int               hAtr;
   datetime          bar;
   string            status;
  };
struct TlInst
  {
   bool              on;
   ENUM_TIMEFRAMES   tf;
   long              magic;
   string            cmt, label, id;
   int               hAtr;
   TLine             brk, trail;
   int               state, dir;
   datetime          breakTime, bar;
   string            status;
  };
HbInst          g_hbI[N_HB];
TlInst          g_tlI[N_TL];
ENUM_TIMEFRAMES g_hbTF = PERIOD_H4, g_tlTF = PERIOD_H1;
long            g_hbMagic = 0, g_tlMagic = 0;
string          g_hbCmt = "MTRB H4BO", g_tlCmt = "MTRB TL", g_tlId = "";
datetime        g_orbT0 = 0;               // sesi yang range-nya sudah dihitung
double          g_orbHigh = 0, g_orbLow = 0;

double          g_score     = 0;
bool            g_scoreOk   = false;
double          g_vwap      = 0;
string          g_status    = "Inisialisasi...";
datetime        g_lastBar   = 0;
bool            g_tester    = false;
bool            g_visual    = false;
bool            g_twin      = false;
string          g_barKey    = "";

// risiko awal (R) per tiket
ulong           g_rTk[];
double          g_rVal[];

// statistik harian
datetime        g_dayStart  = 0;
int             g_dayTrades = 0, g_dayWins = 0, g_dayLosses = 0, g_dayConsecLoss = 0;
double          g_dayPL     = 0;
double          g_dayPips   = 0;           // pips terealisasi hari ini (jumlah semua tiket)
datetime        g_pipLockDay = 0;          // hari ketika target/batas pips tercapai
datetime        g_lastLossTime = 0;

// news
struct NewsItem
  {
   datetime          t;
   string            name;
   int               imp;   // 2 = medium, 3 = high
  };
NewsItem        g_news[];
datetime        g_newsRefreshed = 0;

// hasil estimasi Buy/Sell volume (dihitung di FlowGet)
struct FlowRes
  {
   bool              ok;
   double            buyPct, deltaPct, cvdPct, slopePct;
   int               div, absorb;      // +1 bullish, -1 bearish, 0 tidak ada
  };
int             g_flowMode = 1;            // 0 mati, 1 tampil/catat, 2 filter

// konteks saat entry, hanya dicatat di Strategy Tester untuk laporan
struct EntryCtx
  {
   ulong             tk;
   double            score, adx, rsi, atr, spread, risk, vwapDist;
  };
EntryCtx        g_ctx[];
EntryCtx        g_cur;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_tester = (bool)MQLInfoInteger(MQL_TESTER);
   g_visual = (bool)MQLInfoInteger(MQL_VISUAL_MODE);

   g_w[0] = InpW_D1;  g_w[1] = InpW_H4;  g_w[2] = InpW_H1; g_w[3] = InpW_M30;
   g_w[4] = InpW_M15; g_w[5] = InpW_M5;  g_w[6] = InpW_M1;

   for(int i = 0; i < NTF; i++)
     {
      g_hFast[i] = iMA(_Symbol, g_tf[i], InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
      g_hSlow[i] = iMA(_Symbol, g_tf[i], InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
      if(g_hFast[i] == INVALID_HANDLE || g_hSlow[i] == INVALID_HANDLE)
        {
         Print("Gagal membuat handle EMA ", g_tfName[i]);
         return INIT_FAILED;
        }
      g_bias[i] = 0;
     }
   g_hAdx  = iADX(_Symbol, PERIOD_M15, InpAdxPeriod);
   g_hRsi  = iRSI(_Symbol, PERIOD_M5, InpRsiPeriod, PRICE_CLOSE);
   g_hAtr  = iATR(_Symbol, InpAtrTF, InpAtrPeriod);
   g_hTrig = iMA(_Symbol, InpSignalTF, InpTriggerEma, 0, MODE_EMA, PRICE_CLOSE);
   g_hSigRsi = iRSI(_Symbol, InpSignalTF, InpRsiPeriod, PRICE_CLOSE);
   g_hMaF  = iMA(_Symbol, InpSignalTF, InpMaFast, 0, MODE_SMA, PRICE_CLOSE);
   g_hMaM  = iMA(_Symbol, InpSignalTF, InpMaMid, 0, MODE_SMA, PRICE_CLOSE);
   g_hMaS  = iMA(_Symbol, InpSignalTF, InpMaSlow, 0, MODE_SMA, PRICE_CLOSE);
   g_hMacd = iMACD(_Symbol, InpSignalTF, InpMacdFast, InpMacdSlow, InpMacdSignal, PRICE_CLOSE);
   // salinan strategi breakout
   bool            hbOn[N_HB]  = {InpEnableHB, InpEnableHB2, InpEnableHB3};
   ENUM_TIMEFRAMES hbTf[N_HB]  = {InpHbTF, InpHbTF2, InpHbTF3};
   long            hbMg[N_HB]  = {101, 111, 112};
   string          hbCm[N_HB]  = {"MTRB H4BO", "MTRB BO2", "MTRB BO3"};
   for(int k = 0; k < N_HB; k++)
     {
      g_hbI[k].on     = hbOn[k];
      g_hbI[k].tf     = hbTf[k];
      g_hbI[k].magic  = InpMagic + hbMg[k];
      g_hbI[k].cmt    = hbCm[k];
      g_hbI[k].label  = "BO " + StringSubstr(EnumToString(hbTf[k]), 7);
      g_hbI[k].hAtr   = iATR(_Symbol, hbTf[k], 14);
      g_hbI[k].bar    = 0;
      g_hbI[k].status = "-";
      if(g_hbI[k].hAtr == INVALID_HANDLE)
         return INIT_FAILED;
     }
   // salinan strategi garis tren
   bool            tlOn[N_TL]  = {InpEnableTL, InpEnableTL2};
   ENUM_TIMEFRAMES tlTf[N_TL]  = {InpTlTF, InpTlTF2};
   long            tlMg[N_TL]  = {103, 113};
   string          tlCm[N_TL]  = {"MTRB TL", "MTRB TL2"};
   for(int k = 0; k < N_TL; k++)
     {
      g_tlI[k].on     = tlOn[k];
      g_tlI[k].tf     = tlTf[k];
      g_tlI[k].magic  = InpMagic + tlMg[k];
      g_tlI[k].cmt    = tlCm[k];
      g_tlI[k].label  = "GT " + StringSubstr(EnumToString(tlTf[k]), 7);
      g_tlI[k].id     = IntegerToString(k);
      g_tlI[k].hAtr   = iATR(_Symbol, tlTf[k], 14);
      g_tlI[k].brk.ok = false;
      g_tlI[k].trail.ok = false;
      g_tlI[k].state  = 0;
      g_tlI[k].dir    = 0;
      g_tlI[k].breakTime = 0;
      g_tlI[k].bar    = 0;
      g_tlI[k].status = "-";
      if(g_tlI[k].hAtr == INVALID_HANDLE)
         return INIT_FAILED;
     }
   g_hHbAtr = g_hbI[0].hAtr;
   g_hTlAtr = g_tlI[0].hAtr;
   g_tlBreak.ok = false;
   g_tlTrail.ok = false;
   g_hSmcAtr = iATR(_Symbol, InpSmcTF, 14);
   g_hMomAtr = iATR(_Symbol, InpMomBiasTF, 14);
   g_hRsmMa  = iMA(_Symbol, InpRsmTF, InpRsmMaPeriod, 0, MODE_SMA, PRICE_CLOSE);
   g_hRsmRsi = iRSI(_Symbol, InpRsmTF, InpRsmRsiPeriod, PRICE_CLOSE);
   g_hRsmSig = (g_hRsmRsi != INVALID_HANDLE) ? iMA(_Symbol, InpRsmTF, InpRsmSmooth, 0, MODE_LWMA, g_hRsmRsi) : INVALID_HANDLE;
   if(g_hRsmMa == INVALID_HANDLE || g_hRsmRsi == INVALID_HANDLE || g_hRsmSig == INVALID_HANDLE)
      return INIT_FAILED;
   g_hDipEma = iMA(_Symbol, InpDipTF, InpDipTrendEma, 0, MODE_EMA, PRICE_CLOSE);
   g_hDipAtr = iATR(_Symbol, InpDipTF, 14);
   for(int k = 0; k < 2; k++)
     {
      ENUM_TIMEFRAMES ntf = (k == 0) ? PERIOD_M1 : PERIOD_M5;
      g_hNaoE[k * 3 + 0] = iMA(_Symbol, ntf, InpNaoFastEma, 0, MODE_EMA, PRICE_CLOSE);
      g_hNaoE[k * 3 + 1] = iMA(_Symbol, ntf, InpNaoMidEma, 0, MODE_EMA, PRICE_CLOSE);
      g_hNaoE[k * 3 + 2] = iMA(_Symbol, ntf, InpNaoSlowEma, 0, MODE_EMA, PRICE_CLOSE);
      g_hNaoSar[k] = iSAR(_Symbol, ntf, InpNaoSarStep, InpNaoSarMax);
      if(g_hNaoE[k * 3] == INVALID_HANDLE || g_hNaoE[k * 3 + 1] == INVALID_HANDLE || g_hNaoE[k * 3 + 2] == INVALID_HANDLE || g_hNaoSar[k] == INVALID_HANDLE)
         return INIT_FAILED;
     }
   g_hCdlRsi = iRSI(_Symbol, InpCdlTF, InpCdlRsiPeriod, PRICE_CLOSE);
   g_hCdlMa  = iMA(_Symbol, InpCdlTF, InpCdlMaPeriod, 0, MODE_SMA, PRICE_CLOSE);
   if(g_hCdlRsi == INVALID_HANDLE || g_hCdlMa == INVALID_HANDLE)
      return INIT_FAILED;
   if(g_hDipEma == INVALID_HANDLE || g_hDipAtr == INVALID_HANDLE)
      return INIT_FAILED;
   g_hRhAdx = iADX(_Symbol, InpRangeTF, InpRhAdxPeriod);
   g_hRhRsi = iRSI(_Symbol, InpRangeTF, 14, PRICE_CLOSE);
   g_hRhAtr = iATR(_Symbol, InpRangeTF, 14);
   if(g_hRhAdx == INVALID_HANDLE || g_hRhRsi == INVALID_HANDLE || g_hRhAtr == INVALID_HANDLE)
      return INIT_FAILED;
   g_mom.ok = false;
   if(g_hMomAtr == INVALID_HANDLE)
      return INIT_FAILED;
   g_smc.ok = false;
   if(g_hTlAtr == INVALID_HANDLE || g_hSmcAtr == INVALID_HANDLE)
      return INIT_FAILED;
   if(g_hMaF == INVALID_HANDLE || g_hMaM == INVALID_HANDLE || g_hMaS == INVALID_HANDLE || g_hMacd == INVALID_HANDLE || g_hHbAtr == INVALID_HANDLE)
     {
      Print("Gagal membuat handle MA/MACD");
      return INIT_FAILED;
     }
   if(g_hAdx == INVALID_HANDLE || g_hRsi == INVALID_HANDLE || g_hAtr == INVALID_HANDLE || g_hTrig == INVALID_HANDLE || g_hSigRsi == INVALID_HANDLE)
     {
      Print("Gagal membuat handle indikator");
      return INIT_FAILED;
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);

   // twin order hanya masuk akal di akun hedging (di netting kedua tiket melebur)
   bool hedging = (AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
   g_twin = InpTwinOrder && hedging;
   if(InpTwinOrder && !hedging)
      Print("Akun bukan hedging: twin order dimatikan, pakai mode satu tiket");

   // pulihkan bar terakhir supaya restart tidak entry dua kali di bar yang sama
   g_barKey = PFX + "lastBar_" + _Symbol + "_" + IntegerToString(InpMagic);
   if(!g_tester && GlobalVariableCheck(g_barKey))
      g_lastBar = (datetime)GlobalVariableGet(g_barKey);

   // nilai awal dari input; dashboard bisa mengubahnya saat EA berjalan
   g_enMain = InpEnableMain; g_enORB = InpEnableORB; g_enSMC = InpEnableSMC; g_enMOM = InpEnableMOM;
   g_enRSM = InpEnableRSM;
   g_enDIP = InpEnableDIP;
   g_enNAO = InpEnableNAO;
   g_enCDL = InpEnableCDL;
   g_enRH = InpEnableRangeHybrid;
   g_flowMode = (int)MathMax(0, MathMin(2, InpFlowMode));
   g_slMin = InpSLMinPerTrade; g_slMax = InpSLMaxPerTrade;
   ApplyMode(InpExtremeMode);
   g_tpMode = (int)MathMax(0, MathMin(3, InpTpMode));
   g_tpUsd = MathMax(0.0, InpTpUsd); g_trStart = MathMax(0.0, InpTrailStartUsd); g_trDist = MathMax(0.0, InpTrailDistUsd);
   g_beAt = MathMax(0.0, InpBeAtUsd); g_beLock = MathMax(0.0, InpBeLockUsd);
   g_sessOn[0] = InpSessAsia; g_sessOn[1] = InpSessLondon; g_sessOn[2] = InpSessNY;
   g_newsOn = InpUseNews;
   g_maxOpenRisk = InpMaxOpenRisk; g_dailyLossPct = InpPortDailyLossPct; g_paused = false;
   DashInit();
   LogInit();

   UpdateDayStats();
   if(!g_tester)
     {
      EventSetTimer(1);
      RefreshNews();
     }
   if(PanelEnabled())
      ChartSetInteger(0, CHART_FOREGROUND, false);
   // tampilkan MA dan MACD di chart bila chart-nya sama dengan timeframe sinyal
   if(!g_tester && InpEntryMode == ENTRY_MAMACD && Period() == InpSignalTF && ChartIndicatorsTotal(0, 0) == 0)
     {
      ChartIndicatorAdd(0, 0, g_hMaF);
      ChartIndicatorAdd(0, 0, g_hMaM);
      ChartIndicatorAdd(0, 0, g_hMaS);
      ChartIndicatorAdd(0, 1, g_hMacd);
     }
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   for(int i = 0; i < NTF; i++)
     {
      IndicatorRelease(g_hFast[i]);
      IndicatorRelease(g_hSlow[i]);
     }
   IndicatorRelease(g_hAdx);
   IndicatorRelease(g_hRsi);
   IndicatorRelease(g_hAtr);
   IndicatorRelease(g_hTrig);
   IndicatorRelease(g_hSigRsi);
   IndicatorRelease(g_hMaF);
   IndicatorRelease(g_hMaM);
   IndicatorRelease(g_hMaS);
   IndicatorRelease(g_hMacd);
   for(int k = 0; k < N_HB; k++)
      IndicatorRelease(g_hbI[k].hAtr);
   for(int k = 0; k < N_TL; k++)
      IndicatorRelease(g_tlI[k].hAtr);
   IndicatorRelease(g_hSmcAtr);
   IndicatorRelease(g_hMomAtr);
   IndicatorRelease(g_hRsmSig);
   IndicatorRelease(g_hRsmRsi);
   IndicatorRelease(g_hRsmMa);
   IndicatorRelease(g_hDipEma);
   IndicatorRelease(g_hDipAtr);
   for(int k = 0; k < 6; k++)
      IndicatorRelease(g_hNaoE[k]);
   IndicatorRelease(g_hNaoSar[0]);
   IndicatorRelease(g_hNaoSar[1]);
   IndicatorRelease(g_hCdlRsi);
   IndicatorRelease(g_hCdlMa);
   IndicatorRelease(g_hRhAdx);
   IndicatorRelease(g_hRhRsi);
   IndicatorRelease(g_hRhAtr);
   LogDeinit();
   ObjectsDeleteAll(0, PFX);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   if(TimeCurrent() - g_newsRefreshed >= 60)
      RefreshNews();
   CalcScore();
   DrawPanel();
   if(InpDashboard)
      DashTick();
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   CheckNewDay();
   ManagePositions();
   CheckDayPipLimits();
   // mode ORB: keluar paling lambat InpOrbFlatMin menit setelah sesi buka, menang atau kalah
   if(InpEntryMode == ENTRY_ORB && InpOrbFlatMin > 0 && TimeCurrent() >= OrbT0() + InpOrbFlatMin * 60 && CountPositions() > 0)
      CloseAllMine();

   // strategi tambahan: masing-masing punya magic number dan posisi sendiri
   PortfolioDayCheck();
   TrailStrategies();
   ExitManage();
   RunHB();
   StrategyORB();
   RunTL();
   StrategySMC();
   StrategyMOM();
   StrategyRSM();
   StrategyDIP();
   StrategyNAO();
   StrategyCDL();
   StrategyRH();
   RefreshStatuses();

   datetime bar = iTime(_Symbol, InpSignalTF, 0);
   if(bar <= 0 || bar == g_lastBar)
      return;
   g_lastBar = bar;
   if(!g_tester)
      GlobalVariableSet(g_barKey, (double)bar);

   CalcScore();
   g_vwap = CalcVWAP();
   if(g_enMain && !g_paused && SessionAllowed())
      CheckEntry();
   else
      g_status = g_enMain ? "PAUSE: dihentikan dari dashboard" : "Strategi utama nonaktif";
   if(g_visual)
      DrawPanel();
  }

//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
     {
      UpdateDayStats();
      g_statsDirty = true;
      LogOnDeal(trans.deal);
     }
  }

//+------------------------------------------------------------------+
//| Util                                                             |
//+------------------------------------------------------------------+
double Val(const int handle, const int buffer, const int shift)
  {
   double a[1];
   if(CopyBuffer(handle, buffer, shift, 1, a) != 1)
      return EMPTY_VALUE;
   return a[0];
  }

bool PanelEnabled()
  {
   return InpShowPanel && (!g_tester || g_visual);
  }

bool IsMine()
  {
   return (PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic);
  }

int CountPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0)
         continue;
      if(IsMine())
         n++;
     }
   return n;
  }

double NormPrice(const double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0)
      return NormalizeDouble(p, _Digits);
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
  }

double NormLot(double lot)
  {
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0)
      lot = MathFloor(lot / step + 1e-9) * step;
   lot = MathMax(vmin, MathMin(vmax, lot));
   return NormalizeDouble(lot, 2);
  }

//+------------------------------------------------------------------+
//| Ambil untung global: berlaku untuk posisi semua mesin.           |
//| Nilai dalam mata uang akun per posisi (dihitung pada lot posisi).|
//| Hanya memperketat: tidak pernah memundurkan SL atau menjauhkan TP|
//+------------------------------------------------------------------+
void ExitManage()
  {
   if(g_tpMode <= 0)
      return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT), minD = MinStopDist();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || !IsOurMagic(PositionGetInteger(POSITION_MAGIC)))
         continue;
      bool   buy  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      int    dir  = buy ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
      double vol  = PositionGetDouble(POSITION_VOLUME), px = buy ? bid : ask;
      double per  = 0;                                   // uang per 1.00 gerak harga pada lot posisi ini
      if(!OrderCalcProfit(buy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, _Symbol, vol, open, open + dir * 1.0, per) || per <= 0)
         continue;
      double gain = dir * (px - open);                   // jarak harga yang sudah untung

      if(g_tpMode == 1)
        {
         if(g_tpUsd <= 0)
            continue;
         double d = g_tpUsd / per, target = NormPrice(open + dir * d);
         if(gain >= d)
           {
            if(trade.PositionClose(tk))
               PrintFormat("[MTRB] TP tetap %.2f tercapai, tiket %I64u ditutup", g_tpUsd, tk);
            continue;
           }
         // pasang juga sebagai TP di broker supaya tetap jalan saat MT5 mati
         if((tp == 0 || dir * (tp - target) > pt / 2) && dir * (target - px) >= minD)
            trade.PositionModify(tk, sl, target);
        }
      else if(g_tpMode == 2)
        {
         if(g_trDist <= 0 || gain * per < g_trStart)
            continue;
         double dist = MathMax(g_trDist / per, minD);
         double newSL = NormPrice(px - dir * dist);
         if(sl == 0 || dir * (newSL - sl) >= 10 * pt)
            trade.PositionModify(tk, newSL, tp);
        }
      else if(g_tpMode == 3)
        {
         if(g_beAt <= 0 || gain * per < g_beAt)
            continue;
         double newSL = NormPrice(open + dir * g_beLock / per);
         if((sl == 0 || dir * (newSL - sl) > pt / 2) && dir * (px - newSL) >= minD)
            trade.PositionModify(tk, newSL, tp);
        }
     }
  }

double MinStopDist()
  {
   double pt     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double lvl    = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * pt;
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   return MathMax(lvl, spread * 2.0) + pt;
  }

bool InSession()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.day_of_week == 0 || dt.day_of_week == 6)
      return false;
   if(dt.day_of_week == 5 && InpFridayStopHour > 0 && dt.hour >= InpFridayStopHour)
      return false;
   if(InpAvoidRollover && ((dt.hour == 21 && dt.min >= 55) || (dt.hour == 22 && dt.min <= 10)))
      return false;
   if(InpSessStartHour == InpSessEndHour)
      return true;
   if(InpSessStartHour < InpSessEndHour)
      return (dt.hour >= InpSessStartHour && dt.hour < InpSessEndHour);
   return (dt.hour >= InpSessStartHour || dt.hour < InpSessEndHour);
  }

datetime DayStart()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
  }

//--- pips mengambang dari semua posisi EA ini
double FloatingPips()
  {
   if(InpPipSize <= 0)
      return 0;
   double sum = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0 || !IsMine())
         continue;
      int dir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      sum += dir * (PositionGetDouble(POSITION_PRICE_CURRENT) - PositionGetDouble(POSITION_PRICE_OPEN)) / InpPipSize;
     }
   return sum;
  }

//--- tutup semua dan kunci hari itu bila target / batas pips harian tersentuh
void CheckDayPipLimits()
  {
   if(InpDayTargetPips <= 0 && InpDayMaxLossPips <= 0)
      return;
   if(CountPositions() == 0)
      return;
   double tot = g_dayPips + FloatingPips();
   bool hitTarget = (InpDayTargetPips > 0 && tot >= InpDayTargetPips);
   bool hitLoss   = (InpDayMaxLossPips > 0 && tot <= -InpDayMaxLossPips);
   if(!hitTarget && !hitLoss)
      return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      trade.PositionClose(tk);
     }
   g_pipLockDay = DayStart();
   g_status = hitTarget ? "STOP: target pips harian tercapai" : "STOP: batas loss pips harian";
  }

//--- VWAP harian dari bar M5 (volume tick)
double CalcVWAP()
  {
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M5, DayStart(), TimeCurrent(), r);
   if(n <= 0)
      return 0;
   double pv = 0, v = 0;
   for(int i = 0; i < n; i++)
     {
      double vol = (double)r[i].tick_volume;
      pv += (r[i].high + r[i].low + r[i].close) / 3.0 * vol;
      v  += vol;
     }
   return (v > 0) ? pv / v : 0;
  }

//--- risiko awal per tiket
void RememberRisk(const ulong tk, const double risk)
  {
   if(tk == 0 || risk <= 0)
      return;
   int n = ArraySize(g_rTk);
   for(int i = 0; i < n; i++)
      if(g_rTk[i] == tk)
        {
         g_rVal[i] = risk;
         return;
        }
   // buang tiket yang sudah tertutup supaya array tidak membengkak
   for(int i = n - 1; i >= 0; i--)
      if(!PositionSelectByTicket(g_rTk[i]))
        {
         g_rTk[i]  = g_rTk[n - 1];
         g_rVal[i] = g_rVal[n - 1];
         n--;
        }
   ArrayResize(g_rTk, n + 1);
   ArrayResize(g_rVal, n + 1);
   g_rTk[n]  = tk;
   g_rVal[n] = risk;
  }

// posisi tk harus sedang ter-select
double RiskOf(const ulong tk, const string cmt, const int dir, const double open, const double sl, const double tp)
  {
   int n = ArraySize(g_rTk);
   for(int i = 0; i < n; i++)
      if(g_rTk[i] == tk)
         return g_rVal[i];
   // fallback setelah EA di-restart
   double risk = 0;
   if(sl > 0 && dir * (open - sl) > 0)
      risk = MathAbs(open - sl);
   else
      if(tp > 0)
        {
         double k = (cmt == CMT_SCALP) ? InpScalpTpR : (cmt == CMT_RUN) ? InpRunnerTpR : InpRR;
         if(k > 0)
            risk = MathAbs(tp - open) / k;
        }
   RememberRisk(tk, risk);
   return risk;
  }

//+------------------------------------------------------------------+
//| Skor bias multi-timeframe: -100 (bearish) .. +100 (bullish)      |
//+------------------------------------------------------------------+
bool CalcScore()
  {
   double sum = 0, wsum = 0;
   for(int i = 0; i < NTF; i++)
     {
      double f = Val(g_hFast[i], 0, 0);
      double s = Val(g_hSlow[i], 0, 0);
      double c = iClose(_Symbol, g_tf[i], 0);
      if(f == EMPTY_VALUE || s == EMPTY_VALUE || c <= 0)
        {
         g_scoreOk = false;
         return false;
        }
      int b = 0;
      b += (f > s) ? 1 : -1;
      b += (c > s) ? 1 : -1;
      g_bias[i] = b / 2;           // +1 bullish, 0 netral, -1 bearish
      sum  += g_w[i] * g_bias[i];
      wsum += g_w[i];
     }
   g_score   = (wsum > 0) ? 100.0 * sum / wsum : 0;
   g_scoreOk = true;
   return true;
  }

//+------------------------------------------------------------------+
//| Statistik harian (satu setup twin dihitung sebagai satu trade)   |
//+------------------------------------------------------------------+
void CheckNewDay()
  {
   if(DayStart() != g_dayStart)
      UpdateDayStats();
  }

void UpdateDayStats()
  {
   g_dayStart = DayStart();
   g_dayTrades = 0; g_dayWins = 0; g_dayLosses = 0; g_dayConsecLoss = 0; g_dayPL = 0;
   g_lastLossTime = 0;
   g_dayPips = 0;
   if(!HistorySelect(g_dayStart - 7 * 86400, TimeCurrent() + 60))
      return;
   int n = HistoryDealsTotal();

   // kumpulkan ID posisi runner supaya tidak dihitung dobel, dan harga buka tiap posisi
   long   runIds[];
   long   inPid[];
   double inPx[];
   int    inDir[];
   for(int i = 0; i < n; i++)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0)
         continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol || HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic)
         continue;
      if(HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_IN)
         continue;
      int q = ArraySize(inPid);
      ArrayResize(inPid, q + 1, 256);
      ArrayResize(inPx, q + 1, 256);
      ArrayResize(inDir, q + 1, 256);
      inPid[q] = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      inPx[q]  = HistoryDealGetDouble(tk, DEAL_PRICE);
      inDir[q] = (HistoryDealGetInteger(tk, DEAL_TYPE) == DEAL_TYPE_BUY) ? 1 : -1;
      if(HistoryDealGetString(tk, DEAL_COMMENT) == CMT_RUN)
        {
         int k = ArraySize(runIds);
         ArrayResize(runIds, k + 1);
         runIds[k] = inPid[q];
        }
     }
   int nRun = ArraySize(runIds);

   for(int i = 0; i < n; i++)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0)
         continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol || HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic)
         continue;
      datetime tm = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      if(tm < g_dayStart)
         continue;
      double p = HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_SWAP) + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      g_dayPL += p;

      long pid = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      bool isRun = false;
      for(int j = 0; j < nRun; j++)
         if(runIds[j] == pid)
           {
            isRun = true;
            break;
           }
      long entry = HistoryDealGetInteger(tk, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_IN && !isRun)
         g_dayTrades++;
      if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
        {
         if(p < 0 && tm > g_lastLossTime)
            g_lastLossTime = tm;
         if(InpPipSize > 0)
            for(int j = ArraySize(inPid) - 1; j >= 0; j--)
               if(inPid[j] == pid)
                 {
                  g_dayPips += inDir[j] * (HistoryDealGetDouble(tk, DEAL_PRICE) - inPx[j]) / InpPipSize;
                  break;
                 }
         if(!isRun)
           {
            if(p > 0)
              {
               g_dayWins++;
               g_dayConsecLoss = 0;
              }
            else
               if(p < 0)
                 {
                  g_dayLosses++;
                  g_dayConsecLoss++;
                 }
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| News (kalender ekonomi MT5; tidak tersedia di Strategy Tester)   |
//+------------------------------------------------------------------+
void RefreshNews()
  {
   g_newsRefreshed = TimeCurrent();
   if(g_tester)
      return;
   datetime now = TimeTradeServer();
   MqlCalendarValue v[];
   int n = CalendarValueHistory(v, now - InpNewsAfterMin * 60 - 60, now + 2 * 86400, NULL, InpNewsCurrency);
   ArrayResize(g_news, 0);
   if(n <= 0)
      return;
   for(int i = 0; i < n; i++)
     {
      MqlCalendarEvent e;
      if(!CalendarEventById(v[i].event_id, e))
         continue;
      if(e.importance < CALENDAR_IMPORTANCE_MODERATE)
         continue;
      int k = ArraySize(g_news);
      ArrayResize(g_news, k + 1);
      g_news[k].t    = v[i].time;
      g_news[k].name = e.name;
      g_news[k].imp  = (e.importance == CALENDAR_IMPORTANCE_HIGH) ? 3 : 2;
     }
   // urutkan berdasarkan waktu
   int m = ArraySize(g_news);
   for(int i = 1; i < m; i++)
     {
      NewsItem x = g_news[i];
      int j = i - 1;
      while(j >= 0 && g_news[j].t > x.t)
        {
         g_news[j + 1] = g_news[j];
         j--;
        }
      g_news[j + 1] = x;
     }
  }

bool NewsBlocked(string &why)
  {
   if(!g_newsOn || g_tester)
      return false;
   datetime now = TimeTradeServer();
   int n = ArraySize(g_news);
   for(int i = 0; i < n; i++)
     {
      if(g_news[i].imp < 3)
         continue;
      if(now >= g_news[i].t - InpNewsBeforeMin * 60 && now <= g_news[i].t + InpNewsAfterMin * 60)
        {
         why = g_news[i].name;
         return true;
        }
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Entry                                                            |
//+------------------------------------------------------------------+
bool OpenOne(const int dir, const double lot, const double sl, const double tp, const string cmt, const double risk)
  {
   bool ok = (dir == 1) ? trade.Buy(lot, _Symbol, 0, sl, tp, cmt) : trade.Sell(lot, _Symbol, 0, sl, tp, cmt);
   uint rc = trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
     {
      PrintFormat("[MTRB] order %s gagal, retcode=%u", cmt, rc);
      return false;
     }
   RememberRisk(trade.ResultOrder(), risk);   // di akun hedging tiket posisi = tiket order pembuka
   LogEntry(trade.ResultOrder(), (long)trade.RequestMagic(), dir, sl, tp, risk);
   if(g_tester)
     {
      int k = ArraySize(g_ctx);
      ArrayResize(g_ctx, k + 1, 1024);
      g_ctx[k]    = g_cur;
      g_ctx[k].tk = trade.ResultOrder();
     }
   return true;
  }

//--- opening range: high/low dari InpOrbRangeMin menit pertama sesi
datetime OrbT0()
  {
   datetime t1 = DayStart() + InpOrbHour * 3600 + InpOrbMinute * 60;
   if(g_extreme)
     {
      datetime t2 = DayStart() + InpSessLondonHour * 3600;      // sesi kedua: buka London
      if(t2 > t1 && TimeCurrent() >= t2)
         return t2;
     }
   return t1;
  }

bool OrbRange(double &hi, double &lo)
  {
   datetime t0 = OrbT0();
   datetime te = t0 + InpOrbRangeMin * 60;
   if(TimeCurrent() < te)
      return false;
   if(g_orbT0 != t0)
     {
      double hh[], ll[];
      int nh = CopyHigh(_Symbol, PERIOD_M1, t0, te - 1, hh);
      int nl = CopyLow(_Symbol, PERIOD_M1, t0, te - 1, ll);
      if(nh <= 0 || nl <= 0 || nh < 0.8 * InpOrbRangeMin)
         return false;
      g_orbHigh = hh[ArrayMaximum(hh)];
      g_orbLow  = ll[ArrayMinimum(ll)];
      g_orbT0   = t0;
     }
   hi = g_orbHigh;
   lo = g_orbLow;
   return true;
  }

void CloseAllMine()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      trade.PositionClose(tk);
     }
  }

//+------------------------------------------------------------------+
//| Strategi tambahan yang berjalan bersamaan dengan strategi utama  |
//+------------------------------------------------------------------+
long MagicHB()  { return g_hbMagic; }        // salinan breakout yang sedang aktif
long MagicORB() { return InpMagic + 102; }
long MagicTL()  { return g_tlMagic; }        // salinan garis tren yang sedang aktif
long MagicSMC() { return InpMagic + 104; }

bool IsHBMagic(const long m) { return (m == InpMagic + 101 || m == InpMagic + 111 || m == InpMagic + 112); }
bool IsTLMagic(const long m) { return (m == InpMagic + 103 || m == InpMagic + 113); }
bool IsOurMagic(const long m)
  {
   return (m == InpMagic || IsHBMagic(m) || IsTLMagic(m) || m == InpMagic + 102 || m == InpMagic + 104 || m == InpMagic + 105 || m == InpMagic + 106 || m == InpMagic + 107 || m == InpMagic + 108 || m == InpMagic + 115 || m == InpMagicRange);
  }

// jalankan tiap salinan strategi: muat keadaannya ke variabel aktif, jalankan, simpan kembali
void RunHB()
  {
   for(int k = 0; k < N_HB; k++)
     {
      if(!g_hbI[k].on)
         continue;
      g_hbTF = g_hbI[k].tf; g_hbMagic = g_hbI[k].magic; g_hbCmt = g_hbI[k].cmt;
      g_hHbAtr = g_hbI[k].hAtr; g_hbBar = g_hbI[k].bar; g_hbStatus = g_hbI[k].status;
      StrategyHB();
      g_hbI[k].bar = g_hbBar; g_hbI[k].status = g_hbStatus;
     }
  }

void RunTL()
  {
   for(int k = 0; k < N_TL; k++)
     {
      if(!g_tlI[k].on)
         continue;
      g_tlTF = g_tlI[k].tf; g_tlMagic = g_tlI[k].magic; g_tlCmt = g_tlI[k].cmt; g_tlId = g_tlI[k].id;
      g_hTlAtr = g_tlI[k].hAtr; g_tlBreak = g_tlI[k].brk; g_tlTrail = g_tlI[k].trail;
      g_tlState = g_tlI[k].state; g_tlDir = g_tlI[k].dir; g_tlBreakTime = g_tlI[k].breakTime;
      g_tlBar = g_tlI[k].bar; g_tlStatus = g_tlI[k].status;
      StrategyTL();
      g_tlI[k].brk = g_tlBreak; g_tlI[k].trail = g_tlTrail;
      g_tlI[k].state = g_tlState; g_tlI[k].dir = g_tlDir; g_tlI[k].breakTime = g_tlBreakTime;
      g_tlI[k].bar = g_tlBar; g_tlI[k].status = g_tlStatus;
     }
  }

bool IsOurs()
  {
   if(PositionGetString(POSITION_SYMBOL) != _Symbol)
      return false;
   long m = PositionGetInteger(POSITION_MAGIC);
   return IsOurMagic(m);
  }

int CountPosMagic(const long magic)
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
         n++;
     }
   return n;
  }

void CloseMagic(const long magic)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic)
         trade.PositionClose(tk);
     }
  }

// waktu entry terakhir strategi ini (7 hari terakhir), supaya restart tidak memicu entry ganda
datetime LastEntryTime(const long magic)
  {
   if(!HistorySelect(TimeCurrent() - 7 * 86400, TimeCurrent() + 60))
      return 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0)
         continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) == _Symbol && HistoryDealGetInteger(tk, DEAL_MAGIC) == magic &&
         HistoryDealGetInteger(tk, DEAL_ENTRY) == DEAL_ENTRY_IN)
         return (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
     }
   return 0;
  }

bool IsWeekend()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return (dt.day_of_week == 0 || dt.day_of_week == 6);
  }

// sesi pasar menurut jam server: 0 Asia, 1 London, 2 New York
int SessionNow()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.hour >= InpSessNYHour)
      return 2;
   if(dt.hour >= InpSessLondonHour)
      return 1;
   return 0;
  }

string SessionName(const int i)
  {
   return (i == 0) ? "Asia" : (i == 1) ? "London" : "New York";
  }

bool SessionAllowed()
  {
   return g_sessOn[SessionNow()];
  }

// total rugi bila semua posisi EA ini kena SL sekarang (posisi yang SL-nya sudah di sisi untung = 0)
double OpenRiskNow()
  {
   double sum = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0 || !IsOurs())
         continue;
      double sl = PositionGetDouble(POSITION_SL);
      if(sl <= 0)
         continue;
      ENUM_ORDER_TYPE ty = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      double pr = 0;
      if(OrderCalcProfit(ty, _Symbol, PositionGetDouble(POSITION_VOLUME), PositionGetDouble(POSITION_PRICE_OPEN), sl, pr) && pr < 0)
         sum -= pr;
     }
   return sum;
  }

// catat equity awal hari; dipakai batas rugi harian portofolio
void PortfolioDayCheck()
  {
   datetime d = DayStart();
   if(d != g_eqDay)
     {
      g_eqDay = d;
      g_eqDayStart = AccountInfoDouble(ACCOUNT_EQUITY);
     }
  }

bool PortfolioDayLocked()
  {
   if(g_dailyLossPct <= 0 || g_eqDayStart <= 0)
      return false;
   return (AccountInfoDouble(ACCOUNT_EQUITY) <= g_eqDayStart * (1.0 - g_dailyLossPct / 100.0));
  }

// pasang parameter sesuai mode. Normal = nilai input. Extreme = syarat dilonggarkan (tidak pernah lebih ketat dari input).
void ApplyMode(const bool ext)
  {
   g_extreme = ext;
   m_rhAdxDetail   = ext ? MathMax(InpAdxDetail, 26.5) : InpAdxDetail;
   m_rhAtrMin      = ext ? MathMin(InpRhAtrMinMult, 2.3) : InpRhAtrMinMult;
   m_rhMinTouch    = ext ? MathMin(InpRhMinTouch, 1) : InpRhMinTouch;
   m_rhMinDistMid  = ext ? MathMin(InpRhMinDistMid, 1.10) : InpRhMinDistMid;
   m_rhMaxDetail   = ext ? (InpMaxTradeDetail > 0 ? MathMax(InpMaxTradeDetail, 11) : 0) : InpMaxTradeDetail;
   m_dipCandles    = ext ? MathMin(InpDipCandles, 2) : InpDipCandles;
   m_dipVolMult    = ext ? MathMin(InpDipVolMult, 1.10) : InpDipVolMult;
   m_dipHourTo     = ext ? MathMax(InpDipHourTo, 23) : InpDipHourTo;
   m_hbLookback    = ext ? MathMin(InpHbLookback, 35) : InpHbLookback;
   m_tlMinTouches  = ext ? MathMin(InpTlMinTouches, 2) : InpTlMinTouches;
   m_tlRetestBars  = ext ? MathMax(InpTlRetestBars, 16) : InpTlRetestBars;
   m_tlTolAtr      = ext ? MathMax(InpTlTolAtr, 0.30) : InpTlTolAtr;
   m_momImpulse    = ext ? MathMin(InpMomImpulseAtr, 0.75) : InpMomImpulseAtr;
   m_momFib        = ext ? MathMax(InpMomFib, 0.618) : InpMomFib;
   m_momExpiry     = ext ? MathMax(InpMomExpiryBars, 10) : InpMomExpiryBars;
   m_smcDisp       = ext ? InpSmcDispAtr * 0.75 : InpSmcDispAtr;
   m_smcMinGap     = ext ? InpSmcMinGapAtr * 0.75 : InpSmcMinGapAtr;
   m_rhRsiHi       = ext ? 58.0 : 63.0;
   m_rhRsiLo       = ext ? 42.0 : 37.0;
   m_rhPinBody     = ext ? 1.2 : 1.6;
   m_rhPinRng      = ext ? 0.33 : 0.40;
   m_rhScoreDetail = ext ? 40 : 48;
  }

// pemisahan mesin per sesi: "" = boleh entry, selain itu alasan penolakan
string SplitBlock(const long magic)
  {
   if(!InpSessionSplit)
      return "";
   int  sn = SessionNow();
   bool asiaEng = (magic == InpMagicRange || (InpSplitDip && magic == InpMagic + 107));
   bool lnEng   = (magic == InpMagic + 101 || magic == InpMagic + 111 || magic == InpMagic + 112     // breakout
                   || magic == InpMagic + 103 || magic == InpMagic + 113                            // garis tren
                   || magic == InpMagic + 105);                                                     // momentum
   if(asiaEng && sn != 0)
      return "Khusus sesi Asia, sekarang " + SessionName(sn);
   if(lnEng && sn == 0)
      return "Khusus London-NY, sekarang Asia";
   return "";
  }

// buka satu tiket untuk strategi tambahan; mengembalikan teks status
string OpenStrategy(const long magic, const int dir, const double slDistIn, const double rr, const string cmt, const double tpPrice = 0, const double lotIn = 0)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double lot = NormLot(lotIn > 0 ? lotIn : InpLot);   // lotIn > 0: lot dari strategi, SL-nya struktural (tidak digeser)
   ENUM_ORDER_TYPE type = (dir == 1) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double price = (dir == 1) ? ask : bid;
   if(g_paused)
      return "PAUSE: dihentikan dari dashboard";
   if(!SessionAllowed())
      return "Sesi " + SessionName(SessionNow()) + " dimatikan";
   string sg = SplitBlock(magic);
   if(sg != "")
      return sg;
   string rb = RuleBlock(magic);
   if(rb != "")
      return rb;
   if(g_flowMode == 2)
     {
      FlowRes fr;
      if(FlowGet(EngTF(magic), fr))
        {
         string fv = FlowVerdict(magic, dir, fr);
         if(fv != "")
            return fv;
        }
     }
   if(PortfolioDayLocked())
      return "STOP: batas rugi harian portofolio";

   // SL per trade: jarak SL dari strategi dijepit ke rentang minimal..maksimal (dalam mata uang akun)
   double slDist = slDistIn;
   if(lotIn <= 0 && (g_slMin > 0 || g_slMax > 0))
     {
      double per1 = 0;                                  // rugi untuk gerak harga 1.00 pada lot ini
      if(OrderCalcProfit(type, _Symbol, lot, price, price - dir * 1.0, per1) && per1 < 0)
        {
         per1 = -per1;
         if(g_slMin > 0 && slDist * per1 < g_slMin)
            slDist = g_slMin / per1;
         if(g_slMax > 0 && slDist * per1 > g_slMax)
            slDist = g_slMax / per1;
         slDist = MathMax(slDist, MinStopDist());
        }
     }
   double newLoss = 0, prN = 0;
   if(OrderCalcProfit(type, _Symbol, lot, price, price - dir * slDist, prN) && prN < 0)
      newLoss = -prN;
   // SL struktural: batas "SL maksimal per trade" dipenuhi dengan mengecilkan lot, bukan menggeser SL
   if(lotIn > 0 && g_slMax > 0 && newLoss > g_slMax)
     {
      lot = NormLot(lot * g_slMax / newLoss);
      newLoss = 0;
      if(OrderCalcProfit(type, _Symbol, lot, price, price - dir * slDist, prN) && prN < 0)
         newLoss = -prN;
      if(newLoss > g_slMax * 1.05)
         return StringFormat("BLOCK: rugi di SL %.2f > SL maks %.2f", newLoss, g_slMax);
     }
   if(InpMaxLossPerTrade > 0 && newLoss > InpMaxLossPerTrade)
      return StringFormat("BLOCK: risiko %.2f > batas", newLoss);
   if(g_maxOpenRisk > 0)
     {
      double openRisk = OpenRiskNow();
      if(openRisk + newLoss > g_maxOpenRisk)
         return StringFormat("BLOCK: total risiko %.0f > %.0f", openRisk + newLoss, g_maxOpenRisk);
     }
   double margin = 0;
   if(!OrderCalcMargin(type, _Symbol, lot, price, margin) || margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
      return "STOP: margin tidak cukup";
   double sl = NormPrice(price - dir * slDist);
   double tp = (tpPrice > 0) ? NormPrice(tpPrice) : (rr > 0) ? NormPrice(price + dir * slDist * rr) : 0;
   ZeroMemory(g_cur);
   g_cur.score = g_score; g_cur.spread = ask - bid; g_cur.risk = slDist;
   trade.SetExpertMagicNumber(magic);
   bool ok = OpenOne(dir, lot, sl, tp, cmt, slDist);
   trade.SetExpertMagicNumber(InpMagic);
   if(!ok)
      return "ORDER GAGAL: " + IntegerToString((int)trade.ResultRetcode());
   return (dir == 1) ? "BUY dibuka" : "SELL dibuka";
  }

//--- trailing stop untuk posisi strategi tambahan: aktif setelah profit >= InpTrailStartUSD
void TrailStrategies()
  {
   bool any = (InpTrailDistUSD > 0 || InpSmHalfAtR > 0 || InpSmBE_USD > 0 || InpHbBE_R > 0 || InpOrbBE_R > 0 ||
               InpHbTrailDistR > 0 || InpOrbTrailDistR > 0 || InpSmcBE_R > 0 || InpRsmBE_R > 0);
   if(!any || (!InpTrailHB && !InpTrailORB && InpSmcBE_R <= 0 && InpRsmBE_R <= 0))
      return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      long m = PositionGetInteger(POSITION_MAGIC);
      bool isHB  = IsHBMagic(m);
      bool isSMC = (m == MagicSMC());
      bool isRSM = (m == InpMagic + 106);
      if(!((isHB && InpTrailHB) || (m == MagicORB() && InpTrailORB) || (isSMC && InpSmcBE_R > 0) || (isRSM && InpRsmBE_R > 0)))
         continue;
      int    dir  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double px   = (dir == 1) ? bid : ask;
      double gain = dir * (px - open);
      if(gain <= 0)
         continue;

      // R = jarak SL awal: dari catatan saat entry, atau ditaksir setelah restart
      double R = 0;
      for(int j = ArraySize(g_rTk) - 1; j >= 0; j--)
         if(g_rTk[j] == tk)
           {
            R = g_rVal[j];
            break;
           }
      if(R <= 0)
        {
         double rr = isHB ? InpHbRR : InpOrbRR;
         if(sl > 0 && dir * (open - sl) > 0)
            R = MathAbs(open - sl);
         else
            if(tp > 0 && rr > 0)
               R = MathAbs(tp - open) / rr;
         RememberRisk(tk, R);
        }

      // setelan per strategi
      double InpSmBE_R        = isHB ? InpHbBE_R : isSMC ? InpSmcBE_R : isRSM ? InpRsmBE_R : InpOrbBE_R;
      double InpSmTrailStartR = isHB ? InpHbTrailStartR : (isSMC || isRSM) ? 0.0 : InpOrbTrailStartR;
      double InpSmTrailDistR  = isHB ? InpHbTrailDistR : (isSMC || isRSM) ? 0.0 : InpOrbTrailDistR;

      double be    = open + dir * InpSmBEOffset;
      double newSL = sl;
      // 1. pangkas risiko jadi setengah
      if(R > 0 && InpSmHalfAtR > 0 && gain >= InpSmHalfAtR * R)
        {
         double c1 = open - dir * 0.5 * R;
         if(newSL == 0 || dir * (c1 - newSL) > 0)
            newSL = c1;
        }
      // 2. breakeven
      if((R > 0 && InpSmBE_R > 0 && gain >= InpSmBE_R * R) || (InpSmBE_USD > 0 && gain >= InpSmBE_USD))
         if(newSL == 0 || dir * (be - newSL) > 0)
            newSL = be;
      // 3. trailing: jarak dalam R dan/atau dalam USD
      double tr = 0;
      bool   hasTr = false;
      if(R > 0 && InpSmTrailDistR > 0 && gain >= InpSmTrailStartR * R)
        {
         tr = px - dir * InpSmTrailDistR * R;
         hasTr = true;
        }
      if(InpTrailDistUSD > 0 && gain >= InpTrailStartUSD)
        {
         double t2 = px - dir * InpTrailDistUSD;
         if(!hasTr || dir * (t2 - tr) > 0)
            tr = t2;
         hasTr = true;
        }
      if(hasTr)
        {
         if(InpSmTrailCapBE && dir * (tr - be) > 0)
            tr = be;                                  // hanya mengurangi rugi, tidak mengunci profit
         if(newSL == 0 || dir * (tr - newSL) > 0)
            newSL = tr;
        }

      newSL = NormPrice(newSL);
      if(newSL == sl || (sl != 0 && dir * (newSL - sl) < InpTrailStepUSD))
         continue;
      if(dir * (px - newSL) < MinStopDist())
         continue;
      trade.PositionModify(tk, newSL, tp);
     }
  }

//--- breakout H4: tren D1, candle menutup di luar high/low N bar, SL ATR, TP kelipatan R
void StrategyHB()
  {
   datetime bar = iTime(_Symbol, g_hbTF, 0);
   if(bar <= 0 || bar == g_hbBar)
      return;
   g_hbBar = bar;
   long mg = MagicHB();
   if(CountPosMagic(mg) > 0)
     {
      g_hbStatus = "Posisi aktif";
      return;
     }
   if(IsWeekend() || LastEntryTime(mg) >= bar)
      return;
   string why = "";
   if(NewsBlocked(why))
     {
      g_hbStatus = "PAUSE news";
      return;
     }
   if(SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID) > InpHbMaxSpread)
     {
      g_hbStatus = "WAIT: spread lebar";
      return;
     }
   double f = Val(g_hFast[0], 0, 0), s = Val(g_hSlow[0], 0, 0), cd = iClose(_Symbol, PERIOD_D1, 0);
   double atr = Val(g_hHbAtr, 0, 1);
   if(f == EMPTY_VALUE || s == EMPTY_VALUE || atr == EMPTY_VALUE || cd <= 0)
     {
      g_hbStatus = "WAIT: data belum siap";
      return;
     }
   int dir = (f > s && cd > s) ? 1 : (f < s && cd < s) ? -1 : 0;
   if(dir == 0)
     {
      g_hbStatus = "WAIT: tren D1 campur";
      return;
     }
   int ih = iHighest(_Symbol, g_hbTF, MODE_HIGH, m_hbLookback, 2);
   int il = iLowest(_Symbol, g_hbTF, MODE_LOW, m_hbLookback, 2);
   if(ih < 0 || il < 0)
      return;
   double hh = iHigh(_Symbol, g_hbTF, ih), ll = iLow(_Symbol, g_hbTF, il);
   double c = iClose(_Symbol, g_hbTF, 1), c2 = iClose(_Symbol, g_hbTF, 2);
   bool trig = (dir == 1) ? (c > hh && c2 <= hh) : (c < ll && c2 >= ll);
   if(!trig)
     {
      g_hbStatus = (dir == 1) ? StringFormat("Tunggu tutup > %.2f", hh) : StringFormat("Tunggu tutup < %.2f", ll);
      return;
     }
   g_hbStatus = OpenStrategy(mg, dir, MathMax(atr * InpHbSLAtr, MinStopDist()), InpHbRR, g_hbCmt);
  }

//--- opening-range breakout: satu trade per hari, stop di range, keluar paling lambat InpOrbFlatMin
void StrategyORB()
  {
   if(!g_enORB)
      return;
   long mg = MagicORB();
   if(InpOrbFlatMin > 0 && TimeCurrent() >= OrbT0() + InpOrbFlatMin * 60 && CountPosMagic(mg) > 0)
      CloseMagic(mg);
   // mode Extreme: posisi dari sesi ORB sebelumnya ditutup saat sesi ORB berikutnya mulai
   if(g_extreme && CountPosMagic(mg) > 0)
     {
      datetime le = LastEntryTime(mg);
      if(le > 0 && le < OrbT0())
         CloseMagic(mg);
     }

   datetime bar = iTime(_Symbol, InpOrbSignalTF, 0);
   if(bar <= 0 || bar == g_orbBar)
      return;
   g_orbBar = bar;
   if(CountPosMagic(mg) > 0)
     {
      g_orbStatus = "Posisi aktif";
      return;
     }
   if(IsWeekend())
      return;
   if(LastEntryTime(mg) >= (g_extreme ? OrbT0() : DayStart()))
     {
      g_orbStatus = g_extreme ? "Sudah trade di sesi ORB ini" : "Sudah trade hari ini";
      return;
     }
   double oh = 0, ol = 0;
   if(!OrbRange(oh, ol))
     {
      g_orbStatus = "Range belum terbentuk";
      return;
     }
   datetime te = OrbT0() + InpOrbRangeMin * 60;
   if(TimeCurrent() > te + InpOrbWindowMin * 60)
     {
      g_orbStatus = "Tidak ada breakout hari ini";
      return;
     }
   if(iTime(_Symbol, InpOrbSignalTF, 1) < te)
      return;
   string why = "";
   if(NewsBlocked(why))
     {
      g_orbStatus = "PAUSE news";
      return;
     }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask - bid > InpOrbMaxSpread)
     {
      g_orbStatus = "WAIT: spread lebar";
      return;
     }
   double c = iClose(_Symbol, InpOrbSignalTF, 1);
   int dir = (c > oh) ? 1 : (c < ol && !InpOrbLongOnly) ? -1 : 0;
   if(dir == 0)
     {
      g_orbStatus = StringFormat("Tunggu tutup di luar %.2f-%.2f", ol, oh);
      return;
     }
   double price = (dir == 1) ? ask : bid;
   double slDist;
   if(InpOrbStop == ORB_STOP_MID)
      slDist = MathAbs(price - (oh + ol) / 2.0);
   else
      if(InpOrbStop == ORB_STOP_OPP)
         slDist = MathAbs(price - ((dir == 1) ? ol : oh));
      else
        {
         double atr = Val(g_hAtr, 0, 1);
         if(atr == EMPTY_VALUE)
            return;
         slDist = atr * InpSLAtr;
        }
   slDist = MathMax(MathMax(InpOrbMinSL, slDist), MinStopDist());
   g_orbStatus = OpenStrategy(mg, dir, slDist, InpOrbRR, CMT_ORB);
  }

//+------------------------------------------------------------------+
//| Strategi garis tren: top-down, break -> pullback/retest -> close |
//+------------------------------------------------------------------+
// nilai garis pada bar dengan shift tertentu (garis diperpanjang ke kanan)
double TLValue(const TLine &ln, const int shift)
  {
   int i1 = iBarShift(_Symbol, g_tlTF, ln.t1);
   int i2 = iBarShift(_Symbol, g_tlTF, ln.t2);
   if(i1 < 0 || i2 <= i1)
      return 0;
   return ln.p1 + (ln.p1 - ln.p2) / (i2 - i1) * (i1 - shift);
  }

// Cari garis tren terbaik dari swing: side=+1 resistance menurun (swing high),
// side=-1 support menanjak (swing low). Garis tidak boleh ditembus harga penutupan
// dari titik lama sampai bar fromBar, dan dipilih yang sentuhannya paling banyak.
bool TLFind(const MqlRates &r[], const int n, const int side, const int fromBar, const double tol, const int minTouches, TLine &out)
  {
   out.ok = false;
   int N = InpTlPivot;
   int piv[];
   for(int i = N + 1; i < n - N; i++)
     {
      double v = (side == 1) ? r[i].high : r[i].low;
      bool isP = true;
      for(int k = 1; k <= N && isP; k++)
        {
         if(side == 1)
           {
            if(r[i - k].high > v || r[i + k].high >= v)
               isP = false;
           }
         else
           {
            if(r[i - k].low < v || r[i + k].low <= v)
               isP = false;
           }
        }
      if(isP)
        {
         int q = ArraySize(piv);
         ArrayResize(piv, q + 1, 32);
         piv[q] = i;
        }
     }
   int np = ArraySize(piv);
   double bestScore = -1;
   for(int a = 0; a < np && a < 3; a++)          // titik terbaru: salah satu dari 3 swing terakhir
     {
      int    i1 = piv[a];
      double p1 = (side == 1) ? r[i1].high : r[i1].low;
      for(int b = a + 1; b < np; b++)
        {
         int i2 = piv[b];
         if(i2 - i1 < InpTlMinSpan)
            continue;
         double p2 = (side == 1) ? r[i2].high : r[i2].low;
         if(side == 1 && p2 <= p1)
            continue;                              // resistance harus menurun
         if(side == -1 && p2 >= p1)
            continue;                              // support harus menanjak
         double slope = (p1 - p2) / (i2 - i1);
         bool pierced = false;
         int  touches = 0, lastTouch = -100;
         for(int j = i2; j >= fromBar; j--)
           {
            double lv = p1 + slope * (i1 - j);
            if(j < i2)
              {
               if(side == 1 && r[j].close > lv + tol)
                 {
                  pierced = true;
                  break;
                 }
               if(side == -1 && r[j].close < lv - tol)
                 {
                  pierced = true;
                  break;
                 }
              }
            double ext = (side == 1) ? r[j].high : r[j].low;
            if(MathAbs(ext - lv) <= tol && MathAbs(j - lastTouch) >= 3)
              {
               touches++;
               lastTouch = j;
              }
           }
         if(pierced || touches < minTouches)
            continue;
         double score = touches * 1000.0 + (i2 - i1);
         if(score > bestScore)
           {
            bestScore = score;
            out.ok = true;
            out.t1 = r[i1].time; out.p1 = p1;
            out.t2 = r[i2].time; out.p2 = p2;
            out.touches = touches;
           }
        }
     }
   return out.ok;
  }

void TLDraw(const string id, const TLine &ln, const color c)
  {
   if(!InpTlDraw || !PanelEnabled())
      return;
   string nme = PFX + id + g_tlId;
   if(!ln.ok)
     {
      ObjectDelete(0, nme);
      return;
     }
   if(ObjectFind(0, nme) < 0)
     {
      ObjectCreate(0, nme, OBJ_TREND, 0, ln.t2, ln.p2, ln.t1, ln.p1);
      ObjectSetInteger(0, nme, OBJPROP_RAY_RIGHT, true);
      ObjectSetInteger(0, nme, OBJPROP_WIDTH, 2);
      ObjectSetInteger(0, nme, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, nme, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, nme, OBJPROP_COLOR, c);
   ObjectMove(0, nme, 0, ln.t2, ln.p2);
   ObjectMove(0, nme, 1, ln.t1, ln.p1);
  }

void TLAlert(const string msg)
  {
   if(InpTlAlerts && !g_tester)
      Alert("MTRB Pro ", _Symbol, ": ", msg);
  }

// posisi terbuka: SL mengikuti garis tren seberang; keluar bila garis itu ditembus
void TLManage(const MqlRates &r[], const int n, const double atr, const double tol)
  {
   long  mg = MagicTL();
   ulong tk = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t != 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == mg)
        {
         tk = t;
         break;
        }
     }
   if(tk == 0)
      return;
   int    dir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
   double sl  = PositionGetDouble(POSITION_SL);
   double tp  = PositionGetDouble(POSITION_TP);
   g_tlStatus = "Posisi aktif";

   if(g_tlTrail.ok && InpTlExitViolation)
     {
      double v = TLValue(g_tlTrail, 1);
      if(v > 0 && dir * (r[1].close - v) < 0)
        {
         trade.PositionClose(tk);
         g_tlTrail.ok = false;
         g_tlStatus = "Keluar: garis seberang ditembus";
         TLAlert(g_tlStatus);
         return;
        }
     }
   TLine ln;
   if(TLFind(r, n, -dir, 1, tol, 2, ln))
      g_tlTrail = ln;
   TLDraw("tl_trail", g_tlTrail, clrOrange);
   if(!g_tlTrail.ok || !InpTlTrailLine)
      return;
   double v0 = TLValue(g_tlTrail, 0);
   if(v0 <= 0)
      return;
   double cand = NormPrice(v0 - dir * InpTlSLBufAtr * atr);
   double px   = (dir == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if((sl == 0 || dir * (cand - sl) >= InpTrailStepUSD) && dir * (px - cand) >= MinStopDist())
      trade.PositionModify(tk, cand, tp);
  }

void StrategyTL()
  {
   datetime bar = iTime(_Symbol, g_tlTF, 0);
   if(bar <= 0 || bar == g_tlBar)
      return;
   g_tlBar = bar;
   long mg = MagicTL();

   MqlRates r[];
   ArraySetAsSeries(r, true);
   int n = CopyRates(_Symbol, g_tlTF, 0, InpTlLookback + InpTlPivot + 5, r);
   double atr = Val(g_hTlAtr, 0, 1);
   if(n < InpTlPivot * 4 + 20 || atr == EMPTY_VALUE || atr <= 0)
     {
      g_tlStatus = "WAIT: data belum siap";
      return;
     }
   double tol = m_tlTolAtr * atr;

   if(CountPosMagic(mg) > 0)
     {
      TLManage(r, n, atr, tol);
      g_tlState = 0;
      return;
     }
   g_tlTrail.ok = false;
   TLDraw("tl_trail", g_tlTrail, clrOrange);
   if(IsWeekend() || LastEntryTime(mg) >= bar)
      return;

   // top-down: arah dari tren D1
   int trend = 0;
   double f = Val(g_hFast[0], 0, 0), s = Val(g_hSlow[0], 0, 0), cd = iClose(_Symbol, PERIOD_D1, 0);
   if(f != EMPTY_VALUE && s != EMPTY_VALUE && cd > 0)
      trend = (f > s && cd > s) ? 1 : (f < s && cd < s) ? -1 : 0;
   if(InpTlTrendFilter && trend == 0)
     {
      g_tlState = 0;
      g_tlStatus = "WAIT: tren D1 campur";
      return;
     }

   // langkah 2 dan 3: pullback / retest, lalu candle menutup
   if(g_tlState == 1)
     {
      int    d     = g_tlDir;
      int    since = iBarShift(_Symbol, g_tlTF, g_tlBreakTime) - 1;
      double v     = TLValue(g_tlBreak, 1);
      if(v <= 0 || since > m_tlRetestBars || (InpTlTrendFilter && trend != d))
        {
         g_tlState = 0;
         g_tlStatus = "Retest tidak terjadi";
        }
      else
         if(d * (r[1].close - v) < -tol)
           {
            g_tlState = 0;
            g_tlStatus = "Break gagal (harga balik)";
           }
         else
           {
            double ext    = (d == 1) ? r[1].low : r[1].high;
            bool   touch  = (since >= 1) && (d * (ext - v) <= tol);
            bool   reject = (d * (r[1].close - v) > 0) && (d * (r[1].close - r[1].open) > 0);
            if(!(touch && reject))
              {
               g_tlStatus = StringFormat("Break OK, tunggu retest %.2f", v);
               return;
              }
            // entry
            g_tlState = 0;
            string why = "";
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            if(NewsBlocked(why) || ask - bid > InpTlMaxSpread)
              {
               g_tlStatus = "Retest saat news / spread lebar";
               return;
              }
            double price  = (d == 1) ? ask : bid;
            double stopPx = ((d == 1) ? MathMin(r[1].low, v) : MathMax(r[1].high, v)) - d * InpTlSLBufAtr * atr;
            // retest yang sah terjadi DI DEKAT garis; candle yang sudah lari jauh bukan retest
            if(InpTlMaxEntryAtr > 0 && d * (price - v) > InpTlMaxEntryAtr * atr)
              {
               g_tlStatus = "Retest terlalu jauh dari garis";
               return;
              }
            double slDist = d * (price - stopPx);
            if(slDist < MathMax(MinStopDist(), 0.3 * atr))
              {
               g_tlStatus = "SL terlalu rapat, dilewati";
               return;
              }
            double tpPx = 0;
            if(InpTlTPatSR)
              {
               // area support/resistance: high (low) tertinggi sebelumnya dalam rentang pencarian
               double sr = (d == 1) ? r[2].high : r[2].low;
               for(int j = 3; j < n; j++)
                  sr = (d == 1) ? MathMax(sr, r[j].high) : MathMin(sr, r[j].low);
               if(d * (sr - price) >= slDist)
                  tpPx = sr;
              }
            g_tlStatus = OpenStrategy(mg, d, slDist, InpTlRR, g_tlCmt, tpPx);
            TLAlert("entry garis tren - " + g_tlStatus);
            return;
           }
     }

   // langkah 1: cari garis tren, tunggu break
   for(int pass = 0; pass < 2; pass++)
     {
      int d = InpTlTrendFilter ? trend : (pass == 0 ? 1 : -1);
      if(InpTlTrendFilter && pass == 1)
         break;
      TLine ln;
      if(!TLFind(r, n, d, 2, tol, m_tlMinTouches, ln))
        {
         if(pass == 0)
           {
            g_tlStatus = "Belum ada garis tren sah";
            TLDraw("tl_main", ln, clrGold);
           }
         continue;
        }
      TLDraw("tl_main", ln, clrGold);
      double v1 = TLValue(ln, 1);
      if(v1 > 0 && d * (r[1].close - v1) > InpTlBreakAtr * atr)
        {
         g_tlBreak = ln;
         g_tlDir = d;
         g_tlState = 1;
         g_tlBreakTime = r[1].time;
         g_tlStatus = StringFormat("Break %s, tunggu retest", d == 1 ? "naik" : "turun");
         TLAlert(g_tlStatus);
         return;
        }
      g_tlStatus = StringFormat("Garis %.2f (%d sentuhan), tunggu break", v1, ln.touches);
     }
  }

//+------------------------------------------------------------------+
//| Strategi SMC: struktur -> liquidity sweep -> order block -> FVG  |
//| -> tunggu harga kembali ke zona (re-entry)                       |
//+------------------------------------------------------------------+
// Harga dicerminkan untuk arah sell, sehingga logika cukup ditulis sekali untuk buy.
double XH(const MqlRates &r[], const int j, const int d) { return (d == 1) ? r[j].high : -r[j].low; }
double XL(const MqlRates &r[], const int j, const int d) { return (d == 1) ? r[j].low : -r[j].high; }
double XO(const MqlRates &r[], const int j, const int d) { return d * r[j].open; }
double XC(const MqlRates &r[], const int j, const int d) { return d * r[j].close; }

bool SmcDetect(const MqlRates &r[], const int n, const int d, const double atr, SmcSetup &st)
  {
   st.ok = false;
   int N = InpSmcPivot;
   // 4. FVG: celah antara candle 3 dan candle 1, candle 2 adalah displacement
   double gapBot = XH(r, 3, d), gapTop = XL(r, 1, d);
   if(gapTop - gapBot < m_smcMinGap * atr)
      return false;
   if(XC(r, 2, d) - XO(r, 2, d) < m_smcDisp * atr)
      return false;
   // 2. liquidity sweep: titik terendah dalam beberapa bar sebelum displacement
   int m = 2;
   for(int j = 3; j <= 2 + InpSmcSweepBars && j < n; j++)
      if(XL(r, j, d) < XL(r, m, d))
         m = j;
   double S = XL(r, m, d);
   // level likuiditas: swing low terdekat yang lebih lama dari sweep
   int p = -1;
   for(int j = m + 2; j < n - N && j <= InpSmcLookback; j++)
     {
      bool isP = true;
      for(int k = 1; k <= N && isP; k++)
         if(XL(r, j - k, d) < XL(r, j, d) || XL(r, j + k, d) <= XL(r, j, d))
            isP = false;
      if(isP)
        {
         p = j;
         break;
        }
     }
   if(p < 0)
      return false;
   double lvl = XL(r, p, d);
   if(S >= lvl)
      return false;                                // level tidak tersapu
   if(MathMax(XC(r, 1, d), XC(r, 2, d)) <= lvl)
      return false;                                // belum kembali ke atas level: bukan jebakan
   // level harus masih utuh sampai gerakan sweep itu sendiri
   for(int j = m + InpSmcSweepBars + 1; j < p; j++)
      if(XL(r, j, d) < lvl)
         return false;
   // 1. struktur: displacement menembus high sebelum sweep (market structure shift)
   double hb = XH(r, m + 1, d);
   for(int j = m + 2; j <= m + InpSmcMssBars && j < p; j++)
      hb = MathMax(hb, XH(r, j, d));
   if(MathMax(XC(r, 1, d), XC(r, 2, d)) <= hb)
      return false;
   // 3. order block: candle berlawanan terakhir sebelum displacement
   int ob = m;
   for(int j = 3; j <= m; j++)
      if(XC(r, j, d) < XO(r, j, d))
        {
         ob = j;
         break;
        }
   double obTop = XH(r, ob, d), obBot = XL(r, ob, d);

   double entry = (InpSmcEntryMode == 1) ? (gapTop + gapBot) / 2.0 : (InpSmcEntryMode == 2) ? MathMin(obTop, gapTop) : gapTop;
   double stop  = (InpSmcStopAtOB ? MathMin(obBot, gapBot) : S) - InpSmcSLBufAtr * atr;
   if(entry - stop < 0.3 * atr)
      return false;
   double tp = 0;
   if(InpSmcTPatLiquidity)
     {
      double liq = XH(r, 1, d);
      for(int j = 2; j < n && j <= InpSmcLookback; j++)
         liq = MathMax(liq, XH(r, j, d));
      if(liq - entry >= entry - stop)
         tp = liq;
     }
   st.ok = true;
   st.dir = d;
   st.entry = d * entry;
   st.stop  = d * stop;
   st.tp    = (tp != 0) ? d * tp : 0;
   st.created = r[1].time;
   return true;
  }

void SmcDraw()
  {
   if(!PanelEnabled())
      return;
   string a = PFX + "smc_entry", b = PFX + "smc_stop";
   if(!g_smc.ok)
     {
      ObjectDelete(0, a);
      ObjectDelete(0, b);
      return;
     }
   if(ObjectFind(0, a) < 0)
     {
      ObjectCreate(0, a, OBJ_HLINE, 0, 0, g_smc.entry);
      ObjectCreate(0, b, OBJ_HLINE, 0, 0, g_smc.stop);
      ObjectSetInteger(0, a, OBJPROP_COLOR, clrDodgerBlue);
      ObjectSetInteger(0, b, OBJPROP_COLOR, clrTomato);
      ObjectSetInteger(0, a, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, b, OBJPROP_STYLE, STYLE_DOT);
     }
   ObjectSetDouble(0, a, OBJPROP_PRICE, g_smc.entry);
   ObjectSetDouble(0, b, OBJPROP_PRICE, g_smc.stop);
  }

void StrategySMC()
  {
   if(!g_enSMC)
      return;
   long mg = MagicSMC();

   // 5. re-entry: tiap tick, masuk begitu harga kembali ke zona
   if(g_smc.ok)
     {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double px  = (g_smc.dir == 1) ? ask : bid;
      if(g_smc.dir * (px - g_smc.entry) <= 0)
        {
         double slDist = g_smc.dir * (px - g_smc.stop);
         string why = "";
         if(CountPosMagic(mg) == 0 && slDist >= MinStopDist() && ask - bid <= InpSmcMaxSpread && !IsWeekend() && !NewsBlocked(why))
            g_smcStatus = OpenStrategy(mg, g_smc.dir, slDist, InpSmcRR, CMT_SMC, g_smc.tp);
         else
            g_smcStatus = "Zona tersentuh, entry dibatalkan";
         g_smc.ok = false;
         SmcDraw();
        }
     }

   datetime bar = iTime(_Symbol, InpSmcTF, 0);
   if(bar <= 0 || bar == g_smcBar)
      return;
   g_smcBar = bar;
   if(CountPosMagic(mg) > 0)
     {
      g_smcStatus = "Posisi aktif";
      g_smc.ok = false;
      return;
     }
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int n = CopyRates(_Symbol, InpSmcTF, 0, InpSmcLookback + InpSmcPivot + 10, r);
   double atr = Val(g_hSmcAtr, 0, 1);
   if(n < 40 || atr == EMPTY_VALUE || atr <= 0)
     {
      g_smcStatus = "WAIT: data belum siap";
      return;
     }
   // setup lama batal bila kedaluwarsa atau level stop sudah tersentuh
   if(g_smc.ok)
     {
      int    age = iBarShift(_Symbol, InpSmcTF, g_smc.created);
      double ext = (g_smc.dir == 1) ? r[1].low : r[1].high;
      if(age > InpSmcExpiryBars || g_smc.dir * (ext - g_smc.stop) < 0)
        {
         g_smc.ok = false;
         g_smcStatus = "Setup batal";
        }
     }
   // konteks: tren D1
   int trend = 0;
   double f = Val(g_hFast[0], 0, 0), s = Val(g_hSlow[0], 0, 0), cd = iClose(_Symbol, PERIOD_D1, 0);
   if(f != EMPTY_VALUE && s != EMPTY_VALUE && cd > 0)
      trend = (f > s && cd > s) ? 1 : (f < s && cd < s) ? -1 : 0;
   if(InpSmcTrendFilter && trend == 0)
     {
      g_smc.ok = false;
      g_smcStatus = "WAIT: tren D1 campur";
      SmcDraw();
      return;
     }
   for(int pass = 0; pass < 2; pass++)
     {
      int d = InpSmcTrendFilter ? trend : (pass == 0 ? 1 : -1);
      if(InpSmcTrendFilter && pass == 1)
         break;
      SmcSetup st;
      if(SmcDetect(r, n, d, atr, st))
        {
         g_smc = st;
         g_smcStatus = StringFormat("%s: tunggu harga kembali ke %.2f", d == 1 ? "BUY" : "SELL", st.entry);
         break;
        }
     }
   if(!g_smc.ok && StringFind(g_smcStatus, "BUY") < 0 && StringFind(g_smcStatus, "SELL") < 0)
      g_smcStatus = "Menunggu sweep + displacement";
   SmcDraw();
  }

//+------------------------------------------------------------------+
//| Strategi momentum: dua candle searah di timeframe peta (M30),    |
//| candle pertama impulsif; entry di timeframe kecil (M5) saat      |
//| harga retrace ke dalam range kedua candle itu                    |
//+------------------------------------------------------------------+
void StrategyMOM()
  {
   if(!g_enMOM)
      return;
   long mg = InpMagic + 105;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // --- eksekusi: menunggu retrace ke level di dalam range
   if(g_mom.ok)
     {
      int    d  = g_mom.dir;
      double px = (d == 1) ? ask : bid;
      bool   go = false;
      if(d * (px - g_mom.stop) <= 0)
        {
         g_mom.ok = false;
         g_momStatus = "Setup batal: range ditembus";
        }
      else
         if(!InpMomConfirm)
            go = (d * (px - g_mom.level) <= 0);
         else
           {
            datetime eb = iTime(_Symbol, InpMomEntryTF, 0);
            if(eb != g_momEBar)
              {
               g_momEBar = eb;
               double o = iOpen(_Symbol, InpMomEntryTF, 1), c = iClose(_Symbol, InpMomEntryTF, 1);
               double ext = (d == 1) ? iLow(_Symbol, InpMomEntryTF, 1) : iHigh(_Symbol, InpMomEntryTF, 1);
               if(d * (ext - g_mom.level) <= 0)
                  g_mom.touched = true;                       // harga sudah retrace ke level
               go = (g_mom.touched && d * (c - o) > 0);       // candle entry menutup searah
              }
           }
      if(go)
        {
         double slDist = d * (px - g_mom.stop);
         string why = "";
         if(CountPosMagic(mg) == 0 && slDist >= MinStopDist() && ask - bid <= InpMomMaxSpread && !IsWeekend() && !NewsBlocked(why))
            g_momStatus = OpenStrategy(mg, d, slDist, InpMomRR, "MTRB MOM");
         else
            g_momStatus = "Retrace terjadi, entry dibatalkan";
         g_mom.ok = false;
        }
     }

   // --- peta arah: tiap bar baru di timeframe peta
   datetime bar = iTime(_Symbol, InpMomBiasTF, 0);
   if(bar <= 0 || bar == g_momBar)
      return;
   g_momBar = bar;
   if(CountPosMagic(mg) > 0)
     {
      g_momStatus = "Posisi aktif";
      g_mom.ok = false;
      return;
     }
   if(g_mom.ok && iBarShift(_Symbol, InpMomBiasTF, g_mom.created) > m_momExpiry)
     {
      g_mom.ok = false;
      g_momStatus = "Setup kedaluwarsa";
     }
   double atr = Val(g_hMomAtr, 0, 1);
   if(atr == EMPTY_VALUE || atr <= 0 || IsWeekend())
      return;
   double o2 = iOpen(_Symbol, InpMomBiasTF, 2), c2 = iClose(_Symbol, InpMomBiasTF, 2);
   double o1 = iOpen(_Symbol, InpMomBiasTF, 1), c1 = iClose(_Symbol, InpMomBiasTF, 1);
   int d = (c2 > o2 && c1 > o1) ? 1 : (c2 < o2 && c1 < o1) ? -1 : 0;
   if(d == 0 || MathAbs(c2 - o2) < m_momImpulse * atr)
     {
      if(!g_mom.ok)
         g_momStatus = "Menunggu dua candle searah";
      return;
     }
   if(InpMomTrendFilter)
     {
      double f = Val(g_hFast[0], 0, 0), s = Val(g_hSlow[0], 0, 0), cd = iClose(_Symbol, PERIOD_D1, 0);
      int trend = (f != EMPTY_VALUE && s != EMPTY_VALUE && cd > 0) ? ((f > s && cd > s) ? 1 : (f < s && cd < s) ? -1 : 0) : 0;
      if(trend != d)
         return;
     }
   double H = MathMax(iHigh(_Symbol, InpMomBiasTF, 1), iHigh(_Symbol, InpMomBiasTF, 2));
   double L = MathMin(iLow(_Symbol, InpMomBiasTF, 1), iLow(_Symbol, InpMomBiasTF, 2));
   g_mom.ok      = true;
   g_mom.touched = false;
   g_mom.dir     = d;
   g_mom.level   = (d == 1) ? H - m_momFib * (H - L) : L + m_momFib * (H - L);
   g_mom.stop    = (d == 1) ? L - InpMomSLBufAtr * atr : H + InpMomSLBufAtr * atr;
   g_mom.created = iTime(_Symbol, InpMomBiasTF, 1);
   g_momEBar     = iTime(_Symbol, InpMomEntryTF, 0);
   g_momStatus   = StringFormat("%s: tunggu retrace ke %.2f", d == 1 ? "BUY" : "SELL", g_mom.level);
  }

//+------------------------------------------------------------------+
//| Jembatan dashboard                                               |
//|  EA -> dashboard : MTRB_Pro_status.json  (folder Common\Files)   |
//|  dashboard -> EA : MTRB_Pro_control.txt  (baris kunci=nilai)     |
//+------------------------------------------------------------------+
#define DASH_STATUS  "MTRB_Pro_status.json"
#define DASH_CONTROL "MTRB_Pro_control.txt"
#define N_ENG 14

struct EngInfo
  {
   string            id, name, type, tf;
   long              magic;
  };
struct EngStat
  {
   double            total, today;
   int               trades, wins, todayTrades;
  };
EngInfo         g_eng[N_ENG];
EngStat         g_es[N_ENG];
int             g_nEng = 0;
string          g_closedJson = "[]";
double          g_lastCloseAllId = 0;
bool            g_ctrlFirst = true;
datetime        g_statsAt = 0;
int             g_dashCount = 0;

string TfName(const ENUM_TIMEFRAMES tf) { return StringSubstr(EnumToString(tf), 7); }

string JS(string s)
  {
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   StringReplace(s, "\n", " ");
   StringReplace(s, "\r", " ");
   StringReplace(s, "\t", " ");
   return s;
  }

void DashAdd(const string id, const string name, const string type, const string tf, const long magic)
  {
   if(g_nEng >= N_ENG)
      return;
   g_eng[g_nEng].id = id; g_eng[g_nEng].name = name; g_eng[g_nEng].type = type; g_eng[g_nEng].tf = tf; g_eng[g_nEng].magic = magic;
   g_nEng++;
  }

void DashInit()
  {
   g_nEng = 0;
   DashAdd("DIP", "Scalping koreksi " + TfName(InpDipTF), "dip", TfName(InpDipTF), InpMagic + 107);
   DashAdd("NAO", "NadirAliOfficial", "nao", "10 detik", InpMagic + 115);
   DashAdd("CDL", "Pola candle + RSI " + TfName(InpCdlTF), "candle", TfName(InpCdlTF), InpMagic + 108);
   DashAdd("RH", "Range Hybrid " + TfName(InpRangeTF), "range", TfName(InpRangeTF), InpMagicRange);
   DashAdd("HB1", "Breakout " + TfName(InpHbTF), "breakout", TfName(InpHbTF), InpMagic + 101);
   DashAdd("HB2", "Breakout " + TfName(InpHbTF2), "breakout", TfName(InpHbTF2), InpMagic + 111);
   DashAdd("HB3", "Breakout " + TfName(InpHbTF3), "breakout", TfName(InpHbTF3), InpMagic + 112);
   DashAdd("TL1", "Garis tren " + TfName(InpTlTF), "trendline", TfName(InpTlTF), InpMagic + 103);
   DashAdd("TL2", "Garis tren " + TfName(InpTlTF2), "trendline", TfName(InpTlTF2), InpMagic + 113);
   DashAdd("ORB", StringFormat("ORB sesi %02d:%02d", InpOrbHour, InpOrbMinute), "orb", TfName(InpOrbSignalTF), InpMagic + 102);
   DashAdd("RSM", "RSI + MA " + TfName(InpRsmTF), "rsima", TfName(InpRsmTF), InpMagic + 106);
   DashAdd("MOM", "Momentum " + TfName(InpMomBiasTF), "momentum", TfName(InpMomBiasTF) + "/" + TfName(InpMomEntryTF), InpMagic + 105);
   DashAdd("SMC", "SMC " + TfName(InpSmcTF), "smc", TfName(InpSmcTF), InpMagic + 104);
   DashAdd("MAIN", "Strategi utama", "main", TfName(InpSignalTF), InpMagic);
  }

bool EngEnabled(const string id)
  {
   if(id == "HB1") return g_hbI[0].on;
   if(id == "HB2") return g_hbI[1].on;
   if(id == "HB3") return g_hbI[2].on;
   if(id == "TL1") return g_tlI[0].on;
   if(id == "TL2") return g_tlI[1].on;
   if(id == "ORB") return g_enORB;
   if(id == "MOM") return g_enMOM;
   if(id == "RSM") return g_enRSM;
   if(id == "DIP") return g_enDIP;
   if(id == "NAO") return g_enNAO;
   if(id == "CDL") return g_enCDL;
   if(id == "RH") return g_enRH;
   if(id == "SMC") return g_enSMC;
   if(id == "MAIN") return g_enMain;
   return false;
  }

string EngStatus(const string id)
  {
   if(id == "HB1") return g_hbI[0].status;
   if(id == "HB2") return g_hbI[1].status;
   if(id == "HB3") return g_hbI[2].status;
   if(id == "TL1") return g_tlI[0].status;
   if(id == "TL2") return g_tlI[1].status;
   if(id == "ORB") return g_orbStatus;
   if(id == "MOM") return g_momStatus;
   if(id == "RSM") return g_rsmStatus;
   if(id == "DIP") return g_dipStatus;
   if(id == "NAO") return g_naoStatus;
   if(id == "CDL") return g_cdlStatus;
   if(id == "RH") return g_rhStatus;
   if(id == "SMC") return g_smcStatus;
   return g_status;
  }

void EngSet(const string id, const bool on)
  {
   if(id == "HB1") g_hbI[0].on = on;
   else if(id == "HB2") g_hbI[1].on = on;
   else if(id == "HB3") g_hbI[2].on = on;
   else if(id == "TL1") g_tlI[0].on = on;
   else if(id == "TL2") g_tlI[1].on = on;
   else if(id == "ORB") g_enORB = on;
   else if(id == "MOM") g_enMOM = on;
   else if(id == "RSM") g_enRSM = on;
   else if(id == "DIP") g_enDIP = on;
   else if(id == "NAO") g_enNAO = on;
   else if(id == "CDL") g_enCDL = on;
   else if(id == "RH") g_enRH = on;
   else if(id == "SMC") g_enSMC = on;
   else if(id == "MAIN") g_enMain = on;
  }

int EngByMagic(const long m)
  {
   for(int i = 0; i < g_nEng; i++)
      if(g_eng[i].magic == m)
         return i;
   return -1;
  }

void CloseAllOurs()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsOurs())
         continue;
      trade.PositionClose(tk);
     }
  }

// baca perintah dashboard; perintah tutup-semua hanya dijalankan sekali per nomor perintah
void DashReadControl()
  {
   int h = FileOpen(DASH_CONTROL, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
     {
      g_ctrlFirst = false;
      return;
     }
   while(!FileIsEnding(h))
     {
      string ln = FileReadString(h);
      int p = StringFind(ln, "=");
      if(p <= 0)
         continue;
      string k = StringSubstr(ln, 0, p), v = StringSubstr(ln, p + 1);
      StringTrimLeft(k); StringTrimRight(k); StringTrimLeft(v); StringTrimRight(v);
      if(k == "paused")
         g_paused = (v == "1");
      else if(k == "max_open_risk")
         g_maxOpenRisk = MathMax(0.0, StringToDouble(v));
      else if(k == "daily_loss_pct")
         g_dailyLossPct = MathMax(0.0, StringToDouble(v));
      else if(k == "sl_min")
         g_slMin = MathMax(0.0, StringToDouble(v));
      else if(k == "sess_asia")
         g_sessOn[0] = (v == "1");
      else if(k == "sess_london")
         g_sessOn[1] = (v == "1");
      else if(k == "sess_ny")
         g_sessOn[2] = (v == "1");
      else if(k == "news_filter")
         g_newsOn = (v == "1");
      else if(k == "sl_max")
         g_slMax = MathMax(0.0, StringToDouble(v));
      else if(k == "mode")
        {
         bool ext = (v == "1");
         if(ext != g_extreme)
           {
            ApplyMode(ext);
            Print("[MTRB] dashboard: mode ", ext ? "EXTREME" : "NORMAL");
           }
        }
      else if(k == "tp_mode")
         g_tpMode = (int)MathMax(0, MathMin(3, (int)StringToInteger(v)));
      else if(k == "tp_usd")
         g_tpUsd = MathMax(0.0, StringToDouble(v));
      else if(k == "trail_start")
         g_trStart = MathMax(0.0, StringToDouble(v));
      else if(k == "trail_dist")
         g_trDist = MathMax(0.0, StringToDouble(v));
      else if(k == "be_at")
         g_beAt = MathMax(0.0, StringToDouble(v));
      else if(k == "be_lock")
         g_beLock = MathMax(0.0, StringToDouble(v));
      else if(k == "close_all")
        {
         double id = StringToDouble(v);
         if(id > 0 && id != g_lastCloseAllId)
           {
            g_lastCloseAllId = id;
            if(!g_ctrlFirst)                       // perintah lama saat EA baru dipasang tidak dijalankan
              {
               Print("[MTRB] dashboard: tutup semua posisi");
               CloseAllOurs();
              }
           }
        }
      else if(RuleControl(k, v))
        {
        }
      else
         EngSet(k, v == "1");
     }
   FileClose(h);
   g_ctrlFirst = false;
  }

// statistik per mesin dari riwayat akun + daftar trade tertutup terakhir
void DashStats()
  {
   for(int i = 0; i < g_nEng; i++)
     {
      g_es[i].total = 0; g_es[i].today = 0; g_es[i].trades = 0; g_es[i].wins = 0; g_es[i].todayTrades = 0;
     }
   g_closedJson = "[]";
   if(!HistorySelect(0, TimeCurrent() + 60))
      return;
   datetime d0 = DayStart();
   int n = HistoryDealsTotal();
   string rows = "";
   int shown = 0;
   for(int i = n - 1; i >= 0; i--)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0 || HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol)
         continue;
      int e = EngByMagic(HistoryDealGetInteger(tk, DEAL_MAGIC));
      if(e < 0)
         continue;
      double   p  = HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_SWAP) + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      datetime tm = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      long     en = HistoryDealGetInteger(tk, DEAL_ENTRY);
      g_es[e].total += p;
      if(tm >= d0)
         g_es[e].today += p;
      if(en != DEAL_ENTRY_OUT && en != DEAL_ENTRY_OUT_BY)
         continue;
      g_es[e].trades++;
      if(p > 0)
         g_es[e].wins++;
      if(tm >= d0)
         g_es[e].todayTrades++;
      if(shown < 40)
        {
         // deal penutup berlawanan arah dengan posisinya
         string side = (HistoryDealGetInteger(tk, DEAL_TYPE) == DEAL_TYPE_SELL) ? "BUY" : "SELL";
         // harga dan waktu entry: deal pembuka dengan nomor posisi yang sama
         long   pid = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
         double opx = 0;
         long   otm = 0;
         for(int q = i - 1; q >= 0; q--)
           {
            ulong t2 = HistoryDealGetTicket(q);
            if(t2 == 0)
               continue;
            if(HistoryDealGetInteger(t2, DEAL_POSITION_ID) == pid && HistoryDealGetInteger(t2, DEAL_ENTRY) == DEAL_ENTRY_IN)
              {
               opx = HistoryDealGetDouble(t2, DEAL_PRICE);
               otm = HistoryDealGetInteger(t2, DEAL_TIME);
               break;
              }
           }
         rows += (shown > 0 ? "," : "") + StringFormat("{\"engine\":\"%s\",\"side\":\"%s\",\"lot\":%.2f,\"open\":%s,\"open_time\":%I64d,\"close\":%s,\"pl\":%.2f,\"time\":%I64d,\"reason\":\"%s\"}",
                 g_eng[e].id, side, HistoryDealGetDouble(tk, DEAL_VOLUME), DoubleToString(opx, _Digits), otm,
                 DoubleToString(HistoryDealGetDouble(tk, DEAL_PRICE), _Digits),
                 p, (long)tm, ReasonStr(HistoryDealGetInteger(tk, DEAL_REASON)));
         shown++;
        }
     }
   g_closedJson = "[" + rows + "]";
   g_statsDirty = false;
   g_statsAt = TimeCurrent();
  }

void DashWriteStatus()
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   string login = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   string tail  = (StringLen(login) > 3) ? StringSubstr(login, StringLen(login) - 3) : login;
   bool   algo  = (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && (bool)MQLInfoInteger(MQL_TRADE_ALLOWED);
   string why = "";
   bool   newsBlk = NewsBlocked(why);

   string s = "{";
   s += StringFormat("\"v\":\"3.07\",\"ts\":%I64d,\"written\":%I64d,\"refreshed\":%I64d,\"refresh_min\":%d,", (long)TimeCurrent(), (long)TimeLocal(), (long)g_refAt, InpStatusRefreshMin);
   s += StringFormat("\"account\":{\"server\":\"%s\",\"login_tail\":\"%s\",\"demo\":%s,\"currency\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,\"free_margin\":%.2f,\"margin_level\":%.1f,\"leverage\":%I64d,\"connected\":%s},",
                     JS(AccountInfoString(ACCOUNT_SERVER)), tail, (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO) ? "true" : "false",
                     JS(AccountInfoString(ACCOUNT_CURRENCY)), AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY),
                     AccountInfoDouble(ACCOUNT_MARGIN_FREE), AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), AccountInfoInteger(ACCOUNT_LEVERAGE),
                     (bool)TerminalInfoInteger(TERMINAL_CONNECTED) ? "true" : "false");
   s += StringFormat("\"symbol\":{\"name\":\"%s\",\"bid\":%s,\"ask\":%s,\"spread\":%.2f,\"digits\":%d},",
                     JS(_Symbol), DoubleToString(bid, _Digits), DoubleToString(ask, _Digits), ask - bid, _Digits);
   // bias 7 timeframe
   s += StringFormat("\"bias\":{\"score\":%.0f,\"ok\":%s,\"tf\":[", g_score, g_scoreOk ? "true" : "false");
   for(int i = 0; i < NTF; i++)
      s += (i > 0 ? "," : "") + StringFormat("{\"n\":\"%s\",\"b\":%d}", g_tfName[i], g_bias[i]);
   s += "]},";
   s += StringFormat("\"risk\":{\"open_risk\":%.2f,\"max_open_risk\":%.2f,\"day_start_equity\":%.2f,\"day_pl\":%.2f,\"daily_loss_pct\":%.2f,\"locked\":%s,\"paused\":%s,\"news_blocked\":%s,\"news_reason\":\"%s\",\"algo\":%s,\"lot\":%.2f,\"sl_min\":%.2f,\"sl_max\":%.2f,\"mode\":%d,\"tp_mode\":%d,\"tp_usd\":%.2f,\"trail_start\":%.2f,\"trail_dist\":%.2f,\"be_at\":%.2f,\"be_lock\":%.2f,\"flow_mode\":%d,\"news_filter\":%s,\"news_before\":%d,\"news_after\":%d},",
                     OpenRiskNow(), g_maxOpenRisk, g_eqDayStart, (g_eqDayStart > 0 ? AccountInfoDouble(ACCOUNT_EQUITY) - g_eqDayStart : 0.0), g_dailyLossPct,
                     PortfolioDayLocked() ? "true" : "false", g_paused ? "true" : "false", newsBlk ? "true" : "false", JS(why), algo ? "true" : "false", NormLot(InpLot), g_slMin, g_slMax, (int)g_extreme, g_tpMode, g_tpUsd, g_trStart, g_trDist, g_beAt, g_beLock, g_flowMode,
                     g_newsOn ? "true" : "false", InpNewsBeforeMin, InpNewsAfterMin);
   s += StringFormat("\"sessions\":{\"asia\":%s,\"london\":%s,\"ny\":%s,\"now\":%d,\"london_hour\":%d,\"ny_hour\":%d},",
                     g_sessOn[0] ? "true" : "false", g_sessOn[1] ? "true" : "false", g_sessOn[2] ? "true" : "false",
                     SessionNow(), InpSessLondonHour, InpSessNYHour);
   s += FlowJson();
   // mesin
   s += "\"engines\":[";
   for(int i = 0; i < g_nEng; i++)
     {
      int    np = CountPosMagic(g_eng[i].magic);
      double fp = 0;
      for(int j = PositionsTotal() - 1; j >= 0; j--)
        {
         if(PositionGetTicket(j) == 0)
            continue;
         if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == g_eng[i].magic)
            fp += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
        }
      s += (i > 0 ? "," : "") + StringFormat("{\"id\":\"%s\",\"name\":\"%s\",\"type\":\"%s\",\"tf\":\"%s\",\"enabled\":%s,\"status\":\"%s\",\"positions\":%d,\"float_pl\":%.2f,\"total_pl\":%.2f,\"trades\":%d,\"wins\":%d,\"today_pl\":%.2f,\"today_trades\":%d,\"blk\":\"%s\",\"msp\":%.2f}",
           g_eng[i].id, JS(g_eng[i].name), g_eng[i].type, g_eng[i].tf, EngEnabled(g_eng[i].id) ? "true" : "false", JS(EngStatus(g_eng[i].id)),
           np, fp, g_es[i].total, g_es[i].trades, g_es[i].wins, g_es[i].today, g_es[i].todayTrades, RuleHours(i), g_mSp[i]);
     }
   s += "],";
   // posisi terbuka
   s += "\"positions\":[";
   int c = 0;
   for(int j = 0; j < PositionsTotal(); j++)
     {
      ulong tk = PositionGetTicket(j);
      if(tk == 0 || !IsOurs())
         continue;
      int e = EngByMagic(PositionGetInteger(POSITION_MAGIC));
      s += (c > 0 ? "," : "") + StringFormat("{\"ticket\":%I64u,\"engine\":\"%s\",\"side\":\"%s\",\"lot\":%.2f,\"open\":%s,\"sl\":%s,\"tp\":%s,\"price\":%s,\"pl\":%.2f,\"time\":%I64d}",
           tk, (e >= 0 ? g_eng[e].id : "?"), (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "BUY" : "SELL", PositionGetDouble(POSITION_VOLUME),
           DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), _Digits), DoubleToString(PositionGetDouble(POSITION_SL), _Digits),
           DoubleToString(PositionGetDouble(POSITION_TP), _Digits), DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), _Digits),
           PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP), (long)PositionGetInteger(POSITION_TIME));
      c++;
     }
   s += "],\"closed\":" + g_closedJson + ",";
   // news terdekat
   s += "\"news\":[";
   datetime now = TimeTradeServer();
   int shown = 0;
   for(int i = 0; i < ArraySize(g_news) && shown < 8; i++)
     {
      if(g_news[i].t < now - InpNewsAfterMin * 60)
         continue;
      s += (shown > 0 ? "," : "") + StringFormat("{\"t\":%I64d,\"name\":\"%s\",\"imp\":%d}", (long)g_news[i].t, JS(g_news[i].name), g_news[i].imp);
      shown++;
     }
   s += "]}";

   uchar buf[];
   int len = StringToCharArray(s, buf, 0, WHOLE_ARRAY, CP_UTF8);
   int h = FileOpen(DASH_STATUS, FILE_WRITE | FILE_BIN | FILE_COMMON | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return;
   if(len > 1)
      FileWriteArray(h, buf, 0, len - 1);
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Estimasi Buy vs Sell volume                                      |
//| Emas CFD tidak punya volume asli: tiap tick dihitung buy kalau   |
//| harga tengah naik, sell kalau turun (tick rule). Timeframe besar |
//| atau tick kosong: buy = volume x posisi close di dalam candle.   |
//+------------------------------------------------------------------+
#define FLOW_SLOTS 12
struct FlowBuf
  {
   ENUM_TIMEFRAMES   tf;
   datetime          t[];
   double            b[], s[];
  };
FlowBuf         g_fb[FLOW_SLOTS];
int             g_fbN = 0;
string          g_blkHr[N_ENG];        // jam WIB yang diblok hasil analisa, format ",11,12,"
double          g_mSp[N_ENG];          // spread maks per mesin hasil analisa (0 = ikut mesin)

void FlowBar(const ENUM_TIMEFRAMES tf, const int shift, double &buy, double &sell)
  {
   buy = 0; sell = 0;
   datetime t0 = iTime(_Symbol, tf, shift);
   int ps = PeriodSeconds(tf);
   if(t0 <= 0)
      return;
   if(ps <= InpFlowTickMaxMin * 60)
     {
      MqlTick tk[];
      int n = CopyTicksRange(_Symbol, tk, COPY_TICKS_INFO, (ulong)t0 * 1000, (ulong)(t0 + ps) * 1000 - 1);
      if(n >= 10)
        {
         double prev = 0;
         int    last = 0;
         for(int i = 0; i < n; i++)
           {
            if(tk[i].bid <= 0 || tk[i].ask <= 0)
               continue;
            double p = (tk[i].bid + tk[i].ask) / 2.0;
            if(prev > 0)
              {
               if(p > prev)
                  last = 1;
               else if(p < prev)
                  last = -1;
               double v = (tk[i].volume_real > 0) ? tk[i].volume_real : 1.0;
               if(last > 0)
                  buy += v;
               else if(last < 0)
                  sell += v;
              }
            prev = p;
           }
         if(buy + sell > 0)
            return;
        }
     }
   double h = iHigh(_Symbol, tf, shift), l = iLow(_Symbol, tf, shift), c = iClose(_Symbol, tf, shift);
   double v = (double)MathMax(1, iVolume(_Symbol, tf, shift));
   if(h - l <= 0)
     {
      buy = v / 2.0; sell = v / 2.0;
      return;
     }
   buy = v * (c - l) / (h - l);
   sell = v - buy;
  }

// hasil volume untuk candle tertutup di timeframe tf; nilai per candle disimpan supaya tiap candle dihitung sekali
bool FlowGet(const ENUM_TIMEFRAMES tf, FlowRes &r)
  {
   ZeroMemory(r);
   int N = MathMax(6, MathMin(200, InpFlowBars));
   int k = -1;
   for(int i = 0; i < g_fbN; i++)
      if(g_fb[i].tf == tf)
        {
         k = i;
         break;
        }
   if(k < 0)
     {
      if(g_fbN >= FLOW_SLOTS)
         return false;
      k = g_fbN++;
      g_fb[k].tf = tf;
      ArrayResize(g_fb[k].t, 0); ArrayResize(g_fb[k].b, 0); ArrayResize(g_fb[k].s, 0);
     }
   datetime last = iTime(_Symbol, tf, 1);
   if(last <= 0 || iTime(_Symbol, tf, N) <= 0)
      return false;
   int m = ArraySize(g_fb[k].t);
   if(m != N || g_fb[k].t[m - 1] != last)
     {
      datetime nt[];
      double   nb[], ns[];
      ArrayResize(nt, N); ArrayResize(nb, N); ArrayResize(ns, N);
      for(int j = 0; j < N; j++)
        {
         int sh = N - j;                       // j = 0 paling lama, j = N-1 candle tertutup terakhir
         nt[j] = iTime(_Symbol, tf, sh);
         int f = -1;
         for(int q = 0; q < m; q++)
            if(g_fb[k].t[q] == nt[j])
              {
               f = q;
               break;
              }
         if(f >= 0)
           {
            nb[j] = g_fb[k].b[f]; ns[j] = g_fb[k].s[f];
           }
         else
            FlowBar(tf, sh, nb[j], ns[j]);
        }
      ArrayResize(g_fb[k].t, N); ArrayResize(g_fb[k].b, N); ArrayResize(g_fb[k].s, N);
      for(int j = 0; j < N; j++)
        {
         g_fb[k].t[j] = nt[j]; g_fb[k].b[j] = nb[j]; g_fb[k].s[j] = ns[j];
        }
     }
   double tb = 0, ts = 0, b5 = 0, s5 = 0, run = 0;
   double cvd[];
   ArrayResize(cvd, N);
   for(int j = 0; j < N; j++)
     {
      double b = g_fb[k].b[j], s = g_fb[k].s[j];
      run += b - s; cvd[j] = run; tb += b; ts += s;
      if(j >= N - 5)
        {
         b5 += b; s5 += s;
        }
     }
   double lb = g_fb[k].b[N - 1], ls = g_fb[k].s[N - 1];
   r.buyPct   = (lb + ls > 0) ? lb / (lb + ls) * 100.0 : 50.0;
   r.deltaPct = (lb + ls > 0) ? (lb - ls) / (lb + ls) * 100.0 : 0.0;
   r.cvdPct   = (tb + ts > 0) ? (tb - ts) / (tb + ts) * 100.0 : 0.0;
   r.slopePct = (b5 + s5 > 0) ? (b5 - s5) / (b5 + s5) * 100.0 : 0.0;
   // divergence: 3 candle terakhir membuat high/low baru tapi CVD tidak ikut
   int    hiR = -1, hiP = -1, loR = -1, loP = -1;
   double hr = 0, hp = 0, lr = DBL_MAX, lp = DBL_MAX, avV = 0, avR = 0;
   for(int j = 0; j < N; j++)
     {
      int    sh = N - j;
      double h = iHigh(_Symbol, tf, sh), l = iLow(_Symbol, tf, sh);
      if(j >= N - 3)
        {
         if(h > hr) { hr = h; hiR = j; }
         if(l < lr) { lr = l; loR = j; }
        }
      else
        {
         if(h > hp) { hp = h; hiP = j; }
         if(l < lp) { lp = l; loP = j; }
        }
      if(j < N - 1)
        {
         avV += g_fb[k].b[j] + g_fb[k].s[j];
         avR += h - l;
        }
     }
   if(hiR >= 0 && hiP >= 0 && hr > hp && cvd[hiR] < cvd[hiP])
      r.div = -1;
   else if(loR >= 0 && loP >= 0 && lr < lp && cvd[loR] > cvd[loP])
      r.div = 1;
   // absorption: candle terakhir volumenya besar tapi geraknya kecil, agresornya tertahan
   avV /= (N - 1); avR /= (N - 1);
   double rng1 = iHigh(_Symbol, tf, 1) - iLow(_Symbol, tf, 1);
   if(avV > 0 && avR > 0 && lb + ls >= 1.5 * avV && rng1 <= 0.6 * avR)
      r.absorb = (lb > ls) ? -1 : 1;
   r.ok = true;
   return true;
  }

// timeframe yang dipakai tiap mesin untuk membaca volume
ENUM_TIMEFRAMES EngTF(const long m)
  {
   if(m == InpMagic + 107) return InpDipTF;
   if(m == InpMagic + 115) return PERIOD_M1;
   if(m == InpMagic + 108) return InpCdlTF;
   if(m == InpMagicRange)  return InpRangeTF;
   if(m == InpMagic + 101) return InpHbTF;
   if(m == InpMagic + 111) return InpHbTF2;
   if(m == InpMagic + 112) return InpHbTF3;
   if(m == InpMagic + 103) return InpTlTF;
   if(m == InpMagic + 113) return InpTlTF2;
   if(m == InpMagic + 102) return InpOrbSignalTF;
   if(m == InpMagic + 106) return InpRsmTF;
   if(m == InpMagic + 105) return InpMomEntryTF;
   if(m == InpMagic + 104) return InpSmcTF;
   return InpSignalTF;
  }

// mesin pembalikan (entry melawan gerak terakhir): Range Hybrid dan pola candle
bool EngReversal(const long m) { return (m == InpMagicRange || m == InpMagic + 108); }

// "" = volume mendukung entry, selain itu alasan penolakan
string FlowVerdict(const long magic, const int dir, const FlowRes &r)
  {
   if(!r.ok)
      return "";
   double with = (dir == 1) ? r.buyPct : 100.0 - r.buyPct;     // porsi volume searah entry
   if(EngReversal(magic))
     {
      double th = g_extreme ? MathMax(InpFlowRevPct, 65.0) : InpFlowRevPct;
      // divergence atau absorption searah entry membatalkan penolakan
      if(100.0 - with >= th && r.div != dir && r.absorb != dir)
         return StringFormat("Volume: dorongan lawan %.0f%%", 100.0 - with);
      return "";
     }
   double th = g_extreme ? MathMin(InpFlowTrendPct, 52.0) : InpFlowTrendPct;
   if(with < th)
      return StringFormat("Volume: %s %.0f%% < %.0f%%", dir == 1 ? "buy" : "sell", with, th);
   if(dir * r.slopePct <= 0)
      return "Volume: CVD tidak searah";
   return "";
  }

string FlowJson()
  {
   FlowRes r;
   if(g_flowMode == 0 || !FlowGet(PERIOD_M5, r))
      return "\"flow\":null,";
   return StringFormat("\"flow\":{\"tf\":\"M5\",\"buy\":%.1f,\"delta\":%.1f,\"cvd\":%.1f,\"slope\":%.1f,\"div\":%d,\"absorb\":%d},",
                       r.buyPct, r.deltaPct, r.cvdPct, r.slopePct, r.div, r.absorb);
  }

//+------------------------------------------------------------------+
//| Aturan dari hasil analisa (diterapkan lewat dashboard)           |
//+------------------------------------------------------------------+
int EngById(const string id)
  {
   for(int i = 0; i < g_nEng; i++)
      if(g_eng[i].id == id)
         return i;
   return -1;
  }

string RuleHours(const int e)
  {
   string s = g_blkHr[e];
   if(StringLen(s) >= 2)
      s = StringSubstr(s, 1, StringLen(s) - 2);
   return s;
  }

string RuleBlock(const long magic)
  {
   int e = EngByMagic(magic);
   if(e < 0)
      return "";
   if(g_blkHr[e] != "")
     {
      MqlDateTime d;
      TimeToStruct(ToWib(TimeTradeServer()), d);
      if(StringFind(g_blkHr[e], "," + IntegerToString(d.hour) + ",") >= 0)
         return StringFormat("Aturan analisa: jam %02d WIB diblok", d.hour);
     }
   if(g_mSp[e] > 0)
     {
      double sp = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(sp > g_mSp[e])
         return StringFormat("Aturan analisa: spread %.2f > %.2f", sp, g_mSp[e]);
     }
   return "";
  }

bool RuleControl(const string k, const string v)
  {
   if(k == "flow_mode")
     {
      g_flowMode = (int)MathMax(0, MathMin(2, (int)StringToInteger(v)));
      return true;
     }
   if(StringFind(k, "blk_") == 0)
     {
      int e = EngById(StringSubstr(k, 4));
      if(e >= 0)
         g_blkHr[e] = (v == "") ? "" : "," + v + ",";
      return true;
     }
   if(StringFind(k, "msp_") == 0)
     {
      int e = EngById(StringSubstr(k, 4));
      if(e >= 0)
         g_mSp[e] = MathMax(0.0, StringToDouble(v));
      return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Pencatat trade: kondisi pasar saat entry + hasil saat tutup      |
//| MTRB_Pro_tradelog.csv = bahan analisa (satu baris per posisi)     |
//| MTRB_Pro_history.csv = seluruh riwayat posisi EA (untuk export)  |
//+------------------------------------------------------------------+
#define LOG_FEAT_N 19
#define LOG_HDR  "close_time_wib,open_time_wib,position,engine,side,lot,open_price,close_price,profit,duration_min,exit_reason,mfe_usd,mae_usd,hour_wib,dow,session,mode,spread,sl_dist,tp_dist,risk_usd,atr_m5,atr_h1,adx_m15,rsi_m5,bias_score,flow_buy_pct,flow_slope,flow_cvd,flow_div,flow_absorb,flow_ok"
#define HIST_HDR "close_time_wib,open_time_wib,position,engine,side,lot,open_price,close_price,profit,duration_min,exit_reason"
int             g_hLgAtr5 = INVALID_HANDLE, g_hLgAtrH1 = INVALID_HANDLE;
ulong           g_lgPid[];
string          g_lgFeat[];
bool            g_histDirty = true;

string LogFile(const string base) { return "MTRB_Pro_" + base + (g_tester ? "_tester" : "") + ".csv"; }

void FileBytes(const int h, const string s)
  {
   uchar buf[];
   int len = StringToCharArray(s, buf, 0, WHOLE_ARRAY, CP_UTF8);
   if(len > 1)
      FileWriteArray(h, buf, 0, len - 1);
  }

void AppendLine(const string file, const string header, const string line)
  {
   int h = FileOpen(file, FILE_READ | FILE_WRITE | FILE_BIN | FILE_COMMON | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return;
   if(FileSize(h) == 0 && header != "")
      FileBytes(h, header + "\r\n");
   FileSeek(h, 0, SEEK_END);
   FileBytes(h, line + "\r\n");
   FileClose(h);
  }

void LogInit()
  {
   g_hLgAtr5  = iATR(_Symbol, PERIOD_M5, 14);
   g_hLgAtrH1 = iATR(_Symbol, PERIOD_H1, 14);
   ArrayResize(g_lgPid, 0);
   ArrayResize(g_lgFeat, 0);
   if(!InpTradeLog)
      return;
   if(g_tester)
     {
      // backtest: file mulai dari kosong tiap pengujian supaya tidak bercampur dengan pengujian sebelumnya
      FileDelete(LogFile("entrylog"), FILE_COMMON);
      FileDelete(LogFile("tradelog"), FILE_COMMON);
      return;
     }
   int h = FileOpen(LogFile("entrylog"), FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
      return;
   while(!FileIsEnding(h))
     {
      string ln = FileReadString(h);
      int p = StringFind(ln, ",");
      if(p <= 0)
         continue;
      int k = ArraySize(g_lgPid);
      ArrayResize(g_lgPid, k + 1, 256);
      ArrayResize(g_lgFeat, k + 1, 256);
      g_lgPid[k]  = (ulong)StringToInteger(StringSubstr(ln, 0, p));
      g_lgFeat[k] = StringSubstr(ln, p + 1);
     }
   FileClose(h);
   int n = ArraySize(g_lgPid);
   if(n > 400)                                // simpan 400 entry terakhir saja di memori
     {
      ArrayRemove(g_lgPid, 0, n - 400);
      ArrayRemove(g_lgFeat, 0, n - 400);
     }
  }

void LogDeinit()
  {
   IndicatorRelease(g_hLgAtr5);
   IndicatorRelease(g_hLgAtrH1);
  }

string NumS(const double v, const int d) { return (v == EMPTY_VALUE) ? "" : DoubleToString(v, d); }

void LogEntry(const ulong pid, const long magic, const int dir, const double sl, const double tp, const double slDist)
  {
   if(!InpTradeLog || pid == 0)
      return;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px  = trade.ResultPrice();
   if(px <= 0)
      px = (dir == 1) ? ask : bid;
   double vol = trade.ResultVolume(), risk = 0, pr = 0;
   ENUM_ORDER_TYPE ty = (dir == 1) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(sl > 0 && OrderCalcProfit(ty, _Symbol, vol, px, sl, pr) && pr < 0)
      risk = -pr;
   MqlDateTime d;
   TimeToStruct(ToWib(TimeTradeServer()), d);
   FlowRes fr;
   bool    fok = FlowGet(EngTF(magic), fr);
   string  fv  = fok ? FlowVerdict(magic, dir, fr) : "";
   string f = StringFormat("%d,%d,%s,%d,%.2f,%.2f,%.2f,%.2f,%s,%s,%s,%s,%.0f,%s,%s,%s,%s,%s,%s",
                           d.hour, d.day_of_week, SessionName(SessionNow()), (int)g_extreme, ask - bid,
                           (sl > 0 ? MathAbs(px - sl) : slDist), (tp > 0 ? MathAbs(tp - px) : 0.0), risk,
                           NumS(Val(g_hLgAtr5, 0, 1), 2), NumS(Val(g_hLgAtrH1, 0, 1), 2), NumS(Val(g_hAdx, 0, 1), 1), NumS(Val(g_hRsi, 0, 1), 1), g_score,
                           fok ? DoubleToString(fr.buyPct, 1) : "", fok ? DoubleToString(fr.slopePct, 1) : "", fok ? DoubleToString(fr.cvdPct, 1) : "",
                           fok ? IntegerToString(fr.div) : "", fok ? IntegerToString(fr.absorb) : "", fok ? (fv == "" ? "1" : "0") : "");
   int k = ArraySize(g_lgPid);
   ArrayResize(g_lgPid, k + 1, 256);
   ArrayResize(g_lgFeat, k + 1, 256);
   g_lgPid[k] = pid; g_lgFeat[k] = f;
   AppendLine(LogFile("entrylog"), "", StringFormat("%I64u,", pid) + f);
  }

void LogOnDeal(const ulong deal)
  {
   g_histDirty = true;
   LogClose(deal);
  }

// satu baris hasil saat posisi tutup penuh; MFE/MAE diperkirakan dari candle M1 selama posisi terbuka
void LogClose(const ulong deal)
  {
   if(!InpTradeLog || deal == 0 || !HistoryDealSelect(deal))
      return;
   long en = HistoryDealGetInteger(deal, DEAL_ENTRY);
   if(en != DEAL_ENTRY_OUT && en != DEAL_ENTRY_OUT_BY)
      return;
   if(HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol || !IsOurMagic(HistoryDealGetInteger(deal, DEAL_MAGIC)))
      return;
   long  mg  = HistoryDealGetInteger(deal, DEAL_MAGIC);
   ulong pid = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
   if(PositionSelectByTicket(pid))
      return;                                 // masih ada sisa lot: dicatat saat tutup penuh
   if(!HistorySelectByPosition(pid))
      return;
   double   pl = 0, vol = 0, opx = 0, cpx = 0;
   datetime ot = 0, ct = 0;
   int      dir = 0;
   long     rsn = 0;
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0)
         continue;
      pl += HistoryDealGetDouble(t, DEAL_PROFIT) + HistoryDealGetDouble(t, DEAL_SWAP) + HistoryDealGetDouble(t, DEAL_COMMISSION);
      long e = HistoryDealGetInteger(t, DEAL_ENTRY);
      if(e == DEAL_ENTRY_IN)
        {
         opx = HistoryDealGetDouble(t, DEAL_PRICE);
         ot  = (datetime)HistoryDealGetInteger(t, DEAL_TIME);
         vol = HistoryDealGetDouble(t, DEAL_VOLUME);
         dir = (HistoryDealGetInteger(t, DEAL_TYPE) == DEAL_TYPE_BUY) ? 1 : -1;
        }
      else
        {
         cpx = HistoryDealGetDouble(t, DEAL_PRICE);
         ct  = (datetime)HistoryDealGetInteger(t, DEAL_TIME);
         rsn = HistoryDealGetInteger(t, DEAL_REASON);
        }
     }
   if(ot == 0 || dir == 0)
      return;
   double hi = MathMax(opx, cpx), lo = MathMin(opx, cpx);
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M1, ot, ct, r);
   for(int i = 0; i < n; i++)
     {
      hi = MathMax(hi, r[i].high);
      lo = MathMin(lo, r[i].low);
     }
   ENUM_ORDER_TYPE ty = (dir == 1) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double fav = (dir == 1) ? hi - opx : opx - lo, adv = (dir == 1) ? opx - lo : hi - opx;
   double mfe = 0, mae = 0, p1 = 0;
   if(OrderCalcProfit(ty, _Symbol, vol, opx, opx + dir * fav, p1))
      mfe = MathMax(0.0, p1);
   if(OrderCalcProfit(ty, _Symbol, vol, opx, opx - dir * adv, p1))
      mae = MathMax(0.0, -p1);
   int    e = EngByMagic(mg);
   string feat = "";
   for(int i = ArraySize(g_lgPid) - 1; i >= 0; i--)
      if(g_lgPid[i] == pid)
        {
         feat = g_lgFeat[i];
         break;
        }
   if(feat == "")
      for(int i = 1; i < LOG_FEAT_N; i++)
         feat += ",";
   string row = StringFormat("%s,%s,%I64u,%s,%s,%.2f,%s,%s,%.2f,%.1f,%s,%.2f,%.2f,",
                             TimeToString(ToWib(ct), TIME_DATE | TIME_SECONDS), TimeToString(ToWib(ot), TIME_DATE | TIME_SECONDS), pid,
                             (e >= 0 ? g_eng[e].id : "?"), dir == 1 ? "BUY" : "SELL", vol, DoubleToString(opx, _Digits), DoubleToString(cpx, _Digits),
                             pl, (double)(ct - ot) / 60.0, ReasonStr(rsn), mfe, mae) + feat;
   AppendLine(LogFile("tradelog"), LOG_HDR, row);
  }

// tulis ulang seluruh riwayat posisi EA (dipanggil dari timer saat ada deal baru)
void HistoryWrite()
  {
   if(g_tester || !HistorySelect(0, TimeCurrent() + 86400))
      return;
   int n = HistoryDealsTotal();
   ulong    pid[];
   string   eng[];
   int      dr[];
   double   vol[], op[], cp[], pl[];
   datetime ot[], ct[];
   long     rs[];
   ArrayResize(pid, n); ArrayResize(eng, n); ArrayResize(dr, n); ArrayResize(vol, n); ArrayResize(op, n);
   ArrayResize(cp, n); ArrayResize(pl, n); ArrayResize(ot, n); ArrayResize(ct, n); ArrayResize(rs, n);
   int cnt = 0;
   for(int i = 0; i < n; i++)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0 || HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol)
         continue;
      int e = EngByMagic(HistoryDealGetInteger(tk, DEAL_MAGIC));
      if(e < 0)
         continue;
      ulong p = (ulong)HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      int   k = -1;
      for(int q = cnt - 1; q >= 0 && q >= cnt - 400; q--)
         if(pid[q] == p)
           {
            k = q;
            break;
           }
      if(k < 0)
        {
         k = cnt++;
         pid[k] = p; eng[k] = g_eng[e].id; dr[k] = 0; vol[k] = 0; op[k] = 0; cp[k] = 0; pl[k] = 0; ot[k] = 0; ct[k] = 0; rs[k] = 0;
        }
      pl[k] += HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_SWAP) + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      long en = HistoryDealGetInteger(tk, DEAL_ENTRY);
      if(en == DEAL_ENTRY_IN)
        {
         op[k]  = HistoryDealGetDouble(tk, DEAL_PRICE);
         ot[k]  = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
         vol[k] = HistoryDealGetDouble(tk, DEAL_VOLUME);
         dr[k]  = (HistoryDealGetInteger(tk, DEAL_TYPE) == DEAL_TYPE_BUY) ? 1 : -1;
        }
      else if(en == DEAL_ENTRY_OUT || en == DEAL_ENTRY_OUT_BY)
        {
         cp[k] = HistoryDealGetDouble(tk, DEAL_PRICE);
         ct[k] = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
         rs[k] = HistoryDealGetInteger(tk, DEAL_REASON);
        }
     }
   string s = HIST_HDR + "\r\n";
   for(int k = 0; k < cnt; k++)
     {
      if(ot[k] == 0 || ct[k] == 0 || PositionSelectByTicket(pid[k]))
         continue;
      s += StringFormat("%s,%s,%I64u,%s,%s,%.2f,%s,%s,%.2f,%.1f,%s\r\n",
                        TimeToString(ToWib(ct[k]), TIME_DATE | TIME_SECONDS), TimeToString(ToWib(ot[k]), TIME_DATE | TIME_SECONDS), pid[k],
                        eng[k], dr[k] == 1 ? "BUY" : "SELL", vol[k], DoubleToString(op[k], _Digits), DoubleToString(cp[k], _Digits),
                        pl[k], (double)(ct[k] - ot[k]) / 60.0, ReasonStr(rs[k]));
     }
   int h = FileOpen("MTRB_Pro_history.csv", FILE_WRITE | FILE_BIN | FILE_COMMON | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
      return;
   FileBytes(h, s);
   FileClose(h);
  }

void HistoryFlush()
  {
   if(!g_histDirty)
      return;
   g_histDirty = false;
   HistoryWrite();
  }

// dipanggil tiap detik dari OnTimer (hanya saat live)
void DashTick()
  {
   g_dashCount++;
   if(g_dashCount % 2 != 0)
      return;
   PortfolioDayCheck();
   DashReadControl();
   if(g_statsDirty || TimeCurrent() - g_statsAt >= 60)
      DashStats();
   HistoryFlush();
   DashWriteStatus();
  }

//+------------------------------------------------------------------+
//| Strategi RSI + Moving Average                                    |
//| Garis sinyal = RSI yang dihaluskan WMA. Di atas 50 -> hanya buy, |
//| di bawah 50 -> hanya sell. Entry pada candle pertama dalam       |
//| episode itu yang menutup di sisi MA dan searah. SL di swing.     |
//+------------------------------------------------------------------+
void StrategyRSM()
  {
   if(!g_enRSM)
      return;
   datetime bar = iTime(_Symbol, InpRsmTF, 0);
   if(bar <= 0 || bar == g_rsmBar)
      return;
   g_rsmBar = bar;
   long mg = InpMagic + 106;

   double sg = Val(g_hRsmSig, 0, 1), ma = Val(g_hRsmMa, 0, 1);
   if(sg == EMPTY_VALUE || ma == EMPTY_VALUE)
     {
      g_rsmStatus = "WAIT: data belum siap";
      return;
     }
   int side = (sg > 50.0) ? 1 : (sg < 50.0) ? -1 : 0;
   if(g_rsmFirst)
     {
      // EA baru dipasang di tengah episode: kalau kesempatan entry episode ini sudah lewat, jangan entry susulan
      g_rsmFirst = false;
      g_rsmEp = side;
      g_rsmTaken = false;
      for(int b = 2; b < 3000 && side != 0; b++)
        {
         double s2 = Val(g_hRsmSig, 0, b), m2 = Val(g_hRsmMa, 0, b);
         if(s2 == EMPTY_VALUE || m2 == EMPTY_VALUE)
            break;
         if(((s2 > 50.0) ? 1 : (s2 < 50.0) ? -1 : 0) != side)
            break;                                     // awal episode
         double o2 = iOpen(_Symbol, InpRsmTF, b), c2 = iClose(_Symbol, InpRsmTF, b);
         if((side == 1) ? (c2 > m2 && c2 > o2) : (c2 < m2 && c2 < o2))
           {
            g_rsmTaken = true;
            break;
           }
        }
     }
   if(side != g_rsmEp)
     {
      g_rsmEp = side;
      g_rsmTaken = false;
     }

   // posisi terbuka: keluar saat garis sinyal balik melewati 50
   bool hasPos = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != mg)
         continue;
      int pd = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      if(InpRsmExitOnFlip && side != 0 && side != pd)
        {
         trade.PositionClose(tk);
         g_rsmStatus = "Keluar: garis sinyal balik";
        }
      else
        {
         hasPos = true;
         g_rsmStatus = "Posisi aktif";
        }
     }
   if(side == 0)
      return;

   double o = iOpen(_Symbol, InpRsmTF, 1), c = iClose(_Symbol, InpRsmTF, 1);
   bool sig = (side == 1) ? (c > ma && c > o) : (c < ma && c < o);
   if(g_rsmTaken || !sig)
     {
      if(!hasPos)
         g_rsmStatus = g_rsmTaken ? StringFormat("Arah %s, jatah entry terpakai", side == 1 ? "naik" : "turun")
                                  : StringFormat("Arah %s, tunggu tutup %s MA %.2f", side == 1 ? "naik" : "turun", side == 1 ? ">" : "<", ma);
      return;
     }
   g_rsmTaken = true;                      // satu kesempatan per episode, diambil atau tidak
   if(hasPos)
      return;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string why = "";
   if(IsWeekend() || dt.hour < InpRsmHourFrom || dt.hour >= InpRsmHourTo || ask - bid > InpRsmMaxSpread || NewsBlocked(why))
     {
      g_rsmStatus = "Sinyal dilewati (jam / spread / news)";
      return;
     }
   int    ih = iHighest(_Symbol, InpRsmTF, MODE_HIGH, InpRsmSwing, 1);
   int    il = iLowest(_Symbol, InpRsmTF, MODE_LOW, InpRsmSwing, 1);
   if(ih < 0 || il < 0)
      return;
   double price  = (side == 1) ? ask : bid;
   double stopPx = (side == 1) ? iLow(_Symbol, InpRsmTF, il) - InpRsmSLBuf : iHigh(_Symbol, InpRsmTF, ih) + InpRsmSLBuf + (ask - bid);
   double slDist = side * (price - stopPx);
   if(slDist < MathMax(InpRsmMinSL, MinStopDist()))
     {
      g_rsmStatus = "SL terlalu rapat, dilewati";
      return;
     }
   g_rsmStatus = OpenStrategy(mg, side, slDist, InpRsmRR, "MTRB RSM");
  }

//+------------------------------------------------------------------+
//| Strategi scalping koreksi searah tren                            |
//| Tren besar naik + pasar ramai + N candle merah berturut-turut    |
//| -> beli (cerminnya untuk jual). SL = ATR, TP = kelipatan SL,     |
//| posisi ditutup paling lambat InpDipMaxMin menit.                 |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Strategi pola candle + RSI                                       |
//| Sell: Dark Cloud Cover / Hanging Man saat RSI tinggi             |
//| Buy : Piercing Line / Hammer saat RSI rendah                     |
//| Keluar: SL/TP, RSI memotong 30/70, atau batas jumlah candle      |
//+------------------------------------------------------------------+
void StrategyCDL()
  {
   if(!g_enCDL)
      return;
   datetime bar = iTime(_Symbol, InpCdlTF, 0);
   if(bar <= 0 || bar == g_cdlBar)
      return;
   g_cdlBar = bar;
   long mg = InpMagic + 108;

   int nb = MathMax(2, InpCdlBodyPeriod);
   MqlRates r[];
   ArraySetAsSeries(r, true);
   double rsi1 = Val(g_hCdlRsi, 0, 1), rsi2 = Val(g_hCdlRsi, 0, 2), ma2 = Val(g_hCdlMa, 0, 2);
   if(CopyRates(_Symbol, InpCdlTF, 0, nb + 3, r) < nb + 3 || rsi1 == EMPTY_VALUE || rsi2 == EMPTY_VALUE || ma2 == EMPTY_VALUE)
     {
      g_cdlStatus = "WAIT: data belum siap";
      return;
     }

   // posisi terbuka: keluar lewat RSI atau batas waktu
   bool hasPos = false;
   bool exitLong  = ((rsi1 < 70 && rsi2 > 70) || (rsi1 < 30 && rsi2 > 30));
   bool exitShort = ((rsi1 > 30 && rsi2 < 30) || (rsi1 > 70 && rsi2 < 70));
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != mg)
         continue;
      bool buy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
      bool old = (InpCdlMaxBars > 0 && TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) >= InpCdlMaxBars * PeriodSeconds(InpCdlTF));
      if(old || (InpCdlExitRsi && (buy ? exitLong : exitShort)))
        {
         if(trade.PositionClose(tk))
           {
            g_cdlStatus = old ? "Keluar: batas waktu" : "Keluar: RSI memotong 30/70";
            continue;
           }
        }
      hasPos = true;
     }
   if(hasPos)
     {
      g_cdlStatus = "Posisi aktif";
      return;
     }

   double avg = 0;
   for(int i = 1; i <= nb; i++)
      avg += MathAbs(r[i].open - r[i].close);
   avg /= nb;
   double o1 = r[1].open, c1 = r[1].close, h1 = r[1].high, l1 = r[1].low;
   double o2 = r[2].open, c2 = r[2].close, h2 = r[2].high, l2 = r[2].low;
   double midOC2 = (o2 + c2) / 2.0, mid1 = (h1 + l1) / 2.0;
   int    d = 0;
   string pat = "";
   if(InpCdlDarkPierce)
     {
      // Dark Cloud Cover: candle naik panjang, lalu buka di atas high-nya dan tutup turun di dalam badannya
      if(c2 - o2 > avg && c1 < c2 && c1 > o2 && midOC2 > ma2 && o1 > h2)
        {
         d = -1; pat = "Dark Cloud Cover";
        }
      // Piercing Line: candle turun panjang, lalu buka di bawah low-nya dan tutup naik panjang di dalam badannya
      else if(c1 - o1 > avg && o2 - c2 > avg && c1 > c2 && c1 < o2 && midOC2 < ma2 && o1 < l2)
        {
         d = 1; pat = "Piercing Line";
        }
     }
   if(d == 0 && InpCdlHangHammer)
     {
      bool upper = (MathMin(o1, c1) > h1 - (h1 - l1) / 3.0);      // badan di sepertiga atas candle
      if(upper && mid1 > ma2 && c1 > c2 && o1 > o2)
        {
         d = -1; pat = "Hanging Man";
        }
      else if(upper && mid1 < ma2 && c1 < c2 && o1 < o2)
        {
         d = 1; pat = "Hammer";
        }
     }
   if(d == 0)
     {
      g_cdlStatus = StringFormat("Tunggu pola candle (RSI %.0f)", rsi1);
      return;
     }
   if((d == 1 && rsi1 >= InpCdlRsiBuy) || (d == -1 && rsi1 <= InpCdlRsiSell))
     {
      g_cdlStatus = StringFormat("%s, RSI %.0f belum konfirmasi", pat, rsi1);
      return;
     }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string why = "";
   if(IsWeekend() || ask - bid > InpCdlMaxSpread || NewsBlocked(why))
     {
      g_cdlStatus = pat + ": sinyal dilewati (spread / news)";
      return;
     }
   double slDist = MathMax(InpCdlSL, MinStopDist());
   g_cdlStatus = OpenStrategy(mg, d, slDist, (InpCdlTP > 0 ? InpCdlTP / slDist : 0), "MTRB CDL");
  }

//+------------------------------------------------------------------+
//| Strategi NadirAliOfficial                                        |
//| Porting "TRILLEX 10S BASIC" (mode Insane) karya Nadir Ali Khan,  |
//| lisensi MIT: github.com/NadirAliOfficial/trillex-10s-ea          |
//| 3 EMA + PSAR searah di M1 dan M5, lalu PSAR pada bar 10 detik    |
//| baru berbalik ke arah itu. Keluar saat PSAR 10 detik berbalik.   |
//+------------------------------------------------------------------+
void NaoEma(const double &p[], const int period, double &e[])
  {
   int n = ArraySize(p);
   ArrayResize(e, n);
   if(n <= 0 || period <= 0)
      return;
   double a = 2.0 / (period + 1.0);
   e[0] = p[0];
   for(int i = 1; i < n; i++)
      e[i] = a * p[i] + (1.0 - a) * e[i - 1];
  }

void NaoSar(const double &h[], const double &l[], const double &c[], const double step, const double maxAF, double &sar[])
  {
   int n = ArraySize(c);
   ArrayResize(sar, n);
   if(n <= 0)
      return;
   if(n == 1)
     {
      sar[0] = l[0];
      return;
     }
   bool   up = (c[1] >= c[0]);
   double af = step, ep = up ? MathMax(h[0], h[1]) : MathMin(l[0], l[1]);
   sar[0] = up ? l[0] : h[0];
   sar[1] = sar[0];
   for(int i = 2; i < n; i++)
     {
      sar[i] = sar[i - 1] + af * (ep - sar[i - 1]);
      if(up)
        {
         sar[i] = MathMin(sar[i], MathMin(l[i - 1], l[i - 2]));
         if(l[i] < sar[i])
           {
            up = false; sar[i] = ep; ep = l[i]; af = step;
           }
         else if(h[i] > ep)
           {
            ep = h[i]; af = MathMin(af + step, maxAF);
           }
        }
      else
        {
         sar[i] = MathMax(sar[i], MathMax(h[i - 1], h[i - 2]));
         if(h[i] > sar[i])
           {
            up = true; sar[i] = ep; ep = h[i]; af = step;
           }
         else if(l[i] < ep)
           {
            ep = l[i]; af = MathMin(af + step, maxAF);
           }
        }
     }
  }

// arah tren satu timeframe: k = 0 (M1) atau 1 (M5). 1 naik, -1 turun, 0 tidak jelas
int NaoTfTrend(const int k)
  {
   ENUM_TIMEFRAMES tf = (k == 0) ? PERIOD_M1 : PERIOD_M5;
   double ef = Val(g_hNaoE[k * 3], 0, 1), em = Val(g_hNaoE[k * 3 + 1], 0, 1), es = Val(g_hNaoE[k * 3 + 2], 0, 1), sar = Val(g_hNaoSar[k], 0, 1);
   double c = iClose(_Symbol, tf, 1);
   if(ef == EMPTY_VALUE || em == EMPTY_VALUE || es == EMPTY_VALUE || sar == EMPTY_VALUE || c <= 0)
      return 0;
   if(ef > em && em > es && sar < c)
      return 1;
   if(ef < em && em < es && sar > c)
      return -1;
   return 0;
  }

void StrategyNAO()
  {
   // bar 10 detik dari harga tengah selalu dibangun, supaya mesin siap saat dinyalakan
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk))
      return;
   double   mid = (tk.bid + tk.ask) * 0.5;
   datetime bucket = (datetime)(tk.time - (tk.time % 10));
   bool     closed = false;
   if(g_naoT == 0)
     {
      g_naoT = bucket; g_naoCurH = mid; g_naoCurL = mid; g_naoCurC = mid;
     }
   else if(bucket == g_naoT)
     {
      g_naoCurH = MathMax(g_naoCurH, mid); g_naoCurL = MathMin(g_naoCurL, mid); g_naoCurC = mid;
     }
   else if(bucket > g_naoT)
     {
      int sz = ArraySize(g_naoC);
      if(sz >= MathMax(100, InpNaoMaxBars))
        {
         ArrayRemove(g_naoH, 0, 1); ArrayRemove(g_naoL, 0, 1); ArrayRemove(g_naoC, 0, 1);
         sz--;
        }
      ArrayResize(g_naoH, sz + 1, 256); ArrayResize(g_naoL, sz + 1, 256); ArrayResize(g_naoC, sz + 1, 256);
      g_naoH[sz] = g_naoCurH; g_naoL[sz] = g_naoCurL; g_naoC[sz] = g_naoCurC;
      closed = true;
      g_naoT = bucket; g_naoCurH = mid; g_naoCurL = mid; g_naoCurC = mid;
     }
   if(!g_enNAO || !closed)
      return;

   long mg = InpMagic + 115;
   int  n = ArraySize(g_naoC), cur = n - 1;
   int  conf = MathMax(0, InpNaoConfirmBars);
   int  need = MathMax(InpNaoSlowEma + 10 + conf, 25 + conf) + 1;
   if(n < 6)
     {
      g_naoStatus = StringFormat("Mengumpulkan bar 10 detik (%d/%d)", n, need);
      return;
     }
   double eF[], eM[], eS[], sar[];
   NaoEma(g_naoC, InpNaoFastEma, eF);
   NaoEma(g_naoC, InpNaoMidEma, eM);
   NaoEma(g_naoC, InpNaoSlowEma, eS);
   NaoSar(g_naoH, g_naoL, g_naoC, InpNaoSarStep, InpNaoSarMax, sar);

   // posisi terbuka: keluar saat bar 10 detik berbalik
   int posDir = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ptk = PositionGetTicket(i);
      if(ptk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != mg)
         continue;
      int  pd = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      bool out = (InpNaoExitMode == 0) ? (pd == 1 ? sar[cur] > g_naoC[cur] : sar[cur] < g_naoC[cur])
                                       : (pd == 1 ? g_naoC[cur] < eF[cur] : g_naoC[cur] > eF[cur]);
      if(out && trade.PositionClose(ptk))
        {
         g_naoStatus = (InpNaoExitMode == 0) ? "Keluar: PSAR 10 detik berbalik" : "Keluar: tutup melewati EMA cepat";
         continue;
        }
      posDir = pd;
     }
   if(n < need)
     {
      if(posDir == 0)
         g_naoStatus = StringFormat("Mengumpulkan bar 10 detik (%d/%d)", n, need);
      return;
     }

   // arah dasar: M1 (dan M5) searah
   int base = NaoTfTrend(0);
   if(base != 0 && InpNaoRequireM5 && NaoTfTrend(1) != base)
      base = 0;
   if(base == 0)
     {
      g_naoStatus = (posDir != 0) ? "Posisi aktif" : "Tunggu M1 dan M5 searah";
      return;
     }

   // PSAR 10 detik baru berbalik dan bertahan, EMA 10 detik searah
   int  flip = cur - conf, prev = flip - 1, sig = 0;
   bool pBelow = (sar[prev] < g_naoC[prev]), fBelow = (sar[flip] < g_naoC[flip]);
   if(pBelow != fBelow)
     {
      bool held = true;
      for(int j = flip; j <= cur; j++)
         if((sar[j] < g_naoC[j]) != fBelow)
            held = false;
      if(held && fBelow && eF[cur] > eM[cur] && eM[cur] > eS[cur])
         sig = 1;
      if(held && !fBelow && eF[cur] < eM[cur] && eM[cur] < eS[cur])
         sig = -1;
     }
   if(sig == 0 || sig != base)
     {
      g_naoStatus = (posDir != 0) ? "Posisi aktif" : StringFormat("Arah %s, tunggu PSAR 10 detik berbalik", base == 1 ? "naik" : "turun");
      return;
     }
   if(posDir != 0)
     {
      if(posDir != base)
        {
         CloseMagic(mg);
         g_naoStatus = "Keluar: sinyal berlawanan";
        }
      else
         g_naoStatus = "Posisi aktif";
      return;
     }

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   string why = "";
   if(IsWeekend() || dt.hour < InpNaoHourFrom || dt.hour >= InpNaoHourTo)
     {
      g_naoStatus = StringFormat("Sinyal di luar jam %02d-%02d", InpNaoHourFrom, InpNaoHourTo);
      return;
     }
   if(tk.ask - tk.bid > InpNaoMaxSpread || NewsBlocked(why))
     {
      g_naoStatus = "Sinyal dilewati (spread / news)";
      return;
     }
   double slDist = MathMax(InpNaoSL, MinStopDist());
   g_naoStatus = OpenStrategy(mg, base, slDist, (InpNaoTP > 0 ? InpNaoTP / slDist : 0), "MTRB NAO");
  }

void StrategyDIP()
  {
   if(!g_enDIP)
      return;
   long mg = InpMagic + 107;

   // batas waktu: scalping tidak menahan posisi lama
   if(InpDipMaxMin > 0)
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong tk = PositionGetTicket(i);
         if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != mg)
            continue;
         if(TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) >= InpDipMaxMin * 60)
           {
            trade.PositionClose(tk);
            g_dipStatus = "Keluar: batas waktu";
           }
        }

   datetime bar = iTime(_Symbol, InpDipTF, 0);
   if(bar <= 0 || bar == g_dipBar)
      return;
   g_dipBar = bar;
   if(CountPosMagic(mg) > 0)
     {
      g_dipStatus = "Posisi aktif";
      return;
     }

   int n = MathMax(1, m_dipCandles);
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, InpDipTF, 0, n + 3, r) < n + 2)
      return;
   double ema = Val(g_hDipEma, 0, 1), atr = Val(g_hDipAtr, 0, 1);
   if(ema == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0)
     {
      g_dipStatus = "WAIT: data belum siap";
      return;
     }
   int trend = (r[1].close > ema) ? 1 : (r[1].close < ema) ? -1 : 0;

   // pasar ramai: ATR sekarang dibanding median ATR beberapa hari terakhir
   double a[];
   int    got = CopyBuffer(g_hDipAtr, 0, 1, InpDipVolBars, a);
   bool   hot = false;
   if(got >= 288)
     {
      ArraySort(a);
      hot = (atr > m_dipVolMult * a[got / 2]);
     }

   bool allDn = true, allUp = true;
   for(int q = 1; q <= n; q++)
     {
      if(!(r[q].close < r[q].open))
         allDn = false;
      if(!(r[q].close > r[q].open))
         allUp = false;
     }
   int d = 0;
   if(allDn && !(r[n + 1].close < r[n + 1].open))
      d = 1;                                // N candle merah (baru terbentuk) -> beli
   else
      if(allUp && !(r[n + 1].close > r[n + 1].open))
         d = -1;                            // N candle hijau -> jual

   if(d == 0)
     {
      g_dipStatus = StringFormat("Tren %s, pasar %s, tunggu %d candle %s", trend == 1 ? "naik" : trend == -1 ? "turun" : "-",
                                 hot ? "ramai" : "tenang", n, trend == 1 ? "merah" : "hijau");
      return;
     }
   if(trend != d)
     {
      g_dipStatus = "Koreksi melawan tren, dilewati";
      return;
     }
   if(!hot)
     {
      g_dipStatus = "Sinyal ada, pasar tenang: dilewati";
      return;
     }
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string why = "";
   if(IsWeekend() || dt.hour < InpDipHourFrom || dt.hour >= m_dipHourTo || ask - bid > InpDipMaxSpread || NewsBlocked(why))
     {
      g_dipStatus = "Sinyal dilewati (jam / spread / news)";
      return;
     }
   double slDist = MathMax(MathMin(atr * InpDipSLAtr, InpDipMaxSL), MathMax(InpDipMinSL, MinStopDist()));
   g_dipStatus = OpenStrategy(mg, d, slDist, InpDipTP, "MTRB DIP");
  }

//+------------------------------------------------------------------+
//| Strategi Range Hybrid (mean reversion) - versi optimasi          |
//| Range = high/low N candle sebelum candle sinyal. Skor kualitas   |
//| range (0-100) memilih mode: STRICT (ketat), DETAIL (longgar),    |
//| atau OFF. Entry saat candle menyentuh tepi range lalu ditolak;   |
//| SL di luar range + buffer. STRICT: TP di tepi seberang.          |
//| DETAIL: target pertama tengah range (tutup sebagian), sisanya    |
//| trailing. Semua angka jarak dikali InpRhScale.                   |
//+------------------------------------------------------------------+
datetime g_rhCoolUntil = 0;     // tidak entry baru sampai waktu ini (setelah partial)
int      g_rhAge = 0;           // umur range: candle sejak high/low range terakhir berubah

double RhScale() { return (InpRhScale > 0) ? InpRhScale : 1.0; }

double g_rhAtr = 0;             // ATR(14) candle terakhir
double g_rhAtrRise = 0;         // ATR sekarang / ATR InpRhAtrRiseBars candle lalu

// batas lebar range: dari ATR (adaptif) atau angka tetap
double RhMinW(const bool strict)
  {
   if(InpRhAdaptive && g_rhAtr > 0)
     {
      double k = (strict && InpMinWidthDetail > 0 && InpMinWidthStrict > InpMinWidthDetail) ? InpMinWidthStrict / InpMinWidthDetail : 1.0;
      return g_rhAtr * m_rhAtrMin * k;
     }
   return (strict ? InpMinWidthStrict : InpMinWidthDetail) * RhScale();
  }

double RhOffW()
  {
   if(InpRhAdaptive && g_rhAtr > 0)
      return g_rhAtr * InpRhAtrOffMult;
   return InpRhForceOffWidth * RhScale();
  }

string RhModeName(const RH_MODE m) { return (m == RH_STRICT) ? "STRICT" : (m == RH_DETAIL) ? "DETAIL" : "OFF"; }

// hitung range, skor, dan mode dari bar tertutup; r[] urutan series (r[1] = candle sinyal)
bool RhEvaluate(const MqlRates &r[], const int L)
  {
   double sc = RhScale(), buf = InpTouchBuffer * sc;
   double hi = -DBL_MAX, lo = DBL_MAX;
   int    iHi = L + 1, iLo = L + 1;
   for(int i = L + 1; i >= 2; i--)                 // dari yang lama ke yang baru
     {
      if(r[i].high >= hi)
        {
         hi = r[i].high;
         iHi = i;
        }
      if(r[i].low <= lo)
        {
         lo = r[i].low;
         iLo = i;
        }
     }
   g_rhAge = MathMin(iHi, iLo) - 1;                // kedua tepi sudah bertahan minimal sebanyak ini
   double adx = Val(g_hRhAdx, 0, 1);
   if(adx == EMPTY_VALUE || adx <= 0)
      return false;
   g_rh.hi = hi; g_rh.lo = lo; g_rh.width = hi - lo; g_rh.adx = adx;
   double width = g_rh.width;
   int score = 0;

   // ATR: nilai sekarang, kestabilan, dan kenaikannya
   double a14[];
   int    got = CopyBuffer(g_hRhAtr, 0, 1, L, a14);     // a14[got-1] = candle terakhir yang tutup
   g_rh.atrStable = false;
   g_rhAtr = 0; g_rhAtrRise = 0;
   if(got == L)
     {
      double sum = 0;
      for(int i = 0; i < got; i++)
         sum += a14[i];
      double avg = sum / got, now = a14[got - 1];
      g_rh.atrStable = (avg > 0 && now >= 0.75 * avg && now <= 1.25 * avg);
      g_rhAtr = now;
      int k = got - 1 - MathMax(1, InpRhAtrRiseBars);
      if(k >= 0 && a14[k] > 0)
         g_rhAtrRise = now / a14[k];
     }
   if(InpRhAdaptive && g_rhAtr <= 0)
      return false;
   double wMinD = RhMinW(false), wMinS = RhMinW(true), wOff = RhOffW();

   // 1. ADX (bobot tinggi)
   if(adx < 17.0)
      score += 30;
   else if(adx < 19.0)
      score += 22;
   else if(adx < 21.5)
      score += 12;
   else if(adx < 23.5)
      score += 5;

   // 2. lebar range
   if(width >= wMinS && width <= 0.85 * wOff)
      score += 20;
   else if(width >= wMinD && width <= wOff)
      score += 11;

   // 3. jumlah sentuhan (candle berurutan yang sama-sama menyentuh dihitung satu)
   int  tH = 0, tL = 0;
   bool pH = false, pL = false;
   for(int i = L + 1; i >= 2; i--)
     {
      bool a = (r[i].high >= hi - buf), b = (r[i].low <= lo + buf);
      if(a && !pH)
         tH++;
      if(b && !pL)
         tL++;
      pH = a; pL = b;
     }
   g_rh.touchHi = tH; g_rh.touchLo = tL;
   if(tH >= 3 && tL >= 3)
      score += 22;
   else if(tH >= 2 && tL >= 2)
      score += 13;
   else if(tH >= 1 && tL >= 1)
      score += 5;

   // 4. false break (lebih dihukum): candle menembus high/low sebelumnya tapi menutup kembali di dalam
   int    fb = 0;
   double rH = r[L + 1].high, rL = r[L + 1].low;
   for(int i = L; i >= 2; i--)
     {
      if(r[i].high > rH + buf && r[i].close < rH)
         fb++;
      if(r[i].low < rL - buf && r[i].close > rL)
         fb++;
      rH = MathMax(rH, r[i].high);
      rL = MathMin(rL, r[i].low);
     }
   g_rh.falseBrk = fb;
   if(fb == 0)
      score += 18;
   else if(fb <= 1)
      score += 10;
   else if(fb <= 2)
      score += 4;

   // 5. ATR stabil: ATR sekarang dalam 25% dari rata-rata ATR sepanjang range
   if(g_rh.atrStable)
      score += 10;
   g_rh.score = score;

   // mode
   if(adx >= m_rhAdxDetail || width < wMinD || width > wOff)
      g_rh.mode = RH_OFF;
   else if(score >= 75 && adx < InpAdxStrict && width >= wMinS)
      g_rh.mode = RH_STRICT;
   else if(score >= m_rhScoreDetail)
      g_rh.mode = RH_DETAIL;
   else
      g_rh.mode = RH_OFF;
   return true;
  }

string RhInfo()
  {
   return StringFormat("skor %d | range %.2f-%.2f (lebar %.2f, boleh %.2f-%.2f, umur %d) | sentuh H%d/L%d | ADX %.1f | ATR %.2f",
                       g_rh.score, g_rh.lo, g_rh.hi, g_rh.width, RhMinW(false), RhOffW(), g_rhAge, g_rh.touchHi, g_rh.touchLo, g_rh.adx, g_rhAtr);
  }

// jumlah entry hari ini, loss beruntun terakhir, dan waktu loss terakhir (dihitung per posisi)
void RhHistory(int &nToday, int &streak, datetime &lastLoss)
  {
   nToday = 0; streak = 0; lastLoss = 0;
   if(!HistorySelect(TimeCurrent() - 7 * 86400, TimeCurrent() + 3600))
      return;
   long     ids[];
   double   net[];
   datetime tcl[];
   int      n = 0;
   datetime d0 = DayStart();
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0 || HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol || HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagicRange)
         continue;
      long     e = HistoryDealGetInteger(tk, DEAL_ENTRY);
      datetime t = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      if(e == DEAL_ENTRY_IN)
        {
         if(t >= d0)
            nToday++;
         continue;
        }
      if(e != DEAL_ENTRY_OUT && e != DEAL_ENTRY_OUT_BY)
         continue;
      long   pid = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      double p = HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_SWAP) + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      int    k = -1;
      for(int j = 0; j < n; j++)
         if(ids[j] == pid)
           {
            k = j;
            break;
           }
      if(k < 0)
        {
         k = n++;
         ArrayResize(ids, n); ArrayResize(net, n); ArrayResize(tcl, n);
         ids[k] = pid; net[k] = 0;
        }
      net[k] += p; tcl[k] = t;
     }
   for(int k = n - 1; k >= 0; k--)
     {
      if(net[k] >= 0)
         break;
      streak++;
      if(lastLoss == 0)
         lastLoss = tcl[k];
     }
  }

// kelola posisi.
// DETAIL: di tengah range tutup sebagian (atau semua bila lot tidak bisa dibagi), sisanya SL ke BE lalu trailing.
// STRICT: SL ke breakeven + sedikit setelah sebagian jarak ke TP ditempuh.
// Titik tengah range dan tanda "sudah partial" disimpan di global variable terminal supaya tahan restart.
void RhManage()
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT), minD = MinStopDist(), sc = RhScale();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagicRange)
         continue;
      int    dir  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN), sl = PositionGetDouble(POSITION_SL), tp = PositionGetDouble(POSITION_TP);
      double vol  = PositionGetDouble(POSITION_VOLUME), px = (dir == 1) ? bid : ask;
      bool   detail = (StringFind(PositionGetString(POSITION_COMMENT), "RHD") >= 0);
      bool   atBE   = (sl > 0 && dir * (sl - open) >= -pt / 2);
      double newSL  = sl;

      if(detail)
        {
         string kM = "MTRB_RH_mid_" + IntegerToString((long)tk), kP = "MTRB_RH_part_" + IntegerToString((long)tk);
         double mid = GlobalVariableCheck(kM) ? GlobalVariableGet(kM) : (tp > 0 ? (open + tp) * 0.5 : open);
         bool   parted = GlobalVariableCheck(kP);
         double dm = dir * (mid - open);
         double prog = (dm > 0) ? dir * (px - open) / dm : 0;      // 0 = entry, 1 = tengah range
         if(!parted && !atBE && prog >= 0.92)
           {
            double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
            double part = (step > 0) ? MathFloor(vol * InpPartialPercent / 100.0 / step + 1e-9) * step : 0;
            part = NormalizeDouble(part, 2);
            if(InpUsePartialDetail && part >= vmin && vol - part >= vmin - 1e-9)
              {
               if(trade.PositionClosePartial(tk, part))
                 {
                  GlobalVariableSet(kP, (double)TimeCurrent());
                  parted = true;
                  g_rhCoolUntil = iTime(_Symbol, InpRangeTF, 0) + InpRhPartialCooldown * PeriodSeconds(InpRangeTF);
                 }
              }
            else
              {
               // lot tidak bisa dibagi (atau partial dimatikan): target pertama = tengah range, tutup semua
               if(trade.PositionClose(tk))
                  g_rhStatus = "Keluar di tengah range";
               continue;
              }
           }
         if(parted || atBE)
           {
            double be = open + dir * 0.12 * sc, tr = px - dir * InpTrailPoints * pt * sc;
            if(sl == 0 || dir * (be - sl) > 0)
               newSL = be;
            if(dir * (tr - newSL) > 5 * pt)
               newSL = tr;
           }
        }
      else
        {
         double total = dir * (tp - open);
         if(tp <= 0 || total <= 0)
            continue;
         if(!atBE && InpRhStrictBEAt > 0 && dir * (px - open) / total >= InpRhStrictBEAt)
            newSL = open + dir * 0.15 * sc;
        }

      newSL = NormPrice(newSL);
      if(newSL == sl || newSL <= 0 || dir * (px - newSL) < minD)
         continue;
      if(sl > 0 && dir * (newSL - sl) <= 0)
         continue;
      trade.PositionModify(tk, newSL, tp);
     }
  }

void StrategyRH()
  {
   if(!g_enRH)
      return;
   long mg = InpMagicRange;
   RhManage();

   datetime bar = iTime(_Symbol, InpRangeTF, 0);
   if(bar <= 0 || bar == g_rhBar)
      return;
   g_rhBar = bar;

   int L = MathMax(8, InpRhLookback);
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, InpRangeTF, 0, L + 5, r) < L + 3 || !RhEvaluate(r, L))
     {
      g_rhStatus = "WAIT: data belum siap";
      return;
     }
   double sc = RhScale();

   // range tiba-tiba melebar -> Off sementara
   if(g_rhPrevWidth > 0 && g_rhPrevWidth <= RhOffW() && g_rh.width > RhOffW() && InpRhForceOffMin > 0)
      g_rhOffUntil = TimeCurrent() + InpRhForceOffMin * 60;
   g_rhPrevWidth = g_rh.width;
   if(TimeCurrent() < g_rhOffUntil)
      g_rh.mode = RH_OFF;

   string info = RhInfo();
   if(CountPosMagic(mg) > 0)
     {
      g_rhStatus = "Posisi aktif | " + RhModeName(g_rh.mode) + " | " + info;
      return;
     }
   GlobalVariablesDeleteAll("MTRB_RH_");            // tidak ada posisi: buang catatan posisi lama
   if(TimeCurrent() < g_rhOffUntil)
     {
      g_rhStatus = "OFF (range melebar, jeda sampai " + TimeToString(g_rhOffUntil, TIME_MINUTES) + ") | " + info;
      return;
     }
   if(TimeCurrent() < g_rhCoolUntil)
     {
      g_rhStatus = "Cooldown setelah partial | " + info;
      return;
     }
   g_rhStatus = RhModeName(g_rh.mode) + " | " + info;
   if(g_rh.mode == RH_OFF)
      return;

   // filter sesi
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(InpSessionSplit)
     {
      // pemisahan sesi aktif: Range Hybrid hanya di sesi Asia, jam InpRhSession* tidak dipakai
      if(IsWeekend() || SessionNow() != 0)
        {
         g_rhStatus += " | khusus sesi Asia";
         return;
        }
     }
   else if(IsWeekend() || dt.hour < InpRhSessionStart || dt.hour >= InpRhSessionEnd)
     {
      g_rhStatus += StringFormat(" | di luar jam %02d-%02d", InpRhSessionStart, InpRhSessionEnd);
      return;
     }
   // filter jumlah sentuhan
   if(m_rhMinTouch > 0 && (g_rh.touchHi < m_rhMinTouch || g_rh.touchLo < m_rhMinTouch))
     {
      g_rhStatus += StringFormat(" | sentuhan kurang (perlu %d atas + %d bawah)", m_rhMinTouch, m_rhMinTouch);
      return;
     }
   // filter ATR naik tajam
   if(InpRhAtrRiseMax > 0 && g_rhAtrRise > InpRhAtrRiseMax)
     {
      g_rhStatus += StringFormat(" | ATR naik tajam (x%.2f)", g_rhAtrRise);
      return;
     }
   // filter umur range
   if(g_rhAge < InpRhMinRangeAge)
     {
      g_rhStatus += StringFormat(" | range masih muda (%d < %d candle)", g_rhAge, InpRhMinRangeAge);
      return;
     }

   // sinyal pada candle yang baru menutup
   bool   strict = (g_rh.mode == RH_STRICT);
   double buf = InpTouchBuffer * sc;
   double o = r[1].open, h = r[1].high, l = r[1].low, c = r[1].close;
   double body = MathAbs(c - o), rng = h - l, upW = h - MathMax(o, c), loW = MathMin(o, c) - l;
   bool   inside = (c < g_rh.hi && c > g_rh.lo);
   bool   tHi = (h >= g_rh.hi - buf), tLo = (l <= g_rh.lo + buf);
   if(!inside || tHi == tLo)
     {
      g_rhStatus += (tHi || tLo) ? " | sentuh tepi tapi belum valid" : " | tunggu harga ke tepi range";
      return;
     }
   double rsi = Val(g_hRhRsi, 0, 1);
   if(rsi == EMPTY_VALUE)
      return;
   bool engS = (c < o && r[2].close > r[2].open && c <= r[2].open && o >= r[2].close);
   bool engB = (c > o && r[2].close < r[2].open && c >= r[2].open && o <= r[2].close);
   int  d = 0;
   if(strict)
     {
      bool pinS = (rng > 0 && upW >= 2.2 * body && upW >= 0.55 * rng), pinB = (rng > 0 && loW >= 2.2 * body && loW >= 0.55 * rng);
      bool big = (body >= 0.25 * sc);
      if(tHi && rsi >= 70.0 && (pinS || (engS && big)))
         d = -1;
      if(tLo && rsi <= 30.0 && (pinB || (engB && big)))
         d = 1;
     }
   else
     {
      bool pinS = (rng > 0 && upW >= m_rhPinBody * body && upW >= m_rhPinRng * rng), pinB = (rng > 0 && loW >= m_rhPinBody * body && loW >= m_rhPinRng * rng);
      if(tHi && rsi >= m_rhRsiHi && (pinS || engS))
         d = -1;
      if(tLo && rsi <= m_rhRsiLo && (pinB || engB))
         d = 1;
     }
   if(d == 0)
     {
      g_rhStatus += StringFormat(" | belum ada rejection valid (RSI %.0f)", rsi);
      return;
     }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double price = (d == 1) ? ask : bid;
   double mid = (g_rh.hi + g_rh.lo) * 0.5;
   if(MathAbs(price - mid) < m_rhMinDistMid * sc)
     {
      g_rhStatus += " | sinyal dilewati: terlalu dekat ke tengah range";
      return;
     }
   if(ask - bid > InpRhMaxSpread)
     {
      g_rhStatus += StringFormat(" | sinyal dilewati: spread %.2f > %.2f", ask - bid, InpRhMaxSpread);
      return;
     }
   string why = "";
   if(NewsBlocked(why))
     {
      g_rhStatus += " | sinyal dilewati: news";
      return;
     }
   int      nToday = 0, streak = 0;
   datetime lastLoss = 0;
   RhHistory(nToday, streak, lastLoss);
   int maxT = strict ? InpMaxTradeStrict : m_rhMaxDetail;
   if(maxT > 0 && nToday >= maxT)
     {
      g_rhStatus += StringFormat(" | batas %d trade hari ini tercapai", maxT);
      return;
     }
   if(InpRhLossPause > 0 && streak >= InpRhLossPause && TimeCurrent() < lastLoss + InpRhLossPauseMin * 60)
     {
      g_rhStatus += StringFormat(" | jeda setelah %d loss beruntun sampai %s", streak, TimeToString(lastLoss + InpRhLossPauseMin * 60, TIME_MINUTES));
      return;
     }

   // SL di luar range + buffer. TP order di tepi seberang; pada DETAIL target pertama (tengah range) dikelola RhManage.
   double slBuf = (strict ? InpSLBufferStrict : InpSLBufferDetail) * sc;
   double slPx  = (d == 1) ? MathMin(g_rh.lo, l) - slBuf : MathMax(g_rh.hi, h) + slBuf;
   double tpPx  = (d == 1) ? g_rh.hi : g_rh.lo + (ask - bid);
   double slDist = MathMax(d * (price - slPx), MinStopDist());
   if(d * ((strict ? tpPx : mid) - price) < MinStopDist())
     {
      g_rhStatus += " | sinyal dilewati: target terlalu dekat";
      return;
     }
   double lot = InpLot;
   if(InpRhUseRisk)
     {
      double per = 0;
      ENUM_ORDER_TYPE ty = (d == 1) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(OrderCalcProfit(ty, _Symbol, 1.0, price, price - d * slDist, per) && per < 0)
         lot = AccountInfoDouble(ACCOUNT_BALANCE) * (strict ? InpRiskStrict : InpRiskDetail) / 100.0 / (-per);
     }
   if(InpRhMaxLot > 0)
      lot = MathMin(lot, InpRhMaxLot);
   lot = MathMax(lot, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
   string res = OpenStrategy(mg, d, slDist, 0, strict ? "MTRB RHS" : "MTRB RHD", tpPx, lot);
   if(!strict && StringFind(res, "dibuka") >= 0)
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong tk = PositionGetTicket(i);
         if(tk != 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == mg)
            GlobalVariableSet("MTRB_RH_mid_" + IntegerToString((long)tk), mid);
        }
   g_rhStatus = res + " | " + RhModeName(g_rh.mode) + " | " + info;
  }

//--- pemicu entry untuk arah dir pada bar tertutup terakhir di InpSignalTF
bool Trigger(const int dir, double &wick)
  {
   wick = 0;
   ENUM_TIMEFRAMES tf = InpSignalTF;
   double o  = iOpen(_Symbol, tf, 1);
   double c  = iClose(_Symbol, tf, 1);
   double h  = iHigh(_Symbol, tf, 1);
   double l  = iLow(_Symbol, tf, 1);
   double c2 = iClose(_Symbol, tf, 2);
   double h2 = iHigh(_Symbol, tf, 2);
   double l2 = iLow(_Symbol, tf, 2);
   double ema = Val(g_hTrig, 0, 1);

   switch(InpEntryMode)
     {
      case ENTRY_PULLBACK:
         if(ema == EMPTY_VALUE)
            return false;
         return (dir == 1) ? (l <= ema && c > ema && c > o) : (h >= ema && c < ema && c < o);
      case ENTRY_ZONE:
         if(ema == EMPTY_VALUE)
            return false;
         return (dir == 1) ? (l <= ema && c > ema && c > h2) : (h >= ema && c < ema && c < l2);
      case ENTRY_DIP:
        {
         double r2 = Val(g_hSigRsi, 0, 2);
         if(r2 == EMPTY_VALUE)
            return false;
         return (dir == 1) ? (r2 <= InpDipRsi && c > o && c > c2) : (r2 >= 100.0 - InpDipRsi && c < o && c < c2);
        }
      case ENTRY_BREAKOUT:
      case ENTRY_SWEEP:
        {
         int ih = iHighest(_Symbol, tf, MODE_HIGH, InpLookback, 2);
         int il = iLowest(_Symbol, tf, MODE_LOW, InpLookback, 2);
         if(ih < 0 || il < 0)
            return false;
         double hh = iHigh(_Symbol, tf, ih);
         double ll = iLow(_Symbol, tf, il);
         if(InpEntryMode == ENTRY_BREAKOUT)
            return (dir == 1) ? (c > hh && c2 <= hh) : (c < ll && c2 >= ll);
         bool sw = (dir == 1) ? (l < ll && c > ll && c > o) : (h > hh && c < hh && c < o);
         if(sw)
            wick = (dir == 1) ? l : h;
         return sw;
        }
      case ENTRY_MAMACD:
        {
         // MA cepat memotong MA tengah, searah MA lambat, dikonfirmasi MACD (DIF vs DEA)
         double f1 = Val(g_hMaF, 0, 1), f2 = Val(g_hMaF, 0, 2);
         double m1 = Val(g_hMaM, 0, 1), m2 = Val(g_hMaM, 0, 2);
         double s1 = Val(g_hMaS, 0, 1);
         double dif = Val(g_hMacd, 0, 1), dea = Val(g_hMacd, 1, 1);
         if(f1 == EMPTY_VALUE || f2 == EMPTY_VALUE || m1 == EMPTY_VALUE || m2 == EMPTY_VALUE || s1 == EMPTY_VALUE || dif == EMPTY_VALUE || dea == EMPTY_VALUE)
            return false;
         bool cross = (dir == 1) ? (f1 > m1 && f2 <= m2) : (f1 < m1 && f2 >= m2);
         bool slow  = !InpMaRequireSlow || ((dir == 1) ? (c > s1 && m1 > s1) : (c < s1 && m1 < s1));
         bool macd  = (dir == 1) ? (dif > dea) : (dif < dea);
         return cross && slow && macd;
        }
      case ENTRY_ORB:
        {
         // bar yang MENUTUP di luar range pembukaan; ekor saja tidak dihitung
         double oh, ol;
         if(!OrbRange(oh, ol))
            return false;
         datetime te = OrbT0() + InpOrbRangeMin * 60;
         if(TimeCurrent() > te + InpOrbWindowMin * 60)
            return false;
         if(iTime(_Symbol, tf, 1) < te)
            return false;
         if(InpOrbLongOnly && dir == -1)
            return false;
         bool brk = (dir == 1) ? (c > oh) : (c < ol);
         if(!brk)
            return false;
         if(InpOrbStop == ORB_STOP_MID)
            wick = (oh + ol) / 2.0;
         else
            if(InpOrbStop == ORB_STOP_OPP)
               wick = (dir == 1) ? ol : oh;
         return true;
        }
      case ENTRY_BIAS:
         return true;
     }
   return false;
  }

void CheckEntry()
  {
   if(CountPositions() > 0)
     {
      g_status = "Posisi aktif - dikelola";
      return;
     }
   if(!g_scoreOk)
     {
      g_status = "WAIT: data timeframe belum siap";
      return;
     }
   if(!InSession())
     {
      g_status = "WAIT: di luar jam trading";
      return;
     }
   if(g_dayTrades >= InpMaxTradesDay)
     {
      g_status = "STOP: batas trade harian tercapai";
      return;
     }
   if(InpMaxConsecLoss > 0 && g_dayConsecLoss >= InpMaxConsecLoss)
     {
      g_status = "STOP: loss beruntun, lanjut besok";
      return;
     }
   double startBal = AccountInfoDouble(ACCOUNT_BALANCE) - g_dayPL;
   if(InpDailyLossPct > 0 && g_dayPL <= -(InpDailyLossPct / 100.0) * startBal)
     {
      g_status = "STOP: batas rugi harian tercapai";
      return;
     }
   if(InpDailyProfitPct > 0 && g_dayPL >= (InpDailyProfitPct / 100.0) * startBal)
     {
      g_status = "STOP: target profit harian tercapai";
      return;
     }
   if(InpCooldownMin > 0 && g_lastLossTime > 0 && TimeCurrent() < g_lastLossTime + InpCooldownMin * 60)
     {
      g_status = "WAIT: jeda setelah loss";
      return;
     }
   bool pipLocked = (g_pipLockDay == g_dayStart);
   if(InpDayTargetPips > 0 && (g_dayPips >= InpDayTargetPips || (pipLocked && g_dayPips > 0)))
     {
      g_status = "STOP: target pips harian tercapai";
      return;
     }
   if(InpDayMaxLossPips > 0 && (g_dayPips <= -InpDayMaxLossPips || (pipLocked && g_dayPips <= 0)))
     {
      g_status = "STOP: batas loss pips harian";
      return;
     }
   string why = "";
   if(NewsBlocked(why))
     {
      g_status = "PAUSE NEWS: " + StringSubstr(why, 0, 28);
      return;
     }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask - bid > InpMaxSpread)
     {
      g_status = "WAIT: spread terlalu lebar";
      return;
     }

   int    dir  = 0;
   double wick = 0;
   if(InpUseBias)
     {
      if(g_score >= InpMinScore)
         dir = 1;
      else
         if(g_score <= -InpMinScore)
            dir = -1;
      if(dir == 0)
        {
         g_status = "WAIT: skor MTF lemah";
         return;
        }
      if(InpRequireH1M15 && (g_bias[2] != dir || g_bias[4] != dir))
        {
         g_status = "WAIT: H1/M15 belum searah";
         return;
        }
     }
   else
     {
      // tanpa bias: arah diambil dari sinyal itu sendiri
      if(Trigger(1, wick))
         dir = 1;
      else
         if(Trigger(-1, wick))
            dir = -1;
      if(dir == 0)
        {
         g_status = "WAIT: belum ada sinyal";
         return;
        }
     }

   double adx = Val(g_hAdx, 0, 1);
   double rsi = Val(g_hRsi, 0, 1);
   double atr = Val(g_hAtr, 0, 1);
   if(adx == EMPTY_VALUE || rsi == EMPTY_VALUE || atr == EMPTY_VALUE)
     {
      g_status = "WAIT: indikator belum siap";
      return;
     }
   if(atr < InpAtrMin)
     {
      g_status = "WAIT: volatilitas terlalu rendah";
      return;
     }
   if(InpAtrMax > 0 && atr > InpAtrMax)
     {
      g_status = "WAIT: volatilitas terlalu liar";
      return;
     }
   if(adx < InpMinADX)
     {
      g_status = "WAIT: ADX lemah (sideways)";
      return;
     }
   if(dir == 1 && rsi > InpRsiOB)
     {
      g_status = "WAIT: RSI overbought";
      return;
     }
   if(dir == -1 && rsi < InpRsiOS)
     {
      g_status = "WAIT: RSI oversold";
      return;
     }

   double c = iClose(_Symbol, InpSignalTF, 1);

   // VWAP: beli hanya di atas nilai wajar hari ini, jual hanya di bawahnya
   if(InpUseVWAP && g_vwap > 0 && ((dir == 1 && c < g_vwap) || (dir == -1 && c > g_vwap)))
     {
      g_status = "WAIT: harga di sisi salah VWAP";
      return;
     }
   // high/low kemarin: area rawan liquidity sweep
   if(InpUsePDGuard)
     {
      double pdh = iHigh(_Symbol, PERIOD_D1, 1);
      double pdl = iLow(_Symbol, PERIOD_D1, 1);
      if(dir == 1 && pdh > 0 && MathAbs(c - pdh) <= InpPDGuardDist)
        {
         g_status = "WAIT: menempel high kemarin";
         return;
        }
      if(dir == -1 && pdl > 0 && MathAbs(c - pdl) <= InpPDGuardDist)
        {
         g_status = "WAIT: menempel low kemarin";
         return;
        }
     }

   // pemicu entry
   bool trig = Trigger(dir, wick);
   if(!trig)
     {
      g_status = (dir == 1) ? "SIAP BUY: tunggu pemicu" : "SIAP SELL: tunggu pemicu";
      return;
     }

   double minD   = MinStopDist();
   double slDist = MathMax(InpMinSL, MathMin(InpMaxSL, atr * InpSLAtr));
   // mode sweep: SL di balik ekor candle yang menyapu
   if(InpEntryMode == ENTRY_SWEEP && wick > 0)
      slDist = MathMax(InpMinSL, MathMin(InpMaxSL, MathAbs(((dir == 1) ? ask : bid) - wick) + 0.1 * atr));
   int    nTk = g_twin ? 2 : 1;
   if(InpSLPips > 0)
      slDist = InpSLPips * InpPipSize;
   // SL tidak boleh melebihi sisa jatah loss hari ini
   if(InpDayMaxLossPips > 0)
     {
      double budget = (InpDayMaxLossPips + g_dayPips) * InpPipSize / nTk;
      if(budget < 3.0 * (ask - bid) || budget < minD)
        {
         g_status = "STOP: sisa jatah loss harian habis";
         return;
        }
      slDist = MathMin(slDist, budget);
     }
   // mode ORB: stop di tengah / seberang range (kecuali SL tetap dalam pips dipakai)
   if(InpEntryMode == ENTRY_ORB && wick > 0 && InpSLPips <= 0)
      slDist = MathMax(InpMinSL, MathAbs(((dir == 1) ? ask : bid) - wick));
   slDist = MathMax(slDist, minD);
   // TP tidak perlu melebihi sisa target hari ini
   double tpCap = (InpDayTargetPips > 0) ? MathMax(minD, (InpDayTargetPips - g_dayPips) * InpPipSize) : DBL_MAX;
   double lot = NormLot(InpLot);

   ENUM_ORDER_TYPE type = (dir == 1) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double price = (dir == 1) ? ask : bid;
   // risk manager: tolak bila rugi di SL melebihi batas per trade
   if(InpMaxLossPerTrade > 0)
     {
      double pr = 0;
      if(OrderCalcProfit(type, _Symbol, lot * nTk, price, price - dir * slDist, pr) && -pr > InpMaxLossPerTrade)
        {
         g_status = StringFormat("BLOCK: risiko %.2f > batas %.2f", -pr, InpMaxLossPerTrade);
         return;
        }
     }
   double margin = 0;
   if(!OrderCalcMargin(type, _Symbol, lot * nTk, price, margin) || margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
     {
      g_status = "STOP: margin tidak cukup";
      return;
     }

   g_cur.tk = 0;
   g_cur.score = g_score; g_cur.adx = adx; g_cur.rsi = rsi; g_cur.atr = atr;
   g_cur.spread = ask - bid; g_cur.risk = slDist;
   g_cur.vwapDist = (g_vwap > 0) ? c - g_vwap : 0;

   double sl = NormPrice(price - dir * slDist);
   bool ok;
   if(g_twin)
     {
      double tp1 = NormPrice(price + dir * MathMax(MathMin(slDist * InpScalpTpR, tpCap), minD));
      double tp2 = NormPrice(price + dir * MathMax(MathMin(slDist * InpRunnerTpR, tpCap), minD));
      ok = OpenOne(dir, lot, sl, tp1, CMT_SCALP, slDist);
      if(ok)
         OpenOne(dir, lot, sl, tp2, CMT_RUN, slDist);
     }
   else
     {
      double tpD = (InpTPPips > 0) ? InpTPPips * InpPipSize : slDist * InpRR;
      double tp  = (tpD > 0) ? NormPrice(price + dir * MathMax(MathMin(tpD, tpCap), minD)) : 0;   // InpRR = 0: tanpa TP
      ok = OpenOne(dir, lot, sl, tp, CMT_ONE, slDist);
     }
   if(ok)
      g_status = (dir == 1) ? "BUY dibuka" : "SELL dibuka";
   else
      g_status = "ORDER GAGAL: " + IntegerToString((int)trade.ResultRetcode());
  }

//+------------------------------------------------------------------+
//| Kelola posisi: breakeven, ratchet, squeeze, ekspansi TP          |
//+------------------------------------------------------------------+
void ManagePositions()
  {
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !IsMine())
         continue;
      string cmt = PositionGetString(POSITION_COMMENT);
      if(cmt == CMT_SCALP)
         continue;                       // scalper: biarkan kena TP/SL apa adanya

      int    dir  = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double px   = (dir == 1) ? bid : ask;

      // trailing stop dalam USD harga: menggantikan breakeven / ratchet
      if(InpTrailDistUSD > 0 && InpTrailMain)
        {
         if(dir * (px - open) >= InpTrailStartUSD)
           {
            double tr = NormPrice(px - dir * InpTrailDistUSD);
            if((sl == 0 || dir * (tr - sl) >= InpTrailStepUSD) && dir * (px - tr) >= MinStopDist())
               trade.PositionModify(tk, tr, tp);
           }
         continue;
        }

      double risk = RiskOf(tk, cmt, dir, open, sl, tp);
      if(risk <= 0)
         continue;
      bool   isRun = (cmt == CMT_RUN);
      double rMult = dir * (px - open) / risk;

      double beTrig = isRun ? InpScalpTpR : InpBE_R;
      if(beTrig <= 0 || rMult < beTrig)
         continue;

      double newSL = sl;
      double newTP = tp;

      // 1. breakeven
      double be = open + dir * InpBEOffset;
      if(sl == 0 || dir * (be - newSL) > 0)
         newSL = be;

      if(InpUseRatchet)
        {
         // 2. ratchet bertahap: di +1.0R kunci +0.5R, di +1.5R kunci +1.0R, dst.
         if(InpRatchetStepR > 0)
           {
            double lockR = MathFloor(rMult / InpRatchetStepR + 1e-9) * InpRatchetStepR - InpRatchetStepR;
            if(lockR > 0)
              {
               double st = open + dir * risk * lockR;
               if(dir * (st - newSL) > 0)
                  newSL = st;
              }
           }
         // 3. dekat TP: rapatkan SL, dan perpanjang TP runner bila momentum masih kuat
         if(tp > 0)
           {
            double distR = dir * (tp - px) / risk;
            if(distR > 0 && distR <= InpSqueezeDistR)
              {
               double sq = px - dir * risk * InpSqueezeLockR;
               if(dir * (sq - newSL) > 0)
                  newSL = sq;
               if(isRun && InpTpExpandR > 0)
                 {
                  double rsi = Val(g_hRsi, 0, 1);
                  bool strong = (rsi != EMPTY_VALUE) && ((dir == 1 && rsi >= InpExpandRsi) || (dir == -1 && rsi <= 100.0 - InpExpandRsi));
                  if(strong)
                     newTP = tp + dir * risk * InpTpExpandR;
                 }
              }
           }
        }

      newSL = NormPrice(newSL);
      newTP = NormPrice(newTP);
      double minD = MinStopDist();
      if(dir * (px - newSL) < minD)
         newSL = sl;                     // terlalu dekat dengan harga, SL lama dipertahankan
      bool slChanged = (newSL != sl) && (sl == 0 || dir * (newSL - sl) >= 10 * pt);
      bool tpChanged = (MathAbs(newTP - tp) > pt);
      if(!slChanged && !tpChanged)
         continue;
      if(!slChanged)
         newSL = sl;
      trade.PositionModify(tk, newSL, newTP);
     }
  }

//+------------------------------------------------------------------+
//| Laporan backtest: rincian tiap tiket ke folder Common\Files      |
//|   MTRB_Pro_trades.csv dan MTRB_Pro_info.txt                      |
//+------------------------------------------------------------------+
struct TradeRec
  {
   long              pid;
   string            kind;
   int               dir;
   datetime          tIn, tOut;
   double            pIn, pOut, profit;
   string            reason;
  };

string ReasonStr(const long r)
  {
   if(r == DEAL_REASON_SL)
      return "SL";
   if(r == DEAL_REASON_TP)
      return "TP";
   if(r == DEAL_REASON_SO)
      return "STOPOUT";
   if(r == DEAL_REASON_EXPERT)
      return "EA";
   return "OTHER";
  }

void WriteReport()
  {
   if(!HistorySelect(0, TimeCurrent() + 60))
      return;
   TradeRec rec[];
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0)
         continue;
      long   dmg   = HistoryDealGetInteger(tk, DEAL_MAGIC);
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol || !IsOurMagic(dmg))
         continue;
      long   pid   = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      long   entry = HistoryDealGetInteger(tk, DEAL_ENTRY);
      double p     = HistoryDealGetDouble(tk, DEAL_PROFIT) + HistoryDealGetDouble(tk, DEAL_SWAP) + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      if(entry == DEAL_ENTRY_IN)
        {
         int k = ArraySize(rec);
         ArrayResize(rec, k + 1, 1024);
         string cmt = HistoryDealGetString(tk, DEAL_COMMENT);
         rec[k].pid    = pid;
         rec[k].kind   = (StringFind(cmt, "MTRB NAO") == 0) ? "NAO" : (StringFind(cmt, "MTRB CDL") == 0) ? "CDL" : (cmt == CMT_SCALP) ? "SCALP" : (cmt == CMT_RUN) ? "RUN" : (cmt == CMT_HB) ? "H4BO" : (cmt == CMT_ORB) ? "ORB" : (cmt == CMT_TL) ? "TL" : (cmt == CMT_SMC) ? "SMC" : (cmt == "MTRB BO2") ? "BO2" : (cmt == "MTRB BO3") ? "BO3" : (cmt == "MTRB TL2") ? "TL2" : (cmt == "MTRB MOM") ? "MOM" : (cmt == "MTRB RSM") ? "RSM" : (cmt == "MTRB DIP") ? "DIP" : (StringFind(cmt, "MTRB RH") == 0) ? "RH" : "ONE";
         rec[k].dir    = (HistoryDealGetInteger(tk, DEAL_TYPE) == DEAL_TYPE_BUY) ? 1 : -1;
         rec[k].tIn    = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
         rec[k].pIn    = HistoryDealGetDouble(tk, DEAL_PRICE);
         rec[k].tOut   = 0;
         rec[k].pOut   = 0;
         rec[k].profit = p;
         rec[k].reason = "OPEN";
        }
      else
        {
         for(int k = ArraySize(rec) - 1; k >= 0; k--)
            if(rec[k].pid == pid)
              {
               rec[k].tOut    = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
               rec[k].pOut    = HistoryDealGetDouble(tk, DEAL_PRICE);
               rec[k].profit += p;
               rec[k].reason  = ReasonStr(HistoryDealGetInteger(tk, DEAL_REASON));
               break;
              }
        }
     }

   string base = "MTRB_Pro" + (InpReportTag == "" ? "" : "_" + InpReportTag);
   int fh = FileOpen(base + "_trades.csv", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(fh != INVALID_HANDLE)
     {
      FileWrite(fh, "pid,kind,dir,open_time,hour,dow,open_price,close_time,close_price,minutes,profit,reason,risk,r_mult,score,adx,rsi,atr,spread,vwap_dist");
      int nc = ArraySize(g_ctx);
      int m  = ArraySize(rec);
      for(int k = 0; k < m; k++)
        {
         EntryCtx c;
         ZeroMemory(c);
         for(int j = 0; j < nc; j++)
            if((long)g_ctx[j].tk == rec[k].pid)
              {
               c = g_ctx[j];
               break;
              }
         MqlDateTime dt;
         TimeToStruct(rec[k].tIn, dt);
         double rm = (c.risk > 0 && rec[k].tOut > 0) ? rec[k].dir * (rec[k].pOut - rec[k].pIn) / c.risk : 0;
         FileWrite(fh, StringFormat("%I64d,%s,%s,%s,%d,%d,%.3f,%s,%.3f,%d,%.2f,%s,%.3f,%.2f,%.0f,%.1f,%.1f,%.2f,%.3f,%.2f",
                                    rec[k].pid, rec[k].kind, rec[k].dir == 1 ? "BUY" : "SELL",
                                    TimeToString(rec[k].tIn, TIME_DATE | TIME_MINUTES), dt.hour, dt.day_of_week, rec[k].pIn,
                                    TimeToString(rec[k].tOut, TIME_DATE | TIME_MINUTES), rec[k].pOut,
                                    (int)((rec[k].tOut - rec[k].tIn) / 60), rec[k].profit, rec[k].reason,
                                    c.risk, rm, c.score, c.adx, c.rsi, c.atr, c.spread, c.vwapDist));
        }
      FileClose(fh);
     }

   fh = FileOpen(base + "_info.txt", FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(fh != INVALID_HANDLE)
     {
      FileWrite(fh, "version=1.30");
      FileWrite(fh, StringFormat("pip=%.2f day_target_pips=%.0f day_max_loss_pips=%.0f sl_pips=%.0f tp_pips=%.0f",
                                 InpPipSize, InpDayTargetPips, InpDayMaxLossPips, InpSLPips, InpTPPips));
      FileWrite(fh, StringFormat("entry_mode=%d signal_tf=%s lookback=%d dip_rsi=%.0f require_h1m15=%d rsi_ob=%.0f rsi_os=%.0f be_r=%.2f twin_input=%d",
                                 (int)InpEntryMode, EnumToString(InpSignalTF), InpLookback, InpDipRsi, (int)InpRequireH1M15, InpRsiOB, InpRsiOS, InpBE_R, (int)InpTwinOrder));
      FileWrite(fh, "symbol=" + _Symbol + " digits=" + IntegerToString(_Digits));
      FileWrite(fh, "currency=" + AccountInfoString(ACCOUNT_CURRENCY) + " leverage=" + IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE)));
      FileWrite(fh, StringFormat("contract_size=%.4f tick_value=%.6f tick_size=%.6f point=%.6f",
                                 SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE), SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE),
                                 SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE), SymbolInfoDouble(_Symbol, SYMBOL_POINT)));
      FileWrite(fh, StringFormat("vol_min=%.2f vol_step=%.2f stops_level=%d margin_mode=%d twin_active=%d",
                                 SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
                                 (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), (int)AccountInfoInteger(ACCOUNT_MARGIN_MODE), (int)g_twin));
      FileWrite(fh, StringFormat("lot=%.2f min_score=%.0f min_adx=%.0f sl_atr=%.2f min_sl=%.2f max_sl=%.2f rr=%.2f scalp_r=%.2f runner_r=%.2f",
                                 InpLot, InpMinScore, InpMinADX, InpSLAtr, InpMinSL, InpMaxSL, InpRR, InpScalpTpR, InpRunnerTpR));
      FileWrite(fh, StringFormat("session=%d-%d max_spread=%.2f max_trades_day=%d vwap=%d pd_guard=%d ratchet=%d",
                                 InpSessStartHour, InpSessEndHour, InpMaxSpread, InpMaxTradesDay, (int)InpUseVWAP, (int)InpUsePDGuard, (int)InpUseRatchet));
      FileWrite(fh, StringFormat("deposit=%.2f net_profit=%.2f profit_factor=%.3f trades=%d equity_dd_pct=%.2f",
                                 TesterStatistics(STAT_INITIAL_DEPOSIT), TesterStatistics(STAT_PROFIT), TesterStatistics(STAT_PROFIT_FACTOR),
                                 (int)TesterStatistics(STAT_TRADES), TesterStatistics(STAT_EQUITY_DDREL_PERCENT)));
      FileClose(fh);
     }
  }

double OnTester()
  {
   if(!MQLInfoInteger(MQL_OPTIMIZATION))
      WriteReport();
   return TesterStatistics(STAT_PROFIT_FACTOR);
  }

//+------------------------------------------------------------------+
//| Panel                                                            |
//+------------------------------------------------------------------+
#define C_BG     C'16,20,28'
#define C_BORDER C'190,150,60'
#define C_GOLD   C'230,190,90'
#define C_TEXT   C'215,220,228'
#define C_DIM    C'125,135,150'
#define C_UP     C'60,200,120'
#define C_DN     C'235,80,90'
#define C_WARN   C'240,170,60'

//+------------------------------------------------------------------+
//| Penyegaran status tiap beberapa menit                            |
//| Hanya memperbarui TEKS status (level, garis, sisa waktu bar).    |
//| Aturan entry tidak berubah: tetap menunggu candle menutup.       |
//+------------------------------------------------------------------+
datetime        g_refAt = 0;

int D1Trend()
  {
   double f = Val(g_hFast[0], 0, 0), s = Val(g_hSlow[0], 0, 0), cd = iClose(_Symbol, PERIOD_D1, 0);
   if(f == EMPTY_VALUE || s == EMPTY_VALUE || cd <= 0)
      return 0;
   return (f > s && cd > s) ? 1 : (f < s && cd < s) ? -1 : 0;
  }

// sisa waktu sampai candle timeframe ini menutup
string BarLeft(const ENUM_TIMEFRAMES tf)
  {
   long s = (long)iTime(_Symbol, tf, 0) + PeriodSeconds(tf) - (long)TimeCurrent();
   if(s < 0)
      s = 0;
   if(s >= 3600)
      return StringFormat("%dj%02dm", (int)(s / 3600), (int)((s % 3600) / 60));
   return StringFormat("%dm", (int)(s / 60));
  }

void RefreshStatuses()
  {
   if(InpStatusRefreshMin <= 0 || TimeCurrent() - g_refAt < InpStatusRefreshMin * 60)
      return;
   g_refAt = TimeCurrent();
   int trend = D1Trend();

   // breakout: level yang harus ditembus oleh candle yang sedang berjalan
   for(int k = 0; k < N_HB; k++)
     {
      if(!g_hbI[k].on)
         continue;
      if(CountPosMagic(g_hbI[k].magic) > 0)
        {
         g_hbI[k].status = "Posisi aktif";
         continue;
        }
      if(trend == 0)
        {
         g_hbI[k].status = "Tren D1 campur, tidak entry";
         continue;
        }
      int ih = iHighest(_Symbol, g_hbI[k].tf, MODE_HIGH, m_hbLookback, 1);
      int il = iLowest(_Symbol, g_hbI[k].tf, MODE_LOW, m_hbLookback, 1);
      if(ih < 0 || il < 0)
         continue;
      double lvl = (trend == 1) ? iHigh(_Symbol, g_hbI[k].tf, ih) : iLow(_Symbol, g_hbI[k].tf, il);
      g_hbI[k].status = StringFormat("Tutup %s %.2f, bar %s lagi", trend == 1 ? ">" : "<", lvl, BarLeft(g_hbI[k].tf));
     }

   // garis tren: garis terbaru dan nilainya sekarang
   for(int k = 0; k < N_TL; k++)
     {
      if(!g_tlI[k].on)
         continue;
      if(CountPosMagic(g_tlI[k].magic) > 0)
        {
         g_tlI[k].status = "Posisi aktif";
         continue;
        }
      g_tlTF = g_tlI[k].tf;
      g_tlId = g_tlI[k].id;
      if(g_tlI[k].state == 1)
        {
         double v = TLValue(g_tlI[k].brk, 0);
         if(v > 0)
            g_tlI[k].status = StringFormat("Break %s, tunggu retest %.2f", g_tlI[k].dir == 1 ? "naik" : "turun", v);
         continue;
        }
      if(InpTlTrendFilter && trend == 0)
        {
         g_tlI[k].status = "Tren D1 campur, tidak entry";
         continue;
        }
      MqlRates r[];
      ArraySetAsSeries(r, true);
      int    n   = CopyRates(_Symbol, g_tlI[k].tf, 0, InpTlLookback + InpTlPivot + 5, r);
      double atr = Val(g_tlI[k].hAtr, 0, 1);
      if(n < InpTlPivot * 4 + 20 || atr == EMPTY_VALUE || atr <= 0)
         continue;
      TLine ln;
      int d = InpTlTrendFilter ? trend : 1;
      if(TLFind(r, n, d, 1, m_tlTolAtr * atr, m_tlMinTouches, ln))
        {
         g_tlI[k].status = StringFormat("Garis %.2f (%d sentuhan), tunggu break", TLValue(ln, 0), ln.touches);
         TLDraw("tl_main", ln, clrGold);
        }
      else
         g_tlI[k].status = "Belum ada garis tren sah";
     }
  }

// Panel mengikuti skala layar Windows: semua jarak piksel dikali g_sc.
double          g_sc = 1.0;
string          g_pUsed[];
int             g_pN = 0;

int SX(const double v) { return (int)MathRound(v * g_sc); }

void PUse(const string n)
  {
   if(g_pN >= ArraySize(g_pUsed))
      ArrayResize(g_pUsed, g_pN + 64);
   g_pUsed[g_pN++] = n;
  }

void PRect(const string id, const int x, const int y, const int w, const int h)
  {
   string n = PFX + "p_" + id;
   PUse(n);
   if(ObjectFind(0, n) < 0)
     {
      ObjectCreate(0, n, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, n, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, n, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, n, OBJPROP_BACK, false);
     }
   ObjectSetInteger(0, n, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, n, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, n, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, n, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, n, OBJPROP_BGCOLOR, C_BG);
   ObjectSetInteger(0, n, OBJPROP_COLOR, C_BORDER);
  }

void PLabel(const string id, const int x, const int y, const string txt, const color c, const int sz = 8,
            const bool bold = false, const ENUM_ANCHOR_POINT anchor = ANCHOR_LEFT_UPPER)
  {
   string n = PFX + "p_" + id;
   PUse(n);
   if(ObjectFind(0, n) < 0)
     {
      ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, n, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, n, OBJPROP_ANCHOR, anchor);
   ObjectSetString(0, n, OBJPROP_FONT, bold ? "Segoe UI Semibold" : "Segoe UI");
   ObjectSetInteger(0, n, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, n, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, sz);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetString(0, n, OBJPROP_TEXT, txt == "" ? " " : txt);
  }

// hapus label panel yang tidak dipakai pada gambar terakhir (baris yang hilang tidak meninggalkan sisa)
void PPurge()
  {
   string pre = PFX + "p_";
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      string n = ObjectName(0, i, 0, -1);
      if(StringFind(n, pre) != 0)
         continue;
      bool used = false;
      for(int j = 0; j < g_pN; j++)
         if(g_pUsed[j] == n)
           {
            used = true;
            break;
           }
      if(!used)
         ObjectDelete(0, n);
     }
  }

string Fit(const string s, const int maxLen)
  {
   if(StringLen(s) <= maxLen)
      return s;
   return StringSubstr(s, 0, maxLen - 2) + "..";
  }

string Countdown(const datetime t, const datetime now)
  {
   long d = (long)t - (long)now;
   if(d <= 0)
      return "lewat " + IntegerToString((int)(-d / 60)) + "m";
   if(d < 3600)
      return IntegerToString((int)(d / 60)) + "m lagi";
   return IntegerToString((int)(d / 3600)) + "j " + IntegerToString((int)((d % 3600) / 60)) + "m lagi";
  }

string EngShort(const int i)
  {
   string id = g_eng[i].id;
   if(StringFind(id, "HB") == 0)
      return "BO " + g_eng[i].tf;
   if(StringFind(id, "TL") == 0)
      return "GT " + g_eng[i].tf;
   if(id == "MAIN")
      return "Utama";
   return id;
  }

// waktu server -> WIB (GMT+7); selisih server-GMT dibulatkan ke 15 menit
datetime ToWib(const datetime srv)
  {
   long off = (long)TimeTradeServer() - (long)TimeGMT();
   off = (long)MathRound(off / 900.0) * 900;
   return (datetime)((long)srv - off + 7 * 3600);
  }

void DrawPanel()
  {
   if(!PanelEnabled())
      return;
   g_sc = MathMax(1.0, (double)TerminalInfoInteger(TERMINAL_SCREEN_DPI) / 96.0);
   g_pN = 0;

   int x = InpPanelX, y = InpPanelY;
   int W = SX(292), pad = SX(12), row = SX(17);
   int L = x + pad, R = x + W - pad, cy = y + SX(9);
   int chartH = (int)ChartGetInteger(0, CHART_HEIGHT_IN_PIXELS, 0);

   PRect("bg", x, y, W, SX(120));          // dibuat paling awal supaya berada di belakang teks

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double spread = ask - bid;
   string cur = AccountInfoString(ACCOUNT_CURRENCY);

   // --- judul
   PLabel("title", L, cy, "MTRB PRO", C_GOLD, 11, true);
   PLabel("sym", R, cy + SX(3), _Symbol + "   " + DoubleToString(bid, _Digits), C_TEXT, 9, false, ANCHOR_RIGHT_UPPER);
   cy += SX(27);

   // --- peringatan (hanya bila ada)
   string nw = "";
   bool   blocked = NewsBlocked(nw);
   bool   algo = (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && (bool)MQLInfoInteger(MQL_TRADE_ALLOWED);
   string warn = "";
   if(!algo && !g_tester)
      warn = "Algo Trading mati: EA tidak bisa trade";
   else
      if(g_paused)
         warn = "Entry dihentikan dari dashboard";
      else
         if(PortfolioDayLocked())
            warn = "Batas rugi harian tercapai";
   if(warn != "")
     {
      PLabel("warn", L, cy, warn, C_DN, 8, true);
      cy += row + SX(2);
     }

   // --- arah dan skor 7 timeframe
   string dirTxt = "NETRAL";
   color  dirCol = C_WARN;
   if(g_scoreOk && g_score >= InpMinScore)
     {
      dirTxt = "NAIK";
      dirCol = C_UP;
     }
   if(g_scoreOk && g_score <= -InpMinScore)
     {
      dirTxt = "TURUN";
      dirCol = C_DN;
     }
   PLabel("dirh", L, cy, "ARAH 7 TIMEFRAME", C_DIM, 7);
   PLabel("scoreh", R, cy, "SKOR", C_DIM, 7, false, ANCHOR_RIGHT_UPPER);
   cy += SX(12);
   PLabel("dir", L, cy, dirTxt, dirCol, 14, true);
   PLabel("score", R, cy, g_scoreOk ? StringFormat("%+.0f", g_score) : "-", dirCol, 14, true, ANCHOR_RIGHT_UPPER);
   cy += SX(30);

   int colW = (W - 2 * pad) / NTF;
   for(int i = 0; i < NTF; i++)
     {
      int    cxm = L + i * colW + colW / 2;
      color  c = (g_bias[i] > 0) ? C_UP : (g_bias[i] < 0) ? C_DN : C_DIM;
      string s = (g_bias[i] > 0) ? "naik" : (g_bias[i] < 0) ? "turun" : "-";
      PLabel("tfn" + IntegerToString(i), cxm, cy, g_tfName[i], C_DIM, 7, false, ANCHOR_UPPER);
      PLabel("tfb" + IntegerToString(i), cxm, cy + SX(12), s, c, 7, true, ANCHOR_UPPER);
     }
   cy += SX(31);

   // --- spread dan news
   PLabel("sph", L, cy, "Spread", C_DIM, 8);
   PLabel("spv", L + SX(46), cy, DoubleToString(spread, 2), C_TEXT, 8, true);
   PLabel("nws", R, cy, !g_newsOn ? "News: tidak dihindari" : blocked ? "News: jeda" : "News: aman", !g_newsOn ? C_DIM : blocked ? C_DN : C_UP, 8, false, ANCHOR_RIGHT_UPPER);
   cy += row;
   int sn = SessionNow();
   PLabel("ssh", L, cy, "Sesi", C_DIM, 8);
   PLabel("ssv", L + SX(46), cy, SessionName(sn), C_TEXT, 8, true);
   PLabel("sss", R, cy, g_sessOn[sn] ? "entry diizinkan" : "entry dimatikan", g_sessOn[sn] ? C_UP : C_DN, 8, false, ANCHOR_RIGHT_UPPER);
   cy += row;
   datetime now = TimeTradeServer();
   PLabel("tmh", L, cy, "Waktu", C_DIM, 8);
   PLabel("tmv", L + SX(46), cy, TimeToString(ToWib(now), TIME_MINUTES) + " WIB", C_TEXT, 8, true);
   PLabel("tms", R, cy, "server " + TimeToString(now, TIME_MINUTES), C_DIM, 8, false, ANCHOR_RIGHT_UPPER);
   cy += row;
   FlowRes pfr;
   if(g_flowMode > 0 && FlowGet(PERIOD_M5, pfr))
     {
      PLabel("flh", L, cy, "Volume", C_DIM, 8);
      PLabel("flv", L + SX(46), cy, StringFormat("Buy %.0f%%  Sell %.0f%%", pfr.buyPct, 100.0 - pfr.buyPct), pfr.buyPct >= 50 ? C_UP : C_DN, 8, true);
      PLabel("fls", R, cy, "M5, CVD " + (pfr.slopePct > 0 ? "naik" : pfr.slopePct < 0 ? "turun" : "datar") + (g_flowMode == 2 ? ", filter" : ""), C_DIM, 8, false, ANCHOR_RIGHT_UPPER);
      cy += row;
     }

   // indikator strategi utama hanya ditampilkan kalau strategi itu dinyalakan
   if(g_enMain)
     {
      double adx = Val(g_hAdx, 0, 0), rsi = Val(g_hRsi, 0, 0), atr = Val(g_hAtr, 0, 0);
      PLabel("ind", L, cy, StringFormat("ADX %.1f    RSI %.1f    ATR %.2f", adx == EMPTY_VALUE ? 0 : adx, rsi == EMPTY_VALUE ? 0 : rsi, atr == EMPTY_VALUE ? 0 : atr), C_DIM, 8);
      cy += row;
     }
   cy += SX(5);

   // --- strategi: hanya yang menyala, satu baris masing-masing
   PLabel("sh", L, cy, "STRATEGI", C_DIM, 7);
   if(g_refAt > 0)
      PLabel("shr", R, cy, "diperbarui " + TimeToString(ToWib(g_refAt), TIME_MINUTES) + " WIB", C_DIM, 7, false, ANCHOR_RIGHT_UPPER);
   cy += SX(13);
   int    nOn = 0;
   for(int i = 0; i < g_nEng; i++)
     {
      string lab = EngShort(i);
      if(!EngEnabled(g_eng[i].id))
         continue;
      string st = EngStatus(g_eng[i].id);
      color  sc = C_TEXT;
      if(StringFind(st, "Posisi aktif") == 0 || StringFind(st, "BUY") == 0 || StringFind(st, "SELL") == 0)
         sc = C_UP;
      else
         if(StringFind(st, "BLOCK") == 0 || StringFind(st, "STOP") == 0 || StringFind(st, "PAUSE") == 0 || StringFind(st, "ORDER GAGAL") == 0)
            sc = C_DN;
      PLabel("en" + IntegerToString(i), L, cy, lab, C_GOLD, 8, true);
      PLabel("es" + IntegerToString(i), L + SX(52), cy, Fit(st == "" ? "-" : st, 36), sc, 8);
      cy += SX(16);
      nOn++;
     }
   if(nOn == 0)
     {
      PLabel("none", L, cy, "Semua strategi mati", C_DIM, 8);
      cy += SX(16);
     }
   cy += SX(5);

   // --- posisi
   int    nPos = 0;
   double pl = 0, vol = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0 || !IsOurs())
         continue;
      nPos++;
      pl  += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      vol += PositionGetDouble(POSITION_VOLUME);
     }
   PLabel("ph", L, cy, "POSISI", C_DIM, 7);
   cy += SX(13);
   if(nPos > 0)
     {
      PLabel("p1", L, cy, StringFormat("%d posisi, %.2f lot", nPos, vol), C_TEXT, 8, true);
      PLabel("p2", R, cy, StringFormat("%+.2f", pl), pl >= 0 ? C_UP : C_DN, 8, true, ANCHOR_RIGHT_UPPER);
     }
   else
      PLabel("p1", L, cy, "Tidak ada posisi", C_DIM, 8);
   cy += row;
   double orisk = OpenRiskNow();
   PLabel("rk", L, cy, "Risiko terbuka", C_DIM, 8);
   PLabel("rkv", R, cy, g_maxOpenRisk > 0 ? StringFormat("%.0f dari %.0f", orisk, g_maxOpenRisk) : StringFormat("%.0f", orisk), C_TEXT, 8, true, ANCHOR_RIGHT_UPPER);
   cy += row + SX(5);

   // --- akun
   double bal = AccountInfoDouble(ACCOUNT_BALANCE), eq = AccountInfoDouble(ACCOUNT_EQUITY);
   PLabel("ah", L, cy, "AKUN", C_DIM, 7);
   cy += SX(13);
   PLabel("d1", L, cy, "Hari ini", C_DIM, 8);
   if(g_eqDayStart > 0)
      PLabel("d1v", R, cy, StringFormat("%+.2f %s", eq - g_eqDayStart, cur), (eq - g_eqDayStart) >= 0 ? C_UP : C_DN, 8, true, ANCHOR_RIGHT_UPPER);
   else
      PLabel("d1v", R, cy, "-", C_DIM, 8, false, ANCHOR_RIGHT_UPPER);
   cy += row;
   PLabel("b1", L, cy, "Saldo", C_DIM, 8);
   PLabel("b1v", R, cy, DoubleToString(bal, 2), C_TEXT, 8, true, ANCHOR_RIGHT_UPPER);
   cy += row;
   PLabel("e1", L, cy, "Equity", C_DIM, 8);
   PLabel("e1v", R, cy, DoubleToString(eq, 2), C_TEXT, 8, true, ANCHOR_RIGHT_UPPER);
   cy += row;

   // --- news: hanya kalau tinggi chart masih cukup
   if(!g_tester)
     {
      datetime now = TimeTradeServer();
      int idx[3];
      int k = 0;
      for(int i = 0; i < ArraySize(g_news) && k < 3; i++)
         if(g_news[i].t >= now - InpNewsAfterMin * 60)
            idx[k++] = i;
      int need = SX(5) + SX(13) + MathMax(k, 1) * SX(16) + SX(8);
      if(cy + need <= chartH - SX(4))
        {
         cy += SX(5);
         PLabel("nh", L, cy, "NEWS " + InpNewsCurrency, C_DIM, 7);
         cy += SX(13);
         if(k == 0)
           {
            PLabel("nw0", L, cy, "Tidak ada news penting 48 jam", C_DIM, 8);
            cy += SX(16);
           }
         for(int q = 0; q < k; q++)
           {
            int i = idx[q];
            PLabel("nw" + IntegerToString(q), L, cy, Fit(g_news[i].name, 28), g_news[i].imp == 3 ? C_DN : C_WARN, 8);
            PLabel("nc" + IntegerToString(q), R, cy, Countdown(g_news[i].t, now), C_DIM, 7, false, ANCHOR_RIGHT_UPPER);
            cy += SX(16);
           }
        }
     }

   PRect("bg", x, y, W, cy - y + SX(8));
   PPurge();
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
