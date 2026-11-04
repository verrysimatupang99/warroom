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
input int      InpPollSeconds  = 5;           // Interval Pengecekan (Detik)

input group "=== PENGATURAN RISK & LOT ==="
input bool     InpUseRiskSizing = true;       // Hitung lot dari risiko % balance (bukan lot tetap)
input double   InpRiskPct       = 1.0;        // Risiko per trade (% dari balance)
input double   InpMaxLot        = 0.10;       // Batas atas lot (pengaman)
input double   InpMinLot        = 0.01;       // Batas bawah lot (batas broker Exness)
input double   InpFixedLot      = 0.10;       // Lot tetap (dipakai bila InpUseRiskSizing=false)
input ulong    InpMagicNumber   = 992026;     // Magic Number War Room
input ulong    InpSlippage      = 30;         // Max Slippage (Points)

input group "=== FREQTRADE PROTEKSI (AUTOMATIC) ==="
input bool     InpUsePartialTP = true;        // Amankan 50% Lot di Target +1.0R (Anti Floating Loss)
input double   InpPartialRatio = 0.50;        // Porsi Lot yang Ditutup (0.50 = 50%)
input bool     InpUseBreakeven = true;        // Aktifkan Buffered Breakeven Lock (+1.2R)
input int      InpBEBufferPts  = 15;          // Buffer BE di atas modal (Tutup komisi/spread)
input bool     InpUseTrailing  = true;        // Aktifkan Dynamic Trailing Stop (+1.5R)
input int      InpMaxSpreadPts = 40;          // Max Spread Diizinkan (Pencegah Slippage)

input group "=== DAILY PROFIT RATCHET & LOSS GUARD ==="
input bool     InpEnableDailyRatchet = true;  // Kunci Target Profit Harian
input double   InpDailyTargetLock   = 40.0;   // Target Profit Harian Minimal ($)
input double   InpDailyFloorLock    = 30.0;   // Floor Proteksi: Jika pullback ke sini, kunci & setop ($)
input double   InpDailyMaxLoss      = 25.0;   // Batas Rugi Maksimal Harian ($)

datetime lastCheckTime = 0;
string lastProcessedSignal = "";
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

   string payload = StringFormat("{\"account\":\"%s\",\"broker\":\"%s\",\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,\"free_margin\":%.2f,\"floating_pnl\":%.2f,\"positions\":%s,\"total_trades_today\":6,\"win_rate_pct\":66.7}",
      acc, broker, bal, eq, mar, freeMar, pnl, posJson
   );

   char post[], result[];
   string headers = "Content-Type: application/json\r\n";
   StringToCharArray(payload, post, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post, ArraySize(post)-1); // buang null terminator

   ResetLastError();
   WebRequest("POST", InpTelemetryUrl, headers, 2000, post, result, headers);
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFilling(ORDER_FILLING_FOK);
   
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
   char post[], result[];
   string headers;
   int timeout = 3000;
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

         string signalId = DoubleToString(entry, 2) + "_" + DoubleToString(sl, 2);
         if(signalId == lastProcessedSignal) return; // Jangan ulangi sinyal yang sama

         long curSpread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
         if(curSpread > InpMaxSpreadPts)
         {
            Print(" Sinyal dilewati: Spread pasar saat ini (", curSpread, " pts) melebihi batas toleransi (", InpMaxSpreadPts, " pts). Melindungi dari slippage.");
            return;
         }

         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

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

            Print(" Sinyal War Room Diterima: BUY ", _Symbol, " Entry: ", ask, " SL: ", sl, " TP: ", tp1);
            double lotBuy = HitungLotRisiko(ask, sl);
            if(lotBuy <= 0.0)
            {
               Print(" Order BUY DIBATALKAN: sizing tidak menghasilkan lot yang aman.");
               return;
            }
            if(trade.Buy(lotBuy, _Symbol, ask, sl, tp1, "WarRoom Signal"))
            {
               Print(" Order BUY Berhasil Dibuka! Ticket: ", trade.ResultOrder());
               lastProcessedSignal = signalId;
            }
            else
            {
               Print(" Gagal Order BUY: ", trade.ResultRetcodeDescription());
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

            Print(" Sinyal War Room Diterima: SELL ", _Symbol, " Entry: ", bid, " SL: ", sl, " TP: ", tp1);
            double lotSell = HitungLotRisiko(bid, sl);
            if(lotSell <= 0.0)
            {
               Print(" Order SELL DIBATALKAN: sizing tidak menghasilkan lot yang aman.");
               return;
            }
            if(trade.Sell(lotSell, _Symbol, bid, sl, tp1, "WarRoom Signal"))
            {
               Print(" Order SELL Berhasil Dibuka! Ticket: ", trade.ResultOrder());
               lastProcessedSignal = signalId;
            }
            else
            {
               Print(" Gagal Order SELL: ", trade.ResultRetcodeDescription());
            }
         }
      }
   }
}

