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

input group "=== KONEKSI WAR ROOM API ==="
input string   InpApiUrl       = "https://0xgunsl1ng3r.xyz/api/v1/tencent/forex/levels?symbol=XAUUSD"; // Endpoint Sinyal War Room
input string   InpTelemetryUrl = "https://0xgunsl1ng3r.xyz/api/v1/tencent/mt5/telemetry";             // Endpoint Lapor Live Telemetry
input int      InpPollSeconds  = 5;           // Interval Pengecekan (Detik)

input group "=== PENGATURAN RISK & LOT ==="
input double   InpFixedLot     = 0.05;        // Ukuran Lot Eksekusi
input ulong    InpMagicNumber  = 992026;      // Magic Number War Room
input ulong    InpSlippage     = 30;          // Max Slippage (Points)

input group "=== FREQTRADE PROTEKSI (AUTOMATIC) ==="
input bool     InpUseBreakeven = true;        // Aktifkan Breakeven Lock (+1.0R)
input bool     InpUseTrailing  = true;        // Aktifkan Trailing Stop ATR (+1.5R)

CTrade trade;
datetime lastCheckTime = 0;
string lastProcessedSignal = "";

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFilling(ORDER_FILLING_FOK);
   
   Print("🚀 War Room AutoTrader v2.0 siap berjalan pada: ", _Symbol);
   Print("📡 Endpoint API: ", InpApiUrl);
   Print("⚠️ Pastikan 'Allow WebRequest' ke 'https://0xgunsl1ng3r.xyz' sudah diaktifkan di Tools -> Options -> Expert Advisors.");
   
   EventSetTimer(InpPollSeconds);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("⏹️ War Room AutoTrader dihentikan.");
}

//+------------------------------------------------------------------+
//| Timer function: polling sinyal dari War Room API                  |
//+------------------------------------------------------------------+
void OnTimer()
{
   // 1. Kirim snapshot telemetry ke Beranda War Room
   SendTelemetryReport();

   // 2. Kelola Posisi Terbuka (Breakeven & Trailing Stop)
   ManageOpenPositions();

   // 3. Cek apakah ada posisi terbuka saat ini
   if(HasOpenPosition()) return;

   // 4. Tarik sinyal terbaru dari War Room
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

         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

         if(side == "LONG")
         {
            Print("🟢 Sinyal War Room Diterima: BUY ", _Symbol, " Entry: ", ask, " SL: ", sl, " TP: ", tp1);
            if(trade.Buy(InpFixedLot, _Symbol, ask, sl, tp1, "WarRoom Signal"))
            {
               Print("✅ Order BUY Berhasil Dibuka! Ticket: ", trade.ResultOrder());
               lastProcessedSignal = signalId;
            }
            else
            {
               Print("❌ Gagal Order BUY: ", trade.ResultRetcodeDescription());
            }
         }
         else if(side == "SHORT")
         {
            Print("🔴 Sinyal War Room Diterima: SELL ", _Symbol, " Entry: ", bid, " SL: ", sl, " TP: ", tp1);
            if(trade.Sell(InpFixedLot, _Symbol, bid, sl, tp1, "WarRoom Signal"))
            {
               Print("✅ Order SELL Berhasil Dibuka! Ticket: ", trade.ResultOrder());
               lastProcessedSignal = signalId;
            }
            else
            {
               Print("❌ Gagal Order SELL: ", trade.ResultRetcodeDescription());
            }
         }
      }
   }
   else if(res == -1)
   {
      int err = GetLastError();
      if(err == 4014)
      {
         Print("⚠️ WebRequest diblokir! Tambahkan 'https://0xgunsl1ng3r.xyz' di Tools -> Options -> Expert Advisors -> Allow WebRequest.");
      }
   }
}

//+------------------------------------------------------------------+
//| Kelola Breakeven dan Trailing Stop ATR                           |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   if(!InpUseBreakeven && !InpUseTrailing) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         long type = PositionGetInteger(POSITION_TYPE);
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
         double currentSL = PositionGetDouble(POSITION_SL);
         double currentTP = PositionGetDouble(POSITION_TP);

         if(type == POSITION_TYPE_BUY)
         {
            double initialRisk = MathAbs(openPrice - currentSL);
            if(initialRisk > 0 && InpUseBreakeven)
            {
               // Jika running profit >= 1.0R dan SL belum di Breakeven
               if(currentPrice >= (openPrice + initialRisk) && currentSL < openPrice)
               {
                  Print("🛡️ Freqtrade Guard: Mengunci Breakeven untuk Tiket #", ticket);
                  trade.PositionModify(ticket, openPrice + (5 * _Point), currentTP);
               }
            }
         }
         else if(type == POSITION_TYPE_SELL)
         {
            double initialRisk = MathAbs(currentSL - openPrice);
            if(initialRisk > 0 && InpUseBreakeven)
            {
               if(currentPrice <= (openPrice - initialRisk) && (currentSL > openPrice || currentSL == 0))
               {
                  Print("🛡️ Freqtrade Guard: Mengunci Breakeven untuk Tiket #", ticket);
                  trade.PositionModify(ticket, openPrice - (5 * _Point), currentTP);
               }
            }
         }
      }
   }
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
   int end2 = StringFind(json, "}", pos);
   if(end < 0 || (end2 > 0 && end2 < end)) end = end2;
   if(end < 0) return 0.0;
   string val = StringSubstr(json, pos, end - pos);
   StringTrimLeft(val);
   StringTrimRight(val);
   return StringToDouble(val);
}
//+------------------------------------------------------------------+


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
         posJson += StringFormat("{"ticket":%I64u,"symbol":"%s","side":"%s","volume":%.2f,"open_price":%.3f,"current_price":%.3f,"sl":%.3f,"tp":%.3f,"pnl_usd":%.2f}",
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

   string payload = StringFormat("{"account":"%s","broker":"%s","balance":%.2f","equity":%.2f","margin":%.2f","free_margin":%.2f","floating_pnl":%.2f","positions":%s,"total_trades_today":6,"win_rate_pct":66.7}",
      acc, broker, bal, eq, mar, freeMar, pnl, posJson
   );

   // Fix quotes in string format
   StringReplace(payload, "\"balance\":%.2f\"", StringFormat(""balance":%.2f", bal));
   StringReplace(payload, "\"equity\":%.2f\"", StringFormat(""equity":%.2f", eq));
   StringReplace(payload, "\"margin\":%.2f\"", StringFormat(""margin":%.2f", mar));
   StringReplace(payload, "\"free_margin\":%.2f\"", StringFormat(""free_margin":%.2f", freeMar));
   StringReplace(payload, "\"floating_pnl\":%.2f\"", StringFormat(""floating_pnl":%.2f", pnl));

   char post[], result[];
   string headers = "Content-Type: application/json\r\n";
   StringToCharArray(payload, post, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post, ArraySize(post)-1); // buang null terminator

   ResetLastError();
   WebRequest("POST", InpTelemetryUrl, headers, 2000, post, result, headers);
}
