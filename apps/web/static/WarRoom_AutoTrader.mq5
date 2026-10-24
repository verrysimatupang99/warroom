void FetchAndExecuteSignal();
bool HasOpenPosition();
//+------------------------------------------------------------------+
//|                                           WarRoom_AutoTrader.mq5 |
//|                                  War Room Quantitative Multi-Asset |
//|                                     https://0xgunsl1ng3r.xyz     |
//+------------------------------------------------------------------+
#property copyright "War Room Quantitative Terminal"
#property link      "https://0xgunsl1ng3r.xyz"
#property version   "2.00"
#property description "Auto-Trade Connector resmi War Room v2.0 untuk MetaTrader 5"

#include <Trade\Trade.mqh>
CTrade trade;

input group "=== KONEKSI WAR ROOM API ==="
input string   InpApiUrl       = "https://0xgunsl1ng3r.xyz/api/v1/tencent/forex/levels?symbol=XAUUSD"; // Endpoint Sinyal War Room
input string   InpTelemetryUrl = "https://0xgunsl1ng3r.xyz/api/v1/tencent/mt5/telemetry";             // Endpoint Lapor Live Telemetry
input string   InpFillUrl      = "https://0xgunsl1ng3r.xyz/api/v1/tencent/mt5/fill";                  // Endpoint Lapor Kualitas Eksekusi
input int      InpPollSeconds  = 5;           // Interval Pengecekan (Detik)
// Timeout HTTP harus LEBIH BESAR dari latensi terburuk /forex/levels.
// Model Laya butuh ~30 detik saat cold start (memuat model 421M) dan 1.5-2.2
// detik saat warm. Nilai lama 3000 ms membuat poll pertama setelah restart API
// selalu timeout sehingga sinyal tidak pernah diterima.
input int      InpHttpTimeoutMs = 15000;      // Timeout WebRequest (milidetik)
input int      InpFailCooldownSec = 120;      // Jeda setelah order ditolak broker (detik)

input group "=== PENGATURAN RISK & LOT ==="
input bool     InpUseRiskSizing = false;      // Hitung lot dari risiko % balance (default OFF: owner pakai lot tetap)
input double   InpRiskPct       = 1.0;        // Risiko per trade (% dari balance)
input double   InpMaxLot        = 0.10;       // Batas atas lot (pengaman)
input double   InpMinLot        = 0.01;       // Batas bawah lot (batas broker Exness)
input double   InpFixedLot      = 0.05;       // Lot tetap (dipakai bila InpUseRiskSizing=false)

input group "=== PENJAGA EKSEKUSI (WAJIB) ==="
// R1: R:R divalidasi ulang pada HARGA FILL (ask/bid), bukan harga sinyal.
// Insiden 21 Okt: sinyal punya SL 3.0 poin tapi harga sudah melesat 6.2 poin,
// sehingga reward tinggal 0.23 vs risk 9.17 (R:R 1:0.03) dan rugi $91.52.
input double   InpMinRR         = 0.80;       // Tolak bila reward/risk < nilai ini (pada harga fill)
input double   InpMaxDriftFrac  = 0.30;       // Tolak bila harga sudah bergerak > fraksi ini dari TP
input int      InpMaxSignalAgeSec = 60;       // Tolak sinyal lebih tua dari ini (detik, 0=nonaktif)
input ulong    InpMagicNumber   = 992026;     // Magic Number War Room
input ulong    InpSlippage      = 30;         // Max Slippage (Points)

input group "=== FREQTRADE PROTEKSI (AUTOMATIC) ==="
input bool     InpUsePartialTP = true;        // Amankan 50% Lot di Target +1.0R (Anti Floating Loss)
input double   InpPartialRatio = 0.50;        // Porsi Lot yang Ditutup (0.50 = 50%)
input bool     InpUseBreakeven = true;        // Aktifkan Buffered Breakeven Lock (+1.2R)
input int      InpBEBufferPts  = 15;          // Buffer BE di atas modal (Tutup komisi/spread)
input bool     InpUseTrailing  = true;        // Aktifkan Dynamic Trailing Stop (+1.5R)
// Batas spread dalam POINTS. XAUUSDm punya 3 desimal -> point = 0.001, sehingga
// 350 pts = $0,35. Nilai lama 40 pts ($0,04) TIDAK MUNGKIN tercapai pada gold
// (spread normal Exness $0,15-$0,35), akibatnya EA menolak SEMUA sinyal.
// 350 pts menahan pelebaran saat rollover/news tanpa memblokir pasar normal.
input int      InpMaxSpreadPts = 350;         // Max Spread Diizinkan (Pencegah Slippage)

input group "=== DAILY PROFIT RATCHET & LOSS GUARD ==="
input bool     InpEnableDailyRatchet = true;  // Kunci Target Profit Harian
input double   InpDailyTargetLock   = 40.0;   // Target Profit Harian Minimal ($)
input double   InpDailyFloorLock    = 30.0;   // Floor Proteksi: Jika pullback ke sini, kunci & setop ($)
input double   InpDailyMaxLoss      = 25.0;   // Batas Rugi Maksimal Harian ($)

datetime lastCheckTime = 0;
string lastProcessedSignal = "";
datetime lastOrderFailTs = 0;   // waktu order terakhir ditolak broker

// Handle indikator M5. Dibuat sekali di OnInit (bukan per tick) karena
// pembuatan handle mahal; CopyBuffer hanya menyalin nilai terakhir.
// Dipakai untuk mengirim snapshot BROKER ke API, supaya jarak SL/TP dihitung dari
// instrumen yang benar-benar dieksekusi (spot XAUUSDm), bukan futures GC=F.
int hAtrM5   = INVALID_HANDLE;
int hEma9M5  = INVALID_HANDLE;
int hEma21M5 = INVALID_HANDLE;

// Ambil nilai terakhir sebuah indikator. 0.0 berarti tidak tersedia, dan
// pemanggil WAJIB memperlakukannya sebagai "tidak diketahui", bukan nol nyata.
double NilaiIndikator(const int handle)
{
   if(handle == INVALID_HANDLE) return 0.0;
   double buf[];
   if(CopyBuffer(handle, 0, 0, 1, buf) <= 0) return 0.0;
   return buf[0];
}
ulong processedPartials[];

bool IsPartialDone(ulong ticket)
{
   for(int i = 0; i < ArraySize(processedPartials); i++)
      if(processedPartials[i] == ticket) return true;
   return false;
}

void MarkPartialDone(ulong ticket)
{
   int sz = ArraySize(processedPartials);
   ArrayResize(processedPartials, sz + 1);
   processedPartials[sz] = ticket;
}
datetime currentDay = 0;
double startOfDayBalance = 0;
double peakProfitToday = 0;
bool dailyLocked = false;

//+------------------------------------------------------------------+
//| Kirim Telemetry Status & Posisi Terbuka ke Server War Room       |
//+------------------------------------------------------------------+
// Statistik hari ini dari riwayat deal broker.
// PENTING: payload telemetri sebelumnya mengirim konstanta
// `"total_trades_today":6,"win_rate_pct":66.7` yang TIDAK PERNAH dihitung.
// Angka itu tampil sebagai data di /mt5/status dan bisa menyesatkan analisis.
void HitungStatistikHariIni(int &totalOut, int &wins, int &losses, double &netPnl)
{
   totalOut = 0;
   wins     = 0;
   losses   = 0;
   netPnl   = 0.0;

   datetime mulai = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   if(!HistorySelect(mulai, TimeCurrent() + 60)) return;

   int deals = HistoryDealsTotal();
   for(int i = 0; i < deals; i++)
   {
      ulong tiket = HistoryDealGetTicket(i);
      if(tiket == 0) continue;
      if(HistoryDealGetInteger(tiket, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      if(HistoryDealGetString(tiket, DEAL_SYMBOL) != _Symbol) continue;

      double untung = HistoryDealGetDouble(tiket, DEAL_PROFIT)
                    + HistoryDealGetDouble(tiket, DEAL_SWAP)
                    + HistoryDealGetDouble(tiket, DEAL_COMMISSION);
      netPnl += untung;
      totalOut++;
      if(untung > 0.0)      wins++;
      else if(untung < 0.0) losses++;
   }
}

void SendTelemetryReport()
{
   string acc = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   string broker = AccountInfoString(ACCOUNT_COMPANY);
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double mar = AccountInfoDouble(ACCOUNT_MARGIN);
   double freeMar = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double pnl = AccountInfoDouble(ACCOUNT_PROFIT);

   string posJson = "[";
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol)
      {
         if(count > 0) posJson += ",";
         string sSide = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "BUY" : "SELL";
         posJson += StringFormat("{\"ticket\":%I64u,\"symbol\":\"%s\",\"side\":\"%s\",\"volume\":%.2f,\"open_price\":%.3f,\"current_price\":%.3f,\"sl\":%.3f,\"tp\":%.3f,\"pnl_usd\":%.2f}",
            ticket,
            PositionGetString(POSITION_SYMBOL),
            sSide,
            PositionGetDouble(POSITION_VOLUME),
            PositionGetDouble(POSITION_PRICE_OPEN),
            PositionGetDouble(POSITION_PRICE_CURRENT),
            PositionGetDouble(POSITION_SL),
            PositionGetDouble(POSITION_TP),
            PositionGetDouble(POSITION_PROFIT)
         );
         count++;
      }
   }
   posJson += "]";

   // --- Snapshot BROKER (Opsi A riset sumber harga) ---
   // API memakai nilai ini untuk menghitung jarak risk/reward pada instrumen yang
   // benar-benar dieksekusi. Sumber lain (Yahoo GC=F) adalah futures dan terbukti
   // meleset ~11,8 poin dari harga broker.
   double bidNow = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double askNow = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   long   spreadNow = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   int    digitNow  = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double atrM5     = NilaiIndikator(hAtrM5);
   double ema9M5    = NilaiIndikator(hEma9M5);
   double ema21M5   = NilaiIndikator(hEma21M5);

   double hi12 = 0.0, lo12 = 0.0;
   double highs[], lows[];
   if(CopyHigh(_Symbol, PERIOD_M5, 0, 12, highs) == 12 &&
      CopyLow(_Symbol, PERIOD_M5, 0, 12, lows) == 12)
   {
      hi12 = highs[ArrayMaximum(highs)];
      lo12 = lows[ArrayMinimum(lows)];
   }

   int    totalHari = 0, menang = 0, kalah = 0;
   double netHari = 0.0;
   HitungStatistikHariIni(totalHari, menang, kalah, netHari);
   double winRate = (totalHari > 0) ? (menang * 100.0 / totalHari) : 0.0;

   string payload = StringFormat(
      "{\"account\":\"%s\",\"broker\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,"
      "\"margin\":%.2f,\"free_margin\":%.2f,\"floating_pnl\":%.2f,\"positions\":%s,"
      "\"total_trades_today\":%d,\"wins_today\":%d,\"losses_today\":%d,\"win_rate_today_pct\":%.1f,"
      "\"net_pnl_today_usd\":%.2f,"
      "\"bid\":%s,\"ask\":%s,\"spread_pts\":%I64d,\"digits\":%d,"
      "\"atr_m5\":%s,\"ema9_m5\":%s,\"ema21_m5\":%s,\"high_12\":%s,\"low_12\":%s}",
      acc, broker, bal, eq, mar, freeMar, pnl, posJson,
      totalHari, menang, kalah, winRate, netHari,
      DoubleToString(bidNow, digitNow), DoubleToString(askNow, digitNow),
      spreadNow, digitNow,
      DoubleToString(atrM5, digitNow), DoubleToString(ema9M5, digitNow),
      DoubleToString(ema21M5, digitNow),
      DoubleToString(hi12, digitNow), DoubleToString(lo12, digitNow)
   );

   char post[], result[];
   string headers = "Content-Type: application/json\r\n";
   StringToCharArray(payload, post, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post, ArraySize(post)-1); // buang null terminator

   ResetLastError();
   WebRequest("POST", InpTelemetryUrl, headers, 2000, post, result, headers);
}

//+------------------------------------------------------------------+
//| Laporkan kualitas eksekusi: harga diminta vs didapat + latensi.   |
//| Murni diagnostik: tidak mengubah keputusan trading apa pun.       |
//| Slippage diukur dalam POINT, positif = fill lebih buruk.          |
//+------------------------------------------------------------------+
void LaporFill(string side, double vol, double diminta, double didapat,
               double sl, double tp, long spreadPts, int latensiMs,
               ulong retcode, int posisiTerbuka)
{
   string payload = StringFormat(
      "{\"ticket\":%I64u,\"symbol\":\"%s\",\"side\":\"%s\",\"volume\":%.2f,"
      "\"price_requested\":%s,\"price_filled\":%s,\"sl\":%s,\"tp\":%s,"
      "\"spread_pts\":%I64d,\"digits\":%d,\"latency_ms\":%d,\"retcode\":%I64u,"
      "\"execution_mode\":%d,\"open_positions\":%d,\"equity\":%.2f}",
      trade.ResultOrder(), _Symbol, side, vol,
      DoubleToString(diminta, _Digits), DoubleToString(didapat, _Digits),
      DoubleToString(sl, _Digits), DoubleToString(tp, _Digits),
      spreadPts, (int)_Digits, latensiMs, retcode,
      (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE),
      posisiTerbuka, AccountInfoDouble(ACCOUNT_EQUITY));

   char post[], result[];
   string headers = "Content-Type: application/json\r\n";
   StringToCharArray(payload, post, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post, ArraySize(post)-1);
   ResetLastError();
   int res = WebRequest("POST", InpFillUrl, headers, 2000, post, result, headers);
   if(res != 200)
      Print(" PERINGATAN: log eksekusi gagal dikirim (HTTP ", res, "). Trading tetap jalan.");
}

//+------------------------------------------------------------------+
//| Hitung posisi terbuka milik EA ini pada simbol chart.             |
//+------------------------------------------------------------------+
int HitungPosisiTerbuka()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
         n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFilling(ORDER_FILLING_FOK);

   // Handle indikator M5 untuk snapshot broker (dipakai SendTelemetryReport).
   hAtrM5   = iATR(_Symbol, PERIOD_M5, 14);
   hEma9M5  = iMA(_Symbol, PERIOD_M5, 9, 0, MODE_EMA, PRICE_CLOSE);
   hEma21M5 = iMA(_Symbol, PERIOD_M5, 21, 0, MODE_EMA, PRICE_CLOSE);
   if(hAtrM5 == INVALID_HANDLE || hEma9M5 == INVALID_HANDLE || hEma21M5 == INVALID_HANDLE)
   {
      Print(" PERINGATAN: sebagian handle indikator gagal dibuat. Snapshot broker ",
            "akan melaporkan atr_m5/ema=0 dan API harus memperlakukannya sebagai ",
            "tidak tersedia.");
   }
   
   Print(" War Room AutoTrader v2.0 siap berjalan pada: ", _Symbol);
   Print(" Endpoint API: ", InpApiUrl);
   Print(" Pastikan 'Allow WebRequest' ke 'https://0xgunsl1ng3r.xyz' sudah diaktifkan di Tools -> Options -> Expert Advisors.");
   
   EventSetTimer(InpPollSeconds);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   // Lepas handle indikator agar tidak bocor saat EA dilepas/di-reload.
   if(hAtrM5   != INVALID_HANDLE) IndicatorRelease(hAtrM5);
   if(hEma9M5  != INVALID_HANDLE) IndicatorRelease(hEma9M5);
   if(hEma21M5 != INVALID_HANDLE) IndicatorRelease(hEma21M5);
   Print(" War Room AutoTrader dihentikan.");
}


//+------------------------------------------------------------------+
//| Cek Proteksi Daily Profit Ratchet & Max Loss Guard              |
//+------------------------------------------------------------------+
bool CheckDailyProtections()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime todayStart = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(currentDay != todayStart)
   {
      currentDay = todayStart;
      startOfDayBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      peakProfitToday = 0;
      dailyLocked = false;
      Print(" Hari Baru Dimulai: Reset baseline balance: $", startOfDayBalance);
   }

   if(startOfDayBalance <= 0)
      startOfDayBalance = AccountInfoDouble(ACCOUNT_BALANCE);

   // Hitung total profit terealisasi hari ini
   HistorySelect(todayStart, TimeCurrent());
   double realizedToday = 0;
   int dealsTotal = HistoryDealsTotal();
   int winCount = 0;
   int totalTrades = 0;

   for(int i = 0; i < dealsTotal; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         long entryType = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entryType == DEAL_ENTRY_OUT || entryType == DEAL_ENTRY_INOUT)
         {
            double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            realizedToday += profit;
            totalTrades++;
            if(profit > 0) winCount++;
         }
      }
   }

   double currentProfit = realizedToday;
   if(currentProfit > peakProfitToday)
      peakProfitToday = currentProfit;

   // 1. Cek Daily Max Loss Guard
   if(InpEnableDailyRatchet && currentProfit <= -InpDailyMaxLoss)
   {
      if(!dailyLocked)
      {
         Print(" DAILY MAX LOSS HIT! Realized: $", currentProfit, " <= -$", InpDailyMaxLoss, ". Menutup posisi & pause sampai besok.");
         CloseAllPositions();
         dailyLocked = true;
      }
      return false; // Jangan ambil posisi baru
   }

   // 2. Cek Daily Profit Ratchet Lock:
   // Jika sudah tembus target lock (0), dan profit turun menyentuh floor lock (0), kunci cuan!
   if(InpEnableDailyRatchet && peakProfitToday >= InpDailyTargetLock)
   {
      if(currentProfit <= InpDailyFloorLock)
      {
         if(!dailyLocked)
         {
            Print(" DAILY PROFIT RATCHET LOCKED! Peak: $", peakProfitToday, " Pullback ke: $", currentProfit, " (Floor: $", InpDailyFloorLock, "). Amankan profit & istirahat.");
            CloseAllPositions();
            dailyLocked = true;
         }
         return false; // Jangan ambil posisi baru
      }
   }

   return !dailyLocked;
}

void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         trade.PositionClose(ticket);
      }
   }
}


//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Kelola Partial Close, Buffered Breakeven, dan Trailing Stop      |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   if(!InpUseBreakeven && !InpUseTrailing && !InpUsePartialTP) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         long   type         = PositionGetInteger(POSITION_TYPE);
         double openPrice    = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
         double currentSL    = PositionGetDouble(POSITION_SL);
         double currentTP    = PositionGetDouble(POSITION_TP);
         double volume       = PositionGetDouble(POSITION_VOLUME);

         double initialRisk = MathAbs(openPrice - currentSL);
         if(initialRisk <= 0) initialRisk = 3.5;

         if(type == POSITION_TYPE_BUY)
         {
            // 1. PARTIAL TAKE PROFIT 50% di +1.0R
            if(InpUsePartialTP && !IsPartialDone(ticket) && volume >= 0.04)
            {
               if(currentPrice >= (openPrice + initialRisk))
               {
                  double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
                  double closeVol = MathRound((volume * InpPartialRatio) / lotStep) * lotStep;
                  if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN) && closeVol < volume)
                  {
                     if(trade.PositionClosePartial(ticket, closeVol))
                     {
                        MarkPartialDone(ticket);
                        Print(" INSTITUTIONAL PARTIAL TAKE PROFIT: Berhasil amankan 50% lot (", closeVol, ") pada tiket #", ticket);
                        PositionSelectByTicket(ticket);
                        currentSL = PositionGetDouble(POSITION_SL);
                     }
                  }
               }
            }

            // 2. BUFFERED BREAKEVEN GUARD di +1.2R
            if(InpUseBreakeven)
            {
               double beTrigger = openPrice + (initialRisk * 1.2);
               double targetSL = openPrice + (InpBEBufferPts * _Point);
               if(currentPrice >= beTrigger && (currentSL < targetSL || currentSL == 0))
               {
                  Print(" Buffered Breakeven Locked: Tiket #", ticket, " SL digeser ke modal + buffer: ", targetSL);
                  trade.PositionModify(ticket, targetSL, currentTP);
               }
            }
         }
         else if(type == POSITION_TYPE_SELL)
         {
            // 1. PARTIAL TAKE PROFIT 50% di +1.0R
            if(InpUsePartialTP && !IsPartialDone(ticket) && volume >= 0.04)
            {
               if(currentPrice <= (openPrice - initialRisk))
               {
                  double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
                  double closeVol = MathRound((volume * InpPartialRatio) / lotStep) * lotStep;
                  if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN) && closeVol < volume)
                  {
                     if(trade.PositionClosePartial(ticket, closeVol))
                     {
                        MarkPartialDone(ticket);
                        Print(" INSTITUTIONAL PARTIAL TAKE PROFIT: Berhasil amankan 50% lot (", closeVol, ") pada tiket #", ticket);
                        PositionSelectByTicket(ticket);
                        currentSL = PositionGetDouble(POSITION_SL);
                     }
                  }
               }
            }

            // 2. BUFFERED BREAKEVEN GUARD di +1.2R
            if(InpUseBreakeven)
            {
               double beTrigger = openPrice - (initialRisk * 1.2);
               double targetSL = openPrice - (InpBEBufferPts * _Point);
               if(currentPrice <= beTrigger && (currentSL > targetSL || currentSL == 0))
               {
                  Print(" Buffered Breakeven Locked: Tiket #", ticket, " SL digeser ke modal + buffer: ", targetSL);
                  trade.PositionModify(ticket, targetSL, currentTP);
               }
            }
         }
      }
   }
}

//| Timer function: polling sinyal dari War Room API                  |
//+------------------------------------------------------------------+
void OnTimer()
{
   // 1. Kirim snapshot telemetry ke Beranda War Room
   SendTelemetryReport();

   // 2. Kelola Posisi Terbuka (Breakeven & Trailing Stop)
   ManageOpenPositions();

   // 3. Periksa Proteksi Harian (Daily Profit Ratchet & Max Loss Guard)
   if(!CheckDailyProtections()) return;

   // 4. Cek apakah ada posisi terbuka saat ini
   if(HasOpenPosition()) return;

   // 5. Tarik sinyal terbaru dari War Room
   FetchAndExecuteSignal();
}

//+------------------------------------------------------------------+
//| Cek apakah ada posisi terbuka dengan Magic Number ini            |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0)
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Parser String JSON Sederhana                                     |
//+------------------------------------------------------------------+
string ExtractJsonString(string json, string key)
{
   string search = "\"" + key + "\":\"";
   int pos = StringFind(json, search);
   if(pos < 0)
   {
      search = "\"" + key + "\": \"";
      pos = StringFind(json, search);
   }
   if(pos < 0) return "";
   pos += StringLen(search);
   int end = StringFind(json, "\"", pos);
   if(end < 0) return "";
   return StringSubstr(json, pos, end - pos);
}

//+------------------------------------------------------------------+
//| Parser Double JSON Sederhana                                     |
//+------------------------------------------------------------------+
// --- Position sizing berbasis RISIKO (bukan lot tetap) ---------------------
// Latar 23 Okt 2026: lot tetap 0.10 pada balance ~$457 menghasilkan risiko
// ~$50/trade = 11% balance, sedangkan InpDailyMaxLoss hanya $25. Satu SL saja
// sudah 2x melebihi batas rugi harian -> win rate 66,7% tetap rugi (net -$43).
//
// Aturan: ukuran posisi ditentukan oleh jarak SL yang BENAR-BENAR dikirim sinyal,
// bukan angka bulat. Bila nilai kontrak tidak terbaca, fungsi mengembalikan 0 dan
// pemanggil WAJIB membatalkan order (lebih baik tidak trading daripada salah ukuran).
double HitungLotRisiko(double entry, double sl)
{
   if(!InpUseRiskSizing) return InpFixedLot;
   double jarak = MathAbs(entry - sl);
   if(jarak <= 0.0)
   {
      Print(" SIZING GAGAL: jarak SL nol (entry=", entry, " sl=", sl, "). Order dibatalkan.");
      return 0.0;
   }

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double risikoUsd = balance * InpRiskPct / 100.0;

   // Nilai 1 lot untuk pergerakan 1 unit harga. XAUUSD: 1 lot = 100 oz.
   // Rumus umum: nilai per lot = TickValue / TickSize.
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0)
   {
      Print(" SIZING GAGAL: tick value/size tidak terbaca (", tickValue, "/", tickSize, "). Order dibatalkan.");
      return 0.0;
   }
   double nilaiPerLotPerHarga = tickValue / tickSize;   // USD per 1 lot per 1.0 harga

   double lot = risikoUsd / (jarak * nilaiPerLotPerHarga);

   // Bulatkan ke lot step broker, lalu jepit di [min, max].
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(lotStep > 0.0)
   {
      // PENTING: jangan MathFloor ke 0. Pada balance kecil, lot hasil hitung sering
      // jatuh DI BAWAH satu lot step (mis. 0.0091 dengan step 0.01). Floor akan
      // menghasilkan 0.00 -> order batal padahal risiko sebenarnya masih wajar.
      // Karena itu pembulatan ke BAWAH dibatasi minimal satu step, lalu penjepitan
      // di bawah yang memutuskan boleh/tidaknya (dengan cek 1.5x target).
      double lotBulat = MathFloor(lot / lotStep) * lotStep;
      lot = (lotBulat > 0.0) ? lotBulat : lotStep;
   }

   double batasAtas = InpMaxLot;
   if(lotMax > 0.0 && lotMax < batasAtas) batasAtas = lotMax;
   double batasBawah = MathMax(InpMinLot, lotMin);

   if(lot < batasBawah) lot = batasBawah;
   if(lot > batasAtas) lot = batasAtas;

   // PENJAGA TERAKHIR: apa pun yang terjadi di atas, risiko uang yang benar-benar
   // dipertaruhkan tidak boleh jauh melebihi target. Tanpa ini, SL yang sangat lebar
   // (mis. 50 dolar) tetap dieksekusi dengan lot minimum 0.01 = risiko ~$50 pada
   // balance $457 (11%) - persis masalah yang mau diperbaiki.
   double risikoAkhir = lot * jarak * nilaiPerLotPerHarga;
   double batasRisiko = MathMax(risikoUsd * 1.5, risikoUsd + 1.0);
   if(risikoAkhir > batasRisiko)
   {
      Print(" SIZING DITOLAK: risiko akhir $", DoubleToString(risikoAkhir, 2),
            " melebihi batas $", DoubleToString(batasRisiko, 2),
            " (target $", DoubleToString(risikoUsd, 2), ", jarak SL ", DoubleToString(jarak, 2),
            "). Order dibatalkan - tunggu setup dengan SL lebih rapat.");
      return 0.0;
   }

   Print(" SIZING: balance=$", balance, " risikoTarget=$", DoubleToString(risikoUsd, 2),
         " jarakSL=", DoubleToString(jarak, 2), " -> lot=", DoubleToString(lot, 2),
         " (risiko nyata $", DoubleToString(risikoAkhir, 2), ")");
   return lot;
}

// ============================================================================
// R1: VALIDASI RISK/REWARD PADA HARGA FILL
//
// Sinyal dari API menghitung SL/TP dari harga snapshot (ind["price"]), sedangkan
// eksekusi memakai ask/bid live. Selisih keduanya mengubah rasio secara diam-diam.
//
// Contoh nyata (trade #6, 21 Okt 2026):
//   API  : entry=4126.98 sl=4122.98 tp1=4132.38   (risk 4.0, reward 5.4)
//   Fill : ask=4132.146
//   Akibat: risk 9.17, reward 0.23 -> R:R 1:0.026 -> rugi $91.52
//
// Pemeriksaan lama hanya "ask >= tp1" dan "ask <= sl" — keduanya lolos pada kasus
// itu. Fungsi ini menolak berdasarkan RASIO, bukan keberadaan harga.
// ============================================================================
bool ValidasiRRFill(const string side, const double fill, const double sl, const double tp,
                    double &riskOut, double &rewardOut, string &alasan,
                    const bool cekDrift = true)
{
   riskOut   = 0.0;
   rewardOut = 0.0;

   if(side == "LONG")
   {
      riskOut   = fill - sl;
      rewardOut = tp - fill;
   }
   else
   {
      riskOut   = sl - fill;
      rewardOut = fill - tp;
   }

   if(riskOut <= 0.0)
   {
      alasan = StringFormat("risk tidak valid (fill=%.3f sl=%.3f)", fill, sl);
      return false;
   }
   if(rewardOut <= 0.0)
   {
      alasan = StringFormat("harga sudah melewati TP (fill=%.3f tp=%.3f)", fill, tp);
      return false;
   }

   double rr = rewardOut / riskOut;

   // (a) Rasio minimum pada harga fill.
   if(rr < InpMinRR)
   {
      alasan = StringFormat("R:R pada fill = 1:%.3f < minimum 1:%.2f (risk %.2f, reward %.2f)",
                            rr, InpMinRR, riskOut, rewardOut);
      return false;
   }

   // (b) Harga sudah bergerak terlalu jauh menuju TP sebelum entry.
   //
   // PENTING: pemeriksaan ini HANYA bermakna pada mode ABSOLUT, yaitu ketika SL/TP
   // berasal dari snapshot harga API dan harga fill bisa sudah bergeser. Pada mode
   // RELATIF level dibangun DARI harga fill, sehingga `risk/(risk+reward)` selalu
   // sama dengan 1/(1+RR) - sebuah konstanta, bukan drift. Untuk RR 1.8 nilainya
   // 35.7%, yang tanpa syarat ini akan menolak SEMUA sinyal relatif (bug terukur
   // 24 Okt 2026: "harga sudah bergerak 36% menuju TP (batas 30%)").
   if(cekDrift)
   {
      double jarakTotal = riskOut + rewardOut;   // jarak SL->TP
      if(jarakTotal > 0.0 && (riskOut / jarakTotal) > InpMaxDriftFrac)
      {
         alasan = StringFormat("harga sudah bergerak %.0f%% menuju TP sebelum entry (batas %.0f%%)",
                               (riskOut / jarakTotal) * 100.0, InpMaxDriftFrac * 100.0);
         return false;
      }
   }

   return true;
}

double ExtractJsonDouble(string json, string key)
{
   string search = "\"" + key + "\":";
   int pos = StringFind(json, search);
   if(pos < 0)
   {
      search = "\"" + key + "\": ";
      pos = StringFind(json, search);
   }
   if(pos < 0) return 0.0;
   pos += StringLen(search);
   int end = StringFind(json, ",", pos);
   string closeBrace = ShortToString(125); int end2 = StringFind(json, closeBrace, pos);
   if(end < 0 || (end2 > 0 && end2 < end)) end = end2;
   if(end < 0) return 0.0;
   string val = StringSubstr(json, pos, end - pos);
   StringTrimLeft(val);
   StringTrimRight(val);
   return StringToDouble(val);
}
//+------------------------------------------------------------------+


//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Eksekusi WebRequest ke War Room & Buka Posisi                    |
//+------------------------------------------------------------------+
void FetchAndExecuteSignal()
{
   // Jeda setelah order gagal. Tanpa ini, saat pasar tutup (akhir pekan) EA
   // mencoba membuka order setiap 5 detik dan ditolak broker terus-menerus.
   if(InpFailCooldownSec > 0 && lastOrderFailTs > 0 &&
      (TimeCurrent() - lastOrderFailTs) < InpFailCooldownSec)
   {
      return;
   }

   char post[], result[];
   string headers;
   int timeout = InpHttpTimeoutMs;
   ResetLastError();

   int res = WebRequest("GET", InpApiUrl, "", timeout, post, result, headers);
   if(res == 200)
   {
      string jsonStr = CharArrayToString(result);
      // Parsing sederhana JSON respons War Room
      if(StringFind(jsonStr, "\"status\":\"OK\"") >= 0 || StringFind(jsonStr, "\"status\": \"OK\"") >= 0)
      {
         string side = ExtractJsonString(jsonStr, "side");
         double entry = ExtractJsonDouble(jsonStr, "entry");
         double sl = ExtractJsonDouble(jsonStr, "sl");
         double tp1 = ExtractJsonDouble(jsonStr, "tp1");

         // R4: mode relatif — engine hanya mengirim NIAT (side) + JARAK (risk/reward).
         // Level dihitung EA dari harga broker sendiri. Ini menutup selisih
         // futures (GC=F) vs spot (XAUUSDm) yang terukur $12,04 sementara jarak
         // SL strategi hanya $2,53.
         string levelsMode  = ExtractJsonString(jsonStr, "levels_mode");
         double jarakRisk   = ExtractJsonDouble(jsonStr, "risk");
         double jarakReward = ExtractJsonDouble(jsonStr, "reward");
         bool   modeRelatif = (levelsMode == "relative");

         // R2: tolak sinyal basi. Tanpa ini sinyal lama dieksekusi ke pasar yang
         // sudah bergerak — penyebab drift harga yang memperburuk R:R (lihat R1).
         double genAt = ExtractJsonDouble(jsonStr, "generated_at");
         if(InpMaxSignalAgeSec > 0 && genAt > 0.0)
         {
            long umurDetik = (long)TimeCurrent() - (long)genAt;
            if(umurDetik > InpMaxSignalAgeSec)
            {
               Print(" Sinyal DITOLAK (basi): umur ", umurDetik, " detik melebihi batas ",
                     InpMaxSignalAgeSec, " detik. Menunggu sinyal segar.");
               return;
            }
         }

         // Kunci anti-duplikat: pada mode relatif, entry/sl berubah tiap poll
         // (mengikuti harga broker). Pakai stempel waktu sinyal agar satu sinyal
         // hanya dieksekusi sekali, bukan berkali-kali saat harga bergerak.
         string signalId;
         if(modeRelatif && genAt > 0.0)
         {
            signalId = "G" + DoubleToString(genAt, 0) + "_" + side;
         }
         else
         {
            signalId = DoubleToString(entry, 2) + "_" + DoubleToString(sl, 2);
         }
         if(signalId == lastProcessedSignal) return; // Jangan ulangi sinyal yang sama

         long curSpread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
         if(curSpread > InpMaxSpreadPts)
         {
            Print(" Sinyal dilewati: Spread pasar saat ini (", curSpread, " pts) melebihi batas toleransi (", InpMaxSpreadPts, " pts). Melindungi dari slippage.");
            return;
         }

         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

         // R4: pada mode relatif, SUSUN LEVEL DARI HARGA BROKER.
         // Engine mengirim jarak (risk/reward) yang dihitung dari snapshot futures;
         // jaraknya tetap valid sebagai jarak, tetapi titik absolutnya tidak.
         // Karena itu entry memakai harga broker, lalu SL/TP diturunkan dari entry.
         if(modeRelatif)
         {
            if(jarakRisk <= 0.0 || jarakReward <= 0.0)
            {
               Print(" Sinyal DITOLAK (mode relatif): risk/reward tidak valid (risk=",
                     jarakRisk, " reward=", jarakReward, ").");
               return;
            }
            if(side == "LONG")
            {
               entry = ask;
               sl    = NormalizeDouble(entry - jarakRisk, _Digits);
               tp1   = NormalizeDouble(entry + jarakReward, _Digits);
            }
            else
            {
               entry = bid;
               sl    = NormalizeDouble(entry + jarakRisk, _Digits);
               tp1   = NormalizeDouble(entry - jarakReward, _Digits);
            }
            Print(" Level relatif dihitung dari broker: entry=", entry,
                  " SL=", sl, " TP=", tp1, " (risk=", jarakRisk, " reward=", jarakReward, ")");
         }

         // Proteksi Validasi Stops MT5:
         // Jika harga pasar (Ask/Bid) sudah melesat MELEWATI target TP atau SL,
         // jangan paksa masuk karena broker akan menolak [invalid stops] atau posisi langsung minus.
         if(side == "LONG")
         {
            if(ask >= tp1)
            {
               Print(" Sinyal LONG dilewati: Harga pasar saat ini (", ask, ") sudah berada di atas target TP (", tp1, "). Menunggu retest berikutnya.");
               return;
            }
            if(ask <= sl)
            {
               Print(" Sinyal LONG dilewati: Harga pasar saat ini (", ask, ") sudah menembus Stop Loss (", sl, "). Dibatalkan.");
               return;
            }

            // R1: validasi rasio pada harga fill SEBELUM order dikirim.
            double riskBuy = 0.0, rewardBuy = 0.0;
            string alasanBuy = "";
            if(!ValidasiRRFill("LONG", ask, sl, tp1, riskBuy, rewardBuy, alasanBuy, !modeRelatif))
            {
               Print(" Sinyal LONG DITOLAK (penjaga R:R): ", alasanBuy);
               return;
            }

            Print(" Sinyal War Room Diterima: BUY ", _Symbol, " Entry: ", ask, " SL: ", sl, " TP: ", tp1,
                  " | R:R pada fill = 1:", DoubleToString(rewardBuy / riskBuy, 2));
            double lotBuy = HitungLotRisiko(ask, sl);
            if(lotBuy <= 0.0)
            {
               Print(" Order BUY DIBATALKAN: sizing tidak menghasilkan lot yang aman.");
               return;
            }
            uint t0Buy = GetTickCount();
            if(trade.Buy(lotBuy, _Symbol, ask, sl, tp1, "WarRoom Signal"))
            {
               int latBuy = (int)(GetTickCount() - t0Buy);
               Print(" Order BUY Berhasil Dibuka! Ticket: ", trade.ResultOrder(),
                     " | fill: ", trade.ResultPrice(), " (diminta ", ask, ") | ", latBuy, " ms");
               LaporFill("BUY", lotBuy, ask, trade.ResultPrice(), sl, tp1,
                         SymbolInfoInteger(_Symbol, SYMBOL_SPREAD), latBuy,
                         trade.ResultRetcode(), HitungPosisiTerbuka());
               lastProcessedSignal = signalId;
            }
            else
            {
               Print(" Gagal Order BUY: ", trade.ResultRetcodeDescription());
               lastOrderFailTs = TimeCurrent();
            }
         }
         else if(side == "SHORT")
         {
            if(bid <= tp1)
            {
               Print(" Sinyal SHORT dilewati: Harga pasar saat ini (", bid, ") sudah berada di bawah target TP (", tp1, "). Menunggu retest berikutnya.");
               return;
            }
            if(bid >= sl)
            {
               Print(" Sinyal SHORT dilewati: Harga pasar saat ini (", bid, ") sudah menembus Stop Loss (", sl, "). Dibatalkan.");
               return;
            }

            // R1: validasi rasio pada harga fill SEBELUM order dikirim.
            double riskSell = 0.0, rewardSell = 0.0;
            string alasanSell = "";
            if(!ValidasiRRFill("SHORT", bid, sl, tp1, riskSell, rewardSell, alasanSell, !modeRelatif))
            {
               Print(" Sinyal SHORT DITOLAK (penjaga R:R): ", alasanSell);
               return;
            }

            Print(" Sinyal War Room Diterima: SELL ", _Symbol, " Entry: ", bid, " SL: ", sl, " TP: ", tp1,
                  " | R:R pada fill = 1:", DoubleToString(rewardSell / riskSell, 2));
            double lotSell = HitungLotRisiko(bid, sl);
            if(lotSell <= 0.0)
            {
               Print(" Order SELL DIBATALKAN: sizing tidak menghasilkan lot yang aman.");
               return;
            }
            uint t0Sell = GetTickCount();
            if(trade.Sell(lotSell, _Symbol, bid, sl, tp1, "WarRoom Signal"))
            {
               int latSell = (int)(GetTickCount() - t0Sell);
               Print(" Order SELL Berhasil Dibuka! Ticket: ", trade.ResultOrder(),
                     " | fill: ", trade.ResultPrice(), " (diminta ", bid, ") | ", latSell, " ms");
               LaporFill("SELL", lotSell, bid, trade.ResultPrice(), sl, tp1,
                         SymbolInfoInteger(_Symbol, SYMBOL_SPREAD), latSell,
                         trade.ResultRetcode(), HitungPosisiTerbuka());
               lastProcessedSignal = signalId;
            }
            else
            {
               Print(" Gagal Order SELL: ", trade.ResultRetcodeDescription());
               lastOrderFailTs = TimeCurrent();
            }
         }
      }
   }
}

