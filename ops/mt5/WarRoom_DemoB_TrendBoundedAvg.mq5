//+------------------------------------------------------------------+
//|                                WarRoom_DemoB_TrendBoundedAvg.mq5 |
//|   Demo-2 (#464202979, Exness Standard USD):                      |
//|   Trend-Filtered Bounded Averaging (EMA200 + RSI Pullback)       |
//|   Flat 0.01 lot | Step max($15, 2.2*ATR) | Max 4 layer           |
//|   Basket TP +$12 | HARD Basket SL -$45 (NO MARTINGALE!)          |
//+------------------------------------------------------------------+
#property copyright "War Room"
#property version   "1.00"
#property strict
#include <Trade\Trade.mqh>

input group "=== KONEKSI WAR ROOM ==="
input string InpApiBase         = "https://polywarroom.vps.webdock.cloud";
input string InpToken           = ""; // WARROOM_EA_SYNC_TOKEN
input int    InpTelemetrySec    = 5;
input string InpStrategyVersion = "demoB-trend-bounded-avg-v1";

input group "=== ATURAN BOUNDED AVERAGING ==="
input ulong  InpMagic           = 464202;
input double InpFixedLot        = 0.01;  // FLAT, DILARANG MARTINGALE
input int    InpMaxLayers       = 4;
input double InpMinStepUsd      = 15.0;  // Jarak minimal antar layer ($)
input double InpStepAtrMult     = 2.2;
input double InpBasketTpUsd     = 12.0;  // Tutup seluruh basket saat floating >= +$12
input double InpHardBasketSlUsd = 45.0;  // WAJIB: tutup seluruh basket saat floating <= -$45
input double InpRsiLow          = 30.0;
input double InpRsiHigh         = 70.0;
input int    InpRolloverStartHr = 20;    // Hindari rollover spread lebar
input int    InpMaxSpreadPts    = 350;
input double InpDailyMaxLossUsd = 45.0;

CTrade   g_trade;
int      g_hEma200  = INVALID_HANDLE;
int      g_hAtr     = INVALID_HANDLE;
int      g_hRsi     = INVALID_HANDLE;
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

int BasketStats(double &totalPnlUsd, long &sideOut, double &lastOpenPx) {
   totalPnlUsd = 0.0;
   sideOut = -1;
   lastOpenPx = 0.0;
   datetime latestTime = 0;
   int cnt = 0;
   for(int i=0; i<PositionsTotal(); i++) {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      totalPnlUsd += (PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP)) * FaktorAkun();
      sideOut = PositionGetInteger(POSITION_TYPE);
      datetime ot = (datetime)PositionGetInteger(POSITION_TIME);
      if(ot >= latestTime) {
         latestTime = ot;
         lastOpenPx = PositionGetDouble(POSITION_PRICE_OPEN);
      }
      cnt++;
   }
   return cnt;
}

void CloseAllBasket() {
   for(int i=PositionsTotal()-1; i>=0; i--) {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      g_trade.PositionClose(tk);
   }
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

void SendTelemetryAndDeals(const bool sesiOk, const string alasan, const double atr, const double rsi, const double ema200) {
   datetime now = TimeCurrent();
   if(now - g_lastTel < InpTelemetrySec) return;
   g_lastTel = now;

   double f = FaktorAkun();
   string posOut = "";
   for(int i=0; i<PositionsTotal(); i++) {
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
   string tren = (bid >= ema200) ? "BULLISH" : "BEARISH";
   string json = StringFormat(
      "{\"account\":\"%s\",\"broker\":\"%s\",\"currency\":\"%s\",\"cent_factor\":%.2f,"
      "\"balance\":%.2f,\"equity\":%.2f,\"floating_pnl\":%.2f,\"margin\":%.2f,\"free_margin\":%.2f,"
      "\"positions\":[%s],\"pending_orders\":[],\"bid\":%.5f,\"ask\":%.5f,\"spread_pts\":%d,\"digits\":%d,"
      "\"atr_m5\":%.3f,\"ema9_m5\":%.3f,\"ema21_m5\":%.3f,\"eval_at\":%s,\"eval_alasan\":\"%s\","
      "\"eval_sesi\":%s,\"eval_atr\":%.3f,\"eval_spread\":%.3f,\"eval_rsi\":%.2f,\"eval_ema_fast\":%.3f,\"eval_ema_slow\":%.3f,\"eval_tren\":\"%s\",\"server_time\":%s}",
      IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)), AccountInfoString(ACCOUNT_COMPANY), AccountInfoString(ACCOUNT_CURRENCY), f,
      AccountInfoDouble(ACCOUNT_BALANCE)*f, AccountInfoDouble(ACCOUNT_EQUITY)*f, AccountInfoDouble(ACCOUNT_PROFIT)*f,
      AccountInfoDouble(ACCOUNT_MARGIN)*f, AccountInfoDouble(ACCOUNT_MARGIN_FREE)*f, posOut,
      bid, ask, spPts, _Digits, atr, bid, ema200, IntegerToString((long)now), alasan,
      (sesiOk ? "true" : "false"), atr, (ask - bid), rsi, bid, ema200, tren, IntegerToString((long)now)
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
   g_hEma200 = iMA(_Symbol, PERIOD_M15, 200, 0, MODE_EMA, PRICE_CLOSE);
   g_hAtr    = iATR(_Symbol, PERIOD_M15, 14);
   g_hRsi    = iRSI(_Symbol, PERIOD_M15, 14, PRICE_CLOSE);
   if(g_hEma200==INVALID_HANDLE || g_hAtr==INVALID_HANDLE || g_hRsi==INVALID_HANDLE)
      return INIT_FAILED;
   EventSetTimer(InpTelemetrySec);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
   EventKillTimer();
   IndicatorRelease(g_hEma200);
   IndicatorRelease(g_hAtr);
   IndicatorRelease(g_hRsi);
}

void EvaluateAndTrade() {
   double ema200[2], atr[2], rsi[2];
   if(CopyBuffer(g_hEma200, 0, 1, 2, ema200) < 2) return;
   if(CopyBuffer(g_hAtr, 0, 1, 2, atr) < 2) return;
   if(CopyBuffer(g_hRsi, 0, 1, 2, rsi) < 2) return;

   double basketPnl = 0.0, lastPx = 0.0;
   long side = -1;
   int layers = BasketStats(basketPnl, side, lastPx);
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   bool sesiOk = (dt.hour < InpRolloverStartHr);
   string alasan = "MENUNGGU_PULLBACK";

   if(layers > 0) {
      if(basketPnl <= -InpHardBasketSlUsd) {
         CloseAllBasket();
         alasan = "HARD_BASKET_SL_TERPICU";
      } else if(basketPnl >= InpBasketTpUsd) {
         CloseAllBasket();
         alasan = "BASKET_TP_TERCAPAI";
      } else if(layers < InpMaxLayers && (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) <= InpMaxSpreadPts) {
         double step = MathMax(InpMinStepUsd, InpStepAtrMult * atr[1]);
         double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         if(side == POSITION_TYPE_BUY && (lastPx - ask) >= step) {
            g_trade.Buy(InpFixedLot, _Symbol, ask, 0.0, 0.0, StringFormat("AVG_L%d", layers + 1));
            alasan = "AVG_ADD_BUY";
         } else if(side == POSITION_TYPE_SELL && (bid - lastPx) >= step) {
            g_trade.Sell(InpFixedLot, _Symbol, bid, 0.0, 0.0, StringFormat("AVG_L%d", layers + 1));
            alasan = "AVG_ADD_SELL";
         } else {
            alasan = StringFormat("BASKET_AKTIF_%dL", layers);
         }
      } else {
         alasan = StringFormat("BASKET_MAX_%dL", layers);
      }
   } else {
      if(!sesiOk) {
         alasan = "DI_LUAR_SESI_ROLLOVER";
      } else if(TodayRealizedPnl() <= -InpDailyMaxLossUsd) {
         alasan = "DAILY_MAX_LOSS_TERCAPAI";
      } else if((int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpreadPts) {
         alasan = "SPREAD_MELEBIHI_BATAS";
      } else {
         double prevClose = iClose(_Symbol, PERIOD_M15, 1);
         if(prevClose > ema200[1] && rsi[1] <= InpRsiLow) {
            double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
            g_trade.Buy(InpFixedLot, _Symbol, ask, 0.0, 0.0, "AVG_L1");
            alasan = "ENTRY_BUY_PULLBACK_EMA200";
         } else if(prevClose < ema200[1] && rsi[1] >= InpRsiHigh) {
            double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
            g_trade.Sell(InpFixedLot, _Symbol, bid, 0.0, 0.0, "AVG_L1");
            alasan = "ENTRY_SELL_PULLBACK_EMA200";
         }
      }
   }
   SendTelemetryAndDeals(sesiOk, alasan, atr[1], rsi[1], ema200[1]);
}

void OnTick()  { EvaluateAndTrade(); }
void OnTimer() { EvaluateAndTrade(); }
