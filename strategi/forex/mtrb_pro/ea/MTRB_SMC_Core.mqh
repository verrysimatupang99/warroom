//+------------------------------------------------------------------+
//| MTRB_SMC_Core.mqh                                                |
//| Inti deteksi pola SMC Gold. Tidak bergantung pada EA, jadi bisa  |
//| dipakai EA MTRB Pro dan script validasi MTRB_SMC_Scan.           |
//|                                                                  |
//| Aturan data:                                                     |
//| - Semua deteksi memakai candle TERTUTUP (shift >= 1).            |
//| - Candle diproses berurutan dari lama ke baru. Saat candle i     |
//|   diproses, hanya candle i dan yang lebih lama yang dibaca.      |
//| - Zona hanya berubah status lewat aturan di SgProcess, dan tiap  |
//|   perubahan dicatat sebagai event beserta alasannya.             |
//+------------------------------------------------------------------+
#ifndef MTRB_SMC_CORE
#define MTRB_SMC_CORE

// jenis pola
#define SG_OB    0      // Order Block
#define SG_RBR   1      // dir +1 = Rally-Base-Rally, dir -1 = Drop-Base-Drop
#define SG_RBS   2      // dir +1 = Resistance Become Support, dir -1 = Support Become Resistance
#define SG_FVG   3      // Fair Value Gap
#define SG_IFVG  4      // Inverse FVG

// status zona
#define SG_DETECTED   0  // terdeteksi, menunggu konfirmasi (iFVG / RBS: menunggu retest)
#define SG_CONFIRMED  1  // konfirmasi retest sudah terjadi (iFVG / RBS)
#define SG_VALID      2  // zona sah, belum disentuh
#define SG_MITIGATED  3  // harga sudah masuk zona, masih bisa dipakai sampai batas sentuhan
#define SG_INVALID    4  // close menembus sisi seberang zona
#define SG_EXPIRED    5  // umur habis, retest tidak datang, atau sentuhan melebihi batas

// pola yang dideteksi pada satu timeframe
#define SGM_OB  1
#define SGM_RBR 2
#define SGM_RBS 4
#define SGM_FVG 8

struct SgParams
  {
   int               atrPeriod;
   double            fvgMinAtr, fvgDispAtr;
   bool              ifvgOn;
   double            ifvgBreakAtr;
   int               ifvgRetestBars;
   double            obDispAtr;
   int               obBosBars, obSearch;
   bool              obWicks;
   double            impAtr, baseRangeAtr, baseTotalAtr, departAtr;
   int               baseMax;
   int               pivot, rbsMinTouch, rbsRetestBars, rbsLookback;
   double            rbsTolAtr, rbsBreakAtr;
   double            invalAtr;
   int               maxTouches;
   int               expBars[2];          // umur maksimal zona: [0] timeframe besar, [1] timeframe kecil
  };

struct SgZone
  {
   string            id;
   int               type, dir, tfi;      // tfi 0 = timeframe besar (M15), 1 = timeframe kecil (M5)
   double            hi, lo, atr;
   datetime          t0;                  // candle jangkar zona (candle OB, candle tengah FVG, base pertama, pivot)
   datetime          tDet;                // waktu buka candle yang mengonfirmasi deteksi
   datetime          tConf, tLast;
   int               status, touches, age;
   bool              inside, used, dirty;
   string            why;
  };

struct SgLevel
  {
   double            px;
   datetime          t;
   int               dir, tfi, touches, age;
   bool              inside, dead;
  };

SgZone          g_sgZ[];
SgLevel         g_sgL[];
string          g_sgEv[];                 // event yang belum ditulis ke log: "detik,event,id,arah,pola,tf,low,high,status,alasan"
ENUM_TIMEFRAMES g_sgTf[2] = {PERIOD_M15, PERIOD_M5};
int             g_sgBos[2] = {0, 0};      // arah break of structure terakhir per timeframe
datetime        g_sgBosT[2] = {0, 0};

string SgTfName(const int tfi) { return StringSubstr(EnumToString(g_sgTf[tfi]), 7); }

string SgPat(const int type, const int dir)
  {
   if(type == SG_OB)
      return "OB";
   if(type == SG_RBR)
      return dir == 1 ? "RBR" : "DBD";
   if(type == SG_RBS)
      return dir == 1 ? "RBS" : "SBR";
   if(type == SG_FVG)
      return "FVG";
   return "iFVG";
  }

string SgSt(const int s)
  {
   switch(s)
     {
      case SG_DETECTED:  return "DETECTED";
      case SG_CONFIRMED: return "CONFIRMED";
      case SG_VALID:     return "VALID";
      case SG_MITIGATED: return "MITIGATED";
      case SG_INVALID:   return "INVALIDATED";
     }
   return "EXPIRED";
  }

bool SgUsable(const int s) { return (s == SG_VALID || s == SG_CONFIRMED || s == SG_MITIGATED); }

void SgDefaults(SgParams &p)
  {
   p.atrPeriod = 14;
   p.fvgMinAtr = 0.10; p.fvgDispAtr = 0.0;
   p.ifvgOn = true; p.ifvgBreakAtr = 0.10; p.ifvgRetestBars = 12;
   p.obDispAtr = 1.0; p.obBosBars = 10; p.obSearch = 4; p.obWicks = true;
   p.impAtr = 0.8; p.baseRangeAtr = 0.6; p.baseTotalAtr = 1.0; p.departAtr = 0.8; p.baseMax = 3;
   p.pivot = 3; p.rbsMinTouch = 2; p.rbsRetestBars = 16; p.rbsLookback = 120; p.rbsTolAtr = 0.25; p.rbsBreakAtr = 0.20;
   p.invalAtr = 0.0; p.maxTouches = 2; p.expBars[0] = 96; p.expBars[1] = 48;
  }

// candle lama yang dibutuhkan sebelum candle pertama bisa diproses
int SgReserve(const SgParams &p)
  {
   return p.atrPeriod + MathMax(MathMax(p.obBosBars, p.baseMax + 2), 2 * p.pivot + 1) + 3;
  }

// ATR sederhana (rata-rata true range) dari candle i dan p-1 candle sebelumnya; 0 = data kurang
double SgAtr(const MqlRates &r[], const int i, const int n, const int per)
  {
   if(per <= 0 || i + per >= n)
      return 0;
   double s = 0;
   for(int k = i; k < i + per; k++)
      s += MathMax(r[k].high, r[k + 1].close) - MathMin(r[k].low, r[k + 1].close);
   return s / per;
  }

string SgStamp(const datetime t)
  {
   MqlDateTime d;
   TimeToStruct(t, d);
   return StringFormat("%04d%02d%02d%02d%02d", d.year, d.mon, d.day, d.hour, d.min);
  }

void SgEvent(const SgZone &z, const string ev, const datetime t)
  {
   string why = z.why;
   StringReplace(why, ",", ";");
   int k = ArraySize(g_sgEv);
   ArrayResize(g_sgEv, k + 1, 64);
   g_sgEv[k] = StringFormat("%I64d,%s,%s,%s,%s,%s,%.2f,%.2f,%s,%s", (long)t, ev, z.id, z.dir == 1 ? "BUY" : "SELL",
                            SgPat(z.type, z.dir), SgTfName(z.tfi), z.lo, z.hi, SgSt(z.status), why);
  }

// waktu tutup candle yang sedang diproses (dipakai sebagai waktu event)
datetime SgCloseTime(const int tfi, const datetime open) { return open + PeriodSeconds(g_sgTf[tfi]); }

void SgSetStatus(const int k, const int st, const string why, const datetime tOpen)
  {
   g_sgZ[k].status = st;
   g_sgZ[k].why    = why;
   g_sgZ[k].tLast  = tOpen;
   g_sgZ[k].dirty  = true;
   SgEvent(g_sgZ[k], "STATUS", SgCloseTime(g_sgZ[k].tfi, tOpen));
  }

// zona baru; -1 bila zona yang sama (jenis, arah, timeframe, candle jangkar) sudah ada
int SgNewZone(const int type, const int dir, const int tfi, const double hi, const double lo, const double atr,
              const datetime t0, const datetime tDet, const int st, const string why)
  {
   for(int k = ArraySize(g_sgZ) - 1; k >= 0; k--)
      if(g_sgZ[k].type == type && g_sgZ[k].dir == dir && g_sgZ[k].tfi == tfi && g_sgZ[k].t0 == t0)
         return -1;
   int k = ArraySize(g_sgZ);
   ArrayResize(g_sgZ, k + 1, 128);
   g_sgZ[k].id      = SgPat(type, dir) + "_" + SgTfName(tfi) + "_" + (dir == 1 ? "B" : "S") + "_" + SgStamp(t0);
   g_sgZ[k].type    = type;
   g_sgZ[k].dir     = dir;
   g_sgZ[k].tfi     = tfi;
   g_sgZ[k].hi      = hi;
   g_sgZ[k].lo      = lo;
   g_sgZ[k].atr     = atr;
   g_sgZ[k].t0      = t0;
   g_sgZ[k].tDet    = tDet;
   g_sgZ[k].tConf   = (st == SG_VALID) ? tDet : 0;
   g_sgZ[k].tLast   = tDet;
   g_sgZ[k].status  = st;
   g_sgZ[k].touches = 0;
   g_sgZ[k].age     = 0;
   g_sgZ[k].inside  = false;
   g_sgZ[k].used    = false;
   g_sgZ[k].dirty   = true;
   g_sgZ[k].why     = why;
   SgEvent(g_sgZ[k], "NEW", SgCloseTime(tfi, tDet));
   return k;
  }

//+------------------------------------------------------------------+
//| Proses satu candle tertutup (indeks i pada array series r[]).    |
//| Urutan: 1) perbarui zona lama, 2) perbarui level S/R,            |
//| 3) deteksi pola baru yang selesai di candle i.                   |
//+------------------------------------------------------------------+
void SgProcess(const MqlRates &r[], const int n, const int i, const int tfi, const int mask, const SgParams &p)
  {
   if(i < 1 || i >= n)
      return;
   double atr = SgAtr(r, i, n, p.atrPeriod);
   if(atr <= 0)
      return;
   datetime t = r[i].time;
   double   o = r[i].open, h = r[i].high, l = r[i].low, c = r[i].close;

   // --- 1. zona yang sudah ada (hanya yang terdeteksi sebelum candle ini)
   int nz = ArraySize(g_sgZ);
   for(int k = 0; k < nz; k++)
     {
      if(g_sgZ[k].tfi != tfi || g_sgZ[k].tDet >= t)
         continue;
      int st = g_sgZ[k].status;
      if(st == SG_INVALID || st == SG_EXPIRED)
         continue;
      int    d  = g_sgZ[k].dir, ty = g_sgZ[k].type;
      double zh = g_sgZ[k].hi, zl = g_sgZ[k].lo, za = g_sgZ[k].atr;
      bool   ov = (l <= zh && h >= zl);
      g_sgZ[k].age++;
      g_sgZ[k].dirty = true;

      if(st == SG_DETECTED)                     // iFVG / RBS: menunggu retest
        {
         bool bad = (d == 1) ? (c < zl - p.invalAtr * za) : (c > zh + p.invalAtr * za);
         if(bad)
           {
            SgSetStatus(k, SG_INVALID, "close kembali menembus zona sebelum retest", t);
            continue;
           }
         double edge = (ty == SG_IFVG) ? ((d == 1) ? zh : zl) : (zh + zl) / 2.0;
         if(ov && d * (c - edge) > 0)
           {
            g_sgZ[k].tConf   = t;
            g_sgZ[k].touches = 1;
            g_sgZ[k].inside  = true;
            g_sgZ[k].age     = 0;
            SgSetStatus(k, SG_CONFIRMED, StringFormat("retest diterima: close %.2f di %s %.2f", c, d == 1 ? "atas" : "bawah", edge), t);
            continue;
           }
         int lim = (ty == SG_IFVG) ? p.ifvgRetestBars : p.rbsRetestBars;
         if(g_sgZ[k].age > lim)
            SgSetStatus(k, SG_EXPIRED, StringFormat("tidak ada retest dalam %d candle", lim), t);
         continue;
        }

      // zona aktif: VALID / CONFIRMED / MITIGATED
      double brk = (d == 1) ? zl - c : c - zh;  // jarak close menembus sisi seberang
      if(brk > p.invalAtr * za)
        {
         SgSetStatus(k, SG_INVALID, StringFormat("close %.2f menembus sisi seberang zona", c), t);
         if(ty == SG_FVG && p.ifvgOn && brk >= p.ifvgBreakAtr * atr)
            SgNewZone(SG_IFVG, -d, tfi, zh, zl, atr, g_sgZ[k].t0, t, SG_DETECTED,
                      StringFormat("FVG %s ditembus close %.2f (%.2f ATR); tunggu retest", d == 1 ? "bullish" : "bearish", c, brk / atr));
         continue;
        }
      if(ov && !g_sgZ[k].inside)
        {
         g_sgZ[k].touches++;
         g_sgZ[k].inside = true;
         if(g_sgZ[k].touches > p.maxTouches)
           {
            SgSetStatus(k, SG_EXPIRED, StringFormat("sentuhan ke-%d melebihi batas %d", g_sgZ[k].touches, p.maxTouches), t);
            continue;
           }
         if(st != SG_MITIGATED)
            SgSetStatus(k, SG_MITIGATED, StringFormat("harga masuk zona (sentuhan ke-%d)", g_sgZ[k].touches), t);
        }
      else if(!ov)
         g_sgZ[k].inside = false;
      if(g_sgZ[k].age > p.expBars[tfi])
         SgSetStatus(k, SG_EXPIRED, StringFormat("umur zona lebih dari %d candle", p.expBars[tfi]), t);
     }

   // --- 2. level resistance / support untuk RBS dan SBR
   if((mask & SGM_RBS) != 0)
     {
      int nl = ArraySize(g_sgL);
      for(int k = 0; k < nl; k++)
        {
         if(g_sgL[k].dead || g_sgL[k].tfi != tfi)
            continue;
         int    d  = g_sgL[k].dir;
         double px = g_sgL[k].px;
         g_sgL[k].age++;
         if(g_sgL[k].age > p.rbsLookback)
           {
            g_sgL[k].dead = true;
            continue;
           }
         if(d * (c - px) > p.rbsBreakAtr * atr)
           {
            g_sgL[k].dead = true;
            if(g_sgL[k].touches >= p.rbsMinTouch)
               SgNewZone(SG_RBS, d, tfi, px + p.rbsTolAtr * atr, px - p.rbsTolAtr * atr, atr, g_sgL[k].t, t, SG_DETECTED,
                         StringFormat("%s %.2f (%d sentuhan) ditembus close %.2f; tunggu retest", d == 1 ? "resistance" : "support", px, g_sgL[k].touches, c));
            continue;
           }
         bool near = (d == 1) ? (h >= px - p.rbsTolAtr * atr) : (l <= px + p.rbsTolAtr * atr);
         if(near && !g_sgL[k].inside)
           {
            g_sgL[k].touches++;
            g_sgL[k].inside = true;
           }
         else if(!near)
            g_sgL[k].inside = false;
        }
      // pivot baru: candle j punya high (low) tertinggi (terendah) dibanding P candle di kiri dan kanannya
      int j = i + p.pivot;
      if(j + p.pivot < n)
        {
         bool ph = true, pl = true;
         for(int q = 1; q <= p.pivot; q++)
           {
            if(r[j - q].high >= r[j].high || r[j + q].high >= r[j].high)
               ph = false;
            if(r[j - q].low <= r[j].low || r[j + q].low <= r[j].low)
               pl = false;
           }
         for(int s = 0; s < 2; s++)
           {
            if((s == 0 && !ph) || (s == 1 && !pl))
               continue;
            int k = ArraySize(g_sgL);
            ArrayResize(g_sgL, k + 1, 64);
            g_sgL[k].px      = (s == 0) ? r[j].high : r[j].low;
            g_sgL[k].t       = r[j].time;
            g_sgL[k].dir     = (s == 0) ? 1 : -1;  // resistance -> calon RBS, support -> calon SBR
            g_sgL[k].tfi     = tfi;
            g_sgL[k].touches = 1;
            g_sgL[k].age     = p.pivot;
            g_sgL[k].inside  = false;
            g_sgL[k].dead    = false;
           }
        }
     }

   // --- 3. pola baru yang selesai di candle i
   // FVG: candle 1 = i+2 (paling lama), candle 2 = i+1, candle 3 = i
   if((mask & SGM_FVG) != 0 && i + 2 < n)
     {
      double body2 = r[i + 1].close - r[i + 1].open;
      double gu = l - r[i + 2].high, gd = r[i + 2].low - h;
      if(gu >= p.fvgMinAtr * atr && gu > 0 && (p.fvgDispAtr <= 0 || body2 >= p.fvgDispAtr * atr))
         SgNewZone(SG_FVG, 1, tfi, l, r[i + 2].high, atr, r[i + 1].time, t, SG_VALID,
                   StringFormat("low candle 3 %.2f > high candle 1 %.2f; gap %.2f ATR", l, r[i + 2].high, gu / atr));
      if(gd >= p.fvgMinAtr * atr && gd > 0 && (p.fvgDispAtr <= 0 || -body2 >= p.fvgDispAtr * atr))
         SgNewZone(SG_FVG, -1, tfi, r[i + 2].low, h, atr, r[i + 1].time, t, SG_VALID,
                   StringFormat("high candle 3 %.2f < low candle 1 %.2f; gap %.2f ATR", h, r[i + 2].low, gd / atr));
     }

   // Order Block: candle i = displacement (badan >= X ATR) yang menutup melewati high/low N candle sebelumnya (BOS);
   // OB = candle berlawanan arah terakhir dalam S candle sebelum displacement. Tanpa candle berlawanan = tidak ada OB.
   if((mask & SGM_OB) != 0 && i + p.obBosBars < n)
     {
      for(int d = 1; d >= -1; d -= 2)
        {
         double body = d * (c - o);
         if(body < p.obDispAtr * atr)
            continue;
         double ext = (d == 1) ? r[i + 1].high : r[i + 1].low;
         for(int q = i + 2; q <= i + p.obBosBars; q++)
            ext = (d == 1) ? MathMax(ext, r[q].high) : MathMin(ext, r[q].low);
         if(d * (c - ext) <= 0)
            continue;
         g_sgBos[tfi]  = d;
         g_sgBosT[tfi] = t;
         int k = -1;
         for(int q = i + 1; q <= i + p.obSearch && q < n; q++)
            if(d * (r[q].close - r[q].open) < 0)
              {
               k = q;
               break;
              }
         if(k < 0)
            continue;
         double zh = p.obWicks ? r[k].high : MathMax(r[k].open, r[k].close);
         double zl = p.obWicks ? r[k].low : MathMin(r[k].open, r[k].close);
         SgNewZone(SG_OB, d, tfi, zh, zl, atr, r[k].time, t, SG_VALID,
                   StringFormat("displacement %.1f ATR; BOS close %.2f %s %.2f", body / atr, c, d == 1 ? ">" : "<", ext));
        }
     }

   // RBR / DBD: impuls masuk (leg-in) -> 1..B candle base sempit -> impuls keluar (departure) yang menutup melewati base
   if((mask & SGM_RBR) != 0)
     {
      for(int d = 1; d >= -1; d -= 2)
        {
         double dep = d * (c - o);
         if(dep < p.departAtr * atr)
            continue;
         for(int b = 1; b <= p.baseMax; b++)
           {
            int L = i + b + 1;
            if(L >= n)
               break;
            double bh = -DBL_MAX, bl = DBL_MAX;
            bool ok = true;
            for(int q = i + 1; q <= i + b; q++)
              {
               if(r[q].high - r[q].low > p.baseRangeAtr * atr)
                 {
                  ok = false;
                  break;
                 }
               bh = MathMax(bh, r[q].high);
               bl = MathMin(bl, r[q].low);
              }
            if(!ok || bh - bl > p.baseTotalAtr * atr)
               break;                            // base lebih panjang juga pasti gagal
            if((d == 1 && c <= bh) || (d == -1 && c >= bl))
               break;                            // departure tidak menutup melewati base
            double legin = d * (r[L].close - r[L].open);
            if(legin < p.impAtr * atr)
               continue;                         // coba base lebih panjang
            SgNewZone(SG_RBR, d, tfi, bh, bl, atr, r[i + b].time, t, SG_VALID,
                      StringFormat("base %d candle (lebar %.1f ATR); impuls masuk %.1f ATR; keluar %.1f ATR", b, (bh - bl) / atr, legin / atr, dep / atr));
            break;
           }
        }
     }
  }

#endif
