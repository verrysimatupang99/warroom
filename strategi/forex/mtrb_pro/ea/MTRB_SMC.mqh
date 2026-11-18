//+------------------------------------------------------------------+
//| MTRB_SMC.mqh                                                     |
//| Mesin SMC Gold untuk MTRB Pro: zona M15 + konfirmasi M5.         |
//| Di-include di akhir MTRB_Pro.mq5; memakai OpenStrategy (gerbang  |
//| risiko, lot, SL min/max, sesi, news, TP global) milik EA.        |
//|                                                                  |
//| Alur tiap candle M5 tertutup:                                    |
//|  1. proses candle M15 dan M5 yang baru tutup (MTRB_SMC_Core)     |
//|  2. untuk BUY dan SELL: cek kehadiran tiap pola, syarat wajib,   |
//|     opsional / skor, zona entry, trigger                         |
//|  3. lolos semua -> OpenStrategy; tiap keputusan dicatat beserta  |
//|     alasannya                                                    |
//+------------------------------------------------------------------+
#include "MTRB_SMC_Core.mqh"

input group "=== Strategi: SMC Gold (zona M15 + konfirmasi M5) ==="
input bool   InpEnableSMCG     = false;    // Mesin SMC Gold (belum diuji: mati sebagai bawaan)
input bool   InpSgBuy          = true;     // Boleh BUY
input bool   InpSgSell         = true;     // Boleh SELL
input ENUM_TIMEFRAMES InpSgHTF = PERIOD_M15; // Timeframe zona (konteks)
input ENUM_TIMEFRAMES InpSgLTF = PERIOD_M5;  // Timeframe konfirmasi dan entry
input int    InpSgScanBars     = 300;      // Candle histori yang diproses saat mulai (per timeframe)
input int    InpSgMode         = 1;        // Confluence: 0 = semua wajib, 1 = wajib + opsional, 2 = skor
input int    InpSgMinOptional  = 1;        // Mode 1: minimal pola opsional M5 yang hadir
input int    InpSgMinScore     = 60;       // Mode 2: skor minimal (0-100)
input bool   InpSgNeedHtfZone  = true;     // Harga wajib berada di minimal satu zona M15 yang dipakai
input string InpSgRoleNote     = "0 = tidak dipakai, 1 = opsional, 2 = wajib"; // Peran pola di bawah
input int    InpSgBuyOB15      = 1;        // BUY: Order Block bullish M15
input int    InpSgBuyRBR15     = 1;        // BUY: Rally-Base-Rally M15
input int    InpSgBuyRBS       = 1;        // BUY: Resistance Become Support M15
input int    InpSgBuyFVG5      = 1;        // BUY: FVG bullish M5
input int    InpSgBuyIFVG5     = 1;        // BUY: iFVG bullish M5 (terkonfirmasi)
input int    InpSgBuyOB5       = 2;        // BUY: Order Block bullish M5
input int    InpSgBuyRBR5      = 0;        // BUY: Rally-Base-Rally M5
input int    InpSgSellOB15     = 1;        // SELL: Order Block bearish M15
input int    InpSgSellDBD15    = 1;        // SELL: Drop-Base-Drop M15
input int    InpSgSellSBR      = 1;        // SELL: Support Become Resistance M15
input int    InpSgSellFVG5     = 1;        // SELL: FVG bearish M5
input int    InpSgSellIFVG5    = 1;        // SELL: iFVG bearish M5 (terkonfirmasi)
input int    InpSgSellOB5      = 2;        // SELL: Order Block bearish M5
input int    InpSgSellDBD5     = 1;        // SELL: Drop-Base-Drop M5
input int    InpSgW_OB15       = 20;       // Skor: OB M15
input int    InpSgW_RBR15      = 15;       // Skor: RBR / DBD M15
input int    InpSgW_RBS        = 15;       // Skor: RBS / SBR
input int    InpSgW_FVG5       = 15;       // Skor: FVG M5
input int    InpSgW_IFVG5      = 15;       // Skor: iFVG M5
input int    InpSgW_OB5        = 20;       // Skor: OB M5
input int    InpSgW_RBR5       = 10;       // Skor: RBR / DBD M5
input int    InpSgLtfMaxAge    = 24;       // Pola M5 dihitung hadir jika terdeteksi dalam N candle M5 terakhir
input double InpSgRbsNearAtr   = 0.50;     // RBS / SBR dihitung hadir jika harga sejauh ini dari zonanya (x ATR M15)
input int    InpSgEntryZone    = 0;        // Zona entry: 0 = OB M5, 1 = FVG / iFVG M5, 2 = zona M5 terbaru yang hadir
input int    InpSgTrigger      = 1;        // Trigger: 0 = candle M5 menyentuh zona, 1 = candle M5 masuk zona lalu menutup keluar searah entry
input int    InpSgSLMode       = 0;        // SL: 0 = balik zona entry M5, 1 = balik zona M15 yang dipakai
input double InpSgSLBufAtr     = 0.30;     // Jarak SL di balik zona (x ATR M5)
input double InpSgMaxSLAtr     = 4.0;      // Tolak jika SL lebih jauh dari ini (x ATR M5, 0 = off)
input double InpSgRR           = 2.0;      // TP = SL x ini (0 = tanpa TP)
input double InpSgMaxSpread    = 0.40;     // Spread maks (USD harga)
input int    InpSgMaxPos       = 1;        // Posisi SMC Gold maksimal bersamaan
input bool   InpSgNoOpposite   = true;     // Tolak entry jika ada posisi EA lain berlawanan arah
input group "=== SMC Gold: definisi pola ==="
input double InpSgFvgMinAtr    = 0.10;     // FVG: lebar gap minimal (x ATR)
input double InpSgFvgDispAtr   = 0.0;      // FVG: badan candle tengah minimal (x ATR, 0 = off)
input double InpSgIfvgBreakAtr = 0.10;     // iFVG: close menembus sisi seberang FVG minimal (x ATR)
input int    InpSgIfvgRetest   = 12;       // iFVG: batas menunggu retest (candle)
input double InpSgObDispAtr    = 1.0;      // OB: badan candle displacement minimal (x ATR)
input int    InpSgObBosBars    = 10;       // OB: displacement harus menutup melewati high/low N candle sebelumnya (BOS)
input int    InpSgObSearch     = 4;        // OB: cari candle berlawanan dalam N candle sebelum displacement
input bool   InpSgObWicks      = true;     // OB: zona pakai sumbu (false = badan saja)
input double InpSgImpAtr       = 0.8;      // RBR/DBD: badan impuls masuk minimal (x ATR)
input double InpSgBaseRangeAtr = 0.6;      // RBR/DBD: range tiap candle base maksimal (x ATR)
input double InpSgBaseTotalAtr = 1.0;      // RBR/DBD: lebar total base maksimal (x ATR)
input double InpSgDepartAtr    = 0.8;      // RBR/DBD: badan impuls keluar minimal (x ATR)
input int    InpSgBaseMax      = 3;        // RBR/DBD: jumlah candle base maksimal
input int    InpSgPivot        = 3;        // RBS/SBR: swing high/low = N candle kiri dan kanan
input int    InpSgRbsTouch     = 2;        // RBS/SBR: sentuhan level minimal sebelum breakout (pivot = 1)
input double InpSgRbsTolAtr    = 0.25;     // RBS/SBR: toleransi sentuhan dan lebar zona (x ATR)
input double InpSgRbsBreakAtr  = 0.20;     // RBS/SBR: close menembus level minimal (x ATR)
input int    InpSgRbsRetest    = 16;       // RBS/SBR: batas menunggu retest (candle M15)
input int    InpSgRbsLookback  = 120;      // RBS/SBR: umur level maksimal (candle M15)
input double InpSgInvalAtr     = 0.0;      // Zona batal jika close menembus sisi seberang lebih dari ini (x ATR)
input int    InpSgMaxTouches   = 2;        // Zona habis setelah N kali disentuh
input int    InpSgExpHtf       = 96;       // Umur zona M15 maksimal (candle)
input int    InpSgExpLtf       = 48;       // Umur zona M5 maksimal (candle)
input group "=== SMC Gold: tampilan dan log ==="
input bool   InpSgDraw         = true;     // Gambar zona di chart
input bool   InpSgDrawFinal    = true;     // Tetap tampilkan zona yang batal / kedaluwarsa (garis titik)
input int    InpSgKeepHours    = 24;       // Hapus zona yang sudah selesai setelah N jam
input bool   InpSgPanel        = true;     // Panel debug SMC Gold (pojok kanan atas)
input bool   InpSgLog          = true;     // Catat zona dan keputusan ke MTRB_Pro_smclog.csv

#define SG_NP 7
// pola dalam urutan panel: jenis dan timeframe
const int SG_PT[SG_NP] = {SG_OB, SG_RBR, SG_RBS, SG_FVG, SG_IFVG, SG_OB, SG_RBR};
const int SG_PF[SG_NP] = {0, 0, 0, 1, 1, 1, 1};
#define SG_MAGIC_OFS 117

struct SgEval
  {
   bool              on;
   string            state[SG_NP];
   bool              pres[SG_NP];
   int               zone[SG_NP];
   int               score, optHave, optNeed;
   string            check, decision, reason;
  };

SgParams        g_sgP;
bool            g_sgEn = false;
string          g_sgStatus = "-";
int             g_sgRole[2][SG_NP];       // [0] = BUY, [1] = SELL
int             g_sgW[SG_NP];
datetime        g_sgDone[2] = {0, 0};     // candle terakhir yang sudah diproses per timeframe
double          g_sgAtrNow[2] = {0, 0};
MqlRates        g_sgBar;                  // candle M5 tertutup terakhir
SgEval          g_sgE[2];
bool            g_sgReady = false;
uint            g_sgPanelAt = 0;

bool   SgEnabled() { return g_sgEn; }
void   SgSetEnabled(const bool on) { g_sgEn = on; }
string SgStatusText() { return g_sgStatus; }
ENUM_TIMEFRAMES SgLtf() { return InpSgLTF; }
string SgTfLabel() { return TfName(InpSgHTF) + "/" + TfName(InpSgLTF); }
long   SgMagic() { return InpMagic + SG_MAGIC_OFS; }

string SgPName(const int p, const int d) { return SgPat(SG_PT[p], d) + " " + SgTfName(SG_PF[p]); }

void SgInit()
  {
   g_sgEn = InpEnableSMCG;
   g_sgTf[0] = InpSgHTF;
   g_sgTf[1] = InpSgLTF;
   SgDefaults(g_sgP);
   g_sgP.fvgMinAtr = InpSgFvgMinAtr; g_sgP.fvgDispAtr = InpSgFvgDispAtr;
   g_sgP.ifvgOn = true; g_sgP.ifvgBreakAtr = InpSgIfvgBreakAtr; g_sgP.ifvgRetestBars = InpSgIfvgRetest;
   g_sgP.obDispAtr = InpSgObDispAtr; g_sgP.obBosBars = MathMax(2, InpSgObBosBars); g_sgP.obSearch = MathMax(1, InpSgObSearch); g_sgP.obWicks = InpSgObWicks;
   g_sgP.impAtr = InpSgImpAtr; g_sgP.baseRangeAtr = InpSgBaseRangeAtr; g_sgP.baseTotalAtr = InpSgBaseTotalAtr;
   g_sgP.departAtr = InpSgDepartAtr; g_sgP.baseMax = MathMax(1, InpSgBaseMax);
   g_sgP.pivot = MathMax(1, InpSgPivot); g_sgP.rbsMinTouch = MathMax(1, InpSgRbsTouch); g_sgP.rbsTolAtr = InpSgRbsTolAtr;
   g_sgP.rbsBreakAtr = InpSgRbsBreakAtr; g_sgP.rbsRetestBars = InpSgRbsRetest; g_sgP.rbsLookback = InpSgRbsLookback;
   g_sgP.invalAtr = MathMax(0.0, InpSgInvalAtr); g_sgP.maxTouches = MathMax(1, InpSgMaxTouches);
   g_sgP.expBars[0] = InpSgExpHtf; g_sgP.expBars[1] = InpSgExpLtf;
   int rb[SG_NP] = {InpSgBuyOB15, InpSgBuyRBR15, InpSgBuyRBS, InpSgBuyFVG5, InpSgBuyIFVG5, InpSgBuyOB5, InpSgBuyRBR5};
   int rs[SG_NP] = {InpSgSellOB15, InpSgSellDBD15, InpSgSellSBR, InpSgSellFVG5, InpSgSellIFVG5, InpSgSellOB5, InpSgSellDBD5};
   int w[SG_NP]  = {InpSgW_OB15, InpSgW_RBR15, InpSgW_RBS, InpSgW_FVG5, InpSgW_IFVG5, InpSgW_OB5, InpSgW_RBR5};
   for(int p = 0; p < SG_NP; p++)
     {
      g_sgRole[0][p] = MathMax(0, MathMin(2, rb[p]));
      g_sgRole[1][p] = MathMax(0, MathMin(2, rs[p]));
      g_sgW[p] = MathMax(0, w[p]);
     }
   ArrayResize(g_sgZ, 0);
   ArrayResize(g_sgL, 0);
   ArrayResize(g_sgEv, 0);
   g_sgDone[0] = 0; g_sgDone[1] = 0;
   g_sgReady = false;
   g_sgStatus = g_sgEn ? "Menyiapkan data" : "-";
   for(int s = 0; s < 2; s++)
     {
      g_sgE[s].on = false;
      g_sgE[s].decision = "WAITING";
      g_sgE[s].reason = "Menunggu candle M5 tutup";
      for(int p = 0; p < SG_NP; p++)
        {
         g_sgE[s].state[p] = "NOT_FOUND";
         g_sgE[s].pres[p] = false;
         g_sgE[s].zone[p] = -1;
        }
     }
   if(g_tester && InpSgLog)
      FileDelete(LogFile("smclog"), FILE_COMMON);
   if(InpSgHTF <= InpSgLTF || PeriodSeconds(InpSgHTF) % PeriodSeconds(InpSgLTF) != 0)
      Print("[SMCG] PERINGATAN: timeframe zona harus lebih besar dan kelipatan timeframe entry");
  }

void SgDeinit()
  {
   ObjectsDeleteAll(0, PFX + "sg");
  }

//+------------------------------------------------------------------+
//| Log                                                              |
//+------------------------------------------------------------------+
#define SG_LOG_HDR "time_wib,event,signal_id,dir,pattern,tf,zone_lo,zone_hi,status,detail,score,entry,sl,tp,result"

string SgWib(const datetime t) { return TimeToString(ToWib(t), TIME_DATE | TIME_SECONDS); }

void SgLog(const datetime t, const string body)
  {
   if(InpSgLog)
      AppendLine(LogFile("smclog"), SG_LOG_HDR, SgWib(t) + "," + body);
  }

// tulis event zona dari inti deteksi; saat memproses histori awal event dibuang (bukan kejadian live)
void SgDrainEvents(const bool write)
  {
   int n = ArraySize(g_sgEv);
   for(int k = 0; k < n && write; k++)
     {
      int p = StringFind(g_sgEv[k], ",");
      if(p <= 0)
         continue;
      SgLog((datetime)StringToInteger(StringSubstr(g_sgEv[k], 0, p)), StringSubstr(g_sgEv[k], p + 1) + ",,,,,");
     }
   ArrayResize(g_sgEv, 0);
  }

//+------------------------------------------------------------------+
//| Sinkronisasi data: proses candle tertutup yang belum diproses    |
//+------------------------------------------------------------------+
// mengembalikan jumlah candle baru yang diproses; -1 = data belum cukup
int SgSync(const int tfi)
  {
   int res = SgReserve(g_sgP);
   int need = MathMax(InpSgScanBars, 50) + res + 5;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int n = CopyRates(_Symbol, g_sgTf[tfi], 0, need, r);
   if(n < res + 20)
      return -1;
   int start = 0;
   if(g_sgDone[tfi] == 0)
      start = n - 1 - res;
   else if(r[1].time != g_sgDone[tfi])
     {
      start = n - 1 - res;                       // terlalu lama tidak diproses: ambil seluruh jendela
      for(int i = 2; i < n - res; i++)
         if(r[i].time == g_sgDone[tfi])
           {
            start = i - 1;
            break;
           }
     }
   int mask = (tfi == 0) ? (SGM_OB | SGM_RBR | SGM_RBS) : (SGM_FVG | SGM_OB | SGM_RBR);
   for(int i = start; i >= 1; i--)
      SgProcess(r, n, i, tfi, mask, g_sgP);
   if(start >= 1)
      g_sgDone[tfi] = r[1].time;
   g_sgAtrNow[tfi] = SgAtr(r, 1, n, g_sgP.atrPeriod);
   if(tfi == 1)
      g_sgBar = r[1];
   return start;
  }

//+------------------------------------------------------------------+
//| Validator                                                        |
//+------------------------------------------------------------------+
// zona pola p arah d yang "hadir" untuk candle M5 terakhir; state = teks status untuk panel
int SgFind(const int p, const int d, string &state)
  {
   int type = SG_PT[p], tfi = SG_PF[p];
   int last = -1, usable = -1;
   double bh = g_sgBar.high, bl = g_sgBar.low;
   for(int k = ArraySize(g_sgZ) - 1; k >= 0; k--)
     {
      if(g_sgZ[k].type != type || g_sgZ[k].dir != d || g_sgZ[k].tfi != tfi)
         continue;
      if(last < 0)
         last = k;
      if(!SgUsable(g_sgZ[k].status))
         continue;
      if(usable < 0)
         usable = k;
      bool ok;
      if(tfi == 0)
        {
         double nr = (type == SG_RBS) ? InpSgRbsNearAtr * g_sgZ[k].atr : 0.0;
         ok = (bl <= g_sgZ[k].hi + nr && bh >= g_sgZ[k].lo - nr);
        }
      else
         ok = (g_sgZ[k].age <= InpSgLtfMaxAge);
      if(ok)
        {
         state = StringFormat("%s %.2f-%.2f", SgSt(g_sgZ[k].status), g_sgZ[k].lo, g_sgZ[k].hi);
         return k;
        }
     }
   if(usable >= 0)
      state = (tfi == 0) ? StringFormat("%s, harga di luar %.2f-%.2f", SgSt(g_sgZ[usable].status), g_sgZ[usable].lo, g_sgZ[usable].hi)
                         : StringFormat("%s tapi lebih tua dari %d candle", SgSt(g_sgZ[usable].status), InpSgLtfMaxAge);
   else if(last >= 0)
      state = (g_sgZ[last].status == SG_DETECTED) ? "WAITING retest " + StringFormat("%.2f-%.2f", g_sgZ[last].lo, g_sgZ[last].hi) : SgSt(g_sgZ[last].status);
   else
      state = "NOT_FOUND";
   return -1;
  }

bool SgTriggered(const int k, const int d, string &why)
  {
   double zh = g_sgZ[k].hi, zl = g_sgZ[k].lo;
   bool ov = (g_sgBar.low <= zh && g_sgBar.high >= zl);
   if(!ov)
     {
      why = StringFormat("Trigger belum: candle M5 belum menyentuh zona %.2f-%.2f", zl, zh);
      return false;
     }
   if(InpSgTrigger == 1 && !(d == 1 ? g_sgBar.close > zh : g_sgBar.close < zl))
     {
      why = StringFormat("Trigger belum: candle M5 menyentuh zona tapi close %.2f belum keluar ke %s %.2f", g_sgBar.close, d == 1 ? "atas" : "bawah", d == 1 ? zh : zl);
      return false;
     }
   return true;
  }

// pilih zona entry M5 sesuai input; -1 bila tidak ada
int SgEntryZone(const SgEval &e)
  {
   if(InpSgEntryZone == 0)
      return e.zone[5];
   if(InpSgEntryZone == 1)
     {
      int a = e.zone[3], b = e.zone[4];
      if(a < 0) return b;
      if(b < 0) return a;
      return (g_sgZ[a].tDet >= g_sgZ[b].tDet) ? a : b;
     }
   int best = -1;
   for(int p = 3; p < SG_NP; p++)
      if(e.zone[p] >= 0 && (best < 0 || g_sgZ[e.zone[p]].tDet > g_sgZ[best].tDet))
         best = e.zone[p];
   return best;
  }

string SgUsedKey(const string id) { return "MTRB_sgu_" + id; }
bool SgIsUsed(const int k)
  {
   if(g_sgZ[k].used)
      return true;
   return (!g_tester && GlobalVariableCheck(SgUsedKey(g_sgZ[k].id)));
  }

bool SgOppositeOpen(const int d, string &why)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0 || !IsOurs())
         continue;
      int pd = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      if(pd == -d)
        {
         int e = EngByMagic(PositionGetInteger(POSITION_MAGIC));
         why = StringFormat("Ada posisi %s dari mesin %s (penjaga arah berlawanan)", pd == 1 ? "BUY" : "SELL", e >= 0 ? g_eng[e].id : "?");
         return true;
        }
     }
   return false;
  }

// evaluasi satu arah; hasil di g_sgE[s]; mengembalikan indeks zona entry bila semua syarat sinyal lolos
int SgEvaluate(const int s)
  {
   int d = (s == 0) ? 1 : -1;
   SgEval e;
   e.on = (s == 0) ? InpSgBuy : InpSgSell;
   e.score = 0; e.optHave = 0; e.optNeed = 0;
   e.check = ""; e.decision = "TOLAK"; e.reason = "";
   int wSum = 0, wHave = 0;
   bool htfAny = false, htfUsed = false, reqOk = true, allOk = true;
   string miss = "";
   for(int p = 0; p < SG_NP; p++)
     {
      e.zone[p] = -1;
      e.pres[p] = false;
      int role = g_sgRole[s][p];
      string st;
      int k = SgFind(p, d, st);
      e.state[p] = (role == 0) ? "off (" + st + ")" : st;
      if(role == 0)
         continue;
      e.zone[p] = k;
      e.pres[p] = (k >= 0);
      wSum += g_sgW[p];
      if(e.pres[p])
         wHave += g_sgW[p];
      if(SG_PF[p] == 0)
        {
         htfUsed = true;
         if(e.pres[p])
            htfAny = true;
        }
      if(!e.pres[p])
         allOk = false;
      if(role == 2 && !e.pres[p])
        {
         reqOk = false;
         miss += (miss == "" ? "" : ", ") + SgPName(p, d);
        }
      if(role == 1 && SG_PF[p] == 1)
        {
         e.optNeed++;
         if(e.pres[p])
            e.optHave++;
        }
     }
   e.score = (wSum > 0) ? (int)MathRound(100.0 * wHave / wSum) : 0;
   e.check = StringFormat("skor %d | wajib %s | opsional M5 %d/%d", e.score, reqOk ? "lengkap" : "kurang", e.optHave, InpSgMinOptional);
   int ez = -1;
   if(!e.on)
      e.reason = (d == 1 ? "BUY" : "SELL") + string(" dimatikan di input");
   else if(InpSgNeedHtfZone && htfUsed && !htfAny)
      e.reason = "Harga tidak berada di zona M15 yang dipakai";
   else if(!reqOk)
      e.reason = "Pola wajib belum ada: " + miss;
   else if(InpSgMode == 0 && !allOk)
      e.reason = "Mode semua-wajib: ada pola yang belum hadir";
   else if(InpSgMode == 1 && e.optHave < InpSgMinOptional)
      e.reason = StringFormat("Pola opsional M5 baru %d dari minimal %d", e.optHave, InpSgMinOptional);
   else if(InpSgMode == 2 && e.score < InpSgMinScore)
      e.reason = StringFormat("Skor %d < %d", e.score, InpSgMinScore);
   else
     {
      ez = SgEntryZone(e);
      string why = "";
      if(ez < 0)
         e.reason = "Tidak ada zona entry M5 (" + (InpSgEntryZone == 0 ? "OB M5" : InpSgEntryZone == 1 ? "FVG / iFVG M5" : "pola M5") + ") yang hadir";
      else if(SgIsUsed(ez))
        {
         e.reason = "Zona " + g_sgZ[ez].id + " sudah dipakai untuk entry";
         ez = -1;
        }
      else if(!SgTriggered(ez, d, why))
        {
         e.reason = why;
         ez = -1;
        }
      else
        {
         e.decision = "SINYAL";
         e.reason = "Semua syarat lolos, zona entry " + g_sgZ[ez].id;
        }
     }
   g_sgE[s] = e;
   return ez;
  }

// satu baris log keputusan per arah per candle M5 (hanya bila harga di zona M15 atau ada sinyal, supaya log tidak banjir)
void SgLogEval(const int s, const int ez, const string result, const double entry, const double sl, const double tp)
  {
   int d = (s == 0) ? 1 : -1;
   string pres = "";
   for(int p = 0; p < SG_NP; p++)
      if(g_sgE[s].pres[p])
         pres += (pres == "" ? "" : "+") + SgPName(p, d);
   string reason = g_sgE[s].reason;
   StringReplace(reason, ",", ";");
   string id = (ez >= 0) ? g_sgZ[ez].id : "";
   double lo = (ez >= 0) ? g_sgZ[ez].lo : 0, hi = (ez >= 0) ? g_sgZ[ez].hi : 0;
   SgLog(g_sgDone[1] + PeriodSeconds(g_sgTf[1]),
         StringFormat("EVAL,%s,%s,%s,%s,%.2f,%.2f,%s,%s,%d,%s,%s,%s,%s", id, d == 1 ? "BUY" : "SELL", pres == "" ? "-" : pres, SgTfName(1), lo, hi,
                      g_sgE[s].decision, reason, g_sgE[s].score, entry > 0 ? DoubleToString(entry, _Digits) : "", sl > 0 ? DoubleToString(sl, _Digits) : "",
                      tp > 0 ? DoubleToString(tp, _Digits) : "", result));
  }

void SgExecute(const int s, const int ez)
  {
   int    d   = (s == 0) ? 1 : -1;
   long   mg  = SgMagic();
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px  = (d == 1) ? ask : bid;
   string why = "";
   string fail = "";
   double atr = g_sgAtrNow[1];
   // batas SL: balik zona entry M5 atau balik zona M15 yang hadir
   double zl = g_sgZ[ez].lo, zh = g_sgZ[ez].hi;
   if(InpSgSLMode == 1)
      for(int p = 0; p < 3; p++)
        {
         int k = g_sgE[s].zone[p];
         if(k < 0)
            continue;
         zl = MathMin(zl, g_sgZ[k].lo);
         zh = MathMax(zh, g_sgZ[k].hi);
        }
   double sl = (d == 1) ? zl - InpSgSLBufAtr * atr : zh + InpSgSLBufAtr * atr;
   double slDist = d * (px - sl);
   if(IsWeekend())
      fail = "Akhir pekan";
   else if(ask - bid > InpSgMaxSpread)
      fail = StringFormat("Spread %.2f > %.2f", ask - bid, InpSgMaxSpread);
   else if(NewsBlocked(why))
      fail = "News: " + why;
   else if(CountPosMagic(mg) >= MathMax(1, InpSgMaxPos))
      fail = "Posisi SMC Gold sudah penuh";
   else if(InpSgNoOpposite && SgOppositeOpen(d, why))
      fail = why;
   else if(slDist < MinStopDist())
      fail = StringFormat("SL terlalu dekat atau harga sudah di balik SL (%.2f)", slDist);
   else if(InpSgMaxSLAtr > 0 && atr > 0 && slDist > InpSgMaxSLAtr * atr)
      fail = StringFormat("SL %.2f > %.1f ATR", slDist, InpSgMaxSLAtr);
   if(fail != "")
     {
      g_sgE[s].decision = "TOLAK";
      g_sgE[s].reason = fail;
      SgLogEval(s, ez, "REJECT", px, sl, 0);
      return;
     }
   string res = OpenStrategy(mg, d, slDist, InpSgRR, "MTRB SMCG");
   bool ok = (StringFind(res, "dibuka") >= 0);
   double tp = (InpSgRR > 0) ? px + d * slDist * InpSgRR : 0;
   if(ok)
     {
      g_sgZ[ez].used = true;
      if(!g_tester)
         GlobalVariableSet(SgUsedKey(g_sgZ[ez].id), (double)TimeCurrent());
      if(PositionSelectByTicket(trade.ResultOrder()))
        {
         px = PositionGetDouble(POSITION_PRICE_OPEN);
         sl = PositionGetDouble(POSITION_SL);
         tp = PositionGetDouble(POSITION_TP);
        }
      g_sgE[s].decision = "ENTRY";
      g_sgE[s].reason = res + " dari zona " + g_sgZ[ez].id;
      SgDrawEntry(ez, d, px, sl, tp);
     }
   else
     {
      g_sgE[s].decision = "TOLAK";
      g_sgE[s].reason = "Gerbang risiko EA: " + res;
     }
   SgLogEval(s, ez, ok ? "ENTRY " + res : "REJECT " + res, px, sl, tp);
  }

//+------------------------------------------------------------------+
//| Tampilan                                                         |
//+------------------------------------------------------------------+
color SgColor(const SgZone &z)
  {
   if(z.type == SG_OB && z.tfi == 0)
      return z.dir == 1 ? clrDodgerBlue : clrRoyalBlue;
   if(z.type == SG_OB)
      return z.dir == 1 ? clrAqua : clrSalmon;
   if(z.type == SG_FVG)
      return z.dir == 1 ? clrLimeGreen : clrRed;
   if(z.type == SG_IFVG)
      return clrYellow;
   if(z.type == SG_RBS)
      return z.dir == 1 ? clrOrange : clrDarkOrange;
   if(z.type == SG_RBR && z.tfi == 0)
      return z.dir == 1 ? clrMediumPurple : clrDarkViolet;
   return z.dir == 1 ? clrPlum : clrMagenta;
  }

bool SgCanDraw() { return InpSgDraw && (!g_tester || g_visual); }

void SgDrawZones()
  {
   bool can = SgCanDraw();
   for(int k = 0; k < ArraySize(g_sgZ); k++)
     {
      if(!g_sgZ[k].dirty)
         continue;
      g_sgZ[k].dirty = false;
      if(!can)
         continue;
      string rn = PFX + "sgz_" + g_sgZ[k].id, ln = PFX + "sgt_" + g_sgZ[k].id;
      int  st  = g_sgZ[k].status;
      bool fin = (st == SG_INVALID || st == SG_EXPIRED);
      if(fin && !InpSgDrawFinal)
        {
         ObjectDelete(0, rn);
         ObjectDelete(0, ln);
         continue;
        }
      int      per = PeriodSeconds(g_sgTf[g_sgZ[k].tfi]);
      datetime t2  = fin ? g_sgZ[k].tLast + per : TimeCurrent() + 2 * per;
      if(ObjectFind(0, rn) < 0)
        {
         ObjectCreate(0, rn, OBJ_RECTANGLE, 0, g_sgZ[k].t0, g_sgZ[k].hi, t2, g_sgZ[k].lo);
         ObjectSetInteger(0, rn, OBJPROP_BACK, true);
         ObjectSetInteger(0, rn, OBJPROP_FILL, false);
         ObjectSetInteger(0, rn, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, rn, OBJPROP_HIDDEN, true);
         ObjectCreate(0, ln, OBJ_TEXT, 0, g_sgZ[k].t0, g_sgZ[k].dir == 1 ? g_sgZ[k].lo : g_sgZ[k].hi);
         ObjectSetInteger(0, ln, OBJPROP_ANCHOR, g_sgZ[k].dir == 1 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);
         ObjectSetInteger(0, ln, OBJPROP_FONTSIZE, 7);
         ObjectSetString(0, ln, OBJPROP_FONT, "Consolas");
         ObjectSetInteger(0, ln, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, ln, OBJPROP_HIDDEN, true);
        }
      color cl = SgColor(g_sgZ[k]);
      ObjectSetInteger(0, rn, OBJPROP_TIME, 1, t2);
      ObjectSetInteger(0, rn, OBJPROP_COLOR, cl);
      ObjectSetInteger(0, rn, OBJPROP_WIDTH, g_sgZ[k].tfi == 0 ? 2 : 1);
      ObjectSetInteger(0, rn, OBJPROP_STYLE, fin ? STYLE_DOT : (st == SG_MITIGATED || st == SG_DETECTED) ? STYLE_DASH : STYLE_SOLID);
      ObjectSetInteger(0, ln, OBJPROP_COLOR, cl);
      ObjectSetString(0, ln, OBJPROP_TEXT, StringFormat("%s %s %s %s", SgPat(g_sgZ[k].type, g_sgZ[k].dir), SgTfName(g_sgZ[k].tfi),
                      g_sgZ[k].dir == 1 ? "BUY" : "SELL", SgSt(st)));
     }
  }

void SgDrawEntry(const int ez, const int d, const double px, const double sl, const double tp)
  {
   if(!SgCanDraw())
      return;
   string b = PFX + "sge_" + g_sgZ[ez].id;
   datetime t1 = TimeCurrent(), t2 = t1 + 20 * PeriodSeconds(g_sgTf[1]);
   ObjectCreate(0, b + "_a", d == 1 ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t1, px);
   ObjectCreate(0, b + "_sl", OBJ_TREND, 0, t1, sl, t2, sl);
   ObjectSetInteger(0, b + "_sl", OBJPROP_COLOR, clrTomato);
   ObjectSetInteger(0, b + "_sl", OBJPROP_RAY_RIGHT, false);
   ObjectSetString(0, b + "_sl", OBJPROP_TEXT, "SL SMCG");
   if(tp > 0)
     {
      ObjectCreate(0, b + "_tp", OBJ_TREND, 0, t1, tp, t2, tp);
      ObjectSetInteger(0, b + "_tp", OBJPROP_COLOR, clrMediumSeaGreen);
      ObjectSetInteger(0, b + "_tp", OBJPROP_RAY_RIGHT, false);
      ObjectSetString(0, b + "_tp", OBJPROP_TEXT, "TP SMCG");
     }
  }

// buang zona selesai yang lebih tua dari batas simpan, dan level yang sudah mati
void SgPrune()
  {
   datetime lim = TimeCurrent() - InpSgKeepHours * 3600;
   int n = ArraySize(g_sgZ), w = 0;
   for(int k = 0; k < n; k++)
     {
      bool fin = (g_sgZ[k].status == SG_INVALID || g_sgZ[k].status == SG_EXPIRED);
      if(fin && g_sgZ[k].tLast < lim)
        {
         ObjectDelete(0, PFX + "sgz_" + g_sgZ[k].id);
         ObjectDelete(0, PFX + "sgt_" + g_sgZ[k].id);
         continue;
        }
      if(w != k)
         g_sgZ[w] = g_sgZ[k];
      w++;
     }
   ArrayResize(g_sgZ, w);
   n = ArraySize(g_sgL);
   w = 0;
   for(int k = 0; k < n; k++)
     {
      if(g_sgL[k].dead)
         continue;
      if(w != k)
         g_sgL[w] = g_sgL[k];
      w++;
     }
   ArrayResize(g_sgL, w);
  }

void SgPLine(const int row, const string txt, const color c)
  {
   string n = PFX + "sgp_" + IntegerToString(row);
   if(ObjectFind(0, n) < 0)
     {
      ObjectCreate(0, n, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, n, OBJPROP_CORNER, CORNER_RIGHT_UPPER);
      ObjectSetInteger(0, n, OBJPROP_ANCHOR, ANCHOR_RIGHT_UPPER);
      ObjectSetInteger(0, n, OBJPROP_XDISTANCE, 12);
      ObjectSetString(0, n, OBJPROP_FONT, "Consolas");
      ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 8);
      ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, n, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, n, OBJPROP_YDISTANCE, 24 + row * 15);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetString(0, n, OBJPROP_TEXT, txt == "" ? " " : txt);
  }

void SgPanel()
  {
   if(!InpSgPanel || (g_tester && !g_visual) || !g_sgEn)
     {
      ObjectsDeleteAll(0, PFX + "sgp_");
      return;
     }
   double sp = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int row = 0;
   SgPLine(row++, StringFormat("SMC GOLD  %s  spread %.2f  %s", _Symbol, sp, g_sgReady ? "" : "(menyiapkan data)"), C_GOLD);
   SgPLine(row++, StringFormat("%s konteks: BOS terakhir %s%s", SgTfName(0), g_sgBos[0] == 1 ? "NAIK" : g_sgBos[0] == -1 ? "TURUN" : "-",
                               g_sgBosT[0] > 0 ? " (" + TimeToString(ToWib(g_sgBosT[0] + PeriodSeconds(g_sgTf[0])), TIME_MINUTES) + " WIB)" : ""), C_TEXT);
   for(int p = 0; p < SG_NP; p++)
     {
      SgPLine(row++, StringFormat("%-9s B: %s", SgPName(p, 1), Fit(g_sgE[0].state[p], 40)), g_sgE[0].pres[p] ? C_UP : C_DIM);
      SgPLine(row++, StringFormat("%-9s S: %s", SgPName(p, -1), Fit(g_sgE[1].state[p], 40)), g_sgE[1].pres[p] ? C_DN : C_DIM);
     }
   for(int s = 0; s < 2; s++)
     {
      color c = (g_sgE[s].decision == "ENTRY" || g_sgE[s].decision == "SINYAL") ? (s == 0 ? C_UP : C_DN) : C_TEXT;
      SgPLine(row++, (s == 0 ? "BUY : " : "SELL: ") + g_sgE[s].check, c);
      SgPLine(row++, "  -> " + g_sgE[s].decision + ": " + Fit(g_sgE[s].reason, 60), c);
     }
   SgPLine(row++, "Candle M5 dievaluasi: " + (g_sgDone[1] > 0 ? TimeToString(ToWib(g_sgDone[1] + PeriodSeconds(g_sgTf[1])), TIME_MINUTES) + " WIB" : "-"), C_DIM);
  }

//+------------------------------------------------------------------+
//| Dipanggil tiap tick dari OnTick                                  |
//+------------------------------------------------------------------+
void StrategySMCG()
  {
   if(!g_sgEn)
     {
      if(g_sgReady || ObjectFind(0, PFX + "sgp_0") >= 0)
        {
         ObjectsDeleteAll(0, PFX + "sg");
         g_sgReady = false;
         g_sgDone[0] = 0; g_sgDone[1] = 0;
         ArrayResize(g_sgZ, 0); ArrayResize(g_sgL, 0); ArrayResize(g_sgEv, 0);
        }
      g_sgStatus = "-";
      return;
     }
   datetime ltfBar = iTime(_Symbol, g_sgTf[1], 0);
   bool newBar = (ltfBar > 0 && (g_sgDone[1] == 0 || iTime(_Symbol, g_sgTf[1], 1) != g_sgDone[1]));
   if(newBar)
     {
      bool first = !g_sgReady;
      // timeframe besar dulu: zona M15 yang dipakai hanya dari candle M15 yang sudah tutup
      int a = SgSync(0), b = SgSync(1);
      if(a < 0 || b < 0)
        {
         g_sgStatus = "WAIT: data histori M15/M5 belum cukup";
         return;
        }
      SgDrainEvents(!first);
      g_sgReady = true;
      if(!first)
        {
         int ez[2] = {-1, -1};
         for(int s = 0; s < 2; s++)
            ez[s] = SgEvaluate(s);
         if(ez[0] >= 0 && ez[1] >= 0)
           {
            for(int s = 0; s < 2; s++)
              {
               g_sgE[s].decision = "TOLAK";
               g_sgE[s].reason = "BUY dan SELL lolos bersamaan: tidak ada entry";
               SgLogEval(s, ez[s], "REJECT konflik arah", 0, 0, 0);
              }
           }
         else
           {
            for(int s = 0; s < 2; s++)
              {
               if(ez[s] >= 0)
                  SgExecute(s, ez[s]);
               else if(g_sgE[s].on && g_sgE[s].reason != "Harga tidak berada di zona M15 yang dipakai")
                  SgLogEval(s, -1, "-", 0, 0, 0);
              }
           }
         g_sgStatus = StringFormat("BUY %s: %s | SELL %s: %s", g_sgE[0].decision, g_sgE[0].reason, g_sgE[1].decision, g_sgE[1].reason);
        }
      else
        {
         // candle pertama setelah histori: hanya untuk panel, tidak entry (sinyal di candle ini bisa sudah basi)
         for(int s = 0; s < 2; s++)
           {
            SgEvaluate(s);
            g_sgE[s].decision = "WAITING";
            g_sgE[s].reason = "Histori baru diproses; entry mulai candle " + SgTfName(1) + " berikutnya";
           }
         g_sgStatus = StringFormat("Siap: %d zona dari histori, menunggu candle %s berikutnya", ArraySize(g_sgZ), SgTfName(1));
        }
      SgPrune();
      SgDrawZones();
      SgPanel();
      g_sgPanelAt = GetTickCount();
     }
   else if(GetTickCount() - g_sgPanelAt > 1000)
     {
      SgPanel();
      g_sgPanelAt = GetTickCount();
     }
  }
