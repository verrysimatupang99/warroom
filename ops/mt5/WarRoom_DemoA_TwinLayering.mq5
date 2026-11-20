//+------------------------------------------------------------------+
//|                                   WarRoom_DemoA_TwinLayering.mq5 |
//|   Demo-1 (#434446792, Exness Standard USD):                      |
//|   Twin-Order Layering (0.01 Scalp + 0.01 Runner + BE + ATR Trail)|
//|   Terintegrasi penuh dengan War Room /mt5/telemetry & /mt5/deal  |
//+------------------------------------------------------------------+
#property copyright "War Room"
#property version   "1.00"
#property strict
#include <Trade\Trade.mqh>

input group "=== KONEKSI WAR ROOM ==="
input string InpApiBase         = "https://polywarroom.vps.webdock.cloud";
input string InpToken           = ""; // WARROOM_EA_SYNC_TOKEN
input int    InpTelemetrySec    = 5;
input string InpStrategyVersion = "demoA-twin-layering-v1";

input group "=== ATURAN TWIN-ORDER LAYERING ==="
input ulong  InpMagic           = 434446;
input double InpLotLeg          = 0.01;  // 0.01 Scalp + 0.01 Runner = 0.02 total
input int    InpBreakoutBars    = 8;     // Breakout N bar M15
input double InpSlAtrMult       = 1.6;
input double InpMinSlUsd        = 3.5;
input double InpMaxSlUsd        = 8.0;
input double InpScalpRR         = 1.0;
input double InpRunnerRR        = 3.0;
input double InpTrailAtrMult    = 1.5;
input int    InpMaxSpreadPts    = 350;   // 350 pts ($0.35 pada 3 digit)

input group "=== SESI & PENJAGA RISIKO ==="
input bool   InpAllowMonday     = true;
input int    InpLondonStartHr   = 8;     // UTC / jam server
input int    InpLondonEndHr     = 9;
input int    InpNyStartHr       = 13;
input int    InpNyEndHr         = 14;
input double InpDailyMaxLossUsd = 30.0;  // Stop harian -3% pada $1.000

CTrade   g_trade;
int      g_hEmaFast = INVALID_HANDLE;
int      g_hEmaSlow = INVALID_HANDLE;
int      g_hAtr     = INVALID_HANDLE;
int      g_hRsi     = INVALID_HANDLE;
datetime g_lastBar  = 0;
datetime g_lastTel  = 0;
ulong    g_sentDeals[];

bool SudahKirim(const ulong t) {
   for(int i=0; i<ArraySize(g_sentDeals); i++) if(g_sentDeals[i]==t) return true;
   return false;
}
void TandaiKirim(const ulong t) {
   int n = ArraySize(g_sentDeals);
   if(n >= 1000) { ArrayRemove(g_sentDeals, 0, 1); n--; }
   ArrayResize(g_sentDeals, n+1); g_sentDeals[n] = t;
}
double FaktorAkun() {
   string cur = AccountInfoString(ACCOUNT_CURRENCY);
   return (cur == "USC" || cur == "EUC") ? 0.01 : 1.0;
}
bool KirimJson(const string path, const string json) {
   if(InpToken == "") return false;
   char data[], res[];
   string hdr = "Content-Type: application/json\r\nX-Warroom-Token: " + InpToken + "\r\n";
   int len = StringLen(json);
   ArrayResize(data, len);
   StringToCharArray(json, data, 0, len, CP_UTF8);
   string resHdr;
   ResetLastError();
   int code = WebRequest("POST", InpApiBase + path, hdr, 8000, data, res, resHdr);
   return (code == 200);
}

int CountMyPositions(ulong &tickets[], string &comments[]) {
   ArrayResize(tickets, 0);
   ArrayResize(comments, 0);
   int cnt = 0;
   for(int i=0; i<PositionsTotal(); i++) {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      ArrayResize(tickets, cnt+1);
      ArrayResize(comments, cnt+1);
      tickets[cnt] = tk;
      comments[cnt] = PositionGetString(POSITION_COMMENT);
      cnt++;
   }
   return cnt;
}

double TodayRealizedPnl() {
   datetime start = (datetime)((long)TimeCurrent() - ((long)TimeCurrent() % 86400));
   double pnl = 0.0;
   if(!HistorySelect(start, TimeCurrent() + 60)) return 0.0;
   for(int i=0; i<HistoryDealsTotal(); i++) {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0 || HistoryDealGetInteger(t, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      if(HistoryDealGetInteger(t, DEAL_MAGIC) != (long)InpMagic) continue;
      pnl += HistoryDealGetDouble(t, DEAL_PROFIT) + HistoryDealGetDouble(t, DEAL_SWAP) + HistoryDealGetDouble(t, DEAL_COMMISSION);
   }
   return pnl * FaktorAkun();
}

void ManageOpenTwin(const double atrVal) {
   ulong tks[]; string cmts[];
   int n = CountMyPositions(tks, cmts);
   if(n == 0) return;
   bool scalpStillOpen = false;
   for(int i=0; i<n; i++) if(StringFind(cmts[i], "SCALP") >= 0) scalpStillOpen = true;
   double spreadPx = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));

   for(int i=0; i<n; i++) {
      if(!PositionSelectByTicket(tks[i])) continue;
      if(StringFind(cmts[i], "RUNNER") < 0) continue;
      if(scalpStillOpen) continue; // Tunggu leg Scalp TP dulu sebelum lock BE + trail Runner

      long typ = PositionGetInteger(POSITION_TYPE);
      double openPx = PositionGetDouble(POSITION_PRICE_OPEN);
      double curSl  = PositionGetDouble(POSITION_SL);
      double curTp  = PositionGetDouble(POSITION_TP);
      double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      if(typ == POSITION_TYPE_BUY) {
         double beSl = NormalizeDouble(openPx + spreadPx * 1.2, _Digits);
         double trailSl = NormalizeDouble(bid - atrVal * InpTrailAtrMult, _Digits);
         double bestSl = MathMax(beSl, trailSl);
         if(bestSl < bid && bestSl > curSl + _Point * 10)
            g_trade.PositionModify(tks[i], bestSl, curTp);
      } else {
         double beSl = NormalizeDouble(openPx - spreadPx * 1.2, _Digits);
         double trailSl = NormalizeDouble(ask + atrVal * InpTrailAtrMult, _Digits);
         double bestSl = (curSl == 0.0) ? beSl : MathMin(beSl, trailSl);
         if(bestSl > ask && (curSl == 0.0 || bestSl < curSl - _Point * 10))
            g_trade.PositionModify(tks[i], bestSl, curTp);
      }
   }
}

bool InActiveSession() {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(!InpAllowMonday && dt.day_of_week == 1) return false;
   bool inLon = (dt.hour >= InpLondonStartHr && dt.hour <= InpLondonEndHr);
   bool inNy  = (dt.hour >= InpNyStartHr && dt.hour <= InpNyEndHr);
   return (inLon || inNy);
}

void SendTelemetryAndDeals(const bool sesiOk, const string alasan, const double atr, const double rsi, const double eFast, const double eSlow) {
   datetime now = TimeCurrent();
   if(now - g_lastTel < InpTelemetrySec) return;
   g_lastTel = now;

   double f = FaktorAkun();
   string posOut = "";
   int pTotal = PositionsTotal();
   for(int i=0; i<pTotal; i++) {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      long tp = PositionGetInteger(POSITION_TYPE);
      if(StringLen(posOut) > 0) posOut += ",";
      posOut += StringFormat(
         "{\"ticket\":%s,\"symbol\":\"%s\",\"side\":\"%s\",\"volume\":%.2f,\"open_price\":%.5f,\"sl\":%.5f,\"tp\":%.5f,\"pnl_usd\":%.2f}",
         IntegerToString((long)tk), sym, (tp==POSITION_TYPE_BUY?"BUY":"SELL"),
         PositionGetDouble(POSITION_VOLUME), PositionGetDouble(POSITION_PRICE_OPEN),
         PositionGetDouble(POSITION_SL), PositionGetDouble(POSITION_TP),
         (PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP)) * f
      );
   }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int spPts = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   string tren = (eFast > eSlow) ? "BULLISH" : "BEARISH";
   string json = StringFormat(
      "{\"account\":\"%s\",\"broker\":\"%s\",\"currency\":\"%s\",\"cent_factor\":%.2f,"
      "\"balance\":%.2f,\"equity\":%.2f,\"floating_pnl\":%.2f,\"margin\":%.2f,\"free_margin\":%.2f,"
      "\"positions\":[%s],\"pending_orders\":[],\"bid\":%.5f,\"ask\":%.5f,\"spread_pts\":%d,\"digits\":%d,"
      "\"atr_m5\":%.3f,\"ema9_m5\":%.3f,\"ema21_m5\":%.3f,\"eval_at\":%s,\"eval_alasan\":\"%s\","
      "\"eval_sesi\":%s,\"eval_atr\":%.3f,\"eval_spread\":%.3f,\"eval_rsi\":%.2f,\"eval_ema_fast\":%.3f,\"eval_ema_slow\":%.3f,\"eval_tren\":\"%s\",\"server_time\":%s}",
      IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)), AccountInfoString(ACCOUNT_COMPANY), AccountInfoString(ACCOUNT_CURRENCY), f,
      AccountInfoDouble(ACCOUNT_BALANCE)*f, AccountInfoDouble(ACCOUNT_EQUITY)*f, AccountInfoDouble(ACCOUNT_PROFIT)*f,
      AccountInfoDouble(ACCOUNT_MARGIN)*f, AccountInfoDouble(ACCOUNT_MARGIN_FREE)*f, posOut,
      bid, ask, spPts, _Digits, atr, eFast, eSlow, IntegerToString((long)now), alasan,
      (sesiOk ? "true" : "false"), atr, (ask - bid), rsi, eFast, eSlow, tren, IntegerToString((long)now)
   );
   KirimJson("/api/v1/tencent/mt5/telemetry", json);

   if(HistorySelect(now - 86400, now + 60)) {
      for(int i=0; i<HistoryDealsTotal(); i++) {
         ulong dt = HistoryDealGetTicket(i);
         if(dt == 0 || SudahKirim(dt) || HistoryDealGetInteger(dt, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
         long tp = HistoryDealGetInteger(dt, DEAL_TYPE);
         string dJson = StringFormat(
            "{\"ticket\":%s,\"position\":%s,\"symbol\":\"%s\",\"side\":\"%s\",\"volume\":%.2f,\"close_time\":\"%s\","
            "\"close_price\":%.5f,\"profit\":%.2f,\"swap\":%.2f,\"commission\":%.2f,\"magic\":%s,\"comment\":\"%s\",\"account\":\"%s\",\"strategy_version\":\"%s\"}",
            IntegerToString((long)dt), IntegerToString(HistoryDealGetInteger(dt, DEAL_POSITION_ID)),
            HistoryDealGetString(dt, DEAL_SYMBOL), (tp==DEAL_TYPE_BUY?"BUY":"SELL"),
            HistoryDealGetDouble(dt, DEAL_VOLUME), TimeToString((datetime)HistoryDealGetInteger(dt, DEAL_TIME), TIME_DATE|TIME_SECONDS),
            HistoryDealGetDouble(dt, DEAL_PRICE), HistoryDealGetDouble(dt, DEAL_PROFIT)*f, HistoryDealGetDouble(dt, DEAL_SWAP)*f,
            HistoryDealGetDouble(dt, DEAL_COMMISSION)*f, IntegerToString(HistoryDealGetInteger(dt, DEAL_MAGIC)),
            HistoryDealGetString(dt, DEAL_COMMENT), IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)), InpStrategyVersion
         );
         if(KirimJson("/api/v1/tencent/mt5/deal", dJson)) TandaiKirim(dt);
      }
   }
}

int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_hEmaFast = iMA(_Symbol, PERIOD_M15, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaSlow = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   g_hAtr     = iATR(_Symbol, PERIOD_M15, 14);
   g_hRsi     = iRSI(_Symbol, PERIOD_M15, 14, PRICE_CLOSE);
   if(g_hEmaFast==INVALID_HANDLE || g_hEmaSlow==INVALID_HANDLE || g_hAtr==INVALID_HANDLE || g_hRsi==INVALID_HANDLE)
      return INIT_FAILED;
   EventSetTimer(InpTelemetrySec);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   IndicatorRelease(g_hEmaFast);
   IndicatorRelease(g_hEmaSlow);
   IndicatorRelease(g_hAtr);
   IndicatorRelease(g_hRsi);
}

void EvaluateAndTrade() {
   double eFast[2], eSlow[2], atr[2], rsi[2];
   if(CopyBuffer(g_hEmaFast, 0, 1, 2, eFast) < 2) return;
   if(CopyBuffer(g_hEmaSlow, 0, 1, 2, eSlow) < 2) return;
   if(CopyBuffer(g_hAtr, 0, 1, 2, atr) < 2) return;
   if(CopyBuffer(g_hRsi, 0, 1, 2, rsi) < 2) return;

   double atrVal = atr[1];
   ManageOpenTwin(atrVal);

   bool sesiOk = InActiveSession();
   string alasan = "MENUNGGU_SETUP";
   ulong tks[]; string cmts[];
   int openCnt = CountMyPositions(tks, cmts);

   if(openCnt > 0) {
      alasan = "POSISI_AKTIF";
   } else if(!sesiOk) {
      alasan = "DI_LUAR_SESI";
   } else if(TodayRealizedPnl() <= -InpDailyMaxLossUsd) {
      alasan = "DAILY_MAX_LOSS_TERCAPAI";
   } else if((int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPts) {
      alasan = "SPREAD_MELEBIHI_BATAS";
   } else if(atrVal < 2.0 || atrVal > 15.0) {
      alasan = "ATR_DI_LUAR_RENTANG";
   } else {
      datetime barTime = iTime(_Symbol, PERIOD_M15, 0);
      if(barTime != g_lastBar) {
         g_lastBar = barTime;
         double prevClose = iClose(_Symbol, PERIOD_M15, 1);
         double hiN = iHigh(_Symbol, PERIOD_M15, iHighest(_Symbol, PERIOD_M15, MODE_HIGH, InpBreakoutBars, 2));
         double loN = iLow(_Symbol, PERIOD_M15, iLowest(_Symbol, PERIOD_M15, MODE_LOW, InpBreakoutBars, 2));
         double slDist = MathMin(MathMax(atrVal * InpSlAtrMult, InpMinSlUsd), InpMaxSlUsd);

         if(eFast[1] > eSlow[1] && prevClose > hiN && rsi[1] <= 70.0) {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            double sl  = NormalizeDouble(ask - slDist, _Digits);
            double tp1 = NormalizeDouble(ask + slDist * InpScalpRR, _Digits);
            double tp2 = NormalizeDouble(ask + slDist * InpRunnerRR, _Digits);
            g_trade.Buy(InpLotLeg, _Symbol, ask, sl, tp1, "TWIN_SCALP");
            g_trade.Buy(InpLotLeg, _Symbol, ask, sl, tp2, "TWIN_RUNNER");
            alasan = "ENTRY_BUY_TWIN";
         } else if(eFast[1] < eSlow[1] && prevClose < loN && rsi[1] >= 30.0) {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            double sl  = NormalizeDouble(bid + slDist, _Digits);
            double tp1 = NormalizeDouble(bid - slDist * InpScalpRR, _Digits);
            double tp2 = NormalizeDouble(bid - slDist * InpRunnerRR, _Digits);
            g_trade.Sell(InpLotLeg, _Symbol, bid, sl, tp1, "TWIN_SCALP");
            g_trade.Sell(InpLotLeg, _Symbol, bid, sl, tp2, "TWIN_RUNNER");
            alasan = "ENTRY_SELL_TWIN";
         }
      }
   }
   SendTelemetryAndDeals(sesiOk, alasan, atrVal, rsi[1], eFast[1], eSlow[1]);
}

void OnTick()  { EvaluateAndTrade(); }
void OnTimer() { EvaluateAndTrade(); }
