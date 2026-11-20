//+------------------------------------------------------------------+
//| GOLD_Reaper_Hexa.mq5                                             |
//| Scalping Eksperimental: EMA 20/50/200 + VWAP + RSI        |
//+------------------------------------------------------------------+
#property copyright "Mes & Nicolas"
#property version   "3.00"
#property description "GOLD Reaper Hexa v3.0 (Riset Quant Nov 2026: Impulse Guard + Asymmetric RSI + Adaptive ATR SL + Twin-Order Fixed)."

#include <Trade\Trade.mqh>
#include <WarRoomTelemetry.mqh>   // telemetri War Room (read-only)

input group "=== Identitas ==="
input long   InpMagic        = 20261104;
input string InpComment      = "GOLD_RP_HEXA";

input group "=== Timeframe ==="
input ENUM_TIMEFRAMES InpEntryTF = PERIOD_M5;
input ENUM_TIMEFRAMES InpTrendTF = PERIOD_M15;

input group "=== Moving Averages (Nicolas Spec: 20/50/200) ==="
input int    InpEmaFast      = 20;
input int    InpEmaSlow      = 50;
input int    InpEmaTrend     = 200;

input group "=== Filter Tambahan (VWAP & MACD) ==="
input bool   InpUseVWAP      = true;  // Filter Volume-Weighted Average Price

input group "=== RSI (Asymmetric Momentum Filter v3.0) ==="
input int    InpRsiPeriod    = 14;
input double InpRsiBuyMin    = 55.0;  // Riset v3.0: Buy butuh momentum kuat (>55.0)
input double InpRsiSellMax   = 52.0;  // Riset v3.0: Sell optimal (<52.0, atau 55.0 utk Sell-Only)
input bool   InpSellOnlyMode = false; // Mode Konservatif SELL-Only (PF 1.63 di riset 2025-2026)

input group "=== Filter Volatilitas (USD) ==="
input int    InpAtrPeriod    = 14;
input double InpAtrMinUSD    = 1.00;
input double InpAtrMaxUSD    = 12.0;

input group "=== Filter Eksekusi & Sesi ==="
input double InpMaxSpreadUSD     = 0.40;
input bool   InpUseSessionFilter = true;  // Filter Sesi London (08-08:59) & NY (13:15-15:59) Wajib Aktif
input int    InpSessionStart     = 8;     // Sesi 1 Start (London 15:00 WIB)
input int    InpSessionEnd       = 9;     // Sesi 1 End (London 16:00 WIB)
input bool   InpUseNYSession     = true;  // Buka Sesi 2 (New York Overlap)
input int    InpNYSessionStart   = 13;    // Sesi 2 Start (NY 20:00 WIB)
input int    InpNYSessionEnd     = 16;    // Sesi 2 End (NY 23:00 WIB - hindari late-session whipsaw)
input int    InpNYBufferMinutes  = 15;    // Jeda Pembukaan Sesi NY (menit) untuk hindari opening whipsaw
input int    InpFridayClose      = 23;
input bool   InpNoMonday         = true;

input group "=== Exits & Proteksi (Riset v3.0) ==="
input double InpSlAtrMult        = 1.4;   // SL = 1.4x ATR M5 (adaptif terhadap volatilitas)
input double InpTpAtrMult        = 3.5;   // TP Single-Order (3.5x ATR)
input bool   InpExitOnReversal   = true;  // Cut-loss dini saat EMA20/50 berbalik arah (wajib ON)
input double InpMinGoldSlUSD     = 0.0;   // Floor SL dimatikan (0.0) agar tidak merusak R:R saat ATR normal

input group "=== Proteksi Profit & Trailing ==="
input bool   InpUseBE            = true;
input double InpBE_TriggerR      = 1.0;   // Pindahkan SL ke BE saat floating >= +1.0R
input double InpBE_OffsetUSD     = 0.50;
input bool   InpUseRatchet       = false; // Matikan Ratchet/Squeeze agresif (gunakan Tier-2 Lock klasik)
input double InpRatchetStepR     = 0.5;   // Kerek SL setiap step kenaikan N x R (0.5R)
input double InpSqueezeDistR     = 0.3;   // Squeeze SL jika sisa jarak ke TP <= N x R (0.3R)
input double InpSqueezeLockR     = 0.35;  // SL dirapatkan hingga selisih N x R di bawah harga (0.35R)
input double InpTpExpandStepR    = 1.5;   // Perpanjang TP sejauh N x R saat TP lama tertembus
input bool   InpUseTier2Lock     = true;  // Tier-2 Lock v2.3/v3.0: saat floating >= +2.0R, kunci SL di +1.0R
input double InpTier2TriggerR    = 2.0;   // Trigger Tier-2 Lock (+2.0R)
input double InpTier2LockR       = 1.0;   // Level kunci profit Tier-2 (+1.0R)

input group "=== Skema B: Twin-Order & Anti-Chasing Impulse Guard ==="
input bool   InpEnableTwinOrder   = true;  // Buka 2 Tiket Simultan (Scalper +0.8R & Runner +2.5R)
input double InpScalpTpR          = 0.8;   // Target TP Tiket Scalper (+0.8R)
input double InpRunnerTpR         = 2.5;   // Target TP Tiket Runner (+2.5R)
input double InpRunnerBeTriggerR  = 1.0;   // Runner pindah ke BE hanya saat floating >= +1.0R (bukan 0.7R!)
input bool   InpAllowMultiLayer   = false; // Dilarang keras Multi-Layer (terbukti memicu chasing di pucuk/dasar)
input int    InpMaxActiveLayers   = 1;     // Maksimal 1 layer aktif
input double InpMinLayerDistAtr   = 0.8;   // Jarak minimal antar layer (x ATR)
input bool   InpOneTradePerImpulse= true;  // Anti-Chasing: maks 1 setup per gelombang crossover EMA20/50

input group "=== Proactive Dynamic Runner Expansion ==="
input bool   InpEnableDynamicRunner = false;       // Matikan ekspansi TP di depan mata agar Runner tidak batal TP
input double InpExpandTriggerR      = 1.5;         // Evaluasi ekspansi saat Runner floating >= +1.5R
input double InpExpandedTpR         = 4.0;         // Target TP baru saat momentum super kuat (+4.0R)
input double InpExpandedLockSlR     = 1.2;         // Kunci SL di +1.2R saat ekspansi aktif (+1.2R)
input double InpRsiMomentumThreshold = 40.0;       // Ambang RSI momentum kuat (Sell < 40, Buy > 60)

input group "=== Risiko & Money Management ==="
input double InpRiskPercent      = 0.5;
input double InpFixedLot         = 0.01;
input int    InpMaxTradesDay     = 15;
input double InpMaxDailyLossPct  = 3.0;
input double InpMaxDailyProfitPct= 8.0;
input int    InpSlippagePts      = 20;

input group "=== Proteksi Tambahan (v3.0) ==="
input int    InpCooldownMin           = 15;    // Cooldown setelah close rugi (15 menit / 3 bar M5)
input int    InpCooldownAfterCloseMin = 15;    // Cooldown setelah close profit/BE (15 menit anti-chasing)
input bool   InpCloseAtSessionEnd     = false; // Tutup posisi Gold saat jendela sesi berakhir

//=================== GLOBAL ===================
CTrade   trade;
int      hEmaFast=INVALID_HANDLE, hEmaSlow=INVALID_HANDLE, hEmaTrend=INVALID_HANDLE;
int      hAtr=INVALID_HANDLE, hRsi=INVALID_HANDLE;
datetime g_lastBar=0;
datetime g_lastGoldBar=0;                                  // bar M5 terakhir (dipersist)
ulong    g_cooldownUntil=0;                                // epoch; 0 = tidak cooldown
const string GOLD_BAR_KEY = "GOLD_RP_HEXA_lastGoldBar";
const string GOLD_IMP_DIR_KEY = "GOLD_RP_HEXA_lastImpDir";
const string GOLD_IMP_USED_KEY = "GOLD_RP_HEXA_impUsed";
int      g_lastSignalDir=0;                                // arah gelombang EMA terakhir (+1 / -1)
bool     g_impulseConsumed=false;                          // apakah gelombang EMA saat ini sudah diambil
int      g_dayKey=-1, g_tradesToday=0;
double   g_dayStartEquity=0.0;
bool     g_dayLocked=false;
ulong    g_tk[32];
double   g_risk[32];
int      g_nTk=0;

//=================== UTIL ====================
double IndVal(int handle,int buf,int shift)
{
   double b[];
   if(handle==INVALID_HANDLE) return 0.0;
   if(CopyBuffer(handle,buf,shift,1,b)!=1) return 0.0;
   return b[0];
}

double CalculateVWAP()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   MqlRates rates[];
   int n = CopyRates(_Symbol, InpEntryTF, dayStart, TimeCurrent(), rates);
   if(n <= 0) return 0.0;

   double sumPV = 0.0;
   double sumV  = 0.0;
   for(int i = 0; i < n; i++)
   {
      double typ = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
      double vol = (double)rates[i].tick_volume;
      sumPV += typ * vol;
      sumV  += vol;
   }
   return (sumV > 0.0) ? (sumPV / sumV) : 0.0;
}

double NormalizeLot(double lot)
{
   double mn=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double mx=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double st=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(st<=0) st=0.01;
   lot=MathRound(lot/st)*st;
   if(lot<mn) lot=mn;
   if(lot>mx) lot=mx;
   return NormalizeDouble(lot,2);
}

bool SpreadOK()
{
   double sp=SymbolInfoInteger(_Symbol,SYMBOL_SPREAD)*_Point;
   return (sp>0.0 && sp<=InpMaxSpreadUSD);
}

bool SessionOK()
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt);
   if(dt.day_of_week==0 || dt.day_of_week==6) return false;
   if(InpNoMonday && dt.day_of_week==1) return false;
   if(dt.day_of_week==5 && dt.hour>=InpFridayClose) return false;

   // Proteksi Rollover Jam 21:55 - 22:10 Server (Daily Bank Settlement)
   if((dt.hour == 21 && dt.min >= 55) || (dt.hour == 22 && dt.min <= 10)) return false;

   if(!InpUseSessionFilter) return true;

   bool s1 = false;
   if(InpSessionStart<=InpSessionEnd)
      s1 = (dt.hour>=InpSessionStart && dt.hour<InpSessionEnd);
   else
      s1 = (dt.hour>=InpSessionStart || dt.hour<InpSessionEnd);

   bool s2 = false;
   if(InpUseNYSession)
   {
      if(InpNYSessionStart<=InpNYSessionEnd)
         s2 = (dt.hour>=InpNYSessionStart && dt.hour<InpNYSessionEnd);
      else
         s2 = (dt.hour>=InpNYSessionStart || dt.hour<InpNYSessionEnd);

      // Jeda Pembukaan Sesi NY (Session Buffer): lewati N menit pertama untuk hindari opening whipsaw
      if(s2 && InpNYBufferMinutes > 0 && dt.hour == InpNYSessionStart && dt.min < InpNYBufferMinutes)
         s2 = false;
   }

   return (s1 || s2);
}

void UpdateDay()
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt);
   int key=dt.year*1000+dt.mon*100+dt.day;
   if(key!=g_dayKey)
   {
      g_dayKey=key;
      g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
      g_tradesToday=0;
      g_dayLocked=false;
   }
}

bool InSessionWindow()
{
   if(!InpUseSessionFilter) return true;
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt);

   bool s1 = false;
   if(InpSessionStart<=InpSessionEnd)
      s1 = (dt.hour>=InpSessionStart && dt.hour<InpSessionEnd);
   else
      s1 = (dt.hour>=InpSessionStart || dt.hour<InpSessionEnd);

   bool s2 = false;
   if(InpUseNYSession)
   {
      if(InpNYSessionStart<=InpNYSessionEnd)
         s2 = (dt.hour>=InpNYSessionStart && dt.hour<InpNYSessionEnd);
      else
         s2 = (dt.hour>=InpNYSessionStart || dt.hour<InpNYSessionEnd);
   }

   return (s1 || s2);
}

void CloseAllGold(string why)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      PrintFormat("[GOLD] CLOSE-ALL #%I64u (%s)", tk, why);
      trade.PositionClose(tk);
   }
}

bool RiskGuardOK()
{
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_dayStartEquity<=0) return true;
   double ddpct=(g_dayStartEquity-eq)/g_dayStartEquity*100.0;
   double prof =(eq-g_dayStartEquity)/g_dayStartEquity*100.0;
   if(ddpct>=InpMaxDailyLossPct)
   {
      if(!g_dayLocked) PrintFormat("[LOCK] loss %.2f%% -> stop hari ini",ddpct);
      g_dayLocked=true;
   }
   if(prof>=InpMaxDailyProfitPct)
   {
      if(!g_dayLocked) PrintFormat("[LOCK] profit %.2f%% -> stop hari ini",prof);
      g_dayLocked=true;
   }
   if(g_dayLocked) return false;
   if(g_tradesToday>=InpMaxTradesDay) return false;
   return true;
}

double AtrUSD(){ return IndVal(hAtr,0,1); }

double LotForRisk(double slPriceDist)
{
   if(InpFixedLot>0.0) return NormalizeLot(InpFixedLot);
   if(slPriceDist<=0.0||_Point<=0.0) return NormalizeLot(0.01);
   double riskMoney=AccountInfoDouble(ACCOUNT_EQUITY)*InpRiskPercent/100.0;
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tv<=0.0||ts<=0.0) return NormalizeLot(0.01);
   double valPerPoint=tv*(_Point/ts);
   double slPts=slPriceDist/_Point;
   double lossPerLot=slPts*valPerPoint;
   if(lossPerLot<=0.0) return NormalizeLot(0.01);
   double calcLot = riskMoney/lossPerLot;
   return NormalizeLot(calcLot);
}

void RememberRisk(ulong tk,double risk)
{
   for(int i=0;i<g_nTk;i++) if(g_tk[i]==tk){ g_risk[i]=risk; return; }
   if(g_nTk<32){ g_tk[g_nTk]=tk; g_risk[g_nTk]=risk; g_nTk++; }
}
double RiskOf(ulong tk)
{
   for(int i=0;i<g_nTk;i++) if(g_tk[i]==tk) return g_risk[i];
   return 0.0;
}
void ForgetRisk(ulong tk)
{
   for(int i=0;i<g_nTk;i++)
      if(g_tk[i]==tk){ g_tk[i]=g_tk[g_nTk-1]; g_risk[i]=g_risk[g_nTk-1]; g_nTk--; return; }
}

bool CanOpenNewLayer(int &activeLayerCount)
{
   activeLayerCount = 0;
   int totalMyPos = 0;
   
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      totalMyPos++;
      
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      long type   = PositionGetInteger(POSITION_TYPE);
      bool isBuy  = (type == POSITION_TYPE_BUY);
      
      // Jika masih ada posisi yang belum BE (masih ada resiko):
      if(isBuy  && (sl < open - _Point/2.0)) return false;
      if(!isBuy && (sl <= 0.0 || sl > open + _Point/2.0)) return false;
   }
   
   activeLayerCount = (InpEnableTwinOrder) ? (totalMyPos + 1) / 2 : totalMyPos;
   
   if(totalMyPos == 0) return true; // Belum ada posisi -> boleh buka
   if(!InpAllowMultiLayer) return false;
   if(activeLayerCount >= InpMaxActiveLayers) return false;
   
   return true;
}

ulong FindLastTicketByComment(string commentTag)
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic &&
         PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetString(POSITION_COMMENT) == commentTag)
         return tk;
   }
   return 0;
}

int CountMyPositions()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      n++;
   }
   return n;
}

// signal: +1 buy, -1 sell, 0 none
int Signal()
{
   double emaF=IndVal(hEmaFast,0,1);
   double emaS=IndVal(hEmaSlow,0,1);
   double emaT=IndVal(hEmaTrend,0,1);
   double rsi =IndVal(hRsi,0,1);
   double pxClose=iClose(_Symbol,InpEntryTF,1);
   double pxTrend=iClose(_Symbol,InpTrendTF,1);

   if(emaF<=0.0||emaS<=0.0||rsi<=0.0) return 0;

   // 1. Filter Trend Higher Timeframe (EMA 200 di M15)
   bool upTrend=(emaT>0.0 && pxTrend>0.0)?(pxTrend>emaT):(emaF>emaS);
   bool dnTrend=(emaT>0.0 && pxTrend>0.0)?(pxTrend<emaT):(emaF<emaS);

   // 2. Filter VWAP
   if(InpUseVWAP)
   {
      double vwap = CalculateVWAP();
      if(vwap > 0.0)
      {
         if(pxClose < vwap) upTrend = false; // Buy hanya jika harga di atas VWAP
         if(pxClose > vwap) dnTrend = false; // Sell hanya jika harga di bawah VWAP
      }
   }


   // 4. Filter Key Levels (PDH / PDL - Liquidity Sweep Guard)
   // Dilarang Buy jika harga menempel tepat di bawah PDH kemarin tanpa breakout jelas
   MqlRates dailyRates[];
   ArraySetAsSeries(dailyRates, true);
   if(CopyRates(_Symbol, PERIOD_D1, 1, 1, dailyRates) > 0)
   {
      double pdh = dailyRates[0].high;
      double pdl = dailyRates[0].low;
      double pt  = _Point;
      if(pxClose >= pdh - 15.0 * pt && pxClose <= pdh + 5.0 * pt)
         upTrend = false; // Hindari jebakan liquidity sweep pucuk kemarin
      if(pxClose <= pdl + 15.0 * pt && pxClose >= pdl - 5.0 * pt)
         dnTrend = false; // Hindari jebakan liquidity sweep dasar kemarin
   }

   // 6. Momentum Entry (v3.0: mendukung InpSellOnlyMode & Asymmetric RSI)
   if(!InpSellOnlyMode && emaF>emaS && upTrend && rsi>InpRsiBuyMin && rsi<75.0) return 1;
   if(emaF<emaS && dnTrend && rsi<InpRsiSellMax && rsi>25.0) return -1;
   return 0;
}

void OpenTrade(int dir)
{
   double atr=AtrUSD();
   if(atr<=0) return;
   double slDist=atr*InpSlAtrMult;

   // Floor SL khusus Emas (XAUUSD) agar tidak tersapu wick kecil saat volatilitas tinggi
   if(InpMinGoldSlUSD > 0.0 && StringFind(_Symbol, "XAU") >= 0 && slDist < InpMinGoldSlUSD)
   {
      PrintFormat("[GOLD] Floor SL aktif: slDist dinaikkan dari %.2f ke %.2f USD (min floor)", slDist, InpMinGoldSlUSD);
      slDist = InpMinGoldSlUSD;
   }

   double stops=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   if(stops>0.0 && slDist<stops*_Point*1.2) slDist=stops*_Point*1.2;

   double lot=LotForRisk(slDist);
   if(lot<=0.0) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double price=(dir>0)?ask:bid;
   int dg=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double sl=(dir>0)?price-slDist:price+slDist;
   sl=NormalizeDouble(sl,dg);

   if(InpEnableTwinOrder)
   {
      // --- TIKET 1: THE CASH-GRABBER (SCALPER +0.7R) ---
      double scalpDist = slDist * InpScalpTpR;
      if(stops>0.0 && scalpDist<stops*_Point*1.2) scalpDist=stops*_Point*1.2;
      double tpScalp = (dir>0)? price + scalpDist : price - scalpDist;
      tpScalp = NormalizeDouble(tpScalp, dg);

      bool ok1 = (dir>0)? trade.Buy(lot, _Symbol, 0.0, sl, tpScalp, "GOLD_SCALP")
                        : trade.Sell(lot, _Symbol, 0.0, sl, tpScalp, "GOLD_SCALP");
      if(ok1)
      {
         g_tradesToday++;
         ulong tk1 = FindLastTicketByComment("GOLD_SCALP");
         if(tk1 > 0)
         {
            RememberRisk(tk1, slDist);
            GoldLogRemember(tk1, (dir>0)?POSITION_TYPE_BUY:POSITION_TYPE_SELL, price, sl, tpScalp);
            PrintFormat("[GOLD_SCALP] OPEN #%I64u %s lot=%.2f @ %.*f | SL=%.*f | TP(+%.1fR)=%.*f",
                        tk1, (dir>0?"BUY":"SELL"), lot, dg, price, dg, sl, InpScalpTpR, dg, tpScalp);
         }
      }

      // --- TIKET 2: THE TREND-RIDER (RUNNER +2.5R DENGAN RATCHET) ---
      double runnerDist = slDist * InpRunnerTpR;
      if(stops>0.0 && runnerDist<stops*_Point*1.2) runnerDist=stops*_Point*1.2;
      double tpRunner = (dir>0)? price + runnerDist : price - runnerDist;
      tpRunner = NormalizeDouble(tpRunner, dg);

      bool ok2 = (dir>0)? trade.Buy(lot, _Symbol, 0.0, sl, tpRunner, "GOLD_RUNNER")
                        : trade.Sell(lot, _Symbol, 0.0, sl, tpRunner, "GOLD_RUNNER");
      if(ok2)
      {
         ulong tk2 = FindLastTicketByComment("GOLD_RUNNER");
         if(tk2 > 0)
         {
            RememberRisk(tk2, slDist);
            GoldLogRemember(tk2, (dir>0)?POSITION_TYPE_BUY:POSITION_TYPE_SELL, price, sl, tpRunner);
            PrintFormat("[GOLD_RUNNER] OPEN #%I64u %s lot=%.2f @ %.*f | SL=%.*f | TP(+%.1fR)=%.*f",
                        tk2, (dir>0?"BUY":"SELL"), lot, dg, price, dg, sl, InpRunnerTpR, dg, tpRunner);
         }
      }
   }
   else
   {
      double tpDist=atr*InpTpAtrMult;
      if(stops>0.0 && tpDist<stops*_Point*1.2) tpDist=stops*_Point*1.2;
      double tp=(dir>0)?price+tpDist:price-tpDist;
      tp=NormalizeDouble(tp,dg);
      bool ok=(dir>0)?trade.Buy(lot,_Symbol,0.0,sl,tp,InpComment)
                     :trade.Sell(lot,_Symbol,0.0,sl,tp,InpComment);
      if(ok)
      {
         g_tradesToday++;
         ulong tk=0;
         for(int i=PositionsTotal()-1;i>=0;i--)
         {
            ulong t=PositionGetTicket(i);
            if(t==0) continue;
            if(PositionGetInteger(POSITION_MAGIC)==InpMagic &&
               PositionGetString(POSITION_SYMBOL)==_Symbol){ tk=t; break; }
         }
         if(tk>0)
         {
            RememberRisk(tk,slDist);
            GoldLogRemember(tk, (dir>0)?POSITION_TYPE_BUY:POSITION_TYPE_SELL, price, sl, tp);
            PrintFormat("[GOLD] OPEN #%I64u %s lot=%.2f @ %.*f | SL=%.*f (%.3f) | TP=%.*f (%.3f) | R:R=%.2f",
                        tk, (dir>0?"BUY":"SELL"), lot,
                        dg, price, dg, sl, slDist, dg, tp, tpDist,
                        (slDist>0.0? tpDist/slDist : 0.0));
         }
      }
   }
}

//=================== LOGGING POSISI GOLD ===================
// Sebelumnya EA hanya mencatat aktivitas BTC, tidak Gold. Akibatnya trade
// Gold yang sudah terjadi tidak terlihat di log -> diagnosa jadi buta.
struct GoldPosLog
{
   ulong    ticket;
   long     type;
   double   open;
   double   sl;
   double   tp;
   datetime openedAt;
};
GoldPosLog g_goldPos[];

void GoldLogRemember(ulong tk, long type, double o, double s, double t)
{
   int n=ArraySize(g_goldPos);
   ArrayResize(g_goldPos, n+1);
   g_goldPos[n].ticket=tk; g_goldPos[n].type=type;
   g_goldPos[n].open=o;   g_goldPos[n].sl=s;   g_goldPos[n].tp=t;
   g_goldPos[n].openedAt=TimeCurrent();
}

// Deteksi posisi yang sudah tutup, lalu cari alasan + profit dari history.
// Dipanggil tiap tick; hanya bekerja saat ada posisi yang hilang.
void GoldLogCheckCloses()
{
   int n=ArraySize(g_goldPos);
   for(int i=n-1;i>=0;i--)
   {
      ulong tk=g_goldPos[i].ticket;
      if(PositionSelectByTicket(tk)) continue;   // masih terbuka

      string reason="tidak diketahui";
      double closePx=0.0, prof=0.0;
      datetime closeTm=0;

      if(HistorySelectByPosition(tk))
      {
         int total=HistoryDealsTotal();
         for(int d=0;d<total;d++)
         {
            ulong dt=HistoryDealGetTicket(d);
            if(dt==0) continue;
            if(HistoryDealGetInteger(dt,DEAL_POSITION_ID)!=tk) continue;
            if(HistoryDealGetInteger(dt,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue;
            closePx = HistoryDealGetDouble(dt,DEAL_PRICE);
            prof    = HistoryDealGetDouble(dt,DEAL_PROFIT);
            closeTm = (datetime)HistoryDealGetInteger(dt,DEAL_TIME);
            long rsn = HistoryDealGetInteger(dt,DEAL_REASON);
            reason = (rsn==DEAL_REASON_SL)  ? "STOP LOSS" :
                     (rsn==DEAL_REASON_TP)  ? "TAKE PROFIT" :
                     (rsn==DEAL_REASON_EXPERT) ? "EA (reversal/BE)" : "manual/other";
         }
      }

      double diff=(g_goldPos[i].type==POSITION_TYPE_BUY)?(closePx-g_goldPos[i].open)
                                                       :(g_goldPos[i].open-closePx);
      int dg=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
      PrintFormat("[GOLD] CLOSE #%I64u %s @ %.*f | entry=%.*f | diff=%+.3f | profit=%+.2f %s | alasan=%s",
                  tk,
                  (g_goldPos[i].type==POSITION_TYPE_BUY?"BUY":"SELL"),
                  dg, closePx, dg, g_goldPos[i].open, diff, prof,
                  AccountInfoString(ACCOUNT_CURRENCY),
                  reason);

      if(prof<0.0 && InpCooldownMin>0)
      {
         g_cooldownUntil=(ulong)TimeCurrent()+(ulong)InpCooldownMin*60;
         PrintFormat("[COOLDOWN] close rugi %+.2f -> jeda entry %d menit", prof, InpCooldownMin);
      }
      else if(InpCooldownAfterCloseMin>0)
      {
         g_cooldownUntil=(ulong)TimeCurrent()+(ulong)InpCooldownAfterCloseMin*60;
         PrintFormat("[COOLDOWN] close profit/BE %+.2f -> jeda anti-chasing %d menit", prof, InpCooldownAfterCloseMin);
      }

      // hapus dari array secara aman (menggunakan ukuran aktual saat ini)
      int curSize = ArraySize(g_goldPos);
      for(int k=i; k<curSize-1; k++) g_goldPos[k] = g_goldPos[k+1];
      ArrayResize(g_goldPos, curSize-1);
   }
}

void ManagePositions()
{
   double atr=AtrUSD();
   int dg=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double emaF=IndVal(hEmaFast,0,1);
   double emaS=IndVal(hEmaSlow,0,1);

   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;

      long posType=PositionGetInteger(POSITION_TYPE);
      bool isBuy=(posType==POSITION_TYPE_BUY);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl  =PositionGetDouble(POSITION_SL);
      double tp  =PositionGetDouble(POSITION_TP);
      double px  =(isBuy)?SymbolInfoDouble(_Symbol,SYMBOL_BID):SymbolInfoDouble(_Symbol,SYMBOL_ASK);

      if(InpExitOnReversal)
      {
         if(isBuy  && emaF<emaS)
         {
            PrintFormat("[GOLD] EXIT reversal #%I64u: EMA fast %.3f < EMA slow %.3f (BUY ditutup)",
                        tk, emaF, emaS);
            trade.PositionClose(tk); continue;
         }
         if(!isBuy && emaF>emaS)
         {
            PrintFormat("[GOLD] EXIT reversal #%I64u: EMA fast %.3f > EMA slow %.3f (SELL ditutup)",
                        tk, emaF, emaS);
            trade.PositionClose(tk); continue;
         }
      }

      double moved=(isBuy)?(px-open):(open-px);
      double risk=RiskOf(tk);
      if(risk<=0.0){ risk=(sl>0.0)?MathAbs(open-sl):atr*InpSlAtrMult; RememberRisk(tk,risk); }
      if(risk<=0.0) continue;
      double rMult=moved/risk;

      // Tier 1: Break-Even Utama (v3.0: Runner memakai InpRunnerBeTriggerR = +1.0R agar tidak tercekik di +0.7R)
      string posComment = PositionGetString(POSITION_COMMENT);
      double beTrigger = (InpEnableTwinOrder && posComment=="GOLD_RUNNER") ? InpRunnerBeTriggerR : InpBE_TriggerR;
      if(InpUseBE && rMult >= beTrigger)
      {
         double beSl = (isBuy) ? (open + InpBE_OffsetUSD) : (open - InpBE_OffsetUSD);
         if((isBuy && sl < beSl - _Point/2.0) || (!isBuy && (sl <= 0.0 || sl > beSl + _Point/2.0)))
         {
            PrintFormat("[GOLD] BREAK-EVEN #%I64u (%s): floating %+.2fR -> SL dipindah ke open%+.2f (%.*f)",
                        tk, posComment, rMult, InpBE_OffsetUSD, dg, NormalizeDouble(beSl,dg));
            trade.PositionModify(tk, NormalizeDouble(beSl, dg), tp);
            sl = beSl;
         }
      }

      // Tier 2 Klasik (v2.3/v3.0): Kunci profit +1.0R saat floating >= +2.0R
      if(InpUseTier2Lock && !InpUseRatchet && rMult >= InpTier2TriggerR)
      {
         double lockSl = (isBuy) ? (open + risk * InpTier2LockR) : (open - risk * InpTier2LockR);
         lockSl = NormalizeDouble(lockSl, dg);
         if((isBuy && sl < lockSl - _Point * 2.0) || (!isBuy && (sl <= 0.0 || sl > lockSl + _Point * 2.0)))
         {
            PrintFormat("[GOLD] TIER-2 LOCK #%I64u (%s): floating %+.2fR -> SL dikunci +%.1fR di %.*f",
                        tk, posComment, rMult, InpTier2LockR, dg, lockSl);
            trade.PositionModify(tk, lockSl, tp);
            sl = lockSl;
         }
      }

      // Tier 2 Alternatif: Multi-Stage Dynamic Ratchet & Expanding TP (default OFF di v3.0)
      double ratchetStartR = (InpEnableTwinOrder && posComment=="GOLD_RUNNER") ? InpRunnerBeTriggerR : InpBE_TriggerR;
      if(InpUseRatchet && rMult >= ratchetStartR)
      {
         double newSl = sl;
         double newTp = tp;
         bool   needMod = false;

         // A1. Proactive Dynamic Expansion (Runner Pro: perluas TP sebelum kena hard-TP broker di +2.5R)
         double initTpDist = risk * InpRunnerTpR;
         bool isNearInitTp = (tp > 0.0 && MathAbs(MathAbs(open - tp) - initTpDist) <= _Point * 20.0);
         double rsiVal = IndVal(hRsi, 0, 1);
         bool strongMomentum = (!isBuy && rsiVal <= InpRsiMomentumThreshold && emaF < emaS) ||
                               (isBuy  && rsiVal >= (100.0 - InpRsiMomentumThreshold) && emaF > emaS);

         if(InpEnableDynamicRunner && posComment=="GOLD_RUNNER" && rMult >= InpExpandTriggerR && isNearInitTp && strongMomentum)
         {
            newTp = isBuy ? NormalizeDouble(open + risk * InpExpandedTpR, dg)
                          : NormalizeDouble(open - risk * InpExpandedTpR, dg);
            double targetLockSl = isBuy ? NormalizeDouble(open + risk * InpExpandedLockSlR, dg)
                                        : NormalizeDouble(open - risk * InpExpandedLockSlR, dg);
            if((isBuy && targetLockSl > newSl + _Point * 2.0) || (!isBuy && (newSl <= 0.0 || targetLockSl < newSl - _Point * 2.0)))
            {
               newSl = targetLockSl;
            }
            needMod = true;
            PrintFormat("[GOLD] [RUNNER_PRO] #%I64u Momentum Super Kuat (RSI=%.1f)! TP diperpanjang ke +%.1fR (%.*f) | SL dikunci di +%.1fR (%.*f)",
                        tk, rsiVal, InpExpandedTpR, dg, newTp, InpExpandedLockSlR, dg, newSl);
         }
         // A2. Standard TP Expansion saat menembus TP lama
         else if(tp > 0.0 && ((isBuy && px >= tp - _Point * 10.0) || (!isBuy && px <= tp + _Point * 10.0)))
         {
            newSl = NormalizeDouble(tp, dg);
            newTp = isBuy ? NormalizeDouble(tp + risk * InpTpExpandStepR, dg) : NormalizeDouble(tp - risk * InpTpExpandStepR, dg);
            needMod = true;
            PrintFormat("[GOLD] [TP_EXPAND] #%I64u tembus TP (%.*f)! SL dikunci di %.*f | Target baru diperpanjang ke %.*f (+%.1fR)",
                        tk, dg, tp, dg, newSl, dg, newTp, InpTpExpandStepR);
         }
         else
         {
            // B. Near-TP Squeeze (dengan minimum step guard $0.30 & broker stops_level check agar tidak spam error)
            double stopsPts = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
            double minModStep = MathMax(0.30, stopsPts * 1.5);
            double distToTp = (tp > 0.0) ? ((isBuy) ? (tp - px) : (px - tp)) : 999999.0;
            double distToTpR = distToTp / risk;
            if(tp > 0.0 && distToTpR <= InpSqueezeDistR && distToTp > minModStep)
            {
               double squeezeSl = (isBuy) ? (px - risk * InpSqueezeLockR) : (px + risk * InpSqueezeLockR);
               squeezeSl = NormalizeDouble(squeezeSl, dg);
               if((isBuy && squeezeSl > newSl + minModStep && px - squeezeSl > stopsPts) ||
                  (!isBuy && (newSl <= 0.0 || squeezeSl < newSl - minModStep) && squeezeSl - px > stopsPts))
               {
                  newSl = squeezeSl;
                  needMod = true;
                  PrintFormat("[GOLD] [SQUEEZE] #%I64u sisa %.2fR ke TP -> SL dirapatkan ke %.*f", tk, distToTpR, dg, newSl);
               }
            }
            else
            {
               // C. Step Ratchet Tiap +0.5R (Kerek SL mengunci profit 0.5R di bawah milestone: +1.0R->+0.5R, +1.5R->+1.0R, dst.)
               double stepR = MathFloor(rMult / InpRatchetStepR) * InpRatchetStepR;
               double targetLockR = stepR - InpRatchetStepR;
               if(targetLockR > 0.0)
               {
                  double stepSl = (isBuy) ? (open + risk * targetLockR) : (open - risk * targetLockR);
                  stepSl = NormalizeDouble(stepSl, dg);
                  if((isBuy && stepSl > newSl + _Point * 2.0) || (!isBuy && (newSl <= 0.0 || stepSl < newSl - _Point * 2.0)))
                  {
                     newSl = stepSl;
                     needMod = true;
                     PrintFormat("[GOLD] [RATCHET] #%I64u floating %+.2fR -> SL dikerek mengunci +%.2fR di %.*f",
                                 tk, rMult, targetLockR, dg, newSl);
                  }
               }
            }
         }

         if(needMod)
         {
            trade.PositionModify(tk, newSl, newTp);
         }
      }
      double vol=PositionGetDouble(POSITION_VOLUME);
      if(vol<=0.0) ForgetRisk(tk);
   }
}


//=================== MULTI-SYMBOL PORTFOLIO ENGINE ===================
input group "=== Portofolio Engine ==="
input bool   InpEnableGold       = true;   // Aktifkan Engine Gold (XAUUSDc - London & NY Peak)
input bool   InpEnableBTC        = false;  // Nonaktifkan BTC agar 100% fokus XAUUSDc
input double InpBtcFixedLot      = 0.01;   // Lot BTC Trend (0.01 = aman utk modal ~1000 USC)

input group "=== Filter Anti-Whipsaw BTC (v2.3) ==="
input bool   InpBtcUseAtrFilter  = true;   // Filter volatilitas BTC (berbasis % harga)
input double InpBtcAtrPctMin     = 0.35;   // ATR/Harga minimum (%) — p10 data 2021-2026
input double InpBtcAtrPctMax     = 1.74;   // ATR/Harga maksimum (%) — p95 data 2021-2026
input double InpBtcAtrMinUSD     = 50.0;   // Hard floor ATR (USD) — pengaman tambahan
input bool   InpBtcUseRangeFilter= true;   // Tolak entry saat pasar sideways sempit
input int    InpBtcRangeBars     = 20;     // Jumlah bar M15 untuk ukur range
input double InpBtcRangeMult     = 3.0;    // Range harus >= Mult x ATR (kalau tidak = sideways)
input bool   InpBtcUseSlFloor    = true;   // Pakai SL minimum absolut
input double InpBtcSlFloorUSD    = 300.0;  // SL minimum (USD) — cegah SL terlalu rapat

// --- Engine BTC versi TREND-FOLLOWING H1 (menggantikan scalping M15) ---
input group "=== BTC Trend-Following (H1) ==="
input double InpBtcSlAtrMult     = 2.5;    // SL = N x ATR(H1)
input bool   InpBtcUseTrail      = true;   // Trailing ratchet
input bool   InpBtcUseBE         = true;   // Kunci profit ke BE saat floating profit
input double InpBtcBeStartR      = 1.0;    // Pindahkan SL ke BE saat floating >= N x R
input double InpBtcBeOffsetUSD   = 10.0;   // Buffer profit di atas Open (USD)
input double InpBtcTrailStartR   = 2.5;    // Mulai trailing setelah N x R
input double InpBtcTrailAtrMult  = 3.5;    // Jarak trailing = N x ATR
input bool   InpBtcUseAdx        = true;   // Filter ADX (tren kuat)
input int    InpBtcAdxPeriod     = 14;
input double InpBtcAdxMin        = 22.0;
input double InpBtcTrendSepPct   = 0.5;    // |EMA50-EMA200|/EMA200 minimal (%)
input bool   InpBtcExitTrendBreak= false;  // Exit bila close balik ke sisi lain EMA50
input bool   InpBtcUseTp         = true;   // Pasang TP fixed di order BTC (v2.5.1)
input double InpBtcTpR           = 4.0;    // TP = N x R (R = jarak SL); 0 = tanpa TP

int hBtcEmaF=INVALID_HANDLE, hBtcEmaS=INVALID_HANDLE, hBtcEmaT=INVALID_HANDLE, hBtcRsi=INVALID_HANDLE, hBtcAtr=INVALID_HANDLE, hBtcAdx=INVALID_HANDLE;
datetime g_lastBtcBar=0;

// Persist bar H1 terakhir yang SUDAH dievaluasi entry lewat GlobalVariable.
// Tanpa ini, restart MT5 me-reset g_lastBtcBar ke 0 -> EA bisa re-entry di
// bar H1 yang sama 2x (akar trade BTC 33x lebih sering dari backtest).
const string BTC_BAR_KEY = "GOLD_RP_HEXA_lastBtcBar";
datetime LoadBtcBar(){ return (datetime)GlobalVariableGet(BTC_BAR_KEY); }
void SaveBtcBar(datetime v){ if(!GlobalVariableSet(BTC_BAR_KEY,(double)v)) Print("[BTC] GAGAL simpan bar state"); }

string GetBtcSymbol()
{
   bool isCustom=false;
   if(SymbolExist("BTCUSDc", isCustom)) return "BTCUSDc";
   if(SymbolExist("BTCUSDm", isCustom)) return "BTCUSDm";
   if(SymbolExist("BTCUSD",  isCustom)) return "BTCUSD";
   return "";
}

double CalculateBtcVWAP(string btcSym)
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   MqlRates rates[];
   int n = CopyRates(btcSym, PERIOD_M15, dayStart, TimeCurrent(), rates);
   if(n <= 0) return 0.0;

   double sumPV = 0.0, sumV = 0.0;
   for(int i = 0; i < n; i++)
   {
      double typ = (rates[i].high + rates[i].low + rates[i].close) / 3.0;
      double vol = (double)rates[i].tick_volume;
      sumPV += typ * vol;
      sumV  += vol;
   }
   return (sumV > 0.0) ? (sumPV / sumV) : 0.0;
}

int BtcSignal(string btcSym)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int donPeriod = 20;
   int need = donPeriod + 2;
   if(CopyRates(btcSym, PERIOD_H1, 0, need, rates) < need) return 0;

   double highestHigh = -DBL_MAX;
   double lowestLow   = DBL_MAX;

   for(int i = 2; i <= donPeriod + 1; i++)
   {
      if(rates[i].high > highestHigh) highestHigh = rates[i].high;
      if(rates[i].low  < lowestLow)   lowestLow   = rates[i].low;
   }

   double c1 = rates[1].close;
   double emaT = IndVal(hBtcEmaT, 0, 1);
   double adx  = IndVal(hBtcAdx, 0, 1);

   if(emaT <= 0.0) return 0;
   if(InpBtcUseAdx && adx > 0.0 && adx < InpBtcAdxMin) return 0;

   // Breakout Donchian 20-H1
   if(c1 > highestHigh && c1 > emaT) return 1;
   if(c1 < lowestLow   && c1 < emaT) return -1;
   return 0;
}

void CheckBtcEngine()
{
   string btcSym = GetBtcSymbol();
   if(!InpEnableBTC)
   {
      if(btcSym != "")
      {
         for(int i=PositionsTotal()-1; i>=0; i--)
         {
            ulong tk=PositionGetTicket(i);
            if(tk==0) continue;
            if(PositionGetInteger(POSITION_MAGIC)!=20261108) continue;
            if(PositionGetString(POSITION_SYMBOL)!=btcSym) continue;
            PrintFormat("[BTC] CLOSE #%I64u: InpEnableBTC=false (auto-cleanup posisi BTC)", tk);
            trade.PositionClose(tk);
         }
      }
      return;
   }
   if(btcSym == "") return;

   // Manage BTC Positions
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=20261108) continue;
      if(PositionGetString(POSITION_SYMBOL)!=btcSym) continue;

      long posType=PositionGetInteger(POSITION_TYPE);
      bool isBuy=(posType==POSITION_TYPE_BUY);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl  =PositionGetDouble(POSITION_SL);
      double tp  =PositionGetDouble(POSITION_TP);
      double px  =(isBuy)?SymbolInfoDouble(btcSym,SYMBOL_BID):SymbolInfoDouble(btcSym,SYMBOL_ASK);
      double atr =IndVal(hBtcAtr,0,1);
      int dg     =(int)SymbolInfoInteger(btcSym,SYMBOL_DIGITS);

      double moved=(isBuy)?(px-open):(open-px);
      double risk=RiskOf(tk);
      if(risk<=0.0){ risk=(sl>0.0)?MathAbs(open-sl):atr*1.5; RememberRisk(tk,risk); }
      if(risk<=0.0) continue;
      double rMult=moved/risk;

      // ==============================================
      // MANAJEMEN BTC TREND-FOLLOWING (H1):
      // 1. Trailing ratchet: mulai di +InpBtcTrailStartR, jarak InpBtcTrailAtrMult x ATR
      // 2. Opsional: exit bila close balik ke sisi lain EMA50 (tren patah)
      // ==============================================
      double pt = SymbolInfoDouble(btcSym, SYMBOL_POINT);

      if(InpBtcExitTrendBreak)
      {
         double emaM = IndVal(hBtcEmaS,0,1);
         double c1   = iClose(btcSym, PERIOD_H1, 1);
         if(emaM>0.0 && c1>0.0)
         {
            if(isBuy && c1 < emaM){ trade.PositionClose(tk); PrintFormat("[BTC] EXIT BUY: tren patah (close %.2f < EMA50 %.2f)", c1, emaM); continue; }
            if(!isBuy && c1 > emaM){ trade.PositionClose(tk); PrintFormat("[BTC] EXIT SELL: tren patah (close %.2f > EMA50 %.2f)", c1, emaM); continue; }
         }
      }

      // 1. Break-Even Protection (Kunci Modal di +1.5R)
      if(InpBtcUseBE && rMult >= InpBtcBeStartR)
      {
         double beSl = (isBuy) ? (open + InpBtcBeOffsetUSD) : (open - InpBtcBeOffsetUSD);
         beSl = NormalizeDouble(beSl, dg);
         if((isBuy && sl < beSl - pt*2.0) || (!isBuy && (sl <= 0.0 || sl > beSl + pt*2.0)))
         {
            PrintFormat("[BTC] BREAK-EVEN #%I64u: floating %+.2fR -> SL dipindah ke open%+.1f (%.*f)",
                        tk, rMult, InpBtcBeOffsetUSD, dg, beSl);
            trade.PositionModify(tk, beSl, tp);
            sl = beSl; // update local SL
         }
      }

      // 2. Multi-Stage Dynamic Ratchet & TP Expansion untuk BTC
      if(InpUseRatchet && rMult >= InpBtcBeStartR)
      {
         double newSl = sl;
         double newTp = tp;
         bool   needMod = false;

         // A. TP Expansion (Jika tembus target TP lama -> kunci SL di TP lama & perpanjang TP baru +1.5R)
         if(tp > 0.0 && ((isBuy && px >= tp - pt * 10.0) || (!isBuy && px <= tp + pt * 10.0)))
         {
            newSl = NormalizeDouble(tp, dg);
            newTp = isBuy ? NormalizeDouble(tp + risk * InpTpExpandStepR, dg) : NormalizeDouble(tp - risk * InpTpExpandStepR, dg);
            needMod = true;
            PrintFormat("[BTC] [TP_EXPAND] #%I64u tembus TP (%.*f)! SL dikunci di %.*f | Target baru diperpanjang ke %.*f (+%.1fR)",
                        tk, dg, tp, dg, newSl, dg, newTp, InpTpExpandStepR);
         }
         else
         {
            // B. Near-TP Squeeze (Jika selisih sisa ke TP tinggal 0.2R - 0.5R)
            double distToTp = (tp > 0.0) ? ((isBuy) ? (tp - px) : (px - tp)) : 999999.0;
            double distToTpR = distToTp / risk;
            if(tp > 0.0 && distToTpR <= InpSqueezeDistR && distToTpR > 0.0)
            {
               double squeezeSl = (isBuy) ? (px - risk * InpSqueezeLockR) : (px + risk * InpSqueezeLockR);
               squeezeSl = NormalizeDouble(squeezeSl, dg);
               if((isBuy && squeezeSl > newSl + pt * 2.0) || (!isBuy && (newSl <= 0.0 || squeezeSl < newSl - pt * 2.0)))
               {
                  newSl = squeezeSl;
                  needMod = true;
                  PrintFormat("[BTC] [SQUEEZE] #%I64u sisa %.2fR ke TP -> SL dirapatkan mepet ke %.*f", tk, distToTpR, dg, newSl);
               }
            }
            else
            {
               // C. Step Ratchet Tiap +0.7R (Kerek SL mengunci profit step sebelumnya)
               double lockR = MathFloor((rMult - InpBtcBeStartR) / InpRatchetStepR) * InpRatchetStepR;
               if(lockR >= InpRatchetStepR)
               {
                  double targetLockR = InpBtcBeStartR + lockR - InpRatchetStepR;
                  double stepSl = (isBuy) ? (open + risk * targetLockR) : (open - risk * targetLockR);
                  stepSl = NormalizeDouble(stepSl, dg);
                  if((isBuy && stepSl > newSl + pt * 2.0) || (!isBuy && (newSl <= 0.0 || stepSl < newSl - pt * 2.0)))
                  {
                     newSl = stepSl;
                     needMod = true;
                     PrintFormat("[BTC] [RATCHET] #%I64u floating %+.2fR -> SL dikerek mengunci +%.1fR di %.*f",
                                 tk, rMult, targetLockR, dg, newSl);
                  }
               }
            }
         }

         if(needMod)
         {
            trade.PositionModify(tk, newSl, newTp);
            sl = newSl;
         }
      }
   }
   datetime bt=iTime(btcSym,PERIOD_H1,0);
   if(bt==g_lastBtcBar) return;
   g_lastBtcBar=bt;
   SaveBtcBar(bt);

   // Check count
   int btcPos=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk>0 && PositionGetInteger(POSITION_MAGIC)==20261108 && PositionGetString(POSITION_SYMBOL)==btcSym) btcPos++;
   }
   if(btcPos > 0) return;

   int sig = BtcSignal(btcSym);
   if(sig != 0)
   {
      double atr = IndVal(hBtcAtr,0,1);
      if(atr < 50.0 || atr > 2500.0) return;

      // --- Filter 1: volatilitas RELATIF (ATR / harga) ---
      // BTC naik ~7x (2021-2026) sehingga ATR absolut tidak bisa dibandingkan antar tahun.
      // Batas diturunkan dari distribusi 51.210 bar ATR H1: p10=0.35%, p95=1.74%.
      if(InpBtcUseAtrFilter)
      {
         double refClose = iClose(btcSym, PERIOD_H1, 1);
         if(refClose <= 0.0) refClose = iClose(btcSym, PERIOD_H1, 0);
         double atrPct = (refClose > 0.0) ? (100.0 * atr / refClose) : 0.0;

         bool tooThin = (atrPct > 0.0 && atrPct < InpBtcAtrPctMin);
         bool tooWild = (InpBtcAtrPctMax > 0.0 && atrPct > InpBtcAtrPctMax);
         bool tooSmallAbs = (atr < InpBtcAtrMinUSD);

         if(tooThin || tooWild || tooSmallAbs)
         {
            static string lastAtrSkip="";
            string tag = TimeToString(iTime(btcSym,PERIOD_H1,0));
            if(tag != lastAtrSkip)
            {
               string why = tooThin ? "pasar terlalu tipis" : (tooWild ? "volatilitas ekstrem" : "ATR absolut terlalu kecil");
               PrintFormat("[BTC] SKIP entry: ATR=%.2f (%.3f%% harga) di luar rentang %.2f%%-%.2f%% -> %s",
                           atr, atrPct, InpBtcAtrPctMin, InpBtcAtrPctMax, why);
               lastAtrSkip = tag;
            }
            return;
         }
      }

      // --- Filter 2: Range sideways (20 bar terakhir harus cukup lebar vs ATR) ---
      if(InpBtcUseRangeFilter)
      {
         MqlRates rr[];
         ArraySetAsSeries(rr, true);
         int need = InpBtcRangeBars + 1;
         if(CopyRates(btcSym, PERIOD_H1, 0, need, rr) >= need)
         {
            double hi = -DBL_MAX, lo = DBL_MAX;
            for(int k=1; k<=InpBtcRangeBars; k++)
            {
               if(rr[k].high > hi) hi = rr[k].high;
               if(rr[k].low  < lo) lo = rr[k].low;
            }
            double rng = hi - lo;
            if(rng < atr * InpBtcRangeMult)
            {
               static string lastRngSkip="";
               string tag2 = TimeToString(iTime(btcSym,PERIOD_M15,0));
               if(tag2 != lastRngSkip)
               {
                  PrintFormat("[BTC] SKIP entry: range %d bar $%.0f < %.1fx ATR ($%.0f) = sideways",
                              InpBtcRangeBars, rng, InpBtcRangeMult, atr*InpBtcRangeMult);
                  lastRngSkip = tag2;
               }
               return;
            }
         }
      }

      double slDist = atr * InpBtcSlAtrMult;

      // --- Slot SL minimum absolut (opsional) ---
      if(InpBtcUseSlFloor && slDist < InpBtcSlFloorUSD)
         slDist = InpBtcSlFloorUSD;

      // TP fixed (v2.5.1): dihitung dari jarak SL, jadi R:R tetap walau SL di-floor.
      // Bila dimatikan (InpBtcUseTp=false / InpBtcTpR=0) kembali ke trailing-only.
      double tpDist = (InpBtcUseTp && InpBtcTpR > 0.0) ? slDist * InpBtcTpR : 0.0;

      double ask = SymbolInfoDouble(btcSym, SYMBOL_ASK);
      double bid = SymbolInfoDouble(btcSym, SYMBOL_BID);
      double px  = (sig > 0) ? ask : bid;
      int dg     = (int)SymbolInfoInteger(btcSym, SYMBOL_DIGITS);
      double sl  = (sig > 0) ? px - slDist : px + slDist;
      double tp  = 0.0;   // tanpa TP fixed (tpDist==0) -> exit hanya via trailing/SL
      if(tpDist > 0.0)
         tp = (sig > 0) ? px + tpDist : px - tpDist;
      sl = NormalizeDouble(sl, dg); tp = NormalizeDouble(tp, dg);

      trade.SetExpertMagicNumber(20261108);
      bool ok = (sig > 0) ? trade.Buy(InpBtcFixedLot, btcSym, 0.0, sl, tp, "BTC_HEXA")
                          : trade.Sell(InpBtcFixedLot, btcSym, 0.0, sl, tp, "BTC_HEXA");
      if(ok)
      {
         for(int i=PositionsTotal()-1;i>=0;i--)
         {
            ulong tk=PositionGetTicket(i);
            if(tk>0 && PositionGetInteger(POSITION_MAGIC)==20261108 && PositionGetString(POSITION_SYMBOL)==btcSym)
            {
               RememberRisk(tk, slDist);
               break;
            }
         }
         PrintFormat("[BTC] OPEN %s lot=%.2f slDist=$%.2f tpDist=$%.2f", (sig>0?"BUY":"SELL"), InpBtcFixedLot, slDist, tpDist);
      }
      trade.SetExpertMagicNumber(InpMagic); // restore
   }
}

//=================== FORWARD TEST LOGGER (CSV) ===================
// Menulis setiap deal yang SUDAH DITUTUP ke MQL5/Files/forward_test.csv.
// Dashboard Python di box membaca file ini. Idempotent: ticket terakhir
// dibaca ulang dari CSV saat init, jadi aman terhadap restart MT5/box.
input bool   InpFtLog     = true;    // Aktifkan pencatatan forward test (CSV)
string g_ftFile = "forward_test.csv";
long   g_ftLastTicket = 0;
bool   g_ftReady = false;

string FtReason(long rsn)
{
   switch((int)rsn)
   {
      case DEAL_REASON_SL:     return "SL";
      case DEAL_REASON_TP:     return "TP";
      case DEAL_REASON_EXPERT: return "EA";
      case DEAL_REASON_CLIENT: return "MANUAL";
      case DEAL_REASON_MOBILE: return "MOBILE";
      default:                 return "OTHER";
   }
}

// Baca ticket terbesar yang sudah tercatat di CSV (untuk idempotensi)
long FtReadLastTicket()
{
   int fh=FileOpen(g_ftFile, FILE_READ|FILE_CSV|FILE_ANSI, ',');
   if(fh==INVALID_HANDLE) return 0;
   long last=0;
   while(!FileIsEnding(fh))
   {
      string line=FileReadString(fh);
      if(StringLen(line)<3) continue;
      string parts[];
      int k=StringSplit(line, ',', parts);
      if(k<1) continue;
      long t=StringToInteger(parts[0]);
      if(t>last) last=t;
   }
   FileClose(fh);
   return last;
}

void FtInit()
{
   if(!InpFtLog) return;
   g_ftLastTicket = FtReadLastTicket();
   g_ftReady = true;
   PrintFormat("[FT] forward test logger siap. lastTicket=%I64d file=%s", g_ftLastTicket, g_ftFile);
}

// Scan history, append deal OUT yang belum tercatat
void FtLog()
{
   if(!g_ftReady) return;
   if(!HistorySelect(0, TimeCurrent()+60)) return;
   int total=HistoryDealsTotal();
   long maxSeen=g_ftLastTicket;
   for(int i=0;i<total;i++)
   {
      ulong dt=HistoryDealGetTicket(i);
      if(dt==0) continue;
      long ticket=(long)dt;
      if(ticket<=g_ftLastTicket) continue;
      if(HistoryDealGetInteger(dt,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue; // hanya deal tutup

      long   posId = HistoryDealGetInteger(dt,DEAL_POSITION_ID);
      string sym   = HistoryDealGetString(dt,DEAL_SYMBOL);
      long   dtype = HistoryDealGetInteger(dt,DEAL_TYPE);
      if(dtype != DEAL_TYPE_BUY && dtype != DEAL_TYPE_SELL) continue;
      // Catatan penting: pada DEAL_ENTRY_OUT, DEAL_TYPE adalah arah deal penutup (kebalikan dari posisi asal!)
      string dir   = (dtype==DEAL_TYPE_BUY) ? "SELL" : "BUY";
      double vol   = HistoryDealGetDouble(dt,DEAL_VOLUME);
      double px    = HistoryDealGetDouble(dt,DEAL_PRICE);
      double prof  = HistoryDealGetDouble(dt,DEAL_PROFIT);
      double comm  = HistoryDealGetDouble(dt,DEAL_COMMISSION);
      double swap  = HistoryDealGetDouble(dt,DEAL_SWAP);
      long   rsn   = HistoryDealGetInteger(dt,DEAL_REASON);
      datetime tm  = (datetime)HistoryDealGetInteger(dt,DEAL_TIME);
      double net   = prof + comm + swap;

      int fh=FileOpen(g_ftFile, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
      if(fh==INVALID_HANDLE) continue;
      FileSeek(fh, 0, SEEK_END);
      FileWrite(fh,
         IntegerToString(ticket), IntegerToString(posId), sym, dir,
         DoubleToString(vol,2), DoubleToString(px,(int)SymbolInfoInteger(sym,SYMBOL_DIGITS)),
         DoubleToString(prof,2), DoubleToString(comm,2), DoubleToString(swap,2),
         DoubleToString(net,2), FtReason(rsn),
         TimeToString(tm, TIME_DATE|TIME_MINUTES));
      FileClose(fh);

      if(ticket>maxSeen) maxSeen=ticket;
   }
   g_ftLastTicket=maxSeen;
}

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePts);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetMarginMode();
   trade.LogLevel(LOG_LEVEL_ERRORS);
   hEmaFast =iMA(_Symbol,InpEntryTF,InpEmaFast,0,MODE_EMA,PRICE_CLOSE);
   hEmaSlow =iMA(_Symbol,InpEntryTF,InpEmaSlow,0,MODE_EMA,PRICE_CLOSE);
   hEmaTrend=iMA(_Symbol,InpTrendTF,InpEmaTrend,0,MODE_EMA,PRICE_CLOSE);
   hRsi     =iRSI(_Symbol,InpEntryTF,InpRsiPeriod,PRICE_CLOSE);
   hAtr     =iATR(_Symbol,InpEntryTF,InpAtrPeriod);

   if(hEmaFast==INVALID_HANDLE||hEmaSlow==INVALID_HANDLE||hEmaTrend==INVALID_HANDLE||
      hRsi==INVALID_HANDLE||hAtr==INVALID_HANDLE)
   { Print("[INIT] handle gagal"); return(INIT_FAILED); }
   UpdateDay();

   // Pulihkan bar M5 terakhir & state gelombang EMA supaya restart tidak memicu entry ganda.
   g_lastGoldBar=(datetime)GlobalVariableGet(GOLD_BAR_KEY);
   if(GlobalVariableCheck(GOLD_IMP_DIR_KEY))
      g_lastSignalDir=(int)GlobalVariableGet(GOLD_IMP_DIR_KEY);
   if(GlobalVariableCheck(GOLD_IMP_USED_KEY))
      g_impulseConsumed=(GlobalVariableGet(GOLD_IMP_USED_KEY)>0.5);
   if(g_lastGoldBar>0)
      PrintFormat("[INIT] resume bar Gold terakhir: %s (impDir=%d impUsed=%s)",
                  TimeToString(g_lastGoldBar,TIME_DATE|TIME_MINUTES),
                  g_lastSignalDir, (g_impulseConsumed?"ya":"tidak"));

   if(InpFixedLot>0.0)
      PrintFormat("[INIT] PERHATIAN: InpFixedLot=%.2f > 0 -> InpRiskPercent=%.2f DIABAIKAN (lot selalu tetap)",
                  InpFixedLot, InpRiskPercent);
   else
      PrintFormat("[INIT] sizing berbasis risiko aktif: %.2f%% equity per trade", InpRiskPercent);

   string btcSym = GetBtcSymbol();
   if(InpEnableBTC && btcSym != "")
   {
      SymbolSelect(btcSym, true);
      if(hBtcEmaF!=INVALID_HANDLE) IndicatorRelease(hBtcEmaF);
      if(hBtcEmaS!=INVALID_HANDLE) IndicatorRelease(hBtcEmaS);
      if(hBtcEmaT!=INVALID_HANDLE) IndicatorRelease(hBtcEmaT);
      if(hBtcRsi !=INVALID_HANDLE) IndicatorRelease(hBtcRsi);
      if(hBtcAtr !=INVALID_HANDLE) IndicatorRelease(hBtcAtr);
      if(hBtcAdx !=INVALID_HANDLE) IndicatorRelease(hBtcAdx);
      hBtcEmaF = iMA(btcSym, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
      hBtcEmaS = iMA(btcSym, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
      hBtcEmaT = iMA(btcSym, PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
      hBtcRsi  = iRSI(btcSym, PERIOD_H1, 14, PRICE_CLOSE);
      hBtcAtr  = iATR(btcSym, PERIOD_H1, 14);
      hBtcAdx  = iADX(btcSym, PERIOD_H1, InpBtcAdxPeriod);
      PrintFormat("[INIT] BTC ENGINE ATTACHED: %s (TREND H1 + ADX + ATR trail) TP=%s (%.2fR)",
                  btcSym, (InpBtcUseTp && InpBtcTpR > 0.0 ? "ON" : "OFF"), InpBtcTpR);
   }

   PrintFormat("[INIT] HEXA v3.0 %s digits=%d spread=$%.2f fixedLot=%.2f EMA=%d/%d/%d VWAP=%s SL=%.1fx TP=%.1fx Twin=%s(Sc=%.1fR/Rn=%.1fR/RnBE=%.1fR) ImpulseGuard=%s",
      _Symbol,(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS),
      SymbolInfoInteger(_Symbol,SYMBOL_SPREAD)*_Point,InpFixedLot,
      InpEmaFast,InpEmaSlow,InpEmaTrend,
      (InpUseVWAP?"on":"off"),
      InpSlAtrMult,InpTpAtrMult,
      (InpEnableTwinOrder?"ON":"OFF"), InpScalpTpR, InpRunnerTpR, InpRunnerBeTriggerR,
      (InpOneTradePerImpulse?"ON":"OFF"));
   FtInit();

   // Set initial WarRoom evaluation snapshot saat OnInit agar UI War Room langsung menampilkan indikator
   {
      double initAtr = AtrUSD();
      double initSp  = SymbolInfoInteger(_Symbol,SYMBOL_SPREAD)*_Point;
      double initRsi = IndVal(hRsi,0,1);
      double initEf  = IndVal(hEmaFast,0,1);
      double initEs  = IndVal(hEmaSlow,0,1);
      string initTr  = (initEf > initEs) ? "BULLISH" : ((initEf < initEs) ? "BEARISH" : "NETRAL");
      bool   initSs  = SessionOK();
      WarRoomSetEval(TimeCurrent(), "INIT_SIAP", initSs, initAtr, initSp, initRsi, initEf, initEs, initTr);
   }
   WarRoomInit();

   // --- [DUMP] inventaris simbol crypto, sekali jalan ---
   if(!FileIsExist("symbols_crypto.csv"))
   {
      int fh=FileOpen("symbols_crypto.csv",FILE_WRITE|FILE_CSV|FILE_ANSI,';');
      if(fh!=INVALID_HANDLE)
      {
         FileWrite(fh,"name","spread_usd","digits","tick_value","vol_min","swap_long","swap_short","trade_mode","description");
         int tot=SymbolsTotal(false), found=0;
         for(int i=0;i<tot;i++)
         {
            string s=SymbolName(i,false);
            if(s=="") continue;
            string u=s; StringToUpper(u);
            if(StringFind(u,"BTC")<0 && StringFind(u,"ETH")<0 && StringFind(u,"SOL")<0 &&
               StringFind(u,"XRP")<0 && StringFind(u,"ADA")<0 && StringFind(u,"DOGE")<0 &&
               StringFind(u,"BNB")<0 && StringFind(u,"LTC")<0 && StringFind(u,"AVAX")<0 &&
               StringFind(u,"LINK")<0 && StringFind(u,"DOT")<0) continue;
            SymbolSelect(s,true);
            double pt=SymbolInfoDouble(s,SYMBOL_POINT);
            double spr=(double)SymbolInfoInteger(s,SYMBOL_SPREAD)*pt;
            FileWrite(fh,s,DoubleToString(spr,5),
                      (string)SymbolInfoInteger(s,SYMBOL_DIGITS),
                      DoubleToString(SymbolInfoDouble(s,SYMBOL_TRADE_TICK_VALUE),5),
                      DoubleToString(SymbolInfoDouble(s,SYMBOL_VOLUME_MIN),3),
                      DoubleToString(SymbolInfoDouble(s,SYMBOL_SWAP_LONG),4),
                      DoubleToString(SymbolInfoDouble(s,SYMBOL_SWAP_SHORT),4),
                      (string)SymbolInfoInteger(s,SYMBOL_TRADE_MODE),
                      SymbolInfoString(s,SYMBOL_DESCRIPTION));
            found++;
         }
         FileClose(fh);
         PrintFormat("[DUMP] simbol crypto=%d dari total %d simbol broker -> symbols_crypto.csv",found,tot);
      }
   }

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(hEmaFast!=INVALID_HANDLE) IndicatorRelease(hEmaFast);
   if(hEmaSlow!=INVALID_HANDLE) IndicatorRelease(hEmaSlow);
   if(hEmaTrend!=INVALID_HANDLE) IndicatorRelease(hEmaTrend);
   if(hRsi!=INVALID_HANDLE) IndicatorRelease(hRsi);
   if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr);
   // BTC engine handles (dibuat sekali di OnInit, dilepas di sini)
   if(hBtcEmaF!=INVALID_HANDLE) IndicatorRelease(hBtcEmaF);
   if(hBtcEmaS!=INVALID_HANDLE) IndicatorRelease(hBtcEmaS);
   if(hBtcEmaT!=INVALID_HANDLE) IndicatorRelease(hBtcEmaT);
   if(hBtcRsi !=INVALID_HANDLE) IndicatorRelease(hBtcRsi);
   if(hBtcAtr !=INVALID_HANDLE) IndicatorRelease(hBtcAtr);
   if(hBtcAdx !=INVALID_HANDLE) IndicatorRelease(hBtcAdx);
   WarRoomDeinit();
}

void TickBody()
{
   {
      static datetime lastTickLog=0;
      if(TimeCurrent()-lastTickLog>=60)
      {
         lastTickLog=TimeCurrent();
         PrintFormat("[TICK] OnTick dipanggil %s (symbol=%s)",
                     TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS), _Symbol);
      }
   }
   CheckBtcEngine();
   UpdateDay();

   ManagePositions();
   GoldLogCheckCloses();
   {
      static datetime lastFt=0;
      if(TimeCurrent()-lastFt>=60){ FtLog(); lastFt=TimeCurrent(); }
   }
   // Flat di akhir sesi bila diaktifkan (default OFF).
   if(InpCloseAtSessionEnd && !InSessionWindow() && CountMyPositions()>0)
      CloseAllGold("sesi berakhir");

   datetime bt=iTime(_Symbol,InpEntryTF,0);
   if(bt<=0)
   {
      static datetime lastWarn=0;
      if(TimeCurrent()-lastWarn>=300)
      {
         PrintFormat("[SCAN] PERINGATAN: iTime(%s,%d) = 0 -> data bar belum tersedia, scan dilewati",
                     _Symbol,(int)InpEntryTF);
         lastWarn=TimeCurrent();
      }
      return;
   }
   if(bt==g_lastGoldBar) return;
   g_lastGoldBar=bt;
   GlobalVariableSet(GOLD_BAR_KEY,(double)bt);

   // Cek apakah gelombang EMA20/50 telah berbalik arah (reset Impulse Guard)
   double curEmaF = IndVal(hEmaFast,0,1);
   double curEmaS = IndVal(hEmaSlow,0,1);
   double curRsi  = IndVal(hRsi,0,1);
   double curAtr  = AtrUSD();
   double sp      = SymbolInfoInteger(_Symbol,SYMBOL_SPREAD)*_Point;
   string curTren = (curEmaF > curEmaS) ? "BULLISH" : ((curEmaF < curEmaS) ? "BEARISH" : "NETRAL");

   if(curEmaF > 0.0 && curEmaS > 0.0)
   {
      if((curEmaF > curEmaS && g_lastSignalDir == -1) || (curEmaF < curEmaS && g_lastSignalDir == 1))
      {
         g_impulseConsumed = false;
         GlobalVariableSet(GOLD_IMP_USED_KEY, 0.0);
      }
   }

   bool sOK = SessionOK();

   if((InpCooldownMin>0 || InpCooldownAfterCloseMin>0) && g_cooldownUntil>0 && (ulong)TimeCurrent()<g_cooldownUntil)
   {
      int remSec = (int)(g_cooldownUntil-(ulong)TimeCurrent());
      string cdWhy = StringFormat("COOLDOWN(%ds)", remSec);
      WarRoomSetEval(TimeCurrent(), cdWhy, sOK, curAtr, sp, curRsi, curEmaF, curEmaS, curTren);
      PrintFormat("[SCAN] %s cooldown sisa %d detik -> lewati bar",
                  TimeToString(bt,TIME_DATE|TIME_MINUTES), remSec);
      return;
   }

   // --- [SCANLOG] catat alasan bar dilewati & kirim ke War Room ---
   bool   spOK = SpreadOK();
   bool   rgOK = RiskGuardOK();
   int    nPos = CountMyPositions();
   int    activeLayers = 0;
   bool   canLayer = CanOpenNewLayer(activeLayers);
   double atr  = curAtr;
   bool   atrOK= (atr>=InpAtrMinUSD && atr<=InpAtrMaxUSD);
   int    sig  = (sOK && spOK && rgOK && canLayer && atrOK) ? Signal() : 0;
   bool   impBlocked = (sig!=0 && InpOneTradePerImpulse && g_impulseConsumed && sig==g_lastSignalDir);

   string why="";
   if(!sOK)             why="DI_LUAR_SESI";
   else if(!spOK)       why="SPREAD";
   else if(!rgOK)       why="RISK_GUARD";
   else if(!canLayer)   why=StringFormat("POSISI_AKTIF(pos=%d)", nPos);
   else if(!atrOK)      why=StringFormat("ATR_DI_LUAR_BATAS(%.2f)",atr);
   else if(sig==0)      why="TIDAK_ADA_SINYAL";
   else if(impBlocked)  why="IMPULSE_SUDAH_DIAMBIL";
   else                 why=StringFormat("SINYAL_%s", (sig>0?"BUY":"SELL"));

   WarRoomSetEval(TimeCurrent(), why, sOK, curAtr, sp, curRsi, curEmaF, curEmaS, curTren);

   PrintFormat("[SCAN] %s sesi=%s spread=%.2f atr=%.2f rsi=%.1f pos=%d layers=%d sig=%d -> %s",
               TimeToString(bt,TIME_DATE|TIME_MINUTES),
               (sOK?"ya":"tidak"), sp, atr, curRsi, nPos, activeLayers, sig, why);

   if(!sOK) return;
   if(!spOK) return;
   if(!rgOK) return;
   if(!canLayer) return;
   if(!atrOK) return;
   if(sig==0 || impBlocked) return;

   g_lastSignalDir = sig;
   g_impulseConsumed = true;
   GlobalVariableSet(GOLD_IMP_DIR_KEY, (double)g_lastSignalDir);
   GlobalVariableSet(GOLD_IMP_USED_KEY, 1.0);
   OpenTrade(sig);
}

void OnTimer()
{
   WarRoomPush();

   // Jalankan badan tick dari timer: di mesin ini OnTick tidak dipanggil terminal.
   TickBody();

   // [BEAT] bukti denyut: timer vs tick vs bar. Dicetak tiap ~60 detik.
   static datetime lastBeat=0;
   if(TimeCurrent()-lastBeat>=60)
   {
      lastBeat=TimeCurrent();
      MqlTick tk;
      bool tickOK=SymbolInfoTick(_Symbol,tk);
      datetime bt=iTime(_Symbol,InpEntryTF,0);
      int bars=Bars(_Symbol,InpEntryTF);
      PrintFormat("[BEAT] server=%s tick=%s bid=%.3f lastTick=%s bar0=%s bars=%d pos=%d",
                  TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),
                  (tickOK?"ya":"TIDAK"),
                  (tickOK?tk.bid:0.0),
                  (tickOK?TimeToString(tk.time,TIME_DATE|TIME_SECONDS):"-"),
                  (bt>0?TimeToString(bt,TIME_DATE|TIME_MINUTES):"NOL"),
                  bars, CountMyPositions());
   }
}

// Pembungkus: kalau terminal memanggil OnTick, jalur ini tetap dipakai.
void OnTick()
{
   TickBody();
}
